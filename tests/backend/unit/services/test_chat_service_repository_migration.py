"""
Test ChatService Repository Migration

Tests that ChatService properly uses RepositoryFactory instead of direct DatabaseService access
and maintains backward compatibility.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from services.chat_service import ChatService, ChatContext
from core.repositories.repository_factory import RepositoryFactory
from core.repositories.chat_repository import ChatRepository
from core.repositories.data_item_repository import DataItemRepository
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from config.models import AppConfig


@pytest.fixture
def mock_database_service():
    """Mock DatabaseService for testing"""
    mock_db = Mock(spec=DatabaseService)
    mock_db.get_async_connection = AsyncMock()
    return mock_db


@pytest.fixture
def mock_chat_repository():
    """Mock ChatRepository for testing"""
    mock_repo = Mock(spec=ChatRepository)
    mock_repo.async_store_chat_message = AsyncMock()
    mock_repo.async_get_chat_history = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_data_item_repository():
    """Mock DataItemRepository for testing"""
    mock_repo = Mock(spec=DataItemRepository)
    mock_repo.async_get_data_items_by_ids = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_repository_factory(mock_database_service, mock_chat_repository, mock_data_item_repository):
    """Mock RepositoryFactory for testing"""
    mock_factory = Mock(spec=RepositoryFactory)
    mock_factory.database_service = mock_database_service
    mock_factory.get_chat_repository.return_value = mock_chat_repository
    mock_factory.get_data_item_repository.return_value = mock_data_item_repository
    return mock_factory


@pytest.fixture
def mock_vector_store():
    """Mock VectorStoreService for testing"""
    mock_vs = Mock(spec=VectorStoreService)
    mock_vs.search = Mock()
    return mock_vs


@pytest.fixture
def mock_embeddings():
    """Mock EmbeddingService for testing"""
    mock_emb = Mock(spec=EmbeddingService)
    mock_emb.initialize = AsyncMock()
    mock_emb.embed_text = AsyncMock()
    return mock_emb


@pytest.fixture
def mock_config():
    """Mock AppConfig for testing"""
    config = Mock(spec=AppConfig)
    config.llm_provider = Mock()
    config.llm_provider.provider = "test_provider"
    return config


@pytest.fixture
def chat_service(mock_config, mock_repository_factory, mock_vector_store, mock_embeddings):
    """Create ChatService instance for testing"""
    service = ChatService(
        config=mock_config,
        repository_factory=mock_repository_factory,
        vector_store=mock_vector_store,
        embeddings=mock_embeddings
    )
    return service


class TestChatServiceRepositoryMigration:
    """Test suite for ChatService repository migration"""
    
    def test_initialization_with_repository_factory(self, chat_service, mock_repository_factory):
        """Test that ChatService initializes correctly with RepositoryFactory"""
        # Verify repository factory is stored
        assert chat_service.repository_factory == mock_repository_factory
        
        # Verify repository instances are created
        assert chat_service.chat_repo is not None
        assert chat_service.data_item_repo is not None
        
        # Verify backward compatibility - database service is still accessible
        assert chat_service.database == mock_repository_factory.database_service
        
        # Verify factory methods were called
        mock_repository_factory.get_chat_repository.assert_called_once()
        mock_repository_factory.get_data_item_repository.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_chat_message_uses_repository(self, chat_service, mock_chat_repository):
        """Test that storing chat messages uses ChatRepository"""
        # Mock LLM response
        mock_llm_response = Mock()
        mock_llm_response.content = "Test response"
        
        # Mock LLM provider
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_provider.generate_response.return_value = mock_llm_response
        chat_service.llm_provider = mock_llm_provider
        
        # Mock context retrieval
        mock_context = ChatContext(
            vector_results=[],
            sql_results=[],
            total_results=0
        )
        
        with patch.object(chat_service, '_get_chat_context', return_value=mock_context):
            with patch.object(chat_service, '_generate_response', return_value=mock_llm_response):
                # Process chat message
                result = await chat_service.process_chat_message("Test message")
                
                # Verify repository method was called
                mock_chat_repository.async_store_chat_message.assert_called_once_with(
                    "Test message", "Test response"
                )
                
                # Verify response is correct
                assert result == "Test response"
    
    @pytest.mark.asyncio
    async def test_get_chat_history_uses_repository(self, chat_service, mock_chat_repository):
        """Test that getting chat history uses ChatRepository"""
        # Mock chat history data
        expected_history = [
            {
                "id": 1,
                "user_message": "Hello",
                "assistant_response": "Hi there!",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
        mock_chat_repository.async_get_chat_history.return_value = expected_history
        
        # Get chat history
        result = await chat_service.get_chat_history(limit=10)
        
        # Verify repository method was called
        mock_chat_repository.async_get_chat_history.assert_called_once_with(10)
        
        # Verify result is correct
        assert result == expected_history
    
    @pytest.mark.asyncio
    async def test_vector_search_uses_data_item_repository(self, chat_service, mock_data_item_repository, mock_embeddings, mock_vector_store):
        """Test that vector search uses DataItemRepository"""
        # Mock embedding result
        mock_embeddings.embed_text.return_value = [0.1, 0.2, 0.3]
        
        # Mock vector store search result
        mock_vector_store.search.return_value = [("item1", 0.9), ("item2", 0.8)]
        
        # Mock repository result
        expected_items = [
            {"id": "item1", "content": "First item"},
            {"id": "item2", "content": "Second item"}
        ]
        mock_data_item_repository.async_get_data_items_by_ids.return_value = expected_items
        
        # Perform vector search
        result = await chat_service._vector_search("test query", max_results=5)
        
        # Verify repository method was called
        mock_data_item_repository.async_get_data_items_by_ids.assert_called_once_with(
            ["item1", "item2"]
        )
        
        # Verify result is correct
        assert result == expected_items
    
    @pytest.mark.asyncio
    async def test_error_storage_uses_repository(self, chat_service, mock_chat_repository):
        """Test that error message storage uses ChatRepository"""
        # Test error storage method
        await chat_service._store_error_message("Test message", "Test error")
        
        # Verify repository method was called
        mock_chat_repository.async_store_chat_message.assert_called_once_with(
            "Test message", 
            "I'm sorry, I encountered an error processing your message. Please try again."
        )
    
    @pytest.mark.asyncio
    async def test_search_data_combines_repositories(self, chat_service, mock_embeddings, mock_vector_store, mock_data_item_repository):
        """Test that search_data method properly combines repository results"""
        # Mock embedding and vector search
        mock_embeddings.embed_text.return_value = [0.1, 0.2, 0.3]
        mock_vector_store.search.return_value = [("item1", 0.9)]
        
        # Mock vector search results
        vector_results = [{"id": "item1", "content": "Vector result"}]
        mock_data_item_repository.async_get_data_items_by_ids.return_value = vector_results
        
        # Mock SQL search results through context retrieval
        sql_results = [{"id": "item2", "content": "SQL result"}]
        
        mock_context = ChatContext(
            vector_results=vector_results,
            sql_results=sql_results,
            total_results=2
        )
        
        with patch.object(chat_service, '_get_chat_context', return_value=mock_context):
            # Perform search
            result = await chat_service.search_data("test query", limit=10)
            
            # Verify results are combined and scored
            assert len(result) == 2
            assert result[0]["id"] == "item1"
            assert result[0]["score"] == 0.9  # Vector search score
            assert result[1]["id"] == "item2"
            assert result[1]["score"] == 0.7  # SQL search score
    
    def test_backward_compatibility_database_access(self, chat_service, mock_repository_factory):
        """Test that direct database access is still available for backward compatibility"""
        # Verify database service is accessible
        assert chat_service.database == mock_repository_factory.database_service
        
        # This ensures that any remaining direct database access still works
        # while we complete the migration
        assert hasattr(chat_service, 'database')
        assert chat_service.database is not None


if __name__ == "__main__":
    pytest.main([__file__])