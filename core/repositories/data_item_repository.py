"""
DataItemRepository implementation for data_items table operations

This repository extracts all data_items-related operations from DatabaseService,
implementing the Repository pattern for better separation of concerns and testability.
Maintains full backward compatibility with existing code.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from contextlib import contextmanager, asynccontextmanager

from .interfaces import IDataItemRepository
from ..json_utils import JSONMetadataParser, DatabaseRowParser

logger = logging.getLogger(__name__)


class DataItemRepository(IDataItemRepository):
    """
    Concrete implementation of IDataItemRepository
    
    Handles all CRUD operations for the data_items table including:
    - Core data storage and retrieval
    - Namespace-based filtering
    - Date-based queries and calendar operations
    - Embedding and ingestion status management
    """
    
    def __init__(self, database_service):
        """
        Initialize repository with database service dependency
        
        Args:
            database_service: DatabaseService instance for connection management
        """
        self.database_service = database_service
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection via DatabaseService"""
        with self.database_service.get_connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def _get_async_connection(self):
        """Get async database connection via DatabaseService"""
        async with self.database_service.get_async_connection() as conn:
            yield conn
    
    # Core CRUD operations
    
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None, days_date: str = None,
                       ingestion_status: str = 'complete') -> None:
        """Store data item with namespaced ID"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, days_date, updated_at, ingestion_status)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (id, namespace, source_id, content, 
                  JSONMetadataParser.serialize_metadata(metadata), days_date, ingestion_status))
            conn.commit()
    
    async def async_store_data_item(self, id: str, namespace: str, source_id: str, 
                                  content: str, metadata: Dict = None, days_date: str = None,
                                  ingestion_status: str = 'complete') -> None:
        """Async version of store_data_item"""
        start_time = time.time()
        
        # Twitter-specific logging (preserved from original)
        if namespace == 'twitter':
            logger.info(f"[TWITTER TRACE] Database storage starting for Twitter item: source_id={source_id}")
            logger.info(f"[TWITTER TRACE] Twitter data details: content_length={len(content) if content else 0}, "
                       f"metadata_keys={list(metadata.keys()) if metadata else []}, days_date={days_date}")
            logger.info(f"[TWITTER TRACE] Twitter storage SQL: INSERT OR REPLACE INTO data_items with id={id}")
        
        try:
            serialized_metadata = JSONMetadataParser.serialize_metadata(metadata)
            
            if namespace == 'twitter':
                logger.info(f"[TWITTER TRACE] Twitter metadata serialization: "
                           f"original_size={len(str(metadata)) if metadata else 0}, "
                           f"serialized_size={len(serialized_metadata) if serialized_metadata else 0}")
            
            async with self._get_async_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO data_items 
                    (id, namespace, source_id, content, metadata, days_date, updated_at, ingestion_status)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (id, namespace, source_id, content, 
                      serialized_metadata, days_date, ingestion_status))
                await conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                
                if namespace == 'twitter':
                    logger.info(f"[TWITTER TRACE] Twitter data storage completed successfully in {execution_time:.2f}ms")
                    logger.info(f"[TWITTER TRACE] Twitter item stored: id={id}, source_id={source_id}, status={ingestion_status}")
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if namespace == 'twitter':
                logger.error(f"[TWITTER TRACE] Twitter data storage failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter storage error context: id={id}, source_id={source_id}, "
                            f"content_length={len(content) if content else 0}")
            logger.error(f"Error in async_store_data_item: {e}")
            raise
    
    def get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Batch fetch data items by namespaced IDs"""
        if not ids:
            return []
        
        placeholders = ','.join('?' * len(ids))
        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE id IN ({placeholders})
                ORDER BY updated_at DESC
            """, ids)
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    async def async_get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Async version of get_data_items_by_ids"""
        if not ids:
            return []
        
        try:
            placeholders = ','.join('?' * len(ids))
            async with self._get_async_connection() as conn:
                async with conn.execute(f"""
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at, embedding_status, ingestion_status
                    FROM data_items 
                    WHERE id IN ({placeholders})
                    ORDER BY updated_at DESC
                """, ids) as cursor:
                    rows = await cursor.fetchall()
                    
                    return DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
        except Exception as e:
            logger.error(f"Error in async_get_data_items_by_ids: {e}")
            raise
    
    # Namespace operations
    
    def get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Get data items for a specific namespace"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE namespace = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (namespace, limit))
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    async def async_get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Async version of get_data_items_by_namespace"""
        start_time = time.time()
        
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                    FROM data_items 
                    WHERE namespace = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (namespace, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    execution_time = (time.time() - start_time) * 1000
                    
                    parsed_rows = DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
                    
                    return parsed_rows
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Error in async_get_data_items_by_namespace: {e}")
            raise
    
    def get_all_namespaces(self) -> List[str]:
        """Get list of all distinct namespaces in data_items table"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT namespace
                FROM data_items
                WHERE namespace IS NOT NULL
                ORDER BY namespace
            """)
            return [row['namespace'] for row in cursor.fetchall()]
    
    async def async_get_all_namespaces(self) -> List[str]:
        """Async version of get_all_namespaces"""
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute("""
                    SELECT DISTINCT namespace 
                    FROM data_items 
                    ORDER BY namespace
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [row['namespace'] for row in rows]
        except Exception as e:
            logger.error(f"Error in async_get_all_namespaces: {e}")
            raise
    
    # Date-based operations
    
    def get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                   namespaces: Optional[List[str]] = None,
                                   limit: int = 100) -> List[Dict]:
        """Get data items within a date range"""
        with self._get_connection() as conn:
            # Base query
            query = """
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE days_date >= ? AND days_date <= ?
            """
            params = [start_date, end_date]
            
            # Add namespace filter if provided
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            # Add ordering and limit
            query += " ORDER BY days_date DESC, updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    async def async_get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                               namespaces: Optional[List[str]] = None,
                                               limit: int = 100) -> List[Dict]:
        """Async version of get_data_items_by_date_range"""
        start_time = time.time()
        
        # Twitter-specific logging (preserved from original)
        is_twitter_query = namespaces and 'twitter' in namespaces
        if is_twitter_query:
            logger.info(f"[TWITTER TRACE] Database date range query starting for Twitter: "
                       f"start_date={start_date}, end_date={end_date}, limit={limit}")
        
        try:
            # Base query
            query = """
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE days_date >= ? AND days_date <= ?
            """
            params = [start_date, end_date]
            
            # Add namespace filter if provided
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            # Add ordering and limit
            query += " ORDER BY days_date DESC, updated_at DESC LIMIT ?"
            params.append(limit)
            
            if is_twitter_query:
                logger.info(f"[TWITTER TRACE] Twitter date query SQL: {query}")
                logger.info(f"[TWITTER TRACE] Twitter date query params: {params}")
            
            async with self._get_async_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    execution_time = (time.time() - start_time) * 1000
                    
                    if is_twitter_query:
                        twitter_rows = [row for row in rows if dict(row).get('namespace') == 'twitter']
                        logger.info(f"[TWITTER TRACE] Twitter date query executed in {execution_time:.2f}ms")
                        logger.info(f"[TWITTER TRACE] Twitter date filtering results: total_rows={len(rows)}, "
                                   f"twitter_rows={len(twitter_rows)}")
                        
                        if twitter_rows:
                            sample_twitter = dict(twitter_rows[0])
                            logger.info(f"[TWITTER TRACE] Twitter sample from date range: "
                                       f"id={sample_twitter.get('id')}, days_date={sample_twitter.get('days_date')}")
                    
                    parsed_rows = DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
                    
                    if is_twitter_query:
                        twitter_parsed = [item for item in parsed_rows if item.get('namespace') == 'twitter']
                        logger.info(f"[TWITTER TRACE] Twitter date range parsing completed: {len(twitter_parsed)} Twitter items")
                    
                    return parsed_rows
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if is_twitter_query:
                logger.error(f"[TWITTER TRACE] Twitter date range query failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter date query error context: start_date={start_date}, "
                            f"end_date={end_date}, namespaces={namespaces}")
            logger.error(f"Error in async_get_data_items_by_date_range: {e}")
            raise
    
    def get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Get all data items for a specific date"""
        return self.get_data_items_by_date_range(date, date, namespaces, limit=1000)
    
    async def async_get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Async version of get_data_items_by_date"""
        # Twitter-specific logging (preserved from original)
        is_twitter_query = namespaces and 'twitter' in namespaces
        if is_twitter_query:
            logger.info(f"[TWITTER TRACE] Database single date query starting for Twitter: date={date}")
        
        result = await self.async_get_data_items_by_date_range(date, date, namespaces, limit=1000)
        
        if is_twitter_query:
            twitter_items = [item for item in result if item.get('namespace') == 'twitter']
            logger.info(f"[TWITTER TRACE] Twitter single date query completed: {len(twitter_items)} Twitter items for {date}")
        
        return result
    
    def get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of dates that have data available"""
        with self._get_connection() as conn:
            query = """
                SELECT DISTINCT days_date 
                FROM data_items 
                WHERE days_date IS NOT NULL
            """
            params = []
            
            # Add namespace filter if provided
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            query += " ORDER BY days_date DESC"
            
            cursor = conn.execute(query, params)
            return [row['days_date'] for row in cursor.fetchall()]
    
    async def async_get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Async version of get_available_dates"""
        try:
            query = """
                SELECT DISTINCT days_date 
                FROM data_items 
                WHERE days_date IS NOT NULL
            """
            params = []
            
            # Add namespace filter if provided
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            query += " ORDER BY days_date DESC"
            
            async with self._get_async_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [row['days_date'] for row in rows]
        except Exception as e:
            logger.error(f"Error in async_get_available_dates: {e}")
            raise
    
    def get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of days that have data (for calendar indicators)"""
        with self._get_connection() as conn:
            query = """
                SELECT DISTINCT days_date
                FROM data_items
                WHERE days_date IS NOT NULL
            """
            params = []
            
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            query += " ORDER BY days_date DESC"
            
            logger.info(f"[CALENDAR DEBUG] Executing query: {query}")
            logger.info(f"[CALENDAR DEBUG] Query params: {params}")
            
            cursor = conn.execute(query, params)
            results = [row['days_date'] for row in cursor.fetchall()]
            
            logger.info(f"[CALENDAR DEBUG] Query returned {len(results)} results")
            logger.info(f"[CALENDAR DEBUG] First 10 results: {results[:10] if results else 'None'}")
            
            # Also check total count of data_items for debugging
            count_cursor = conn.execute("SELECT COUNT(*) as count FROM data_items")
            total_count = count_cursor.fetchone()['count']
            logger.info(f"[CALENDAR DEBUG] Total data_items in database: {total_count}")
            
            # Check how many have days_date populated
            date_cursor = conn.execute("SELECT COUNT(*) as count FROM data_items WHERE days_date IS NOT NULL")
            date_count = date_cursor.fetchone()['count']
            logger.info(f"[CALENDAR DEBUG] Data items with days_date populated: {date_count}")
            
            return results
    
    async def async_get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Async version of get_days_with_data"""
        start_time = time.time()
        
        # Twitter-specific logging (preserved from original)
        is_twitter_query = namespaces and 'twitter' in namespaces
        if is_twitter_query:
            logger.info(f"[TWITTER TRACE] Database days with data query starting for Twitter")
        
        try:
            query = """
                SELECT DISTINCT days_date
                FROM data_items
                WHERE days_date IS NOT NULL
            """
            params = []
            
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            query += " ORDER BY days_date DESC"
            
            if is_twitter_query:
                logger.info(f"[TWITTER TRACE] Twitter days query SQL: {query}")
                logger.info(f"[TWITTER TRACE] Twitter days query params: {params}")
            
            async with self._get_async_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    dates = [row['days_date'] for row in rows]
                    
                    execution_time = (time.time() - start_time) * 1000
                    
                    if is_twitter_query:
                        logger.info(f"[TWITTER TRACE] Twitter days query executed in {execution_time:.2f}ms")
                        logger.info(f"[TWITTER TRACE] Twitter data integrity check: found {len(dates)} days with Twitter data")
                        if dates:
                            logger.info(f"[TWITTER TRACE] Twitter date range: {dates[-1]} to {dates[0]} ({len(dates)} days)")
                        else:
                            logger.warning(f"[TWITTER TRACE] No Twitter data found in database - potential data integrity issue")
                    
                    return dates
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if is_twitter_query:
                logger.error(f"[TWITTER TRACE] Twitter days query failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter days query error context: namespaces={namespaces}")
            logger.error(f"Error in async_get_days_with_data: {e}")
            raise
    
    # Embedding and status operations
    
    def update_embedding_status(self, id: str, status: str) -> None:
        """Update embedding status for a data item"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE data_items 
                SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, id))
            conn.commit()
    
    async def async_update_embedding_status(self, id: str, status: str) -> None:
        """Async version of update_embedding_status"""
        try:
            async with self._get_async_connection() as conn:
                await conn.execute("""
                    UPDATE data_items 
                    SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, id))
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in async_update_embedding_status: {e}")
            raise
    
    def update_ingestion_status(self, item_id: str, status: str) -> None:
        """Update ingestion status for a data item"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE data_items
                SET ingestion_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, item_id))
            conn.commit()
    
    async def async_update_ingestion_status(self, item_id: str, status: str) -> None:
        """Async version of update_ingestion_status"""
        start_time = time.time()
        
        # Check if this is a Twitter item for logging (preserved from original)
        is_twitter_item = item_id.startswith('twitter:') if item_id else False
        
        if is_twitter_item:
            logger.info(f"[TWITTER TRACE] Database ingestion status update starting: item_id={item_id}, status={status}")
        
        try:
            async with self._get_async_connection() as conn:
                await conn.execute("""
                    UPDATE data_items
                    SET ingestion_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, item_id))
                await conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                
                if is_twitter_item:
                    logger.info(f"[TWITTER TRACE] Twitter ingestion status updated in {execution_time:.2f}ms: "
                               f"item_id={item_id}, new_status={status}")
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if is_twitter_item:
                logger.error(f"[TWITTER TRACE] Twitter ingestion status update failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter status update error context: item_id={item_id}, status={status}")
            logger.error(f"Error in async_update_ingestion_status: {e}")
            raise
    
    def get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Get data items that need embedding"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata
                FROM data_items 
                WHERE embedding_status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    async def async_get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Async version of get_pending_embeddings"""
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, namespace, source_id, content, metadata
                    FROM data_items 
                    WHERE embedding_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
        except Exception as e:
            logger.error(f"Error in async_get_pending_embeddings: {e}")
            raise