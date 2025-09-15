"""
Unit tests for TwitterAPIService and TwitterRateLimitService in manual-only mode.

These tests verify that both services continue to function correctly when used
for manual operations without automatic scheduling, ensuring rate limiting,
API connectivity, and data processing work as expected.
"""

import asyncio
import json
import logging
import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call
import aiohttp
from aioresponses import aioresponses

# Import the services under test
from services.twitter_api_service import (
    TwitterAPIService,
    TwitterAPIError,
    TwitterAuthError,
    TwitterRateLimitError,
    TwitterNotFoundError,
    TwitterPermissionError
)
from services.twitter_rate_limit_service import TwitterRateLimitService


# Mock TwitterConfig class
class MockTwitterConfig:
    """Mock TwitterConfig for testing"""
    
    def __init__(
        self,
        bearer_token: str = "test_bearer_token_1234567890abcdef",
        user_id: str = "123456789",
        username: str = "testuser",
        request_timeout: int = 30,
        retry_delay: float = 1.0,
        other_error_max_retries: int = 3,
        lookback_days: int = 1,
        diagnostic_mode: bool = False
    ):
        self.bearer_token = bearer_token
        self.user_id = user_id
        self.username = username
        self.request_timeout = request_timeout
        self.retry_delay = retry_delay
        self.other_error_max_retries = other_error_max_retries
        self.lookback_days = lookback_days
        self.diagnostic_mode = diagnostic_mode
    
    def is_api_configured(self) -> bool:
        """Check if API is properly configured"""
        return bool(self.bearer_token and self.user_id)


# Mock DatabaseService class
class MockDatabaseService:
    """Mock DatabaseService for testing"""
    
    def __init__(self):
        self.data = {}
        self.query_log = []
    
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Mock fetch_one method"""
        self.query_log.append(('fetch_one', query, params))
        
        if 'data_sources' in query and 'namespace = ?' in query:
            namespace = params[0] if params else None
            if namespace == 'twitter':
                return self.data.get('twitter_last_synced')
        return None
    
    async def execute_query(self, query: str, params: tuple = None) -> int:
        """Mock execute_query method"""
        self.query_log.append(('execute_query', query, params))
        
        if 'UPDATE data_sources' in query and 'namespace = ?' in query:
            if params and len(params) >= 2:
                timestamp, namespace = params[0], params[1]
                if namespace == 'twitter':
                    self.data['twitter_last_synced'] = {'last_synced': timestamp}
                    return 1
        return 0
    
    def set_last_synced(self, timestamp: str):
        """Helper to set last synced time for testing"""
        self.data['twitter_last_synced'] = {'last_synced': timestamp}
    
    def clear_data(self):
        """Helper to clear test data"""
        self.data.clear()
        self.query_log.clear()


@pytest.fixture
def mock_config():
    """Fixture providing a mock Twitter configuration"""
    return MockTwitterConfig()


@pytest.fixture
def mock_config_unconfigured():
    """Fixture providing an unconfigured Twitter configuration"""
    return MockTwitterConfig(bearer_token="", user_id="")


@pytest.fixture
def mock_db_service():
    """Fixture providing a mock database service"""
    return MockDatabaseService()


@pytest.fixture
def sample_tweet_data():
    """Fixture providing sample tweet data for testing"""
    return {
        'id': '1234567890123456789',
        'text': 'This is a test tweet with some content #testing',
        'created_at': '2024-01-15T10:30:00.000Z',
        'public_metrics': {
            'retweet_count': 5,
            'like_count': 10,
            'reply_count': 2,
            'quote_count': 1
        },
        'geo': {
            'place_id': 'place123'
        },
        'attachments': {
            'media_keys': ['media_key_1', 'media_key_2']
        }
    }


@pytest.fixture
def sample_api_response(sample_tweet_data):
    """Fixture providing a complete API response with includes"""
    return {
        'data': [sample_tweet_data],
        'includes': {
            'places': [
                {
                    'id': 'place123',
                    'full_name': 'San Francisco, CA',
                    'name': 'San Francisco',
                    'country': 'United States',
                    'country_code': 'US',
                    'place_type': 'city'
                }
            ],
            'media': [
                {
                    'media_key': 'media_key_1',
                    'type': 'photo',
                    'url': 'https://pbs.twimg.com/media/test1.jpg',
                    'width': 1200,
                    'height': 800
                },
                {
                    'media_key': 'media_key_2',
                    'type': 'video',
                    'preview_image_url': 'https://pbs.twimg.com/media/test2_preview.jpg',
                    'width': 1920,
                    'height': 1080
                }
            ]
        }
    }


class TestTwitterAPIService:
    """Test cases for TwitterAPIService manual operation"""
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_success(self, mock_config, sample_api_response, caplog):
        """Test successful tweet fetching with proper logging"""
        caplog.set_level(logging.INFO)
        
        with aioresponses() as m:
            # Mock the API response
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                payload=sample_api_response,
                status=200
            )
            
            async with TwitterAPIService(mock_config) as service:
                tweets = await service.fetch_user_tweets_today()
                
                assert len(tweets) == 1
                tweet = tweets[0]
                
                # Verify tweet structure
                assert tweet['tweet_id'] == '1234567890123456789'
                assert tweet['text'] == 'This is a test tweet with some content #testing'
                assert tweet['days_date'] == '2024-01-15'
                assert 'created_at' in tweet
                assert tweet['public_metrics'] == sample_api_response['data'][0]['public_metrics']
                
                # Verify media URLs are properly serialized
                media_urls = json.loads(tweet['media_urls'])
                assert len(media_urls) == 2
                assert 'https://pbs.twimg.com/media/test1.jpg' in media_urls
                assert 'https://pbs.twimg.com/media/test2_preview.jpg' in media_urls
                
                # Verify place data is included
                assert tweet['place_id'] == 'place123'
                assert tweet['place']['full_name'] == 'San Francisco, CA'
        
        # Verify logging behavior
        log_messages = [record.message for record in caplog.records]
        twitter_trace_logs = [msg for msg in log_messages if '[TWITTER TRACE]' in msg]
        
        assert len(twitter_trace_logs) > 0
        assert any('fetch_user_tweets_today starting' in msg for msg in twitter_trace_logs)
        assert any('API call completed' in msg for msg in twitter_trace_logs)
        assert any('fetch_user_tweets_today completed' in msg for msg in twitter_trace_logs)
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_unconfigured(self, mock_config_unconfigured, caplog):
        """Test behavior when API is not configured"""
        caplog.set_level(logging.INFO)
        
        async with TwitterAPIService(mock_config_unconfigured) as service:
            tweets = await service.fetch_user_tweets_today()
            
            assert tweets == []
        
        # Verify proper logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE] API Configuration validation failed' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_rate_limit_error(self, mock_config, caplog):
        """Test handling of rate limit errors"""
        caplog.set_level(logging.INFO)
        
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                status=429,
                payload={'detail': 'Rate limit exceeded'},
                headers={'retry-after': '900'}
            )
            
            async with TwitterAPIService(mock_config) as service:
                tweets = await service.fetch_user_tweets_today()
                
                assert tweets == []
        
        # Verify rate limit logging
        log_messages = [record.message for record in caplog.records]
        assert any('Rate limit exceeded' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Rate limit exceeded' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_auth_error(self, mock_config, caplog):
        """Test handling of authentication errors"""
        caplog.set_level(logging.INFO)
        
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                status=401,
                payload={'detail': 'Invalid authentication credentials'}
            )
            
            async with TwitterAPIService(mock_config) as service:
                tweets = await service.fetch_user_tweets_today()
                
                assert tweets == []
        
        # Verify auth error logging
        log_messages = [record.message for record in caplog.records]
        assert any('Authentication error' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Authentication error' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_permission_error(self, mock_config, caplog):
        """Test handling of permission errors"""
        caplog.set_level(logging.INFO)
        
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                status=403,
                payload={'detail': 'Forbidden'}
            )
            
            async with TwitterAPIService(mock_config) as service:
                tweets = await service.fetch_user_tweets_today()
                
                assert tweets == []
        
        # Verify permission error logging
        log_messages = [record.message for record in caplog.records]
        assert any('Permission error' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Permission error' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_fetch_user_tweets_today_not_found_error(self, mock_config, caplog):
        """Test handling of not found errors"""
        caplog.set_level(logging.INFO)
        
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                status=404,
                payload={'detail': 'User not found'}
            )
            
            async with TwitterAPIService(mock_config) as service:
                tweets = await service.fetch_user_tweets_today()
                
                assert tweets == []
        
        # Verify not found error logging
        log_messages = [record.message for record in caplog.records]
        assert any('Resource not found' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Resource not found' in msg for msg in log_messages)
    
    def test_parse_tweet_valid_data(self, mock_config, sample_tweet_data):
        """Test _parse_tweet with valid tweet data"""
        service = TwitterAPIService(mock_config)
        
        # Add place and media data to the tweet
        sample_tweet_data['place'] = {
            'id': 'place123',
            'full_name': 'San Francisco, CA'
        }
        sample_tweet_data['media_items'] = [
            {'url': 'https://example.com/image1.jpg'},
            {'preview_image_url': 'https://example.com/image2_preview.jpg'}
        ]
        
        result = service._parse_tweet(sample_tweet_data)
        
        assert result is not None
        assert result['tweet_id'] == '1234567890123456789'
        assert result['text'] == 'This is a test tweet with some content #testing'
        assert result['days_date'] == '2024-01-15'
        assert result['place_id'] == 'place123'
        assert result['place'] == sample_tweet_data['place']
        
        # Verify media URLs are properly serialized
        media_urls = json.loads(result['media_urls'])
        assert len(media_urls) == 2
        assert 'https://example.com/image1.jpg' in media_urls
        assert 'https://example.com/image2_preview.jpg' in media_urls
    
    def test_parse_tweet_missing_required_fields(self, mock_config, caplog):
        """Test _parse_tweet with missing required fields"""
        caplog.set_level(logging.DEBUG)
        service = TwitterAPIService(mock_config)
        
        # Test missing ID
        tweet_no_id = {'text': 'Test tweet', 'created_at': '2024-01-15T10:30:00.000Z'}
        result = service._parse_tweet(tweet_no_id)
        assert result is None
        
        # Test missing text
        tweet_no_text = {'id': '123', 'created_at': '2024-01-15T10:30:00.000Z'}
        result = service._parse_tweet(tweet_no_text)
        assert result is None
        
        # Test missing created_at
        tweet_no_date = {'id': '123', 'text': 'Test tweet'}
        result = service._parse_tweet(tweet_no_date)
        assert result is None
        
        # Verify debug logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and "missing 'id' field" in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and "missing 'text' field" in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and "missing 'created_at' field" in msg for msg in log_messages)
    
    def test_parse_tweet_invalid_timestamp(self, mock_config, caplog):
        """Test _parse_tweet with invalid timestamp"""
        caplog.set_level(logging.DEBUG)
        service = TwitterAPIService(mock_config)
        
        tweet_invalid_date = {
            'id': '123',
            'text': 'Test tweet',
            'created_at': 'invalid-date-format'
        }
        
        result = service._parse_tweet(tweet_invalid_date)
        assert result is None
        
        # Verify debug logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'has invalid timestamp' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_test_api_connectivity_success(self, mock_config):
        """Test successful API connectivity test"""
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}",
                payload={
                    'data': {
                        'id': mock_config.user_id,
                        'username': mock_config.username,
                        'name': 'Test User'
                    }
                },
                status=200
            )
            
            async with TwitterAPIService(mock_config) as service:
                result = await service.test_api_connectivity()
                
                assert result['success'] is True
                assert 'response_data' in result
                assert 'duration_ms' in result
                assert result['user_info']['id'] == mock_config.user_id
                assert result['user_info']['username'] == mock_config.username
    
    @pytest.mark.asyncio
    async def test_test_api_connectivity_unconfigured(self, mock_config_unconfigured):
        """Test API connectivity test with unconfigured service"""
        async with TwitterAPIService(mock_config_unconfigured) as service:
            result = await service.test_api_connectivity()
            
            assert result['success'] is False
            assert result['error'] == 'API not configured'
            assert result['details'] == 'Missing bearer token or user ID'
    
    @pytest.mark.asyncio
    async def test_test_api_connectivity_failure(self, mock_config):
        """Test API connectivity test with network failure"""
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}",
                status=500,
                payload={'error': 'Internal server error'}
            )
            
            async with TwitterAPIService(mock_config) as service:
                result = await service.test_api_connectivity()
                
                assert result['success'] is False
                assert 'error' in result
                assert 'error_type' in result
                assert 'duration_ms' in result
    
    def test_is_configured(self, mock_config, mock_config_unconfigured, caplog):
        """Test configuration checking"""
        caplog.set_level(logging.INFO)
        
        # Test configured service
        service_configured = TwitterAPIService(mock_config)
        assert service_configured.is_configured() is True
        
        # Test unconfigured service
        service_unconfigured = TwitterAPIService(mock_config_unconfigured)
        assert service_unconfigured.is_configured() is False
        
        # Verify diagnostic logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Configuration Diagnostics' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Bearer token present' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Final configuration result' in msg for msg in log_messages)


class TestTwitterRateLimitService:
    """Test cases for TwitterRateLimitService manual operation"""
    
    @pytest.mark.asyncio
    async def test_can_fetch_now_no_previous_fetch(self, mock_db_service, caplog):
        """Test can_fetch_now when no previous fetch exists"""
        caplog.set_level(logging.INFO)
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        can_fetch, minutes_until = await service.can_fetch_now()
        
        assert can_fetch is True
        assert minutes_until == 0
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'No previous fetch found' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_can_fetch_now_within_rate_limit(self, mock_db_service, caplog):
        """Test can_fetch_now when within rate limit period"""
        caplog.set_level(logging.INFO)
        
        # Set last fetch to 5 minutes ago
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        mock_db_service.set_last_synced(five_minutes_ago.isoformat())
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        can_fetch, minutes_until = await service.can_fetch_now()
        
        assert can_fetch is False
        assert minutes_until > 0
        assert minutes_until <= 11  # Should be around 10-11 minutes remaining
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Rate limited' in msg for msg in log_messages)
        assert any('[TWITTER TRACE]' in msg and 'Elapsed minutes' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_can_fetch_now_outside_rate_limit(self, mock_db_service, caplog):
        """Test can_fetch_now when outside rate limit period"""
        caplog.set_level(logging.INFO)
        
        # Set last fetch to 20 minutes ago
        twenty_minutes_ago = datetime.utcnow() - timedelta(minutes=20)
        mock_db_service.set_last_synced(twenty_minutes_ago.isoformat())
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        can_fetch, minutes_until = await service.can_fetch_now()
        
        assert can_fetch is True
        assert minutes_until == 0
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'allowing fetch' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_record_fetch_attempt_success(self, mock_db_service, caplog):
        """Test recording successful fetch attempt"""
        caplog.set_level(logging.INFO)
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        await service.record_fetch_attempt(success=True)
        
        # Verify database was updated
        assert len(mock_db_service.query_log) > 0
        update_queries = [log for log in mock_db_service.query_log if log[0] == 'execute_query']
        assert len(update_queries) > 0
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Recorded successful fetch' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_record_fetch_attempt_failure(self, mock_db_service, caplog):
        """Test recording failed fetch attempt"""
        caplog.set_level(logging.INFO)
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        await service.record_fetch_attempt(success=False)
        
        # Verify database was not updated for failed attempts
        update_queries = [log for log in mock_db_service.query_log if log[0] == 'execute_query']
        assert len(update_queries) == 0
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Failed fetch not recorded' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_get_last_fetch_time(self, mock_db_service):
        """Test retrieving last fetch time"""
        # Test with no previous fetch
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        last_fetch = await service.get_last_fetch_time()
        assert last_fetch is None
        
        # Test with previous fetch
        test_time = datetime.utcnow() - timedelta(minutes=10)
        mock_db_service.set_last_synced(test_time.isoformat())
        
        last_fetch = await service.get_last_fetch_time()
        assert last_fetch is not None
        assert abs((last_fetch - test_time).total_seconds()) < 1  # Should be very close
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_no_previous_fetch(self, mock_db_service):
        """Test status for day when no previous fetch exists"""
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        today = datetime.utcnow().strftime('%Y-%m-%d')
        status = await service.get_status_for_day(today)
        
        assert status is None
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_recent_fetch(self, mock_db_service):
        """Test status for day with recent fetch"""
        # Set last fetch to 5 minutes ago
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        mock_db_service.set_last_synced(five_minutes_ago.isoformat())
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        today = datetime.utcnow().strftime('%Y-%m-%d')
        status = await service.get_status_for_day(today)
        
        assert status is not None
        assert status['type'] == 'active'
        assert status['icon'] == '🔄'
        assert 'minutes_until_next' in status
        assert 'Updated' in status['status']
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_old_date(self, mock_db_service):
        """Test status for older date"""
        # Set last fetch to 1 hour ago
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        mock_db_service.set_last_synced(one_hour_ago.isoformat())
        
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        # Test with date 5 days ago
        old_date = (datetime.utcnow() - timedelta(days=5)).strftime('%Y-%m-%d')
        status = await service.get_status_for_day(old_date)
        
        assert status is not None
        assert status['type'] == 'complete'
        assert status['icon'] == '✅'
        assert 'Data complete' in status['status']
    
    def test_format_time_ago(self, mock_db_service):
        """Test time formatting functionality"""
        service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        now = datetime.utcnow()
        
        # Test "just now"
        result = service._format_time_ago(now - timedelta(seconds=30))
        assert result == "just now"
        
        # Test minutes
        result = service._format_time_ago(now - timedelta(minutes=5))
        assert result == "5 min ago"
        
        # Test hours
        result = service._format_time_ago(now - timedelta(hours=2))
        assert result == "2h ago"
        
        # Test days
        result = service._format_time_ago(now - timedelta(days=3))
        assert result == "3d ago"
    
    @pytest.mark.asyncio
    async def test_different_rate_limit_intervals(self, mock_db_service):
        """Test service with different rate limit intervals"""
        # Test with 5-minute interval
        service_5min = TwitterRateLimitService(mock_db_service, rate_limit_minutes=5.0)
        
        # Set last fetch to 3 minutes ago
        three_minutes_ago = datetime.utcnow() - timedelta(minutes=3)
        mock_db_service.set_last_synced(three_minutes_ago.isoformat())
        
        can_fetch, minutes_until = await service_5min.can_fetch_now()
        assert can_fetch is False
        assert minutes_until > 0
        assert minutes_until <= 3
        
        # Test with 30-minute interval
        service_30min = TwitterRateLimitService(mock_db_service, rate_limit_minutes=30.0)
        
        can_fetch, minutes_until = await service_30min.can_fetch_now()
        assert can_fetch is False
        assert minutes_until > 25  # Should be around 27 minutes remaining


class TestTwitterServicesIntegration:
    """Integration tests for TwitterAPIService and TwitterRateLimitService working together"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_before_api_call(self, mock_config, mock_db_service, sample_api_response, caplog):
        """Test that rate limiting is checked before making API calls"""
        caplog.set_level(logging.INFO)
        
        # Set up rate limit service with recent fetch
        rate_service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        two_minutes_ago = datetime.utcnow() - timedelta(minutes=2)
        mock_db_service.set_last_synced(two_minutes_ago.isoformat())
        
        # Check rate limit status
        can_fetch, minutes_until = await rate_service.can_fetch_now()
        assert can_fetch is False
        assert minutes_until > 0
        
        # In a real implementation, the API service would check this before making calls
        # For this test, we verify the rate limit service correctly reports the status
        
        # Verify logging shows rate limit status
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Rate limited' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_successful_fetch_recording(self, mock_config, mock_db_service, sample_api_response, caplog):
        """Test that successful fetches are properly recorded"""
        caplog.set_level(logging.INFO)
        
        rate_service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        # Simulate successful API call and recording
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                payload=sample_api_response,
                status=200
            )
            
            async with TwitterAPIService(mock_config) as api_service:
                tweets = await api_service.fetch_user_tweets_today()
                
                # Record the successful fetch
                await rate_service.record_fetch_attempt(success=True)
                
                # Verify tweets were fetched
                assert len(tweets) == 1
                
                # Verify fetch was recorded
                last_fetch = await rate_service.get_last_fetch_time()
                assert last_fetch is not None
                
                # Verify rate limit is now active
                can_fetch, minutes_until = await rate_service.can_fetch_now()
                assert can_fetch is False
                assert minutes_until > 0
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Recorded successful fetch' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_failed_fetch_not_recorded(self, mock_config, mock_db_service, caplog):
        """Test that failed fetches are not recorded for rate limiting"""
        caplog.set_level(logging.INFO)
        
        rate_service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        # Simulate failed API call
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                status=429,
                payload={'detail': 'Rate limit exceeded'}
            )
            
            async with TwitterAPIService(mock_config) as api_service:
                tweets = await api_service.fetch_user_tweets_today()
                
                # Record the failed fetch
                await rate_service.record_fetch_attempt(success=False)
                
                # Verify no tweets were fetched
                assert tweets == []
                
                # Verify fetch was not recorded for rate limiting
                last_fetch = await rate_service.get_last_fetch_time()
                assert last_fetch is None
                
                # Verify rate limit is not active (since no successful fetch occurred)
                can_fetch, minutes_until = await rate_service.can_fetch_now()
                assert can_fetch is True
                assert minutes_until == 0
        
        # Verify logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Failed fetch not recorded' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self, mock_config_unconfigured, mock_db_service):
        """Test that both services handle unconfigured state properly"""
        # Test API service
        async with TwitterAPIService(mock_config_unconfigured) as api_service:
            assert api_service.is_configured() is False
            tweets = await api_service.fetch_user_tweets_today()
            assert tweets == []
            
            connectivity_result = await api_service.test_api_connectivity()
            assert connectivity_result['success'] is False
        
        # Test rate limit service (should work regardless of API configuration)
        rate_service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        can_fetch, minutes_until = await rate_service.can_fetch_now()
        assert can_fetch is True  # No previous fetch, so should allow
        assert minutes_until == 0
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_config, caplog):
        """Test handling of database errors in rate limit service"""
        caplog.set_level(logging.ERROR)
        
        # Create a mock database service that raises errors
        class ErrorDatabaseService:
            async def fetch_one(self, query: str, params: tuple = None):
                raise Exception("Database connection error")
            
            async def execute_query(self, query: str, params: tuple = None):
                raise Exception("Database write error")
        
        error_db_service = ErrorDatabaseService()
        rate_service = TwitterRateLimitService(error_db_service, rate_limit_minutes=15.0)
        
        # Test that errors are handled gracefully
        can_fetch, minutes_until = await rate_service.can_fetch_now()
        assert can_fetch is True  # Should default to allowing fetch on error
        assert minutes_until == 0
        
        # Test recording attempt with database error
        await rate_service.record_fetch_attempt(success=True)
        
        # Verify error logging
        log_messages = [record.message for record in caplog.records]
        assert any('[TWITTER TRACE]' in msg and 'Error checking rate limit' in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_manual_mode_independence(self, mock_config, mock_db_service, sample_api_response):
        """Test that services work independently without scheduler integration"""
        # This test verifies that the services work in manual-only mode
        # without requiring any scheduler or automatic sync components
        
        rate_service = TwitterRateLimitService(mock_db_service, rate_limit_minutes=15.0)
        
        # Verify initial state
        can_fetch, minutes_until = await rate_service.can_fetch_now()
        assert can_fetch is True
        assert minutes_until == 0
        
        # Perform manual fetch
        with aioresponses() as m:
            m.get(
                f"https://api.twitter.com/2/users/{mock_config.user_id}/tweets",
                payload=sample_api_response,
                status=200
            )
            
            async with TwitterAPIService(mock_config) as api_service:
                # Verify service is configured
                assert api_service.is_configured() is True
                
                # Perform fetch
                tweets = await api_service.fetch_user_tweets_today()
                assert len(tweets) == 1
                
                # Record successful fetch
                await rate_service.record_fetch_attempt(success=True)
                
                # Verify rate limiting is now active
                can_fetch, minutes_until = await rate_service.can_fetch_now()
                assert can_fetch is False
                assert minutes_until > 0
        
        # Verify the services maintain their state independently
        # and don't require any external scheduler or sync manager
        last_fetch = await rate_service.get_last_fetch_time()
        assert last_fetch is not None
        
        # Test status reporting
        today = datetime.utcnow().strftime('%Y-%m-%d')
        status = await rate_service.get_status_for_day(today)
        assert status is not None
        assert status['type'] == 'active'