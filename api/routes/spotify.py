"""
Spotify API routes for retrieving Spotify track data and OAuth authentication.
"""
import logging
import json
import urllib.parse
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core.dependencies import get_startup_service_dependency
from services.startup import StartupService
from services.spotify_token_service import SpotifyTokenService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/spotify", tags=["spotify"])


class SpotifyImage(BaseModel):
    """Spotify image model."""
    url: str
    height: Optional[int] = None
    width: Optional[int] = None


class SpotifyArtist(BaseModel):
    """Spotify artist model."""
    id: str
    name: str
    external_urls: Dict[str, str]
    genres: Optional[List[str]] = None
    popularity: Optional[int] = None
    followers: Optional[Dict[str, Any]] = None


class SpotifyAlbum(BaseModel):
    """Spotify album model."""
    id: str
    name: str
    artists: List[SpotifyArtist]
    images: List[SpotifyImage]
    external_urls: Dict[str, str]
    release_date: str
    release_date_precision: str
    total_tracks: int
    album_type: str
    genres: Optional[List[str]] = None
    popularity: Optional[int] = None


class SpotifyAudioFeatures(BaseModel):
    """Spotify audio features model."""
    danceability: float
    energy: float
    key: int
    loudness: float
    mode: int
    speechiness: float
    acousticness: float
    instrumentalness: float
    liveness: float
    valence: float
    tempo: float
    duration_ms: int
    time_signature: int


class SpotifyTrack(BaseModel):
    """Comprehensive Spotify track response model."""
    id: str
    name: str
    artists: List[SpotifyArtist]
    album: SpotifyAlbum
    duration_ms: int
    popularity: int
    explicit: bool
    preview_url: Optional[str]
    external_urls: Dict[str, str]
    external_ids: Dict[str, str]
    available_markets: List[str]
    disc_number: int
    track_number: int
    is_local: bool
    audio_features: Optional[SpotifyAudioFeatures] = None
    played_at: Optional[str] = None  # For recently played tracks


class AuthUrlResponse(BaseModel):
    """OAuth authorization URL response."""
    auth_url: str


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int


class TokenInfo(BaseModel):
    """Token information response."""
    has_token: bool
    is_expired: bool
    scope: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


class AuthStatusResponse(BaseModel):
    """Authentication status response."""
    authenticated: bool
    token_info: TokenInfo


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
    """Transform database row to comprehensive SpotifyTrack object."""
    try:
        # Parse content JSON
        content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
        
        # Parse metadata JSON
        metadata = {}
        if row["metadata"]:
            metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        
        # Transform artists to SpotifyArtist objects
        artists = []
        for artist_data in content.get("artists", []):
            artists.append(SpotifyArtist(
                id=artist_data.get("id", ""),
                name=artist_data.get("name", "Unknown Artist"),
                external_urls=artist_data.get("external_urls", {}),
                genres=artist_data.get("genres"),
                popularity=artist_data.get("popularity"),
                followers=artist_data.get("followers")
            ))
        
        # If no artists in content, create default
        if not artists:
            artists = [SpotifyArtist(
                id="",
                name="Unknown Artist", 
                external_urls={}
            )]
        
        # Transform album to SpotifyAlbum object
        album_data = content.get("album", {})
        album_artists = []
        for artist_data in album_data.get("artists", []):
            album_artists.append(SpotifyArtist(
                id=artist_data.get("id", ""),
                name=artist_data.get("name", "Unknown Artist"),
                external_urls=artist_data.get("external_urls", {})
            ))
        
        if not album_artists:
            album_artists = artists  # Fallback to track artists
        
        # Transform album images to SpotifyImage objects
        images = []
        for image_data in album_data.get("images", []):
            images.append(SpotifyImage(
                url=image_data.get("url", ""),
                height=image_data.get("height"),
                width=image_data.get("width")
            ))
        
        album = SpotifyAlbum(
            id=album_data.get("id", ""),
            name=album_data.get("name", "Unknown Album"),
            artists=album_artists,
            images=images,
            external_urls=album_data.get("external_urls", {}),
            release_date=album_data.get("release_date", ""),
            release_date_precision=album_data.get("release_date_precision", "day"),
            total_tracks=album_data.get("total_tracks", 0),
            album_type=album_data.get("album_type", "album"),
            genres=album_data.get("genres"),
            popularity=album_data.get("popularity")
        )
        
        # Transform audio features to SpotifyAudioFeatures object
        audio_features_data = metadata.get("audio_features", {})
        audio_features = None
        if audio_features_data:
            audio_features = SpotifyAudioFeatures(
                danceability=audio_features_data.get("danceability", 0.0),
                energy=audio_features_data.get("energy", 0.0),
                key=audio_features_data.get("key", 0),
                loudness=audio_features_data.get("loudness", 0.0),
                mode=audio_features_data.get("mode", 0),
                speechiness=audio_features_data.get("speechiness", 0.0),
                acousticness=audio_features_data.get("acousticness", 0.0),
                instrumentalness=audio_features_data.get("instrumentalness", 0.0),
                liveness=audio_features_data.get("liveness", 0.0),
                valence=audio_features_data.get("valence", 0.0),
                tempo=audio_features_data.get("tempo", 0.0),
                duration_ms=audio_features_data.get("duration_ms", content.get("duration_ms", 0)),
                time_signature=audio_features_data.get("time_signature", 4)
            )
        
        # Extract played_at from metadata or content
        played_at = metadata.get("played_at") or content.get("played_at")
        
        return SpotifyTrack(
            id=content.get("id", ""),
            name=content.get("name", "Unknown Title"),
            artists=artists,
            album=album,
            duration_ms=content.get("duration_ms", 0),
            popularity=content.get("popularity", 0),
            explicit=content.get("explicit", False),
            preview_url=content.get("preview_url"),
            external_urls=content.get("external_urls", {}),
            external_ids=content.get("external_ids", {}),
            available_markets=content.get("available_markets", []),
            disc_number=content.get("disc_number", 1),
            track_number=content.get("track_number", 0),
            is_local=content.get("is_local", False),
            audio_features=audio_features,
            played_at=played_at
        )
    except Exception as e:
        logger.error(f"Error transforming Spotify data item: {e}")
        # Return a default track object for malformed data
        default_artist = SpotifyArtist(id="", name="Unknown Artist", external_urls={})
        default_album = SpotifyAlbum(
            id="", 
            name="Unknown Album", 
            artists=[default_artist], 
            images=[], 
            external_urls={}, 
            release_date="", 
            release_date_precision="day", 
            total_tracks=0, 
            album_type="album"
        )
        
        return SpotifyTrack(
            id="unknown",
            name="Unknown Title",
            artists=[default_artist],
            album=default_album,
            duration_ms=0,
            popularity=0,
            explicit=False,
            preview_url=None,
            external_urls={},
            external_ids={},
            available_markets=[],
            disc_number=1,
            track_number=0,
            is_local=False,
            audio_features=None,
            played_at=""
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


@router.get("/auth/callback")
async def auth_callback(
    code: Optional[str] = Query(None, description="Authorization code from Spotify"),
    error: Optional[str] = Query(None, description="Error from Spotify OAuth"),
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Handle Spotify OAuth callback and redirect back to frontend."""
    try:
        logger.info("Handling Spotify OAuth callback")
        
        # Check for OAuth error
        if error:
            logger.error(f"Spotify OAuth error: {error}")
            # Redirect to frontend with error
            return RedirectResponse(
                url=f"https://127.0.0.1:5173/spotify/callback?error={urllib.parse.quote(error)}",
                status_code=302
            )
        
        # Check for authorization code
        if not code:
            error_msg = "Missing authorization code"
            logger.error(error_msg)
            return RedirectResponse(
                url=f"https://127.0.0.1:5173/spotify/callback?error={urllib.parse.quote(error_msg)}",
                status_code=302
            )
        
        # Exchange code for token using real Spotify API
        token_data = await exchange_code_for_token(code, startup_service.config.spotify)
        
        # Store tokens in database using SpotifyTokenService
        token_service = SpotifyTokenService(startup_service.database, startup_service.config.spotify)
        success = await token_service.store_tokens(token_data)
        
        if not success:
            error_msg = "Failed to store authentication tokens"
            logger.error(error_msg)
            return RedirectResponse(
                url=f"https://127.0.0.1:5173/spotify/callback?error={urllib.parse.quote(error_msg)}",
                status_code=302
            )
        
        logger.info("Successfully exchanged code for token and stored in database")
        
        # Now that user is authenticated, enable automatic sync
        if startup_service.sync_manager:
            try:
                # Find the registered Spotify source and enable auto-sync
                for source_namespace, source in startup_service.ingestion_service._sources.items():
                    if source_namespace == "spotify" and hasattr(source, 'token_service'):
                        enabled = await startup_service.sync_manager.enable_auto_sync_for_authenticated_source(source)
                        if enabled:
                            logger.info("Automatic Spotify sync enabled after successful authentication")
                        else:
                            logger.warning("Failed to enable automatic Spotify sync after authentication")
                        break
            except Exception as sync_error:
                logger.warning(f"Failed to enable automatic sync after authentication: {sync_error}")
                # Don't fail the OAuth flow if sync enablement fails
        
        # Redirect to frontend with success
        return RedirectResponse(
            url="https://127.0.0.1:5173/spotify/callback?success=true",
            status_code=302
        )
        
    except HTTPException as he:
        # Redirect to frontend with error
        error_msg = str(he.detail) if hasattr(he, 'detail') else str(he)
        return RedirectResponse(
            url=f"https://127.0.0.1:5173/spotify/callback?error={urllib.parse.quote(error_msg)}",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Error handling Spotify OAuth callback: {e}")
        return RedirectResponse(
            url=f"https://127.0.0.1:5173/spotify/callback?error={urllib.parse.quote(str(e))}",
            status_code=302
        )


async def exchange_code_for_token(code: str, config) -> Dict[str, Any]:
    """Exchange authorization code for access token."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": config.redirect_uri,
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        
        if response.status_code != 200:
            error_data = response.json()
            error_code = error_data.get("error", "unknown_error")
            error_description = error_data.get("error_description", "Token exchange failed")
            error_msg = f"{error_code}: {error_description}"
            logger.error(f"Spotify token exchange failed: {response.status_code} - {error_msg}")
            raise HTTPException(status_code=400, detail=f"OAuth error: {error_msg}")
        
        token_data = response.json()
        logger.info("Successfully exchanged authorization code for tokens")
        return token_data
        
    except HTTPException:
        # Re-raise HTTPException as-is (don't wrap it)
        raise
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during token exchange: {e}")
        raise HTTPException(status_code=500, detail="Failed to exchange authorization code")
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {e}")
        raise HTTPException(status_code=500, detail="Token exchange failed")


@router.get("/auth/status", response_model=AuthStatusResponse)
async def get_auth_status(
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Get current Spotify authentication status."""
    try:
        logger.info("Getting Spotify authentication status")
        
        # Create token service
        token_service = SpotifyTokenService(startup_service.database, startup_service.config.spotify)
        
        # Check authentication status
        is_authenticated = await token_service.is_authenticated()
        
        # Get token info
        token_info_data = await token_service.get_token_info()
        
        token_info = TokenInfo(
            has_token=token_info_data["has_token"],
            is_expired=token_info_data["is_expired"],
            scope=token_info_data["scope"],
            expires_at=token_info_data["expires_at"],
            created_at=token_info_data["created_at"]
        )
        
        logger.info(f"Spotify authentication status: authenticated={is_authenticated}")
        return AuthStatusResponse(
            authenticated=is_authenticated,
            token_info=token_info
        )
        
    except Exception as e:
        logger.error(f"Error getting Spotify auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/track/{track_id}", response_model=SpotifyTrack)
async def get_track_by_id(
    track_id: str,
    market: Optional[str] = Query(None, description="ISO 3166-1 alpha-2 country code for market-specific data"),
    include_audio_features: bool = Query(True, description="Include audio features in response"),
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """
    Get comprehensive Spotify track metadata by track ID.

    Args:
        track_id: Spotify track ID
        market: Optional ISO 3166-1 alpha-2 country code for market-specific data
        include_audio_features: Whether to include audio features (default: True)

    Returns:
        SpotifyTrack: Comprehensive track metadata
    """
    try:
        logger.info(f"Fetching Spotify track: {track_id}, market: {market}")

        # Validate track ID format (basic validation)
        if not track_id or len(track_id) != 22:
            raise HTTPException(status_code=400, detail="Invalid track ID format")

        # Get Spotify source instance
        spotify_source = _get_spotify_source(startup_service)

        # Fetch track data
        track_data = await _fetch_track_data(spotify_source, track_id, market)

        # Fetch audio features if requested
        audio_features = None
        if include_audio_features:
            audio_features = await _fetch_audio_features(spotify_source, track_id)

        # Transform to comprehensive model
        spotify_track = _transform_to_comprehensive_track(track_data, audio_features)

        logger.info(f"Successfully retrieved track: {track_id}")
        return spotify_track

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch track: {str(e)}")


async def _fetch_track_data(spotify_source, track_id: str, market: Optional[str] = None) -> Dict[str, Any]:
    """Fetch track data from Spotify API."""
    try:
        # Get access token
        await spotify_source._get_access_token()

        # Create client
        client = await spotify_source._ensure_client()

        # Build request parameters
        params = {}
        if market:
            params["market"] = market

        # Make request to tracks endpoint
        response = await spotify_source._make_request_with_retry(
            client, f"/tracks/{track_id}", params
        )

        if not response:
            raise Exception(f"Failed to fetch track {track_id}")

        return response.json()

    except Exception as e:
        logger.error(f"Error fetching track data for {track_id}: {e}")
        raise


async def _fetch_audio_features(spotify_source, track_id: str) -> Optional[Dict[str, Any]]:
    """Fetch audio features for a track."""
    try:
        # Get access token
        await spotify_source._get_access_token()

        # Create client
        client = await spotify_source._ensure_client()

        # Make request to audio-features endpoint
        response = await spotify_source._make_request_with_retry(
            client, f"/audio-features/{track_id}", {}
        )

        if response:
            return response.json()
        else:
            logger.warning(f"No audio features available for track {track_id}")
            return None

    except Exception as e:
        logger.warning(f"Error fetching audio features for {track_id}: {e}")
        return None


def _get_spotify_source(startup_service: StartupService):
    """Get configured Spotify source instance."""
    from sources.spotify import SpotifySource
    from config.models import SpotifyConfig

    # Get Spotify config
    config = startup_service.config.spotify

    if not config.is_api_configured():
        raise HTTPException(status_code=500, detail="Spotify API not configured")

    # Create source instance
    spotify_config = SpotifyConfig(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri=config.redirect_uri,
        enabled=True,
        sync_interval_hours=1,
        recently_played_limit=50
    )

    return SpotifySource(spotify_config, startup_service.database)


def _transform_to_comprehensive_track(track_data: Dict[str, Any], audio_features: Optional[Dict[str, Any]] = None) -> SpotifyTrack:
    """Transform Spotify API response to comprehensive SpotifyTrack model."""
    try:
        # Transform album data
        album_data = track_data.get("album", {})
        album = SpotifyAlbum(
            id=album_data.get("id", ""),
            name=album_data.get("name", ""),
            artists=[
                SpotifyArtist(
                    id=artist.get("id", ""),
                    name=artist.get("name", ""),
                    external_urls=artist.get("external_urls", {}),
                    genres=None,  # Would need separate API call
                    popularity=None,  # Would need separate API call
                    followers=None  # Would need separate API call
                ) for artist in album_data.get("artists", [])
            ],
            images=[
                SpotifyImage(
                    url=img.get("url", ""),
                    height=img.get("height"),
                    width=img.get("width")
                ) for img in album_data.get("images", [])
            ],
            external_urls=album_data.get("external_urls", {}),
            release_date=album_data.get("release_date", ""),
            release_date_precision=album_data.get("release_date_precision", ""),
            total_tracks=album_data.get("total_tracks", 0),
            album_type=album_data.get("album_type", ""),
            genres=None,  # Would need separate API call
            popularity=None  # Would need separate API call
        )

        # Transform artists data
        artists = [
            SpotifyArtist(
                id=artist.get("id", ""),
                name=artist.get("name", ""),
                external_urls=artist.get("external_urls", {}),
                genres=None,  # Would need separate API call
                popularity=None,  # Would need separate API call
                followers=None  # Would need separate API call
            ) for artist in track_data.get("artists", [])
        ]

        # Transform audio features if available
        audio_features_model = None
        if audio_features:
            audio_features_model = SpotifyAudioFeatures(
                danceability=audio_features.get("danceability", 0.0),
                energy=audio_features.get("energy", 0.0),
                key=audio_features.get("key", 0),
                loudness=audio_features.get("loudness", 0.0),
                mode=audio_features.get("mode", 0),
                speechiness=audio_features.get("speechiness", 0.0),
                acousticness=audio_features.get("acousticness", 0.0),
                instrumentalness=audio_features.get("instrumentalness", 0.0),
                liveness=audio_features.get("liveness", 0.0),
                valence=audio_features.get("valence", 0.0),
                tempo=audio_features.get("tempo", 0.0),
                duration_ms=audio_features.get("duration_ms", 0),
                time_signature=audio_features.get("time_signature", 4)
            )

        # Create comprehensive track model
        return SpotifyTrack(
            id=track_data.get("id", ""),
            name=track_data.get("name", ""),
            artists=artists,
            album=album,
            duration_ms=track_data.get("duration_ms", 0),
            popularity=track_data.get("popularity", 0),
            explicit=track_data.get("explicit", False),
            preview_url=track_data.get("preview_url"),
            external_urls=track_data.get("external_urls", {}),
            external_ids=track_data.get("external_ids", {}),
            available_markets=track_data.get("available_markets", []),
            disc_number=track_data.get("disc_number", 1),
            track_number=track_data.get("track_number", 0),
            is_local=track_data.get("is_local", False),
            audio_features=audio_features_model,
            played_at=None  # Not applicable for individual track lookup
        )

    except Exception as e:
        logger.error(f"Error transforming track data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to transform track data: {str(e)}")