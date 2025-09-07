"""
API Coverage Summary Tests
Tests for key API endpoints to verify basic functionality and coverage
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.health import router as health_router
from services.startup import StartupService
from core.dependencies import get_startup_service_dependency


class TestAPIRouteCoverage:
    """Test coverage for core API routes"""
    
    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service with all required methods"""
        service = MagicMock(spec=StartupService)
        
        # Health route responses
        service.get_application_status.return_value = {
            "startup_complete": True,
            "services": {
                "database": True,
                "chat_service": True,
                "sync_manager": True,
                "embedding_service": True
            },
            "version": "1.0.0",
            "environment": "test",
            "uptime_seconds": 3600
        }
        
        # Chat service mock
        service.chat_service = AsyncMock()
        service.chat_service.process_chat_message.return_value = "Test response"
        service.chat_service.get_chat_history.return_value = []
        service.chat_service.search_data.return_value = []
        
        # Sync manager mock
        service.sync_manager = MagicMock()
        service.ingestion_service = MagicMock()
        service.ingestion_service.sources = {"limitless": MagicMock(), "weather": MagicMock()}
        
        # Database mock
        service.database = MagicMock()
        service.database.get_calendar_month_data.return_value = {
            "month": "January", "year": 2024, "days": []
        }
        service.database.get_calendar_day_data.return_value = {
            "conversations": [], "activities": [], "weather": None, "news": []
        }
        
        return service
    
    @pytest.fixture
    def health_app(self, mock_startup_service):
        """Create health route test app"""
        app = FastAPI()
        app.include_router(health_router)
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
        return app
    
    def test_health_routes_coverage(self, health_app):
        """Test health routes for basic coverage"""
        client = TestClient(health_app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "healthy" in data
        assert data["healthy"] is True
        
        # Test status endpoint  
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "services" in data["data"]
    
    def test_pydantic_models_coverage(self):
        """Test Pydantic model coverage for API routes"""
        # Import and test health models
        from api.routes.health import HealthResponse, StatusResponse
        
        # Test HealthResponse
        health_response = HealthResponse(
            healthy=True,
            services={"database": True, "chat_service": True},
            details={"version": "1.0.0"}
        )
        assert health_response.healthy is True
        assert health_response.services["database"] is True
        
        # Test StatusResponse
        status_response = StatusResponse(
            data={"startup_complete": True},
            timestamp="2024-01-15T10:00:00Z"
        )
        assert status_response.data["startup_complete"] is True
        assert status_response.timestamp == "2024-01-15T10:00:00Z"
        
        # Import and test chat models
        from api.routes.chat import ChatMessageRequest, ChatMessageResponse
        
        # Test ChatMessageRequest
        chat_request = ChatMessageRequest(message="Hello AI")
        assert chat_request.message == "Hello AI"
        
        # Test ChatMessageResponse
        chat_response = ChatMessageResponse(
            response="Hello human",
            timestamp="2024-01-15T10:00:00Z"
        )
        assert chat_response.response == "Hello human"
        assert chat_response.timestamp == "2024-01-15T10:00:00Z"
        
        # Import and test sync models
        from api.routes.sync import SyncTriggerRequest, SyncResponse
        
        # Test SyncTriggerRequest
        sync_request = SyncTriggerRequest(source="limitless")
        assert sync_request.source == "limitless"
        
        sync_request_none = SyncTriggerRequest()
        assert sync_request_none.source is None
        
        # Test SyncResponse
        sync_response = SyncResponse(
            status="triggered",
            message="Sync started"
        )
        assert sync_response.status == "triggered"
        assert sync_response.message == "Sync started"
        
        # Import and test system models  
        from api.routes.system import SystemResponse, SearchRequest, SearchResult
        
        # Test SearchRequest
        search_request = SearchRequest(query="test", limit=10)
        assert search_request.query == "test"
        assert search_request.limit == 10
        
        # Test SearchResult
        search_result = SearchResult(
            id="test:1",
            content="Test content",
            score=0.95,
            source="test",
            date="2024-01-15"
        )
        assert search_result.id == "test:1"
        assert search_result.score == 0.95
        
        # Test SystemResponse
        system_response = SystemResponse(
            success=True,
            message="Operation completed",
            result={"details": "success"}
        )
        assert system_response.success is True
        assert system_response.result["details"] == "success"
    


class TestAPIErrorHandling:
    """Test API error handling coverage"""
    
    def test_health_service_unavailable(self):
        """Test health endpoint when service is unavailable"""
        app = FastAPI()
        app.include_router(health_router)
        # Don't override dependencies - should get 503
        
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 503
        
        data = response.json()
        assert "detail" in data