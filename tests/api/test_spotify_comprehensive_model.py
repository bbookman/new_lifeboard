"""
TDD Tests for Comprehensive SpotifyTrack Model Enhancement
Following TDD principles - these tests should fail initially.

Tests the enhancement of SpotifyTrack to expose all captured Spotify data
including album images, full artist objects, and structured audio features.
"""
import pytest
import json
from unittest.mock import Mock

from api.routes.spotify import (
    SpotifyTrack, SpotifyAlbum, SpotifyArtist, SpotifyImage, SpotifyAudioFeatures,
    transform_spotify_data_item
)


class TestComprehensiveSpotifyTrackModel:
    """Test comprehensive SpotifyTrack model with rich data."""

    @pytest.fixture
    def comprehensive_database_row(self):
        """Mock database row with comprehensive Spotify data."""
        return {
            "id": 1,
            "namespace": "spotify",
            "source_id": "track_123_2024-01-15T10:30:00Z",
            "content": json.dumps({
                "id": "track_123",
                "name": "Bohemian Rhapsody",
                "artists": [
                    {
                        "id": "artist_123",
                        "name": "Queen",
                        "external_urls": {"spotify": "https://open.spotify.com/artist/artist_123"},
                        "genres": ["rock", "classic rock"],
                        "popularity": 85,
                        "followers": {"total": 50000000}
                    },
                    {
                        "id": "artist_456", 
                        "name": "David Bowie",
                        "external_urls": {"spotify": "https://open.spotify.com/artist/artist_456"},
                        "genres": ["rock", "glam rock"],
                        "popularity": 80,
                        "followers": {"total": 25000000}
                    }
                ],
                "album": {
                    "id": "album_123",
                    "name": "A Night at the Opera",
                    "artists": [
                        {
                            "id": "artist_123",
                            "name": "Queen",
                            "external_urls": {"spotify": "https://open.spotify.com/artist/artist_123"}
                        }
                    ],
                    "images": [
                        {"url": "https://i.scdn.co/image/large.jpg", "height": 640, "width": 640},
                        {"url": "https://i.scdn.co/image/medium.jpg", "height": 300, "width": 300},
                        {"url": "https://i.scdn.co/image/small.jpg", "height": 64, "width": 64}
                    ],
                    "external_urls": {"spotify": "https://open.spotify.com/album/album_123"},
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
                "external_urls": {"spotify": "https://open.spotify.com/track/track_123"},
                "external_ids": {"isrc": "GBCEE7500123"},
                "available_markets": ["US", "GB", "CA", "AU"],
                "disc_number": 1,
                "track_number": 11,
                "is_local": False,
                "played_at": "2024-01-15T10:30:00Z"
            }),
            "metadata": json.dumps({
                "track": {
                    "id": "track_123",
                    "name": "Bohemian Rhapsody",
                    "artists": [{"name": "Queen"}, {"name": "David Bowie"}],
                    "album": {"name": "A Night at the Opera"}
                },
                "played_at": "2024-01-15T10:30:00Z",
                "audio_features": {
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
            }),
            "embedding_status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "days_date": "2024-01-15"
        }

    def test_spotify_track_includes_album_images(self, comprehensive_database_row):
        """Test SpotifyTrack includes full album with images array."""
        # This test should FAIL initially since current implementation doesn't extract album images
        track = transform_spotify_data_item(comprehensive_database_row)
        
        # Verify track is SpotifyTrack instance
        assert isinstance(track, SpotifyTrack)
        
        # Verify album is SpotifyAlbum instance (not just string)
        assert isinstance(track.album, SpotifyAlbum)
        assert track.album.name == "A Night at the Opera"
        assert track.album.id == "album_123"
        
        # Verify album images are included
        assert len(track.album.images) == 3
        assert isinstance(track.album.images[0], SpotifyImage)
        assert track.album.images[0].url == "https://i.scdn.co/image/large.jpg"
        assert track.album.images[0].height == 640
        assert track.album.images[0].width == 640
        
        # Verify additional album metadata
        assert track.album.release_date == "1975-11-21"
        assert track.album.total_tracks == 12
        assert track.album.album_type == "album"

    def test_spotify_track_includes_multiple_artists_objects(self, comprehensive_database_row):
        """Test SpotifyTrack includes full artist objects with external URLs."""
        # This test should FAIL initially since current implementation only extracts first artist name
        track = transform_spotify_data_item(comprehensive_database_row)
        
        # Verify artists is array of SpotifyArtist objects (not just first artist name)
        assert isinstance(track.artists, list)
        assert len(track.artists) == 2
        
        # Verify first artist
        first_artist = track.artists[0]
        assert isinstance(first_artist, SpotifyArtist)
        assert first_artist.id == "artist_123"
        assert first_artist.name == "Queen"
        assert first_artist.external_urls["spotify"] == "https://open.spotify.com/artist/artist_123"
        
        # Verify second artist  
        second_artist = track.artists[1]
        assert isinstance(second_artist, SpotifyArtist)
        assert second_artist.id == "artist_456"
        assert second_artist.name == "David Bowie"
        assert second_artist.external_urls["spotify"] == "https://open.spotify.com/artist/artist_456"

    def test_spotify_track_includes_structured_audio_features(self, comprehensive_database_row):
        """Test SpotifyTrack uses SpotifyAudioFeatures model instead of raw dict."""
        # This test should FAIL initially since current implementation returns raw dict
        track = transform_spotify_data_item(comprehensive_database_row)
        
        # Verify audio_features is SpotifyAudioFeatures instance (not dict)
        assert isinstance(track.audio_features, SpotifyAudioFeatures)
        
        # Verify audio features fields
        assert track.audio_features.danceability == 0.414
        assert track.audio_features.energy == 0.404
        assert track.audio_features.valence == 0.224
        assert track.audio_features.tempo == 71.105
        assert track.audio_features.key == 0
        assert track.audio_features.mode == 0
        assert track.audio_features.time_signature == 4

    def test_spotify_track_comprehensive_fields_populated(self, comprehensive_database_row):
        """Test all comprehensive fields are populated from database metadata."""
        # This test should FAIL initially since current implementation doesn't populate all fields
        track = transform_spotify_data_item(comprehensive_database_row)
        
        # Verify comprehensive track fields
        assert track.id == "track_123"
        assert track.name == "Bohemian Rhapsody"
        assert track.duration_ms == 355000
        assert track.popularity == 80
        assert track.explicit == False
        assert track.preview_url == "https://p.scdn.co/mp3-preview/preview.mp3"
        assert track.disc_number == 1
        assert track.track_number == 11
        assert track.is_local == False
        
        # Verify external data
        assert track.external_urls["spotify"] == "https://open.spotify.com/track/track_123"
        assert track.external_ids["isrc"] == "GBCEE7500123"
        assert "US" in track.available_markets
        assert "GB" in track.available_markets
        
        # Verify played_at is set
        assert track.played_at == "2024-01-15T10:30:00Z"

    def test_spotify_track_backward_compatibility(self, comprehensive_database_row):
        """Test existing API consumers still receive expected fields."""
        # This test should PASS - ensure we don't break existing functionality
        track = transform_spotify_data_item(comprehensive_database_row)
        
        # These fields must exist for backward compatibility
        assert hasattr(track, 'id')
        assert hasattr(track, 'name') 
        assert hasattr(track, 'artists')
        assert hasattr(track, 'album')
        assert hasattr(track, 'duration_ms')
        assert hasattr(track, 'played_at')
        assert hasattr(track, 'preview_url')
        assert hasattr(track, 'external_urls')
        assert hasattr(track, 'audio_features')

    def test_spotify_track_handles_missing_optional_data(self):
        """Test SpotifyTrack handles missing optional fields gracefully."""
        # Test with minimal data to ensure we don't break on missing fields
        minimal_row = {
            "id": 1,
            "namespace": "spotify", 
            "source_id": "track_minimal_2024-01-15T10:30:00Z",
            "content": json.dumps({
                "id": "track_minimal",
                "name": "Minimal Song",
                "artists": [{"name": "Minimal Artist"}],
                "album": {"name": "Minimal Album"},
                "duration_ms": 180000,
                "played_at": "2024-01-15T10:30:00Z"
                # Missing: images, external_urls, popularity, etc.
            }),
            "metadata": json.dumps({
                "track": {"id": "track_minimal", "name": "Minimal Song"},
                "played_at": "2024-01-15T10:30:00Z"
                # Missing: audio_features
            }),
            "embedding_status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "days_date": "2024-01-15"
        }
        
        # Should not crash and should provide reasonable defaults
        track = transform_spotify_data_item(minimal_row)
        
        assert isinstance(track, SpotifyTrack)
        assert track.id == "track_minimal"
        assert track.name == "Minimal Song"
        
        # Should handle missing audio_features gracefully
        if track.audio_features is not None:
            assert isinstance(track.audio_features, (SpotifyAudioFeatures, dict))

    def test_spotify_track_handles_malformed_data(self):
        """Test SpotifyTrack handles malformed data without crashing."""
        malformed_row = {
            "id": 1,
            "namespace": "spotify",
            "source_id": "track_malformed_2024-01-15T10:30:00Z", 
            "content": "invalid_json",  # Malformed JSON
            "metadata": json.dumps({}),
            "embedding_status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "days_date": "2024-01-15"
        }
        
        # Should not crash - should return a valid SpotifyTrack with defaults
        track = transform_spotify_data_item(malformed_row)
        
        assert isinstance(track, SpotifyTrack)
        # Should have sensible defaults when data is malformed
        assert track.id in ["unknown", ""]
        assert track.name in ["Unknown Title", ""]


class TestComprehensiveSpotifyAPI:
    """Test API endpoints return comprehensive data."""
    
    def test_recent_tracks_returns_comprehensive_data(self):
        """Test GET /spotify/recent returns comprehensive SpotifyTrack objects."""
        # This will be implemented after the transform function is enhanced
        # For now, just assert the structure we expect
        pass
        
    def test_tracks_endpoint_returns_comprehensive_data(self):
        """Test GET /spotify/tracks returns comprehensive SpotifyTrack objects."""
        # This will be implemented after the transform function is enhanced  
        # For now, just assert the structure we expect
        pass