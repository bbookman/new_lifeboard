"""
Startup integration for Clean Up Crew system.

This module handles the initialization and integration of all Clean Up Crew components:
- Database migrations
- Service initialization 
- WebSocket setup
- Background job registration
- API route registration
"""

import logging
from typing import Any, Dict, List, Optional

from api.routes.websocket import setup_websocket_integration
from core.database import DatabaseService
from core.embeddings import EmbeddingService
from services.clean_up_crew_service import CleanUpCrewService
from services.scheduler import AsyncScheduler
from services.semantic_deduplication_service import SemanticDeduplicationService
from services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class CleanUpCrewBootstrap:
    """
    Bootstrap class for initializing the Clean Up Crew semantic deduplication system.
    
    Handles:
    - Service dependency injection and initialization
    - Database migration execution
    - Background job scheduling setup
    - WebSocket integration configuration
    - Error handling and graceful degradation
    """

    def __init__(self):
        self.services: Dict[str, Any] = {}
        self.is_initialized = False
        self.initialization_errors: List[str] = []

    async def initialize(self,
                        database_service: DatabaseService,
                        embedding_service: EmbeddingService,
                        scheduler_service: AsyncScheduler) -> bool:
        """
        Initialize all Clean Up Crew components.
        
        Args:
            database_service: Database service instance
            embedding_service: Embedding service instance  
            scheduler_service: Scheduler service instance
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        logger.info("Starting Clean Up Crew system initialization...")

        try:
            # Step 1: Run database migrations
            await self._run_migrations(database_service)

            # Step 2: Initialize semantic deduplication service
            semantic_service = await self._initialize_semantic_service(
                database_service, embedding_service,
            )

            # Step 3: Initialize WebSocket manager
            websocket_manager = await self._initialize_websocket_manager()

            # Step 4: Initialize Clean Up Crew service
            crew_service = await self._initialize_crew_service(
                database_service, scheduler_service, semantic_service, websocket_manager,
            )

            # Step 5: Set up WebSocket integration
            await self._setup_websocket_integration(crew_service, websocket_manager)

            # Step 6: Store service references
            self.services = {
                "database_service": database_service,
                "embedding_service": embedding_service,
                "scheduler_service": scheduler_service,
                "semantic_service": semantic_service,
                "websocket_manager": websocket_manager,
                "clean_up_crew_service": crew_service,
            }

            self.is_initialized = True
            logger.info("Clean Up Crew system initialization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Clean Up Crew initialization failed: {e}")
            self.initialization_errors.append(str(e))
            return False

    async def shutdown(self):
        """Shutdown all Clean Up Crew components gracefully"""
        logger.info("Shutting down Clean Up Crew system...")

        # Shutdown in reverse order of initialization
        if "clean_up_crew_service" in self.services:
            try:
                await self.services["clean_up_crew_service"].shutdown()
            except Exception as e:
                logger.error(f"Error shutting down crew service: {e}")

        if "websocket_manager" in self.services:
            try:
                await self.services["websocket_manager"].stop()
            except Exception as e:
                logger.error(f"Error shutting down WebSocket manager: {e}")

        self.services.clear()
        self.is_initialized = False
        logger.info("Clean Up Crew system shutdown complete")

    def get_service(self, service_name: str) -> Optional[Any]:
        """Get a service instance by name"""
        return self.services.get(service_name)

    def get_all_services(self) -> Dict[str, Any]:
        """Get all initialized services"""
        return self.services.copy()

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components"""
        health = {
            "initialized": self.is_initialized,
            "initialization_errors": self.initialization_errors,
            "services": {},
        }

        # Check each service health
        if "clean_up_crew_service" in self.services:
            crew_service = self.services["clean_up_crew_service"]
            health["services"]["clean_up_crew"] = {
                "initialized": crew_service.is_initialized,
                "background_job_registered": crew_service.background_job_id is not None,
                "active_processing": len(crew_service.active_day_processing),
            }

        if "websocket_manager" in self.services:
            websocket_manager = self.services["websocket_manager"]
            health["services"]["websocket"] = {
                "running": websocket_manager.is_running,
                "connections": len(websocket_manager.connections),
                "topics": len(websocket_manager.subscriptions),
            }

        if "scheduler_service" in self.services:
            scheduler = self.services["scheduler_service"]
            health["services"]["scheduler"] = {
                "running": scheduler.is_running,
                "total_jobs": len(scheduler.jobs),
                "running_jobs": len(scheduler.running_jobs),
            }

        return health

    async def _run_migrations(self, database_service: DatabaseService):
        """Run necessary database migrations"""
        logger.info("Running Clean Up Crew database migrations...")

        try:
            # Use the proper MigrationRunner to handle all migrations
            from core.migrations.runner import MigrationRunner

            migration_runner = MigrationRunner(database_service.db_path)
            result = migration_runner.run_migrations()

            if result["success"]:
                if result["applied_migrations"]:
                    logger.info(f"Successfully applied migrations: {result['applied_migrations']}")
                else:
                    logger.info("All migrations already applied")
            else:
                logger.error(f"Migration failed: {result['errors']}")
                raise RuntimeError(f"Migration failed: {'; '.join(result['errors'])}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

    async def _initialize_semantic_service(self,
                                         database_service: DatabaseService,
                                         embedding_service: EmbeddingService) -> SemanticDeduplicationService:
        """Initialize the semantic deduplication service"""
        logger.info("Initializing semantic deduplication service...")

        service = SemanticDeduplicationService(
            database_service=database_service,
            embedding_service=embedding_service,
        )

        logger.info("Semantic deduplication service initialized")
        return service

    async def _initialize_websocket_manager(self) -> WebSocketManager:
        """Initialize the WebSocket manager"""
        logger.info("Initializing WebSocket manager...")

        manager = WebSocketManager(heartbeat_interval=30)
        await manager.start()

        logger.info("WebSocket manager initialized and started")
        return manager

    async def _initialize_crew_service(self,
                                     database_service: DatabaseService,
                                     scheduler_service: AsyncScheduler,
                                     semantic_service: SemanticDeduplicationService,
                                     websocket_manager: WebSocketManager) -> CleanUpCrewService:
        """Initialize the Clean Up Crew service"""
        logger.info("Initializing Clean Up Crew service...")

        service = CleanUpCrewService(
            database_service=database_service,
            scheduler_service=scheduler_service,
            semantic_service=semantic_service,
            websocket_manager=websocket_manager,
        )

        await service.initialize()

        logger.info("Clean Up Crew service initialized")
        return service

    async def _setup_websocket_integration(self,
                                         crew_service: CleanUpCrewService,
                                         websocket_manager: WebSocketManager):
        """Set up integration between crew service and WebSocket manager"""
        logger.info("Setting up WebSocket integration...")

        await setup_websocket_integration(crew_service, websocket_manager)

        logger.info("WebSocket integration configured")


# Global bootstrap instance
_bootstrap_instance: Optional[CleanUpCrewBootstrap] = None


async def initialize_clean_up_crew(database_service: DatabaseService,
                                 embedding_service: EmbeddingService,
                                 scheduler_service: AsyncScheduler) -> CleanUpCrewBootstrap:
    """
    Initialize the Clean Up Crew system.
    
    This should be called during application startup after core services are initialized.
    """
    global _bootstrap_instance

    if _bootstrap_instance and _bootstrap_instance.is_initialized:
        logger.warning("Clean Up Crew already initialized")
        return _bootstrap_instance

    _bootstrap_instance = CleanUpCrewBootstrap()
    success = await _bootstrap_instance.initialize(
        database_service=database_service,
        embedding_service=embedding_service,
        scheduler_service=scheduler_service,
    )

    if not success:
        logger.error("Clean Up Crew initialization failed")
        raise RuntimeError("Clean Up Crew system initialization failed")

    return _bootstrap_instance


async def shutdown_clean_up_crew():
    """Shutdown the Clean Up Crew system"""
    global _bootstrap_instance

    if _bootstrap_instance:
        await _bootstrap_instance.shutdown()
        _bootstrap_instance = None


def get_clean_up_crew_bootstrap() -> Optional[CleanUpCrewBootstrap]:
    """Get the Clean Up Crew bootstrap instance"""
    return _bootstrap_instance


def get_clean_up_crew_service() -> Optional[CleanUpCrewService]:
    """Get the Clean Up Crew service instance"""
    if _bootstrap_instance:
        return _bootstrap_instance.get_service("clean_up_crew_service")
    return None


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Get the WebSocket manager instance"""
    if _bootstrap_instance:
        return _bootstrap_instance.get_service("websocket_manager")
    return None
