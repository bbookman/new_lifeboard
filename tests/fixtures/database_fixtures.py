"""
Database fixtures for isolated test database lifecycle management.

This module provides comprehensive database testing utilities including
temporary database creation, test data population, and cleanup management.
"""

import pytest
import pytest_asyncio
import tempfile
import os
import sqlite3
import aiosqlite
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from contextlib import contextmanager
from unittest.mock import Mock, MagicMock, AsyncMock

# Sync DatabaseService removed - use AsyncDatabaseService only
from core.async_database import AsyncDatabaseService
from core.migrations.runner import MigrationRunner
from sources.base import DataItem


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file path for testing"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    yield temp_db.name
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except FileNotFoundError:
        pass


# Legacy sync database fixtures removed - use async fixtures only


# Legacy sync database_service fixture removed - use async_database_service


# Legacy sync memory_database fixture removed - use async_memory_database


# Async Database Fixtures

@pytest_asyncio.fixture(scope="function")
async def async_clean_database(temp_db_path):
    """Create a clean async database with migrations applied"""
    db_service = AsyncDatabaseService(temp_db_path)
    await db_service.initialize()
    yield db_service
    await db_service.close()


@pytest_asyncio.fixture(scope="function") 
async def async_database_service(async_clean_database):
    """Alias for async_clean_database for consistency"""
    return async_clean_database


@pytest_asyncio.fixture
async def async_memory_database():
    """Create an in-memory async database for fast testing"""
    db_service = AsyncDatabaseService(":memory:")
    await db_service.initialize()
    return db_service


# Legacy sync database_with_test_data fixture removed - use async_database_with_test_data


@pytest_asyncio.fixture
async def async_database_with_test_data(async_clean_database):
    """Async database pre-populated with test data"""
    db = async_clean_database
    
    # Sample test data
    test_data = [
        {
            'id': 'limitless:test_001',
            'namespace': 'limitless',
            'source_id': 'test_001',
            'content': 'Test meeting discussion about project planning',
            'metadata': {
                'title': 'Project Planning Meeting',
                'start_time': '2025-01-15T09:00:00Z',
                'end_time': '2025-01-15T10:00:00Z',
                'participants': ['Alice', 'Bob']
            },
            'days_date': '2025-01-15'
        },
        {
            'id': 'news:test_001',
            'namespace': 'news',
            'source_id': 'test_001',
            'content': 'Breaking news about technology advancement',
            'metadata': {
                'title': 'Tech Breakthrough',
                'published_datetime_utc': '2025-01-15T12:00:00Z',
                'link': 'https://example.com/news/1'
            },
            'days_date': '2025-01-15'
        },
        {
            'id': 'weather:test_001',
            'namespace': 'weather',
            'source_id': 'test_001',
            'content': 'Sunny weather forecast for tomorrow',
            'metadata': {
                'temperature': 75,
                'humidity': 65,
                'forecast_date': '2025-01-16'
            },
            'days_date': '2025-01-15'
        }
    ]
    
    # Insert test data
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
def sample_data_items():
    """Generate sample DataItem objects for testing"""
    return [
        DataItem(
            id="limitless:sample_001",
            namespace="limitless",
            source_id="sample_001",
            content="Sample conversation about AI and productivity",
            metadata={
                "title": "AI Productivity Discussion",
                "timestamp": "2025-01-15T14:30:00Z",
                "duration": 1800
            },
            days_date="2025-01-15"
        ),
        DataItem(
            id="news:sample_001",
            namespace="news",
            source_id="sample_001",
            content="Latest developments in renewable energy",
            metadata={
                "title": "Renewable Energy Advances",
                "published_datetime_utc": "2025-01-15T16:00:00Z",
                "category": "Technology"
            },
            days_date="2025-01-15"
        ),
        DataItem(
            id="twitter:sample_001",
            namespace="twitter",
            source_id="sample_001",
            content="Interesting thought about remote work productivity",
            metadata={
                "timestamp": "2025-01-15T18:45:00Z",
                "retweets": 15,
                "likes": 42
            },
            days_date="2025-01-15"
        )
    ]


# Legacy sync DatabaseTestHelper class removed - use async patterns only


# Legacy sync db_helper fixture removed


# Legacy sync isolated_database_test fixture removed


# Legacy sync mock_database_service fixture removed


# Database Transaction Management

# Legacy sync transactional_database fixture removed


# Specialized Database Scenarios

# Legacy sync corrupted_database_scenario fixture removed


# Legacy sync readonly_database_scenario fixture removed


# Legacy sync large_dataset_database fixture removed


# Migration Testing

@pytest.fixture
def migration_test_database():
    """Database for testing migration scenarios"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    # Create database but don't run migrations
    conn = sqlite3.connect(temp_file.name)
    conn.close()
    
    yield temp_file.name
    
    # Cleanup
    try:
        os.unlink(temp_file.name)
    except FileNotFoundError:
        pass


@pytest.fixture
def pre_migration_database(migration_test_database):
    """Database in pre-migration state for testing migration logic"""
    # Create an old schema version for testing migrations
    conn = sqlite3.connect(migration_test_database)
    
    # Create old schema (example)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS old_data (
            id INTEGER PRIMARY KEY,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert some test data
    conn.execute("INSERT INTO old_data (content) VALUES (?)", ("Old format data",))
    conn.commit()
    conn.close()
    
    return migration_test_database


# Export async fixtures only
__all__ = [
    "temp_db_path",
    "async_clean_database",
    "async_database_service", 
    "async_memory_database",
    "async_database_with_test_data",
    "sample_data_items",
    "migration_test_database",
    "pre_migration_database"
]