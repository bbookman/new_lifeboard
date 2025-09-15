import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timezone

from core.base_service import BaseService
from services.debug_mixin import ServiceDebugMixin
from sources.base import DataItem, BaseSource
from sources.sync_manager import SyncManager
from sources.limitless_processor import LimitlessProcessor, BaseProcessor
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


class IngestionService(BaseService, ServiceDebugMixin):
    """Service for ingesting data from various sources into the Lifeboard system"""
    
    def __init__(self,
                 database: DatabaseService,
                 vector_store: VectorStoreService,
                 embedding_service: EmbeddingService,
                 config: AppConfig):
        BaseService.__init__(self, service_name="IngestionService", config=config)
        ServiceDebugMixin.__init__(self, "ingestion_service")
        self.database = database
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        
        # Log service initialization
        self.log_service_call("__init__", {
            "database_available": database is not None,
            "vector_store_available": vector_store is not None,
            "embedding_service_available": embedding_service is not None
        })
        
        # Initialize processors
        self.processors: Dict[str, BaseProcessor] = {
            "limitless": LimitlessProcessor(
                enable_segmentation=True, 
                enable_markdown_generation=True,
                enable_semantic_deduplication=True,
                embedding_service=embedding_service
            )
        }
        self.default_processor = BaseProcessor()
        
        # Track registered sources
        self.sources: Dict[str, BaseSource] = {}
        
        # Add dependencies and capabilities
        self.add_dependency("DatabaseService")
        self.add_dependency("VectorStoreService")
        self.add_dependency("EmbeddingService")
        self.add_capability("data_ingestion")
        self.add_capability("source_management")
        self.add_capability("embedding_processing")
        self.add_capability("batch_processing")
    
    async def register_source(self, source: BaseSource):
        """Register a data source"""
        self.sources[source.namespace] = source
        
        # Register in database
        await self.database.async_register_data_source(
            namespace=source.namespace,
            source_type=source.get_source_type(),
            metadata={"registered_at": datetime.now(timezone.utc).isoformat()}
        )
        
        logger.info(f"Registered source: {source.namespace} ({source.get_source_type()})")
    
    async def ingest_from_source(self, 
                                namespace: str, 
                                force_full_sync: bool = False,
                                limit: int = 1000,
                                ingestion_mode: str = 'partial') -> IngestionResult:
        """Ingest data from a specific source"""
        if namespace not in self.sources:
            raise ValueError(f"Source {namespace} not registered")
        
        source = self.sources[namespace]
        result = IngestionResult()
        result.start_time = datetime.now(timezone.utc)
        
        # Twitter-specific trace logging
        if namespace == 'twitter':
            logger.info(f"Twitter ingestion starting")
        
        try:
            logger.info(f"Starting ingestion from {namespace}")
            
            # Unified source handling for all sources
            last_sync = await self.database.async_get_setting(f"{namespace}_last_sync")
            since = None
            if last_sync and not force_full_sync:
                try:
                    # Handle case where last_sync might be a JSON object due to json_utils processing
                    if isinstance(last_sync, dict):
                        if 'raw_value' in last_sync:
                            actual_timestamp = last_sync['raw_value']
                            logger.debug(f"Extracting timestamp from raw_value structure for {namespace}: {actual_timestamp}")
                            last_sync = actual_timestamp
                        else:
                            logger.warning(f"Invalid timestamp structure for {namespace}: {last_sync}")
                            last_sync = None
                    
                    # Ensure we have a string before parsing
                    if last_sync and isinstance(last_sync, str):
                        since = datetime.fromisoformat(last_sync)
                    elif last_sync:
                        logger.warning(f"Timestamp is not a string for {namespace}: {type(last_sync)} = {last_sync}")
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse last sync time for {namespace}: {last_sync} - {e}")
            
            # Collect items for batch processing
            items = []
            
            # Twitter-specific trace logging for fetch operation
            if namespace == 'twitter':
                fetch_start_time = time.time()

            async for item in source.fetch_items(since=since, limit=limit):
                items.append(item)
                result.items_processed += 1

            # Twitter-specific trace logging for collection results
            if namespace == 'twitter':
                fetch_duration = (time.time() - fetch_start_time) * 1000
                logger.debug(f"[TWITTER TRACE] Twitter fetch operation completed in {fetch_duration:.2f}ms")
            
            # Process items - use batch processing for namespace with batch-capable processors
            if items:
                processor = self.processors.get(namespace, self.default_processor)
                
                # Twitter-specific trace logging for processing phase
                if namespace == 'twitter':
                    processing_start_time = time.time()
                    logger.debug(f"[TWITTER TRACE] Starting Twitter processing phase with {len(items)} items")
                    logger.debug(f"[TWITTER TRACE] Using processor: {type(processor).__name__}")
                
                # Check if processor supports batch processing (has process_batch method)
                if hasattr(processor, 'process_batch') and callable(getattr(processor, 'process_batch')):
                    logger.info(f"Using batch processing for {namespace} with {len(items)} items")
                    if namespace == 'twitter':
                        logger.debug(f"[TWITTER TRACE] Twitter batch processing enabled")
                    try:
                        processed_items = await processor.process_batch(items)

                        if namespace == 'twitter':
                            logger.debug(f"[TWITTER TRACE] Twitter batch processing completed, got {len(processed_items)} processed items")
                        
                        # Store each processed item
                        for processed_item in processed_items:
                            await self._store_processed_item(processed_item, result)
                            
                    except Exception as e:
                        logger.error(f"Batch processing failed for {namespace}: {e}")
                        if namespace == 'twitter':
                            logger.debug(f"[TWITTER TRACE] Twitter batch processing failed: {e}")
                        # Fall back to individual processing
                        logger.info(f"Falling back to individual processing for {namespace}")
                        if namespace == 'twitter':
                            logger.debug(f"[TWITTER TRACE] Twitter falling back to individual processing")
                        for item in items:
                            await self._process_and_store_item(item, result)
                else:
                    # Use individual processing for processors that don't support batching
                    logger.debug(f"Using individual processing for {namespace} (no batch support)")
                    if namespace == 'twitter':
                        logger.debug(f"[TWITTER TRACE] Twitter using individual processing (no batch support)")
                    for item in items:
                        await self._process_and_store_item(item, result)
                
                # Twitter-specific trace logging for processing completion
                if namespace == 'twitter':
                    processing_duration = (time.time() - processing_start_time) * 1000
                    logger.debug(f"[TWITTER TRACE] Twitter processing phase completed in {processing_duration:.2f}ms")
            
            # Update last sync time after successful processing
            await self.database.async_set_setting(
                f"{namespace}_last_sync", 
                datetime.now(timezone.utc).isoformat()
            )
        
        except Exception as e:
            error_msg = f"Ingestion failed for {namespace}: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        finally:
            result.end_time = datetime.now(timezone.utc)
            logger.info(f"Ingestion completed for {namespace}: {result.to_dict()}")
            
            # Twitter-specific comprehensive lifecycle reporting
            if namespace == 'twitter':
                total_duration = (result.end_time - result.start_time).total_seconds() * 1000
                logger.debug(f"[TWITTER TRACE] Twitter ingestion lifecycle completed in {total_duration:.2f}ms")
                logger.debug(f"[TWITTER TRACE] Twitter data flow metrics: received={result.items_processed}, stored={result.items_stored}, errors={len(result.errors)}")
                if result.errors:
                    logger.error(f"[TWITTER TRACE] Twitter ingestion errors: {result.errors}")
                else:
                    logger.debug(f"[TWITTER TRACE] Twitter ingestion completed successfully with no errors")
                
                # Query database for Twitter data_items to verify storage
                try:
                    query_start_time = time.time()
                    twitter_items = await self.database.async_get_data_items_by_namespace('twitter', limit=5)
                    query_duration = (time.time() - query_start_time) * 1000
                    total_count = len(twitter_items)
                    sample_ids = [item.get('id', item.get('source_id', 'unknown'))[:20] for item in twitter_items[:3]]
                    logger.debug(f"[TWITTER TRACE] Database verification query completed in {query_duration:.2f}ms: found {total_count} total Twitter items")
                    logger.debug(f"[TWITTER TRACE] Sample Twitter item IDs: {sample_ids}")
                except Exception as e:
                    logger.error(f"[TWITTER TRACE] Database verification query failed: {e}")
            
            # WebSocket notifications removed - no longer needed
        
        return result
    
    async def _store_processed_item(self, processed_item: DataItem, result: IngestionResult):
        """Store a pre-processed data item"""
        try:
            # Create namespaced ID
            namespaced_id = NamespacedIDManager.create_id(
                processed_item.namespace, 
                processed_item.source_id
            )
            
            # Extract days_date for calendar support
            days_date = self._extract_days_date(processed_item)
            
            # Twitter-specific trace logging for database storage
            if processed_item.namespace == 'twitter':
                storage_start_time = time.time()
                content_length = len(processed_item.content) if processed_item.content else 0
                logger.debug(f"[TWITTER TRACE] Starting Twitter database storage: id={namespaced_id}, content_length={content_length}, days_date={days_date}")
            
            # Store in database
            await self.database.async_store_data_item(
                id=namespaced_id,
                namespace=processed_item.namespace,
                source_id=processed_item.source_id,
                content=processed_item.content,
                metadata=processed_item.metadata,
                days_date=days_date
            )
            
            result.items_stored += 1
            logger.debug(f"Stored batch-processed item: {namespaced_id}")
            
            # Twitter-specific trace logging for storage success
            if processed_item.namespace == 'twitter':
                storage_duration = (time.time() - storage_start_time) * 1000
                logger.debug(f"[TWITTER TRACE] Twitter database storage completed successfully in {storage_duration:.2f}ms for {namespaced_id}")
            
        except Exception as e:
            error_msg = f"Error storing processed item {processed_item.source_id}: {str(e)}"
            logger.error(error_msg)
            if processed_item.namespace == 'twitter':
                logger.error(f"[TWITTER TRACE] Twitter database storage failed for {processed_item.source_id}: {str(e)}")
                logger.debug(f"[TWITTER TRACE] Twitter storage error context: namespaced_id={namespaced_id if 'namespaced_id' in locals() else 'not_created'}")
            result.errors.append(error_msg)
    
    async def _process_and_store_item(self, item: DataItem, result: IngestionResult):
        """Process and store a single data item"""
        try:
            # Twitter-specific trace logging for DataItem processing
            if item.namespace == 'twitter':
                content_length = len(item.content) if item.content else 0
                metadata_keys = list(item.metadata.keys()) if item.metadata else []
                logger.debug(f"[TWITTER TRACE] Processing Twitter DataItem: source_id={item.source_id}, content_length={content_length}")
                logger.debug(f"[TWITTER TRACE] Twitter DataItem metadata keys: {metadata_keys}")
                processing_start_time = time.time()
            
            # Select the correct processor for the namespace
            processor = self.processors.get(item.namespace, self.default_processor)
            processed_item = processor.process(item)
            
            if item.namespace == 'twitter':
                processing_duration = (time.time() - processing_start_time) * 1000
                logger.debug(f"[TWITTER TRACE] Twitter DataItem processing completed in {processing_duration:.2f}ms")
            
            # Store the processed item
            await self._store_processed_item(processed_item, result)
            
        except Exception as e:
            error_msg = f"Error processing item {item.source_id}: {str(e)}"
            logger.error(error_msg)
            if item.namespace == 'twitter':
                logger.error(f"[TWITTER TRACE] Twitter DataItem processing failed for {item.source_id}: {str(e)}")
                logger.debug(f"[TWITTER TRACE] Twitter error context: namespace={item.namespace}, content_available={item.content is not None}")
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
            pending_items = await self.database.async_get_pending_embeddings(limit=batch_size * 2)
            
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
                        await self.database.async_update_embedding_status(item['id'], 'completed')
                        result["successful"] += 1
                        logger.debug(f"Generated embedding for: {item['id']}")
                    else:
                        await self.database.async_update_embedding_status(item['id'], 'failed')
                        result["failed"] += 1
                        result["errors"].append(f"Failed to add vector for {item['id']}")
                
                except Exception as e:
                    await self.database.async_update_embedding_status(item['id'], 'failed')
                    result["failed"] += 1
                    result["errors"].append(f"Error processing {item['id']}: {str(e)}")
                
                result["processed"] += 1
        
        except Exception as e:
            error_msg = f"Batch embedding failed: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            
            # Mark all items in batch as failed
            for item in batch:
                await self.database.async_update_embedding_status(item['id'], 'failed')
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
        logger.info(f"Manually ingested item: {namespaced_id}")
        
        return namespaced_id
    
    async def ingest_items(self, namespace: str, data_items: List[DataItem]) -> IngestionResult:
        """Ingest multiple DataItems through the standard processing pipeline"""
        result = IngestionResult()
        result.start_time = datetime.now(timezone.utc)
        
        logger.info(f"Ingesting {len(data_items)} items for namespace: {namespace}")
        
        # Twitter-specific trace logging for batch ingestion
        if namespace == 'twitter':
            logger.debug(f"[TWITTER TRACE] Twitter batch ingestion starting at {result.start_time.isoformat()}")
            logger.debug(f"[TWITTER TRACE] Processing {len(data_items)} Twitter DataItems")
            twitter_batch_start_time = time.time()
        
        try:
            # Process each item using the standard processing method
            for item in data_items:
                logger.debug(f"Processing item: {item.source_id}")
                
                # Twitter-specific validation logging
                if namespace == 'twitter' and item.namespace == 'twitter':
                    logger.debug(f"[TWITTER TRACE] Validating Twitter DataItem: {item.source_id}")
                    if not item.content:
                        logger.warning(f"[TWITTER TRACE] Twitter DataItem {item.source_id} has no content")
                    if not item.metadata:
                        logger.warning(f"[TWITTER TRACE] Twitter DataItem {item.source_id} has no metadata")
                
                await self._process_and_store_item(item, result)
                result.items_processed += 1
                logger.debug(f"Successfully processed item: {item.source_id}")
                
                # Twitter-specific success logging
                if namespace == 'twitter' and item.namespace == 'twitter':
                    logger.debug(f"[TWITTER TRACE] Twitter DataItem {item.source_id} processed and stored successfully")
            
            result.end_time = datetime.now(timezone.utc)
            
            logger.info(f"Ingestion completed for {namespace}: {result.items_processed} processed, "
                       f"{result.items_stored} stored, {len(result.errors)} errors")
            
            # Twitter-specific batch completion logging
            if namespace == 'twitter':
                twitter_batch_duration = (time.time() - twitter_batch_start_time) * 1000
                logger.debug(f"[TWITTER TRACE] Twitter batch ingestion completed in {twitter_batch_duration:.2f}ms")
                logger.debug(f"[TWITTER TRACE] Twitter batch results: {result.items_processed} processed, {result.items_stored} stored")
                if result.errors:
                    logger.error(f"[TWITTER TRACE] Twitter batch ingestion errors: {result.errors}")
            
        except Exception as e:
            error_msg = f"Error during batch ingestion for {namespace}: {str(e)}"
            logger.error(error_msg)
            if namespace == 'twitter':
                logger.debug(f"[TWITTER TRACE] Twitter batch ingestion failed: {str(e)}")
            result.errors.append(error_msg)
            result.end_time = datetime.now(timezone.utc)
        
        return result
    
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
        
        return results
    
    async def _initialize_service(self) -> bool:
        """Initialize the ingestion service"""
        try:
            # Ensure all dependencies are ready
            if not self.database or not self.vector_store or not self.embedding_service:
                self.logger.error("Missing required dependencies for IngestionService")
                return False
            
            self.logger.info("IngestionService initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize IngestionService: {e}")
            return False
    
    async def _shutdown_service(self) -> bool:
        """Shutdown the ingestion service"""
        try:
            # Clean up any pending operations
            self.sources.clear()
            self.logger.info("IngestionService shutdown successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error during IngestionService shutdown: {e}")
            return False
    
    async def _check_service_health(self) -> Dict[str, Any]:
        """Check service health"""
        health_info = {
            "registered_sources": len(self.sources),
            "source_names": list(self.sources.keys()),
            "processors_available": len(self.processors) > 0,
            "healthy": True
        }
        
        try:
            # Check database connectivity
            db_stats = await self.database.async_get_database_stats()
            health_info["database_available"] = True
            health_info["total_items"] = db_stats.get("total_items", 0)
            
            # Check vector store
            vs_stats = self.vector_store.get_stats()
            health_info["vector_store_available"] = True
            health_info["total_vectors"] = vs_stats.get("total_vectors", 0)
            
            # Check pending embeddings
            pending_items = await self.database.async_get_pending_embeddings(limit=100)
            pending = len(pending_items)
            health_info["pending_embeddings"] = pending
            
        except Exception as e:
            health_info["healthy"] = False
            health_info["error"] = str(e)
        
        return health_info
    
    async def async_get_ingestion_status(self) -> Dict[str, Any]:
        """Get current ingestion status"""
        # Async version - properly handles async database calls
        db_stats = await self.database.async_get_database_stats()
        pending_items = await self.database.async_get_pending_embeddings(limit=1000)
        
        status = {
            "registered_sources": list(self.sources.keys()),
            "database_stats": db_stats,
            "vector_store_stats": self.vector_store.get_stats(),
            "pending_embeddings": len(pending_items)
        }
        
        # Add per-source stats
        source_stats = {}
        for namespace in self.sources.keys():
            items = await self.database.async_get_data_items_by_namespace(namespace, limit=1)
            last_sync = await self.database.async_get_setting(f"{namespace}_last_sync")
            source_stats[namespace] = {
                "source_type": self.sources[namespace].get_source_type(),
                "has_data": len(items) > 0,
                "last_sync": last_sync
            }
        
        status["source_stats"] = source_stats
        
        return status
    
    def get_ingestion_status(self) -> Dict[str, Any]:
        """Sync wrapper for async_get_ingestion_status() - handles event loop properly"""
        import asyncio
        
        try:
            # Check if we're already in a running event loop
            loop = asyncio.get_running_loop()
            # We're in an async context, this should not be called from here
            logger.warning("get_ingestion_status() called from async context. Use async_get_ingestion_status() instead.")
            # Return minimal status to avoid crash
            return {
                "registered_sources": list(self.sources.keys()),
                "error": "Called from async context - use async_get_ingestion_status()"
            }
        except RuntimeError:
            # No running loop, safe to create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.async_get_ingestion_status())
            finally:
                loop.close()
    
    def _extract_days_date(self, item: DataItem) -> Optional[str]:
        """Extract days_date from DataItem for calendar support"""
        try:
            # First try to use created_at if available
            if item.created_at:
                # Ensure created_at is timezone-aware (assume UTC if naive)
                if item.created_at.tzinfo is None or item.created_at.tzinfo.utcoffset(item.created_at) is None:
                    created_at_aware = item.created_at.replace(tzinfo=timezone.utc)
                else:
                    created_at_aware = item.created_at

                user_timezone = self._get_user_timezone_for_namespace(item.namespace)
                return self.database.extract_date_from_timestamp(
                    created_at_aware.isoformat(), 
                    user_timezone
                )
            
            # Fallback to extracting from metadata
            if item.metadata:
                # Parse metadata if it's a string, otherwise use as-is
                metadata_dict = item.metadata
                if isinstance(item.metadata, str):
                    from core.json_utils import JSONMetadataParser
                    metadata_dict = JSONMetadataParser.parse_metadata(item.metadata)
                
                if metadata_dict:
                    # Try different timestamp fields that might be in metadata
                    timestamp_fields = ['start_time', 'startTime', 'published_datetime_utc', 'created_at', 'timestamp', 'original_created_at']
                    
                    for field in timestamp_fields:
                        if field in metadata_dict and metadata_dict[field]:
                            # Ensure the timestamp is timezone-aware (assume UTC if naive)
                            dt_obj = None
                            try:
                                if isinstance(metadata_dict[field], datetime):
                                    dt_obj = metadata_dict[field]
                                elif isinstance(metadata_dict[field], str):
                                    # Try parsing as ISO format, assuming UTC if no timezone info
                                    if metadata_dict[field].endswith('Z'):
                                        dt_obj = datetime.fromisoformat(metadata_dict[field].replace('Z', '+00:00'))
                                    elif '+' in metadata_dict[field] or '-' in metadata_dict[field][10:]:
                                        dt_obj = datetime.fromisoformat(metadata_dict[field])
                                    else:
                                        dt_obj = datetime.fromisoformat(metadata_dict[field]).replace(tzinfo=timezone.utc)
                            except (ValueError, TypeError):
                                pass

                            if dt_obj:
                                if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
                                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                                
                                user_timezone = self._get_user_timezone_for_namespace(item.namespace)
                                extracted_date = self.database.extract_date_from_timestamp(
                                    dt_obj.isoformat(), 
                                    user_timezone
                                )
                            if extracted_date:
                                return extracted_date
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract days_date from item {item.source_id}: {e}")
            return None
    
    def _get_user_timezone_for_namespace(self, namespace: str) -> str:
        """Get user timezone configuration for a specific namespace"""
        # Use the configured user timezone for all namespaces to ensure consistent date extraction
        # This ensures days_date reflects the user's local date regardless of data source
        return self.config.limitless.timezone
    
    async def can_fetch_now(self) -> tuple[bool, int]:
        """
        Check if a fetch operation is allowed now.
        This is a compatibility method for cases where IngestionService is used as rate_limit_service.
        Always returns True, 0 since IngestionService doesn't implement rate limiting.
        """
        return True, 0

    async def record_fetch_attempt(self, success: bool = True) -> None:
        """
        Record a fetch attempt.
        This is a compatibility method for cases where IngestionService is used as rate_limit_service.
        Does nothing since IngestionService doesn't implement rate limiting.
        """
        pass

