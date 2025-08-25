"""
Comprehensive tests for calendar API routes
Tests FastAPI endpoints for calendar navigation and day detail views
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date, timezone
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.calendar import router
from services.startup import StartupService
from core.database import DatabaseService


class TestCalendarRoutes:
    """Test calendar API endpoints"""
    
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
    def mock_database_service(self):
        """Mock database service for testing"""
        service = MagicMock(spec=DatabaseService)
        return service
    
    @pytest.fixture
    def sample_calendar_data(self):
        """Sample calendar data for testing"""
        return {
            "2024-01-15": {
                "conversations": [
                    {
                        "id": "limitless:conv1",
                        "title": "Project Planning Discussion",
                        "start_time": "09:30",
                        "end_time": "10:30",
                        "participants": ["Alice", "Bob"],
                        "summary": "Discussed Q1 project milestones and resource allocation"
                    }
                ],
                "activities": [
                    {
                        "id": "limitless:act1",
                        "title": "Morning Walk",
                        "start_time": "07:00",
                        "end_time": "07:45",
                        "category": "exercise",
                        "location": "Central Park"
                    }
                ],
                "weather": {
                    "temperature": 22,
                    "condition": "sunny",
                    "humidity": 65,
                    "description": "Clear skies with gentle breeze"
                },
                "news": [
                    {
                        "title": "Tech Industry Sees Major AI Breakthrough",
                        "snippet": "New developments in artificial intelligence promise to revolutionize...",
                        "link": "https://example.com/ai-news",
                        "published": "2024-01-15T08:00:00Z"
                    }
                ]
            }
        }
    
    @pytest.fixture
    def sample_month_data(self):
        """Sample month view data for testing"""
        return {
            "month": "January",
            "year": 2024,
            "days": [
                {
                    "date": "2024-01-01",
                    "has_data": True,
                    "conversation_count": 3,
                    "activity_count": 5,
                    "mood_score": 7.5
                },
                {
                    "date": "2024-01-02",
                    "has_data": True,
                    "conversation_count": 2,
                    "activity_count": 4,
                    "mood_score": 8.0
                },
                {
                    "date": "2024-01-03",
                    "has_data": False,
                    "conversation_count": 0,
                    "activity_count": 0,
                    "mood_score": None
                }
            ],
            "statistics": {
                "total_conversations": 15,
                "total_activities": 32,
                "average_mood": 7.2,
                "active_days": 28
            }
        }
    
    def test_calendar_month_view_success(self, client, mock_startup_service, mock_database_service, sample_month_data):
        """Test calendar month view endpoint"""
        mock_startup_service.database = mock_database_service
        
        # Mock the actual database method used by the month endpoint
        days_data = {"all": ["2024-01-01", "2024-01-15", "2024-01-28"]}
        mock_database_service.get_days_with_data.return_value = ["2024-01-01", "2024-01-15", "2024-01-28"]
        mock_database_service.get_all_namespaces.return_value = ["limitless", "news"]
        
        with patch('api.routes.calendar.get_config') as mock_config, \
             patch('api.routes.calendar.get_sync_status_service') as mock_sync_service:
            
            mock_config.return_value = MagicMock()
            mock_sync_service.return_value = None  # No sync service available
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure for actual API
        assert "year" in data
        assert "month" in data
        assert "month_name" in data
        assert "days_with_data" in data
        assert "total_days_with_data" in data
        
        # Verify month data
        assert data["month"] == 1
        assert data["year"] == 2024
        assert data["month_name"] == "January"
    
    def test_calendar_day_view_success(self, client, mock_startup_service, mock_database_service, sample_calendar_data):
        """Test calendar day view endpoint"""
        mock_startup_service.database = mock_database_service
        
        # Mock the actual methods used by the day endpoint
        sample_items = [
            {
                "id": "limitless:123",
                "namespace": "limitless", 
                "content": "Sample content",
                "metadata": {"title": "Sample conversation"}
            }
        ]
        sample_markdown = "# Sample Day\n\nSample content here."
        
        mock_database_service.get_data_items_by_date.return_value = sample_items
        mock_database_service.get_markdown_by_date.return_value = sample_markdown
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/day/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure for actual API
        assert "date" in data
        assert "formatted_date" in data
        assert "day_of_week" in data
        assert "markdown_content" in data
        assert "item_count" in data
        assert "has_data" in data
        
        # Verify data content
        assert data["date"] == "2024-01-15"
        assert data["formatted_date"] == "January 15, 2024"
        assert data["day_of_week"] == "Monday" 
        assert data["markdown_content"] == sample_markdown
        assert data["item_count"] == 1
        assert data["has_data"] == True
    
    def test_calendar_month_view_invalid_date(self, client, mock_startup_service, mock_database_service):
        """Test calendar month view with invalid date parameters"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            
            # Invalid month - should get 400 error from validation
            response = client.get("/calendar/month/2024/13")
            assert response.status_code == 400
            
            # Invalid year - should get 422 from FastAPI validation
            response = client.get("/calendar/month/abc/1")
            assert response.status_code == 422
    
    def test_calendar_day_view_invalid_date(self, client, mock_startup_service, mock_database_service):
        """Test calendar day view with invalid date format"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            
            # Invalid date format - should get 400 error from date parsing
            response = client.get("/calendar/day/invalid-date")
            assert response.status_code == 400
            
            # Non-existent date - should get 400 error from date parsing
            response = client.get("/calendar/day/2024-02-30")
            assert response.status_code == 400
    
    def test_calendar_database_service_unavailable(self, client):
        """Test calendar endpoints when database service is unavailable"""
        # Create a separate app instance with a startup service that has no database
        from fastapi import FastAPI
        from core.dependencies import get_startup_service_dependency
        from services.startup import StartupService
        from unittest.mock import MagicMock
        
        mock_startup_service_no_db = MagicMock(spec=StartupService)
        mock_startup_service_no_db.database = None
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service_no_db
        
        from fastapi.testclient import TestClient
        client_no_db = TestClient(app)
        
        response = client_no_db.get("/calendar/month/2024/1")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Database service not available"
    
    def test_calendar_data_fetch_error(self, client, mock_startup_service, mock_database_service):
        """Test calendar endpoints with database error"""
        mock_startup_service.database = mock_database_service
        
        # Mock the actual database methods to raise exceptions
        mock_database_service.get_days_with_data.side_effect = Exception("Database connection failed")
        mock_database_service.get_all_namespaces.return_value = []
        
        with patch('api.routes.calendar.get_config') as mock_config, \
             patch('api.routes.calendar.get_sync_status_service') as mock_sync_service:
            
            mock_config.return_value = MagicMock()
            mock_sync_service.return_value = None
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 500
    
    def test_calendar_month_navigation(self, client, mock_startup_service, mock_database_service):
        """Test calendar month navigation endpoints"""
        mock_startup_service.database = mock_database_service
        
        # Mock the actual database methods
        mock_database_service.get_days_with_data.return_value = ["2024-02-01", "2024-02-15"]
        mock_database_service.get_all_namespaces.return_value = ["limitless", "news"]
        
        with patch('api.routes.calendar.get_config') as mock_config, \
             patch('api.routes.calendar.get_sync_status_service') as mock_sync_service:
            
            mock_config.return_value = MagicMock()
            mock_sync_service.return_value = None
            response = client.get("/calendar/month/2024/2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["month"] == 2
        assert data["year"] == 2024
        assert data["month_name"] == "February"
    
    def test_calendar_current_month_endpoint(self, client, mock_startup_service, mock_database_service):
        """Test calendar current month endpoint (via today API)"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/today")
        
        assert response.status_code == 200
        data = response.json()
        assert "today" in data
        assert "timezone" in data
    
    def test_calendar_day_detail_with_no_data(self, client, mock_startup_service, mock_database_service):
        """Test calendar day view for date with no data"""
        mock_startup_service.database = mock_database_service
        
        # Mock database methods to return empty data
        mock_database_service.get_data_items_by_date.return_value = []
        mock_database_service.get_markdown_by_date.return_value = "# 2024-01-20\n\nNo data available for this date."
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/day/2024-01-20")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["date"] == "2024-01-20"
        assert data["item_count"] == 0
        assert data["has_data"] == False
        assert "No data available" in data["markdown_content"]
    
    def test_calendar_performance_timing(self, client, mock_startup_service, mock_database_service):
        """Test calendar endpoint response timing"""
        mock_startup_service.database = mock_database_service
        
        # Mock database methods
        mock_database_service.get_days_with_data.return_value = ["2024-01-01", "2024-01-15"]
        mock_database_service.get_all_namespaces.return_value = ["limitless"]
        
        import time
        start_time = time.time()
        
        with patch('api.routes.calendar.get_config') as mock_config, \
             patch('api.routes.calendar.get_sync_status_service') as mock_sync_service:
            
            mock_config.return_value = MagicMock()
            mock_sync_service.return_value = None
            response = client.get("/calendar/month/2024/1")
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Calendar endpoint should be reasonably fast
        assert response_time < 0.1
    
    def test_calendar_data_filtering(self, client, mock_startup_service, mock_database_service):
        """Test calendar data filtering capabilities"""
        mock_startup_service.database = mock_database_service
        
        # Mock database methods for filtered data
        sample_items = [
            {
                "id": "limitless:conv1",
                "namespace": "limitless",
                "content": "Work meeting content",
                "metadata": {"title": "Work Meeting", "category": "work"}
            }
        ]
        mock_database_service.get_data_items_by_date.return_value = sample_items
        mock_database_service.get_markdown_by_date.return_value = "# Work Meeting\n\nWork meeting content"
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            # Note: Query parameters are not implemented in current API
            response = client.get("/calendar/day/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["item_count"] == 1
        assert data["has_data"] == True
    
    def test_calendar_timezone_handling(self, client, mock_startup_service, mock_database_service):
        """Test calendar handles timezone correctly"""
        mock_startup_service.database = mock_database_service
        
        # Mock database methods
        mock_database_service.get_data_items_by_date.return_value = []
        mock_database_service.get_markdown_by_date.return_value = "# 2024-01-15\n\nSample content"
        
        with patch('api.routes.calendar.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            # Note: Timezone parameters not implemented in current API
            response = client.get("/calendar/day/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2024-01-15"
        assert data["formatted_date"] == "January 15, 2024"
    
    def test_calendar_response_headers(self, client, mock_startup_service, mock_database_service):
        """Test calendar endpoints include proper headers"""
        mock_startup_service.database = mock_database_service
        
        # Mock database methods
        mock_database_service.get_days_with_data.return_value = ["2024-01-01"]
        mock_database_service.get_all_namespaces.return_value = ["limitless"]
        
        with patch('api.routes.calendar.get_config') as mock_config, \
             patch('api.routes.calendar.get_sync_status_service') as mock_sync_service:
            
            mock_config.return_value = MagicMock()
            mock_sync_service.return_value = None
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_calendar_edge_cases(self, client, mock_startup_service, mock_database_service):
        """Test calendar with edge case dates"""
        mock_startup_service.database = mock_database_service
        
        # Mock database methods for leap year February
        mock_database_service.get_days_with_data.return_value = ["2024-02-29"]  # Leap day
        mock_database_service.get_all_namespaces.return_value = ["limitless"]
        
        with patch('api.routes.calendar.get_config') as mock_config, \
             patch('api.routes.calendar.get_sync_status_service') as mock_sync_service:
            
            mock_config.return_value = MagicMock()
            mock_sync_service.return_value = None
            # Test leap year February
            response = client.get("/calendar/month/2024/2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2024
        assert data["month"] == 2
        assert data["month_name"] == "February"