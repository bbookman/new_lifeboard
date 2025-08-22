"""
OpenAI LLM provider implementation
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from config.models import OpenAIConfig
from core.http_client_mixin import HTTPClientMixin
from core.retry_utils import (
    NetworkErrorRetryCondition,
    RetryExecutor,
    create_llm_retry_config,
)

from .base import BaseLLMProvider, LLMError, LLMResponse


class OpenAIProvider(BaseLLMProvider, HTTPClientMixin):
    """OpenAI cloud LLM provider"""

    def __init__(self, config: OpenAIConfig):
        BaseLLMProvider.__init__(self, "openai")
        HTTPClientMixin.__init__(self)
        self.config = config

    def _create_client_config(self) -> Dict[str, Any]:
        """Create HTTP client configuration for OpenAI API"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        return {
            "base_url": self.config.base_url,
            "timeout": self.config.timeout,
            "headers": headers,
        }

    async def _make_test_request(self, client: httpx.AsyncClient) -> httpx.Response:
        """Make a test request to verify OpenAI connectivity"""
        return await client.get("/models")

    async def is_available(self) -> bool:
        """Check if OpenAI is available and configured"""
        if not self.config.is_configured():
            self.logger.warning("OpenAI not configured - missing API key")
            return False

        return await super().test_connection()

    async def generate_response(self,
                              prompt: str,
                              context: Optional[str] = None,
                              max_tokens: Optional[int] = None,
                              temperature: Optional[float] = None) -> LLMResponse:
        """Generate a response using OpenAI"""
        self._validate_parameters(max_tokens, temperature)
        self._log_request(prompt, context=bool(context), max_tokens=max_tokens, temperature=temperature)

        if not await self.is_available():
            raise LLMError("OpenAI is not available", self.provider_name)

        # Build the messages array
        messages = []
        if context:
            messages.append({
                "role": "system",
                "content": f"Context: {context}",
            })

        messages.append({
            "role": "user",
            "content": prompt,
        })

        # Prepare request payload
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        }

        # Add optional parameters
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        else:
            payload["max_tokens"] = self.config.max_tokens

        try:
            client = await self._ensure_client()
            response = await self._make_request_with_retry(client, "/chat/completions", payload)

            if response.status_code != 200:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                raise LLMError(f"OpenAI API error: {error_msg}", self.provider_name)

            data = response.json()

            # Extract response content
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("No choices in OpenAI response", self.provider_name)

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                raise LLMError("Empty response from OpenAI", self.provider_name)

            # Build usage information
            usage_data = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }

            # Build metadata
            metadata = {
                "model": data.get("model", self.config.model),
                "finish_reason": choices[0].get("finish_reason"),
                "system_fingerprint": data.get("system_fingerprint"),
                "created": data.get("created"),
                "object": data.get("object"),
            }

            llm_response = LLMResponse.create(
                content=content,
                model=self.config.model,
                provider=self.provider_name,
                usage=usage,
                metadata=metadata,
            )

            self._log_response(llm_response)
            return llm_response

        except httpx.RequestError as e:
            raise LLMError(f"OpenAI request failed: {e}", self.provider_name)
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON response from OpenAI: {e}", self.provider_name)

    async def generate_streaming_response(self,
                                        prompt: str,
                                        context: Optional[str] = None,
                                        max_tokens: Optional[int] = None,
                                        temperature: Optional[float] = None) -> AsyncIterator[str]:
        """Generate a streaming response using OpenAI"""
        self._validate_parameters(max_tokens, temperature)
        self._log_request(prompt, context=bool(context), max_tokens=max_tokens, temperature=temperature, streaming=True)

        if not await self.is_available():
            raise LLMError("OpenAI is not available", self.provider_name)

        # Build the messages array
        messages = []
        if context:
            messages.append({
                "role": "system",
                "content": f"Context: {context}",
            })

        messages.append({
            "role": "user",
            "content": prompt,
        })

        # Prepare request payload
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
        }

        # Add optional parameters
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        else:
            payload["max_tokens"] = self.config.max_tokens

        try:
            client = await self._ensure_client()

            async with client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    error_data = {}
                    try:
                        error_content = await response.aread()
                        error_data = json.loads(error_content)
                    except:
                        pass
                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise LLMError(f"OpenAI streaming API error: {error_msg}", self.provider_name)

                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content

                                # Check if streaming is done
                                if choices[0].get("finish_reason") is not None:
                                    break

                        except json.JSONDecodeError:
                            continue  # Skip invalid JSON lines

        except httpx.RequestError as e:
            raise LLMError(f"OpenAI streaming request failed: {e}", self.provider_name)

    async def get_models(self) -> List[str]:
        """Get list of available OpenAI models"""
        if not await self.is_available():
            return []

        try:
            client = await self._ensure_client()
            response = await client.get("/models")

            if response.status_code != 200:
                self.logger.warning(f"Failed to get OpenAI models: {response.status_code}")
                return []

            data = response.json()
            models = [model.get("id", "") for model in data.get("data", [])]
            # Filter for chat models only
            chat_models = [model for model in models if "gpt" in model.lower() and model]
            return sorted(chat_models)

        except Exception as e:
            self.logger.warning(f"Error getting OpenAI models: {e}")
            return []

    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get information about a specific OpenAI model"""
        if not await self.is_available():
            return {}

        try:
            client = await self._ensure_client()
            response = await client.get(f"/models/{model_name}")

            if response.status_code != 200:
                self.logger.warning(f"Failed to get OpenAI model info for {model_name}: {response.status_code}")
                return {}

            return response.json()

        except Exception as e:
            self.logger.warning(f"Error getting OpenAI model info for {model_name}: {e}")
            return {}

    async def _make_request_with_retry(self, client: httpx.AsyncClient, endpoint: str, payload: Dict[str, Any]) -> httpx.Response:
        """Make HTTP request with retry logic using unified retry framework"""
        # Create retry configuration optimized for LLM calls
        retry_config = create_llm_retry_config(max_retries=self.config.max_retries)
        retry_condition = NetworkErrorRetryCondition()
        retry_executor = RetryExecutor(retry_config, retry_condition)

        async def make_request():
            return await client.post(endpoint, json=payload)

        result = await retry_executor.execute_async(make_request)

        if result.success:
            return result.result
        raise result.exception
