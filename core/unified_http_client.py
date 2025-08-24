"""
Unified HTTP Client for Lifeboard
Provides standardized retry logic, authentication, and error handling across all API clients.

As specified in latest_clean.md Phase 2: HTTP Client Unification
"""
import asyncio
import logging
import base64
from typing import Dict, Any, Optional, Union
from enum import Enum
import httpx

from core.feature_flags import FeatureFlag, FeatureFlagManager


# Custom Exceptions
class HTTPClientError(Exception):
    """Base exception for HTTP client errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[httpx.Response] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(HTTPClientError):
    """Authentication configuration errors"""
    pass


class RetryExhaustedError(HTTPClientError):
    """Raised when maximum retry attempts are exceeded"""
    pass


class AuthMethod(Enum):
    """Supported authentication methods"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"


class UnifiedHTTPClient:
    """
    Unified HTTP client providing:
    - Standardized retry logic with exponential backoff
    - Multiple authentication methods
    - Consistent error handling and logging
    - Resource management with async context manager
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize HTTP client with configuration.
        
        Args:
            config: Configuration dictionary containing:
                - base_url (str): Base URL for all requests
                - timeout (float): Request timeout in seconds (default: 30.0)
                - max_retries (int): Maximum retry attempts (default: 3)
                - retry_backoff_factor (float): Backoff multiplier (default: 2.0)
                - retry_backoff_max (float): Maximum backoff time (default: 60.0)
                - auth_method (AuthMethod): Authentication method (default: NONE)
                - auth_config (dict): Authentication configuration
        """
        self.base_url = config['base_url']
        self.timeout = config.get('timeout', 30.0)
        self.max_retries = config.get('max_retries', 3)
        self.retry_backoff_factor = config.get('retry_backoff_factor', 2.0)
        self.retry_backoff_max = config.get('retry_backoff_max', 60.0)
        
        # Authentication setup
        auth_method = config.get('auth_method', AuthMethod.NONE)
        if isinstance(auth_method, str):
            try:
                self.auth_method = AuthMethod(auth_method)
            except ValueError:
                raise ValueError(f"Invalid auth_method: {auth_method}")
        else:
            self.auth_method = auth_method
        
        self.auth_config = config.get('auth_config', {})
        
        # Validate authentication configuration
        self._validate_auth_config()
        
        # HTTP client instance
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock: Optional[asyncio.Lock] = None
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def _validate_auth_config(self):
        """Validate authentication configuration"""
        if self.auth_method == AuthMethod.NONE:
            return
        
        if not self.auth_config:
            raise AuthenticationError(f"auth_config is required for {self.auth_method.value}")
        
        if self.auth_method == AuthMethod.API_KEY:
            if 'api_key' not in self.auth_config or 'header_name' not in self.auth_config:
                raise AuthenticationError("api_key and header_name are required for API_KEY auth")
        
        elif self.auth_method == AuthMethod.BEARER_TOKEN:
            if 'token' not in self.auth_config:
                raise AuthenticationError("token is required for BEARER_TOKEN auth")
        
        elif self.auth_method == AuthMethod.BASIC:
            if 'username' not in self.auth_config or 'password' not in self.auth_config:
                raise AuthenticationError("username and password are required for BASIC auth")
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Thread-safe client creation"""
        if self._client is None:
            if self._client_lock is None:
                self._client_lock = asyncio.Lock()
            
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self.base_url,
                        timeout=httpx.Timeout(self.timeout),
                        follow_redirects=True
                    )
        
        return self._client
    
    def _prepare_auth(self) -> Dict[str, Any]:
        """Prepare authentication headers and parameters"""
        headers = {}
        auth = None
        
        if self.auth_method == AuthMethod.API_KEY:
            header_name = self.auth_config['header_name']
            api_key = self.auth_config['api_key']
            headers[header_name] = api_key
        
        elif self.auth_method == AuthMethod.BEARER_TOKEN:
            token = self.auth_config['token']
            headers['Authorization'] = f'Bearer {token}'
        
        elif self.auth_method == AuthMethod.BASIC:
            username = self.auth_config['username']
            password = self.auth_config['password']
            auth = (username, password)
        
        return {'headers': headers, 'auth': auth}
    
    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with authentication"""
        client = await self._ensure_client()
        
        # Prepare authentication
        auth_params = self._prepare_auth()
        
        # Merge headers
        request_headers = kwargs.pop('headers', {})
        request_headers.update(auth_params['headers'])
        
        # Set up request parameters
        request_params = {
            'headers': request_headers,
            **kwargs
        }
        
        if auth_params['auth']:
            request_params['auth'] = auth_params['auth']
        
        # Make the request
        method_func = getattr(client, method.lower())
        return await method_func(url, **request_params)
    
    async def _make_request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._make_request(method, url, **kwargs)
                
                # Check if response indicates we should retry (5xx errors)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error: {response.status_code}",
                        request=response.request,
                        response=response
                    )
                
                return response
                
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_exception = e
                
                # Don't retry on client errors (4xx)
                if isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500:
                    break
                
                # Don't retry on final attempt
                if attempt == self.max_retries:
                    break
                
                # Calculate backoff time
                backoff_time = min(
                    self.retry_backoff_factor ** attempt,
                    self.retry_backoff_max
                )
                
                self.logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                    f"Retrying in {backoff_time} seconds..."
                )
                
                await asyncio.sleep(backoff_time)
        
        # All retries exhausted
        if isinstance(last_exception, httpx.HTTPStatusError) and 400 <= last_exception.response.status_code < 500:
            # Client error - don't wrap as RetryExhaustedError
            raise HTTPClientError(
                f"HTTP {last_exception.response.status_code}: {last_exception}",
                status_code=last_exception.response.status_code,
                response=last_exception.response
            )
        else:
            # Server error or connection issue - wrap as RetryExhaustedError
            raise RetryExhaustedError(
                f"Maximum retries ({self.max_retries}) exceeded. Last error: {last_exception}"
            )
    
    async def _handle_response(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Handle request with consistent error handling and logging"""
        try:
            return await self._make_request_with_retry(method, url, **kwargs)
        
        except (RetryExhaustedError, HTTPClientError):
            # Already wrapped, re-raise
            raise
        
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error in {method} {url}: {e}")
            raise HTTPClientError(
                f"HTTP {e.response.status_code}: {e}",
                status_code=e.response.status_code,
                response=e.response
            )
        
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            self.logger.error(f"Connection/timeout error in {method} {url}: {e}")
            raise HTTPClientError(f"Connection error: {e}")
        
        except Exception as e:
            self.logger.error(f"Unexpected error in {method} {url}: {e}")
            raise HTTPClientError(f"Unexpected error: {e}")
    
    # HTTP Methods
    async def get(self, url: str, params: Optional[Dict] = None, **kwargs) -> httpx.Response:
        """Make GET request"""
        request_kwargs = {'params': params, **kwargs} if params else kwargs
        return await self._handle_response('GET', url, **request_kwargs)
    
    async def post(self, url: str, data: Optional[Dict] = None, **kwargs) -> httpx.Response:
        """Make POST request"""
        request_kwargs = {'json': data, **kwargs} if data else kwargs
        return await self._handle_response('POST', url, **request_kwargs)
    
    async def put(self, url: str, data: Optional[Dict] = None, **kwargs) -> httpx.Response:
        """Make PUT request"""
        request_kwargs = {'json': data, **kwargs} if data else kwargs
        return await self._handle_response('PUT', url, **request_kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """Make DELETE request"""
        return await self._handle_response('DELETE', url, **kwargs)
    
    # Resource Management
    async def close(self):
        """Close HTTP client and clean up resources"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.close()


# Factory function for easy client creation
def create_http_client(config: Dict[str, Any]) -> UnifiedHTTPClient:
    """
    Factory function to create configured HTTP client.
    
    Args:
        config: Client configuration dictionary
        
    Returns:
        UnifiedHTTPClient: Configured client instance
    """
    return UnifiedHTTPClient(config)