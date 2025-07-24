import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from services.scheduler import AsyncScheduler
from services.ingestion import IngestionService
from services.sync_manager_service import SyncManagerService
from services.chat_service import ChatService
from sources.limitless import LimitlessSource
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
            
            # 5.5. Initialize embedding processing scheduler
            await self._initialize_embedding_scheduler(startup_result)
            
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
            if self.config.limitless.api_key:
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
                    logger.info(f"Performing startup sync for {namespace}")
                    result = await self.sync_manager.trigger_immediate_sync(namespace, force_full_sync=False)
                    startup_sync_results[namespace] = result.to_dict()
                    logger.info(f"Startup sync completed for {namespace}: {result.items_processed} processed")
                    
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
    
    async def _initialize_embedding_scheduler(self, startup_result: Dict[str, Any]):
        """Initialize embedding processing scheduler"""
        try:
            logger.info("Initializing embedding processing scheduler...")
            
            # Check if embedding processing is enabled
            if not self.config.embedding_processing.enabled:
                logger.info("Embedding processing scheduler disabled in config")
                startup_result["embedding_scheduler_enabled"] = False
                return
            
            # Ensure we have required services
            if not self.scheduler:
                logger.warning("No scheduler available - embedding processing will only be available via API")
                startup_result["embedding_scheduler_enabled"] = False
                return
                
            if not self.ingestion_service:
                logger.warning("No ingestion service available - cannot schedule embedding processing")
                startup_result["embedding_scheduler_enabled"] = False
                return
            
            # Create embedding processing job
            async def embedding_processing_job():
                """Background job for processing pending embeddings"""
                try:
                    logger.info("🔄 EMBEDDING SCHEDULER: Starting scheduled embedding processing")
                    
                    result = await self.ingestion_service.process_pending_embeddings(
                        batch_size=self.config.embedding_processing.batch_size
                    )
                    
                    logger.info(f"🔄 EMBEDDING SCHEDULER: Completed - {result.get('embeddings_processed', 0)} embeddings generated")
                    return result
                    
                except Exception as e:
                    logger.error(f"❌ EMBEDDING SCHEDULER: Failed with error: {e}")
                    return {"success": False, "error": str(e)}
            
            # Register the job with the scheduler
            interval_seconds = self.config.embedding_processing.interval_hours * 3600
            embedding_job_id = self.scheduler.add_job(
                name="embedding_processing",
                namespace="system",
                func=embedding_processing_job,
                interval_seconds=interval_seconds
            )
            
            logger.info(f"✅ EMBEDDING SCHEDULER: Registered job with {self.config.embedding_processing.interval_hours}h interval (ID: {embedding_job_id})")
            
            # Optionally run startup processing for the current backlog
            if self.config.embedding_processing.startup_processing:
                logger.info(f"🚀 EMBEDDING SCHEDULER: Running startup processing for up to {self.config.embedding_processing.startup_limit} items")
                try:
                    startup_result_embed = await self.ingestion_service.process_pending_embeddings(
                        batch_size=min(self.config.embedding_processing.startup_limit, self.config.embedding_processing.batch_size)
                    )
                    logger.info(f"🚀 EMBEDDING SCHEDULER: Startup processing completed - {startup_result_embed.get('embeddings_processed', 0)} embeddings generated")
                except Exception as e:
                    logger.warning(f"⚠️ EMBEDDING SCHEDULER: Startup processing failed: {e}")
            
            startup_result["embedding_scheduler_enabled"] = True
            startup_result["embedding_job_id"] = embedding_job_id
            startup_result["services_initialized"].append("embedding_scheduler")
            logger.info("Embedding processing scheduler initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize embedding scheduler: {str(e)}"
            logger.error(error_msg)
            startup_result["errors"].append(error_msg)
            startup_result["embedding_scheduler_enabled"] = False
    
    async def shutdown_application(self):
        """Gracefully shutdown all services"""
        logger.info("Starting application shutdown...")
        
        try:
            # Stop sync manager and scheduler
            if self.sync_manager:
                await self.sync_manager.stop_auto_sync()
            
            # Close chat service
            if self.chat_service:
                await self.chat_service.close()
            
            # Close other services
            if self.vector_store:
                self.vector_store.cleanup()
            
            logger.info("Application shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
    
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
    startup_service = StartupService(config)
    set_startup_service(startup_service)
    
    return await startup_service.initialize_application(enable_auto_sync)


async def shutdown_application():
    """Shutdown the application"""
    startup_service = get_startup_service()
    if startup_service:
        await startup_service.shutdown_application()