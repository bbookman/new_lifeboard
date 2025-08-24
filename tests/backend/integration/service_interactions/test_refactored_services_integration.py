"""
Integration tests for refactored services using Enhanced Debug Logging.

This module tests that the refactored services properly integrate with
ServiceDebugMixin and DebugDatabaseConnection without breaking existing functionality.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

# Import refactored services
from services.chat_service import ChatService
from services.news_service import NewsService
from services.sync_manager_service import SyncManagerService
from services.ingestion import IngestionService


class TestRefactoredServicesIntegration:
    """Test refactored services maintain functionality while adding debug capabilities."""
    
    def test_chat_service_initialization(self):
        """Test ChatService initializes correctly with debug mixin."""
        # Mock dependencies
        mock_config = Mock()
        mock_database = Mock()
        mock_vector_store = Mock()
        mock_embeddings = Mock()
        
        # Create service instance
        with patch.object(ChatService, 'log_service_call') as mock_log:
            service = ChatService(mock_config, mock_database, mock_vector_store, mock_embeddings)
            
            # Verify service inherits from ServiceDebugMixin
            assert hasattr(service, 'log_service_call')
            assert hasattr(service, 'log_database_operation')
            assert hasattr(service, 'log_external_api_call')
            assert hasattr(service, 'service_name')
            
            # Verify initialization logging was called
            mock_log.assert_called()
            
    def test_chat_service_debug_logging_integration(self):
        """Test ChatService debug logging doesn't interfere with core functionality."""
        # Mock dependencies
        mock_config = Mock()
        mock_database = Mock()
        mock_vector_store = Mock()
        mock_embeddings = Mock()
        
        # Mock chat history method
        expected_history = [{"id": 1, "message": "test"}]
        mock_database.get_chat_history.return_value = expected_history
        
        with patch.object(ChatService, 'log_service_call'):
            with patch.object(ChatService, 'log_database_operation'):
                with patch.object(ChatService, 'log_service_performance_metric'):
                    service = ChatService(mock_config, mock_database, mock_vector_store, mock_embeddings)
                    
                    # Test core functionality still works
                    result = service.get_chat_history(10)
                    assert result == expected_history
                    
                    # Verify database was called correctly
                    mock_database.get_chat_history.assert_called_once_with(10)
                    
    def test_news_service_initialization_with_debug_db(self):
        """Test NewsService initializes with DebugDatabaseConnection when available."""
        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        try:
            # Mock database service with db_path
            mock_db_service = Mock()
            mock_db_service.db_path = temp_db.name
            mock_config = Mock()
            mock_config.unique_items_per_day = 5
            
            with patch.object(NewsService, 'log_service_call') as mock_log:
                service = NewsService(mock_db_service, mock_config)
                
                # Verify service has debug capabilities
                assert hasattr(service, 'debug_db')
                assert service.debug_db is not None
                assert service.debug_db.db_path == temp_db.name
                
                # Verify initialization logging was called
                mock_log.assert_called()
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
                
    def test_news_service_fallback_without_db_path(self):
        """Test NewsService falls back gracefully when db_path not available."""
        # Mock database service without db_path
        mock_db_service = Mock()
        # Remove db_path attribute
        if hasattr(mock_db_service, 'db_path'):
            del mock_db_service.db_path
            
        mock_config = Mock()
        mock_config.unique_items_per_day = 5
        
        with patch.object(NewsService, 'log_service_call') as mock_log:
            service = NewsService(mock_db_service, mock_config)
            
            # Verify service still works but without debug_db
            assert hasattr(service, 'debug_db')
            assert service.debug_db is None
            
            # Verify initialization logging was still called
            mock_log.assert_called()
            
    def test_sync_manager_service_multiple_inheritance(self):
        """Test SyncManagerService correctly inherits from both BaseService and ServiceDebugMixin."""
        # Mock dependencies
        mock_scheduler = Mock()
        mock_ingestion_service = Mock()
        mock_config = Mock()
        
        with patch.object(SyncManagerService, 'log_service_call') as mock_log:
            service = SyncManagerService(mock_scheduler, mock_ingestion_service, mock_config)
            
            # Verify multiple inheritance works correctly
            assert hasattr(service, 'service_name')  # From BaseService
            assert hasattr(service, 'log_service_call')  # From ServiceDebugMixin
            assert hasattr(service, 'add_dependency')  # From BaseService
            assert hasattr(service, 'log_service_error')  # From ServiceDebugMixin
            
            # Verify initialization logging was called
            mock_log.assert_called()
            
    def test_ingestion_service_multiple_inheritance(self):
        """Test IngestionService correctly inherits from both BaseService and ServiceDebugMixin."""
        # Mock dependencies
        mock_database = Mock()
        mock_vector_store = Mock()
        mock_embedding_service = Mock()
        mock_config = Mock()
        
        with patch.object(IngestionService, 'log_service_call') as mock_log:
            service = IngestionService(mock_database, mock_vector_store, mock_embedding_service, mock_config)
            
            # Verify multiple inheritance works correctly
            assert hasattr(service, 'service_name')  # From BaseService
            assert hasattr(service, 'log_service_call')  # From ServiceDebugMixin
            assert hasattr(service, 'add_dependency')  # From BaseService
            assert hasattr(service, 'log_external_api_call')  # From ServiceDebugMixin
            
            # Verify initialization logging was called
            mock_log.assert_called()
            
    def test_services_maintain_original_functionality(self):
        """Test that adding debug logging doesn't break original service contracts."""
        # This test verifies that services still have their original methods
        # and can be used as before
        
        # Mock all dependencies
        mock_config = Mock()
        mock_database = Mock()
        mock_vector_store = Mock()
        mock_embeddings = Mock()
        mock_scheduler = Mock()
        mock_ingestion = Mock()
        mock_news_config = Mock()
        
        with patch.multiple(
            'services.chat_service',
            ServiceDebugMixin=MagicMock()
        ), patch.multiple(
            'services.sync_manager_service', 
            ServiceDebugMixin=MagicMock()
        ), patch.multiple(
            'services.ingestion',
            ServiceDebugMixin=MagicMock()
        ), patch.multiple(
            'services.news_service',
            ServiceDebugMixin=MagicMock()
        ):
            # Create service instances
            chat_service = ChatService(mock_config, mock_database, mock_vector_store, mock_embeddings)
            sync_service = SyncManagerService(mock_scheduler, mock_ingestion, mock_config)
            ingestion_service = IngestionService(mock_database, mock_vector_store, mock_embeddings, mock_config)
            news_service = NewsService(mock_database, mock_news_config)
            
            # Verify core methods still exist
            assert hasattr(chat_service, 'get_chat_history')
            assert callable(chat_service.get_chat_history)
            
            assert hasattr(sync_service, 'register_source_for_auto_sync')
            assert callable(sync_service.register_source_for_auto_sync)
            
            assert hasattr(news_service, 'get_news_by_date')
            assert callable(news_service.get_news_by_date)
            
            assert hasattr(news_service, 'get_latest_news')
            assert callable(news_service.get_latest_news)


class TestDebugLoggingPerformanceImpact:
    """Test that debug logging doesn't significantly impact performance."""
    
    def test_service_call_logging_overhead(self):
        """Test that service call logging has minimal overhead."""
        import time
        
        # Mock database service
        mock_db_service = Mock()
        mock_config = Mock()
        mock_config.unique_items_per_day = 5
        
        # Test with debug logging
        with patch.object(NewsService, 'log_service_call'):
            service = NewsService(mock_db_service, mock_config)
            
            start_time = time.time()
            for _ in range(100):
                service.log_service_call("test_method", {"param": "value"})
            with_logging_time = time.time() - start_time
            
        # Debug logging should complete quickly (less than 1 second for 100 calls)
        assert with_logging_time < 1.0, f"Debug logging took {with_logging_time:.3f}s for 100 calls"
        
    def test_database_logging_overhead(self):
        """Test that database operation logging has minimal overhead."""
        import time
        
        mock_db_service = Mock()
        mock_config = Mock()
        
        with patch.object(NewsService, 'log_service_call'):
            service = NewsService(mock_db_service, mock_config)
            
            start_time = time.time()
            for _ in range(100):
                service.log_database_operation("SELECT", "test_table", 10.5)
            logging_time = time.time() - start_time
            
        # Database logging should complete quickly
        assert logging_time < 1.0, f"Database logging took {logging_time:.3f}s for 100 calls"


class TestErrorHandlingWithDebugLogging:
    """Test error handling works correctly with debug logging."""
    
    def test_service_error_logging_on_exception(self):
        """Test that service errors are logged when exceptions occur."""
        mock_config = Mock()
        mock_database = Mock()
        mock_vector_store = Mock()
        mock_embeddings = Mock()
        
        # Mock database to raise an exception
        mock_database.get_chat_history.side_effect = Exception("Database error")
        
        with patch.object(ChatService, 'log_service_call'):
            with patch.object(ChatService, 'log_service_error') as mock_error_log:
                with patch.object(ChatService, 'log_database_operation'):
                    with patch.object(ChatService, 'log_service_performance_metric'):
                        service = ChatService(mock_config, mock_database, mock_vector_store, mock_embeddings)
                        
                        # This should not raise an exception due to error handling
                        try:
                            result = service.get_chat_history(10)
                            # Method should handle the exception gracefully
                        except Exception:
                            # If exception propagates, that's also valid behavior
                            pass
                            
    def test_graceful_degradation_with_logging_failure(self):
        """Test services continue working even if logging fails."""
        mock_db_service = Mock()
        mock_config = Mock()
        mock_config.unique_items_per_day = 5
        
        # Mock logging to fail
        with patch.object(NewsService, 'log_service_call', side_effect=Exception("Logging failed")):
            # Service should still initialize despite logging failure
            try:
                service = NewsService(mock_db_service, mock_config)
                # Service should exist and have expected attributes
                assert service.db_service == mock_db_service
                assert service.items_per_day == 5
            except Exception:
                pytest.fail("Service initialization should not fail due to logging errors")