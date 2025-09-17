"""
Integration Test for Repository Pattern Migration

Tests that all migrated services (LLMService, ChatService, IngestionService) work correctly
with the repository pattern and maintain backward compatibility.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from core.repositories.repository_factory import RepositoryFactory
from core.repositories.data_item_repository import DataItemRepository
from core.repositories.chat_repository import ChatRepository
from core.repositories.settings_repository import SettingsRepository
from core.repositories.data_source_repository import DataSourceRepository
from core.repositories.llm_repository import LLMRepository
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from services.llm_service import LLMService
from services.chat_service import ChatService
from services.ingestion import IngestionService
from services.document_service import DocumentService
from config.models import AppConfig


@pytest.fixture
def mock_database_service():
    """Mock DatabaseService for testing"""
    mock_db = Mock(spec=DatabaseService)
    mock_db.get_connection = Mock()
    mock_db.get_async_connection = AsyncMock()
    mock_db.extract_date_from_timestamp = Mock(return_value="2025-09-17")
    return mock_db


@pytest.fixture
def repository_factory_with_mocked_repositories(mock_database_service):
    """Create RepositoryFactory with mocked repositories"""
    factory = RepositoryFactory(mock_database_service)
    
    # Mock all repository methods to avoid actual database calls
    factory._data_item_repository = Mock()
    factory._chat_repository = Mock()
    factory._settings_repository = Mock()
    factory._data_source_repository = Mock()
    factory._llm_repository = Mock()
    
    # Set up async methods
    for repo in [factory._data_item_repository, factory._chat_repository, 
                 factory._settings_repository, factory._data_source_repository, 
                 factory._llm_repository]:
        for attr_name in dir(repo):
            if attr_name.startswith('async_'):
                setattr(repo, attr_name, AsyncMock())
        
        # Add specific methods that might be missing
        if not hasattr(repo, 'async_get_database_stats'):
            repo.async_get_database_stats = AsyncMock()
        if not hasattr(repo, '__enter__'):
            repo.__enter__ = Mock(return_value=repo)
        if not hasattr(repo, '__exit__'):
            repo.__exit__ = Mock(return_value=None)
    
    return factory


@pytest.fixture
def mock_services_dependencies():
    """Mock services dependencies"""
    vector_store = Mock(spec=VectorStoreService)
    vector_store.search = Mock(return_value=[])
    vector_store.add_vector = Mock(return_value=True)
    vector_store.get_stats = Mock(return_value={"total_vectors": 100})
    
    embeddings = Mock(spec=EmbeddingService)
    embeddings.initialize = AsyncMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embeddings.embed_texts = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    
    config = Mock(spec=AppConfig)
    config.llm_provider = Mock()
    config.llm_provider.provider = "test_provider"
    config.limitless = Mock()
    config.limitless.timezone = "America/New_York"
    config.documents = Mock()
    config.documents.max_title_length = 200
    config.documents.max_content_length = 10000
    
    return vector_store, embeddings, config


class TestRepositoryPatternMigrationIntegration:
    """Integration test suite for repository pattern migration"""
    
    def test_repository_factory_creates_all_repositories(self, repository_factory_with_mocked_repositories):
        """Test that RepositoryFactory creates all required repositories"""
        factory = repository_factory_with_mocked_repositories
        
        # Test that all repositories can be retrieved
        data_item_repo = factory.get_data_item_repository()
        chat_repo = factory.get_chat_repository()
        settings_repo = factory.get_settings_repository()
        data_source_repo = factory.get_data_source_repository()
        llm_repo = factory.get_llm_repository()
        
        # Verify all repositories are created
        assert data_item_repo is not None
        assert chat_repo is not None
        assert settings_repo is not None
        assert data_source_repo is not None
        assert llm_repo is not None
        
        # Verify singleton pattern (same instance returned)
        assert factory.get_data_item_repository() is data_item_repo
        assert factory.get_chat_repository() is chat_repo
        assert factory.get_settings_repository() is settings_repo
        assert factory.get_data_source_repository() is data_source_repo
        assert factory.get_llm_repository() is llm_repo
    
    def test_llm_service_uses_repository_factory(self, repository_factory_with_mocked_repositories, mock_services_dependencies):
        """Test that LLMService properly uses RepositoryFactory"""
        vector_store, embeddings, config = mock_services_dependencies
        
        # Create DocumentService mock
        document_service = Mock(spec=DocumentService)
        
        # Create LLMService with RepositoryFactory
        llm_service = LLMService(
            repository_factory=repository_factory_with_mocked_repositories,
            document_service=document_service,
            config=config
        )
        
        # Verify repositories are properly injected
        assert llm_service.repository_factory == repository_factory_with_mocked_repositories
        assert llm_service.llm_repo is not None
        assert llm_service.data_item_repo is not None
        
        # Verify backward compatibility
        assert llm_service.database == repository_factory_with_mocked_repositories.database_service
    
    def test_chat_service_uses_repository_factory(self, repository_factory_with_mocked_repositories, mock_services_dependencies):
        """Test that ChatService properly uses RepositoryFactory"""
        vector_store, embeddings, config = mock_services_dependencies
        
        # Create ChatService with RepositoryFactory
        chat_service = ChatService(
            config=config,
            repository_factory=repository_factory_with_mocked_repositories,
            vector_store=vector_store,
            embeddings=embeddings
        )
        
        # Verify repositories are properly injected
        assert chat_service.repository_factory == repository_factory_with_mocked_repositories
        assert chat_service.chat_repo is not None
        assert chat_service.data_item_repo is not None
        
        # Verify backward compatibility
        assert chat_service.database == repository_factory_with_mocked_repositories.database_service
    
    def test_ingestion_service_uses_repository_factory(self, repository_factory_with_mocked_repositories, mock_services_dependencies):
        """Test that IngestionService properly uses RepositoryFactory"""
        vector_store, embeddings, config = mock_services_dependencies
        
        # Create IngestionService with RepositoryFactory
        ingestion_service = IngestionService(
            repository_factory=repository_factory_with_mocked_repositories,
            vector_store=vector_store,
            embedding_service=embeddings,
            config=config
        )
        
        # Verify repositories are properly injected
        assert ingestion_service.repository_factory == repository_factory_with_mocked_repositories
        assert ingestion_service.data_item_repo is not None
        assert ingestion_service.settings_repo is not None
        assert ingestion_service.data_source_repo is not None
        
        # Verify backward compatibility
        assert ingestion_service.database == repository_factory_with_mocked_repositories.database_service
    
    @pytest.mark.asyncio
    async def test_services_interact_through_repositories(self, repository_factory_with_mocked_repositories, mock_services_dependencies):
        """Test that services can interact through repositories without conflicts"""
        vector_store, embeddings, config = mock_services_dependencies
        factory = repository_factory_with_mocked_repositories
        
        # Create all migrated services
        document_service = Mock(spec=DocumentService)
        
        llm_service = LLMService(
            repository_factory=factory,
            document_service=document_service,
            config=config
        )
        
        chat_service = ChatService(
            config=config,
            repository_factory=factory,
            vector_store=vector_store,
            embeddings=embeddings
        )
        
        ingestion_service = IngestionService(
            repository_factory=factory,
            vector_store=vector_store,
            embedding_service=embeddings,
            config=config
        )
        
        # Mock repository responses for interaction testing
        factory._chat_repository.async_get_chat_history = AsyncMock(return_value=[
            {"id": 1, "user_message": "Hello", "assistant_response": "Hi!"}
        ])
        factory._llm_repository.async_get_cached_summary = AsyncMock(return_value="Test summary")
        factory._data_item_repository.async_get_database_stats = AsyncMock(return_value={"total_items": 100})
        factory._data_item_repository.async_get_pending_embeddings = AsyncMock(return_value=[])
        factory._data_item_repository.async_get_data_items_by_namespace = AsyncMock(return_value=[{"id": "test:123"}])
        factory._settings_repository.async_get_setting = AsyncMock(return_value="2025-09-17T10:00:00Z")
        
        # Test operations that use repositories
        chat_history = await chat_service.get_chat_history(limit=10)
        cached_summary = await llm_service.get_cached_summary("2025-09-17")
        ingestion_status = await ingestion_service.async_get_ingestion_status()
        
        # Verify operations succeeded
        assert len(chat_history) == 1
        assert cached_summary == "Test summary"
        assert "database_stats" in ingestion_status
        
        # Verify repositories were called correctly
        factory._chat_repository.async_get_chat_history.assert_called_once_with(10)
        factory._llm_repository.async_get_cached_summary.assert_called_once_with("2025-09-17")
        factory._data_item_repository.async_get_database_stats.assert_called()
    
    def test_repository_factory_health_check(self, repository_factory_with_mocked_repositories):
        """Test that RepositoryFactory health check works correctly"""
        factory = repository_factory_with_mocked_repositories
        
        # Perform health check
        health_status = factory.health_check()
        
        # Verify that we get a health status response
        assert isinstance(health_status, dict)
        assert len(health_status) > 0
        
        # Verify that we have checks for repository components
        repository_keys = ["data_item", "chat", "settings", "data_source", "llm"]
        present_keys = [key for key in repository_keys if key in health_status]
        assert len(present_keys) >= 4  # At least most repositories should be checked
    
    def test_backward_compatibility_preserved(self, repository_factory_with_mocked_repositories, mock_services_dependencies):
        """Test that backward compatibility is preserved for database access"""
        vector_store, embeddings, config = mock_services_dependencies
        factory = repository_factory_with_mocked_repositories
        
        # Create services
        document_service = Mock(spec=DocumentService)
        
        llm_service = LLMService(
            repository_factory=factory,
            document_service=document_service,
            config=config
        )
        
        chat_service = ChatService(
            config=config,
            repository_factory=factory,
            vector_store=vector_store,
            embeddings=embeddings
        )
        
        ingestion_service = IngestionService(
            repository_factory=factory,
            vector_store=vector_store,
            embedding_service=embeddings,
            config=config
        )
        
        # Verify all services have direct database access for backward compatibility
        assert llm_service.database == factory.database_service
        assert chat_service.database == factory.database_service
        assert ingestion_service.database == factory.database_service
        
        # Verify utility methods are still accessible
        assert hasattr(ingestion_service.database, 'extract_date_from_timestamp')
    
    def test_repository_isolation(self, repository_factory_with_mocked_repositories):
        """Test that repository instances are properly isolated"""
        factory = repository_factory_with_mocked_repositories
        
        # Get multiple instances of the same repository type
        repo1 = factory.get_data_item_repository()
        repo2 = factory.get_data_item_repository()
        
        # Should be the same instance (singleton pattern)
        assert repo1 is repo2
        
        # Different repository types should be different instances
        data_repo = factory.get_data_item_repository()
        chat_repo = factory.get_chat_repository()
        settings_repo = factory.get_settings_repository()
        
        assert data_repo is not chat_repo
        assert data_repo is not settings_repo
        assert chat_repo is not settings_repo


if __name__ == "__main__":
    pytest.main([__file__])