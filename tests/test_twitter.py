import json
from unittest.mock import MagicMock, patch

import pytest

from config.models import TwitterConfig
from core.database import DatabaseService
from sources.twitter import TwitterSource


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
                            "media_url_https": "https://example.com/image.jpg",
                        },
                    ],
                },
            },
        },
        {
            "tweet": {
                "id": "456",
                "created_at": "Tue May 07 12:00:00 +0000 2024",
                "full_text": "Another test tweet.",
                "entities": {},
            },
        },
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
    with open(tweet_js_path, encoding="utf-8") as f:
        content = f.read()
        # Remove JavaScript wrapper
        if "window.YTD.tweet.part0 = [" in content:
            content = content.split("window.YTD.tweet.part0 = [", 1)[1]
            content = content.rsplit("]", 1)[0]
        raw_tweets = json.loads(f"[{content}]")

    tweets = twitter_source._parse_tweets(raw_tweets)

    assert len(tweets) == 2

    assert tweets[0]["tweet_id"] == "123"
    assert tweets[0]["text"] == "This is a test tweet."
    assert json.loads(tweets[0]["media_urls"]) == ["https://example.com/image.jpg"]

    assert tweets[1]["tweet_id"] == "456"
    assert tweets[1]["text"] == "Another test tweet."
    assert json.loads(tweets[1]["media_urls"]) == []

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
        max_retries=3,
        retry_delay=1.0,
        request_timeout=30.0,
    )
    mock_db_service = MagicMock(spec=DatabaseService)

    source = TwitterSource(real_config, mock_db_service)

    # Mock the API service context manager and method
    with patch.object(source.api_service, "__aenter__", return_value=source.api_service):
        with patch.object(source.api_service, "__aexit__", return_value=None):
            with patch.object(source.api_service, "get_user_id", return_value="123456789"):
                result = await source.test_connection()
                assert result is True

@pytest.mark.asyncio
async def test_twitter_source_test_connection_with_api_failure():
    mock_config = MagicMock(spec=TwitterConfig)
    mock_config.is_configured.return_value = True
    mock_config.is_api_configured.return_value = True
    mock_config.username = "testuser"
    mock_db_service = MagicMock(spec=DatabaseService)

    source = TwitterSource(mock_config, mock_db_service)

    # Mock API failure
    with patch.object(source.api_service, "__aenter__", return_value=source.api_service):
        with patch.object(source.api_service, "__aexit__", return_value=None):
            with patch.object(source.api_service, "get_user_id", side_effect=Exception("API Error")):
                result = await source.test_connection()
                assert result is False
