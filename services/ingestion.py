import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timezone

from sources.base import DataItem, BaseSource
from sources.limitless import LimitlessSource
from sources.sync_manager import LimitlessSyncManager
from sources.limitless_processor import LimitlessProcessor
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from core.ids import NamespacedIDManager
from config.models import AppConfig

logger = logging.getLogger(__name__)


class IngestionResult:
    """Result of an ingestion operation"""
    
    def __init__(self):
        self.items_processed = 0
        self.items_stored = 0
        self.items_skipped = 0
        self.embeddings_generated = 0
        self.errors: List[str] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    @property
    def success(self) -> bool:
        """Check if ingestion was successful"""
        return len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "items_processed": self.items_processed,
            "items_stored": self.items_stored,
            "items_skipped": self.items_skipped,
            "embeddings_generated": self.embeddings_generated,
            "errors": self.errors,
            "success": self.success,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }


class IngestionService:
    """Service for ingesting data from various sources into the Lifeboard system"""
    
    def __init__(self,
                 database: DatabaseService,
                 vector_store: VectorStoreService,
                 embedding_service: EmbeddingService,
                 config: AppConfig):
        self.database = database
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.config = config
        
        # Initialize processor
        self.processor = LimitlessProcessor(enable_segmentation=True)
        
        # Track registered sources
        self.sources: Dict[str, BaseSource] = {}
    
    def register_source(self, source: BaseSource):
        """Register a data source"""
        self.sources[source.namespace] = source
        
        # Register in database
        self.database.register_data_source(
            namespace=source.namespace,
            source_type=source.get_source_type(),
            metadata={"registered_at": datetime.now(timezone.utc).isoformat()}
        )
        
        logger.info(f"Registered source: {source.namespace} ({source.get_source_type()})")
    
    async def ingest_from_source(self, 
                                namespace: str, 
                                force_full_sync: bool = False,
                                limit: int = 1000) -> IngestionResult:
        """Ingest data from a specific source"""
        if namespace not in self.sources:
            raise ValueError(f"Source {namespace} not registered")
        
        source = self.sources[namespace]
        result = IngestionResult()
        result.start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"Starting ingestion from {namespace}")
            
            # Handle Limitless source with sync manager
            if isinstance(source, LimitlessSource):
                sync_manager = LimitlessSyncManager(
                    limitless_source=source,
                    database=self.database,
                    config=self.config.limitless
                )
                
                async for item in sync_manager.sync(force_full_sync=force_full_sync, limit=limit):
                    await self._process_and_store_item(item, result)
            
            else:
                # Generic source handling
                last_sync = self.database.get_setting(f"{namespace}_last_sync")
                since = None
                if last_sync and not force_full_sync:
                    since = datetime.fromisoformat(last_sync)
                
                async for item in source.fetch_items(since=since, limit=limit):
                    await self._process_and_store_item(item, result)
                
                # Update last sync time
                self.database.set_setting(
                    f"{namespace}_last_sync", 
                    datetime.now(timezone.utc).isoformat()
                )
        
        except Exception as e:
            error_msg = f"Ingestion failed for {namespace}: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        finally:
            result.end_time = datetime.now(timezone.utc)
            
            # Automatically process embeddings for newly ingested items
            if result.items_stored > 0:
                try:
                    logger.info(f"Auto-processing embeddings for {result.items_stored} newly ingested items...")
                    embedding_result = await self.process_pending_embeddings(batch_size=32)
                    result.embeddings_generated = embedding_result.get("successful", 0)
                    logger.info(f"Auto-embedding processing completed: {result.embeddings_generated} embeddings generated")
                    
                    if embedding_result.get("errors"):
                        result.errors.extend(embedding_result["errors"])
                        
                except Exception as e:
                    error_msg = f"Auto-embedding processing failed: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
            
            logger.info(f"Ingestion completed for {namespace}: {result.to_dict()}")
        
        return result
    
    async def _process_and_store_item(self, item: DataItem, result: IngestionResult):
        """Process and store a single data item"""
        try:
            result.items_processed += 1
            
            # Process the item through the pipeline
            processed_item = self.processor.process(item)
            
            # Create namespaced ID
            namespaced_id = NamespacedIDManager.create_id(
                processed_item.namespace, 
                processed_item.source_id
            )
            
            # Store in database
            self.database.store_data_item(
                id=namespaced_id,
                namespace=processed_item.namespace,
                source_id=processed_item.source_id,
                content=processed_item.content,
                metadata=processed_item.metadata
            )
            
            result.items_stored += 1
            logger.debug(f"Stored item: {namespaced_id}")
            
        except Exception as e:
            error_msg = f"Error processing item {item.source_id}: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def process_pending_embeddings(self, batch_size: int = 32) -> Dict[str, Any]:
        """Process items that need embeddings"""
        result = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            # Get items needing embeddings
            pending_items = self.database.get_pending_embeddings(limit=batch_size * 2)
            
            if not pending_items:
                logger.info("No pending embeddings")
                return result
            
            logger.info(f"Processing {len(pending_items)} pending embeddings")
            
            # Process in batches
            for i in range(0, len(pending_items), batch_size):
                batch = pending_items[i:i + batch_size]
                await self._process_embedding_batch(batch, result)
        
        except Exception as e:
            error_msg = f"Error processing embeddings: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    async def _process_embedding_batch(self, batch: List[Dict], result: Dict[str, Any]):
        """Process a batch of items for embedding generation"""
        try:
            # Prepare content for embedding
            texts = []
            items = []
            
            for item in batch:
                if item['content']:  # Only embed items with content
                    texts.append(item['content'])
                    items.append(item)
            
            if not texts:
                return
            
            # Generate embeddings
            embeddings = await self.embedding_service.embed_texts(texts)
            
            # Store embeddings and update status
            for item, embedding in zip(items, embeddings):
                try:
                    # Add to vector store
                    success = self.vector_store.add_vector(item['id'], embedding)
                    
                    if success:
                        # Update embedding status
                        self.database.update_embedding_status(item['id'], 'completed')
                        result["successful"] += 1
                        logger.debug(f"Generated embedding for: {item['id']}")
                    else:
                        self.database.update_embedding_status(item['id'], 'failed')
                        result["failed"] += 1
                        result["errors"].append(f"Failed to add vector for {item['id']}")
                
                except Exception as e:
                    self.database.update_embedding_status(item['id'], 'failed')
                    result["failed"] += 1
                    result["errors"].append(f"Error processing {item['id']}: {str(e)}")
                
                result["processed"] += 1
        
        except Exception as e:
            error_msg = f"Batch embedding failed: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            
            # Mark all items in batch as failed
            for item in batch:
                self.database.update_embedding_status(item['id'], 'failed')
                result["failed"] += 1
                result["processed"] += 1
    
    async def manual_ingest_item(self, 
                                namespace: str,
                                content: str,
                                source_id: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """Manually ingest a single item"""
        if source_id is None:
            source_id = str(datetime.now(timezone.utc).timestamp())
        
        if metadata is None:
            metadata = {}
        
        # Create data item
        item = DataItem(
            namespace=namespace,
            source_id=source_id,
            content=content,
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Process and store
        result = IngestionResult()
        await self._process_and_store_item(item, result)
        
        if result.errors:
            raise Exception(f"Failed to ingest item: {result.errors[0]}")
        
        # Auto-process embeddings for the manually ingested item
        if result.items_stored > 0:
            try:
                embedding_result = await self.process_pending_embeddings(batch_size=1)
                result.embeddings_generated = embedding_result.get("successful", 0)
                logger.info(f"Auto-generated embedding for manually ingested item")
            except Exception as e:
                logger.warning(f"Auto-embedding failed for manually ingested item: {e}")
        
        namespaced_id = NamespacedIDManager.create_id(namespace, source_id)
        logger.info(f"Manually ingested item: {namespaced_id}")
        
        return namespaced_id
    
    async def full_sync_all_sources(self, limit_per_source: int = 1000) -> Dict[str, IngestionResult]:
        """Perform full sync for all registered sources"""
        results = {}
        
        for namespace in self.sources.keys():
            try:
                logger.info(f"Starting full sync for {namespace}")
                result = await self.ingest_from_source(
                    namespace=namespace,
                    force_full_sync=True,
                    limit=limit_per_source
                )
                results[namespace] = result
                
            except Exception as e:
                logger.error(f"Full sync failed for {namespace}: {e}")
                error_result = IngestionResult()
                error_result.errors.append(str(e))
                results[namespace] = error_result
        
        # Process any remaining pending embeddings after all syncs
        total_items = sum(result.items_stored for result in results.values() if hasattr(result, 'items_stored'))
        if total_items > 0:
            try:
                logger.info(f"Processing any remaining pending embeddings after full sync...")
                final_embedding_result = await self.process_pending_embeddings(batch_size=64)
                logger.info(f"Final embedding processing: {final_embedding_result.get('successful', 0)} embeddings generated")
            except Exception as e:
                logger.warning(f"Final embedding processing failed: {e}")
        
        return results
    
    async def incremental_sync_all_sources(self, limit_per_source: int = 1000) -> Dict[str, IngestionResult]:
        """Perform incremental sync for all registered sources"""
        results = {}
        
        for namespace in self.sources.keys():
            try:
                logger.info(f"Starting incremental sync for {namespace}")
                result = await self.ingest_from_source(
                    namespace=namespace,
                    force_full_sync=False,
                    limit=limit_per_source
                )
                results[namespace] = result
                
            except Exception as e:
                logger.error(f"Incremental sync failed for {namespace}: {e}")
                error_result = IngestionResult()
                error_result.errors.append(str(e))
                results[namespace] = error_result
        
        # Process any remaining pending embeddings after all syncs
        total_items = sum(result.items_stored for result in results.values() if hasattr(result, 'items_stored'))
        if total_items > 0:
            try:
                logger.info(f"Processing any remaining pending embeddings after incremental sync...")
                final_embedding_result = await self.process_pending_embeddings(batch_size=64)
                logger.info(f"Final embedding processing: {final_embedding_result.get('successful', 0)} embeddings generated")
            except Exception as e:
                logger.warning(f"Final embedding processing failed: {e}")
        
        return results
    
    def get_ingestion_status(self) -> Dict[str, Any]:
        """Get current ingestion status"""
        status = {
            "registered_sources": list(self.sources.keys()),
            "database_stats": self.database.get_database_stats(),
            "vector_store_stats": self.vector_store.get_stats(),
            "pending_embeddings": len(self.database.get_pending_embeddings(limit=1000))
        }
        
        # Add per-source stats
        source_stats = {}
        for namespace in self.sources.keys():
            items = self.database.get_data_items_by_namespace(namespace, limit=1)
            source_stats[namespace] = {
                "source_type": self.sources[namespace].get_source_type(),
                "has_data": len(items) > 0,
                "last_sync": self.database.get_setting(f"{namespace}_last_sync")
            }
        
        status["source_stats"] = source_stats
        
        return status