"""
E2E test for Twitter endpoints with on-demand source creation.

Tests that Twitter endpoints can create TwitterSource instances on-demand
when not registered in the ingestion service, validating the runtime wiring
to api.dependencies.twitter.get_twitter_source.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime

from api.routes.calendar import router as calendar_router
from config.models import TwitterConfig
from services.startup import StartupService
from core.database import DatabaseService
from services.ingestion import IngestionService


@pytest.fixture
def mock_startup_service():
    """Create a mock startup service with empty sources"""
    startup_service = Mock(spec=StartupService)
    
    # Mock database service
    database = Mock(spec=DatabaseService)
    startup_service.database = database
    
    # Mock ingestion service with empty sources (no 'twitter' source)
    ingestion_service = Mock(spec=IngestionService)
    ingestion_service.sources = {}  # Important: no 'twitter' source registered
    startup_service.ingestion_service = ingestion_service
    
    # Mock Twitter config with basic configuration
    twitter_config = Mock(spec=TwitterConfig)
    twitter_config.is_configured.return_value = True
    twitter_config.is_api_configured.return_value = False  # Avoid actual API calls
    twitter_config.rate_limit_minutes = 15
    
    startup_service.config = Mock()
    startup_service.config.twitter = twitter_config
    
    return startup_service


@pytest.fixture
def test_app():
    """Create test FastAPI app with calendar router"""
    app = FastAPI()
    app.include_router(calendar_router)
    return app


@pytest.fixture
def mock_rate_limit_service():
    """Create a mock rate limit service"""
    rate_limit_service = Mock()
    rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))  # Can fetch, 0 minutes wait
    rate_limit_service.get_last_fetch_time = AsyncMock(return_value=None)
    return rate_limit_service


@pytest.fixture
def mock_twitter_api_service():
    """Create a mock Twitter API service"""
    api_service = Mock()
    return api_service


class TestTwitterEndpointsOnDemand:
    """Test Twitter endpoints with on-demand source creation"""
    
    @patch('api.dependencies.twitter.get_dependency_registry')
    @patch('api.dependencies.twitter.TwitterSource')
    @patch('api.dependencies.twitter.TwitterRateLimitService')
    @patch('api.dependencies.twitter.TwitterAPIService')
    def test_twitter_status_endpoint_on_demand_creation(
        self,
        mock_twitter_api_service_class,
        mock_rate_limit_service_class,
        mock_twitter_source_class,
        mock_get_registry,
        test_app,
        mock_startup_service,
        mock_rate_limit_service
    ):
        """Test that /twitter/status/{date} creates TwitterSource on-demand"""
        
        # Setup mocks
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = mock_startup_service
        mock_get_registry.return_value = mock_registry
        
        # Mock service constructors
        mock_rate_limit_service_class.return_value = mock_rate_limit_service
        mock_twitter_api_service_class.return_value = None  # No API service since not configured
        
        # Mock TwitterSource creation
        mock_twitter_source = Mock()
        mock_twitter_source.rate_limit_service = mock_rate_limit_service
        mock_twitter_source_class.return_value = mock_twitter_source
        
        # Create test client
        client = TestClient(test_app)
        
        # Make request to Twitter status endpoint
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check expected response structure
        assert "can_fetch_now" in data
        assert "minutes_until_next" in data
        assert "last_fetch_time" in data
        
        # Verify the response values from our mock
        assert data["can_fetch_now"] is True
        assert data["minutes_until_next"] == 0
        assert data["last_fetch_time"] is None
        
        # Verify that the dependency registry was called
        mock_get_registry.assert_called()
        mock_registry.get_startup_service.assert_called()
        
        # Verify that TwitterRateLimitService was constructed due to on-demand creation
        mock_rate_limit_service_class.assert_called_once_with(
            mock_startup_service.database,
            15  # rate_limit_minutes from config
        )
        
        # Verify that rate limit service methods were called
        mock_rate_limit_service.can_fetch_now.assert_called_once()
        mock_rate_limit_service.get_last_fetch_time.assert_called_once()
    
    @patch('api.dependencies.twitter.get_dependency_registry')
    @patch('api.dependencies.twitter.TwitterSource')
    @patch('api.dependencies.twitter.TwitterRateLimitService')
    @patch('api.dependencies.twitter.TwitterAPIService')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_startup_service_dependency')
    def test_twitter_fetch_endpoint_on_demand_creation_rate_limited(
        self,
        mock_get_startup_service,
        mock_get_database_service,
        mock_twitter_api_service_class,
        mock_rate_limit_service_class,
        mock_twitter_source_class,
        mock_get_registry,
        test_app,
        mock_startup_service
    ):
        """Test that /twitter/fetch/{date} creates TwitterSource on-demand and respects rate limits"""
        
        # Setup mocks
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = mock_startup_service
        mock_get_registry.return_value = mock_registry
        
        # Mock rate limit service to return rate limited
        mock_rate_limit_service = Mock()
        mock_rate_limit_service.can_fetch_now = AsyncMock(return_value=(False, 10))  # Rate limited, 10 minutes wait
        mock_rate_limit_service_class.return_value = mock_rate_limit_service
        
        # Mock Twitter API service
        mock_twitter_api_service_class.return_value = None
        
        # Mock TwitterSource creation
        mock_twitter_source = Mock()
        mock_twitter_source.rate_limit_service = mock_rate_limit_service
        mock_twitter_source_class.return_value = mock_twitter_source
        
        # Mock database and startup service dependencies
        mock_database = Mock()
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
        mock_get_database_service.return_value = mock_database
        
        mock_startup_service.ingestion_service = Mock()
        mock_get_startup_service.return_value = mock_startup_service
        
        # Create test client
        client = TestClient(test_app)
        
        # Make request to Twitter fetch endpoint
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        # Verify rate limit response
        assert response.status_code == 429
        data = response.json()
        assert "Rate limited" in data["detail"]
        assert "10 minutes" in data["detail"]
        
        # Verify Retry-After header
        assert "retry-after" in response.headers
        assert response.headers["retry-after"] == "600"  # 10 minutes * 60 seconds
        
        # Verify that the dependency registry was called
        mock_get_registry.assert_called()
        mock_registry.get_startup_service.assert_called()
        
        # Verify that TwitterRateLimitService was constructed due to on-demand creation
        mock_rate_limit_service_class.assert_called_once_with(
            mock_startup_service.database,
            15  # rate_limit_minutes from config
        )
        
        # Verify that rate limit check was performed
        mock_rate_limit_service.can_fetch_now.assert_called_once()
    
    @patch('api.dependencies.twitter.get_dependency_registry')
    def test_twitter_endpoints_fail_when_not_configured(
        self,
        mock_get_registry,
        test_app,
        mock_startup_service
    ):
        """Test that endpoints fail gracefully when Twitter is not configured"""
        
        # Setup mocks with unconfigured Twitter
        mock_startup_service.config.twitter.is_configured.return_value = False
        
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = mock_startup_service
        mock_get_registry.return_value = mock_registry
        
        # Create test client
        client = TestClient(test_app)
        
        # Test status endpoint
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        assert response.status_code == 404
        assert "not configured" in response.json()["detail"]
        
        # Test fetch endpoint  
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        assert response.status_code == 404
        assert "not configured" in response.json()["detail"]
    
    @patch('api.dependencies.twitter.get_dependency_registry')
    def test_twitter_endpoints_fail_when_startup_service_unavailable(
        self,
        mock_get_registry,
        test_app
    ):
        """Test that endpoints fail when startup service is not available"""
        
        # Setup mocks with no startup service
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = None
        mock_get_registry.return_value = mock_registry
        
        # Create test client
        client = TestClient(test_app)
        
        # Test status endpoint
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        assert response.status_code == 503
        assert "Application not properly initialized" in response.json()["detail"]
        
        # Test fetch endpoint  
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        assert response.status_code == 503
        assert "Application not initialized" in response.json()["detail"]
    
    def test_invalid_date_format(self, test_app):
        """Test that endpoints reject invalid date formats"""
        client = TestClient(test_app)
        
        # Test status endpoint with invalid date
        response = client.get("/api/calendar/twitter/status/invalid-date")
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
        
        # Test fetch endpoint with invalid date
        response = client.post("/api/calendar/twitter/fetch/invalid-date")
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]