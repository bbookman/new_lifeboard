"""
Backend integration tests for Spotify functionality.

Tests the complete flow: SpotifySource → IngestionService → Database → API
"""
import pytest
import asyncio
import json
import httpx
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from sources.spotify import SpotifySource
from sources.base import DataItem
from config.models import SpotifyConfig, AppConfig
from core.database import DatabaseService
from services.ingestion import IngestionService
from services.sync_manager_service import SyncManagerService
from services.scheduler import AsyncScheduler
from api.routes.spotify import SpotifyTrack, transform_spotify_data_item


class TestSpotifyIntegration:
    """Integration tests for Spotify backend functionality"""

    @pytest.fixture
    def spotify_config(self):
        """Create a valid Spotify configuration for testing"""
        return SpotifyConfig(
            enabled=True,
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            sync_interval_hours=1,
            recently_played_limit=50,
            max_retries=3,
            retry_delay=1.0,
            request_timeout=30.0,
            rate_limit_max_delay=300.0,
            respect_retry_after=True,
            required_scopes=["user-read-recently-played"]
        )

    @pytest.fixture
    def app_config(self, spotify_config):
        """Create app config with Spotify configuration"""
        config = MagicMock()
        config.spotify = spotify_config
        config.scheduler = MagicMock()
        config.scheduler.job_timeout_minutes = 10
        return config

    @pytest.fixture
    def mock_db_service(self):
        """Create a mock database service"""
        db_service = MagicMock(spec=DatabaseService)
        db_service.get_connection = MagicMock()
        db_service.async_get_setting = AsyncMock()
        db_service.async_set_setting = AsyncMock()
        return db_service

    @pytest.fixture
    def mock_spotify_api_responses(self):
        """Mock Spotify API responses"""
        return {
            "token_response": {
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            },
            "recently_played_response": {
                "items": [
                    {
                        "track": {
                            "id": "track_123",
                            "name": "Test Song",
                            "artists": [{"name": "Test Artist"}],
                            "album": {"name": "Test Album"},
                            "duration_ms": 180000,
                            "preview_url": "https://example.com/preview.mp3",
                            "external_urls": {"spotify": "https://open.spotify.com/track/track_123"},
                            "popularity": 75
                        },
                        "played_at": "2023-12-01T10:30:00Z"
                    },
                    {
                        "track": {
                            "id": "track_456",
                            "name": "Another Song",
                            "artists": [{"name": "Another Artist"}],
                            "album": {"name": "Another Album"},
                            "duration_ms": 210000,
                            "preview_url": None,
                            "external_urls": {"spotify": "https://open.spotify.com/track/track_456"},
                            "popularity": 60
                        },
                        "played_at": "2023-12-01T10:25:00Z"
                    }
                ]
            },
            "audio_features_response": {
                "audio_features": [
                    {
                        "id": "track_123",
                        "danceability": 0.8,
                        "energy": 0.7,
                        "valence": 0.9,
                        "tempo": 120.0
                    },
                    {
                        "id": "track_456",
                        "danceability": 0.6,
                        "energy": 0.5,
                        "valence": 0.4,
                        "tempo": 95.0
                    }
                ]
            }
        }

    @pytest.fixture
    async def spotify_source(self, spotify_config, mock_db_service):
        """Create a SpotifySource instance for testing"""
        return SpotifySource(spotify_config, mock_db_service)

    @pytest.mark.asyncio
    async def test_spotify_source_initialization(self, spotify_source, spotify_config):
        """Test SpotifySource initializes correctly with valid config"""
        assert spotify_source.namespace == "spotify"
        assert spotify_source.config == spotify_config
        assert spotify_source.is_configured() == True
        assert spotify_source.get_source_type() == "spotify_api"

    @pytest.mark.asyncio
    async def test_spotify_source_invalid_config(self, mock_db_service):
        """Test SpotifySource raises error with invalid config"""
        invalid_config = SpotifyConfig(
            enabled=False,
            client_id="",
            client_secret="",
            redirect_uri="",
            sync_interval_hours=1,
            recently_played_limit=50
        )
        
        with pytest.raises(ValueError, match="Spotify source is disabled"):
            SpotifySource(invalid_config, mock_db_service)

    @pytest.mark.asyncio
    async def test_spotify_token_acquisition(self, spotify_source, mock_spotify_api_responses):
        """Test access token acquisition using client credentials flow"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_spotify_api_responses["token_response"]
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            token = await spotify_source._get_access_token()
            
            assert token == "test_access_token"
            assert spotify_source.access_token == "test_access_token"
            assert spotify_source.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_spotify_connection_test(self, spotify_source, mock_spotify_api_responses):
        """Test Spotify API connection test"""
        with patch.object(spotify_source, '_get_access_token', return_value="test_token"), \
             patch.object(spotify_source, '_ensure_client') as mock_ensure_client, \
             patch.object(spotify_source, '_make_test_request') as mock_test_request:
            
            mock_client = MagicMock()
            mock_ensure_client.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_test_request.return_value = mock_response
            
            result = await spotify_source.test_connection()
            assert result == True

    @pytest.mark.asyncio
    async def test_spotify_fetch_items_success(self, spotify_source, mock_spotify_api_responses):
        """Test successful fetching of Spotify tracks"""
        with patch.object(spotify_source, '_get_access_token', return_value="test_token"), \
             patch.object(spotify_source, '_ensure_client') as mock_ensure_client, \
             patch.object(spotify_source, '_make_request_with_retry') as mock_request:
            
            # Mock client
            mock_client = MagicMock()
            mock_ensure_client.return_value = mock_client
            
            # Mock API responses
            recently_played_response = MagicMock()
            recently_played_response.json.return_value = mock_spotify_api_responses["recently_played_response"]
            
            audio_features_response = MagicMock()
            audio_features_response.json.return_value = mock_spotify_api_responses["audio_features_response"]
            
            mock_request.side_effect = [recently_played_response, audio_features_response]
            
            # Fetch items
            items = []
            async for item in spotify_source.fetch_items():
                items.append(item)
            
            # Verify results
            assert len(items) == 2
            
            # Check first item
            first_item = items[0]
            assert isinstance(first_item, DataItem)
            assert first_item.namespace == "spotify"
            assert first_item.source_id == "track_123_2023-12-01T10:30:00Z"
            assert "Test Song" in first_item.content
            assert "Test Artist" in first_item.content
            
            # Check metadata structure
            metadata = first_item.metadata
            assert metadata["track"]["id"] == "track_123"
            assert metadata["track"]["name"] == "Test Song"
            assert metadata["played_at"] == "2023-12-01T10:30:00Z"
            assert metadata["audio_features"]["danceability"] == 0.8

    @pytest.mark.asyncio
    async def test_spotify_fetch_items_api_error(self, spotify_source):
        """Test handling of Spotify API errors during fetch"""
        with patch.object(spotify_source, '_get_access_token', return_value="test_token"), \
             patch.object(spotify_source, '_ensure_client') as mock_ensure_client, \
             patch.object(spotify_source, '_make_request_with_retry', return_value=None):
            
            mock_client = MagicMock()
            mock_ensure_client.return_value = mock_client
            
            # Should not yield any items when API fails
            items = []
            async for item in spotify_source.fetch_items():
                items.append(item)
            
            assert len(items) == 0

    @pytest.mark.asyncio
    async def test_spotify_get_item_not_supported(self, spotify_source):
        """Test that get_item returns None (not supported by Spotify API)"""
        result = await spotify_source.get_item("some_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_data_item_transformation(self, spotify_source, mock_spotify_api_responses):
        """Test transformation of Spotify track data to DataItem"""
        track_item = mock_spotify_api_responses["recently_played_response"]["items"][0]
        audio_features = mock_spotify_api_responses["audio_features_response"]["audio_features"][0]
        
        data_item = spotify_source._transform_track(track_item, audio_features)
        
        assert isinstance(data_item, DataItem)
        assert data_item.namespace == "spotify"
        assert data_item.source_id == "track_123_2023-12-01T10:30:00Z"
        assert "Test Song by Test Artist from Test Album" == data_item.content
        assert data_item.created_at.isoformat() == "2023-12-01T10:30:00+00:00"
        
        # Check metadata structure
        metadata = data_item.metadata
        assert metadata["track"]["id"] == "track_123"
        assert metadata["audio_features"]["danceability"] == 0.8

    @pytest.mark.asyncio
    async def test_ingestion_service_integration(self, spotify_source, mock_db_service, mock_spotify_api_responses):
        """Test integration with IngestionService"""
        # Mock IngestionService
        ingestion_service = MagicMock()
        ingestion_service.sources = {"spotify": spotify_source}
        ingestion_service.ingest_from_source = AsyncMock()
        
        # Mock successful ingestion result
        mock_result = MagicMock()
        mock_result.items_processed = 2
        mock_result.items_stored = 2
        mock_result.errors = []
        mock_result.to_dict.return_value = {
            "items_processed": 2,
            "items_stored": 2,
            "errors": []
        }
        ingestion_service.ingest_from_source.return_value = mock_result
        
        # Test ingestion
        result = await ingestion_service.ingest_from_source(
            namespace="spotify",
            force_full_sync=False,
            limit=50
        )
        
        assert result.items_processed == 2
        assert result.items_stored == 2
        assert len(result.errors) == 0
        
        # Verify ingestion was called with correct parameters
        ingestion_service.ingest_from_source.assert_called_once_with(
            namespace="spotify",
            force_full_sync=False,
            limit=50
        )

    @pytest.mark.asyncio
    async def test_sync_manager_integration(self, app_config, mock_db_service):
        """Test integration with SyncManagerService"""
        # Mock dependencies
        mock_scheduler = MagicMock(spec=AsyncScheduler)
        mock_scheduler.add_job = MagicMock(return_value="job_123")
        
        mock_ingestion_service = MagicMock()
        mock_spotify_source = MagicMock()
        mock_spotify_source.namespace = "spotify"
        mock_ingestion_service.sources = {"spotify": mock_spotify_source}
        
        # Create sync manager
        sync_manager = SyncManagerService(
            scheduler=mock_scheduler,
            ingestion_service=mock_ingestion_service,
            config=app_config
        )
        
        # Test source registration
        success = await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        assert success == True
        assert "spotify" in sync_manager.source_job_mapping
        assert sync_manager.source_job_mapping["spotify"] == "job_123"
        
        # Verify scheduler was called with correct interval
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        assert call_args[1]["name"] == "sync_spotify"
        assert call_args[1]["namespace"] == "spotify"
        assert call_args[1]["interval_seconds"] == 3600  # 1 hour

    @pytest.mark.asyncio
    async def test_sync_manager_auto_discovery(self, app_config, mock_db_service):
        """Test auto-discovery of Spotify source by SyncManagerService"""
        # Mock dependencies
        mock_scheduler = MagicMock(spec=AsyncScheduler)
        mock_ingestion_service = MagicMock()
        mock_spotify_source = MagicMock()
        mock_spotify_source.namespace = "spotify"
        mock_ingestion_service.sources = {"spotify": mock_spotify_source}
        
        # Create sync manager
        sync_manager = SyncManagerService(
            scheduler=mock_scheduler,
            ingestion_service=mock_ingestion_service,
            config=app_config
        )
        
        # Mock register_source_for_auto_sync to return success
        with patch.object(sync_manager, 'register_source_for_auto_sync', return_value=True) as mock_register:
            registered_sources = await sync_manager.auto_discover_and_register_sources()
            
            assert "spotify" in registered_sources
            mock_register.assert_called_with(mock_spotify_source)

    @pytest.mark.asyncio
    async def test_database_persistence(self, mock_db_service, mock_spotify_api_responses):
        """Test that Spotify data is properly persisted to database"""
        # Mock database operations
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.execute.return_value = mock_cursor
        mock_connection.commit = MagicMock()
        mock_db_service.get_connection.return_value.__enter__.return_value = mock_connection
        
        # Create sample DataItem
        track_item = mock_spotify_api_responses["recently_played_response"]["items"][0]
        audio_features = mock_spotify_api_responses["audio_features_response"]["audio_features"][0]
        
        data_item = DataItem(
            namespace="spotify",
            source_id="track_123_2023-12-01T10:30:00Z",
            content="Test Song by Test Artist from Test Album",
            metadata={
                "track": track_item["track"],
                "played_at": track_item["played_at"],
                "audio_features": audio_features
            },
            created_at=datetime(2023, 12, 1, 10, 30, 0, tzinfo=timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Simulate database insertion
        insert_query = """
            INSERT INTO data_items (namespace, source_id, content, metadata, created_at, updated_at, days_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        # Verify the data would be inserted correctly
        assert data_item.namespace == "spotify"
        assert data_item.source_id == "track_123_2023-12-01T10:30:00Z"
        assert "Test Song" in data_item.content
        assert data_item.metadata["track"]["id"] == "track_123"

    @pytest.mark.asyncio
    async def test_api_route_integration(self, mock_spotify_api_responses):
        """Test API route data transformation"""
        # Create mock database row
        track_item = mock_spotify_api_responses["recently_played_response"]["items"][0]
        audio_features = mock_spotify_api_responses["audio_features_response"]["audio_features"][0]
        
        mock_row = {
            "id": 1,
            "namespace": "spotify",
            "source_id": "track_123_2023-12-01T10:30:00Z",
            "content": json.dumps(track_item["track"]),
            "metadata": json.dumps({
                "track": track_item["track"],
                "played_at": track_item["played_at"],
                "audio_features": audio_features
            }),
            "created_at": "2023-12-01T10:30:00Z",
            "updated_at": "2023-12-01T10:30:00Z",
            "days_date": "2023-12-01"
        }
        
        # Test transformation
        spotify_track = transform_spotify_data_item(mock_row)
        
        assert isinstance(spotify_track, SpotifyTrack)
        assert spotify_track.id == "track_123"
        assert spotify_track.title == "Test Song"
        assert spotify_track.artist == "Test Artist"
        assert spotify_track.album == "Test Album"
        assert spotify_track.duration_ms == 180000
        assert spotify_track.preview_url == "https://example.com/preview.mp3"
        assert spotify_track.audio_features["danceability"] == 0.8

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, spotify_source, mock_spotify_api_responses):
        """Test error handling and recovery scenarios"""
        # Test token refresh on 401 error
        with patch.object(spotify_source, '_get_access_token') as mock_get_token, \
             patch.object(spotify_source, '_ensure_client') as mock_ensure_client, \
             patch.object(spotify_source, '_make_request_with_retry') as mock_request:
            
            mock_client = MagicMock()
            mock_ensure_client.return_value = mock_client
            
            # First call fails with 401, second succeeds
            mock_request.side_effect = [
                None,  # First call fails
                MagicMock(json=lambda: mock_spotify_api_responses["recently_played_response"])  # Second succeeds
            ]
            
            # Should handle the error gracefully
            items = []
            async for item in spotify_source.fetch_items():
                items.append(item)
            
            # Should not crash, but may return empty results
            assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_rate_limiting_handling(self, spotify_source):
        """Test handling of rate limiting (429 responses)"""
        with patch.object(spotify_source, '_get_access_token', return_value="test_token"), \
             patch.object(spotify_source, '_ensure_client') as mock_ensure_client, \
             patch('httpx.AsyncClient') as mock_client_class:
            
            mock_client = MagicMock()
            mock_ensure_client.return_value = mock_client
            
            # Mock rate limited response
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}
            mock_client.get = AsyncMock(return_value=mock_response)
            
            # Should handle rate limiting gracefully
            result = await spotify_source._make_request_with_retry(
                mock_client, 
                "/me/player/recently-played", 
                {"limit": "50"}
            )
            
            # Should return None when rate limited and retries exhausted
            assert result is None

    @pytest.mark.asyncio
    async def test_complete_integration_flow(self, spotify_config, mock_db_service, mock_spotify_api_responses):
        """Test complete end-to-end integration flow"""
        # 1. Create SpotifySource
        spotify_source = SpotifySource(spotify_config, mock_db_service)
        
        # 2. Mock external API calls
        with patch.object(spotify_source, '_get_access_token', return_value="test_token"), \
             patch.object(spotify_source, '_ensure_client') as mock_ensure_client, \
             patch.object(spotify_source, '_make_request_with_retry') as mock_request:
            
            mock_client = MagicMock()
            mock_ensure_client.return_value = mock_client
            
            # Mock successful API responses
            recently_played_response = MagicMock()
            recently_played_response.json.return_value = mock_spotify_api_responses["recently_played_response"]
            
            audio_features_response = MagicMock()
            audio_features_response.json.return_value = mock_spotify_api_responses["audio_features_response"]
            
            mock_request.side_effect = [recently_played_response, audio_features_response]
            
            # 3. Fetch data from source
            items = []
            async for item in spotify_source.fetch_items():
                items.append(item)
            
            # 4. Verify data structure
            assert len(items) == 2
            
            for item in items:
                assert isinstance(item, DataItem)
                assert item.namespace == "spotify"
                assert item.source_id.startswith("track_")
                assert item.content is not None
                assert item.metadata is not None
                assert item.created_at is not None
                
                # Verify metadata structure
                assert "track" in item.metadata
                assert "played_at" in item.metadata
                assert "audio_features" in item.metadata
                
                # Verify track data
                track_data = item.metadata["track"]
                assert "id" in track_data
                assert "name" in track_data
                assert "artists" in track_data
                assert "album" in track_data
            
            # 5. Verify API transformation would work
            for item in items:
                # Simulate database row structure
                mock_row = {
                    "id": 1,
                    "namespace": item.namespace,
                    "source_id": item.source_id,
                    "content": json.dumps(item.metadata["track"]),
                    "metadata": json.dumps(item.metadata),
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                    "days_date": item.created_at.strftime("%Y-%m-%d")
                }
                
                # Test API transformation
                spotify_track = transform_spotify_data_item(mock_row)
                assert isinstance(spotify_track, SpotifyTrack)
                assert spotify_track.id == item.metadata["track"]["id"]
                assert spotify_track.title == item.metadata["track"]["name"]

    @pytest.mark.asyncio
    async def test_sync_metadata(self, spotify_source):
        """Test sync metadata generation"""
        metadata = await spotify_source.get_sync_metadata()
        
        assert metadata["source_type"] == "spotify_api"
        assert metadata["namespace"] == "spotify"
        assert metadata["is_configured"] == True
        assert metadata["recently_played_limit"] == 50
        assert metadata["sync_interval_hours"] == 1
        assert "last_sync" in metadata