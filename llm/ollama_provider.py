"""
Ollama LLM provider implementation
"""

import httpx
import json
import asyncio
from typing import Dict, Any, Optional, List, AsyncIterator

from .base import BaseLLMProvider, LLMResponse, LLMError
from config.models import OllamaConfig


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self, config: OllamaConfig):
        super().__init__("ollama")
        self.config = config
        self.client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )
        return self.client
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def is_available(self) -> bool:
        """Check if Ollama is available and configured"""
        if not self.config.is_configured():
            self.logger.warning("Ollama not configured - missing base_url or model")
            return False
        
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"Ollama not available: {e}")
            return False
    
    async def generate_response(self, 
                              prompt: str, 
                              context: Optional[str] = None,
                              max_tokens: Optional[int] = None,
                              temperature: Optional[float] = None) -> LLMResponse:
        """Generate a response using Ollama"""
        self._validate_parameters(max_tokens, temperature)
        self._log_request(prompt, context=bool(context), max_tokens=max_tokens, temperature=temperature)
        
        if not await self.is_available():
            raise LLMError("Ollama is not available", self.provider_name)
        
        # Build the full prompt with context
        full_prompt = prompt
        if context:
            full_prompt = f"Context: {context}\n\nUser: {prompt}\n\nAssistant:"
        
        # Prepare request payload
        payload = {
            "model": self.config.model,
            "prompt": full_prompt,
            "stream": False
        }
        
        # Add optional parameters
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        
        if options:
            payload["options"] = options
        
        try:
            client = self._get_client()
            response = await self._make_request_with_retry(client, "/api/generate", payload)
            
            if response.status_code != 200:
                raise LLMError(f"Ollama API error: {response.status_code}", self.provider_name)
            
            data = response.json()
            
            # Extract response content
            content = data.get("response", "")
            if not content:
                raise LLMError("Empty response from Ollama", self.provider_name)
            
            # Build usage information
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            }
            
            # Build metadata
            metadata = {
                "model": data.get("model", self.config.model),
                "done": data.get("done", True),
                "context": data.get("context", []),
                "total_duration": data.get("total_duration", 0),
                "load_duration": data.get("load_duration", 0),
                "prompt_eval_duration": data.get("prompt_eval_duration", 0),
                "eval_duration": data.get("eval_duration", 0)
            }
            
            llm_response = LLMResponse.create(
                content=content,
                model=self.config.model,
                provider=self.provider_name,
                usage=usage,
                metadata=metadata
            )
            
            self._log_response(llm_response)
            return llm_response
            
        except httpx.RequestError as e:
            raise LLMError(f"Ollama request failed: {e}", self.provider_name)
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON response from Ollama: {e}", self.provider_name)
    
    async def generate_streaming_response(self, 
                                        prompt: str, 
                                        context: Optional[str] = None,
                                        max_tokens: Optional[int] = None,
                                        temperature: Optional[float] = None) -> AsyncIterator[str]:
        """Generate a streaming response using Ollama"""
        self._validate_parameters(max_tokens, temperature)
        self._log_request(prompt, context=bool(context), max_tokens=max_tokens, temperature=temperature, streaming=True)
        
        if not await self.is_available():
            raise LLMError("Ollama is not available", self.provider_name)
        
        # Build the full prompt with context
        full_prompt = prompt
        if context:
            full_prompt = f"Context: {context}\n\nUser: {prompt}\n\nAssistant:"
        
        # Prepare request payload
        payload = {
            "model": self.config.model,
            "prompt": full_prompt,
            "stream": True
        }
        
        # Add optional parameters
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        
        if options:
            payload["options"] = options
        
        try:
            client = self._get_client()
            
            async with client.stream("POST", "/api/generate", json=payload) as response:
                if response.status_code != 200:
                    raise LLMError(f"Ollama streaming API error: {response.status_code}", self.provider_name)
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data.get("response", "")
                            if content:
                                yield content
                            
                            # Check if streaming is done
                            if data.get("done", False):
                                break
                                
                        except json.JSONDecodeError:
                            continue  # Skip invalid JSON lines
                            
        except httpx.RequestError as e:
            raise LLMError(f"Ollama streaming request failed: {e}", self.provider_name)
    
    async def get_models(self) -> List[str]:
        """Get list of available Ollama models"""
        if not await self.is_available():
            return []
        
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            
            if response.status_code != 200:
                self.logger.warning(f"Failed to get Ollama models: {response.status_code}")
                return []
            
            data = response.json()
            models = [model.get("name", "") for model in data.get("models", [])]
            return [model for model in models if model]  # Filter out empty names
            
        except Exception as e:
            self.logger.warning(f"Error getting Ollama models: {e}")
            return []
    
    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get information about a specific Ollama model"""
        if not await self.is_available():
            return {}
        
        try:
            client = self._get_client()
            response = await client.post("/api/show", json={"name": model_name})
            
            if response.status_code != 200:
                self.logger.warning(f"Failed to get Ollama model info for {model_name}: {response.status_code}")
                return {}
            
            return response.json()
            
        except Exception as e:
            self.logger.warning(f"Error getting Ollama model info for {model_name}: {e}")
            return {}
    
    async def _make_request_with_retry(self, client: httpx.AsyncClient, endpoint: str, payload: Dict[str, Any]) -> httpx.Response:
        """Make HTTP request with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(endpoint, json=payload)
                return response
                
            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue
        
        # All retries failed
        raise last_exception