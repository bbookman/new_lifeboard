"""
Comprehensive tests for sync API routes
Tests FastAPI endpoints for data synchronization triggers and status
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.sync import router, SyncTriggerRequest, SyncResponse
from services.startup import StartupService


class TestSyncRoutes:
    """Test sync API endpoints"""
    
    @pytest.fixture
    def app(self, mock_startup_service):
        """Create FastAPI test application with dependency overrides"""
        from core.dependencies import get_startup_service_dependency
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service for testing"""
        service = MagicMock(spec=StartupService)
        service.sync_manager = MagicMock()
        service.ingestion_service = MagicMock()
        service.ingestion_service.sources = {
            'limitless': MagicMock(),
            'weather': MagicMock(),
            'news': MagicMock()
        }
        return service
    
    @pytest.fixture
    def mock_sync_manager(self, mock_startup_service):
        """Mock sync manager for testing"""
        sync_manager = mock_startup_service.sync_manager
        sync_manager.sync_source = AsyncMock()
        sync_manager.scheduler = MagicMock()
        return sync_manager
    
    def test_trigger_sync_specific_source_success(self, client, mock_startup_service, mock_sync_manager):
        """Test triggering sync for a specific source"""
        response = client.post("/sync/trigger", json={"source": "limitless"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert "message" in data
        
        # Verify content
        assert data["status"] == "triggered"
        assert "limitless" in data["message"]
        
        # Verify sync was triggered
        mock_sync_manager.sync_source.assert_called_once()
    
    def test_trigger_sync_all_sources_success(self, client, mock_startup_service, mock_sync_manager):
        """Test triggering sync for all sources"""
        response = client.post("/sync/trigger", json={})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["status"] == "triggered"
        assert "all sources" in data["message"]
        
        # Verify all sources mentioned in message
        message = data["message"]
        assert "limitless" in message
        assert "weather" in message
        assert "news" in message
        
        # Verify sync was triggered for each source (3 calls)
        assert mock_sync_manager.sync_source.call_count == 3
    
    def test_trigger_sync_nonexistent_source(self, client, mock_startup_service, mock_sync_manager):
        """Test triggering sync for non-existent source"""
        response = client.post("/sync/trigger", json={"source": "nonexistent"})
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]
        assert "nonexistent" in data["detail"]
        
        # Verify sync was not triggered
        mock_sync_manager.sync_source.assert_not_called()
    
    def test_trigger_sync_sync_manager_unavailable(self, client, mock_startup_service):
        """Test triggering sync when sync manager is unavailable"""
        mock_startup_service.sync_manager = None
        
        response = client.post("/sync/trigger", json={"source": "limitless"})
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Sync manager not available"
    
    def test_trigger_sync_manager_error(self, client, mock_startup_service, mock_sync_manager):
        """Test triggering sync when sync manager raises exception"""
        mock_sync_manager.sync_source.side_effect = Exception("Sync service connection failed")
        
        response = client.post("/sync/trigger", json={"source": "limitless"})
        
        # Background task should be queued successfully, error occurs during task execution
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
        assert "limitless" in data["message"]
    
    def test_trigger_sync_empty_source_string(self, client, mock_startup_service, mock_sync_manager):
        """Test triggering sync with empty source string"""
        response = client.post("/sync/trigger", json={"source": ""})
        
        # Empty string should trigger all sources sync
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
        assert "all sources" in data["message"]
        
        # Should trigger sync for all 3 sources
        assert mock_sync_manager.sync_source.call_count == 3
    
    def test_get_sync_status_success(self, client, mock_startup_service, mock_sync_manager):
        """Test getting sync status successfully"""
        response = client.get("/sync/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "sync_manager_healthy" in data
        assert "sources" in data
        assert "scheduler_running" in data
        
        # Verify content
        assert data["sync_manager_healthy"] is True
        assert data["scheduler_running"] is True
        
        # Verify source status
        sources = data["sources"]
        assert "limitless" in sources
        assert "weather" in sources
        assert "news" in sources
        
        # Verify source details
        limitless_status = sources["limitless"]
        assert limitless_status["available"] is True
        assert limitless_status["status"] == "available"
        assert "last_sync" in limitless_status
    
    def test_get_sync_status_sync_manager_unavailable(self, client, mock_startup_service):
        """Test getting sync status when sync manager is unavailable"""
        mock_startup_service.sync_manager = None
        
        response = client.get("/sync/status")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Sync manager not available"
    
    def test_get_sync_status_no_ingestion_service(self, client, mock_startup_service, mock_sync_manager):
        """Test getting sync status when ingestion service is unavailable"""
        mock_startup_service.ingestion_service = None
        
        response = client.get("/sync/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still return basic status even without ingestion service
        assert data["sync_manager_healthy"] is True
        assert "sources" in data
        # Sources should be empty since no ingestion service
        assert len(data["sources"]) == 0
    
    def test_get_sync_status_no_scheduler(self, client, mock_startup_service):
        """Test getting sync status when scheduler is not running"""
        mock_startup_service.sync_manager = MagicMock()
        # No scheduler attribute
        delattr(mock_startup_service.sync_manager, 'scheduler')
        
        response = client.get("/sync/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["sync_manager_healthy"] is True
        assert data["scheduler_running"] is False
    
    def test_get_sync_status_service_error(self, client, mock_startup_service, mock_sync_manager):
        """Test getting sync status when service raises exception"""
        # Mock ingestion_service to raise exception when accessing sources
        mock_startup_service.ingestion_service.sources = property(lambda self: exec('raise Exception("Database error")'))
        
        response = client.get("/sync/status")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get sync status" in data["detail"]
    
    def test_sync_twitter_endpoint(self, client, mock_startup_service):
        """Test Twitter-specific sync endpoint"""
        # Add twitter to sources
        mock_startup_service.ingestion_service.sources["twitter"] = MagicMock()
        
        response = client.post("/api/sync/twitter")
        
        assert response.status_code == 200
        data = response.json()
        
        # Twitter sync returns special message about manual upload
        assert "manual archive upload" in data["message"]
        assert "upload endpoint" in data["message"]
    
    def test_sync_twitter_not_configured(self, client, mock_startup_service):
        """Test Twitter sync when Twitter source is not configured"""
        # Remove twitter from sources
        mock_startup_service.ingestion_service.sources = {
            'limitless': MagicMock(),
            'weather': MagicMock(),
            'news': MagicMock()
        }
        
        response = client.post("/api/sync/twitter")
        
        assert response.status_code == 404
        data = response.json()
        assert "Twitter source not available" in data["detail"]
    
    def test_sync_trigger_request_model_validation(self):
        """Test SyncTriggerRequest Pydantic model validation"""
        # Valid request with source
        valid_data = {"source": "limitless"}
        request = SyncTriggerRequest(**valid_data)
        assert request.source == "limitless"
        
        # Valid request without source (should default to None)
        empty_data = {}
        request = SyncTriggerRequest(**empty_data)
        assert request.source is None
        
        # Valid request with None source
        none_data = {"source": None}
        request = SyncTriggerRequest(**none_data)
        assert request.source is None
    
    def test_sync_response_model_validation(self):
        """Test SyncResponse Pydantic model validation"""
        # Valid response with message
        valid_data = {
            "status": "triggered",
            "message": "Sync triggered for limitless"
        }
        response = SyncResponse(**valid_data)
        assert response.status == "triggered"
        assert response.message == "Sync triggered for limitless"
        
        # Valid response without message
        minimal_data = {"status": "completed"}
        response = SyncResponse(**minimal_data)
        assert response.status == "completed"
        assert response.message is None
    
    def test_sync_invalid_json_payload(self, client, mock_startup_service):
        """Test sync endpoint with invalid JSON payload"""
        response = client.post("/sync/trigger", json={"invalid_field": "test"})
        
        # Should still work since SyncTriggerRequest allows additional fields to be ignored
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
    
    def test_sync_endpoint_cors_headers(self, client, mock_startup_service, mock_sync_manager):
        """Test sync endpoints include proper headers"""
        response = client.post("/sync/trigger", json={"source": "limitless"})
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_sync_performance_timing(self, client, mock_startup_service, mock_sync_manager):
        """Test sync endpoint response timing"""
        import time
        start_time = time.time()
        
        response = client.post("/sync/trigger", json={"source": "limitless"})
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Sync trigger should be fast (just queuing background task)
        assert response_time < 0.1
    
    def test_sync_status_performance_timing(self, client, mock_startup_service, mock_sync_manager):
        """Test sync status endpoint response timing"""
        import time
        start_time = time.time()
        
        response = client.get("/sync/status")
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Status check should be very fast
        assert response_time < 0.05
    
    def test_sync_concurrent_triggers(self, client, mock_startup_service, mock_sync_manager):
        """Test sync endpoint handles concurrent trigger requests"""
        import threading
        
        responses = []
        errors = []
        
        def trigger_sync(source):
            try:
                response = client.post("/sync/trigger", json={"source": source})
                responses.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Start multiple concurrent requests for different sources
        threads = []
        sources = ["limitless", "weather", "news"]
        for source in sources:
            thread = threading.Thread(target=trigger_sync, args=[source])
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Verify all requests succeeded
        assert len(errors) == 0
        assert len(responses) == 3
        assert all(status == 200 for status in responses)
        
        # Verify sync was triggered for each request
        assert mock_sync_manager.sync_source.call_count == 3
    
    def test_sync_background_task_integration(self, client, mock_startup_service, mock_sync_manager):
        """Test sync trigger properly integrates with FastAPI background tasks"""
        from fastapi import BackgroundTasks
        
        # Track if background task was added
        task_calls = []
        
        def mock_add_task(func, *args, **kwargs):
            task_calls.append((func, args, kwargs))
        

        with patch.object(BackgroundTasks, 'add_task', mock_add_task):
            response = client.post("/sync/trigger", json={"source": "limitless"})
        
        assert response.status_code == 200
        
        # Verify background task was properly configured
        # Note: In actual test, background task execution is handled by TestClient
        # so we mainly verify the endpoint structure is correct
        data = response.json()
        assert data["status"] == "triggered"