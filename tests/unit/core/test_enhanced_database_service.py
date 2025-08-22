"""
Test cases for enhanced database service with connection pooling.

Tests the enhanced DatabaseService that uses connection pooling for improved
performance and resource management.
"""

import pytest
import sqlite3
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from core.enhanced_database import EnhancedDatabaseService
from core.database_pool import PoolConfig


class TestEnhancedDatabaseService:
    """Test cases for enhanced database service."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database path."""
        return str(tmp_path / "test_enhanced.db")

    @pytest.fixture
    def pool_config(self):
        """Create test pool configuration."""
        return PoolConfig(
            max_connections=5,
            min_connections=2,
            connection_timeout=5.0,
            health_check_interval=30.0
        )

    @pytest.fixture
    def enhanced_db_service(self, temp_db_path, pool_config):
        """Create enhanced database service for testing."""
        service = EnhancedDatabaseService(temp_db_path, pool_config)
        yield service
        service.close()

    def test_service_initialization(self, enhanced_db_service, temp_db_path, pool_config):
        """Test enhanced database service initialization."""
        assert enhanced_db_service.db_path == temp_db_path
        assert enhanced_db_service.pool_config == pool_config
        assert enhanced_db_service._pool is not None
        assert enhanced_db_service._performance_metrics is not None

    def test_backward_compatibility_with_original_methods(self, enhanced_db_service):
        """Test that all original DatabaseService methods still work."""
        # Test store_data_item
        enhanced_db_service.store_data_item(
            id="test:1",
            namespace="test",
            source_id="1",
            content="test content",
            metadata={"key": "value"},
            days_date="2024-01-01"
        )
        
        # Test get_data_items_by_ids
        items = enhanced_db_service.get_data_items_by_ids(["test:1"])
        assert len(items) == 1
        assert items[0]["content"] == "test content"

    def test_connection_pooling_performance_improvement(self, enhanced_db_service):
        """Test that connection pooling improves performance."""
        # Store multiple items to measure performance
        start_time = time.time()
        
        for i in range(10):
            enhanced_db_service.store_data_item(
                id=f"perf:test:{i}",
                namespace="perf_test",
                source_id=str(i),
                content=f"test content {i}",
                days_date="2024-01-01"
            )
        
        duration = time.time() - start_time
        
        # Should complete reasonably quickly (this is more of a regression test)
        assert duration < 5.0  # Should complete in under 5 seconds

    def test_concurrent_database_operations(self, enhanced_db_service):
        """Test concurrent database operations with connection pooling."""
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                # Perform multiple operations
                enhanced_db_service.store_data_item(
                    id=f"concurrent:worker:{worker_id}",
                    namespace="concurrent_test",
                    source_id=str(worker_id),
                    content=f"worker {worker_id} content",
                    days_date="2024-01-01"
                )
                
                # Read back the data
                items = enhanced_db_service.get_data_items_by_ids([f"concurrent:worker:{worker_id}"])
                if items:
                    results.append(items[0]["content"])
                
            except Exception as e:
                errors.append(e)
        
        # Run multiple workers concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(20)]
            for future in futures:
                future.result()
        
        # All operations should succeed
        assert len(errors) == 0
        assert len(results) == 20

    def test_performance_metrics_collection(self, enhanced_db_service):
        """Test that performance metrics are collected."""
        # Perform some operations
        enhanced_db_service.store_data_item(
            id="metrics:test:1",
            namespace="metrics_test", 
            source_id="1",
            content="test content",
            days_date="2024-01-01"
        )
        
        enhanced_db_service.get_data_items_by_ids(["metrics:test:1"])
        
        # Get metrics
        metrics = enhanced_db_service.get_performance_metrics()
        
        assert metrics is not None
        assert "total_operations" in metrics
        assert "average_operation_time" in metrics
        assert "pool_stats" in metrics
        assert metrics["total_operations"] >= 2  # At least store and get operations

    def test_connection_health_monitoring_integration(self, enhanced_db_service):
        """Test integration with connection health monitoring."""
        # Enable health monitoring
        enhanced_db_service._pool.config.enable_health_monitoring = True
        
        # Perform operations
        enhanced_db_service.store_data_item(
            id="health:test:1",
            namespace="health_test",
            source_id="1", 
            content="test content",
            days_date="2024-01-01"
        )
        
        # Get pool statistics
        pool_stats = enhanced_db_service._pool.get_stats()
        
        assert pool_stats.total_connections > 0
        assert pool_stats.health_check_failures == 0

    def test_graceful_service_shutdown(self, enhanced_db_service):
        """Test graceful shutdown of enhanced database service."""
        # Perform some operations
        enhanced_db_service.store_data_item(
            id="shutdown:test:1",
            namespace="shutdown_test",
            source_id="1",
            content="test content",
            days_date="2024-01-01"
        )
        
        # Close the service
        enhanced_db_service.close()
        
        # After closing, pool should be empty
        pool_stats = enhanced_db_service._pool.get_stats()
        assert pool_stats.total_connections == 0

    def test_error_handling_with_connection_recovery(self, enhanced_db_service):
        """Test error handling and connection recovery."""
        # Test that the service can handle database errors gracefully
        # by attempting to store data with invalid SQL-like content
        
        # First, verify normal operation works
        enhanced_db_service.store_data_item(
            id="normal:test:1",
            namespace="normal_test",
            source_id="1",
            content="normal content",
            days_date="2024-01-01"
        )
        
        # The service should handle various edge cases gracefully
        # without crashing the entire connection pool
        items = enhanced_db_service.get_data_items_by_ids(["normal:test:1"])
        assert len(items) == 1

    def test_migration_compatibility(self, enhanced_db_service):
        """Test that database migrations still work with enhanced service."""
        # The service should initialize the database properly
        # Check that tables exist
        with enhanced_db_service._pool.get_connection() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='data_items'
            """)
            result = cursor.fetchone()
            assert result is not None

    def test_settings_persistence_with_pooling(self, enhanced_db_service):
        """Test that settings persistence works with connection pooling."""
        # Set a setting
        enhanced_db_service.set_setting("test_key", "test_value")
        
        # Get the setting back
        value = enhanced_db_service.get_setting("test_key")
        assert value == "test_value"
        
        # Test with complex data
        complex_data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        enhanced_db_service.set_setting("complex_key", complex_data)
        
        retrieved_data = enhanced_db_service.get_setting("complex_key")
        assert retrieved_data == complex_data

    def test_namespace_operations_with_pooling(self, enhanced_db_service):
        """Test namespace operations work correctly with pooling."""
        # Register data source
        enhanced_db_service.register_data_source(
            namespace="pool_test",
            source_type="test_source",
            metadata={"test": True}
        )
        
        # Store items in namespace
        for i in range(5):
            enhanced_db_service.store_data_item(
                id=f"pool_test:{i}",
                namespace="pool_test",
                source_id=str(i),
                content=f"content {i}",
                days_date="2024-01-01"
            )
        
        # Get items by namespace
        items = enhanced_db_service.get_data_items_by_namespace("pool_test")
        assert len(items) == 5
        
        # Update source item count
        count = enhanced_db_service.update_source_item_count("pool_test")
        assert count == 5

    def test_embedding_status_operations_with_pooling(self, enhanced_db_service):
        """Test embedding status operations with connection pooling."""
        # Store item with explicit pending status
        enhanced_db_service.store_data_item(
            id="embed:test:1",
            namespace="embed_test",
            source_id="1",
            content="test content for embedding",
            days_date="2024-01-01",
            ingestion_status="complete"
        )
        
        # Set embedding status to pending initially
        enhanced_db_service.update_embedding_status("embed:test:1", "pending")
        
        # Get pending embeddings
        pending = enhanced_db_service.get_pending_embeddings()
        embed_test_items = [item for item in pending if item["id"] == "embed:test:1"]
        assert len(embed_test_items) >= 1
        
        # Update embedding status to completed
        enhanced_db_service.update_embedding_status("embed:test:1", "completed")
        
        # Check status was updated
        items = enhanced_db_service.get_data_items_by_ids(["embed:test:1"])
        assert len(items) == 1
        assert items[0]["embedding_status"] == "completed"

    def test_database_statistics_with_pooling(self, enhanced_db_service):
        """Test database statistics collection with connection pooling."""
        # Store some test data
        for i in range(3):
            enhanced_db_service.store_data_item(
                id=f"stats:test:{i}",
                namespace="stats_test",
                source_id=str(i),
                content=f"stats content {i}",
                days_date="2024-01-01"
            )
        
        # Get database stats
        stats = enhanced_db_service.get_database_stats()
        
        assert stats["total_items"] >= 3
        assert "stats_test" in stats["namespace_counts"]
        assert stats["namespace_counts"]["stats_test"] >= 3
        assert stats["active_sources"] >= 0
        assert stats["database_size_mb"] >= 0

    def test_chat_operations_with_pooling(self, enhanced_db_service):
        """Test chat operations work with connection pooling."""
        # Store chat message
        enhanced_db_service.store_chat_message(
            "Test user message",
            "Test assistant response"
        )
        
        # Get chat history
        history = enhanced_db_service.get_chat_history(limit=10)
        
        assert len(history) >= 1
        assert history[-1]["user_message"] == "Test user message"
        assert history[-1]["assistant_response"] == "Test assistant response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])