from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from core.database import DatabaseService
from core.embeddings import EmbeddingService
from services.semantic_deduplication_service import SemanticDeduplicationService
from sources.base import DataItem
from sources.semantic_deduplication_processor import (
    SemanticCluster,
    SemanticDeduplicationProcessor,
    SpokenLine,
)


class TestSemanticDeduplicationProcessor:
    """Test suite for semantic deduplication processor"""

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service for testing"""
        service = Mock(spec=EmbeddingService)

        # Mock embedding generation - similar texts get similar embeddings
        async def mock_embed_texts(texts):
            embeddings = []
            for text in texts:
                if "weather" in text.lower() or "hot" in text.lower() or "heat" in text.lower():
                    # Similar embeddings for weather-related content
                    embeddings.append(np.array([0.8, 0.2, 0.1, 0.1]))
                elif "meeting" in text.lower() or "prepare" in text.lower():
                    # Similar embeddings for meeting-related content
                    embeddings.append(np.array([0.1, 0.8, 0.2, 0.1]))
                else:
                    # Different embedding for unrelated content
                    embeddings.append(np.array([0.1, 0.1, 0.1, 0.8]))
            return embeddings

        service.embed_texts = AsyncMock(side_effect=mock_embed_texts)
        return service

    @pytest.fixture
    def processor(self, mock_embedding_service):
        """Create processor instance for testing"""
        return SemanticDeduplicationProcessor(
            similarity_threshold=0.85,
            min_line_words=3,
            embedding_service=mock_embedding_service,
        )

    @pytest.fixture
    def sample_conversations(self):
        """Sample conversation data for testing"""
        return [
            DataItem(
                namespace="limitless",
                source_id="conv1",
                content="Weather conversation",
                metadata={
                    "original_lifelog": {
                        "title": "Weather Discussion",
                        "startTime": "2024-01-15T10:00:00Z",
                        "contents": [
                            {
                                "type": "blockquote",
                                "content": "Wow it is really hot today",
                                "speakerName": "John",
                                "speakerIdentifier": "user",
                                "startTime": "2024-01-15T10:00:00Z",
                            },
                            {
                                "type": "blockquote",
                                "content": "I hate this heat so much",
                                "speakerName": "John",
                                "speakerIdentifier": "user",
                                "startTime": "2024-01-15T10:01:00Z",
                            },
                            {
                                "type": "blockquote",
                                "content": "Let's go inside where it's cool",
                                "speakerName": "Sarah",
                                "speakerIdentifier": "other",
                                "startTime": "2024-01-15T10:02:00Z",
                            },
                        ],
                    },
                },
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            DataItem(
                namespace="limitless",
                source_id="conv2",
                content="Meeting preparation",
                metadata={
                    "original_lifelog": {
                        "title": "Work Planning",
                        "startTime": "2024-01-15T14:00:00Z",
                        "contents": [
                            {
                                "type": "blockquote",
                                "content": "I need to prepare for the meeting tomorrow",
                                "speakerName": "John",
                                "speakerIdentifier": "user",
                                "startTime": "2024-01-15T14:00:00Z",
                            },
                            {
                                "type": "blockquote",
                                "content": "I should get ready for tomorrow's meeting",
                                "speakerName": "John",
                                "speakerIdentifier": "user",
                                "startTime": "2024-01-15T14:01:00Z",
                            },
                        ],
                    },
                },
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

    @pytest.mark.asyncio
    async def test_extract_spoken_lines(self, processor, sample_conversations):
        """Test extraction of spoken lines from conversations"""
        lines = processor._extract_spoken_lines(sample_conversations)

        assert len(lines) == 5  # Total blockquote lines across conversations
        assert all(isinstance(line, SpokenLine) for line in lines)
        assert all(len(line.text.split()) >= processor.min_line_words for line in lines)

        # Check specific lines
        weather_lines = [line for line in lines if "hot" in line.text or "heat" in line.text]
        assert len(weather_lines) == 2

        meeting_lines = [line for line in lines if "meeting" in line.text]
        assert len(meeting_lines) == 2

    @pytest.mark.asyncio
    async def test_generate_embeddings(self, processor, sample_conversations):
        """Test embedding generation for lines"""
        lines = processor._extract_spoken_lines(sample_conversations)
        embeddings = await processor._generate_embeddings(lines)

        assert len(embeddings) == len(lines)
        assert all(isinstance(emb, np.ndarray) for emb in embeddings.values())

        # Check that similar content gets similar embeddings
        hot_embedding = embeddings["Wow it is really hot today"]
        heat_embedding = embeddings["I hate this heat so much"]

        # Calculate similarity
        similarity = np.dot(hot_embedding, heat_embedding) / (
            np.linalg.norm(hot_embedding) * np.linalg.norm(heat_embedding)
        )

        assert similarity > 0.8  # Should be similar

    @pytest.mark.asyncio
    async def test_identify_clusters(self, processor, sample_conversations):
        """Test cluster identification"""
        lines = processor._extract_spoken_lines(sample_conversations)
        embeddings = await processor._generate_embeddings(lines)
        clusters = processor._identify_clusters(lines, embeddings)

        assert len(clusters) >= 2  # Should find weather and meeting clusters
        assert all(isinstance(cluster, SemanticCluster) for cluster in clusters)
        assert all(cluster.frequency_count >= processor.min_cluster_size for cluster in clusters)

        # Check cluster themes
        themes = [cluster.theme for cluster in clusters]
        assert any("weather" in theme for theme in themes)
        assert any("meeting" in theme for theme in themes)

    @pytest.mark.asyncio
    async def test_process_batch(self, processor, sample_conversations):
        """Test full batch processing"""
        processed_items = await processor.process_batch(sample_conversations)

        assert len(processed_items) == len(sample_conversations)

        # Check that display_conversation was created
        for item in processed_items:
            assert "display_conversation" in item.metadata
            assert "semantic_clusters" in item.metadata
            assert "semantic_metadata" in item.metadata

            display_conv = item.metadata["display_conversation"]
            semantic_meta = item.metadata["semantic_metadata"]

            # Verify display conversation structure
            assert isinstance(display_conv, list)
            assert semantic_meta["processed"] is True
            assert semantic_meta["total_lines_analyzed"] > 0

            # Check for deduplication indicators
            deduplicated_lines = [node for node in display_conv if node.get("is_deduplicated")]
            unique_lines = [node for node in display_conv if node.get("is_unique")]

            assert len(display_conv) <= len(item.metadata["original_lifelog"]["contents"])

    def test_choose_canonical_line(self, processor):
        """Test canonical line selection"""
        lines = [
            SpokenLine("This is a longer version of the same idea", "John", "user", "2024-01-15T10:00:00Z", "conv1", {}),
            SpokenLine("Same idea", "John", "user", "2024-01-15T10:01:00Z", "conv1", {}),
            SpokenLine("This is the same idea but longer", "John", "user", "2024-01-15T10:02:00Z", "conv1", {}),
        ]

        canonical = processor._choose_canonical_line(lines)

        # Should choose the first one chronologically, or shortest if no timestamps
        assert canonical.text == "Same idea"  # Shortest version

    def test_generate_theme(self, processor):
        """Test theme generation from text"""
        assert "weather" in processor._generate_theme("It's so hot today").lower()
        assert "work" in processor._generate_theme("I need to prepare for the meeting").lower()
        assert "energy" in processor._generate_theme("I'm so tired").lower()
        assert "food" in processor._generate_theme("I'm hungry for lunch").lower()

    def test_get_processing_stats(self, processor):
        """Test processing statistics"""
        stats = processor.get_processing_stats()

        assert "embedding_cache_size" in stats
        assert "similarity_threshold" in stats
        assert "clustering_method" in stats
        assert stats["similarity_threshold"] == 0.85


class TestSemanticDeduplicationService:
    """Test suite for semantic deduplication service"""

    @pytest.fixture
    def mock_database(self):
        """Mock database service"""
        db = Mock(spec=DatabaseService)

        # Mock get_data_items_by_namespace
        db.get_data_items_by_namespace.return_value = [
            {
                "id": "limitless:conv1",
                "namespace": "limitless",
                "source_id": "conv1",
                "content": "Test content",
                "metadata": {
                    "original_lifelog": {
                        "title": "Test Conversation",
                        "contents": [],
                    },
                },
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
            },
        ]

        # Mock store_data_item
        db.store_data_item = Mock()

        # Mock connection context manager
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = [0]  # For cluster exists check
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.commit = Mock()

        db.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        db.get_connection.return_value.__exit__ = Mock(return_value=None)

        return db

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service"""
        service = Mock(spec=EmbeddingService)
        service.embed_texts = AsyncMock(return_value=[np.array([1, 0, 0, 0])])
        return service

    @pytest.fixture
    def service(self, mock_database, mock_embedding_service):
        """Create service instance for testing"""
        return SemanticDeduplicationService(mock_database, mock_embedding_service)

    @pytest.mark.asyncio
    async def test_fetch_conversations(self, service, mock_database):
        """Test fetching conversations from database"""
        conversations = await service._fetch_conversations("limitless", 10)

        assert len(conversations) == 1
        assert isinstance(conversations[0], DataItem)
        assert conversations[0].namespace == "limitless"
        assert conversations[0].source_id == "conv1"

        mock_database.get_data_items_by_namespace.assert_called_once_with("limitless", limit=10)

    @pytest.mark.asyncio
    async def test_store_semantic_cluster(self, service, mock_database):
        """Test storing semantic cluster in database"""
        cluster_data = {
            "theme": "test_theme",
            "canonical": "test canonical line",
            "confidence": 0.9,
            "frequency": 5,
            "variations": [
                {
                    "text": "variation 1",
                    "speaker": "John",
                    "similarity": 0.8,
                    "timestamp": "2024-01-15T10:00:00Z",
                },
            ],
        }

        item = DataItem("limitless", "test", "content", {}, datetime.now(), datetime.now())

        result = await service._store_semantic_cluster("test_cluster", cluster_data, item)

        assert result is True
        # Verify database calls were made
        assert mock_database.get_connection.called

    @pytest.mark.asyncio
    async def test_cluster_exists(self, service, mock_database):
        """Test checking if cluster exists"""
        exists = await service._cluster_exists("test_cluster")

        assert exists is False  # Mock returns 0
        assert mock_database.get_connection.called

    @pytest.mark.asyncio
    async def test_process_historical_conversations(self, service, mock_database, mock_embedding_service):
        """Test processing historical conversations"""
        with patch.object(service.processor, "process_batch") as mock_process:
            mock_process.return_value = [
                DataItem("limitless", "conv1", "content", {
                    "display_conversation": [],
                    "semantic_clusters": {},
                    "semantic_metadata": {"processed": True},
                }, datetime.now(), datetime.now()),
            ]

            result = await service.process_historical_conversations("limitless", batch_size=10)

            assert result.total_processed == 1
            assert result.items_modified == 1
            assert len(result.errors) == 0

            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cluster_statistics(self, service, mock_database):
        """Test getting cluster statistics"""
        # Mock return values for statistics queries
        mock_conn = mock_database.get_connection.return_value.__enter__.return_value
        mock_cursor = mock_conn.execute.return_value

        # Mock different return values for different queries
        def mock_execute(*args):
            query = args[0] if args else ""
            if "COUNT(*) as total_clusters" in query:
                mock_cursor.fetchone.return_value = {
                    "total_clusters": 5,
                    "avg_frequency": 10.5,
                    "max_frequency": 25,
                    "avg_confidence": 0.85,
                }
            elif "theme, COUNT(*)" in query:
                mock_cursor.fetchall.return_value = [
                    {"theme": "weather_complaints", "count": 3},
                    {"theme": "meeting_prep", "count": 2},
                ]
            elif "total_mappings" in query:
                mock_cursor.fetchone.return_value = {"total_mappings": 15}
            return mock_cursor

        mock_conn.execute.side_effect = mock_execute

        stats = await service.get_cluster_statistics()

        assert "cluster_stats" in stats
        assert "theme_distribution" in stats
        assert "mapping_stats" in stats
        assert "generated_at" in stats


class TestLimitlessProcessorIntegration:
    """Test integration of semantic deduplication with LimitlessProcessor"""

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service"""
        service = Mock(spec=EmbeddingService)
        service.embed_texts = AsyncMock(return_value=[np.array([1, 0, 0, 0])])
        return service

    def test_processor_initialization_with_semantic_deduplication(self, mock_embedding_service):
        """Test that processor initializes with semantic deduplication enabled"""
        from sources.limitless_processor import LimitlessProcessor

        processor = LimitlessProcessor(
            enable_semantic_deduplication=True,
            embedding_service=mock_embedding_service,
        )

        assert processor.enable_semantic_deduplication is True
        assert hasattr(processor, "semantic_processor")

        pipeline_info = processor.get_pipeline_info()
        assert pipeline_info["semantic_deduplication_enabled"] is True
        assert pipeline_info["supports_batch_processing"] is True
        assert "SemanticDeduplicationProcessor" in pipeline_info["processors"]

    def test_processor_initialization_without_semantic_deduplication(self):
        """Test processor works without semantic deduplication"""
        from sources.limitless_processor import LimitlessProcessor

        processor = LimitlessProcessor(enable_semantic_deduplication=False)

        assert processor.enable_semantic_deduplication is False

        pipeline_info = processor.get_pipeline_info()
        assert pipeline_info["semantic_deduplication_enabled"] is False
        assert "DeduplicationProcessor" in pipeline_info["processors"]

    @pytest.mark.asyncio
    async def test_batch_processing_integration(self, mock_embedding_service):
        """Test batch processing with semantic deduplication"""
        from sources.limitless_processor import LimitlessProcessor

        processor = LimitlessProcessor(
            enable_semantic_deduplication=True,
            embedding_service=mock_embedding_service,
        )

        # Create test items
        test_items = [
            DataItem(
                namespace="limitless",
                source_id="test1",
                content="Test content",
                metadata={"original_lifelog": {"contents": []}},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

        with patch.object(processor.semantic_processor, "process_batch") as mock_batch:
            mock_batch.return_value = test_items

            result = await processor.process_batch(test_items)

            assert len(result) == 1
            mock_batch.assert_called_once_with(test_items)


class TestDatabaseMigration:
    """Test database schema for semantic deduplication"""

    def test_migration_up(self):
        """Test migration creates required tables"""
        from core.migrations.versions.add_semantic_deduplication_tables import up

        mock_conn = Mock()
        up(mock_conn)

        # Verify tables were created
        execute_calls = mock_conn.execute.call_args_list

        # Check that semantic_clusters table was created
        clusters_table_created = any(
            "CREATE TABLE IF NOT EXISTS semantic_clusters" in str(call)
            for call in execute_calls
        )
        assert clusters_table_created

        # Check that line_cluster_mapping table was created
        mapping_table_created = any(
            "CREATE TABLE IF NOT EXISTS line_cluster_mapping" in str(call)
            for call in execute_calls
        )
        assert mapping_table_created

        # Check that indexes were created
        indexes_created = any(
            "CREATE INDEX" in str(call)
            for call in execute_calls
        )
        assert indexes_created

    def test_migration_down(self):
        """Test migration cleanup"""
        from core.migrations.versions.add_semantic_deduplication_tables import down

        mock_conn = Mock()
        down(mock_conn)

        # Verify tables were dropped
        execute_calls = mock_conn.execute.call_args_list

        drop_calls = [str(call) for call in execute_calls if "DROP TABLE" in str(call)]
        assert len(drop_calls) == 2  # Should drop both tables


@pytest.mark.integration
class TestEndToEndSemanticDeduplication:
    """End-to-end integration tests"""

    @pytest.mark.asyncio
    async def test_full_semantic_deduplication_workflow(self):
        """Test complete workflow from raw data to displayed conversation"""

        # This would be a full integration test with real database
        # For now, we'll use mocks to simulate the full workflow

        # Mock services
        mock_db = Mock(spec=DatabaseService)
        mock_embedding = Mock(spec=EmbeddingService)

        # Create realistic test data
        raw_conversations = [
            {
                "id": "limitless:conv1",
                "namespace": "limitless",
                "source_id": "conv1",
                "content": "Weather conversation",
                "metadata": {
                    "original_lifelog": {
                        "title": "Weather Talk",
                        "contents": [
                            {
                                "type": "blockquote",
                                "content": "It is so hot outside",
                                "speakerName": "John",
                                "startTime": "2024-01-15T10:00:00Z",
                            },
                            {
                                "type": "blockquote",
                                "content": "This heat is unbearable",
                                "speakerName": "John",
                                "startTime": "2024-01-15T10:01:00Z",
                            },
                            {
                                "type": "blockquote",
                                "content": "Let us go inside",
                                "speakerName": "Sarah",
                                "startTime": "2024-01-15T10:02:00Z",
                            },
                        ],
                    },
                },
            },
        ]

        mock_db.get_data_items_by_namespace.return_value = raw_conversations
        mock_embedding.embed_texts = AsyncMock(return_value=[
            np.array([0.8, 0.2, 0.1, 0.1]),  # Similar embeddings for similar content
            np.array([0.7, 0.3, 0.1, 0.1]),
            np.array([0.1, 0.1, 0.8, 0.2]),   # Different for unrelated content
        ])

        # Create and run service
        service = SemanticDeduplicationService(mock_db, mock_embedding)

        result = await service.process_historical_conversations("limitless", batch_size=10)

        # Verify processing completed successfully
        assert result.total_processed > 0
        assert len(result.errors) == 0

        # This test demonstrates the structure but would need a real database
        # for complete validation of the stored results
