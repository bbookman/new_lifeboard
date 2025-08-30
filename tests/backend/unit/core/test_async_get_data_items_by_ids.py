"""
TDD Test for AsyncDatabaseService.get_data_items_by_ids implementation

Following TDD methodology:
RED: Write failing test first
GREEN: Implement to make test pass
REFACTOR: Improve implementation
"""

import pytest
import tempfile
import os
from core.async_database import AsyncDatabaseService
from tests.fixtures.async_database_fixtures import async_temp_db_path


class TestAsyncGetDataItemsByIds:
    """Test suite for get_data_items_by_ids async implementation"""
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_empty_list(self, async_temp_db_path):
        """RED: Test with empty ID list should return empty list"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        result = await db_service.get_data_items_by_ids([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_single_item(self, async_temp_db_path):
        """RED: Test fetching single item by ID"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store test data
        test_id = "test:001"
        await db_service.store_data_item(
            test_id, "test", "001", "Test Content", 
            {"title": "Test Item"}, "2025-01-15"
        )
        
        # Fetch by ID
        result = await db_service.get_data_items_by_ids([test_id])
        
        assert len(result) == 1
        assert result[0]['id'] == test_id
        assert result[0]['content'] == "Test Content"
        assert result[0]['namespace'] == "test"
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_multiple_items(self, async_temp_db_path):
        """RED: Test fetching multiple items by IDs"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store multiple test items
        test_ids = ["test:001", "test:002", "other:003"]
        for i, test_id in enumerate(test_ids):
            namespace = test_id.split(':')[0]
            await db_service.store_data_item(
                test_id, namespace, f"00{i+1}", f"Content {i+1}", 
                {"title": f"Item {i+1}"}, "2025-01-15"
            )
        
        # Fetch all by IDs
        result = await db_service.get_data_items_by_ids(test_ids)
        
        assert len(result) == 3
        result_ids = [item['id'] for item in result]
        assert all(test_id in result_ids for test_id in test_ids)
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_nonexistent(self, async_temp_db_path):
        """RED: Test fetching non-existent IDs should return empty list"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        result = await db_service.get_data_items_by_ids(["nonexistent:001", "missing:002"])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_partial_match(self, async_temp_db_path):
        """RED: Test mixed existing/non-existing IDs"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store one item
        existing_id = "test:001"
        await db_service.store_data_item(
            existing_id, "test", "001", "Test Content", 
            {"title": "Exists"}, "2025-01-15"
        )
        
        # Query with existing and non-existing IDs
        result = await db_service.get_data_items_by_ids([existing_id, "missing:002"])
        
        assert len(result) == 1
        assert result[0]['id'] == existing_id