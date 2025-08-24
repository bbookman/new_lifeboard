"""
Test suite for Unified HTTP Client
Following TDD approach as specified in latest_clean.md Phase 2
"""
import pytest
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any
import json

from core.unified_http_client import (
    UnifiedHTTPClient, 
    HTTPClientError, 
    AuthenticationError, 
    RetryExhaustedError,
    AuthMethod
)


class TestUnifiedHTTPClient:
    """Test Unified HTTP Client basic functionality"""
    
    @pytest.fixture
    def client_config(self):
        """Basic client configuration for testing"""
        return {
            'base_url': 'https://api.example.com',
            'timeout': 30.0,
            'max_retries': 3,
            'auth_method': AuthMethod.API_KEY,
            'auth_config': {'api_key': 'test-key', 'header_name': 'X-API-Key'}
        }
    
    @pytest.fixture
    def client(self, client_config):
        """Create client instance for testing"""
        return UnifiedHTTPClient(client_config)
    
    def test_client_initialization(self, client_config):
        """Test that client initializes with correct configuration"""
        client = UnifiedHTTPClient(client_config)
        
        assert client.base_url == 'https://api.example.com'
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.auth_method == AuthMethod.API_KEY
        assert client.auth_config['api_key'] == 'test-key'
    
    def test_client_initialization_with_defaults(self):
        """Test client initialization with minimal config uses defaults"""
        minimal_config = {'base_url': 'https://api.example.com'}
        client = UnifiedHTTPClient(minimal_config)
        
        assert client.base_url == 'https://api.example.com'
        assert client.timeout == 30.0  # default
        assert client.max_retries == 3  # default
        assert client.auth_method == AuthMethod.NONE  # default
    
    def test_invalid_auth_method_raises_error(self):
        """Test that invalid auth method raises error during initialization"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': 'invalid_method'
        }
        
        with pytest.raises(ValueError, match="Invalid auth_method"):
            UnifiedHTTPClient(config)


class TestUnifiedHTTPClientRetryLogic:
    """Test retry logic with exponential backoff"""
    
    @pytest.fixture
    def client_config(self):
        return {
            'base_url': 'https://api.example.com',
            'max_retries': 3,
            'retry_backoff_factor': 2.0,
            'retry_backoff_max': 60.0
        }
    
    @pytest.fixture
    def client(self, client_config):
        return UnifiedHTTPClient(client_config)
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, client):
        """Test that client retries on 5xx server errors"""
        with patch.object(client, '_make_request') as mock_request:
            # First 2 attempts fail with 500, third succeeds
            mock_request.side_effect = [
                httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500)),
                httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500)),
                Mock(status_code=200, json=lambda: {'success': True})
            ]
            
            result = await client.get('/test')
            
            assert mock_request.call_count == 3
            assert result.status_code == 200
    
    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, client):
        """Test that client retries on connection errors"""
        with patch.object(client, '_make_request') as mock_request:
            # First 2 attempts fail with connection error, third succeeds
            mock_request.side_effect = [
                httpx.ConnectError("Connection failed"),
                httpx.ConnectError("Connection failed"),
                Mock(status_code=200, json=lambda: {'success': True})
            ]
            
            result = await client.get('/test')
            
            assert mock_request.call_count == 3
            assert result.status_code == 200
    
    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, client):
        """Test that client does not retry on 4xx client errors"""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "Bad Request", 
                request=Mock(), 
                response=Mock(status_code=400)
            )
            
            with pytest.raises(HTTPClientError):
                await client.get('/test')
            
            # Should only try once
            assert mock_request.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_exhausted_error(self, client):
        """Test that RetryExhaustedError is raised when max retries exceeded"""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "Server Error", 
                request=Mock(), 
                response=Mock(status_code=500)
            )
            
            with pytest.raises(RetryExhaustedError) as exc_info:
                await client.get('/test')
            
            assert mock_request.call_count == 4  # initial + 3 retries
            assert "Maximum retries (3) exceeded" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, client):
        """Test that exponential backoff timing works correctly"""
        with patch('asyncio.sleep') as mock_sleep:
            with patch.object(client, '_make_request') as mock_request:
                mock_request.side_effect = [
                    httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500)),
                    httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500)),
                    httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500)),
                    httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500))
                ]
                
                with pytest.raises(RetryExhaustedError):
                    await client.get('/test')
                
                # Check exponential backoff: 1, 2, 4 seconds
                expected_sleeps = [1.0, 2.0, 4.0]
                actual_sleeps = [call.args[0] for call in mock_sleep.call_args_list]
                assert actual_sleeps == expected_sleeps


class TestUnifiedHTTPClientAuthMethods:
    """Test different authentication methods"""
    
    @pytest.mark.asyncio
    async def test_api_key_authentication(self):
        """Test API key authentication in header"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.API_KEY,
            'auth_config': {
                'api_key': 'test-api-key-123',
                'header_name': 'X-API-Key'
            }
        }
        client = UnifiedHTTPClient(config)
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {'success': True})
            
            await client.get('/test')
            
            # Verify API key was added to headers
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert headers['X-API-Key'] == 'test-api-key-123'
    
    @pytest.mark.asyncio
    async def test_bearer_token_authentication(self):
        """Test Bearer token authentication"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.BEARER_TOKEN,
            'auth_config': {
                'token': 'bearer-token-xyz'
            }
        }
        client = UnifiedHTTPClient(config)
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {'success': True})
            
            await client.get('/test')
            
            # Verify Bearer token was added to Authorization header
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert headers['Authorization'] == 'Bearer bearer-token-xyz'
    
    @pytest.mark.asyncio
    async def test_basic_authentication(self):
        """Test Basic authentication"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.BASIC,
            'auth_config': {
                'username': 'testuser',
                'password': 'testpass'
            }
        }
        client = UnifiedHTTPClient(config)
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {'success': True})
            
            await client.get('/test')
            
            # Verify Basic auth was set
            call_args = mock_get.call_args
            auth = call_args[1]['auth']
            assert auth == ('testuser', 'testpass')
    
    @pytest.mark.asyncio
    async def test_no_authentication(self):
        """Test no authentication method"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.NONE
        }
        client = UnifiedHTTPClient(config)
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {'success': True})
            
            await client.get('/test')
            
            # Verify no auth headers were added
            call_args = mock_get.call_args
            headers = call_args[1].get('headers', {})
            auth = call_args[1].get('auth')
            
            assert 'Authorization' not in headers
            assert 'X-API-Key' not in headers
            assert auth is None
    
    def test_missing_auth_config_raises_error(self):
        """Test that missing auth config raises error"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.API_KEY
            # Missing auth_config
        }
        
        with pytest.raises(AuthenticationError, match="auth_config is required"):
            UnifiedHTTPClient(config)
    
    def test_invalid_api_key_config_raises_error(self):
        """Test that invalid API key config raises error"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.API_KEY,
            'auth_config': {
                # Missing api_key and header_name
                'invalid_key': 'value'
            }
        }
        
        with pytest.raises(AuthenticationError, match="api_key and header_name are required"):
            UnifiedHTTPClient(config)


class TestUnifiedHTTPClientErrorHandling:
    """Test consistent error handling across all methods"""
    
    @pytest.fixture
    def client(self):
        config = {'base_url': 'https://api.example.com'}
        return UnifiedHTTPClient(config)
    
    @pytest.mark.asyncio
    async def test_http_status_error_handling(self, client):
        """Test that HTTP status errors are wrapped consistently"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock(status_code=404, text="Not Found")
            mock_get.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=mock_response
            )
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get('/test')
            
            assert exc_info.value.status_code == 404
            assert "Not Found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, client):
        """Test that connection errors are wrapped consistently"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get('/test')
            
            assert "Connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, client):
        """Test that timeout errors are wrapped consistently"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get('/test')
            
            assert "Request timeout" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_error_logging_consistency(self, client):
        """Test that errors are logged consistently"""
        with patch.object(client, 'logger') as mock_logger:
            with patch.object(client, '_make_request_with_retry') as mock_retry:
                mock_response = Mock(status_code=404, text="Not Found")
                mock_retry.side_effect = httpx.HTTPStatusError(
                    "Not Found", request=Mock(), response=mock_response
                )
                
                with pytest.raises(HTTPClientError):
                    await client.get('/test')
                
                # Verify error was logged during error handling
                mock_logger.error.assert_called_once()


class TestUnifiedHTTPClientMethods:
    """Test HTTP methods (GET, POST, PUT, DELETE)"""
    
    @pytest.fixture
    def client(self):
        config = {'base_url': 'https://api.example.com'}
        return UnifiedHTTPClient(config)
    
    @pytest.mark.asyncio
    async def test_get_method(self, client):
        """Test GET method with query parameters"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {'data': 'test'})
            
            result = await client.get('/test', params={'key': 'value'})
            
            assert result.status_code == 200
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[1]['params'] == {'key': 'value'}
    
    @pytest.mark.asyncio
    async def test_post_method(self, client):
        """Test POST method with JSON data"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = Mock(status_code=201, json=lambda: {'created': True})
            
            data = {'name': 'test', 'value': 123}
            result = await client.post('/test', data=data)
            
            assert result.status_code == 201
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]['json'] == data
    
    @pytest.mark.asyncio
    async def test_put_method(self, client):
        """Test PUT method with JSON data"""
        with patch('httpx.AsyncClient.put') as mock_put:
            mock_put.return_value = Mock(status_code=200, json=lambda: {'updated': True})
            
            data = {'id': 1, 'name': 'updated'}
            result = await client.put('/test/1', data=data)
            
            assert result.status_code == 200
            mock_put.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_method(self, client):
        """Test DELETE method"""
        with patch('httpx.AsyncClient.delete') as mock_delete:
            mock_delete.return_value = Mock(status_code=204)
            
            result = await client.delete('/test/1')
            
            assert result.status_code == 204
            mock_delete.assert_called_once()


class TestUnifiedHTTPClientContextManager:
    """Test async context manager functionality"""
    
    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up resources"""
        config = {'base_url': 'https://api.example.com'}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            async with UnifiedHTTPClient(config) as client:
                # Force client creation
                await client._ensure_client()
                assert client is not None
            
            # Verify client was closed
            mock_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_manual_close(self):
        """Test manual client closure"""
        config = {'base_url': 'https://api.example.com'}
        client = UnifiedHTTPClient(config)
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            await client._ensure_client()  # Create client
            await client.close()
            
            mock_client.aclose.assert_called_once()


class TestUnifiedHTTPClientIntegration:
    """Integration tests for real-world usage patterns"""
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_retry_and_auth(self):
        """Test complete workflow with authentication and retry logic"""
        config = {
            'base_url': 'https://api.example.com',
            'auth_method': AuthMethod.API_KEY,
            'auth_config': {'api_key': 'test-key', 'header_name': 'X-API-Key'},
            'max_retries': 2
        }
        
        client = UnifiedHTTPClient(config)
        
        with patch('httpx.AsyncClient.get') as mock_get:
            # First call fails, second succeeds
            mock_get.side_effect = [
                httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock(status_code=500)),
                Mock(status_code=200, json=lambda: {'success': True})
            ]
            
            result = await client.get('/test')
            
            assert result.status_code == 200
            assert mock_get.call_count == 2
            
            # Verify auth headers were present in both calls
            for call in mock_get.call_args_list:
                headers = call[1]['headers']
                assert headers['X-API-Key'] == 'test-key'