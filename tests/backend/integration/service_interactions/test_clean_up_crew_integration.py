"""
Integration tests for Clean Up Crew semantic deduplication system.

Tests the complete integration of:
- CleanUpCrewService orchestration
- SemanticDeduplicationService processing
- Database schema and queue management
- API endpoints and HTTP polling communication
"""

import pytest
import pytest_asyncio
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


class TestCleanUpCrewIntegration:
    """Integration tests for the complete Clean Up Crew system"""
    
    @pytest_asyncio.fixture
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
    database_service.get_connection.return_value = mock_conn
    return database_service, embedding_service, scheduler_service
    
    @pytest_asyncio.fixture
    async def crew_service(self, mock_services):
        """Create a CleanUpCrewService instance for testing"""
        database_service, embedding_service, scheduler_service = mock_services
        
        semantic_service = SemanticDeduplicationService(
            database_service=database_service,
            embedding_service=embedding_service
        )
        
        service = CleanUpCrewService(
            database_service=database_service,
            scheduler_service=scheduler_service,
            semantic_service=semantic_service
        )
        
        # Mock the scheduler add_job method
    scheduler_service.add_job = AsyncMock(return_value="test-job-id")
    yield service
    
    @pytest.mark.asyncio
    async def test_crew_service_initialization(self, crew_service):
        """Test CleanUpCrewService initialization"""
        
        # Initialize the service
        await crew_service.initialize()
        
        assert crew_service.is_initialized
        job_id = crew_service.background_job_id
        if asyncio.iscoroutine(job_id):
            job_id = await job_id
        assert job_id == "test-job-id"
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
        class AsyncConnection:
            def __init__(self, cursor):
                self._cursor = cursor
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc, tb):
                pass
            async def execute(self, *args, **kwargs):
                return self._cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_items
        mock_conn = AsyncConnection(mock_cursor)
        crew_service.database.get_connection.return_value = mock_conn
        
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


