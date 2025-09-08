import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
import httpx
from sources.spotify import SpotifySource
from config.models import SpotifyConfig
from models.data_item import DataItem


class TestSpotifySourceInit:
    """Test SpotifySource initialization with various configurations."""
    
    def test_init_with_valid_config(self):
        """Test initialization with valid SpotifyConfig."""
        config = SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True,
            sync_interval_hours=1,
            recently_played_limit=50
        )
        
        source = SpotifySource(config)
        
        assert source.config == config
        assert source.name == "spotify"
        assert source.namespace == "spotify"
        assert source.base_url == "https://api.spotify.com/v1"
        assert source.access_token is None
        assert source.token_expires_at is None
    
    def test_init_with_invalid_config_missing_client_id(self):
        """Test initialization fails with missing client_id."""
        config = SpotifyConfig(
            client_id="",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True
        )
        
        with pytest.raises(ValueError, match="client_id is required"):
            SpotifySource(config)
    
    def test_init_with_invalid_config_missing_client_secret(self):
        """Test initialization fails with missing client_secret."""
        config = SpotifyConfig(
            client_id="test_client_id",
            client_secret="",
            redirect_uri="http://localhost:8888/callback",
            enabled=True
        )
        
        with pytest.raises(ValueError, match="client_secret is required"):
            SpotifySource(config)
    
    def test_init_with_disabled_config(self):
        """Test initialization with disabled config."""
        config = SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=False
        )
        
        with pytest.raises(ValueError, match="Spotify source is disabled"):
            SpotifySource(config)


class TestSpotifySourceConnection:
    """Test SpotifySource connection and authentication."""
    
    @pytest.fixture
    def valid_config(self):
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True,
            sync_interval_hours=1
        )
    
    @pytest.fixture
    def spotify_source(self, valid_config):
        return SpotifySource(valid_config)
    
    @pytest.mark.asyncio
    async def test_test_connection_success_with_valid_token(self, spotify_source, httpx_mock):
        """Test successful connection with valid access token."""
        # Mock token acquisition
        token_response = {
            "access_token": "valid_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        httpx_mock.add_response(
            method="POST",
            url="https://accounts.spotify.com/api/token",
            json=token_response,
            status_code=200
        )
        
        # Mock /me endpoint
        me_response = {
            "id": "test_user",
            "display_name": "Test User",
            "email": "test@example.com"
        }
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me",
            json=me_response,
            status_code=200
        )
        
        result = await spotify_source.test_connection()
        
        assert result is True
        assert spotify_source.access_token == "valid_access_token"
        assert spotify_source.token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_test_connection_failure_invalid_credentials(self, spotify_source, httpx_mock):
        """Test connection failure with invalid credentials."""
        error_response = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }
        httpx_mock.add_response(
            method="POST",
            url="https://accounts.spotify.com/api/token",
            json=error_response,
            status_code=400
        )
        
        result = await spotify_source.test_connection()
        
        assert result is False
        assert spotify_source.access_token is None
    
    @pytest.mark.asyncio
    async def test_test_connection_network_error(self, spotify_source, httpx_mock):
        """Test connection failure due to network error."""
        httpx_mock.add_exception(
            httpx.ConnectError("Network unreachable")
        )
        
        result = await spotify_source.test_connection()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_test_connection_me_endpoint_failure(self, spotify_source, httpx_mock):
        """Test connection failure when /me endpoint fails."""
        # Mock successful token acquisition
        token_response = {
            "access_token": "valid_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        httpx_mock.add_response(
            method="POST",
            url="https://accounts.spotify.com/api/token",
            json=token_response,
            status_code=200
        )
        
        # Mock /me endpoint failure
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me",
            json={"error": {"status": 401, "message": "Invalid access token"}},
            status_code=401
        )
        
        result = await spotify_source.test_connection()
        
        assert result is False


class TestSpotifySourceTokenManagement:
    """Test OAuth token management and refresh logic."""
    
    @pytest.fixture
    def valid_config(self):
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True
        )
    
    @pytest.fixture
    def spotify_source(self, valid_config):
        return SpotifySource(valid_config)
    
    @pytest.mark.asyncio
    async def test_get_access_token_first_time(self, spotify_source, httpx_mock):
        """Test getting access token for the first time."""
        token_response = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        httpx_mock.add_response(
            method="POST",
            url="https://accounts.spotify.com/api/token",
            json=token_response,
            status_code=200
        )
        
        token = await spotify_source._get_access_token()
        
        assert token == "new_access_token"
        assert spotify_source.access_token == "new_access_token"
        assert spotify_source.token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_get_access_token_reuse_valid_token(self, spotify_source):
        """Test reusing valid access token."""
        # Set up existing valid token
        spotify_source.access_token = "existing_token"
        spotify_source.token_expires_at = datetime.now(timezone.utc).timestamp() + 1800  # 30 minutes from now
        
        token = await spotify_source._get_access_token()
        
        assert token == "existing_token"
    
    @pytest.mark.asyncio
    async def test_get_access_token_refresh_expired_token(self, spotify_source, httpx_mock):
        """Test refreshing expired access token."""
        # Set up expired token
        spotify_source.access_token = "expired_token"
        spotify_source.token_expires_at = datetime.now(timezone.utc).timestamp() - 100  # Expired
        
        token_response = {
            "access_token": "refreshed_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        httpx_mock.add_response(
            method="POST",
            url="https://accounts.spotify.com/api/token",
            json=token_response,
            status_code=200
        )
        
        token = await spotify_source._get_access_token()
        
        assert token == "refreshed_access_token"
        assert spotify_source.access_token == "refreshed_access_token"
    
    @pytest.mark.asyncio
    async def test_get_access_token_failure(self, spotify_source, httpx_mock):
        """Test access token acquisition failure."""
        error_response = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }
        httpx_mock.add_response(
            method="POST",
            url="https://accounts.spotify.com/api/token",
            json=error_response,
            status_code=400
        )
        
        with pytest.raises(Exception, match="Failed to get access token"):
            await spotify_source._get_access_token()


class TestSpotifySourceFetchItems:
    """Test fetching items from Spotify API."""
    
    @pytest.fixture
    def valid_config(self):
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True,
            recently_played_limit=20
        )
    
    @pytest.fixture
    def spotify_source(self, valid_config):
        source = SpotifySource(valid_config)
        source.access_token = "valid_token"
        source.token_expires_at = datetime.now(timezone.utc).timestamp() + 3600
        return source
    
    @pytest.mark.asyncio
    async def test_fetch_items_success(self, spotify_source, httpx_mock):
        """Test successful fetching of recently played tracks."""
        recently_played_response = {
            "items": [
                {
                    "track": {
                        "id": "track_1",
                        "name": "Test Song 1",
                        "artists": [{"name": "Test Artist 1"}],
                        "album": {
                            "name": "Test Album 1",
                            "images": [{"url": "https://example.com/album1.jpg"}]
                        },
                        "duration_ms": 180000,
                        "preview_url": "https://example.com/preview1.mp3",
                        "external_urls": {"spotify": "https://open.spotify.com/track/track_1"}
                    },
                    "played_at": "2023-12-07T10:30:00Z"
                },
                {
                    "track": {
                        "id": "track_2",
                        "name": "Test Song 2",
                        "artists": [{"name": "Test Artist 2"}],
                        "album": {
                            "name": "Test Album 2",
                            "images": [{"url": "https://example.com/album2.jpg"}]
                        },
                        "duration_ms": 210000,
                        "preview_url": None,
                        "external_urls": {"spotify": "https://open.spotify.com/track/track_2"}
                    },
                    "played_at": "2023-12-07T10:33:00Z"
                }
            ]
        }
        
        # Mock recently played endpoint
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me/player/recently-played?limit=20",
            json=recently_played_response,
            status_code=200
        )
        
        # Mock audio features endpoint
        audio_features_response = {
            "audio_features": [
                {
                    "id": "track_1",
                    "danceability": 0.8,
                    "energy": 0.7,
                    "valence": 0.9,
                    "tempo": 120.0
                },
                {
                    "id": "track_2",
                    "danceability": 0.6,
                    "energy": 0.5,
                    "valence": 0.4,
                    "tempo": 95.0
                }
            ]
        }
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/audio-features?ids=track_1,track_2",
            json=audio_features_response,
            status_code=200
        )
        
        items = await spotify_source.fetch_items()
        
        assert len(items) == 2
        
        # Verify first item
        item1 = items[0]
        assert isinstance(item1, DataItem)
        assert item1.namespace == "spotify"
        assert item1.source_id == "track_1_2023-12-07T10:30:00Z"
        assert item1.data["track"]["name"] == "Test Song 1"
        assert item1.data["track"]["artists"][0]["name"] == "Test Artist 1"
        assert item1.data["played_at"] == "2023-12-07T10:30:00Z"
        assert item1.data["audio_features"]["danceability"] == 0.8
        
        # Verify second item
        item2 = items[1]
        assert item2.namespace == "spotify"
        assert item2.source_id == "track_2_2023-12-07T10:33:00Z"
        assert item2.data["track"]["preview_url"] is None
        assert item2.data["audio_features"]["tempo"] == 95.0
    
    @pytest.mark.asyncio
    async def test_fetch_items_empty_response(self, spotify_source, httpx_mock):
        """Test fetching items with empty response."""
        empty_response = {"items": []}
        
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me/player/recently-played?limit=20",
            json=empty_response,
            status_code=200
        )
        
        items = await spotify_source.fetch_items()
        
        assert items == []
    
    @pytest.mark.asyncio
    async def test_fetch_items_api_error(self, spotify_source, httpx_mock):
        """Test fetching items with API error."""
        error_response = {
            "error": {
                "status": 401,
                "message": "Invalid access token"
            }
        }
        
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me/player/recently-played?limit=20",
            json=error_response,
            status_code=401
        )
        
        with pytest.raises(Exception, match="Failed to fetch recently played tracks"):
            await spotify_source.fetch_items()
    
    @pytest.mark.asyncio
    async def test_fetch_items_rate_limit(self, spotify_source, httpx_mock):
        """Test fetching items with rate limit error."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me/player/recently-played?limit=20",
            status_code=429,
            headers={"Retry-After": "60"}
        )
        
        with pytest.raises(Exception, match="Rate limited"):
            await spotify_source.fetch_items()
    
    @pytest.mark.asyncio
    async def test_fetch_items_network_error(self, spotify_source, httpx_mock):
        """Test fetching items with network error."""
        httpx_mock.add_exception(
            httpx.ConnectError("Network unreachable")
        )
        
        with pytest.raises(Exception, match="Network error"):
            await spotify_source.fetch_items()
    
    @pytest.mark.asyncio
    async def test_fetch_items_audio_features_failure(self, spotify_source, httpx_mock):
        """Test fetching items when audio features API fails."""
        recently_played_response = {
            "items": [
                {
                    "track": {
                        "id": "track_1",
                        "name": "Test Song 1",
                        "artists": [{"name": "Test Artist 1"}],
                        "album": {
                            "name": "Test Album 1",
                            "images": [{"url": "https://example.com/album1.jpg"}]
                        },
                        "duration_ms": 180000,
                        "preview_url": "https://example.com/preview1.mp3",
                        "external_urls": {"spotify": "https://open.spotify.com/track/track_1"}
                    },
                    "played_at": "2023-12-07T10:30:00Z"
                }
            ]
        }
        
        # Mock recently played endpoint
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/me/player/recently-played?limit=20",
            json=recently_played_response,
            status_code=200
        )
        
        # Mock audio features endpoint failure
        httpx_mock.add_response(
            method="GET",
            url="https://api.spotify.com/v1/audio-features?ids=track_1",
            status_code=500
        )
        
        items = await spotify_source.fetch_items()
        
        assert len(items) == 1
        # Should still return item but without audio features
        assert "audio_features" not in items[0].data or items[0].data["audio_features"] is None


class TestSpotifySourceGetItem:
    """Test get_item method behavior."""
    
    @pytest.fixture
    def valid_config(self):
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True
        )
    
    @pytest.fixture
    def spotify_source(self, valid_config):
        return SpotifySource(valid_config)
    
    @pytest.mark.asyncio
    async def test_get_item_not_supported(self, spotify_source):
        """Test that get_item returns None as it's not supported by Spotify API."""
        result = await spotify_source.get_item("any_id")
        assert result is None


class TestSpotifySourceTransformTrack:
    """Test track data transformation."""
    
    @pytest.fixture
    def valid_config(self):
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True
        )
    
    @pytest.fixture
    def spotify_source(self, valid_config):
        return SpotifySource(valid_config)
    
    def test_transform_track_complete_data(self, spotify_source):
        """Test transforming track with complete data."""
        track_item = {
            "track": {
                "id": "track_123",
                "name": "Amazing Song",
                "artists": [
                    {"name": "Primary Artist"},
                    {"name": "Featured Artist"}
                ],
                "album": {
                    "name": "Great Album",
                    "images": [
                        {"url": "https://example.com/large.jpg", "height": 640},
                        {"url": "https://example.com/medium.jpg", "height": 300},
                        {"url": "https://example.com/small.jpg", "height": 64}
                    ]
                },
                "duration_ms": 240000,
                "preview_url": "https://example.com/preview.mp3",
                "external_urls": {"spotify": "https://open.spotify.com/track/track_123"},
                "popularity": 85
            },
            "played_at": "2023-12-07T15:45:30Z"
        }
        
        audio_features = {
            "danceability": 0.75,
            "energy": 0.82,
            "valence": 0.68,
            "tempo": 128.5,
            "acousticness": 0.12,
            "instrumentalness": 0.001,
            "liveness": 0.15,
            "speechiness": 0.04
        }
        
        data_item = spotify_source._transform_track(track_item, audio_features)
        
        assert isinstance(data_item, DataItem)
        assert data_item.namespace == "spotify"
        assert data_item.source_id == "track_123_2023-12-07T15:45:30Z"
        
        # Verify track data
        track_data = data_item.data["track"]
        assert track_data["id"] == "track_123"
        assert track_data["name"] == "Amazing Song"
        assert len(track_data["artists"]) == 2
        assert track_data["artists"][0]["name"] == "Primary Artist"
        assert track_data["album"]["name"] == "Great Album"
        assert track_data["duration_ms"] == 240000
        assert track_data["preview_url"] == "https://example.com/preview.mp3"
        
        # Verify played_at
        assert data_item.data["played_at"] == "2023-12-07T15:45:30Z"
        
        # Verify audio features
        features = data_item.data["audio_features"]
        assert features["danceability"] == 0.75
        assert features["energy"] == 0.82
        assert features["tempo"] == 128.5
    
    def test_transform_track_missing_preview_url(self, spotify_source):
        """Test transforming track with missing preview URL."""
        track_item = {
            "track": {
                "id": "track_456",
                "name": "No Preview Song",
                "artists": [{"name": "Artist Name"}],
                "album": {
                    "name": "Album Name",
                    "images": []
                },
                "duration_ms": 180000,
                "preview_url": None,
                "external_urls": {"spotify": "https://open.spotify.com/track/track_456"}
            },
            "played_at": "2023-12-07T16:00:00Z"
        }
        
        data_item = spotify_source._transform_track(track_item, None)
        
        assert data_item.data["track"]["preview_url"] is None
        assert data_item.data["audio_features"] is None
    
    def test_transform_track_missing_album_images(self, spotify_source):
        """Test transforming track with missing album images."""
        track_item = {
            "track": {
                "id": "track_789",
                "name": "No Image Song",
                "artists": [{"name": "Artist Name"}],
                "album": {
                    "name": "Album Name",
                    "images": []
                },
                "duration_ms": 200000,
                "preview_url": "https://example.com/preview.mp3",
                "external_urls": {"spotify": "https://open.spotify.com/track/track_789"}
            },
            "played_at": "2023-12-07T16:15:00Z"
        }
        
        data_item = spotify_source._transform_track(track_item, None)
        
        assert data_item.data["track"]["album"]["images"] == []
    
    def test_transform_track_source_id_format(self, spotify_source):
        """Test that source_id follows the correct format."""
        track_item = {
            "track": {
                "id": "special_track_id_123",
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {"name": "Test Album", "images": []},
                "duration_ms": 150000,
                "preview_url": None,
                "external_urls": {"spotify": "https://open.spotify.com/track/special_track_id_123"}
            },
            "played_at": "2023-12-07T20:30:45Z"
        }
        
        data_item = spotify_source._transform_track(track_item, None)
        
        expected_source_id = "special_track_id_123_2023-12-07T20:30:45Z"
        assert data_item.source_id == expected_source_id


class TestSpotifySourceDataItemValidation:
    """Test DataItem format validation."""
    
    @pytest.fixture
    def valid_config(self):
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True
        )
    
    @pytest.fixture
    def spotify_source(self, valid_config):
        return SpotifySource(valid_config)
    
    def test_data_item_namespace_validation(self, spotify_source):
        """Test that all DataItems have correct namespace."""
        track_item = {
            "track": {
                "id": "test_track",
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {"name": "Test Album", "images": []},
                "duration_ms": 180000,
                "preview_url": None,
                "external_urls": {"spotify": "https://open.spotify.com/track/test_track"}
            },
            "played_at": "2023-12-07T12:00:00Z"
        }
        
        data_item = spotify_source._transform_track(track_item, None)
        
        assert data_item.namespace == "spotify"
    
    def test_data_item_source_id_uniqueness(self, spotify_source):
        """Test that source_id is unique for different tracks and play times."""
        track_item_1 = {
            "track": {
                "id": "track_1",
                "name": "Song 1",
                "artists": [{"name": "Artist 1"}],
                "album": {"name": "Album 1", "images": []},
                "duration_ms": 180000,
                "preview_url": None,
                "external_urls": {"spotify": "https://open.spotify.com/track/track_1"}
            },
            "played_at": "2023-12-07T12:00:00Z"
        }
        
        track_item_2 = {
            "track": {
                "id": "track_1",  # Same track
                "name": "Song 1",
                "artists": [{"name": "Artist 1"}],
                "album": {"name": "Album 1", "images": []},
                "duration_ms": 180000,
                "preview_url": None,
                "external_urls": {"spotify": "https://open.spotify.com/track/track_1"}
            },
            "played_at": "2023-12-07T12:05:00Z"  # Different play time
        }
        
        data_item_1 = spotify_source._transform_track(track_item_1, None)
        data_item_2 = spotify_source._transform_track(track_item_2, None)
        
        assert data_item_1.source_id != data_item_2.source_id
        assert data_item_1.source_id == "track_1_2023-12-07T12:00:00Z"
        assert data_item_2.source_id == "track_1_2023-12-07T12:05:00Z"
    
    def test_data_item_required_fields(self, spotify_source):
        """Test that DataItem contains all required fields."""
        track_item = {
            "track": {
                "id": "required_fields_test",
                "name": "Required Fields Song",
                "artists": [{"name": "Required Artist"}],
                "album": {"name": "Required Album", "images": []},
                "duration_ms": 200000,
                "preview_url": "https://example.com/preview.mp3",
                "external_urls": {"spotify": "https://open.spotify.com/track/required_fields_test"}
            },
            "played_at": "2023-12-07T14:30:00Z"
        }
        
        audio_features = {
            "danceability": 0.5,
            "energy": 0.6,
            "valence": 0.7,
            "tempo": 100.0
        }
        
        data_item = spotify_source._transform_track(track_item, audio_features)
        
        # Check DataItem structure
        assert hasattr(data_item, 'namespace')
        assert hasattr(data_item, 'source_id')
        assert hasattr(data_item, 'data')
        
        # Check required data fields
        assert 'track' in data_item.data
        assert 'played_at' in data_item.data
        assert 'audio_features' in data_item.data
        
        # Check track fields
        track = data_item.data['track']
        required_track_fields = ['id', 'name', 'artists', 'album', 'duration_ms', 'external_urls']
        for field in required_track_fields:
            assert field in track, f"Missing required track field: {field}"