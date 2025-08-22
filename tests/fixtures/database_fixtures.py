"""
Database fixtures for isolated test database lifecycle management.

This module provides comprehensive database testing utilities including
temporary database creation, test data population, and cleanup management.
"""

import json
import os
import sqlite3
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from core.database import DatabaseService
from sources.base import DataItem


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file path for testing"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()

    yield temp_db.name

    # Cleanup
    try:
        os.unlink(temp_db.name)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="function")
def clean_database(temp_db_path):
    """Create a clean database with migrations applied"""
    db_service = DatabaseService(temp_db_path)
    return db_service

    # Cleanup handled by temp_db_path fixture


@pytest.fixture(scope="function")
def database_service(clean_database):
    """Alias for clean_database for consistency"""
    return clean_database


@pytest.fixture
def memory_database():
    """Create an in-memory database for fast testing"""
    db_service = DatabaseService(":memory:")
    return db_service


@pytest.fixture
def database_with_test_data(clean_database):
    """Database pre-populated with test data"""
    db = clean_database

    # Sample test data
    test_data = [
        {
            "id": "limitless:test_001",
            "namespace": "limitless",
            "source_id": "test_001",
            "content": "Test meeting discussion about project planning",
            "metadata": {
                "title": "Project Planning Meeting",
                "start_time": "2025-01-15T09:00:00Z",
                "end_time": "2025-01-15T10:00:00Z",
                "participants": ["Alice", "Bob"],
            },
            "days_date": "2025-01-15",
        },
        {
            "id": "news:test_001",
            "namespace": "news",
            "source_id": "test_001",
            "content": "Breaking news about technology advancement",
            "metadata": {
                "title": "Tech Breakthrough",
                "published_datetime_utc": "2025-01-15T12:00:00Z",
                "link": "https://example.com/news/1",
            },
            "days_date": "2025-01-15",
        },
        {
            "id": "weather:test_001",
            "namespace": "weather",
            "source_id": "test_001",
            "content": "Sunny weather forecast for tomorrow",
            "metadata": {
                "temperature": 75,
                "humidity": 65,
                "forecast_date": "2025-01-16",
            },
            "days_date": "2025-01-15",
        },
    ]

    # Insert test data
    for item in test_data:
        db.store_data_item(
            id=item["id"],
            namespace=item["namespace"],
            source_id=item["source_id"],
            content=item["content"],
            metadata=item["metadata"],
            days_date=item["days_date"],
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
                "duration": 1800,
            },
            days_date="2025-01-15",
        ),
        DataItem(
            id="news:sample_001",
            namespace="news",
            source_id="sample_001",
            content="Latest developments in renewable energy",
            metadata={
                "title": "Renewable Energy Advances",
                "published_datetime_utc": "2025-01-15T16:00:00Z",
                "category": "Technology",
            },
            days_date="2025-01-15",
        ),
        DataItem(
            id="twitter:sample_001",
            namespace="twitter",
            source_id="sample_001",
            content="Interesting thought about remote work productivity",
            metadata={
                "timestamp": "2025-01-15T18:45:00Z",
                "retweets": 15,
                "likes": 42,
            },
            days_date="2025-01-15",
        ),
    ]


class DatabaseTestHelper:
    """Helper class for database testing operations"""

    @staticmethod
    def insert_data_items(db_service: DatabaseService, data_items: List[DataItem]):
        """Insert multiple DataItems into the database"""
        for item in data_items:
            db_service.store_data_item(
                id=item.id,
                namespace=item.namespace,
                source_id=item.source_id,
                content=item.content,
                metadata=item.metadata,
                days_date=item.days_date,
            )

    @staticmethod
    def count_items_by_namespace(db_service: DatabaseService, namespace: str) -> int:
        """Count items in a specific namespace"""
        with db_service.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM data_items WHERE namespace = ?",
                (namespace,),
            )
            return cursor.fetchone()[0]

    @staticmethod
    def get_all_namespaces(db_service: DatabaseService) -> List[str]:
        """Get all unique namespaces in the database"""
        with db_service.get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT namespace FROM data_items")
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def clear_namespace(db_service: DatabaseService, namespace: str):
        """Clear all items from a specific namespace"""
        with db_service.get_connection() as conn:
            conn.execute("DELETE FROM data_items WHERE namespace = ?", (namespace,))
            conn.commit()

    @staticmethod
    def get_table_schema(db_service: DatabaseService, table_name: str) -> Dict[str, Any]:
        """Get the schema information for a table"""
        with db_service.get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            return {
                col[1]: {  # col[1] is column name
                    "type": col[2],     # col[2] is data type
                    "notnull": col[3],  # col[3] is not null flag
                    "default": col[4],  # col[4] is default value
                    "pk": col[5],        # col[5] is primary key flag
                }
                for col in columns
            }

    @staticmethod
    def verify_migrations_applied(db_service: DatabaseService) -> bool:
        """Verify that all migrations have been applied"""
        try:
            with db_service.get_connection() as conn:
                # Check for key tables
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('data_items', 'data_sources', 'migrations')
                """)
                tables = [row[0] for row in cursor.fetchall()]

                required_tables = ["data_items", "data_sources", "migrations"]
                return all(table in tables for table in required_tables)
        except Exception:
            return False


@pytest.fixture
def db_helper():
    """Fixture providing the DatabaseTestHelper class"""
    return DatabaseTestHelper


@pytest.fixture
def isolated_database_test():
    """Context manager for completely isolated database tests"""

    class IsolatedDatabaseTest:
        def __init__(self):
            self.temp_file = None
            self.db_service = None

        def __enter__(self):
            self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            self.temp_file.close()
            self.db_service = DatabaseService(self.temp_file.name)
            return self.db_service

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.temp_file:
                try:
                    os.unlink(self.temp_file.name)
                except FileNotFoundError:
                    pass

    return IsolatedDatabaseTest


@pytest.fixture
def mock_database_service():
    """Mock DatabaseService for testing without actual database operations"""
    mock_db = MagicMock(spec=DatabaseService)

    # Configure common mock behaviors
    mock_db.store_data_item.return_value = None
    mock_db.get_data_items_by_namespace.return_value = []
    mock_db.get_markdown_by_date.return_value = "# No data found"
    mock_db.get_all_data_items.return_value = []
    mock_db.delete_data_item.return_value = True
    mock_db.update_embedding_status.return_value = None

    return mock_db


# Database Transaction Management

@pytest.fixture
def transactional_database(clean_database):
    """Database with automatic transaction rollback for test isolation"""

    class TransactionalDatabase:
        def __init__(self, db_service):
            self.db_service = db_service
            self._connection = None
            self._transaction_active = False

        def __enter__(self):
            self._connection = sqlite3.connect(self.db_service.db_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("BEGIN")
            self._transaction_active = True
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._transaction_active:
                self._connection.execute("ROLLBACK")
            if self._connection:
                self._connection.close()

        def execute(self, query, params=None):
            """Execute a query within the transaction"""
            return self._connection.execute(query, params or ())

        def executemany(self, query, params_list):
            """Execute a query multiple times within the transaction"""
            return self._connection.executemany(query, params_list)

        def commit(self):
            """Commit the transaction (test will still rollback on exit)"""
            self._connection.commit()

    return TransactionalDatabase(clean_database)


# Specialized Database Scenarios

@pytest.fixture
def corrupted_database_scenario(temp_db_path):
    """Create a scenario with a corrupted database for error testing"""
    # Create database and then corrupt it
    db_service = DatabaseService(temp_db_path)

    # Corrupt the database by writing invalid data
    with open(temp_db_path, "w") as f:
        f.write("This is not a valid SQLite database")

    return temp_db_path


@pytest.fixture
def readonly_database_scenario(database_with_test_data, temp_db_path):
    """Create a read-only database scenario"""
    # Make the database file read-only
    os.chmod(temp_db_path, 0o444)

    yield database_with_test_data

    # Restore write permissions for cleanup
    os.chmod(temp_db_path, 0o644)


@pytest.fixture
def large_dataset_database(clean_database):
    """Database with a large dataset for performance testing"""
    db = clean_database

    # Generate a large number of test items
    items = []
    for i in range(1000):
        items.append({
            "id": f"perf_test:{i:04d}",
            "namespace": "perf_test",
            "source_id": f"{i:04d}",
            "content": f"Performance test content item {i}" * 10,  # Make content longer
            "metadata": {
                "index": i,
                "category": f"category_{i % 10}",
                "timestamp": f"2025-01-{(i % 30) + 1:02d}T{(i % 24):02d}:00:00Z",
            },
            "days_date": f"2025-01-{(i % 30) + 1:02d}",
        })

    # Batch insert for performance
    with db.get_connection() as conn:
        for item in items:
            conn.execute("""
                INSERT INTO data_items 
                (id, namespace, source_id, content, metadata, days_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                item["id"], item["namespace"], item["source_id"],
                item["content"], json.dumps(item["metadata"]), item["days_date"],
            ))
        conn.commit()

    return db


# Migration Testing

@pytest.fixture
def migration_test_database():
    """Database for testing migration scenarios"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
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


# Export all fixtures
__all__ = [
    "DatabaseTestHelper",
    "clean_database",
    "corrupted_database_scenario",
    "database_service",
    "database_with_test_data",
    "db_helper",
    "isolated_database_test",
    "large_dataset_database",
    "memory_database",
    "migration_test_database",
    "mock_database_service",
    "pre_migration_database",
    "readonly_database_scenario",
    "sample_data_items",
    "temp_db_path",
    "transactional_database",
]
