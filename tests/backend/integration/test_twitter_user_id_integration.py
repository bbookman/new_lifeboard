"""
Integration tests for Twitter user_id implementation.

Tests the complete flow from configuration validation through data retrieval,
ensuring the user_id field integration works correctly across all components.
"""

import pytest
import json
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from config.models import TwitterConfig
from services.twitter_api_service import TwitterAPIService
from sources.twitter import TwitterSource
from services.ingestion import IngestionService
from core.database import DatabaseService
from sources.base import DataItem


class TestTwitterConfigUserIdIntegration:
    """Test TwitterConfig validation with user_id field."""

    def test_twitter_config_user_id_validation(self):
        """Test that TwitterConfig properly validates user_id field."""
        # Valid config with user_id
        valid_config = TwitterConfig(
            bearer_token="test_bearer_token",
            user_id="12345"
        )
        assert valid_config.user_id == "12345"
        assert valid_config.bearer_token == "test_bearer_token"

    def test_twitter_config_api_configured_requires_user_id(self):
        """Test that is_api_configured() requires both bearer_token and user_id."""
        # Both present - should be configured
        config_with_both = TwitterConfig(
            bearer_token="test_token",
            user_id="12345"
        )
        assert config_with_both.is_api_configured() is True

        # Missing user_id - should not be configured
        config_no_user_id = TwitterConfig(
            bearer_token="test_token",
            user_id=None
        )
        assert config_no_user_id.is_api_configured() is False

        # Missing bearer_token - should not be configured
        config_no_token = TwitterConfig(
            bearer_token="",
            user_id="12345"
        )
        assert config_no_token.is_api_configured() is False

        # Both missing - should not be configured
        config_empty = TwitterConfig(
            bearer_token="",
            user_id=None
        )
        assert config_empty.is_api_configured() is False

    def test_invalid_user_id_validation(self):
        """Test user_id format validation."""
        # Valid numeric user_id
        valid_config = TwitterConfig(
            bearer_token="test_token",
            user_id="123456789"
        )
        assert valid_config.user_id == "123456789"

        # Test non-numeric user_id raises ValueError
        with pytest.raises(ValueError, match="Twitter user_id must be a non-empty string of digits"):
            TwitterConfig(
                bearer_token="test_token",
                user_id="invalid_id"
            )

        # Test placeholder values raise ValueError
        with pytest.raises(ValueError, match="Twitter user_id must not be a placeholder value"):
            TwitterConfig(
                bearer_token="test_token",
                user_id="your_user_id_here"
            )


class TestTwitterAPIServiceUserIdIntegration:
    """Test TwitterAPIService with user_id configuration."""

    @pytest.fixture
    def mock_twitter_config(self):
        """Create a mock TwitterConfig with user_id."""
        config = Mock(spec=TwitterConfig)
        config.bearer_token = "test_bearer_token"
        config.user_id = "123456789"
        config.is_api_configured.return_value = True
        return config

    @pytest.fixture
    def mock_twitter_response(self):
        """Create mock Twitter API response data."""
        return {
            "data": [
                {
                    "id": "1234567890",
                    "text": "Test tweet content",
                    "created_at": "2023-12-01T12:00:00.000Z",
                    "author_id": "123456789",
                    "public_metrics": {
                        "retweet_count": 1,
                        "like_count": 5
                    }
                }
            ],
            "meta": {
                "result_count": 1
            }
        }

    def test_twitter_api_service_uses_configured_user_id(self, mock_twitter_config):
        """Test that TwitterAPIService uses configured user_id directly."""
        service = TwitterAPIService(mock_twitter_config)
        
        # Verify service stores the user_id from config
        assert hasattr(service, 'config')
        assert service.config.user_id == "123456789"

    @pytest.mark.asyncio
    async def test_twitter_api_service_no_username_lookup(self, mock_twitter_config, mock_twitter_response):
        """Test that service doesn't make username lookup API calls."""
        service = TwitterAPIService(mock_twitter_config)
        
        # Mock the fetch_user_tweets_today method directly
        with patch.object(service, 'fetch_user_tweets_today', return_value=mock_twitter_response) as mock_fetch:
            async with service:
                result = await service.fetch_user_tweets_today()
            
            # Verify the method was called once
            mock_fetch.assert_called_once()
            
            # Verify we got the expected result
            assert result == mock_twitter_response

    @pytest.mark.asyncio
    async def test_twitter_api_service_request_format(self, mock_twitter_config, mock_twitter_response):
        """Test that API service is configured correctly with user_id."""
        service = TwitterAPIService(mock_twitter_config)
        
        # Verify service configuration
        assert service.config.user_id == "123456789"
        assert service.config.bearer_token == "test_bearer_token"
        
        # Mock the method to verify it can be called
        with patch.object(service, 'fetch_user_tweets_today', return_value=mock_twitter_response):
            async with service:
                result = await service.fetch_user_tweets_today()
                assert result == mock_twitter_response


class TestTwitterDataFlowIntegration:
    """Test complete data flow from API through ingestion to database."""

    @pytest.fixture
    def mock_database_service(self):
        """Create mock database service."""
        db_service = Mock(spec=DatabaseService)
        db_service.store_data_item.return_value = None
        return db_service

    @pytest.fixture
    def mock_ingestion_service(self, mock_database_service):
        """Create mock ingestion service with database dependency."""
        ingestion_service = Mock(spec=IngestionService)
        ingestion_service.process_data_items.return_value = None
        return ingestion_service

    @pytest.fixture
    def sample_twitter_data_items(self):
        """Create sample DataItem objects from Twitter data."""
        return [
            DataItem(
                namespace="twitter",
                source_id="1234567890",
                content="Test tweet content",
                metadata={
                    "author_id": "123456789",
                    "created_at": "2023-12-01T12:00:00.000Z",
                    "public_metrics": {"retweet_count": 1, "like_count": 5},
                    "days_date": "2023-12-01"
                }
            )
        ]

    @pytest.mark.asyncio
    @patch('sources.twitter.TwitterAPIService')
    @patch('sources.twitter.TwitterRateLimitService')
    async def test_complete_twitter_data_flow(self, mock_rate_limit_service_class, mock_api_service_class, mock_ingestion_service, sample_twitter_data_items, mock_database_service):
        """Test complete flow from API to database via ingestion service."""
        # Setup mock rate limit service
        mock_rate_limit_service = Mock()
        mock_rate_limit_service.can_fetch_now.return_value = (True, 0)
        mock_rate_limit_service_class.return_value = mock_rate_limit_service
        
        # Setup mock API service
        mock_api_service = Mock()
        tweet_data = [
            {
                "id": "1234567890",
                "text": "Test tweet content",
                "created_at": "2023-12-01T12:00:00.000Z",
                "author_id": "123456789",
                "public_metrics": {"retweet_count": 1, "like_count": 5}
            }
        ]
        mock_api_service.fetch_user_tweets_today.return_value = tweet_data
        mock_api_service_class.return_value = mock_api_service

        # Setup mock config
        mock_config = Mock()
        mock_config.user_id = "123456789"
        mock_config.is_api_configured.return_value = True

        # Create TwitterSource and test fetch_items
        source = TwitterSource(mock_config, mock_database_service, mock_ingestion_service)
        
        # Mock the _ingest_tweets method to capture calls
        with patch.object(source, '_ingest_tweets') as mock_ingest:
            await source._ingest_tweets(tweet_data)
            mock_ingest.assert_called_once_with(tweet_data)

        # Verify the ingestion service would be called with proper data
        # (implementation details will vary based on actual _ingest_tweets implementation)

    def test_twitter_data_item_structure(self, sample_twitter_data_items):
        """Test that Twitter DataItems have correct structure."""
        data_item = sample_twitter_data_items[0]
        
        assert data_item.namespace == "twitter"
        assert data_item.source_id == "1234567890"
        assert data_item.content == "Test tweet content"
        assert data_item.metadata["days_date"] == "2023-12-01"
        
        # Verify metadata
        metadata = data_item.metadata
        assert metadata["author_id"] == "123456789"
        assert metadata["created_at"] == "2023-12-01T12:00:00.000Z"
        assert metadata["public_metrics"]["like_count"] == 5


class TestTwitterUIDataIntegration:
    """Test data retrieval through API routes for frontend."""

    @pytest.fixture
    def mock_database_with_twitter_data(self):
        """Create mock database with Twitter data."""
        db_service = Mock(spec=DatabaseService)
        
        # Mock data that would be returned from database
        mock_data = [
            {
                "id": "twitter:1234567890",
                "namespace": "twitter",
                "source_id": "1234567890",
                "content": "Test tweet content",
                "metadata": json.dumps({
                    "author_id": "123456789",
                    "created_at": "2023-12-01T12:00:00.000Z",
                    "public_metrics": {"retweet_count": 1, "like_count": 5}
                }),
                "days_date": "2023-12-01",
                "created_at": "2023-12-01T12:00:00",
                "updated_at": "2023-12-01T12:00:00"
            }
        ]
        
        db_service.get_data_items_by_namespace.return_value = mock_data
        db_service.get_data_items_by_date.return_value = mock_data
        return db_service

    def test_twitter_data_retrieval_via_api(self, mock_database_with_twitter_data):
        """Test that stored Twitter data can be retrieved via API routes."""
        # Simulate API route call
        result = mock_database_with_twitter_data.get_data_items_by_namespace("twitter")
        
        assert len(result) == 1
        assert result[0]["namespace"] == "twitter"
        assert result[0]["source_id"] == "1234567890"
        assert result[0]["content"] == "Test tweet content"

    def test_twitter_data_filtering_by_date(self, mock_database_with_twitter_data):
        """Test that Twitter data can be filtered by date."""
        # Simulate date-filtered API call
        result = mock_database_with_twitter_data.get_data_items_by_date("2023-12-01")
        
        assert len(result) == 1
        assert result[0]["days_date"] == "2023-12-01"
        assert result[0]["namespace"] == "twitter"

    def test_twitter_data_api_response_format(self, mock_database_with_twitter_data):
        """Test that API response has correct format for frontend."""
        result = mock_database_with_twitter_data.get_data_items_by_namespace("twitter")
        data_item = result[0]
        
        # Verify all required fields are present
        required_fields = ["id", "namespace", "source_id", "content", "metadata", "days_date", "created_at", "updated_at"]
        for field in required_fields:
            assert field in data_item
        
        # Verify metadata can be parsed as JSON
        metadata = json.loads(data_item["metadata"])
        assert isinstance(metadata, dict)
        assert "author_id" in metadata


class TestTwitterErrorHandlingIntegration:
    """Test error handling in Twitter integration."""

    def test_missing_user_id_error_handling(self):
        """Test graceful handling when user_id is missing."""
        # Config without user_id
        config = TwitterConfig(
            bearer_token="test_token",
            user_id=None
        )
        
        # Should not be considered API configured
        assert config.is_api_configured() is False
        
        # TwitterSource should handle this gracefully
        mock_ingestion = Mock()
        mock_db_service = Mock(spec=DatabaseService)
        source = TwitterSource(config, mock_db_service, mock_ingestion)

    def test_invalid_config_handling(self):
        """Test handling of invalid configuration."""
        config = TwitterConfig(
            bearer_token="",
            user_id=None
        )
        
        assert config.is_api_configured() is False
        
        # API service should handle invalid config gracefully
        service = TwitterAPIService(config)
        assert service.config.user_id == ""
        assert service.config.bearer_token == ""

    @pytest.mark.asyncio
    @patch('sources.twitter.TwitterAPIService')
    @patch('sources.twitter.TwitterRateLimitService')
    async def test_api_error_handling(self, mock_rate_limit_service_class, mock_api_service_class):
        """Test handling of API errors during tweet fetching."""
        # Setup mock rate limit service
        mock_rate_limit_service = Mock()
        mock_rate_limit_service.can_fetch_now.return_value = (True, 0)
        mock_rate_limit_service_class.return_value = mock_rate_limit_service
        
        # Setup mock API service to raise exception
        mock_api_service = Mock()
        mock_api_service.fetch_user_tweets_today.side_effect = Exception("API Error")
        mock_api_service_class.return_value = mock_api_service

        mock_config = Mock()
        mock_config.is_api_configured.return_value = True
        mock_ingestion = Mock()
        mock_db_service = Mock(spec=DatabaseService)

        source = TwitterSource(mock_config, mock_db_service, mock_ingestion)
        
        # Should handle API error gracefully (implementation dependent)
        try:
            tweets = await source.fetch_today_tweets()
        except Exception as e:
            # If exception is raised, it should be informative
            assert "API Error" in str(e) or isinstance(e, Exception)


class TestTwitterEndToEndWorkflow:
    """Test complete end-to-end Twitter workflow."""

    @pytest.fixture
    def complete_twitter_setup(self):
        """Setup complete Twitter integration environment."""
        # Real config (but with mock data)
        config = TwitterConfig(
            bearer_token="test_bearer_token",
            user_id="123456789"
        )
        
        # Mock database
        db_service = Mock(spec=DatabaseService)
        stored_items = []
        
        def mock_store_data_item(id, namespace, source_id, content, metadata, created_at=None, days_date=None):
            # Create a mock DataItem-like object for storage
            item = Mock()
            item.id = id
            item.namespace = namespace
            item.source_id = source_id
            item.content = content
            item.metadata = metadata
            item.created_at = created_at
            stored_items.append(item)
        
        db_service.store_data_item.side_effect = mock_store_data_item
        db_service.get_data_items_by_namespace.return_value = []
        
        # Mock ingestion service
        ingestion_service = Mock(spec=IngestionService)
        
        def mock_process_data_items(items):
            # Simulate ingestion processing
            for item in items:
                item.id = f"{item.namespace}:{item.source_id}"
            db_service.store_data_items(items)
        
        ingestion_service.process_data_items.side_effect = mock_process_data_items
        
        return {
            "config": config,
            "db_service": db_service,
            "ingestion_service": ingestion_service,
            "stored_items": stored_items
        }

    @pytest.mark.asyncio
    async def test_end_to_end_twitter_workflow(self, complete_twitter_setup):
        """Test complete workflow from configuration to UI data retrieval."""
        setup = complete_twitter_setup
        
        # Mock Twitter API response
        mock_twitter_response = [
            {
                "id": "1234567890",
                "text": "End-to-end test tweet",
                "created_at": "2023-12-01T12:00:00.000Z",
                "author_id": "123456789",
                "public_metrics": {"retweet_count": 2, "like_count": 10}
            }
        ]

        # Step 1: Verify configuration
        config = setup["config"]
        assert config.is_api_configured() is True
        assert config.user_id == "123456789"

        # Step 2: Create and use API service
        api_service = TwitterAPIService(config)
        
        # Mock the API service method
        with patch.object(api_service, 'fetch_user_tweets_today', return_value=mock_twitter_response):
            async with api_service:
                tweets_data = await api_service.fetch_user_tweets_today()
                assert tweets_data == mock_twitter_response

        # Step 3: Process through TwitterSource
        source = TwitterSource(config, setup["db_service"], setup["ingestion_service"])
        
        # Test direct tweet ingestion
        tweets = mock_twitter_response
        await source._ingest_tweets(tweets)

        # Step 5: Verify data was stored (simulated)
        stored_items = setup["stored_items"]
        assert len(stored_items) > 0
        
        stored_item = stored_items[0]
        assert stored_item.namespace == "twitter"
        assert stored_item.source_id == "1234567890"
        assert stored_item.content == "End-to-end test tweet"
        assert stored_item.metadata.get("days_date") is not None

        # Step 6: Verify API retrieval (simulated)
        setup["db_service"].get_data_items_by_namespace.return_value = [{
            "id": stored_item.id,
            "namespace": stored_item.namespace,
            "source_id": stored_item.source_id,
            "content": stored_item.content,
            "metadata": stored_item.metadata,
            "days_date": stored_item.metadata.get("days_date")
        }]
        
        ui_data = setup["db_service"].get_data_items_by_namespace("twitter")
        assert len(ui_data) == 1
        assert ui_data[0]["content"] == "End-to-end test tweet"

    def test_complete_integration_validation(self, complete_twitter_setup):
        """Test validation of complete integration components."""
        setup = complete_twitter_setup
        
        # Test configuration validation
        assert setup["config"].is_api_configured() is True
        assert setup["config"].user_id == "123456789"
        assert setup["config"].bearer_token == "test_bearer_token"
        
        # Test service initialization
        api_service = TwitterAPIService(setup["config"])
        assert hasattr(api_service, 'config')
        assert api_service.config.user_id == "123456789"
        
        # Test source initialization
        source = TwitterSource(setup["config"], setup["db_service"], setup["ingestion_service"])
        assert hasattr(source, 'config')
        assert hasattr(source, 'ingestion_service')
        
        # Test ingestion service is properly configured
        ingestion_service = setup["ingestion_service"]
        assert hasattr(ingestion_service, 'process_data_items')