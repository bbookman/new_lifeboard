"""
Test TemplateProcessor Repository Migration

Tests that TemplateProcessor properly uses RepositoryFactory instead of direct DatabaseService access
and maintains backward compatibility.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from services.template_processor import TemplateProcessor
from core.repositories.repository_factory import RepositoryFactory
from core.repositories.data_item_repository import DataItemRepository
from core.database import DatabaseService
from config.models import AppConfig


@pytest.fixture
def mock_database_service():
    """Mock DatabaseService for testing"""
    mock_db = Mock(spec=DatabaseService)
    mock_db.get_async_connection = AsyncMock()
    return mock_db


@pytest.fixture
def mock_data_item_repository():
    """Mock DataItemRepository for testing"""
    mock_repo = Mock(spec=DataItemRepository)
    mock_repo.async_get_data_items_by_date = AsyncMock()
    mock_repo.async_get_data_items_by_date_range = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_repository_factory(mock_database_service, mock_data_item_repository):
    """Mock RepositoryFactory for testing"""
    mock_factory = Mock(spec=RepositoryFactory)
    mock_factory.database_service = mock_database_service
    mock_factory.get_data_item_repository.return_value = mock_data_item_repository
    return mock_factory


@pytest.fixture
def mock_config():
    """Mock AppConfig for testing"""
    config = Mock(spec=AppConfig)
    config.limitless = Mock()
    config.limitless.timezone = "America/New_York"
    return config


@pytest.fixture
def template_processor(mock_repository_factory, mock_config):
    """Create TemplateProcessor instance for testing"""
    processor = TemplateProcessor(
        repository_factory=mock_repository_factory,
        config=mock_config
    )
    return processor


class TestTemplateProcessorRepositoryMigration:
    """Test suite for TemplateProcessor repository migration"""
    
    def test_initialization_with_repository_factory(self, template_processor, mock_repository_factory):
        """Test that TemplateProcessor initializes correctly with RepositoryFactory"""
        # Verify repository factory is stored
        assert template_processor.repository_factory == mock_repository_factory
        
        # Verify repository instances are created
        assert template_processor.data_item_repo is not None
        
        # Verify backward compatibility - database service is still accessible
        assert template_processor.database == mock_repository_factory.database_service
        
        # Verify factory methods were called
        mock_repository_factory.get_data_item_repository.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_day_template_uses_data_item_repository(self, template_processor, mock_data_item_repository, mock_config):
        """Test that resolving DAY templates uses DataItemRepository"""
        # Mock data items for DAY query
        test_data = [
            {"id": "limitless:123", "content": "Test content", "days_date": "2025-09-17"}
        ]
        mock_data_item_repository.async_get_data_items_by_date.return_value = test_data
        
        # Test template content
        content = "Here is today's data: {{LIMITLESS_DAY}}"
        
        # Mock template cache methods to avoid direct database calls
        with patch.object(template_processor, '_get_cached_result', return_value=None), \
             patch.object(template_processor, '_cache_result', return_value=None), \
             patch.object(template_processor, '_cleanup_expired_cache', return_value=None):
            
            # Resolve template
            result = await template_processor.resolve_template(content, "2025-09-17")
            
            # Verify repository method was called with correct parameters
            mock_data_item_repository.async_get_data_items_by_date.assert_called_once_with(
                "2025-09-17", 
                namespaces=["limitless"]
            )
            
            # Verify template was resolved
            assert result.variables_resolved == 1
            assert "[2025-09-17] Test content" in result.resolved_content
    
    @pytest.mark.asyncio
    async def test_resolve_week_template_uses_data_item_repository(self, template_processor, mock_data_item_repository):
        """Test that resolving WEEK templates uses DataItemRepository"""
        # Mock data items for WEEK query
        test_data = [
            {"id": "limitless:123", "content": "Week content 1", "days_date": "2025-09-17"},
            {"id": "limitless:124", "content": "Week content 2", "days_date": "2025-09-16"}
        ]
        mock_data_item_repository.async_get_data_items_by_date_range.return_value = test_data
        
        # Test template content
        content = "Here is this week's data: {{LIMITLESS_WEEK}}"
        
        # Mock template cache methods to avoid direct database calls
        with patch.object(template_processor, '_get_cached_result', return_value=None), \
             patch.object(template_processor, '_cache_result', return_value=None), \
             patch.object(template_processor, '_cleanup_expired_cache', return_value=None):
            
            # Resolve template
            result = await template_processor.resolve_template(content, "2025-09-17")
            
            # Verify repository method was called with correct date range
            mock_data_item_repository.async_get_data_items_by_date_range.assert_called_once()
            call_args = mock_data_item_repository.async_get_data_items_by_date_range.call_args
            
            # Check that start_date is 6 days before target_date and end_date is target_date
            assert call_args[0][0] == "2025-09-11"  # 6 days before 2025-09-17
            assert call_args[0][1] == "2025-09-17"  # target date
            assert call_args[1]["namespaces"] == ["limitless"]
            
            # Verify template was resolved
            assert result.variables_resolved == 1
            assert "Week content 1" in result.resolved_content
            assert "Week content 2" in result.resolved_content
    
    @pytest.mark.asyncio
    async def test_resolve_month_template_uses_data_item_repository(self, template_processor, mock_data_item_repository):
        """Test that resolving MONTH templates uses DataItemRepository"""
        # Mock data items for MONTH query
        test_data = [
            {"id": "news:123", "content": "Month content", "days_date": "2025-09-17"}
        ]
        mock_data_item_repository.async_get_data_items_by_date_range.return_value = test_data
        
        # Test template content
        content = "Here is this month's news: {{NEWS_MONTH}}"
        
        # Mock template cache methods to avoid direct database calls
        with patch.object(template_processor, '_get_cached_result', return_value=None), \
             patch.object(template_processor, '_cache_result', return_value=None), \
             patch.object(template_processor, '_cleanup_expired_cache', return_value=None):
            
            # Resolve template
            result = await template_processor.resolve_template(content, "2025-09-17")
            
            # Verify repository method was called with correct date range (first of month to target)
            mock_data_item_repository.async_get_data_items_by_date_range.assert_called_once()
            call_args = mock_data_item_repository.async_get_data_items_by_date_range.call_args
            
            # Check that start_date is first of month and end_date is target_date
            assert call_args[0][0] == "2025-09-01"  # First of September
            assert call_args[0][1] == "2025-09-17"  # target date
            assert call_args[1]["namespaces"] == ["news"]
            
            # Verify template was resolved
            assert result.variables_resolved == 1
            assert "Month content" in result.resolved_content
    
    @pytest.mark.asyncio
    async def test_multiple_templates_use_repository(self, template_processor, mock_data_item_repository):
        """Test that multiple templates in one content use repository correctly"""
        # Mock different data for different queries
        limitless_data = [{"id": "limitless:123", "content": "Limitless today", "days_date": "2025-09-17"}]
        twitter_data = [{"id": "twitter:456", "content": "Twitter today", "days_date": "2025-09-17"}]
        
        async def mock_get_by_date(date, namespaces):
            if namespaces == ["limitless"]:
                return limitless_data
            elif namespaces == ["twitter"]:
                return twitter_data
            return []
            
        mock_data_item_repository.async_get_data_items_by_date.side_effect = mock_get_by_date
        
        # Test template content with multiple variables
        content = "Limitless: {{LIMITLESS_DAY}} Twitter: {{TWITTER_DAY}}"
        
        # Mock template cache methods to avoid direct database calls
        with patch.object(template_processor, '_get_cached_result', return_value=None), \
             patch.object(template_processor, '_cache_result', return_value=None), \
             patch.object(template_processor, '_cleanup_expired_cache', return_value=None):
            
            # Resolve template
            result = await template_processor.resolve_template(content, "2025-09-17")
            
            # Verify repository method was called twice with different namespaces
            assert mock_data_item_repository.async_get_data_items_by_date.call_count == 2
            
            # Check call arguments
            calls = mock_data_item_repository.async_get_data_items_by_date.call_args_list
            limitless_call = next(call for call in calls if call[1]["namespaces"] == ["limitless"])
            twitter_call = next(call for call in calls if call[1]["namespaces"] == ["twitter"])
            
            assert limitless_call[0][0] == "2025-09-17"
            assert twitter_call[0][0] == "2025-09-17"
            
            # Verify both templates were resolved
            assert result.variables_resolved == 2
            assert "Limitless today" in result.resolved_content
            assert "Twitter today" in result.resolved_content
    
    def test_backward_compatibility_database_access(self, template_processor, mock_repository_factory):
        """Test that direct database access is still available for backward compatibility"""
        # Verify database service is accessible for template cache operations
        assert template_processor.database == mock_repository_factory.database_service
        
        # This ensures that template cache operations can still access database directly
        assert hasattr(template_processor, 'database')
        assert template_processor.database is not None
    
    def test_template_parsing_still_works(self, template_processor):
        """Test that template parsing functionality is unchanged"""
        content = "Test {{LIMITLESS_DAY}} and {{NEWS_WEEK}} and {{TWITTER_MONTH}}"
        
        variables = template_processor.parse_template_variables(content)
        
        assert len(variables) == 3
        assert variables[0].source == "LIMITLESS"
        assert variables[0].time_range == "DAY"
        assert variables[1].source == "NEWS"
        assert variables[1].time_range == "WEEK"
        assert variables[2].source == "TWITTER"
        assert variables[2].time_range == "MONTH"
    
    def test_template_validation_still_works(self, template_processor):
        """Test that template validation functionality is unchanged"""
        content = "Test {{LIMITLESS_DAY}}"
        
        validation = template_processor.validate_template(content)
        
        assert validation["is_valid"]
        assert validation["total_variables"] == 1
        assert len(validation["valid_variables"]) == 1
        assert "{{LIMITLESS_DAY}}" in validation["valid_variables"]
        assert len(validation["invalid_variables"]) == 0
        assert "LIMITLESS" in validation["supported_sources"]
        assert "DAY" in validation["supported_time_ranges"]


if __name__ == "__main__":
    pytest.main([__file__])