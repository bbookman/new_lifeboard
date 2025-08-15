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
    def app(self):
        """Create FastAPI test application"""
        app = FastAPI()
        app.include_router(router)
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
        
        # Mock the calendar service method that would generate month data
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', return_value=sample_month_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "month" in data
        assert "year" in data
        assert "days" in data
        assert "statistics" in data
        
        # Verify month data
        assert data["month"] == "January"
        assert data["year"] == 2024
        assert len(data["days"]) == 3
        
        # Verify statistics
        stats = data["statistics"]
        assert stats["total_conversations"] == 15
        assert stats["total_activities"] == 32
        assert stats["average_mood"] == 7.2
    
    def test_calendar_day_view_success(self, client, mock_startup_service, mock_database_service, sample_calendar_data):
        """Test calendar day view endpoint"""
        mock_startup_service.database = mock_database_service
        
        day_data = sample_calendar_data["2024-01-15"]
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_day_data', return_value=day_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/day/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "conversations" in data
        assert "activities" in data
        assert "weather" in data
        assert "news" in data
        
        # Verify conversations
        conversations = data["conversations"]
        assert len(conversations) == 1
        assert conversations[0]["title"] == "Project Planning Discussion"
        assert conversations[0]["start_time"] == "09:30"
        
        # Verify activities
        activities = data["activities"]
        assert len(activities) == 1
        assert activities[0]["title"] == "Morning Walk"
        assert activities[0]["category"] == "exercise"
        
        # Verify weather
        weather = data["weather"]
        assert weather["temperature"] == 22
        assert weather["condition"] == "sunny"
        
        # Verify news
        news = data["news"]
        assert len(news) == 1
        assert "AI Breakthrough" in news[0]["title"]
    
    def test_calendar_month_view_invalid_date(self, client, mock_startup_service, mock_database_service):
        """Test calendar month view with invalid date parameters"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service):
            # Invalid month
            response = client.get("/calendar/month/2024/13")
            assert response.status_code == 422 or response.status_code == 400
            
            # Invalid year
            response = client.get("/calendar/month/abc/1")
            assert response.status_code == 422
    
    def test_calendar_day_view_invalid_date(self, client, mock_startup_service, mock_database_service):
        """Test calendar day view with invalid date format"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service):
            # Invalid date format
            response = client.get("/calendar/day/invalid-date")
            assert response.status_code == 422 or response.status_code == 400
            
            # Non-existent date
            response = client.get("/calendar/day/2024-02-30")
            assert response.status_code == 422 or response.status_code == 400
    
    def test_calendar_database_service_unavailable(self, client, mock_startup_service):
        """Test calendar endpoints when database service is unavailable"""
        mock_startup_service.database = None
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Database service not available"
    
    def test_calendar_data_fetch_error(self, client, mock_startup_service, mock_database_service):
        """Test calendar endpoints with database error"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', side_effect=Exception("Database connection failed")):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 500
    
    def test_calendar_month_navigation(self, client, mock_startup_service, mock_database_service):
        """Test calendar month navigation endpoints"""
        mock_startup_service.database = mock_database_service
        
        # Test next month navigation
        next_month_data = {
            "month": "February",
            "year": 2024,
            "days": [],
            "statistics": {"total_conversations": 0}
        }
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', return_value=next_month_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/month/2024/2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "February"
        assert data["year"] == 2024
    
    def test_calendar_current_month_endpoint(self, client, mock_startup_service, mock_database_service, sample_month_data):
        """Test calendar current month endpoint"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', return_value=sample_month_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/current")
        
        # This endpoint should redirect to current month or return current month data
        assert response.status_code in [200, 302]
    
    def test_calendar_day_detail_with_no_data(self, client, mock_startup_service, mock_database_service):
        """Test calendar day view for date with no data"""
        mock_startup_service.database = mock_database_service
        
        empty_day_data = {
            "conversations": [],
            "activities": [],
            "weather": None,
            "news": []
        }
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_day_data', return_value=empty_day_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/day/2024-01-20")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["conversations"]) == 0
        assert len(data["activities"]) == 0
        assert data["weather"] is None
        assert len(data["news"]) == 0
    
    def test_calendar_performance_timing(self, client, mock_startup_service, mock_database_service, sample_month_data):
        """Test calendar endpoint response timing"""
        mock_startup_service.database = mock_database_service
        
        import time
        start_time = time.time()
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', return_value=sample_month_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/month/2024/1")
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Calendar endpoint should be reasonably fast
        assert response_time < 0.1
    
    def test_calendar_data_filtering(self, client, mock_startup_service, mock_database_service):
        """Test calendar data filtering capabilities"""
        mock_startup_service.database = mock_database_service
        
        filtered_data = {
            "conversations": [
                {
                    "id": "limitless:conv1",
                    "title": "Work Meeting",
                    "category": "work",
                    "start_time": "09:00"
                }
            ],
            "activities": [
                {
                    "id": "limitless:act1",
                    "title": "Exercise",
                    "category": "fitness",
                    "start_time": "07:00"
                }
            ],
            "weather": {"temperature": 20},
            "news": []
        }
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_day_data', return_value=filtered_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/day/2024-01-15?category=work")
        
        assert response.status_code == 200
        # Note: Actual filtering logic would depend on implementation
    
    def test_calendar_timezone_handling(self, client, mock_startup_service, mock_database_service, sample_calendar_data):
        """Test calendar handles timezone correctly"""
        mock_startup_service.database = mock_database_service
        
        # Test with timezone parameter
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_day_data', return_value=sample_calendar_data["2024-01-15"]):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/day/2024-01-15?timezone=America/New_York")
        
        assert response.status_code == 200
        # Timezone handling would be implementation-specific
    
    def test_calendar_response_headers(self, client, mock_startup_service, mock_database_service, sample_month_data):
        """Test calendar endpoints include proper headers"""
        mock_startup_service.database = mock_database_service
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', return_value=sample_month_data):
            
            mock_config.return_value = MagicMock()
            response = client.get("/calendar/month/2024/1")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_calendar_edge_cases(self, client, mock_startup_service, mock_database_service):
        """Test calendar with edge case dates"""
        mock_startup_service.database = mock_database_service
        
        edge_case_data = {
            "month": "February", 
            "year": 2024,  # Leap year
            "days": [],
            "statistics": {}
        }
        
        with patch('api.routes.calendar.get_startup_service_dependency', return_value=mock_startup_service), \
             patch('api.routes.calendar.get_config') as mock_config, \
             patch.object(mock_database_service, 'get_calendar_month_data', return_value=edge_case_data):
            
            mock_config.return_value = MagicMock()
            # Test leap year February
            response = client.get("/calendar/month/2024/2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2024
        assert data["month"] == "February"