"""
Simplified tests for health routes to verify basic functionality
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.health import router
from core.dependencies import get_startup_service_dependency
from services.startup import StartupService


class TestHealthSimple:
    """Simple health endpoint tests"""

    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service"""
        service = MagicMock(spec=StartupService)
        service.get_application_status.return_value = {
            "startup_complete": True,
            "services": {
                "database": True,
                "chat_service": True,
                "sync_manager": True,
            },
            "version": "1.0.0",
        }
        return service

    @pytest.fixture
    def app(self, mock_startup_service):
        """Create test app with mocked dependencies"""
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
        return app

    @pytest.fixture
    def client(self, app):
        """Test client"""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test basic health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "healthy" in data
        assert "services" in data

    def test_status_endpoint(self, client):
        """Test basic status endpoint"""
        response = client.get("/status")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "services" in data["data"]
