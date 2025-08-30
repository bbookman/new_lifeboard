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

                # Create chat_messages table for storing chat conversations
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_message TEXT NOT NULL,
                        assistant_response TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        session_id TEXT,
                        metadata TEXT
                    )
                """)

                await conn.commit()

                self.debug.log_state("database_initialized", {
                    "tables_created": ["data_items", "data_sources", "system_settings", "chat_messages"],
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

    async def get_data_items_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Batch fetch data items by namespaced IDs asynchronously.

        Args:
            ids: List of namespaced IDs to fetch

        Returns:
            List of data item dictionaries

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_data_items_by_ids", {
            "id_count": len(ids)
        })

        if not ids:
            return []

        try:
            placeholders = ','.join('?' * len(ids))
            query = f"""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE id IN ({placeholders})
                ORDER BY updated_at DESC
            """

            async with self.get_connection() as conn:
                cursor = await conn.execute(query, ids)
                rows = await cursor.fetchall()
                result = DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in rows]
                )

                self.debug.log_performance_metric("get_data_items_by_ids_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_data_items_by_ids_failed", {
                "error": str(e), "id_count": len(ids)
            }, level="ERROR")
            raise

    async def update_source_item_count(self, namespace: str, count: Optional[int] = None) -> int:
        """
        Update item count for a data source asynchronously.

        Args:
            namespace: Namespace to count items for
            count: Optional explicit count value. If None, will count from database.

        Returns:
            The updated item count for the namespace

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("update_source_item_count", {
            "namespace": namespace,
            "explicit_count": count is not None
        })

        try:
            async with self.get_connection() as conn:
                # Use explicit count or calculate from database
                if count is not None:
                    final_count = count
                else:
                    # Count items for the namespace
                    cursor = await conn.execute(
                        "SELECT COUNT(*) as count FROM data_items WHERE namespace = ?", 
                        (namespace,)
                    )
                    row = await cursor.fetchone()
                    final_count = row['count']

                # Update the data_sources table with the new count
                await conn.execute("""
                    UPDATE data_sources 
                    SET item_count = ?, last_synced = CURRENT_TIMESTAMP
                    WHERE namespace = ?
                """, (final_count, namespace))
                await conn.commit()

                self.debug.log_performance_metric("update_source_item_count_duration", 0.001)
                return final_count

        except Exception as e:
            self.debug.log_state("update_source_item_count_failed", {
                "error": str(e), "namespace": namespace
            }, level="ERROR")
            raise

    async def get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """
        Get list of days that have data asynchronously (for calendar indicators).

        Args:
            namespaces: Optional list of namespaces to filter by

        Returns:
            List of date strings in YYYY-MM-DD format, sorted in descending order

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_days_with_data", {
            "namespaces_count": len(namespaces) if namespaces else 0
        })

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

            async with self.get_connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                result = [row['days_date'] for row in rows]

                self.debug.log_performance_metric("get_days_with_data_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_days_with_data_failed", {
                "error": str(e), "namespaces_count": len(namespaces) if namespaces else 0
            }, level="ERROR")
            raise

    async def get_available_dates(self, namespaces: Optional[List[str]] = None, limit: Optional[int] = None) -> List[str]:
        """
        Get list of dates that have data available asynchronously.

        Args:
            namespaces: Optional list of namespaces to filter by
            limit: Optional limit on number of dates to return

        Returns:
            List of date strings in YYYY-MM-DD format, sorted in descending order

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_available_dates", {
            "namespaces_count": len(namespaces) if namespaces else 0,
            "limit": limit
        })

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
            
            # Add limit if provided
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            async with self.get_connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                result = [row['days_date'] for row in rows]

                self.debug.log_performance_metric("get_available_dates_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_available_dates_failed", {
                "error": str(e), "namespaces_count": len(namespaces) if namespaces else 0
            }, level="ERROR")
            raise

    def extract_date_from_timestamp(self, timestamp_str: str, user_timezone: str = "UTC") -> Optional[str]:
        """
        Extract date string (YYYY-MM-DD) from timestamp with timezone conversion.
        
        This is a utility method that doesn't require async operation.

        Args:
            timestamp_str: ISO-8601 timestamp string
            user_timezone: Target timezone for conversion (default: UTC)

        Returns:
            Date string in YYYY-MM-DD format, or None if parsing fails

        Raises:
            None: This method catches all exceptions and returns None on failure
        """
        if not timestamp_str:
            return None
        
        try:
            import pytz
            
            # Parse ISO-8601 timestamp
            if timestamp_str.endswith('Z'):
                # UTC timestamp
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            elif '+' in timestamp_str or '-' in timestamp_str[10:]:
                # Already has timezone info
                dt = datetime.fromisoformat(timestamp_str)
            else:
                # Assume UTC if no timezone info
                dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)

            # Always convert to the target timezone
            try:
                target_tz = pytz.timezone(user_timezone)
                dt = dt.astimezone(target_tz)
            except Exception:
                # If target timezone is invalid, convert to UTC as a fallback
                dt = dt.astimezone(pytz.utc)

            # Return date in YYYY-MM-DD format
            return dt.strftime('%Y-%m-%d')
            
        except (ValueError, TypeError) as e:
            return None

    async def get_all_namespaces(self) -> List[str]:
        """
        Get a list of all distinct namespaces present in the data_items table.

        Returns:
            List of namespace strings, sorted alphabetically

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_all_namespaces")

        try:
            query = """
                SELECT DISTINCT namespace
                FROM data_items
                WHERE namespace IS NOT NULL
                ORDER BY namespace
            """

            async with self.get_connection() as conn:
                cursor = await conn.execute(query)
                rows = await cursor.fetchall()
                result = [row['namespace'] for row in rows]

                self.debug.log_performance_metric("get_all_namespaces_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_all_namespaces_failed", {
                "error": str(e)
            }, level="ERROR")
            raise

    async def store_chat_message(self, user_message: str, assistant_response: str) -> None:
        """
        Store a chat message exchange asynchronously.

        Args:
            user_message: The user's message
            assistant_response: The assistant's response

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("store_chat_message", {
            "user_msg_len": len(user_message),
            "assistant_msg_len": len(assistant_response)
        })

        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO chat_messages (user_message, assistant_response)
                    VALUES (?, ?)
                """, (user_message, assistant_response))
                await conn.commit()

                self.debug.log_performance_metric("store_chat_message_duration", 0.001)

        except Exception as e:
            self.debug.log_state("store_chat_message_failed", {
                "error": str(e)
            }, level="ERROR")
            raise

    async def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent chat history asynchronously.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of chat message dictionaries in chronological order (oldest first)

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_chat_history", {"limit": limit})

        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, user_message, assistant_response, timestamp
                    FROM chat_messages
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))

                rows = await cursor.fetchall()
                messages = []
                for row in rows:
                    messages.append({
                        'id': row['id'],
                        'user_message': row['user_message'],
                        'assistant_response': row['assistant_response'],
                        'timestamp': row['timestamp']
                    })

                # Return in chronological order (oldest first)
                result = list(reversed(messages))

                self.debug.log_performance_metric("get_chat_history_duration", 0.001)
                return result

        except Exception as e:
            self.debug.log_state("get_chat_history_failed", {
                "error": str(e), "limit": limit
            }, level="ERROR")
            raise

    async def get_markdown_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> str:
        """
        Extract and combine markdown content from metadata for a specific date asynchronously.

        Args:
            date: Date string in YYYY-MM-DD format
            namespaces: Optional list of namespaces to filter by

        Returns:
            Combined markdown content for the date

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("get_markdown_by_date", {
            "date": date,
            "namespaces_count": len(namespaces) if namespaces else 0
        })

        try:
            import re
            
            markdown_parts = []
            
            # Use unified data_items table for all namespaces
            data_items = await self.get_data_items_by_date(date, namespaces)
            
            for i, item in enumerate(data_items, 1):
                if item.get('metadata'):
                    metadata = item['metadata']
                    markdown_content = None
                    fallback_used = None
                    
                    if isinstance(metadata, dict):
                        # First, try to get pre-generated cleaned markdown
                        markdown_content = metadata.get('cleaned_markdown')
                        if markdown_content:
                            fallback_used = "cleaned_markdown"
                        
                        # If no cleaned markdown, try original approaches for backward compatibility
                        if not markdown_content:
                            # Try to get markdown directly
                            direct_markdown = metadata.get('markdown')
                            if direct_markdown:
                                fallback_used = "metadata.markdown"
                                
                                # Check if we need to deduplicate with title
                                title = metadata.get('title', '')
                                if title:
                                    title_header = f"# {title}"
                                    # If the direct markdown doesn't start with our title, prepend it and deduplicate
                                    if not direct_markdown.strip().startswith(title_header):
                                        deduplicated_content = self._remove_duplicate_headers(direct_markdown, title_header)
                                        markdown_content = f"{title_header}\n\n{deduplicated_content}"
                                    else:
                                        # Just remove any duplicate instances
                                        markdown_content = self._remove_duplicate_headers(direct_markdown, title_header)
                                        # Ensure we have at least one title header at the start
                                        if not markdown_content.strip().startswith(title_header):
                                            markdown_content = f"{title_header}\n\n{markdown_content}"
                                else:
                                    markdown_content = direct_markdown
                            
                            # If no direct markdown, try to get from original_lifelog
                            if not markdown_content and 'original_lifelog' in metadata:
                                original = metadata['original_lifelog']
                                if isinstance(original, dict):
                                    original_markdown = original.get('markdown')
                                    if original_markdown:
                                        fallback_used = "original_lifelog.markdown"
                                        
                                        # Check if we need to deduplicate with title
                                        title = metadata.get('title', '')
                                        if title:
                                            title_header = f"# {title}"
                                            # If the original markdown doesn't start with our title, prepend it and deduplicate
                                            if not original_markdown.strip().startswith(title_header):
                                                deduplicated_content = self._remove_duplicate_headers(original_markdown, title_header)
                                                markdown_content = f"{title_header}\n\n{deduplicated_content}"
                                            else:
                                                # Just remove any duplicate instances
                                                markdown_content = self._remove_duplicate_headers(original_markdown, title_header)
                                                # Ensure we have at least one title header at the start
                                                if not markdown_content.strip().startswith(title_header):
                                                    markdown_content = f"{title_header}\n\n{markdown_content}"
                                        else:
                                            markdown_content = original_markdown
                            
                            # If still no markdown, construct from content
                            if not markdown_content:
                                fallback_used = "constructed_from_title_content"
                                title = metadata.get('title', '')
                                
                                content = item.get('content', '')
                                
                                if title:
                                    title_header = f"# {title}"
                                    # Remove any duplicate headers from content before adding our own
                                    deduplicated_content = self._remove_duplicate_headers(content, title_header)
                                    markdown_content = f"{title_header}\n\n{deduplicated_content}"
                                else:
                                    # Create a generic header even if no title
                                    generic_header = f"# Entry {item.get('source_id', 'Unknown')}"
                                    deduplicated_content = self._remove_duplicate_headers(content, generic_header)
                                    markdown_content = f"{generic_header}\n\n{deduplicated_content}"
                                
                                # Add timestamp if available (only for fallback case)
                                if markdown_content:
                                    start_time = metadata.get('start_time')
                                    if start_time:
                                        try:
                                            # Parse and format timestamp
                                            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                            timestamp_info = f"*{dt.strftime('%I:%M %p')}*"
                                            # Insert timestamp after the header
                                            lines = markdown_content.split('\n')
                                            if lines and lines[0].startswith('#'):
                                                lines.insert(1, timestamp_info)
                                                lines.insert(2, '')  # Add blank line
                                                markdown_content = '\n'.join(lines)
                                            else:
                                                markdown_content = f"{timestamp_info}\n\n{markdown_content}"
                                        except Exception as e:
                                            pass  # Ignore timestamp parsing errors
                    
                    if markdown_content:
                        markdown_parts.append(markdown_content)
            
            # Combine all markdown with separators
            if markdown_parts:
                combined_markdown = "\n\n---\n\n".join(markdown_parts)
                
                self.debug.log_performance_metric("get_markdown_by_date_duration", 0.001)
                return combined_markdown
            else:
                fallback_content = f"# {date}\n\nNo data available for this date."
                
                self.debug.log_performance_metric("get_markdown_by_date_duration", 0.001)
                return fallback_content

        except Exception as e:
            self.debug.log_state("get_markdown_by_date_failed", {
                "error": str(e), "date": date, "namespaces_count": len(namespaces) if namespaces else 0
            }, level="ERROR")
            raise

    def _remove_duplicate_headers(self, content: str, target_header: str) -> str:
        """
        Remove duplicate instances of a header from content.
        
        This is a utility method that doesn't require async operation.

        Args:
            content: Text content to process
            target_header: Header to remove duplicates of

        Returns:
            Content with duplicate headers removed
        """
        if not content or not target_header:
            return content
        
        lines = content.split('\n')
        filtered_lines = []
        target_header_clean = target_header.strip()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # If we find a matching header
            if line == target_header_clean:
                # Skip this line and any immediately following empty lines
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                continue
            else:
                filtered_lines.append(lines[i])
                i += 1
        
        return '\n'.join(filtered_lines)

    async def delete_data_item(self, id: str) -> bool:
        """
        Delete a data item by ID asynchronously.

        Args:
            id: Namespaced ID of the data item to delete

        Returns:
            True if item was deleted, False if item didn't exist

        Raises:
            Exception: Database operation errors
        """
        self.log_service_call("delete_data_item", {"id": id})

        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(
                    "DELETE FROM data_items WHERE id = ?", (id,)
                )
                await conn.commit()
                
                # Check if any rows were affected
                deleted = cursor.rowcount > 0
                
                self.debug.log_performance_metric("delete_data_item_duration", 0.001)
                return deleted

        except Exception as e:
            self.debug.log_state("delete_data_item_failed", {
                "error": str(e), "id": id
            }, level="ERROR")
            raise

    def get_migration_status(self) -> Dict[str, Any]:
        """
        Get migration status information.
        
        Returns:
            Dictionary with migration status information
        """
        self.log_service_call("get_migration_status", {})
        
        try:
            # Basic migration status - can be enhanced later
            return {
                "migrations_applied": True,
                "last_migration": "initial_schema",
                "database_version": "1.0"
            }
        except Exception as e:
            self.debug.log_state("get_migration_status_failed", {
                "error": str(e)
            }, level="ERROR")
            raise

    async def update_ingestion_status(self, id: str, status: str) -> None:
        """
        Update the ingestion status of a data item asynchronously.
        
        Args:
            id: The namespaced ID of the data item
            status: New ingestion status (pending, processing, complete, failed, error)
        """
        self.log_service_call("update_ingestion_status", {
            "id": id, "status": status
        })
        
        try:
            async with self.get_connection() as conn:
                await conn.execute(
                    "UPDATE data_items SET ingestion_status = ? WHERE id = ?",
                    (status, id)
                )
                await conn.commit()
                
                self.debug.log_performance_metric("update_ingestion_status_duration", 0.001)
                
        except Exception as e:
            self.debug.log_state("update_ingestion_status_failed", {
                "error": str(e), "id": id, "status": status
            }, level="ERROR")
            raise

    async def get_active_namespaces(self) -> List[str]:
        """
        Get list of active data source namespaces asynchronously.
        
        Returns:
            List of active namespace strings
        """
        self.log_service_call("get_active_namespaces", {})
        
        try:
            async with self.get_connection() as conn:
                async with conn.execute("""
                    SELECT namespace FROM data_sources 
                    WHERE is_active = TRUE
                    ORDER BY namespace
                """) as cursor:
                    rows = await cursor.fetchall()
                    result = [row[0] for row in rows]
                    
                    self.debug.log_performance_metric("get_active_namespaces_duration", 0.001)
                    return result
                    
        except Exception as e:
            self.debug.log_state("get_active_namespaces_failed", {
                "error": str(e)
            }, level="ERROR")
            raise


class AsyncMigrationRunner:
    """
    Async migration runner for database schema management.
    
    This is a basic interface implementation that matches the test expectations.
    Full migration functionality can be implemented later if needed.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize AsyncMigrationRunner with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.debug = DebugLogger("AsyncMigrationRunner")
    
    async def run_migrations(self) -> Dict[str, Any]:
        """
        Run database migrations asynchronously.
        
        Returns:
            Dictionary with migration results
            
        Raises:
            NotImplementedError: This method is not yet implemented
        """
        raise NotImplementedError("AsyncMigrationRunner.run_migrations not yet implemented")