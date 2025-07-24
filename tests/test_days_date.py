"""
Tests for days_date functionality - timezone-aware date extraction and calendar queries
"""

import pytest
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import Mock

from core.database import DatabaseService
from sources.base import DataItem
from services.ingestion import IngestionService
from config.models import AppConfig, LimitlessConfig, NewsConfig


class TestDaysDateExtraction:
    """Test timezone-aware date extraction from timestamps"""
    
    def setup_method(self):
        """Set up test database for each test"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db = DatabaseService(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up test database after each test"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_extract_date_from_utc_z_format(self):
        """Test extracting date from UTC timestamp with Z suffix"""
        timestamp = "2024-01-15T14:30:00Z"
        result = self.db.extract_date_from_timestamp(timestamp, "UTC")
        assert result == "2024-01-15"
    
    def test_extract_date_from_utc_offset_format(self):
        """Test extracting date from UTC timestamp with +00:00 offset"""
        timestamp = "2024-01-15T14:30:00+00:00"
        result = self.db.extract_date_from_timestamp(timestamp, "UTC")
        assert result == "2024-01-15"
    
    def test_extract_date_with_timezone_conversion(self):
        """Test timezone conversion affects date extraction"""
        # 2:30 AM PST = 10:30 AM UTC (same day)
        timestamp = "2024-01-15T02:30:00-08:00"
        result = self.db.extract_date_from_timestamp(timestamp, "UTC")
        assert result == "2024-01-15"
        
        # But in PST timezone, it should still be the 15th
        result_pst = self.db.extract_date_from_timestamp(timestamp, "America/Los_Angeles")
        assert result_pst == "2024-01-15"
    
    def test_extract_date_with_cross_midnight_conversion(self):
        """Test timezone conversion that crosses midnight"""
        # 8:30 PM EST = 1:30 AM UTC next day
        timestamp = "2024-01-15T20:30:00-05:00"
        result = self.db.extract_date_from_timestamp(timestamp, "UTC")
        assert result == "2024-01-16"  # Next day in UTC
        
        # But in EST, it should still be the 15th
        result_est = self.db.extract_date_from_timestamp(timestamp, "America/New_York")
        assert result_est == "2024-01-15"
    
    def test_extract_date_invalid_timestamp(self):
        """Test handling of invalid timestamps"""
        result = self.db.extract_date_from_timestamp("invalid-timestamp", "UTC")
        assert result is None
    
    def test_extract_date_none_timestamp(self):
        """Test handling of None timestamp"""
        result = self.db.extract_date_from_timestamp(None, "UTC")
        assert result is None
    
    def test_extract_date_empty_timestamp(self):
        """Test handling of empty timestamp"""
        result = self.db.extract_date_from_timestamp("", "UTC")
        assert result is None
    
    def test_extract_date_invalid_timezone_fallback(self):
        """Test fallback to UTC when invalid timezone is provided"""
        timestamp = "2024-01-15T14:30:00Z"
        result = self.db.extract_date_from_timestamp(timestamp, "Invalid/Timezone")
        assert result == "2024-01-15"  # Should still work with UTC fallback


class TestDaysDateDatabase:
    """Test database operations with days_date column"""
    
    def setup_method(self):
        """Set up test database for each test"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db = DatabaseService(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up test database after each test"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_store_data_item_with_days_date(self):
        """Test storing data item with days_date"""
        self.db.store_data_item(
            id="limitless:test-123",
            namespace="limitless",
            source_id="test-123",
            content="Test content",
            metadata={"start_time": "2024-01-15T14:30:00Z"},
            days_date="2024-01-15"
        )
        
        # Verify it was stored
        items = self.db.get_data_items_by_ids(["limitless:test-123"])
        assert len(items) == 1
        assert items[0]["days_date"] == "2024-01-15"
        assert items[0]["content"] == "Test content"
    
    def test_get_data_items_by_date(self):
        """Test querying data items by specific date"""
        # Store items for different dates
        self.db.store_data_item("limitless:item1", "limitless", "item1", "Content 1", days_date="2024-01-15")
        self.db.store_data_item("limitless:item2", "limitless", "item2", "Content 2", days_date="2024-01-15")
        self.db.store_data_item("limitless:item3", "limitless", "item3", "Content 3", days_date="2024-01-16")
        
        # Query by date
        items_jan15 = self.db.get_data_items_by_date("2024-01-15")
        items_jan16 = self.db.get_data_items_by_date("2024-01-16")
        
        assert len(items_jan15) == 2
        assert len(items_jan16) == 1
        assert all(item["days_date"] == "2024-01-15" for item in items_jan15)
        assert items_jan16[0]["days_date"] == "2024-01-16"
    
    def test_get_data_items_by_date_range(self):
        """Test querying data items by date range"""
        # Store items across multiple dates
        dates_and_content = [
            ("2024-01-10", "Content 10"),
            ("2024-01-15", "Content 15a"),
            ("2024-01-15", "Content 15b"),
            ("2024-01-20", "Content 20"),
            ("2024-01-25", "Content 25")
        ]
        
        for i, (date, content) in enumerate(dates_and_content):
            self.db.store_data_item(f"test:item{i}", "test", f"item{i}", content, days_date=date)
        
        # Query date range
        items = self.db.get_data_items_by_date_range("2024-01-14", "2024-01-21")
        
        # Should include items from 15th and 20th
        assert len(items) == 3
        dates_in_range = {item["days_date"] for item in items}
        assert dates_in_range == {"2024-01-15", "2024-01-20"}
    
    def test_get_data_items_by_date_range_with_namespace_filter(self):
        """Test date range query with namespace filtering"""
        # Store items from different namespaces
        self.db.store_data_item("limitless:item1", "limitless", "item1", "Limitless 1", days_date="2024-01-15")
        self.db.store_data_item("news:item1", "news", "item1", "News 1", days_date="2024-01-15")
        self.db.store_data_item("limitless:item2", "limitless", "item2", "Limitless 2", days_date="2024-01-16")
        
        # Query with namespace filter
        limitless_items = self.db.get_data_items_by_date_range(
            "2024-01-15", "2024-01-16", namespaces=["limitless"]
        )
        
        assert len(limitless_items) == 2
        assert all(item["namespace"] == "limitless" for item in limitless_items)
    
    def test_get_available_dates(self):
        """Test getting list of available dates"""
        # Store items for various dates
        dates = ["2024-01-10", "2024-01-15", "2024-01-15", "2024-01-20"]  # Note: duplicate date
        
        for i, date in enumerate(dates):
            self.db.store_data_item(f"test:item{i}", "test", f"item{i}", f"Content {i}", days_date=date)
        
        available_dates = self.db.get_available_dates()
        
        # Should return unique dates in descending order
        assert available_dates == ["2024-01-20", "2024-01-15", "2024-01-10"]
    
    def test_get_available_dates_with_namespace_filter(self):
        """Test getting available dates with namespace filtering"""
        # Store items for different namespaces and dates
        self.db.store_data_item("limitless:item1", "limitless", "item1", "Content 1", days_date="2024-01-15")
        self.db.store_data_item("news:item1", "news", "item1", "Content 2", days_date="2024-01-16")
        self.db.store_data_item("limitless:item2", "limitless", "item2", "Content 3", days_date="2024-01-17")
        
        # Query available dates for limitless only
        limitless_dates = self.db.get_available_dates(namespaces=["limitless"])
        
        assert limitless_dates == ["2024-01-17", "2024-01-15"]


class TestIngestionServiceDaysDate:
    """Test ingestion service date extraction and storage"""
    
    def setup_method(self):
        """Set up test services"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Create mock config
        self.config = AppConfig(
            limitless=LimitlessConfig(timezone="America/New_York"),
            news=NewsConfig()
        )
        
        # Create services with mocks
        self.database = DatabaseService(self.temp_db.name)
        self.vector_store = Mock()
        self.embedding_service = Mock()
        
        self.ingestion_service = IngestionService(
            database=self.database,
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            config=self.config
        )
    
    def teardown_method(self):
        """Clean up"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_extract_days_date_from_created_at(self):
        """Test extracting days_date from DataItem.created_at"""
        item = DataItem(
            namespace="limitless",
            source_id="test-123",
            content="Test content",
            metadata={},
            created_at=datetime.fromisoformat("2024-01-15T14:30:00+00:00"),
            updated_at=datetime.now(timezone.utc)
        )
        
        result = self.ingestion_service._extract_days_date(item)
        
        # Should extract date using limitless timezone (America/New_York)
        assert result == "2024-01-15"
    
    def test_extract_days_date_from_metadata_start_time(self):
        """Test extracting days_date from metadata start_time field"""
        item = DataItem(
            namespace="limitless",
            source_id="test-123",
            content="Test content",
            metadata={"start_time": "2024-01-15T14:30:00Z"},
            created_at=None,  # No created_at, should use metadata
            updated_at=datetime.now(timezone.utc)
        )
        
        result = self.ingestion_service._extract_days_date(item)
        assert result == "2024-01-15"
    
    def test_extract_days_date_from_metadata_published_datetime(self):
        """Test extracting days_date from metadata published_datetime_utc field (news style)"""
        item = DataItem(
            namespace="news",
            source_id="test-456",
            content="News content",
            metadata={"published_datetime_utc": "2024-01-15T18:30:00+00:00"},
            created_at=None,
            updated_at=datetime.now(timezone.utc)
        )
        
        result = self.ingestion_service._extract_days_date(item)
        assert result == "2024-01-15"
    
    def test_extract_days_date_no_timestamp(self):
        """Test handling when no timestamp is available"""
        item = DataItem(
            namespace="limitless",
            source_id="test-123",
            content="Test content",
            metadata={},
            created_at=None,
            updated_at=datetime.now(timezone.utc)
        )
        
        result = self.ingestion_service._extract_days_date(item)
        assert result is None
    
    def test_get_user_timezone_for_namespace(self):
        """Test getting correct timezone for different namespaces"""
        # Limitless should use configured timezone
        limitless_tz = self.ingestion_service._get_user_timezone_for_namespace("limitless")
        assert limitless_tz == "America/New_York"
        
        # News should use UTC
        news_tz = self.ingestion_service._get_user_timezone_for_namespace("news")
        assert news_tz == "UTC"
        
        # Unknown namespace should default to UTC
        unknown_tz = self.ingestion_service._get_user_timezone_for_namespace("unknown")
        assert unknown_tz == "UTC"
    
    def test_process_and_store_item_with_days_date(self):
        """Test that _process_and_store_item extracts and stores days_date"""
        from services.ingestion import IngestionResult
        
        # Create test item
        item = DataItem(
            namespace="limitless",
            source_id="test-123",
            content="Test conversation",
            metadata={"start_time": "2024-01-15T14:30:00Z"},
            created_at=datetime.fromisoformat("2024-01-15T14:30:00+00:00"),
            updated_at=datetime.now(timezone.utc)
        )
        
        result = IngestionResult()
        
        # Process and store
        import asyncio
        asyncio.run(self.ingestion_service._process_and_store_item(item, result))
        
        # Verify it was stored with days_date
        stored_items = self.database.get_data_items_by_ids(["limitless:test-123"])
        assert len(stored_items) == 1
        assert stored_items[0]["days_date"] == "2024-01-15"
        assert result.items_processed == 1
        assert result.items_stored == 1


class TestDaysDateIntegration:
    """Integration tests for complete days_date workflow"""
    
    def setup_method(self):
        """Set up integration test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db = DatabaseService(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_calendar_workflow(self):
        """Test complete calendar workflow with real-world data patterns"""
        # Simulate a week of mixed data from different sources
        test_data = [
            # Monday - Limitless conversations
            ("limitless:conv1", "limitless", "conv1", "Morning standup meeting", "2024-01-15"),
            ("limitless:conv2", "limitless", "conv2", "Lunch with colleague", "2024-01-15"),
            
            # Tuesday - Mixed sources
            ("limitless:conv3", "limitless", "conv3", "Project planning session", "2024-01-16"),
            ("news:article1", "news", "article1", "Tech industry news", "2024-01-16"),
            
            # Wednesday - Just news
            ("news:article2", "news", "article2", "Market updates", "2024-01-17"),
            
            # Friday - Busy day
            ("limitless:conv4", "limitless", "conv4", "Team retrospective", "2024-01-19"),
            ("limitless:conv5", "limitless", "conv5", "1:1 with manager", "2024-01-19"),
            ("news:article3", "news", "article3", "Weekend reading", "2024-01-19"),
        ]
        
        # Store all test data
        for item_id, namespace, source_id, content, date in test_data:
            self.db.store_data_item(item_id, namespace, source_id, content, days_date=date)
        
        # Test calendar queries
        
        # 1. Get available dates (for calendar view)
        available_dates = self.db.get_available_dates()
        expected_dates = ["2024-01-19", "2024-01-17", "2024-01-16", "2024-01-15"]
        assert available_dates == expected_dates
        
        # 2. Get busy day details
        friday_items = self.db.get_data_items_by_date("2024-01-19")
        assert len(friday_items) == 3
        friday_content = [item["content"] for item in friday_items]
        assert "Team retrospective" in friday_content
        assert "1:1 with manager" in friday_content
        assert "Weekend reading" in friday_content
        
        # 3. Get work week overview (Mon-Fri)
        work_week = self.db.get_data_items_by_date_range("2024-01-15", "2024-01-19")
        assert len(work_week) == 8  # All items
        
        # 4. Filter by source type
        limitless_only = self.db.get_data_items_by_date_range(
            "2024-01-15", "2024-01-19", namespaces=["limitless"]
        )
        assert len(limitless_only) == 5
        assert all(item["namespace"] == "limitless" for item in limitless_only)
        
        # 5. Check dates with conversations vs news
        limitless_dates = self.db.get_available_dates(namespaces=["limitless"])
        news_dates = self.db.get_available_dates(namespaces=["news"])
        
        assert "2024-01-15" in limitless_dates  # Monday conversations
        assert "2024-01-15" not in news_dates   # No news on Monday
        assert "2024-01-17" not in limitless_dates  # No conversations Wednesday
        assert "2024-01-17" in news_dates      # But news on Wednesday
        
        print("✅ Calendar workflow integration test passed!")


if __name__ == "__main__":
    # Run tests with pytest if available, otherwise run basic tests
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        print("Running basic tests without pytest...")
        
        # Run a few basic tests manually
        test_db = TestDaysDateExtraction()
        test_db.setup_method()
        test_db.test_extract_date_from_utc_z_format()
        test_db.test_extract_date_with_timezone_conversion()
        test_db.teardown_method()
        print("✅ Basic date extraction tests passed")
        
        test_queries = TestDaysDateDatabase()
        test_queries.setup_method()
        test_queries.test_store_data_item_with_days_date()
        test_queries.test_get_data_items_by_date()
        test_queries.teardown_method()
        print("✅ Basic database query tests passed")
        
        print("\n🎉 All basic tests completed successfully!")
        print("📝 Run 'python -m pytest tests/test_days_date.py -v' for full test suite")