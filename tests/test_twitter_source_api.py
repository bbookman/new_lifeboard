import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import json

from sources.twitter import TwitterSource
from sources.base import DataItem
from config.models import TwitterConfig
from core.database import DatabaseService
from services.twitter_api_service import TwitterAPIService

@pytest.fixture
def api_enabled_config():
    """Twitter configuration with API enabled"""
    return TwitterConfig(
        enabled=True,
        bearer_token="valid_bearer_token_123",
        username="testuser",
        max_retries=2,
        retry_delay=0.1,
        request_timeout=5.0
    )

@pytest.fixture
def api_disabled_config():
    """Twitter configuration with API disabled"""
    return TwitterConfig(
        enabled=True,
        bearer_token=None,
        username=None
    )

@pytest.fixture
def mock_database_service():
    """Mock database service"""
    db_service = MagicMock(spec=DatabaseService)
    db_service.get_data_items_by_namespace.return_value = []
    db_service.get_data_items_by_ids.return_value = []
    return db_service

@pytest.fixture
def mock_ingestion_service():
    """Mock ingestion service"""
    ingestion_service = AsyncMock()
    ingestion_service.ingest_items.return_value = MagicMock(
        items_stored=2,
        errors=[]
    )
    return ingestion_service

@pytest.fixture
def sample_api_tweets():
    """Sample tweets from API"""
    return [
        {
            "tweet_id": "1234567890123456789",
            "created_at": "2024-01-15T10:30:00+00:00",
            "days_date": "2024-01-15",
            "text": "This is a test tweet from API",
            "media_urls": "[]",
            "public_metrics": {"like_count": 5, "retweet_count": 2},
            "context_annotations": []
        },
        {
            "tweet_id": "9876543210987654321",
            "created_at": "2024-01-15T14:45:00+00:00",
            "days_date": "2024-01-15",
            "text": "Another test tweet from API",
            "media_urls": "[]",
            "public_metrics": {"like_count": 10, "retweet_count": 1},
            "context_annotations": []
        }
    ]

@pytest.fixture
def existing_database_items():
    """Sample existing items in database"""
    return [
        {
            "namespace": "twitter",
            "source_id": "old_tweet_123",
            "content": "Old tweet from database",
            "metadata": json.dumps({
                "media_urls": "[]",
                "source_type": "twitter_archive",
                "days_date": "2024-01-14"
            }),
            "created_at": "2024-01-14T12:00:00+00:00",
            "updated_at": "2024-01-14T12:00:00+00:00"
        }
    ]

class TestTwitterSourceAPIIntegration:
    """Test TwitterSource integration with API functionality"""

    def test_twitter_source_initialization_with_api(self, api_enabled_config, mock_database_service):
        """Test TwitterSource initialization with API configuration"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        
        assert source.namespace == "twitter"
        assert source.config == api_enabled_config
        assert source.db_service == mock_database_service
        assert source.processor is not None
        assert source.api_service is not None
        assert isinstance(source.api_service, TwitterAPIService)

    @pytest.mark.asyncio
    async def test_fetch_today_tweets_api_configured(self, api_enabled_config, mock_database_service, sample_api_tweets):
        """Test fetching today's tweets when API is configured"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        
        with patch.object(source.api_service, 'fetch_user_tweets_today', return_value=sample_api_tweets):
            tweets = await source.fetch_today_tweets()
            
            assert len(tweets) == 2
            assert tweets[0]["tweet_id"] == "1234567890123456789"
            assert tweets[0]["text"] == "This is a test tweet from API"
            assert tweets[1]["tweet_id"] == "9876543210987654321"

    @pytest.mark.asyncio
    async def test_fetch_today_tweets_api_not_configured(self, api_disabled_config, mock_database_service):
        """Test fetching today's tweets when API is not configured"""
        source = TwitterSource(api_disabled_config, mock_database_service)
        
        tweets = await source.fetch_today_tweets()
        
        assert tweets == []

    @pytest.mark.asyncio
    async def test_fetch_today_tweets_api_error(self, api_enabled_config, mock_database_service):
        """Test fetching today's tweets when API throws an error"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        
        with patch.object(source.api_service, 'fetch_user_tweets_today', side_effect=Exception("API Error")):
            tweets = await source.fetch_today_tweets()
            
            assert tweets == []

    @pytest.mark.asyncio
    async def test_get_existing_tweet_ids(self, api_enabled_config, mock_database_service, existing_database_items):
        """Test getting existing tweet IDs from database"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        mock_database_service.get_data_items_by_namespace.return_value = existing_database_items
        
        existing_ids = await source._get_existing_tweet_ids()
        
        assert existing_ids == {"old_tweet_123"}
        mock_database_service.get_data_items_by_namespace.assert_called_once_with("twitter", limit=10000)

    @pytest.mark.asyncio
    async def test_fetch_items_with_api_new_tweets(self, api_enabled_config, mock_database_service, 
                                                  mock_ingestion_service, sample_api_tweets, existing_database_items):
        """Test fetch_items with API that has new tweets"""
        source = TwitterSource(api_enabled_config, mock_database_service, mock_ingestion_service)
        
        # Mock database calls
        mock_database_service.get_data_items_by_namespace.side_effect = [
            existing_database_items,  # For _get_existing_tweet_ids
            existing_database_items   # For getting existing data
        ]
        
        # Mock API fetch
        with patch.object(source, 'fetch_today_tweets', return_value=sample_api_tweets):
            items = []
            async for item in source.fetch_items():
                items.append(item)
            
            # Should get 3 items: 2 new from API + 1 existing from database
            assert len(items) == 3
            
            # Check API tweets were processed and yielded
            api_items = [item for item in items if item.metadata.get('source_type') == 'twitter_api']
            assert len(api_items) == 2
            
            # Check existing database item was yielded
            db_items = [item for item in items if item.source_id == 'old_tweet_123']
            assert len(db_items) == 1
            
            # Verify ingestion was called
            mock_ingestion_service.ingest_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_items_with_api_no_new_tweets(self, api_enabled_config, mock_database_service,
                                                     mock_ingestion_service, existing_database_items):
        """Test fetch_items with API that has no new tweets"""
        source = TwitterSource(api_enabled_config, mock_database_service, mock_ingestion_service)
        
        # Mock existing tweets that include what API would return
        existing_tweets_with_api = existing_database_items + [
            {
                "namespace": "twitter",
                "source_id": "1234567890123456789",  # Same as would be returned by API
                "content": "Existing API tweet",
                "metadata": json.dumps({"source_type": "twitter_api"}),
                "created_at": "2024-01-15T10:30:00+00:00",
                "updated_at": "2024-01-15T10:30:00+00:00"
            }
        ]
        
        mock_database_service.get_data_items_by_namespace.side_effect = [
            existing_tweets_with_api,  # For _get_existing_tweet_ids
            existing_tweets_with_api   # For getting existing data
        ]
        
        # Mock API returning tweet that already exists
        api_tweets = [{
            "tweet_id": "1234567890123456789",  # Already exists
            "created_at": "2024-01-15T10:30:00+00:00",
            "days_date": "2024-01-15",
            "text": "Duplicate tweet",
            "media_urls": "[]"
        }]
        
        with patch.object(source, 'fetch_today_tweets', return_value=api_tweets):
            items = []
            async for item in source.fetch_items():
                items.append(item)
            
            # Should only get existing items, no ingestion of duplicates
            assert len(items) == 2  # Original existing items
            mock_ingestion_service.ingest_items.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_items_without_api(self, api_disabled_config, mock_database_service, existing_database_items):
        """Test fetch_items without API configuration"""
        source = TwitterSource(api_disabled_config, mock_database_service)
        mock_database_service.get_data_items_by_namespace.return_value = existing_database_items
        
        items = []
        async for item in source.fetch_items():
            items.append(item)
        
        # Should only get existing database items
        assert len(items) == 1
        assert items[0].source_id == "old_tweet_123"

    @pytest.mark.asyncio
    async def test_fetch_items_with_since_filter(self, api_enabled_config, mock_database_service, existing_database_items):
        """Test fetch_items with since parameter filtering"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        mock_database_service.get_data_items_by_namespace.return_value = existing_database_items
        
        # Set since to after the existing item's date
        since = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        
        with patch.object(source, 'fetch_today_tweets', return_value=[]):
            items = []
            async for item in source.fetch_items(since=since):
                items.append(item)
            
            # Should filter out the old item
            assert len(items) == 0

    @pytest.mark.asyncio
    async def test_test_connection_with_api_success(self, api_enabled_config, mock_database_service):
        """Test connection test with successful API"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        
        with patch.object(source.api_service, 'get_user_id', return_value="123456789"):
            with patch.object(source.api_service, '__aenter__', return_value=source.api_service):
                with patch.object(source.api_service, '__aexit__', return_value=None):
                    result = await source.test_connection()
                    
                    assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_with_api_failure(self, api_enabled_config, mock_database_service):
        """Test connection test with failed API"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        
        with patch.object(source.api_service, 'get_user_id', side_effect=Exception("API Error")):
            with patch.object(source.api_service, '__aenter__', return_value=source.api_service):
                with patch.object(source.api_service, '__aexit__', return_value=None):
                    result = await source.test_connection()
                    
                    assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_without_api(self, api_disabled_config, mock_database_service):
        """Test connection test without API configuration"""
        source = TwitterSource(api_disabled_config, mock_database_service)
        
        result = await source.test_connection()
        
        assert result is True  # Should pass for basic configuration

    @pytest.mark.asyncio
    async def test_test_connection_disabled(self, mock_database_service):
        """Test connection test with disabled configuration"""
        disabled_config = TwitterConfig(enabled=False)
        source = TwitterSource(disabled_config, mock_database_service)
        
        result = await source.test_connection()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_ingest_tweets_error_handling(self, api_enabled_config, mock_database_service, mock_ingestion_service):
        """Test error handling during tweet ingestion"""
        source = TwitterSource(api_enabled_config, mock_database_service, mock_ingestion_service)
        
        # Mock ingestion service to return errors
        mock_ingestion_service.ingest_items.return_value = MagicMock(
            items_stored=1,
            errors=["Error processing tweet 2"]
        )
        
        tweets = [
            {
                "tweet_id": "123",
                "created_at": "2024-01-15T10:30:00+00:00",
                "days_date": "2024-01-15",
                "text": "Test tweet",
                "media_urls": "[]"
            }
        ]
        
        # Should not raise exception even with ingestion errors
        await source._ingest_tweets(tweets)
        
        mock_ingestion_service.ingest_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_item_by_source_id(self, api_enabled_config, mock_database_service, existing_database_items):
        """Test getting specific item by source ID"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        mock_database_service.get_data_items_by_ids.return_value = existing_database_items
        
        item = await source.get_item("old_tweet_123")
        
        assert item is not None
        assert item.source_id == "old_tweet_123"
        assert item.content == "Old tweet from database"
        mock_database_service.get_data_items_by_ids.assert_called_once_with(["twitter:old_tweet_123"])

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, api_enabled_config, mock_database_service):
        """Test getting non-existent item"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        mock_database_service.get_data_items_by_ids.return_value = []
        
        item = await source.get_item("nonexistent")
        
        assert item is None

    def test_get_source_type(self, api_enabled_config, mock_database_service):
        """Test source type identifier"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        
        assert source.get_source_type() == "twitter_archive"

    @pytest.mark.asyncio
    async def test_get_data_for_date(self, api_enabled_config, mock_database_service, existing_database_items):
        """Test getting data for specific date"""
        source = TwitterSource(api_enabled_config, mock_database_service)
        mock_database_service.get_data_items_by_date.return_value = existing_database_items
        
        data = await source.get_data_for_date("2024-01-14")
        
        assert data == existing_database_items
        mock_database_service.get_data_items_by_date.assert_called_once_with("2024-01-14", ["twitter"])

    @pytest.mark.asyncio
    async def test_data_item_processing_metadata(self, api_enabled_config, mock_database_service, mock_ingestion_service):
        """Test that API tweets are properly converted to DataItems with correct metadata"""
        source = TwitterSource(api_enabled_config, mock_database_service, mock_ingestion_service)
        
        api_tweets = [{
            "tweet_id": "123456789",
            "created_at": "2024-01-15T10:30:00+00:00",
            "days_date": "2024-01-15",
            "text": "Test tweet with metrics",
            "media_urls": "[]",
            "public_metrics": {"like_count": 5},
            "context_annotations": [{"entity": {"name": "Technology"}}]
        }]
        
        mock_database_service.get_data_items_by_namespace.side_effect = [[], []]  # No existing tweets
        
        with patch.object(source, 'fetch_today_tweets', return_value=api_tweets):
            items = []
            async for item in source.fetch_items():
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            
            assert isinstance(item, DataItem)
            assert item.namespace == "twitter"
            assert item.source_id == "123456789"
            assert item.content == "Test tweet with metrics"
            assert item.metadata["source_type"] == "twitter_api"
            assert item.metadata["public_metrics"] == {"like_count": 5}
            assert item.metadata["context_annotations"] == [{"entity": {"name": "Technology"}}]
            assert item.metadata["days_date"] == "2024-01-15"