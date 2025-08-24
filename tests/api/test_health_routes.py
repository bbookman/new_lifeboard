"""
Comprehensive tests for health and status API routes
Tests FastAPI endpoints for health monitoring and status checking
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.health import router, HealthResponse, StatusResponse
from services.startup import StartupService
from core.dependencies import get_startup_service_dependency


class TestHealthRoutes:
    """Test health and status API endpoints"""
    
    @pytest.fixture
    def app(self, mock_startup_service):
        """Create FastAPI test application with mocked dependencies"""
        app = FastAPI()
        app.include_router(router)
        
        # Override the dependency with our mock
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
    def mock_healthy_status(self):
        """Mock healthy application status"""
        return {
            "startup_complete": True,
            "services": {
                "database": True,
                "chat_service": True,
                "sync_manager": True,
                "websocket_manager": True,
                "embedding_service": True
            },
            "initialization_time": "2024-01-15T09:30:00.000Z",
            "version": "1.0.0",
            "environment": "test",
            "uptime_seconds": 3600,
            "memory_usage_mb": 512.5,
            "database_status": {
                "connected": True,
                "tables_created": True,
                "migration_version": "v1.0.0"
            },
            "embedding_status": {
                "model_loaded": True,
                "cache_size": 1000,
                "average_response_time_ms": 25.5
            }
        }
    
    @pytest.fixture
    def mock_unhealthy_status(self):
        """Mock unhealthy application status"""
        return {
            "startup_complete": False,
            "services": {
                "database": True,
                "chat_service": False,
                "sync_manager": True,
                "websocket_manager": False,
                "embedding_service": True
            },
            "initialization_time": None,
            "version": "1.0.0",
            "environment": "test",
            "uptime_seconds": 120,
            "errors": [
                "Chat service initialization failed",
                "WebSocket manager connection timeout"
            ],
            "database_status": {
                "connected": True,
                "tables_created": True,
                "migration_version": "v1.0.0"
            },
            "embedding_status": {
                "model_loaded": True,
                "cache_size": 0,
                "average_response_time_ms": None
            }
        }
    
    def test_health_check_healthy(self, client, mock_startup_service, mock_healthy_status):
        """Test health check endpoint with healthy status"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "healthy" in data
        assert "services" in data
        assert "details" in data
        
        # Verify health status
        assert data["healthy"] is True
        
        # Verify services status
        services = data["services"]
        assert services["database"] is True
        assert services["chat_service"] is True
        assert services["sync_manager"] is True
        assert services["websocket_manager"] is True
        assert services["embedding_service"] is True
        
        # Verify details include all status information
        details = data["details"]
        assert details["startup_complete"] is True
        assert details["version"] == "1.0.0"
        assert details["uptime_seconds"] == 3600
        assert details["memory_usage_mb"] == 512.5
    
    def test_health_check_unhealthy(self, client, mock_startup_service, mock_unhealthy_status):
        """Test health check endpoint with unhealthy status"""
        mock_startup_service.get_application_status.return_value = mock_unhealthy_status
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify health status is false
        assert data["healthy"] is False
        
        # Verify some services are down
        services = data["services"]
        assert services["chat_service"] is False
        assert services["websocket_manager"] is False
        
        # Verify error details are included
        details = data["details"]
        assert "errors" in details
        assert len(details["errors"]) == 2
        assert "Chat service initialization failed" in details["errors"]
        assert "WebSocket manager connection timeout" in details["errors"]
    
    def test_health_check_service_unavailable(self, client):
        """Test health check when startup service is unavailable"""
        def mock_dependency():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Application not initialized")
        
        with patch('api.routes.health.get_startup_service_dependency', side_effect=mock_dependency):
            response = client.get("/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Application not initialized"
    
    def test_health_check_exception_handling(self, client, mock_startup_service):
        """Test health check with service exception"""
        mock_startup_service.get_application_status.side_effect = Exception("Database connection failed")
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/health")
        
        assert response.status_code == 503
        data = response.json()
        assert "Health check failed" in data["detail"]
    
    def test_status_endpoint_detailed(self, client, mock_startup_service, mock_healthy_status):
        """Test status endpoint with detailed information"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "timestamp" in data
        assert "data" in data
        
        # Verify timestamp format
        timestamp = data["timestamp"]
        # Should be ISO format
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Verify all status data is included
        status_data = data["data"]
        assert status_data["startup_complete"] is True
        assert status_data["version"] == "1.0.0"
        assert "services" in status_data
        assert "database_status" in status_data
        assert "embedding_status" in status_data
        
        # Verify database status details
        db_status = status_data["database_status"]
        assert db_status["connected"] is True
        assert db_status["tables_created"] is True
        assert db_status["migration_version"] == "v1.0.0"
        
        # Verify embedding status details
        embed_status = status_data["embedding_status"]
        assert embed_status["model_loaded"] is True
        assert embed_status["cache_size"] == 1000
        assert embed_status["average_response_time_ms"] == 25.5
    
    def test_status_endpoint_with_errors(self, client, mock_startup_service, mock_unhealthy_status):
        """Test status endpoint with error conditions"""
        mock_startup_service.get_application_status.return_value = mock_unhealthy_status
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        
        status_data = data["data"]
        assert status_data["startup_complete"] is False
        assert "errors" in status_data
        assert len(status_data["errors"]) == 2
    
    def test_status_endpoint_exception_handling(self, client, mock_startup_service):
        """Test status endpoint with service exception"""
        mock_startup_service.get_application_status.side_effect = RuntimeError("Service initialization failed")
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/status")
        
        assert response.status_code == 500
        data = response.json()
        assert "Status check failed" in data["detail"]
    
    def test_health_response_model_validation(self):
        """Test HealthResponse Pydantic model validation"""
        # Valid response
        valid_data = {
            "healthy": True,
            "services": {"database": True, "chat": True},
            "details": {"version": "1.0.0"}
        }
        response = HealthResponse(**valid_data)
        assert response.healthy is True
        assert response.services["database"] is True
        assert response.details["version"] == "1.0.0"
        
        # Response without optional details
        minimal_data = {
            "healthy": False,
            "services": {"database": False}
        }
        response = HealthResponse(**minimal_data)
        assert response.healthy is False
        assert response.details is None
    
    def test_status_response_model_validation(self):
        """Test StatusResponse Pydantic model validation"""
        valid_data = {
            "timestamp": "2024-01-15T09:30:00.000Z",
            "data": {
                "startup_complete": True,
                "services": {"database": True},
                "version": "1.0.0"
            }
        }
        response = StatusResponse(**valid_data)
        assert response.timestamp == "2024-01-15T09:30:00.000Z"
        assert response.data["startup_complete"] is True
    
    def test_health_check_response_headers(self, client, mock_startup_service, mock_healthy_status):
        """Test health check response includes proper headers"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/health")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_status_check_response_headers(self, client, mock_startup_service, mock_healthy_status):
        """Test status check response includes proper headers"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/status")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_health_check_performance(self, client, mock_startup_service, mock_healthy_status):
        """Test health check endpoint performance"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        import time
        start_time = time.time()
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/health")
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Health check should be fast (under 100ms in test environment)
        assert response_time < 0.1
    
    def test_health_check_concurrent_requests(self, client, mock_startup_service, mock_healthy_status):
        """Test health check handles concurrent requests"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        import threading
        import time
        
        responses = []
        errors = []
        
        def make_request():
            try:
                with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
                    response = client.get("/health")
                    responses.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Start multiple concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Verify all requests succeeded
        assert len(errors) == 0
        assert len(responses) == 5
        assert all(status == 200 for status in responses)
    
    def test_health_check_with_partial_service_data(self, client, mock_startup_service):
        """Test health check with missing service information"""
        partial_status = {
            "startup_complete": True,
            "services": {
                "database": True
                # Missing other services
            },
            "version": "1.0.0"
        }
        mock_startup_service.get_application_status.return_value = partial_status
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["services"]["database"] is True
    
    def test_status_endpoint_timestamp_accuracy(self, client, mock_startup_service, mock_healthy_status):
        """Test status endpoint timestamp is current"""
        mock_startup_service.get_application_status.return_value = mock_healthy_status
        
        before_request = datetime.now(timezone.utc)
        
        with patch('api.routes.health.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/status")
        
        after_request = datetime.now(timezone.utc)
        
        assert response.status_code == 200
        data = response.json()
        
        # Parse timestamp from response
        response_timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        
        # Verify timestamp is between before and after request times
        assert before_request <= response_timestamp <= after_request