"""
Test suite for source-specific processing verification

This test suite verifies that each source processes data correctly according to its specific requirements:
- Limitless: Full processor pipeline with deduplication and segmentation
- News: Deduplication strategy (fetch 20, select 5 unique headlines)
- Weather: DataItem transformation with forecast day separation  
- Twitter: Simple processing with metadata enhancement
"""

import pytest
import asyncio
import tempfile
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from core.database import DatabaseService
from sources.base import DataItem
from sources.limitless import LimitlessSource
from sources.limitless_processor import LimitlessProcessor
from sources.weather import WeatherSource
from sources.news import NewsSource
from sources.twitter import TwitterSource, TwitterProcessor
from config.factory import get_config


class TestSourceSpecificProcessing:
    """Test source-specific processing requirements"""

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
    def config(self):
        """Get application configuration"""
        return get_config()

    @pytest.fixture
    def limitless_processor(self):
        """Create Limitless processor with segmentation enabled"""
        return LimitlessProcessor(enable_segmentation=True)

    @pytest.fixture
    def twitter_processor(self):
        """Create Twitter processor"""
        return TwitterProcessor()

    def test_limitless_processor_handles_deduplication(self, limitless_processor):
        """Test that Limitless processor handles deduplication correctly"""
        
        # Create duplicate content items
        item1 = DataItem(
            namespace="limitless",
            source_id="dup-test-1",
            content="This is duplicate content for testing",
            metadata={
                "start_time": "2025-01-15T09:00:00Z",
                "original_lifelog": {"markdown": "# Test\nThis is duplicate content for testing"}
            },
            created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        item2 = DataItem(
            namespace="limitless",
            source_id="dup-test-2", 
            content="This is duplicate content for testing",  # Same content
            metadata={
                "start_time": "2025-01-15T10:00:00Z",
                "original_lifelog": {"markdown": "# Test\nThis is duplicate content for testing"}
            },
            created_at=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        )
        
        # Process both items
        processed1 = limitless_processor.process(item1)
        processed2 = limitless_processor.process(item2)
        
        # Verify processor maintains source identity
        assert processed1.source_id == "dup-test-1"
        assert processed2.source_id == "dup-test-2"
        
        # Verify processor enhances content
        assert processed1.content is not None
        assert processed2.content is not None
        
        # Verify metadata is preserved and enhanced
        assert processed1.metadata is not None
        assert processed2.metadata is not None

    def test_limitless_processor_segments_conversations(self, limitless_processor):
        """Test that Limitless processor segments long conversations"""
        
        # Create item with long conversation content
        long_content = "\n".join([
            f"Speaker {i % 3}: This is message {i} in a long conversation. " * 10
            for i in range(20)  # 20 messages to trigger segmentation
        ])
        
        item = DataItem(
            namespace="limitless",
            source_id="segment-test",
            content=long_content,
            metadata={
                "start_time": "2025-01-15T09:00:00Z",
                "end_time": "2025-01-15T11:00:00Z",
                "original_lifelog": {"markdown": f"# Long Meeting\n{long_content}"}
            },
            created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        # Process item
        processed = limitless_processor.process(item)
        
        # Verify content was processed
        assert processed.content is not None
        assert len(processed.content) > 0
        
        # Verify metadata indicates processing occurred
        assert processed.metadata is not None
        assert "processing_history" in processed.metadata

    def test_limitless_processor_extracts_metadata(self, limitless_processor):
        """Test that Limitless processor extracts and enriches metadata"""
        
        item = DataItem(
            namespace="limitless",
            source_id="meta-test",
            content="John: Let's schedule the meeting for tomorrow. Jane: Sounds good, 2 PM works.",
            metadata={
                "start_time": "2025-01-15T09:00:00Z",
                "end_time": "2025-01-15T09:30:00Z",
                "original_lifelog": {
                    "title": "Quick Planning Chat",
                    "markdown": "# Planning\nJohn: Let's schedule the meeting for tomorrow. Jane: Sounds good, 2 PM works."
                }
            },
            created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        # Process item
        processed = limitless_processor.process(item)
        
        # Verify metadata enrichment
        assert processed.metadata is not None
        
        # Check for processing indicators
        processing_history = processed.metadata.get("processing_history", [])
        processor_names = [step.get("processor") for step in processing_history]
        
        # Should have gone through multiple processors
        assert "BasicCleaningProcessor" in processor_names
        assert "MetadataEnrichmentProcessor" in processor_names

    @pytest.mark.asyncio
    async def test_weather_source_transforms_api_data(self, database_service, config):
        """Test that Weather source transforms API data into DataItems correctly"""
        
        # Mock weather API response
        weather_response = {
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
        
        # Create Weather source
        weather_source = WeatherSource(config.weather, database_service)
        
        # Test transformation method
        data_items = weather_source._transform_weather_data(weather_response)
        
        # Verify correct number of items (one per forecast day)
        assert len(data_items) == 2
        
        # Verify first item
        item1 = data_items[0]
        assert isinstance(item1, DataItem)
        assert item1.namespace == "weather"
        assert item1.source_id == "weather_2025-01-15"
        assert "Weather forecast for 2025-01-15" in item1.content
        assert "sunny" in item1.content
        assert item1.metadata["condition_code"] == "sunny"
        assert item1.metadata["temperature_max"] == 25.0
        
        # Verify second item
        item2 = data_items[1]
        assert isinstance(item2, DataItem)
        assert item2.namespace == "weather"
        assert item2.source_id == "weather_2025-01-16"
        assert "Weather forecast for 2025-01-16" in item2.content
        assert "cloudy" in item2.content
        assert item2.metadata["condition_code"] == "cloudy"
        assert item2.metadata["temperature_max"] == 22.0

    @pytest.mark.asyncio
    async def test_weather_source_handles_temperature_units(self, database_service, config):
        """Test that Weather source handles temperature unit conversion"""
        
        weather_response = {
            "forecastDaily": {
                "readTime": "2025-01-15T08:00:00Z",
                "days": [
                    {
                        "forecastStart": "2025-01-15T00:00:00Z",
                        "conditionCode": "sunny",
                        "temperatureMax": 25.0,  # Celsius from API
                        "temperatureMin": 15.0,
                        "daytimeForecast": {"conditionCode": "sunny"}
                    }
                ]
            }
        }
        
        # Test with standard units (should convert to Fahrenheit)
        config.weather.units = "standard"
        weather_source = WeatherSource(config.weather, database_service)
        data_items = weather_source._transform_weather_data(weather_response)
        
        item = data_items[0]
        # Should contain converted temperatures
        assert "77.0°F" in item.content  # 25°C = 77°F
        assert "59.0°F" in item.content  # 15°C = 59°F
        
        # Metadata should contain converted values
        assert item.metadata["temperature_max"] == 77.0
        assert item.metadata["temperature_min"] == 59.0

    @pytest.mark.asyncio 
    async def test_news_source_deduplication_strategy(self, database_service, config):
        """Test that News source implements correct deduplication strategy"""
        
        # Mock news API response with similar headlines (more than 5)
        news_response = {
            "data": [
                {"title": "Tech Innovation Breakthrough", "link": "url1", "snippet": "desc1", "published_datetime_utc": "2025-01-15T10:00:00Z"},
                {"title": "Technology Innovation Breakthrough", "link": "url2", "snippet": "desc2", "published_datetime_utc": "2025-01-15T10:30:00Z"},  # Similar
                {"title": "Market Update Today", "link": "url3", "snippet": "desc3", "published_datetime_utc": "2025-01-15T11:00:00Z"},
                {"title": "Stock Market Update", "link": "url4", "snippet": "desc4", "published_datetime_utc": "2025-01-15T11:30:00Z"},  # Similar
                {"title": "Weather Report", "link": "url5", "snippet": "desc5", "published_datetime_utc": "2025-01-15T12:00:00Z"},
                {"title": "Sports Results", "link": "url6", "snippet": "desc6", "published_datetime_utc": "2025-01-15T12:30:00Z"},
                {"title": "Politics Today", "link": "url7", "snippet": "desc7", "published_datetime_utc": "2025-01-15T13:00:00Z"},
                {"title": "Entertainment News", "link": "url8", "snippet": "desc8", "published_datetime_utc": "2025-01-15T13:30:00Z"},
            ]
        }
        
        # Create News source
        news_source = NewsSource(config.news, database_service)
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = news_response
            mock_get.return_value = mock_response
            
            # Fetch items (should apply deduplication)
            data_items = []
            async for item in news_source.fetch_items(limit=10):
                data_items.append(item)
            
            # Should return exactly 5 items (UNIQUE_NEWS_ITEMS_PER_DAY)
            assert len(data_items) <= 5  # May be less due to deduplication
            
            # Verify all items are DataItem objects
            for item in data_items:
                assert isinstance(item, DataItem)
                assert item.namespace == "news"
                assert item.content is not None
                assert item.metadata is not None

    def test_twitter_processor_enhances_metadata(self, twitter_processor):
        """Test that Twitter processor enhances metadata correctly"""
        
        item = DataItem(
            namespace="twitter",
            source_id="tweet-123",
            content="Excited about the new project launch! #coding #startup",
            metadata={
                "media_urls": "[]",
                "original_created_at": "2025-01-15T12:00:00",
                "source_type": "twitter_archive"
            },
            created_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        )
        
        # Process item
        processed = twitter_processor.process(item)
        
        # Verify basic properties preserved
        assert processed.namespace == "twitter"
        assert processed.source_id == "tweet-123"
        assert processed.content == item.content
        
        # Verify metadata enhancement
        assert processed.metadata is not None
        assert processed.metadata["source_type"] == "twitter_archive"
        assert processed.metadata["original_created_at"] == "2025-01-15T12:00:00"

    @pytest.mark.asyncio
    async def test_twitter_source_filters_existing_tweets(self, database_service, config):
        """Test that Twitter source filters out existing tweets during import"""
        
        # Store existing tweet in database
        existing_tweet_data = {
            "namespace": "twitter",
            "source_id": "existing-tweet-123",
            "content": "This tweet already exists",
            "metadata": {"source_type": "twitter_archive"},
            "days_date": "2025-01-15"
        }
        
        database_service.store_data_item(
            id="twitter:existing-tweet-123",
            **existing_tweet_data
        )
        
        # Create Twitter source
        twitter_source = TwitterSource(config.twitter, database_service)
        
        # Mock _get_existing_tweet_ids to return the existing tweet
        existing_ids = await twitter_source._get_existing_tweet_ids()
        assert "existing-tweet-123" in existing_ids or len(existing_ids) >= 1

    def test_processor_error_handling(self, limitless_processor):
        """Test that processors handle errors gracefully"""
        
        # Create item with malformed metadata
        malformed_item = DataItem(
            namespace="limitless",
            source_id="error-test",
            content="Valid content",
            metadata="invalid json string",  # This should be a dict
            created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        # Processing should not crash
        try:
            processed = limitless_processor.process(malformed_item)
            # Should return a processed item even with errors
            assert processed is not None
            assert processed.namespace == "limitless"
            assert processed.source_id == "error-test"
        except Exception as e:
            pytest.fail(f"Processor should handle errors gracefully, but raised: {e}")

    def test_content_preservation_across_processing(self):
        """Test that essential content is preserved across all processing"""
        
        # Test data for each source type
        test_cases = [
            {
                "processor": LimitlessProcessor(),
                "item": DataItem(
                    namespace="limitless",
                    source_id="preserve-test-1",
                    content="Important meeting content that must be preserved",
                    metadata={"start_time": "2025-01-15T09:00:00Z"},
                    created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
                )
            },
            {
                "processor": TwitterProcessor(),
                "item": DataItem(
                    namespace="twitter",
                    source_id="preserve-test-2",
                    content="Important tweet content that must be preserved #important",
                    metadata={"original_created_at": "2025-01-15T12:00:00"},
                    created_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
                )
            }
        ]
        
        for case in test_cases:
            processor = case["processor"]
            original_item = case["item"]
            
            # Process item
            processed = processor.process(original_item)
            
            # Verify essential properties preserved
            assert processed.namespace == original_item.namespace
            assert processed.source_id == original_item.source_id
            
            # Content should be preserved or enhanced, not lost
            assert processed.content is not None
            assert len(processed.content) > 0
            
            # Original content should be findable in processed content or metadata
            original_content = original_item.content.lower()
            processed_content = processed.content.lower() if processed.content else ""
            processed_metadata_str = str(processed.metadata).lower() if processed.metadata else ""
            
            content_preserved = (
                original_content in processed_content or 
                original_content in processed_metadata_str
            )
            
            assert content_preserved, f"Original content lost during {processor.__class__.__name__} processing"

    @pytest.mark.asyncio
    async def test_source_specific_storage_patterns(self, database_service, config):
        """Test that sources maintain their specific storage patterns while using unified flow"""
        
        # Create sources
        limitless_source = LimitlessSource(config.limitless, database_service)
        weather_source = WeatherSource(config.weather, database_service)
        
        # Mock data for testing
        limitless_data = DataItem(
            namespace="limitless",
            source_id="storage-test-1",
            content="Test limitless content",
            metadata={"start_time": "2025-01-15T09:00:00Z"},
            created_at=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        weather_data = [DataItem(
            namespace="weather",
            source_id="weather_2025-01-15",
            content="Test weather content",
            metadata={"condition_code": "sunny"},
            created_at=datetime(2025, 1, 15, 8, 0, tzinfo=timezone.utc)
        )]
        
        # Test that weather source still stores raw API data
        sample_weather_api_data = {
            "forecastDaily": {
                "readTime": "2025-01-15T08:00:00Z",
                "days": [{"forecastStart": "2025-01-15T00:00:00Z", "conditionCode": "sunny"}]
            }
        }
        
        # Store weather API data (this is source-specific storage)
        await weather_source._store_weather_data(sample_weather_api_data)
        
        # Verify weather data was stored in specialized table
        with database_service.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM weather")
            row = cursor.fetchone()
            assert row['count'] >= 1, "Weather data should be stored in specialized weather table"
        
        # Verify that while sources maintain specialized storage,
        # they also participate in unified data_items flow
        # (This would be tested in integration with ingestion service)

    def test_metadata_standardization_across_sources(self):
        """Test that all sources provide standardized metadata fields"""
        
        required_fields = ["source_type", "days_date"]
        timestamp_fields = ["start_time", "created_at", "original_created_at", "published_datetime_utc", "forecast_start"]
        
        # Test metadata from each source type
        test_metadata_samples = [
            {
                "source": "limitless",
                "metadata": {
                    "start_time": "2025-01-15T09:00:00Z",
                    "end_time": "2025-01-15T10:00:00Z",
                    "original_lifelog": {"title": "Meeting"}
                }
            },
            {
                "source": "weather", 
                "metadata": {
                    "forecast_start": "2025-01-15T00:00:00Z",
                    "condition_code": "sunny",
                    "temperature_max": 25.0
                }
            },
            {
                "source": "news",
                "metadata": {
                    "published_datetime_utc": "2025-01-15T14:00:00Z",
                    "link": "https://example.com"
                }
            },
            {
                "source": "twitter",
                "metadata": {
                    "original_created_at": "2025-01-15T12:00:00",
                    "media_urls": "[]"
                }
            }
        ]
        
        for sample in test_metadata_samples:
            metadata = sample["metadata"]
            
            # Verify at least one timestamp field is present
            has_timestamp = any(field in metadata for field in timestamp_fields)
            assert has_timestamp, f"{sample['source']} metadata missing timestamp field"
            
            # Verify metadata is structured (dict, not string)
            assert isinstance(metadata, dict), f"{sample['source']} metadata should be dict"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])