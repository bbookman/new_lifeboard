"""
Tests for chat service functionality (Phase 7)
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.factory import create_test_config
from config.models import LLMProviderConfig, OllamaConfig
from core.database import DatabaseService
from core.embeddings import EmbeddingService
from core.vector_store import VectorStoreService
from llm.base import LLMResponse
from services.chat_service import ChatContext, ChatService


class TestChatService:
    """Test suite for ChatService"""

    @pytest.fixture
    def mock_database(self):
        """Mock database service"""
        mock_db = Mock(spec=DatabaseService)
        mock_db.store_chat_message = Mock()
        mock_db.get_chat_history = Mock(return_value=[])
        mock_db.get_connection = Mock()
        mock_db.get_data_items_by_ids = Mock(return_value=[])
        return mock_db

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store service"""
        mock_vs = Mock(spec=VectorStoreService)
        mock_vs.search = Mock(return_value=[])
        return mock_vs

    @pytest.fixture
    def mock_embeddings(self):
        """Mock embedding service"""
        mock_emb = Mock(spec=EmbeddingService)
        mock_emb.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
        return mock_emb

    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        config = create_test_config()
        # Override with Ollama config for testing
        config.llm_provider = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(
                base_url="http://localhost:11434",
                model="llama2",
                timeout=30,
                max_retries=3,
            ),
        )
        return config

    @pytest.fixture
    def chat_service(self, mock_config, mock_database, mock_vector_store, mock_embeddings):
        """Create chat service instance"""
        return ChatService(
            config=mock_config,
            database=mock_database,
            vector_store=mock_vector_store,
            embeddings=mock_embeddings,
        )

    def test_chat_service_initialization(self, chat_service):
        """Test chat service initialization"""
        assert chat_service.llm_provider is None
        assert chat_service.database is not None
        assert chat_service.vector_store is not None
        assert chat_service.embeddings is not None

    @pytest.mark.asyncio
    async def test_initialize_chat_service(self, chat_service):
        """Test chat service LLM provider initialization"""
        with patch("services.chat_service.create_llm_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.is_available = AsyncMock(return_value=True)
            mock_create.return_value = mock_provider

            await chat_service.initialize()

            assert chat_service.llm_provider is not None
            mock_create.assert_called_once()
            mock_provider.is_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_chat_service_unavailable_provider(self, chat_service):
        """Test initialization with unavailable LLM provider"""
        with patch("services.chat_service.create_llm_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.is_available = AsyncMock(return_value=False)
            mock_create.return_value = mock_provider

            await chat_service.initialize()

            assert chat_service.llm_provider is not None
            mock_provider.is_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_search(self, chat_service):
        """Test vector search functionality"""
        # Setup mock data
        chat_service.vector_store.search.return_value = [("id1", 0.9), ("id2", 0.8)]
        chat_service.database.get_data_items_by_ids.return_value = [
            {"id": "id1", "content": "Test content 1"},
            {"id": "id2", "content": "Test content 2"},
        ]

        results = await chat_service._vector_search("test query", 5)

        chat_service.embeddings.embed_text.assert_called_once_with("test query")
        chat_service.vector_store.search.assert_called_once_with([0.1, 0.2, 0.3], k=5)
        chat_service.database.get_data_items_by_ids.assert_called_once_with(["id1", "id2"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_vector_search_error_handling(self, chat_service):
        """Test vector search error handling"""
        chat_service.embeddings.embed_text.side_effect = Exception("Embedding error")

        results = await chat_service._vector_search("test query", 5)

        assert results == []

    @pytest.mark.asyncio
    async def test_sql_search(self, chat_service):
        """Test SQL search functionality"""
        # Setup mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                "id": "test:1",
                "namespace": "test",
                "source_id": "1",
                "content": "Test content with query",
                "metadata": '{"key": "value"}',
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        chat_service.database.get_connection.return_value = mock_conn

        results = await chat_service._sql_search("query", 5)

        assert len(results) == 1
        assert results[0]["content"] == "Test content with query"
        assert results[0]["metadata"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_sql_search_error_handling(self, chat_service):
        """Test SQL search error handling"""
        chat_service.database.get_connection.side_effect = Exception("Database error")

        results = await chat_service._sql_search("query", 5)

        assert results == []

    @pytest.mark.asyncio
    async def test_get_chat_context(self, chat_service):
        """Test chat context retrieval"""
        with patch.object(chat_service, "_vector_search") as mock_vector:
            with patch.object(chat_service, "_sql_search") as mock_sql:
                mock_vector.return_value = [{"id": "v1", "content": "Vector result"}]
                mock_sql.return_value = [{"id": "s1", "content": "SQL result"}]

                context = await chat_service._get_chat_context("test query", 10)

                assert isinstance(context, ChatContext)
                assert len(context.vector_results) == 1
                assert len(context.sql_results) == 1
                assert context.total_results == 2

                mock_vector.assert_called_once_with("test query", 5)
                mock_sql.assert_called_once_with("test query", 5)

    def test_build_context_text(self, chat_service):
        """Test context text building"""
        context = ChatContext(
            vector_results=[
                {"id": "v1", "content": "Vector search result content"},
                {"id": "v2", "content": "Another vector result"},
            ],
            sql_results=[
                {"id": "s1", "content": "SQL search result content"},
            ],
            total_results=3,
        )

        context_text = chat_service._build_context_text(context)

        assert "=== Relevant Information (Semantic Search) ===" in context_text
        assert "=== Additional Relevant Information (Keyword Search) ===" in context_text
        assert "Vector search result content" in context_text
        assert "SQL search result content" in context_text

    def test_build_context_text_empty(self, chat_service):
        """Test context text building with empty results"""
        context = ChatContext(
            vector_results=[],
            sql_results=[],
            total_results=0,
        )

        context_text = chat_service._build_context_text(context)

        assert context_text == "No relevant information found in your personal data."

    def test_build_context_text_deduplication(self, chat_service):
        """Test context text building with duplicate IDs"""
        context = ChatContext(
            vector_results=[
                {"id": "same_id", "content": "Vector result"},
            ],
            sql_results=[
                {"id": "same_id", "content": "SQL result"},
                {"id": "unique_id", "content": "Unique SQL result"},
            ],
            total_results=3,
        )

        context_text = chat_service._build_context_text(context)

        assert "Vector result" in context_text
        assert "Unique SQL result" in context_text
        assert context_text.count("SQL result") == 0  # Duplicate should be filtered out

    @pytest.mark.asyncio
    async def test_generate_response(self, chat_service):
        """Test LLM response generation"""
        mock_provider = AsyncMock()
        mock_response = LLMResponse.create(
            content="Test response",
            model="test-model",
            provider="test",
        )
        mock_provider.generate_response.return_value = mock_response
        chat_service.llm_provider = mock_provider

        context = ChatContext(
            vector_results=[{"content": "Context content"}],
            sql_results=[],
            total_results=1,
        )

        response = await chat_service._generate_response("Test question", context)

        assert response.content == "Test response"
        mock_provider.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_no_provider(self, chat_service):
        """Test response generation without LLM provider"""
        context = ChatContext(vector_results=[], sql_results=[], total_results=0)

        with pytest.raises(Exception):
            await chat_service._generate_response("Test question", context)

    @pytest.mark.asyncio
    async def test_process_chat_message_success(self, chat_service):
        """Test successful chat message processing"""
        # Setup mocks
        mock_provider = AsyncMock()
        mock_response = LLMResponse.create(
            content="Test assistant response",
            model="test-model",
            provider="test",
        )
        mock_provider.generate_response.return_value = mock_response
        chat_service.llm_provider = mock_provider

        with patch.object(chat_service, "_get_chat_context") as mock_context:
            mock_context.return_value = ChatContext(
                vector_results=[],
                sql_results=[],
                total_results=0,
            )

            response = await chat_service.process_chat_message("Test question")

            assert response == "Test assistant response"
            chat_service.database.store_chat_message.assert_called_once_with(
                "Test question",
                "Test assistant response",
            )

    @pytest.mark.asyncio
    async def test_process_chat_message_error(self, chat_service):
        """Test chat message processing with error"""
        with patch.object(chat_service, "_get_chat_context") as mock_context:
            mock_context.side_effect = Exception("Context error")

            response = await chat_service.process_chat_message("Test question")

            assert "I'm sorry, I encountered an error" in response
            # Should still try to store the error message
            chat_service.database.store_chat_message.assert_called_once()

    def test_get_chat_history(self, chat_service):
        """Test chat history retrieval"""
        expected_history = [
            {
                "id": 1,
                "user_message": "Test question",
                "assistant_response": "Test response",
                "timestamp": "2024-01-01T00:00:00",
            },
        ]
        chat_service.database.get_chat_history.return_value = expected_history

        history = chat_service.get_chat_history(20)

        assert history == expected_history
        chat_service.database.get_chat_history.assert_called_once_with(20)

    @pytest.mark.asyncio
    async def test_close(self, chat_service):
        """Test service cleanup"""
        mock_provider = AsyncMock()
        chat_service.llm_provider = mock_provider

        await chat_service.close()

        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_provider(self, chat_service):
        """Test cleanup without provider"""
        # Should not raise exception
        await chat_service.close()

        # No assertions needed - just ensuring no exception is raised


class TestChatContext:
    """Test suite for ChatContext dataclass"""

    def test_chat_context_creation(self):
        """Test ChatContext creation"""
        context = ChatContext(
            vector_results=[{"id": "1"}],
            sql_results=[{"id": "2"}],
            total_results=2,
        )

        assert len(context.vector_results) == 1
        assert len(context.sql_results) == 1
        assert context.total_results == 2
