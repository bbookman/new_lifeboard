"""
LLM Service Workflow Tests for Summary Generation

Test-Driven Development (TDD) tests for the complete user-defined summary
prompt workflow, including data aggregation from multiple namespaces
and LLM unavailable scenarios.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from services.llm_service import LLMService, LLMGenerationResult
from services.document_service import DocumentService
from services.template_processor import TemplateProcessor
from core.database import DatabaseService
from llm.base import LLMResponse, LLMError
from llm.factory import LLMProviderFactory
from config.models import AppConfig


class TestLLMServiceSummaryWorkflow:
    """Test LLM Service complete summary generation workflow"""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all LLM service dependencies"""
        database = Mock(spec=DatabaseService)
        document_service = Mock(spec=DocumentService)
        config = Mock(spec=AppConfig)
        config.llm_provider = Mock()
        config.llm_provider.provider_type = Mock()
        config.llm_provider.provider_type.value = "ollama"
        
        # Mock database connection context
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.commit = Mock()
        
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        database.get_connection.return_value = mock_context
        
        return database, document_service, config, mock_cursor

    @pytest.fixture
    def sample_multi_namespace_data(self):
        """Sample data from multiple namespaces for a given date"""
        return {
            "news_data": [
                {
                    "title": "AI Revolution Continues",
                    "snippet": "New breakthrough in machine learning announced"
                },
                {
                    "title": "Tech Market Update", 
                    "snippet": "Technology stocks show strong performance"
                }
            ],
            "twitter_data": [
                {
                    "content": "Exciting day learning about new AI developments! #tech #AI"
                },
                {
                    "content": "Just finished reading about quantum computing applications"
                }
            ],
            "limitless_data": [
                {
                    "processed_content": "Meeting Summary: Discussed Q1 product roadmap and resource allocation"
                },
                {
                    "processed_content": "Call Notes: Customer feedback session revealed positive sentiment"
                }
            ],
            "weather_data": {
                "response_json": json.dumps({
                    "data": [{
                        "weather": "partly cloudy",
                        "temperature": 22,
                        "conditions": "Pleasant day for outdoor activities"
                    }]
                })
            }
        }

    async def test_generate_daily_summary_with_user_defined_prompt(self, mock_dependencies, sample_multi_namespace_data):
        """Test complete summary generation with user-defined prompt and multi-namespace data"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock prompt settings and document retrieval
        mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "user-prompt-123"},  # Prompt setting
            sample_multi_namespace_data["weather_data"],  # Weather data
            None  # End of fetchone calls
        ]
        
        # Mock news and limitless data queries
        mock_cursor.fetchall.side_effect = [
            sample_multi_namespace_data["news_data"],  # News items
            sample_multi_namespace_data["limitless_data"]  # Limitless activities
        ]
        
        # Mock user-defined prompt document
        user_prompt_doc = Mock()
        user_prompt_doc.content_md = "Create a comprehensive daily summary for {{DATE}} including highlights from news, activities, and weather. Focus on: {{USER_CONTEXT}}"
        document_service.get_document.return_value = user_prompt_doc
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = "Create a comprehensive daily summary for 2024-01-15 including highlights from news, activities, and weather. Focus on technology and productivity"
        resolved_template.errors = []
        resolved_template.variables_resolved = ["DATE", "USER_CONTEXT"]
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM provider
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_response = LLMResponse(
            content="Daily Summary for 2024-01-15:\n\n**Technology Highlights:**\n- AI Revolution continues with new ML breakthrough\n- Tech stocks performing well\n\n**Activities:**\n- Productive Q1 planning meeting\n- Positive customer feedback session\n\n**Weather:** Pleasant 22°C, partly cloudy - perfect for outdoor activities\n\n**Social Insights:**\n- Active learning about AI and quantum computing\n\n**Overall Theme:** Technology-focused day with strong productivity",
            model="llama2",
            provider="ollama", 
            usage={"total_tokens": 250}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Create service and inject mocks
        service = LLMService(database, document_service, config)
        service.llm_provider = mock_llm_provider
        service.template_processor = mock_template_processor
        
        # Test summary generation
        result = await service.generate_daily_summary("2024-01-15")
        
        # Verify successful generation
        assert result.success is True
        assert "Daily Summary for 2024-01-15:" in result.content
        assert "AI Revolution continues" in result.content
        assert "Q1 planning meeting" in result.content
        assert "22°C, partly cloudy" in result.content
        assert "quantum computing" in result.content
        assert result.generation_time > 0
        assert result.model_info["model"] == "llama2"
        assert result.model_info["provider"] == "ollama"
        
        # Verify template resolution was called
        mock_template_processor.resolve_template.assert_called_once()
        
        # Verify LLM generation was called with resolved prompt
        mock_llm_provider.generate_response.assert_called_once()
        call_args = mock_llm_provider.generate_response.call_args[0][0]
        assert "Create a comprehensive daily summary for 2024-01-15" in call_args

    async def test_generate_daily_summary_no_llm_provider_configured(self, mock_dependencies):
        """Test summary generation when no LLM provider is configured"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Create service without LLM provider
        service = LLMService(database, document_service, config)
        service.llm_provider = None
        
        # Test generation attempt
        result = await service.generate_daily_summary("2024-01-15")
        
        # Verify failure result
        assert result.success is False
        assert "No LLM provider available" in result.error_message
        assert result.content == ""
        assert result.generation_time == 0

    async def test_generate_daily_summary_no_data_available(self, mock_dependencies):
        """Test summary generation when no data exists for the given date"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock empty data responses
        mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "prompt-123"},  # Prompt setting
            None,  # No weather data
            None   # End of fetchone calls  
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # No news items
            []   # No limitless activities
        ]
        
        # Mock prompt document
        user_prompt_doc = Mock()
        user_prompt_doc.content_md = "Generate summary for {{DATE}}"
        document_service.get_document.return_value = user_prompt_doc
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = "Generate summary for 2024-01-15"
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM provider response for no data
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_response = LLMResponse(
            content="No significant data available to summarize for 2024-01-15. This appears to be a quiet day with minimal recorded activities.",
            model="llama2",
            provider="ollama",
            usage={"total_tokens": 50}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Create service and inject mocks
        service = LLMService(database, document_service, config)
        service.llm_provider = mock_llm_provider
        service.template_processor = mock_template_processor
        
        # Test generation
        result = await service.generate_daily_summary("2024-01-15")
        
        # Verify generation succeeded but indicates no data
        assert result.success is True
        assert "No significant data available" in result.content
        assert "quiet day" in result.content

    async def test_generate_daily_summary_no_prompt_defined(self, mock_dependencies):
        """Test summary generation when user has not defined a summary prompt"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock no prompt setting configured
        mock_cursor.fetchone.side_effect = [
            None,  # No prompt setting
            None   # No weather data
        ]
        mock_cursor.fetchall.side_effect = [[], []]  # No data
        
        # Create service
        service = LLMService(database, document_service, config)
        service.llm_provider = AsyncMock()
        service.llm_provider.is_available.return_value = True
        
        # Test generation
        result = await service.generate_daily_summary("2024-01-15")
        
        # Verify failure due to no prompt
        assert result.success is False
        assert "No summary prompt configured" in result.error_message or "prompt" in result.error_message.lower()

    async def test_cached_summary_retrieval_and_storage(self, mock_dependencies):
        """Test caching behavior for generated summaries"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Test cache retrieval
        mock_cursor.fetchone.return_value = {
            "content": "Cached summary content from previous generation",
            "prompt_used": "Previous prompt",
            "created_at": "2024-01-15T10:00:00Z"
        }
        
        service = LLMService(database, document_service, config)
        
        # Test getting cached summary
        cached = await service.get_cached_summary("2024-01-15")
        
        assert cached == "Cached summary content from previous generation"
        
        # Test cache miss
        mock_cursor.fetchone.return_value = None
        cached_miss = await service.get_cached_summary("2024-01-16")
        
        assert cached_miss is None

    async def test_generate_daily_summary_with_force_regenerate(self, mock_dependencies, sample_multi_namespace_data):
        """Test force regeneration bypasses cache and creates new summary"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock existing cached content
        mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "prompt-123"},  # Prompt setting
            sample_multi_namespace_data["weather_data"],  # Weather
            None
        ]
        mock_cursor.fetchall.side_effect = [
            sample_multi_namespace_data["news_data"],
            sample_multi_namespace_data["limitless_data"]
        ]
        
        # Mock prompt and template
        user_prompt_doc = Mock()
        user_prompt_doc.content_md = "Updated prompt for {{DATE}}"
        document_service.get_document.return_value = user_prompt_doc
        
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = "Updated prompt for 2024-01-15"
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM provider
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_response = LLMResponse(
            content="Newly generated summary with latest prompt and data",
            model="llama2",
            provider="ollama",
            usage={"total_tokens": 150}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Create service
        service = LLMService(database, document_service, config)
        service.llm_provider = mock_llm_provider
        service.template_processor = mock_template_processor
        
        # Test force regeneration
        result = await service.generate_daily_summary("2024-01-15", force_regenerate=True)
        
        # Should generate new content regardless of cache
        assert result.success is True
        assert "Newly generated summary" in result.content
        
        # Verify LLM was called for generation
        mock_llm_provider.generate_response.assert_called_once()

    async def test_generate_daily_summary_llm_error_handling(self, mock_dependencies):
        """Test handling of LLM generation errors"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock basic setup
        mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "prompt-123"},
            None
        ]
        mock_cursor.fetchall.side_effect = [[], []]
        
        # Mock prompt
        user_prompt_doc = Mock()
        user_prompt_doc.content_md = "Test prompt"
        document_service.get_document.return_value = user_prompt_doc
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = "Test prompt"
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM provider that raises error
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_provider.generate_response.side_effect = LLMError("Model timeout error")
        
        # Create service
        service = LLMService(database, document_service, config)
        service.llm_provider = mock_llm_provider
        service.template_processor = mock_template_processor
        
        # Test generation with error
        result = await service.generate_daily_summary("2024-01-15")
        
        # Verify error is handled gracefully
        assert result.success is False
        assert "timeout" in result.error_message.lower() or "error" in result.error_message.lower()

    async def test_build_daily_context_multi_namespace_aggregation(self, mock_dependencies, sample_multi_namespace_data):
        """Test _build_daily_context correctly aggregates data from all namespaces"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock database queries for all namespaces
        mock_cursor.fetchall.side_effect = [
            sample_multi_namespace_data["news_data"],  # News
            sample_multi_namespace_data["limitless_data"]  # Limitless
        ]
        mock_cursor.fetchone.return_value = sample_multi_namespace_data["weather_data"]
        
        # Create service
        service = LLMService(database, document_service, config)
        
        # Test context building
        context = await service._build_daily_context("2024-01-15")
        
        # Verify all data types are included
        assert "Date: 2024-01-15" in context
        assert "News Headlines:" in context
        assert "AI Revolution Continues" in context
        assert "Tech Market Update" in context
        assert "Activities:" in context
        assert "Q1 product roadmap" in context
        assert "Customer feedback session" in context
        assert "Weather:" in context
        assert "partly cloudy" in context
        assert "22" in context

    async def test_summary_storage_after_generation(self, mock_dependencies):
        """Test that generated summaries are properly stored in database"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock successful generation setup
        mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "prompt-123"},
            None
        ]
        mock_cursor.fetchall.side_effect = [[], []]
        
        # Mock prompt
        user_prompt_doc = Mock()
        user_prompt_doc.content_md = "Test prompt"
        document_service.get_document.return_value = user_prompt_doc
        
        # Mock template processor
        mock_template_processor = Mock()
        resolved_template = Mock()
        resolved_template.resolved_content = "Resolved test prompt"
        resolved_template.errors = []
        mock_template_processor.resolve_template.return_value = resolved_template
        
        # Mock LLM response
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_response = LLMResponse(
            content="Generated summary content",
            model="test-model",
            provider="ollama",
            usage={"total_tokens": 100}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Create service
        service = LLMService(database, document_service, config)
        service.llm_provider = mock_llm_provider
        service.template_processor = mock_template_processor
        
        # Test generation (which should trigger storage)
        result = await service.generate_daily_summary("2024-01-15")
        
        # Verify generation succeeded
        assert result.success is True
        
        # Verify database execute was called for storage (INSERT or REPLACE)
        # The exact SQL will vary, but should include INSERT/REPLACE into generated_summaries
        execute_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        storage_calls = [call for call in execute_calls if "generated_summaries" in call and ("INSERT" in call or "REPLACE" in call)]
        assert len(storage_calls) > 0, "Summary should be stored in database after generation"


class TestLLMServicePromptManagement:
    """Test prompt management functionality in LLM Service"""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock dependencies for prompt management tests"""
        database = Mock(spec=DatabaseService)
        document_service = Mock(spec=DocumentService)
        config = Mock(spec=AppConfig)
        config.llm_provider = Mock()
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        database.get_connection.return_value = mock_context
        
        return database, document_service, config, mock_cursor

    async def test_prompt_setting_retrieval(self, mock_dependencies):
        """Test retrieval of user-defined prompt settings"""
        database, document_service, config, mock_cursor = mock_dependencies
        
        # Mock prompt setting in database
        mock_cursor.fetchone.return_value = {
            "prompt_document_id": "user-prompt-456",
            "is_active": True,
            "created_at": "2024-01-10T09:00:00Z"
        }
        
        service = LLMService(database, document_service, config)
        
        # This is tested implicitly in generate_daily_summary, but we can verify
        # the query pattern by checking the SQL calls made
        result = await service.generate_daily_summary("2024-01-15")
        
        # Check that prompt_settings was queried
        execute_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        prompt_queries = [call for call in execute_calls if "prompt_settings" in call and "daily_summary_prompt" in call]
        assert len(prompt_queries) > 0, "Should query for daily_summary_prompt setting"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])