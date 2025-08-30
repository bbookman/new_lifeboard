"""
AsyncDatabaseService - Asynchronous Database Operations

This module provides the async implementation of database operations using aiosqlite
to align with the application's async architecture and improve performance.

This is Phase 1 implementation - interface definition and basic structure.
Full implementation will be completed in Phase 2.
"""

import logging
import aiosqlite
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from core.debug_logger import DebugLogger
from services.debug_mixin import ServiceDebugMixin
from core.json_utils import JSONMetadataParser, DatabaseRowParser

# Add validation logging for aiosqlite DEBUG flood diagnosis
aiosqlite_logger = logging.getLogger("aiosqlite")
current_level = aiosqlite_logger.getEffectiveLevel()
logger = logging.getLogger(__name__)
logger.info(f"[DEBUG DIAGNOSIS] aiosqlite logger effective level: {logging.getLevelName(current_level)}")
logger.info(f"[DEBUG DIAGNOSIS] aiosqlite logger has handlers: {len(aiosqlite_logger.handlers)}")
if aiosqlite_logger.parent:
    logger.info(f"[DEBUG DIAGNOSIS] aiosqlite parent logger: {aiosqlite_logger.parent.name}, level: {logging.getLevelName(aiosqlite_logger.parent.getEffectiveLevel())}")


class AsyncDatabaseService(ServiceDebugMixin):
    """
    Asynchronous database service for non-blocking I/O operations.

    This service provides async/await compatible database operations using aiosqlite,
    replacing the synchronous sqlite3 operations for improved performance in async contexts.

    Phase 1: Interface definition and basic structure
    Phase 2: Full method implementation with TDD approach
    """

    def __init__(self, db_path: str = "lifeboard.db"):
        """
        Initialize AsyncDatabaseService with database path.

        Args:
            db_path: Path to SQLite database file or ":memory:" for in-memory database
        """
        super().__init__("async_database")
        self.db_path = db_path
        self.debug = DebugLogger("AsyncDatabaseService")
        self._connection_pool = None

        # Log initialization
        self.debug.log_state("initialization", {
            "db_path": db_path,
            "memory_db": db_path == ":memory:"
        })

    async def _init_database(self) -> None:
        """
        Initialize database schema and create necessary tables.

        This method creates the required database tables if they don't exist.
        It's called during the initialization process.
        """
        self.log_service_call("_init_database")

        try:
            async with self.get_connection() as conn:
                # Create data_items table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_items (
                        id TEXT PRIMARY KEY,
                        namespace TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        content TEXT,
                        metadata TEXT,
                        days_date TEXT,
                        ingestion_status TEXT DEFAULT 'pending',
                        embedding_status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for better query performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_data_items_namespace
                    ON data_items(namespace)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_data_items_days_date
                    ON data_items(days_date)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_data_items_ingestion_status
                    ON data_items(ingestion_status)
                """)

                # Create data_sources table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_sources (
                        namespace TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        metadata TEXT,
                        item_count INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        last_synced TIMESTAMP,
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create system_settings table for storing application settings
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await conn.commit()

                self.debug.log_state("database_initialized", {
                    "tables_created": ["data_items", "data_sources", "system_settings"],
                    "indexes_created": ["idx_data_items_namespace", "idx_data_items_days_date", "idx_data_items_ingestion_status"]
                })

        except Exception as e:
            self.debug.log_state("database_initialization_failed", {"error": str(e)}, level="ERROR")
            raise

    async def initialize(self) -> None:
        """
        Async initialization of database schema and setup.

        This method should be called during application startup to ensure
        the database is properly initialized before use.
        """
        self.log_service_call("initialize")

        try:
            await self._init_database()
            self.log_service_call("initialize", {"status": "completed"})
        except Exception as e:
            self.debug.log_state("initialization_failed", {"error": str(e)}, level="ERROR")
            raise

    async def close(self) -> None:
        """
        Close database connections and cleanup resources.

        This method should be called during application shutdown to ensure
        proper cleanup of database connections and resources.
        """
        self.log_service_call("close")

        try:
            # Connection pool cleanup will be implemented in Phase 2
            if self._connection_pool:
                await self._connection_pool.close_all()
            self.log_service_call("close", {"status": "completed"})
        except Exception as e:
            self.debug.log_state("close_failed", {"error": str(e)}, level="ERROR")
            raise

    @asynccontextmanager
    async def get_connection(self):
        """
        Async context manager for database connections.

        Provides a database connection with proper async context management.
        In Phase 2, this will integrate with connection pooling for better performance.

        Yields:
            aiosqlite.Connection: Async database connection
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    # Core CRUD Operations - Interface Definitions
    # Full implementations will be added in Phase 2 with TDD approach

    async def store_data_item(self, id: str, namespace: str, source_id: str,
                              content: str, metadata: Dict = None, days_date: str = None,
                              ingestion_status: str = 'complete') -> None:
        """
        Store a data item asynchronously.

        Args:
            id: Unique identifier for the data item
            namespace: Namespace for data isolation
            source_id: Source-specific identifier
            content: Text content of the item
            metadata: Optional metadata dictionary
            days_date: Date string in YYYY-MM-DD format
            ingestion_status: Status of ingestion process

        Raises:
            Exception: Database operation errors
        """
        # Add frequency tracking for DEBUG flood diagnosis
        if not hasattr(self, '_store_call_count'):
            self._store_call_count = 0
        self._store_call_count += 1

        logger.info(f"[DEBUG DIAGNOSIS] store_data_item call #{self._store_call_count} for namespace: {namespace}, id: {id}")

        self.log_service_call("store_data_item", {
            "namespace": namespace,
            "ingestion_status": ingestion_status,
            "has_metadata": metadata is not None
        })

        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO data_items
                    (id, namespace, source_id, content, metadata, days_date, ingestion_status, embedding_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (id, namespace, source_id, content,
                      JSONMetadataParser.serialize_metadata(metadata), days_date, ingestion_status, 'pending'))
                await conn.commit()

                self.debug.log_performance_metric("store_data_item_duration", 0.001)

        except Exception as e:
            self.debug.log_state("store_data_item_failed", {
                "error": str(e), "id": id, "namespace": namespace
            }, level="ERROR")
            raise

    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Async method for fetching one row from database.

        Args:
            query: SQL query string
            params: Query parameters tuple

        Returns:
            Dictionary representing the row, or None if no results
        """
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(query, params or ())
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error in fetch_one: {e}")
            raise

    async def execute_query(self, query: str, params: tuple = None) -> None:
        """
        Async method for executing a query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            params: Query parameters tuple
        """
        try:
            async with self.get_connection() as conn:
                await conn.execute(query, params or ())
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in execute_query: {e}")
            raise

    # Data Source Management - Interface Definitions

    async def register_data_source(self, namespace: str, source_type: str,
                                   metadata: Dict = None) -> None:
        """
        Register a data source asynchronously.

        Args:
            namespace: Unique namespace for the data source
            source_type: Type of data source
            metadata: Optional metadata dictionary

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("register_data_source", {
            "namespace": namespace, "source_type": source_type
        })

        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO data_sources
                    (namespace, source_type, metadata, first_seen)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (namespace, source_type, JSONMetadataParser.serialize_metadata(metadata)))
                await conn.commit()

                self.debug.log_performance_metric("register_data_source_duration", 0.001)

        except Exception as e:
            self.debug.log_state("register_data_source_failed", {
                "error": str(e), "namespace": namespace, "source_type": source_type
            }, level="ERROR")
            raise

    async def get_data_items_by_date(self, date: str, namespaces: List[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve data items by date asynchronously.

        Args:
            date: Date string in YYYY-MM-DD format
            namespaces: Optional list of namespaces to filter by

        Returns:
            List of data item dictionaries

        Raises:
            Exception: Database operation errors
        """
        return await self.get_data_items_by_date_range(date, date, namespaces, limit=1000)

    async def get_data_items_by_date_range(self, start_date: str, end_date: str,
                                           namespaces: List[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve data items within a date range asynchronously.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            namespaces: Optional list of namespaces to filter by
            limit: Maximum number of items to return

        Returns:
            List of data item dictionaries

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_data_items_by_date_range", {
            "start_date": start_date, "end_date": end_date,
            "namespaces_count": len(namespaces) if namespaces else 0, "limit": limit
        })

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

            async with self.get_connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                result = DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in rows]
                )

                self.debug.log_performance_metric("get_data_items_by_date_range_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_data_items_by_date_range_failed", {
                "error": str(e), "start_date": start_date, "end_date": end_date
            }, level="ERROR")
            raise

    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics asynchronously.

        Returns:
            Dictionary containing database statistics

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_database_stats")

        try:
            async with self.get_connection() as conn:
                # Total items
                cursor = await conn.execute("SELECT COUNT(*) as count FROM data_items")
                row = await cursor.fetchone()
                total_items = row['count']

                # Items by namespace
                cursor = await conn.execute("""
                    SELECT namespace, COUNT(*) as count
                    FROM data_items
                    GROUP BY namespace
                    ORDER BY count DESC
                """)
                rows = await cursor.fetchall()
                namespace_counts = {row['namespace']: row['count'] for row in rows}

                # Embedding status
                cursor = await conn.execute("""
                    SELECT embedding_status, COUNT(*) as count
                    FROM data_items
                    GROUP BY embedding_status
                """)
                rows = await cursor.fetchall()
                embedding_status = {row['embedding_status']: row['count'] for row in rows}

                # Data sources
                cursor = await conn.execute("SELECT COUNT(*) as count FROM data_sources WHERE is_active = TRUE")
                row = await cursor.fetchone()
                active_sources = row['count']

                result = {
                    'total_items': total_items,
                    'namespace_counts': namespace_counts,
                    'embedding_status': embedding_status,
                    'active_sources': active_sources,
                    'database_path': self.db_path,
                    'database_size_mb': Path(self.db_path).stat().st_size / (1024 * 1024) if Path(self.db_path).exists() else 0
                }

                self.debug.log_performance_metric("get_database_stats_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_database_stats_failed", {
                "error": str(e)
            }, level="ERROR")
            raise

    async def get_pending_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get data items that need embedding asynchronously.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of data item dictionaries with pending embeddings

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_pending_embeddings", {"limit": limit})

        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, namespace, source_id, content, metadata
                    FROM data_items
                    WHERE embedding_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,))

                rows = await cursor.fetchall()
                result = DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in rows]
                )

                self.debug.log_performance_metric("get_pending_embeddings_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_pending_embeddings_failed", {
                "error": str(e), "limit": limit
            }, level="ERROR")
            raise

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get database-backed setting asynchronously.

        Args:
            key: Setting key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The setting value, or default if not found

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_setting", {"key": key, "has_default": default is not None})

        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT value FROM system_settings WHERE key = ?", (key,))
                row = await cursor.fetchone()
                if row:
                    # Try to parse as JSON, fallback to string value
                    parsed = JSONMetadataParser.parse_metadata(row['value'])
                    result = parsed if parsed is not None else row['value']
                    self.debug.log_performance_metric("get_setting_duration", 0.001)
                    return result
                return default

        except Exception as e:
            self.debug.log_state("get_setting_failed", {
                "error": str(e), "key": key
            }, level="ERROR")
            raise

    async def set_setting(self, key: str, value: Any):
        """
        Set database-backed setting asynchronously.

        Args:
            key: Setting key to store
            value: Value to store (will be JSON serialized if complex)

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("set_setting", {
            "key": key, "value_type": type(value).__name__
        })

        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, JSONMetadataParser.serialize_metadata(value) or value))
                await conn.commit()

                self.debug.log_performance_metric("set_setting_duration", 0.001)

        except Exception as e:
            self.debug.log_state("set_setting_failed", {
                "error": str(e), "key": key, "value_type": type(value).__name__
            }, level="ERROR")
    async def update_embedding_status(self, id: str, status: str) -> None:
        """
        Update embedding status for a data item asynchronously.

        Args:
            id: ID of the data item to update
            status: New embedding status

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("update_embedding_status", {"id": id, "status": status})

        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE data_items
                    SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, id))
                await conn.commit()

                self.debug.log_performance_metric("update_embedding_status_duration", 0.001)

        except Exception as e:
            self.debug.log_state("update_embedding_status_failed", {
                "error": str(e), "id": id, "status": status
            }, level="ERROR")
            raise

    async def get_data_items_by_namespace(self, namespace: str, limit: Optional[int] = None,
                                          offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve data items by namespace asynchronously.

        Args:
            namespace: Namespace to filter by
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of data item dictionaries

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_data_items_by_namespace", {
            "namespace": namespace, "limit": limit, "offset": offset
        })

        try:
            query = """
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items
                WHERE namespace = ?
                ORDER BY updated_at DESC
            """
            params = [namespace]

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            if offset > 0:
                query += " OFFSET ?"
                params.append(offset)

            async with self.get_connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                result = DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in rows]
                )

                self.debug.log_performance_metric("get_data_items_by_namespace_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_data_items_by_namespace_failed", {
                "error": str(e), "namespace": namespace
            }, level="ERROR")
            raise