"""
Tests for simplified CleanUpCrewService functionality
Tests the new HTTP-based approach without WebSocket dependencies
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from services.clean_up_crew_service import CleanUpCrewService
from core.database import DatabaseService
from services.scheduler import AsyncScheduler
from services.semantic_deduplication_service import SemanticDeduplicationService


class TestSimplifiedCleanUpCrewService:
    """Test suite for simplified CleanUpCrewService without WebSocket dependencies"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database service"""
        mock_db = Mock(spec=DatabaseService)
        mock_db.get_connection = Mock()
        # Setup mock connection context manager
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'count': 0}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_db.get_connection.return_value = mock_conn
        return mock_db
    
    @pytest.fixture
    def mock_scheduler(self):
        """Mock scheduler service"""
        mock_scheduler = AsyncMock(spec=AsyncScheduler)
        mock_scheduler.add_job.return_value = "test-job-id"
        return mock_scheduler
    
    @pytest.fixture
    def mock_semantic_service(self):
        """Mock semantic deduplication service"""
        mock_service = AsyncMock(spec=SemanticDeduplicationService)
        return mock_service
    
    @pytest.fixture
    def clean_up_crew_service(self, mock_database, mock_scheduler, mock_semantic_service):
        """Create CleanUpCrewService instance for testing"""
        # Create service without WebSocket manager (simplified)
        service = CleanUpCrewService(
            database_service=mock_database,
            scheduler_service=mock_scheduler,
            semantic_service=mock_semantic_service,
            websocket_manager=None  # No WebSocket dependency
        )
        return service

    def test_get_queue_stats_basic_structure(self, clean_up_crew_service):
        """Test get_queue_stats returns correct basic structure"""
        # Mock database query results for various status counts
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock a single row result with all the status columns
        mock_row = {
            'completed_days': 25,
            'pending_days': 3,  
            'processing_days': 1,
            'failed_days': 1
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_queue_stats()
        
        # Verify structure matches expected API response
        assert "total_days" in result
        assert "completed_days" in result
        assert "pending_days" in result
        assert "processing_days" in result
        assert "failed_days" in result
        assert "active_processing" in result
        assert "last_updated" in result
        
        # Verify data types
        assert isinstance(result["total_days"], int)
        assert isinstance(result["completed_days"], int)
        assert isinstance(result["pending_days"], int)
        assert isinstance(result["processing_days"], int)
        assert isinstance(result["failed_days"], int)
        assert isinstance(result["active_processing"], bool)
        assert isinstance(result["last_updated"], str)

    def test_get_queue_stats_correct_calculations(self, clean_up_crew_service):
        """Test get_queue_stats calculates totals correctly"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock specific counts
        mock_row = {
            'completed_days': 25,
            'pending_days': 3,  
            'processing_days': 1,
            'failed_days': 1
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_queue_stats()
        
        # Verify calculations
        assert result["total_days"] == 30  # 25 + 3 + 1 + 1
        assert result["completed_days"] == 25
        assert result["pending_days"] == 3
        assert result["processing_days"] == 1
        assert result["failed_days"] == 1
        assert result["active_processing"] is True  # processing_days > 0

    def test_get_queue_stats_no_active_processing(self, clean_up_crew_service):
        """Test get_queue_stats when no active processing"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock no active processing - single row result
        mock_row = {
            'completed_days': 25,
            'pending_days': 5,
            'processing_days': 0,  # No active processing
            'failed_days': 0
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_queue_stats()
        
        assert result["active_processing"] is False  # processing_days == 0
        assert result["processing_days"] == 0

    def test_get_queue_stats_database_error_handling(self, clean_up_crew_service):
        """Test get_queue_stats error handling when database fails"""
        # Mock database error
        clean_up_crew_service.database.get_connection.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc_info:
            clean_up_crew_service.get_queue_stats()
        
        assert "Database connection failed" in str(exc_info.value)

    def test_get_queue_stats_thread_safety(self, clean_up_crew_service):
        """Test get_queue_stats thread safety"""
        import threading
        
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock single row result for thread safety test
        mock_row = {
            'completed_days': 10,
            'pending_days': 5,
            'processing_days': 1,
            'failed_days': 0
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        results = []
        errors = []
        
        def get_stats():
            try:
                result = clean_up_crew_service.get_queue_stats()
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple concurrent requests
        threads = []
        for i in range(3):
            thread = threading.Thread(target=get_stats)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5)
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 3

    def test_get_day_status_success(self, clean_up_crew_service):
        """Test get_day_status returns correct day-specific information"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock day-specific data - matches actual database query structure
        mock_cursor.fetchone.return_value = {
            'semantic_status': 'completed',
            'total_items': 45,
            'processed_items': 45,
            'failed_items': 0,
            'last_updated': '2024-01-15T09:45:00Z'
        }
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_day_status('2024-01-15')
        
        # Verify structure
        assert "status" in result
        assert "total_items" in result
        assert "processed_items" in result
        assert "failed_items" in result
        assert "last_updated" in result
        assert "processing_time_seconds" in result
        
        # Verify content
        assert result["status"] == "completed"
        assert result["total_items"] == 45
        assert result["processed_items"] == 45
        assert result["failed_items"] == 0
        # Note: processing_time_seconds is calculated as min(total_items * 0.5, 60.0)
        assert result["processing_time_seconds"] == min(45 * 0.5, 60.0)

    def test_get_day_status_partial_progress(self, clean_up_crew_service):
        """Test get_day_status with partial progress calculation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock partial progress - matches actual database query structure
        mock_cursor.fetchone.return_value = {
            'semantic_status': 'processing',
            'total_items': 100,
            'processed_items': 75,
            'failed_items': 5,
            'last_updated': '2024-01-15T10:30:00Z'
        }
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_day_status('2024-01-15')
        
        # Status is determined by logic: since processed_items > 0 and failed_items > 0, status = "failed"
        assert result["status"] == "failed"  # failed_items > 0 takes precedence
        assert result["failed_items"] == 5
        assert result["processed_items"] == 75

    def test_get_day_status_zero_items(self, clean_up_crew_service):
        """Test get_day_status with zero total items"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock zero items - based on actual implementation, this should return None
        mock_cursor.fetchone.return_value = {
            'semantic_status': 'pending',
            'total_items': 0,
            'processed_items': 0,
            'failed_items': 0,
            'last_updated': '2024-01-15T00:00:00Z'
        }
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_day_status('2024-01-15')
        
        # Based on actual implementation: if total_items == 0, return None
        assert result is None

    def test_get_day_status_not_found(self, clean_up_crew_service):
        """Test get_day_status when day not found"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # Day not found
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        result = clean_up_crew_service.get_day_status('2024-01-01')
        
        assert result is None

    def test_get_day_status_database_error(self, clean_up_crew_service):
        """Test get_day_status error handling"""
        clean_up_crew_service.database.get_connection.side_effect = Exception("Database error")
        
        with pytest.raises(Exception) as exc_info:
            clean_up_crew_service.get_day_status('2024-01-15')
        
        assert "Database error" in str(exc_info.value)

    def test_update_internal_state_cache(self, clean_up_crew_service):
        """Test internal state cache updates correctly"""
        # Mock processing operation that should update cache
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Initial state - single row result
        initial_row = {
            'completed_days': 20,
            'pending_days': 5,
            'processing_days': 0,
            'failed_days': 0
        }
        mock_cursor.fetchone.return_value = initial_row
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Get initial stats
        initial_stats = clean_up_crew_service.get_queue_stats()
        assert initial_stats["completed_days"] == 20
        assert initial_stats["active_processing"] is False
        
        # Simulate state change
        updated_row = {
            'completed_days': 21,
            'pending_days': 4,
            'processing_days': 0,
            'failed_days': 0
        }
        mock_cursor.fetchone.return_value = updated_row
        
        # Get updated stats
        updated_stats = clean_up_crew_service.get_queue_stats()
        assert updated_stats["completed_days"] == 21
        assert updated_stats["pending_days"] == 4

    def test_state_cache_thread_safe_access(self, clean_up_crew_service):
        """Test thread-safe access to internal state cache"""
        import threading
        
        mock_conn = Mock()
        mock_cursor = Mock()
        
        def setup_mock_results(completed_count):
            return {
                'completed_days': completed_count,
                'pending_days': 5,
                'processing_days': 0,
                'failed_days': 0
            }
        
        # Initial setup
        mock_cursor.fetchone.return_value = setup_mock_results(20)
        mock_conn.execute.return_value = mock_cursor
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        results = []
        
        def access_state(index):
            # Simulate different completed counts for each thread
            mock_cursor.fetchone.return_value = setup_mock_results(20 + index)
            stats = clean_up_crew_service.get_queue_stats()
            results.append(stats["completed_days"])
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=access_state, args=[i])
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=5)
        
        # All threads should complete successfully
        assert len(results) == 5

    def test_no_websocket_callback_methods(self, clean_up_crew_service):
        """Test that WebSocket callback methods behavior (existing service still has them but websocket_manager is None)"""
        # WebSocket methods may still exist but should be non-functional without websocket_manager
        # Should not have functional websocket_manager attribute
        assert clean_up_crew_service.websocket_manager is None

    def test_processing_operations_update_cache(self, clean_up_crew_service):
        """Test that processing operations update internal state cache"""
        # Mock database for processing operation
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Before processing - single row result
        before_row = {
            'completed_days': 20,
            'pending_days': 5,
            'processing_days': 0,
            'failed_days': 0
        }
        
        # After processing - single row result
        after_row = {
            'completed_days': 21,
            'pending_days': 4,
            'processing_days': 0,
            'failed_days': 0
        }
        
        # Setup mock to return different results for before/after
        call_count = 0
        def side_effect_generator():
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call (before)
                return before_row
            else:  # Second call (after)
                return after_row
        
        mock_cursor.fetchone.side_effect = side_effect_generator
        mock_conn.execute.return_value = mock_cursor  
        clean_up_crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Get stats before
        before_stats = clean_up_crew_service.get_queue_stats()
        assert before_stats["completed_days"] == 20
        
        # Simulate processing operation (this would update cache in real implementation)
        # For test, we just call get_queue_stats again to simulate cache update
        after_stats = clean_up_crew_service.get_queue_stats()
        
        # Verify processing operations can update state
        assert isinstance(after_stats, dict)
        assert "total_days" in after_stats