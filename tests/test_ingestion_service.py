"""
Comprehensive tests for IngestionService.

This test suite covers all IngestionService functionality including data pipeline
coordination, processor management, source registration, batch processing, and
error handling across the complete ingestion workflow.
"""

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.embeddings import EmbeddingService
from core.vector_store import VectorStoreService
from services.ingestion import IngestionResult, IngestionService
from sources.base import BaseSource, DataItem
from sources.limitless_processor import BaseProcessor, LimitlessProcessor

# Using shared fixtures from tests/fixtures/
# clean_database, embedding_service, etc. are available


class MockSource(BaseSource):
    """Mock source for testing"""

    def __init__(self, namespace: str, items: List[DataItem] = None):
        super().__init__(namespace)
        self.items = items or []
        self.fetch_call_count = 0

    async def fetch_items(self, since=None, limit=1000) -> AsyncIterator[DataItem]:
        """Mock fetch implementation"""
        self.fetch_call_count += 1
        for item in self.items[:limit]:
            if since is None or (item.created_at and item.created_at > since):
                yield item

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Mock get_item implementation"""
        for item in self.items:
            if item.source_id == source_id:
                return item
        return None

    def get_source_type(self) -> str:
        return "mock"

    async def test_connection(self) -> bool:
        """Mock test_connection implementation"""
        return True


class MockProcessor(BaseProcessor):
    """Mock processor for testing"""

    def __init__(self, should_fail: bool = False):
        super().__init__()
        self.process_count = 0
        self.should_fail = should_fail

    def process(self, item: DataItem) -> DataItem:
        """Mock process implementation"""
        self.process_count += 1
        if self.should_fail:
            raise Exception("Mock processor failure")

        # Simple processing - add processed flag to metadata
        processed_metadata = item.metadata.copy() if item.metadata else {}
        processed_metadata["processed"] = True
        processed_metadata["processor"] = "mock"

        return DataItem(
            namespace=item.namespace,
            source_id=item.source_id,
            content=item.content,
            metadata=processed_metadata,
            created_at=item.created_at,
            updated_at=datetime.now(timezone.utc),
        )


class MockBatchProcessor(BaseProcessor):
    """Mock processor with batch processing capability"""

    def __init__(self, should_fail: bool = False):
        super().__init__()
        self.process_batch_count = 0
        self.should_fail = should_fail

    async def process_batch(self, items: List[DataItem]) -> List[DataItem]:
        """Mock batch process implementation"""
        self.process_batch_count += 1
        if self.should_fail:
            raise Exception("Mock batch processor failure")

        processed_items = []
        for item in items:
            processed_metadata = item.metadata.copy() if item.metadata else {}
            processed_metadata["batch_processed"] = True
            processed_metadata["processor"] = "mock_batch"

            processed_items.append(DataItem(
                namespace=item.namespace,
                source_id=item.source_id,
                content=item.content,
                metadata=processed_metadata,
                created_at=item.created_at,
                updated_at=datetime.now(timezone.utc),
            ))

        return processed_items

    def process(self, item: DataItem) -> DataItem:
        """Individual processing fallback"""
        processed_metadata = item.metadata.copy() if item.metadata else {}
        processed_metadata["individual_processed"] = True
        processed_metadata["processor"] = "mock_batch_individual"

        return DataItem(
            namespace=item.namespace,
            source_id=item.source_id,
            content=item.content,
            metadata=processed_metadata,
            created_at=item.created_at,
            updated_at=datetime.now(timezone.utc),
        )


@pytest.fixture
def mock_vector_store():
    """Create mock vector store service"""
    mock_vs = Mock(spec=VectorStoreService)
    mock_vs.add_vector.return_value = True
    mock_vs.get_stats.return_value = {"total_vectors": 100, "dimension": 384}
    return mock_vs


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service"""
    mock_es = Mock(spec=EmbeddingService)
    mock_es.embed_texts = AsyncMock(return_value=[
        [0.1] * 384,  # Mock embedding vectors
        [0.2] * 384,
        [0.3] * 384,
    ])
    return mock_es


@pytest.fixture
def ingestion_config(app_config):
    """Create ingestion service configuration"""
    return app_config


@pytest.fixture
def ingestion_service(clean_database, mock_vector_store, mock_embedding_service, ingestion_config):
    """Create IngestionService instance for testing"""
    service = IngestionService(
        database=clean_database,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        config=ingestion_config,
    )
    return service


@pytest.fixture
def sample_data_items():
    """Create sample DataItem instances for testing"""
    now = datetime.now(timezone.utc)

    return [
        DataItem(
            namespace="test",
            source_id="item_001",
            content="Test content 1",
            metadata={"title": "Test Item 1", "type": "text"},
            created_at=now,
            updated_at=now,
        ),
        DataItem(
            namespace="test",
            source_id="item_002",
            content="Test content 2",
            metadata={"title": "Test Item 2", "type": "text"},
            created_at=now,
            updated_at=now,
        ),
        DataItem(
            namespace="test",
            source_id="item_003",
            content="Test content 3",
            metadata={"title": "Test Item 3", "type": "text"},
            created_at=now,
            updated_at=now,
        ),
    ]


class TestIngestionServiceInitialization:
    """Test ingestion service initialization and setup"""

    def test_ingestion_service_initialization(self, clean_database, mock_vector_store, mock_embedding_service, ingestion_config):
        """Test successful service initialization"""
        service = IngestionService(
            database=clean_database,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=ingestion_config,
        )

        assert service.database == clean_database
        assert service.vector_store == mock_vector_store
        assert service.embedding_service == mock_embedding_service
        assert service.config == ingestion_config

        # Check processors
        assert "limitless" in service.processors
        assert isinstance(service.processors["limitless"], LimitlessProcessor)
        assert isinstance(service.default_processor, BaseProcessor)

        # Check dependencies and capabilities
        assert "DatabaseService" in service._dependencies
        assert "VectorStoreService" in service._dependencies
        assert "EmbeddingService" in service._dependencies
        assert "data_ingestion" in service._capabilities
        assert "source_management" in service._capabilities

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, ingestion_service):
        """Test complete service lifecycle"""
        # Initialize
        success = await ingestion_service.initialize()
        assert success is True
        assert ingestion_service.is_initialized

        # Health check
        health = await ingestion_service._check_service_health()
        assert health["healthy"] is True
        assert "registered_sources" in health
        assert "database_available" in health

        # Shutdown
        success = await ingestion_service._shutdown_service()
        assert success is True

    @pytest.mark.asyncio
    async def test_initialization_with_missing_dependencies(self, mock_vector_store, mock_embedding_service, ingestion_config):
        """Test initialization failure with missing dependencies"""
        service = IngestionService(
            database=None,  # Missing database
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=ingestion_config,
        )

        success = await service.initialize()
        assert success is False


class TestSourceRegistration:
    """Test source registration and management"""

    def test_register_source(self, ingestion_service, sample_data_items):
        """Test registering a new source"""
        source = MockSource("test_source", sample_data_items)

        ingestion_service.register_source(source)

        # Verify source is registered
        assert "test_source" in ingestion_service.sources
        assert ingestion_service.sources["test_source"] == source

        # Verify database registration
        # Note: Database registration is called but we can't easily verify without mocking

    def test_get_ingestion_status(self, ingestion_service, sample_data_items):
        """Test retrieving ingestion status"""
        # Register a source
        source = MockSource("test_source", sample_data_items)
        ingestion_service.register_source(source)

        status = ingestion_service.get_ingestion_status()

        assert "registered_sources" in status
        assert "test_source" in status["registered_sources"]
        assert "database_stats" in status
        assert "vector_store_stats" in status
        assert "source_stats" in status
        assert "test_source" in status["source_stats"]


class TestDataIngestion:
    """Test data ingestion workflows"""

    @pytest.mark.asyncio
    async def test_ingest_from_source_basic(self, ingestion_service, sample_data_items):
        """Test basic source ingestion"""
        source = MockSource("test_source", sample_data_items)
        ingestion_service.register_source(source)

        result = await ingestion_service.ingest_from_source("test_source")

        assert isinstance(result, IngestionResult)
        assert result.success
        assert result.items_processed == len(sample_data_items)
        assert result.items_stored == len(sample_data_items)
        assert result.items_skipped == 0
        assert len(result.errors) == 0
        assert result.start_time is not None
        assert result.end_time is not None

    @pytest.mark.asyncio
    async def test_ingest_from_source_with_limit(self, ingestion_service, sample_data_items):
        """Test source ingestion with item limit"""
        source = MockSource("test_source", sample_data_items)
        ingestion_service.register_source(source)

        result = await ingestion_service.ingest_from_source("test_source", limit=2)

        assert result.success
        assert result.items_processed == 2
        assert result.items_stored == 2

    @pytest.mark.asyncio
    async def test_ingest_from_source_force_full_sync(self, ingestion_service, sample_data_items):
        """Test force full sync ignores last sync time"""
        source = MockSource("test_source", sample_data_items)
        ingestion_service.register_source(source)

        # Set a recent last sync time
        ingestion_service.database.set_setting("test_source_last_sync", datetime.now(timezone.utc).isoformat())

        result = await ingestion_service.ingest_from_source("test_source", force_full_sync=True)

        assert result.success
        assert result.items_processed == len(sample_data_items)

    @pytest.mark.asyncio
    async def test_ingest_from_unregistered_source(self, ingestion_service):
        """Test ingestion from unregistered source raises error"""
        with pytest.raises(ValueError, match="Source nonexistent not registered"):
            await ingestion_service.ingest_from_source("nonexistent")

    @pytest.mark.asyncio
    async def test_ingest_items_direct(self, ingestion_service, sample_data_items):
        """Test direct item ingestion"""
        result = await ingestion_service.ingest_items("test_namespace", sample_data_items)

        assert isinstance(result, IngestionResult)
        assert result.success
        assert result.items_processed == len(sample_data_items)
        assert result.items_stored == len(sample_data_items)

    @pytest.mark.asyncio
    async def test_manual_ingest_item(self, ingestion_service):
        """Test manual single item ingestion"""
        content = "Manually ingested content"
        metadata = {"type": "manual", "source": "user"}

        item_id = await ingestion_service.manual_ingest_item(
            namespace="manual",
            content=content,
            metadata=metadata,
        )

        assert item_id.startswith("manual:")

        # Verify item was stored
        stored_items = ingestion_service.database.get_data_items_by_namespace("manual")
        assert len(stored_items) == 1
        assert stored_items[0]["content"] == content


class TestProcessorManagement:
    """Test processor selection and coordination"""

    @pytest.mark.asyncio
    async def test_processor_selection_registered(self, ingestion_service, sample_data_items):
        """Test that registered processor is used for namespace"""
        # Register custom processor for limitless namespace
        mock_processor = MockProcessor()
        ingestion_service.processors["limitless"] = mock_processor

        # Create items for limitless namespace
        limitless_items = [
            DataItem(
                namespace="limitless",
                source_id="limitless_001",
                content="Limitless content",
                metadata={"type": "conversation"},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        result = await ingestion_service.ingest_items("limitless", limitless_items)

        assert result.success
        assert mock_processor.process_count == 1

    @pytest.mark.asyncio
    async def test_processor_selection_default(self, ingestion_service, sample_data_items):
        """Test that default processor is used for unknown namespace"""
        # Replace default processor with mock
        mock_processor = MockProcessor()
        ingestion_service.default_processor = mock_processor

        result = await ingestion_service.ingest_items("unknown_namespace", sample_data_items)

        assert result.success
        assert mock_processor.process_count == len(sample_data_items)

    @pytest.mark.asyncio
    async def test_batch_processor_usage(self, ingestion_service, sample_data_items):
        """Test batch processor is used when available"""
        # Register batch processor
        batch_processor = MockBatchProcessor()
        ingestion_service.processors["batch_test"] = batch_processor

        # Create source with batch processor namespace
        source = MockSource("batch_test", sample_data_items)
        ingestion_service.register_source(source)

        result = await ingestion_service.ingest_from_source("batch_test")

        assert result.success
        assert batch_processor.process_batch_count == 1

        # Verify batch processing metadata was added
        stored_items = ingestion_service.database.get_data_items_by_namespace("batch_test")
        for item in stored_items:
            assert item["metadata"]["batch_processed"] is True

    @pytest.mark.asyncio
    async def test_batch_processor_fallback_to_individual(self, ingestion_service, sample_data_items):
        """Test fallback to individual processing when batch fails"""
        # Register batch processor that fails
        batch_processor = MockBatchProcessor(should_fail=True)
        ingestion_service.processors["batch_fail"] = batch_processor

        source = MockSource("batch_fail", sample_data_items)
        ingestion_service.register_source(source)

        result = await ingestion_service.ingest_from_source("batch_fail")

        assert result.success
        assert batch_processor.process_batch_count == 1  # Batch was attempted

        # Verify fallback to individual processing occurred
        stored_items = ingestion_service.database.get_data_items_by_namespace("batch_fail")
        for item in stored_items:
            assert item["metadata"]["individual_processed"] is True


class TestEmbeddingProcessing:
    """Test embedding generation and processing"""

    @pytest.mark.asyncio
    async def test_process_pending_embeddings_basic(self, ingestion_service, sample_data_items):
        """Test basic pending embeddings processing"""
        # First ingest some items
        result = await ingestion_service.ingest_items("test_embeddings", sample_data_items)
        assert result.success

        # Process pending embeddings
        embedding_result = await ingestion_service.process_pending_embeddings()

        assert embedding_result["processed"] > 0
        assert embedding_result["successful"] > 0
        assert embedding_result["failed"] == 0
        assert len(embedding_result["errors"]) == 0

        # Verify embedding service was called
        ingestion_service.embedding_service.embed_texts.assert_called()

        # Verify vector store was called
        ingestion_service.vector_store.add_vector.assert_called()

    @pytest.mark.asyncio
    async def test_process_pending_embeddings_with_batch_size(self, ingestion_service, sample_data_items):
        """Test embedding processing with custom batch size"""
        # Ingest items
        await ingestion_service.ingest_items("test_batch", sample_data_items)

        # Process with small batch size
        result = await ingestion_service.process_pending_embeddings(batch_size=2)

        assert result["processed"] > 0
        # Should process in batches of 2

    @pytest.mark.asyncio
    async def test_process_pending_embeddings_no_items(self, ingestion_service):
        """Test embedding processing when no items are pending"""
        result = await ingestion_service.process_pending_embeddings()

        assert result["processed"] == 0
        assert result["successful"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_process_pending_embeddings_vector_store_failure(self, ingestion_service, sample_data_items):
        """Test handling vector store failures during embedding processing"""
        # Make vector store fail
        ingestion_service.vector_store.add_vector.return_value = False

        # Ingest items
        await ingestion_service.ingest_items("test_fail", sample_data_items)

        # Process embeddings
        result = await ingestion_service.process_pending_embeddings()

        assert result["processed"] > 0
        assert result["failed"] > 0
        assert result["successful"] == 0
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_process_pending_embeddings_service_failure(self, ingestion_service, sample_data_items):
        """Test handling embedding service failures"""
        # Make embedding service fail
        ingestion_service.embedding_service.embed_texts.side_effect = Exception("Embedding failed")

        # Ingest items
        await ingestion_service.ingest_items("test_embed_fail", sample_data_items)

        # Process embeddings
        result = await ingestion_service.process_pending_embeddings()

        assert result["processed"] > 0
        assert result["failed"] > 0
        assert len(result["errors"]) > 0


class TestBulkOperations:
    """Test bulk ingestion operations"""

    @pytest.mark.asyncio
    async def test_full_sync_all_sources(self, ingestion_service, sample_data_items):
        """Test full sync across all registered sources"""
        # Register multiple sources
        source1 = MockSource("source1", sample_data_items[:2])
        source2 = MockSource("source2", sample_data_items[2:])

        ingestion_service.register_source(source1)
        ingestion_service.register_source(source2)

        results = await ingestion_service.full_sync_all_sources()

        assert len(results) == 2
        assert "source1" in results
        assert "source2" in results

        for namespace, result in results.items():
            assert isinstance(result, IngestionResult)
            assert result.success
            assert result.items_processed > 0

    @pytest.mark.asyncio
    async def test_incremental_sync_all_sources(self, ingestion_service, sample_data_items):
        """Test incremental sync across all registered sources"""
        # Register sources
        source1 = MockSource("inc_source1", sample_data_items[:2])
        source2 = MockSource("inc_source2", sample_data_items[2:])

        ingestion_service.register_source(source1)
        ingestion_service.register_source(source2)

        results = await ingestion_service.incremental_sync_all_sources()

        assert len(results) == 2
        assert "inc_source1" in results
        assert "inc_source2" in results

        for result in results.values():
            assert isinstance(result, IngestionResult)
            assert result.success

    @pytest.mark.asyncio
    async def test_bulk_sync_with_source_failure(self, ingestion_service, sample_data_items):
        """Test bulk sync handling individual source failures"""
        # Create a source that will fail
        failing_source = MockSource("failing_source", sample_data_items)

        # Mock the source to raise an exception
        async def failing_fetch(*args, **kwargs):
            raise Exception("Source fetch failed")
            yield  # This line will never be reached, but it makes this a generator

        failing_source.fetch_items = failing_fetch

        # Register normal and failing sources
        normal_source = MockSource("normal_source", sample_data_items)
        ingestion_service.register_source(normal_source)
        ingestion_service.register_source(failing_source)

        results = await ingestion_service.full_sync_all_sources()

        assert len(results) == 2
        assert results["normal_source"].success
        assert not results["failing_source"].success
        assert len(results["failing_source"].errors) > 0


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_processor_failure_handling(self, ingestion_service, sample_data_items):
        """Test handling processor failures"""
        # Register failing processor
        failing_processor = MockProcessor(should_fail=True)
        ingestion_service.processors["failing"] = failing_processor

        # Create items that will trigger processor failure
        failing_items = [
            DataItem(
                namespace="failing",
                source_id="fail_001",
                content="This will fail",
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        result = await ingestion_service.ingest_items("failing", failing_items)

        # Should handle errors gracefully
        assert not result.success
        assert len(result.errors) > 0
        assert result.items_processed == 1
        assert result.items_stored == 0

    @pytest.mark.asyncio
    async def test_database_storage_failure(self, ingestion_service, sample_data_items):
        """Test handling database storage failures"""
        # Mock database to fail storage
        original_store = ingestion_service.database.store_data_item
        ingestion_service.database.store_data_item = Mock(side_effect=Exception("Database error"))

        result = await ingestion_service.ingest_items("db_fail", sample_data_items)

        assert not result.success
        assert len(result.errors) > 0
        assert result.items_processed == len(sample_data_items)
        assert result.items_stored == 0

        # Restore original method
        ingestion_service.database.store_data_item = original_store

    @pytest.mark.asyncio
    async def test_invalid_last_sync_time_handling(self, ingestion_service, sample_data_items):
        """Test handling invalid last sync timestamps"""
        source = MockSource("invalid_sync", sample_data_items)
        ingestion_service.register_source(source)

        # Set invalid last sync time
        ingestion_service.database.set_setting("invalid_sync_last_sync", "invalid-timestamp")

        # Should handle gracefully and continue with full sync
        result = await ingestion_service.ingest_from_source("invalid_sync")

        assert result.success
        assert result.items_processed == len(sample_data_items)

    @pytest.mark.asyncio
    async def test_complex_last_sync_structure_handling(self, ingestion_service, sample_data_items):
        """Test handling complex last sync timestamp structures"""
        source = MockSource("complex_sync", sample_data_items)
        ingestion_service.register_source(source)

        # Set complex last sync structure (like what json_utils might create)
        complex_timestamp = {
            "raw_value": "2025-01-15T10:00:00Z",
            "parsed_value": "2025-01-15T10:00:00+00:00",
        }
        ingestion_service.database.set_setting("complex_sync_last_sync", complex_timestamp)

        # Should extract timestamp from raw_value and work correctly
        result = await ingestion_service.ingest_from_source("complex_sync")

        assert result.success


class TestDateExtraction:
    """Test date extraction for calendar support"""

    def test_extract_days_date_from_created_at(self, ingestion_service):
        """Test date extraction from item created_at"""
        item = DataItem(
            namespace="test",
            source_id="date_test",
            content="Test content",
            metadata={},
            created_at=datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        days_date = ingestion_service._extract_days_date(item)
        assert days_date == "2025-01-15"

    def test_extract_days_date_from_metadata_timestamp(self, ingestion_service):
        """Test date extraction from metadata timestamp fields"""
        item = DataItem(
            namespace="test",
            source_id="meta_date_test",
            content="Test content",
            metadata={
                "start_time": "2025-01-15T22:30:00Z",
                "title": "Test with timestamp",
            },
            created_at=None,
            updated_at=datetime.now(timezone.utc),
        )

        days_date = ingestion_service._extract_days_date(item)
        assert days_date == "2025-01-15"

    def test_extract_days_date_with_timezone_conversion(self, ingestion_service):
        """Test date extraction with timezone conversion"""
        # Item with timestamp in different timezone
        item = DataItem(
            namespace="limitless",  # Uses configured timezone
            source_id="tz_test",
            content="Test content",
            metadata={
                "start_time": "2025-01-15T22:30:00-08:00",  # PST timestamp
            },
            created_at=None,
            updated_at=datetime.now(timezone.utc),
        )

        days_date = ingestion_service._extract_days_date(item)
        # Should be converted to user's timezone
        assert days_date == "2025-01-15"

    def test_extract_days_date_fallback_to_none(self, ingestion_service):
        """Test date extraction fallback when no valid timestamps"""
        item = DataItem(
            namespace="test",
            source_id="no_date_test",
            content="Test content",
            metadata={"title": "No timestamps"},
            created_at=None,
            updated_at=datetime.now(timezone.utc),
        )

        days_date = ingestion_service._extract_days_date(item)
        assert days_date is None


class TestWebSocketNotifications:
    """Test WebSocket notification sending"""

    @pytest.mark.asyncio
    async def test_send_completion_notifications(self, ingestion_service, sample_data_items):
        """Test WebSocket notifications are sent for complete ingestions"""
        # Mock WebSocket manager
        with patch("services.ingestion.get_websocket_manager") as mock_get_ws:
            mock_ws_manager = Mock()
            mock_ws_manager.send_day_update = AsyncMock()
            mock_get_ws.return_value = mock_ws_manager

            # Register source and ingest with complete mode
            source = MockSource("notification_test", sample_data_items)
            ingestion_service.register_source(source)

            result = await ingestion_service.ingest_from_source(
                "notification_test",
                ingestion_mode="complete",
            )

            assert result.success
            # WebSocket notifications should be sent
            mock_ws_manager.send_day_update.assert_called()

    @pytest.mark.asyncio
    async def test_notification_failure_handling(self, ingestion_service, sample_data_items):
        """Test graceful handling of notification failures"""
        # Mock WebSocket manager to fail
        with patch("services.ingestion.get_websocket_manager") as mock_get_ws:
            mock_ws_manager = Mock()
            mock_ws_manager.send_day_update = AsyncMock(side_effect=Exception("WebSocket error"))
            mock_get_ws.return_value = mock_ws_manager

            source = MockSource("notification_fail", sample_data_items)
            ingestion_service.register_source(source)

            # Should complete successfully despite notification failure
            result = await ingestion_service.ingest_from_source(
                "notification_fail",
                ingestion_mode="complete",
            )

            assert result.success


class TestIngestionResultClass:
    """Test IngestionResult utility class"""

    def test_ingestion_result_initialization(self):
        """Test IngestionResult initialization"""
        result = IngestionResult()

        assert result.items_processed == 0
        assert result.items_stored == 0
        assert result.items_skipped == 0
        assert result.embeddings_generated == 0
        assert result.errors == []
        assert result.start_time is None
        assert result.end_time is None
        assert result.success is True  # No errors = success

    def test_ingestion_result_success_property(self):
        """Test success property logic"""
        result = IngestionResult()

        # No errors = success
        assert result.success is True

        # With errors = failure
        result.errors.append("Some error")
        assert result.success is False

    def test_ingestion_result_to_dict(self):
        """Test conversion to dictionary"""
        result = IngestionResult()
        result.items_processed = 5
        result.items_stored = 4
        result.items_skipped = 1
        result.embeddings_generated = 3
        result.errors = ["Error 1"]
        result.start_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result.end_time = datetime(2025, 1, 15, 10, 5, 0, tzinfo=timezone.utc)

        result_dict = result.to_dict()

        assert result_dict["items_processed"] == 5
        assert result_dict["items_stored"] == 4
        assert result_dict["items_skipped"] == 1
        assert result_dict["embeddings_generated"] == 3
        assert result_dict["errors"] == ["Error 1"]
        assert result_dict["success"] is False
        assert result_dict["start_time"] == "2025-01-15T10:00:00+00:00"
        assert result_dict["end_time"] == "2025-01-15T10:05:00+00:00"


class TestPerformanceScenarios:
    """Test performance-related scenarios"""

    @pytest.mark.asyncio
    async def test_large_batch_ingestion(self, ingestion_service):
        """Test ingestion of large batches"""
        # Create large batch of items
        large_batch = []
        for i in range(100):
            large_batch.append(DataItem(
                namespace="large_batch",
                source_id=f"item_{i:03d}",
                content=f"Content for item {i}",
                metadata={"index": i},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))

        import time
        start_time = time.perf_counter()

        result = await ingestion_service.ingest_items("large_batch", large_batch)

        end_time = time.perf_counter()
        duration = end_time - start_time

        assert result.success
        assert result.items_processed == 100
        assert result.items_stored == 100
        # Should complete within reasonable time
        assert duration < 10.0  # 10 seconds for 100 items

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_source_ingestion(self, ingestion_service, sample_data_items):
        """Test concurrent ingestion from multiple sources"""
        # Register multiple sources
        sources = []
        for i in range(5):
            source = MockSource(f"concurrent_{i}", sample_data_items)
            ingestion_service.register_source(source)
            sources.append(source)

        # Run concurrent ingestions
        tasks = [
            ingestion_service.ingest_from_source(f"concurrent_{i}")
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        for result in results:
            assert result.success
            assert result.items_processed == len(sample_data_items)

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_embedding_batch_performance(self, ingestion_service):
        """Test embedding processing performance with large batches"""
        # Create items that will need embeddings
        items = []
        for i in range(50):
            items.append(DataItem(
                namespace="embed_perf",
                source_id=f"embed_{i:03d}",
                content=f"Content for embedding {i} with sufficient length to be meaningful",
                metadata={"type": "performance_test"},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))

        # Ingest items
        await ingestion_service.ingest_items("embed_perf", items)

        # Process embeddings
        import time
        start_time = time.perf_counter()

        result = await ingestion_service.process_pending_embeddings(batch_size=16)

        end_time = time.perf_counter()
        duration = end_time - start_time

        assert result["processed"] == 50
        assert result["successful"] == 50
        # Should complete within reasonable time
        assert duration < 5.0  # 5 seconds for 50 embeddings (mocked)
