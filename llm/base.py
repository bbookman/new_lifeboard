"""
Base classes for LLM provider abstraction
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response format"""
    content: str
    model: str
    provider: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    @classmethod
    def create(cls, content: str, model: str, provider: str, 
               usage: Optional[Dict[str, Any]] = None,
               metadata: Optional[Dict[str, Any]] = None) -> "LLMResponse":
        """Create an LLM response with current timestamp"""
        return cls(
            content=content,
            model=model,
            provider=provider,
            usage=usage or {},
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc)
        )


class LLMError(Exception):
    """Base exception for LLM provider errors"""
    def __init__(self, message: str, provider: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.logger = logging.getLogger(f"{__name__}.{provider_name}")
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available and configured"""
        pass
    
    @abstractmethod
    async def generate_response(self, 
                              prompt: str, 
                              context: Optional[str] = None,
                              max_tokens: Optional[int] = None,
                              temperature: Optional[float] = None) -> LLMResponse:
        """Generate a response to a prompt"""
        pass
    
    @abstractmethod
    async def generate_streaming_response(self, 
                                        prompt: str, 
                                        context: Optional[str] = None,
                                        max_tokens: Optional[int] = None,
                                        temperature: Optional[float] = None) -> AsyncIterator[str]:
        """Generate a streaming response to a prompt"""
        pass
    
    @abstractmethod
    async def get_models(self) -> List[str]:
        """Get list of available models for this provider"""
        pass
    
    @abstractmethod
    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get information about a specific model"""
        pass
    
    async def test_connection(self) -> bool:
        """Test connection to the LLM provider - default implementation returns True"""
        return True
    
    async def close(self):
        """Close any connections and cleanup resources"""
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def _validate_parameters(self, max_tokens: Optional[int], temperature: Optional[float]):
        """Validate common parameters"""
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        
        if temperature is not None and not (0.0 <= temperature <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
    
    def _log_request(self, prompt: str, **kwargs):
        """Log LLM request for debugging"""
        self.logger.debug(f"LLM request to {self.provider_name}: prompt_length={len(prompt)}, params={kwargs}")
    
    def _log_response(self, response: LLMResponse):
        """Log LLM response for debugging"""
        self.logger.debug(f"LLM response from {self.provider_name}: content_length={len(response.content)}, usage={response.usage}")