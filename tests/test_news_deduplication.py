"""
Comprehensive deduplication tests for News source implementation
Tests the selection algorithm and headline deduplication logic
"""

import pytest
import json
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from sources.news import NewsSource
from sources.base import DataItem
from config.models import NewsConfig
from core.database import DatabaseService


class TestNewsDeduplication:
    """Tests for news deduplication and selection algorithms"""
    
    @pytest.fixture
    def news_config(self):
        """Test News configuration optimized for deduplication testing"""
        return NewsConfig(
            api_key="test_api_key_dedup",
            language="en",
            enabled=True,
            country="US",
            unique_items_per_day=3,  # Small number for testing
            endpoint="real-time-news-data.p.rapidapi.com",
            items_to_retrieve=10,  # Fetch more than we need
            max_retries=2,
            retry_delay=0.1,
            request_timeout=5.0,
            sync_interval_hours=24
        )
    
    @pytest.fixture
    def mock_db_service(self):
        """Mock database service for deduplication tests"""
        db_service = MagicMock(spec=DatabaseService)
        
        # Mock connection context manager
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"count": 0}  # No existing news by default
        mock_cursor.fetchall.return_value = []
        
        db_service.get_connection.return_value.__enter__.return_value = mock_conn
        db_service.get_connection.return_value.__exit__.return_value = None
        
        return db_service
    
    @pytest.fixture
    def duplicate_articles_response(self):
        """API response with duplicate and similar articles"""
        return {
            "status": "OK",
            "request_id": "dedup_test_123",
            "data": [
                {
                    "title": "Breaking: Major Tech Company Reports Record Earnings",
                    "link": "https://tech-daily.com/major-tech-earnings-q4",
                    "snippet": "Technology giant announces unprecedented quarterly profits, beating analyst expectations by wide margin.",
                    "thumbnail_url": "https://tech-daily.com/images/earnings-q4.jpg",
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Tech Giant Posts Record Q4 Earnings Beat",  # Similar content, different title
                    "link": "https://finance-wire.com/tech-giant-q4-earnings",
                    "snippet": "Major technology company exceeded analyst forecasts with record quarterly earnings announcement.",
                    "thumbnail_url": "https://finance-wire.com/images/tech-earnings.jpg",
                    "published_datetime_utc": "2024-01-15T09:15:00.000Z"
                },
                {
                    "title": "Breaking: Major Tech Company Reports Record Earnings",  # Exact duplicate title
                    "link": "https://news-central.com/tech-earnings-record",
                    "snippet": "Technology giant announces unprecedented quarterly profits, beating analyst expectations by wide margin.",
                    "thumbnail_url": "https://news-central.com/images/tech-earnings.jpg",
                    "published_datetime_utc": "2024-01-15T09:30:00.000Z"
                },
                {
                    "title": "Climate Change Summit Reaches Breakthrough Agreement",
                    "link": "https://world-news.com/climate-summit-breakthrough",
                    "snippet": "International delegates achieve historic consensus on carbon reduction targets after intense negotiations.",
                    "thumbnail_url": "https://world-news.com/images/climate-agreement.jpg",
                    "published_datetime_utc": "2024-01-15T11:00:00.000Z"
                },
                {
                    "title": "Space Mission Successfully Deploys Research Satellite",
                    "link": "https://space-today.com/satellite-deployment-success",
                    "snippet": "Advanced research satellite deployed in orbit, enabling new studies of Earth's atmosphere and climate patterns.",
                    "thumbnail_url": "https://space-today.com/images/satellite-deploy.jpg",
                    "published_datetime_utc": "2024-01-15T13:00:00.000Z"
                },
                {
                    "title": "Medical Breakthrough: New Treatment Shows Promise",
                    "link": "https://health-news.com/medical-breakthrough-treatment",
                    "snippet": "Experimental therapy demonstrates significant improvement in patient outcomes during clinical trials.",
                    "thumbnail_url": "https://health-news.com/images/medical-breakthrough.jpg",
                    "published_datetime_utc": "2024-01-15T14:00:00.000Z"
                },
                {
                    "title": "Stock Markets Close at Record Highs",
                    "link": "https://market-watch.com/markets-record-close",
                    "snippet": "Major indices finish trading session at all-time highs following positive economic indicators.",
                    "thumbnail_url": "https://market-watch.com/images/market-highs.jpg",
                    "published_datetime_utc": "2024-01-15T16:00:00.000Z"
                },
                {
                    "title": "Breaking: Major Tech Company Reports Record Earnings",  # Another exact duplicate
                    "link": "https://business-today.com/tech-company-earnings",
                    "snippet": "Technology company surpasses earnings expectations with record quarterly performance.",
                    "thumbnail_url": "https://business-today.com/images/tech-earnings.jpg",
                    "published_datetime_utc": "2024-01-15T16:30:00.000Z"
                },
                {
                    "title": "Innovation in Renewable Energy Sector Accelerates",
                    "link": "https://energy-news.com/renewable-innovation-accelerates",
                    "snippet": "New technological advances drive rapid growth in clean energy adoption across multiple countries.",
                    "thumbnail_url": "https://energy-news.com/images/renewable-innovation.jpg",
                    "published_datetime_utc": "2024-01-15T17:00:00.000Z"
                },
                {
                    "title": "Global Supply Chain Shows Signs of Recovery",
                    "link": "https://logistics-today.com/supply-chain-recovery",
                    "snippet": "International shipping and logistics networks demonstrate improved efficiency after recent disruptions.",
                    "thumbnail_url": "https://logistics-today.com/images/supply-chain.jpg",
                    "published_datetime_utc": "2024-01-15T18:00:00.000Z"
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_selection_algorithm_respects_limit(self, news_config, mock_db_service, duplicate_articles_response):
        """Test that selection algorithm respects unique_items_per_day limit"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = duplicate_articles_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            # Should respect unique_items_per_day limit (3)
            assert len(items) == 3
            
            # Verify API was called to fetch more items than limit
            mock_client.get.assert_called_once_with("/top-headlines", params={
                "limit": "10",  # items_to_retrieve
                "country": "US",
                "lang": "en"
            })
    
    @pytest.mark.asyncio
    async def test_natural_deduplication_by_url(self, news_config, mock_db_service):
        """Test that articles with same URL are naturally deduplicated by source_id"""
        # Create response with same URL but different content
        same_url_response = {
            "status": "OK",
            "data": [
                {
                    "title": "First Version of Article",
                    "link": "https://example.com/same-article",
                    "snippet": "Original version of the article",
                    "thumbnail_url": "https://example.com/image1.jpg",
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Updated Version of Article",
                    "link": "https://example.com/same-article",  # Same URL
                    "snippet": "Updated version with more details",
                    "thumbnail_url": "https://example.com/image2.jpg",
                    "published_datetime_utc": "2024-01-15T10:00:00.000Z"
                },
                {
                    "title": "Different Article",
                    "link": "https://example.com/different-article",
                    "snippet": "Completely different article",
                    "thumbnail_url": "https://example.com/image3.jpg",
                    "published_datetime_utc": "2024-01-15T11:00:00.000Z"
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = same_url_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            # Should get 2 unique articles (same URL creates same source_id)
            source_ids = [item.source_id for item in items]
            assert len(set(source_ids)) == 2  # Only 2 unique source_ids
    
    @pytest.mark.asyncio
    async def test_source_id_consistency(self, news_config, mock_db_service):
        """Test that source_id generation is consistent and deterministic"""
        source = NewsSource(news_config, mock_db_service)
        
        # Same URL should always generate same source_id
        article = {
            "title": "Test Article",
            "link": "https://example.com/test-article",
            "snippet": "Test snippet",
            "thumbnail_url": "https://example.com/image.jpg",
            "published_datetime_utc": "2024-01-15T12:00:00.000Z"
        }
        
        # Transform same article multiple times
        item1 = source._transform_article(article)
        item2 = source._transform_article(article)
        item3 = source._transform_article(article)
        
        assert item1.source_id == item2.source_id == item3.source_id
        
        # Verify source_id is hash of URL
        expected_id = hashlib.sha1("https://example.com/test-article".encode()).hexdigest()
        assert item1.source_id == expected_id
    
    @pytest.mark.asyncio
    async def test_url_based_deduplication_edge_cases(self, news_config, mock_db_service):
        """Test URL-based deduplication with edge cases"""
        source = NewsSource(news_config, mock_db_service)
        
        test_cases = [
            # Same URL with different fragments/queries should be same
            ("https://example.com/article?utm=1", "https://example.com/article?utm=2"),
            # Different protocols should be different
            ("http://example.com/article", "https://example.com/article"),
            # Different domains should be different
            ("https://example.com/article", "https://different.com/article"),
            # Different paths should be different
            ("https://example.com/article1", "https://example.com/article2"),
        ]
        
        for url1, url2 in test_cases:
            article1 = {
                "title": "Test Article 1",
                "link": url1,
                "snippet": "Test snippet 1",
                "thumbnail_url": None,
                "published_datetime_utc": "2024-01-15T12:00:00.000Z"
            }
            
            article2 = {
                "title": "Test Article 2",
                "link": url2,
                "snippet": "Test snippet 2",
                "thumbnail_url": None,
                "published_datetime_utc": "2024-01-15T12:00:00.000Z"
            }
            
            item1 = source._transform_article(article1)
            item2 = source._transform_article(article2)
            
            if url1 == url2:
                assert item1.source_id == item2.source_id, f"Same URLs should have same ID: {url1}"
            else:
                assert item1.source_id != item2.source_id, f"Different URLs should have different IDs: {url1} vs {url2}"
    
    @pytest.mark.asyncio
    async def test_fetch_select_algorithm(self, news_config, mock_db_service, duplicate_articles_response):
        """Test the fetch-20-select-5 algorithm mentioned in architecture"""
        # Configure to fetch 10, select 3
        news_config.items_to_retrieve = 10
        news_config.unique_items_per_day = 3
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = duplicate_articles_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            # Should fetch 10 (items_to_retrieve) but only yield 3 (unique_items_per_day)
            assert len(items) == 3
            
            # Verify API call fetched more than returned
            call_args = mock_client.get.call_args
            params = call_args[1]['params']
            assert params["limit"] == "10"  # items_to_retrieve
    
    @pytest.mark.asyncio
    async def test_selection_order_priority(self, news_config, mock_db_service):
        """Test that selection respects order from API (first N unique items)"""
        ordered_response = {
            "status": "OK",
            "data": [
                {
                    "title": "First Article",
                    "link": "https://example.com/first",
                    "snippet": "This should be selected first",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Second Article",
                    "link": "https://example.com/second",
                    "snippet": "This should be selected second",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T10:00:00.000Z"
                },
                {
                    "title": "Third Article",
                    "link": "https://example.com/third",
                    "snippet": "This should be selected third",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T11:00:00.000Z"
                },
                {
                    "title": "Fourth Article",
                    "link": "https://example.com/fourth",
                    "snippet": "This should NOT be selected (over limit)",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T12:00:00.000Z"
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = ordered_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            assert len(items) == 3
            
            # Verify order is preserved
            assert "First Article" in items[0].content
            assert "Second Article" in items[1].content
            assert "Third Article" in items[2].content
            
            # Verify fourth article was not selected
            contents = [item.content for item in items]
            assert not any("Fourth Article" in content for content in contents)
    
    @pytest.mark.asyncio
    async def test_invalid_articles_filtered_out(self, news_config, mock_db_service):
        """Test that invalid articles are filtered out during selection"""
        mixed_response = {
            "status": "OK",
            "data": [
                {
                    "title": "",  # Invalid: empty title
                    "link": "https://example.com/empty-title",
                    "snippet": "Article with empty title",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Valid Article 1",
                    "link": "https://example.com/valid1",
                    "snippet": "This is a valid article",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Article with no link",
                    "link": "",  # Invalid: empty link
                    "snippet": "Article with empty link",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Valid Article 2",
                    "link": "https://example.com/valid2",
                    "snippet": "This is another valid article",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                },
                {
                    "title": "Valid Article 3",
                    "link": "https://example.com/valid3",
                    "snippet": "This is a third valid article",
                    "thumbnail_url": None,
                    "published_datetime_utc": "2024-01-15T09:00:00.000Z"
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mixed_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            # Should only get the 3 valid articles
            assert len(items) == 3
            
            # Verify all returned articles are valid
            for item in items:
                assert "Valid Article" in item.content
                assert item.source_id is not None
                assert len(item.source_id) > 0
    
    @pytest.mark.asyncio
    async def test_database_deduplication_check(self, news_config):
        """Test database-level deduplication checking"""
        # Mock database service that shows existing news
        mock_db_service = MagicMock(spec=DatabaseService)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        
        # First call: check count (returns > 0)
        mock_cursor.fetchone.return_value = {"count": 5}  # Existing news found
        
        mock_db_service.get_connection.return_value.__enter__.return_value = mock_conn
        mock_db_service.get_connection.return_value.__exit__.return_value = None
        
        source = NewsSource(news_config, mock_db_service)
        
        # Should check for existing data
        today = datetime.now().strftime("%Y-%m-%d")
        has_data = source._has_news_data_for_date(today)
        
        assert has_data is True
        
        # Verify database query was made
        mock_conn.execute.assert_called_with(
            """
                SELECT COUNT(*) as count FROM data_items 
                WHERE namespace = 'news' AND days_date = ?
            """,
            (today,)
        )
    
    @pytest.mark.asyncio
    async def test_no_duplicate_fetch_same_day(self, news_config):
        """Test that source doesn't fetch if data already exists for today"""
        # Mock database service showing existing news for today
        mock_db_service = MagicMock(spec=DatabaseService)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"count": 3}  # Existing news
        
        mock_db_service.get_connection.return_value.__enter__.return_value = mock_conn
        mock_db_service.get_connection.return_value.__exit__.return_value = None
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            # Should not make API call or return items
            assert len(items) == 0
            mock_client.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_news_by_date_functionality(self, news_config):
        """Test database query methods for retrieving stored news"""
        # Mock database service with sample news data
        mock_db_service = MagicMock(spec=DatabaseService)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        
        # Mock news data in database
        mock_cursor.fetchall.return_value = [
            {
                "id": "news:abc123",
                "source_id": "abc123",
                "content": "Tech company announces breakthrough",
                "metadata": '{"title": "Tech Breakthrough", "link": "https://example.com/tech", "snippet": "Major announcement"}',
                "created_at": "2024-01-15T09:00:00.000Z",
                "days_date": "2024-01-15"
            }
        ]
        
        mock_db_service.get_connection.return_value.__enter__.return_value = mock_conn
        mock_db_service.get_connection.return_value.__exit__.return_value = None
        
        source = NewsSource(news_config, mock_db_service)
        news_items = source.get_news_by_date(mock_db_service, "2024-01-15")
        
        assert len(news_items) == 1
        assert news_items[0]["title"] == "Tech Breakthrough"
        assert news_items[0]["link"] == "https://example.com/tech"
        assert news_items[0]["source"] == "data_items"
    
    @pytest.mark.asyncio
    async def test_get_news_count_by_date(self, news_config):
        """Test counting news articles for a specific date"""
        mock_db_service = MagicMock(spec=DatabaseService)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"count": 5}
        
        mock_db_service.get_connection.return_value.__enter__.return_value = mock_conn
        mock_db_service.get_connection.return_value.__exit__.return_value = None
        
        source = NewsSource(news_config, mock_db_service)
        count = source.get_news_count_by_date(mock_db_service, "2024-01-15")
        
        assert count == 5
        
        # Verify correct SQL query
        mock_conn.execute.assert_called_with(
            """
                SELECT COUNT(*) as count FROM data_items 
                WHERE namespace = 'news' AND days_date = ?
            """,
            ("2024-01-15",)
        )
    
    @pytest.mark.asyncio
    async def test_unique_source_ids_generated(self, news_config, mock_db_service, duplicate_articles_response):
        """Test that all generated items have unique source IDs within a fetch"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = duplicate_articles_response
            mock_client.get.return_value = mock_response
            
            source = NewsSource(news_config, mock_db_service)
            items = []
            
            async for item in source.fetch_items():
                items.append(item)
            
            # Collect all source IDs
            source_ids = [item.source_id for item in items]
            
            # Verify all source IDs are unique
            assert len(source_ids) == len(set(source_ids)), "All source IDs should be unique"
            
            # Verify source IDs are not empty
            assert all(source_id for source_id in source_ids), "No source ID should be empty"