"""
Test for Spotify token service

Following TDD approach - these tests should fail initially (RED phase)
until the SpotifyTokenService is implemented.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import sqlite3
import os

# Import the service - should now work with implementation
from services.spotify_token_service import SpotifyTokenService

# Mock config and database service imports
try:
    from config.factory import get_config
    from core.database import DatabaseService
except ImportError:
    get_config = None
    DatabaseService = None


class TestSpotifyTokenService:
    """Test suite for Spotify token service"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        
        # Create spotify_tokens table for testing
        conn.execute("""
            CREATE TABLE spotify_tokens (
                id INTEGER PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at TIMESTAMP NOT NULL,
                scope TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        yield conn
        conn.close()
        os.close(fd)
        os.unlink(path)
    
    @pytest.fixture
    def mock_db_service(self, temp_db):
        """Mock database service"""
        mock_service = Mock(spec=DatabaseService)
        mock_service.get_connection.return_value = temp_db
        mock_service.execute_query = AsyncMock()
        mock_service.fetch_one = AsyncMock()
        mock_service.fetch_all = AsyncMock()
        return mock_service
    
    @pytest.fixture
    def mock_config(self):
        """Mock Spotify configuration"""
        mock_config = Mock()
        mock_config.spotify.client_id = "test_client_id"
        mock_config.spotify.client_secret = "test_client_secret"
        mock_config.spotify.redirect_uri = "http://localhost:8000/callback"
        return mock_config
    
    @pytest.fixture
    def service(self, mock_db_service, mock_config):
        """Create SpotifyTokenService instance for testing"""
        return SpotifyTokenService(
            db_service=mock_db_service,
            config=mock_config
        )
    
    def test_service_initialization_succeeds_with_implementation(self):
        """Test that service can be imported and initialized"""
        # GREEN: This should now pass with service implemented
        assert SpotifyTokenService is not None, "SpotifyTokenService should be implemented"
        
        # Test basic initialization
        service = SpotifyTokenService()
        assert service is not None, "Service should initialize successfully"
        assert hasattr(service, 'store_tokens'), "Service should have store_tokens method"
        assert hasattr(service, 'get_valid_token'), "Service should have get_valid_token method"
    
    @pytest.mark.asyncio
    async def test_store_tokens_creates_new_entry(self, service, mock_db_service):
        """Test storing new tokens creates database entry"""
        # Mock no existing token (should trigger INSERT)
        mock_db_service.fetch_one.return_value = None
        
        token_data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "scope": "user-read-recently-played"
        }
        
        result = await service.store_tokens(token_data)
        
        assert result is True, "Token storage should succeed"
        
        # Verify database call was made
        mock_db_service.execute_query.assert_called_once()
        call_args = mock_db_service.execute_query.call_args
        
        # Check SQL contains INSERT
        assert "INSERT" in call_args[0][0], "Should execute INSERT statement"
        assert "spotify_tokens" in call_args[0][0], "Should insert into spotify_tokens table"
        
        # Check token values were passed
        assert "test_access_token" in call_args[0][1], "Should include access token"
        assert "test_refresh_token" in call_args[0][1], "Should include refresh token"
    
    @pytest.mark.asyncio
    async def test_store_tokens_updates_existing_entry(self, service, mock_db_service):
        """Test storing tokens updates existing entry instead of creating duplicate"""
        # Mock existing token found (first call), then UPDATE (second call)
        mock_db_service.fetch_one.side_effect = [
            {
                "id": 1,
                "access_token": "old_token",
                "expires_at": datetime.now() + timedelta(minutes=30)
            },
            None  # For any subsequent calls
        ]
        
        token_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "scope": "user-read-recently-played"
        }
        
        result = await service.store_tokens(token_data)
        
        assert result is True, "Token update should succeed"
        
        # Should call UPDATE not INSERT
        call_args = mock_db_service.execute_query.call_args
        assert "UPDATE" in call_args[0][0], "Should execute UPDATE statement"
    
    @pytest.mark.asyncio
    async def test_get_valid_token_returns_unexpired_token(self, service, mock_db_service):
        """Test getting valid token returns unexpired token"""
        # RED: This will fail - method not implemented
        
        future_expiry = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.return_value = {
            "access_token": "valid_token",
            "refresh_token": "valid_refresh",
            "expires_at": future_expiry,
            "scope": "user-read-recently-played"
        }
        
        token = await service.get_valid_token()
        
        assert token is not None, "Should return valid token"
        assert token["access_token"] == "valid_token", "Should return correct access token"
        assert token["expires_at"] == future_expiry, "Should include expiry time"
    
    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_expired(self, service, mock_db_service):
        """Test getting valid token returns None for expired token"""
        # RED: This will fail - method not implemented
        
        past_expiry = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.return_value = {
            "access_token": "expired_token",
            "expires_at": past_expiry
        }
        
        token = await service.get_valid_token()
        
        assert token is None, "Should return None for expired token"
    
    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_no_token(self, service, mock_db_service):
        """Test getting valid token returns None when no token stored"""
        # RED: This will fail - method not implemented
        
        mock_db_service.fetch_one.return_value = None
        
        token = await service.get_valid_token()
        
        assert token is None, "Should return None when no token stored"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_refresh_token_if_needed_refreshes_expired_token(
        self, mock_post, service, mock_db_service
    ):
        """Test token refresh when current token is expired"""
        # RED: This will fail - method not implemented
        
        # Mock expired token (first call), then existing token (second call for store_tokens)
        past_expiry = (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.side_effect = [
            {
                "access_token": "expired_token",
                "refresh_token": "valid_refresh",
                "expires_at": past_expiry
            },
            {
                "id": 1,
                "access_token": "expired_token",
                "refresh_token": "valid_refresh",
                "expires_at": past_expiry
            }
        ]
        
        # Mock Spotify token refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "user-read-recently-played"
        }
        mock_post.return_value = mock_response
        
        result = await service.refresh_token_if_needed()
        
        assert result is True, "Token refresh should succeed"
        
        # Verify Spotify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://accounts.spotify.com/api/token"
        
        # Verify token was stored
        mock_db_service.execute_query.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_skips_valid_token(self, service, mock_db_service):
        """Test token refresh skipped when current token is valid"""
        # RED: This will fail - method not implemented
        
        # Mock valid token (expires in 1 hour)
        future_expiry = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.return_value = {
            "access_token": "valid_token",
            "refresh_token": "valid_refresh",
            "expires_at": future_expiry
        }
        
        result = await service.refresh_token_if_needed()
        
        assert result is True, "Should succeed without refresh"
        
        # Should not call execute_query for UPDATE (no refresh needed)
        assert not mock_db_service.execute_query.called, "Should not update database"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_refresh_token_handles_refresh_failure(
        self, mock_post, service, mock_db_service
    ):
        """Test token refresh handles Spotify API errors"""
        # RED: This will fail - method not implemented
        
        # Mock expired token
        past_expiry = (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.return_value = {
            "access_token": "expired_token",
            "refresh_token": "invalid_refresh",
            "expires_at": past_expiry
        }
        
        # Mock failed Spotify response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Invalid refresh token"
        }
        mock_post.return_value = mock_response
        
        result = await service.refresh_token_if_needed()
        
        assert result is False, "Should return False on refresh failure"
        
        # Should not update database with invalid token
        assert not mock_db_service.execute_query.called, "Should not store invalid token"
    
    @pytest.mark.asyncio
    async def test_is_authenticated_true_with_valid_token(self, service, mock_db_service):
        """Test authentication status with valid token"""
        # RED: This will fail - method not implemented
        
        future_expiry = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.return_value = {
            "access_token": "valid_token",
            "expires_at": future_expiry
        }
        
        is_auth = await service.is_authenticated()
        
        assert is_auth is True, "Should be authenticated with valid token"
    
    @pytest.mark.asyncio
    async def test_is_authenticated_false_with_expired_token(self, service, mock_db_service):
        """Test authentication status with expired token"""
        # RED: This will fail - method not implemented
        
        past_expiry = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        mock_db_service.fetch_one.return_value = {
            "access_token": "expired_token",
            "expires_at": past_expiry
        }
        
        is_auth = await service.is_authenticated()
        
        assert is_auth is False, "Should not be authenticated with expired token"
    
    @pytest.mark.asyncio
    async def test_is_authenticated_false_with_no_token(self, service, mock_db_service):
        """Test authentication status with no token"""
        # RED: This will fail - method not implemented
        
        mock_db_service.fetch_one.return_value = None
        
        is_auth = await service.is_authenticated()
        
        assert is_auth is False, "Should not be authenticated with no token"
    
    @pytest.mark.asyncio
    async def test_revoke_tokens_removes_stored_tokens(self, service, mock_db_service):
        """Test token revocation removes tokens from database"""
        # RED: This will fail - method not implemented
        
        result = await service.revoke_tokens()
        
        assert result is True, "Token revocation should succeed"
        
        # Verify DELETE query was executed
        mock_db_service.execute_query.assert_called_once()
        call_args = mock_db_service.execute_query.call_args
        assert "DELETE" in call_args[0][0], "Should execute DELETE statement"
        assert "spotify_tokens" in call_args[0][0], "Should delete from spotify_tokens table"
    
    @pytest.mark.asyncio
    async def test_get_token_info_returns_metadata(self, service, mock_db_service):
        """Test getting token metadata information"""
        # RED: This will fail - method not implemented
        
        mock_token = {
            "access_token": "test_token",
            "expires_at": (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'),
            "scope": "user-read-recently-played",
            "created_at": (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": (datetime.now() - timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
        }
        mock_db_service.fetch_one.return_value = mock_token
        
        info = await service.get_token_info()
        
        assert info is not None, "Should return token info"
        assert info["has_token"] is True, "Should indicate token exists"
        assert info["is_expired"] is False, "Should indicate token is not expired"
        assert info["scope"] == "user-read-recently-played", "Should include scope"
        assert "expires_at" in info, "Should include expiry time"
        assert "created_at" in info, "Should include creation time"
    
    @pytest.mark.asyncio 
    async def test_get_token_info_handles_no_token(self, service, mock_db_service):
        """Test getting token info when no token exists"""
        # RED: This will fail - method not implemented
        
        mock_db_service.fetch_one.return_value = None
        
        info = await service.get_token_info()
        
        assert info is not None, "Should return info object"
        assert info["has_token"] is False, "Should indicate no token"
        assert info["is_expired"] is True, "Should consider no token as expired"
        assert info["scope"] is None, "Should have no scope"


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])