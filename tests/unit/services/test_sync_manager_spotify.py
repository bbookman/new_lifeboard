import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any, List

from services.sync_manager_service import SyncManagerService
from services.scheduler import AsyncScheduler
from services.ingestion import IngestionService, IngestionResult
from sources.spotify import SpotifySource
from config.models import AppConfig, SpotifyConfig
from core.database import DatabaseService


class TestSyncManagerSpotifyIntegration:
    """Test SpotifySource integration with SyncManagerService"""
    
    @pytest.fixture
    def mock_spotify_config(self):
        """Create a mock Spotify configuration"""
        return SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8888/callback",
            enabled=True,
            sync_interval_hours=2,
            recently_played_limit=20,
            max_retries=3,
            retry_delay=1.0,
            request_timeout=30.0,
            rate_limit_max_delay=60,
            respect_retry_after=True,
            required_scopes=["user-read-recently-played", "user-read-playback-state"]
        )
    
    @pytest.fixture
    def mock_app_config(self, mock_spotify_config):
        """Create a mock app configuration with Spotify enabled"""
        config = MagicMock(spec=AppConfig)
        config.spotify = mock_spotify_config
        config.scheduler = MagicMock()
        config.scheduler.job_timeout_minutes = 30
        return config
    
    @pytest.fixture
    def mock_spotify_source(self, mock_spotify_config):
        """Create a mock SpotifySource"""
        mock_db_service = MagicMock(spec=DatabaseService)
        source = MagicMock(spec=SpotifySource)
        source.namespace = "spotify"
        source.config = mock_spotify_config
        source.is_configured.return_value = True
        return source
    
    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock AsyncScheduler"""
        scheduler = MagicMock(spec=AsyncScheduler)
        scheduler.add_job = MagicMock(return_value="spotify_job_123")
        scheduler.remove_job = MagicMock(return_value=True)
        scheduler.trigger_job = AsyncMock(return_value=True)
        scheduler.pause_job = MagicMock(return_value=True)
        scheduler.resume_job = MagicMock(return_value=True)
        scheduler.get_job_status = MagicMock(return_value={
            "job_id": "spotify_job_123",
            "status": "running",
            "last_run": "2024-01-01T12:00:00Z",
            "next_run": "2024-01-01T14:00:00Z",
            "interval_seconds": 7200,
            "error_count": 0
        })
        scheduler.get_all_jobs_status = MagicMock(return_value={
            "jobs": {
                "spotify_job_123": {
                    "job_id": "spotify_job_123",
                    "status": "running",
                    "last_run": "2024-01-01T12:00:00Z",
                    "next_run": "2024-01-01T14:00:00Z",
                    "interval_seconds": 7200,
                    "error_count": 0
                }
            },
            "summary": {
                "total_jobs": 1,
                "running_jobs": 1,
                "paused_jobs": 0,
                "failed_jobs": 0
            }
        })
        scheduler.is_running = True
        scheduler.stats = {"total_executions": 5, "successful_executions": 5}
        return scheduler
    
    @pytest.fixture
    def mock_ingestion_service(self, mock_spotify_source):
        """Create a mock IngestionService"""
        service = MagicMock(spec=IngestionService)
        service.sources = {"spotify": mock_spotify_source}
        service.ingest_from_source = AsyncMock(return_value=IngestionResult(
            items_processed=10,
            items_stored=8,
            errors=[],
            source_namespace="spotify",
            ingestion_mode="complete"
        ))
        service.async_get_ingestion_status = AsyncMock(return_value={
            "source_stats": {
                "spotify": {
                    "total_items": 100,
                    "last_sync": "2024-01-01T12:00:00Z",
                    "status": "active"
                }
            },
            "registered_sources": ["spotify"],
            "database_stats": {"total_items": 100},
            "vector_store_stats": {"indexed_items": 95},
            "pending_embeddings": 5
        })
        service.database = MagicMock()
        service.database.async_get_setting = AsyncMock(return_value=None)
        return service
    
    @pytest.fixture
    def sync_manager(self, mock_scheduler, mock_ingestion_service, mock_app_config):
        """Create SyncManagerService instance with mocked dependencies"""
        return SyncManagerService(
            scheduler=mock_scheduler,
            ingestion_service=mock_ingestion_service,
            config=mock_app_config
        )
    
    @pytest.mark.asyncio
    async def test_auto_discover_includes_spotify_when_configured(
        self, sync_manager, mock_app_config, mock_spotify_source
    ):
        """Test that auto_discover_and_register_sources includes Spotify when properly configured"""
        # Ensure Spotify is enabled and configured
        mock_app_config.spotify.enabled = True
        mock_app_config.spotify.is_fully_configured.return_value = True
        mock_spotify_source.is_configured.return_value = True
        
        # Mock the register_source_for_auto_sync method to return True
        with patch.object(sync_manager, 'register_source_for_auto_sync', new_callable=AsyncMock) as mock_register:
            mock_register.return_value = True
            
            registered_sources = await sync_manager.auto_discover_and_register_sources()
            
            # Verify Spotify was included
            assert "spotify" in registered_sources
            mock_register.assert_called_with(mock_spotify_source)
    
    @pytest.mark.asyncio
    async def test_auto_discover_excludes_spotify_when_disabled(
        self, sync_manager, mock_app_config, mock_spotify_source
    ):
        """Test that auto_discover_and_register_sources excludes Spotify when disabled"""
        # Disable Spotify
        mock_app_config.spotify.enabled = False
        mock_app_config.spotify.is_fully_configured.return_value = False
        
        with patch.object(sync_manager, 'register_source_for_auto_sync', new_callable=AsyncMock) as mock_register:
            registered_sources = await sync_manager.auto_discover_and_register_sources()
            
            # Verify Spotify was not included
            assert "spotify" not in registered_sources
            # Verify register was not called for Spotify
            mock_register.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_auto_discover_excludes_spotify_when_not_configured(
        self, sync_manager, mock_app_config, mock_spotify_source
    ):
        """Test that auto_discover_and_register_sources excludes Spotify when not fully configured"""
        # Enable but not fully configured
        mock_app_config.spotify.enabled = True
        mock_app_config.spotify.is_fully_configured.return_value = False
        
        with patch.object(sync_manager, 'register_source_for_auto_sync', new_callable=AsyncMock) as mock_register:
            registered_sources = await sync_manager.auto_discover_and_register_sources()
            
            # Verify Spotify was not included
            assert "spotify" not in registered_sources
            mock_register.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_auto_discover_excludes_spotify_when_not_in_sources(
        self, sync_manager, mock_app_config, mock_ingestion_service
    ):
        """Test that auto_discover_and_register_sources excludes Spotify when not in ingestion sources"""
        # Configure Spotify but remove from sources
        mock_app_config.spotify.enabled = True
        mock_app_config.spotify.is_fully_configured.return_value = True
        mock_ingestion_service.sources = {}  # No Spotify source
        
        with patch.object(sync_manager, 'register_source_for_auto_sync', new_callable=AsyncMock) as mock_register:
            registered_sources = await sync_manager.auto_discover_and_register_sources()
            
            # Verify Spotify was not included
            assert "spotify" not in registered_sources
            mock_register.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_register_source_for_auto_sync_with_spotify(
        self, sync_manager, mock_spotify_source, mock_scheduler
    ):
        """Test register_source_for_auto_sync with SpotifySource"""
        result = await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Verify registration was successful
        assert result is True
        
        # Verify scheduler.add_job was called with correct parameters
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        
        # Check job parameters
        assert call_args[1]["name"] == "sync_spotify"
        assert call_args[1]["namespace"] == "spotify"
        assert call_args[1]["interval_seconds"] == 7200  # 2 hours * 3600 seconds
        assert call_args[1]["max_retries"] == 3
        assert callable(call_args[1]["func"])
        
        # Verify source is tracked in mapping
        assert "spotify" in sync_manager.source_job_mapping
        assert sync_manager.source_job_mapping["spotify"] == "spotify_job_123"
    
    @pytest.mark.asyncio
    async def test_sync_interval_determination_for_spotify(
        self, sync_manager, mock_spotify_source, mock_scheduler
    ):
        """Test that sync interval is correctly determined for Spotify source"""
        # Set specific sync interval
        mock_spotify_source.config.sync_interval_hours = 3
        
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Verify interval was calculated correctly (3 hours * 3600 seconds)
        call_args = mock_scheduler.add_job.call_args
        assert call_args[1]["interval_seconds"] == 10800  # 3 * 3600
    
    @pytest.mark.asyncio
    async def test_register_source_prevents_duplicate_registration(
        self, sync_manager, mock_spotify_source, mock_scheduler
    ):
        """Test that registering the same source twice is prevented"""
        # Register once
        result1 = await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        assert result1 is True
        
        # Try to register again
        result2 = await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        assert result2 is False
        
        # Verify scheduler.add_job was only called once
        assert mock_scheduler.add_job.call_count == 1
    
    @pytest.mark.asyncio
    async def test_spotify_appears_in_sync_status(
        self, sync_manager, mock_spotify_source, mock_scheduler, mock_ingestion_service
    ):
        """Test that Spotify source appears in sync status after registration"""
        # Register the source
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Get sync status
        status = await sync_manager.get_source_sync_status("spotify")
        
        # Verify status is returned
        assert status is not None
        assert status["namespace"] == "spotify"
        assert status["job_id"] == "spotify_job_123"
        assert "scheduler_status" in status
        assert "ingestion_status" in status
    
    @pytest.mark.asyncio
    async def test_spotify_appears_in_all_sources_sync_status(
        self, sync_manager, mock_spotify_source, mock_scheduler, mock_ingestion_service
    ):
        """Test that Spotify appears in all sources sync status"""
        # Register the source
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Get all sources status
        all_status = await sync_manager.get_all_sources_sync_status()
        
        # Verify Spotify is included
        assert "sources" in all_status
        assert "spotify" in all_status["sources"]
        
        spotify_status = all_status["sources"]["spotify"]
        assert spotify_status["namespace"] == "spotify"
        assert spotify_status["job_id"] == "spotify_job_123"
        assert "scheduler_status" in spotify_status
        assert "ingestion_status" in spotify_status
    
    @pytest.mark.asyncio
    async def test_trigger_scheduled_job_for_spotify(
        self, sync_manager, mock_spotify_source, mock_scheduler
    ):
        """Test triggering scheduled job for Spotify"""
        # Register the source
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Trigger the job
        result = await sync_manager.trigger_scheduled_job("spotify")
        
        # Verify job was triggered
        assert result is True
        mock_scheduler.trigger_job.assert_called_once_with("spotify_job_123")
    
    @pytest.mark.asyncio
    async def test_trigger_scheduled_job_for_unregistered_spotify(
        self, sync_manager, mock_scheduler
    ):
        """Test triggering scheduled job for unregistered Spotify source"""
        # Try to trigger without registering
        result = await sync_manager.trigger_scheduled_job("spotify")
        
        # Verify it fails gracefully
        assert result is False
        mock_scheduler.trigger_job.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_unregister_spotify_source(
        self, sync_manager, mock_spotify_source, mock_scheduler
    ):
        """Test unregistering Spotify source from auto sync"""
        # Register first
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        assert "spotify" in sync_manager.source_job_mapping
        
        # Unregister
        result = await sync_manager.unregister_source_from_auto_sync("spotify")
        
        # Verify unregistration was successful
        assert result is True
        mock_scheduler.remove_job.assert_called_once_with("spotify_job_123")
        assert "spotify" not in sync_manager.source_job_mapping
    
    @pytest.mark.asyncio
    async def test_pause_and_resume_spotify_sync(
        self, sync_manager, mock_spotify_source, mock_scheduler
    ):
        """Test pausing and resuming Spotify sync"""
        # Register first
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Pause
        pause_result = sync_manager.pause_source_sync("spotify")
        assert pause_result is True
        mock_scheduler.pause_job.assert_called_once_with("spotify_job_123")
        
        # Resume
        resume_result = sync_manager.resume_source_sync("spotify")
        assert resume_result is True
        mock_scheduler.resume_job.assert_called_once_with("spotify_job_123")
    
    @pytest.mark.asyncio
    async def test_spotify_sync_function_execution(
        self, sync_manager, mock_spotify_source, mock_scheduler, mock_ingestion_service
    ):
        """Test that the sync function created for Spotify executes correctly"""
        # Register the source
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Get the sync function that was passed to scheduler
        call_args = mock_scheduler.add_job.call_args
        sync_function = call_args[1]["func"]
        
        # Execute the sync function
        result = await sync_function()
        
        # Verify ingestion service was called
        mock_ingestion_service.ingest_from_source.assert_called_once_with(
            namespace="spotify",
            force_full_sync=False,
            limit=1000,
            ingestion_mode='complete'
        )
        
        # Verify result format
        assert isinstance(result, dict)
        assert "items_processed" in result or "success" in result
    
    @pytest.mark.asyncio
    async def test_spotify_sync_function_handles_errors(
        self, sync_manager, mock_spotify_source, mock_scheduler, mock_ingestion_service
    ):
        """Test that the sync function handles errors gracefully"""
        # Make ingestion service raise an exception
        mock_ingestion_service.ingest_from_source.side_effect = Exception("Test error")
        
        # Register the source
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Get the sync function
        call_args = mock_scheduler.add_job.call_args
        sync_function = call_args[1]["func"]
        
        # Execute the sync function - should not raise
        result = await sync_function()
        
        # Verify error was handled gracefully
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert "error" in result
        assert result["items_processed"] == 0
        assert result["items_stored"] == 0
    
    @pytest.mark.asyncio
    async def test_spotify_sync_function_timeout_handling(
        self, sync_manager, mock_spotify_source, mock_scheduler, mock_ingestion_service
    ):
        """Test that the sync function handles timeouts correctly"""
        import asyncio
        
        # Make ingestion service timeout
        async def timeout_side_effect(*args, **kwargs):
            await asyncio.sleep(10)  # This will timeout
            
        mock_ingestion_service.ingest_from_source.side_effect = timeout_side_effect
        
        # Register the source
        await sync_manager.register_source_for_auto_sync(mock_spotify_source)
        
        # Get the sync function
        call_args = mock_scheduler.add_job.call_args
        sync_function = call_args[1]["func"]
        
        # Execute with a very short timeout by patching asyncio.wait_for
        with patch('asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError("Test timeout")
            
            result = await sync_function()
            
            # Verify timeout was handled gracefully
            assert isinstance(result, dict)
            assert result.get("success") is False
            assert result.get("error") == "timeout"
            assert result["items_processed"] == 0
            assert result["items_stored"] == 0
    
    @pytest.mark.asyncio
    async def test_should_sync_on_startup_for_spotify(
        self, sync_manager, mock_ingestion_service
    ):
        """Test should_sync_on_startup logic for Spotify"""
        # Test when never synced before
        mock_ingestion_service.database.async_get_setting.return_value = None
        
        should_sync = await sync_manager.should_sync_on_startup("spotify")
        assert should_sync is True
        
        # Test when recently synced
        recent_time = datetime.now(timezone.utc).isoformat()
        mock_ingestion_service.database.async_get_setting.return_value = recent_time
        
        should_sync = await sync_manager.should_sync_on_startup("spotify")
        # Should not sync if recently synced (depends on interval)
        # This test verifies the method doesn't crash with Spotify namespace
        assert isinstance(should_sync, bool)
    
    @pytest.mark.asyncio
    async def test_immediate_sync_for_spotify(
        self, sync_manager, mock_ingestion_service
    ):
        """Test triggering immediate sync for Spotify"""
        result = await sync_manager.trigger_immediate_sync("spotify", force_full_sync=True)
        
        # Verify ingestion service was called correctly
        mock_ingestion_service.ingest_from_source.assert_called_once_with(
            namespace="spotify",
            force_full_sync=True,
            limit=1000,
            ingestion_mode='partial'
        )
        
        # Verify result
        assert isinstance(result, IngestionResult)
        assert result.source_namespace == "spotify"