"""
Enhanced database service with connection pooling and performance monitoring.

Extends the original DatabaseService with connection pooling, performance metrics,
and improved resource management while maintaining backward compatibility.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.database import DatabaseService
from core.database_pool import DatabasePool, PoolConfig
from core.json_utils import DatabaseRowParser, JSONMetadataParser
from core.migrations import MigrationRunner

logger = logging.getLogger(__name__)


@dataclass 
class PerformanceMetrics:
    """Performance metrics for database operations."""
    
    total_operations: int = 0
    total_operation_time: float = 0.0
    average_operation_time: float = 0.0
    fastest_operation: float = float('inf')
    slowest_operation: float = 0.0
    operations_by_type: Dict[str, int] = field(default_factory=dict)
    
    def add_operation(self, operation_type: str, duration: float):
        """Add an operation to the metrics.
        
        Args:
            operation_type: Type of operation (e.g., 'store_data_item', 'get_data_items')
            duration: Duration of operation in seconds
        """
        self.total_operations += 1
        self.total_operation_time += duration
        self.average_operation_time = self.total_operation_time / self.total_operations
        
        self.fastest_operation = min(self.fastest_operation, duration)
        self.slowest_operation = max(self.slowest_operation, duration)
        
        self.operations_by_type[operation_type] = self.operations_by_type.get(operation_type, 0) + 1


class EnhancedDatabaseService:
    """Enhanced database service with connection pooling and performance monitoring.
    
    This service provides all the functionality of the original DatabaseService
    but uses connection pooling for improved performance and resource management.
    """
    
    def __init__(self, db_path: str = "lifeboard.db", pool_config: Optional[PoolConfig] = None):
        """Initialize enhanced database service.
        
        Args:
            db_path: Path to SQLite database file
            pool_config: Configuration for connection pool
        """
        self.db_path = db_path
        self.pool_config = pool_config or PoolConfig()
        
        # Initialize connection pool
        self._pool = DatabasePool(db_path, self.pool_config)
        
        # Performance monitoring
        self._performance_metrics = PerformanceMetrics()
        
        # Initialize database (migrations)
        self._init_database()
        
        logger.info(f"ENHANCED_DB: Initialized with pool config: {self.pool_config}")

    def _init_database(self):
        """Initialize database using migration system."""
        migration_runner = MigrationRunner(self.db_path)
        result = migration_runner.run_migrations()

        if not result["success"]:
            raise RuntimeError(f"Database initialization failed: {result['errors']}")

    def _execute_with_metrics(self, operation_type: str, operation_func):
        """Execute an operation with performance metrics tracking.
        
        Args:
            operation_type: Type of operation for metrics
            operation_func: Function to execute
            
        Returns:
            Result of operation_func
        """
        start_time = time.time()
        try:
            result = operation_func()
            return result
        finally:
            duration = time.time() - start_time
            self._performance_metrics.add_operation(operation_type, duration)

    # Database connection context (for backward compatibility and direct access)
    def get_connection(self):
        """Get a database connection (for backward compatibility)."""
        return self._pool.get_connection()

    # Original DatabaseService methods with connection pooling
    
    def store_data_item(self, id: str, namespace: str, source_id: str,
                       content: str, metadata: Dict = None, days_date: str = None,
                       ingestion_status: str = "complete"):
        """Store data item with namespaced ID."""
        def _operation():
            with self._pool.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO data_items 
                    (id, namespace, source_id, content, metadata, days_date, updated_at, ingestion_status)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (id, namespace, source_id, content,
                      JSONMetadataParser.serialize_metadata(metadata), days_date, ingestion_status))
                conn.commit()
        
        return self._execute_with_metrics("store_data_item", _operation)

    def get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Batch fetch data items by namespaced IDs."""
        def _operation():
            if not ids:
                return []

            placeholders = ",".join("?" * len(ids))
            with self._pool.get_connection() as conn:
                cursor = conn.execute(f"""
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at, embedding_status
                    FROM data_items 
                    WHERE id IN ({placeholders})
                    ORDER BY updated_at DESC
                """, ids)

                return DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in cursor.fetchall()],
                )
        
        return self._execute_with_metrics("get_data_items_by_ids", _operation)

    def get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Get data items for a specific namespace."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at, embedding_status
                    FROM data_items 
                    WHERE namespace = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (namespace, limit))

                return DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in cursor.fetchall()],
                )
        
        return self._execute_with_metrics("get_data_items_by_namespace", _operation)

    def update_embedding_status(self, id: str, status: str):
        """Update embedding status for a data item."""
        def _operation():
            with self._pool.get_connection() as conn:
                conn.execute("""
                    UPDATE data_items 
                    SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, id))
                conn.commit()
        
        return self._execute_with_metrics("update_embedding_status", _operation)

    def update_ingestion_status(self, item_id: str, status: str):
        """Update ingestion status for a data item."""
        def _operation():
            with self._pool.get_connection() as conn:
                conn.execute("""
                    UPDATE data_items
                    SET ingestion_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, item_id))
                conn.commit()
        
        return self._execute_with_metrics("update_ingestion_status", _operation)

    def get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Get data items that need embedding."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, namespace, source_id, content, metadata
                    FROM data_items 
                    WHERE embedding_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,))

                return DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in cursor.fetchall()],
                )
        
        return self._execute_with_metrics("get_pending_embeddings", _operation)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get database-backed setting."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT value FROM system_settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    # Try to parse as JSON, fallback to string value
                    parsed = JSONMetadataParser.parse_metadata(row["value"])
                    return parsed if parsed is not None else row["value"]
                return default
        
        return self._execute_with_metrics("get_setting", _operation)

    def set_setting(self, key: str, value: Any):
        """Set database-backed setting."""
        def _operation():
            with self._pool.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, JSONMetadataParser.serialize_metadata(value) or value))
                conn.commit()
        
        return self._execute_with_metrics("set_setting", _operation)

    def register_data_source(self, namespace: str, source_type: str, metadata: Dict = None):
        """Register a new data source."""
        def _operation():
            with self._pool.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO data_sources 
                    (namespace, source_type, metadata, first_seen)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (namespace, source_type, JSONMetadataParser.serialize_metadata(metadata)))
                conn.commit()
        
        return self._execute_with_metrics("register_data_source", _operation)

    def get_active_namespaces(self) -> List[str]:
        """Get list of active data source namespaces."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT namespace FROM data_sources 
                    WHERE is_active = TRUE
                    ORDER BY namespace
                """)
                return [row["namespace"] for row in cursor.fetchall()]
        
        return self._execute_with_metrics("get_active_namespaces", _operation)

    def update_source_item_count(self, namespace: str):
        """Update item count for a data source."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM data_items WHERE namespace = ?
                """, (namespace,))
                count = cursor.fetchone()["count"]

                conn.execute("""
                    UPDATE data_sources 
                    SET item_count = ?
                    WHERE namespace = ?
                """, (count, namespace))
                conn.commit()

                return count
        
        return self._execute_with_metrics("update_source_item_count", _operation)

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        def _operation():
            with self._pool.get_connection() as conn:
                # Total items
                cursor = conn.execute("SELECT COUNT(*) as count FROM data_items")
                total_items = cursor.fetchone()["count"]

                # Items by namespace
                cursor = conn.execute("""
                    SELECT namespace, COUNT(*) as count 
                    FROM data_items 
                    GROUP BY namespace
                    ORDER BY count DESC
                """)
                namespace_counts = {row["namespace"]: row["count"] for row in cursor.fetchall()}

                # Embedding status
                cursor = conn.execute("""
                    SELECT embedding_status, COUNT(*) as count 
                    FROM data_items 
                    GROUP BY embedding_status
                """)
                embedding_status = {row["embedding_status"]: row["count"] for row in cursor.fetchall()}

                # Data sources
                cursor = conn.execute("SELECT COUNT(*) as count FROM data_sources WHERE is_active = TRUE")
                active_sources = cursor.fetchone()["count"]

                import os
                return {
                    "total_items": total_items,
                    "namespace_counts": namespace_counts,
                    "embedding_status": embedding_status,
                    "active_sources": active_sources,
                    "database_path": self.db_path,
                    "database_size_mb": os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0,
                }
        
        return self._execute_with_metrics("get_database_stats", _operation)

    def store_chat_message(self, user_message: str, assistant_response: str):
        """Store a chat message exchange."""
        def _operation():
            with self._pool.get_connection() as conn:
                conn.execute("""
                    INSERT INTO chat_messages (user_message, assistant_response)
                    VALUES (?, ?)
                """, (user_message, assistant_response))
                conn.commit()
        
        return self._execute_with_metrics("store_chat_message", _operation)

    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent chat history."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, user_message, assistant_response, timestamp
                    FROM chat_messages
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        "id": row["id"],
                        "user_message": row["user_message"],
                        "assistant_response": row["assistant_response"],
                        "timestamp": row["timestamp"],
                    })

                # Return in chronological order (oldest first)
                return list(reversed(messages))
        
        return self._execute_with_metrics("get_chat_history", _operation)

    # Additional methods that delegate to original DatabaseService for complex operations
    
    def extract_date_from_timestamp(self, timestamp_str: str, user_timezone: str = "UTC") -> Optional[str]:
        """Extract date string (YYYY-MM-DD) from timestamp with timezone conversion."""
        # This method doesn't need pooling as it's pure computation
        temp_service = DatabaseService()  # Temporary instance for the method
        return temp_service.extract_date_from_timestamp(timestamp_str, user_timezone)

    def get_data_items_by_date_range(self, start_date: str, end_date: str,
                                   namespaces: Optional[List[str]] = None,
                                   limit: int = 100) -> List[Dict]:
        """Get data items within a date range."""
        def _operation():
            with self._pool.get_connection() as conn:
                # Base query
                query = """
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                    FROM data_items 
                    WHERE days_date >= ? AND days_date <= ?
                """
                params = [start_date, end_date]

                # Add namespace filter if provided
                if namespaces:
                    placeholders = ",".join("?" * len(namespaces))
                    query += f" AND namespace IN ({placeholders})"
                    params.extend(namespaces)

                # Add ordering and limit
                query += " ORDER BY days_date DESC, updated_at DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)

                return DatabaseRowParser.parse_rows_with_metadata(
                    [dict(row) for row in cursor.fetchall()],
                )
        
        return self._execute_with_metrics("get_data_items_by_date_range", _operation)

    def get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Get all data items for a specific date."""
        return self.get_data_items_by_date_range(date, date, namespaces, limit=1000)

    def get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of dates that have data available."""
        def _operation():
            with self._pool.get_connection() as conn:
                query = """
                    SELECT DISTINCT days_date 
                    FROM data_items 
                    WHERE days_date IS NOT NULL
                """
                params = []

                # Add namespace filter if provided
                if namespaces:
                    placeholders = ",".join("?" * len(namespaces))
                    query += f" AND namespace IN ({placeholders})"
                    params.extend(namespaces)

                query += " ORDER BY days_date DESC"

                cursor = conn.execute(query, params)
                return [row["days_date"] for row in cursor.fetchall()]
        
        return self._execute_with_metrics("get_available_dates", _operation)

    def get_migration_status(self) -> Dict[str, Any]:
        """Get database migration status."""
        migration_runner = MigrationRunner(self.db_path)
        return migration_runner.get_migration_status()

    def get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of days that have data (for calendar indicators)."""
        def _operation():
            with self._pool.get_connection() as conn:
                query = """
                    SELECT DISTINCT days_date
                    FROM data_items
                    WHERE days_date IS NOT NULL
                """
                params = []

                if namespaces:
                    placeholders = ",".join("?" * len(namespaces))
                    query += f" AND namespace IN ({placeholders})"
                    params.extend(namespaces)

                query += " ORDER BY days_date DESC"

                logger.info(f"[CALENDAR DEBUG] Executing query: {query}")
                logger.info(f"[CALENDAR DEBUG] Query params: {params}")

                cursor = conn.execute(query, params)
                results = [row["days_date"] for row in cursor.fetchall()]

                logger.info(f"[CALENDAR DEBUG] Query returned {len(results)} results")
                logger.info(f"[CALENDAR DEBUG] First 10 results: {results[:10] if results else 'None'}")

                # Also check total count of data_items for debugging
                count_cursor = conn.execute("SELECT COUNT(*) as count FROM data_items")
                total_count = count_cursor.fetchone()["count"]
                logger.info(f"[CALENDAR DEBUG] Total data_items in database: {total_count}")

                # Check how many have days_date populated
                date_cursor = conn.execute("SELECT COUNT(*) as count FROM data_items WHERE days_date IS NOT NULL")
                date_count = date_cursor.fetchone()["count"]
                logger.info(f"[CALENDAR DEBUG] Data items with days_date populated: {date_count}")

                return results
        
        return self._execute_with_metrics("get_days_with_data", _operation)

    def get_all_namespaces(self) -> List[str]:
        """Get a list of all distinct namespaces present in the data_items table."""
        def _operation():
            with self._pool.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT DISTINCT namespace
                    FROM data_items
                    WHERE namespace IS NOT NULL
                    ORDER BY namespace
                """)
                return [row["namespace"] for row in cursor.fetchall()]
        
        return self._execute_with_metrics("get_all_namespaces", _operation)

    def get_markdown_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> str:
        """Extract and combine markdown content from metadata for a specific date."""
        # This is a complex method that we'll delegate to a temporary instance
        # for now, but could be optimized later
        def _operation():
            temp_service = DatabaseService(self.db_path)
            return temp_service.get_markdown_by_date(date, namespaces)
        
        return self._execute_with_metrics("get_markdown_by_date", _operation)

    # Enhanced functionality
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for database operations.
        
        Returns:
            Dict containing performance statistics and pool information
        """
        pool_stats = self._pool.get_stats()
        
        return {
            "total_operations": self._performance_metrics.total_operations,
            "total_operation_time": self._performance_metrics.total_operation_time,
            "average_operation_time": self._performance_metrics.average_operation_time,
            "fastest_operation": self._performance_metrics.fastest_operation if self._performance_metrics.fastest_operation != float('inf') else 0,
            "slowest_operation": self._performance_metrics.slowest_operation,
            "operations_by_type": self._performance_metrics.operations_by_type,
            "pool_stats": {
                "total_connections": pool_stats.total_connections,
                "available_connections": pool_stats.available_connections,
                "active_connections": pool_stats.active_connections,
                "total_connections_created": pool_stats.total_connections_created,
                "total_connections_closed": pool_stats.total_connections_closed,
                "health_check_failures": pool_stats.health_check_failures,
            }
        }

    def close(self):
        """Close all database connections and cleanup resources."""
        logger.info("ENHANCED_DB: Closing enhanced database service")
        self._pool.close_all_connections()

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close()
        except Exception:
            pass  # Ignore errors during cleanup