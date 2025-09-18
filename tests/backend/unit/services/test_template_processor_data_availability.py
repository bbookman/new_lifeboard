"""
Tests for data availability tracking in TemplateProcessor
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from services.template_processor import TemplateProcessor, TemplateVariable, ResolvedTemplate
from config.models import AppConfig


@pytest.fixture
def mock_repository_factory():
    """Create a mock repository factory"""
    factory = MagicMock()
    
    # Mock data item repository
    mock_data_item_repo = AsyncMock()
    factory.get_data_item_repository.return_value = mock_data_item_repo
    
    # Mock database service
    mock_database = AsyncMock()
    factory.database_service = mock_database
    
    return factory


@pytest.fixture
def mock_config():
    """Create a mock config"""
    config = MagicMock(spec=AppConfig)
    return config


@pytest.fixture
def template_processor(mock_repository_factory, mock_config):
    """Create a TemplateProcessor instance with mocked dependencies"""
    processor = TemplateProcessor(
        repository_factory=mock_repository_factory,
        config=mock_config,
        cache_enabled=False  # Disable caching for tests
    )
    return processor


class TestTemplateProcessorDataAvailability:
    """Test suite for data availability tracking functionality"""

    @pytest.mark.asyncio
    async def test_resolve_template_with_no_data_tracks_missing_variables(self, template_processor):
        """Test that variables with no data are tracked properly"""
        content = "Today's activities: {{LIMITLESS_DAY}}\nNews: {{NEWS_DAY}}"
        
        # Mock repository to return empty data for both variables
        mock_repo = template_processor.data_item_repo
        mock_repo.async_get_data_items_by_date.return_value = []
        
        result = await template_processor.resolve_template(content, "2024-01-01")
        
        # Check that resolved template contains data availability information
        assert isinstance(result, ResolvedTemplate)
        assert len(result.variables_without_data) == 2
        assert len(result.data_availability_messages) == 2
        
        # Check that the correct variables are tracked
        variable_sources = [var.source for var in result.variables_without_data]
        assert "LIMITLESS" in variable_sources
        assert "NEWS" in variable_sources
        
        # Check message content
        messages = result.data_availability_messages
        assert any("limitless" in msg.lower() for msg in messages)
        assert any("news" in msg.lower() for msg in messages)
        assert all("try again soon" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_resolve_template_with_partial_data(self, template_processor):
        """Test that only variables with no data are tracked"""
        content = "Today's activities: {{LIMITLESS_DAY}}\nNews: {{NEWS_DAY}}"
        
        # Mock repository to return data for LIMITLESS but not NEWS
        mock_repo = template_processor.data_item_repo
        
        def mock_get_data_items(date, namespaces):
            if namespaces == ['limitless']:
                return [{'content': 'Had a meeting at 2pm', 'days_date': date}]
            elif namespaces == ['news']:
                return []
            return []
        
        mock_repo.async_get_data_items_by_date.side_effect = mock_get_data_items
        
        result = await template_processor.resolve_template(content, "2024-01-01")
        
        # Check that only NEWS variable is tracked as missing
        assert len(result.variables_without_data) == 1
        assert result.variables_without_data[0].source == "NEWS"
        assert len(result.data_availability_messages) == 1
        assert "news" in result.data_availability_messages[0].lower()

    @pytest.mark.asyncio
    async def test_resolve_template_with_all_data_available(self, template_processor):
        """Test that no missing data is tracked when all variables have data"""
        content = "Today's activities: {{LIMITLESS_DAY}}\nNews: {{NEWS_DAY}}"
        
        # Mock repository to return data for both variables
        mock_repo = template_processor.data_item_repo
        mock_repo.async_get_data_items_by_date.return_value = [
            {'content': 'Some data', 'days_date': '2024-01-01'}
        ]
        
        result = await template_processor.resolve_template(content, "2024-01-01")
        
        # Check that no missing data is tracked
        assert len(result.variables_without_data) == 0
        assert len(result.data_availability_messages) == 0

    @pytest.mark.asyncio
    async def test_resolve_template_with_no_variables(self, template_processor):
        """Test template resolution with no template variables"""
        content = "This is a simple prompt with no template variables."
        
        result = await template_processor.resolve_template(content, "2024-01-01")
        
        # Check that no data availability tracking occurs
        assert len(result.variables_without_data) == 0
        assert len(result.data_availability_messages) == 0
        assert result.resolved_content == content

    def test_generate_data_availability_messages_formats_correctly(self, template_processor):
        """Test that data availability messages are formatted correctly"""
        # Manually set some missing variables
        template_processor._missing_data_variables = [
            TemplateVariable("{{LIMITLESS_DAY}}", "LIMITLESS", "DAY", "{{LIMITLESS_DAY}}"),
            TemplateVariable("{{TWITTER_WEEK}}", "TWITTER", "WEEK", "{{TWITTER_WEEK}}")
        ]
        
        messages = template_processor._generate_data_availability_messages()
        
        assert len(messages) == 2
        assert "No data available for limitless at the moment, try again soon" in messages
        assert "No data available for twitter at the moment, try again soon" in messages

    def test_deduplication_prevents_duplicate_messages(self, template_processor):
        """Test that duplicate variables don't create duplicate messages"""
        # Test tracking duplicate variables
        var = TemplateVariable("{{LIMITLESS_DAY}}", "LIMITLESS", "DAY", "{{LIMITLESS_DAY}}")
        template_processor._missing_data_variables = []
        
        # Track the same variable multiple times
        template_processor._track_missing_data_variable(var)
        template_processor._track_missing_data_variable(var)  # Duplicate
        template_processor._track_missing_data_variable(var)  # Another duplicate
        
        # Should only have one variable tracked
        assert len(template_processor._missing_data_variables) == 1
        
        # Should only generate one message
        messages = template_processor._generate_data_availability_messages()
        assert len(messages) == 1
        assert messages[0] == "No data available for limitless at the moment, try again soon"

    def test_message_deduplication_by_source(self, template_processor):
        """Test that messages are deduplicated by source name"""
        # Create multiple variables with same source but different time ranges
        template_processor._missing_data_variables = [
            TemplateVariable("{{LIMITLESS_DAY}}", "LIMITLESS", "DAY", "{{LIMITLESS_DAY}}"),
            TemplateVariable("{{LIMITLESS_WEEK}}", "LIMITLESS", "WEEK", "{{LIMITLESS_WEEK}}"),
            TemplateVariable("{{LIMITLESS_MONTH}}", "LIMITLESS", "MONTH", "{{LIMITLESS_MONTH}}")
        ]
        
        messages = template_processor._generate_data_availability_messages()
        
        # Should only generate one message for limitless source
        assert len(messages) == 1
        assert messages[0] == "No data available for limitless at the moment, try again soon"

    def test_track_missing_data_variable_accumulates_correctly(self, template_processor):
        """Test that missing data variables are tracked cumulatively"""
        var1 = TemplateVariable("{{LIMITLESS_DAY}}", "LIMITLESS", "DAY", "{{LIMITLESS_DAY}}")
        var2 = TemplateVariable("{{NEWS_DAY}}", "NEWS", "DAY", "{{NEWS_DAY}}")
        
        template_processor._track_missing_data_variable(var1)
        template_processor._track_missing_data_variable(var2)
        
        assert len(template_processor._missing_data_variables) == 2
        assert var1 in template_processor._missing_data_variables
        assert var2 in template_processor._missing_data_variables

    @pytest.mark.asyncio
    async def test_format_data_items_with_no_data_calls_tracking(self, template_processor):
        """Test that _format_data_items calls tracking when no data is available"""
        var = TemplateVariable("{{LIMITLESS_DAY}}", "LIMITLESS", "DAY", "{{LIMITLESS_DAY}}")
        
        result = template_processor._format_data_items([], var)
        
        # Check that the result indicates no data
        assert "[NO_DATA:LIMITLESS_DAY]" in result
        
        # Check that tracking was called
        assert hasattr(template_processor, '_missing_data_variables')
        assert len(template_processor._missing_data_variables) == 1
        assert template_processor._missing_data_variables[0] == var