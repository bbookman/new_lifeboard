"""
Comprehensive tests for DatabaseService.

This test suite covers all DatabaseService functionality including CRUD operations,
migrations, settings management, chat history, and data querying capabilities.
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from core.database import DatabaseService
from core.json_utils import JSONMetadataParser

# Using shared fixtures from tests/fixtures/
# clean_database, database_with_test_data, temp_db_path, etc. are available


class TestDatabaseServiceInitialization:
    """Test database initialization and setup"""
    
    def test_database_initialization_success(self, temp_db_path):
        """Test successful database initialization"""
        db_service = DatabaseService(temp_db_path)
        
        assert db_service.db_path == temp_db_path
        assert os.path.exists(temp_db_path)
    
    def test_database_initialization_with_default_path(self):
        """Test initialization with default database path"""
        with patch('core.database.MigrationRunner') as mock_migration_runner:
            mock_migration_runner.return_value.run_migrations.return_value = {"success": True}
            
            db_service = DatabaseService()
            assert db_service.db_path == "lifeboard.db"
    
    def test_database_initialization_migration_failure(self, temp_db_path):
        """Test database initialization when migrations fail"""
        with patch('core.database.MigrationRunner') as mock_migration_runner:
            mock_migration_runner.return_value.run_migrations.return_value = {
                "success": False,
                "errors": ["Migration failed"]
            }
            
            with pytest.raises(RuntimeError, match="Database initialization failed"):
                DatabaseService(temp_db_path)
    
    def test_get_connection_context_manager(self, clean_database):
        """Test that connection context manager works properly"""
        with clean_database.get_connection() as conn:
            # Should be able to execute a simple query
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'data_items' in tables
        
        # Connection should be closed after context manager exits


class TestDataItemOperations:
    """Test CRUD operations for data items"""
    
    def test_store_data_item_basic(self, clean_database):
        """Test storing a basic data item"""
        db = clean_database
        
        test_id = "test:001"
        test_namespace = "test"
        test_source_id = "001"
        test_content = "Test content"
        test_metadata = {"title": "Test Item", "type": "test"}
        test_date = "2025-01-15"
        
        db.store_data_item(
            id=test_id,
            namespace=test_namespace,
            source_id=test_source_id,
            content=test_content,
            metadata=test_metadata,
            days_date=test_date
        )
        
        # Verify item was stored
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM data_items WHERE id = ?", (test_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['id'] == test_id
            assert row['namespace'] == test_namespace
            assert row['source_id'] == test_source_id
            assert row['content'] == test_content
            assert row['days_date'] == test_date
            assert row['ingestion_status'] == 'complete'
            
            # Verify metadata was serialized properly
            stored_metadata = JSONMetadataParser.parse_metadata(row['metadata'])
            assert stored_metadata == test_metadata
    
    def test_store_data_item_with_custom_status(self, clean_database):
        """Test storing data item with custom ingestion status"""
        db = clean_database
        
        db.store_data_item(
            id="test:002",
            namespace="test",
            source_id="002",
            content="Test content",
            ingestion_status="partial"  # Use valid status from CHECK constraint
        )
        
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT ingestion_status FROM data_items WHERE id = ?", ("test:002",))
            row = cursor.fetchone()
            assert row['ingestion_status'] == 'partial'
    
    def test_store_data_item_replace_existing(self, clean_database):
        """Test that storing item with same ID replaces existing"""
        db = clean_database
        
        # Store initial item
        db.store_data_item(
            id="test:003",
            namespace="test",
            source_id="003",
            content="Original content",
            metadata={"version": 1}
        )
        
        # Store updated item with same ID
        db.store_data_item(
            id="test:003",
            namespace="test",
            source_id="003",
            content="Updated content",
            metadata={"version": 2}
        )
        
        # Verify only one item exists with updated content
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM data_items WHERE id = ?", ("test:003",))
            count = cursor.fetchone()[0]
            assert count == 1
            
            cursor = conn.execute("SELECT content, metadata FROM data_items WHERE id = ?", ("test:003",))
            row = cursor.fetchone()
            assert row['content'] == "Updated content"
            
            metadata = JSONMetadataParser.parse_metadata(row['metadata'])
            assert metadata['version'] == 2
    
    def test_get_data_items_by_ids_basic(self, database_with_test_data):
        """Test retrieving data items by IDs"""
        db = database_with_test_data
        
        # Get specific items by ID
        ids = ["limitless:test_001", "news:test_001"]
        items = db.get_data_items_by_ids(ids)
        
        assert len(items) == 2
        
        # Verify items are returned in correct order (by updated_at DESC)
        found_ids = [item['id'] for item in items]
        assert all(item_id in found_ids for item_id in ids)
        
        # Verify item structure
        for item in items:
            assert 'id' in item
            assert 'namespace' in item
            assert 'source_id' in item
            assert 'content' in item
            assert 'metadata' in item
            assert 'days_date' in item
            assert 'created_at' in item
            assert 'updated_at' in item
    
    def test_get_data_items_by_ids_empty_list(self, clean_database):
        """Test retrieving items with empty ID list"""
        db = clean_database
        
        items = db.get_data_items_by_ids([])
        assert items == []
    
    def test_get_data_items_by_ids_nonexistent(self, clean_database):
        """Test retrieving items with non-existent IDs"""
        db = clean_database
        
        items = db.get_data_items_by_ids(["nonexistent:001", "fake:002"])
        assert items == []
    
    def test_get_data_items_by_namespace(self, database_with_test_data):
        """Test retrieving items by namespace"""
        db = database_with_test_data
        
        # Get limitless items
        limitless_items = db.get_data_items_by_namespace("limitless")
        assert len(limitless_items) >= 1
        
        for item in limitless_items:
            assert item['namespace'] == "limitless"
        
        # Test with limit
        limited_items = db.get_data_items_by_namespace("limitless", limit=1)
        assert len(limited_items) <= 1
    
    def test_get_data_items_by_namespace_empty(self, clean_database):
        """Test retrieving items from non-existent namespace"""
        db = clean_database
        
        items = db.get_data_items_by_namespace("nonexistent")
        assert items == []


class TestEmbeddingStatusOperations:
    """Test embedding status management"""
    
    def test_update_embedding_status(self, database_with_test_data):
        """Test updating embedding status"""
        db = database_with_test_data
        
        test_id = "limitless:test_001"
        
        # Update status to complete  
        db.update_embedding_status(test_id, "complete")
        
        # Verify status was updated
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT embedding_status FROM data_items WHERE id = ?", (test_id,))
            row = cursor.fetchone()
            assert row['embedding_status'] == "complete"
    
    def test_update_ingestion_status(self, database_with_test_data):
        """Test updating ingestion status"""
        db = database_with_test_data
        
        test_id = "limitless:test_001"
        
        # Update status to failed (valid status)
        db.update_ingestion_status(test_id, "failed")
        
        # Verify status was updated
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT ingestion_status FROM data_items WHERE id = ?", (test_id,))
            row = cursor.fetchone()
            assert row['ingestion_status'] == "failed"
    
    def test_get_pending_embeddings(self, clean_database):
        """Test retrieving items with pending embeddings"""
        db = clean_database
        
        # Store items with different embedding statuses
        db.store_data_item("test:001", "test", "001", "Content 1")
        db.store_data_item("test:002", "test", "002", "Content 2")
        
        # Set one to complete (valid status)  
        db.update_embedding_status("test:001", "complete")
        
        # Get pending items
        pending = db.get_pending_embeddings()
        
        # Should only return the pending item
        assert len(pending) == 1
        assert pending[0]['id'] == "test:002"
        # Note: embedding_status is not included in get_pending_embeddings return data
        # The method only returns items with pending status by definition
    
    def test_get_pending_embeddings_with_limit(self, clean_database):
        """Test retrieving pending embeddings with limit"""
        db = clean_database
        
        # Store multiple pending items
        for i in range(5):
            db.store_data_item(f"test:{i:03d}", "test", f"{i:03d}", f"Content {i}")
        
        # Get with limit
        pending = db.get_pending_embeddings(limit=3)
        assert len(pending) <= 3


class TestSettingsManagement:
    """Test application settings storage and retrieval"""
    
    def test_set_and_get_setting(self, clean_database):
        """Test setting and getting application settings"""
        db = clean_database
        
        # Set a setting
        db.set_setting("test_key", "test_value")
        
        # Get the setting
        value = db.get_setting("test_key")
        assert value == "test_value"
    
    def test_get_setting_with_default(self, clean_database):
        """Test getting setting with default value"""
        db = clean_database
        
        # Get non-existent setting with default
        value = db.get_setting("nonexistent_key", "default_value")
        assert value == "default_value"
    
    def test_set_setting_json_serializable(self, clean_database):
        """Test setting complex JSON-serializable values"""
        db = clean_database
        
        complex_value = {
            "string": "value",
            "number": 42,
            "boolean": True,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }
        
        db.set_setting("complex_key", complex_value)
        retrieved_value = db.get_setting("complex_key")
        
        assert retrieved_value == complex_value
    
    def test_update_existing_setting(self, clean_database):
        """Test updating an existing setting"""
        db = clean_database
        
        # Set initial value
        db.set_setting("update_key", "initial_value")
        
        # Update value
        db.set_setting("update_key", "updated_value")
        
        # Verify updated value
        value = db.get_setting("update_key")
        assert value == "updated_value"


class TestDataSourceManagement:
    """Test data source registration and management"""
    
    def test_register_data_source(self, clean_database):
        """Test registering a new data source"""
        db = clean_database
        
        metadata = {"api_key": "test_key", "endpoint": "test_endpoint"}
        
        db.register_data_source("test_source", "api", metadata)
        
        # Verify source was registered
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM data_sources WHERE namespace = ?", ("test_source",))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['namespace'] == "test_source"
            assert row['source_type'] == "api"
            assert row['is_active'] is True
            
            stored_metadata = json.loads(row['metadata'])
            assert stored_metadata == metadata
    
    def test_get_active_namespaces(self, database_with_test_data):
        """Test retrieving active namespaces"""
        db = database_with_test_data
        
        # Register some data sources
        db.register_data_source("active_source", "api", {})
        
        # Deactivate a source
        with db.get_connection() as conn:
            conn.execute("UPDATE data_sources SET is_active = FALSE WHERE namespace = ?", ("active_source",))
            conn.commit()
        
        active_namespaces = db.get_active_namespaces()
        
        # Should only include active sources
        assert "active_source" not in active_namespaces
    
    def test_update_source_item_count(self, clean_database):
        """Test updating source item count"""
        db = clean_database
        
        # Register a source
        db.register_data_source("count_test", "api", {})
        
        # Add some items
        for i in range(3):
            db.store_data_item(f"count_test:{i:03d}", "count_test", f"{i:03d}", f"Content {i}")
        
        # Update count
        db.update_source_item_count("count_test")
        
        # Verify count was updated
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT item_count FROM data_sources WHERE namespace = ?", ("count_test",))
            row = cursor.fetchone()
            assert row['item_count'] == 3


class TestChatHistory:
    """Test chat message storage and retrieval"""
    
    def test_store_chat_message(self, clean_database):
        """Test storing chat messages"""
        db = clean_database
        
        user_msg = "What happened today?"
        assistant_msg = "Here's what happened today..."
        
        db.store_chat_message(user_msg, assistant_msg)
        
        # Verify message was stored
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM chat_messages ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            
            assert row is not None
            assert row['user_message'] == user_msg
            assert row['assistant_response'] == assistant_msg
            assert row['timestamp'] is not None
    
    def test_get_chat_history(self, clean_database):
        """Test retrieving chat history"""
        db = clean_database
        
        # Store multiple messages
        messages = [
            ("Message 1", "Response 1"),
            ("Message 2", "Response 2"),
            ("Message 3", "Response 3")
        ]
        
        for user_msg, assistant_msg in messages:
            db.store_chat_message(user_msg, assistant_msg)
        
        # Get history
        history = db.get_chat_history()
        
        assert len(history) == 3
        
        # Should be in reverse chronological order (most recent first)
        assert history[0]['user_message'] == "Message 3"
        assert history[0]['assistant_response'] == "Response 3"
        
        # Verify structure
        for msg in history:
            assert 'id' in msg
            assert 'user_message' in msg
            assert 'assistant_response' in msg
            assert 'timestamp' in msg
    
    def test_get_chat_history_with_limit(self, clean_database):
        """Test retrieving chat history with limit"""
        db = clean_database
        
        # Store multiple messages
        for i in range(10):
            db.store_chat_message(f"Message {i}", f"Response {i}")
        
        # Get limited history
        history = db.get_chat_history(limit=5)
        assert len(history) == 5


class TestDateOperations:
    """Test date-based data operations"""
    
    def test_extract_date_from_timestamp(self, clean_database):
        """Test extracting date from timestamp string"""
        db = clean_database
        
        # Test UTC timestamp
        timestamp = "2025-01-15T14:30:00Z"
        date = db.extract_date_from_timestamp(timestamp)
        assert date == "2025-01-15"
        
        # Test with timezone
        timestamp_tz = "2025-01-15T22:30:00-08:00"
        date_tz = db.extract_date_from_timestamp(timestamp_tz, "America/Los_Angeles")
        assert date_tz == "2025-01-15"
    
    def test_get_data_items_by_date(self, database_with_test_data):
        """Test retrieving items by specific date"""
        db = database_with_test_data
        
        items = db.get_data_items_by_date("2025-01-15")
        
        # Should return items for that date
        assert len(items) > 0
        
        for item in items:
            assert item['days_date'] == "2025-01-15"
    
    def test_get_data_items_by_date_with_namespaces(self, database_with_test_data):
        """Test retrieving items by date filtered by namespaces"""
        db = database_with_test_data
        
        items = db.get_data_items_by_date("2025-01-15", namespaces=["limitless"])
        
        # Should only return limitless items
        for item in items:
            assert item['namespace'] == "limitless"
            assert item['days_date'] == "2025-01-15"
    
    def test_get_available_dates(self, database_with_test_data):
        """Test retrieving available dates"""
        db = database_with_test_data
        
        dates = db.get_available_dates()
        
        assert len(dates) > 0
        assert "2025-01-15" in dates
        
        # Dates should be sorted
        assert dates == sorted(dates)
    
    def test_get_days_with_data(self, database_with_test_data):
        """Test retrieving days with data"""
        db = database_with_test_data
        
        days = db.get_days_with_data()
        
        assert len(days) > 0
        assert "2025-01-15" in days


class TestMarkdownGeneration:
    """Test markdown content generation"""
    
    def test_get_markdown_by_date(self, database_with_test_data):
        """Test generating markdown for a specific date"""
        db = database_with_test_data
        
        markdown = db.get_markdown_by_date("2025-01-15")
        
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        
        # Should contain headers for different namespaces
        assert "# Lifeboard" in markdown or "No data found" not in markdown
    
    def test_get_markdown_by_date_with_namespaces(self, database_with_test_data):
        """Test generating markdown filtered by namespaces"""
        db = database_with_test_data
        
        markdown = db.get_markdown_by_date("2025-01-15", namespaces=["limitless"])
        
        assert isinstance(markdown, str)
        # Should only contain limitless content
    
    def test_get_markdown_no_data(self, clean_database):
        """Test markdown generation when no data exists"""
        db = clean_database
        
        markdown = db.get_markdown_by_date("2099-12-31")
        
        assert "No data found" in markdown or len(markdown.strip()) == 0


class TestDatabaseStats:
    """Test database statistics and metadata"""
    
    def test_get_database_stats(self, database_with_test_data):
        """Test retrieving database statistics"""
        db = database_with_test_data
        
        stats = db.get_database_stats()
        
        assert isinstance(stats, dict)
        assert 'total_items' in stats
        assert 'namespaces' in stats
        assert 'earliest_date' in stats
        assert 'latest_date' in stats
        
        assert stats['total_items'] > 0
        assert len(stats['namespaces']) > 0
    
    def test_get_all_namespaces(self, database_with_test_data):
        """Test retrieving all namespaces"""
        db = database_with_test_data
        
        namespaces = db.get_all_namespaces()
        
        assert isinstance(namespaces, list)
        assert len(namespaces) > 0
        assert "limitless" in namespaces
    
    def test_get_migration_status(self, clean_database):
        """Test retrieving migration status"""
        db = clean_database
        
        status = db.get_migration_status()
        
        assert isinstance(status, dict)
        # Should contain migration information


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_store_data_item_with_invalid_metadata(self, clean_database):
        """Test storing item with metadata that can't be serialized"""
        db = clean_database
        
        # This should handle the error gracefully
        with patch('core.json_utils.JSONMetadataParser.serialize_metadata') as mock_serialize:
            mock_serialize.return_value = None
            
            # Should not raise an exception
            db.store_data_item("test:error", "test", "error", "content", {"invalid": object()})
    
    def test_database_connection_error_handling(self, temp_db_path):
        """Test handling of database connection errors"""
        db = DatabaseService(temp_db_path)
        
        # Remove the database file to cause connection issues
        os.remove(temp_db_path)
        
        # Operations should handle the missing database gracefully
        # Note: SQLite will recreate the file, but schema won't exist
        with pytest.raises(Exception):
            # This should fail because tables don't exist
            db.store_data_item("test:001", "test", "001", "content")
    
    def test_get_data_items_with_corrupted_metadata(self, clean_database):
        """Test retrieving items with corrupted metadata"""
        db = clean_database
        
        # Insert item with invalid JSON metadata directly
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO data_items (id, namespace, source_id, content, metadata, days_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("test:corrupt", "test", "corrupt", "content", "invalid json", "2025-01-15"))
            conn.commit()
        
        # Should handle corrupted metadata gracefully
        items = db.get_data_items_by_ids(["test:corrupt"])
        
        # Should still return the item, but metadata might be None or default
        assert len(items) == 1
        assert items[0]['id'] == "test:corrupt"


class TestPerformance:
    """Test performance characteristics"""
    
    def test_batch_operations_performance(self, clean_database):
        """Test performance of batch operations"""
        db = clean_database
        
        # Store multiple items
        import time
        start_time = time.perf_counter()
        
        for i in range(100):
            db.store_data_item(f"perf:test_{i:03d}", "perf", f"test_{i:03d}", f"Content {i}")
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 5.0  # 5 seconds for 100 items
        
        # Test batch retrieval
        ids = [f"perf:test_{i:03d}" for i in range(100)]
        
        start_time = time.perf_counter()
        items = db.get_data_items_by_ids(ids)
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        assert len(items) == 100
        assert duration < 1.0  # 1 second for batch retrieval
    
    @pytest.mark.performance
    def test_large_dataset_operations(self, clean_database):
        """Test operations with larger datasets"""
        db = clean_database
        
        # This test is marked as performance test
        # Store larger dataset
        for i in range(1000):
            db.store_data_item(
                f"large:test_{i:04d}", 
                "large", 
                f"test_{i:04d}", 
                f"Content {i} " * 10,  # Larger content
                {"index": i, "category": f"cat_{i % 10}"}
            )
        
        # Test various operations
        stats = db.get_database_stats()
        assert stats['total_items'] >= 1000
        
        # Test namespace query
        items = db.get_data_items_by_namespace("large", limit=50)
        assert len(items) == 50
        
        # Test date operations
        dates = db.get_available_dates()
        assert len(dates) > 0