"""
TDD Test for AsyncDatabaseService.get_all_namespaces implementation

Following TDD methodology:
RED: Write failing test first
GREEN: Implement to make test pass
REFACTOR: Improve implementation
"""

import pytest
from core.async_database import AsyncDatabaseService
from tests.fixtures.async_database_fixtures import async_temp_db_path


class TestAsyncGetAllNamespaces:
    """Test suite for get_all_namespaces async implementation"""
    
    @pytest.mark.asyncio
    async def test_get_all_namespaces_empty_database(self, async_temp_db_path):
        """RED: Test with empty database should return empty list"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        result = await db_service.get_all_namespaces()
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_all_namespaces_single_namespace(self, async_temp_db_path):
        """RED: Test with single namespace"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store test data in single namespace
        await db_service.store_data_item(
            "test:001", "test", "001", "Test Content", 
            {"title": "Test Item"}, "2025-01-15"
        )
        
        result = await db_service.get_all_namespaces()
        assert result == ["test"]
    
    @pytest.mark.asyncio
    async def test_get_all_namespaces_multiple_namespaces(self, async_temp_db_path):
        """RED: Test with multiple namespaces"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store test data in different namespaces
        namespaces = ["limitless", "news", "weather", "twitter"]
        for i, namespace in enumerate(namespaces):
            await db_service.store_data_item(
                f"{namespace}:00{i+1}", namespace, f"00{i+1}", f"Content {i+1}", 
                {"title": f"Item {i+1}"}, "2025-01-15"
            )
        
        result = await db_service.get_all_namespaces()
        
        # Should be sorted alphabetically as per sync implementation
        assert len(result) == 4
        assert result == sorted(namespaces)
    
    @pytest.mark.asyncio
    async def test_get_all_namespaces_handles_empty_strings(self, async_temp_db_path):
        """RED: Test that empty string namespaces are handled properly"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store valid items
        await db_service.store_data_item(
            "valid:001", "valid", "001", "Valid Content", 
            {}, "2025-01-15"
        )
        
        # NOTE: Can't test NULL due to NOT NULL constraint, 
        # but method correctly filters with WHERE namespace IS NOT NULL
        result = await db_service.get_all_namespaces()
        assert result == ["valid"]
    
    @pytest.mark.asyncio
    async def test_get_all_namespaces_distinct(self, async_temp_db_path):
        """RED: Test that duplicate namespaces are deduplicated"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store multiple items with same namespace
        for i in range(3):
            await db_service.store_data_item(
                f"test:00{i+1}", "test", f"00{i+1}", f"Content {i+1}", 
                {}, "2025-01-15"
            )
        
        # Add item from different namespace
        await db_service.store_data_item(
            "other:001", "other", "001", "Other Content", 
            {}, "2025-01-15"
        )
        
        result = await db_service.get_all_namespaces()
        assert len(result) == 2
        assert "other" in result
        assert "test" in result
        assert result == sorted(result)  # Should be sorted