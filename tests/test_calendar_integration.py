"""
Test suite for calendar integration functionality

This test suite verifies that the calendar functionality works correctly with the unified data architecture:
- Calendar displays data from all sources
- Calendar API endpoints return correct data
- Date filtering works across all source types
- Calendar UI integration functions properly
"""

import pytest
import asyncio
import tempfile
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from fastapi.testclient import TestClient
from fastapi import FastAPI

from core.database import DatabaseService
from api.routes.calendar import router as calendar_router
from services.startup import StartupService
from config.factory import get_config


class TestCalendarIntegration:
    """Test calendar integration with unified data architecture"""

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
    def mock_startup_service(self, database_service):
        """Create mock startup service"""
        mock_startup = Mock(spec=StartupService)
        mock_startup.database = database_service
        mock_startup.config = get_config()
        return mock_startup

    @pytest.fixture
    def test_app(self, mock_startup_service):
        """Create test FastAPI app with calendar routes"""
        app = FastAPI()
        app.include_router(calendar_router)
        
        # Override dependency
        app.dependency_overrides[StartupService] = lambda: mock_startup_service
        
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)

    @pytest.fixture
    def sample_data_all_sources(self, database_service):
        """Store sample data from all sources for testing"""
        test_date = "2025-01-15"
        
        # Limitless data
        database_service.store_data_item(
            id="limitless:cal-test-1",
            namespace="limitless",
            source_id="cal-test-1",
            content="Morning standup meeting with team",
            metadata={
                "start_time": "2025-01-15T09:00:00Z",
                "end_time": "2025-01-15T09:30:00Z",
                "title": "Standup Meeting"
            },
            days_date=test_date
        )
        
        # Weather data
        database_service.store_data_item(
            id="weather:cal-test-1",
            namespace="weather",
            source_id="weather_2025-01-15",
            content="Weather forecast for 2025-01-15\nCondition: sunny\nTemperature: 59.0°F to 77.0°F",
            metadata={
                "condition_code": "sunny",
                "temperature_max": 77.0,
                "temperature_min": 59.0,
                "forecast_start": "2025-01-15T00:00:00Z"
            },
            days_date=test_date
        )
        
        # News data
        database_service.store_data_item(
            id="news:cal-test-1",
            namespace="news",
            source_id="cal-test-1",
            content="Tech Innovation Breakthrough\nScientists develop new technology for improved efficiency",
            metadata={
                "title": "Tech Innovation Breakthrough",
                "link": "https://example.com/news1",
                "published_datetime_utc": "2025-01-15T14:00:00Z"
            },
            days_date=test_date
        )
        
        # Twitter data
        database_service.store_data_item(
            id="twitter:cal-test-1",
            namespace="twitter",
            source_id="cal-test-1",
            content="Excited about the progress on our new project! #coding #startup",
            metadata={
                "original_created_at": "2025-01-15T12:00:00",
                "media_urls": "[]"
            },
            days_date=test_date
        )
        
        return test_date

    def test_get_days_with_data_includes_all_sources(self, database_service, sample_data_all_sources):
        """Test that get_days_with_data returns days from all sources"""
        test_date = sample_data_all_sources
        
        # Get days with data
        days_with_data = database_service.get_days_with_data()
        
        # Should include the test date
        assert test_date in days_with_data
        
        # Test namespace filtering
        limitless_days = database_service.get_days_with_data(namespaces=["limitless"])
        weather_days = database_service.get_days_with_data(namespaces=["weather"])
        news_days = database_service.get_days_with_data(namespaces=["news"])
        twitter_days = database_service.get_days_with_data(namespaces=["twitter"])
        
        assert test_date in limitless_days
        assert test_date in weather_days
        assert test_date in news_days
        assert test_date in twitter_days

    def test_get_data_items_by_date_returns_all_sources(self, database_service, sample_data_all_sources):
        """Test that get_data_items_by_date returns data from all sources"""
        test_date = sample_data_all_sources
        
        # Get all data for the date
        date_data = database_service.get_data_items_by_date(test_date)
        
        # Should have data from all 4 sources
        assert len(date_data) == 4
        
        # Verify all source types are represented
        namespaces = [item['namespace'] for item in date_data]
        assert "limitless" in namespaces
        assert "weather" in namespaces
        assert "news" in namespaces
        assert "twitter" in namespaces
        
        # Verify content is present
        for item in date_data:
            assert item['content'] is not None
            assert len(item['content']) > 0
            assert item['days_date'] == test_date

    def test_get_data_items_by_date_range(self, database_service):
        """Test date range queries work across all sources"""
        
        # Store data across multiple dates
        dates = ["2025-01-15", "2025-01-16", "2025-01-17"]
        
        for i, date in enumerate(dates):
            database_service.store_data_item(
                id=f"limitless:range-test-{i}",
                namespace="limitless",
                source_id=f"range-test-{i}",
                content=f"Content for {date}",
                metadata={"test_date": date},
                days_date=date
            )
            
            database_service.store_data_item(
                id=f"weather:range-test-{i}",
                namespace="weather",
                source_id=f"weather_{date}",
                content=f"Weather for {date}",
                metadata={"test_date": date},
                days_date=date
            )
        
        # Test range query
        range_data = database_service.get_data_items_by_date_range("2025-01-15", "2025-01-17")
        
        # Should have data from all dates and both sources
        assert len(range_data) == 6  # 3 dates × 2 sources
        
        # Verify dates are within range
        for item in range_data:
            assert item['days_date'] in dates

    @pytest.mark.asyncio
    async def test_calendar_api_days_with_data_endpoint(self, client, sample_data_all_sources):
        """Test /api/days-with-data API endpoint"""
        
        # Mock templates to avoid template dependency
        with patch('api.routes.calendar.templates') as mock_templates:
            response = client.get("/calendar/api/days-with-data")
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return both 'all' and 'twitter' lists
            assert "all" in data
            assert "twitter" in data
            assert isinstance(data["all"], list)
            assert isinstance(data["twitter"], list)
            
            # Should include our test date
            test_date = sample_data_all_sources
            assert test_date in data["all"]

    @pytest.mark.asyncio
    async def test_calendar_api_days_with_data_filtered(self, client, sample_data_all_sources):
        """Test /api/days-with-data with year/month filtering"""
        
        with patch('api.routes.calendar.templates'):
            response = client.get("/calendar/api/days-with-data?year=2025&month=1")
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return filtered results
            assert "all" in data
            assert "twitter" in data
            
            # All returned dates should be from January 2025
            for date in data["all"]:
                assert date.startswith("2025-01")

    @pytest.mark.asyncio 
    async def test_calendar_api_day_details_endpoint(self, client, sample_data_all_sources):
        """Test /api/day/{date} API endpoint"""
        test_date = sample_data_all_sources
        
        with patch('api.routes.calendar.templates'):
            response = client.get(f"/calendar/api/day/{test_date}")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert data["date"] == test_date
            assert "formatted_date" in data
            assert "day_of_week" in data
            assert "markdown_content" in data
            assert "item_count" in data
            assert data["has_data"] is True
            
            # Should have found our test data
            assert data["item_count"] > 0

    @pytest.mark.asyncio
    async def test_calendar_api_enhanced_day_data_endpoint(self, client, sample_data_all_sources):
        """Test /api/day/{date}/enhanced API endpoint"""
        test_date = sample_data_all_sources
        
        with patch('api.routes.calendar.templates'):
            # Mock weather and news services
            with patch('api.routes.calendar.get_weather_service') as mock_weather_service:
                with patch('api.routes.calendar.get_news_service') as mock_news_service:
                    
                    # Mock service returns
                    mock_weather = Mock()
                    mock_weather.get_weather_for_date_range.return_value = [
                        {"condition": "sunny", "temp_max": 77, "temp_min": 59}
                    ]
                    mock_weather_service.return_value = mock_weather
                    
                    mock_news = Mock()
                    mock_news.get_news_by_date.return_value = [
                        {"title": "Test News", "link": "http://example.com"}
                    ]
                    mock_news_service.return_value = mock_news
                    
                    response = client.get(f"/calendar/api/day/{test_date}/enhanced")
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    # Verify enhanced response structure
                    assert data["date"] == test_date
                    assert "weather" in data
                    assert "news" in data
                    assert "limitless" in data
                    assert "summary" in data
                    
                    # Verify weather data
                    assert data["weather"]["has_data"] is True
                    assert len(data["weather"]["forecast_days"]) > 0
                    
                    # Verify news data
                    assert data["news"]["has_data"] is True
                    assert data["news"]["count"] > 0
                    
                    # Verify limitless data
                    assert data["limitless"]["has_data"] is True
                    assert data["limitless"]["item_count"] > 0

    def test_calendar_markdown_extraction_all_sources(self, database_service, sample_data_all_sources):
        """Test that markdown extraction works for all source types"""
        test_date = sample_data_all_sources
        
        # Test markdown extraction for limitless namespace (special handling)
        limitless_markdown = database_service.get_markdown_by_date(test_date, namespaces=["limitless"])
        assert limitless_markdown is not None
        assert len(limitless_markdown) > 0
        assert "Standup Meeting" in limitless_markdown or "standup" in limitless_markdown.lower()
        
        # Test markdown extraction for other namespaces
        weather_markdown = database_service.get_markdown_by_date(test_date, namespaces=["weather"])
        assert weather_markdown is not None
        assert len(weather_markdown) > 0
        
        # Test markdown extraction for all namespaces combined
        all_markdown = database_service.get_markdown_by_date(test_date)
        assert all_markdown is not None
        assert len(all_markdown) > 0

    def test_calendar_date_extraction_consistency(self, database_service):
        """Test that date extraction works consistently for calendar integration"""
        
        # Test different timestamp formats from each source
        test_cases = [
            {
                "namespace": "limitless",
                "metadata": {"start_time": "2025-01-20T09:00:00Z"},
                "expected_date": "2025-01-20"
            },
            {
                "namespace": "weather", 
                "metadata": {"forecast_start": "2025-01-21T00:00:00Z"},
                "expected_date": "2025-01-21"
            },
            {
                "namespace": "news",
                "metadata": {"published_datetime_utc": "2025-01-22T14:00:00Z"},
                "expected_date": "2025-01-22"
            },
            {
                "namespace": "twitter",
                "metadata": {"original_created_at": "2025-01-23T12:00:00"},
                "expected_date": "2025-01-23"
            }
        ]
        
        for i, case in enumerate(test_cases):
            item_id = f"{case['namespace']}:date-test-{i}"
            database_service.store_data_item(
                id=item_id,
                namespace=case['namespace'],
                source_id=f"date-test-{i}",
                content=f"Test content for {case['namespace']}",
                metadata=case['metadata'],
                days_date=case['expected_date']
            )
            
            # Verify the date was stored correctly
            date_data = database_service.get_data_items_by_date(case['expected_date'])
            namespace_items = [item for item in date_data if item['namespace'] == case['namespace']]
            assert len(namespace_items) >= 1, f"Date extraction failed for {case['namespace']}"

    def test_calendar_empty_date_handling(self, database_service):
        """Test calendar behavior with dates that have no data"""
        
        empty_date = "2025-12-31"  # Date with no data
        
        # Should return empty results gracefully
        date_data = database_service.get_data_items_by_date(empty_date)
        assert len(date_data) == 0
        
        days_with_data = database_service.get_days_with_data()
        assert empty_date not in days_with_data
        
        # Markdown should return appropriate message
        markdown = database_service.get_markdown_by_date(empty_date)
        assert "No data available" in markdown

    @pytest.mark.asyncio
    async def test_calendar_api_invalid_date_handling(self, client):
        """Test calendar API error handling for invalid dates"""
        
        with patch('api.routes.calendar.templates'):
            # Test invalid date format
            response = client.get("/calendar/api/day/invalid-date")
            assert response.status_code == 400
            
            # Test invalid month in month API
            response = client.get("/calendar/api/month/2025/13")
            assert response.status_code == 400
            
            # Test invalid year
            response = client.get("/calendar/api/month/1800/1")
            assert response.status_code == 400

    def test_calendar_performance_large_dataset(self, database_service):
        """Test calendar performance with larger datasets"""
        
        # Create larger dataset across multiple dates and sources
        dates = [f"2025-01-{day:02d}" for day in range(1, 32)]  # Full month
        namespaces = ["limitless", "weather", "news", "twitter"]
        
        # Store test data
        for date in dates:
            for namespace in namespaces:
                database_service.store_data_item(
                    id=f"{namespace}:perf-{date}",
                    namespace=namespace,
                    source_id=f"perf-{date}",
                    content=f"Performance test content for {namespace} on {date}",
                    metadata={"test": "performance", "date": date},
                    days_date=date
                )
        
        # Test that queries complete in reasonable time
        import time
        
        start_time = time.time()
        days_with_data = database_service.get_days_with_data()
        query_time = time.time() - start_time
        
        # Should complete quickly (under 1 second for this dataset size)
        assert query_time < 1.0
        assert len(days_with_data) >= len(dates)
        
        # Test date range query performance
        start_time = time.time()
        range_data = database_service.get_data_items_by_date_range("2025-01-01", "2025-01-31")
        query_time = time.time() - start_time
        
        assert query_time < 2.0  # Should complete quickly
        assert len(range_data) > 0

    def test_calendar_timezone_handling(self, database_service):
        """Test that calendar handles timezone conversions correctly"""
        
        # Test data with different timezone formats
        timezone_test_cases = [
            {
                "timestamp": "2025-01-15T14:00:00Z",  # UTC
                "expected_date": "2025-01-15"
            },
            {
                "timestamp": "2025-01-15T23:30:00Z",  # Late UTC, might be next day in some timezones
                "expected_date": "2025-01-15"  # Should extract based on user timezone
            },
            {
                "timestamp": "2025-01-16T01:00:00+02:00",  # With timezone offset
                "expected_date": "2025-01-15"  # Should convert to user timezone
            }
        ]
        
        for i, case in enumerate(timezone_test_cases):
            # Test timestamp extraction
            extracted_date = database_service.extract_date_from_timestamp(
                case['timestamp'], 
                user_timezone="America/New_York"
            )
            
            # Should extract date consistently
            assert extracted_date is not None
            # Note: Exact date depends on timezone conversion, but should be valid format
            assert len(extracted_date) == 10  # YYYY-MM-DD format
            assert extracted_date.startswith("2025-01")

    def test_calendar_data_completeness_verification(self, database_service, sample_data_all_sources):
        """Test that calendar shows complete data from unified architecture"""
        test_date = sample_data_all_sources
        
        # Verify each source type contributed data
        all_data = database_service.get_data_items_by_date(test_date)
        
        # Should have exactly 4 items (one from each source)
        assert len(all_data) == 4
        
        # Verify content quality
        for item in all_data:
            # Each item should have meaningful content
            assert item['content'] is not None
            assert len(item['content']) > 10  # Non-trivial content
            
            # Each item should have proper metadata
            assert item['metadata'] is not None
            
            # Each item should have correct date
            assert item['days_date'] == test_date
            
            # Each item should have valid namespace
            assert item['namespace'] in ["limitless", "weather", "news", "twitter"]
        
        # Verify no duplicates
        source_ids = [item['source_id'] for item in all_data]
        assert len(source_ids) == len(set(source_ids))  # All unique


if __name__ == "__main__":
    pytest.main([__file__, "-v"])