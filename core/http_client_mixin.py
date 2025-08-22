"""
HTTP Client Mixin for managing async HTTP clients consistently across the application.

This mixin provides a unified pattern for HTTP client lifecycle management,
eliminating duplication across sources and LLM providers.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx


class HTTPClientMixin(ABC):
    """
    Mixin class that provides standardized HTTP client management.
    
    Classes using this mixin must implement _create_client_config() to specify
    their specific client configuration (base_url, headers, timeout, etc.).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock: Optional[asyncio.Lock] = None

    @abstractmethod
    def _create_client_config(self) -> Dict[str, Any]:
        """
        Create configuration dictionary for the HTTP client.
        
        Returns:
            Dict containing httpx.AsyncClient constructor arguments:
            - base_url: str
            - headers: Dict[str, str]
            - timeout: float
            - Any other httpx.AsyncClient kwargs
        """

    def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create the HTTP client instance.
        
        Returns:
            httpx.AsyncClient: The configured async HTTP client
        """
        if self._client is None:
            config = self._create_client_config()
            self._client = httpx.AsyncClient(**config)
        return self._client

    async def _ensure_client(self) -> httpx.AsyncClient:
        """
        Thread-safe way to ensure the client is created.
        
        Returns:
            httpx.AsyncClient: The configured async HTTP client
        """
        if self._client is None:
            if self._client_lock is None:
                self._client_lock = asyncio.Lock()
            async with self._client_lock:
                if self._client is None:
                    config = self._create_client_config()
                    self._client = httpx.AsyncClient(**config)
        return self._client

    async def close(self):
        """
        Close the HTTP client and clean up resources.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        await self.close()

    @property
    def client(self) -> Optional[httpx.AsyncClient]:
        """
        Read-only access to the current client instance.
        Use _get_client() or _ensure_client() to create/access the client.
        """
        return self._client


class BaseHTTPSource(HTTPClientMixin):
    """
    Base class for HTTP-based data sources.
    
    Combines HTTPClientMixin with common source patterns.
    Note: This is a mixin, classes should also inherit from BaseSource.
    """

    def __init__(self, config, *args, **kwargs):
        self.config = config
        super().__init__(*args, **kwargs)

    async def test_connection(self) -> bool:
        """
        Test if the HTTP connection is working.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            client = await self._ensure_client()
            response = await self._make_test_request(client)
            return response.status_code < 400
        except Exception:
            return False

    @abstractmethod
    async def _make_test_request(self, client: httpx.AsyncClient) -> httpx.Response:
        """
        Make a test request to verify connectivity.
        
        Args:
            client: The HTTP client to use
            
        Returns:
            httpx.Response: The response from the test request
        """


class BaseLLMProvider(HTTPClientMixin):
    """
    Base class for LLM providers that use HTTP APIs.
    
    Combines HTTPClientMixin with common LLM provider patterns.
    """

    def __init__(self, config, *args, **kwargs):
        self.config = config
        super().__init__(*args, **kwargs)

    async def test_connection(self) -> bool:
        """
        Test if the LLM provider connection is working.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            client = await self._ensure_client()
            response = await self._make_test_request(client)
            return response.status_code < 400
        except Exception:
            return False

    @abstractmethod
    async def _make_test_request(self, client: httpx.AsyncClient) -> httpx.Response:
        """
        Make a test request to verify LLM provider connectivity.
        
        Args:
            client: The HTTP client to use
            
        Returns:
            httpx.Response: The response from the test request
        """
