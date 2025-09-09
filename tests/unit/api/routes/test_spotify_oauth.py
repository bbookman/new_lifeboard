"""
Test for Spotify OAuth routes

Following TDD approach - these tests should fail initially (RED phase)
until the real OAuth implementation is complete.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Mock the SpotifyTokenService import
try:
    from services.spotify_token_service import SpotifyTokenService
    from api.routes.spotify import router, exchange_code_for_token
    from config.models import SpotifyConfig
    from core.dependencies import get_startup_service_dependency
except ImportError:
    SpotifyTokenService = None
    router = None
    exchange_code_for_token = None
    SpotifyConfig = None
    get_startup_service_dependency = None


class TestSpotifyOAuth:
    """Test suite for Spotify OAuth implementation"""
    
    @pytest.fixture
    def mock_spotify_config(self):
        """Mock Spotify configuration"""
        mock_config = Mock(spec=SpotifyConfig)
        mock_config.client_id = "test_client_id"
        mock_config.client_secret = "test_client_secret"
        mock_config.redirect_uri = "http://localhost:8000/callback"
        mock_config.required_scopes = ["user-read-recently-played"]
        mock_config.is_api_configured.return_value = True
        return mock_config
    
    @pytest.fixture
    def mock_startup_service(self, mock_spotify_config):
        """Mock startup service"""
        mock_service = Mock()
        mock_service.config.spotify = mock_spotify_config
        return mock_service
    
    @pytest.fixture
    def mock_token_service(self):
        """Mock SpotifyTokenService"""
        if SpotifyTokenService is None:
            pytest.skip("SpotifyTokenService not implemented yet")
        
        mock_service = Mock(spec=SpotifyTokenService)
        mock_service.store_tokens = AsyncMock(return_value=True)
        mock_service.is_authenticated = AsyncMock(return_value=False)
        mock_service.get_token_info = AsyncMock(return_value={
            "has_token": False,
            "is_expired": True,
            "scope": None,
            "expires_at": None,
            "created_at": None
        })
        return mock_service
    
    def test_oauth_imports_fail_without_implementation(self):
        """Test that OAuth imports fail until implemented"""
        # RED: This will fail until real implementation exists
        assert exchange_code_for_token is not None, "exchange_code_for_token not implemented yet"
        assert SpotifyTokenService is not None, "SpotifyTokenService not implemented yet"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_exchange_code_for_token_makes_real_api_call(self, mock_post, mock_spotify_config):
        """Test that exchange_code_for_token makes real HTTP request to Spotify"""
        # RED: This will fail - function still returns mock data
        
        # Mock successful Spotify response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "real_access_token",
            "refresh_token": "real_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "user-read-recently-played"
        }
        mock_post.return_value = mock_response
        
        # Call the function
        result = await exchange_code_for_token("test_code", mock_spotify_config)
        
        # Verify real API call was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check correct endpoint
        assert call_args[0][0] == "https://accounts.spotify.com/api/token"
        
        # Check correct data sent
        assert call_args[1]["data"]["grant_type"] == "authorization_code"
        assert call_args[1]["data"]["code"] == "test_code"
        assert call_args[1]["data"]["redirect_uri"] == "http://localhost:8000/callback"
        assert call_args[1]["data"]["client_id"] == "test_client_id"
        assert call_args[1]["data"]["client_secret"] == "test_client_secret"
        
        # Check result is from real API
        assert result["access_token"] == "real_access_token"
        assert result["refresh_token"] == "real_refresh_token"
        assert result != {"access_token": "mock_access_token"}  # Should not be mock data
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_exchange_code_handles_spotify_error(self, mock_post, mock_spotify_config):
        """Test error handling in token exchange"""
        # RED: This will fail - error handling not implemented
        
        # Mock Spotify error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Invalid authorization code"
        }
        mock_post.return_value = mock_response
        
        # Should raise HTTPException for Spotify errors
        with pytest.raises(HTTPException) as exc_info:
            await exchange_code_for_token("invalid_code", mock_spotify_config)
        
        assert exc_info.value.status_code == 400
        assert "invalid_grant" in str(exc_info.value.detail)
    
    def test_auth_callback_stores_tokens_in_database(self, mock_token_service, mock_startup_service):
        """Test that auth callback stores tokens using SpotifyTokenService"""
        # RED: This will fail - callback doesn't use token service yet
        
        if router is None:
            pytest.skip("Router not available")
        
        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Mock the startup service dependency
        def override_startup_service():
            return mock_startup_service
        
        app.dependency_overrides[get_startup_service_dependency] = override_startup_service
        
        # Mock successful token exchange
        with patch('api.routes.spotify.exchange_code_for_token') as mock_exchange, \
             patch('api.routes.spotify.SpotifyTokenService') as mock_token_class:
            
            mock_token_class.return_value = mock_token_service
            mock_exchange.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token", 
                "expires_in": 3600,
                "scope": "user-read-recently-played"
            }
            
            # Make callback request
            response = client.get("/spotify/auth/callback?code=test_code")
            
            # Verify response
            assert response.status_code == 200
            
            # Verify token service was used to store tokens
            mock_token_service.store_tokens.assert_called_once()
            call_args = mock_token_service.store_tokens.call_args[0][0]
            assert call_args["access_token"] == "test_access_token"
            assert call_args["refresh_token"] == "test_refresh_token"
    
    def test_auth_status_endpoint_exists(self, mock_startup_service):
        """Test that auth status endpoint exists and works"""
        # RED: This will fail - endpoint doesn't exist yet
        
        if router is None:
            pytest.skip("Router not available")
        
        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Mock the startup service dependency
        def override_startup_service():
            return mock_startup_service
        
        app.dependency_overrides[get_startup_service_dependency] = override_startup_service
        
        # Request auth status
        response = client.get("/spotify/auth/status")
        
        # Should return status information
        assert response.status_code == 200
        data = response.json()
        
        # Should have required fields
        assert "authenticated" in data
        assert "token_info" in data
        assert isinstance(data["authenticated"], bool)
    
    def test_auth_status_returns_authenticated_true_with_valid_token(self, mock_token_service, mock_startup_service):
        """Test auth status returns true when user has valid token"""
        # RED: This will fail - endpoint doesn't exist yet
        
        # Mock authenticated state
        mock_token_service.is_authenticated.return_value = True
        mock_token_service.get_token_info.return_value = {
            "has_token": True,
            "is_expired": False,
            "scope": "user-read-recently-played",
            "expires_at": "2024-12-31 23:59:59",
            "created_at": "2024-12-01 00:00:00"
        }
        
        if router is None:
            pytest.skip("Router not available")
        
        # Create test client with token service
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        def override_startup_service():
            return mock_startup_service
        
        app.dependency_overrides[get_startup_service_dependency] = override_startup_service
        
        with patch('api.routes.spotify.SpotifyTokenService') as mock_token_class:
            mock_token_class.return_value = mock_token_service
            
            response = client.get("/spotify/auth/status")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["authenticated"] is True
            assert data["token_info"]["has_token"] is True
            assert data["token_info"]["is_expired"] is False
    
    def test_auth_status_returns_authenticated_false_with_no_token(self, mock_token_service, mock_startup_service):
        """Test auth status returns false when user has no token"""
        # RED: This will fail - endpoint doesn't exist yet
        
        # Mock unauthenticated state  
        mock_token_service.is_authenticated.return_value = False
        mock_token_service.get_token_info.return_value = {
            "has_token": False,
            "is_expired": True,
            "scope": None,
            "expires_at": None,
            "created_at": None
        }
        
        if router is None:
            pytest.skip("Router not available")
        
        # Create test client
        from fastapi import FastAPI
        app = FastAPI()  
        app.include_router(router)
        client = TestClient(app)
        
        def override_startup_service():
            return mock_startup_service
        
        app.dependency_overrides[get_startup_service_dependency] = override_startup_service
        
        with patch('api.routes.spotify.SpotifyTokenService') as mock_token_class:
            mock_token_class.return_value = mock_token_service
            
            response = client.get("/spotify/auth/status")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["authenticated"] is False
            assert data["token_info"]["has_token"] is False
            assert data["token_info"]["is_expired"] is True


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])