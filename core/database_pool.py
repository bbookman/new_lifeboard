"""
Database connection pool implementation for SQLite with health monitoring.

Provides connection pooling, health checking, and resource management for 
improved database performance and reliability.
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Configuration for database connection pool."""
    
    max_connections: int = 10
    min_connections: int = 2
    connection_timeout: float = 30.0
    health_check_interval: float = 60.0
    enable_health_monitoring: bool = True
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.max_connections < self.min_connections:
            raise ValueError("max_connections must be >= min_connections")
        
        if self.connection_timeout <= 0:
            raise ValueError("connection_timeout must be positive")
        
        if self.health_check_interval <= 0:
            raise ValueError("health_check_interval must be positive")


@dataclass
class ConnectionStats:
    """Statistics for database connection pool."""
    
    total_connections: int = 0
    available_connections: int = 0
    active_connections: int = 0
    total_connections_created: int = 0
    total_connections_closed: int = 0
    health_check_failures: int = 0


class DatabasePool:
    """Database connection pool with health monitoring and resource management."""
    
    def __init__(self, db_path: str, config: Optional[PoolConfig] = None):
        """Initialize database connection pool.
        
        Args:
            db_path: Path to SQLite database file
            config: Pool configuration, uses defaults if None
        """
        self.db_path = db_path
        self.config = config or PoolConfig()
        
        # Thread-safe pool of connections
        self._pool: Queue[sqlite3.Connection] = Queue(maxsize=self.config.max_connections)
        self._pool_lock = threading.RLock()
        
        # Statistics tracking
        self._stats = ConnectionStats()
        self._stats_lock = threading.Lock()
        
        # Health monitoring
        self._health_monitor_executor: Optional[ThreadPoolExecutor] = None
        self._health_monitor_stop_event = threading.Event()
        
        # Initialize minimum connections
        self._initialize_pool()
        
        # Start health monitoring if enabled
        if self.config.enable_health_monitoring:
            self._start_health_monitoring()

    def _initialize_pool(self):
        """Initialize pool with minimum number of connections."""
        logger.info(f"POOL: Initializing database pool with {self.config.min_connections} connections")
        
        for _ in range(self.config.min_connections):
            try:
                conn = self._create_connection()
                self._pool.put(conn, block=False)
                
                with self._stats_lock:
                    self._stats.total_connections += 1
                    self._stats.available_connections += 1
                    self._stats.total_connections_created += 1
                    
            except Exception as e:
                logger.error(f"POOL: Failed to create initial connection: {e}")
                raise

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with proper configuration."""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.config.connection_timeout,
                check_same_thread=False  # Allow use across threads
            )
            
            # Configure connection
            conn.row_factory = sqlite3.Row
            conn.isolation_level = None  # Autocommit mode
            
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            
            logger.debug(f"POOL: Created new database connection to {self.db_path}")
            return conn
            
        except Exception as e:
            logger.error(f"POOL: Failed to create database connection: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool with automatic return.
        
        Yields:
            sqlite3.Connection: Database connection
            
        Raises:
            TimeoutError: If no connection available within timeout
        """
        conn = None
        try:
            # Try to get existing connection from pool
            try:
                conn = self._pool.get(timeout=self.config.connection_timeout)
                logger.debug("POOL: Retrieved existing connection from pool")
                
            except Empty:
                # Pool is empty, try to create new connection if under max
                with self._pool_lock:
                    current_total = self._stats.total_connections
                    if current_total < self.config.max_connections:
                        conn = self._create_connection()
                        
                        with self._stats_lock:
                            self._stats.total_connections += 1
                            self._stats.total_connections_created += 1
                            
                        logger.debug("POOL: Created new connection (pool was empty)")
                    else:
                        raise TimeoutError(
                            f"No database connections available within {self.config.connection_timeout}s timeout"
                        )
            
            # Verify connection health before use
            if not self._is_connection_healthy(conn):
                logger.warning("POOL: Connection failed health check, creating new one")
                self._close_connection(conn)
                conn = self._create_connection()
                
                with self._stats_lock:
                    self._stats.total_connections_created += 1
            
            # Update stats for active connection
            with self._stats_lock:
                self._stats.available_connections -= 1
                self._stats.active_connections += 1
            
            yield conn
            
        except Exception as e:
            logger.error(f"POOL: Error in connection context manager: {e}")
            if conn:
                self._close_connection(conn)
                conn = None
            raise
            
        finally:
            # Return connection to pool or close if unhealthy
            if conn:
                try:
                    if self._is_connection_healthy(conn):
                        self._pool.put(conn, block=False)
                        
                        with self._stats_lock:
                            self._stats.available_connections += 1
                            self._stats.active_connections -= 1
                            
                        logger.debug("POOL: Returned healthy connection to pool")
                    else:
                        logger.warning("POOL: Closing unhealthy connection")
                        self._close_connection(conn)
                        
                except Exception as e:
                    logger.error(f"POOL: Error returning connection to pool: {e}")
                    self._close_connection(conn)

    def _is_connection_healthy(self, conn: sqlite3.Connection) -> bool:
        """Check if a connection is healthy and usable.
        
        Args:
            conn: Database connection to check
            
        Returns:
            bool: True if connection is healthy
        """
        try:
            # Simple health check query
            conn.execute("SELECT 1").fetchone()
            return True
            
        except Exception as e:
            logger.debug(f"POOL: Connection health check failed: {e}")
            
            with self._stats_lock:
                self._stats.health_check_failures += 1
                
            return False

    def _close_connection(self, conn: sqlite3.Connection):
        """Close a connection and update statistics.
        
        Args:
            conn: Connection to close
        """
        try:
            conn.close()
            
            with self._stats_lock:
                self._stats.total_connections -= 1
                self._stats.total_connections_closed += 1
                
            logger.debug("POOL: Closed database connection")
            
        except Exception as e:
            logger.error(f"POOL: Error closing connection: {e}")

    def _start_health_monitoring(self):
        """Start background health monitoring task."""
        if self._health_monitor_executor is not None:
            return  # Already started
        
        self._health_monitor_executor = ThreadPoolExecutor(
            max_workers=1, 
            thread_name_prefix="db-health-monitor"
        )
        
        self._health_monitor_executor.submit(self._health_monitoring_task)
        logger.info("POOL: Started health monitoring background task")

    def _stop_health_monitoring(self):
        """Stop background health monitoring task."""
        if self._health_monitor_executor is None:
            return  # Not started
        
        self._health_monitor_stop_event.set()
        self._health_monitor_executor.shutdown(wait=True)
        self._health_monitor_executor = None
        self._health_monitor_stop_event.clear()
        
        logger.info("POOL: Stopped health monitoring background task")

    def _health_monitoring_task(self):
        """Background task for monitoring connection health."""
        logger.debug("POOL: Health monitoring task started")
        
        while not self._health_monitor_stop_event.is_set():
            try:
                self._check_pool_health()
                
                # Wait for next check interval or stop event
                self._health_monitor_stop_event.wait(self.config.health_check_interval)
                
            except Exception as e:
                logger.error(f"POOL: Error in health monitoring task: {e}")
                time.sleep(5)  # Brief pause before retrying

    def _check_pool_health(self):
        """Check health of all connections in pool."""
        logger.debug("POOL: Running health check on pool connections")
        
        unhealthy_connections = []
        healthy_connections = []
        
        # Check all available connections
        while True:
            try:
                conn = self._pool.get_nowait()
                
                if self._is_connection_healthy(conn):
                    healthy_connections.append(conn)
                else:
                    unhealthy_connections.append(conn)
                    
            except Empty:
                break  # No more connections in pool
        
        # Close unhealthy connections
        for conn in unhealthy_connections:
            self._close_connection(conn)
        
        # Return healthy connections to pool
        for conn in healthy_connections:
            try:
                self._pool.put_nowait(conn)
            except Exception as e:
                logger.error(f"POOL: Error returning healthy connection to pool: {e}")
                self._close_connection(conn)
        
        # Create replacement connections if needed
        connections_removed = len(unhealthy_connections)
        if connections_removed > 0:
            logger.info(f"POOL: Removed {connections_removed} unhealthy connections")
            
            # Ensure we maintain minimum connections
            current_available = len(healthy_connections)
            needed = max(0, self.config.min_connections - current_available)
            
            for _ in range(needed):
                try:
                    new_conn = self._create_connection()
                    self._pool.put_nowait(new_conn)
                    
                    with self._stats_lock:
                        self._stats.total_connections += 1
                        self._stats.available_connections += 1
                        self._stats.total_connections_created += 1
                        
                except Exception as e:
                    logger.error(f"POOL: Failed to create replacement connection: {e}")

    def get_stats(self) -> ConnectionStats:
        """Get current pool statistics.
        
        Returns:
            ConnectionStats: Current pool statistics
        """
        with self._stats_lock:
            # Create a copy of current stats
            return ConnectionStats(
                total_connections=self._stats.total_connections,
                available_connections=self._stats.available_connections,
                active_connections=self._stats.active_connections,
                total_connections_created=self._stats.total_connections_created,
                total_connections_closed=self._stats.total_connections_closed,
                health_check_failures=self._stats.health_check_failures
            )

    def close_all_connections(self):
        """Close all connections in the pool and stop health monitoring."""
        logger.info("POOL: Closing all connections in pool")
        
        # Stop health monitoring
        self._stop_health_monitoring()
        
        # Close all connections in pool
        closed_count = 0
        while True:
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
                closed_count += 1
                
            except Empty:
                break  # No more connections
        
        # Reset statistics
        with self._stats_lock:
            self._stats.available_connections = 0
            self._stats.active_connections = 0
            self._stats.total_connections = 0
        
        logger.info(f"POOL: Closed {closed_count} connections")

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close_all_connections()
        except Exception:
            pass  # Ignore errors during cleanup