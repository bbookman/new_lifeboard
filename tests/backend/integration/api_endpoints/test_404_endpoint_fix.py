"""
Test-driven development tests for fixing 404 endpoint issues.

This test file validates that the specific 404 errors mentioned by the user
are resolved and that all expected API endpoints return proper HTTP status codes.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from api.server import app


class TestEndpointAvailability:
    """Test that specific endpoints causing 404 errors are properly available."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies to avoid initialization issues."""
        
        # Mock the startup service dependency to avoid "Application not initialized" 
        from core.dependencies import get_startup_service_dependency
        mock_startup_service = Mock()
        mock_startup_service.database = Mock()
        mock_startup_service.llm_service = Mock()
        
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
        
        return TestClient(app)

    def test_news_endpoint_exists(self, client):
        """Test /api/news endpoint returns proper status (not 404)"""
        # This should return 200 or business logic error (like 422 for missing date), never 404
        response = client.get("/api/news?date=2025-08-22")
        
        # Should not be 404 - endpoint should exist
        assert response.status_code != 404, f"News endpoint returned 404: {response.text}"
        
        # Should be either 200 (success) or 4xx/5xx business logic error, but not 404
        assert response.status_code in [200, 422, 500, 503], f"Unexpected status {response.status_code}: {response.text}"

    def test_data_items_endpoint_exists(self, client):
        """Test /api/data_items endpoint returns proper status (not 404)"""
        # This should return 200 or business logic error, never 404
        response = client.get("/api/data_items?namespace=twitter&date=2025-08-22")
        
        # Should not be 404 - endpoint should exist
        assert response.status_code != 404, f"Data items endpoint returned 404: {response.text}"
        
        # Should be either 200 (success) or 4xx/5xx business logic error, but not 404
        assert response.status_code in [200, 422, 500, 503], f"Unexpected status {response.status_code}: {response.text}"

    def test_llm_summary_endpoint_exists(self, client):
        """Test /api/llm/summary/{date} endpoint returns proper status (not 404)"""
        # This should return 200 or business logic error, never 404
        response = client.get("/api/llm/summary/2025-08-22")
        
        # Should not be 404 - endpoint should exist
        assert response.status_code != 404, f"LLM summary endpoint returned 404: {response.text}"
        
        # Should be either 200 (success) or 4xx/5xx business logic error, but not 404
        assert response.status_code in [200, 422, 500, 503], f"Unexpected status {response.status_code}: {response.text}"

    def test_all_problematic_endpoints_are_available(self, client):
        """Test all endpoints mentioned in the original 404 errors are available."""
        problematic_endpoints = [
            "/api/llm/summary/2025-08-22",
            "/api/news?date=2025-08-22", 
            "/api/data_items?namespace=twitter&date=2025-08-22"
        ]
        
        for endpoint in problematic_endpoints:
            response = client.get(endpoint)
            assert response.status_code != 404, f"Endpoint {endpoint} still returns 404: {response.text}"

    def test_news_endpoint_without_date_parameter(self, client):
        """Test news endpoint behavior when required parameters are missing."""
        response = client.get("/api/news")
        
        # Should not be 404 (route exists), but may be 422 (missing required parameter)
        assert response.status_code != 404, f"News endpoint without date returned 404: {response.text}"

    def test_data_items_endpoint_without_parameters(self, client):
        """Test data_items endpoint behavior when parameters are missing."""
        response = client.get("/api/data_items")
        
        # Should not be 404 (route exists), but may return data or validation error
        assert response.status_code != 404, f"Data items endpoint without params returned 404: {response.text}"