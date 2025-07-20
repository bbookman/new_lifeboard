import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import time
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService, EmbeddingBatch
from core.ids import NamespacedIDManager
from sources.registry import SourceRegistry
from sources.base import SourceBase, DataItem, SourceSyncResult
from config.models import SchedulerConfig


logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting data from sources into the storage system"""
    
    def __init__(self, 
                 db_service: DatabaseService,
                 vector_service: VectorStoreService, 
                 embedding_service: EmbeddingService,
                 source_registry: SourceRegistry,
                 config: SchedulerConfig = None):
        self.db = db_service
        self.vector_store = vector_service
        self.embeddings = embedding_service
        self.source_registry = source_registry
        self.config = config or SchedulerConfig()
        self.logger = logging.getLogger(__name__)
    
    async def ingest_from_source(self, namespace: str, since: Optional[datetime] = None) -> SourceSyncResult:
        """
        Ingest data from a specific source
        
        Args:
            namespace: Source namespace to ingest from
            since: Only ingest data updated since this timestamp
            
        Returns:
            SourceSyncResult with ingestion statistics
        """
        start_time = time.time()
        source = self.source_registry.get_source(namespace)
        
        if not source:
            return SourceSyncResult(
                source_namespace=namespace,
                items_fetched=0,
                items_added=0,
                items_updated=0,
                items_failed=0,
                sync_duration_seconds=0,
                last_sync_time=datetime.now(),
                errors=[f"Source {namespace} not found in registry"]
            )
        
        self.logger.info(f"Starting ingestion from source: {namespace}")
        
        items_fetched = 0
        items_added = 0
        items_updated = 0
        items_failed = 0
        errors = []
        
        try:
            # Fetch data from source
            async for data_item in source.fetch_data(since):
                items_fetched += 1
                
                try:
                    # Create namespaced ID
                    namespaced_id = NamespacedIDManager.create_id(namespace, data_item.source_id)
                    
                    # Check if item already exists
                    existing_items = self.db.get_data_items_by_ids([namespaced_id])
                    is_update = len(existing_items) > 0
                    
                    # Prepare metadata
                    metadata = data_item.metadata or {}
                    if data_item.timestamp:
                        metadata['timestamp'] = data_item.timestamp.isoformat()
                    
                    # Store in database
                    self.db.store_data_item(
                        id=namespaced_id,
                        namespace=namespace,
                        source_id=data_item.source_id,
                        content=data_item.content,
                        metadata=metadata
                    )
                    
                    if is_update:
                        items_updated += 1
                        self.logger.debug(f"Updated item: {namespaced_id}")
                    else:
                        items_added += 1
                        self.logger.debug(f"Added new item: {namespaced_id}")
                    
                    # Mark for embedding (will be processed by scheduler)
                    self.db.update_embedding_status(namespaced_id, 'pending')
                    
                except Exception as e:
                    items_failed += 1
                    error_msg = f"Failed to process item {data_item.source_id}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            # Update source item count
            self.db.update_source_item_count(namespace)
            
            sync_duration = time.time() - start_time
            
            result = SourceSyncResult(
                source_namespace=namespace,
                items_fetched=items_fetched,
                items_added=items_added,
                items_updated=items_updated,
                items_failed=items_failed,
                sync_duration_seconds=sync_duration,
                last_sync_time=datetime.now(),
                errors=errors
            )
            
            self.logger.info(
                f"Ingestion completed for {namespace}: "
                f"{items_added} added, {items_updated} updated, "
                f"{items_failed} failed in {sync_duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            sync_duration = time.time() - start_time
            error_msg = f"Ingestion failed for {namespace}: {str(e)}"
            self.logger.error(error_msg)
            
            return SourceSyncResult(
                source_namespace=namespace,
                items_fetched=items_fetched,
                items_added=items_added,
                items_updated=items_updated,
                items_failed=items_failed,
                sync_duration_seconds=sync_duration,
                last_sync_time=datetime.now(),
                errors=errors + [error_msg]
            )
    
    async def ingest_from_all_sources(self, since: Optional[datetime] = None) -> Dict[str, SourceSyncResult]:
        """
        Ingest data from all active sources
        
        Args:
            since: Only ingest data updated since this timestamp
            
        Returns:
            Dictionary mapping namespace to SourceSyncResult
        """
        self.logger.info("Starting ingestion from all active sources")
        results = {}
        
        active_sources = self.source_registry.get_active_sources()
        
        # Create tasks for parallel ingestion
        tasks = []
        for source in active_sources:
            task = asyncio.create_task(
                self.ingest_from_source(source.namespace, since),
                name=f"ingest_{source.namespace}"
            )
            tasks.append((source.namespace, task))
        
        # Wait for all ingestion tasks to complete
        for namespace, task in tasks:
            try:
                result = await task
                results[namespace] = result
            except Exception as e:
                self.logger.error(f"Ingestion task failed for {namespace}: {e}")
                results[namespace] = SourceSyncResult(
                    source_namespace=namespace,
                    items_fetched=0,
                    items_added=0,
                    items_updated=0,
                    items_failed=0,
                    sync_duration_seconds=0,
                    last_sync_time=datetime.now(),
                    errors=[f"Task failed: {str(e)}"]
                )
        
        # Log summary
        total_added = sum(r.items_added for r in results.values())
        total_updated = sum(r.items_updated for r in results.values())
        total_failed = sum(r.items_failed for r in results.values())
        
        self.logger.info(
            f"Ingestion summary: {total_added} added, {total_updated} updated, "
            f"{total_failed} failed across {len(results)} sources"
        )
        
        return results
    
    async def process_pending_embeddings(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Process items that need embeddings
        
        Args:
            batch_size: Number of items to process in this batch
            
        Returns:
            Statistics about embedding processing
        """
        if batch_size is None:
            batch_size = self.config.embedding_batch_size
        
        self.logger.info(f"Processing pending embeddings (batch size: {batch_size})")
        start_time = time.time()
        
        # Get pending items
        pending_items = self.db.get_pending_embeddings(batch_size)
        
        if not pending_items:
            return {
                'processed': 0,
                'succeeded': 0,
                'failed': 0,
                'duration_seconds': time.time() - start_time,
                'errors': []
            }
        
        self.logger.info(f"Found {len(pending_items)} items pending embedding")
        
        # Create embedding batch
        embedding_batch = EmbeddingBatch(self.embeddings)
        for item in pending_items:
            embedding_batch.add(item['content'], item['id'])
        
        succeeded = 0
        failed = 0
        errors = []
        
        try:
            # Process embeddings
            embedding_results = await embedding_batch.process()
            
            # Store embeddings in vector store
            for namespaced_id, embedding in embedding_results:
                try:
                    success = self.vector_store.add_vector(namespaced_id, embedding)
                    if success:
                        self.db.update_embedding_status(namespaced_id, 'completed')
                        succeeded += 1
                    else:
                        self.db.update_embedding_status(namespaced_id, 'failed')
                        failed += 1
                        errors.append(f"Failed to add vector for {namespaced_id}")
                        
                except Exception as e:
                    self.db.update_embedding_status(namespaced_id, 'failed')
                    failed += 1
                    error_msg = f"Error processing embedding for {namespaced_id}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
        except Exception as e:
            # Mark all items as failed
            for item in pending_items:
                self.db.update_embedding_status(item['id'], 'failed')
                failed += 1
            
            error_msg = f"Batch embedding processing failed: {str(e)}"
            errors.append(error_msg)
            self.logger.error(error_msg)
        
        duration = time.time() - start_time
        
        self.logger.info(
            f"Embedding processing completed: {succeeded} succeeded, "
            f"{failed} failed in {duration:.2f}s"
        )
        
        return {
            'processed': len(pending_items),
            'succeeded': succeeded,
            'failed': failed,
            'duration_seconds': duration,
            'errors': errors
        }
    
    async def reprocess_failed_embeddings(self, max_retries: int = None) -> Dict[str, Any]:
        """
        Retry embedding generation for failed items
        
        Args:
            max_retries: Maximum retry attempts
            
        Returns:
            Statistics about retry processing
        """
        if max_retries is None:
            max_retries = getattr(self.config, 'max_embedding_retries', 3)
        
        # This would require tracking retry counts in the database
        # For now, we'll just reprocess all failed items
        self.logger.info("Reprocessing failed embeddings")
        
        # Reset failed items to pending (simplified approach)
        # In production, you'd want more sophisticated retry logic
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE data_items 
                    SET embedding_status = 'pending' 
                    WHERE embedding_status = 'failed'
                """)
                updated_count = cursor.rowcount
                conn.commit()
            
            self.logger.info(f"Reset {updated_count} failed items to pending")
            
            # Process the pending items
            if updated_count > 0:
                return await self.process_pending_embeddings()
            else:
                return {
                    'processed': 0,
                    'succeeded': 0,
                    'failed': 0,
                    'duration_seconds': 0,
                    'errors': []
                }
                
        except Exception as e:
            error_msg = f"Failed to reprocess failed embeddings: {str(e)}"
            self.logger.error(error_msg)
            return {
                'processed': 0,
                'succeeded': 0,
                'failed': 0,
                'duration_seconds': 0,
                'errors': [error_msg]
            }
    
    async def manual_ingest_item(self, namespace: str, content: str, 
                                source_id: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Manually ingest a single item
        
        Args:
            namespace: Target namespace
            content: Item content
            source_id: Optional source ID (will be generated if not provided)
            metadata: Optional metadata
            
        Returns:
            The namespaced ID of the created item
        """
        if not source_id:
            source_id = f"manual_{int(time.time())}"
        
        namespaced_id = NamespacedIDManager.create_id(namespace, source_id)
        
        # Add timestamp to metadata
        if metadata is None:
            metadata = {}
        metadata['ingestion_type'] = 'manual'
        metadata['ingestion_time'] = datetime.now().isoformat()
        
        # Store in database
        self.db.store_data_item(
            id=namespaced_id,
            namespace=namespace,
            source_id=source_id,
            content=content,
            metadata=metadata
        )
        
        # Mark for embedding
        self.db.update_embedding_status(namespaced_id, 'pending')
        
        self.logger.info(f"Manually ingested item: {namespaced_id}")
        return namespaced_id
    
    async def delete_item(self, namespaced_id: str) -> bool:
        """
        Delete an item from both database and vector store
        
        Args:
            namespaced_id: ID of item to delete
            
        Returns:
            True if deletion was successful
        """
        try:
            # Remove from vector store
            self.vector_store.remove_vector(namespaced_id)
            
            # Remove from database
            with self.db.get_connection() as conn:
                cursor = conn.execute("DELETE FROM data_items WHERE id = ?", (namespaced_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            
            if deleted:
                self.logger.info(f"Deleted item: {namespaced_id}")
            
            return deleted
            
        except Exception as e:
            self.logger.error(f"Failed to delete item {namespaced_id}: {e}")
            return False
    
    async def cleanup_namespace(self, namespace: str) -> Dict[str, int]:
        """
        Remove all data for a specific namespace
        
        Args:
            namespace: Namespace to clean up
            
        Returns:
            Statistics about cleanup operation
        """
        self.logger.info(f"Cleaning up namespace: {namespace}")
        
        try:
            # Get items to delete
            items = self.db.get_data_items_by_namespace(namespace, limit=999999)
            item_count = len(items)
            
            # Remove from vector store
            vector_count = self.vector_store.clear_namespace(namespace)
            
            # Remove from database
            with self.db.get_connection() as conn:
                cursor = conn.execute("DELETE FROM data_items WHERE namespace = ?", (namespace,))
                db_deleted = cursor.rowcount
                
                # Also remove from data_sources
                cursor = conn.execute("DELETE FROM data_sources WHERE namespace = ?", (namespace,))
                source_deleted = cursor.rowcount
                
                conn.commit()
            
            self.logger.info(
                f"Cleaned up namespace {namespace}: "
                f"{db_deleted} database items, {vector_count} vectors"
            )
            
            return {
                'namespace': namespace,
                'database_items_deleted': db_deleted,
                'vectors_deleted': vector_count,
                'source_record_deleted': source_deleted
            }
            
        except Exception as e:
            error_msg = f"Failed to cleanup namespace {namespace}: {str(e)}"
            self.logger.error(error_msg)
            return {
                'namespace': namespace,
                'database_items_deleted': 0,
                'vectors_deleted': 0,
                'source_record_deleted': 0,
                'error': error_msg
            }
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion service statistics"""
        db_stats = self.db.get_database_stats()
        vector_stats = self.vector_store.get_stats()
        
        return {
            'database': db_stats,
            'vector_store': vector_stats,
            'config': {
                'embedding_batch_size': self.config.embedding_batch_size,
                'embedding_interval_seconds': self.config.embedding_interval_seconds
            }
        }