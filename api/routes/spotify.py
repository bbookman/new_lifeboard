"""
Spotify API routes for retrieving Spotify track data and OAuth authentication.
"""
import logging
import json
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.dependencies import get_startup_service_dependency
from services.startup import StartupService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/spotify", tags=["spotify"])


class SpotifyTrack(BaseModel):
    """Spotify track response model."""
    id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    played_at: str
    preview_url: Optional[str]
    external_urls: Dict[str, str]
    audio_features: Dict[str, Any]


class AuthUrlResponse(BaseModel):
    """OAuth authorization URL response."""
    auth_url: str


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int


def validate_date_format(date_str: str) -> bool:
    """Validate date string format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False


def transform_spotify_data_item(row: Dict[str, Any]) -> SpotifyTrack:
    """Transform database row to SpotifyTrack object."""
    try:
        # Parse content JSON
        content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
        
        # Parse metadata JSON
        metadata = {}
        if row["metadata"]:
            metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        
        # Extract artist name (first artist)
        artist = "Unknown Artist"
        if content.get("artists") and len(content["artists"]) > 0:
            artist = content["artists"][0].get("name", "Unknown Artist")
        
        # Extract audio features
        audio_features = metadata.get("audio_features", {})
        
        return SpotifyTrack(
            id=content.get("id", ""),
            title=content.get("name", "Unknown Title"),
            artist=artist,
            album=content.get("album", {}).get("name", "Unknown Album"),
            duration_ms=content.get("duration_ms", 0),
            played_at=content.get("played_at", ""),
            preview_url=content.get("preview_url"),
            external_urls=content.get("external_urls", {}),
            audio_features=audio_features
        )
    except Exception as e:
        logger.error(f"Error transforming Spotify data item: {e}")
        # Return a default track object for malformed data
        return SpotifyTrack(
            id="unknown",
            title="Unknown Title",
            artist="Unknown Artist",
            album="Unknown Album",
            duration_ms=0,
            played_at="",
            preview_url=None,
            external_urls={},
            audio_features={}
        )


@router.get("/recent", response_model=List[SpotifyTrack])
async def get_recent_tracks(
    date: Optional[str] = Query(None, description="Filter by date in YYYY-MM-DD format"),
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Get recently played Spotify tracks."""
    try:
        logger.info(f"Getting recent Spotify tracks - date: {date}")
        
        # Validate date format if provided
        if date and not validate_date_format(date):
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
        # Build query conditions
        conditions = ["namespace = ?"]
        params = ["spotify"]
        
        if date:
            conditions.append("days_date = ?")
            params.append(date)
        
        # Build the query
        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT id, namespace, source_id, content, metadata, 
                   embedding_status, created_at, updated_at, days_date
            FROM data_items
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT 50
        """
        params.append(50)
        
        with startup_service.database.get_connection() as conn:
            cursor = conn.execute(query, params)
            tracks = []
            
            for row in cursor.fetchall():
                # Convert row to dict
                row_dict = {
                    "id": row["id"],
                    "namespace": row["namespace"],
                    "source_id": row["source_id"],
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "embedding_status": row["embedding_status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "days_date": row["days_date"]
                }
                
                # Transform to SpotifyTrack
                track = transform_spotify_data_item(row_dict)
                tracks.append(track)
        
        logger.info(f"Retrieved {len(tracks)} recent Spotify tracks")
        return tracks
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recent Spotify tracks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tracks", response_model=List[SpotifyTrack])
async def get_tracks(
    date: Optional[str] = Query(None, description="Filter by date in YYYY-MM-DD format"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of tracks to return"),
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Get Spotify tracks with optional filtering."""
    try:
        logger.info(f"Getting Spotify tracks - date: {date}, limit: {limit}")
        
        # Validate date format if provided
        if date and not validate_date_format(date):
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
        # Build query conditions - always filter by spotify namespace
        conditions = ["namespace = ?"]
        params = ["spotify"]
        
        if date:
            conditions.append("days_date = ?")
            params.append(date)
        
        # Build the query
        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT id, namespace, source_id, content, metadata, 
                   embedding_status, created_at, updated_at, days_date
            FROM data_items
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        logger.info(f"Executing Spotify tracks query: {query} with params: {params}")

        with startup_service.database.get_connection() as conn:
            cursor = conn.execute(query, params)
            tracks = []
            
            for row in cursor.fetchall():
                # Convert row to dict
                row_dict = {
                    "id": row["id"],
                    "namespace": row["namespace"],
                    "source_id": row["source_id"],
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "embedding_status": row["embedding_status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "days_date": row["days_date"]
                }
                
                # Transform to SpotifyTrack
                track = transform_spotify_data_item(row_dict)
                tracks.append(track)
        
        logger.info(f"Retrieved {len(tracks)} Spotify tracks")
        return tracks
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Spotify tracks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/url", response_model=AuthUrlResponse)
async def get_auth_url(
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Get Spotify OAuth authorization URL."""
    try:
        logger.info("Generating Spotify authorization URL")
        
        # Get Spotify config
        config = startup_service.config.spotify
        
        if not config.is_api_configured():
            raise HTTPException(status_code=500, detail="Spotify API not configured")
        
        # Build authorization URL
        params = {
            "client_id": config.client_id,
            "response_type": "code",
            "redirect_uri": config.redirect_uri,
            "scope": " ".join(config.required_scopes),
            "show_dialog": "true"
        }
        
        auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
        
        logger.info("Generated Spotify authorization URL")
        return AuthUrlResponse(auth_url=auth_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Spotify auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback", response_model=TokenResponse)
async def auth_callback(
    code: Optional[str] = Query(None, description="Authorization code from Spotify"),
    error: Optional[str] = Query(None, description="Error from Spotify OAuth"),
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Handle Spotify OAuth callback."""
    try:
        logger.info("Handling Spotify OAuth callback")
        
        # Check for OAuth error
        if error:
            logger.error(f"Spotify OAuth error: {error}")
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        # Check for authorization code
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
        
        # Exchange code for token (mock implementation for now)
        # In a real implementation, this would make an HTTP request to Spotify's token endpoint
        token_data = exchange_code_for_token(code, startup_service.config.spotify)
        
        logger.info("Successfully exchanged code for token")
        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data["expires_in"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Spotify OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def exchange_code_for_token(code: str, config) -> Dict[str, Any]:
    """Exchange authorization code for access token."""
    # Mock implementation for testing
    # In real implementation, this would make HTTP request to:
    # POST https://accounts.spotify.com/api/token
    return {
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer"
    }