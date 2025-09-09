"""
Spotify Token Service

Manages OAuth tokens for Spotify API authentication, including storage,
refresh, and validation of user access tokens.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx

from core.database import DatabaseService
from config.factory import get_config

logger = logging.getLogger(__name__)


class SpotifyTokenService:
    """Service for managing Spotify OAuth tokens"""
    
    def __init__(self, db_service: DatabaseService = None, config = None):
        """Initialize the service with database and config dependencies"""
        self.db_service = db_service or DatabaseService()
        self.config = config or get_config()
        
        # Spotify OAuth endpoints
        self.token_url = "https://accounts.spotify.com/api/token"
        
        # Token refresh threshold (refresh if expires within 5 minutes)
        self.refresh_threshold = timedelta(minutes=5)
    
    async def store_tokens(self, token_data: Dict[str, Any]) -> bool:
        """
        Store or update Spotify OAuth tokens in database
        
        Args:
            token_data: Token response from Spotify OAuth
                - access_token: The access token
                - refresh_token: The refresh token (optional)
                - expires_in: Seconds until expiration
                - scope: Granted scopes
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate expiry time
            expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            
            # Check if we already have tokens (single user setup)
            existing_token = await self.db_service.fetch_one(
                "SELECT id FROM spotify_tokens LIMIT 1"
            )
            
            if existing_token:
                # Update existing token
                await self.db_service.execute_query(
                    """
                    UPDATE spotify_tokens 
                    SET access_token = ?, 
                        refresh_token = COALESCE(?, refresh_token),
                        expires_at = ?, 
                        scope = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        token_data['access_token'],
                        token_data.get('refresh_token'),
                        expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                        token_data.get('scope'),
                        existing_token['id']
                    )
                )
                logger.info("Updated existing Spotify tokens")
            else:
                # Insert new token
                await self.db_service.execute_query(
                    """
                    INSERT INTO spotify_tokens 
                    (access_token, refresh_token, expires_at, scope)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        token_data['access_token'],
                        token_data.get('refresh_token'),
                        expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                        token_data.get('scope')
                    )
                )
                logger.info("Stored new Spotify tokens")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store Spotify tokens: {e}")
            return False
    
    async def get_valid_token(self) -> Optional[Dict[str, Any]]:
        """
        Get a valid (non-expired) access token
        
        Returns:
            Token data if valid, None if expired or not found
        """
        try:
            token_row = await self.db_service.fetch_one(
                """
                SELECT access_token, refresh_token, expires_at, scope, created_at, updated_at
                FROM spotify_tokens 
                ORDER BY updated_at DESC 
                LIMIT 1
                """
            )
            
            if not token_row:
                return None
            
            # Parse expiry time (handle both string and datetime objects)
            expires_at_str = token_row['expires_at']
            if isinstance(expires_at_str, datetime):
                expires_at = expires_at_str
            else:
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
            
            # Check if token is still valid
            if datetime.now() >= expires_at:
                logger.debug("Spotify token is expired")
                return None
            
            return dict(token_row)
            
        except Exception as e:
            logger.error(f"Failed to get valid token: {e}")
            return None
    
    async def refresh_token_if_needed(self) -> bool:
        """
        Refresh token if it's expired or about to expire
        
        Returns:
            True if token is valid or refresh successful, False otherwise
        """
        try:
            token_row = await self.db_service.fetch_one(
                """
                SELECT access_token, refresh_token, expires_at
                FROM spotify_tokens 
                ORDER BY updated_at DESC 
                LIMIT 1
                """
            )
            
            if not token_row:
                logger.debug("No tokens found")
                return False
            
            # Parse expiry time (handle both string and datetime objects)
            expires_at_str = token_row['expires_at']
            if isinstance(expires_at_str, datetime):
                expires_at = expires_at_str
            else:
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
            
            # Check if refresh is needed
            if datetime.now() + self.refresh_threshold < expires_at:
                logger.debug("Token is still valid, no refresh needed")
                return True
            
            # Need to refresh
            refresh_token = token_row['refresh_token']
            if not refresh_token:
                logger.error("No refresh token available")
                return False
            
            # Call Spotify token refresh endpoint
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        'grant_type': 'refresh_token',
                        'refresh_token': refresh_token,
                        'client_id': self.config.spotify.client_id,
                        'client_secret': self.config.spotify.client_secret,
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return False
            
            # Store new tokens
            new_token_data = response.json()
            success = await self.store_tokens(new_token_data)
            
            if success:
                logger.info("Successfully refreshed Spotify tokens")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return False
    
    async def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with Spotify
        
        Returns:
            True if valid token exists, False otherwise
        """
        token = await self.get_valid_token()
        return token is not None
    
    async def revoke_tokens(self) -> bool:
        """
        Revoke and remove all stored tokens
        
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.db_service.execute_query(
                "DELETE FROM spotify_tokens"
            )
            logger.info("Revoked all Spotify tokens")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke tokens: {e}")
            return False
    
    async def get_token_info(self) -> Dict[str, Any]:
        """
        Get metadata about the current token status
        
        Returns:
            Dictionary with token information
        """
        try:
            token_row = await self.db_service.fetch_one(
                """
                SELECT access_token, expires_at, scope, created_at, updated_at
                FROM spotify_tokens 
                ORDER BY updated_at DESC 
                LIMIT 1
                """
            )
            
            if not token_row:
                return {
                    "has_token": False,
                    "is_expired": True,
                    "scope": None,
                    "expires_at": None,
                    "created_at": None
                }
            
            # Parse expiry time (handle both string and datetime objects)
            expires_at_str = token_row['expires_at']
            if isinstance(expires_at_str, datetime):
                expires_at = expires_at_str
            else:
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
            is_expired = datetime.now() >= expires_at
            
            return {
                "has_token": True,
                "is_expired": is_expired,
                "scope": token_row['scope'],
                "expires_at": token_row['expires_at'],
                "created_at": token_row['created_at']
            }
            
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return {
                "has_token": False,
                "is_expired": True,
                "scope": None,
                "expires_at": None,
                "created_at": None
            }