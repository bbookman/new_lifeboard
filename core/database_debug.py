"""
Database Debug Connection for Enhanced Database Monitoring.

This module provides the DebugDatabaseConnection class that wraps database
connections with comprehensive logging and monitoring capabilities.
"""

import sqlite3
import time
from contextlib import contextmanager
from typing import Dict, Any
from core.debug_logger import DebugLogger


class DebugDatabaseConnection:
    """
    Debug wrapper for database connections with comprehensive monitoring.
    
    This class provides enhanced database connection management with:
    - Connection lifecycle tracking
    - Connection duration monitoring
    - Active connection counting
    - Detailed logging for debugging
    - Proper resource cleanup
    
    Usage:
        debug_db = DebugDatabaseConnection("path/to/database.db")
        
        with debug_db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the debug database connection wrapper.
        
        Args:
            db_path: Path to the SQLite database file or ":memory:" for in-memory DB
        """
        self.db_path = db_path
        self.debug = DebugLogger("database")
        self.connection_count = 0
        self.active_connections: Dict[str, float] = {}
        
    @contextmanager
    def get_connection(self):
        """
        Context manager to get a database connection with debug monitoring.
        
        Provides:
        - Automatic connection management
        - Connection duration tracking
        - Active connection monitoring  
        - Proper cleanup on exit
        - Row factory configuration
        
        Yields:
            sqlite3.Connection: Database connection with row factory configured
            
        Example:
            with debug_db.get_connection() as conn:
                cursor = conn.execute("SELECT id, name FROM users")
                for row in cursor:
                    print(row['name'])  # Access by column name
        """
        # Generate unique connection ID
        conn_id = f"conn_{self.connection_count}"
        self.connection_count += 1
        start_time = time.time()
        
        # Log connection opening
        self.debug.log_state("connection_open", {
            'connection_id': conn_id,
            'total_connections': len(self.active_connections) + 1,
            'db_path': self.db_path,
            'connection_count': self.connection_count
        })
        
        # Create connection and configure
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column name access
        
        # Track active connection
        self.active_connections[conn_id] = start_time
        
        try:
            yield conn
        finally:
            # Calculate connection duration
            duration = time.time() - start_time
            
            # Log connection closing
            self.debug.log_state("connection_close", {
                'connection_id': conn_id,
                'duration_ms': round(duration * 1000, 2),
                'remaining_connections': len(self.active_connections) - 1,
                'db_path': self.db_path
            })
            
            # Clean up tracking
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]
                
            # Close connection
            conn.close()
            
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get current connection statistics.
        
        Returns:
            Dictionary containing connection statistics including:
            - total_connections_created: Total connections created since initialization
            - active_connections_count: Currently active connections
            - active_connection_ids: List of active connection IDs
            - db_path: Database file path
        """
        stats = {
            'total_connections_created': self.connection_count,
            'active_connections_count': len(self.active_connections),
            'active_connection_ids': list(self.active_connections.keys()),
            'db_path': self.db_path,
            'timestamp': time.time()
        }
        
        # Log statistics request
        self.debug.log_state("connection_stats", stats, "INFO")
        
        return stats
        
    def get_active_connection_durations(self) -> Dict[str, float]:
        """
        Get the duration of all currently active connections.
        
        Returns:
            Dictionary mapping connection IDs to their duration in milliseconds
        """
        current_time = time.time()
        durations = {}
        
        for conn_id, start_time in self.active_connections.items():
            duration_ms = round((current_time - start_time) * 1000, 2)
            durations[conn_id] = duration_ms
            
        # Log active connection durations
        self.debug.log_state("active_connection_durations", {
            'active_count': len(durations),
            'durations': durations,
            'timestamp': current_time
        }, "DEBUG")
        
        return durations
        
    def log_connection_health(self) -> Dict[str, Any]:
        """
        Log and return connection health information.
        
        Returns:
            Dictionary containing health metrics for database connections
        """
        current_time = time.time()
        active_durations = self.get_active_connection_durations()
        
        # Calculate health metrics
        health_data = {
            'status': 'healthy' if len(self.active_connections) < 10 else 'warning',
            'total_connections_created': self.connection_count,
            'active_connections': len(self.active_connections),
            'longest_active_duration_ms': max(active_durations.values()) if active_durations else 0,
            'average_active_duration_ms': (
                round(sum(active_durations.values()) / len(active_durations), 2) 
                if active_durations else 0
            ),
            'db_path': self.db_path,
            'timestamp': current_time
        }
        
        # Add warning if too many active connections
        if len(self.active_connections) >= 10:
            health_data['warning'] = f"High number of active connections: {len(self.active_connections)}"
            
        # Add warning for long-running connections (>30 seconds)
        long_running = [conn_id for conn_id, duration in active_durations.items() if duration > 30000]
        if long_running:
            health_data['long_running_connections'] = long_running
            
        # Log health check
        log_level = "WARNING" if health_data['status'] != 'healthy' else "INFO"
        self.debug.log_state("connection_health", health_data, log_level)
        
        return health_data
        
    def close_all_connections(self) -> int:
        """
        Emergency method to close all tracked connections.
        
        Note: This method cannot actually close the connections since they're 
        managed by context managers, but it can reset the tracking state.
        
        Returns:
            Number of connections that were being tracked
        """
        active_count = len(self.active_connections)
        
        self.debug.log_state("emergency_connection_cleanup", {
            'active_connections_cleared': active_count,
            'connection_ids': list(self.active_connections.keys()),
            'timestamp': time.time()
        }, "WARNING")
        
        # Clear tracking (actual connections will be closed by their context managers)
        self.active_connections.clear()
        
        return active_count
        
    def __repr__(self) -> str:
        """String representation of the debug database connection."""
        return (f"DebugDatabaseConnection(db_path='{self.db_path}', "
                f"total_created={self.connection_count}, "
                f"active={len(self.active_connections)})")


# Convenience functions for common database patterns
@contextmanager
def debug_database_transaction(debug_db: DebugDatabaseConnection):
    """
    Context manager for database transactions with debug monitoring.
    
    Args:
        debug_db: DebugDatabaseConnection instance
        
    Yields:
        sqlite3.Connection: Database connection with transaction management
        
    Example:
        with debug_database_transaction(debug_db) as conn:
            conn.execute("INSERT INTO users (name) VALUES (?)", ("John",))
            conn.execute("UPDATE users SET status = 'active' WHERE name = ?", ("John",))
            # Transaction automatically committed on success, rolled back on error
    """
    with debug_db.get_connection() as conn:
        try:
            yield conn
            conn.commit()
            debug_db.debug.log_state("transaction_committed", {
                'db_path': debug_db.db_path,
                'timestamp': time.time()
            }, "INFO")
        except Exception as e:
            conn.rollback()
            debug_db.debug.log_state("transaction_rolled_back", {
                'db_path': debug_db.db_path,
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': time.time()
            }, "WARNING")
            raise


def execute_with_debug_timing(debug_db: DebugDatabaseConnection, query: str, params=None):
    """
    Execute a query with debug timing information.
    
    Args:
        debug_db: DebugDatabaseConnection instance
        query: SQL query to execute
        params: Optional query parameters
        
    Returns:
        Query results as a list of Row objects
    """
    start_time = time.time()
    
    with debug_db.get_connection() as conn:
        cursor = conn.execute(query, params or ())
        results = cursor.fetchall()
        
    execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    # Log query execution
    debug_db.debug.log_state("query_executed", {
        'query': query[:100] + "..." if len(query) > 100 else query,  # Truncate long queries
        'params_count': len(params) if params else 0,
        'result_count': len(results),
        'execution_time_ms': round(execution_time, 2),
        'db_path': debug_db.db_path,
        'timestamp': time.time()
    }, "DEBUG")
    
    return results


# Example usage and integration patterns
class ExampleDatabaseService:
    """Example service showing how to integrate DebugDatabaseConnection."""
    
    def __init__(self, db_path: str):
        self.debug_db = DebugDatabaseConnection(db_path)
        
    def get_user_by_id(self, user_id: int):
        """Example method using debug database connection."""
        with self.debug_db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return cursor.fetchone()
            
    def create_user(self, name: str, email: str):
        """Example method using transaction with debug monitoring."""
        with debug_database_transaction(self.debug_db) as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email) VALUES (?, ?) RETURNING id",
                (name, email)
            )
            return cursor.fetchone()['id']
            
    def get_database_health(self):
        """Get database connection health metrics."""
        return self.debug_db.log_connection_health()