"""
Tests for LLM factory and provider management
"""

from unittest.mock import AsyncMock, patch

import pytest

from config.models import LLMProviderConfig, OllamaConfig, OpenAIConfig
from llm.base import LLMError
from llm.factory import LLMProviderFactory, create_llm_provider
from llm.ollama_provider import OllamaProvider
from llm.openai_provider import OpenAIProvider


class TestLLMProviderFactory:
    """Test LLM provider factory functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(
                base_url="http://localhost:11434",
                model="llama2",
            ),
            openai=OpenAIConfig(
                api_key="sk-test-key",
                model="gpt-3.5-turbo",
            ),
        )
        self.factory = LLMProviderFactory(self.config)

    def test_factory_initialization(self):
        """Test factory initialization"""
        assert self.factory.config == self.config
        assert self.factory._providers == {}
        assert self.factory._active_provider is None

    @pytest.mark.asyncio
    async def test_get_provider_ollama(self):
        """Test getting Ollama provider"""
        provider = await self.factory.get_provider("ollama")

        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"
        assert provider.config == self.config.ollama

        # Should be cached
        assert "ollama" in self.factory._providers
        assert self.factory._providers["ollama"] is provider

    @pytest.mark.asyncio
    async def test_get_provider_openai(self):
        """Test getting OpenAI provider"""
        provider = await self.factory.get_provider("openai")

        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"
        assert provider.config == self.config.openai

        # Should be cached
        assert "openai" in self.factory._providers
        assert self.factory._providers["openai"] is provider

    @pytest.mark.asyncio
    async def test_get_provider_unknown(self):
        """Test getting unknown provider"""
        with pytest.raises(LLMError, match="Unknown provider: unknown"):
            await self.factory.get_provider("unknown")

    @pytest.mark.asyncio
    async def test_get_provider_default(self):
        """Test getting provider with default (from config)"""
        provider = await self.factory.get_provider()

        # Should get the default provider (ollama)
        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_get_provider_caching(self):
        """Test that providers are properly cached"""
        provider1 = await self.factory.get_provider("ollama")
        provider2 = await self.factory.get_provider("ollama")

        # Should be the same instance
        assert provider1 is provider2

    @pytest.mark.asyncio
    async def test_get_active_provider(self):
        """Test getting active provider"""
        provider = await self.factory.get_active_provider()

        assert isinstance(provider, OllamaProvider)
        assert self.factory._active_provider is provider

        # Subsequent calls should return same instance
        provider2 = await self.factory.get_active_provider()
        assert provider2 is provider

    @pytest.mark.asyncio
    async def test_switch_provider_same(self):
        """Test switching to same provider"""
        # First get active provider
        original_provider = await self.factory.get_active_provider()
        assert isinstance(original_provider, OllamaProvider)

        # Switch to same provider
        switched_provider = await self.factory.switch_provider("ollama")

        assert switched_provider is original_provider
        assert self.factory.config.provider == "ollama"

    @pytest.mark.asyncio
    async def test_switch_provider_different(self):
        """Test switching to different provider"""
        # First get active provider (ollama)
        original_provider = await self.factory.get_active_provider()
        original_provider.close = AsyncMock()

        # Switch to OpenAI
        switched_provider = await self.factory.switch_provider("openai")

        assert isinstance(switched_provider, OpenAIProvider)
        assert switched_provider is not original_provider
        assert self.factory.config.provider == "openai"
        assert self.factory._active_provider is switched_provider

        # Original provider should have been closed
        original_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_provider_unknown(self):
        """Test switching to unknown provider"""
        with pytest.raises(LLMError, match="Unknown provider: unknown"):
            await self.factory.switch_provider("unknown")

    @pytest.mark.asyncio
    async def test_check_provider_availability_available(self):
        """Test checking availability of available provider"""
        with patch.object(OllamaProvider, "is_available", return_value=True), \
             patch.object(OllamaProvider, "get_models", return_value=["llama2", "codellama"]):

            result = await self.factory.check_provider_availability("ollama")

            assert result["provider"] == "ollama"
            assert result["available"] is True
            assert result["configured"] is True
            assert result["models"] == ["llama2", "codellama"]
            assert result["model_count"] == 2

    @pytest.mark.asyncio
    async def test_check_provider_availability_unavailable(self):
        """Test checking availability of unavailable provider"""
        with patch.object(OllamaProvider, "is_available", return_value=False):

            result = await self.factory.check_provider_availability("ollama")

            assert result["provider"] == "ollama"
            assert result["available"] is False
            assert result["configured"] is True

    @pytest.mark.asyncio
    async def test_check_provider_availability_error(self):
        """Test checking availability with provider error"""
        with patch.object(self.factory, "get_provider", side_effect=Exception("Provider error")):

            result = await self.factory.check_provider_availability("ollama")

            assert result["provider"] == "ollama"
            assert result["available"] is False
            assert result["configured"] is False
            assert result["error"] == "Provider error"

    @pytest.mark.asyncio
    async def test_check_provider_availability_default(self):
        """Test checking availability of default provider"""
        with patch.object(OllamaProvider, "is_available", return_value=True):

            result = await self.factory.check_provider_availability()

            # Should check the default provider (ollama)
            assert result["provider"] == "ollama"
            assert result["available"] is True

    @pytest.mark.asyncio
    async def test_check_provider_availability_model_error(self):
        """Test checking availability when get_models fails"""
        with patch.object(OllamaProvider, "is_available", return_value=True), \
             patch.object(OllamaProvider, "get_models", side_effect=Exception("Model fetch error")):

            result = await self.factory.check_provider_availability("ollama")

            assert result["provider"] == "ollama"
            assert result["available"] is True
            assert result["configured"] is True
            # Should not have models info when get_models fails
            assert "models" not in result

    @pytest.mark.asyncio
    async def test_check_all_providers(self):
        """Test checking availability of all providers"""
        with patch.object(OllamaProvider, "is_available", return_value=True), \
             patch.object(OpenAIProvider, "is_available", return_value=False):

            results = await self.factory.check_all_providers()

            assert "ollama" in results
            assert "openai" in results

            assert results["ollama"]["available"] is True
            assert results["openai"]["available"] is False

    @pytest.mark.asyncio
    async def test_close_all_providers(self):
        """Test closing all providers"""
        # Create some providers
        ollama_provider = await self.factory.get_provider("ollama")
        openai_provider = await self.factory.get_provider("openai")

        # Mock their close methods
        ollama_provider.close = AsyncMock()
        openai_provider.close = AsyncMock()

        # Set active provider
        self.factory._active_provider = ollama_provider

        # Close all
        await self.factory.close_all()

        # All providers should be closed
        ollama_provider.close.assert_called_once()
        openai_provider.close.assert_called_once()

        # Internal state should be cleared
        assert self.factory._providers == {}
        assert self.factory._active_provider is None

    @pytest.mark.asyncio
    async def test_close_all_providers_with_error(self):
        """Test closing all providers when one fails"""
        # Create some providers
        ollama_provider = await self.factory.get_provider("ollama")
        openai_provider = await self.factory.get_provider("openai")

        # Mock their close methods, one fails
        ollama_provider.close = AsyncMock(side_effect=Exception("Close error"))
        openai_provider.close = AsyncMock()

        # Close all - should not raise exception
        await self.factory.close_all()

        # Both should have been attempted
        ollama_provider.close.assert_called_once()
        openai_provider.close.assert_called_once()

        # State should still be cleared
        assert self.factory._providers == {}
        assert self.factory._active_provider is None


class TestLLMProviderFactoryCreation:
    """Test LLM provider factory creation scenarios"""

    @pytest.mark.asyncio
    async def test_create_ollama_provider_internal(self):
        """Test internal Ollama provider creation"""
        config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(model="test-model"),
        )
        factory = LLMProviderFactory(config)

        provider = await factory._create_provider("ollama")

        assert isinstance(provider, OllamaProvider)
        assert provider.config.model == "test-model"

    @pytest.mark.asyncio
    async def test_create_openai_provider_internal(self):
        """Test internal OpenAI provider creation"""
        config = LLMProviderConfig(
            provider="openai",
            openai=OpenAIConfig(api_key="test-key", model="gpt-4"),
        )
        factory = LLMProviderFactory(config)

        provider = await factory._create_provider("openai")

        assert isinstance(provider, OpenAIProvider)
        assert provider.config.api_key == "test-key"
        assert provider.config.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_create_unknown_provider_internal(self):
        """Test internal creation of unknown provider"""
        config = LLMProviderConfig()
        factory = LLMProviderFactory(config)

        with pytest.raises(LLMError, match="Unknown provider: unknown"):
            await factory._create_provider("unknown")


class TestCreateLLMProvider:
    """Test create_llm_provider factory function"""

    def test_create_llm_provider_function(self):
        """Test create_llm_provider factory function"""
        config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(model="test-model"),
        )

        factory = create_llm_provider(config)

        assert isinstance(factory, LLMProviderFactory)
        assert factory.config is config

    @pytest.mark.asyncio
    async def test_created_factory_works(self):
        """Test that factory created by function works correctly"""
        config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(model="test-model"),
        )

        factory = create_llm_provider(config)
        provider = await factory.get_provider("ollama")

        assert isinstance(provider, OllamaProvider)
        assert provider.config.model == "test-model"


class TestLLMProviderFactoryEdgeCases:
    """Test edge cases and error conditions"""

    def test_factory_with_invalid_config(self):
        """Test factory with invalid configuration"""
        config = LLMProviderConfig(provider="invalid")
        factory = LLMProviderFactory(config)

        # Factory creation should succeed, but provider creation should fail
        assert factory.config.provider == "invalid"

    @pytest.mark.asyncio
    async def test_switch_provider_before_any_provider_created(self):
        """Test switching provider before any provider is created"""
        config = LLMProviderConfig(provider="ollama")
        factory = LLMProviderFactory(config)

        # No active provider yet
        assert factory._active_provider is None

        # Switch to OpenAI
        provider = await factory.switch_provider("openai")

        assert isinstance(provider, OpenAIProvider)
        assert factory._active_provider is provider
        assert factory.config.provider == "openai"

    @pytest.mark.asyncio
    async def test_get_active_provider_after_config_change(self):
        """Test getting active provider after config change"""
        config = LLMProviderConfig(provider="ollama")
        factory = LLMProviderFactory(config)

        # Get initial active provider
        provider1 = await factory.get_active_provider()
        assert isinstance(provider1, OllamaProvider)

        # Manually change config (simulating external config change)
        factory.config.provider = "openai"

        # Get active provider again - should still return the cached one
        provider2 = await factory.get_active_provider()
        assert provider2 is provider1  # Same instance

        # But switching should work
        provider3 = await factory.switch_provider("openai")
        assert isinstance(provider3, OpenAIProvider)

    @pytest.mark.asyncio
    async def test_provider_cleanup_on_factory_deletion(self):
        """Test that providers can be properly cleaned up"""
        config = LLMProviderConfig(provider="ollama")
        factory = LLMProviderFactory(config)

        # Create provider
        provider = await factory.get_provider("ollama")
        provider.close = AsyncMock()

        # Manually clean up
        await factory.close_all()

        provider.close.assert_called_once()
