"""
TDD Test for AsyncDatabaseService.get_markdown_by_date implementation

Following TDD methodology:
RED: Write failing test first
GREEN: Implement to make test pass
REFACTOR: Improve implementation

Note: This is a complex method with ~150 lines of fallback logic
"""

import pytest
from core.async_database import AsyncDatabaseService
from tests.fixtures.async_database_fixtures import async_temp_db_path


class TestAsyncGetMarkdownByDate:
    """Test suite for get_markdown_by_date async implementation"""
    
    @pytest.mark.asyncio
    async def test_get_markdown_by_date_empty_database(self, async_temp_db_path):
        """RED: Test with empty database should return fallback content"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        result = await db_service.get_markdown_by_date("2025-01-15")
        
        # Should return fallback content for date with no data
        assert "# 2025-01-15" in result
        assert "No data available for this date" in result
    
    @pytest.mark.asyncio
    async def test_get_markdown_by_date_simple_content(self, async_temp_db_path):
        """RED: Test with simple content, should construct from title and content"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store simple item with title
        await db_service.store_data_item(
            "test:001", "test", "001", "This is test content", 
            {"title": "Test Entry"}, "2025-01-15"
        )
        
        result = await db_service.get_markdown_by_date("2025-01-15")
        
        # Should construct markdown from title and content
        assert "# Test Entry" in result
        assert "This is test content" in result
    
    @pytest.mark.asyncio
    async def test_get_markdown_by_date_with_cleaned_markdown(self, async_temp_db_path):
        """RED: Test with cleaned_markdown in metadata (highest priority)"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store item with cleaned_markdown (highest priority fallback)
        await db_service.store_data_item(
            "test:001", "test", "001", "Original content", 
            {
                "title": "Test Entry",
                "cleaned_markdown": "# Test Entry\n\nThis is cleaned markdown content."
            }, 
            "2025-01-15"
        )
        
        result = await db_service.get_markdown_by_date("2025-01-15")
        
        # Should use cleaned_markdown directly
        assert "This is cleaned markdown content." in result
        assert "Original content" not in result  # Should not fallback to content
    
    @pytest.mark.asyncio
    async def test_get_markdown_by_date_multiple_items(self, async_temp_db_path):
        """RED: Test with multiple items, should combine with separators"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store multiple items for same date
        await db_service.store_data_item(
            "test:001", "test", "001", "First content", 
            {"title": "First Entry"}, "2025-01-15"
        )
        await db_service.store_data_item(
            "test:002", "test", "002", "Second content", 
            {"title": "Second Entry"}, "2025-01-15"
        )
        
        result = await db_service.get_markdown_by_date("2025-01-15")
        
        # Should combine multiple items with separators
        assert "# First Entry" in result
        assert "# Second Entry" in result
        assert "---" in result  # Separator between items
        assert "First content" in result
        assert "Second content" in result