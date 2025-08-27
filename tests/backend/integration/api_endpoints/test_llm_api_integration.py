"""
Backend API Integration Tests for LLM Endpoints

Test-Driven Development (TDD) tests for user-defined summary prompts
and Daily Summary Card integration. These tests verify the complete
API workflow from prompt definition to summary generation.
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import status
from contextlib import contextmanager

from api.server import app
from services.llm_service import LLMService, LLMGenerationResult
from services.startup import StartupService
from llm.base import LLMResponse
from core.dependencies import get_startup_service_dependency


class TestLLMAPIIntegration:
    """Test LLM API endpoints with real integration scenarios"""

    @contextmanager
    def override_startup_service(self, startup_service):
        """Context manager to override startup service dependency"""
        app.dependency_overrides[get_startup_service_dependency] = lambda: startup_service
        try:
            yield
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service with LLM service"""
        startup_service = Mock()
        llm_service = Mock(spec=LLMService)
        
        # Add llm_provider attribute to satisfy route dependency check
        mock_provider = Mock()
        llm_service.llm_provider = mock_provider
        
        startup_service.llm_service = llm_service
        return startup_service, llm_service

    @pytest.fixture
    def sample_daily_data(self):
        """Sample data that would exist for a given date"""
        return {
            "news": [
                {"title": "AI Breakthrough", "snippet": "Major AI development announced"},
                {"title": "Tech Update", "snippet": "New technology released"}
            ],
            "twitter": [
                {"content": "Great day for tech!", "username": "user1"},
                {"content": "Learning about AI", "username": "user2"}
            ],
            "limitless": [
                {"processed_content": "Meeting notes: Discussed project timeline"},
                {"processed_content": "Call summary: Customer feedback session"}
            ]
        }

    def test_generate_summary_endpoint_with_llm_available(self, client, mock_startup_service, sample_daily_data):
        """Test /api/llm/generate-summary when LLM is available and data exists"""
        startup_service, llm_service = mock_startup_service
        
        # Mock successful LLM generation
        generation_result = LLMGenerationResult(
            content="Daily Summary: Great day with AI developments and productive meetings.",
            prompt_used="Generate a daily summary for {date}",
            model_info={"model": "test-model", "provider": "ollama"},
            generation_time=1.5,
            success=True
        )
        llm_service.generate_daily_summary = AsyncMock(return_value=generation_result)
        llm_service.get_cached_summary = AsyncMock(return_value=None)  # No cache

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert data["content"] == "Daily Summary: Great day with AI developments and productive meetings."
        assert data["days_date"] == "2024-01-15"
        assert data["prompt_used"] == "Generate a daily summary for {date}"
        assert data["cached"] is False
        assert data["generation_time"] == 1.5
        assert data["model_info"]["model"] == "test-model"

        # Verify the LLM service was called correctly
        llm_service.generate_daily_summary.assert_called_once_with(
            days_date="2024-01-15",
            force_regenerate=False
        )

    def test_generate_summary_endpoint_with_cached_content(self, client, mock_startup_service):
        """Test /api/llm/generate-summary returns cached content when available"""
        startup_service, llm_service = mock_startup_service
        
        # Mock cached content
        cached_content = "Cached Summary: Yesterday was productive with multiple achievements."
        llm_service.get_cached_summary = AsyncMock(return_value=cached_content)

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert data["content"] == cached_content
        assert data["cached"] is True
        assert data["generation_time"] == 0.0
        assert data["model_info"]["provider"] == "cache"

        # Should not call generate when cached content exists
        llm_service.generate_daily_summary.assert_not_called()

    def test_generate_summary_endpoint_force_regenerate(self, client, mock_startup_service):
        """Test /api/llm/generate-summary with force_regenerate=True bypasses cache"""
        startup_service, llm_service = mock_startup_service
        
        # Mock cached content exists but should be bypassed
        llm_service.get_cached_summary = AsyncMock(return_value="Old cached content")
        
        # Mock new generation
        generation_result = LLMGenerationResult(
            content="Newly generated summary with latest data.",
            prompt_used="Updated prompt",
            model_info={"model": "latest-model", "provider": "ollama"},
            generation_time=2.1,
            success=True
        )
        llm_service.generate_daily_summary = AsyncMock(return_value=generation_result)

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": True}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert data["content"] == "Newly generated summary with latest data."
        assert data["cached"] is False
        assert data["generation_time"] == 2.1

        # Should call generate even with cached content when force_regenerate=True
        llm_service.generate_daily_summary.assert_called_once_with(
            days_date="2024-01-15",
            force_regenerate=True
        )

    def test_generate_summary_endpoint_no_llm_available(self, client):
        """Test /api/llm/generate-summary when LLM service is not available"""
        # Mock startup service without LLM service
        startup_service = Mock()
        startup_service.llm_service = None

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "LLM service not available" in response.json()["detail"]

    def test_generate_summary_endpoint_no_llm_provider(self, client):
        """Test /api/llm/generate-summary when LLM service exists but provider is not available"""
        # Mock startup service with LLM service but no provider
        startup_service = Mock()
        llm_service = Mock()
        llm_service.llm_provider = None  # Provider not available
        startup_service.llm_service = llm_service

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "LLM service not available" in response.json()["detail"]

    def test_generate_summary_endpoint_llm_generation_failure(self, client, mock_startup_service):
        """Test /api/llm/generate-summary when LLM generation fails"""
        startup_service, llm_service = mock_startup_service
        
        # Mock failed generation
        generation_result = LLMGenerationResult(
            content="",
            prompt_used="Test prompt",
            model_info={"provider": "ollama"},
            generation_time=0.5,
            success=False,
            error_message="No LLM provider configured"
        )
        llm_service.generate_daily_summary = AsyncMock(return_value=generation_result)
        llm_service.get_cached_summary = AsyncMock(return_value=None)

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is False
        assert data["error_message"] == "No LLM provider configured"
        assert data["content"] == ""

    def test_generate_summary_endpoint_no_data_for_date(self, client, mock_startup_service):
        """Test /api/llm/generate-summary when no data exists for the given date"""
        startup_service, llm_service = mock_startup_service
        
        # Mock generation result indicating no data
        generation_result = LLMGenerationResult(
            content="No data available to summarize for this date.",
            prompt_used="Generate summary for {date}",
            model_info={"model": "test-model", "provider": "ollama"},
            generation_time=0.8,
            success=True
        )
        llm_service.generate_daily_summary = AsyncMock(return_value=generation_result)
        llm_service.get_cached_summary = AsyncMock(return_value=None)

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-12-25", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "No data available to summarize" in data["content"]

    def test_get_summary_endpoint_with_cached_content(self, client, mock_startup_service):
        """Test /api/llm/summary/{days_date} returns cached content"""
        startup_service, llm_service = mock_startup_service
        
        cached_content = "Cached summary for the requested date."
        llm_service.get_cached_summary = AsyncMock(return_value=cached_content)

        with self.override_startup_service(startup_service):
            response = client.get("/api/llm/summary/2024-01-15")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["content"] == cached_content
        assert data["days_date"] == "2024-01-15"
        assert data["cached"] is True

    def test_get_summary_endpoint_no_cached_content(self, client, mock_startup_service):
        """Test /api/llm/summary/{days_date} when no cached content exists"""
        startup_service, llm_service = mock_startup_service
        
        llm_service.get_cached_summary = AsyncMock(return_value=None)

        with self.override_startup_service(startup_service):
            response = client.get("/api/llm/summary/2024-01-15")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["content"] is None
        assert data["days_date"] == "2024-01-15"
        assert data["cached"] is True

    def test_get_summary_endpoint_no_llm_available(self, client):
        """Test /api/llm/summary/{days_date} when LLM service is not available"""
        startup_service = Mock()
        startup_service.llm_service = None

        with self.override_startup_service(startup_service):
            response = client.get("/api/llm/summary/2024-01-15")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "LLM service not available" in response.json()["detail"]

    def test_llm_health_endpoint_with_healthy_service(self, client, mock_startup_service):
        """Test /api/llm/health when LLM service is healthy"""
        startup_service, llm_service = mock_startup_service
        
        health_info = {
            "status": "healthy",
            "provider": "ollama",
            "models_available": 2,
            "last_generation": "2024-01-15T10:30:00Z"
        }
        llm_service._check_service_health = AsyncMock(return_value=health_info)

        with self.override_startup_service(startup_service):
            response = client.get("/api/llm/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["provider"] == "ollama"
        assert data["models_available"] == 2

    def test_llm_health_endpoint_no_llm_available(self, client):
        """Test /api/llm/health when LLM service is not available"""
        startup_service = Mock()
        startup_service.llm_service = None

        with self.override_startup_service(startup_service):
            response = client.get("/api/llm/health")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "LLM service not available" in response.json()["detail"]

    def test_invalid_date_format_handling(self, client, mock_startup_service):
        """Test API handles invalid date formats gracefully"""
        startup_service, llm_service = mock_startup_service
        
        # Mock that no cached content exists and generation returns an error
        llm_service.get_cached_summary = AsyncMock(return_value=None)
        generation_result = LLMGenerationResult(
            content="",
            prompt_used="Test prompt",
            model_info={"provider": "ollama"},
            generation_time=0.1,
            success=False,
            error_message="Invalid date format"
        )
        llm_service.generate_daily_summary = AsyncMock(return_value=generation_result)
        
        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "invalid-date", "force_regenerate": False}
            )

        # Should return 200 with failed generation result
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False
        assert "Invalid date format" in data["error_message"]

    def test_concurrent_summary_requests(self, client, mock_startup_service):
        """Test API handles concurrent summary requests for the same date"""
        startup_service, llm_service = mock_startup_service
        
        generation_result = LLMGenerationResult(
            content="Concurrent summary test",
            prompt_used="Test prompt",
            model_info={"model": "test", "provider": "ollama"},
            generation_time=1.0,
            success=True
        )
        llm_service.generate_daily_summary = AsyncMock(return_value=generation_result)
        llm_service.get_cached_summary = AsyncMock(return_value=None)

        with self.override_startup_service(startup_service):
            # Make concurrent requests
            import threading
            responses = []
            
            def make_request():
                response = client.post(
                    "/api/llm/generate-summary",
                    json={"days_date": "2024-01-15", "force_regenerate": False}
                )
                responses.append(response)
            
            threads = [threading.Thread(target=make_request) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        # All requests should succeed
        assert all(response.status_code == status.HTTP_200_OK for response in responses)
        assert all(response.json()["success"] is True for response in responses)


class TestLLMAPIErrorHandling:
    """Test error handling scenarios for LLM API endpoints"""

    @contextmanager
    def override_startup_service(self, startup_service):
        """Context manager to override startup service dependency"""
        app.dependency_overrides[get_startup_service_dependency] = lambda: startup_service
        try:
            yield
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)

    def test_malformed_request_body(self, client):
        """Test API handles malformed request bodies"""
        # Create a minimal startup service to pass dependency injection
        startup_service = Mock()
        llm_service = Mock(spec=LLMService)
        llm_service.llm_provider = Mock()
        startup_service.llm_service = llm_service
        
        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"invalid_field": "value"}
            )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_fields(self, client):
        """Test API validates required fields"""
        # Create a minimal startup service to pass dependency injection
        startup_service = Mock()
        llm_service = Mock(spec=LLMService)
        llm_service.llm_provider = Mock()
        startup_service.llm_service = llm_service
        
        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={}
            )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_service_exception_handling(self, client):
        """Test API handles service exceptions gracefully"""
        startup_service = Mock()
        llm_service = Mock(spec=LLMService)
        llm_service.get_cached_summary = AsyncMock(side_effect=Exception("Database error"))
        
        # Add llm_provider attribute to satisfy route dependency check
        mock_provider = Mock()
        llm_service.llm_provider = mock_provider
        
        startup_service.llm_service = llm_service

        with self.override_startup_service(startup_service):
            response = client.post(
                "/api/llm/generate-summary",
                json={"days_date": "2024-01-15", "force_regenerate": False}
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to generate daily summary" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])