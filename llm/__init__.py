"""
LLM Provider Abstraction Layer

This module provides a provider-agnostic interface for LLM integration,
supporting both local (Ollama) and cloud (OpenAI) providers.
"""

from .base import BaseLLMProvider, LLMError, LLMResponse
from .factory import LLMProviderFactory, create_llm_provider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

__all__ = [
    "BaseLLMProvider",
    "LLMError",
    "LLMProviderFactory",
    "LLMResponse",
    "OllamaProvider",
    "OpenAIProvider",
    "create_llm_provider",
]
