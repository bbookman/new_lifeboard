"""
Test suite for LLMService with Enhanced Debug Logging capabilities.
"""

import pytest
import logging
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from services.llm_service import LLMService, LLMGenerationResult
from services.debug_mixin import ServiceDebugMixin
from core.base_service import BaseService
from llm.base import LLMResponse


class TestLLMServiceDebugIntegration:
    """Test LLMService enhanced debug logging integration."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_database = Mock()
        self.mock_document_service = Mock()
        self.mock_config = Mock()
        self.mock_config.llm_provider = Mock()
        self.mock_config.llm_provider.provider_type = Mock()
        self.mock_config.llm_provider.provider_type.value = "ollama"
        
        # Mock database connection
        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_conn.execute.return_value = self.mock_cursor
        self.mock_conn.commit = Mock()
        
        self.mock_context = Mock()
        self.mock_context.__enter__ = Mock(return_value=self.mock_conn)
        self.mock_context.__exit__ = Mock(return_value=False)
        self.mock_database.get_connection.return_value = self.mock_context

    def test_llm_service_inherits_debug_mixin(self):
        """Test that LLMService properly inherits from both BaseService and ServiceDebugMixin."""
        llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
        
        # Verify inheritance
        assert isinstance(llm_service, BaseService)
        assert isinstance(llm_service, ServiceDebugMixin)
        assert hasattr(llm_service, 'log_service_call')
        assert hasattr(llm_service, 'log_database_operation')
        assert hasattr(llm_service, 'log_external_api_call')
        assert hasattr(llm_service, 'service_name')
        
        # Verify service name
        assert llm_service.service_name == "llm_service"

    def test_initialization_logging(self, caplog):
        """Test that service initialization is logged with proper parameters."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
        
        # Check for initialization log
        log_messages = [record.message for record in caplog.records]
        assert any("SERVICE_CALL llm_service.__init__" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_initialize_service_logging(self, caplog):
        """Test that service initialization is logged with performance metrics."""
        # Mock LLM provider and factory
        mock_llm_provider = AsyncMock()
        mock_llm_provider.provider_name = "test_provider"
        mock_llm_provider.is_available.return_value = True
        mock_llm_provider.get_models.return_value = ["model1", "model2"]
        
        mock_factory = Mock()
        mock_factory.get_active_provider = AsyncMock(return_value=mock_llm_provider)
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
            llm_service.llm_factory = mock_factory
            
            result = await llm_service._initialize_service()
        
        # Verify initialization succeeded
        assert result is True
        assert llm_service.llm_provider == mock_llm_provider
        
        # Check logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log service call
        assert any("SERVICE_CALL llm_service._initialize_service" in msg for msg in log_messages)
        
        # Should log performance metrics
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        assert any("llm_provider_init_duration" in msg for msg in metric_logs)
        assert any("llm_connectivity_test_duration" in msg for msg in metric_logs)
        assert any("llm_available_models" in msg for msg in metric_logs)

    @pytest.mark.asyncio
    async def test_get_cached_summary_logging(self, caplog):
        """Test that cached summary retrieval is logged correctly."""
        # Mock database response
        self.mock_cursor.fetchone.return_value = {
            'content': 'Test cached summary content'
        }
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
            result = await llm_service.get_cached_summary("2024-01-15")
        
        # Verify result
        assert result == 'Test cached summary content'
        
        # Check logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log service call
        assert any("SERVICE_CALL llm_service.get_cached_summary" in msg for msg in log_messages)
        
        # Should log database operation
        assert any("DB_OPERATION SELECT" in msg for msg in log_messages)
        
        # Should log cache hit
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        assert any("llm_cache_hit" in msg for msg in metric_logs)

    @pytest.mark.asyncio
    async def test_get_cached_summary_cache_miss(self, caplog):
        """Test cache miss logging."""
        # Mock no result
        self.mock_cursor.fetchone.return_value = None
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
            result = await llm_service.get_cached_summary("2024-01-15")
        
        # Verify no result
        assert result is None
        
        # Check cache miss logging
        log_messages = [record.message for record in caplog.records]
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        assert any("llm_cache_miss" in msg for msg in metric_logs)

    @pytest.mark.asyncio
    async def test_generate_daily_summary_logging(self, caplog):
        """Test that daily summary generation is comprehensively logged."""
        # Mock LLM provider
        mock_llm_provider = AsyncMock()
        mock_llm_provider.provider_name = "test_provider"
        mock_llm_provider.is_available.return_value = True
        
        mock_llm_response = LLMResponse(
            content="Generated summary content",
            model="test-model",
            provider="test-provider",
            usage={"total_tokens": 150}
        )
        mock_llm_provider.generate_response.return_value = mock_llm_response
        
        # Mock prompt retrieval
        mock_document = Mock()
        mock_document.id = "prompt-123"
        mock_document.document_type = "prompt"
        mock_document.content_md = "Generate a summary for {date}"
        
        # Mock template processor
        mock_resolved_template = Mock()
        mock_resolved_template.resolved_content = "Generate a summary for 2024-01-15"
        mock_resolved_template.errors = []
        mock_resolved_template.variables_resolved = ["date"]
        
        # Mock database queries for context
        self.mock_cursor.fetchone.side_effect = [
            {"prompt_document_id": "prompt-123"},  # Prompt setting
            None,  # Weather data
        ]
        self.mock_cursor.fetchall.side_effect = [
            [{"title": "News 1", "snippet": "Test news"}],  # News items
            [{"processed_content": "Test activity content"}]  # Activities
        ]
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
            llm_service.llm_provider = mock_llm_provider
            llm_service.document_service.get_document.return_value = mock_document
            llm_service.template_processor.resolve_template.return_value = mock_resolved_template
            
            result = await llm_service.generate_daily_summary("2024-01-15")
        
        # Verify successful generation
        assert result.success is True
        assert result.content == "Generated summary content"
        assert result.generation_time > 0
        
        # Check comprehensive logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log main service call
        assert any("SERVICE_CALL llm_service.generate_daily_summary" in msg for msg in log_messages)
        
        # Should log sub-operations
        assert any("SERVICE_CALL llm_service._build_daily_context" in msg for msg in log_messages)
        assert any("SERVICE_CALL llm_service._store_generated_content" in msg for msg in log_messages)
        
        # Should log external API call
        assert any("API_CALL llm_provider" in msg for msg in log_messages)
        
        # Should log comprehensive metrics
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        expected_metrics = [
            "llm_provider_check_duration",
            "llm_prompt_retrieval_duration", 
            "llm_context_build_duration",
            "llm_request_duration",
            "llm_response_length",
            "llm_tokens_used",
            "llm_storage_duration",
            "llm_generation_success"
        ]
        
        for metric in expected_metrics:
            assert any(metric in msg for msg in metric_logs), f"Missing metric: {metric}"

    @pytest.mark.asyncio
    async def test_generate_daily_summary_error_logging(self, caplog):
        """Test that generation errors are properly logged."""
        # Mock LLM provider that raises an exception
        mock_llm_provider = AsyncMock()
        mock_llm_provider.is_available.return_value = True
        mock_llm_provider.generate_response.side_effect = Exception("LLM generation failed")
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
            llm_service.llm_provider = mock_llm_provider
            
            result = await llm_service.generate_daily_summary("2024-01-15")
        
        # Verify failed generation
        assert result.success is False
        assert "Generation failed" in result.error_message
        
        # Check error logging
        log_messages = [record.message for record in caplog.records]
        assert any("SERVICE_ERROR llm_service.generate_daily_summary" in msg for msg in log_messages)
        
        # Should log error metrics
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        assert any("llm_generation_general_error" in msg for msg in metric_logs)

    @pytest.mark.asyncio
    async def test_build_daily_context_logging(self, caplog):
        """Test that context building is comprehensively logged."""
        # Mock database queries
        self.mock_cursor.fetchall.side_effect = [
            [{"title": "News 1", "snippet": "Snippet 1"}, {"title": "News 2", "snippet": None}],  # News
            [{"processed_content": "Activity 1"}, {"processed_content": "Activity 2"}]  # Activities
        ]
        self.mock_cursor.fetchone.return_value = {
            'response_json': '{"data": [{"weather": "sunny", "temperature": 22}]}'
        }
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
            
            context = await llm_service._build_daily_context("2024-01-15")
        
        # Verify context was built
        assert "Date: 2024-01-15" in context
        assert "News Headlines:" in context
        assert "Weather:" in context
        assert "Activities:" in context
        
        # Check logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log service call
        assert any("SERVICE_CALL llm_service._build_daily_context" in msg for msg in log_messages)
        
        # Should log database operations
        assert any("DB_OPERATION SELECT" in msg and "news" in msg for msg in log_messages)
        assert any("DB_OPERATION SELECT" in msg and "weather" in msg for msg in log_messages)
        assert any("DB_OPERATION SELECT" in msg and "limitless" in msg for msg in log_messages)
        
        # Should log context metrics
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        expected_metrics = [
            "llm_context_news_items",
            "llm_context_weather_found", 
            "llm_context_activity_items",
            "llm_context_final_length",
            "llm_context_total_duration"
        ]
        
        for metric in expected_metrics:
            assert any(metric in msg for msg in metric_logs), f"Missing context metric: {metric}"

    def test_service_health_metrics(self):
        """Test that service health metrics are available."""
        llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
        
        # Get health metrics
        health_metrics = llm_service.get_service_health_metrics()
        
        # Verify health metrics structure
        assert 'service' in health_metrics
        assert health_metrics['service'] == 'llm_service'
        assert 'status' in health_metrics
        assert 'timestamp' in health_metrics

    def test_service_preserves_baseservice_functionality(self):
        """Test that LLMService still provides BaseService functionality."""
        llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
        
        # Verify BaseService functionality is preserved
        assert hasattr(llm_service, 'add_dependency')
        assert hasattr(llm_service, 'add_capability') 
        assert hasattr(llm_service, '_initialize_service')
        assert hasattr(llm_service, '_shutdown_service')
        assert hasattr(llm_service, '_check_service_health')
        
        # Verify dependencies and capabilities were added
        assert "DatabaseService" in llm_service.dependencies
        assert "DocumentService" in llm_service.dependencies
        assert "llm_generation" in llm_service.capabilities
        assert "daily_summary" in llm_service.capabilities


class TestLLMServicePerformanceImpact:
    """Test performance impact of debug logging in LLMService."""

    def setup_method(self):
        """Set up performance test fixtures."""
        self.mock_database = Mock()
        self.mock_document_service = Mock()
        self.mock_config = Mock()
        self.mock_config.llm_provider = Mock()
        self.mock_config.llm_provider.provider_type = Mock()
        self.mock_config.llm_provider.provider_type.value = "ollama"

    @pytest.mark.asyncio
    async def test_logging_performance_overhead(self):
        """Test that debug logging has minimal performance impact."""
        import time
        
        # Mock database response for cache hits
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"content": "Cached content"}
        mock_conn.execute.return_value = mock_cursor
        
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        self.mock_database.get_connection.return_value = mock_context
        
        llm_service = LLMService(self.mock_database, self.mock_document_service, self.mock_config)
        
        # Benchmark cached summary calls
        start_time = time.time()
        for _ in range(50):
            result = await llm_service.get_cached_summary("2024-01-15")
        duration = time.time() - start_time
        
        # Should complete 50 cache lookups quickly
        assert duration < 1.0, f"50 cached summary calls took {duration:.3f}s - too slow"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])