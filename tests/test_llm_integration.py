"""
Integration tests for LLM providers with real API calls

These tests require real API keys and running services.
They can be skipped if the required services are not available.
"""

import pytest
import os
import asyncio
from typing import AsyncIterator

from llm.factory import create_llm_provider
from llm.base import LLMError
from config.models import LLMProviderConfig, OllamaConfig, OpenAIConfig


# Test markers for conditional execution
pytestmark = pytest.mark.integration


class TestOllamaIntegration:
    """Integration tests for Ollama provider"""
    
    @pytest.fixture
    def ollama_config(self):
        """Create Ollama config for testing"""
        return LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "llama2"),
                timeout=30.0,
                max_retries=2
            )
        )
    
    @pytest.fixture
    async def ollama_factory(self, ollama_config):
        """Create and cleanup Ollama factory"""
        factory = create_llm_provider(ollama_config)
        yield factory
        await factory.close_all()
    
    @pytest.mark.skipif(
        not os.getenv("TEST_OLLAMA", "false").lower() == "true",
        reason="Ollama integration tests disabled (set TEST_OLLAMA=true to enable)"
    )
    @pytest.mark.asyncio
    async def test_ollama_availability(self, ollama_factory):
        """Test Ollama availability check"""
        result = await ollama_factory.check_provider_availability("ollama")
        
        if result["available"]:
            assert result["configured"] is True
            assert "models" in result
            assert result["model_count"] >= 0
        else:
            # Ollama not running - this is expected in many environments
            pytest.skip("Ollama not available for integration testing")
    
    @pytest.mark.skipif(
        not os.getenv("TEST_OLLAMA", "false").lower() == "true",
        reason="Ollama integration tests disabled"
    )
    @pytest.mark.asyncio
    async def test_ollama_generate_response(self, ollama_factory):
        """Test Ollama response generation"""
        provider = await ollama_factory.get_provider("ollama")
        
        if not await provider.is_available():
            pytest.skip("Ollama not available for integration testing")
        
        response = await provider.generate_response(
            "What is 2+2? Answer with just the number.",
            max_tokens=10,
            temperature=0.0
        )
        
        assert response.content
        assert response.model
        assert response.provider == "ollama"
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage
        assert response.usage["total_tokens"] > 0
    
    @pytest.mark.skipif(
        not os.getenv("TEST_OLLAMA", "false").lower() == "true",
        reason="Ollama integration tests disabled"
    )
    @pytest.mark.asyncio
    async def test_ollama_streaming_response(self, ollama_factory):
        """Test Ollama streaming response"""
        provider = await ollama_factory.get_provider("ollama")
        
        if not await provider.is_available():
            pytest.skip("Ollama not available for integration testing")
        
        chunks = []
        async for chunk in provider.generate_streaming_response(
            "Count from 1 to 3, separated by spaces.",
            max_tokens=20,
            temperature=0.0
        ):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert full_response
    
    @pytest.mark.skipif(
        not os.getenv("TEST_OLLAMA", "false").lower() == "true",
        reason="Ollama integration tests disabled"
    )
    @pytest.mark.asyncio
    async def test_ollama_get_models(self, ollama_factory):
        """Test getting Ollama models"""
        provider = await ollama_factory.get_provider("ollama")
        
        if not await provider.is_available():
            pytest.skip("Ollama not available for integration testing")
        
        models = await provider.get_models()
        
        assert isinstance(models, list)
        # Should have at least one model if Ollama is running
        if models:
            assert all(isinstance(model, str) for model in models)
    
    @pytest.mark.skipif(
        not os.getenv("TEST_OLLAMA", "false").lower() == "true",
        reason="Ollama integration tests disabled"
    )
    @pytest.mark.asyncio
    async def test_ollama_model_info(self, ollama_factory):
        """Test getting Ollama model info"""
        provider = await ollama_factory.get_provider("ollama")
        
        if not await provider.is_available():
            pytest.skip("Ollama not available for integration testing")
        
        models = await provider.get_models()
        if not models:
            pytest.skip("No models available for testing")
        
        # Test with first available model
        model_name = models[0]
        info = await provider.get_model_info(model_name)
        
        assert isinstance(info, dict)
        # Should have some model information
        if info:
            assert "modelfile" in info or "details" in info


class TestOpenAIIntegration:
    """Integration tests for OpenAI provider"""
    
    @pytest.fixture
    def openai_config(self):
        """Create OpenAI config for testing"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            pytest.skip("OpenAI API key not available for integration testing")
        
        return LLMProviderConfig(
            provider="openai",
            openai=OpenAIConfig(
                api_key=api_key,
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                timeout=30.0,
                max_retries=2,
                max_tokens=50  # Keep small for cost
            )
        )
    
    @pytest.fixture
    async def openai_factory(self, openai_config):
        """Create and cleanup OpenAI factory"""
        factory = create_llm_provider(openai_config)
        yield factory
        await factory.close_all()
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available for integration testing"
    )
    @pytest.mark.asyncio
    async def test_openai_availability(self, openai_factory):
        """Test OpenAI availability check"""
        result = await openai_factory.check_provider_availability("openai")
        
        assert result["available"] is True
        assert result["configured"] is True
        assert "models" in result
        assert result["model_count"] > 0
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available for integration testing"
    )
    @pytest.mark.asyncio
    async def test_openai_generate_response(self, openai_factory):
        """Test OpenAI response generation"""
        provider = await openai_factory.get_provider("openai")
        
        response = await provider.generate_response(
            "What is 2+2? Answer with just the number.",
            max_tokens=10,
            temperature=0.0
        )
        
        assert response.content
        assert response.model
        assert response.provider == "openai"
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage
        assert response.usage["total_tokens"] > 0
        assert "4" in response.content  # Should contain the answer
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available for integration testing"
    )
    @pytest.mark.asyncio
    async def test_openai_generate_response_with_context(self, openai_factory):
        """Test OpenAI response generation with context"""
        provider = await openai_factory.get_provider("openai")
        
        response = await provider.generate_response(
            "What should I do?",
            context="You are a helpful math tutor. The user is learning basic arithmetic.",
            max_tokens=30,
            temperature=0.0
        )
        
        assert response.content
        assert response.provider == "openai"
        # Response should be relevant to math tutoring context
        assert any(word in response.content.lower() 
                  for word in ["math", "practice", "problem", "learn", "help"])
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available for integration testing"
    )
    @pytest.mark.asyncio
    async def test_openai_streaming_response(self, openai_factory):
        """Test OpenAI streaming response"""
        provider = await openai_factory.get_provider("openai")
        
        chunks = []
        async for chunk in provider.generate_streaming_response(
            "Count from 1 to 3, separated by spaces.",
            max_tokens=20,
            temperature=0.0
        ):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert full_response
        # Should contain the numbers
        assert any(num in full_response for num in ["1", "2", "3"])
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available for integration testing"
    )
    @pytest.mark.asyncio
    async def test_openai_get_models(self, openai_factory):
        """Test getting OpenAI models"""
        provider = await openai_factory.get_provider("openai")
        
        models = await provider.get_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        # Should include GPT models
        assert any("gpt" in model.lower() for model in models)
        # Should be sorted
        assert models == sorted(models)
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available for integration testing"
    )
    @pytest.mark.asyncio
    async def test_openai_model_info(self, openai_factory):
        """Test getting OpenAI model info"""
        provider = await openai_factory.get_provider("openai")
        
        # Test with a known model
        model_name = "gpt-3.5-turbo"
        info = await provider.get_model_info(model_name)
        
        assert isinstance(info, dict)
        assert "id" in info
        assert info["id"] == model_name


class TestProviderSwitching:
    """Integration tests for provider switching"""
    
    @pytest.fixture
    def multi_provider_config(self):
        """Create config with both providers"""
        openai_key = os.getenv("OPENAI_API_KEY")
        
        return LLMProviderConfig(
            provider="ollama",  # Start with Ollama
            ollama=OllamaConfig(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "llama2")
            ),
            openai=OpenAIConfig(
                api_key=openai_key,
                model="gpt-3.5-turbo",
                max_tokens=20
            )
        )
    
    @pytest.fixture
    async def multi_factory(self, multi_provider_config):
        """Create factory with multiple providers"""
        factory = create_llm_provider(multi_provider_config)
        yield factory
        await factory.close_all()
    
    @pytest.mark.asyncio
    async def test_check_all_providers(self, multi_factory):
        """Test checking availability of all providers"""
        results = await multi_factory.check_all_providers()
        
        assert "ollama" in results
        assert "openai" in results
        
        # Check structure of results
        for provider_name, result in results.items():
            assert "provider" in result
            assert "available" in result
            assert "configured" in result
            assert result["provider"] == provider_name
    
    @pytest.mark.skipif(
        not (os.getenv("TEST_OLLAMA", "false").lower() == "true" and 
             os.getenv("OPENAI_API_KEY")),
        reason="Both Ollama and OpenAI needed for switching test"
    )
    @pytest.mark.asyncio
    async def test_provider_switching_functionality(self, multi_factory):
        """Test switching between providers"""
        # Check what's available
        availability = await multi_factory.check_all_providers()
        
        available_providers = [
            name for name, info in availability.items() 
            if info["available"]
        ]
        
        if len(available_providers) < 2:
            pytest.skip(f"Need at least 2 providers available, got {len(available_providers)}")
        
        # Test switching between available providers
        for provider_name in available_providers:
            provider = await multi_factory.switch_provider(provider_name)
            assert provider.provider_name == provider_name
            
            # Test that it can generate a response
            response = await provider.generate_response(
                "Hello",
                max_tokens=5,
                temperature=0.0
            )
            assert response.content
            assert response.provider == provider_name


class TestErrorHandling:
    """Integration tests for error handling"""
    
    @pytest.mark.asyncio
    async def test_ollama_not_available(self):
        """Test handling when Ollama is not available"""
        # Use a definitely unavailable URL
        config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(
                base_url="http://localhost:99999",  # Unlikely to be running
                model="nonexistent-model"
            )
        )
        
        factory = create_llm_provider(config)
        
        try:
            result = await factory.check_provider_availability("ollama")
            assert result["available"] is False
            
            provider = await factory.get_provider("ollama")
            assert not await provider.is_available()
            
            # Should raise error when trying to generate
            with pytest.raises(LLMError, match="Ollama is not available"):
                await provider.generate_response("Test")
                
        finally:
            await factory.close_all()
    
    @pytest.mark.asyncio
    async def test_openai_invalid_key(self):
        """Test handling when OpenAI key is invalid"""
        config = LLMProviderConfig(
            provider="openai",
            openai=OpenAIConfig(
                api_key="sk-invalid-key-for-testing",
                model="gpt-3.5-turbo"
            )
        )
        
        factory = create_llm_provider(config)
        
        try:
            provider = await factory.get_provider("openai")
            
            # Should detect as not available due to auth error
            is_available = await provider.is_available()
            assert not is_available
            
            # Should raise error when trying to generate
            with pytest.raises(LLMError):
                await provider.generate_response("Test")
                
        finally:
            await factory.close_all()


# Helper to run all integration tests
def run_integration_tests():
    """
    Helper function to run integration tests with appropriate markers
    
    Usage:
        # Run all integration tests
        pytest tests/test_llm_integration.py -m integration
        
        # Run only Ollama tests (requires Ollama running)
        TEST_OLLAMA=true pytest tests/test_llm_integration.py::TestOllamaIntegration
        
        # Run only OpenAI tests (requires API key)
        OPENAI_API_KEY=your_key pytest tests/test_llm_integration.py::TestOpenAIIntegration
    """
    pass