"""
Tests for manual Twitter fetch API endpoints

This module tests the manual Twitter fetch functionality after removing Twitter
from automatic source registration. Tests verify that on-demand Twitter source
creation works correctly and that all rate limiting, API connectivity, and data
processing functions remain operational for manual operations.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from api.routes.calendar import router
from api.dependencies.twitter import get_twitter_source
from services.twitter_api_service import TwitterAPIService, TwitterRateLimitError, TwitterAuthError, TwitterNotFoundError
from services.twitter_rate_limit_service import TwitterRateLimitService
from sources.twitter import TwitterSource
from core.database import DatabaseService
from services.ingestion import IngestionService, IngestionResult
from config.models import TwitterConfig


@pytest.fixture
def mock_database():
    """Mock database service"""
    db = Mock(spec=DatabaseService)
    db.async_get_data_items_by_date = AsyncMock(return_value=[])
    db.fetch_one = AsyncMock(return_value=None)
    db.execute_query = AsyncMock(return_value=1)
    return db


@pytest.fixture
def mock_twitter_config():
    """Mock Twitter configuration"""
    config = Mock(spec=TwitterConfig)
    config.bearer_token = "test_bearer_token"
    config.user_id = "123456789"
    config.username = "testuser"
    config.rate_limit_minutes = 15.0
    config.is_api_configured.return_value = True
    config.is_configured.return_value = True
    return config


@pytest.fixture
def mock_twitter_api_service():
    """Mock Twitter API service"""
    service = Mock(spec=TwitterAPIService)
    service.fetch_user_tweets_today = AsyncMock(return_value=[])
    service.test_api_connectivity = AsyncMock(return_value={'success': True})
    return service


@pytest.fixture
def mock_twitter_rate_limit_service():
    """Mock Twitter rate limit service"""
    service = Mock(spec=TwitterRateLimitService)
    service.can_fetch_now = AsyncMock(return_value=(True, 0))
    service.get_last_fetch_time = AsyncMock(return_value=None)
    service.record_fetch_attempt = AsyncMock()
    return service


@pytest.fixture
def mock_twitter_source(mock_twitter_config, mock_twitter_api_service, mock_twitter_rate_limit_service):
    """Mock Twitter source"""
    source = Mock(spec=TwitterSource)
    source.config = mock_twitter_config
    source.api_service = mock_twitter_api_service
    source.rate_limit_service = mock_twitter_rate_limit_service
    source.namespace = "twitter"
    source.fetch_today_tweets = AsyncMock(return_value=[])
    source._get_existing_tweet_ids = AsyncMock(return_value=set())
    source.processor = Mock()
    source.processor.process = Mock(return_value=Mock())
    return source


@pytest.fixture
def mock_ingestion_service():
    """Mock ingestion service"""
    service = Mock(spec=IngestionService)
    service.sources = {}
    service.register_source = Mock()
    service._process_and_store_item = AsyncMock()
    service.process_pending_embeddings = AsyncMock(return_value={'processed': 0})
    return service


@pytest.fixture
def mock_startup_service(mock_database, mock_ingestion_service, mock_twitter_config):
    """Mock startup service"""
    startup = Mock()
    startup.database = mock_database
    startup.ingestion_service = mock_ingestion_service
    startup.config = Mock()
    startup.config.twitter = mock_twitter_config
    return startup


@pytest.fixture
def mock_dependency_registry(mock_startup_service):
    """Mock dependency registry"""
    registry = Mock()
    registry.get_startup_service.return_value = mock_startup_service
    return registry


class TestTwitterRateLimitStatusEndpoint:
    """Test the /api/calendar/twitter/status/{date} endpoint"""

    @patch('api.routes.calendar.get_dependency_registry')
    def test_valid_date_no_previous_fetch(self, mock_get_registry, mock_dependency_registry, mock_twitter_source):
        """Test status endpoint with valid date and no previous fetch"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock rate limit service to return no previous fetch
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        mock_twitter_source.rate_limit_service.get_last_fetch_time.return_value = None
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_fetch_now"] is True
        assert data["minutes_until_next"] == 0
        assert data["last_fetch_time"] is None

    @patch('api.routes.calendar.get_dependency_registry')
    def test_valid_date_rate_limited(self, mock_get_registry, mock_dependency_registry, mock_twitter_source):
        """Test status endpoint when rate limited"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock rate limit service to return rate limited
        last_fetch = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (False, 10)
        mock_twitter_source.rate_limit_service.get_last_fetch_time.return_value = last_fetch
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_fetch_now"] is False
        assert data["minutes_until_next"] == 10
        assert data["last_fetch_time"] == last_fetch.isoformat()

    def test_invalid_date_format(self):
        """Test status endpoint with invalid date format"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/invalid-date")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    @patch('api.routes.calendar.get_dependency_registry')
    def test_twitter_source_not_configured(self, mock_get_registry, mock_dependency_registry):
        """Test status endpoint when Twitter source is not configured"""
        mock_get_registry.return_value = mock_dependency_registry
        
        # Mock startup service with no registered Twitter source
        mock_startup = Mock()
        mock_startup.ingestion_service = Mock()
        mock_startup.ingestion_service.sources = {}  # No registered sources
        mock_startup.config = None  # No config available
        mock_dependency_registry.get_startup_service.return_value = mock_startup
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 404
        assert "Twitter source not configured" in response.json()["detail"]

    @patch('api.routes.calendar.get_dependency_registry')
    def test_startup_service_not_available(self, mock_get_registry):
        """Test status endpoint when startup service is not available"""
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = None
        mock_get_registry.return_value = mock_registry
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 503
        assert "Application not properly initialized" in response.json()["detail"]


class TestTwitterFetchEndpoint:
    """Test the /api/calendar/twitter/fetch/{date} endpoint"""

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_ingestion_service')
    def test_successful_fetch(self, mock_get_ingestion, mock_get_db, mock_get_registry, 
                             mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test successful Twitter fetch"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_get_ingestion.return_value = mock_ingestion_service
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data
        mock_database.async_get_data_items_by_date.return_value = []
        
        # Mock rate limit allows fetch
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock successful tweet fetch
        mock_tweets = [
            {
                'tweet_id': '123',
                'text': 'Test tweet',
                'created_at': '2024-01-15T10:00:00Z',
                'days_date': '2024-01-15',
                'media_urls': '[]'
            }
        ]
        mock_twitter_source.fetch_today_tweets.return_value = mock_tweets
        mock_twitter_source._get_existing_tweet_ids.return_value = set()
        
        # Mock ingestion result
        result = IngestionResult()
        result.items_processed = 1
        result.items_stored = 1
        result.errors = []
        
        async def mock_process_and_store(item, result_obj):
            result_obj.items_processed += 1
            result_obj.items_stored += 1
        
        mock_ingestion_service._process_and_store_item.side_effect = mock_process_and_store
        
        # Mock final verification
        mock_database.async_get_data_items_by_date.side_effect = [[], [{'id': 1}]]  # First empty, then with data
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["items_processed"] == 1
        assert data["items_stored"] == 1
        assert data["date"] == "2024-01-15"

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    def test_data_already_exists(self, mock_get_db, mock_get_registry, 
                                 mock_dependency_registry, mock_twitter_source, mock_database):
        """Test fetch when data already exists"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock existing data
        existing_items = [{'id': 1, 'content': 'existing tweet'}]
        mock_database.async_get_data_items_by_date.return_value = existing_items
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["items_processed"] == 0
        assert data["items_existing"] == 1
        assert "already exists" in data["message"]

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    def test_rate_limited(self, mock_get_db, mock_get_registry, 
                         mock_dependency_registry, mock_twitter_source, mock_database):
        """Test fetch when rate limited"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data
        mock_database.async_get_data_items_by_date.return_value = []
        
        # Mock rate limit prevents fetch
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (False, 10)
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 429
        assert "Rate limited" in response.json()["detail"]
        assert response.headers.get("Retry-After") == "600"  # 10 minutes * 60 seconds

    def test_invalid_date_format_fetch(self):
        """Test fetch endpoint with invalid date format"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/invalid-date")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_config')
    def test_twitter_not_configured(self, mock_get_config, mock_get_db, mock_get_registry, 
                                   mock_dependency_registry, mock_twitter_source, mock_database):
        """Test fetch when Twitter API is not configured"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data
        mock_database.async_get_data_items_by_date.return_value = []
        
        # Mock rate limit allows fetch
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock Twitter not configured
        mock_config = Mock()
        mock_config.twitter.is_api_configured.return_value = False
        mock_get_config.return_value = mock_config
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 503
        assert "Twitter API not configured" in response.json()["detail"]


class TestTwitterSourceDependency:
    """Test the get_twitter_source dependency function"""

    @patch('api.routes.calendar.get_dependency_registry')
    def test_existing_registered_source(self, mock_get_registry, mock_dependency_registry, mock_twitter_source):
        """Test getting existing registered Twitter source"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        from api.routes.calendar import get_twitter_source
        
        result = get_twitter_source()
        
        assert result == mock_twitter_source

    @patch('api.routes.calendar.get_dependency_registry')
    def test_source_not_configured(self, mock_get_registry, mock_dependency_registry):
        """Test when Twitter source is not configured"""
        mock_get_registry.return_value = mock_dependency_registry
        
        # Mock startup service with no registered Twitter source and no config
        mock_startup = Mock()
        mock_startup.ingestion_service = Mock()
        mock_startup.ingestion_service.sources = {}  # No registered sources
        mock_startup.config = None  # No config available
        mock_dependency_registry.get_startup_service.return_value = mock_startup
        
        with pytest.raises(HTTPException) as exc_info:
            get_twitter_source()
        
        assert exc_info.value.status_code == 404
        assert "Twitter source not configured" in str(exc_info.value.detail)

    @patch('api.routes.calendar.get_dependency_registry')
    def test_wrong_source_type(self, mock_get_registry, mock_dependency_registry):
        """Test when Twitter source is wrong type"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": "wrong_type"}
        
        from api.routes.calendar import get_twitter_source
        
        with pytest.raises(HTTPException) as exc_info:
            get_twitter_source()
        
        assert exc_info.value.status_code == 404
        assert "not properly configured" in str(exc_info.value.detail)

    @patch('api.routes.calendar.get_dependency_registry')
    def test_startup_service_not_available(self, mock_get_registry):
        """Test when startup service is not available"""
        mock_registry = Mock()
        mock_registry.get_startup_service.return_value = None
        mock_get_registry.return_value = mock_registry
        
        from api.routes.calendar import get_twitter_source
        
        with pytest.raises(HTTPException) as exc_info:
            get_twitter_source()
        
        assert exc_info.value.status_code == 503
        assert "Application not properly initialized" in str(exc_info.value.detail)

    @patch('api.routes.calendar.get_dependency_registry')
    def test_ingestion_service_not_available(self, mock_get_registry, mock_dependency_registry):
        """Test when ingestion service is not available"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_startup = Mock()
        mock_startup.ingestion_service = None
        mock_dependency_registry.get_startup_service.return_value = mock_startup
        
        from api.routes.calendar import get_twitter_source
        
        with pytest.raises(HTTPException) as exc_info:
            get_twitter_source()
        
        assert exc_info.value.status_code == 503
        assert "Ingestion service not available" in str(exc_info.value.detail)


class TestOnDemandTwitterSourceCreation:
    """Test on-demand Twitter source creation from settings.py"""

    @patch('api.routes.settings.get_dependency_registry')
    def test_on_demand_source_creation_success(self, mock_get_registry, mock_dependency_registry, mock_twitter_config):
        """Test successful on-demand Twitter source creation"""
        mock_get_registry.return_value = mock_dependency_registry
        
        # Mock startup service with no registered Twitter source
        mock_startup = Mock()
        mock_startup.ingestion_service = Mock()
        mock_startup.ingestion_service.sources = {}  # No registered Twitter source
        mock_startup.config = Mock()
        mock_startup.config.twitter = mock_twitter_config
        mock_startup.database = Mock()
        mock_dependency_registry.get_startup_service.return_value = mock_startup
        
        # Mock TwitterSource creation
        with patch('api.dependencies.twitter.TwitterAPIService') as mock_api_service_class, \
             patch('api.dependencies.twitter.TwitterRateLimitService') as mock_rate_limit_class, \
             patch('api.dependencies.twitter.TwitterSource') as mock_twitter_source_class:
            
            mock_api_service = Mock()
            mock_rate_limit_service = Mock()
            mock_twitter_source = Mock()
            
            mock_api_service_class.return_value = mock_api_service
            mock_rate_limit_class.return_value = mock_rate_limit_service
            mock_twitter_source_class.return_value = mock_twitter_source
            
            # Use the imported get_twitter_source from api.dependencies.twitter
            
            result = get_twitter_source()
            
            assert result == mock_twitter_source
            mock_twitter_source_class.assert_called_once()

    @patch('api.routes.settings.get_dependency_registry')
    def test_on_demand_creation_config_not_available(self, mock_get_registry, mock_dependency_registry):
        """Test on-demand creation when Twitter config is not available"""
        mock_get_registry.return_value = mock_dependency_registry
        
        # Mock startup service with no Twitter config
        mock_startup = Mock()
        mock_startup.ingestion_service = Mock()
        mock_startup.ingestion_service.sources = {}
        mock_startup.config = None
        mock_dependency_registry.get_startup_service.return_value = mock_startup
        
        from api.routes.settings import get_twitter_source
        
        with pytest.raises(HTTPException) as exc_info:
            get_twitter_source()
        
        assert exc_info.value.status_code == 404
        assert "Twitter source not configured" in str(exc_info.value.detail)

    @patch('api.routes.settings.get_dependency_registry')
    def test_on_demand_creation_not_configured(self, mock_get_registry, mock_dependency_registry):
        """Test on-demand creation when Twitter is not configured"""
        mock_get_registry.return_value = mock_dependency_registry
        
        # Mock startup service with unconfigured Twitter
        mock_startup = Mock()
        mock_startup.ingestion_service = Mock()
        mock_startup.ingestion_service.sources = {}
        mock_startup.config = Mock()
        mock_startup.config.twitter = Mock()
        mock_startup.config.twitter.is_configured.return_value = False
        mock_dependency_registry.get_startup_service.return_value = mock_startup
        
        from api.routes.settings import get_twitter_source
        
        with pytest.raises(HTTPException) as exc_info:
            get_twitter_source()
        
        assert exc_info.value.status_code == 404
        assert "Twitter source not configured" in str(exc_info.value.detail)


class TestDataFlowVerification:
    """Test data flow from fetch to storage"""

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_ingestion_service')
    def test_complete_data_flow(self, mock_get_ingestion, mock_get_db, mock_get_registry,
                               mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test complete data flow from fetch to final verification"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_get_ingestion.return_value = mock_ingestion_service
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock the complete flow
        mock_database.async_get_data_items_by_date.side_effect = [
            [],  # No existing data initially
            [{'id': 1, 'content': 'processed tweet'}]  # Data exists after processing
        ]
        
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock tweet data
        mock_tweets = [
            {
                'tweet_id': '123',
                'text': 'Test tweet',
                'created_at': '2024-01-15T10:00:00Z',
                'days_date': '2024-01-15',
                'media_urls': '[]'
            }
        ]
        mock_twitter_source.fetch_today_tweets.return_value = mock_tweets
        mock_twitter_source._get_existing_tweet_ids.return_value = set()
        
        # Mock data processing
        from sources.base import DataItem
        processed_item = DataItem(
            namespace="twitter",
            source_id="123",
            content="Test tweet",
            metadata={'source_type': 'twitter_api'},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock_twitter_source.processor.process.return_value = processed_item
        
        # Track ingestion calls
        ingestion_calls = []
        async def track_ingestion(item, result):
            ingestion_calls.append(item)
            result.items_processed += 1
            result.items_stored += 1
        
        mock_ingestion_service._process_and_store_item.side_effect = track_ingestion
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify data flow
        assert data["success"] is True
        assert data["items_processed"] == 1
        assert data["items_stored"] == 1
        assert data["items_final"] == 1
        
        # Verify ingestion was called
        assert len(ingestion_calls) == 1
        assert ingestion_calls[0].source_id == "123"
        
        # Verify embedding processing was triggered
        mock_ingestion_service.process_pending_embeddings.assert_called_once()
        
        # Verify rate limit was recorded
        mock_twitter_source.rate_limit_service.record_fetch_attempt.assert_called_once_with(success=True)

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_ingestion_service')
    def test_error_handling_during_processing(self, mock_get_ingestion, mock_get_db, mock_get_registry,
                                             mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test error handling during data processing"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_get_ingestion.return_value = mock_ingestion_service
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data
        mock_database.async_get_data_items_by_date.return_value = []
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock tweet fetch
        mock_tweets = [{'tweet_id': '123', 'text': 'Test', 'created_at': '2024-01-15T10:00:00Z', 'days_date': '2024-01-15'}]
        mock_twitter_source.fetch_today_tweets.return_value = mock_tweets
        mock_twitter_source._get_existing_tweet_ids.return_value = set()
        
        # Mock processing error
        mock_ingestion_service._process_and_store_item.side_effect = Exception("Processing failed")
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 500
        assert "Error processing data" in response.json()["detail"]

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_ingestion_service')
    def test_no_tweets_found(self, mock_get_ingestion, mock_get_db, mock_get_registry,
                            mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test when no tweets are found for the date"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_get_ingestion.return_value = mock_ingestion_service
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data
        mock_database.async_get_data_items_by_date.return_value = []
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock no tweets found
        mock_twitter_source.fetch_today_tweets.return_value = []
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["items_processed"] == 0
        assert "No tweets found" in data["message"]


class TestTwitterAPIServiceIntegration:
    """Test integration with TwitterAPIService"""

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_ingestion_service')
    def test_api_service_rate_limit_error(self, mock_get_ingestion, mock_get_db, mock_get_registry,
                                         mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test handling of TwitterRateLimitError from API service"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_get_ingestion.return_value = mock_ingestion_service
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data and rate limit allows
        mock_database.async_get_data_items_by_date.return_value = []
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock API service rate limit error
        mock_twitter_source.fetch_today_tweets.side_effect = TwitterRateLimitError("Rate limited by API", retry_after=900)
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        # Should handle gracefully and return error
        assert response.status_code == 500

    @patch('api.routes.calendar.get_dependency_registry')
    @patch('api.routes.calendar.get_database_service_dependency')
    @patch('api.routes.calendar.get_ingestion_service')
    def test_api_service_auth_error(self, mock_get_ingestion, mock_get_db, mock_get_registry,
                                   mock_dependency_registry, mock_twitter_source, mock_database, mock_ingestion_service):
        """Test handling of TwitterAuthError from API service"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_get_db.return_value = mock_database
        mock_get_ingestion.return_value = mock_ingestion_service
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock no existing data and rate limit allows
        mock_database.async_get_data_items_by_date.return_value = []
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (True, 0)
        
        # Mock API service auth error
        mock_twitter_source.fetch_today_tweets.side_effect = TwitterAuthError("Authentication failed", status_code=401)
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/api/calendar/twitter/fetch/2024-01-15")
        
        # Should handle gracefully and return error
        assert response.status_code == 500


class TestRateLimitServiceIntegration:
    """Test integration with TwitterRateLimitService"""

    @patch('api.routes.calendar.get_dependency_registry')
    def test_rate_limit_service_database_error(self, mock_get_registry, mock_dependency_registry, mock_twitter_source):
        """Test handling of database errors in rate limit service"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock rate limit service database error
        mock_twitter_source.rate_limit_service.can_fetch_now.side_effect = Exception("Database error")
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 500

    @patch('api.routes.calendar.get_dependency_registry')
    def test_rate_limit_service_time_calculations(self, mock_get_registry, mock_dependency_registry, mock_twitter_source):
        """Test rate limit service time calculations"""
        mock_get_registry.return_value = mock_dependency_registry
        mock_dependency_registry.get_startup_service().ingestion_service.sources = {"twitter": mock_twitter_source}
        
        # Mock specific time scenario
        last_fetch = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_twitter_source.rate_limit_service.can_fetch_now.return_value = (False, 5)
        mock_twitter_source.rate_limit_service.get_last_fetch_time.return_value = last_fetch
        
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/api/calendar/twitter/status/2024-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_fetch_now"] is False
        assert data["minutes_until_next"] == 5
        assert data["last_fetch_time"] == last_fetch.isoformat()