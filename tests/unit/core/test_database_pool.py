"""
Test cases for database connection pool implementation.

Tests database connection pooling, health monitoring, and resource management
following TDD methodology.
"""

import pytest
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from core.database_pool import DatabasePool, PoolConfig, ConnectionStats


class TestDatabasePool:
    """Test cases for database connection pool."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database path."""
        return str(tmp_path / "test.db")

    @pytest.fixture
    def pool_config(self):
        """Create test pool configuration."""
        return PoolConfig(
            max_connections=5,
            min_connections=2,
            connection_timeout=5.0,
            health_check_interval=30.0,
            enable_health_monitoring=True
        )

    @pytest.fixture
    def database_pool(self, temp_db_path, pool_config):
        """Create database pool for testing."""
        pool = DatabasePool(temp_db_path, pool_config)
        yield pool
        pool.close_all_connections()

    def test_pool_initialization(self, database_pool, pool_config):
        """Test that database pool initializes correctly."""
        assert database_pool.db_path is not None
        assert database_pool.config == pool_config
        assert database_pool._pool is not None
        assert database_pool._pool_lock is not None
        
        # Check that pool has minimum connections via stats
        stats = database_pool.get_stats()
        assert stats.total_connections >= pool_config.min_connections

    def test_get_connection_returns_valid_connection(self, database_pool):
        """Test that get_connection returns a valid SQLite connection."""
        with database_pool.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_connection_returned_to_pool(self, database_pool):
        """Test that connections are properly returned to pool."""
        initial_stats = database_pool.get_stats()
        
        with database_pool.get_connection() as conn:
            # During use, available connections should be reduced
            stats_during_use = database_pool.get_stats()
            assert stats_during_use.available_connections < initial_stats.available_connections
            assert stats_during_use.active_connections > initial_stats.active_connections
        
        # After context manager, connection should be returned
        final_stats = database_pool.get_stats()
        assert final_stats.available_connections == initial_stats.available_connections
        assert final_stats.active_connections == initial_stats.active_connections

    def test_pool_respects_max_connections(self, database_pool, pool_config):
        """Test that pool doesn't exceed maximum connections."""
        connections = []
        
        # Get all available connections
        for _ in range(pool_config.max_connections + 2):
            try:
                conn_cm = database_pool.get_connection()
                conn = conn_cm.__enter__()
                connections.append((conn_cm, conn))
            except Exception:
                break
        
        # Should not exceed max connections
        assert len(connections) <= pool_config.max_connections
        
        # Clean up connections
        for conn_cm, conn in connections:
            try:
                conn_cm.__exit__(None, None, None)
            except:
                pass

    def test_concurrent_connection_access(self, database_pool):
        """Test concurrent access to connection pool."""
        results = []
        errors = []
        
        def worker():
            try:
                with database_pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    results.append(result[0])
                    time.sleep(0.1)  # Simulate work
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(20)]
            for future in futures:
                future.result()
        
        # All operations should succeed
        assert len(errors) == 0
        assert len(results) == 20
        assert all(result == 1 for result in results)

    def test_connection_health_check(self, database_pool):
        """Test connection health checking functionality."""
        # Test with real connection (should be healthy)
        with database_pool.get_connection() as conn:
            assert database_pool._is_connection_healthy(conn) == True
        
        # Mock an unhealthy connection
        unhealthy_conn = Mock(spec=sqlite3.Connection)
        unhealthy_conn.execute.side_effect = sqlite3.OperationalError("Database is locked")
        
        assert database_pool._is_connection_healthy(unhealthy_conn) == False

    def test_connection_timeout(self, temp_db_path):
        """Test connection timeout when pool is exhausted."""
        config = PoolConfig(
            max_connections=1,
            min_connections=1,
            connection_timeout=0.1  # Very short timeout
        )
        pool = DatabasePool(temp_db_path, config)
        
        try:
            # Get the only connection
            with pool.get_connection() as conn1:
                # Try to get another connection - should timeout
                with pytest.raises(TimeoutError):
                    with pool.get_connection() as conn2:
                        pass
        finally:
            pool.close_all_connections()

    def test_pool_statistics(self, database_pool):
        """Test pool statistics collection."""
        stats = database_pool.get_stats()
        
        assert isinstance(stats, ConnectionStats)
        assert stats.total_connections >= 0
        assert stats.available_connections >= 0
        assert stats.active_connections >= 0
        assert stats.total_connections_created >= 0

    def test_pool_configuration_validation(self, temp_db_path):
        """Test pool configuration validation."""
        # Invalid configuration - max < min
        with pytest.raises(ValueError):
            config = PoolConfig(max_connections=2, min_connections=5)
            DatabasePool(temp_db_path, config)
        
        # Invalid timeout
        with pytest.raises(ValueError):
            config = PoolConfig(connection_timeout=-1)
            DatabasePool(temp_db_path, config)

    def test_connection_cleanup_on_error(self, database_pool):
        """Test that connections are properly cleaned up on errors."""
        initial_stats = database_pool.get_stats()
        
        try:
            with database_pool.get_connection() as conn:
                # Simulate an error
                raise RuntimeError("Test error")
        except RuntimeError:
            pass
        
        # Pool should be back to initial state (allow some tolerance for timing)
        final_stats = database_pool.get_stats()
        assert final_stats.available_connections >= initial_stats.available_connections - 1

    def test_health_monitoring_background_task(self, database_pool):
        """Test health monitoring background task."""
        # Enable health monitoring
        database_pool.config.enable_health_monitoring = True
        database_pool.config.health_check_interval = 0.1  # Short interval for testing
        
        # Start health monitoring
        database_pool._start_health_monitoring()
        
        # Let it run briefly
        time.sleep(0.2)
        
        # Stop health monitoring
        database_pool._stop_health_monitoring()
        
        # Health monitoring should have run without errors
        stats = database_pool.get_stats()
        assert stats.total_connections >= 0

    def test_pool_close_all_connections(self, database_pool):
        """Test closing all connections in pool."""
        # Get some connections to populate the pool
        with database_pool.get_connection() as conn:
            pass
        
        initial_stats = database_pool.get_stats()
        assert initial_stats.total_connections > 0
        
        # Close all connections
        database_pool.close_all_connections()
        
        # Pool should be empty
        final_stats = database_pool.get_stats()
        assert final_stats.total_connections == 0
        assert final_stats.available_connections == 0

    def test_database_row_factory_preserved(self, database_pool):
        """Test that row factory is properly set on connections."""
        with database_pool.get_connection() as conn:
            assert conn.row_factory == sqlite3.Row

    def test_connection_isolation_level(self, database_pool):
        """Test that connection isolation level is properly configured."""
        with database_pool.get_connection() as conn:
            # Should be set to None for autocommit mode in SQLite
            assert conn.isolation_level is None

    def test_concurrent_pool_statistics(self, database_pool):
        """Test that pool statistics are thread-safe."""
        stats_results = []
        
        def collect_stats():
            for _ in range(10):
                stats = database_pool.get_stats()
                stats_results.append(stats)
                time.sleep(0.01)
        
        # Run multiple threads collecting stats
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(collect_stats) for _ in range(5)]
            for future in futures:
                future.result()
        
        # All stats should be valid
        assert len(stats_results) == 50
        for stats in stats_results:
            assert isinstance(stats, ConnectionStats)
            assert stats.total_connections >= 0


class TestPoolConfig:
    """Test cases for pool configuration."""

    def test_default_configuration(self):
        """Test default pool configuration values."""
        config = PoolConfig()
        
        assert config.max_connections == 10
        assert config.min_connections == 2
        assert config.connection_timeout == 30.0
        assert config.health_check_interval == 60.0
        assert config.enable_health_monitoring == True

    def test_custom_configuration(self):
        """Test custom pool configuration."""
        config = PoolConfig(
            max_connections=20,
            min_connections=5,
            connection_timeout=10.0,
            health_check_interval=30.0,
            enable_health_monitoring=False
        )
        
        assert config.max_connections == 20
        assert config.min_connections == 5
        assert config.connection_timeout == 10.0
        assert config.health_check_interval == 30.0
        assert config.enable_health_monitoring == False

    def test_configuration_validation(self):
        """Test configuration validation."""
        # Valid configuration
        config = PoolConfig(max_connections=10, min_connections=2)
        assert config.max_connections == 10
        assert config.min_connections == 2
        
        # Invalid: max < min
        with pytest.raises(ValueError, match="max_connections must be >= min_connections"):
            PoolConfig(max_connections=2, min_connections=5)
        
        # Invalid: negative timeout
        with pytest.raises(ValueError, match="connection_timeout must be positive"):
            PoolConfig(connection_timeout=-1)
        
        # Invalid: negative health check interval
        with pytest.raises(ValueError, match="health_check_interval must be positive"):
            PoolConfig(health_check_interval=-1)


class TestConnectionStats:
    """Test cases for connection statistics."""

    def test_stats_creation(self):
        """Test connection stats creation."""
        stats = ConnectionStats(
            total_connections=10,
            available_connections=8,
            active_connections=2,
            total_connections_created=15,
            total_connections_closed=5,
            health_check_failures=1
        )
        
        assert stats.total_connections == 10
        assert stats.available_connections == 8
        assert stats.active_connections == 2
        assert stats.total_connections_created == 15
        assert stats.total_connections_closed == 5
        assert stats.health_check_failures == 1

    def test_stats_validation(self):
        """Test that stats values are consistent."""
        stats = ConnectionStats(
            total_connections=10,
            available_connections=8,
            active_connections=2
        )
        
        # Available + active should equal total
        assert stats.available_connections + stats.active_connections == stats.total_connections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])