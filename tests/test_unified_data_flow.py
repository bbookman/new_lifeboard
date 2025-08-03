"""
Test suite for unified data flow architecture verification

This test suite verifies that the unified data architecture works correctly:
- All sources yield DataItem objects
- All data flows through the standard ingestion pipeline
- All data is stored in the data_items table with proper days_date
- Calendar can retrieve data from all sources
- Search can find data from all sources
"""

import pytest
import asyncio
import tempfile
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from services.ingestion import IngestionService
from sources.base import DataItem
from sources.limitless import LimitlessSource
from sources.weather import WeatherSource
from sources.news import NewsSource
from sources.twitter import TwitterSource
from config.factory import get_config


class TestUnifiedDataFlow:
    """Test unified data flow architecture"""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name

    @pytest.fixture
    def database_service(self, temp_db_path):
        """Create database service with temporary database"""
        return DatabaseService(temp_db_path)

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store service"""
        mock = Mock(spec=VectorStoreService)
        mock.add_vector = Mock(return_value=True)
        mock.get_stats = Mock(return_value={"total_vectors": 0})
        return mock

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service"""
        mock = Mock(spec=EmbeddingService)
        mock.embed_texts = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        return mock

    @pytest.fixture
    def ingestion_service(self, database_service, mock_vector_store, mock_embedding_service):
        """Create ingestion service with mocked dependencies"""
        config = get_config()
        return IngestionService(
            database=database_service,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=config
        )

    @pytest.fixture
    def sample_limitless_data(self):
        """Sample Limitless API response data"""
        return {
            "lifelogs": [
                {
                    "id": "limitless-123",
                    "title": "Morning Meeting",
                    "start_time": "2025-01-15T09:00:00Z",
                    "end_time": "2025-01-15T10:00:00Z",
                    "is_starred": False,
                    "updated_at": "2025-01-15T10:30:00Z",
                    "markdown": "# Morning Meeting\n\nDiscussed project timeline and deliverables.",
                    "processed_content": "Meeting about project timeline and deliverables"
                }
            ]
        }

    @pytest.fixture
    def sample_weather_data(self):
        """Sample Weather API response data"""
        return {
            "forecastDaily": {
                "readTime": "2025-01-15T08:00:00Z",
                "days": [
                    {
                        "forecastStart": "2025-01-15T00:00:00Z",
                        "conditionCode": "sunny",
                        "temperatureMax": 25.0,
                        "temperatureMin": 15.0,
                        "daytimeForecast": {"conditionCode": "sunny"}
                    },
                    {
                        "forecastStart": "2025-01-16T00:00:00Z",
                        "conditionCode": "cloudy",
                        "temperatureMax": 22.0,
                        "temperatureMin": 12.0,
                        "daytimeForecast": {"conditionCode": "cloudy"}
                    }
                ]
            }
        }

    @pytest.fixture
    def sample_news_data(self):
        """Sample News API response data"""
        return [
            {
                "title": "Tech Innovation Breakthrough",
                "link": "https://example.com/news1",
                "snippet": "Scientists develop new technology",
                "published_datetime_utc": "2025-01-15T14:00:00Z"
            },
            {
                "title": "Market Update Today",
                "link": "https://example.com/news2", 
                "snippet": "Stock markets show positive trends",
                "published_datetime_utc": "2025-01-15T15:00:00Z"
            }
        ]

    @pytest.fixture
    def sample_twitter_data(self):
        """Sample Twitter archive data"""
        return [
            {
                "tweet_id": "tweet-123",
                "created_at": "2025-01-15T12:00:00",
                "days_date": "2025-01-15",
                "text": "Excited about the new project launch!",
                "media_urls": "[]"
            }
        ]

    @pytest.mark.asyncio
    async def test_limitless_source_yields_data_items(self, ingestion_service, sample_limitless_data):
        """Test that Limitless source yields DataItem objects"""
        config = get_config()
        
        # Mock the API response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_limitless_data
            mock_get.return_value = mock_response
            
            # Create Limitless source
            limitless_source = LimitlessSource(config.limitless, ingestion_service.database)
            ingestion_service.register_source(limitless_source)
            
            # Test data item yielding
            data_items = []
            async for item in limitless_source.fetch_items(limit=10):
                assert isinstance(item, DataItem)
                assert item.namespace == "limitless"
                assert item.source_id == "limitless-123"
                assert "Morning Meeting" in item.content
                assert item.metadata is not None
                data_items.append(item)
            
            assert len(data_items) >= 1
            assert all(isinstance(item, DataItem) for item in data_items)

    @pytest.mark.asyncio
    async def test_weather_source_yields_data_items(self, ingestion_service, sample_weather_data):
        """Test that Weather source yields DataItem objects"""
        config = get_config()
        
        # Mock the API response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_weather_data
            mock_get.return_value = mock_response
            
            # Create Weather source
            weather_source = WeatherSource(config.weather, ingestion_service.database)
            ingestion_service.register_source(weather_source)
            
            # Test data item yielding
            data_items = []
            async for item in weather_source.fetch_items(limit=10):
                assert isinstance(item, DataItem)
                assert item.namespace == "weather"
                assert item.source_id.startswith("weather_")
                assert "Weather forecast" in item.content
                assert item.metadata is not None
                data_items.append(item)
            
            # Should yield one item per forecast day
            assert len(data_items) == 2  # Two forecast days in sample data

    @pytest.mark.asyncio
    async def test_news_source_yields_data_items(self, ingestion_service, sample_news_data):
        """Test that News source yields DataItem objects"""
        config = get_config()
        
        # Mock the API response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": sample_news_data}
            mock_get.return_value = mock_response
            
            # Create News source
            news_source = NewsSource(config.news, ingestion_service.database)
            ingestion_service.register_source(news_source)
            
            # Test data item yielding
            data_items = []
            async for item in news_source.fetch_items(limit=10):
                assert isinstance(item, DataItem)
                assert item.namespace == "news"
                assert item.content is not None
                assert item.metadata is not None
                data_items.append(item)
            
            assert len(data_items) >= 1

    @pytest.mark.asyncio
    async def test_ingestion_stores_all_sources_in_data_items(self, ingestion_service, database_service):
        """Test that ingestion service stores data from all sources in data_items table"""
        
        # Create sample DataItems from each source type
        limitless_item = DataItem(
            namespace="limitless",
            source_id="test-limitless-1",
            content="Test limitless content",
            metadata={"start_time": "2025-01-15T09:00:00Z"},
            created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        weather_item = DataItem(
            namespace="weather", 
            source_id="weather_2025-01-15",
            content="Weather forecast for 2025-01-15",
            metadata={"condition_code": "sunny", "temperature_max": 25.0},
            created_at=datetime(2025, 1, 15, 8, 0, tzinfo=timezone.utc)
        )
        
        news_item = DataItem(
            namespace="news",
            source_id="news-123",
            content="Breaking news story",
            metadata={"published_datetime_utc": "2025-01-15T14:00:00Z"},
            created_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc)
        )
        
        twitter_item = DataItem(
            namespace="twitter",
            source_id="tweet-456", 
            content="Great day for coding!",
            metadata={"original_created_at": "2025-01-15T12:00:00"},
            created_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        )
        
        # Process each item through ingestion service
        from services.ingestion import IngestionResult
        result = IngestionResult()
        
        await ingestion_service._process_and_store_item(limitless_item, result)
        await ingestion_service._process_and_store_item(weather_item, result)
        await ingestion_service._process_and_store_item(news_item, result)
        await ingestion_service._process_and_store_item(twitter_item, result)
        
        # Verify all items were stored successfully
        assert result.items_stored == 4
        assert len(result.errors) == 0
        
        # Verify data exists in data_items table
        limitless_data = database_service.get_data_items_by_namespace("limitless")
        weather_data = database_service.get_data_items_by_namespace("weather")
        news_data = database_service.get_data_items_by_namespace("news")
        twitter_data = database_service.get_data_items_by_namespace("twitter")
        
        assert len(limitless_data) >= 1
        assert len(weather_data) >= 1
        assert len(news_data) >= 1
        assert len(twitter_data) >= 1
        
        # Verify days_date was set correctly for calendar integration
        all_items = database_service.get_data_items_by_date("2025-01-15")
        assert len(all_items) >= 4  # Should find all items for the test date

    @pytest.mark.asyncio
    async def test_calendar_integration_shows_all_sources(self, database_service):
        """Test that calendar can retrieve data from all sources"""
        
        # Store test data for different sources
        test_date = "2025-01-15"
        
        database_service.store_data_item(
            id="limitless:test-1",
            namespace="limitless",
            source_id="test-1",
            content="Limitless content",
            metadata={"source_type": "limitless"},
            days_date=test_date
        )
        
        database_service.store_data_item(
            id="weather:test-1",
            namespace="weather",
            source_id="test-1", 
            content="Weather content",
            metadata={"source_type": "weather"},
            days_date=test_date
        )
        
        database_service.store_data_item(
            id="news:test-1",
            namespace="news",
            source_id="test-1",
            content="News content",
            metadata={"source_type": "news"},
            days_date=test_date
        )
        
        database_service.store_data_item(
            id="twitter:test-1",
            namespace="twitter",
            source_id="test-1",
            content="Twitter content", 
            metadata={"source_type": "twitter"},
            days_date=test_date
        )
        
        # Test calendar data retrieval
        days_with_data = database_service.get_days_with_data()
        assert test_date in days_with_data
        
        # Test retrieving data for specific date
        date_data = database_service.get_data_items_by_date(test_date)
        assert len(date_data) == 4
        
        # Verify all source types are represented
        source_types = [item['namespace'] for item in date_data]
        assert "limitless" in source_types
        assert "weather" in source_types
        assert "news" in source_types
        assert "twitter" in source_types

    @pytest.mark.asyncio
    async def test_embedding_pipeline_processes_all_sources(self, ingestion_service, database_service, mock_embedding_service):
        """Test that embedding pipeline processes data from all sources"""
        
        # Store data items that need embedding
        test_items = [
            ("limitless:embed-1", "limitless", "embed-1", "Limitless content for embedding", "2025-01-15"),
            ("weather:embed-1", "weather", "embed-1", "Weather content for embedding", "2025-01-15"),
            ("news:embed-1", "news", "embed-1", "News content for embedding", "2025-01-15"),
            ("twitter:embed-1", "twitter", "embed-1", "Twitter content for embedding", "2025-01-15")
        ]
        
        for item_id, namespace, source_id, content, days_date in test_items:
            database_service.store_data_item(
                id=item_id,
                namespace=namespace,
                source_id=source_id,
                content=content,
                metadata={"test": True},
                days_date=days_date
            )
        
        # Process pending embeddings
        result = await ingestion_service.process_pending_embeddings(batch_size=10)
        
        # Verify embeddings were processed
        assert result["processed"] >= 4
        assert result["successful"] >= 4
        assert len(result["errors"]) == 0
        
        # Verify embedding service was called with content from all sources
        mock_embedding_service.embed_texts.assert_called()
        call_args = mock_embedding_service.embed_texts.call_args[0][0]  # First positional argument
        
        # Verify content from all namespaces was included
        content_texts = set(call_args)
        assert any("Limitless content" in text for text in content_texts)
        assert any("Weather content" in text for text in content_texts)
        assert any("News content" in text for text in content_texts)
        assert any("Twitter content" in text for text in content_texts)

    @pytest.mark.asyncio
    async def test_search_finds_data_from_all_sources(self, database_service, mock_vector_store):
        """Test that search can find data from all sources"""
        
        # Store test data with embeddings
        test_data = [
            ("limitless:search-1", "limitless", "Meeting about project planning"),
            ("weather:search-1", "weather", "Sunny weather forecast"),
            ("news:search-1", "news", "Technology breakthrough announced"),
            ("twitter:search-1", "twitter", "Excited about new features")
        ]
        
        for item_id, namespace, content in test_data:
            database_service.store_data_item(
                id=item_id,
                namespace=namespace,
                source_id="search-1",
                content=content,
                metadata={"searchable": True},
                days_date="2025-01-15"
            )
            # Mark as embedded
            database_service.update_embedding_status(item_id, "completed")
        
        # Mock vector store to return IDs from all sources
        mock_vector_store.search_similar = Mock(return_value=[
            ("limitless:search-1", 0.9),
            ("weather:search-1", 0.8),
            ("news:search-1", 0.7),
            ("twitter:search-1", 0.6)
        ])
        
        # Test that database can retrieve items by IDs from vector search
        search_ids = ["limitless:search-1", "weather:search-1", "news:search-1", "twitter:search-1"]
        search_results = database_service.get_data_items_by_ids(search_ids)
        
        assert len(search_results) == 4
        
        # Verify all source types are in search results
        result_namespaces = [item['namespace'] for item in search_results]
        assert "limitless" in result_namespaces
        assert "weather" in result_namespaces
        assert "news" in result_namespaces
        assert "twitter" in result_namespaces

    def test_days_date_extraction_consistency(self, ingestion_service):
        """Test that days_date extraction works consistently across all sources"""
        
        # Test different timestamp formats from different sources
        test_cases = [
            # Limitless format
            DataItem(
                namespace="limitless",
                source_id="test-1",
                content="test",
                metadata={"start_time": "2025-01-15T09:00:00Z"},
                created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
            ),
            # Weather format
            DataItem(
                namespace="weather",
                source_id="test-2",
                content="test",
                metadata={"forecast_start": "2025-01-15T00:00:00Z"},
                created_at=datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)
            ),
            # News format
            DataItem(
                namespace="news",
                source_id="test-3",
                content="test",
                metadata={"published_datetime_utc": "2025-01-15T14:00:00Z"},
                created_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc)
            ),
            # Twitter format
            DataItem(
                namespace="twitter",
                source_id="test-4",
                content="test",
                metadata={"original_created_at": "2025-01-15T12:00:00"},
                created_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
            )
        ]
        
        for item in test_cases:
            days_date = ingestion_service._extract_days_date(item)
            assert days_date == "2025-01-15", f"Failed for {item.namespace}: got {days_date}"

    @pytest.mark.asyncio
    async def test_end_to_end_data_flow(self, ingestion_service, database_service):
        """Test complete end-to-end data flow from source to search"""
        
        # Create a DataItem representing data from each source
        test_items = [
            DataItem(
                namespace="limitless",
                source_id="e2e-limitless",
                content="End-to-end test meeting content",
                metadata={"start_time": "2025-01-15T10:00:00Z", "test": "e2e"},
                created_at=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
            ),
            DataItem(
                namespace="weather",
                source_id="e2e-weather",
                content="End-to-end test weather forecast",
                metadata={"condition_code": "sunny", "test": "e2e"},
                created_at=datetime(2025, 1, 15, 8, 0, tzinfo=timezone.utc)
            ),
            DataItem(
                namespace="news",
                source_id="e2e-news",
                content="End-to-end test news article",
                metadata={"published_datetime_utc": "2025-01-15T15:00:00Z", "test": "e2e"},
                created_at=datetime(2025, 1, 15, 15, 0, tzinfo=timezone.utc)
            ),
            DataItem(
                namespace="twitter",
                source_id="e2e-twitter",
                content="End-to-end test tweet content",
                metadata={"original_created_at": "2025-01-15T13:00:00", "test": "e2e"},
                created_at=datetime(2025, 1, 15, 13, 0, tzinfo=timezone.utc)
            )
        ]
        
        # Process each item through the complete pipeline
        from services.ingestion import IngestionResult
        result = IngestionResult()
        
        for item in test_items:
            await ingestion_service._process_and_store_item(item, result)
        
        # Verify pipeline processed all items successfully
        assert result.items_stored == 4
        assert len(result.errors) == 0
        
        # Verify data is searchable by namespace
        for namespace in ["limitless", "weather", "news", "twitter"]:
            namespace_data = database_service.get_data_items_by_namespace(namespace, limit=100)
            e2e_items = [item for item in namespace_data if item.get('metadata', {}).get('test') == 'e2e']
            assert len(e2e_items) >= 1, f"No e2e test data found for {namespace}"
        
        # Verify calendar integration works
        test_date = "2025-01-15"
        date_data = database_service.get_data_items_by_date(test_date)
        e2e_date_items = [item for item in date_data if item.get('metadata', {}).get('test') == 'e2e']
        assert len(e2e_date_items) == 4, "Not all e2e items found for test date"
        
        # Verify days_date was extracted correctly for all sources
        days_with_data = database_service.get_days_with_data()
        assert test_date in days_with_data
        
        # Verify embedding status is set to pending for all items
        pending_embeddings = database_service.get_pending_embeddings(limit=100)
        e2e_pending = [item for item in pending_embeddings if item.get('metadata', {}).get('test') == 'e2e']
        assert len(e2e_pending) == 4, "Not all e2e items queued for embedding"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])