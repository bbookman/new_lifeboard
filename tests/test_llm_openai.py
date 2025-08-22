"""
Tests for OpenAI LLM provider
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from config.models import OpenAIConfig
from llm.base import LLMError
from llm.openai_provider import OpenAIProvider


class TestOpenAIConfig:
    """Test OpenAI configuration"""

    def test_default_values(self):
        """Test default configuration values"""
        config = OpenAIConfig()

        assert config.api_key is None
        assert config.model == "gpt-3.5-turbo"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.timeout == 60.0
        assert config.max_retries == 3
        assert config.max_tokens == 1000
        assert config.temperature == 0.7

    def test_custom_values(self):
        """Test custom configuration values"""
        config = OpenAIConfig(
            api_key="test-key",
            model="gpt-4",
            base_url="https://custom.openai.com/v1",
            timeout=30.0,
            max_retries=5,
            max_tokens=2000,
            temperature=0.5,
        )

        assert config.api_key == "test-key"
        assert config.model == "gpt-4"
        assert config.base_url == "https://custom.openai.com/v1"
        assert config.timeout == 30.0
        assert config.max_retries == 5
        assert config.max_tokens == 2000
        assert config.temperature == 0.5

    def test_is_configured_valid(self):
        """Test is_configured with valid config"""
        config = OpenAIConfig(api_key="sk-valid-key")
        assert config.is_configured() is True

    def test_is_configured_missing_key(self):
        """Test is_configured with missing API key"""
        config = OpenAIConfig(api_key=None)
        assert config.is_configured() is False

        config = OpenAIConfig(api_key="")
        assert config.is_configured() is False

        config = OpenAIConfig(api_key="your_openai_api_key_here")
        assert config.is_configured() is False


class TestOpenAIProvider:
    """Test OpenAI provider functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.config = OpenAIConfig(
            api_key="sk-test-key",
            model="gpt-3.5-turbo",
            base_url="https://api.openai.com/v1",
            timeout=30.0,
            max_retries=2,
            max_tokens=1000,
            temperature=0.7,
        )
        self.provider = OpenAIProvider(self.config)

    def test_provider_initialization(self):
        """Test provider initialization"""
        assert self.provider.provider_name == "openai"
        assert self.provider.config == self.config
        assert self.provider.client is None

    def test_get_client_creates_client(self):
        """Test that _get_client creates HTTP client with proper headers"""
        client = self.provider._get_client()

        assert isinstance(client, httpx.AsyncClient)
        assert str(client.base_url) == "https://api.openai.com/v1"
        assert client.timeout == 30.0

        # Check authorization header
        auth_header = client.headers.get("Authorization")
        assert auth_header == "Bearer sk-test-key"

        content_type_header = client.headers.get("Content-Type")
        assert content_type_header == "application/json"

        assert self.provider.client is client

    def test_get_client_reuses_client(self):
        """Test that _get_client reuses existing client"""
        client1 = self.provider._get_client()
        client2 = self.provider._get_client()

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing HTTP client"""
        # Create client
        client = self.provider._get_client()
        mock_aclose = AsyncMock()
        client.aclose = mock_aclose

        await self.provider.close()

        mock_aclose.assert_called_once()
        assert self.provider.client is None

    @pytest.mark.asyncio
    async def test_is_available_not_configured(self):
        """Test is_available when not configured"""
        config = OpenAIConfig(api_key=None)
        provider = OpenAIProvider(config)

        result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_success(self):
        """Test is_available when OpenAI is available"""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch.object(self.provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await self.provider.is_available()

            assert result is True
            mock_client.get.assert_called_once_with("/models")

    @pytest.mark.asyncio
    async def test_is_available_failure(self):
        """Test is_available when OpenAI is not available"""
        with patch.object(self.provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.RequestError("Connection failed")
            mock_get_client.return_value = mock_client

            result = await self.provider.is_available()

            assert result is False

    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test successful response generation"""
        prompt = "Test prompt"
        expected_content = "Generated response"

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": expected_content,
                    },
                    "finish_reason": "stop",
                },
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25,
            },
            "model": "gpt-3.5-turbo",
            "created": 1234567890,
            "object": "chat.completion",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            result = await self.provider.generate_response(prompt)

            assert result.content == expected_content
            assert result.model == "gpt-3.5-turbo"
            assert result.provider == "openai"
            assert result.usage["prompt_tokens"] == 10
            assert result.usage["completion_tokens"] == 15
            assert result.usage["total_tokens"] == 25
            assert result.metadata["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_generate_response_with_context(self):
        """Test response generation with context"""
        prompt = "Test prompt"
        context = "Test context"

        mock_response_data = {
            "choices": [
                {
                    "message": {"content": "Response with context"},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            "model": "gpt-3.5-turbo",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response) as mock_request:

            await self.provider.generate_response(prompt, context=context)

            # Verify the request was made with context as system message
            call_args = mock_request.call_args
            payload = call_args[0][2]  # Third argument is payload
            messages = payload["messages"]

            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert "Context: Test context" in messages[0]["content"]
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == prompt

    @pytest.mark.asyncio
    async def test_generate_response_with_parameters(self):
        """Test response generation with parameters"""
        prompt = "Test prompt"
        max_tokens = 150
        temperature = 0.8

        mock_response_data = {
            "choices": [{"message": {"content": "Parameterized response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "model": "gpt-3.5-turbo",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response) as mock_request:

            await self.provider.generate_response(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Verify parameters were included in request
            call_args = mock_request.call_args
            payload = call_args[0][2]
            assert payload["max_tokens"] == max_tokens
            assert payload["temperature"] == temperature

    @pytest.mark.asyncio
    async def test_generate_response_uses_default_max_tokens(self):
        """Test that default max_tokens from config is used when not specified"""
        prompt = "Test prompt"

        mock_response_data = {
            "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "model": "gpt-3.5-turbo",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response) as mock_request:

            await self.provider.generate_response(prompt)

            # Should use config default (1000)
            call_args = mock_request.call_args
            payload = call_args[0][2]
            assert payload["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_generate_response_not_available(self):
        """Test response generation when OpenAI not available"""
        with patch.object(self.provider, "is_available", return_value=False):

            with pytest.raises(LLMError, match="OpenAI is not available"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_api_error(self):
        """Test response generation with API error"""
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {
                "message": "Invalid request",
                "type": "invalid_request_error",
            },
        }

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            with pytest.raises(LLMError, match="OpenAI API error: Invalid request"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_no_choices(self):
        """Test response generation with no choices"""
        mock_response_data = {
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
            "model": "gpt-3.5-turbo",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            with pytest.raises(LLMError, match="No choices in OpenAI response"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_empty_content(self):
        """Test response generation with empty content"""
        mock_response_data = {
            "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
            "model": "gpt-3.5-turbo",
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            with pytest.raises(LLMError, match="Empty response from OpenAI"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_streaming_response_success(self):
        """Test successful streaming response generation"""
        prompt = "Test streaming prompt"

        # Mock streaming response data
        stream_data = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
            'data: {"choices": [{"delta": {"content": "!"}, "finish_reason": "stop"}]}',
            "data: [DONE]",
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = stream_data

        mock_client = AsyncMock()
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_get_client", return_value=mock_client):

            chunks = []
            async for chunk in self.provider.generate_streaming_response(prompt):
                chunks.append(chunk)

            assert chunks == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_generate_streaming_response_not_available(self):
        """Test streaming response when OpenAI not available"""
        with patch.object(self.provider, "is_available", return_value=False):

            with pytest.raises(LLMError, match="OpenAI is not available"):
                async for _ in self.provider.generate_streaming_response("Test"):
                    pass

    @pytest.mark.asyncio
    async def test_generate_streaming_response_api_error(self):
        """Test streaming response with API error"""
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.aread.return_value = b'{"error": {"message": "Bad request"}}'

        mock_client = AsyncMock()
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_get_client", return_value=mock_client):

            with pytest.raises(LLMError, match="OpenAI streaming API error: Bad request"):
                async for _ in self.provider.generate_streaming_response("Test"):
                    pass

    @pytest.mark.asyncio
    async def test_get_models_success(self):
        """Test getting available models"""
        mock_response_data = {
            "data": [
                {"id": "gpt-3.5-turbo", "object": "model"},
                {"id": "gpt-4", "object": "model"},
                {"id": "text-davinci-003", "object": "model"},  # Should be filtered out
                {"id": "gpt-3.5-turbo-16k", "object": "model"},
            ],
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_get_client", return_value=mock_client):

            models = await self.provider.get_models()

            # Should only include GPT models, sorted
            expected_models = ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4"]
            assert models == expected_models
            mock_client.get.assert_called_once_with("/models")

    @pytest.mark.asyncio
    async def test_get_models_not_available(self):
        """Test getting models when OpenAI not available"""
        with patch.object(self.provider, "is_available", return_value=False):

            models = await self.provider.get_models()

            assert models == []

    @pytest.mark.asyncio
    async def test_get_model_info_success(self):
        """Test getting model information"""
        model_name = "gpt-3.5-turbo"
        mock_response_data = {
            "id": "gpt-3.5-turbo",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai",
            "permission": [],
            "root": "gpt-3.5-turbo",
            "parent": None,
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_get_client", return_value=mock_client):

            info = await self.provider.get_model_info(model_name)

            assert info == mock_response_data
            mock_client.get.assert_called_once_with(f"/models/{model_name}")

    @pytest.mark.asyncio
    async def test_make_request_with_retry_success(self):
        """Test successful request with retry logic"""
        mock_response = AsyncMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        result = await self.provider._make_request_with_retry(
            mock_client, "/test", {"test": "data"},
        )

        assert result == mock_response
        mock_client.post.assert_called_once_with("/test", json={"test": "data"})

    @pytest.mark.asyncio
    async def test_make_request_with_retry_failure(self):
        """Test request with retry logic after failures"""
        mock_client = AsyncMock()
        mock_client.post.side_effect = [
            httpx.RequestError("First failure"),
            httpx.RequestError("Second failure"),
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(httpx.RequestError, match="Second failure"):
                await self.provider._make_request_with_retry(
                    mock_client, "/test", {"test": "data"},
                )

            # Should have retried based on max_retries (2)
            assert mock_client.post.call_count == 2
            # Should have slept once between retries
            mock_sleep.assert_called_once_with(1)  # 2^0 = 1 second

    @pytest.mark.asyncio
    async def test_parameter_validation(self):
        """Test that parameter validation is called"""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            await self.provider.generate_response("Test", max_tokens=-1)

        with pytest.raises(ValueError, match="temperature must be between"):
            await self.provider.generate_response("Test", temperature=3.0)
