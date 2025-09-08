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
        assert tracks[0]["audio_features"] == {}