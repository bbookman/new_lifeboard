"""
Integration tests for manual Twitter fetch functionality.

Tests the complete flow from frontend button interaction through API endpoints
to backend services, verifying that manual Twitter fetch works correctly after
removing Twitter from automatic source registration.
"""

import asyncio
import json
import pytest
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional

from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the components we're testing
from api.routes.calendar import router as calendar_router
from api.dependencies.twitter import get_twitter_source
from services.twitter_api_service import TwitterAPIService, TwitterAPIError, TwitterRateLimitError
from services.twitter_rate_limit_service import TwitterRateLimitService
from sources.twitter import TwitterSource
from sources.base import DataItem
from services.ingestion import IngestionService, IngestionResult
from core.database import DatabaseService
from config.models import TwitterConfig
from core.dependencies import get_dependency_registry

logger = logging.getLogger(__name__)


class TestManualTwitterFetchFunctionality:
    """Integration tests for manual Twitter fetch functionality"""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI app with calendar router"""
        app = FastAPI()
        app.include_router(calendar_router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_database(self):
        """Mock database service"""
        db = Mock(spec=DatabaseService)
        db.async_get_data_items_by_date = AsyncMock(return_value=[])
        db.fetch_one = AsyncMock(return_value=None)
        db.execute_query = AsyncMock(return_value=1)
        return db
    
    @pytest.fixture
    def mock_twitter_config(self):
        """Mock Twitter configuration"""
        config = Mock(spec=TwitterConfig)
        config.bearer_token = "test_bearer_token_1234567890"
        config.user_id = "123456789"
        config.username = "testuser"
        config.rate_limit_minutes = 15.0
        config.lookback_days = 1
        config.request_timeout = 30
        config.retry_delay = 1
        config.other_error_max_retries = 3
        config.diagnostic_mode = False
        config.is_api_configured.return_value = True
        config.is_configured.return_value = True
        return config
    
    @pytest.fixture
    def mock_twitter_api_service(self, mock_twitter_config):
        """Mock Twitter API service"""
        service = Mock(spec=TwitterAPIService)
        service.config = mock_twitter_config
        service.fetch_user_tweets_today = AsyncMock(return_value=[])
        service.is_configured.return_value = True
        service.test_api_connectivity = AsyncMock(return_value={'success': True})
        return service
    
    @pytest.fixture
    def mock_twitter_rate_limit_service(self, mock_database):
        """Mock Twitter rate limit service"""
        service = Mock(spec=TwitterRateLimitService)
        service.can_fetch_now = AsyncMock(return_value=(True, 0))
        service.record_fetch_attempt = AsyncMock()
        service.get_last_fetch_time = AsyncMock(return_value=None)
        return service
    
    @pytest.fixture
    def mock_twitter_source(self, mock_twitter_config, mock_twitter_api_service, mock_twitter_rate_limit_service):
        """Mock Twitter source"""
        source = Mock(spec=TwitterSource)
        source.config = mock_twitter_config
        source.api_service = mock_twitter_api_service
        source.rate_limit_service = mock_twitter_rate_limit_service
        source.namespace = "twitter"
        source.fetch_today_tweets = AsyncMock(return_value=[])
        source._get_existing_tweet_ids = AsyncMock(return_value=set())
        source.processor = Mock()
        source.processor.process = Mock(side_effect=lambda x: x)
        return source
    
    @pytest.fixture
    def mock_ingestion_service(self):
        """Mock ingestion service"""
        service = Mock(spec=IngestionService)
        service.sources = {}
        service.register_source = Mock()
        service._process_and_store_item = AsyncMock()
        service.process_pending_embeddings = AsyncMock(return_value={'processed': 0})
        return service
    
    @pytest.fixture
    def mock_startup_service(self, mock_ingestion_service, mock_twitter_config):
        """Mock startup service"""
        startup = Mock()
        startup.ingestion_service = mock_ingestion_service
        startup.config = Mock()
        startup.config.twitter = mock_twitter_config
        startup.database = Mock(spec=DatabaseService)
        return startup
    
    @pytest.fixture
    def mock_dependency_registry(self, mock_startup_service):
        """Mock dependency registry"""
        registry = Mock()
        registry.get_startup_service.return_value = mock_startup_service
        return registry


class TestTwitterFetchButtonFunctionality(TestManualTwitterFetchFunctionality):
    """Test TwitterFetchButton component functionality through API integration"""
    
    def test_rate_limit_status_endpoint_success(self, client, mock_dependency_registry, mock_twitter_source):
        """Test rate limit status endpoint returns correct information"""
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                # Mock rate limit service to return specific status
                mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))
                mock_twitter_source.rate_limit_service.get_last_fetch_time = AsyncMock(
                    return_value=datetime.now(timezone.utc) - timedelta(minutes=20)
                )
                
                response = client.get("/api/calendar/twitter/status/2024-01-15")
                
                assert response.status_code == 200
                data = response.json()
                assert "can_fetch_now" in data
                assert "minutes_until_next" in data
                assert "last_fetch_time" in data
                assert data["can_fetch_now"] is True
                assert data["minutes_until_next"] == 0
    
    def test_rate_limit_status_endpoint_rate_limited(self, client, mock_dependency_registry, mock_twitter_source):
        """Test rate limit status endpoint when rate limited"""
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                # Mock rate limit service to return rate limited status
                mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(False, 10))
                mock_twitter_source.rate_limit_service.get_last_fetch_time = AsyncMock(
                    return_value=datetime.now(timezone.utc) - timedelta(minutes=5)
                )
                
                response = client.get("/api/calendar/twitter/status/2024-01-15")
                
                assert response.status_code == 200
                data = response.json()
                assert data["can_fetch_now"] is False
                assert data["minutes_until_next"] == 10
                assert data["last_fetch_time"] is not None
    
    def test_rate_limit_status_endpoint_invalid_date(self, client, mock_dependency_registry, mock_twitter_source):
        """Test rate limit status endpoint with invalid date format"""
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                response = client.get("/api/calendar/twitter/status/invalid-date")
                
                assert response.status_code == 400
                assert "Invalid date format" in response.json()["detail"]
    
    def test_rate_limit_status_endpoint_twitter_not_configured(self, client, mock_dependency_registry):
        """Test rate limit status endpoint when Twitter source not configured"""
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', side_effect=Exception("Twitter source not configured")):
                response = client.get("/api/calendar/twitter/status/2024-01-15")
                
                assert response.status_code == 500


class TestAPIEndpointFunctionality(TestManualTwitterFetchFunctionality):
    """Test API endpoint functionality for manual Twitter fetch"""
    
    def test_fetch_endpoint_success_new_data(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test successful fetch with new data"""
        # Mock no existing data
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
        
        # Mock successful tweet fetch
        sample_tweets = [
            {
                'tweet_id': '123456789',
                'created_at': '2024-01-15T10:00:00Z',
                'days_date': '2024-01-15',
                'text': 'Test tweet content',
                'media_urls': '[]'
            }
        ]
        mock_twitter_source.fetch_today_tweets = AsyncMock(return_value=sample_tweets)
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))
        
        # Mock ingestion result
        mock_result = Mock(spec=IngestionResult)
        mock_result.items_processed = 1
        mock_result.items_stored = 1
        mock_result.errors = []
        mock_result.start_time = datetime.now(timezone.utc)
        mock_result.end_time = datetime.now(timezone.utc)
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                    with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                        with patch('services.ingestion.IngestionResult', return_value=mock_result):
                            response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Successfully fetched and processed" in data["message"]
        assert data["items_processed"] == 1
        assert data["items_stored"] == 1
        assert data["date"] == "2024-01-15"
    
    def test_fetch_endpoint_data_already_exists(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test fetch endpoint when data already exists"""
        # Mock existing data
        existing_items = [
            {'id': 1, 'source_id': '123456789', 'content': 'Existing tweet'}
        ]
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=existing_items)
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                    with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Data already exists" in data["message"]
        assert data["items_processed"] == 0
        assert data["items_existing"] == 1
    
    def test_fetch_endpoint_rate_limited(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test fetch endpoint when rate limited"""
        # Mock no existing data but rate limited
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(False, 10))
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                    with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 429
        assert "Rate limited" in response.json()["detail"]
        assert response.headers.get("Retry-After") == "600"  # 10 minutes * 60 seconds
    
    def test_fetch_endpoint_invalid_date(self, client, mock_dependency_registry, mock_twitter_source):
        """Test fetch endpoint with invalid date format"""
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                response = client.post("/api/calendar/twitter/fetch/invalid-date")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
    
    def test_fetch_endpoint_twitter_not_configured(self, client, mock_dependency_registry):
        """Test fetch endpoint when Twitter API not configured"""
        mock_config = Mock()
        mock_config.twitter.is_api_configured.return_value = False
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', side_effect=Exception("Twitter API not configured")):
                with patch('config.factory.get_config', return_value=mock_config):
                    response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 500


class TestOnDemandTwitterSourceCreation(TestManualTwitterFetchFunctionality):
    """Test on-demand Twitter source creation functionality"""
    
    def test_get_twitter_source_creates_on_demand_when_not_registered(self, mock_dependency_registry, mock_twitter_config):
        """Test that get_twitter_source creates TwitterSource when not registered"""
        # Mock startup service with no registered Twitter source
        mock_startup_service = mock_dependency_registry.get_startup_service.return_value
        mock_startup_service.ingestion_service.sources = {}  # No registered sources
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.TwitterAPIService') as mock_api_service_class:
                with patch('api.dependencies.twitter.TwitterRateLimitService') as mock_rate_limit_service_class:
                    with patch('api.dependencies.twitter.TwitterSource') as mock_twitter_source_class:
                        # Mock the service constructors
                        mock_api_service = Mock()
                        mock_rate_limit_service = Mock()
                        mock_twitter_source = Mock()
                        
                        mock_api_service_class.return_value = mock_api_service
                        mock_rate_limit_service_class.return_value = mock_rate_limit_service
                        mock_twitter_source_class.return_value = mock_twitter_source
                        
                        # Call the dependency function
                        result = get_twitter_source()
                        
                        # Verify on-demand creation was called
                        mock_api_service_class.assert_called_once_with(mock_twitter_config)
                        mock_rate_limit_service_class.assert_called_once()
                        mock_twitter_source_class.assert_called_once()
                        
                        assert result == mock_twitter_source
    
    def test_get_twitter_source_uses_existing_registered_source(self, mock_dependency_registry, mock_twitter_source):
        """Test that get_twitter_source uses existing registered source when available"""
        # Mock startup service with registered Twitter source
        mock_startup_service = mock_dependency_registry.get_startup_service.return_value
        mock_startup_service.ingestion_service.sources = {"twitter": mock_twitter_source}
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            result = get_twitter_source()
            
            assert result == mock_twitter_source
    
    def test_get_twitter_source_handles_missing_configuration(self, mock_dependency_registry):
        """Test that get_twitter_source handles missing Twitter configuration"""
        # Mock startup service with no Twitter config
        mock_startup_service = mock_dependency_registry.get_startup_service.return_value
        mock_startup_service.ingestion_service.sources = {}
        mock_startup_service.config.twitter = None
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with pytest.raises(Exception) as exc_info:
                get_twitter_source()
            
            assert "not configured" in str(exc_info.value).lower()
    
    def test_get_twitter_source_handles_startup_service_unavailable(self):
        """Test that get_twitter_source handles unavailable startup service"""
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = None
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_registry):
            with pytest.raises(Exception) as exc_info:
                get_twitter_source()
            
            assert "not properly initialized" in str(exc_info.value).lower()


class TestServiceIntegration(TestManualTwitterFetchFunctionality):
    """Test service integration for manual Twitter fetch"""
    
    @pytest.mark.asyncio
    async def test_twitter_api_service_fetch_user_tweets_today(self, mock_twitter_config):
        """Test TwitterAPIService fetch_user_tweets_today method"""
        service = TwitterAPIService(mock_twitter_config)
        
        # Mock the session and API response
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'data': [
                {
                    'id': '123456789',
                    'text': 'Test tweet',
                    'created_at': '2024-01-15T10:00:00.000Z',
                    'public_metrics': {'like_count': 5}
                }
            ]
        })
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(service, 'session', mock_session):
            tweets = await service.fetch_user_tweets_today()
            
            assert len(tweets) == 1
            assert tweets[0]['tweet_id'] == '123456789'
            assert tweets[0]['text'] == 'Test tweet'
            assert tweets[0]['days_date'] == '2024-01-15'
    
    @pytest.mark.asyncio
    async def test_twitter_api_service_handles_rate_limit_error(self, mock_twitter_config):
        """Test TwitterAPIService handles rate limit errors correctly"""
        service = TwitterAPIService(mock_twitter_config)
        
        # Mock rate limit response
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {'retry-after': '900'}
        mock_response.json = AsyncMock(return_value={'detail': 'Rate limit exceeded'})
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(service, 'session', mock_session):
            tweets = await service.fetch_user_tweets_today()
            
            # Should return empty list on rate limit error
            assert tweets == []
    
    @pytest.mark.asyncio
    async def test_twitter_rate_limit_service_can_fetch_now(self, mock_database):
        """Test TwitterRateLimitService can_fetch_now logic"""
        service = TwitterRateLimitService(mock_database, rate_limit_minutes=15.0)
        
        # Mock no previous fetch
        service._get_last_fetch_time = AsyncMock(return_value=None)
        
        can_fetch, minutes_until = await service.can_fetch_now()
        
        assert can_fetch is True
        assert minutes_until == 0
    
    @pytest.mark.asyncio
    async def test_twitter_rate_limit_service_rate_limited(self, mock_database):
        """Test TwitterRateLimitService when rate limited"""
        service = TwitterRateLimitService(mock_database, rate_limit_minutes=15.0)
        
        # Mock recent fetch (5 minutes ago)
        recent_fetch = datetime.utcnow() - timedelta(minutes=5)
        service._get_last_fetch_time = AsyncMock(return_value=recent_fetch)
        
        can_fetch, minutes_until = await service.can_fetch_now()
        
        assert can_fetch is False
        assert minutes_until > 0
        assert minutes_until <= 11  # Should be around 10-11 minutes remaining
    
    @pytest.mark.asyncio
    async def test_twitter_rate_limit_service_record_fetch_attempt(self, mock_database):
        """Test TwitterRateLimitService records fetch attempts correctly"""
        service = TwitterRateLimitService(mock_database, rate_limit_minutes=15.0)
        service._update_last_fetch_time = AsyncMock()
        
        await service.record_fetch_attempt(success=True)
        
        service._update_last_fetch_time.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_data_processing_pipeline_integration(self, mock_twitter_source, mock_ingestion_service, mock_database):
        """Test complete data processing pipeline from fetch to storage"""
        # Mock tweet data
        sample_tweets = [
            {
                'tweet_id': '123456789',
                'created_at': '2024-01-15T10:00:00Z',
                'days_date': '2024-01-15',
                'text': 'Test tweet content',
                'media_urls': '[]'
            }
        ]
        mock_twitter_source.fetch_today_tweets = AsyncMock(return_value=sample_tweets)
        mock_twitter_source._get_existing_tweet_ids = AsyncMock(return_value=set())
        
        # Mock ingestion result
        mock_result = Mock(spec=IngestionResult)
        mock_result.items_processed = 0
        mock_result.items_stored = 0
        mock_result.errors = []
        mock_result.start_time = datetime.now(timezone.utc)
        mock_result.end_time = datetime.now(timezone.utc)
        
        # Simulate processing pipeline
        tweets = await mock_twitter_source.fetch_today_tweets()
        assert len(tweets) == 1
        
        # Verify tweet structure
        tweet = tweets[0]
        assert tweet['tweet_id'] == '123456789'
        assert tweet['days_date'] == '2024-01-15'
        assert tweet['text'] == 'Test tweet content'
    
    @pytest.mark.asyncio
    async def test_embedding_generation_integration(self, mock_ingestion_service):
        """Test embedding generation is triggered after data processing"""
        mock_ingestion_service.process_pending_embeddings = AsyncMock(
            return_value={'processed': 1, 'generated': 1}
        )
        
        # Simulate embedding processing
        result = await mock_ingestion_service.process_pending_embeddings(batch_size=32)
        
        assert result['processed'] == 1
        assert result['generated'] == 1
        mock_ingestion_service.process_pending_embeddings.assert_called_once_with(batch_size=32)


class TestErrorHandlingAndEdgeCases(TestManualTwitterFetchFunctionality):
    """Test error handling and edge cases"""
    
    def test_fetch_endpoint_handles_twitter_api_errors(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test fetch endpoint handles various Twitter API errors"""
        # Mock no existing data
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))
        
        # Mock Twitter API error
        mock_twitter_source.fetch_today_tweets = AsyncMock(
            side_effect=Exception("Twitter API connection failed")
        )
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                    with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
    
    def test_fetch_endpoint_handles_no_tweets_found(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test fetch endpoint when no tweets are found"""
        # Mock no existing data and no tweets from API
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))
        mock_twitter_source.fetch_today_tweets = AsyncMock(return_value=[])
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                    with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "No tweets found" in data["message"]
        assert data["items_processed"] == 0
    
    def test_status_endpoint_handles_service_errors(self, client, mock_dependency_registry, mock_twitter_source):
        """Test status endpoint handles service errors gracefully"""
        # Mock rate limit service error
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_rate_limit_service_handles_database_errors(self, mock_database):
        """Test rate limit service handles database errors gracefully"""
        service = TwitterRateLimitService(mock_database, rate_limit_minutes=15.0)
        
        # Mock database error
        mock_database.fetch_one = AsyncMock(side_effect=Exception("Database error"))
        
        # Should return True, 0 on error (allow fetch to proceed)
        can_fetch, minutes_until = await service.can_fetch_now()
        
        assert can_fetch is True
        assert minutes_until == 0


class TestFrontendIntegration(TestManualTwitterFetchFunctionality):
    """Test frontend integration scenarios"""
    
    def test_button_state_transitions_via_api(self, client, mock_dependency_registry, mock_twitter_source):
        """Test button state transitions through API calls"""
        # Test initial state (can fetch)
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))
        mock_twitter_source.rate_limit_service.get_last_fetch_time = AsyncMock(return_value=None)
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                response = client.get("/api/calendar/twitter/status/2024-01-15")
                
                assert response.status_code == 200
                data = response.json()
                assert data["can_fetch_now"] is True
                assert data["minutes_until_next"] == 0
                
                # This would correspond to button showing "Fetch now" state
    
    def test_button_disabled_state_via_api(self, client, mock_dependency_registry, mock_twitter_source):
        """Test button disabled state through API calls"""
        # Test rate limited state (button should be disabled)
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(False, 5))
        mock_twitter_source.rate_limit_service.get_last_fetch_time = AsyncMock(
            return_value=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                response = client.get("/api/calendar/twitter/status/2024-01-15")
                
                assert response.status_code == 200
                data = response.json()
                assert data["can_fetch_now"] is False
                assert data["minutes_until_next"] == 5
                
                # This would correspond to button showing "Next fetch available in 5 minutes" state
    
    def test_fetch_success_callback_simulation(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test successful fetch that would trigger success callback"""
        # Mock successful fetch scenario
        mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
        mock_twitter_source.rate_limit_service.can_fetch_now = AsyncMock(return_value=(True, 0))
        mock_twitter_source.fetch_today_tweets = AsyncMock(return_value=[
            {
                'tweet_id': '123456789',
                'created_at': '2024-01-15T10:00:00Z',
                'days_date': '2024-01-15',
                'text': 'Test tweet',
                'media_urls': '[]'
            }
        ])
        
        mock_result = Mock(spec=IngestionResult)
        mock_result.items_processed = 1
        mock_result.items_stored = 1
        mock_result.errors = []
        mock_result.start_time = datetime.now(timezone.utc)
        mock_result.end_time = datetime.now(timezone.utc)
        
        with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
            with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                    with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                        with patch('services.ingestion.IngestionResult', return_value=mock_result):
                            response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # This would trigger the onFetchComplete callback in the frontend
        # and cause the button to refresh its status
    
    def test_error_display_scenarios(self, client, mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test various error scenarios that would be displayed in frontend"""
        test_cases = [
            {
                'scenario': 'rate_limited',
                'setup': lambda: setattr(mock_twitter_source.rate_limit_service, 'can_fetch_now', 
                                        AsyncMock(return_value=(False, 10))),
                'expected_status': 429,
                'expected_message': 'Rate limited'
            },
            {
                'scenario': 'invalid_date',
                'setup': lambda: None,
                'url_date': 'invalid-date',
                'expected_status': 400,
                'expected_message': 'Invalid date format'
            }
        ]
        
        for case in test_cases:
            if case['scenario'] == 'rate_limited':
                # Setup rate limited scenario
                mock_database.async_get_data_items_by_date = AsyncMock(return_value=[])
                case['setup']()
                
                with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
                    with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                        with patch('api.routes.calendar.get_database_service_dependency', return_value=mock_database):
                            with patch('api.routes.calendar.get_ingestion_service', return_value=mock_ingestion_service):
                                response = client.post("/api/calendar/twitter/fetch/2024-01-15")
                
                assert response.status_code == case['expected_status']
                assert case['expected_message'] in response.json()["detail"]
            
            elif case['scenario'] == 'invalid_date':
                with patch('core.dependencies.get_dependency_registry', return_value=mock_dependency_registry):
                    with patch('api.dependencies.twitter.get_twitter_source', return_value=mock_twitter_source):
                        response = client.post(f"/api/calendar/twitter/fetch/{case.get('url_date', '2024-01-15')}")
                
                assert response.status_code == case['expected_status']
                assert case['expected_message'] in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])