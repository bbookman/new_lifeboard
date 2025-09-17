"""
Unit tests for SettingsRepository implementation

These tests verify that the SettingsRepository correctly implements
the ISettingsRepository interface and maintains backward compatibility
with the original DatabaseService functionality.
"""

import pytest
import tempfile
import os
import asyncio
from datetime import datetime, timezone

from core.repositories.settings_repository import SettingsRepository
from core.repositories.interfaces import ISettingsRepository
from core.database import DatabaseService


@pytest.fixture
def temp_db_path():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def database_service(temp_db_path):
    """Create a test DatabaseService instance"""
    return DatabaseService(temp_db_path)


@pytest.fixture
def repository(database_service):
    """Create a SettingsRepository instance for testing"""
    return SettingsRepository(database_service)


class TestSettingsRepositoryInterface:
    """Test that SettingsRepository properly implements ISettingsRepository"""
    
    def test_implements_interface(self, repository):
        """Verify repository implements the interface"""
        assert isinstance(repository, ISettingsRepository)
    
    def test_has_all_interface_methods(self, repository):
        """Verify all interface methods are implemented"""
        interface_methods = [
            'get_setting', 'async_get_setting',
            'set_setting', 'async_set_setting'
        ]
        
        for method_name in interface_methods:
            assert hasattr(repository, method_name), f"Missing method: {method_name}"
            assert callable(getattr(repository, method_name)), f"Method not callable: {method_name}"


class TestSettingsRepositoryInitialization:
    """Test repository initialization and setup"""
    
    def test_initialization_with_database_service(self, database_service):
        """Test repository initialization with database service"""
        repo = SettingsRepository(database_service)
        assert repo.database_service is database_service
        assert hasattr(repo, 'logger')
    
    def test_connection_management(self, repository):
        """Test database connection context managers"""
        # Test sync connection
        with repository._get_connection() as conn:
            assert conn is not None
            # Verify connection works
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1


class TestSettingsOperations:
    """Test core settings storage and retrieval operations"""
    
    def test_set_and_get_string_setting(self, repository):
        """Test storing and retrieving a string setting"""
        key = "test_string"
        value = "test_value"
        
        repository.set_setting(key, value)
        result = repository.get_setting(key)
        
        assert result == value
    
    def test_set_and_get_dict_setting(self, repository):
        """Test storing and retrieving a dictionary setting"""
        key = "test_dict"
        value = {"name": "test", "version": 1, "enabled": True}
        
        repository.set_setting(key, value)
        result = repository.get_setting(key)
        
        assert result == value
        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["version"] == 1
        assert result["enabled"] is True
    
    def test_set_and_get_list_setting(self, repository):
        """Test storing and retrieving a list setting"""
        key = "test_list"
        value = ["item1", "item2", "item3"]
        
        repository.set_setting(key, value)
        result = repository.get_setting(key)
        
        assert result == value
        assert isinstance(result, list)
        assert len(result) == 3
    
    def test_set_and_get_number_setting(self, repository):
        """Test storing and retrieving numeric settings"""
        # Test integer
        repository.set_setting("test_int", 42)
        assert repository.get_setting("test_int") == 42
        
        # Test float
        repository.set_setting("test_float", 3.14159)
        assert repository.get_setting("test_float") == 3.14159
    
    def test_set_and_get_boolean_setting(self, repository):
        """Test storing and retrieving boolean settings"""
        repository.set_setting("test_true", True)
        repository.set_setting("test_false", False)
        
        assert repository.get_setting("test_true") is True
        assert repository.get_setting("test_false") is False
    
    def test_get_nonexistent_setting_with_default(self, repository):
        """Test retrieving nonexistent setting returns default"""
        result = repository.get_setting("nonexistent", "default_value")
        assert result == "default_value"
    
    def test_get_nonexistent_setting_without_default(self, repository):
        """Test retrieving nonexistent setting returns None"""
        result = repository.get_setting("nonexistent")
        assert result is None
    
    def test_setting_update_overwrites_previous_value(self, repository):
        """Test that updating a setting overwrites the previous value"""
        key = "test_update"
        
        # Set initial value
        repository.set_setting(key, "initial_value")
        assert repository.get_setting(key) == "initial_value"
        
        # Update value
        repository.set_setting(key, "updated_value")
        assert repository.get_setting(key) == "updated_value"
    
    def test_setting_type_conversion(self, repository):
        """Test that different types can be stored and retrieved correctly"""
        test_cases = [
            ("string_setting", "test string"),
            ("int_setting", 123),
            ("float_setting", 45.67),
            ("bool_true_setting", True),
            ("bool_false_setting", False),
            ("dict_setting", {"key": "value", "number": 42}),
            ("list_setting", [1, 2, 3, "four"]),
            ("null_setting", None)
        ]
        
        for key, value in test_cases:
            repository.set_setting(key, value)
            result = repository.get_setting(key)
            assert result == value, f"Failed for {key}: expected {value}, got {result}"


@pytest.mark.asyncio
class TestAsyncSettingsOperations:
    """Test asynchronous settings operations"""
    
    async def test_async_set_and_get_setting(self, repository):
        """Test async storing and retrieving settings"""
        key = "async_test"
        value = {"async": True, "data": [1, 2, 3]}
        
        await repository.async_set_setting(key, value)
        result = await repository.async_get_setting(key)
        
        assert result == value
        assert result["async"] is True
        assert result["data"] == [1, 2, 3]
    
    async def test_async_get_nonexistent_setting(self, repository):
        """Test async retrieval of nonexistent setting"""
        result = await repository.async_get_setting("async_nonexistent", "async_default")
        assert result == "async_default"
    
    async def test_async_setting_update(self, repository):
        """Test async setting updates"""
        key = "async_update"
        
        await repository.async_set_setting(key, "async_initial")
        assert await repository.async_get_setting(key) == "async_initial"
        
        await repository.async_set_setting(key, "async_updated")
        assert await repository.async_get_setting(key) == "async_updated"
    
    async def test_async_complex_data_types(self, repository):
        """Test async operations with complex data types"""
        complex_data = {
            "user_preferences": {
                "theme": "dark",
                "notifications": True,
                "features": ["feature1", "feature2"]
            },
            "last_login": "2024-01-01T00:00:00Z",
            "version": 1.2
        }
        
        await repository.async_set_setting("async_complex", complex_data)
        result = await repository.async_get_setting("async_complex")
        
        assert result == complex_data
        assert result["user_preferences"]["theme"] == "dark"
        assert result["user_preferences"]["notifications"] is True
        assert len(result["user_preferences"]["features"]) == 2


class TestMixedSyncAsyncOperations:
    """Test interaction between sync and async operations"""
    
    def test_sync_set_async_get(self, repository):
        """Test setting with sync method and getting with async method"""
        key = "mixed_sync_async"
        value = {"mixed": True, "test": "sync_to_async"}
        
        # Set with sync method
        repository.set_setting(key, value)
        
        # Get with async method (need to run in event loop)
        async def async_get():
            return await repository.async_get_setting(key)
        
        result = asyncio.run(async_get())
        assert result == value
    
    def test_async_set_sync_get(self, repository):
        """Test setting with async method and getting with sync method"""
        key = "mixed_async_sync"
        value = {"mixed": True, "test": "async_to_sync"}
        
        # Set with async method
        async def async_set():
            await repository.async_set_setting(key, value)
        
        asyncio.run(async_set())
        
        # Get with sync method
        result = repository.get_setting(key)
        assert result == value


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_empty_key_handling(self, repository):
        """Test handling of empty or invalid keys"""
        # Empty string key should work (it's a valid key)
        repository.set_setting("", "empty_key_value")
        assert repository.get_setting("") == "empty_key_value"
    
    def test_none_value_handling(self, repository):
        """Test handling of None values"""
        key = "none_value_test"
        repository.set_setting(key, None)
        result = repository.get_setting(key)
        assert result is None
    
    def test_large_value_handling(self, repository):
        """Test handling of large values"""
        key = "large_value"
        large_value = {"data": "x" * 10000, "numbers": list(range(1000))}
        
        repository.set_setting(key, large_value)
        result = repository.get_setting(key)
        
        assert result == large_value
        assert len(result["data"]) == 10000
        assert len(result["numbers"]) == 1000


class TestBackwardCompatibility:
    """Test backward compatibility with original DatabaseService"""
    
    def test_method_signatures_match(self, repository):
        """Verify method signatures match the interface"""
        import inspect
        from core.repositories.interfaces import ISettingsRepository
        
        # Get all methods from the interface
        interface_methods = inspect.getmembers(ISettingsRepository, predicate=inspect.isfunction)
        
        for method_name, method in interface_methods:
            if method_name.startswith('_'):
                continue
                
            # Check that repository has the method
            assert hasattr(repository, method_name), f"Repository missing method: {method_name}"
            
            # Check signature compatibility
            interface_sig = inspect.signature(method)
            repo_method = getattr(repository.__class__, method_name)
            repo_sig = inspect.signature(repo_method)
            
            # Parameters should match (excluding 'self')
            interface_params = list(interface_sig.parameters.keys())[1:]  # Skip 'self'
            repo_params = list(repo_sig.parameters.keys())[1:]  # Skip 'self'
            
            assert interface_params == repo_params, f"Parameter mismatch in {method_name}: {interface_params} vs {repo_params}"
    
    def test_data_serialization_compatibility(self, repository):
        """Test that data serialization is compatible with original implementation"""
        # Test various data types that DatabaseService handles
        test_data = [
            ("simple_string", "test"),
            ("simple_number", 42),
            ("simple_boolean", True),
            ("complex_dict", {"nested": {"data": True}, "list": [1, 2, 3]}),
            ("unicode_string", "測試中文字符"),
            ("special_chars", "!@#$%^&*()_+-={}[]|\\:;\"'<>?,./")
        ]
        
        for key, value in test_data:
            repository.set_setting(key, value)
            result = repository.get_setting(key)
            assert result == value, f"Serialization compatibility failed for {key}"