"""
Integration tests for ChatService with real embeddings

Tests the complete workflow from chat message to response generation,
verifying that real embeddings provide better vector search results.
"""

import logging
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from config.models import AppConfig, EmbeddingConfig, LLMProviderConfig
from core.embeddings import EmbeddingService
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


@pytest.mark.integration
class TestChatIntegration:
    """Test complete chat workflow with real embeddings"""

    @pytest_asyncio.fixture
    async def embedding_service(self):
        """Create real embedding service for testing"""
        config = EmbeddingConfig(model_name="all-MiniLM-L6-v2")
        service = EmbeddingService(config)
        await service.initialize()
        return service

    @pytest.fixture
    def mock_database(self):
        """Mock database service"""
        database = Mock()
        database.get_data_items_by_ids = Mock(return_value=[
            {
                "id": 1,
                "namespace": "test",
                "source_id": "test-1",
                "content": "This is a test document about machine learning and AI.",
                "metadata": {"type": "document"},
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01",
            },
            {
                "id": 2,
                "namespace": "test",
                "source_id": "test-2",
                "content": "Another document discussing neural networks and deep learning.",
                "metadata": {"type": "document"},
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01",
            },
        ])
        database.store_chat_message = Mock()
        database.get_chat_history = Mock(return_value=[])
        return database

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store service"""
        vector_store = Mock()
        # Return items in order of relevance (higher scores first)
        vector_store.search = Mock(return_value=[
            (1, 0.85),  # High similarity
            (2, 0.73),   # Lower similarity
        ])
        return vector_store

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response"""
        mock_response = Mock()
        mock_response.content = "Based on the provided context, machine learning is a subset of AI that enables systems to learn from data."
        mock_response.metadata = {}
        return mock_response

    @pytest_asyncio.fixture
    async def chat_service(self, embedding_service, mock_database, mock_vector_store, mock_llm_response):
        """Create chat service with real embeddings"""
        config = AppConfig(
            llm_provider=LLMProviderConfig(provider="ollama"),
            embeddings=EmbeddingConfig(model_name="all-MiniLM-L6-v2"),
        )

        service = ChatService(config, mock_database, mock_vector_store, embedding_service)

        # Mock LLM provider
        mock_provider = AsyncMock()
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.generate_response = AsyncMock(return_value=mock_llm_response)
        service.llm_provider = mock_provider

        await service.initialize()
        return service

    @pytest.mark.asyncio
    async def test_complete_chat_workflow(self, chat_service, mock_vector_store, mock_database):
        """Test complete chat workflow with real embeddings"""
        query = "Tell me about machine learning"

        response = await chat_service.process_chat_message(query)

        # Verify embedding was generated and used for vector search
        assert mock_vector_store.search.called
        query_embedding = mock_vector_store.search.call_args[0][0]

        # Verify embedding has correct dimensions (384 for MiniLM)
        assert len(query_embedding) == 384
        assert all(isinstance(val, float) for val in query_embedding)

        # Verify database operations
        assert mock_database.get_data_items_by_ids.called
        assert mock_database.store_chat_message.called

        # Verify response
        assert isinstance(response, str)
        assert len(response) > 0
        assert "machine learning" in response.lower()

    @pytest.mark.asyncio
    async def test_vector_search_with_real_embeddings(self, chat_service):
        """Test vector search produces meaningful embeddings"""
        # Test similar queries produce similar embeddings
        embedding1 = await chat_service.embeddings.embed_text("machine learning algorithms")
        embedding2 = await chat_service.embeddings.embed_text("AI and ML techniques")
        embedding3 = await chat_service.embeddings.embed_text("cooking recipes and food")

        # Calculate cosine similarity manually
        def cosine_similarity(a, b):
            import numpy as np
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        # Similar topics should have higher similarity
        similar_similarity = cosine_similarity(embedding1, embedding2)
        different_similarity = cosine_similarity(embedding1, embedding3)

        assert similar_similarity > different_similarity
        assert similar_similarity > 0.5  # Should be reasonably similar
        assert different_similarity < 0.5  # Should be less similar

    @pytest.mark.asyncio
    async def test_context_building_with_real_data(self, chat_service):
        """Test that context building works with real search results"""
        query = "What is artificial intelligence?"

        context = await chat_service._get_chat_context(query, max_results=4)

        # Should have both vector and SQL results
        assert len(context.vector_results) > 0
        assert context.total_results > 0

        # Build context text
        context_text = chat_service._build_context_text(context)
        assert isinstance(context_text, str)
        assert len(context_text) > 0

    @pytest.mark.asyncio
    async def test_error_handling_with_real_service(self, chat_service, mock_vector_store):
        """Test error handling when vector search fails"""
        # Make vector search fail
        mock_vector_store.search.side_effect = Exception("Vector search error")

        # Should still work with SQL fallback
        response = await chat_service.process_chat_message("test query")
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_embedding_service_initialization(self, embedding_service):
        """Test that embedding service initializes correctly"""
        assert embedding_service.model is not None
        assert embedding_service.is_initialized

        # Test embedding generation
        test_text = "This is a test sentence"
        embedding = await embedding_service.embed_text(test_text)

        assert isinstance(embedding, list)
        assert len(embedding) == 384  # MiniLM dimensions
        assert all(isinstance(val, float) for val in embedding)

    @pytest.mark.asyncio
    async def test_batch_embedding_in_context(self, embedding_service):
        """Test batch embedding functionality in realistic scenario"""
        texts = [
            "Machine learning is a subset of artificial intelligence",
            "Deep learning uses neural networks with multiple layers",
            "Natural language processing helps computers understand text",
            "Computer vision enables machines to interpret visual data",
        ]

        embeddings = await embedding_service.embed_batch(texts)

        assert len(embeddings) == len(texts)
        for embedding in embeddings:
            assert len(embedding) == 384
            assert all(isinstance(val, float) for val in embedding)

    @pytest.mark.asyncio
    async def test_service_cleanup(self, chat_service):
        """Test proper cleanup of services"""
        # Should not raise exceptions
        await chat_service.close()

        # Embedding service should still be accessible for cleanup
        if hasattr(chat_service.embeddings, "model") and chat_service.embeddings.model:
            assert chat_service.embeddings.is_initialized
