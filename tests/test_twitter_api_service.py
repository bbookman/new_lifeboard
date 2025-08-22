from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from config.models import TwitterConfig
from services.twitter_api_service import TwitterAPIService


@pytest.fixture
def valid_twitter_config():
    """Valid Twitter configuration for testing"""
    return TwitterConfig(
        bearer_token="valid_bearer_token_123",
        username="testuser",
        max_retries=2,
        retry_delay=0.1,
        request_timeout=5.0,
    )

@pytest.fixture
def invalid_twitter_config():
    """Invalid Twitter configuration for testing"""
    return TwitterConfig(
        bearer_token=None,
        username=None,
    )

@pytest.fixture
def sample_user_response():
    """Sample Twitter API user response"""
    return {
        "data": {
            "id": "123456789",
            "name": "Test User",
            "username": "testuser",
        },
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
                "public_metrics": {
                    "retweet_count": 5,
                    "like_count": 10,
                    "reply_count": 2,
                    "quote_count": 1,
                },
                "context_annotations": [
                    {
                        "domain": {"id": "66", "name": "Twitter Platform"},
                        "entity": {"id": "781974596752842752", "name": "Services"},
                    },
                ],
            },
            {
                "id": "9876543210987654321",
                "text": "Another test tweet with no metrics",
                "created_at": "2024-01-15T14:45:00.000Z",
            },
        ],
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

        # Test context manager entry
        async with service as ctx_service:
            assert ctx_service is service
            assert service.session is not None
            assert isinstance(service.session, aiohttp.ClientSession)
            assert service.session._timeout.total == 5.0  # request_timeout

            # Check headers
            auth_header = service.session._default_headers.get("Authorization")
            assert auth_header == "Bearer valid_bearer_token_123"

            user_agent = service.session._default_headers.get("User-Agent")
            assert user_agent == "Lifeboard/1.0"

        # Session should be closed after context exit
        assert service.session.closed

    @pytest.mark.asyncio
    async def test_make_request_success(self, valid_twitter_config, sample_user_response):
        """Test successful API request"""
        service = TwitterAPIService(valid_twitter_config)

        with patch("aiohttp.ClientSession.get") as mock_get:
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
        """Test rate-limited API request with retry"""
        service = TwitterAPIService(valid_twitter_config)

        with patch("aiohttp.ClientSession.get") as mock_get:
            with patch("asyncio.sleep") as mock_sleep:
                # First call: rate limited, second call: success
                mock_response_429 = AsyncMock()
                mock_response_429.status = 429
                mock_response_429.headers = {"retry-after": "1"}
                mock_response_429.json = AsyncMock(return_value={"error": "Rate limited"})

                mock_response_200 = AsyncMock()
                mock_response_200.status = 200
                mock_response_200.json = AsyncMock(return_value={"data": {"id": "123"}})

                mock_get.return_value.__aenter__.side_effect = [mock_response_429, mock_response_200]

                async with service:
                    result = await service._make_request("https://api.twitter.com/2/test")

                    assert result == {"data": {"id": "123"}}
                    assert mock_get.call_count == 2
                    mock_sleep.assert_called_once_with(1)  # retry-after value

    @pytest.mark.asyncio
    async def test_make_request_unauthorized(self, valid_twitter_config):
        """Test unauthorized API request"""
        service = TwitterAPIService(valid_twitter_config)

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.json = AsyncMock(return_value={"error": "Unauthorized"})
            mock_get.return_value.__aenter__.return_value = mock_response

            async with service:
                with pytest.raises(ValueError, match="Unauthorized: Check your Twitter bearer token"):
                    await service._make_request("https://api.twitter.com/2/test")

    @pytest.mark.asyncio
    async def test_make_request_user_not_found(self, valid_twitter_config):
        """Test user not found API request"""
        service = TwitterAPIService(valid_twitter_config)

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.json = AsyncMock(return_value={"error": "User not found"})
            mock_get.return_value.__aenter__.return_value = mock_response

            async with service:
                with pytest.raises(ValueError, match="User 'testuser' not found"):
                    await service._make_request("https://api.twitter.com/2/test")

    @pytest.mark.asyncio
    async def test_make_request_max_retries_exceeded(self, valid_twitter_config):
        """Test max retries exceeded"""
        service = TwitterAPIService(valid_twitter_config)

        with patch("aiohttp.ClientSession.get") as mock_get:
            with patch("asyncio.sleep"):
                # All requests fail with 500
                mock_response = AsyncMock()
                mock_response.status = 500
                mock_response.json = AsyncMock(return_value={"error": "Internal server error"})
                mock_get.return_value.__aenter__.return_value = mock_response

                async with service:
                    with pytest.raises(Exception, match="Twitter API error 500"):
                        await service._make_request("https://api.twitter.com/2/test")

                    assert mock_get.call_count == 2  # max_retries

    @pytest.mark.asyncio
    async def test_get_user_id_success(self, valid_twitter_config, sample_user_response):
        """Test successful user ID retrieval"""
        service = TwitterAPIService(valid_twitter_config)

        with patch.object(service, "_make_request", return_value=sample_user_response):
            async with service:
                user_id = await service.get_user_id("testuser")

                assert user_id == "123456789"

    @pytest.mark.asyncio
    async def test_get_user_id_no_data(self, valid_twitter_config):
        """Test user ID retrieval with no data"""
        service = TwitterAPIService(valid_twitter_config)

        with patch.object(service, "_make_request", return_value={"errors": [{"detail": "User not found"}]}):
            async with service:
                with pytest.raises(ValueError, match="User data not found for username: testuser"):
                    await service.get_user_id("testuser")

    @pytest.mark.asyncio
    async def test_get_todays_tweets_success(self, valid_twitter_config, sample_tweets_response):
        """Test successful today's tweets retrieval"""
        service = TwitterAPIService(valid_twitter_config)

        with patch.object(service, "_make_request", return_value=sample_tweets_response):
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

        with patch.object(service, "_make_request", return_value=empty_tweets_response):
            async with service:
                tweets = await service.get_todays_tweets("123456789")

                assert len(tweets) == 0

    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_success(self, valid_twitter_config, sample_user_response, sample_tweets_response):
        """Test successful full workflow"""
        service = TwitterAPIService(valid_twitter_config)

        def mock_make_request(url, params=None):
            if "users/by/username" in url:
                return sample_user_response
            if "users/123456789/tweets" in url:
                return sample_tweets_response
            raise ValueError(f"Unexpected URL: {url}")

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            async with service:
                tweets = await service.fetch_user_tweets_today()

                assert len(tweets) == 2

                # Check transformed format
                tweet1 = tweets[0]
                assert tweet1["tweet_id"] == "1234567890123456789"
                assert tweet1["text"] == "This is a test tweet from today"
                assert tweet1["days_date"] == "2024-01-15"
                assert tweet1["media_urls"] == "[]"
                assert tweet1["public_metrics"] == {
                    "retweet_count": 5,
                    "like_count": 10,
                    "reply_count": 2,
                    "quote_count": 1,
                }

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
        """Test error handling during fetch"""
        service = TwitterAPIService(valid_twitter_config)

        with patch.object(service, "get_user_id", side_effect=Exception("API Error")):
            async with service:
                with pytest.raises(Exception, match="API Error"):
                    await service.fetch_user_tweets_today()

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

        with patch("aiohttp.ClientSession.get") as mock_get:
            with patch("asyncio.sleep") as mock_sleep:
                # First call: network error, second call: success
                mock_get.return_value.__aenter__.side_effect = [
                    aiohttp.ClientError("Network error"),
                    AsyncMock(status=200, json=AsyncMock(return_value={"data": {"id": "123"}})),
                ]

                async with service:
                    result = await service._make_request("https://api.twitter.com/2/test")

                    assert result == {"data": {"id": "123"}}
                    assert mock_get.call_count == 2
                    mock_sleep.assert_called_once_with(0.1)  # retry_delay
