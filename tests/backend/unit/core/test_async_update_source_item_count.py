"""
TDD Test for AsyncDatabaseService.update_source_item_count implementation

Following TDD methodology:
RED: Write failing test first
GREEN: Implement to make test pass
REFACTOR: Improve implementation
"""

import pytest
from core.async_database import AsyncDatabaseService
from tests.fixtures.async_database_fixtures import async_temp_db_path


class TestAsyncUpdateSourceItemCount:
    """Test suite for update_source_item_count async implementation"""
    
    @pytest.mark.asyncio
    async def test_update_source_item_count_empty_namespace(self, async_temp_db_path):
        """RED: Test with namespace that has no items should return 0"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Register a data source but don't add any items
        await db_service.register_data_source("empty", "test_source")
        
        result = await db_service.update_source_item_count("empty")
        assert result == 0
        
        # Verify the count was updated in data_sources table
        count_result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?", 
            ("empty",)
        )
        assert count_result['item_count'] == 0
    
    @pytest.mark.asyncio
    async def test_update_source_item_count_single_item(self, async_temp_db_path):
        """RED: Test with namespace that has one item"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Register data source and add one item
        await db_service.register_data_source("test", "test_source")
        await db_service.store_data_item(
            "test:001", "test", "001", "Test Content", 
            {"title": "Test Item"}, "2025-01-15"
        )
        
        result = await db_service.update_source_item_count("test")
        assert result == 1
        
        # Verify the count was updated in data_sources table
        count_result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?", 
            ("test",)
        )
        assert count_result['item_count'] == 1
    
    @pytest.mark.asyncio
    async def test_update_source_item_count_multiple_items(self, async_temp_db_path):
        """RED: Test with namespace that has multiple items"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Register data source and add multiple items
        await db_service.register_data_source("multi", "test_source")
        for i in range(5):
            await db_service.store_data_item(
                f"multi:00{i+1}", "multi", f"00{i+1}", f"Content {i+1}", 
                {"title": f"Item {i+1}"}, "2025-01-15"
            )
        
        result = await db_service.update_source_item_count("multi")
        assert result == 5
        
        # Verify the count was updated in data_sources table
        count_result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?", 
            ("multi",)
        )
        assert count_result['item_count'] == 5
    
    @pytest.mark.asyncio
    async def test_update_source_item_count_nonexistent_namespace(self, async_temp_db_path):
        """RED: Test with namespace that doesn't exist in data_sources"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Don't register the namespace but try to update its count
        result = await db_service.update_source_item_count("nonexistent")
        assert result == 0
    
    @pytest.mark.asyncio
    async def test_update_source_item_count_after_deletion(self, async_temp_db_path):
        """RED: Test that count decreases when items are deleted"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Register data source and add items
        await db_service.register_data_source("dynamic", "test_source")
        await db_service.store_data_item(
            "dynamic:001", "dynamic", "001", "Content 1", {}, "2025-01-15"
        )
        await db_service.store_data_item(
            "dynamic:002", "dynamic", "002", "Content 2", {}, "2025-01-15"
        )
        
        # Initial count should be 2
        result1 = await db_service.update_source_item_count("dynamic")
        assert result1 == 2
        
        # Delete one item manually (simulating deletion)
        await db_service.execute_query(
            "DELETE FROM data_items WHERE id = ?", ("dynamic:001",)
        )
        
        # Count should now be 1
        result2 = await db_service.update_source_item_count("dynamic")
        assert result2 == 1
        
        # Verify the count was updated in data_sources table
        count_result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?", 
            ("dynamic",)
        )
        assert count_result['item_count'] == 1