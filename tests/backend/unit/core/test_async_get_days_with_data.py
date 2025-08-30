"""
TDD Test for AsyncDatabaseService.get_days_with_data implementation

Following TDD methodology:
RED: Write failing test first
GREEN: Implement to make test pass
REFACTOR: Improve implementation
"""

import pytest
from core.async_database import AsyncDatabaseService
from tests.fixtures.async_database_fixtures import async_temp_db_path


class TestAsyncGetDaysWithData:
    """Test suite for get_days_with_data async implementation"""
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_empty_database(self, async_temp_db_path):
        """RED: Test with empty database should return empty list"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        result = await db_service.get_days_with_data()
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_single_date(self, async_temp_db_path):
        """RED: Test with single date"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store test data for single date
        await db_service.store_data_item(
            "test:001", "test", "001", "Test Content", 
            {"title": "Test Item"}, "2025-01-15"
        )
        
        result = await db_service.get_days_with_data()
        assert result == ["2025-01-15"]
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_multiple_dates(self, async_temp_db_path):
        """RED: Test with multiple dates"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store test data for different dates
        dates = ["2025-01-15", "2025-01-14", "2025-01-13"]
        for i, date in enumerate(dates):
            await db_service.store_data_item(
                f"test:00{i+1}", "test", f"00{i+1}", f"Content {i+1}", 
                {"title": f"Item {i+1}"}, date
            )
        
        result = await db_service.get_days_with_data()
        
        # Should be sorted in descending order (newest first)
        assert len(result) == 3
        assert result == sorted(dates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_namespace_filter(self, async_temp_db_path):
        """RED: Test with namespace filtering"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store test data for different namespaces and dates
        await db_service.store_data_item(
            "news:001", "news", "001", "News Content", {}, "2025-01-15"
        )
        await db_service.store_data_item(
            "weather:001", "weather", "001", "Weather Content", {}, "2025-01-15"
        )
        await db_service.store_data_item(
            "news:002", "news", "002", "News Content 2", {}, "2025-01-14"
        )
        
        # Filter by news namespace only
        result = await db_service.get_days_with_data(["news"])
        assert len(result) == 2
        assert "2025-01-15" in result
        assert "2025-01-14" in result
        
        # Filter by weather namespace only
        result_weather = await db_service.get_days_with_data(["weather"])
        assert result_weather == ["2025-01-15"]
        
        # Filter by both namespaces
        result_both = await db_service.get_days_with_data(["news", "weather"])
        assert len(result_both) == 2
        assert set(result_both) == {"2025-01-15", "2025-01-14"}
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_null_dates_filtered(self, async_temp_db_path):
        """RED: Test that items with NULL days_date are excluded"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store item with valid date
        await db_service.store_data_item(
            "test:001", "test", "001", "Valid Content", {}, "2025-01-15"
        )
        
        # Store item with NULL date (by passing None)
        await db_service.store_data_item(
            "test:002", "test", "002", "Null Date Content", {}, None
        )
        
        result = await db_service.get_days_with_data()
        assert result == ["2025-01-15"]  # Only the item with valid date
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_distinct_dates(self, async_temp_db_path):
        """RED: Test that duplicate dates are deduplicated"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store multiple items with same date
        for i in range(3):
            await db_service.store_data_item(
                f"test:00{i+1}", "test", f"00{i+1}", f"Content {i+1}", 
                {}, "2025-01-15"
            )
        
        result = await db_service.get_days_with_data()
        assert result == ["2025-01-15"]  # Only one instance of the date