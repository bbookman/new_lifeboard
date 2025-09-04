import pytest
import os
import json
from datetime import datetime
from sources.twitter import TwitterSource
from config.models import TwitterConfig
from core.database import DatabaseService
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.fixture
def sample_twitter_export(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    tweets_js_path = data_dir / "tweet.js"

    tweets_data = [
        {
            "tweet": {
                "id": "123",
                "created_at": "Mon May 06 12:00:00 +0000 2024",
                "full_text": "This is a test tweet.",
                "entities": {
                    "media": [
                        {
                            "media_url_https": "https://example.com/image.jpg"
                        }
                    ]
                }
            }
        },
        {
            "tweet": {
                "id": "456",
                "created_at": "Tue May 07 12:00:00 +0000 2024",
                "full_text": "Another test tweet.",
                "entities": {}
            }
        }
    ]

    with open(tweets_js_path, "w") as f:
        f.write(f"window.YTD.tweet.part0 = {json.dumps(tweets_data)}")

    return tmp_path

def test_parse_twitter_export(sample_twitter_export):
    # Mock config and db_service
    mock_config = MagicMock(spec=TwitterConfig)
    mock_db_service = MagicMock(spec=DatabaseService)
    
    # Instantiate TwitterSource
    twitter_source = TwitterSource(mock_config, mock_db_service)

    # Read the raw tweet data from the generated file
    tweet_js_path = sample_twitter_export / "data" / "tweet.js"
    with open(tweet_js_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Remove JavaScript wrapper
        if 'window.YTD.tweet.part0 = [' in content:
            content = content.split('window.YTD.tweet.part0 = [', 1)[1]
            content = content.rsplit(']', 1)[0]
        raw_tweets = json.loads(f'[{content}]')

    tweets = twitter_source._parse_tweets(raw_tweets)

    assert len(tweets) == 2

    assert tweets[0]['tweet_id'] == "123"
    assert tweets[0]['text'] == "This is a test tweet."
    assert json.loads(tweets[0]['media_urls']) == ["https://example.com/image.jpg"]

    assert tweets[1]['tweet_id'] == "456"
    assert tweets[1]['text'] == "Another test tweet."
    assert json.loads(tweets[1]['media_urls']) == []

@pytest.mark.asyncio
async def test_twitter_source_fetch_items():
    mock_config = MagicMock(spec=TwitterConfig)
    mock_config.is_configured.return_value = True
    mock_config.is_api_configured.return_value = False  # No API configured
    mock_db_service = MagicMock(spec=DatabaseService)
    mock_db_service.get_data_items_by_namespace.return_value = []
    
    source = TwitterSource(mock_config, mock_db_service)

    items = []
    async for item in source.fetch_items():
        items.append(item)
    
    # Should have no items since database is empty and API is not configured
    assert len(items) == 0

@pytest.mark.asyncio
async def test_twitter_source_test_connection(sample_twitter_export):
    mock_config = MagicMock(spec=TwitterConfig)
    mock_config.is_configured.return_value = True
    mock_config.is_api_configured.return_value = False  # No API configured
    mock_db_service = MagicMock(spec=DatabaseService)
    source = TwitterSource(mock_config, mock_db_service)
    assert await source.test_connection()

@pytest.mark.asyncio
async def test_twitter_source_test_connection_fail(tmp_path):
    mock_config = MagicMock(spec=TwitterConfig)
    mock_config.is_configured.return_value = False  # Completely disabled
    mock_config.is_api_configured.return_value = False
    mock_db_service = MagicMock(spec=DatabaseService)
    source = TwitterSource(mock_config, mock_db_service)
    assert not await source.test_connection()

@pytest.mark.asyncio
async def test_twitter_source_test_connection_with_api_success():
    # Create real config instead of mock to avoid attribute errors
    real_config = TwitterConfig(
        enabled=True,
        bearer_token="test_token",
        username="testuser",
        user_id="123456789",
        max_retries=3,
        retry_delay=1.0,
        request_timeout=30.0
    )
    mock_db_service = MagicMock(spec=DatabaseService)
    
    source = TwitterSource(real_config, mock_db_service)
    
    # Mock the API service context manager and method
    with patch.object(source.api_service, '__aenter__', new=AsyncMock(return_value=source.api_service)):
        with patch.object(source.api_service, '__aexit__', new=AsyncMock(return_value=None)):
            with patch.object(source.api_service, 'fetch_user_tweets_today', return_value=[]):
                result = await source.test_connection()
                assert result is True

@pytest.mark.asyncio
async def test_twitter_source_test_connection_with_api_failure():
    mock_config = MagicMock(spec=TwitterConfig)
    mock_config.is_configured.return_value = True
    mock_config.is_api_configured.return_value = True
    mock_config.user_id = "123456789"
    mock_db_service = MagicMock(spec=DatabaseService)
    
    source = TwitterSource(mock_config, mock_db_service)
    
    # Mock API failure
    with patch.object(source.api_service, '__aenter__', new=AsyncMock(return_value=source.api_service)):
        with patch.object(source.api_service, '__aexit__', new=AsyncMock(return_value=None)):
            with patch.object(source.api_service, 'fetch_user_tweets_today', side_effect=Exception("API Error")):
                result = await source.test_connection()
                assert result is False

@pytest.mark.asyncio
async def test_twitter_source_api_not_configured_missing_user_id():
    """Test that TwitterSource handles missing user_id appropriately"""
    config = TwitterConfig(
        enabled=True,
        bearer_token="valid_token",
        user_id=None  # Missing user_id
    )
    mock_db_service = MagicMock(spec=DatabaseService)
    source = TwitterSource(config, mock_db_service)
    
    # API should not be considered configured
    assert not config.is_api_configured()
    
    # Connection test should still pass (for archive mode)
    assert await source.test_connection()

@pytest.mark.asyncio
async def test_api_service_not_invoked_when_user_id_missing():
    """Test that API service methods are not invoked when user_id is missing"""
    config = TwitterConfig(
        enabled=True,
        bearer_token="valid_token",
        user_id=None  # Missing user_id makes API invalid
    )
    mock_db_service = MagicMock(spec=DatabaseService)
    mock_db_service.get_data_items_by_namespace.return_value = []  # Empty database
    mock_ingestion_service = MagicMock()
    
    source = TwitterSource(config, mock_db_service, mock_ingestion_service)
    
    # Mock the API service methods to track if they're called
    with patch.object(source.api_service, '__aenter__', new=AsyncMock()) as mock_aenter:
        with patch.object(source.api_service, '__aexit__', new=AsyncMock()) as mock_aexit:
            with patch.object(source.api_service, 'fetch_user_tweets_today') as mock_fetch:
                with patch.object(source, 'fetch_today_tweets') as mock_fetch_today:
                    
                    # Call fetch_items - should not invoke API when user_id is missing
                    items = []
                    async for item in source.fetch_items():
                        items.append(item)
                    
                    # Verify API methods were not called since user_id is missing
                    mock_aenter.assert_not_called()
                    mock_aexit.assert_not_called() 
                    mock_fetch.assert_not_called()
                    mock_fetch_today.assert_not_called()
                    
                    # Should return empty list (no database items, no API calls)
                    assert len(items) == 0
