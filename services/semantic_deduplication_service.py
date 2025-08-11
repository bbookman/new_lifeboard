import logging
import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from sources.base import DataItem
from sources.semantic_deduplication_processor import (
    SemanticDeduplicationProcessor, 
    SemanticCluster, 
    ProcessingResult
)
from core.database import DatabaseService
from core.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class SemanticDeduplicationService:
    """
    Pure processing engine for semantic deduplication.
    
    This service focuses solely on the core semantic processing algorithms:
    - Embedding generation and similarity calculations
    - Clustering algorithms and pattern recognition
    - Content analysis and deduplication logic
    - Results preparation for storage
    
    Note: Queue management and orchestration is handled by CleanUpCrewService
    """
    
    def __init__(self, database_service: DatabaseService, embedding_service: EmbeddingService):
        self.database = database_service
        self.embedding_service = embedding_service
        self.processor = SemanticDeduplicationProcessor(embedding_service=embedding_service)
        
        # Processing configuration
        self.default_batch_size = 50
        self.similarity_threshold = 0.85
        self.min_cluster_size = 2
        
        logger.info("Initialized SemanticDeduplicationService as pure processing engine")
    
    async def process_data_items(self, data_items: List[Dict[str, Any]]) -> ProcessingResult:
        """
        Process a list of data items for semantic deduplication.
        
        This is the core processing method that takes raw data items and returns
        semantic deduplication results. Queue management is handled externally.
        
        Args:
            data_items: List of data item dictionaries from database
            
        Returns:
            ProcessingResult with processing statistics and results
        """
        start_time = time.time()
        logger.info(f"Processing {len(data_items)} data items for semantic deduplication")
        
        try:
            if not data_items:
                return ProcessingResult(0, 0, 0, 0, [])
            
            # Convert database rows to DataItem objects
            converted_items = []
            for raw_item in data_items:
                try:
                    data_item = DataItem(
                        namespace=raw_item['namespace'],
                        source_id=raw_item['source_id'],
                        content=raw_item['content'],
                        metadata=raw_item['metadata'],
                        created_at=self._parse_datetime(raw_item.get('created_at')),
                        updated_at=self._parse_datetime(raw_item.get('updated_at'))
                    )
                    converted_items.append(data_item)
                    
                except Exception as e:
                    logger.warning(f"Error converting data item {raw_item.get('id', 'unknown')}: {e}")
                    continue
            
            if not converted_items:
                logger.warning("No valid data items after conversion")
                return ProcessingResult(0, 0, 0, 0, ["No valid items after conversion"])
            
            # Process with semantic deduplication
            processed_items = await self.processor.process_batch(converted_items)
            
            # Store results
            stored_clusters = await self._store_semantic_results(processed_items)
            
            processing_time = time.time() - start_time
            result = ProcessingResult(
                total_processed=len(converted_items),
                clusters_created=len(stored_clusters),
                processing_time=processing_time,
                items_modified=len(processed_items),
                errors=[]
            )
            
            logger.info(f"Processing completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in data items processing: {e}")
            return ProcessingResult(
                total_processed=len(data_items),
                clusters_created=0,
                processing_time=time.time() - start_time,
                items_modified=0,
                errors=[str(e)]
            )
    
    async def process_historical_conversations(self, 
                                             namespace: str = "limitless",
                                             batch_size: int = 50,
                                             max_items: Optional[int] = None) -> ProcessingResult:
        """
        Process all historical conversations for semantic deduplication
        
        Args:
            namespace: Namespace to process (default: "limitless")
            batch_size: Number of items to process per batch
            max_items: Maximum number of items to process (None for all)
            
        Returns:
            ProcessingResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Starting historical conversation processing for namespace '{namespace}'")
        
        try:
            # Fetch conversations from database
            items = await self._fetch_conversations(namespace, max_items)
            logger.info(f"Fetched {len(items)} conversations for processing")
            
            if not items:
                logger.info("No conversations found to process")
                return ProcessingResult(
                    total_processed=0,
                    clusters_created=0,
                    processing_time=time.time() - start_time,
                    items_modified=0,
                    errors=[]
                )
            
            # Process in batches
            total_clusters_created = 0
            total_items_modified = 0
            errors = []
            
            for batch_start in range(0, len(items), batch_size):
                batch_end = min(batch_start + batch_size, len(items))
                batch = items[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (len(items) + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches}: "
                           f"items {batch_start} to {batch_end-1}")
                
                try:
                    # Process batch with semantic deduplication
                    processed_batch = await self.processor.process_batch(batch)
                    
                    # Store results in database
                    batch_clusters = await self._store_semantic_results(processed_batch)
                    total_clusters_created += len(batch_clusters)
                    total_items_modified += len(processed_batch)
                    
                    logger.info(f"Batch {batch_num} completed: "
                               f"{len(batch_clusters)} clusters created, "
                               f"{len(processed_batch)} items updated")
                    
                except Exception as e:
                    error_msg = f"Error processing batch {batch_num}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Clear processor caches to free memory
            self.processor.clear_caches()
            
            processing_time = time.time() - start_time
            result = ProcessingResult(
                total_processed=len(items),
                clusters_created=total_clusters_created,
                processing_time=processing_time,
                items_modified=total_items_modified,
                errors=errors
            )
            
            logger.info(f"Historical processing completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in historical conversation processing: {e}")
            return ProcessingResult(
                total_processed=0,
                clusters_created=0,
                processing_time=time.time() - start_time,
                items_modified=0,
                errors=[str(e)]
            )
    
    async def process_incremental_conversations(self, 
                                              new_items: List[DataItem],
                                              existing_clusters: Optional[List[SemanticCluster]] = None) -> ProcessingResult:
        """
        Process new conversations against existing semantic clusters
        
        Args:
            new_items: New DataItem objects to process
            existing_clusters: Existing clusters to match against (fetched if None)
            
        Returns:
            ProcessingResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Processing {len(new_items)} new conversations incrementally")
        
        try:
            if not new_items:
                return ProcessingResult(0, 0, 0, 0, [])
            
            # Load existing clusters if not provided
            if existing_clusters is None:
                existing_clusters = await self._load_existing_clusters()
                logger.info(f"Loaded {len(existing_clusters)} existing clusters")
            
            # Process new items
            processed_items = await self.processor.process_batch(new_items)
            
            # Store results
            new_clusters = await self._store_semantic_results(processed_items)
            
            processing_time = time.time() - start_time
            result = ProcessingResult(
                total_processed=len(new_items),
                clusters_created=len(new_clusters),
                processing_time=processing_time,
                items_modified=len(processed_items),
                errors=[]
            )
            
            logger.info(f"Incremental processing completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in incremental conversation processing: {e}")
            return ProcessingResult(
                total_processed=len(new_items),
                clusters_created=0,
                processing_time=time.time() - start_time,
                items_modified=0,
                errors=[str(e)]
            )
    
    async def _fetch_conversations(self, namespace: str, max_items: Optional[int]) -> List[DataItem]:
        """Fetch conversations from database as DataItem objects"""
        
        limit = max_items or 1000  # Default reasonable limit
        raw_items = self.database.get_data_items_by_namespace(namespace, limit=limit)
        
        # Convert to DataItem objects
        data_items = []
        for raw_item in raw_items:
            try:
                # Parse the database row into a DataItem
                data_item = DataItem(
                    namespace=raw_item['namespace'],
                    source_id=raw_item['source_id'],
                    content=raw_item['content'],
                    metadata=raw_item['metadata'],  # Already parsed by DatabaseRowParser
                    created_at=self._parse_datetime(raw_item.get('created_at')),
                    updated_at=self._parse_datetime(raw_item.get('updated_at'))
                )
                data_items.append(data_item)
                
            except Exception as e:
                logger.warning(f"Error parsing database row to DataItem: {e}")
                continue
        
        return data_items
    
    async def _store_semantic_results(self, processed_items: List[DataItem]) -> List[str]:
        """Store semantic deduplication results in database"""
        
        stored_clusters = []
        
        for item in processed_items:
            try:
                # Update data_items table with new metadata
                await self._update_item_metadata(item)
                
                # Store semantic clusters
                semantic_clusters = item.metadata.get('semantic_clusters', {})
                for cluster_id, cluster_data in semantic_clusters.items():
                    if await self._store_semantic_cluster(cluster_id, cluster_data, item):
                        stored_clusters.append(cluster_id)
                
            except Exception as e:
                logger.error(f"Error storing results for item {item.source_id}: {e}")
                continue
        
        return stored_clusters
    
    async def _update_item_metadata(self, item: DataItem):
        """Update data_items table with enhanced metadata"""
        
        item_id = f"{item.namespace}:{item.source_id}"
        days_date = self._extract_days_date(item)
        
        self.database.store_data_item(
            id=item_id,
            namespace=item.namespace,
            source_id=item.source_id,
            content=item.content,
            metadata=item.metadata,
            days_date=days_date
        )
        
        logger.debug(f"Updated metadata for item {item_id}")
    
    async def _store_semantic_cluster(self, cluster_id: str, cluster_data: Dict[str, Any], 
                                    source_item: DataItem) -> bool:
        """Store a semantic cluster in the database"""
        
        try:
            # Check if cluster already exists
            if await self._cluster_exists(cluster_id):
                logger.debug(f"Cluster {cluster_id} already exists, updating")
                return await self._update_existing_cluster(cluster_id, cluster_data)
            
            # Insert new cluster
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO semantic_clusters 
                    (id, theme, canonical_line, confidence_score, frequency_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    cluster_id,
                    cluster_data['theme'],
                    cluster_data['canonical'],
                    cluster_data['confidence'],
                    cluster_data['frequency']
                ))
                
                # Store line mappings
                item_id = f"{source_item.namespace}:{source_item.source_id}"
                
                # Store canonical line
                conn.execute("""
                    INSERT INTO line_cluster_mapping 
                    (data_item_id, line_content, cluster_id, similarity_score, 
                     speaker, line_timestamp, is_canonical)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_id,
                    cluster_data['canonical'],
                    cluster_id,
                    1.0,  # Canonical has 100% similarity to itself
                    self._extract_canonical_speaker(cluster_data),
                    self._extract_canonical_timestamp(cluster_data),
                    True
                ))
                
                # Store variations
                for variation in cluster_data.get('variations', []):
                    conn.execute("""
                        INSERT INTO line_cluster_mapping 
                        (data_item_id, line_content, cluster_id, similarity_score, 
                         speaker, line_timestamp, is_canonical)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item_id,
                        variation['text'],
                        cluster_id,
                        variation['similarity'],
                        variation['speaker'],
                        variation['timestamp'],
                        False
                    ))
                
                conn.commit()
            
            logger.debug(f"Stored cluster {cluster_id} with {len(cluster_data.get('variations', []))} variations")
            return True
            
        except Exception as e:
            logger.error(f"Error storing cluster {cluster_id}: {e}")
            return False
    
    async def _cluster_exists(self, cluster_id: str) -> bool:
        """Check if a cluster already exists"""
        
        with self.database.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM semantic_clusters WHERE id = ?",
                (cluster_id,)
            )
            count = cursor.fetchone()[0]
            return count > 0
    
    async def _update_existing_cluster(self, cluster_id: str, cluster_data: Dict[str, Any]) -> bool:
        """Update an existing cluster with new data"""
        
        try:
            with self.database.get_connection() as conn:
                # Update cluster metadata
                conn.execute("""
                    UPDATE semantic_clusters 
                    SET frequency_count = ?, confidence_score = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    cluster_data['frequency'],
                    cluster_data['confidence'],
                    cluster_id
                ))
                conn.commit()
            
            logger.debug(f"Updated existing cluster {cluster_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating cluster {cluster_id}: {e}")
            return False
    
    async def _load_existing_clusters(self) -> List[SemanticCluster]:
        """Load existing semantic clusters from database"""
        
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, theme, canonical_line, confidence_score, frequency_count
                    FROM semantic_clusters
                    ORDER BY frequency_count DESC
                """)
                
                clusters = []
                for row in cursor.fetchall():
                    # Load variations for this cluster
                    variations_cursor = conn.execute("""
                        SELECT line_content, speaker, line_timestamp, similarity_score
                        FROM line_cluster_mapping
                        WHERE cluster_id = ? AND is_canonical = FALSE
                    """, (row['id'],))
                    
                    variations = []
                    for var_row in variations_cursor.fetchall():
                        from sources.semantic_deduplication_processor import LineVariation
                        variations.append(LineVariation(
                            original_text=var_row['line_content'],
                            speaker=var_row['speaker'] or "Unknown",
                            timestamp=var_row['line_timestamp'] or "",
                            conversation_id="",  # Not stored in mapping table
                            similarity_to_canonical=var_row['similarity_score'],
                            line_hash=""  # Will be generated
                        ))
                    
                    from sources.semantic_deduplication_processor import SemanticCluster
                    cluster = SemanticCluster(
                        cluster_id=row['id'],
                        theme=row['theme'],
                        canonical_line=row['canonical_line'],
                        canonical_hash="",  # Will be generated
                        variations=variations,
                        confidence_score=row['confidence_score'],
                        frequency_count=row['frequency_count']
                    )
                    clusters.append(cluster)
                
                return clusters
                
        except Exception as e:
            logger.error(f"Error loading existing clusters: {e}")
            return []
    
    async def get_cluster_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored semantic clusters"""
        
        try:
            with self.database.get_connection() as conn:
                # Basic cluster stats
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_clusters,
                        AVG(frequency_count) as avg_frequency,
                        MAX(frequency_count) as max_frequency,
                        AVG(confidence_score) as avg_confidence
                    FROM semantic_clusters
                """)
                stats = dict(cursor.fetchone())
                
                # Theme distribution
                cursor = conn.execute("""
                    SELECT theme, COUNT(*) as count
                    FROM semantic_clusters
                    GROUP BY theme
                    ORDER BY count DESC
                    LIMIT 10
                """)
                theme_distribution = [dict(row) for row in cursor.fetchall()]
                
                # Line mapping stats
                cursor = conn.execute("""
                    SELECT COUNT(*) as total_mappings
                    FROM line_cluster_mapping
                """)
                mapping_stats = dict(cursor.fetchone())
                
                return {
                    "cluster_stats": stats,
                    "theme_distribution": theme_distribution,
                    "mapping_stats": mapping_stats,
                    "generated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting cluster statistics: {e}")
            return {}
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from database"""
        if not dt_str:
            return None
        
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    
    def _extract_days_date(self, item: DataItem) -> str:
        """Extract days_date from item metadata"""
        
        # Try to get from original lifelog
        original_lifelog = item.metadata.get('original_lifelog', {})
        start_time = original_lifelog.get('startTime')
        
        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        
        # Fallback to current date
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_canonical_speaker(self, cluster_data: Dict[str, Any]) -> Optional[str]:
        """Extract speaker for canonical line from cluster data"""
        
        # Look through variations to find canonical line speaker
        canonical_text = cluster_data['canonical']
        for variation in cluster_data.get('variations', []):
            if variation['text'] == canonical_text:
                return variation['speaker']
        
        # Fallback to first variation speaker
        variations = cluster_data.get('variations', [])
        return variations[0]['speaker'] if variations else None
    
    def _extract_canonical_timestamp(self, cluster_data: Dict[str, Any]) -> Optional[str]:
        """Extract timestamp for canonical line from cluster data"""
        
        # Look through variations to find canonical line timestamp
        canonical_text = cluster_data['canonical']
        for variation in cluster_data.get('variations', []):
            if variation['text'] == canonical_text:
                return variation['timestamp']
        
        # Fallback to first variation timestamp
        variations = cluster_data.get('variations', [])
        return variations[0]['timestamp'] if variations else None