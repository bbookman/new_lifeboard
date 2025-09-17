"""
Test IngestionService Repository Migration

Tests that IngestionService properly uses RepositoryFactory instead of direct DatabaseService access
and maintains backward compatibility.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from services.ingestion import IngestionService, IngestionResult
from core.repositories.repository_factory import RepositoryFactory
from core.repositories.data_item_repository import DataItemRepository
from core.repositories.settings_repository import SettingsRepository
from core.repositories.data_source_repository import DataSourceRepository
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from sources.base import DataItem, BaseSource
from config.models import AppConfig


@pytest.fixture
def mock_database_service():
    """Mock DatabaseService for testing"""
    mock_db = Mock(spec=DatabaseService)
    mock_db.extract_date_from_timestamp = Mock(return_value="2025-09-17")
    return mock_db


@pytest.fixture
def mock_data_item_repository():
    """Mock DataItemRepository for testing"""
    mock_repo = Mock(spec=DataItemRepository)
    mock_repo.async_store_data_item = AsyncMock()
    mock_repo.async_get_data_items_by_namespace = AsyncMock()
    mock_repo.async_get_pending_embeddings = AsyncMock()
    mock_repo.async_update_embedding_status = AsyncMock()
    mock_repo.async_get_database_stats = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_settings_repository():
    """Mock SettingsRepository for testing"""
    mock_repo = Mock(spec=SettingsRepository)
    mock_repo.async_get_setting = AsyncMock()
    mock_repo.async_set_setting = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_data_source_repository():
    """Mock DataSourceRepository for testing"""
    mock_repo = Mock(spec=DataSourceRepository)
    mock_repo.async_register_data_source = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_repository_factory(mock_database_service, mock_data_item_repository, 
                          mock_settings_repository, mock_data_source_repository):
    """Mock RepositoryFactory for testing"""
    mock_factory = Mock(spec=RepositoryFactory)
    mock_factory.database_service = mock_database_service
    mock_factory.get_data_item_repository.return_value = mock_data_item_repository
    mock_factory.get_settings_repository.return_value = mock_settings_repository
    mock_factory.get_data_source_repository.return_value = mock_data_source_repository
    return mock_factory


@pytest.fixture
def mock_vector_store():
    """Mock VectorStoreService for testing"""
    mock_vs = Mock(spec=VectorStoreService)
    mock_vs.add_vector = Mock(return_value=True)
    mock_vs.get_stats = Mock(return_value={"total_vectors": 100})
    return mock_vs


@pytest.fixture
def mock_embeddings():
    """Mock EmbeddingService for testing"""
    mock_emb = Mock(spec=EmbeddingService)
    mock_emb.embed_texts = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return mock_emb


@pytest.fixture
def mock_config():
    """Mock AppConfig for testing"""
    config = Mock(spec=AppConfig)
    config.limitless = Mock()
    config.limitless.timezone = "America/New_York"
    return config


@pytest.fixture
def mock_source():
    """Mock BaseSource for testing"""
    source = Mock(spec=BaseSource)
    source.namespace = "test_source"
    source.get_source_type.return_value = "test_type"
    source.fetch_items = AsyncMock()
    return source


@pytest.fixture
def ingestion_service(mock_repository_factory, mock_vector_store, mock_embeddings, mock_config):
    """Create IngestionService instance for testing"""
    service = IngestionService(
        repository_factory=mock_repository_factory,
        vector_store=mock_vector_store,
        embedding_service=mock_embeddings,
        config=mock_config
    )
    return service


class TestIngestionServiceRepositoryMigration:
    """Test suite for IngestionService repository migration"""
    
    def test_initialization_with_repository_factory(self, ingestion_service, mock_repository_factory):
        """Test that IngestionService initializes correctly with RepositoryFactory"""
        # Verify repository factory is stored
        assert ingestion_service.repository_factory == mock_repository_factory
        
        # Verify repository instances are created
        assert ingestion_service.data_item_repo is not None
        assert ingestion_service.settings_repo is not None
        assert ingestion_service.data_source_repo is not None
        
        # Verify backward compatibility - database service is still accessible
        assert ingestion_service.database == mock_repository_factory.database_service
        
        # Verify factory methods were called
        mock_repository_factory.get_data_item_repository.assert_called_once()
        mock_repository_factory.get_settings_repository.assert_called_once()
        mock_repository_factory.get_data_source_repository.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_source_uses_data_source_repository(self, ingestion_service, 
                                                             mock_data_source_repository, mock_source):
        """Test that source registration uses DataSourceRepository"""
        # Register source
        await ingestion_service.register_source(mock_source)
        
        # Verify repository method was called
        mock_data_source_repository.async_register_data_source.assert_called_once()
        call_args = mock_data_source_repository.async_register_data_source.call_args
        
        assert call_args[1]["namespace"] == "test_source"
        assert call_args[1]["source_type"] == "test_type"
        assert "registered_at" in call_args[1]["metadata"]
        
        # Verify source is stored in memory
        assert "test_source" in ingestion_service.sources
        assert ingestion_service.sources["test_source"] == mock_source
    
    @pytest.mark.asyncio
    async def test_store_data_item_uses_repository(self, ingestion_service, mock_data_item_repository):
        """Test that storing data items uses DataItemRepository"""
        # Create test data item
        test_item = DataItem(
            namespace="test",
            source_id="123",
            content="Test content",
            metadata={"test": "data"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Create result object
        result = IngestionResult()
        
        # Store processed item
        await ingestion_service._store_processed_item(test_item, result)
        
        # Verify repository method was called
        mock_data_item_repository.async_store_data_item.assert_called_once()
        call_args = mock_data_item_repository.async_store_data_item.call_args
        
        assert call_args[1]["namespace"] == "test"
        assert call_args[1]["source_id"] == "123"
        assert call_args[1]["content"] == "Test content"
        assert call_args[1]["metadata"] == {"test": "data"}
        
        # Verify result is updated
        assert result.items_stored == 1
    
    @pytest.mark.asyncio
    async def test_sync_time_tracking_uses_settings_repository(self, ingestion_service, 
                                                             mock_settings_repository, mock_source):
        """Test that sync time tracking uses SettingsRepository"""
        # Mock source fetch
        test_item = DataItem(
            namespace="test_source",
            source_id="123",
            content="Test content",
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        async def mock_fetch_items(since=None, limit=1000):
            yield test_item
        
        mock_source.fetch_items = mock_fetch_items
        
        # Register source first
        await ingestion_service.register_source(mock_source)
        
        # Mock settings calls
        mock_settings_repository.async_get_setting.return_value = None
        
        # Perform ingestion
        await ingestion_service.ingest_from_source("test_source")
        
        # Verify settings repository methods were called
        mock_settings_repository.async_get_setting.assert_called_with("test_source_last_sync")
        mock_settings_repository.async_set_setting.assert_called()
        
        # Check that set_setting was called with the correct namespace
        set_call_args = mock_settings_repository.async_set_setting.call_args
        assert set_call_args[0][0] == "test_source_last_sync"
        # The timestamp should be an ISO format string
        assert isinstance(set_call_args[0][1], str)
    
    @pytest.mark.asyncio
    async def test_embedding_processing_uses_data_item_repository(self, ingestion_service, 
                                                                mock_data_item_repository, mock_embeddings):
        """Test that embedding processing uses DataItemRepository"""
        # Mock pending embeddings
        pending_items = [
            {"id": "test:123", "content": "Test content 1"},
            {"id": "test:456", "content": "Test content 2"}
        ]
        mock_data_item_repository.async_get_pending_embeddings.return_value = pending_items
        
        # Process embeddings
        result = await ingestion_service.process_pending_embeddings(batch_size=32)
        
        # Verify repository methods were called
        mock_data_item_repository.async_get_pending_embeddings.assert_called_once_with(limit=64)
        
        # Verify embedding status updates were called (at least once for successful items)
        assert mock_data_item_repository.async_update_embedding_status.call_count >= 1
        
        # Verify embedding service was called
        mock_embeddings.embed_texts.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ingestion_status_uses_repositories(self, ingestion_service, 
                                                    mock_data_item_repository, mock_settings_repository):
        """Test that getting ingestion status uses repositories"""
        # Mock repository responses
        mock_data_item_repository.async_get_database_stats.return_value = {"total_items": 100}
        mock_data_item_repository.async_get_pending_embeddings.return_value = []
        mock_data_item_repository.async_get_data_items_by_namespace.return_value = [{"id": "test:123"}]
        mock_settings_repository.async_get_setting.return_value = "2025-09-17T10:00:00Z"
        
        # Register a test source
        mock_source = Mock(spec=BaseSource)
        mock_source.namespace = "test"
        mock_source.get_source_type.return_value = "test_type"
        ingestion_service.sources["test"] = mock_source
        
        # Get ingestion status
        status = await ingestion_service.async_get_ingestion_status()
        
        # Verify repository methods were called
        mock_data_item_repository.async_get_database_stats.assert_called_once()
        mock_data_item_repository.async_get_pending_embeddings.assert_called_once()
        mock_data_item_repository.async_get_data_items_by_namespace.assert_called_with("test", limit=1)
        mock_settings_repository.async_get_setting.assert_called_with("test_last_sync")
        
        # Verify status structure
        assert "database_stats" in status
        assert "pending_embeddings" in status
        assert "source_stats" in status
        assert "test" in status["source_stats"]
    
    def test_backward_compatibility_database_access(self, ingestion_service, mock_repository_factory):
        """Test that direct database access is still available for backward compatibility"""
        # Verify database service is accessible
        assert ingestion_service.database == mock_repository_factory.database_service
        
        # This ensures that utility methods like extract_date_from_timestamp still work
        assert hasattr(ingestion_service, 'database')
        assert ingestion_service.database is not None
    
    def test_extract_date_from_timestamp_still_uses_database(self, ingestion_service, mock_database_service):
        """Test that utility methods still use database service directly"""
        # Create test data item
        test_item = DataItem(
            namespace="test",
            source_id="123",
            content="Test content",
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Extract days_date (this should use database utility method)
        days_date = ingestion_service._extract_days_date(test_item)
        
        # Verify database utility method was called
        mock_database_service.extract_date_from_timestamp.assert_called()
        assert days_date == "2025-09-17"


if __name__ == "__main__":
    pytest.main([__file__])