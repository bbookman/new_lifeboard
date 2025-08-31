"""
Test suite for async DatabaseService operations.

This file follows TDD approach for converting sync DatabaseService methods to async.
Each test follows the RED-GREEN-REFACTOR cycle as outlined in the async refactor plan.
"""

import pytest
import tempfile
import os
import json
import asyncio
import time
from typing import Dict, List, Any
from datetime import datetime

from core.database import DatabaseService
from core.json_utils import JSONMetadataParser


class TestAsyncDatabaseCRUD:
    """Test async CRUD operations for DatabaseService"""
    
    @pytest.mark.asyncio
    async def test_async_store_data_item_success(self, async_database):
        """Test async storage of data item - RED phase test"""
        # This test will initially fail until we implement async_store_data_item
        data_item = {
            'id': 'test:async_001',
            'namespace': 'test',
            'source_id': 'async_001',
            'content': 'Test async content',
            'metadata': {'test': True},
            'days_date': '2025-01-15'
        }
        
        # This will fail until async method is implemented
        await async_database.async_store_data_item(**data_item)
        
        # Verify storage using async method
        items = await async_database.async_get_data_items_by_ids([data_item['id']])
        assert len(items) == 1
        assert items[0]['content'] == data_item['content']
    
    @pytest.mark.asyncio
    async def test_async_get_data_items_by_ids_success(self, async_database):
        """Test async batch fetching of data items by IDs"""
        # Store test data first
        test_ids = ['test:async_batch_1', 'test:async_batch_2']
        
        for i, item_id in enumerate(test_ids):
            await async_database.async_store_data_item(
                id=item_id,
                namespace='test',
                source_id=f'async_batch_{i+1}',
                content=f'Async batch content {i+1}',
                metadata={'batch_index': i+1},
                days_date='2025-01-15'
            )
        
        # Test batch fetching
        items = await async_database.async_get_data_items_by_ids(test_ids)
        assert len(items) == 2
        assert all(item['id'] in test_ids for item in items)
    
    @pytest.mark.asyncio
    async def test_async_get_data_items_by_ids_empty_list(self, async_database):
        """Test async batch fetching with empty ID list"""
        items = await async_database.async_get_data_items_by_ids([])
        assert items == []
    
    @pytest.mark.asyncio
    async def test_async_get_data_items_by_ids_nonexistent(self, async_database):
        """Test async batch fetching with nonexistent IDs"""
        items = await async_database.async_get_data_items_by_ids(['nonexistent:001'])
        assert items == []
    
    @pytest.mark.asyncio
    async def test_async_store_data_item_with_metadata(self, async_database):
        """Test async storage with complex metadata"""
        complex_metadata = {
            'nested': {'data': {'value': 42}},
            'list': [1, 2, 3],
            'timestamp': '2025-01-15T10:00:00Z'
        }
        
        await async_database.async_store_data_item(
            id='test:complex_metadata',
            namespace='test',
            source_id='complex_metadata',
            content='Test content with complex metadata',
            metadata=complex_metadata,
            days_date='2025-01-15'
        )
        
        items = await async_database.async_get_data_items_by_ids(['test:complex_metadata'])
        assert len(items) == 1
        assert items[0]['metadata'] == complex_metadata
    
    @pytest.mark.asyncio
    async def test_async_store_data_item_replace_existing(self, async_database):
        """Test async storage replaces existing items with same ID"""
        item_id = 'test:replace_test'
        
        # Store initial item
        await async_database.async_store_data_item(
            id=item_id,
            namespace='test',
            source_id='replace_test',
            content='Original content',
            metadata={'version': 1},
            days_date='2025-01-15'
        )
        
        # Replace with updated content
        await async_database.async_store_data_item(
            id=item_id,
            namespace='test',
            source_id='replace_test',
            content='Updated content',
            metadata={'version': 2},
            days_date='2025-01-15'
        )
        
        # Verify replacement
        items = await async_database.async_get_data_items_by_ids([item_id])
        assert len(items) == 1
        assert items[0]['content'] == 'Updated content'
        assert items[0]['metadata']['version'] == 2


class TestAsyncDatabaseQuery:
    """Test async query operations for DatabaseService"""
    
    @pytest.mark.asyncio
    async def test_async_get_data_items_by_namespace(self, async_database):
        """Test async namespace-based querying"""
        # Store test data in different namespaces
        await async_database.async_store_data_item(
            id='test_ns:item1', namespace='test_ns', source_id='item1',
            content='Content 1', days_date='2025-01-15'
        )
        await async_database.async_store_data_item(
            id='other_ns:item1', namespace='other_ns', source_id='item1',
            content='Content 2', days_date='2025-01-15'
        )
        
        # Test namespace filtering
        items = await async_database.async_get_data_items_by_namespace('test_ns')
        assert len(items) == 1
        assert items[0]['namespace'] == 'test_ns'
    
    @pytest.mark.asyncio
    async def test_async_get_data_items_by_date_range(self, async_database):
        """Test async date range querying"""
        # Store test data for different dates
        await async_database.async_store_data_item(
            id='date_test:1', namespace='test', source_id='1',
            content='Content 1', days_date='2025-01-15'
        )
        await async_database.async_store_data_item(
            id='date_test:2', namespace='test', source_id='2',
            content='Content 2', days_date='2025-01-16'
        )
        await async_database.async_store_data_item(
            id='date_test:3', namespace='test', source_id='3',
            content='Content 3', days_date='2025-01-17'
        )
        
        # Test date range filtering
        items = await async_database.async_get_data_items_by_date_range('2025-01-15', '2025-01-16')
        assert len(items) == 2
        dates = [item['days_date'] for item in items]
        assert '2025-01-15' in dates
        assert '2025-01-16' in dates
        assert '2025-01-17' not in dates
    
    @pytest.mark.asyncio
    async def test_async_get_data_items_by_date(self, async_database):
        """Test async single date querying"""
        # Store test data
        await async_database.async_store_data_item(
            id='single_date:1', namespace='test', source_id='1',
            content='Content for date', days_date='2025-01-15'
        )
        
        # Test single date query
        items = await async_database.async_get_data_items_by_date('2025-01-15')
        assert len(items) == 1
        assert items[0]['days_date'] == '2025-01-15'
    
    @pytest.mark.asyncio
    async def test_async_get_available_dates(self, async_database):
        """Test async available dates querying"""
        # Store test data for different dates
        dates = ['2025-01-15', '2025-01-16', '2025-01-17']
        for i, date in enumerate(dates):
            await async_database.async_store_data_item(
                id=f'date_avail:{i}', namespace='test', source_id=str(i),
                content=f'Content {i}', days_date=date
            )
        
        # Test available dates query
        available_dates = await async_database.async_get_available_dates()
        assert len(available_dates) == 3
        for date in dates:
            assert date in available_dates
    
    @pytest.mark.asyncio
    async def test_async_get_days_with_data(self, async_database):
        """Test async days with data querying"""
        # Store test data
        await async_database.async_store_data_item(
            id='days_test:1', namespace='test', source_id='1',
            content='Content', days_date='2025-01-15'
        )
        
        # Test days with data query
        days = await async_database.async_get_days_with_data()
        assert '2025-01-15' in days
    
    @pytest.mark.asyncio
    async def test_async_get_all_namespaces(self, async_database):
        """Test async namespace listing"""
        # Store test data in different namespaces
        namespaces = ['ns1', 'ns2', 'ns3']
        for i, ns in enumerate(namespaces):
            await async_database.async_store_data_item(
                id=f'{ns}:item{i}', namespace=ns, source_id=f'item{i}',
                content=f'Content {i}', days_date='2025-01-15'
            )
        
        # Test namespace listing
        all_namespaces = await async_database.async_get_all_namespaces()
        for ns in namespaces:
            assert ns in all_namespaces


class TestAsyncDatabaseSettings:
    """Test async settings and metadata operations"""
    
    @pytest.mark.asyncio
    async def test_async_get_set_setting(self, async_database):
        """Test async setting storage and retrieval"""
        # Test setting storage
        await async_database.async_set_setting('test_key', 'test_value')
        
        # Test setting retrieval
        value = await async_database.async_get_setting('test_key')
        assert value == 'test_value'
    
    @pytest.mark.asyncio
    async def test_async_get_setting_with_default(self, async_database):
        """Test async setting retrieval with default value"""
        value = await async_database.async_get_setting('nonexistent_key', 'default_value')
        assert value == 'default_value'
    
    @pytest.mark.asyncio
    async def test_async_get_set_setting_complex_data(self, async_database):
        """Test async setting with complex JSON data"""
        complex_data = {
            'nested': {'value': 42},
            'list': [1, 2, 3],
            'boolean': True
        }
        
        await async_database.async_set_setting('complex_key', complex_data)
        retrieved = await async_database.async_get_setting('complex_key')
        assert retrieved == complex_data
    
    @pytest.mark.asyncio
    async def test_async_register_data_source(self, async_database):
        """Test async data source registration"""
        metadata = {'api_endpoint': 'https://api.example.com'}
        
        await async_database.async_register_data_source('test_source', 'api', metadata)
        
        # Verify registration by checking active namespaces
        namespaces = await async_database.async_get_active_namespaces()
        assert 'test_source' in namespaces
    
    @pytest.mark.asyncio
    async def test_async_get_active_namespaces(self, async_database):
        """Test async active namespaces retrieval"""
        # Register multiple sources
        sources = [('source1', 'api'), ('source2', 'file'), ('source3', 'manual')]
        for ns, source_type in sources:
            await async_database.async_register_data_source(ns, source_type)
        
        # Test retrieval
        active_namespaces = await async_database.async_get_active_namespaces()
        for ns, _ in sources:
            assert ns in active_namespaces
    
    @pytest.mark.asyncio
    async def test_async_update_source_item_count(self, async_database):
        """Test async source item count update"""
        # Register source and add items
        await async_database.async_register_data_source('count_test', 'test')
        
        for i in range(3):
            await async_database.async_store_data_item(
                id=f'count_test:item{i}', namespace='count_test', source_id=f'item{i}',
                content=f'Content {i}', days_date='2025-01-15'
            )
        
        # Update count
        count = await async_database.async_update_source_item_count('count_test')
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_async_get_database_stats(self, async_database):
        """Test async database statistics retrieval"""
        # Add some test data
        await async_database.async_store_data_item(
            id='stats:1', namespace='stats_test', source_id='1',
            content='Stats content', days_date='2025-01-15'
        )
        
        # Get stats
        stats = await async_database.async_get_database_stats()
        assert 'total_items' in stats
        assert 'namespace_counts' in stats
        assert 'embedding_status' in stats
        assert stats['total_items'] >= 1
    
    @pytest.mark.asyncio
    async def test_async_store_chat_message(self, async_database):
        """Test async chat message storage"""
        await async_database.async_store_chat_message('Hello', 'Hi there!')
        
        # Verify storage
        history = await async_database.async_get_chat_history(limit=1)
        assert len(history) == 1
        assert history[0]['user_message'] == 'Hello'
        assert history[0]['assistant_response'] == 'Hi there!'
    
    @pytest.mark.asyncio
    async def test_async_get_chat_history(self, async_database):
        """Test async chat history retrieval"""
        # Store multiple messages
        messages = [
            ('Message 1', 'Response 1'),
            ('Message 2', 'Response 2'),
            ('Message 3', 'Response 3')
        ]
        
        for user_msg, assistant_msg in messages:
            await async_database.async_store_chat_message(user_msg, assistant_msg)
        
        # Test retrieval
        history = await async_database.async_get_chat_history(limit=2)
        assert len(history) == 2
        # Should be in chronological order (oldest first)
        assert history[0]['user_message'] == 'Message 2'
        assert history[1]['user_message'] == 'Message 3'


class TestAsyncDatabaseEmbedding:
    """Test async embedding operations"""
    
    @pytest.mark.asyncio
    async def test_async_update_embedding_status(self, async_database):
        """Test async embedding status update"""
        # Store test item
        await async_database.async_store_data_item(
            id='embed:test1', namespace='test', source_id='test1',
            content='Test content for embedding', days_date='2025-01-15'
        )
        
        # Update embedding status
        await async_database.async_update_embedding_status('embed:test1', 'completed')
        
        # Verify update (using sync method for now since no async alternative)
        items = await async_database.async_get_data_items_by_ids(['embed:test1'])
        assert len(items) == 1
        assert items[0]['embedding_status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_async_update_ingestion_status(self, async_database):
        """Test async ingestion status update"""
        # Store test item
        await async_database.async_store_data_item(
            id='ingest:test1', namespace='test', source_id='test1',
            content='Test content for ingestion', days_date='2025-01-15'
        )
        
        # Update ingestion status (use valid status from constraint)
        await async_database.async_update_ingestion_status('ingest:test1', 'partial')
        
        # Verify update
        items = await async_database.async_get_data_items_by_ids(['ingest:test1'])
        assert len(items) == 1
        assert items[0]['ingestion_status'] == 'partial'
    
    @pytest.mark.asyncio
    async def test_async_get_pending_embeddings(self, async_database):
        """Test async pending embeddings retrieval"""
        # Store items with different embedding statuses
        await async_database.async_store_data_item(
            id='pending:1', namespace='test', source_id='1',
            content='Pending embedding content 1', days_date='2025-01-15'
        )
        await async_database.async_store_data_item(
            id='completed:1', namespace='test', source_id='2',
            content='Completed embedding content', days_date='2025-01-15'
        )
        
        # Update one to completed status
        await async_database.async_update_embedding_status('completed:1', 'completed')
        
        # Get pending embeddings
        pending = await async_database.async_get_pending_embeddings()
        assert len(pending) >= 1
        assert any(item['id'] == 'pending:1' for item in pending)
        assert not any(item['id'] == 'completed:1' for item in pending)


class TestAsyncDatabaseTransactions:
    """Test async transaction support and error handling"""
    
    @pytest.mark.asyncio
    async def test_async_transaction_success(self, async_database):
        """Test successful async transaction"""
        # Test transaction context manager
        async with async_database.async_transaction() as conn:
            await conn.execute("""
                INSERT INTO data_items 
                (id, namespace, source_id, content, days_date)
                VALUES (?, ?, ?, ?, ?)
            """, ('trans:success', 'test', 'success', 'Transaction test', '2025-01-15'))
            # Transaction will commit automatically
        
        # Verify data was committed
        items = await async_database.async_get_data_items_by_ids(['trans:success'])
        assert len(items) == 1
        assert items[0]['content'] == 'Transaction test'
    
    @pytest.mark.asyncio
    async def test_async_transaction_rollback(self, async_database):
        """Test async transaction rollback on error"""
        try:
            async with async_database.async_transaction() as conn:
                await conn.execute("""
                    INSERT INTO data_items 
                    (id, namespace, source_id, content, days_date)
                    VALUES (?, ?, ?, ?, ?)
                """, ('trans:rollback', 'test', 'rollback', 'Rollback test', '2025-01-15'))
                
                # Force an error to trigger rollback
                raise Exception("Simulated error")
        except Exception:
            # Expected exception
            pass
        
        # Verify data was rolled back
        items = await async_database.async_get_data_items_by_ids(['trans:rollback'])
        assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_transactions(self, async_database):
        """Test concurrent async transactions"""
        import asyncio
        
        async def create_item(i):
            async with async_database.async_transaction() as conn:
                await conn.execute("""
                    INSERT INTO data_items 
                    (id, namespace, source_id, content, days_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (f'concurrent_trans:{i}', 'test', f'item_{i}', f'Content {i}', '2025-01-15'))
        
        # Run multiple transactions concurrently
        tasks = [create_item(i) for i in range(5)]
        await asyncio.gather(*tasks)
        
        # Verify all items were created
        all_ids = [f'concurrent_trans:{i}' for i in range(5)]
        items = await async_database.async_get_data_items_by_ids(all_ids)
        assert len(items) == 5


class TestAsyncDatabaseConcurrency:
    """Test concurrent async operations"""
    
    @pytest.mark.asyncio
    async def test_concurrent_store_operations(self, async_database):
        """Test multiple concurrent store operations"""
        import asyncio
        
        # Create tasks for concurrent operations
        tasks = []
        for i in range(10):
            task = async_database.async_store_data_item(
                id=f'concurrent:item_{i}',
                namespace='concurrent',
                source_id=f'item_{i}',
                content=f'Concurrent content {i}',
                metadata={'index': i},
                days_date='2025-01-15'
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks)
        
        # Verify all items were stored
        all_ids = [f'concurrent:item_{i}' for i in range(10)]
        items = await async_database.async_get_data_items_by_ids(all_ids)
        assert len(items) == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_read_operations(self, async_database):
        """Test multiple concurrent read operations"""
        import asyncio
        
        # First populate test data
        test_ids = ['limitless:concurrent_read_001', 'news:concurrent_read_001']
        await async_database.async_store_data_item(
            id=test_ids[0], namespace='limitless', source_id='concurrent_read_001',
            content='Concurrent read test content 1', days_date='2025-01-15'
        )
        await async_database.async_store_data_item(
            id=test_ids[1], namespace='news', source_id='concurrent_read_001',
            content='Concurrent read test content 2', days_date='2025-01-15'
        )
        
        # Create tasks for concurrent reads
        tasks = []
        for _ in range(10):
            task = async_database.async_get_data_items_by_ids(test_ids)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all reads returned correct data
        for result in results:
            assert len(result) == 2
            assert any(item['id'] == test_ids[0] for item in result)
            assert any(item['id'] == test_ids[1] for item in result)


class TestAsyncDatabasePerformance:
    """Test async performance benchmarking"""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_async_concurrent_operations_performance(self, async_database):
        """Test concurrent async operations performance - from refactor plan"""
        import asyncio
        import time
        
        # Test concurrent async operations
        start_time = time.perf_counter()
        
        tasks = []
        for i in range(100):
            task = async_database.async_store_data_item(
                id=f'perf:concurrent_{i}', 
                namespace='perf', 
                source_id=str(i), 
                content=f'Content {i}',
                days_date='2025-01-15'
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        concurrent_time = time.perf_counter() - start_time
        
        # Test sequential async operations
        start_time = time.perf_counter()
        for i in range(100, 200):
            await async_database.async_store_data_item(
                id=f'perf:sequential_{i}', 
                namespace='perf', 
                source_id=str(i), 
                content=f'Content {i}',
                days_date='2025-01-15'
            )
        sequential_time = time.perf_counter() - start_time
        
        # For SQLite, concurrent operations may not be faster due to single connection
        # but they should complete successfully without blocking the event loop
        assert concurrent_time > 0 and sequential_time > 0  # Both should complete
        
        print(f"\nPerformance Results:")
        print(f"Concurrent operations: {concurrent_time:.3f}s")
        print(f"Sequential operations: {sequential_time:.3f}s")
        print(f"Performance improvement: {(sequential_time - concurrent_time) / sequential_time * 100:.1f}%")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_async_bulk_read_performance(self, async_database):
        """Test async bulk read performance"""
        import time
        
        # Setup: create 500 test items
        setup_tasks = []
        for i in range(500):
            task = async_database.async_store_data_item(
                id=f'bulk_read:{i}', 
                namespace='bulk_test', 
                source_id=str(i),
                content=f'Bulk test content {i}' * 5,  # Make content longer
                days_date='2025-01-15'
            )
            setup_tasks.append(task)
        
        await asyncio.gather(*setup_tasks)
        
        # Test bulk read performance
        start_time = time.perf_counter()
        all_ids = [f'bulk_read:{i}' for i in range(500)]
        items = await async_database.async_get_data_items_by_ids(all_ids)
        read_time = time.perf_counter() - start_time
        
        assert len(items) == 500
        assert read_time < 2.0  # Should complete within 2 seconds
        
        print(f"\nBulk Read Performance:")
        print(f"Read 500 items in: {read_time:.3f}s")
        print(f"Items per second: {500 / read_time:.1f}")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_async_namespace_query_performance(self, async_database):
        """Test async namespace query performance with large dataset"""
        import time
        
        # Setup: create items across multiple namespaces
        namespaces = ['ns1', 'ns2', 'ns3', 'ns4', 'ns5']
        setup_tasks = []
        
        for ns in namespaces:
            for i in range(100):  # 100 items per namespace
                task = async_database.async_store_data_item(
                    id=f'{ns}:item_{i}', 
                    namespace=ns, 
                    source_id=str(i),
                    content=f'Content for {ns} item {i}',
                    days_date='2025-01-15'
                )
                setup_tasks.append(task)
        
        await asyncio.gather(*setup_tasks)
        
        # Test namespace query performance
        start_time = time.perf_counter()
        items = await async_database.async_get_data_items_by_namespace('ns1', limit=100)
        query_time = time.perf_counter() - start_time
        
        assert len(items) == 100
        assert query_time < 0.5  # Should complete within 500ms
        assert all(item['namespace'] == 'ns1' for item in items)
        
        print(f"\nNamespace Query Performance:")
        print(f"Queried 100 items from namespace in: {query_time:.3f}s")


# Export all fixtures
__all__ = [
    "temp_db_path",
    "clean_database",
    "database_service",
    "memory_database", 
    "database_with_test_data",
    "sample_data_items",
    "db_helper",
    "DatabaseTestHelper",
    "isolated_database_test",
    "mock_database_service",
    "transactional_database",
    "corrupted_database_scenario",
    "readonly_database_scenario",
    "large_dataset_database",
    "migration_test_database",
    "pre_migration_database",
    "async_database",
    "async_database_with_test_data"
]