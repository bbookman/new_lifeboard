import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timezone

from core.base_service import BaseService
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


class IngestionService(BaseService):
    """Service for ingesting data from various sources into the Lifeboard system"""
    
    def __init__(self,
                 database: DatabaseService,
                 vector_store: VectorStoreService,
                 embedding_service: EmbeddingService,
                 config: AppConfig):
        super().__init__(service_name="IngestionService", config=config)
        self.database = database
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        
        # Initialize processors
        self.processors: Dict[str, BaseProcessor] = {
            "limitless": LimitlessProcessor(enable_segmentation=True)
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
            
            # Unified source handling for all sources
            last_sync = self.database.get_setting(f"{namespace}_last_sync")
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
            
            async for item in source.fetch_items(since=since, limit=limit):
                await self._process_and_store_item(item, result)
            
            # Update last sync time after successful processing
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
            logger.info(f"Ingestion completed for {namespace}: {result.to_dict()}")
        
        return result
    
    async def _process_and_store_item(self, item: DataItem, result: IngestionResult):
        """Process and store a single data item"""
        try:
            result.items_processed += 1
            
            # Select the correct processor for the namespace
            processor = self.processors.get(item.namespace, self.default_processor)
            processed_item = processor.process(item)
            
            # Create namespaced ID
            namespaced_id = NamespacedIDManager.create_id(
                processed_item.namespace, 
                processed_item.source_id
            )
            
            # Extract days_date for calendar support
            days_date = self._extract_days_date(processed_item)
            
            # Store in database
            self.database.store_data_item(
                id=namespaced_id,
                namespace=processed_item.namespace,
                source_id=processed_item.source_id,
                content=processed_item.content,
                metadata=processed_item.metadata,
                days_date=days_date
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
            "processor_available": self.processor is not None,
            "healthy": True
        }
        
        try:
            # Check database connectivity
            db_stats = self.database.get_database_stats()
            health_info["database_available"] = True
            health_info["total_items"] = db_stats.get("total_items", 0)
            
            # Check vector store
            vs_stats = self.vector_store.get_stats()
            health_info["vector_store_available"] = True
            health_info["total_vectors"] = vs_stats.get("total_vectors", 0)
            
            # Check pending embeddings
            pending = len(self.database.get_pending_embeddings(limit=100))
            health_info["pending_embeddings"] = pending
            
        except Exception as e:
            health_info["healthy"] = False
            health_info["error"] = str(e)
        
        return health_info
    
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
    
    def _extract_days_date(self, item: DataItem) -> Optional[str]:
        """Extract days_date from DataItem for calendar support"""
        try:
            # First try to use created_at if available
            if item.created_at:
                # Get user timezone from config for this namespace
                user_timezone = self._get_user_timezone_for_namespace(item.namespace)
                return self.database.extract_date_from_timestamp(
                    item.created_at.isoformat(), 
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
                            user_timezone = self._get_user_timezone_for_namespace(item.namespace)
                            extracted_date = self.database.extract_date_from_timestamp(
                                str(metadata_dict[field]), 
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