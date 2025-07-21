"""
LLM Provider Abstraction Layer

This module provides a provider-agnostic interface for LLM integration,
supporting both local (Ollama) and cloud (OpenAI) providers.
"""

from .base import BaseLLMProvider, LLMResponse, LLMError
from .factory import create_llm_provider, LLMProviderFactory
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

__all__ = [
    "BaseLLMProvider",
    "LLMResponse", 
    "LLMError",
    "create_llm_provider",
    "LLMProviderFactory",
    "OllamaProvider",
    "OpenAIProvider"
]