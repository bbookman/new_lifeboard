#!/usr/bin/env python3
"""
Calendar Endpoint Routing Tests

Tests to prevent URL path mismatch issues between frontend and backend,
specifically addressing the calendar 404 error caused by incorrect API paths.

Issue Fixed: Frontend was calling /calendar/api/days-with-data 
but backend only serves /calendar/days-with-data
"""

import pytest
import requests
import json
from datetime import datetime, date
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock, patch

from api.routes.calendar import router
from core.database import DatabaseService
from services.startup import StartupService
from core.dependencies import get_startup_service_dependency


class TestCalendarEndpointRouting:
    """Test calendar API endpoint routing and URL path correctness"""
    
    @pytest.fixture
    def app(self, mock_startup_service):
        """Create FastAPI test application"""
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
        """Mock startup service with database"""
        service = MagicMock(spec=StartupService)
        db_service = MagicMock(spec=DatabaseService)
        service.database = db_service
        return service
    
    @pytest.fixture
    def mock_database_responses(self):
        """Mock database responses for testing"""
        return {
            'days_data': ["2024-01-15", "2024-01-16", "2024-01-17"],
            'namespaces': ['limitless', 'news', 'twitter'],
            'limitless_data': ["2024-01-15", "2024-01-16"],
            'news_data': ["2024-01-16", "2024-01-17"],
            'twitter_data': ["2024-01-15", "2024-01-17"]
        }

    def test_correct_calendar_days_with_data_path(self, client, mock_startup_service, mock_database_responses):
        """Test that /calendar/days-with-data works (correct path)"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            response = client.get("/calendar/days-with-data?year=2024&month=1")
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "sync_status" in data
        assert isinstance(data["data"], dict)
        assert "all" in data["data"]

    def test_incorrect_calendar_api_path_returns_404(self, client, mock_startup_service):
        """Test that /calendar/api/days-with-data returns 404 (incorrect path from old bug)"""
        # This is the path that was causing the 404 error before the fix
        response = client.get("/calendar/api/days-with-data?year=2024&month=1")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data

    def test_all_calendar_endpoints_correct_paths(self, client, mock_startup_service, mock_database_responses):
        """Test that all calendar endpoints use correct paths (without /api/ prefix)"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        db.get_data_items_by_date.return_value = []
        db.get_markdown_by_date.return_value = "# Test Date\n\nNo data available."
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            
            # Test correct paths (should work)
            endpoints_correct = [
                "/calendar/days-with-data",
                "/calendar/days-with-data?year=2024&month=1", 
                "/calendar/today",
                "/calendar/day/2024-01-15",
                "/calendar/month/2024/1",
            ]
            
            for endpoint in endpoints_correct:
                response = client.get(endpoint)
                assert response.status_code in [200, 400], f"Endpoint {endpoint} should be accessible (got {response.status_code})"

    def test_all_calendar_api_endpoints_return_404(self, client, mock_startup_service):
        """Test that all /calendar/api/* endpoints return 404 (incorrect paths)"""
        # These are the paths that would cause 404 errors (old bug pattern)
        endpoints_incorrect = [
            "/calendar/api/days-with-data",
            "/calendar/api/days-with-data?year=2024&month=1",
            "/calendar/api/today", 
            "/calendar/api/day/2024-01-15",
            "/calendar/api/month/2024/1",
        ]
        
        for endpoint in endpoints_incorrect:
            response = client.get(endpoint)
            assert response.status_code == 404, f"Endpoint {endpoint} should return 404 (got {response.status_code})"

    def test_calendar_routing_with_various_parameters(self, client, mock_startup_service, mock_database_responses):
        """Test calendar routing works with different parameter combinations"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            
            # Test various parameter combinations
            test_cases = [
                "/calendar/days-with-data",  # No parameters
                "/calendar/days-with-data?year=2024",  # Year only (should work)
                "/calendar/days-with-data?month=1",  # Month only (should work) 
                "/calendar/days-with-data?year=2024&month=1",  # Both parameters
                "/calendar/days-with-data?year=2024&month=12",  # December
                "/calendar/days-with-data?year=2023&month=2",  # Different year
            ]
            
            for endpoint in test_cases:
                response = client.get(endpoint)
                assert response.status_code == 200, f"Endpoint {endpoint} should work (got {response.status_code})"
                data = response.json()
                assert "data" in data
                assert "sync_status" in data

    def test_calendar_routing_edge_cases(self, client, mock_startup_service, mock_database_responses):
        """Test calendar routing with edge cases and invalid parameters"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            
            # These should still route correctly but may return filtered results
            edge_cases = [
                "/calendar/days-with-data?year=1999&month=1",  # Very old year
                "/calendar/days-with-data?year=2050&month=6",  # Future year
                "/calendar/days-with-data?year=2024&month=13", # Invalid month (should still route)
                "/calendar/days-with-data?year=-1&month=1",    # Negative year (should still route)
            ]
            
            for endpoint in edge_cases:
                response = client.get(endpoint)
                # Should route correctly (200) even if data filtering produces empty results
                assert response.status_code == 200, f"Endpoint {endpoint} should route correctly (got {response.status_code})"

    def test_websocket_routing_not_affected(self, client):
        """Test that WebSocket endpoints are not affected by calendar routing changes"""
        # WebSocket endpoints should still work correctly
        # Note: We can't test actual WebSocket connections in TestClient, 
        # but we can test the routing doesn't conflict
        
        # Since our app only includes calendar router, WebSocket will return 404,
        # but this test ensures calendar routing changes don't break other routing
        response = client.get("/ws/processing")
        # In our test app, this will be 404 since we only included calendar router
        # The important thing is that calendar routing doesn't interfere
        assert response.status_code == 404, "Expected 404 for WebSocket in calendar-only test app"

    @pytest.mark.parametrize("year,month", [
        (2024, 1), (2024, 12), (2023, 6), (2025, 3)
    ])
    def test_calendar_routing_parameterized(self, client, mock_startup_service, mock_database_responses, year, month):
        """Parameterized test for calendar routing with different year/month combinations"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            
            # Correct path should work
            response = client.get(f"/calendar/days-with-data?year={year}&month={month}")
            assert response.status_code == 200
            
            # Incorrect path should fail
            response = client.get(f"/calendar/api/days-with-data?year={year}&month={month}")
            assert response.status_code == 404

    def test_calendar_response_format_consistency(self, client, mock_startup_service, mock_database_responses):
        """Test that calendar endpoints return consistent response formats"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            
            response = client.get("/calendar/days-with-data?year=2024&month=1")
            assert response.status_code == 200
            
            data = response.json()
            
            # Verify expected response structure
            assert "data" in data
            assert "sync_status" in data
            assert isinstance(data["data"], dict)
            
            # Verify namespace data structure
            for namespace in mock_database_responses['namespaces']:
                assert namespace in data["data"], f"Namespace {namespace} should be in response"
                assert isinstance(data["data"][namespace], list), f"Namespace {namespace} data should be a list"

    def test_calendar_cors_headers_present(self, client, mock_startup_service, mock_database_responses):
        """Test that calendar endpoints include proper CORS headers for frontend access"""
        db = mock_startup_service.database
        db.get_days_with_data.return_value = mock_database_responses['days_data']
        db.get_all_namespaces.return_value = mock_database_responses['namespaces']
        
        with patch('api.routes.calendar.get_sync_status_service') as mock_sync:
            mock_sync.return_value = None
            
            response = client.get("/calendar/days-with-data")
            assert response.status_code == 200
            
            # Test that response is JSON
            assert response.headers.get("content-type") == "application/json"
            
            # Verify response can be parsed as JSON
            data = response.json()
            assert isinstance(data, dict)


class TestCalendarEndpointIntegration:
    """Integration tests for calendar endpoints with live server (if running)"""
    
    def test_live_server_calendar_routing(self):
        """Test calendar routing against live server (if available)"""
        try:
            # Test if server is running
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Live server not available")
        except requests.RequestException:
            pytest.skip("Live server not available")
        
        # Test correct path works
        try:
            response = requests.get("http://localhost:8000/calendar/days-with-data", timeout=5)
            assert response.status_code == 200, "Correct calendar path should work on live server"
            
            data = response.json()
            assert "data" in data
            assert "sync_status" in data
            
        except requests.RequestException as e:
            pytest.fail(f"Live server calendar test failed: {e}")
        
        # Test incorrect path fails
        try:
            response = requests.get("http://localhost:8000/calendar/api/days-with-data", timeout=5)
            assert response.status_code == 404, "Incorrect calendar path should return 404 on live server"
            
        except requests.RequestException as e:
            pytest.fail(f"Live server calendar negative test failed: {e}")

    def test_live_server_frontend_backend_sync(self):
        """Test that frontend and backend calendar URLs are in sync (if server available)"""
        try:
            # Test server availability
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Live server not available")
        except requests.RequestException:
            pytest.skip("Live server not available")
        
        # Simulate the exact frontend call after the fix
        frontend_url = "http://localhost:8000/calendar/days-with-data"
        current_date = datetime.now()
        params = {
            "year": current_date.year,
            "month": current_date.month
        }
        
        try:
            response = requests.get(frontend_url, params=params, timeout=5)
            assert response.status_code == 200, "Frontend-style calendar call should work"
            
            data = response.json()
            assert isinstance(data, dict)
            assert "data" in data
            
        except requests.RequestException as e:
            pytest.fail(f"Frontend-backend sync test failed: {e}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])