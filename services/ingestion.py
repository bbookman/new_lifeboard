import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timezone

from sources.base import DataItem, BaseSource
from sources.limitless import LimitlessSource
from sources.sync_manager import LimitlessSyncManager
from sources.limitless_processor import LimitlessProcessor
from sources.chunking_processor import ChunkingEmbeddingIntegrator
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
        
        # Initialize processor with chunking support
        chunking_config = getattr(config, 'chunking', {})
        self.processor = LimitlessProcessor(
            enable_segmentation=True,
            enable_intelligent_chunking=True,
            chunking_config=chunking_config
        )
        
        # Initialize chunking integrator for embedding generation
        self.chunking_integrator = ChunkingEmbeddingIntegrator()
        
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
            
            # Note: Embedding processing is now handled by a separate scheduler
            # This allows for faster data ingestion and flexible embedding processing
            if result.items_stored > 0:
                logger.info(f"Stored {result.items_stored} new items. Embeddings will be processed by the embedding scheduler.")
            
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
        """Process items that need embeddings with intelligent chunking support"""
        result = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "chunking_stats": {
                "items_chunked": 0,
                "total_chunks_created": 0,
                "chunk_embeddings_created": 0
            }
        }
        
        try:
            # Get items needing embeddings
            pending_items = self.database.get_pending_embeddings(limit=batch_size * 2)
            
            if not pending_items:
                logger.info("No pending embeddings")
                return result
            
            logger.info(f"Processing {len(pending_items)} pending embeddings")
            
            # Convert to DataItems for chunking analysis
            data_items = []
            for item in pending_items:
                data_item = DataItem(
                    namespace=item.get('namespace', ''),
                    source_id=item.get('id', '').split(':', 1)[-1] if ':' in item.get('id', '') else item.get('id', ''),
                    content=item.get('content', ''),
                    metadata=item.get('metadata', {}),
                    created_at=None,
                    updated_at=None
                )
                data_items.append(data_item)
            
            # Prepare embedding tasks with chunking support
            embedding_tasks = self.chunking_integrator.prepare_items_for_embedding(data_items)
            
            logger.info(f"Prepared {len(embedding_tasks)} embedding tasks from {len(data_items)} items")
            
            # Get chunking statistics
            chunking_stats = self.chunking_integrator.get_embedding_stats(embedding_tasks)
            result["chunking_stats"].update(chunking_stats)
            
            # Process embedding tasks in batches
            for i in range(0, len(embedding_tasks), batch_size):
                batch_tasks = embedding_tasks[i:i + batch_size]
                await self._process_chunking_embedding_batch(batch_tasks, result)
        
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

    async def _process_chunking_embedding_batch(self, batch_tasks: List[Dict], result: Dict[str, Any]):
        """Process a batch of chunking-aware embedding tasks"""
        try:
            # Prepare content for embedding
            texts = []
            tasks = []
            
            for task in batch_tasks:
                if task.get('content'):  # Only embed tasks with content
                    texts.append(task['content'])
                    tasks.append(task)
            
            if not texts:
                return
            
            # Generate embeddings
            embeddings = await self.embedding_service.embed_texts(texts)
            
            # Store embeddings and update status
            for task, embedding in zip(tasks, embeddings):
                try:
                    # Use the task ID for vector storage
                    task_id = task.get('id', task.get('item_id', 'unknown'))
                    success = self.vector_store.add_vector(task_id, embedding)
                    
                    if success:
                        # Update embedding status for original item
                        original_id = task.get('original_id', task_id)
                        self.database.update_embedding_status(original_id, 'completed')
                        result["successful"] += 1
                        
                        # Track chunking stats
                        if task.get('type') == 'chunk':
                            result["chunking_stats"]["chunk_embeddings_created"] += 1
                        
                        logger.debug(f"Generated embedding for task: {task_id}")
                    else:
                        original_id = task.get('original_id', task_id)
                        self.database.update_embedding_status(original_id, 'failed')
                        result["failed"] += 1
                        result["errors"].append(f"Failed to add vector for task {task_id}")
                
                except Exception as e:
                    original_id = task.get('original_id', task.get('item_id', task_id))
                    self.database.update_embedding_status(original_id, 'failed')
                    result["failed"] += 1
                    result["errors"].append(f"Error processing task {task_id}: {str(e)}")
                
                result["processed"] += 1
        
        except Exception as e:
            error_msg = f"Chunking batch embedding failed: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            
            # Mark all original items in batch as failed
            for task in batch_tasks:
                original_id = task.get('original_id', task.get('item_id', 'unknown'))
                self.database.update_embedding_status(original_id, 'failed')
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
        
        namespaced_id = NamespacedIDManager.create_id(namespace, source_id)
        logger.info(f"Manually ingested item: {namespaced_id} (embedding will be processed by scheduler)")
        
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
        
        # Note: Embeddings are now processed by a separate scheduler
        total_items = sum(result.items_stored for result in results.values() if hasattr(result, 'items_stored'))
        if total_items > 0:
            logger.info(f"Full sync completed: {total_items} items stored. Embeddings will be processed by the embedding scheduler.")
        
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
        
        # Note: Embeddings are now processed by a separate scheduler
        total_items = sum(result.items_stored for result in results.values() if hasattr(result, 'items_stored'))
        if total_items > 0:
            logger.info(f"Incremental sync completed: {total_items} items stored. Embeddings will be processed by the embedding scheduler.")
        
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