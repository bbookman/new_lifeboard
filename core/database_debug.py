"""
Database connection debug monitoring for Lifeboard cleanup.

This module provides enhanced database connection monitoring including:
- Connection lifecycle tracking
- Performance metrics collection
- Connection pool monitoring
- Query execution timing
- Connection leak detection

Usage:
    from core.database_debug import DebugDatabaseConnection
    
    db_debug = DebugDatabaseConnection("lifeboard.db")
    with db_debug.get_connection() as conn:
        # database operations
"""

import sqlite3
import time
import threading
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from core.debug_logger import DebugLogger


class ConnectionInfo:
    """Information about a database connection."""
    
    def __init__(self, connection_id: str, created_at: datetime, thread_id: str):
        self.connection_id = connection_id
        self.created_at = created_at
        self.thread_id = thread_id
        self.queries_executed = 0
        self.total_query_time = 0.0
        self.last_activity = created_at
        
    def update_activity(self, query_time: float = 0.0):
        """Update connection activity metrics."""
        self.last_activity = datetime.utcnow()
        if query_time > 0:
            self.queries_executed += 1
            self.total_query_time += query_time
            
    @property
    def age_seconds(self) -> float:
        """Get connection age in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
        
    @property
    def idle_seconds(self) -> float:
        """Get idle time in seconds."""
        return (datetime.utcnow() - self.last_activity).total_seconds()
        
    @property
    def average_query_time(self) -> float:
        """Get average query execution time."""
        return self.total_query_time / max(self.queries_executed, 1)


class DebugDatabaseConnection:
    """
    Enhanced database connection manager with comprehensive debugging.
    
    Provides connection pooling, monitoring, and debugging capabilities
    for tracking database usage during the cleanup process.
    """
    
    def __init__(self, db_path: str, pool_size: int = 5, connection_timeout: float = 30.0):
        """
        Initialize debug database connection manager.
        
        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of connections in pool
            connection_timeout: Timeout for connection operations in seconds
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.connection_timeout = connection_timeout
        
        # Debug logging
        self.debug = DebugLogger("database")
        
        # Connection tracking
        self.connection_count = 0
        self.active_connections: Dict[str, ConnectionInfo] = {}
        self.connection_pool: List[sqlite3.Connection] = []
        self.pool_lock = threading.Lock()
        
        # Performance metrics
        self.total_connections_created = 0
        self.total_queries_executed = 0
        self.total_query_time = 0.0
        self.connection_errors = 0
        
        # Initialize monitoring
        self._setup_monitoring()
        
    def _setup_monitoring(self):
        """Setup connection monitoring and health checks."""
        self.debug.log_milestone("database_monitor_initialized", {
            'db_path': self.db_path,
            'pool_size': self.pool_size,
            'connection_timeout': self.connection_timeout
        })
        
    @contextmanager
    def get_connection(self):
        """
        Get a database connection with comprehensive monitoring.
        
        Yields:
            SQLite connection object
            
        Raises:
            sqlite3.Error: If connection fails
            TimeoutError: If connection timeout exceeded
        """
        conn_id = f"conn_{self.connection_count}"
        self.connection_count += 1
        start_time = time.time()
        thread_id = str(threading.current_thread().ident)
        
        self.debug.log_state("connection_requested", {
            'connection_id': conn_id,
            'thread_id': thread_id,
            'active_connections': len(self.active_connections),
            'pool_size': len(self.connection_pool)
        })
        
        connection = None
        try:
            # Get connection from pool or create new one
            connection = self._get_pooled_connection()
            if connection is None:
                connection = self._create_new_connection()
                
            # Track connection
            conn_info = ConnectionInfo(conn_id, datetime.utcnow(), thread_id)
            self.active_connections[conn_id] = conn_info
            
            connection_time = time.time() - start_time
            
            self.debug.log_state("connection_established", {
                'connection_id': conn_id,
                'connection_time_ms': round(connection_time * 1000, 2),
                'total_active': len(self.active_connections),
                'thread_id': thread_id
            })
            
            # Wrap connection for query monitoring
            monitored_connection = self._wrap_connection_for_monitoring(
                connection, conn_id, conn_info
            )
            
            yield monitored_connection
            
        except Exception as e:
            self.connection_errors += 1
            self.debug.logger.error(f"Connection failed for {conn_id}", extra={
                'connection_id': conn_id,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'thread_id': thread_id,
                'connection_errors_total': self.connection_errors
            })
            raise
            
        finally:
            # Clean up connection
            if connection:
                self._cleanup_connection(conn_id, connection)
                
    def _get_pooled_connection(self) -> Optional[sqlite3.Connection]:
        """Get a connection from the pool if available."""
        with self.pool_lock:
            if self.connection_pool:
                return self.connection_pool.pop()
        return None
        
    def _create_new_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.connection_timeout,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            
            self.total_connections_created += 1
            
            self.debug.log_performance_metric(
                "new_connection_created", 
                self.total_connections_created, 
                "count"
            )
            
            return conn
            
        except sqlite3.Error as e:
            self.debug.logger.error(f"Failed to create connection", extra={
                'db_path': self.db_path,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise
            
    def _wrap_connection_for_monitoring(
        self, 
        connection: sqlite3.Connection, 
        conn_id: str, 
        conn_info: ConnectionInfo
    ) -> sqlite3.Connection:
        """Wrap connection to monitor query execution."""
        
        # Store original execute methods
        original_execute = connection.execute
        original_executemany = connection.executemany
        
        def monitored_execute(sql, parameters=None):
            start_time = time.time()
            try:
                result = original_execute(sql, parameters or [])
                query_time = time.time() - start_time
                
                self._log_query_execution(conn_id, sql, query_time, success=True)
                conn_info.update_activity(query_time)
                
                return result
                
            except Exception as e:
                query_time = time.time() - start_time
                self._log_query_execution(
                    conn_id, sql, query_time, success=False, error=str(e)
                )
                raise
                
        def monitored_executemany(sql, parameters):
            start_time = time.time()
            try:
                result = original_executemany(sql, parameters)
                query_time = time.time() - start_time
                
                self._log_query_execution(
                    conn_id, f"{sql} (batch: {len(parameters)} items)", 
                    query_time, success=True
                )
                conn_info.update_activity(query_time)
                
                return result
                
            except Exception as e:
                query_time = time.time() - start_time
                self._log_query_execution(
                    conn_id, f"{sql} (batch)", query_time, 
                    success=False, error=str(e)
                )
                raise
        
        # Replace execute methods
        connection.execute = monitored_execute
        connection.executemany = monitored_executemany
        
        return connection
        
    def _log_query_execution(
        self, 
        conn_id: str, 
        sql: str, 
        execution_time: float, 
        success: bool, 
        error: Optional[str] = None
    ):
        """Log query execution details."""
        self.total_queries_executed += 1
        self.total_query_time += execution_time
        
        log_data = {
            'connection_id': conn_id,
            'sql_preview': sql[:100] + "..." if len(sql) > 100 else sql,
            'execution_time_ms': round(execution_time * 1000, 2),
            'success': success,
            'total_queries': self.total_queries_executed
        }
        
        if error:
            log_data['error'] = error
            
        if success:
            self.debug.logger.debug("QUERY_EXECUTED", extra=log_data)
        else:
            self.debug.logger.error("QUERY_FAILED", extra=log_data)
            
        # Log slow queries
        if execution_time > 1.0:  # Queries taking more than 1 second
            self.debug.logger.warning("SLOW_QUERY", extra=log_data)
            
    def _cleanup_connection(self, conn_id: str, connection: sqlite3.Connection):
        """Clean up connection and update metrics."""
        start_time = time.time()
        
        try:
            # Get connection info
            conn_info = self.active_connections.pop(conn_id, None)
            
            # Return to pool if space available
            with self.pool_lock:
                if len(self.connection_pool) < self.pool_size:
                    self.connection_pool.append(connection)
                    pooled = True
                else:
                    connection.close()
                    pooled = False
                    
            cleanup_time = time.time() - start_time
            
            self.debug.log_state("connection_cleanup", {
                'connection_id': conn_id,
                'cleanup_time_ms': round(cleanup_time * 1000, 2),
                'pooled': pooled,
                'remaining_active': len(self.active_connections),
                'pool_size': len(self.connection_pool),
                'queries_executed': conn_info.queries_executed if conn_info else 0,
                'total_query_time_ms': round(
                    (conn_info.total_query_time * 1000) if conn_info else 0, 2
                ),
                'connection_age_seconds': round(
                    conn_info.age_seconds if conn_info else 0, 2
                )
            })
            
        except Exception as e:
            self.debug.logger.error(f"Connection cleanup failed", extra={
                'connection_id': conn_id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive connection statistics."""
        return {
            'active_connections': len(self.active_connections),
            'pool_size': len(self.connection_pool),
            'total_created': self.total_connections_created,
            'total_queries': self.total_queries_executed,
            'total_query_time_seconds': self.total_query_time,
            'average_query_time_ms': round(
                (self.total_query_time / max(self.total_queries_executed, 1)) * 1000, 2
            ),
            'connection_errors': self.connection_errors,
            'oldest_connection_age': max(
                (info.age_seconds for info in self.active_connections.values()),
                default=0
            ),
            'most_idle_connection': max(
                (info.idle_seconds for info in self.active_connections.values()),
                default=0
            )
        }
        
    def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                # Test basic connectivity
                conn.execute("SELECT 1").fetchone()
                
                # Check database integrity
                integrity_result = conn.execute("PRAGMA integrity_check").fetchone()
                
            health_check_time = time.time() - start_time
            
            health_status = {
                'status': 'healthy',
                'health_check_time_ms': round(health_check_time * 1000, 2),
                'integrity': integrity_result[0] if integrity_result else 'unknown',
                'stats': self.get_connection_stats()
            }
            
            self.debug.log_state("health_check_completed", health_status)
            
            return health_status
            
        except Exception as e:
            health_status = {
                'status': 'unhealthy',
                'error_type': type(e).__name__,
                'error_message': str(e),
                'stats': self.get_connection_stats()
            }
            
            self.debug.logger.error("Database health check failed", extra=health_status)
            
            return health_status
            
    def close_all_connections(self):
        """Close all connections and clean up resources."""
        self.debug.log_milestone("closing_all_connections", {
            'active_connections': len(self.active_connections),
            'pool_connections': len(self.connection_pool)
        })
        
        # Close active connections
        for conn_id in list(self.active_connections.keys()):
            self.active_connections.pop(conn_id, None)
            
        # Close pooled connections
        with self.pool_lock:
            for conn in self.connection_pool:
                try:
                    conn.close()
                except Exception as e:
                    self.debug.logger.error(f"Error closing pooled connection", extra={
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    })
            self.connection_pool.clear()
            
        self.debug.log_milestone("all_connections_closed")