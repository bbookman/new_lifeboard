"""
DataSourceRepository implementation for data_sources table operations

This repository extracts all data source-related operations from DatabaseService,
implementing the Repository pattern for better separation of concerns and testability.
Maintains full backward compatibility with existing code.
"""

import logging
from typing import List, Dict
from contextlib import contextmanager, asynccontextmanager

from .interfaces import IDataSourceRepository
from ..json_utils import JSONMetadataParser

logger = logging.getLogger(__name__)


class DataSourceRepository(IDataSourceRepository):
    """
    Concrete implementation of IDataSourceRepository
    
    Handles all CRUD operations for the data_sources table including:
    - Data source registration and metadata management
    - Active namespace tracking and retrieval  
    - Item count updates and statistics
    - Both sync and async operations for all functionality
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
    
    def register_data_source(self, namespace: str, source_type: str, metadata: Dict = None) -> None:
        """Register a new data source"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_sources 
                (namespace, source_type, metadata, first_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (namespace, source_type, JSONMetadataParser.serialize_metadata(metadata)))
            conn.commit()
    
    async def async_register_data_source(self, namespace: str, source_type: str, metadata: Dict = None) -> None:
        """Async version of register_data_source"""
        try:
            async with self._get_async_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO data_sources 
                    (namespace, source_type, metadata, first_seen)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (namespace, source_type, JSONMetadataParser.serialize_metadata(metadata)))
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Error in async_register_data_source: {e}")
            raise
    
    def get_active_namespaces(self) -> List[str]:
        """Get list of active data source namespaces"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT namespace FROM data_sources 
                WHERE is_active = TRUE
                ORDER BY namespace
            """)
            return [row['namespace'] for row in cursor.fetchall()]
    
    async def async_get_active_namespaces(self) -> List[str]:
        """Async version of get_active_namespaces"""
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute("""
                    SELECT namespace FROM data_sources 
                    WHERE is_active = TRUE
                    ORDER BY namespace
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [row['namespace'] for row in rows]
        except Exception as e:
            self.logger.error(f"Error in async_get_active_namespaces: {e}")
            raise
    
    def update_source_item_count(self, namespace: str) -> int:
        """Update item count for a data source, returns new count"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM data_items WHERE namespace = ?
            """, (namespace,))
            count = cursor.fetchone()['count']
            
            conn.execute("""
                UPDATE data_sources 
                SET item_count = ?
                WHERE namespace = ?
            """, (count, namespace))
            conn.commit()
            
            return count
    
    async def async_update_source_item_count(self, namespace: str) -> int:
        """Async version of update_source_item_count"""
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute("""
                    SELECT COUNT(*) as count FROM data_items WHERE namespace = ?
                """, (namespace,)) as cursor:
                    count_row = await cursor.fetchone()
                    count = count_row['count']
                
                await conn.execute("""
                    UPDATE data_sources 
                    SET item_count = ?
                    WHERE namespace = ?
                """, (count, namespace))
                await conn.commit()
                
                return count
        except Exception as e:
            self.logger.error(f"Error in async_update_source_item_count: {e}")
            raise