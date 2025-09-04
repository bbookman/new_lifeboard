import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import aiohttp
import json

from services.twitter_api_service import (
    TwitterAPIService, 
    TwitterAPIError,
    TwitterAuthError,
    TwitterPermissionError,
    TwitterNotFoundError,
    TwitterRateLimitError
)
from config.models import TwitterConfig

@pytest.fixture
def valid_twitter_config():
    """Valid Twitter configuration for testing"""
    return TwitterConfig(
        bearer_token="valid_bearer_token_123",
        username="testuser",
        user_id="123456789012345678",
        max_retries=2,
        retry_delay=0.1,
        request_timeout=5.0
    )

@pytest.fixture
def invalid_twitter_config():
    """Invalid Twitter configuration for testing"""
    return TwitterConfig(
        bearer_token=None,
        username=None
    )

@pytest.fixture
def sample_user_response():
    """Sample Twitter API user response"""
    return {
        "data": {
            "id": "123456789",
            "name": "Test User",
            "username": "testuser"
        }
    }

@pytest.fixture
def sample_tweets_response():
    """Sample Twitter API tweets response"""
    return {
        "data": [
            {
                "id": "1234567890123456789",
                "text": "This is a test tweet from today",
                "created_at": "2024-01-15T10:30:00.000Z",
            },
            {
                "id": "9876543210987654321",
                "text": "Another test tweet with no metrics",
                "created_at": "2024-01-15T14:45:00.000Z"
            }
        ]
    }

@pytest.fixture
def empty_tweets_response():
    """Empty Twitter API tweets response"""
    return {"meta": {"result_count": 0}}

class TestTwitterAPIService:
    """Test TwitterAPIService functionality"""

    def test_service_initialization(self, valid_twitter_config):
        """Test TwitterAPIService initialization"""
        service = TwitterAPIService(valid_twitter_config)
        
        assert service.config == valid_twitter_config
        assert service.base_url == "https://api.twitter.com/2"
        assert service.session is None
        assert service.is_configured() is True

    def test_service_initialization_invalid_config(self, invalid_twitter_config):
        """Test TwitterAPIService initialization with invalid config"""
        service = TwitterAPIService(invalid_twitter_config)
        
        assert service.config == invalid_twitter_config
        assert service.is_configured() is False

    @pytest.mark.asyncio
    async def test_context_manager_setup(self, valid_twitter_config):
        """Test async context manager setup and teardown"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_instance = AsyncMock()
            mock_session_class.return_value = mock_session_instance
            
            # Test context manager entry
            async with service as ctx_service:
                assert ctx_service is service
                assert service.session is mock_session_instance
                
                # Verify ClientSession was called with expected parameters
                mock_session_class.assert_called_once_with(
                    timeout=aiohttp.ClientTimeout(total=5.0),
                    headers={
                        "Authorization": "Bearer valid_bearer_token_123",
                        "User-Agent": "Lifeboard/1.0"
                    }
                )
            
            # Verify session close was called
            mock_session_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_success(self, valid_twitter_config, sample_user_response):
        """Test successful API request"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=sample_user_response)
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                result = await service._make_request("https://api.twitter.com/2/users/by/username/testuser")
                
                assert result == sample_user_response
                mock_get.assert_called_once_with("https://api.twitter.com/2/users/by/username/testuser", params=None)

    @pytest.mark.asyncio
    async def test_make_request_rate_limited(self, valid_twitter_config):
        """Test rate-limited API request raises error immediately (no retries)"""
        from services.twitter_api_service import TwitterRateLimitError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {"retry-after": "900"}  # 15 minutes
            mock_response_429.json = AsyncMock(return_value={"error": "Rate limited"})
            
            mock_get.return_value.__aenter__.return_value = mock_response_429
            
            async with service:
                with pytest.raises(TwitterRateLimitError) as exc_info:
                    await service._make_request("https://api.twitter.com/2/test")
                
                # Should not retry, just raise immediately
                assert mock_get.call_count == 1
                assert exc_info.value.retry_after == 900
                assert "15 minutes" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_unauthorized(self, valid_twitter_config):
        """Test unauthorized API request"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.json = AsyncMock(return_value={"error": "Unauthorized"})
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterAuthError, match="Authentication failed"):
                    await service._make_request("https://api.twitter.com/2/test")

    @pytest.mark.asyncio
    async def test_make_request_user_not_found(self, valid_twitter_config):
        """Test user not found API request"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.json = AsyncMock(return_value={"error": "User not found"})
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterNotFoundError, match="not found"):
                    await service._make_request("https://api.twitter.com/2/test")

    @pytest.mark.asyncio
    async def test_make_request_max_retries_exceeded(self, valid_twitter_config):
        """Test max retries exceeded"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            with patch('asyncio.sleep'):
                # All requests fail with 500
                mock_response = AsyncMock()
                mock_response.status = 500
                mock_response.json = AsyncMock(return_value={"error": "Internal server error"})
                mock_get.return_value.__aenter__.return_value = mock_response
                
                async with service:
                    with pytest.raises(TwitterAPIError, match="server error"):
                        await service._make_request("https://api.twitter.com/2/test")
                    
                    assert mock_get.call_count == service.config.other_error_max_retries  # Should retry 3 times

    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_missing_user_id(self):
        """Test that service handles missing user_id gracefully"""
        config = TwitterConfig(bearer_token="valid_token", user_id=None)
        service = TwitterAPIService(config)
        
        tweets = await service.fetch_user_tweets_today()
        assert tweets == []

    @pytest.mark.asyncio
    async def test_get_todays_tweets_success(self, valid_twitter_config, sample_tweets_response):
        """Test successful today's tweets retrieval"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch.object(service, '_make_request', return_value=sample_tweets_response):
            async with service:
                tweets = await service.get_todays_tweets("123456789")
                
                assert len(tweets) == 2
                assert tweets[0]["id"] == "1234567890123456789"
                assert tweets[0]["text"] == "This is a test tweet from today"
                assert tweets[1]["id"] == "9876543210987654321"

    @pytest.mark.asyncio
    async def test_get_todays_tweets_empty(self, valid_twitter_config, empty_tweets_response):
        """Test today's tweets retrieval with no tweets"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch.object(service, '_make_request', return_value=empty_tweets_response):
            async with service:
                tweets = await service.get_todays_tweets("123456789")
                
                assert len(tweets) == 0

    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_success(self, valid_twitter_config, sample_tweets_response):
        """Test successful full workflow using configured user_id"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch.object(service, '_make_request', return_value=sample_tweets_response):
            async with service:
                tweets = await service.fetch_user_tweets_today()
                
                assert len(tweets) == 2
                
                # Check transformed format
                tweet1 = tweets[0]
                assert tweet1["tweet_id"] == "1234567890123456789"
                assert tweet1["text"] == "This is a test tweet from today"
                assert tweet1["days_date"] == "2024-01-15"
                assert tweet1["media_urls"] == "[]"
                
                tweet2 = tweets[1]
                assert tweet2["tweet_id"] == "9876543210987654321"
                assert tweet2["text"] == "Another test tweet with no metrics"
                assert tweet2["days_date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_not_configured(self, invalid_twitter_config):
        """Test fetch when API not configured"""
        service = TwitterAPIService(invalid_twitter_config)
        
        tweets = await service.fetch_user_tweets_today()
        assert tweets == []

    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_error_handling(self, valid_twitter_config):
        """Test error handling during fetch - returns empty list on errors"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch.object(service, 'get_todays_tweets', side_effect=Exception("API Error")):
            async with service:
                # Should return empty list on error, not raise exception
                tweets = await service.fetch_user_tweets_today()
                assert tweets == []

    @pytest.mark.asyncio
    async def test_context_manager_without_session_error(self, valid_twitter_config):
        """Test using _make_request without context manager"""
        service = TwitterAPIService(valid_twitter_config)
        
        with pytest.raises(RuntimeError, match="TwitterAPIService must be used as async context manager"):
            await service._make_request("https://api.twitter.com/2/test")

    @pytest.mark.asyncio
    async def test_network_error_retry(self, valid_twitter_config):
        """Test network error with exponential backoff"""
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            with patch('asyncio.sleep') as mock_sleep:
                # First call: network error, second call: success
                mock_get.return_value.__aenter__.side_effect = [
                    aiohttp.ClientError("Network error"),
                    AsyncMock(status=200, json=AsyncMock(return_value={"data": {"id": "123"}}))
                ]
                
                async with service:
                    result = await service._make_request("https://api.twitter.com/2/test")
                    
                    assert result == {"data": {"id": "123"}}
                    assert mock_get.call_count == 2
                    mock_sleep.assert_called_once_with(0.1)  # retry_delay


class TestTwitterAPIServiceEnhancedErrorHandling:
    """Test suite for enhanced Twitter API error handling"""
    
    @pytest.mark.asyncio
    async def test_403_forbidden_error_handling(self, valid_twitter_config):
        """Test 403 Forbidden error handling with detailed messages"""
        from services.twitter_api_service import TwitterPermissionError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 403
            mock_response.json.return_value = {
                "detail": "Forbidden",
                "errors": ["Insufficient permissions"]
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterPermissionError) as exc_info:
                    await service._make_request("https://api.twitter.com/2/test")
                
                assert exc_info.value.status_code == 403
                assert "Access forbidden" in str(exc_info.value)
                assert "API permissions" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_401_unauthorized_enhanced_error(self, valid_twitter_config):
        """Test 401 Unauthorized with enhanced error messages"""
        from services.twitter_api_service import TwitterAuthError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.json.return_value = {"detail": "Invalid bearer token"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterAuthError) as exc_info:
                    await service._make_request("https://api.twitter.com/2/test")
                
                assert exc_info.value.status_code == 401
                assert "Authentication failed" in str(exc_info.value)
                assert "bearer token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_404_not_found_enhanced_error(self, valid_twitter_config):
        """Test 404 Not Found with context-aware messages"""
        from services.twitter_api_service import TwitterNotFoundError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.json.return_value = {"detail": "User not found"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterNotFoundError) as exc_info:
                    await service._make_request("https://api.twitter.com/2/users/by/username/testuser")
                
                assert exc_info.value.status_code == 404
                assert "testuser" in str(exc_info.value)
                assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_429_rate_limit_enhanced_error(self, valid_twitter_config):
        """Test 429 Rate Limit with retry information"""
        from services.twitter_api_service import TwitterRateLimitError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.headers = {'retry-after': '900'}  # 15 minutes
            mock_response.json.return_value = {"detail": "Rate limit exceeded"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterRateLimitError) as exc_info:
                    await service._make_request("https://api.twitter.com/2/test")
                
                assert exc_info.value.retry_after == 900
                assert "Rate limit exceeded" in str(exc_info.value)
                assert "900 seconds" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_500_server_error_retry_logic(self, valid_twitter_config):
        """Test 500 server errors with retry logic"""
        from services.twitter_api_service import TwitterAPIError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            with patch('asyncio.sleep') as mock_sleep:
                mock_response = AsyncMock()
                mock_response.status = 500
                mock_response.json.return_value = {"detail": "Internal server error"}
                mock_get.return_value.__aenter__.return_value = mock_response
                
                async with service:
                    with pytest.raises(TwitterAPIError) as exc_info:
                        await service._make_request("https://api.twitter.com/2/test")
                    
                    assert exc_info.value.status_code == 500
                    assert "server error" in str(exc_info.value)
                    # Should retry based on other_error_max_retries (3 times by default)
                    assert mock_get.call_count == service.config.other_error_max_retries
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_graceful_degradation(self, valid_twitter_config):
        """Test fetch_user_tweets_today returns empty list on errors"""
        from services.twitter_api_service import TwitterAuthError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.json.return_value = {"detail": "Unauthorized"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                result = await service.fetch_user_tweets_today()
                
                # Should return empty list instead of raising exception
                assert result == []
    
    @pytest.mark.asyncio
    async def test_get_user_id_enhanced_error_handling(self, valid_twitter_config):
        """Test get_user_id with enhanced error handling"""
        from services.twitter_api_service import TwitterNotFoundError
        
        service = TwitterAPIService(valid_twitter_config)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.json.return_value = {"detail": "User not found"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with service:
                with pytest.raises(TwitterNotFoundError) as exc_info:
                    await service.get_user_id("nonexistentuser")
                
                # Should contain error about user not found (either parameter or configured username)
                error_msg = str(exc_info.value)
                assert "not found" in error_msg.lower()
    
    @pytest.mark.asyncio
    async def test_place_fields_in_api_request(self, valid_twitter_config):
        """Test that place fields are included in API requests and processed correctly"""
        service = TwitterAPIService(valid_twitter_config)
        
        # Mock tweets response with place data
        tweets_with_places = {
            "data": [
                {
                    "id": "1234567890123456789",
                    "text": "Tweet with location",
                    "created_at": "2024-01-15T10:30:00.000Z",
                    "geo": {"place_id": "place123"}
                }
            ],
            "includes": {
                "places": [
                    {
                        "id": "place123",
                        "full_name": "San Francisco, CA",
                        "name": "San Francisco",
                        "country": "United States",
                        "country_code": "US",
                        "place_type": "city",
                        "geo": {"bbox": [-122.5, 37.7, -122.3, 37.8]}
                    }
                ]
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            tweets_response = AsyncMock()
            tweets_response.status = 200
            tweets_response.json.return_value = tweets_with_places
            
            mock_get.return_value.__aenter__.return_value = tweets_response
            
            async with service:
                tweets = await service.fetch_user_tweets_today()
                
                # Verify place fields were requested in API call
                call_args = mock_get.call_args_list[0]  # Only one API call
                params = call_args[1]['params']
                assert 'place.fields' in params
                assert 'id,full_name,name,country,country_code,place_type,geo' in params['place.fields']
                
                # Verify normalized output contains place data
                assert len(tweets) == 1
                tweet = tweets[0]
                assert 'place' in tweet
                assert 'geo' in tweet
                assert tweet['place']['full_name'] == 'San Francisco, CA'
                assert tweet['geo']['place_id'] == 'place123'

    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_never_calls_get_user_id(self, valid_twitter_config, sample_tweets_response):
        """Test that fetch_user_tweets_today never calls get_user_id in the new workflow"""
        service = TwitterAPIService(valid_twitter_config)
        
        # Patch get_user_id to raise AssertionError if called
        with patch.object(service, 'get_user_id', side_effect=AssertionError("Should not be called")):
            with patch.object(service, '_make_request', return_value=sample_tweets_response):
                async with service:
                    tweets = await service.fetch_user_tweets_today()
                    
                    # Should return transformed tweets without calling get_user_id
                    assert len(tweets) == 2
                    assert tweets[0]["tweet_id"] == "1234567890123456789"