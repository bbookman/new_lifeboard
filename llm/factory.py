"""
LLM provider factory for creating and managing LLM provider instances
"""

from typing import Dict, Any, Optional
import logging

from .base import BaseLLMProvider, LLMError
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from config.models import LLMProviderConfig

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory for creating LLM provider instances"""
    
    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._active_provider: Optional[BaseLLMProvider] = None
    
    async def get_provider(self, provider_name: Optional[str] = None) -> BaseLLMProvider:
        """Get a provider instance, creating it if necessary"""
        if provider_name is None:
            provider_name = self.config.provider
        
        if provider_name not in self._providers:
            self._providers[provider_name] = await self._create_provider(provider_name)
        
        return self._providers[provider_name]
    
    async def get_active_provider(self) -> BaseLLMProvider:
        """Get the currently active provider"""
        if self._active_provider is None:
            self._active_provider = await self.get_provider()
        
        return self._active_provider
    
    async def switch_provider(self, provider_name: str) -> BaseLLMProvider:
        """Switch to a different provider"""
        if provider_name not in ["ollama", "openai"]:
            raise LLMError(f"Unknown provider: {provider_name}", "factory")
        
        # Close current active provider if different
        if self._active_provider and self._active_provider.provider_name != provider_name:
            await self._active_provider.close()
        
        # Update config and get new provider
        self.config.provider = provider_name
        self._active_provider = await self.get_provider(provider_name)
        
        logger.info(f"Switched to LLM provider: {provider_name}")
        return self._active_provider
    
    async def check_provider_availability(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """Check the availability of a provider"""
        if provider_name is None:
            provider_name = self.config.provider
        
        try:
            provider = await self.get_provider(provider_name)
            is_available = await provider.is_available()
            
            result = {
                "provider": provider_name,
                "available": is_available,
                "configured": True
            }
            
            if is_available:
                # Get additional info if available
                try:
                    models = await provider.get_models()
                    result["models"] = models
                    result["model_count"] = len(models)
                except Exception as e:
                    logger.warning(f"Could not get models for {provider_name}: {e}")
            
            return result
            
        except Exception as e:
            return {
                "provider": provider_name,
                "available": False,
                "configured": False,
                "error": str(e)
            }
    
    async def check_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """Check availability of all supported providers"""
        results = {}
        
        for provider_name in ["ollama", "openai"]:
            results[provider_name] = await self.check_provider_availability(provider_name)
        
        return results
    
    async def close_all(self):
        """Close all provider connections"""
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider {provider.provider_name}: {e}")
        
        self._providers.clear()
        self._active_provider = None
    
    async def _create_provider(self, provider_name: str) -> BaseLLMProvider:
        """Create a new provider instance"""
        if provider_name == "ollama":
            provider = OllamaProvider(self.config.ollama)
        elif provider_name == "openai":
            provider = OpenAIProvider(self.config.openai)
        else:
            raise LLMError(f"Unknown provider: {provider_name}", "factory")
        
        logger.info(f"Created LLM provider: {provider_name}")
        return provider


def create_llm_provider(config: LLMProviderConfig) -> LLMProviderFactory:
    """Create an LLM provider factory from configuration"""
    return LLMProviderFactory(config)