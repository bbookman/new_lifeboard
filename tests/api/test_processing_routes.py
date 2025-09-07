"""
Comprehensive tests for processing API routes
Tests FastAPI endpoints for processing queue status and day-specific processing information
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.processing import router
from services.clean_up_crew_service import CleanUpCrewService
from services.startup import StartupService


class TestProcessingRoutes:
    """Test processing API endpoints"""
    
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
        return service
    
    @pytest.fixture
    def mock_clean_up_crew_service(self):
        """Mock clean up crew service for testing"""
        service = MagicMock(spec=CleanUpCrewService)
        return service
    
    @pytest.fixture
    def sample_processing_stats(self):
        """Sample processing statistics for testing"""
        return {
            "total_days": 30,
            "completed_days": 25,
            "pending_days": 3,
            "processing_days": 1,
            "failed_days": 1,
            "active_processing": True,
            "last_updated": "2024-01-15T10:30:00Z"
        }
    
    @pytest.fixture
    def sample_day_status(self):
        """Sample day-specific processing status for testing"""
        return {
            "date": "2024-01-15",
            "status": "completed",
            "progress": 100,
            "total_items": 45,
            "processed_items": 45,
            "failed_items": 0,
            "last_updated": "2024-01-15T09:45:00Z",
            "processing_time_seconds": 23.5
        }

    def test_get_processing_queue_success(self, client, mock_startup_service, mock_clean_up_crew_service, sample_processing_stats):
        """Test successful processing queue status retrieval"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_queue_stats.return_value = sample_processing_stats
        
        response = client.get("/api/processing/queue")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches expected schema
        assert "total_days" in data
        assert "completed_days" in data
        assert "pending_days" in data
        assert "processing_days" in data
        assert "failed_days" in data
        assert "active_processing" in data
        assert "last_updated" in data
        
        # Verify content matches sample data
        assert data["total_days"] == 30
        assert data["completed_days"] == 25
        assert data["pending_days"] == 3
        assert data["processing_days"] == 1
        assert data["failed_days"] == 1
        assert data["active_processing"] is True
        assert data["last_updated"] == "2024-01-15T10:30:00Z"
        
        # Verify service was called correctly
        mock_clean_up_crew_service.get_queue_stats.assert_called_once()

    def test_get_processing_queue_service_unavailable(self, client, mock_startup_service):
        """Test processing queue when service is unavailable"""
        mock_startup_service.clean_up_crew_service = None
        
        response = client.get("/api/processing/queue")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Clean up crew service not available"

    def test_get_processing_queue_service_error(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test processing queue when service raises exception"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_queue_stats.side_effect = Exception("Database connection failed")
        
        response = client.get("/api/processing/queue")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get processing queue status" in data["detail"]

    def test_get_day_processing_status_success(self, client, mock_startup_service, mock_clean_up_crew_service, sample_day_status):
        """Test successful day-specific processing status retrieval"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_day_status.return_value = sample_day_status
        
        response = client.get("/api/processing/day/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches expected schema
        assert "date" in data
        assert "status" in data
        assert "progress" in data
        assert "total_items" in data
        assert "processed_items" in data
        assert "failed_items" in data
        assert "last_updated" in data
        assert "processing_time_seconds" in data
        
        # Verify content matches sample data
        assert data["date"] == "2024-01-15"
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["total_items"] == 45
        assert data["processed_items"] == 45
        assert data["failed_items"] == 0
        assert data["last_updated"] == "2024-01-15T09:45:00Z"
        assert data["processing_time_seconds"] == 23.5
        
        # Verify service was called with correct date
        mock_clean_up_crew_service.get_day_status.assert_called_once_with("2024-01-15")

    def test_get_day_processing_status_invalid_date_format(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test day processing status with invalid date format"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        
        response = client.get("/api/processing/day/invalid-date")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid date format" in data["detail"]

    def test_get_day_processing_status_future_date(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test day processing status with future date"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        future_date = "2025-12-31"
        
        response = client.get(f"/api/processing/day/{future_date}")
        
        assert response.status_code == 400
        data = response.json()
        assert "Future dates not allowed" in data["detail"]

    def test_get_day_processing_status_service_unavailable(self, client, mock_startup_service):
        """Test day processing status when service is unavailable"""
        mock_startup_service.clean_up_crew_service = None
        
        response = client.get("/api/processing/day/2024-01-15")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Clean up crew service not available"

    def test_get_day_processing_status_service_error(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test day processing status when service raises exception"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_day_status.side_effect = Exception("Data retrieval failed")
        
        response = client.get("/api/processing/day/2024-01-15")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get day processing status" in data["detail"]

    def test_get_day_processing_status_not_found(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test day processing status when day not found"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_day_status.return_value = None
        
        response = client.get("/api/processing/day/2024-01-01")
        
        assert response.status_code == 404
        data = response.json()
        assert "Day not found" in data["detail"]

    def test_processing_queue_response_schema_validation(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test processing queue response schema validation"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        
        # Test with incomplete data
        incomplete_stats = {
            "total_days": 10,
            "completed_days": 8
            # Missing other required fields
        }
        mock_clean_up_crew_service.get_queue_stats.return_value = incomplete_stats
        
        response = client.get("/api/processing/queue")
        
        # Should still return 200 but with default values for missing fields
        assert response.status_code == 200
        data = response.json()
        assert "total_days" in data
        assert "completed_days" in data

    def test_day_status_edge_dates(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test day processing status with edge case dates"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        
        edge_dates = [
            "2024-02-29",  # Leap year
            "2024-12-31",  # End of year
            "2024-01-01",  # Start of year
        ]
        
        for test_date in edge_dates:
            mock_day_status = {
                "date": test_date,
                "status": "pending",
                "progress": 0,
                "total_items": 10,
                "processed_items": 0,
                "failed_items": 0,
                "last_updated": f"{test_date}T00:00:00Z",
                "processing_time_seconds": 0.0
            }
            mock_clean_up_crew_service.get_day_status.return_value = mock_day_status
            
            response = client.get(f"/api/processing/day/{test_date}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["date"] == test_date

    def test_processing_endpoints_concurrent_requests(self, client, mock_startup_service, mock_clean_up_crew_service, sample_processing_stats):
        """Test processing endpoints handle concurrent requests"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_queue_stats.return_value = sample_processing_stats
        
        import threading
        
        responses = []
        errors = []
        
        def make_request():
            try:
                response = client.get("/api/processing/queue")
                responses.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Start multiple concurrent requests
        threads = []
        for i in range(3):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Verify all requests succeeded
        assert len(errors) == 0
        assert len(responses) == 3
        assert all(status == 200 for status in responses)

    def test_processing_endpoints_performance_timing(self, client, mock_startup_service, mock_clean_up_crew_service, sample_processing_stats):
        """Test processing endpoint response timing"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_queue_stats.return_value = sample_processing_stats
        
        import time
        start_time = time.time()
        
        response = client.get("/api/processing/queue")
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # API overhead should be minimal (under 50ms in test environment)
        assert response_time < 0.05

    def test_processing_endpoints_cors_headers(self, client, mock_startup_service, mock_clean_up_crew_service, sample_processing_stats):
        """Test processing endpoints include proper headers"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.get_queue_stats.return_value = sample_processing_stats
        
        response = client.get("/api/processing/queue")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_trigger_processing_success(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test successful processing trigger"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.trigger_batch_processing = AsyncMock(return_value=["result1", "result2", "result3"])
        
        response = client.post("/api/processing/trigger")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "processed" in data
        
        # Verify content
        assert data["success"] is True
        assert data["processed"] == 3
        
        # Verify service was called
        mock_clean_up_crew_service.trigger_batch_processing.assert_called_once()

    def test_trigger_processing_service_unavailable(self, client, mock_startup_service):
        """Test trigger processing when service is unavailable"""
        mock_startup_service.clean_up_crew_service = None
        
        response = client.post("/api/processing/trigger")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Clean up crew service not available"

    @pytest.mark.asyncio
    async def test_trigger_processing_service_error(self, client, mock_startup_service, mock_clean_up_crew_service):
        """Test trigger processing when service raises exception"""
        mock_startup_service.clean_up_crew_service = mock_clean_up_crew_service
        mock_clean_up_crew_service.trigger_batch_processing = AsyncMock(side_effect=Exception("Processing failed"))
        
        response = client.post("/api/processing/trigger")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to trigger processing" in data["detail"]