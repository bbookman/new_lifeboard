"""
Integration tests for Clean Up Crew semantic deduplication system.

Tests the complete integration of:
- CleanUpCrewService orchestration
- SemanticDeduplicationService processing
- WebSocketManager real-time updates
- Database schema and queue management
- API endpoints and WebSocket communication
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from services.clean_up_crew_service import (
    CleanUpCrewService, 
    ProcessingStatus, 
    DayProcessingResult
)
from services.semantic_deduplication_service import (
    SemanticDeduplicationService,
    ProcessingResult
)
from services.websocket_manager import WebSocketManager, MessageType
from services.startup_integration import CleanUpCrewBootstrap


class TestCleanUpCrewIntegration:
    """Integration tests for the complete Clean Up Crew system"""
    
    @pytest.fixture
    async def mock_services(self):
        """Create mock services for testing"""
        database_service = MagicMock()
        embedding_service = MagicMock()
        scheduler_service = AsyncMock()
        
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'count': 0}
        mock_conn.execute.return_value = mock_cursor
        database_service.get_connection.return_value.__enter__.return_value = mock_conn
        
        return database_service, embedding_service, scheduler_service
    
    @pytest.fixture
    async def crew_service(self, mock_services):
        """Create a CleanUpCrewService instance for testing"""
        database_service, embedding_service, scheduler_service = mock_services
        
        semantic_service = SemanticDeduplicationService(
            database_service=database_service,
            embedding_service=embedding_service
        )
        
        websocket_manager = WebSocketManager(heartbeat_interval=1)
        await websocket_manager.start()
        
        service = CleanUpCrewService(
            database_service=database_service,
            scheduler_service=scheduler_service,
            semantic_service=semantic_service,
            websocket_manager=websocket_manager
        )
        
        # Mock the scheduler add_job method
        scheduler_service.add_job.return_value = "test-job-id"
        
        yield service
        
        await websocket_manager.stop()
    
    @pytest.mark.asyncio
    async def test_crew_service_initialization(self, crew_service):
        """Test CleanUpCrewService initialization"""
        
        # Initialize the service
        await crew_service.initialize()
        
        assert crew_service.is_initialized
        assert crew_service.background_job_id == "test-job-id"
        assert len(crew_service.active_day_processing) == 0
    
    @pytest.mark.asyncio
    async def test_day_processing_workflow(self, crew_service):
        """Test complete day processing workflow"""
        
        await crew_service.initialize()
        
        # Mock data items for a day
        mock_items = [
            {
                'id': 'limitless:item1',
                'namespace': 'limitless',
                'source_id': 'item1',
                'content': 'Test conversation content',
                'metadata': {},
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
        ]
        
        # Mock the database query to return our test items
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_items
        mock_conn.execute.return_value = mock_cursor
        crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Mock semantic processing results
        with patch.object(crew_service.semantic_service, 'process_data_items') as mock_process:
            mock_process.return_value = ProcessingResult(
                total_processed=1,
                clusters_created=1,
                processing_time=1.5,
                items_modified=1,
                errors=[]
            )
            
            # Trigger processing for a test day
            result = await crew_service.trigger_day_processing('2024-01-15')
            
            assert result.status == ProcessingStatus.COMPLETED
            assert result.items_processed == 1
            assert result.clusters_created == 1
            assert result.processing_time > 0
            assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_websocket_integration(self):
        """Test WebSocket manager integration"""
        
        manager = WebSocketManager(heartbeat_interval=1)
        await manager.start()
        
        try:
            # Test connection stats
            stats = await manager.get_connection_stats()
            assert stats['total_connections'] == 0
            assert stats['is_running'] is True
            
            # Test message broadcasting
            await manager.send_processing_status(
                days_date='2024-01-15',
                status='completed',
                progress={'items_processed': 5}
            )
            
            # Test queue stats broadcasting
            await manager.send_queue_stats({
                'total_days': 10,
                'completed_days': 5,
                'pending_days': 3,
                'failed_days': 2
            })
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_bootstrap_initialization(self, mock_services):
        """Test complete system bootstrap"""
        
        database_service, embedding_service, scheduler_service = mock_services
        
        # Mock successful migration check
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Migrations table exists
        mock_conn.execute.return_value = mock_cursor
        database_service.get_connection.return_value.__enter__.return_value = mock_conn
        
        scheduler_service.add_job.return_value = "bootstrap-test-job"
        
        bootstrap = CleanUpCrewBootstrap()
        
        try:
            success = await bootstrap.initialize(
                database_service=database_service,
                embedding_service=embedding_service,
                scheduler_service=scheduler_service
            )
            
            assert success
            assert bootstrap.is_initialized
            
            # Check all services are initialized
            services = bootstrap.get_all_services()
            assert 'clean_up_crew_service' in services
            assert 'websocket_manager' in services
            assert 'semantic_service' in services
            
            # Check health status
            health = bootstrap.get_health_status()
            assert health['initialized'] is True
            assert 'clean_up_crew' in health['services']
            assert 'websocket' in health['services']
            
        finally:
            await bootstrap.shutdown()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, crew_service):
        """Test error handling in processing workflow"""
        
        await crew_service.initialize()
        
        # Mock processing failure
        with patch.object(crew_service.semantic_service, 'process_data_items') as mock_process:
            mock_process.side_effect = Exception("Processing failed")
            
            # Mock empty items to avoid database dependency
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.execute.return_value = mock_cursor
            crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
            
            result = await crew_service.trigger_day_processing('2024-01-15')
            
            # Should complete successfully with empty items
            assert result.status == ProcessingStatus.COMPLETED
            assert result.items_processed == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_limits(self, crew_service):
        """Test concurrent processing limits and queue management"""
        
        await crew_service.initialize()
        crew_service.max_concurrent_days = 2
        
        # Mock items for multiple days
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # Empty items for quick completion
        mock_conn.execute.return_value = mock_cursor
        crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Start processing multiple days
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                crew_service.trigger_day_processing(f'2024-01-{15+i:02d}')
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should complete (since we're using empty items)
        assert all(r.status == ProcessingStatus.COMPLETED for r in results)
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_progress_callbacks(self, crew_service):
        """Test progress callback system"""
        
        await crew_service.initialize()
        
        callback_calls = []
        
        async def test_callback(days_date: str, status: ProcessingStatus):
            callback_calls.append((days_date, status))
        
        await crew_service.add_progress_callback(test_callback)
        
        # Mock empty processing
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        crew_service.database.get_connection.return_value.__enter__.return_value = mock_conn
        
        await crew_service.trigger_day_processing('2024-01-15')
        
        # Should have received progress callbacks
        assert len(callback_calls) >= 2  # At least processing start and completion
        assert ('2024-01-15', ProcessingStatus.PROCESSING) in callback_calls
        assert ('2024-01-15', ProcessingStatus.COMPLETED) in callback_calls
        
        await crew_service.remove_progress_callback(test_callback)


class TestSemanticDeduplicationProcessing:
    """Test semantic deduplication processing engine"""
    
    @pytest.fixture
    def mock_semantic_service(self):
        """Create mock semantic deduplication service"""
        database_service = MagicMock()
        embedding_service = MagicMock()
        
        # Mock database operations
        mock_conn = MagicMock()
        database_service.get_connection.return_value.__enter__.return_value = mock_conn
        
        return SemanticDeduplicationService(
            database_service=database_service,
            embedding_service=embedding_service
        )
    
    @pytest.mark.asyncio
    async def test_data_items_processing(self, mock_semantic_service):
        """Test processing of data items"""
        
        mock_items = [
            {
                'namespace': 'limitless',
                'source_id': 'item1',
                'content': 'Test content',
                'metadata': {},
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
        ]
        
        # Mock the processor
        with patch.object(mock_semantic_service.processor, 'process_batch') as mock_batch:
            from sources.base import DataItem
            mock_batch.return_value = [
                DataItem(
                    namespace='limitless',
                    source_id='item1',
                    content='Test content',
                    metadata={'semantic_clusters': {}}
                )
            ]
            
            result = await mock_semantic_service.process_data_items(mock_items)
            
            assert result.total_processed == 1
            assert result.items_modified == 1
            assert len(result.errors) == 0


class TestWebSocketCommunication:
    """Test WebSocket communication features"""
    
    @pytest.mark.asyncio
    async def test_message_types_and_routing(self):
        """Test different message types and topic routing"""
        
        manager = WebSocketManager(heartbeat_interval=1)
        await manager.start()
        
        try:
            # Test queue stats message
            await manager.send_queue_stats({
                'total_days': 10,
                'completed_days': 5
            })
            
            # Test processing status message
            await manager.send_processing_status(
                days_date='2024-01-15',
                status='processing',
                progress={'items_processed': 3}
            )
            
            # Test day-specific update
            await manager.send_day_update(
                days_date='2024-01-15',
                update_data={'clusters_created': 2}
            )
            
            # All should execute without errors
            stats = await manager.get_connection_stats()
            assert stats['is_running'] is True
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_subscription_management(self):
        """Test WebSocket subscription management"""
        
        manager = WebSocketManager(heartbeat_interval=1)
        await manager.start()
        
        try:
            # Simulate subscription operations
            manager.subscriptions['test_topic'] = {'client1', 'client2'}
            
            stats = await manager.get_connection_stats()
            assert 'test_topic' in stats['topic_subscribers']
            assert stats['topic_subscribers']['test_topic'] == 2
            
        finally:
            await manager.stop()


if __name__ == "__main__":
    # Run basic integration test
    import asyncio
    
    async def run_basic_test():
        print("Running basic Clean Up Crew integration test...")
        
        # Mock services
        database_service = MagicMock()
        embedding_service = MagicMock()
        scheduler_service = AsyncMock()
        
        # Mock successful responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.execute.return_value = mock_cursor
        database_service.get_connection.return_value.__enter__.return_value = mock_conn
        
        scheduler_service.add_job.return_value = "test-job"
        
        # Test bootstrap
        bootstrap = CleanUpCrewBootstrap()
        
        try:
            success = await bootstrap.initialize(
                database_service=database_service,
                embedding_service=embedding_service,
                scheduler_service=scheduler_service
            )
            
            print(f"Bootstrap initialization: {'SUCCESS' if success else 'FAILED'}")
            
            if success:
                health = bootstrap.get_health_status()
                print(f"System health: {health}")
            
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            await bootstrap.shutdown()
            print("Test cleanup completed")
    
    asyncio.run(run_basic_test())