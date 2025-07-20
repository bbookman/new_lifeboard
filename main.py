#!/usr/bin/env python3
"""
Lifeboard - Interactive Reflection Space and Planning Assistant

Main application entry point for the KISS multi-source memory chat system.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from config.factory import create_config, ConfigurationFactory
from config.settings import SettingsManager
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from sources.registry import SourceRegistry, SourceFactory
from services.namespace_prediction import NamespacePredictionService, MockNamespacePredictionService
from services.search import SearchService
from services.ingestion import IngestionService


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('lifeboard.log')
    ]
)

logger = logging.getLogger(__name__)


class LifeboardApplication:
    """Main Lifeboard application"""
    
    def __init__(self):
        self.config = None
        self.db = None
        self.vector_store = None
        self.embeddings = None
        self.source_registry = None
        self.settings_manager = None
        self.prediction_service = None
        self.search_service = None
        self.ingestion_service = None
        self.running = False
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize all application components"""
        logger.info("Initializing Lifeboard application...")
        
        try:
            # Load configuration
            logger.info("Loading configuration...")
            self.config = create_config()
            
            # Validate configuration
            issues = ConfigurationFactory.validate_config(self.config)
            if issues:
                logger.warning("Configuration issues found:")
                for issue in issues:
                    logger.warning(f"  - {issue}")
            
            # Initialize core services
            logger.info("Initializing database service...")
            self.db = DatabaseService(self.config.database.path)
            
            logger.info("Initializing settings manager...")
            self.settings_manager = SettingsManager(self.db)
            
            logger.info("Initializing vector store...")
            self.vector_store = VectorStoreService(self.config.vector_store)
            
            logger.info("Initializing embedding service...")
            self.embeddings = EmbeddingService(self.config.embeddings)
            await self.embeddings.warmup()
            
            # Initialize source registry
            logger.info("Initializing source registry...")
            self.source_registry = SourceRegistry()
            
            # Set up initial sources
            ConfigurationFactory.setup_initial_sources(self.config, self.settings_manager)
            
            # Load sources from configuration
            if self.config.sources:
                loaded_count, failed_count = self.source_registry.load_sources_from_configs(self.config.sources)
                logger.info(f"Loaded {loaded_count} sources, {failed_count} failed")
            
            # Initialize namespace prediction service
            logger.info("Initializing namespace prediction service...")
            try:
                self.prediction_service = NamespacePredictionService(
                    self.config.llm,
                    self.source_registry.get_namespaces()
                )
                # Test the prediction service
                test_result = await self.prediction_service.test_prediction()
                if not test_result['success']:
                    logger.warning("LLM prediction service test failed, using mock service")
                    self.prediction_service = MockNamespacePredictionService(
                        self.source_registry.get_namespaces()
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize LLM prediction service: {e}")
                logger.info("Using mock namespace prediction service")
                self.prediction_service = MockNamespacePredictionService(
                    self.source_registry.get_namespaces()
                )
            
            # Initialize search service
            logger.info("Initializing search service...")
            self.search_service = SearchService(
                self.db,
                self.vector_store,
                self.embeddings,
                self.prediction_service,
                self.config.search
            )
            
            # Initialize ingestion service
            logger.info("Initializing ingestion service...")
            self.ingestion_service = IngestionService(
                self.db,
                self.vector_store,
                self.embeddings,
                self.source_registry,
                self.config.scheduler
            )
            
            logger.info("Lifeboard application initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise
    
    async def start(self):
        """Start the application"""
        if not self.config:
            await self.initialize()
        
        logger.info("Starting Lifeboard application...")
        self.running = True
        
        try:
            # Initial data sync if sources are configured
            if self.source_registry.get_active_sources():
                logger.info("Performing initial data sync...")
                sync_results = await self.ingestion_service.ingest_from_all_sources()
                
                total_items = sum(r.items_added + r.items_updated for r in sync_results.values())
                logger.info(f"Initial sync completed: {total_items} items ingested")
                
                # Process embeddings for new items
                if total_items > 0:
                    logger.info("Processing embeddings for new items...")
                    embedding_result = await self.ingestion_service.process_pending_embeddings()
                    logger.info(f"Embedding processing completed: {embedding_result['succeeded']} succeeded")
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Print startup summary
            await self._print_startup_summary()
            
            return self
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            self.running = False
            raise
    
    async def _start_background_tasks(self):
        """Start background processing tasks"""
        logger.info("Starting background tasks...")
        
        # Start embedding processing task
        asyncio.create_task(self._embedding_processor_task())
        
        # Start periodic sync task
        asyncio.create_task(self._periodic_sync_task())
        
        logger.info("Background tasks started")
    
    async def _embedding_processor_task(self):
        """Background task to process pending embeddings"""
        while self.running:
            try:
                await asyncio.sleep(self.config.scheduler.embedding_interval_seconds)
                
                if not self.running:
                    break
                
                # Process pending embeddings
                result = await self.ingestion_service.process_pending_embeddings()
                if result['processed'] > 0:
                    logger.info(
                        f"Background embedding processing: {result['succeeded']} succeeded, "
                        f"{result['failed']} failed"
                    )
                
            except Exception as e:
                logger.error(f"Embedding processor task error: {e}")
                await asyncio.sleep(10)  # Brief pause before retrying
    
    async def _periodic_sync_task(self):
        """Background task for periodic source synchronization"""
        while self.running:
            try:
                # Wait for sync interval (default 24 hours)
                sync_interval_hours = 24  # Could be made configurable
                await asyncio.sleep(sync_interval_hours * 3600)
                
                if not self.running:
                    break
                
                logger.info("Starting periodic sync...")
                sync_results = await self.ingestion_service.ingest_from_all_sources()
                
                total_items = sum(r.items_added + r.items_updated for r in sync_results.values())
                logger.info(f"Periodic sync completed: {total_items} items updated")
                
            except Exception as e:
                logger.error(f"Periodic sync task error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    async def _print_startup_summary(self):
        """Print application startup summary"""
        stats = {
            'database': self.db.get_database_stats(),
            'vector_store': self.vector_store.get_stats(),
            'sources': self.source_registry.get_registry_stats(),
            'search': self.search_service.get_search_stats()
        }
        
        print("\n" + "="*60)
        print("🚀 LIFEBOARD APPLICATION STARTED")
        print("="*60)
        print(f"Database: {stats['database']['total_items']} items across {stats['database']['active_sources']} sources")
        print(f"Vector Store: {stats['vector_store']['total_vectors']} vectors (dimension {stats['vector_store']['dimension']})")
        print(f"Active Sources: {', '.join(stats['sources']['active_namespaces']) if stats['sources']['active_namespaces'] else 'None'}")
        print(f"Search Service: {stats['search']['search_config']['default_top_k']} default results")
        print("="*60)
        print("Ready for queries! Use search_service.search('your query') to search.")
        print("="*60 + "\n")
    
    async def search(self, query: str, **kwargs):
        """Convenience method for searching"""
        if not self.search_service:
            raise RuntimeError("Application not initialized")
        
        response = await self.search_service.search(query, **kwargs)
        return response
    
    async def ingest_manual_item(self, namespace: str, content: str, **kwargs):
        """Convenience method for manual ingestion"""
        if not self.ingestion_service:
            raise RuntimeError("Application not initialized")
        
        namespaced_id = await self.ingestion_service.manual_ingest_item(namespace, content, **kwargs)
        
        # Process embedding immediately
        await self.ingestion_service.process_pending_embeddings(batch_size=1)
        
        return namespaced_id
    
    async def get_stats(self):
        """Get comprehensive application statistics"""
        if not self.running:
            return {"status": "not_running"}
        
        return {
            "status": "running",
            "database": self.db.get_database_stats(),
            "vector_store": self.vector_store.get_stats(),
            "sources": self.source_registry.get_registry_stats(),
            "search": self.search_service.get_search_stats(),
            "ingestion": self.ingestion_service.get_ingestion_stats()
        }
    
    async def shutdown(self):
        """Gracefully shutdown the application"""
        logger.info("Shutting down Lifeboard application...")
        self.running = False
        self._shutdown_event.set()
        
        try:
            # Save vector store
            if self.vector_store:
                self.vector_store.save_index()
                logger.info("Vector store saved")
            
            # Cleanup embedding service
            if self.embeddings:
                self.embeddings.cleanup()
                logger.info("Embedding service cleaned up")
            
            # Cleanup source registry
            if self.source_registry:
                self.source_registry.cleanup()
                logger.info("Source registry cleaned up")
            
            logger.info("Lifeboard application shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()


# Global application instance
app = None


async def create_app() -> LifeboardApplication:
    """Create and initialize the application"""
    global app
    app = LifeboardApplication()
    await app.start()
    return app


async def shutdown_handler():
    """Handle shutdown signal"""
    global app
    if app:
        await app.shutdown()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(shutdown_handler())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main application entry point"""
    setup_signal_handlers()
    
    try:
        # Create and start application
        app = await create_app()
        
        # Example usage
        logger.info("Application ready! Running example search...")
        
        # Perform example search
        search_response = await app.search("What did I work on recently?")
        print(f"\nExample search results: {search_response.total_results} items found")
        
        for i, result in enumerate(search_response.results[:3]):
            print(f"  {i+1}. [{result.namespace}] {result.content[:100]}...")
        
        # Keep the application running
        logger.info("Application running. Press Ctrl+C to shutdown.")
        await app.wait_for_shutdown()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)