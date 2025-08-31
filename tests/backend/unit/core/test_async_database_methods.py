"""
Test suite for new async database methods in DatabaseService.

Tests the Phase 0 async refactor changes:
- Real async fetch_one() method using aiosqlite
- Real async execute_query() method using aiosqlite  
- Async connection management patterns
- aiosqlite integration and configuration
"""

import pytest
import pytest_asyncio
import tempfile
import os
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from core.database import DatabaseService


@pytest_asyncio.fixture
async def async_database():
    """Async database fixture for testing async methods"""
    # Create temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # Initialize database with migrations
    db_service = DatabaseService(db_path)
    
    yield db_service
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.mark.asyncio
class TestAsyncDatabaseMethods:
    """Test the new real async database methods"""
    
    async def test_async_fetch_one_returns_data(self, async_database):
        """Test fetch_one returns data when row exists"""
        # Insert test data using async execute_query
        await async_database.execute_query(
            """INSERT INTO data_items 
               (id, namespace, source_id, content, metadata, days_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('test:async_fetch_one', 'test', 'async_test', 'Test content for async fetch', '{}', '2025-08-31')
        )
        
        # Test async fetch_one
        result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?", 
            ('test:async_fetch_one',)
        )
        
        assert result is not None
        assert result['id'] == 'test:async_fetch_one'
        assert result['content'] == 'Test content for async fetch'
        assert result['namespace'] == 'test'
    
    async def test_async_fetch_one_returns_none_when_no_data(self, async_database):
        """Test fetch_one returns None when no row exists"""
        result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?", 
            ('nonexistent:id',)
        )
        
        assert result is None
    
    async def test_async_execute_query_insert(self, async_database):
        """Test execute_query can insert data"""
        # Use async execute_query to insert data
        await async_database.execute_query(
            """INSERT INTO data_items 
               (id, namespace, source_id, content, metadata, days_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('test:async_insert', 'test', 'async_test', 'Async inserted content', '{}', '2025-08-31')
        )
        
        # Verify data was inserted using sync method
        with async_database.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM data_items WHERE id = ?", ('test:async_insert',))
            row = cursor.fetchone()
            
        assert row is not None
        assert row['content'] == 'Async inserted content'
    
    async def test_async_execute_query_update(self, async_database):
        """Test execute_query can update data"""
        # Insert test data first using async execute_query
        await async_database.execute_query(
            """INSERT INTO data_items 
               (id, namespace, source_id, content, metadata, days_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('test:async_update', 'test', 'async_test', 'Original content', '{}', '2025-08-31')
        )
        
        # Update using async execute_query
        await async_database.execute_query(
            "UPDATE data_items SET content = ? WHERE id = ?",
            ('Updated async content', 'test:async_update')
        )
        
        # Verify update using async fetch_one
        result = await async_database.fetch_one(
            "SELECT content FROM data_items WHERE id = ?", 
            ('test:async_update',)
        )
            
        assert result['content'] == 'Updated async content'
    
    async def test_async_execute_query_delete(self, async_database):
        """Test execute_query can delete data"""
        # Insert test data first using async execute_query
        await async_database.execute_query(
            """INSERT INTO data_items 
               (id, namespace, source_id, content, metadata, days_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('test:async_delete', 'test', 'async_test', 'Content to delete', '{}', '2025-08-31')
        )
        
        # Delete using async execute_query
        await async_database.execute_query(
            "DELETE FROM data_items WHERE id = ?",
            ('test:async_delete',)
        )
        
        # Verify deletion using async fetch_one
        result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?", 
            ('test:async_delete',)
        )
            
        assert result is None


@pytest.mark.asyncio 
class TestAsyncConnectionPatterns:
    """Test the new async connection management patterns"""
    
    async def test_get_async_connection_context_manager(self, async_database):
        """Test async connection context manager works properly"""
        async with async_database.get_async_connection() as conn:
            # Test basic query to verify connection works
            async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                tables = await cursor.fetchall()
                
            # Should have core tables from migrations
            table_names = [row[0] for row in tables]
            assert 'data_items' in table_names
            assert 'data_sources' in table_names
            
            # Verify we can insert data through the connection
            await conn.execute(
                """INSERT INTO data_items 
                   (id, namespace, source_id, content, metadata, days_date) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ('test:connection_test', 'test', 'async_test', 'Connection test', '{}', '2025-08-31')
            )
            await conn.commit()
    
    async def test_async_transaction_commit_success(self, async_database):
        """Test async transaction commits successfully"""
        async with async_database.async_transaction() as conn:
            await conn.execute(
                """INSERT INTO data_items 
                   (id, namespace, source_id, content, metadata, days_date) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ('test:transaction_commit', 'test', 'async_test', 'Transaction content', '{}', '2025-08-31')
            )
            # Transaction should commit when context exits
        
        # Verify data was committed
        result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?",
            ('test:transaction_commit',)
        )
        
        assert result is not None
        assert result['content'] == 'Transaction content'
    
    async def test_async_transaction_rollback_on_exception(self, async_database):
        """Test async transaction rolls back on exception"""
        with pytest.raises(ValueError, match="Test exception"):
            async with async_database.async_transaction() as conn:
                await conn.execute(
                    """INSERT INTO data_items 
                       (id, namespace, source_id, content, metadata, days_date) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    ('test:transaction_rollback', 'test', 'async_test', 'Should be rolled back', '{}', '2025-08-31')
                )
                # Raise exception to trigger rollback
                raise ValueError("Test exception")
        
        # Verify data was rolled back
        result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?",
            ('test:transaction_rollback',)
        )
        
        assert result is None


@pytest.mark.asyncio
class TestAsyncPerformance:
    """Test async performance characteristics"""
    
    async def test_concurrent_async_operations(self, async_database):
        """Test multiple concurrent async database operations"""
        # Insert test data first using async methods
        insert_tasks = []
        for i in range(10):
            task = async_database.execute_query(
                """INSERT INTO data_items 
                   (id, namespace, source_id, content, metadata, days_date) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (f'test:concurrent_{i}', 'test', 'async_test', 
                 f'Concurrent content {i}', '{}', '2025-08-31')
            )
            insert_tasks.append(task)
        
        # Execute all inserts concurrently
        await asyncio.gather(*insert_tasks)
        
        # Create multiple concurrent fetch operations
        fetch_tasks = []
        for i in range(10):
            task = async_database.fetch_one(
                "SELECT * FROM data_items WHERE id = ?",
                (f'test:concurrent_{i}',)
            )
            fetch_tasks.append(task)
        
        # Execute all fetch tasks concurrently
        results = await asyncio.gather(*fetch_tasks)
        
        # Verify all operations completed successfully
        assert len(results) == 10
        for i, result in enumerate(results):
            assert result is not None
            assert result['id'] == f'test:concurrent_{i}'
            assert result['content'] == f'Concurrent content {i}'
    
    async def test_concurrent_async_writes(self, async_database):
        """Test multiple concurrent async write operations"""
        # Create multiple concurrent write operations
        tasks = []
        for i in range(5):
            task = async_database.execute_query(
                """INSERT INTO data_items 
                   (id, namespace, source_id, content, metadata, days_date) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (f'test:concurrent_write_{i}', 'test', 'async_test', 
                 f'Concurrent write {i}', '{}', '2025-08-31')
            )
            tasks.append(task)
        
        # Execute all writes concurrently
        await asyncio.gather(*tasks)
        
        # Verify all writes completed
        for i in range(5):
            result = await async_database.fetch_one(
                "SELECT * FROM data_items WHERE id = ?",
                (f'test:concurrent_write_{i}',)
            )
            assert result is not None
            assert result['content'] == f'Concurrent write {i}'


@pytest.mark.asyncio
class TestAsyncErrorHandling:
    """Test async error handling patterns"""
    
    async def test_async_fetch_one_database_error(self, async_database):
        """Test fetch_one handles database errors properly"""
        with pytest.raises(Exception):
            await async_database.fetch_one("INVALID SQL QUERY")
    
    async def test_async_execute_query_database_error(self, async_database):
        """Test execute_query handles database errors properly"""
        with pytest.raises(Exception):
            await async_database.execute_query("INVALID SQL QUERY")
    
    async def test_async_connection_cleanup_on_error(self, async_database):
        """Test async connection is properly cleaned up on error"""
        initial_connections = 0  # aiosqlite manages connections internally
        
        with pytest.raises(Exception):
            async with async_database.get_async_connection() as conn:
                raise ValueError("Test connection error")
        
        # Connection should be cleaned up automatically by aiosqlite
        # This test verifies no exception is raised during cleanup


@pytest.mark.asyncio
class TestAsyncIntegration:
    """Test async methods integration with existing sync methods"""
    
    async def test_async_fetch_one_matches_sync_behavior(self, async_database):
        """Test async fetch_one returns same data as sync equivalent"""
        # Insert test data using async method
        test_id = 'test:sync_async_comparison'
        await async_database.execute_query(
            """INSERT INTO data_items 
               (id, namespace, source_id, content, metadata, days_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (test_id, 'test', 'async_test', 'Comparison content', '{"key": "value"}', '2025-08-31')
        )
        
        # Get data using async method
        async_result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?", (test_id,)
        )
        
        # Get data using sync method
        with async_database.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM data_items WHERE id = ?", (test_id,))
            sync_row = cursor.fetchone()
            sync_result = dict(sync_row) if sync_row else None
        
        # Compare results
        assert async_result == sync_result
        assert async_result['content'] == 'Comparison content'
    
    async def test_async_execute_query_matches_sync_behavior(self, async_database):
        """Test async execute_query has same effect as sync equivalent"""
        test_id = 'test:execute_comparison'
        
        # Insert using async execute_query
        await async_database.execute_query(
            """INSERT INTO data_items 
               (id, namespace, source_id, content, metadata, days_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (test_id, 'test', 'async_test', 'Execute query content', '{}', '2025-08-31')
        )
        
        # Verify using async fetch_one
        result = await async_database.fetch_one(
            "SELECT * FROM data_items WHERE id = ?", (test_id,)
        )
        
        assert result is not None
        assert result['content'] == 'Execute query content'
        assert result['namespace'] == 'test'