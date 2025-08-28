"""
Async Database fixtures for isolated async test database lifecycle management.

This module provides comprehensive async database testing utilities including
temporary database creation, test data population, and cleanup management
for the async DatabaseService refactoring.
"""

import pytest
import pytest_asyncio
import tempfile
import os
import aiosqlite
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

# Import the async database service
from core.async_database import AsyncDatabaseService
from sources.base import DataItem


@pytest.fixture(scope="function")
def async_temp_db_path():
    """Create a temporary database file path for async testing"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='_async.db')
    temp_db.close()
    
    yield temp_db.name
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except FileNotFoundError:
        pass


@pytest_asyncio.fixture(scope="function")
async def async_clean_database(async_temp_db_path):
    """Create a clean async database with migrations applied"""
    # Note: This will be updated once AsyncDatabaseService is created
    # For now, create a placeholder that can be used in tests
    
    # Initialize database schema using aiosqlite directly
    async with aiosqlite.connect(async_temp_db_path) as conn:
        # Create the basic schema
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS data_items (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                source_id TEXT NOT NULL,
                content TEXT,
                metadata TEXT,
                embedding_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                days_date TEXT NOT NULL,
                ingestion_status TEXT DEFAULT 'complete'
            )
        """)
        
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
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT NOT NULL,
                assistant_response TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP
            )
        """)

        await conn.commit()
    mock_db = AsyncDatabaseService(async_temp_db_path)
    yield mock_db


@pytest_asyncio.fixture(scope="function") 
async def async_database_service(async_clean_database):
    """Alias for async_clean_database for consistency"""
    return async_clean_database


@pytest_asyncio.fixture
async def async_memory_database():
    """Create an in-memory async database for fast testing"""
    mock_db = AsyncDatabaseService(":memory:")
    return mock_db


@pytest_asyncio.fixture
async def async_database_with_test_data(async_clean_database):
    """Async database pre-populated with test data"""
    db = async_clean_database
    
    # Sample test data
    test_data = [
        {
            'id': 'limitless:async_test_001',
            'namespace': 'limitless',
            'source_id': 'async_test_001',
            'content': 'Async test meeting discussion about project planning',
            'metadata': {
                'title': 'Async Project Planning Meeting',
                'start_time': '2025-01-15T09:00:00Z',
                'end_time': '2025-01-15T10:00:00Z',
                'participants': ['Alice', 'Bob']
            },
            'days_date': '2025-01-15'
        },
        {
            'id': 'news:async_test_001',
            'namespace': 'news',
            'source_id': 'async_test_001',
            'content': 'Breaking async news about technology advancement',
            'metadata': {
                'title': 'Async Tech Breakthrough',
                'published_datetime_utc': '2025-01-15T12:00:00Z',
                'link': 'https://example.com/async-news/1'
            },
            'days_date': '2025-01-15'
        },
        {
            'id': 'weather:async_test_001',
            'namespace': 'weather',
            'source_id': 'async_test_001',
            'content': 'Sunny async weather forecast for tomorrow',
            'metadata': {
                'temperature': 75,
                'humidity': 65,
                'forecast_date': '2025-01-16'
            },
            'days_date': '2025-01-15'
        }
    ]
    
    # Insert test data using async methods
    for item in test_data:
        await db.store_data_item(
            id=item['id'],
            namespace=item['namespace'],
            source_id=item['source_id'],
            content=item['content'],
            metadata=item['metadata'],
            days_date=item['days_date']
        )
    
    return db


@pytest.fixture
def async_sample_data_items():
    """Generate sample DataItem objects for async testing"""
    return [
        DataItem(
            id="limitless:async_sample_001",
            namespace="limitless",
            source_id="async_sample_001",
            content="Async sample conversation about AI and productivity",
            metadata={
                "title": "Async AI Productivity Discussion",
                "timestamp": "2025-01-15T14:30:00Z",
                "duration": 1800
            },
            days_date="2025-01-15"
        ),
        DataItem(
            id="news:async_sample_001",
            namespace="news",
            source_id="async_sample_001",
            content="Async latest developments in renewable energy",
            metadata={
                "title": "Async Renewable Energy Advances",
                "published_datetime_utc": "2025-01-15T16:00:00Z",
                "category": "Technology"
            },
            days_date="2025-01-15"
        ),
        DataItem(
            id="twitter:async_sample_001",
            namespace="twitter",
            source_id="async_sample_001",
            content="Async interesting thought about remote work productivity",
            metadata={
                "timestamp": "2025-01-15T18:45:00Z",
                "retweets": 15,
                "likes": 42
            },
            days_date="2025-01-15"
        )
    ]


class AsyncDatabaseTestHelper:
    """Helper class for async database testing operations"""
    
    @staticmethod
    async def insert_data_items(db_service, data_items: List[DataItem]):
        """Insert multiple DataItems into the async database"""
        for item in data_items:
            await db_service.store_data_item(
                id=item.id,
                namespace=item.namespace,
                source_id=item.source_id,
                content=item.content,
                metadata=item.metadata,
                days_date=item.days_date
            )
    
    @staticmethod
    async def count_items_by_namespace(db_service, namespace: str) -> int:
        """Count items in a specific namespace using async operations"""
        async with aiosqlite.connect(db_service.db_path) as conn:
            async with conn.execute(
                "SELECT COUNT(*) FROM data_items WHERE namespace = ?",
                (namespace,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    @staticmethod
    async def get_all_namespaces(db_service) -> List[str]:
        """Get all unique namespaces in the database using async operations"""
        async with aiosqlite.connect(db_service.db_path) as conn:
            async with conn.execute("SELECT DISTINCT namespace FROM data_items") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    @staticmethod
    async def clear_namespace(db_service, namespace: str):
        """Clear all items from a specific namespace using async operations"""
        async with aiosqlite.connect(db_service.db_path) as conn:
            await conn.execute("DELETE FROM data_items WHERE namespace = ?", (namespace,))
            await conn.commit()
    
    @staticmethod
    async def get_table_schema(db_service, table_name: str) -> Dict[str, Any]:
        """Get the schema information for a table using async operations"""
        async with aiosqlite.connect(db_service.db_path) as conn:
            async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
                columns = await cursor.fetchall()
                return {
                    col[1]: {  # col[1] is column name
                        'type': col[2],     # col[2] is data type
                        'notnull': col[3],  # col[3] is not null flag
                        'default': col[4],  # col[4] is default value
                        'pk': col[5]        # col[5] is primary key flag
                    }
                    for col in columns
                }
    
    @staticmethod
    async def verify_migrations_applied(db_service) -> bool:
        """Verify that all migrations have been applied using async operations"""
        try:
            async with aiosqlite.connect(db_service.db_path) as conn:
                # Check for key tables
                async with conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('data_items', 'data_sources', 'migrations')
                """) as cursor:
                    rows = await cursor.fetchall()
                    tables = [row[0] for row in rows]
                    
                    required_tables = ['data_items', 'data_sources', 'migrations']
                    return all(table in tables for table in required_tables)
        except Exception:
            return False


@pytest.fixture
def async_db_helper():
    """Fixture providing the AsyncDatabaseTestHelper class"""
    return AsyncDatabaseTestHelper


@pytest.fixture
def async_isolated_database_test():
    """Context manager for completely isolated async database tests"""
    
    class AsyncIsolatedDatabaseTest:
        def __init__(self):
            self.temp_file = None
            self.db_service = None
        
        async def __aenter__(self):
            self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_isolated_async.db')
            self.temp_file.close()
            self.db_service = AsyncDatabaseService(self.temp_file.name)
            await self.db_service.initialize()
            return self.db_service
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.db_service:
                await self.db_service.close()
            if self.temp_file:
                try:
                    os.unlink(self.temp_file.name)
                except FileNotFoundError:
                    pass
    
    return AsyncIsolatedDatabaseTest


@pytest.fixture
def mock_async_database_service():
    """Mock AsyncDatabaseService for testing without actual database operations"""
    mock_db = AsyncMock()  # spec=AsyncDatabaseService when available
    
    # Configure common async mock behaviors
    mock_db.store_data_item = AsyncMock(return_value=None)
    mock_db.get_data_items_by_namespace = AsyncMock(return_value=[])
    mock_db.get_markdown_by_date = AsyncMock(return_value="# No async data found")
    mock_db.get_all_data_items = AsyncMock(return_value=[])
    mock_db.delete_data_item = AsyncMock(return_value=True)
    mock_db.update_embedding_status = AsyncMock(return_value=None)
    mock_db.fetch_one = AsyncMock(return_value=None)
    mock_db.execute_query = AsyncMock(return_value=None)
    mock_db.initialize = AsyncMock(return_value=None)
    mock_db.close = AsyncMock(return_value=None)
    
    return mock_db


# Async Database Transaction Management

@pytest_asyncio.fixture
async def async_transactional_database(async_clean_database):
    """Async database with automatic transaction rollback for test isolation"""
    
    class AsyncTransactionalDatabase:
        def __init__(self, db_service):
            self.db_service = db_service
            self._connection = None
            self._transaction_active = False
        
        async def __aenter__(self):
            self._connection = await aiosqlite.connect(self.db_service.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("BEGIN")
            self._transaction_active = True
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self._transaction_active:
                await self._connection.execute("ROLLBACK")
            if self._connection:
                await self._connection.close()
        
        async def execute(self, query, params=None):
            """Execute a query within the async transaction"""
            return await self._connection.execute(query, params or ())
        
        async def executemany(self, query, params_list):
            """Execute a query multiple times within the async transaction"""
            return await self._connection.executemany(query, params_list)
        
        async def commit(self):
            """Commit the transaction (test will still rollback on exit)"""
            await self._connection.commit()
    
    return AsyncTransactionalDatabase(async_clean_database)


# Async Performance Testing Fixtures

@pytest_asyncio.fixture
async def async_large_dataset_database(async_clean_database):
    """Async database with a large dataset for performance testing"""
    db = async_clean_database
    
    # Generate a large number of test items for concurrent testing
    async with aiosqlite.connect(db.db_path) as conn:
        # Prepare data for batch insert
        items_data = []
        for i in range(1000):
            metadata = {
                'index': i,
                'category': f'async_category_{i % 10}',
                'timestamp': f'2025-01-{(i % 30) + 1:02d}T{(i % 24):02d}:00:00Z'
            }
            items_data.append((
                f'async_perf_test:{i:04d}',
                'async_perf_test',
                f'{i:04d}',
                f'Async performance test content item {i}' * 10,  # Make content longer
                json.dumps(metadata),
                f'2025-01-{(i % 30) + 1:02d}'
            ))
        
        # Batch insert for performance
        await conn.executemany("""
            INSERT INTO data_items 
            (id, namespace, source_id, content, metadata, days_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, items_data)
        
        await conn.commit()
    
    return db


@pytest_asyncio.fixture
async def async_concurrent_test_database(async_clean_database):
    """Database optimized for concurrent async operation testing"""
    db = async_clean_database
    
    # Pre-populate with data that can be safely accessed concurrently
    async with aiosqlite.connect(db.db_path) as conn:
        concurrent_data = []
        for i in range(50):
            for namespace in ['concurrent_test_a', 'concurrent_test_b', 'concurrent_test_c']:
                concurrent_data.append((
                    f'{namespace}:{i:03d}',
                    namespace,
                    f'{i:03d}',
                    f'Concurrent test content for {namespace} item {i}',
                    json.dumps({'index': i, 'namespace': namespace}),
                    f'2025-01-{(i % 10) + 1:02d}'
                ))
        
        await conn.executemany("""
            INSERT INTO data_items 
            (id, namespace, source_id, content, metadata, days_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, concurrent_data)
        
        await conn.commit()
    
    return db


# AsyncDatabaseService is now imported from core.async_database
# Temporary implementation removed in favor of actual service class


# Export all async fixtures
__all__ = [
    "async_temp_db_path",
    "async_clean_database",
    "async_database_service", 
    "async_memory_database",
    "async_database_with_test_data",
    "async_sample_data_items",
    "async_db_helper",
    "AsyncDatabaseTestHelper",
    "async_isolated_database_test",
    "mock_async_database_service",
    "async_transactional_database",
    "async_large_dataset_database",
    "async_concurrent_test_database"
]