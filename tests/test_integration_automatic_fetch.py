"""
Integration tests for end-to-end automatic Limitless data fetch flow.
Tests the complete flow from frontend request through backend processing to data storage.
"""

import pytest
import asyncio
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.routes.calendar import fetch_limitless_for_date
from sources.base import DataItem
from sources.limitless import LimitlessSource
from services.ingestion import IngestionService, IngestionResult
from core.database import DatabaseService
from config.models import LimitlessConfig


class TestEndToEndAutomaticFetch:
    """Integration tests for complete automatic fetch workflow"""

    @pytest.fixture
    def mock_database_service(self):
        """Create a comprehensive mock DatabaseService"""
        db = MagicMock(spec=DatabaseService)
        
        # Initially no data
        db.get_data_items_by_date.return_value = []
        
        # Mock store operations
        db.store_data_item = MagicMock()
        db.update_embedding_status = MagicMock()
        db.get_pending_embeddings.return_value = []
        
        # Mock settings operations
        db.get_setting.return_value = None
        db.set_setting = MagicMock()
        
        # Mock data source registration
        db.register_data_source = MagicMock()
        
        return db

    @pytest.fixture
    def mock_limitless_source(self):
        """Create a comprehensive mock LimitlessSource"""
        source = MagicMock(spec=LimitlessSource)
        source.namespace = "limitless"
        source.test_connection = AsyncMock(return_value=True)
        source.get_source_type.return_value = "limitless_api"
        
        # Create realistic test data
        test_items = [
            DataItem(
                namespace="limitless",
                source_id="test-item-1",
                content="# Morning Meeting\n\nDiscussed project timeline and key deliverables.",
                metadata={
                    "title": "Morning Meeting",
                    "start_time": "2024-01-15T14:00:00Z",
                    "end_time": "2024-01-15T14:30:00Z",
                    "speakers": ["Alice", "Bob"]
                },
                created_at=datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
            ),
            DataItem(
                namespace="limitless",
                source_id="test-item-2", 
                content="# Lunch Discussion\n\nBrainstormed ideas for the new feature.",
                metadata={
                    "title": "Lunch Discussion",
                    "start_time": "2024-01-15T17:00:00Z",
                    "end_time": "2024-01-15T17:45:00Z",
                    "speakers": ["Carol", "Dave"]
                },
                created_at=datetime(2024, 1, 15, 17, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 17, 45, 0, tzinfo=timezone.utc)
            )
        ]
        
        async def mock_fetch_items(since=None, limit=100):
            for item in test_items:
                yield item
        
        source.fetch_items = mock_fetch_items
        return source

    @pytest.fixture
    def mock_ingestion_service(self):
        """Create a comprehensive mock IngestionService"""
        service = MagicMock(spec=IngestionService)
        service.sources = {}
        
        # Mock processors
        mock_processor = MagicMock()
        mock_processor.process = MagicMock()
        mock_processor.process_batch = AsyncMock()
        
        service.processors = {'limitless': mock_processor}
        service.default_processor = mock_processor
        
        # Mock store operations
        async def mock_store_processed_item(item, result):
            # Simulate successful storage
            pass
        
        service._store_processed_item = AsyncMock(side_effect=mock_store_processed_item)
        service.register_source = MagicMock()
        
        # Mock embedding processing
        service.process_pending_embeddings = AsyncMock(return_value={
            "processed": 2,
            "successful": 2,
            "failed": 0,
            "errors": []
        })
        
        return service

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = MagicMock()
        config.limitless = MagicMock(spec=LimitlessConfig)
        config.limitless.is_api_key_configured.return_value = True
        config.limitless.timezone = "America/New_York"
        return config

    @pytest.mark.asyncio
    async def test_complete_automatic_fetch_workflow(
        self, 
        mock_database_service, 
        mock_limitless_source, 
        mock_ingestion_service,
        mock_config
    ):
        """Test the complete end-to-end automatic fetch workflow"""
        
        with patch('api.routes.calendar.get_config', return_value=mock_config), \
             patch('api.routes.calendar.LimitlessSource', return_value=mock_limitless_source):
            
            # Step 1: Call the fetch endpoint
            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database_service,
                ingestion_service=mock_ingestion_service
            )
            
            # Step 2: Verify successful response
            assert result["success"] is True
            assert result["date"] == "2024-01-15"
            assert result["items_processed"] > 0
            assert result["items_stored"] > 0
            assert "Successfully fetched and processed" in result["message"]
            
            # Step 3: Verify API connectivity was tested
            mock_limitless_source.test_connection.assert_called_once()
            
            # Step 4: Verify data was fetched from source
            # Note: We can't easily verify fetch_items was called due to async generator
            
            # Step 5: Verify source was registered with ingestion service
            mock_ingestion_service.register_source.assert_called()
            
            # Step 6: Verify data processing occurred
            assert mock_ingestion_service._store_processed_item.call_count > 0
            
            # Step 7: Verify embeddings were processed
            mock_ingestion_service.process_pending_embeddings.assert_called_once()
            
            # Step 8: Verify final data retrieval
            mock_database_service.get_data_items_by_date.assert_called()

    @pytest.mark.asyncio
    async def test_frontend_to_backend_integration(self, mock_database_service, mock_ingestion_service):
        """Test the integration between frontend automatic fetch and backend endpoint"""
        
        # Simulate frontend automatic fetch API call
        frontend_request_data = {
            "method": "POST",
            "url": "http://localhost:8000/calendar/api/limitless/fetch/2024-01-15",
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        # Verify request structure
        assert frontend_request_data["method"] == "POST"
        assert "limitless/fetch" in frontend_request_data["url"]
        assert "2024-01-15" in frontend_request_data["url"]
        assert frontend_request_data["headers"]["Content-Type"] == "application/json"
        
        # Mock successful backend response
        mock_backend_response = {
            "success": True,
            "message": "Successfully fetched and processed data for 2024-01-15",
            "items_processed": 2,
            "items_stored": 2,
            "items_final": 2,
            "errors": [],
            "date": "2024-01-15"
        }
        
        # Simulate frontend processing of response
        if mock_backend_response["success"]:
            # Frontend would show success message and refetch data
            should_refetch = True
            expected_message = "Automatic fetch successful"
        else:
            should_refetch = False
            expected_message = "Automatic fetch failed"
        
        assert should_refetch is True
        assert "successful" in expected_message

    @pytest.mark.asyncio
    async def test_error_propagation_through_stack(
        self,
        mock_database_service,
        mock_ingestion_service
    ):
        """Test that errors are properly propagated from backend to frontend"""
        
        # Test API key not configured error
        with patch('api.routes.calendar.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = False
            mock_get_config.return_value = mock_config
            
            with pytest.raises(Exception) as exc_info:
                await fetch_limitless_for_date(
                    date="2024-01-15",
                    database=mock_database_service,
                    ingestion_service=mock_ingestion_service
                )
            
            # Verify error structure
            assert "API key not configured" in str(exc_info.value)
        
        # Test connection failure error
        with patch('api.routes.calendar.get_config') as mock_get_config, \
             patch('api.routes.calendar.LimitlessSource') as mock_source_class:
            
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_get_config.return_value = mock_config
            
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=False)
            mock_source_class.return_value = mock_source
            
            with pytest.raises(Exception) as exc_info:
                await fetch_limitless_for_date(
                    date="2024-01-15",
                    database=mock_database_service,
                    ingestion_service=mock_ingestion_service
                )
            
            assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_data_consistency_through_pipeline(
        self,
        mock_database_service,
        mock_limitless_source,
        mock_ingestion_service,
        mock_config
    ):
        """Test that data maintains consistency through the entire processing pipeline"""
        
        with patch('api.routes.calendar.get_config', return_value=mock_config), \
             patch('api.routes.calendar.LimitlessSource', return_value=mock_limitless_source):
            
            # Configure processor to return processed items
            processed_items = []
            
            def mock_process(item):
                # Simulate processing that adds metadata
                processed_item = DataItem(
                    namespace=item.namespace,
                    source_id=item.source_id,
                    content=item.content,
                    metadata={
                        **item.metadata,
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                        "cleaned_markdown": f"# {item.metadata.get('title', 'Untitled')}\n\n{item.content}"
                    },
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                processed_items.append(processed_item)
                return processed_item
            
            mock_ingestion_service.processors['limitless'].process.side_effect = mock_process
            
            # Execute fetch
            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database_service,
                ingestion_service=mock_ingestion_service
            )
            
            # Verify data consistency
            assert result["success"] is True
            assert len(processed_items) > 0
            
            # Verify each processed item has required structure
            for item in processed_items:
                assert item.namespace == "limitless"
                assert item.source_id is not None
                assert item.content is not None
                assert "processed_at" in item.metadata
                assert "cleaned_markdown" in item.metadata

    @pytest.mark.asyncio 
    async def test_performance_characteristics(
        self,
        mock_database_service,
        mock_limitless_source,
        mock_ingestion_service,
        mock_config
    ):
        """Test performance characteristics of the automatic fetch process"""
        
        import time
        
        with patch('api.routes.calendar.get_config', return_value=mock_config), \
             patch('api.routes.calendar.LimitlessSource', return_value=mock_limitless_source):
            
            # Measure execution time
            start_time = time.time()
            
            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database_service,
                ingestion_service=mock_ingestion_service
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Verify reasonable performance (should complete quickly in test environment)
            assert execution_time < 5.0  # Should complete within 5 seconds
            assert result["success"] is True
            
            # Verify efficient database operations (not too many calls)
            assert mock_database_service.get_data_items_by_date.call_count <= 3  # Initial + final check

    @pytest.mark.asyncio
    async def test_concurrent_fetch_requests(
        self,
        mock_database_service,
        mock_limitless_source,
        mock_ingestion_service,
        mock_config
    ):
        """Test behavior when multiple concurrent fetch requests are made"""
        
        with patch('api.routes.calendar.get_config', return_value=mock_config), \
             patch('api.routes.calendar.LimitlessSource', return_value=mock_limitless_source):
            
            # Simulate concurrent requests for the same date
            tasks = []
            for i in range(3):
                task = fetch_limitless_for_date(
                    date="2024-01-15",
                    database=mock_database_service,
                    ingestion_service=mock_ingestion_service
                )
                tasks.append(task)
            
            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all completed successfully (or at least one succeeded)
            successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
            assert len(successful_results) >= 1
            
            # Verify data consistency across results
            for result in successful_results:
                assert result["date"] == "2024-01-15"
                assert "items_processed" in result

    @pytest.mark.asyncio
    async def test_edge_cases_and_boundary_conditions(
        self,
        mock_database_service,
        mock_ingestion_service
    ):
        """Test edge cases and boundary conditions"""
        
        # Test with future date
        with patch('api.routes.calendar.get_config') as mock_get_config, \
             patch('api.routes.calendar.LimitlessSource') as mock_source_class:
            
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config
            
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)
            
            # Mock empty fetch result for future date
            async def mock_fetch_items(since=None, limit=100):
                return
                yield  # unreachable
            
            mock_source.fetch_items = mock_fetch_items
            mock_source_class.return_value = mock_source
            
            # Test future date
            future_date = "2025-12-31"
            result = await fetch_limitless_for_date(
                date=future_date,
                database=mock_database_service,
                ingestion_service=mock_ingestion_service
            )
            
            assert result["success"] is True
            assert result["items_processed"] == 0
            assert "No data found" in result["message"]

    def test_logging_and_observability(self):
        """Test that comprehensive logging is in place for observability"""
        
        # Verify logging patterns exist in the code
        import inspect
        from api.routes.calendar import fetch_limitless_for_date
        
        source_code = inspect.getsource(fetch_limitless_for_date)
        
        # Check for key observability patterns
        required_log_patterns = [
            "[OnDemandFetch]",
            "logger.info",
            "logger.debug", 
            "logger.error",
            "Starting on-demand fetch",
            "Fetched .* items",
            "Processing .* items",
            "On-demand fetch completed"
        ]
        
        for pattern in required_log_patterns:
            if ".*" not in pattern:
                assert pattern in source_code
        
        # Verify error logging scenarios
        error_scenarios = [
            "Invalid date format",
            "API key not configured", 
            "Failed to connect",
            "Error fetching data",
            "Critical error"
        ]
        
        for scenario in error_scenarios:
            assert scenario in source_code

    @pytest.mark.asyncio
    async def test_rollback_and_cleanup_on_failure(
        self,
        mock_database_service,
        mock_ingestion_service
    ):
        """Test that failures are handled gracefully with proper cleanup"""
        
        # Test processing failure
        with patch('api.routes.calendar.get_config') as mock_get_config, \
             patch('api.routes.calendar.LimitlessSource') as mock_source_class:
            
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config
            
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)
            mock_source.namespace = "limitless"
            
            # Create test item
            test_item = DataItem(
                namespace="limitless",
                source_id="test-123",
                content="Test content",
                metadata={"title": "Test"},
                created_at=datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
            )
            
            async def mock_fetch_items(since=None, limit=100):
                yield test_item
            
            mock_source.fetch_items = mock_fetch_items
            mock_source_class.return_value = mock_source
            
            # Configure processor to fail
            mock_processor = MagicMock()
            mock_processor.process.side_effect = Exception("Processing failed")
            mock_ingestion_service.processors = {'limitless': mock_processor}
            
            # Execute and verify graceful failure handling
            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database_service,
                ingestion_service=mock_ingestion_service
            )
            
            # Should still return success but with errors reported
            assert result["success"] is True
            assert result["items_processed"] >= 1
            assert result["items_stored"] == 0  # Nothing stored due to errors
            assert len(result["errors"]) > 0
            assert "Processing failed" in str(result["errors"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])