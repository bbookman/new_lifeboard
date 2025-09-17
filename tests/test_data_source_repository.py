"""
Unit tests for DataSourceRepository implementation

These tests verify that the DataSourceRepository correctly implements
the IDataSourceRepository interface and maintains backward compatibility
with the original DatabaseService functionality.
"""

import pytest
import tempfile
import os
import asyncio

from core.repositories.data_source_repository import DataSourceRepository
from core.repositories.interfaces import IDataSourceRepository
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
    """Create a DataSourceRepository instance for testing"""
    return DataSourceRepository(database_service)


class TestDataSourceRepositoryInterface:
    """Test that DataSourceRepository properly implements IDataSourceRepository"""
    
    def test_implements_interface(self, repository):
        """Verify repository implements the interface"""
        assert isinstance(repository, IDataSourceRepository)
    
    def test_has_all_interface_methods(self, repository):
        """Verify all interface methods are implemented"""
        interface_methods = [
            'register_data_source', 'async_register_data_source',
            'get_active_namespaces', 'async_get_active_namespaces',
            'update_source_item_count', 'async_update_source_item_count'
        ]
        
        for method_name in interface_methods:
            assert hasattr(repository, method_name), f"Missing method: {method_name}"
            assert callable(getattr(repository, method_name)), f"Method not callable: {method_name}"


class TestDataSourceRepositoryInitialization:
    """Test repository initialization and setup"""
    
    def test_initialization_with_database_service(self, database_service):
        """Test repository initialization with database service"""
        repo = DataSourceRepository(database_service)
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


class TestDataSourceRegistration:
    """Test data source registration operations"""
    
    def test_register_basic_data_source(self, repository):
        """Test registering a basic data source"""
        repository.register_data_source("test_namespace", "test_type")
        
        # Verify registration by checking active namespaces
        namespaces = repository.get_active_namespaces()
        assert "test_namespace" in namespaces
    
    def test_register_data_source_with_metadata(self, repository):
        """Test registering a data source with metadata"""
        metadata = {
            "api_endpoint": "https://api.example.com",
            "version": "1.0",
            "config": {"timeout": 30}
        }
        
        repository.register_data_source("test_namespace", "api_source", metadata)
        
        # Verify registration
        namespaces = repository.get_active_namespaces()
        assert "test_namespace" in namespaces
    
    def test_register_multiple_data_sources(self, repository):
        """Test registering multiple data sources"""
        sources = [
            ("namespace1", "type1", {"key1": "value1"}),
            ("namespace2", "type2", {"key2": "value2"}),
            ("namespace3", "type3", None)
        ]
        
        for namespace, source_type, metadata in sources:
            repository.register_data_source(namespace, source_type, metadata)
        
        # Verify all namespaces are registered
        namespaces = repository.get_active_namespaces()
        assert "namespace1" in namespaces
        assert "namespace2" in namespaces
        assert "namespace3" in namespaces
        assert len(namespaces) >= 3
    
    def test_register_data_source_replace_existing(self, repository):
        """Test that registering overwrites existing data source"""
        # Register initial source
        repository.register_data_source("test_namespace", "old_type", {"old": "data"})
        namespaces_initial = repository.get_active_namespaces()
        assert "test_namespace" in namespaces_initial
        
        # Replace with new data
        repository.register_data_source("test_namespace", "new_type", {"new": "data"})
        namespaces_final = repository.get_active_namespaces()
        assert "test_namespace" in namespaces_final
        
        # Should still have the same number of unique namespaces
        assert len([ns for ns in namespaces_final if ns == "test_namespace"]) == 1
    
    def test_register_empty_metadata(self, repository):
        """Test registering with empty metadata"""
        repository.register_data_source("empty_meta", "test_type", {})
        namespaces = repository.get_active_namespaces()
        assert "empty_meta" in namespaces
    
    def test_register_none_metadata(self, repository):
        """Test registering with None metadata"""
        repository.register_data_source("none_meta", "test_type", None)
        namespaces = repository.get_active_namespaces()
        assert "none_meta" in namespaces


class TestActiveNamespaces:
    """Test active namespace retrieval operations"""
    
    def test_get_active_namespaces_empty(self, repository):
        """Test getting active namespaces when none exist"""
        namespaces = repository.get_active_namespaces()
        assert namespaces == []
    
    def test_get_active_namespaces_single(self, repository):
        """Test getting a single active namespace"""
        repository.register_data_source("single_namespace", "test_type")
        namespaces = repository.get_active_namespaces()
        assert namespaces == ["single_namespace"]
    
    def test_get_active_namespaces_multiple(self, repository):
        """Test getting multiple active namespaces"""
        test_namespaces = ["namespace_a", "namespace_b", "namespace_c"]
        
        for namespace in test_namespaces:
            repository.register_data_source(namespace, "test_type")
        
        namespaces = repository.get_active_namespaces()
        for expected_namespace in test_namespaces:
            assert expected_namespace in namespaces
    
    def test_get_active_namespaces_ordering(self, repository):
        """Test that active namespaces are returned in alphabetical order"""
        test_namespaces = ["zebra", "alpha", "beta", "gamma"]
        
        # Register in random order
        for namespace in test_namespaces:
            repository.register_data_source(namespace, "test_type")
        
        namespaces = repository.get_active_namespaces()
        relevant_namespaces = [ns for ns in namespaces if ns in test_namespaces]
        assert relevant_namespaces == sorted(test_namespaces)


class TestItemCountUpdates:
    """Test item count update operations"""
    
    def test_update_source_item_count_empty(self, repository, database_service):
        """Test updating item count for namespace with no items"""
        repository.register_data_source("empty_namespace", "test_type")
        count = repository.update_source_item_count("empty_namespace")
        assert count == 0
    
    def test_update_source_item_count_with_items(self, repository, database_service):
        """Test updating item count for namespace with items"""
        # Register data source
        repository.register_data_source("test_namespace", "test_type")
        
        # Add some data items to the namespace
        for i in range(3):
            database_service.store_data_item(
                id=f"test_namespace:item_{i}",
                namespace="test_namespace",
                source_id=f"item_{i}",
                content=f"Test content {i}",
                days_date="2024-01-01"
            )
        
        # Update and verify count
        count = repository.update_source_item_count("test_namespace")
        assert count == 3
    
    def test_update_source_item_count_nonexistent_namespace(self, repository):
        """Test updating count for namespace that doesn't exist in data_sources"""
        # This should still work - it counts items even if namespace not registered
        count = repository.update_source_item_count("nonexistent_namespace")
        assert count == 0
    
    def test_update_source_item_count_return_value(self, repository, database_service):
        """Test that update_source_item_count returns the correct count"""
        repository.register_data_source("count_test", "test_type")
        
        # Start with empty
        count = repository.update_source_item_count("count_test")
        assert count == 0
        
        # Add items and verify count increases
        database_service.store_data_item(
            id="count_test:item_1",
            namespace="count_test",
            source_id="item_1",
            content="Content 1",
            days_date="2024-01-01"
        )
        count = repository.update_source_item_count("count_test")
        assert count == 1
        
        # Add more items
        database_service.store_data_item(
            id="count_test:item_2",
            namespace="count_test",
            source_id="item_2",
            content="Content 2",
            days_date="2024-01-01"
        )
        count = repository.update_source_item_count("count_test")
        assert count == 2


@pytest.mark.asyncio
class TestAsyncDataSourceOperations:
    """Test asynchronous data source operations"""
    
    async def test_async_register_data_source(self, repository):
        """Test async data source registration"""
        await repository.async_register_data_source("async_namespace", "async_type")
        
        # Verify with sync method
        namespaces = repository.get_active_namespaces()
        assert "async_namespace" in namespaces
    
    async def test_async_register_with_metadata(self, repository):
        """Test async registration with metadata"""
        metadata = {"async": True, "config": {"setting": "value"}}
        await repository.async_register_data_source("async_meta", "async_type", metadata)
        
        namespaces = repository.get_active_namespaces()
        assert "async_meta" in namespaces
    
    async def test_async_get_active_namespaces(self, repository):
        """Test async retrieval of active namespaces"""
        # Register some sources first
        await repository.async_register_data_source("async1", "type1")
        await repository.async_register_data_source("async2", "type2")
        
        # Test async retrieval
        namespaces = await repository.async_get_active_namespaces()
        assert "async1" in namespaces
        assert "async2" in namespaces
    
    async def test_async_update_source_item_count(self, repository, database_service):
        """Test async item count updates"""
        await repository.async_register_data_source("async_count", "test_type")
        
        # Add some items
        database_service.store_data_item(
            id="async_count:item_1",
            namespace="async_count",
            source_id="item_1",
            content="Async content 1",
            days_date="2024-01-01"
        )
        database_service.store_data_item(
            id="async_count:item_2",
            namespace="async_count",
            source_id="item_2",
            content="Async content 2",
            days_date="2024-01-01"
        )
        
        # Update count asynchronously
        count = await repository.async_update_source_item_count("async_count")
        assert count == 2
    
    async def test_async_empty_namespaces(self, repository):
        """Test async operations with empty namespaces"""
        namespaces = await repository.async_get_active_namespaces()
        assert namespaces == []
        
        count = await repository.async_update_source_item_count("nonexistent")
        assert count == 0


class TestMixedSyncAsyncOperations:
    """Test interaction between sync and async operations"""
    
    def test_sync_register_async_retrieve(self, repository):
        """Test registering with sync and retrieving with async"""
        repository.register_data_source("mixed_sync", "test_type")
        
        async def async_get():
            return await repository.async_get_active_namespaces()
        
        namespaces = asyncio.run(async_get())
        assert "mixed_sync" in namespaces
    
    def test_async_register_sync_retrieve(self, repository):
        """Test registering with async and retrieving with sync"""
        async def async_register():
            await repository.async_register_data_source("mixed_async", "test_type")
        
        asyncio.run(async_register())
        
        namespaces = repository.get_active_namespaces()
        assert "mixed_async" in namespaces
    
    def test_mixed_item_count_operations(self, repository, database_service):
        """Test mixed sync/async item count operations"""
        # Register with async
        async def setup():
            await repository.async_register_data_source("mixed_count", "test_type")
        asyncio.run(setup())
        
        # Add items with sync
        database_service.store_data_item(
            id="mixed_count:item_1",
            namespace="mixed_count",
            source_id="item_1",
            content="Mixed content",
            days_date="2024-01-01"
        )
        
        # Update count with sync
        sync_count = repository.update_source_item_count("mixed_count")
        assert sync_count == 1
        
        # Verify with async
        async def verify():
            return await repository.async_update_source_item_count("mixed_count")
        
        async_count = asyncio.run(verify())
        assert async_count == 1


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_register_empty_namespace(self, repository):
        """Test registering with empty namespace"""
        repository.register_data_source("", "test_type")
        namespaces = repository.get_active_namespaces()
        assert "" in namespaces
    
    def test_register_empty_source_type(self, repository):
        """Test registering with empty source type"""
        repository.register_data_source("test_namespace", "")
        namespaces = repository.get_active_namespaces()
        assert "test_namespace" in namespaces
    
    def test_complex_metadata_serialization(self, repository):
        """Test registering with complex metadata that requires JSON serialization"""
        complex_metadata = {
            "nested": {
                "deeply": {
                    "structure": ["list", "of", "items"]
                }
            },
            "numbers": [1, 2, 3, 4.5],
            "boolean": True,
            "null": None
        }
        
        repository.register_data_source("complex_meta", "test_type", complex_metadata)
        namespaces = repository.get_active_namespaces()
        assert "complex_meta" in namespaces


class TestBackwardCompatibility:
    """Test backward compatibility with original DatabaseService"""
    
    def test_method_signatures_match(self, repository):
        """Verify method signatures match the interface"""
        import inspect
        from core.repositories.interfaces import IDataSourceRepository
        
        # Get all methods from the interface
        interface_methods = inspect.getmembers(IDataSourceRepository, predicate=inspect.isfunction)
        
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
    
    def test_registration_behavior_matches_original(self, repository, database_service):
        """Test that registration behavior matches original DatabaseService"""
        # Test that INSERT OR REPLACE behavior works as expected
        repository.register_data_source("test_compat", "original_type", {"version": 1})
        namespaces_first = repository.get_active_namespaces()
        count_first = len([ns for ns in namespaces_first if ns == "test_compat"])
        
        # Register again with different data
        repository.register_data_source("test_compat", "updated_type", {"version": 2})
        namespaces_second = repository.get_active_namespaces()
        count_second = len([ns for ns in namespaces_second if ns == "test_compat"])
        
        # Should still have only one instance
        assert count_first == 1
        assert count_second == 1
    
    def test_count_update_behavior(self, repository, database_service):
        """Test that count update behavior matches original"""
        repository.register_data_source("count_compat", "test_type")
        
        # Initial count should be 0
        initial_count = repository.update_source_item_count("count_compat")
        assert initial_count == 0
        
        # Add items through DatabaseService (original method)
        database_service.store_data_item(
            id="count_compat:test_1",
            namespace="count_compat",
            source_id="test_1",
            content="Test content",
            days_date="2024-01-01"
        )
        
        # Count should update correctly
        updated_count = repository.update_source_item_count("count_compat")
        assert updated_count == 1