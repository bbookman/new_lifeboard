"""
Integration tests for end-to-end Limitless sync flow
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from config.factory import create_test_config
from config.models import LimitlessConfig
from core.database import DatabaseService
from core.embeddings import EmbeddingService
from core.vector_store import VectorStoreService
from services.ingestion import IngestionService
from sources.base import DataItem
from sources.limitless import LimitlessSource


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_config(temp_dir):
    """Create test configuration"""
    return create_test_config(temp_dir)


@pytest.fixture
def database_service(test_config):
    """Create test database service"""
    db = DatabaseService(test_config.database.path)
    yield db
    # Cleanup
    if os.path.exists(test_config.database.path):
        os.unlink(test_config.database.path)


@pytest.fixture
def vector_store_service(test_config):
    """Create test vector store service"""
    vector_store = VectorStoreService(test_config.vector_store)
    yield vector_store
    # Cleanup
    vector_store.cleanup()
    for path in [test_config.vector_store.index_path, test_config.vector_store.id_map_path]:
        if os.path.exists(path):
            os.unlink(path)


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service"""
    service = AsyncMock(spec=EmbeddingService)

    # Mock embedding responses
    import numpy as np
    service.embed_text.return_value = np.random.rand(384).astype(np.float32)
    service.embed_texts.return_value = [np.random.rand(384).astype(np.float32) for _ in range(3)]
    service.get_model_info.return_value = {"status": "mock", "dimension": 384}

    return service


@pytest.fixture
def mock_limitless_source():
    """Create mock Limitless source"""
    config = LimitlessConfig(api_key="test_key")
    source = LimitlessSource(config)

    # Mock the client
    with patch.object(source, "_get_client") as mock_client_method:
        mock_client = AsyncMock()
        mock_client_method.return_value = mock_client
        yield source


@pytest.fixture
def ingestion_service(database_service, vector_store_service, mock_embedding_service, test_config):
    """Create ingestion service with all dependencies"""
    return IngestionService(
        database=database_service,
        vector_store=vector_store_service,
        embedding_service=mock_embedding_service,
        config=test_config,
    )


@pytest.fixture
def sample_limitless_data():
    """Sample Limitless API response data"""
    return [
        {
            "id": "lifelog_1",
            "title": "Morning Standup",
            "markdown": "# Morning Standup\n\n**Alice:** Let's start with updates.\n\n**User:** I completed the API integration yesterday.",
            "startTime": "2024-01-15T09:00:00Z",
            "endTime": "2024-01-15T09:15:00Z",
            "isStarred": False,
            "updatedAt": "2024-01-15T09:20:00Z",
            "contents": [
                {
                    "type": "heading1",
                    "content": "Morning Standup",
                    "startTime": "2024-01-15T09:00:00Z",
                    "endTime": "2024-01-15T09:00:30Z",
                    "speakerName": None,
                    "speakerIdentifier": None,
                },
                {
                    "type": "blockquote",
                    "content": "Let's start with updates.",
                    "startTime": "2024-01-15T09:01:00Z",
                    "endTime": "2024-01-15T09:01:15Z",
                    "speakerName": "Alice",
                    "speakerIdentifier": None,
                },
                {
                    "type": "blockquote",
                    "content": "I completed the API integration yesterday.",
                    "startTime": "2024-01-15T09:02:00Z",
                    "endTime": "2024-01-15T09:02:30Z",
                    "speakerName": "User",
                    "speakerIdentifier": "user",
                },
            ],
        },
        {
            "id": "lifelog_2",
            "title": "Client Call",
            "markdown": "# Client Call\n\n**Client:** We need the features by next week.\n\n**User:** That timeline is aggressive but doable.",
            "startTime": "2024-01-15T14:00:00Z",
            "endTime": "2024-01-15T14:30:00Z",
            "isStarred": True,
            "updatedAt": "2024-01-15T14:35:00Z",
            "contents": [
                {
                    "type": "heading1",
                    "content": "Client Call",
                    "startTime": "2024-01-15T14:00:00Z",
                    "endTime": "2024-01-15T14:00:30Z",
                    "speakerName": None,
                    "speakerIdentifier": None,
                },
                {
                    "type": "blockquote",
                    "content": "We need the features by next week.",
                    "startTime": "2024-01-15T14:01:00Z",
                    "endTime": "2024-01-15T14:01:15Z",
                    "speakerName": "Client",
                    "speakerIdentifier": None,
                },
                {
                    "type": "blockquote",
                    "content": "That timeline is aggressive but doable.",
                    "startTime": "2024-01-15T14:02:00Z",
                    "endTime": "2024-01-15T14:02:30Z",
                    "speakerName": "User",
                    "speakerIdentifier": "user",
                },
            ],
        },
    ]


class TestIngestionService:
    """Test ingestion service functionality"""

    @pytest.mark.asyncio
    async def test_service_initialization(self, ingestion_service):
        """Test ingestion service initialization"""
        assert ingestion_service.database is not None
        assert ingestion_service.vector_store is not None
        assert ingestion_service.embedding_service is not None
        assert ingestion_service.processor is not None
        assert len(ingestion_service.sources) == 0

    @pytest.mark.asyncio
    async def test_source_registration(self, ingestion_service, mock_limitless_source):
        """Test registering a data source"""
        # Register source
        ingestion_service.register_source(mock_limitless_source)

        # Check it's registered
        assert "limitless" in ingestion_service.sources
        assert ingestion_service.sources["limitless"] == mock_limitless_source

        # Check database registration
        namespaces = ingestion_service.database.get_active_namespaces()
        assert "limitless" in namespaces

    @pytest.mark.asyncio
    async def test_manual_item_ingestion(self, ingestion_service):
        """Test manually ingesting a single item"""
        # Ingest item
        namespaced_id = await ingestion_service.manual_ingest_item(
            namespace="test",
            content="This is a test conversation",
            source_id="manual_test_1",
            metadata={"type": "manual_test"},
        )

        # Verify it was stored
        assert namespaced_id == "test:manual_test_1"

        items = ingestion_service.database.get_data_items_by_ids([namespaced_id])
        assert len(items) == 1

        item = items[0]
        assert item["namespace"] == "test"
        assert item["source_id"] == "manual_test_1"
        assert item["content"] == "This is a test conversation"
        assert item["metadata"]["type"] == "manual_test"

        # Should have processing metadata
        assert "processing_history" in item["metadata"]

    @pytest.mark.asyncio
    async def test_embedding_processing(self, ingestion_service, mock_embedding_service):
        """Test processing items for embeddings"""
        # Add some items to database
        await ingestion_service.manual_ingest_item(
            namespace="test",
            content="First test item",
            source_id="embed_test_1",
        )

        await ingestion_service.manual_ingest_item(
            namespace="test",
            content="Second test item",
            source_id="embed_test_2",
        )

        # Process embeddings
        result = await ingestion_service.process_pending_embeddings(batch_size=2)

        # Check results
        assert result["processed"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert len(result["errors"]) == 0

        # Verify embeddings were called
        mock_embedding_service.embed_texts.assert_called_once()

        # Check database status updated
        items = ingestion_service.database.get_data_items_by_ids([
            "test:embed_test_1", "test:embed_test_2",
        ])

        for item in items:
            # Should be marked as completed (no longer pending)
            assert item["id"] not in [
                pi["id"] for pi in ingestion_service.database.get_pending_embeddings()
            ]


class TestLimitlessIntegration:
    """Test end-to-end Limitless integration"""

    @pytest.mark.asyncio
    async def test_limitless_source_ingestion(self, ingestion_service, mock_limitless_source, sample_limitless_data):
        """Test full ingestion from Limitless source"""
        # Register the Limitless source
        ingestion_service.register_source(mock_limitless_source)

        # Mock the source to return sample data
        async def mock_sync(*args, **kwargs):
            for lifelog_data in sample_limitless_data:
                # Transform to DataItem (simulating what LimitlessSource does)
                content_parts = [lifelog_data["title"]]
                for content_node in lifelog_data.get("contents", []):
                    if content_node.get("content"):
                        speaker = content_node.get("speakerName")
                        if speaker:
                            if content_node.get("speakerIdentifier") == "user":
                                speaker_prefix = f"{speaker} (You): "
                            else:
                                speaker_prefix = f"{speaker}: "
                            content_parts.append(f"{speaker_prefix}{content_node['content']}")
                        else:
                            content_parts.append(content_node["content"])

                item = DataItem(
                    namespace="limitless",
                    source_id=lifelog_data["id"],
                    content="\n".join(content_parts),
                    metadata={
                        "original_lifelog": lifelog_data,
                        "title": lifelog_data["title"],
                        "is_starred": lifelog_data["isStarred"],
                        "speakers": ["Alice", "User", "Client"] if "Client" in str(lifelog_data) else ["Alice", "User"],
                    },
                    created_at=datetime.fromisoformat(lifelog_data["startTime"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(lifelog_data["updatedAt"].replace("Z", "+00:00")),
                )
                yield item

        # Mock the sync manager's sync method
        with patch("sources.sync_manager.SyncManager.sync_source", side_effect=mock_sync):
            # Perform ingestion
            result = await ingestion_service.ingest_from_source("limitless", limit=10)

        # Verify results
        assert result.success is True
        assert result.items_processed == 2
        assert result.items_stored == 2
        assert len(result.errors) == 0

        # Verify data was stored in database
        items = ingestion_service.database.get_data_items_by_namespace("limitless")
        assert len(items) == 2

        # Check first item
        item1 = next((item for item in items if item["source_id"] == "lifelog_1"), None)
        assert item1 is not None
        assert "Morning Standup" in item1["content"]
        assert "Alice: Let's start with updates" in item1["content"]
        assert "User (You): I completed the API integration" in item1["content"]

        # Check metadata processing
        assert "processing_history" in item1["metadata"]
        assert "content_stats" in item1["metadata"]
        assert "conversation_metadata" in item1["metadata"]

        # Check conversation metadata
        conv_metadata = item1["metadata"]["conversation_metadata"]
        assert conv_metadata["speaker_count"] == 2
        assert conv_metadata["has_user_participation"] is True
        assert conv_metadata["total_content_nodes"] == 3

        # Check second item
        item2 = next((item for item in items if item["source_id"] == "lifelog_2"), None)
        assert item2 is not None
        assert "Client Call" in item2["content"]
        assert item2["metadata"]["is_starred"] is True

    @pytest.mark.asyncio
    async def test_full_end_to_end_pipeline(self, ingestion_service, mock_limitless_source,
                                          mock_embedding_service, sample_limitless_data):
        """Test complete end-to-end pipeline: sync → process → store → embed"""
        # Register source
        ingestion_service.register_source(mock_limitless_source)

        # Mock source data
        async def mock_sync(*args, **kwargs):
            for lifelog_data in sample_limitless_data[:1]:  # Just one item for simplicity
                item = DataItem(
                    namespace="limitless",
                    source_id=lifelog_data["id"],
                    content=f"{lifelog_data['title']}\nAlice: Let's start with updates.\nUser (You): I completed the API integration yesterday.",
                    metadata={
                        "original_lifelog": lifelog_data,
                        "title": lifelog_data["title"],
                        "speakers": ["Alice", "User"],
                    },
                    created_at=datetime.fromisoformat(lifelog_data["startTime"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(lifelog_data["updatedAt"].replace("Z", "+00:00")),
                )
                yield item

        with patch("sources.sync_manager.SyncManager.sync_source", side_effect=mock_sync):
            # Step 1: Ingest from source
            ingest_result = await ingestion_service.ingest_from_source("limitless")
            assert ingest_result.success is True
            assert ingest_result.items_stored == 1

            # Step 2: Process embeddings
            embed_result = await ingestion_service.process_pending_embeddings()
            assert embed_result["successful"] == 1
            assert embed_result["failed"] == 0

        # Verify complete pipeline
        # 1. Item is in database
        items = ingestion_service.database.get_data_items_by_namespace("limitless")
        assert len(items) == 1

        item = items[0]
        assert item["id"] == "limitless:lifelog_1"

        # 2. Item has been processed
        assert "processing_history" in item["metadata"]
        assert "content_stats" in item["metadata"]

        # 3. Embedding was generated
        mock_embedding_service.embed_texts.assert_called_once()

        # 4. Vector was stored
        vector_stats = ingestion_service.vector_store.get_stats()
        assert vector_stats["total_vectors"] == 1

        # 5. No pending embeddings remain
        pending = ingestion_service.database.get_pending_embeddings()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_ingestion_status_reporting(self, ingestion_service, mock_limitless_source):
        """Test ingestion status reporting"""
        # Initial status
        status = ingestion_service.get_ingestion_status()
        assert len(status["registered_sources"]) == 0
        assert status["database_stats"]["total_items"] == 0

        # Register source and add data
        ingestion_service.register_source(mock_limitless_source)
        await ingestion_service.manual_ingest_item("limitless", "test content", "test_1")

        # Check updated status
        status = ingestion_service.get_ingestion_status()
        assert "limitless" in status["registered_sources"]
        assert status["database_stats"]["total_items"] == 1
        assert status["source_stats"]["limitless"]["has_data"] is True
        assert status["source_stats"]["limitless"]["source_type"] == "limitless_api"
        assert status["pending_embeddings"] == 1

    @pytest.mark.asyncio
    async def test_incremental_sync_behavior(self, ingestion_service, mock_limitless_source,
                                           sample_limitless_data):
        """Test incremental sync vs full sync behavior"""
        # Register source
        ingestion_service.register_source(mock_limitless_source)

        # Mock initial sync
        async def mock_first_sync(force_full_sync=False, limit=1000):
            # Return first item only
            lifelog_data = sample_limitless_data[0]
            item = DataItem(
                namespace="limitless",
                source_id=lifelog_data["id"],
                content=lifelog_data["title"],
                metadata={"original_lifelog": lifelog_data},
            )
            yield item

        # Mock incremental sync (returns second item)
        async def mock_incremental_sync(force_full_sync=False, limit=1000):
            if force_full_sync:
                # Full sync returns both
                for lifelog_data in sample_limitless_data:
                    item = DataItem(
                        namespace="limitless",
                        source_id=lifelog_data["id"],
                        content=lifelog_data["title"],
                        metadata={"original_lifelog": lifelog_data},
                    )
                    yield item
            else:
                # Incremental returns only new item
                lifelog_data = sample_limitless_data[1]
                item = DataItem(
                    namespace="limitless",
                    source_id=lifelog_data["id"],
                    content=lifelog_data["title"],
                    metadata={"original_lifelog": lifelog_data},
                )
                yield item

        # First sync
        with patch("sources.sync_manager.SyncManager.sync_source", side_effect=mock_first_sync):
            result1 = await ingestion_service.ingest_from_source("limitless")
            assert result1.items_stored == 1

        # Incremental sync
        with patch("sources.sync_manager.SyncManager.sync_source", side_effect=mock_incremental_sync):
            result2 = await ingestion_service.ingest_from_source("limitless", force_full_sync=False)
            assert result2.items_stored == 1

        # Should have 2 total items
        items = ingestion_service.database.get_data_items_by_namespace("limitless")
        assert len(items) == 2

        # Force full sync should work too
        with patch("sources.sync_manager.SyncManager.sync_source", side_effect=mock_incremental_sync):
            result3 = await ingestion_service.ingest_from_source("limitless", force_full_sync=True)
            # Will attempt to store both, but they already exist
            assert result3.items_processed == 2
