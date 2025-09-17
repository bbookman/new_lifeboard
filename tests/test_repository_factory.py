"""
Unit tests for RepositoryFactory implementation

These tests verify that the RepositoryFactory correctly creates and manages
all repository instances with proper dependency injection and caching behavior.
"""

import pytest
import tempfile
import os

from core.repositories.repository_factory import RepositoryFactory
from core.repositories.interfaces import (
    IDataItemRepository, ISettingsRepository, 
    IChatRepository, IDataSourceRepository
)
from core.repositories.data_item_repository import DataItemRepository
from core.repositories.settings_repository import SettingsRepository
from core.repositories.chat_repository import ChatRepository
from core.repositories.data_source_repository import DataSourceRepository
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
def factory(database_service):
    """Create a RepositoryFactory instance for testing"""
    return RepositoryFactory(database_service)


class TestRepositoryFactoryInitialization:
    """Test factory initialization and setup"""
    
    def test_initialization_with_database_service(self, database_service):
        """Test factory initialization with database service"""
        factory = RepositoryFactory(database_service)
        assert factory.database_service is database_service
        assert hasattr(factory, 'logger')
        
        # Verify cache is initialized but empty
        assert factory._data_item_repository is None
        assert factory._settings_repository is None
        assert factory._chat_repository is None
        assert factory._data_source_repository is None


class TestSingletonRepositoryCreation:
    """Test singleton repository creation (cached instances)"""
    
    def test_get_data_item_repository(self, factory):
        """Test getting DataItemRepository instance"""
        repo = factory.get_data_item_repository()
        assert isinstance(repo, IDataItemRepository)
        assert isinstance(repo, DataItemRepository)
        assert repo.database_service is factory.database_service
    
    def test_get_settings_repository(self, factory):
        """Test getting SettingsRepository instance"""
        repo = factory.get_settings_repository()
        assert isinstance(repo, ISettingsRepository)
        assert isinstance(repo, SettingsRepository)
        assert repo.database_service is factory.database_service
    
    def test_get_chat_repository(self, factory):
        """Test getting ChatRepository instance"""
        repo = factory.get_chat_repository()
        assert isinstance(repo, IChatRepository)
        assert isinstance(repo, ChatRepository)
        assert repo.database_service is factory.database_service
    
    def test_get_data_source_repository(self, factory):
        """Test getting DataSourceRepository instance"""
        repo = factory.get_data_source_repository()
        assert isinstance(repo, IDataSourceRepository)
        assert isinstance(repo, DataSourceRepository)
        assert repo.database_service is factory.database_service


class TestRepositoryCaching:
    """Test repository caching behavior"""
    
    def test_data_item_repository_caching(self, factory):
        """Test that DataItemRepository instances are cached"""
        repo1 = factory.get_data_item_repository()
        repo2 = factory.get_data_item_repository()
        assert repo1 is repo2  # Same instance
    
    def test_settings_repository_caching(self, factory):
        """Test that SettingsRepository instances are cached"""
        repo1 = factory.get_settings_repository()
        repo2 = factory.get_settings_repository()
        assert repo1 is repo2  # Same instance
    
    def test_chat_repository_caching(self, factory):
        """Test that ChatRepository instances are cached"""
        repo1 = factory.get_chat_repository()
        repo2 = factory.get_chat_repository()
        assert repo1 is repo2  # Same instance
    
    def test_data_source_repository_caching(self, factory):
        """Test that DataSourceRepository instances are cached"""
        repo1 = factory.get_data_source_repository()
        repo2 = factory.get_data_source_repository()
        assert repo1 is repo2  # Same instance
    
    def test_different_repository_types_are_different_instances(self, factory):
        """Test that different repository types create different instances"""
        data_item_repo = factory.get_data_item_repository()
        settings_repo = factory.get_settings_repository()
        chat_repo = factory.get_chat_repository()
        data_source_repo = factory.get_data_source_repository()
        
        # All should be different instances
        assert data_item_repo is not settings_repo
        assert data_item_repo is not chat_repo
        assert data_item_repo is not data_source_repo
        assert settings_repo is not chat_repo
        assert settings_repo is not data_source_repo
        assert chat_repo is not data_source_repo


class TestNonCachedRepositoryCreation:
    """Test non-cached repository creation (new instances)"""
    
    def test_create_data_item_repository(self, factory):
        """Test creating new DataItemRepository instance"""
        repo1 = factory.create_data_item_repository()
        repo2 = factory.create_data_item_repository()
        
        # Should be different instances
        assert repo1 is not repo2
        assert isinstance(repo1, DataItemRepository)
        assert isinstance(repo2, DataItemRepository)
        assert repo1.database_service is factory.database_service
        assert repo2.database_service is factory.database_service
    
    def test_create_settings_repository(self, factory):
        """Test creating new SettingsRepository instance"""
        repo1 = factory.create_settings_repository()
        repo2 = factory.create_settings_repository()
        
        # Should be different instances
        assert repo1 is not repo2
        assert isinstance(repo1, SettingsRepository)
        assert isinstance(repo2, SettingsRepository)
    
    def test_create_chat_repository(self, factory):
        """Test creating new ChatRepository instance"""
        repo1 = factory.create_chat_repository()
        repo2 = factory.create_chat_repository()
        
        # Should be different instances
        assert repo1 is not repo2
        assert isinstance(repo1, ChatRepository)
        assert isinstance(repo2, ChatRepository)
    
    def test_create_data_source_repository(self, factory):
        """Test creating new DataSourceRepository instance"""
        repo1 = factory.create_data_source_repository()
        repo2 = factory.create_data_source_repository()
        
        # Should be different instances
        assert repo1 is not repo2
        assert isinstance(repo1, DataSourceRepository)
        assert isinstance(repo2, DataSourceRepository)


class TestCacheManagement:
    """Test cache management functionality"""
    
    def test_reset_cache(self, factory):
        """Test resetting the repository cache"""
        # Get cached instances
        data_item_repo1 = factory.get_data_item_repository()
        settings_repo1 = factory.get_settings_repository()
        chat_repo1 = factory.get_chat_repository()
        data_source_repo1 = factory.get_data_source_repository()
        
        # Reset cache
        factory.reset_cache()
        
        # Get new instances
        data_item_repo2 = factory.get_data_item_repository()
        settings_repo2 = factory.get_settings_repository()
        chat_repo2 = factory.get_chat_repository()
        data_source_repo2 = factory.get_data_source_repository()
        
        # Should be different instances after cache reset
        assert data_item_repo1 is not data_item_repo2
        assert settings_repo1 is not settings_repo2
        assert chat_repo1 is not chat_repo2
        assert data_source_repo1 is not data_source_repo2
    
    def test_cache_behavior_after_reset(self, factory):
        """Test that caching works correctly after reset"""
        factory.reset_cache()
        
        # Get repositories twice after reset
        repo1 = factory.get_data_item_repository()
        repo2 = factory.get_data_item_repository()
        
        # Should be cached (same instance)
        assert repo1 is repo2


class TestGetAllRepositories:
    """Test getting all repositories at once"""
    
    def test_get_all_repositories(self, factory):
        """Test getting all repository instances"""
        repos = factory.get_all_repositories()
        
        assert isinstance(repos, dict)
        assert 'data_item' in repos
        assert 'settings' in repos
        assert 'chat' in repos
        assert 'data_source' in repos
        
        assert isinstance(repos['data_item'], IDataItemRepository)
        assert isinstance(repos['settings'], ISettingsRepository)
        assert isinstance(repos['chat'], IChatRepository)
        assert isinstance(repos['data_source'], IDataSourceRepository)
    
    def test_get_all_repositories_caching(self, factory):
        """Test that get_all_repositories returns cached instances"""
        repos1 = factory.get_all_repositories()
        repos2 = factory.get_all_repositories()
        
        # Should return the same cached instances
        assert repos1['data_item'] is repos2['data_item']
        assert repos1['settings'] is repos2['settings']
        assert repos1['chat'] is repos2['chat']
        assert repos1['data_source'] is repos2['data_source']


class TestHealthCheck:
    """Test repository health check functionality"""
    
    def test_health_check_all_healthy(self, factory):
        """Test health check when all repositories are healthy"""
        health_status = factory.health_check()
        
        assert isinstance(health_status, dict)
        assert 'data_item' in health_status
        assert 'settings' in health_status
        assert 'chat' in health_status
        assert 'data_source' in health_status
        
        # All should be healthy
        assert health_status['data_item'] == 'healthy'
        assert health_status['settings'] == 'healthy'
        assert health_status['chat'] == 'healthy'
        assert health_status['data_source'] == 'healthy'
    
    def test_health_check_creates_repositories(self, factory):
        """Test that health check creates repository instances if not cached"""
        # Ensure cache is empty
        factory.reset_cache()
        
        # Health check should create instances
        health_status = factory.health_check()
        
        # Verify repositories are now cached
        assert factory._data_item_repository is not None
        assert factory._settings_repository is not None
        assert factory._chat_repository is not None
        assert factory._data_source_repository is not None
        
        # And all should be healthy
        assert all(status == 'healthy' for status in health_status.values())


class TestFactoryIntegration:
    """Test factory integration with actual repository operations"""
    
    def test_data_item_repository_integration(self, factory):
        """Test that factory-created DataItemRepository works correctly"""
        repo = factory.get_data_item_repository()
        
        # Test basic operation
        repo.store_data_item(
            id="test:item1",
            namespace="test",
            source_id="item1",
            content="Test content",
            days_date="2024-01-01"
        )
        
        items = repo.get_data_items_by_ids(["test:item1"])
        assert len(items) == 1
        assert items[0]['content'] == "Test content"
    
    def test_settings_repository_integration(self, factory):
        """Test that factory-created SettingsRepository works correctly"""
        repo = factory.get_settings_repository()
        
        # Test basic operation
        repo.set_setting("test_key", "test_value")
        value = repo.get_setting("test_key")
        assert value == "test_value"
    
    def test_chat_repository_integration(self, factory):
        """Test that factory-created ChatRepository works correctly"""
        repo = factory.get_chat_repository()
        
        # Test basic operation
        repo.store_chat_message("Hello", "Hi there!")
        history = repo.get_chat_history(limit=1)
        assert len(history) == 1
        assert history[0]['user_message'] == "Hello"
        assert history[0]['assistant_response'] == "Hi there!"
    
    def test_data_source_repository_integration(self, factory):
        """Test that factory-created DataSourceRepository works correctly"""
        repo = factory.get_data_source_repository()
        
        # Test basic operation
        repo.register_data_source("test_namespace", "test_type")
        namespaces = repo.get_active_namespaces()
        assert "test_namespace" in namespaces


class TestFactoryErrorHandling:
    """Test factory error handling"""
    
    def test_factory_with_invalid_database_service(self):
        """Test factory behavior with invalid database service"""
        # This should not crash during factory creation
        factory = RepositoryFactory(None)
        assert factory.database_service is None
        
        # Repository creation should succeed but repository operations should fail
        repo = factory.get_data_item_repository()
        assert repo is not None
        assert repo.database_service is None
        
        # But operations on the repository should fail
        with pytest.raises(AttributeError):
            repo.store_data_item("test:id", "test", "id", "content", days_date="2024-01-01")


class TestFactoryDependencyInjection:
    """Test that dependency injection works correctly"""
    
    def test_all_repositories_share_same_database_service(self, factory):
        """Test that all repositories get the same database service instance"""
        data_item_repo = factory.get_data_item_repository()
        settings_repo = factory.get_settings_repository()
        chat_repo = factory.get_chat_repository()
        data_source_repo = factory.get_data_source_repository()
        
        # All repositories should share the same database service
        assert data_item_repo.database_service is factory.database_service
        assert settings_repo.database_service is factory.database_service
        assert chat_repo.database_service is factory.database_service
        assert data_source_repo.database_service is factory.database_service
        
        # All should be the same instance
        assert data_item_repo.database_service is settings_repo.database_service
        assert settings_repo.database_service is chat_repo.database_service
        assert chat_repo.database_service is data_source_repo.database_service
    
    def test_new_repositories_get_correct_database_service(self, factory):
        """Test that non-cached repositories also get correct database service"""
        data_item_repo = factory.create_data_item_repository()
        settings_repo = factory.create_settings_repository()
        chat_repo = factory.create_chat_repository()
        data_source_repo = factory.create_data_source_repository()
        
        # All should have the correct database service
        assert data_item_repo.database_service is factory.database_service
        assert settings_repo.database_service is factory.database_service
        assert chat_repo.database_service is factory.database_service
        assert data_source_repo.database_service is factory.database_service