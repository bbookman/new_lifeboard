"""
Tests for LLM base classes and models
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from llm.base import LLMResponse, LLMError, BaseLLMProvider


class TestLLMResponse:
    """Test LLM response model"""
    
    def test_create_response(self):
        """Test creating an LLM response"""
        content = "Test response content"
        model = "gpt-3.5-turbo"
        provider = "openai"
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        metadata = {"temperature": 0.7, "max_tokens": 100}
        
        response = LLMResponse.create(
            content=content,
            model=model,
            provider=provider,
            usage=usage,
            metadata=metadata
        )
        
        assert response.content == content
        assert response.model == model
        assert response.provider == provider
        assert response.usage == usage
        assert response.metadata == metadata
        assert isinstance(response.timestamp, datetime)
        assert response.timestamp.tzinfo == timezone.utc
    
    def test_create_response_with_defaults(self):
        """Test creating response with default usage and metadata"""
        response = LLMResponse.create(
            content="Test",
            model="test-model",
            provider="test-provider"
        )
        
        assert response.content == "Test"
        assert response.model == "test-model"
        assert response.provider == "test-provider"
        assert response.usage == {}
        assert response.metadata == {}
        assert isinstance(response.timestamp, datetime)
    
    def test_response_timestamp_is_utc(self):
        """Test that response timestamp is in UTC"""
        response = LLMResponse.create(
            content="Test",
            model="test-model",
            provider="test-provider"
        )
        
        assert response.timestamp.tzinfo == timezone.utc
        # Should be very recent
        now = datetime.now(timezone.utc)
        assert (now - response.timestamp).total_seconds() < 1


class TestLLMError:
    """Test LLM error handling"""
    
    def test_llm_error_basic(self):
        """Test basic LLM error"""
        message = "Test error message"
        provider = "test-provider"
        
        error = LLMError(message, provider)
        
        assert str(error) == message
        assert error.provider == provider
        assert error.error_code is None
    
    def test_llm_error_with_code(self):
        """Test LLM error with error code"""
        message = "API rate limit exceeded"
        provider = "openai"
        error_code = "rate_limit_exceeded"
        
        error = LLMError(message, provider, error_code)
        
        assert str(error) == message
        assert error.provider == provider
        assert error.error_code == error_code
    
    def test_llm_error_inheritance(self):
        """Test that LLMError inherits from Exception"""
        error = LLMError("Test", "provider")
        assert isinstance(error, Exception)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing base functionality"""
    
    def __init__(self, provider_name: str = "mock"):
        super().__init__(provider_name)
        self.is_available_result = True
        self.generate_response_result = None
        self.streaming_response_result = []
        self.models_result = []
        self.model_info_result = {}
    
    async def is_available(self) -> bool:
        return self.is_available_result
    
    async def generate_response(self, prompt, context=None, max_tokens=None, temperature=None):
        return self.generate_response_result
    
    async def generate_streaming_response(self, prompt, context=None, max_tokens=None, temperature=None):
        for chunk in self.streaming_response_result:
            yield chunk
    
    async def get_models(self):
        return self.models_result
    
    async def get_model_info(self, model_name):
        return self.model_info_result


class TestBaseLLMProvider:
    """Test base LLM provider functionality"""
    
    def test_provider_initialization(self):
        """Test provider initialization"""
        provider = MockLLMProvider("test-provider")
        
        assert provider.provider_name == "test-provider"
        assert provider.logger.name.endswith("test-provider")
    
    def test_validate_parameters_valid(self):
        """Test parameter validation with valid values"""
        provider = MockLLMProvider()
        
        # Should not raise any exceptions
        provider._validate_parameters(100, 0.7)
        provider._validate_parameters(None, None)
        provider._validate_parameters(1, 0.0)
        provider._validate_parameters(1000, 2.0)
    
    def test_validate_parameters_invalid_max_tokens(self):
        """Test parameter validation with invalid max_tokens"""
        provider = MockLLMProvider()
        
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider._validate_parameters(0, 0.7)
        
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider._validate_parameters(-1, 0.7)
    
    def test_validate_parameters_invalid_temperature(self):
        """Test parameter validation with invalid temperature"""
        provider = MockLLMProvider()
        
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            provider._validate_parameters(100, -0.1)
        
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            provider._validate_parameters(100, 2.1)
    
    def test_log_request(self):
        """Test request logging"""
        provider = MockLLMProvider()
        provider.logger = MagicMock()
        
        provider._log_request("Test prompt", max_tokens=100, temperature=0.7)
        
        provider.logger.debug.assert_called_once()
        call_args = provider.logger.debug.call_args[0][0]
        assert "LLM request to mock" in call_args
        assert "prompt_length=11" in call_args
    
    def test_log_response(self):
        """Test response logging"""
        provider = MockLLMProvider()
        provider.logger = MagicMock()
        
        response = LLMResponse.create(
            content="Test response",
            model="test-model",
            provider="mock",
            usage={"total_tokens": 50}
        )
        
        provider._log_response(response)
        
        provider.logger.debug.assert_called_once()
        call_args = provider.logger.debug.call_args[0][0]
        assert "LLM response from mock" in call_args
        assert "content_length=13" in call_args
    
    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test close method (default implementation)"""
        provider = MockLLMProvider()
        
        # Should not raise any exceptions
        await provider.close()
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager functionality"""
        provider = MockLLMProvider()
        provider.close = AsyncMock()
        
        async with provider as p:
            assert p is provider
        
        provider.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_abstract_methods_implemented(self):
        """Test that all abstract methods are implemented in mock"""
        provider = MockLLMProvider()
        
        # These should not raise NotImplementedError
        assert await provider.is_available() is True
        assert await provider.generate_response("test") is None
        
        # Test streaming response
        chunks = []
        async for chunk in provider.generate_streaming_response("test"):
            chunks.append(chunk)
        assert chunks == []
        
        assert await provider.get_models() == []
        assert await provider.get_model_info("test") == {}


class TestLLMProviderValidation:
    """Test LLM provider validation edge cases"""
    
    @pytest.mark.asyncio
    async def test_provider_with_real_validation(self):
        """Test provider with actual validation calls"""
        provider = MockLLMProvider()
        
        # Set up mock response
        expected_response = LLMResponse.create(
            content="Generated content",
            model="test-model",
            provider="mock"
        )
        provider.generate_response_result = expected_response
        
        # Test with valid parameters
        result = await provider.generate_response(
            "Test prompt",
            max_tokens=100,
            temperature=0.5
        )
        
        assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_provider_parameter_validation_in_context(self):
        """Test parameter validation is called in real context"""
        provider = MockLLMProvider()
        
        # Should raise validation error before attempting generation
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            await provider.generate_response("Test", max_tokens=-1)
        
        with pytest.raises(ValueError, match="temperature must be between"):
            await provider.generate_response("Test", temperature=3.0)