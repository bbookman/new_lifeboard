"""
Tests for Spotify API routes.
Following TDD principles - these tests should fail initially until routes are implemented.
"""
import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

# Mock the app and dependencies for testing
@pytest.fixture
def mock_startup_service():
    """Mock startup service with database connection."""
    mock_service = Mock()
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Setup database connection mock
    mock_service.database.get_connection.return_value.__enter__.return_value = mock_conn
    mock_service.database.get_connection.return_value.__exit__.return_value = None
    mock_conn.execute.return_value = mock_cursor
    
    return mock_service, mock_conn, mock_cursor


@pytest.fixture
def test_app():
    """Create test FastAPI app with Spotify routes."""
    app = FastAPI()
    
    # This will fail initially since spotify routes don't exist yet
    try:
        from api.routes.spotify import router
        app.include_router(router)
    except ImportError:
        # Expected to fail in RED phase
        pass
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def sample_spotify_data():
    """Sample Spotify data items for testing."""
    return [
        {
            "id": 1,
            "namespace": "spotify",
            "source_id": "track_123_2024-01-15T10:30:00Z",
            "content": json.dumps({
                "id": "track_123",
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {"name": "Test Album"},
                "duration_ms": 180000,
                "preview_url": "https://preview.spotify.com/track_123",
                "external_urls": {"spotify": "https://open.spotify.com/track/track_123"},
                "played_at": "2024-01-15T10:30:00Z"
            }),
            "metadata": json.dumps({
                "audio_features": {
                    "danceability": 0.8,
                    "energy": 0.7,
                    "valence": 0.6
                }
            }),
            "embedding_status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "days_date": "2024-01-15"
        },
        {
            "id": 2,
            "namespace": "spotify",
            "source_id": "track_456_2024-01-15T11:00:00Z",
            "content": json.dumps({
                "id": "track_456",
                "name": "Another Song",
                "artists": [{"name": "Another Artist"}],
                "album": {"name": "Another Album"},
                "duration_ms": 210000,
                "preview_url": None,
                "external_urls": {"spotify": "https://open.spotify.com/track/track_456"},
                "played_at": "2024-01-15T11:00:00Z"
            }),
            "metadata": json.dumps({
                "audio_features": {
                    "danceability": 0.5,
                    "energy": 0.9,
                    "valence": 0.3
                }
            }),
            "embedding_status": "completed",
            "created_at": "2024-01-15T11:00:00Z",
            "updated_at": "2024-01-15T11:00:00Z",
            "days_date": "2024-01-15"
        }
    ]


class TestSpotifyRecentEndpoint:
    """Test GET /spotify/recent endpoint."""
    
    def test_get_recent_tracks_success(self, client, mock_startup_service, sample_spotify_data):
        """Test successful retrieval of recent tracks."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        
        # Mock database response
        mock_cursor.fetchall.return_value = [
            {k: v for k, v in track.items()} for track in sample_spotify_data
        ]
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/recent")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "track_123"
        assert data[0]["title"] == "Test Song"
        assert data[0]["artist"] == "Test Artist"
        assert data[0]["album"] == "Test Album"
        assert data[0]["duration_ms"] == 180000
        assert data[0]["played_at"] == "2024-01-15T10:30:00Z"
        assert data[0]["preview_url"] == "https://preview.spotify.com/track_123"
        assert "audio_features" in data[0]
    
    def test_get_recent_tracks_with_date_filter(self, client, mock_startup_service, sample_spotify_data):
        """Test recent tracks with date parameter."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = [sample_spotify_data[0]]
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/recent?date=2024-01-15")
        
        assert response.status_code == 200
        
        # Verify database query was called with correct parameters
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "namespace = ?" in query
        assert "days_date = ?" in query
        assert "spotify" in params
        assert "2024-01-15" in params
    
    def test_get_recent_tracks_invalid_date(self, client, mock_startup_service):
        """Test recent tracks with invalid date format."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/recent?date=invalid-date")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
    
    def test_get_recent_tracks_empty_result(self, client, mock_startup_service):
        """Test recent tracks when no data available."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = []
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/recent")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_recent_tracks_database_error(self, client, mock_startup_service):
        """Test recent tracks with database error."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_conn.execute.side_effect = Exception("Database connection failed")
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/recent")
        
        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]


class TestSpotifyTracksEndpoint:
    """Test GET /spotify/tracks endpoint."""
    
    def test_get_tracks_success(self, client, mock_startup_service, sample_spotify_data):
        """Test successful retrieval of tracks."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Verify SpotifyTrack interface format
        track = data[0]
        required_fields = ["id", "title", "artist", "album", "duration_ms", "played_at", "preview_url", "external_urls", "audio_features"]
        for field in required_fields:
            assert field in track
    
    def test_get_tracks_with_date_filter(self, client, mock_startup_service, sample_spotify_data):
        """Test tracks with date parameter."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks?date=2024-01-15")
        
        assert response.status_code == 200
        
        # Verify namespace filtering
        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "namespace = ?" in query
        assert "spotify" in params
    
    def test_get_tracks_with_limit(self, client, mock_startup_service, sample_spotify_data):
        """Test tracks with limit parameter."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data[:1]
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks?limit=1")
        
        assert response.status_code == 200
        
        # Verify limit in query
        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "LIMIT ?" in query
        assert 1 in params
    
    def test_get_tracks_limit_validation(self, client, mock_startup_service):
        """Test tracks with invalid limit values."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            # Test limit too low
            response = client.get("/spotify/tracks?limit=0")
            assert response.status_code == 422
            
            # Test limit too high
            response = client.get("/spotify/tracks?limit=1001")
            assert response.status_code == 422
    
    def test_get_tracks_namespace_filtering(self, client, mock_startup_service, sample_spotify_data):
        """Test that only spotify namespace data is returned."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        
        # Add non-spotify data to test filtering
        mixed_data = sample_spotify_data + [
            {
                "id": 3,
                "namespace": "news",
                "source_id": "news_123",
                "content": json.dumps({"title": "News Article"}),
                "metadata": "{}",
                "embedding_status": "completed",
                "created_at": "2024-01-15T12:00:00Z",
                "updated_at": "2024-01-15T12:00:00Z",
                "days_date": "2024-01-15"
            }
        ]
        
        mock_cursor.fetchall.return_value = mixed_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        # Verify query filters by spotify namespace
        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "namespace = ?" in query
        assert "spotify" in params


class TestSpotifyAuthEndpoints:
    """Test OAuth authentication endpoints."""
    
    def test_spotify_auth_url(self, client):
        """Test getting Spotify authorization URL."""
        with patch('api.routes.spotify.get_startup_service_dependency'):
            response = client.get("/spotify/auth/url")
        
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "spotify.com/authorize" in data["auth_url"]
        assert "client_id" in data["auth_url"]
        assert "scope" in data["auth_url"]
    
    def test_spotify_auth_callback_success(self, client):
        """Test successful OAuth callback."""
        with patch('api.routes.spotify.get_startup_service_dependency'):
            with patch('api.routes.spotify.exchange_code_for_token') as mock_exchange:
                mock_exchange.return_value = {
                    "access_token": "test_token",
                    "refresh_token": "test_refresh",
                    "expires_in": 3600
                }
                
                response = client.get("/spotify/auth/callback?code=test_code")
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == "test_token"
    
    def test_spotify_auth_callback_error(self, client):
        """Test OAuth callback with error."""
        with patch('api.routes.spotify.get_startup_service_dependency'):
            response = client.get("/spotify/auth/callback?error=access_denied")
        
        assert response.status_code == 400
        assert "access_denied" in response.json()["detail"]
    
    def test_spotify_auth_callback_missing_code(self, client):
        """Test OAuth callback without code parameter."""
        with patch('api.routes.spotify.get_startup_service_dependency'):
            response = client.get("/spotify/auth/callback")
        
        assert response.status_code == 400
        assert "Missing authorization code" in response.json()["detail"]


class TestSpotifyResponseFormat:
    """Test response format matches SpotifyTrack interface."""
    
    def test_spotify_track_interface_compliance(self, client, mock_startup_service, sample_spotify_data):
        """Test that response matches expected SpotifyTrack interface."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        assert response.status_code == 200
        tracks = response.json()
        
        for track in tracks:
            # Required fields for SpotifyTrack interface
            assert isinstance(track["id"], str)
            assert isinstance(track["title"], str)
            assert isinstance(track["artist"], str)
            assert isinstance(track["album"], str)
            assert isinstance(track["duration_ms"], int)
            assert isinstance(track["played_at"], str)
            assert track["preview_url"] is None or isinstance(track["preview_url"], str)
            assert isinstance(track["external_urls"], dict)
            assert "spotify" in track["external_urls"]
            assert isinstance(track["audio_features"], dict)
    
    def test_audio_features_format(self, client, mock_startup_service, sample_spotify_data):
        """Test audio features are properly formatted."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        tracks = response.json()
        audio_features = tracks[0]["audio_features"]
        
        # Verify audio features structure
        expected_features = ["danceability", "energy", "valence"]
        for feature in expected_features:
            assert feature in audio_features
            assert isinstance(audio_features[feature], (int, float))
            assert 0 <= audio_features[feature] <= 1


class TestSpotifyPagination:
    """Test pagination parameters."""
    
    def test_default_pagination(self, client, mock_startup_service, sample_spotify_data):
        """Test default pagination behavior."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        # Verify default limit is applied
        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "LIMIT ?" in query
        # Default limit should be 50 or similar reasonable default
        assert any(isinstance(p, int) and p > 0 for p in params)
    
    def test_custom_pagination(self, client, mock_startup_service, sample_spotify_data):
        """Test custom pagination parameters."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        mock_cursor.fetchall.return_value = sample_spotify_data[:10]
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks?limit=10")
        
        assert response.status_code == 200
        
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        assert 10 in params


class TestSpotifyErrorHandling:
    """Test error handling scenarios."""
    
    def test_malformed_content_handling(self, client, mock_startup_service):
        """Test handling of malformed JSON content."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        
        # Mock data with malformed JSON
        malformed_data = [{
            "id": 1,
            "namespace": "spotify",
            "source_id": "track_123",
            "content": "invalid json",
            "metadata": "{}",
            "embedding_status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "days_date": "2024-01-15"
        }]
        
        mock_cursor.fetchall.return_value = malformed_data
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        # Should handle gracefully, either skip malformed items or return error
        assert response.status_code in [200, 500]
    
    def test_missing_metadata_handling(self, client, mock_startup_service):
        """Test handling of missing metadata."""
        mock_service, mock_conn, mock_cursor = mock_startup_service
        
        # Mock data with missing metadata
        data_no_metadata = [{
            "id": 1,
            "namespace": "spotify",
            "source_id": "track_123",
            "content": json.dumps({
                "id": "track_123",
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {"name": "Test Album"},
                "duration_ms": 180000,
                "played_at": "2024-01-15T10:30:00Z"
            }),
            "metadata": None,
            "embedding_status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "days_date": "2024-01-15"
        }]
        
        mock_cursor.fetchall.return_value = data_no_metadata
        
        with patch('api.routes.spotify.get_startup_service_dependency', return_value=mock_service):
            response = client.get("/spotify/tracks")
        
        assert response.status_code == 200
        tracks = response.json()
        # Should provide default empty audio_features
class TestSpotifyTrackByIdEndpoint:
    """Test GET /spotify/track/{track_id} endpoint."""

    @pytest.fixture
    def sample_spotify_track_data(self):
        """Sample comprehensive Spotify track data."""
        return {
            "id": "4iV5W9uYEdYUVa79Axb7Rh",
            "name": "Bohemian Rhapsody",
            "artists": [
                {
                    "id": "1dfeR4HaWDbWqFHLkxsg1d",
                    "name": "Queen",
                    "external_urls": {"spotify": "https://open.spotify.com/artist/1dfeR4HaWDbWqFHLkxsg1d"},
                    "genres": ["rock", "classic rock"],
                    "popularity": 85,
                    "followers": {"total": 50000000}
                }
            ],
            "album": {
                "id": "6i6folBtxKV28WX3msQ4FE",
                "name": "A Night at the Opera",
                "artists": [
                    {
                        "id": "1dfeR4HaWDbWqFHLkxsg1d",
                        "name": "Queen",
                        "external_urls": {"spotify": "https://open.spotify.com/artist/1dfeR4HaWDbWqFHLkxsg1d"}
                    }
                ],
                "images": [
                    {"url": "https://i.scdn.co/image/large.jpg", "height": 640, "width": 640},
                    {"url": "https://i.scdn.co/image/medium.jpg", "height": 300, "width": 300},
                    {"url": "https://i.scdn.co/image/small.jpg", "height": 64, "width": 64}
                ],
                "external_urls": {"spotify": "https://open.spotify.com/album/6i6folBtxKV28WX3msQ4FE"},
                "release_date": "1975-11-21",
                "release_date_precision": "day",
                "total_tracks": 12,
                "album_type": "album",
                "genres": ["rock", "classic rock"],
                "popularity": 80
            },
            "duration_ms": 355000,
            "popularity": 80,
            "explicit": False,
            "preview_url": "https://p.scdn.co/mp3-preview/preview.mp3",
            "external_urls": {"spotify": "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"},
            "external_ids": {"isrc": "GBCEE7500123"},
            "available_markets": ["US", "GB", "CA", "AU"],
            "disc_number": 1,
            "track_number": 11,
            "is_local": False
        }

    @pytest.fixture
    def sample_audio_features(self):
        """Sample audio features data."""
        return {
            "danceability": 0.414,
            "energy": 0.404,
            "key": 0,
            "loudness": -9.928,
            "mode": 0,
            "speechiness": 0.0499,
            "acousticness": 0.271,
            "instrumentalness": 0.0000000294,
            "liveness": 0.300,
            "valence": 0.224,
            "tempo": 71.105,
            "duration_ms": 354947,
            "time_signature": 4
        }

    def test_get_track_by_id_success(self, client, mock_startup_service, sample_spotify_track_data, sample_audio_features):
        """Test successful retrieval of individual track."""
        mock_service, mock_conn, mock_cursor = mock_startup_service

        # Mock Spotify source
        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock(return_value=Mock())

        with patch('api.routes.spotify._get_spotify_source', return_value=mock_spotify_source), \
             patch('api.routes.spotify._fetch_track_data', return_value=sample_spotify_track_data), \
             patch('api.routes.spotify._fetch_audio_features', return_value=sample_audio_features), \
             patch('api.routes.spotify._transform_to_comprehensive_track') as mock_transform:

            # Mock the transformation
            mock_track = Mock()
            mock_track.id = sample_spotify_track_data["id"]
            mock_track.name = sample_spotify_track_data["name"]
            mock_transform.return_value = mock_track

            response = client.get("/spotify/track/4iV5W9uYEdYUVa79Axb7Rh")

            assert response.status_code == 200
            mock_transform.assert_called_once()

    def test_get_track_by_id_invalid_format(self, client, mock_startup_service):
        """Test track retrieval with invalid track ID format."""
        mock_service, mock_conn, mock_cursor = mock_startup_service

        response = client.get("/spotify/track/invalid")

        assert response.status_code == 400
        assert "Invalid track ID format" in response.json()["detail"]

    def test_get_track_by_id_with_market(self, client, mock_startup_service, sample_spotify_track_data):
        """Test track retrieval with market parameter."""
        mock_service, mock_conn, mock_cursor = mock_startup_service

        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock(return_value=Mock())

        with patch('api.routes.spotify._get_spotify_source', return_value=mock_spotify_source), \
             patch('api.routes.spotify._fetch_track_data') as mock_fetch, \
             patch('api.routes.spotify._fetch_audio_features', return_value=None), \
             patch('api.routes.spotify._transform_to_comprehensive_track') as mock_transform:

            mock_fetch.return_value = sample_spotify_track_data
            mock_transform.return_value = Mock()

            response = client.get("/spotify/track/4iV5W9uYEdYUVa79Axb7Rh?market=US")

            assert response.status_code == 200
            mock_fetch.assert_called_once()
            # Verify market parameter was passed
            call_args = mock_fetch.call_args
            assert call_args[0][1] == "US"  # market parameter

    def test_get_track_by_id_without_audio_features(self, client, mock_startup_service, sample_spotify_track_data):
        """Test track retrieval without audio features."""
        mock_service, mock_conn, mock_cursor = mock_startup_service

        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock(return_value=Mock())

        with patch('api.routes.spotify._get_spotify_source', return_value=mock_spotify_source), \
             patch('api.routes.spotify._fetch_track_data', return_value=sample_spotify_track_data), \
             patch('api.routes.spotify._fetch_audio_features') as mock_audio_fetch, \
             patch('api.routes.spotify._transform_to_comprehensive_track') as mock_transform:

            mock_audio_fetch.return_value = None
            mock_transform.return_value = Mock()

            response = client.get("/spotify/track/4iV5W9uYEdYUVa79Axb7Rh?include_audio_features=false")

            assert response.status_code == 200
            mock_audio_fetch.assert_not_called()

    def test_get_track_by_id_api_error(self, client, mock_startup_service):
        """Test track retrieval with API error."""
        mock_service, mock_conn, mock_cursor = mock_startup_service

        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock(return_value=Mock())

        with patch('api.routes.spotify._get_spotify_source', return_value=mock_spotify_source), \
             patch('api.routes.spotify._fetch_track_data', side_effect=Exception("API Error")):

            response = client.get("/spotify/track/4iV5W9uYEdYUVa79Axb7Rh")

            assert response.status_code == 500
            assert "Failed to fetch track" in response.json()["detail"]

    def test_get_track_by_id_not_configured(self, client, mock_startup_service):
        """Test track retrieval when Spotify is not configured."""
        mock_service, mock_conn, mock_cursor = mock_startup_service

        with patch('api.routes.spotify._get_spotify_source', side_effect=Exception("Spotify API not configured")):
            response = client.get("/spotify/track/4iV5W9uYEdYUVa79Axb7Rh")

            assert response.status_code == 500
            assert "Spotify API not configured" in response.json()["detail"]


class TestSpotifyTrackDataFetching:
    """Test track data fetching functions."""

    def test_fetch_track_data_success(self):
        """Test successful track data fetching."""
        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock()
        mock_client = Mock()
        mock_spotify_source._ensure_client.return_value = mock_client
        mock_spotify_source._make_request_with_retry = AsyncMock()

        sample_data = {"id": "test_track", "name": "Test Track"}
        mock_spotify_source._make_request_with_retry.return_value = Mock(json=Mock(return_value=sample_data))

        import asyncio
        from api.routes.spotify import _fetch_track_data

        async def run_test():
            result = await _fetch_track_data(mock_spotify_source, "test_track_id", "US")
            assert result == sample_data
            mock_spotify_source._make_request_with_retry.assert_called_once()

        asyncio.run(run_test())

    def test_fetch_track_data_failure(self):
        """Test track data fetching failure."""
        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock()
        mock_spotify_source._make_request_with_retry = AsyncMock(return_value=None)

        import asyncio
        from api.routes.spotify import _fetch_track_data

        async def run_test():
            with pytest.raises(Exception, match="Failed to fetch track"):
                await _fetch_track_data(mock_spotify_source, "test_track_id")

        asyncio.run(run_test())

    def test_fetch_audio_features_success(self):
        """Test successful audio features fetching."""
        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock()
        mock_spotify_source._make_request_with_retry = AsyncMock()

        sample_features = {"danceability": 0.8, "energy": 0.7}
        mock_spotify_source._make_request_with_retry.return_value = Mock(json=Mock(return_value=sample_features))

        import asyncio
        from api.routes.spotify import _fetch_audio_features

        async def run_test():
            result = await _fetch_audio_features(mock_spotify_source, "test_track_id")
            assert result == sample_features

        asyncio.run(run_test())

    def test_fetch_audio_features_not_available(self):
        """Test audio features not available."""
        mock_spotify_source = Mock()
        mock_spotify_source._get_access_token = AsyncMock()
        mock_spotify_source._ensure_client = AsyncMock()
        mock_spotify_source._make_request_with_retry = AsyncMock(return_value=None)

        import asyncio
        from api.routes.spotify import _fetch_audio_features

        async def run_test():
            result = await _fetch_audio_features(mock_spotify_source, "test_track_id")
            assert result is None

        asyncio.run(run_test())


class TestSpotifyTrackTransformation:
    """Test track data transformation functions."""

    def test_transform_to_comprehensive_track_complete(self, sample_spotify_track_data, sample_audio_features):
        """Test transformation with complete data."""
        from api.routes.spotify import _transform_to_comprehensive_track

        result = _transform_to_comprehensive_track(sample_spotify_track_data, sample_audio_features)

        assert result.id == sample_spotify_track_data["id"]
        assert result.name == sample_spotify_track_data["name"]
        assert result.popularity == sample_spotify_track_data["popularity"]
        assert result.explicit == sample_spotify_track_data["explicit"]
        assert result.duration_ms == sample_spotify_track_data["duration_ms"]
        assert result.disc_number == sample_spotify_track_data["disc_number"]
        assert result.track_number == sample_spotify_track_data["track_number"]
        assert result.is_local == sample_spotify_track_data["is_local"]

        # Test album transformation
        assert result.album.id == sample_spotify_track_data["album"]["id"]
        assert result.album.name == sample_spotify_track_data["album"]["name"]
        assert len(result.album.images) == 3
        assert result.album.release_date == sample_spotify_track_data["album"]["release_date"]

        # Test artists transformation
        assert len(result.artists) == 1
        assert result.artists[0].id == sample_spotify_track_data["artists"][0]["id"]
        assert result.artists[0].name == sample_spotify_track_data["artists"][0]["name"]

        # Test audio features
        assert result.audio_features is not None
        assert result.audio_features.danceability == sample_audio_features["danceability"]
        assert result.audio_features.energy == sample_audio_features["energy"]
        assert result.audio_features.tempo == sample_audio_features["tempo"]

        # Test external data
        assert result.external_urls == sample_spotify_track_data["external_urls"]
        assert result.external_ids == sample_spotify_track_data["external_ids"]
        assert result.available_markets == sample_spotify_track_data["available_markets"]

    def test_transform_to_comprehensive_track_no_audio_features(self, sample_spotify_track_data):
        """Test transformation without audio features."""
        from api.routes.spotify import _transform_to_comprehensive_track

        result = _transform_to_comprehensive_track(sample_spotify_track_data, None)

        assert result.audio_features is None

    def test_transform_to_comprehensive_track_minimal_data(self):
        """Test transformation with minimal required data."""
        from api.routes.spotify import _transform_to_comprehensive_track

        minimal_data = {
            "id": "test_id",
            "name": "Test Track",
            "artists": [{"id": "artist_id", "name": "Test Artist", "external_urls": {}}],
            "album": {
                "id": "album_id",
                "name": "Test Album",
                "artists": [{"id": "artist_id", "name": "Test Artist", "external_urls": {}}],
                "images": [],
                "external_urls": {},
                "release_date": "2023-01-01",
                "release_date_precision": "day",
                "total_tracks": 10,
                "album_type": "album"
            },
            "duration_ms": 180000,
            "popularity": 50,
            "explicit": False,
            "external_urls": {},
            "external_ids": {},
            "available_markets": [],
            "disc_number": 1,
            "track_number": 1,
            "is_local": False
        }

        result = _transform_to_comprehensive_track(minimal_data, None)

        assert result.id == "test_id"
        assert result.name == "Test Track"
        assert result.album.name == "Test Album"
        assert result.artists[0].name == "Test Artist"
        assert tracks[0]["audio_features"] == {}