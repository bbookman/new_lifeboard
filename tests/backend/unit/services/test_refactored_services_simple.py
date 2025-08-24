"""
Simple tests to validate refactored services work correctly.
"""

import pytest
from unittest.mock import Mock, patch

# Test individual service imports and basic functionality
def test_chat_service_import_and_debug_mixin():
    """Test ChatService can be imported and has debug capabilities."""
    from services.chat_service import ChatService
    
    # Mock dependencies
    mock_config = Mock()
    mock_database = Mock()
    mock_vector_store = Mock()
    mock_embeddings = Mock()
    
    with patch.object(ChatService, 'log_service_call'):
        service = ChatService(mock_config, mock_database, mock_vector_store, mock_embeddings)
        
        # Check it has debug mixin methods
        assert hasattr(service, 'log_service_call')
        assert hasattr(service, 'log_database_operation')
        assert hasattr(service, 'service_name')
        assert service.service_name == "chat_service"

def test_news_service_import_and_debug_mixin():
    """Test NewsService can be imported and has debug capabilities."""
    from services.news_service import NewsService
    
    # Mock dependencies
    mock_db_service = Mock()
    mock_config = Mock()
    mock_config.unique_items_per_day = 5
    
    with patch.object(NewsService, 'log_service_call'):
        service = NewsService(mock_db_service, mock_config)
        
        # Check it has debug mixin methods
        assert hasattr(service, 'log_service_call')
        assert hasattr(service, 'log_database_operation')
        assert hasattr(service, 'service_name')
        assert service.service_name == "news_service"

def test_sync_manager_service_import_and_debug_mixin():
    """Test SyncManagerService can be imported and has debug capabilities."""
    from services.sync_manager_service import SyncManagerService
    
    # Mock dependencies
    mock_scheduler = Mock()
    mock_ingestion = Mock()
    mock_config = Mock()
    
    with patch.object(SyncManagerService, 'log_service_call'):
        service = SyncManagerService(mock_scheduler, mock_ingestion, mock_config)
        
        # Check it has both BaseService and ServiceDebugMixin methods
        assert hasattr(service, 'log_service_call')
        assert hasattr(service, 'service_name')
        assert hasattr(service, 'add_dependency')  # From BaseService

def test_ingestion_service_import_and_debug_mixin():
    """Test IngestionService can be imported and has debug capabilities."""
    from services.ingestion import IngestionService
    
    # Mock dependencies
    mock_database = Mock()
    mock_vector_store = Mock()
    mock_embedding_service = Mock()
    mock_config = Mock()
    
    with patch.object(IngestionService, 'log_service_call'):
        service = IngestionService(mock_database, mock_vector_store, mock_embedding_service, mock_config)
        
        # Check it has both BaseService and ServiceDebugMixin methods
        assert hasattr(service, 'log_service_call')
        assert hasattr(service, 'service_name')
        assert hasattr(service, 'add_dependency')  # From BaseService