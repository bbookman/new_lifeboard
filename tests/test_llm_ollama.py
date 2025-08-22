"""
Tests for Ollama LLM provider
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from config.models import OllamaConfig
from llm.base import LLMError
from llm.ollama_provider import OllamaProvider


class TestOllamaConfig:
    """Test Ollama configuration"""

    def test_default_values(self):
        """Test default configuration values"""
        config = OllamaConfig()

        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama2"
        assert config.timeout == 60.0
        assert config.max_retries == 3

    def test_custom_values(self):
        """Test custom configuration values"""
        config = OllamaConfig(
            base_url="http://custom:8080",
            model="custom-model",
            timeout=30.0,
            max_retries=5,
        )

        assert config.base_url == "http://custom:8080"
        assert config.model == "custom-model"
        assert config.timeout == 30.0
        assert config.max_retries == 5

    def test_is_configured_valid(self):
        """Test is_configured with valid config"""
        config = OllamaConfig(
            base_url="http://localhost:11434",
            model="llama2",
        )

        assert config.is_configured() is True

    def test_is_configured_missing_url(self):
        """Test is_configured with missing base_url"""
        config = OllamaConfig(base_url="", model="llama2")
        assert config.is_configured() is False

    def test_is_configured_missing_model(self):
        """Test is_configured with missing model"""
        config = OllamaConfig(base_url="http://localhost:11434", model="")
        assert config.is_configured() is False


class TestOllamaProvider:
    """Test Ollama provider functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.config = OllamaConfig(
            base_url="http://localhost:11434",
            model="llama2",
            timeout=30.0,
            max_retries=2,
        )
        self.provider = OllamaProvider(self.config)

    def test_provider_initialization(self):
        """Test provider initialization"""
        assert self.provider.provider_name == "ollama"
        assert self.provider.config == self.config
        assert self.provider.client is None

    def test_get_client_creates_client(self):
        """Test that _get_client creates HTTP client"""
        client = self.provider._get_client()

        assert isinstance(client, httpx.AsyncClient)
        assert str(client.base_url) == "http://localhost:11434"
        assert client.timeout == 30.0
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
    async def test_close_no_client(self):
        """Test closing when no client exists"""
        # Should not raise any exceptions
        await self.provider.close()

    @pytest.mark.asyncio
    async def test_is_available_not_configured(self):
        """Test is_available when not configured"""
        config = OllamaConfig(base_url="", model="llama2")
        provider = OllamaProvider(config)

        result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_success(self):
        """Test is_available when Ollama is available"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(self.provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await self.provider.is_available()

            assert result is True
            mock_client.get.assert_called_once_with("/api/tags")

    @pytest.mark.asyncio
    async def test_is_available_failure(self):
        """Test is_available when Ollama is not available"""
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
            "response": expected_content,
            "model": "llama2",
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 20,
            "total_duration": 1000000,
            "context": [1, 2, 3],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            result = await self.provider.generate_response(prompt)

            assert result.content == expected_content
            assert result.model == "llama2"
            assert result.provider == "ollama"
            assert result.usage["prompt_tokens"] == 10
            assert result.usage["completion_tokens"] == 20
            assert result.usage["total_tokens"] == 30
            assert result.metadata["done"] is True

    @pytest.mark.asyncio
    async def test_generate_response_with_context(self):
        """Test response generation with context"""
        prompt = "Test prompt"
        context = "Test context"

        mock_response_data = {
            "response": "Response with context",
            "model": "llama2",
            "done": True,
            "prompt_eval_count": 15,
            "eval_count": 25,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response) as mock_request:

            await self.provider.generate_response(prompt, context=context)

            # Verify the request was made with context in the prompt
            call_args = mock_request.call_args
            payload = call_args[0][2]  # Third argument is payload
            assert "Context: Test context" in payload["prompt"]
            assert "User: Test prompt" in payload["prompt"]

    @pytest.mark.asyncio
    async def test_generate_response_with_parameters(self):
        """Test response generation with parameters"""
        prompt = "Test prompt"
        max_tokens = 150
        temperature = 0.8

        mock_response_data = {
            "response": "Parameterized response",
            "model": "llama2",
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 20,
        }

        mock_response = MagicMock()
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
            options = payload["options"]
            assert options["num_predict"] == max_tokens
            assert options["temperature"] == temperature

    @pytest.mark.asyncio
    async def test_generate_response_not_available(self):
        """Test response generation when Ollama not available"""
        with patch.object(self.provider, "is_available", return_value=False):

            with pytest.raises(LLMError, match="Ollama is not available"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_api_error(self):
        """Test response generation with API error"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            with pytest.raises(LLMError, match="Ollama API error: 500"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_empty_response(self):
        """Test response generation with empty response"""
        mock_response_data = {
            "response": "",
            "model": "llama2",
            "done": True,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            with pytest.raises(LLMError, match="Empty response from Ollama"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_response_invalid_json(self):
        """Test response generation with invalid JSON"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_make_request_with_retry", return_value=mock_response):

            with pytest.raises(LLMError, match="Invalid JSON response from Ollama"):
                await self.provider.generate_response("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_streaming_response_success(self):
        """Test successful streaming response generation"""
        prompt = "Test streaming prompt"

        # Mock streaming response data
        stream_data = [
            '{"response": "Hello", "done": false}',
            '{"response": " world", "done": false}',
            '{"response": "!", "done": true}',
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
        """Test streaming response when Ollama not available"""
        with patch.object(self.provider, "is_available", return_value=False):

            with pytest.raises(LLMError, match="Ollama is not available"):
                async for _ in self.provider.generate_streaming_response("Test"):
                    pass

    @pytest.mark.asyncio
    async def test_get_models_success(self):
        """Test getting available models"""
        mock_response_data = {
            "models": [
                {"name": "llama2"},
                {"name": "codellama"},
                {"name": "mistral"},
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

            assert models == ["llama2", "codellama", "mistral"]
            mock_client.get.assert_called_once_with("/api/tags")

    @pytest.mark.asyncio
    async def test_get_models_not_available(self):
        """Test getting models when Ollama not available"""
        with patch.object(self.provider, "is_available", return_value=False):

            models = await self.provider.get_models()

            assert models == []

    @pytest.mark.asyncio
    async def test_get_model_info_success(self):
        """Test getting model information"""
        model_name = "llama2"
        mock_response_data = {
            "modelfile": "FROM llama2",
            "parameters": "temperature 0.7",
            "template": "{{ .Prompt }}",
            "details": {
                "format": "ggml",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "7B",
                "quantization_level": "Q4_0",
            },
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(self.provider, "is_available", return_value=True), \
             patch.object(self.provider, "_get_client", return_value=mock_client):

            info = await self.provider.get_model_info(model_name)

            assert info == mock_response_data
            mock_client.post.assert_called_once_with("/api/show", json={"name": model_name})

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
    async def test_make_request_with_retry_eventual_success(self):
        """Test request that succeeds after initial failure"""
        mock_response = AsyncMock()
        mock_client = AsyncMock()
        mock_client.post.side_effect = [
            httpx.RequestError("First failure"),
            mock_response,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await self.provider._make_request_with_retry(
                mock_client, "/test", {"test": "data"},
            )

            assert result == mock_response
            assert mock_client.post.call_count == 2
