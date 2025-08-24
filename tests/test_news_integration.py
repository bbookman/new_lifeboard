"""
Comprehensive integration tests for News source implementation
Tests headline fetching, API integration, and error resilience
"""

import pytest
import json
import httpx
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from sources.news import NewsSource
from sources.base import DataItem
from config.models import NewsConfig
from core.database import DatabaseService


class TestNewsIntegration:
    """Integration tests for News API source"""
    
    @pytest.fixture
    def news_config(self):
        """Test News configuration with realistic settings"""
        return NewsConfig(
            api_key="test_api_key_12345",
            language="en",
            enabled=True,
            country="US",
            unique_items_per_day=5,
            endpoint="real-time-news-data.p.rapidapi.com",
            items_to_retrieve=20,
            max_retries=3,
            retry_delay=0.1,
            rate_limit_max_delay=30.0,
            respect_retry_after=True,
            request_timeout=10.0,
            sync_interval_hours=24
        )
    
    @pytest.fixture
    def mock_db_service(self):
        """Mock database service for integration tests"""
        db_service = MagicMock(spec=DatabaseService)
        
        # Mock connection context manager
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"count": 0}  # No existing news
        mock_cursor.fetchall.return_value = []
        
        db_service.get_connection.return_value.__enter__.return_value = mock_conn
        db_service.get_connection.return_value.__exit__.return_value = None
        
        return db_service
    
    @pytest.fixture
    def sample_api_response(self):
        """Sample API response with diverse news articles"""
        return {
            "status": "OK",
            "request_id": "test_request_456",
            "data": [
                {
                    "title": "Breaking: Major Tech Company Announces AI Breakthrough",
                    "link": "https://tech-news.com/ai-breakthrough-2024",
                    "snippet": "Revolutionary artificial intelligence technology could transform how we work and live, company executives announced during quarterly earnings call.",
                    "thumbnail_url": "https://tech-news.com/images/ai-breakthrough.jpg",
                    "published_datetime_utc": "2024-01-15T09:30:00.000Z",
                    "source_url": "https://tech-news.com",
                    "source_logo_url": "https://tech-news.com/logo.png"
                },
                {
                    "title": "Global Climate Summit Reaches Historic Agreement",
                    "link": "https://world-news.com/climate-summit-agreement",
                    "snippet": "Representatives from 195 countries signed landmark climate accord aimed at reducing carbon emissions by 50% within the next decade.",
                    "thumbnail_url": "https://world-news.com/images/climate-summit.jpg",
                    "published_datetime_utc": "2024-01-15T11:45:00.000Z",
                    "source_url": "https://world-news.com",
                    "source_logo_url": "https://world-news.com/logo.png"
                },
                {
                    "title": "Stock Markets Rally Following Federal Reserve Decision",
                    "link": "https://finance-news.com/fed-decision-markets",
                    "snippet": "Major indices posted significant gains after central bank maintained current interest rates and signaled potential for future cuts.",
                    "thumbnail_url": "https://finance-news.com/images/market-rally.jpg",
                    "published_datetime_utc": "2024-01-15T14:20:00.000Z",
                    "source_url": "https://finance-news.com",
                    "source_logo_url": "https://finance-news.com/logo.png"
                },
                {
                    "title": "Space Mission Successfully Launches New Satellite",
                    "link": "https://space-news.com/satellite-launch-success",
                    "snippet": "Advanced communications satellite deployed successfully, enabling improved global internet connectivity for remote regions.",
                    "thumbnail_url": "https://space-news.com/images/satellite-launch.jpg",
                    "published_datetime_utc": "2024-01-15T16:10:00.000Z",
                    "source_url": "https://space-news.com",
                    "source_logo_url": "https://space-news.com/logo.png"
                },
                {
                    "title": "Medical Research Team Discovers Potential Cancer Treatment",
                    "link": "https://medical-news.com/cancer-treatment-discovery",
                    "snippet": "Breakthrough research shows promising results in early trials, offering new hope for patients with aggressive cancer types.",
                    "thumbnail_url": "https://medical-news.com/images/cancer-research.jpg",
                    "published_datetime_utc": "2024-01-15T17:30:00.000Z",
                    "source_url": "https://medical-news.com",
                    "source_logo_url": "https://medical-news.com/logo.png"
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_full_integration_flow(self, news_config, mock_db_service, sample_api_response):
        """Test complete integration flow from API call to DataItem generation"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock successful API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items(limit=5):
                items.append(item)
            
            # Verify we got the expected number of items
            assert len(items) == 5
            
            # Verify each item is properly structured
            for item in items:
                assert isinstance(item, DataItem)
                assert item.namespace == "news"
                assert item.source_id is not None
                assert item.content is not None
                assert item.metadata is not None
                assert item.created_at is not None
                assert item.updated_at is not None
            
            # Verify API call was made with correct parameters
            mock_client.get.assert_called_once_with("/top-headlines", params={
                "limit": "20",  # items_to_retrieve
                "country": "US",
                "lang": "en"
            })
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, mock_db_service):
        """Test source configuration validation"""
        # Test with missing API key
        invalid_config = NewsConfig(
            api_key="",
            language="en",
            enabled=True,
            endpoint="real-time-news-data.p.rapidapi.com"
        )
        
        source = NewsSource(invalid_config, mock_db_service)
        assert not source.is_configured()
        
        # Test with missing endpoint
        invalid_config2 = NewsConfig(
            api_key="test_key",
            language="en",
            enabled=True,
            endpoint=""
        )
        
        source2 = NewsSource(invalid_config2, mock_db_service)
        assert not source2.is_configured()
        
        # Test with placeholder endpoint
        invalid_config3 = NewsConfig(
            api_key="test_key",
            language="en",
            enabled=True,
            endpoint="example.com"  # This is a placeholder and should be invalid
        )
        
        source3 = NewsSource(invalid_config3, mock_db_service)
        assert not source3.is_configured()
        
        # Test with valid configuration
        valid_config = NewsConfig(
            api_key="test_key_valid",
            language="en",
            enabled=True,
            endpoint="real-time-news-data.p.rapidapi.com"
        )
        
        source4 = NewsSource(valid_config, mock_db_service)
        assert source4.is_configured()
    
    @pytest.mark.asyncio
    async def test_client_configuration(self, news_config, mock_db_service):
        """Test HTTP client configuration and headers"""
        source = NewsSource(news_config, mock_db_service)
        client_config = source._create_client_config()
        
        assert client_config["base_url"] == "https://real-time-news-data.p.rapidapi.com"
        assert client_config["headers"]["x-rapidapi-key"] == "test_api_key_12345"
        assert client_config["headers"]["x-rapidapi-host"] == "real-time-news-data.p.rapidapi.com"
        assert client_config["timeout"] == 10.0
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, news_config, mock_db_service):
        """Test successful connection validation"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock successful test response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "OK", "data": []}
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            result = await source.test_connection()
            
            assert result is True
            mock_client.get.assert_called_once_with("/top-headlines", params={
                "limit": "1",
                "country": "US",
                "lang": "en"
            })
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self, news_config, mock_db_service):
        """Test connection validation failure scenarios"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Test network error
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")
            
            source = NewsSource(news_config, mock_db_service)
            result = await source.test_connection()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_api_response_parsing(self, news_config, mock_db_service):
        """Test parsing of various API response formats"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Test with minimal response
            minimal_response = {
                "status": "OK",
                "data": [{
                    "title": "Simple News Title",
                    "link": "https://example.com/simple-news",
                    "snippet": "Simple news snippet",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T12:00:00.000Z"
                }]
            }
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = minimal_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items(limit=1):
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            assert "Simple News Title" in item.content
            assert item.metadata["title"] == "Simple News Title"
            assert item.metadata["link"] == "https://example.com/simple-news"
            assert item.metadata["thumbnail_url"] is None
    
    @pytest.mark.asyncio
    async def test_empty_api_response_handling(self, news_config, mock_db_service):
        """Test handling of empty API responses"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Test empty data array
            empty_response = {"status": "OK", "data": []}
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = empty_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items(limit=5):
                items.append(item)
            
            assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_article_transformation_edge_cases(self, news_config, mock_db_service):
        """Test article transformation with edge cases"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Test articles with various edge cases
            edge_case_response = {
                "status": "OK",
                "data": [
                    {
                        "title": "",  # Empty title
                        "link": "https://example.com/empty-title",
                        "snippet": "Article with empty title",
                        "thumbnail_url": "",
                        "published_datetime_utc": "2024-01-15T12:00:00.000Z"
                    },
                    {
                        "title": "Valid Article",
                        "link": "",  # Empty link
                        "snippet": "Article with empty link",
                        "thumbnail_url": "https://example.com/image.jpg",
                        "published_datetime_utc": "2024-01-15T12:00:00.000Z"
                    },
                    {
                        "title": "Valid Article with Invalid Date",
                        "link": "https://example.com/invalid-date",
                        "snippet": "Article with invalid date",
                        "thumbnail_url": "https://example.com/image.jpg",
                        "published_datetime_utc": "invalid-date-format"
                    },
                    {
                        "title": "Valid Article",
                        "link": "https://example.com/valid",
                        "snippet": "Completely valid article",
                        "thumbnail_url": "https://example.com/image.jpg",
                        "published_datetime_utc": "2024-01-15T12:00:00.000Z"
                    }
                ]
            }
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = edge_case_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            # Override the unique_items_per_day to ensure we don't limit selection
            source.config.unique_items_per_day = 10
            
            async for item in source.fetch_items(limit=10):
                items.append(item)
            
            # Should only get the valid articles (title and link required)
            # There should be 2 valid articles: "Valid Article with Invalid Date" and "Valid Article"
            assert len(items) == 2
            
            # Verify the valid articles were processed
            contents = [item.content for item in items]
            assert any("Valid Article with Invalid Date" in content for content in contents)
            assert any("Completely valid article" in content for content in contents)
    
    @pytest.mark.asyncio
    async def test_metadata_preservation(self, news_config, mock_db_service, sample_api_response):
        """Test that all metadata is properly preserved"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            # Set unique_items_per_day to 1 to ensure we only get one item
            source.config.unique_items_per_day = 1
            
            async for item in source.fetch_items():
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            metadata = item.metadata
            
            # Verify all expected metadata fields are present
            assert metadata["title"] == "Breaking: Major Tech Company Announces AI Breakthrough"
            assert metadata["link"] == "https://tech-news.com/ai-breakthrough-2024"
            assert metadata["snippet"] == "Revolutionary artificial intelligence technology could transform how we work and live, company executives announced during quarterly earnings call."
            assert metadata["thumbnail_url"] == "https://tech-news.com/images/ai-breakthrough.jpg"
            assert metadata["published_datetime_utc"] == "2024-01-15T09:30:00.000Z"
            assert metadata["source_type"] == "news_api"
    
    @pytest.mark.asyncio
    async def test_content_combination(self, news_config, mock_db_service):
        """Test that title and snippet are properly combined in content"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            test_response = {
                "status": "OK",
                "data": [{
                    "title": "Test Article Title",
                    "link": "https://example.com/test",
                    "snippet": "This is the article snippet providing more context.",
                    "thumbnail_url": "https://example.com/image.jpg",
                    "published_datetime_utc": "2024-01-15T12:00:00.000Z"
                }]
            }
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = test_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items(limit=1):
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            
            # Content should contain both title and snippet
            assert "Test Article Title" in item.content
            assert "This is the article snippet providing more context." in item.content
            # They should be separated by double newlines
            assert "Test Article Title\n\nThis is the article snippet providing more context." == item.content
    
    @pytest.mark.asyncio
    async def test_source_id_generation(self, news_config, mock_db_service):
        """Test that source IDs are generated consistently from URLs"""
        source = NewsSource(news_config, mock_db_service)
        
        # Test same URL generates same source_id
        article1 = {
            "title": "Test Article 1",
            "link": "https://example.com/test-article",
            "snippet": "Test snippet 1",
            "thumbnail_url": None,
            "published_datetime_utc": "2024-01-15T12:00:00.000Z"
        }
        
        article2 = {
            "title": "Test Article 2",  # Different title
            "link": "https://example.com/test-article",  # Same URL
            "snippet": "Test snippet 2",  # Different snippet
            "thumbnail_url": None,
            "published_datetime_utc": "2024-01-15T13:00:00.000Z"  # Different time
        }
        
        item1 = source._transform_article(article1)
        item2 = source._transform_article(article2)
        
        # Same URL should generate same source_id
        assert item1.source_id == item2.source_id
        
        # Different URLs should generate different source_ids
        article3 = {
            "title": "Test Article 3",
            "link": "https://example.com/different-article",
            "snippet": "Test snippet 3",
            "thumbnail_url": None,
            "published_datetime_utc": "2024-01-15T12:00:00.000Z"
        }
        
        item3 = source._transform_article(article3)
        assert item1.source_id != item3.source_id
    
    @pytest.mark.asyncio
    async def test_sync_metadata_generation(self, news_config, mock_db_service):
        """Test sync metadata generation for monitoring"""
        source = NewsSource(news_config, mock_db_service)
        metadata = await source.get_sync_metadata()
        
        assert metadata["source_type"] == "news_api"
        assert metadata["namespace"] == "news"
        assert metadata["is_configured"] is True
        assert metadata["api_endpoint"] == "real-time-news-data.p.rapidapi.com"
        assert metadata["country"] == "US"
        assert metadata["language"] == "en"
        assert metadata["unique_items_per_day"] == 5
        assert metadata["items_to_retrieve"] == 20
        assert "last_sync" in metadata
        
        # Verify last_sync is valid ISO timestamp
        datetime.fromisoformat(metadata["last_sync"])
    
    @pytest.mark.asyncio
    async def test_rate_limiting_respected(self, news_config, mock_db_service):
        """Test that rate limiting parameters are properly configured"""
        source = NewsSource(news_config, mock_db_service)
        
        # Verify rate limiting configuration
        assert source.config.rate_limit_max_delay == 30.0
        assert source.config.respect_retry_after is True
        assert source.config.max_retries == 3
    
    @pytest.mark.asyncio
    async def test_existing_data_check(self, news_config):
        """Test that source checks for existing data before API calls"""
        # Mock database service that returns existing news
        mock_db_service = MagicMock(spec=DatabaseService)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"count": 3}  # Existing news found
        
        mock_db_service.get_connection.return_value.__enter__.return_value = mock_conn
        mock_db_service.get_connection.return_value.__exit__.return_value = None
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items(limit=5):
                items.append(item)
            
            # Should not make API call if data exists
            assert len(items) == 0
            mock_client.get.assert_not_called()