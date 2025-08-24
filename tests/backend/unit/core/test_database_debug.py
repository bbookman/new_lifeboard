"""
Tests for DebugDatabaseConnection - Database connection monitoring.

This module tests the database debug connection wrapper that provides comprehensive
logging and monitoring capabilities for database operations.
"""

import pytest
import sqlite3
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
from core.database_debug import DebugDatabaseConnection


class TestDebugDatabaseConnection:
    """Test cases for DebugDatabaseConnection functionality."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a temporary database file for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize test table
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO test_table (id, name) VALUES (1, 'test')")
            conn.commit()
            
        self.debug_db = DebugDatabaseConnection(self.db_path)
        
    def teardown_method(self):
        """Clean up after each test method."""
        # Remove temporary database file
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
            
    def test_initialization(self):
        """Test DebugDatabaseConnection initialization."""
        debug_db = DebugDatabaseConnection("/path/to/test.db")
        assert debug_db.db_path == "/path/to/test.db"
        assert debug_db.connection_count == 0
        assert len(debug_db.active_connections) == 0
        assert hasattr(debug_db, 'debug')
        
    def test_initialization_with_different_paths(self):
        """Test initialization with various database paths."""
        paths = [
            "/tmp/test1.db",
            ":memory:",
            "/var/lib/app.sqlite",
            "relative_path.db"
        ]
        
        for path in paths:
            debug_db = DebugDatabaseConnection(path)
            assert debug_db.db_path == path
            
    def test_get_connection_context_manager(self):
        """Test basic connection context manager functionality."""
        with patch.object(self.debug_db.debug, 'log_state') as mock_log:
            with self.debug_db.get_connection() as conn:
                assert conn is not None
                assert isinstance(conn, sqlite3.Connection)
                
                # Test that we can execute a query
                cursor = conn.execute("SELECT COUNT(*) FROM test_table")
                result = cursor.fetchone()
                assert result[0] == 1
                
            # Verify logging calls were made
            assert mock_log.call_count >= 2  # At least open and close
            
    def test_connection_tracking(self):
        """Test that connections are properly tracked."""
        initial_count = self.debug_db.connection_count
        
        with self.debug_db.get_connection() as conn:
            # Connection should be tracked
            assert self.debug_db.connection_count == initial_count + 1
            assert len(self.debug_db.active_connections) == 1
            
        # After context exit, active connections should be empty
        assert len(self.debug_db.active_connections) == 0
        
    def test_connection_count_increment(self):
        """Test that connection count increments properly."""
        initial_count = self.debug_db.connection_count
        
        # Open multiple connections sequentially
        for i in range(3):
            with self.debug_db.get_connection() as conn:
                assert self.debug_db.connection_count == initial_count + i + 1
                
        # Final count should be initial + 3
        assert self.debug_db.connection_count == initial_count + 3
        
    def test_multiple_concurrent_connections(self):
        """Test handling of multiple concurrent connections."""
        connections = []
        
        try:
            # Open multiple connections without closing
            for i in range(3):
                conn_context = self.debug_db.get_connection()
                conn = conn_context.__enter__()
                connections.append((conn_context, conn))
                
            # Should track all active connections
            assert len(self.debug_db.active_connections) == 3
            
        finally:
            # Clean up connections
            for conn_context, conn in connections:
                try:
                    conn_context.__exit__(None, None, None)
                except:
                    pass
                    
    def test_connection_logging_on_open(self):
        """Test that connection opening is logged properly."""
        with patch.object(self.debug_db.debug, 'log_state') as mock_log:
            with self.debug_db.get_connection() as conn:
                pass
                
            # Check that connection_open was logged
            open_calls = [call for call in mock_log.call_args_list 
                         if call[0][0] == 'connection_open']
            assert len(open_calls) >= 1
            
            # Verify log data structure
            open_call = open_calls[0]
            log_data = open_call[0][1]
            assert 'connection_id' in log_data
            assert 'total_connections' in log_data
            assert 'db_path' in log_data
            assert log_data['db_path'] == self.db_path
            
    def test_connection_logging_on_close(self):
        """Test that connection closing is logged properly."""
        with patch.object(self.debug_db.debug, 'log_state') as mock_log:
            with self.debug_db.get_connection() as conn:
                pass
                
            # Check that connection_close was logged
            close_calls = [call for call in mock_log.call_args_list 
                          if call[0][0] == 'connection_close']
            assert len(close_calls) >= 1
            
            # Verify log data structure
            close_call = close_calls[0]
            log_data = close_call[0][1]
            assert 'connection_id' in log_data
            assert 'duration_ms' in log_data
            assert 'remaining_connections' in log_data
            assert log_data['duration_ms'] >= 0
            
    def test_connection_duration_calculation(self):
        """Test that connection duration is calculated correctly."""
        with patch.object(self.debug_db.debug, 'log_state') as mock_log:
            start_time = time.time()
            
            with self.debug_db.get_connection() as conn:
                # Simulate some work
                time.sleep(0.1)
                
            end_time = time.time()
            expected_duration_ms = (end_time - start_time) * 1000
            
            # Find the close call
            close_calls = [call for call in mock_log.call_args_list 
                          if call[0][0] == 'connection_close']
            assert len(close_calls) >= 1
            
            close_call = close_calls[0]
            logged_duration = close_call[0][1]['duration_ms']
            
            # Duration should be reasonable (within 50ms of expected)
            assert abs(logged_duration - expected_duration_ms) < 50
            
    def test_connection_id_uniqueness(self):
        """Test that connection IDs are unique."""
        connection_ids = []
        
        with patch.object(self.debug_db.debug, 'log_state') as mock_log:
            # Open multiple connections
            for i in range(5):
                with self.debug_db.get_connection() as conn:
                    pass
                    
            # Extract connection IDs from open calls
            open_calls = [call for call in mock_log.call_args_list 
                         if call[0][0] == 'connection_open']
                         
            for call in open_calls:
                connection_id = call[0][1]['connection_id']
                connection_ids.append(connection_id)
                
        # All connection IDs should be unique
        assert len(connection_ids) == len(set(connection_ids))
        
    def test_row_factory_configuration(self):
        """Test that connections have row_factory configured."""
        with self.debug_db.get_connection() as conn:
            # Row factory should be set to sqlite3.Row
            assert conn.row_factory == sqlite3.Row
            
            # Test that it works
            cursor = conn.execute("SELECT id, name FROM test_table WHERE id = 1")
            row = cursor.fetchone()
            
            # Should be able to access by column name
            assert row['id'] == 1
            assert row['name'] == 'test'
            
    def test_connection_cleanup_on_exception(self):
        """Test that connections are properly cleaned up when exceptions occur."""
        initial_active_count = len(self.debug_db.active_connections)
        
        with pytest.raises(ValueError):
            with self.debug_db.get_connection() as conn:
                # Raise an exception to test cleanup
                raise ValueError("Test exception")
                
        # Active connections should be cleaned up
        assert len(self.debug_db.active_connections) == initial_active_count
        
    def test_connection_state_tracking(self):
        """Test that active connection state is tracked correctly."""
        # Initially no active connections
        assert len(self.debug_db.active_connections) == 0
        
        with self.debug_db.get_connection() as conn1:
            # One active connection
            assert len(self.debug_db.active_connections) == 1
            
            with self.debug_db.get_connection() as conn2:
                # Two active connections
                assert len(self.debug_db.active_connections) == 2
                
            # Back to one active connection
            assert len(self.debug_db.active_connections) == 1
            
        # No active connections
        assert len(self.debug_db.active_connections) == 0
        
    def test_database_file_not_exist_handling(self):
        """Test handling when database file doesn't exist."""
        non_existent_db = DebugDatabaseConnection("/path/that/does/not/exist.db")
        
        # Should be able to create connection (SQLite creates file automatically)
        with pytest.raises(sqlite3.OperationalError):
            with non_existent_db.get_connection() as conn:
                # This should fail due to path not existing
                conn.execute("SELECT 1")
                
    def test_memory_database_support(self):
        """Test support for in-memory databases."""
        memory_db = DebugDatabaseConnection(":memory:")
        
        with memory_db.get_connection() as conn:
            # Should be able to create and use tables
            conn.execute("CREATE TABLE memory_test (id INTEGER)")
            conn.execute("INSERT INTO memory_test (id) VALUES (1)")
            
            cursor = conn.execute("SELECT COUNT(*) FROM memory_test")
            result = cursor.fetchone()
            assert result[0] == 1
            
    def test_concurrent_connection_tracking(self):
        """Test connection tracking with overlapping connections."""
        with patch.object(self.debug_db.debug, 'log_state') as mock_log:
            # Start first connection
            conn1_context = self.debug_db.get_connection()
            conn1 = conn1_context.__enter__()
            
            try:
                # Start second connection while first is still active
                with self.debug_db.get_connection() as conn2:
                    # Both connections should be tracked
                    assert len(self.debug_db.active_connections) == 2
                    
                # After second connection closes, first should still be tracked
                assert len(self.debug_db.active_connections) == 1
                
            finally:
                # Clean up first connection
                conn1_context.__exit__(None, None, None)
                
            # All connections should be cleaned up
            assert len(self.debug_db.active_connections) == 0


class TestDebugDatabaseConnectionIntegration:
    """Integration tests for DebugDatabaseConnection with real database operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.debug_db = DebugDatabaseConnection(self.db_path)
        
    def teardown_method(self):
        """Clean up after tests."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
            
    def test_real_database_operations(self):
        """Test with actual database operations."""
        with self.debug_db.get_connection() as conn:
            # Create table
            conn.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT
                )
            """)
            
            # Insert data
            conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", 
                        ("John Doe", "john@example.com"))
            
            # Query data
            cursor = conn.execute("SELECT * FROM users WHERE name = ?", ("John Doe",))
            result = cursor.fetchone()
            
            assert result is not None
            assert result['name'] == "John Doe"
            assert result['email'] == "john@example.com"
            
    def test_transaction_handling(self):
        """Test database transaction handling."""
        with self.debug_db.get_connection() as conn:
            conn.execute("CREATE TABLE transactions (id INTEGER, value TEXT)")
            
            # Test successful transaction
            with conn:
                conn.execute("INSERT INTO transactions (id, value) VALUES (1, 'success')")
                
            # Verify data was committed
            cursor = conn.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 1
            
            # Test rollback on exception
            try:
                with conn:
                    conn.execute("INSERT INTO transactions (id, value) VALUES (2, 'rollback')")
                    raise ValueError("Force rollback")
            except ValueError:
                pass
                
            # Should still only have one record
            cursor = conn.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 1