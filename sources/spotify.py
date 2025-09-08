import httpx
import asyncio
import logging
import urllib.parse
import json
import hashlib
import base64
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .base import BaseSource, DataItem
from config.models import SpotifyConfig
from core.database import DatabaseService
from core.retry_utils import (
    RetryExecutor,
    create_api_retry_config,
    create_enhanced_api_retry_condition,
    create_rate_limit_retry_config,
    RetryConfig,
    BackoffStrategy,
)
from core.http_client_mixin import BaseHTTPSource

logger = logging.getLogger(__name__)


class SpotifySource(BaseHTTPSource, BaseSource):
    """Spotify Web API source for recently played tracks"""
    
    def __init__(self, config: SpotifyConfig, db_service: DatabaseService = None):
        """
        Initialize SpotifySource with configuration.
        
        Args:
            config: SpotifyConfig instance containing API configuration
            db_service: DatabaseService instance for data operations
        """
        super().__init__(config, "spotify")
        self.config = config
        self.db_service = db_service
        self.access_token = None
        self.token_expires_at = None
        self.base_url = "https://api.spotify.com/v1"
        
        # Validate configuration
        if not self.config.enabled:
            raise ValueError("Spotify source is disabled")
        if not self.config.client_id or not self.config.client_id.strip():
            raise ValueError("client_id is required")
        if not self.config.client_secret or not self.config.client_secret.strip():
            raise ValueError("client_secret is required")

    def is_configured(self) -> bool:
        """Check if the source is fully configured"""
        return self.config.is_fully_configured()
    
    def _create_client_config(self) -> Dict[str, Any]:
        """Create HTTP client configuration for Spotify API"""
        if not self.is_configured():
            raise ValueError("Spotify source is not configured.")
        
        return {
            "base_url": self.base_url,
            "headers": {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            },
            "timeout": self.config.request_timeout
        }
    
    def get_source_type(self) -> str:
        """
        Return the source type identifier.
        
        Returns:
            Source type string
        """
        return "spotify_api"
    
    async def _get_access_token(self) -> str:
        """
        Get or refresh access token using client credentials flow.
        
        Returns:
            Valid access token
            
        Raises:
            Exception: If token acquisition fails
        """
        # Check if current token is still valid
        if (self.access_token and self.token_expires_at and 
            datetime.now(timezone.utc).timestamp() < self.token_expires_at - 300):  # 5 min buffer
            return self.access_token
        
        # Get new token using client credentials flow
        auth_string = f"{self.config.client_id}:{self.config.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://accounts.spotify.com/api/token",
                    headers=headers,
                    data=data,
                    timeout=self.config.request_timeout
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data["access_token"]
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expires_at = datetime.now(timezone.utc).timestamp() + expires_in
                    return self.access_token
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_msg = error_data.get("error_description", f"HTTP {response.status_code}")
                    raise Exception(f"Failed to get access token: {error_msg}")
                    
            except httpx.RequestError as e:
                raise Exception(f"Network error getting access token: {e}")
    
    async def _make_test_request(self, client: httpx.AsyncClient) -> httpx.Response:
        """Make a test request to verify Spotify API connectivity"""
        return await client.get("/me")
    
    async def test_connection(self) -> bool:
        """
        Test API connectivity.
        
        Returns:
            True if connection is successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("Spotify source is not configured. Connection test skipped.")
            return False
        
        try:
            # Get access token first
            await self._get_access_token()
            
            # Test with /me endpoint
            return await super().test_connection()
            
        except Exception as e:
            logger.error(f"Spotify connection test failed: {e}")
            return False

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """
        Fetch recently played tracks from Spotify.
        
        Args:
            since: Optional datetime to fetch items since (not used by this API)
            limit: Maximum number of items to fetch (will use config.recently_played_limit)
            
        Yields:
            DataItem instances containing track data
        """
        logger.info(f"Starting Spotify fetch - configured: {self.is_configured()}")
        
        if not self.is_configured():
            logger.warning("Spotify source is not configured. Skipping data fetch.")
            return

        try:
            # Get access token
            await self._get_access_token()
            
            # Create client with auth headers
            client = await self._ensure_client()
            
            # Build request parameters
            params = {
                "limit": str(min(self.config.recently_played_limit, 50))  # Spotify API max is 50
            }
            
            logger.info(f"Fetching up to {params['limit']} recently played tracks from Spotify")
            
            # Make API request with retries
            response = await self._make_request_with_retry(client, "/me/player/recently-played", params)
            
            if not response:
                logger.error("Failed to fetch recently played tracks from Spotify API")
                return
            
            data = response.json()
            items = data.get("items", [])
            logger.info(f"Spotify API returned {len(items)} tracks")
            
            if not items:
                logger.info("No recently played tracks returned from Spotify API")
                return
            
            # Extract track IDs for audio features
            track_ids = [item["track"]["id"] for item in items if item.get("track", {}).get("id")]
            audio_features_map = {}
            
            if track_ids:
                # Fetch audio features in batches (max 100 per request)
                for i in range(0, len(track_ids), 100):
                    batch_ids = track_ids[i:i+100]
                    features_response = await self._make_request_with_retry(
                        client, 
                        "/audio-features", 
                        {"ids": ",".join(batch_ids)}
                    )
                    
                    if features_response:
                        features_data = features_response.json()
                        for feature in features_data.get("audio_features", []):
                            if feature:  # Some tracks might not have audio features
                                audio_features_map[feature["id"]] = feature
            
            # Transform and yield items
            for item in items:
                track_id = item.get("track", {}).get("id")
                audio_features = audio_features_map.get(track_id) if track_id else None
                
                data_item = self._transform_track(item, audio_features)
                if data_item:
                    yield data_item
                    
            logger.info(f"Successfully fetched {len(items)} Spotify tracks")
            
        except Exception as e:
            logger.error(f"Error fetching Spotify tracks: {e}")
            raise Exception(f"Failed to fetch recently played tracks: {e}")
    
    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """
        Get specific track by ID.
        
        Note: The Spotify API doesn't support fetching individual recently played items by ID,
        so this method returns None.
        
        Args:
            source_id: Track ID (unused)
            
        Returns:
            None (not supported by this API)
        """
        logger.warning("Individual track fetching not supported by Spotify recently played API")
        return None
    
    def _transform_track(self, track_item: Dict[str, Any], audio_features: Optional[Dict[str, Any]] = None) -> Optional[DataItem]:
        """
        Transform Spotify track to standardized DataItem.
        
        Args:
            track_item: Raw track data from Spotify API
            audio_features: Optional audio features data
            
        Returns:
            DataItem instance or None if transformation fails
        """
        try:
            track = track_item.get("track", {})
            played_at = track_item.get("played_at", "")
            
            track_id = track.get("id", "")
            track_name = track.get("name", "")
            
            if not track_id or not track_name or not played_at:
                logger.warning(f"Skipping track missing required fields: {track_item}")
                return None
            
            # Create source_id combining track_id and played_at timestamp
            source_id = f"{track_id}_{played_at}"
            
            # Prepare track data
            track_data = {
                "id": track_id,
                "name": track_name,
                "artists": track.get("artists", []),
                "album": track.get("album", {}),
                "duration_ms": track.get("duration_ms", 0),
                "preview_url": track.get("preview_url"),
                "external_urls": track.get("external_urls", {}),
                "popularity": track.get("popularity")
            }
            
            # Prepare complete data structure
            data = {
                "track": track_data,
                "played_at": played_at,
                "audio_features": audio_features
            }
            
            # Create searchable content
            artists_str = ", ".join([artist.get("name", "") for artist in track_data["artists"]])
            album_name = track_data["album"].get("name", "")
            content_parts = [track_name]
            if artists_str:
                content_parts.append(f"by {artists_str}")
            if album_name:
                content_parts.append(f"from {album_name}")
            content = " ".join(content_parts)
            
            # Parse played_at datetime
            created_at = None
            if played_at:
                try:
                    if played_at.endswith('Z'):
                        created_at = datetime.fromisoformat(played_at.replace('Z', '+00:00'))
                    else:
                        created_at = datetime.fromisoformat(played_at)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse played_at datetime '{played_at}': {e}")
            
            return DataItem(
                namespace=self.namespace,
                source_id=source_id,
                content=content,
                metadata=data,
                created_at=created_at,
                updated_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error transforming Spotify track: {e}")
            return None
    
    async def _make_request_with_retry(
        self, 
        client: httpx.AsyncClient, 
        endpoint: str, 
        params: Dict[str, Any]
    ) -> Optional[httpx.Response]:
        """
        Make HTTP request with retry logic using the unified retry framework.
        
        Args:
            client: HTTP client instance
            endpoint: API endpoint to call
            params: Request parameters
            
        Returns:
            Response object or None if all retries failed
        """
        # Log the request for debugging
        query_string = urllib.parse.urlencode(params)
        full_url = f"{self.base_url}{endpoint}?{query_string}"
        logger.info(f"Spotify API Request: {full_url}")
        
        # Create enhanced retry configuration
        retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_delay,
            max_delay=60.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            rate_limit_base_delay=30.0,
            rate_limit_max_delay=self.config.rate_limit_max_delay,
            respect_retry_after=self.config.respect_retry_after,
            jitter=True
        )
        retry_condition = create_enhanced_api_retry_condition()
        retry_executor = RetryExecutor(retry_config, retry_condition)
        
        async def make_request():
            response = await client.get(endpoint, params=params)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                # Rate limited
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    logger.warning(f"Rate limited, retry after {retry_after} seconds")
                raise Exception(f"Rate limited: {response.status_code}")
            elif response.status_code in [500, 502, 503, 504]:
                # Server errors - retryable
                response.raise_for_status()
            elif response.status_code == 401:
                # Unauthorized - try to refresh token
                logger.warning("Access token expired, refreshing...")
                await self._get_access_token()
                # Update client headers
                client.headers["Authorization"] = f"Bearer {self.access_token}"
                response.raise_for_status()
            else:
                # Non-retryable error
                logger.error(f"Spotify API request failed with status {response.status_code}: {response.text}")
                return None
        
        try:
            result = await retry_executor.execute_async(make_request)
            return result.result if result.success else None
        except Exception as e:
            logger.error(f"Spotify request failed after all retries: {e}")
            return None

    async def get_sync_metadata(self) -> Dict[str, Any]:
        """
        Return sync metadata.
        
        Returns:
            Dictionary containing sync metadata
        """
        return {
            "source_type": self.get_source_type(),
            "namespace": self.namespace,
            "is_configured": self.is_configured(),
            "recently_played_limit": self.config.recently_played_limit,
            "sync_interval_hours": self.config.sync_interval_hours,
            "last_sync": datetime.now(timezone.utc).isoformat()
        }