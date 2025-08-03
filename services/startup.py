import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from services.scheduler import AsyncScheduler
from services.ingestion import IngestionService
from services.sync_manager_service import SyncManagerService
from services.chat_service import ChatService
from sources.limitless import LimitlessSource
from sources.news import NewsSource
from sources.weather import WeatherSource
from sources.twitter import TwitterSource
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from core.logging_config import setup_application_logging
from config.models import AppConfig

logger = logging.getLogger(__name__)


class StartupService:
    """Service responsible for application initialization and startup orchestration"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.database: Optional[DatabaseService] = None
        self.vector_store: Optional[VectorStoreService] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self.ingestion_service: Optional[IngestionService] = None
        self.scheduler: Optional[AsyncScheduler] = None
        self.sync_manager: Optional[SyncManagerService] = None
        self.chat_service: Optional[ChatService] = None
        self.startup_complete = False
        self.logging_setup_result: Optional[Dict[str, Any]] = None
        
    async def initialize_application(self, enable_auto_sync: Optional[bool] = None) -> Dict[str, Any]:
        """Initialize all application services and components"""
        # Use config setting if not explicitly overridden
        if enable_auto_sync is None:
            enable_auto_sync = self.config.auto_sync.enabled
            
        startup_result = {
            "success": False,
            "services_initialized": [],
            "sources_registered": [],
            "auto_sync_enabled": enable_auto_sync,
            "auto_register_sources": self.config.auto_sync.auto_register_sources,
            "errors": [],
            "startup_time": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # 0. Initialize centralized logging first (before any other logging)
            await self._initialize_logging(startup_result)
            
            logger.info("Starting application initialization...")
            
            # 1. Initialize core services
            await self._initialize_core_services(startup_result)
            
            # 2. Initialize ingestion service
            await self._initialize_ingestion_service(startup_result)
            
            # 2.5. Initialize chat service (Phase 7)
            await self._initialize_chat_service(startup_result)
            
            # 3. Register data sources (if auto-register is enabled)
            if self.config.auto_sync.auto_register_sources:
                await self._register_data_sources(startup_result)
            
            # 4. Initialize scheduler and sync management (if enabled)
            if enable_auto_sync:
                await self._initialize_sync_services(startup_result)
                await self._start_auto_sync(startup_result)
                
                # 5. Perform startup sync if enabled
                if self.config.auto_sync.startup_sync_enabled:
                    await self._perform_startup_sync(startup_result)
            
            # 6. Perform startup health check
            health_status = await self._perform_startup_health_check()
            startup_result["health_check"] = health_status
            
            self.startup_complete = True
            startup_result["success"] = True
            
            logger.info(f"Application initialization completed successfully. "
                       f"Services: {len(startup_result['services_initialized'])}, "
                       f"Sources: {len(startup_result['sources_registered'])}")
            
        except Exception as e:
            error_msg = f"Application initialization failed: {str(e)}"
            logger.error(error_msg)
            startup_result["errors"].append(error_msg)
            startup_result["success"] = False
        
        return startup_result
    
    async def _initialize_logging(self, startup_result: Dict[str, Any]):
        """Initialize centralized logging system"""
        try:
            logger.info("Initializing centralized logging system...")
            
            # Setup application logging using the configuration parameters
            self.logging_setup_result = setup_application_logging(
                log_level=self.config.logging.level,
                log_file_path=self.config.logging.file_path,
                max_file_size=self.config.logging.max_file_size,
                backup_count=self.config.logging.backup_count,
                console_logging=self.config.logging.console_logging,
                include_correlation_ids=self.config.logging.include_correlation_ids
            )
            
            if self.logging_setup_result.get("success", False):
                startup_result["services_initialized"].append("logging")
                logger.info("Centralized logging system initialized successfully")
            else:
                # Log setup failed but don't fail the entire startup
                error_msg = f"Logging setup failed: {self.logging_setup_result.get('error', 'Unknown error')}"
                logger.warning(error_msg)
                startup_result["errors"].append(error_msg)
                
        except Exception as e:
            # Fallback logging setup failed - continue with basic logging
            error_msg = f"Failed to initialize logging system: {str(e)}"
            logger.error(error_msg)
            startup_result["errors"].append(error_msg)
            
            # Store failed result for status reporting
            self.logging_setup_result = {
                "success": False,
                "error": str(e),
                "fallback_logging": True
            }

    async def _initialize_core_services(self, startup_result: Dict[str, Any]):
        """Initialize core services (database, vector store, embeddings)"""
        try:
            # Database service
            logger.info("Initializing database service...")
            self.database = DatabaseService(self.config.database.path)
            startup_result["services_initialized"].append("database")
            
            # Embedding service
            logger.info("Initializing embedding service...")
            self.embedding_service = EmbeddingService(self.config.embeddings)
            startup_result["services_initialized"].append("embeddings")
            
            # Vector store service
            logger.info("Initializing vector store service...")
            self.vector_store = VectorStoreService(self.config.vector_store)
            startup_result["services_initialized"].append("vector_store")
            
            logger.info("Core services initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize core services: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def _initialize_ingestion_service(self, startup_result: Dict[str, Any]):
        """Initialize the ingestion service"""
        try:
            logger.info("Initializing ingestion service...")
            
            self.ingestion_service = IngestionService(
                database=self.database,
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
                config=self.config
            )
            
            startup_result["services_initialized"].append("ingestion")
            logger.info("Ingestion service initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize ingestion service: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def _initialize_chat_service(self, startup_result: Dict[str, Any]):
        """Initialize the chat service (Phase 7)"""
        try:
            logger.info("Initializing chat service...")
            
            self.chat_service = ChatService(
                config=self.config,
                database=self.database,
                vector_store=self.vector_store,
                embeddings=self.embedding_service
            )
            
            # Initialize the chat service (sets up LLM provider)
            await self.chat_service.initialize()
            
            startup_result["services_initialized"].append("chat")
            logger.info("Chat service initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize chat service: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def _register_data_sources(self, startup_result: Dict[str, Any]):
        """Register available data sources"""
        try:
            logger.info("Registering data sources...")
            
            # Register Limitless source if API key is available
            if self.config.limitless.is_api_key_configured():
                try:
                    logger.info("Registering Limitless source...")
                    limitless_source = LimitlessSource(self.config.limitless)
                    self.ingestion_service.register_source(limitless_source)
                    startup_result["sources_registered"].append("limitless")
                    logger.info("Limitless source registered successfully")
                    
                except Exception as e:
                    error_msg = f"Failed to register Limitless source: {str(e)}"
                    logger.warning(error_msg)
                    startup_result["errors"].append(error_msg)
            else:
                logger.info("Limitless API key not configured, skipping source registration")
            
            # Register News source if fully configured (enabled, API key, and endpoint)
            if self.config.news.is_fully_configured():
                try:
                    logger.info("Registering News source...")
                    news_source = NewsSource(self.config.news, self.database)
                    self.ingestion_service.register_source(news_source)
                    startup_result["sources_registered"].append("news")
                    logger.info("News source registered successfully")
                    
                except Exception as e:
                    error_msg = f"Failed to register News source: {str(e)}"
                    logger.warning(error_msg)
                    startup_result["errors"].append(error_msg)
            else:
                if not self.config.news.enabled:
                    logger.info("News service disabled in configuration, skipping source registration")
                elif not self.config.news.is_api_key_configured():
                    logger.info("News API key not configured, skipping source registration")
                elif not self.config.news.is_endpoint_configured():
                    logger.info("News endpoint not configured, skipping source registration")
                else:
                    logger.info("News source not fully configured, skipping source registration")
            
            # Register Twitter source if enabled and path is provided
            if self.config.twitter.is_configured():
                try:
                    logger.info("Registering Twitter source...")
                    twitter_source = TwitterSource(
                        self.config.twitter,
                        self.database,
                        self.ingestion_service
                    )
                    self.ingestion_service.register_source(twitter_source)
                    startup_result["sources_registered"].append("twitter")
                    logger.info("Twitter source registered successfully")
                except Exception as e:
                    error_msg = f"Failed to register Twitter source: {str(e)}"
                    logger.warning(error_msg)
                    startup_result["errors"].append(error_msg)
            else:
                logger.info("Twitter source not configured, skipping source registration")

            # Register Weather source if fully configured (enabled, API key, and endpoint)
            if self.config.weather.is_fully_configured():
                try:
                    logger.info("Registering Weather source...")
                    weather_source = WeatherSource(self.config.weather, self.database)
                    self.ingestion_service.register_source(weather_source)
                    startup_result["sources_registered"].append("weather")
                    logger.info("Weather source registered successfully")
                except Exception as e:
                    error_msg = f"Failed to register Weather source: {str(e)}"
                    logger.error(error_msg)
                    startup_result["errors"].append(error_msg)
            else:
                if not self.config.weather.enabled:
                    logger.info("Weather service disabled in configuration, skipping source registration")
                elif not self.config.weather.is_api_key_configured():
                    logger.info("Weather API key not configured, skipping source registration")
                elif not self.config.weather.is_endpoint_configured():
                    logger.info("Weather endpoint not configured, skipping source registration")
                else:
                    logger.info("Weather source not fully configured, skipping source registration")

            # Future: Add other source registrations here
            # if self.config.notion.api_key:
            #     notion_source = NotionSource(self.config.notion)
            #     self.ingestion_service.register_source(notion_source)
            #     startup_result["sources_registered"].append("notion")
            
            logger.info(f"Data source registration completed. "
                       f"Registered: {startup_result['sources_registered']}")
            
        except Exception as e:
            error_msg = f"Failed to register data sources: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def _initialize_sync_services(self, startup_result: Dict[str, Any]):
        """Initialize scheduler and sync management services"""
        try:
            logger.info("Initializing sync services...")
            
            # Initialize scheduler
            self.scheduler = AsyncScheduler(
                check_interval_seconds=self.config.scheduler.check_interval_seconds,
                max_concurrent_jobs=self.config.scheduler.max_concurrent_jobs
            )
            
            # Initialize sync manager
            self.sync_manager = SyncManagerService(
                scheduler=self.scheduler,
                ingestion_service=self.ingestion_service,
                config=self.config
            )
            
            startup_result["services_initialized"].extend(["scheduler", "sync_manager"])
            logger.info("Sync services initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize sync services: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def _start_auto_sync(self, startup_result: Dict[str, Any]):
        """Start automatic synchronization"""
        try:
            logger.info("Starting automatic synchronization...")
            
            success = await self.sync_manager.start_auto_sync()
            
            if success:
                startup_result["auto_sync_started"] = True
                logger.info("Automatic synchronization started successfully")
            else:
                startup_result["auto_sync_started"] = False
                logger.warning("Automatic synchronization could not be started (no sources available)")
            
        except Exception as e:
            error_msg = f"Failed to start automatic synchronization: {str(e)}"
            logger.error(error_msg)
            startup_result["errors"].append(error_msg)
            startup_result["auto_sync_started"] = False
    
    async def _perform_startup_sync(self, startup_result: Dict[str, Any]):
        """Perform initial sync on startup if configured"""
        try:
            logger.info(f"Waiting {self.config.auto_sync.startup_sync_delay_seconds}s before startup sync...")
            await asyncio.sleep(self.config.auto_sync.startup_sync_delay_seconds)
            
            logger.info("Starting startup sync...")
            
            startup_sync_results = {}
            for namespace in startup_result.get("sources_registered", []):
                try:
                    # Check if this source should be synced based on time interval
                    should_sync = await self.sync_manager.should_sync_on_startup(namespace)
                    
                    if should_sync:
                        logger.info(f"Performing startup sync for {namespace}")
                        result = await self.sync_manager.trigger_immediate_sync(namespace, force_full_sync=False)
                        startup_sync_results[namespace] = result.to_dict()
                        logger.info(f"Startup sync completed for {namespace}: {result.items_processed} processed")
                    else:
                        logger.info(f"Skipping startup sync for {namespace} - not due for sync yet")
                        startup_sync_results[namespace] = {"skipped": True, "reason": "Not due for sync"}
                    
                except Exception as e:
                    error_msg = f"Startup sync failed for {namespace}: {str(e)}"
                    logger.error(error_msg)
                    startup_sync_results[namespace] = {"error": error_msg}
            
            startup_result["startup_sync_results"] = startup_sync_results
            logger.info("Startup sync completed for all sources")
            
        except Exception as e:
            error_msg = f"Startup sync failed: {str(e)}"
            logger.error(error_msg)
            startup_result["errors"].append(error_msg)
    
    async def _perform_startup_health_check(self) -> Dict[str, Any]:
        """Perform health check after startup"""
        health_status = {
            "database_healthy": False,
            "vector_store_healthy": False,
            "embedding_service_healthy": False,
            "ingestion_service_healthy": False,
            "scheduler_healthy": False,
            "sync_manager_healthy": False,
            "overall_healthy": False
        }
        
        try:
            # Check database
            if self.database:
                db_stats = self.database.get_database_stats()
                health_status["database_healthy"] = db_stats is not None
            
            # Check vector store
            if self.vector_store:
                vs_stats = self.vector_store.get_stats()
                health_status["vector_store_healthy"] = vs_stats is not None
            
            # Check embedding service
            if self.embedding_service:
                # Simple health check - try to embed a test string
                try:
                    test_embeddings = await self.embedding_service.embed_texts(["test"])
                    health_status["embedding_service_healthy"] = len(test_embeddings) > 0
                except:
                    health_status["embedding_service_healthy"] = False
            
            # Check ingestion service
            if self.ingestion_service:
                ingestion_status = self.ingestion_service.get_ingestion_status()
                health_status["ingestion_service_healthy"] = ingestion_status is not None
            
            # Check scheduler
            if self.scheduler:
                health_status["scheduler_healthy"] = self.scheduler.is_running
            
            # Check sync manager
            if self.sync_manager:
                try:
                    sync_health = await self.sync_manager.health_check()
                    health_status["sync_manager_healthy"] = sync_health.get("healthy", False)
                    health_status["sync_health_details"] = sync_health
                except:
                    health_status["sync_manager_healthy"] = False
            
            # Overall health
            core_services_healthy = all([
                health_status["database_healthy"],
                health_status["vector_store_healthy"],
                health_status["embedding_service_healthy"],
                health_status["ingestion_service_healthy"]
            ])
            
            # Sync services are optional
            sync_services_healthy = True
            if self.scheduler:
                sync_services_healthy = health_status["scheduler_healthy"]
            if self.sync_manager:
                sync_services_healthy = sync_services_healthy and health_status["sync_manager_healthy"]
            
            health_status["overall_healthy"] = core_services_healthy and sync_services_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["health_check_error"] = str(e)
        
        return health_status
    
    async def shutdown_application(self):
        """Gracefully shutdown all services with timeout protection"""
        logger.info("SHUTDOWN_SERVICE: *** Starting application shutdown ***")
        
        shutdown_tasks = []
        shutdown_errors = []
        
        try:
            # Stop sync manager and scheduler first (most critical)
            if self.sync_manager:
                logger.info("SHUTDOWN_SERVICE: Stopping sync manager...")
                try:
                    await asyncio.wait_for(self.sync_manager.stop_auto_sync(), timeout=10.0)
                    logger.info("SHUTDOWN_SERVICE: Sync manager stopped successfully")
                except asyncio.TimeoutError:
                    logger.warning("SHUTDOWN_SERVICE: Sync manager shutdown timeout - forcing stop")
                    shutdown_errors.append("Sync manager shutdown timeout")
                except Exception as e:
                    logger.error(f"SHUTDOWN_SERVICE: Error stopping sync manager: {e}")
                    shutdown_errors.append(f"Sync manager error: {e}")
            else:
                logger.info("SHUTDOWN_SERVICE: No sync manager to stop")
            
            # Stop scheduler if it exists
            if self.scheduler:
                logger.info("SHUTDOWN_SERVICE: Stopping scheduler...")
                try:
                    await asyncio.wait_for(self.scheduler.stop(), timeout=5.0)
                    logger.info("SHUTDOWN_SERVICE: Scheduler stopped successfully")
                except asyncio.TimeoutError:
                    logger.warning("SHUTDOWN_SERVICE: Scheduler shutdown timeout")
                    shutdown_errors.append("Scheduler shutdown timeout")
                except Exception as e:
                    logger.error(f"SHUTDOWN_SERVICE: Error stopping scheduler: {e}")
                    shutdown_errors.append(f"Scheduler error: {e}")
            
            # Close chat service
            if self.chat_service:
                logger.info("SHUTDOWN_SERVICE: Closing chat service...")
                try:
                    await asyncio.wait_for(self.chat_service.close(), timeout=5.0)
                    logger.info("SHUTDOWN_SERVICE: Chat service closed successfully")
                except asyncio.TimeoutError:
                    logger.warning("SHUTDOWN_SERVICE: Chat service shutdown timeout")
                    shutdown_errors.append("Chat service shutdown timeout")
                except Exception as e:
                    logger.error(f"SHUTDOWN_SERVICE: Error closing chat service: {e}")
                    shutdown_errors.append(f"Chat service error: {e}")
            else:
                logger.info("SHUTDOWN_SERVICE: No chat service to close")
            
            # Database cleanup (uses context managers, no explicit cleanup needed)
            if self.database:
                logger.info("SHUTDOWN_SERVICE: Database uses context managers - no explicit cleanup needed")
            else:
                logger.info("SHUTDOWN_SERVICE: No database service to cleanup")
            
            # Clean up vector store
            if self.vector_store:
                logger.info("SHUTDOWN_SERVICE: Cleaning up vector store...")
                try:
                    self.vector_store.cleanup()
                    logger.info("SHUTDOWN_SERVICE: Vector store cleaned up")
                except Exception as e:
                    logger.error(f"SHUTDOWN_SERVICE: Error cleaning vector store: {e}")
                    shutdown_errors.append(f"Vector store error: {e}")
            else:
                logger.info("SHUTDOWN_SERVICE: No vector store to cleanup")
            
            # Clean up embedding service if needed
            if self.embedding_service:
                logger.info("SHUTDOWN_SERVICE: Cleaning up embedding service...")
                try:
                    # Most embedding services don't need explicit cleanup, but check if method exists
                    if hasattr(self.embedding_service, 'cleanup'):
                        self.embedding_service.cleanup()
                    logger.info("SHUTDOWN_SERVICE: Embedding service cleaned up")
                except Exception as e:
                    logger.error(f"SHUTDOWN_SERVICE: Error cleaning embedding service: {e}")
                    shutdown_errors.append(f"Embedding service error: {e}")
            
            # Final cleanup
            self.startup_complete = False
            
            if shutdown_errors:
                logger.warning(f"SHUTDOWN_SERVICE: Completed with {len(shutdown_errors)} errors: {shutdown_errors}")
            else:
                logger.info("SHUTDOWN_SERVICE: *** Application shutdown completed successfully ***")
            
        except Exception as e:
            logger.error(f"SHUTDOWN_SERVICE: Critical error during application shutdown: {e}")
            logger.exception("SHUTDOWN_SERVICE: Full shutdown exception details:")
            shutdown_errors.append(f"Critical shutdown error: {e}")
        
        finally:
            # Log final status regardless of errors
            logger.info(f"SHUTDOWN_SERVICE: Shutdown process complete. Errors: {len(shutdown_errors)}")
            if shutdown_errors:
                for i, error in enumerate(shutdown_errors, 1):
                    logger.error(f"SHUTDOWN_SERVICE: Error {i}: {error}")
    
    def get_application_status(self) -> Dict[str, Any]:
        """Get current application status"""
        status = {
            "startup_complete": self.startup_complete,
            "services": {
                "logging": self.logging_setup_result is not None and self.logging_setup_result.get("success", False),
                "database": self.database is not None,
                "vector_store": self.vector_store is not None,
                "embedding_service": self.embedding_service is not None,
                "ingestion_service": self.ingestion_service is not None,
                "chat_service": self.chat_service is not None,
                "scheduler": self.scheduler is not None,
                "sync_manager": self.sync_manager is not None
            }
        }
        
        # Add logging setup details if available
        if self.logging_setup_result:
            status["logging_details"] = self.logging_setup_result
        
        # Add detailed status if services are available
        if self.ingestion_service:
            status["ingestion_status"] = self.ingestion_service.get_ingestion_status()
        
        if self.sync_manager:
            status["sync_status"] = self.sync_manager.get_all_sources_sync_status()
        
        return status
    
    async def trigger_immediate_sync(self, namespace: str, force_full_sync: bool = False):
        """Trigger immediate sync for a namespace"""
        if not self.sync_manager:
            raise Exception("Sync manager not initialized")
        
        return await self.sync_manager.trigger_immediate_sync(namespace, force_full_sync)
    
    async def process_pending_embeddings(self, batch_size: int = 32):
        """Process any pending embeddings"""
        if not self.ingestion_service:
            raise Exception("Ingestion service not initialized")
        
        return await self.ingestion_service.process_pending_embeddings(batch_size)


# Global startup service instance
_startup_service: Optional[StartupService] = None


def get_startup_service() -> Optional[StartupService]:
    """Get the global startup service instance"""
    return _startup_service


def set_startup_service(startup_service: StartupService):
    """Set the global startup service instance"""
    global _startup_service
    _startup_service = startup_service


async def initialize_application(config: AppConfig, enable_auto_sync: bool = True) -> Dict[str, Any]:
    """Initialize the application with the given configuration"""
    import os
    
    logger.info("STARTUP: *** BEGINNING APPLICATION INITIALIZATION ***")
    
    # Check for test mode environment variable
    test_mode = os.getenv("LIFEBOARD_TEST_MODE", "false").lower() == "true"
    disable_sync = os.getenv("LIFEBOARD_DISABLE_SYNC", "false").lower() == "true"
    
    if test_mode or disable_sync:
        logger.warning("STARTUP: *** TEST MODE ENABLED - DISABLING AUTO-SYNC ***")
        enable_auto_sync = False
    
    logger.info(f"STARTUP: enable_auto_sync = {enable_auto_sync}")
    logger.info(f"STARTUP: test_mode = {test_mode}")
    logger.info(f"STARTUP: disable_sync = {disable_sync}")
    
    startup_service = StartupService(config)
    set_startup_service(startup_service)
    
    logger.info("STARTUP: Starting service initialization...")
    result = await startup_service.initialize_application(enable_auto_sync)
    
    logger.info(f"STARTUP: Initialization completed with result: {result.get('success', False)}")
    logger.info("STARTUP: *** APPLICATION INITIALIZATION FINISHED ***")
    
    return result


async def shutdown_application():
    """Shutdown the application with timeout protection"""
    logger.info("SHUTDOWN: *** SHUTDOWN APPLICATION CALLED ***")
    
    startup_service = get_startup_service()
    if startup_service:
        logger.info("SHUTDOWN: Startup service found, proceeding with shutdown...")
        try:
            # Give the shutdown process up to 30 seconds to complete
            await asyncio.wait_for(startup_service.shutdown_application(), timeout=30.0)
            logger.info("SHUTDOWN: *** SHUTDOWN APPLICATION COMPLETED SUCCESSFULLY ***")
        except asyncio.CancelledError:
            logger.info("SHUTDOWN: Shutdown cancelled by user (CTRL+C). Exiting gracefully.")
        except asyncio.TimeoutError:
            logger.error("SHUTDOWN: Application shutdown timeout after 30 seconds")
            logger.error("SHUTDOWN: Some resources may not have been properly released")
        except Exception as e:
            logger.error(f"SHUTDOWN: Error during application shutdown: {e}")
            logger.exception("SHUTDOWN: Full shutdown exception details:")
    else:
        logger.warning("SHUTDOWN: No startup service found to shutdown")
    
    # Clear the global startup service reference
    global _startup_service
    _startup_service = None
    logger.info("SHUTDOWN: Global startup service reference cleared")