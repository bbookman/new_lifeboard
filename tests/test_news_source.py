"""
Tests for News API source implementation
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from config.models import NewsConfig
from sources.base import DataItem
from sources.news import NewsSource


@pytest.fixture
def news_config():
    """Test News configuration"""
    return NewsConfig(
        api_key="test_rapid_api_key",
        language="en",
        enabled=True,
        country="US",
        unique_items_per_day=5,
        endpoint="real-time-news-data.p.rapidapi.com",
        items_to_retrieve=20,
        max_retries=2,
        retry_delay=0.1,  # Fast retries for testing
        request_timeout=5.0,
        sync_interval_hours=24,
    )


@pytest.fixture
def sample_news_article():
    """Sample news article from RapidAPI"""
    return {
        "title": "Tech Stock Rally Continues as AI Investments Surge",
        "link": "https://example-news.com/tech-stock-rally-ai-investments",
        "snippet": "Major technology stocks experienced significant gains today as investors showed renewed confidence in artificial intelligence investments. The surge comes amid reports of breakthrough AI developments.",
        "photo_url": "https://example-news.com/images/tech-stocks-ai.jpg",
        "published_datetime_utc": "2024-01-15T14:30:00.000Z",
        "source_url": "https://example-news.com",
        "source_logo_url": "https://example-news.com/logo.png",
        "source_favicon_url": "https://example-news.com/favicon.ico",
    }


@pytest.fixture
def sample_api_response(sample_news_article):
    """Sample API response with news articles"""
    return {
        "status": "OK",
        "request_id": "test_request_123",
        "data": [sample_news_article],
    }


class TestNewsConfig:
    """Test News configuration"""

    def test_config_creation(self):
        """Test basic configuration creation"""
        config = NewsConfig(api_key="test_key")
        assert config.api_key == "test_key"
        assert config.language == "en"
        assert config.enabled is True
        assert config.country == "US"
        assert config.unique_items_per_day == 5
        assert config.endpoint == "real-time-news-data.p.rapidapi.com"
        assert config.items_to_retrieve == 20

    def test_config_customization(self):
        """Test configuration with custom values"""
        config = NewsConfig(
            api_key="custom_key",
            language="fr",
            enabled=False,
            country="FR",
            unique_items_per_day=10,
            endpoint="custom-news.api.com",
            items_to_retrieve=50,
            max_retries=5,
        )
        assert config.api_key == "custom_key"
        assert config.language == "fr"
        assert config.enabled is False
        assert config.country == "FR"
        assert config.unique_items_per_day == 10
        assert config.endpoint == "custom-news.api.com"
        assert config.items_to_retrieve == 50
        assert config.max_retries == 5


class TestNewsSource:
    """Test News source functionality"""

    @pytest.mark.asyncio
    async def test_source_initialization(self, news_config):
        """Test source initialization"""
        source = NewsSource(news_config)
        assert source.namespace == "news"
        assert source.config == news_config
        assert source.get_source_type() == "news_api"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, news_config):
        """Test successful connection test"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "OK", "data": []}
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            result = await source.test_connection()

            assert result is True
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert "/v1/news" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, news_config):
        """Test connection test failure"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock failed response
            mock_client.get.side_effect = httpx.RequestError("Connection failed")

            source = NewsSource(news_config)
            result = await source.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_client_creation(self, news_config):
        """Test HTTP client creation and headers"""
        source = NewsSource(news_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = source._get_client()

            mock_client_class.assert_called_once_with(
                base_url="https://real-time-news-data.p.rapidapi.com",
                headers={
                    "X-RapidAPI-Key": "test_rapid_api_key",
                    "X-RapidAPI-Host": "real-time-news-data.p.rapidapi.com",
                },
                timeout=5.0,
            )

    @pytest.mark.asyncio
    async def test_fetch_items_success(self, news_config, sample_api_response):
        """Test successful item fetching"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock successful API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            items = []

            async for item in source.fetch_items(limit=1):
                items.append(item)

            assert len(items) == 1
            item = items[0]

            # Verify DataItem structure
            assert isinstance(item, DataItem)
            assert item.namespace == "news"
            assert "tech-stock-rally-ai-investments" in item.source_id
            assert "Tech Stock Rally Continues" in item.content
            assert "artificial intelligence investments" in item.content

            # Verify metadata preservation
            assert "original_article" in item.metadata
            assert item.metadata["title"] == "Tech Stock Rally Continues as AI Investments Surge"
            assert item.metadata["link"] == "https://example-news.com/tech-stock-rally-ai-investments"
            assert item.metadata["thumbnail_url"] == "https://example-news.com/images/tech-stocks-ai.jpg"
            assert item.created_at is not None

    @pytest.mark.asyncio
    async def test_fetch_items_with_limit(self, news_config):
        """Test fetching items with limit"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock response with multiple articles
            articles = [
                {
                    "title": f"News Article {i}",
                    "link": f"https://example.com/article{i}",
                    "snippet": f"This is article {i}",
                    "photo_url": f"https://example.com/image{i}.jpg",
                    "published_datetime_utc": "2024-01-15T14:30:00.000Z",
                }
                for i in range(1, 4)
            ]
            api_response = {"status": "OK", "data": articles}

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            items = []

            async for item in source.fetch_items(limit=2):
                items.append(item)

            assert len(items) == 2
            assert "News Article 1" in items[0].content
            assert "News Article 2" in items[1].content

    @pytest.mark.asyncio
    async def test_fetch_items_with_since_parameter(self, news_config, sample_api_response):
        """Test fetching items with since datetime"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            since_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

            items = []
            async for item in source.fetch_items(since=since_time, limit=1):
                items.append(item)

            # Verify API call parameters
            call_args = mock_client.get.call_args
            params = call_args[1]["params"]
            assert params["lang"] == "en"
            assert params["country"] == "US"
            assert params["limit"] == 20

    @pytest.mark.asyncio
    async def test_get_item_success(self, news_config, sample_news_article):
        """Test getting specific item by ID"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock search response that finds the article
            api_response = {"status": "OK", "data": [sample_news_article]}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            item = await source.get_item("tech-stock-rally-ai-investments")

            assert item is not None
            assert "tech-stock-rally-ai-investments" in item.source_id
            assert item.metadata["title"] == "Tech Stock Rally Continues as AI Investments Surge"

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, news_config):
        """Test getting non-existent item"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock empty response
            api_response = {"status": "OK", "data": []}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            item = await source.get_item("nonexistent-article")

            assert item is None

    @pytest.mark.asyncio
    async def test_retry_logic_on_rate_limit(self, news_config, sample_api_response):
        """Test retry logic when rate limited"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # First call returns 429 (rate limited), second succeeds
            rate_limit_response = MagicMock()
            rate_limit_response.status_code = 429

            success_response = MagicMock()
            success_response.status_code = 200
            success_response.json.return_value = sample_api_response

            mock_client.get.side_effect = [rate_limit_response, success_response]

            source = NewsSource(news_config)

            with patch("asyncio.sleep") as mock_sleep:
                items = []
                async for item in source.fetch_items(limit=1):
                    items.append(item)

                # Should have retried once
                assert len(items) == 1
                assert mock_client.get.call_count == 2
                mock_sleep.assert_called_once()  # Should have slept before retry

    @pytest.mark.asyncio
    async def test_retry_logic_max_retries_exceeded(self, news_config):
        """Test retry logic when max retries exceeded"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Always return 429 (rate limited)
            rate_limit_response = MagicMock()
            rate_limit_response.status_code = 429
            mock_client.get.return_value = rate_limit_response

            source = NewsSource(news_config)

            with patch("asyncio.sleep") as mock_sleep:
                items = []
                async for item in source.fetch_items(limit=1):
                    items.append(item)

                # Should have stopped after max retries
                assert len(items) == 0
                assert mock_client.get.call_count == 3  # Initial + 2 retries
                assert mock_sleep.call_count == 2  # Sleep before each retry

    @pytest.mark.asyncio
    async def test_data_transformation_edge_cases(self, news_config):
        """Test data transformation with edge cases"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Article with minimal data
            minimal_article = {
                "title": "Minimal News",
                "link": "https://example.com/minimal",
                "snippet": "",
                "photo_url": None,
                "published_datetime_utc": None,
            }

            api_response = {"status": "OK", "data": [minimal_article]}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            items = []

            async for item in source.fetch_items(limit=1):
                items.append(item)

            assert len(items) == 1
            item = items[0]

            # Should handle empty content gracefully
            assert "minimal" in item.source_id
            assert "Minimal News" in item.content
            assert item.metadata["thumbnail_url"] is None
            assert item.created_at is None

    @pytest.mark.asyncio
    async def test_transform_article_url_extraction(self, news_config):
        """Test URL extraction from article link for source_id"""
        source = NewsSource(news_config)

        test_cases = [
            ("https://example.com/tech-stocks-rally", "tech-stocks-rally"),
            ("https://news.com/path/to/article-name", "article-name"),
            ("https://site.com/news/123/some-title", "some-title"),
            ("https://example.com/", ""),
            ("invalid-url", "invalid-url"),
        ]

        for url, expected in test_cases:
            article = {
                "title": "Test Article",
                "link": url,
                "snippet": "Test snippet",
                "photo_url": None,
                "published_datetime_utc": "2024-01-15T14:30:00.000Z",
            }

            data_item = source._transform_article(article)
            assert expected in data_item.source_id or data_item.source_id == expected

    @pytest.mark.asyncio
    async def test_datetime_parsing(self, news_config):
        """Test datetime parsing from various formats"""
        source = NewsSource(news_config)

        test_cases = [
            "2024-01-15T14:30:00.000Z",
            "2024-01-15T14:30:00Z",
            "2024-01-15 14:30:00",
            None,
            "invalid-date",
        ]

        for date_str in test_cases:
            article = {
                "title": "Test Article",
                "link": "https://example.com/test",
                "snippet": "Test snippet",
                "photo_url": None,
                "published_datetime_utc": date_str,
            }

            data_item = source._transform_article(article)

            if date_str and date_str.startswith("2024"):
                assert data_item.created_at is not None
                assert isinstance(data_item.created_at, datetime)
            else:
                assert data_item.created_at is None

    @pytest.mark.asyncio
    async def test_client_cleanup(self, news_config):
        """Test HTTP client cleanup"""
        source = NewsSource(news_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Get client (creates it)
            client = source._get_client()
            assert source.client is not None

            # Close should clean up
            await source.close()
            mock_client.aclose.assert_called_once()
            assert source.client is None

    @pytest.mark.asyncio
    async def test_context_manager(self, news_config):
        """Test using source as async context manager"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            async with NewsSource(news_config) as source:
                assert source is not None
                # Use source here
                client = source._get_client()

            # Should have closed automatically
            mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_metadata(self, news_config):
        """Test sync metadata generation"""
        source = NewsSource(news_config)
        metadata = await source.get_sync_metadata()

        assert metadata["source_type"] == "news_api"
        assert metadata["namespace"] == "news"
        assert metadata["api_endpoint"] == "real-time-news-data.p.rapidapi.com"
        assert metadata["language"] == "en"
        assert metadata["country"] == "US"
        assert "last_sync" in metadata

        # Verify last_sync is valid ISO timestamp
        datetime.fromisoformat(metadata["last_sync"])  # Should not raise

    @pytest.mark.asyncio
    async def test_api_error_handling(self, news_config):
        """Test handling of API errors"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock API error response
            error_response = MagicMock()
            error_response.status_code = 400
            error_response.json.return_value = {"status": "ERROR", "message": "Invalid parameters"}
            mock_client.get.return_value = error_response

            source = NewsSource(news_config)
            items = []

            async for item in source.fetch_items(limit=1):
                items.append(item)

            # Should handle error gracefully and return no items
            assert len(items) == 0

    @pytest.mark.asyncio
    async def test_http_timeout_handling(self, news_config):
        """Test handling of HTTP timeouts"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock timeout exception
            mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

            source = NewsSource(news_config)
            items = []

            async for item in source.fetch_items(limit=1):
                items.append(item)

            # Should handle timeout gracefully and return no items
            assert len(items) == 0

    @pytest.mark.asyncio
    async def test_malformed_json_handling(self, news_config):
        """Test handling of malformed JSON responses"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock response with invalid JSON
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_client.get.return_value = mock_response

            source = NewsSource(news_config)
            items = []

            async for item in source.fetch_items(limit=1):
                items.append(item)

            # Should handle JSON error gracefully and return no items
            assert len(items) == 0
