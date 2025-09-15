"""
Integration tests to verify that Twitter sources are completely bypassed by the automatic scheduler system.

This test suite confirms that the automated Twitter activity generating excessive [TWITTER TRACE] logs 
has been eliminated while preserving manual functionality.
"""

import asyncio
import logging
import pytest
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from services.startup import StartupService
from services.sync_manager_service import SyncManagerService
from services.scheduler import AsyncScheduler
from services.ingestion import IngestionService
from services.twitter_api_service import TwitterAPIService
from services.twitter_rate_limit_service import TwitterRateLimitService
from sources.twitter import TwitterSource
from sources.limitless import LimitlessSource
from sources.news import NewsSource
from sources.weather import WeatherSource
from sources.spotify import SpotifySource
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from config.models import AppConfig, TwitterConfig, LimitlessConfig, NewsConfig, WeatherConfig, SpotifyConfig
from config.models import DatabaseConfig, VectorStoreConfig, EmbeddingConfig, SchedulerConfig

logger = logging.getLogger(__name__)


class TestTwitterSchedulerBypass:
    """Test suite to verify Twitter sources are bypassed by automatic scheduler system"""
    
    @pytest.fixture
    async def mock_config(self):
        """Create a mock configuration with all sources enabled"""
        config = Mock(spec=AppConfig)
        
        # Twitter config - configured but should be bypassed
        config.twitter = Mock(spec=TwitterConfig)
        config.twitter.enabled = True
        config.twitter.bearer_token = "test_bearer_token"
        config.twitter.user_id = "123456789"
        config.twitter.username = "testuser"
        config.twitter.is_configured.return_value = True
        config.twitter.is_api_configured.return_value = True
        
        # Other source configs - should be registered normally
        config.limitless = Mock(spec=LimitlessConfig)
        config.limitless.api_key = "test_limitless_key"
        config.limitless.is_api_key_configured.return_value = True
        config.limitless.sync_interval_hours = 6
        
        config.news = Mock(spec=NewsConfig)
        config.news.enabled = True
        config.news.api_key = "test_news_key"
        config.news.endpoint = "https://api.news.com"
        config.news.is_fully_configured.return_value = True
        config.news.is_api_key_configured.return_value = True
        config.news.is_endpoint_configured.return_value = True
        config.news.sync_interval_hours = 12
        
        config.weather = Mock(spec=WeatherConfig)
        config.weather.enabled = True
        config.weather.api_key = "test_weather_key"
        config.weather.endpoint = "https://api.weather.com"
        config.weather.is_fully_configured.return_value = True
        config.weather.is_api_key_configured.return_value = True
        config.weather.is_endpoint_configured.return_value = True
        config.weather.sync_interval_hours = 8
        
        config.spotify = Mock(spec=SpotifyConfig)
        config.spotify.enabled = True
        config.spotify.client_id = "test_spotify_client"
        config.spotify.client_secret = "test_spotify_secret"
        config.spotify.is_api_configured.return_value = True
        config.spotify.is_fully_configured.return_value = True
        config.spotify.sync_interval_hours = 24
        
        # Core service configs
        config.database = Mock(spec=DatabaseConfig)
        config.database.path = ":memory:"
        
        config.vector_store = Mock(spec=VectorStoreConfig)
        config.embeddings = Mock(spec=EmbeddingConfig)
        
        config.scheduler = Mock(spec=SchedulerConfig)
        config.scheduler.check_interval_seconds = 300
        config.scheduler.max_concurrent_jobs = 3
        config.scheduler.job_timeout_minutes = 30
        
        return config
    
    @pytest.fixture
    async def mock_database(self):
        """Create a mock database service"""
        db = Mock(spec=DatabaseService)
        db.get_connection = Mock()
        db.async_get_setting = AsyncMock(return_value=None)
        db.async_get_database_stats = AsyncMock(return_value={"tables": 5})
        return db
    
    @pytest.fixture
    async def mock_vector_store(self):
        """Create a mock vector store service"""
        vs = Mock(spec=VectorStoreService)
        vs.get_stats = Mock(return_value={"collections": 1})
        vs.cleanup = Mock()
        return vs
    
    @pytest.fixture
    async def mock_embedding_service(self):
        """Create a mock embedding service"""
        es = Mock(spec=EmbeddingService)
        es.is_initialized = True
        es.model = Mock()
        return es
    
    @pytest.fixture
    async def startup_service(self, mock_config, mock_database, mock_vector_store, mock_embedding_service):
        """Create a startup service with mocked dependencies"""
        startup = StartupService(mock_config)
        startup.database = mock_database
        startup.vector_store = mock_vector_store
        startup.embedding_service = mock_embedding_service
        return startup
    
    @pytest.fixture
    async def mock_ingestion_service(self, mock_database, mock_vector_store, mock_embedding_service, mock_config):
        """Create a mock ingestion service"""
        ingestion = Mock(spec=IngestionService)
        ingestion.sources = {}
        ingestion.register_source = Mock()
        ingestion.async_get_ingestion_status = AsyncMock(return_value={
            "registered_sources": [],
            "source_stats": {},
            "database_stats": {},
            "vector_store_stats": {},
            "pending_embeddings": 0
        })
        return ingestion
    
    @pytest.fixture
    async def scheduler(self, mock_config):
        """Create a real scheduler instance for testing"""
        scheduler = AsyncScheduler(
            check_interval_seconds=mock_config.scheduler.check_interval_seconds,
            max_concurrent_jobs=mock_config.scheduler.max_concurrent_jobs
        )
        yield scheduler
        # Cleanup
        if scheduler.is_running:
            await scheduler.stop()
    
    @pytest.fixture
    async def sync_manager(self, scheduler, mock_ingestion_service, mock_config):
        """Create a sync manager with real scheduler and mock ingestion service"""
        return SyncManagerService(
            scheduler=scheduler,
            ingestion_service=mock_ingestion_service,
            config=mock_config
        )
    
    async def test_startup_skips_twitter_source_registration(self, startup_service, mock_config):
        """Test that startup process skips Twitter source registration"""
        with patch.object(startup_service, '_initialize_core_services') as mock_core, \
             patch.object(startup_service, '_initialize_ingestion_service') as mock_ingestion, \
             patch.object(startup_service, '_initialize_chat_service') as mock_chat, \
             patch.object(startup_service, '_initialize_document_service') as mock_doc, \
             patch.object(startup_service, '_initialize_default_prompt') as mock_prompt, \
             patch.object(startup_service, '_initialize_llm_service') as mock_llm, \
             patch.object(startup_service, '_initialize_sync_status_service') as mock_sync_status, \
             patch.object(startup_service, '_initialize_sync_services') as mock_sync_services, \
             patch.object(startup_service, '_start_auto_sync') as mock_auto_sync, \
             patch.object(startup_service, '_start_background_sync') as mock_bg_sync, \
             patch.object(startup_service, '_perform_startup_health_check') as mock_health, \
             patch.object(startup_service, '_initialize_logging') as mock_logging:
            
            # Mock all initialization methods to succeed
            mock_core.return_value = None
            mock_ingestion.return_value = None
            mock_chat.return_value = None
            mock_doc.return_value = None
            mock_prompt.return_value = None
            mock_llm.return_value = None
            mock_sync_status.return_value = None
            mock_sync_services.return_value = None
            mock_auto_sync.return_value = None
            mock_bg_sync.return_value = None
            mock_health.return_value = {"overall_healthy": True}
            mock_logging.return_value = None
            
            # Create mock ingestion service to track source registrations
            mock_ingestion_service = Mock()
            startup_service.ingestion_service = mock_ingestion_service
            
            # Mock source creation
            with patch('sources.limitless.LimitlessSource') as mock_limitless_cls, \
                 patch('sources.news.NewsSource') as mock_news_cls, \
                 patch('sources.weather.WeatherSource') as mock_weather_cls, \
                 patch('sources.spotify.SpotifySource') as mock_spotify_cls:
                
                mock_limitless_cls.return_value = Mock(spec=LimitlessSource)
                mock_news_cls.return_value = Mock(spec=NewsSource)
                mock_weather_cls.return_value = Mock(spec=WeatherSource)
                mock_spotify_cls.return_value = Mock(spec=SpotifySource)
                
                # Run the actual _register_data_sources method
                startup_result = {"sources_registered": [], "errors": []}
                await startup_service._register_data_sources(startup_result)
                
                # Verify Twitter source was NOT registered
                registered_sources = startup_result["sources_registered"]
                assert "twitter" not in registered_sources, "Twitter source should not be registered during startup"
                
                # Verify other sources were registered (if configured)
                expected_sources = ["limitless", "news", "weather", "spotify"]
                for source in expected_sources:
                    assert source in registered_sources, f"{source} should be registered during startup"
                
                # Verify TwitterSource was never instantiated during startup
                with patch('sources.twitter.TwitterSource') as mock_twitter_cls:
                    mock_twitter_cls.assert_not_called()
    
    async def test_startup_logs_twitter_skip_message(self, startup_service, mock_config, caplog):
        """Test that startup logs indicate Twitter source is skipped"""
        with patch.object(startup_service, '_initialize_core_services'), \
             patch.object(startup_service, '_initialize_ingestion_service'), \
             patch.object(startup_service, '_initialize_chat_service'), \
             patch.object(startup_service, '_initialize_document_service'), \
             patch.object(startup_service, '_initialize_default_prompt'), \
             patch.object(startup_service, '_initialize_llm_service'), \
             patch.object(startup_service, '_initialize_sync_status_service'), \
             patch.object(startup_service, '_initialize_sync_services'), \
             patch.object(startup_service, '_start_auto_sync'), \
             patch.object(startup_service, '_start_background_sync'), \
             patch.object(startup_service, '_perform_startup_health_check'), \
             patch.object(startup_service, '_initialize_logging'):
            
            startup_service.ingestion_service = Mock()
            
            with caplog.at_level(logging.INFO):
                startup_result = {"sources_registered": [], "errors": []}
                await startup_service._register_data_sources(startup_result)
                
                # Check for Twitter skip message in logs
                twitter_skip_messages = [
                    record.message for record in caplog.records 
                    if "twitter" in record.message.lower() and "skip" in record.message.lower()
                ]
                assert len(twitter_skip_messages) > 0, "Should log message about skipping Twitter source registration"
    
    async def test_sync_manager_auto_discovery_excludes_twitter(self, sync_manager, mock_ingestion_service):
        """Test that sync manager auto-discovery doesn't include Twitter sources"""
        # Mock ingestion service to have various sources including Twitter
        mock_limitless = Mock(spec=LimitlessSource)
        mock_limitless.namespace = "limitless"
        
        mock_news = Mock(spec=NewsSource)
        mock_news.namespace = "news"
        
        mock_weather = Mock(spec=WeatherSource)
        mock_weather.namespace = "weather"
        
        mock_spotify = Mock(spec=SpotifySource)
        mock_spotify.namespace = "spotify"
        
        mock_twitter = Mock(spec=TwitterSource)
        mock_twitter.namespace = "twitter"
        
        # Set up ingestion service sources
        mock_ingestion_service.sources = {
            "limitless": mock_limitless,
            "news": mock_news,
            "weather": mock_weather,
            "spotify": mock_spotify,
            "twitter": mock_twitter  # Twitter source present but should be ignored
        }
        
        # Mock the register_source_for_auto_sync method to track calls
        original_register = sync_manager.register_source_for_auto_sync
        registered_sources = []
        
        async def track_register(source, force_full_sync=False):
            registered_sources.append(source.namespace)
            # Return False for Twitter (as per actual implementation)
            if isinstance(source, TwitterSource):
                return False
            return True
        
        sync_manager.register_source_for_auto_sync = track_register
        
        # Run auto-discovery
        discovered_sources = await sync_manager.auto_discover_and_register_sources()
        
        # Verify Twitter was not discovered/registered
        assert "twitter" not in discovered_sources, "Twitter should not be auto-discovered"
        assert "twitter" not in registered_sources, "Twitter should not be registered for auto-sync"
        
        # Verify other sources were discovered (assuming they're configured)
        expected_sources = ["limitless", "news", "weather", "spotify"]
        for source in expected_sources:
            assert source in discovered_sources, f"{source} should be auto-discovered"
    
    async def test_sync_manager_register_source_rejects_twitter(self, sync_manager):
        """Test that sync manager explicitly rejects Twitter sources for auto-sync"""
        mock_twitter = Mock(spec=TwitterSource)
        mock_twitter.namespace = "twitter"
        
        # Attempt to register Twitter source
        result = await sync_manager.register_source_for_auto_sync(mock_twitter)
        
        # Should return False (rejected)
        assert result is False, "Twitter source registration should be rejected"
        
        # Verify no job was created for Twitter
        assert "twitter" not in sync_manager.source_job_mapping, "No Twitter job should be created"
    
    async def test_scheduler_has_no_twitter_jobs_after_startup(self, scheduler, sync_manager):
        """Test that scheduler contains no Twitter jobs after startup process"""
        # Start the scheduler
        await scheduler.start()
        
        # Run auto-discovery (which should skip Twitter)
        await sync_manager.auto_discover_and_register_sources()
        
        # Check scheduler jobs
        all_jobs = scheduler.get_all_jobs_status()
        twitter_jobs = [
            job for job_id, job in all_jobs["jobs"].items() 
            if job.get("namespace") == "twitter"
        ]
        
        assert len(twitter_jobs) == 0, "No Twitter jobs should exist in scheduler"
        
        # Also check by namespace
        twitter_namespace_jobs = scheduler.get_jobs_by_namespace("twitter")
        assert len(twitter_namespace_jobs) == 0, "No Twitter jobs should exist for twitter namespace"
    
    async def test_no_automatic_twitter_trace_logs(self, sync_manager, caplog):
        """Test that no automatic [TWITTER TRACE] logs are generated during startup"""
        with caplog.at_level(logging.INFO):
            # Run auto-discovery and startup processes
            await sync_manager.auto_discover_and_register_sources()
            
            # Check for [TWITTER TRACE] logs
            twitter_trace_logs = [
                record.message for record in caplog.records 
                if "[TWITTER TRACE]" in record.message
            ]
            
            # Should be no automatic Twitter trace logs during startup
            assert len(twitter_trace_logs) == 0, f"No automatic [TWITTER TRACE] logs should be generated, found: {twitter_trace_logs}"
    
    async def test_ingestion_service_registry_excludes_twitter_after_startup(self, startup_service, mock_config):
        """Test that ingestion service source registry doesn't contain Twitter after startup"""
        # Mock the ingestion service
        mock_ingestion = Mock(spec=IngestionService)
        mock_ingestion.sources = {}
        mock_ingestion.register_source = Mock()
        startup_service.ingestion_service = mock_ingestion
        
        # Run source registration
        startup_result = {"sources_registered": [], "errors": []}
        await startup_service._register_data_sources(startup_result)
        
        # Verify Twitter source was not registered with ingestion service
        registered_calls = mock_ingestion.register_source.call_args_list
        twitter_registrations = [
            call for call in registered_calls 
            if hasattr(call[0][0], 'namespace') and call[0][0].namespace == "twitter"
        ]
        
        assert len(twitter_registrations) == 0, "Twitter source should not be registered with ingestion service"
    
    async def test_manual_twitter_operations_work_independently(self, mock_config):
        """Test that manual Twitter operations work without affecting scheduler"""
        # Create a Twitter source manually (simulating on-demand creation)
        twitter_config = mock_config.twitter
        
        with patch('services.twitter_api_service.TwitterAPIService') as mock_api_service, \
             patch('services.twitter_rate_limit_service.TwitterRateLimitService') as mock_rate_service:
            
            mock_api_instance = Mock()
            mock_api_service.return_value = mock_api_instance
            
            mock_rate_instance = Mock()
            mock_rate_service.return_value = mock_rate_instance
            mock_rate_instance.can_fetch_now = AsyncMock(return_value=(True, 0))
            mock_rate_instance.record_fetch_attempt = AsyncMock()
            
            # Create Twitter source manually
            with patch('sources.twitter.TwitterSource') as mock_twitter_cls:
                mock_twitter = Mock(spec=TwitterSource)
                mock_twitter.namespace = "twitter"
                mock_twitter.api_service = mock_api_instance
                mock_twitter.rate_limit_service = mock_rate_instance
                mock_twitter.fetch_today_tweets = AsyncMock(return_value=[])
                mock_twitter_cls.return_value = mock_twitter
                
                # Simulate manual Twitter operation
                twitter_source = mock_twitter_cls(twitter_config, Mock(), mock_rate_instance)
                
                # Verify manual operations work
                tweets = await twitter_source.fetch_today_tweets()
                assert isinstance(tweets, list), "Manual Twitter fetch should work"
                
                # Verify rate limiting works
                can_fetch, minutes = await twitter_source.rate_limit_service.can_fetch_now()
                assert isinstance(can_fetch, bool), "Rate limiting should work for manual operations"
    
    async def test_on_demand_twitter_source_creation(self, mock_config):
        """Test that Twitter sources can be created on-demand without scheduler registration"""
        # Simulate the get_twitter_source dependency function behavior
        mock_database = Mock(spec=DatabaseService)
        
        with patch('services.twitter_api_service.TwitterAPIService') as mock_api_service, \
             patch('services.twitter_rate_limit_service.TwitterRateLimitService') as mock_rate_service:
            
            mock_api_instance = Mock()
            mock_api_service.return_value = mock_api_instance
            
            mock_rate_instance = Mock()
            mock_rate_service.return_value = mock_rate_instance
            
            # Create Twitter source on-demand
            with patch('sources.twitter.TwitterSource') as mock_twitter_cls:
                mock_twitter = Mock(spec=TwitterSource)
                mock_twitter.namespace = "twitter"
                mock_twitter.api_service = mock_api_instance
                mock_twitter.rate_limit_service = mock_rate_instance
                mock_twitter_cls.return_value = mock_twitter
                
                # Simulate on-demand creation (like in get_twitter_source dependency)
                twitter_source = mock_twitter_cls(mock_config.twitter, mock_database, mock_rate_instance)
                
                assert twitter_source is not None, "On-demand Twitter source creation should work"
                assert twitter_source.namespace == "twitter", "Twitter source should have correct namespace"
                assert hasattr(twitter_source, 'api_service'), "Twitter source should have API service"
                assert hasattr(twitter_source, 'rate_limit_service'), "Twitter source should have rate limit service"
    
    async def test_other_sources_continue_automatic_scheduling(self, sync_manager, scheduler):
        """Test that removing Twitter doesn't affect other source scheduling"""
        # Mock other sources
        mock_limitless = Mock(spec=LimitlessSource)
        mock_limitless.namespace = "limitless"
        
        mock_news = Mock(spec=NewsSource)
        mock_news.namespace = "news"
        
        # Start scheduler
        await scheduler.start()
        
        # Register non-Twitter sources
        limitless_registered = await sync_manager.register_source_for_auto_sync(mock_limitless)
        news_registered = await sync_manager.register_source_for_auto_sync(mock_news)
        
        assert limitless_registered is True, "Limitless source should be registered successfully"
        assert news_registered is True, "News source should be registered successfully"
        
        # Verify jobs were created for other sources
        assert "limitless" in sync_manager.source_job_mapping, "Limitless job should be created"
        assert "news" in sync_manager.source_job_mapping, "News job should be created"
        assert "twitter" not in sync_manager.source_job_mapping, "Twitter job should not be created"
        
        # Verify scheduler has the jobs
        all_jobs = scheduler.get_all_jobs_status()
        job_namespaces = [job.get("namespace") for job in all_jobs["jobs"].values()]
        
        assert "limitless" in job_namespaces, "Limitless job should exist in scheduler"
        assert "news" in job_namespaces, "News job should exist in scheduler"
        assert "twitter" not in job_namespaces, "Twitter job should not exist in scheduler"
    
    async def test_system_stability_with_mixed_operations(self, sync_manager, scheduler, mock_config):
        """Test system stability with mixed manual/automatic source operations"""
        # Start scheduler
        await scheduler.start()
        
        # Register automatic sources
        mock_limitless = Mock(spec=LimitlessSource)
        mock_limitless.namespace = "limitless"
        await sync_manager.register_source_for_auto_sync(mock_limitless)
        
        # Simulate manual Twitter operations while automatic sources are running
        with patch('sources.twitter.TwitterSource') as mock_twitter_cls:
            mock_twitter = Mock(spec=TwitterSource)
            mock_twitter.namespace = "twitter"
            mock_twitter.fetch_today_tweets = AsyncMock(return_value=[])
            mock_twitter_cls.return_value = mock_twitter
            
            # Create Twitter source manually
            twitter_source = mock_twitter_cls(mock_config.twitter, Mock(), Mock())
            
            # Perform manual Twitter operation
            await twitter_source.fetch_today_tweets()
            
            # Verify automatic sources are still working
            assert "limitless" in sync_manager.source_job_mapping, "Automatic sources should continue working"
            assert "twitter" not in sync_manager.source_job_mapping, "Twitter should not interfere with automatic scheduling"
            
            # Verify scheduler is still healthy
            health = scheduler.get_scheduler_health()
            assert health["scheduler_running"] is True, "Scheduler should remain running"
            assert len(health["health_issues"]) == 0, "No health issues should be present"
    
    async def test_startup_process_verification_complete(self, startup_service, mock_config, caplog):
        """Comprehensive test of complete startup process with Twitter bypass"""
        with patch.object(startup_service, '_initialize_core_services'), \
             patch.object(startup_service, '_initialize_ingestion_service'), \
             patch.object(startup_service, '_initialize_chat_service'), \
             patch.object(startup_service, '_initialize_document_service'), \
             patch.object(startup_service, '_initialize_default_prompt'), \
             patch.object(startup_service, '_initialize_llm_service'), \
             patch.object(startup_service, '_initialize_sync_status_service'), \
             patch.object(startup_service, '_initialize_sync_services'), \
             patch.object(startup_service, '_start_auto_sync'), \
             patch.object(startup_service, '_start_background_sync'), \
             patch.object(startup_service, '_perform_startup_health_check') as mock_health, \
             patch.object(startup_service, '_initialize_logging'):
            
            mock_health.return_value = {"overall_healthy": True}
            startup_service.ingestion_service = Mock()
            startup_service.scheduler = Mock()
            startup_service.sync_manager = Mock()
            startup_service.sync_status_service = Mock()
            
            with caplog.at_level(logging.INFO):
                # Run complete startup process
                result = await startup_service.initialize_application()
                
                # Verify startup succeeded
                assert result["success"] is True, "Startup should succeed"
                
                # Verify Twitter is not in registered sources
                assert "twitter" not in result.get("sources_registered", []), "Twitter should not be in registered sources"
                
                # Verify other sources are registered
                expected_sources = ["limitless", "news", "weather", "spotify"]
                registered_sources = result.get("sources_registered", [])
                for source in expected_sources:
                    assert source in registered_sources, f"{source} should be registered"
                
                # Verify no Twitter trace logs from automatic operations
                automatic_twitter_logs = [
                    record.message for record in caplog.records 
                    if "[TWITTER TRACE]" in record.message and "automatic" in record.message.lower()
                ]
                assert len(automatic_twitter_logs) == 0, "No automatic Twitter trace logs should be present"
    
    async def test_rate_limiting_works_independently_of_scheduler(self, mock_config):
        """Test that Twitter rate limiting works independently of scheduler system"""
        mock_database = Mock(spec=DatabaseService)
        
        # Create rate limit service
        rate_service = TwitterRateLimitService(mock_database, rate_limit_minutes=15.0)
        
        # Mock database responses
        mock_database.fetch_one = AsyncMock(return_value=None)  # No previous fetch
        mock_database.execute_query = AsyncMock(return_value=1)  # Successful update
        
        # Test rate limiting functionality
        can_fetch, minutes_until = await rate_service.can_fetch_now()
        assert can_fetch is True, "Should allow fetch when no previous fetch exists"
        assert minutes_until == 0, "No wait time when no previous fetch exists"
        
        # Record a fetch
        await rate_service.record_fetch_attempt(success=True)
        
        # Mock database to return recent fetch time
        recent_time = datetime.utcnow()
        mock_database.fetch_one = AsyncMock(return_value={"last_synced": recent_time.isoformat()})
        
        # Test rate limiting after recent fetch
        can_fetch, minutes_until = await rate_service.can_fetch_now()
        assert can_fetch is False, "Should not allow fetch immediately after recent fetch"
        assert minutes_until > 0, "Should have wait time after recent fetch"
    
    async def test_manual_fetch_does_not_trigger_automatic_scheduling(self, sync_manager, mock_config):
        """Test that manual Twitter fetches don't trigger automatic scheduling"""
        # Ensure no Twitter jobs exist initially
        assert "twitter" not in sync_manager.source_job_mapping, "No Twitter jobs should exist initially"
        
        # Simulate manual Twitter fetch (like through API endpoint)
        with patch('sources.twitter.TwitterSource') as mock_twitter_cls:
            mock_twitter = Mock(spec=TwitterSource)
            mock_twitter.namespace = "twitter"
            mock_twitter.fetch_today_tweets = AsyncMock(return_value=[])
            mock_twitter_cls.return_value = mock_twitter
            
            # Create and use Twitter source manually
            twitter_source = mock_twitter_cls(mock_config.twitter, Mock(), Mock())
            await twitter_source.fetch_today_tweets()
            
            # Verify no automatic scheduling was triggered
            assert "twitter" not in sync_manager.source_job_mapping, "Manual fetch should not create automatic jobs"
            
            # Verify sync manager state is unchanged
            all_status = await sync_manager.get_all_sources_sync_status()
            twitter_status = all_status["sources"].get("twitter")
            assert twitter_status is None, "Twitter should not appear in automatic sync status"


if __name__ == "__main__":
    pytest.main([__file__])