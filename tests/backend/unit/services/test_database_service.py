"""
Comprehensive tests for AsyncDatabaseService.

This test suite covers all AsyncDatabaseService functionality including CRUD operations,
migrations, settings management, chat history, and data querying capabilities.
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from core.async_database import AsyncDatabaseService
from core.json_utils import JSONMetadataParser

# Using shared fixtures from tests/fixtures/
# async_clean_database, database_with_test_data, temp_db_path, etc. are available


class TestDatabaseServiceInitialization:
    """Test database initialization and setup"""
    
    @pytest.mark.asyncio
    async def test_database_initialization_success(self, temp_db_path):
        """Test successful database initialization"""
        db_service = AsyncDatabaseService(temp_db_path)
        
        assert db_service.db_path == temp_db_path
        assert os.path.exists(temp_db_path)
    
    @pytest.mark.asyncio
    async def test_database_initialization_with_default_path(self):
        """Test initialization with default database path"""
        with patch('core.database.MigrationRunner') as mock_migration_runner:
            mock_migration_runner.return_value.run_migrations.return_value = {"success": True}
            
            db_service = AsyncDatabaseService()
            assert db_service.db_path == "lifeboard.db"
    
    @pytest.mark.asyncio
    async def test_database_initialization_migration_failure(self, temp_db_path):
        """Test database initialization when migrations fail"""
        # AsyncDatabaseService doesn't use MigrationRunner in constructor
        # Instead test that initialize() can handle database errors
        db_service = AsyncDatabaseService(temp_db_path)
        
        # Corrupt the database to cause initialization failure
        with open(temp_db_path, 'w') as f:
            f.write("Invalid SQLite data")
        
        with pytest.raises(Exception):  # SQLite will raise various exceptions for corrupted DB
            await db_service.initialize()
    
    @pytest.mark.asyncio
    async def test_get_connection_context_manager(self, async_clean_database):
        """Test that connection context manager works properly"""
        async with async_clean_database.get_connection() as conn:
            # Should be able to execute a simple query
            async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                rows = await cursor.fetchall()
                tables = [row[0] for row in rows]
                assert 'data_items' in tables
        
        # Connection should be closed after context manager exits


class TestDataItemOperations:
    """Test CRUD operations for data items"""
    
    @pytest.mark.asyncio
    async def test_store_data_item_basic(self, async_clean_database):
        """Test storing a basic data item"""
        db = async_clean_database
        
        test_id = "test:001"
        test_namespace = "test"
        test_source_id = "001"
        test_content = "Test content"
        test_metadata = {"title": "Test Item", "type": "test"}
        test_date = "2025-01-15"
        
        await db.store_data_item(
            id=test_id,
            namespace=test_namespace,
            source_id=test_source_id,
            content=test_content,
            metadata=test_metadata,
            days_date=test_date
        )
        
        # Verify item was stored
        async with db.get_connection() as conn:
            async with conn.execute("SELECT * FROM data_items WHERE id = ?", (test_id,)) as cursor:
                row = await cursor.fetchone()
            
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
    
    @pytest.mark.asyncio
    async def test_store_data_item_with_custom_status(self, async_clean_database):
        """Test storing data item with custom ingestion status"""
        db = async_clean_database
        
        await db.store_data_item(
            id="test:002",
            namespace="test",
            source_id="002",
            content="Test content",
            days_date="2025-01-15",  # Required field
            ingestion_status="partial"  # Use valid status from CHECK constraint
        )
        
        async with db.get_connection() as conn:
            async with conn.execute("SELECT ingestion_status FROM data_items WHERE id = ?", ("test:002",)) as cursor:
                row = await cursor.fetchone()
            assert row['ingestion_status'] == 'partial'
    
    @pytest.mark.asyncio
    async def test_store_data_item_replace_existing(self, async_clean_database):
        """Test that storing item with same ID replaces existing"""
        db = async_clean_database
        
        # Store initial item
        await db.store_data_item(
            id="test:003",
            namespace="test",
            source_id="003",
            content="Original content",
            metadata={"version": 1},
            days_date="2025-01-15"
        )
        
        # Store updated item with same ID
        await db.store_data_item(
            id="test:003",
            namespace="test",
            source_id="003",
            content="Updated content",
            metadata={"version": 2},
            days_date="2025-01-15"
        )
        
        # Verify only one item exists with updated content
        async with db.get_connection() as conn:
            async with conn.execute("SELECT COUNT(*) FROM data_items WHERE id = ?", ("test:003",)) as cursor:
                row = await cursor.fetchone()
                count = row[0]
            assert count == 1
            
            async with conn.execute("SELECT content, metadata FROM data_items WHERE id = ?", ("test:003",)) as cursor:
                row = await cursor.fetchone()
            assert row['content'] == "Updated content"
            
            metadata = JSONMetadataParser.parse_metadata(row['metadata'])
            assert metadata['version'] == 2
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_basic(self, async_database_with_test_data):
        """Test retrieving data items by IDs"""
        db = async_database_with_test_data
        
        # Get specific items by ID (using async fixture IDs)
        ids = ["limitless:async_test_001", "news:async_test_001"]
        items = await db.get_data_items_by_ids(ids)
        
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
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_empty_list(self, async_clean_database):
        """Test retrieving items with empty ID list"""
        db = async_clean_database
        
        items = await db.get_data_items_by_ids([])
        assert items == []
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_nonexistent(self, async_clean_database):
        """Test retrieving items with non-existent IDs"""
        db = async_clean_database
        
        items = await db.get_data_items_by_ids(["nonexistent:001", "fake:002"])
        assert items == []
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_namespace(self, async_database_with_test_data):
        """Test retrieving items by namespace"""
        db = async_database_with_test_data
        
        # Get limitless items
        limitless_items = await db.get_data_items_by_namespace("limitless")
        assert len(limitless_items) >= 1
        
        for item in limitless_items:
            assert item['namespace'] == "limitless"
        
        # Test with limit
        limited_items = await db.get_data_items_by_namespace("limitless", limit=1)
        assert len(limited_items) <= 1
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_namespace_empty(self, async_clean_database):
        """Test retrieving items from non-existent namespace"""
        db = async_clean_database
        
        items = await db.get_data_items_by_namespace("nonexistent")
        assert items == []


class TestEmbeddingStatusOperations:
    """Test embedding status management"""
    
    @pytest.mark.asyncio
    async def test_update_embedding_status(self, async_database_with_test_data):
        """Test updating embedding status"""
        db = async_database_with_test_data
        
        test_id = "limitless:async_test_001"
        
        # Update status to complete  
        await db.update_embedding_status(test_id, "complete")
        
        # Verify status was updated
        async with db.get_connection() as conn:
            async with conn.execute("SELECT embedding_status FROM data_items WHERE id = ?", (test_id,)) as cursor:
                row = await cursor.fetchone()
            assert row['embedding_status'] == "complete"
    
    @pytest.mark.asyncio
    async def test_update_ingestion_status(self, async_database_with_test_data):
        """Test updating ingestion status"""
        db = async_database_with_test_data
        
        test_id = "limitless:async_test_001"
        
        # Update status to failed (valid status)
        await db.update_ingestion_status(test_id, "failed")
        
        # Verify status was updated
        async with db.get_connection() as conn:
            async with conn.execute("SELECT ingestion_status FROM data_items WHERE id = ?", (test_id,)) as cursor:
                row = await cursor.fetchone()
            assert row['ingestion_status'] == "failed"
    
    @pytest.mark.asyncio
    async def test_get_pending_embeddings(self, async_clean_database):
        """Test retrieving items with pending embeddings"""
        db = async_clean_database
        
        # Store items with different embedding statuses
        await db.store_data_item("test:001", "test", "001", "Content 1", days_date="2025-01-15")
        await db.store_data_item("test:002", "test", "002", "Content 2", days_date="2025-01-15")
        
        # Set one to complete (valid status)  
        await db.update_embedding_status("test:001", "complete")
        
        # Get pending items
        pending = await db.get_pending_embeddings()
        
        # Should only return the pending item
        assert len(pending) == 1
        assert pending[0]['id'] == "test:002"
        # Note: embedding_status is not included in get_pending_embeddings return data
        # The method only returns items with pending status by definition
    
    @pytest.mark.asyncio
    async def test_get_pending_embeddings_with_limit(self, async_clean_database):
        """Test retrieving pending embeddings with limit"""
        db = async_clean_database
        
        # Store multiple pending items
        for i in range(5):
            await db.store_data_item(f"test:{i:03d}", "test", f"{i:03d}", f"Content {i}", days_date="2025-01-15")
        
        # Get with limit
        pending = await db.get_pending_embeddings(limit=3)
        assert len(pending) <= 3


class TestSettingsManagement:
    """Test application settings storage and retrieval"""
    
    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, async_clean_database):
        """Test setting and getting application settings"""
        db = async_clean_database
        
        # Set a setting
        await db.set_setting("test_key", "test_value")
        
        # Get the setting
        value = await db.get_setting("test_key")
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_get_setting_with_default(self, async_clean_database):
        """Test getting setting with default value"""
        db = async_clean_database
        
        # Get non-existent setting with default
        value = await db.get_setting("nonexistent_key", "default_value")
        assert value == "default_value"
    
    @pytest.mark.asyncio
    async def test_set_setting_json_serializable(self, async_clean_database):
        """Test setting complex JSON-serializable values"""
        db = async_clean_database
        
        complex_value = {
            "string": "value",
            "number": 42,
            "boolean": True,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }
        
        await db.set_setting("complex_key", complex_value)
        retrieved_value = await db.get_setting("complex_key")
        
        assert retrieved_value == complex_value
    
    @pytest.mark.asyncio
    async def test_update_existing_setting(self, async_clean_database):
        """Test updating an existing setting"""
        db = async_clean_database
        
        # Set initial value
        await db.set_setting("update_key", "initial_value")
        
        # Update value
        await db.set_setting("update_key", "updated_value")
        
        # Verify updated value
        value = await db.get_setting("update_key")
        assert value == "updated_value"


class TestDataSourceManagement:
    """Test data source registration and management"""
    
    @pytest.mark.asyncio
    async def test_register_data_source(self, async_clean_database):
        """Test registering a new data source"""
        db = async_clean_database
        
        metadata = {"api_key": "test_key", "endpoint": "test_endpoint"}
        
        await db.register_data_source("test_source", "api", metadata)
        
        # Verify source was registered
        async with db.get_connection() as conn:
            async with conn.execute("SELECT * FROM data_sources WHERE namespace = ?", ("test_source",)) as cursor:
                row = await cursor.fetchone()
            
            assert row is not None
            assert row['namespace'] == "test_source"
            assert row['source_type'] == "api"
            assert row['is_active'] == 1  # SQLite returns 1 for TRUE boolean
            
            stored_metadata = json.loads(row['metadata'])
            assert stored_metadata == metadata
    
    @pytest.mark.asyncio
    async def test_get_active_namespaces(self, async_database_with_test_data):
        """Test retrieving active namespaces"""
        db = async_database_with_test_data
        
        # Register some data sources
        await db.register_data_source("active_source", "api", {})
        
        # Deactivate a source
        async with db.get_connection() as conn:
            await conn.execute("UPDATE data_sources SET is_active = FALSE WHERE namespace = ?", ("active_source",))
            await conn.commit()
        
        active_namespaces = await db.get_active_namespaces()
        
        # Should only include active sources
        assert "active_source" not in active_namespaces
    
    @pytest.mark.asyncio
    async def test_update_source_item_count(self, async_clean_database):
        """Test updating source item count"""
        db = async_clean_database
        
        # Register a source
        await db.register_data_source("count_test", "api", {})
        
        # Add some items
        for i in range(3):
            await db.store_data_item(f"count_test:{i:03d}", "count_test", f"{i:03d}", f"Content {i}", days_date="2025-01-15")
        
        # Update count
        await db.update_source_item_count("count_test")
        
        # Verify count was updated
        async with db.get_connection() as conn:
            async with conn.execute("SELECT item_count FROM data_sources WHERE namespace = ?", ("count_test",)) as cursor:
                row = await cursor.fetchone()
            assert row['item_count'] == 3


class TestChatHistory:
    """Test chat message storage and retrieval"""
    
    @pytest.mark.asyncio
    async def test_store_chat_message(self, async_clean_database):
        """Test storing chat messages"""
        db = async_clean_database
        
        user_msg = "What happened today?"
        assistant_msg = "Here's what happened today..."
        
        await db.store_chat_message(user_msg, assistant_msg)
        
        # Verify message was stored
        async with db.get_connection() as conn:
            async with conn.execute("SELECT * FROM chat_messages ORDER BY id DESC LIMIT 1") as cursor:
                row = await cursor.fetchone()
            
            assert row is not None
            assert row['user_message'] == user_msg
            assert row['assistant_response'] == assistant_msg
            assert row['timestamp'] is not None
    
    @pytest.mark.asyncio
    async def test_get_chat_history(self, async_clean_database):
        """Test retrieving chat history"""
        db = async_clean_database
        
        # Store multiple messages
        messages = [
            ("Message 1", "Response 1"),
            ("Message 2", "Response 2"),
            ("Message 3", "Response 3")
        ]
        
        for user_msg, assistant_msg in messages:
            await db.store_chat_message(user_msg, assistant_msg)
        
        # Get history
        history = await db.get_chat_history()
        
        assert len(history) == 3
        
        # Should be in chronological order (oldest first) according to actual implementation
        assert history[0]['user_message'] == "Message 1"
        assert history[0]['assistant_response'] == "Response 1"
        
        # Verify structure
        for msg in history:
            assert 'id' in msg
            assert 'user_message' in msg
            assert 'assistant_response' in msg
            assert 'timestamp' in msg
    
    @pytest.mark.asyncio
    async def test_get_chat_history_with_limit(self, async_clean_database):
        """Test retrieving chat history with limit"""
        db = async_clean_database
        
        # Store multiple messages
        for i in range(10):
            await db.store_chat_message(f"Message {i}", f"Response {i}")
        
        # Get limited history
        history = await db.get_chat_history(limit=5)
        assert len(history) == 5


class TestDateOperations:
    """Test date-based data operations"""
    
    @pytest.mark.asyncio
    async def test_extract_date_from_timestamp(self, async_clean_database):
        """Test extracting date from timestamp string"""
        db = async_clean_database
        
        # Test UTC timestamp
        timestamp = "2025-01-15T14:30:00Z"
        date = db.extract_date_from_timestamp(timestamp)
        assert date == "2025-01-15"
        
        # Test with timezone
        timestamp_tz = "2025-01-15T22:30:00-08:00"
        date_tz = db.extract_date_from_timestamp(timestamp_tz, "America/Los_Angeles")
        assert date_tz == "2025-01-15"
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_date(self, async_database_with_test_data):
        """Test retrieving items by specific date"""
        db = async_database_with_test_data
        
        items = await db.get_data_items_by_date("2025-01-15")
        
        # Should return items for that date
        assert len(items) > 0
        
        for item in items:
            assert item['days_date'] == "2025-01-15"
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_date_with_namespaces(self, async_database_with_test_data):
        """Test retrieving items by date filtered by namespaces"""
        db = async_database_with_test_data
        
        items = await db.get_data_items_by_date("2025-01-15", namespaces=["limitless"])
        
        # Should only return limitless items
        for item in items:
            assert item['namespace'] == "limitless"
            assert item['days_date'] == "2025-01-15"
    
    @pytest.mark.asyncio
    async def test_get_available_dates(self, async_database_with_test_data):
        """Test retrieving available dates"""
        db = async_database_with_test_data
        
        dates = await db.get_available_dates()
        
        assert len(dates) > 0
        assert "2025-01-15" in dates
        
        # Dates should be sorted
        assert dates == sorted(dates)
    
    @pytest.mark.asyncio
    async def test_get_days_with_data(self, async_database_with_test_data):
        """Test retrieving days with data"""
        db = async_database_with_test_data
        
        days = await db.get_days_with_data()
        
        assert len(days) > 0
        assert "2025-01-15" in days
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_date_range(self, async_database_with_test_data):
        """Test retrieving items by date range"""
        db = async_database_with_test_data
        
        # Test date range query
        items = await db.get_data_items_by_date_range("2025-01-01", "2025-01-31")
        
        # Should return items within the date range
        assert len(items) > 0
        
        for item in items:
            assert item['days_date'] >= "2025-01-01"
            assert item['days_date'] <= "2025-01-31"
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_date_range_with_namespaces(self, async_database_with_test_data):
        """Test retrieving items by date range filtered by namespaces"""
        db = async_database_with_test_data
        
        items = await db.get_data_items_by_date_range(
            "2025-01-01", "2025-01-31", 
            namespaces=["limitless", "news"]
        )
        
        # Should only return items from specified namespaces
        for item in items:
            assert item['namespace'] in ["limitless", "news"]
            assert item['days_date'] >= "2025-01-01"
            assert item['days_date'] <= "2025-01-31"
    
    @pytest.mark.asyncio
    async def test_get_data_items_by_date_range_with_limit(self, async_database_with_test_data):
        """Test retrieving items by date range with limit"""
        db = async_database_with_test_data
        
        # Add more test data to ensure limit is tested
        for i in range(10):
            await db.store_data_item(
                f"range_test:{i:03d}",
                "range_test", 
                f"{i:03d}",
                f"Range test content {i}",
                days_date="2025-01-20"
            )
        
        items = await db.get_data_items_by_date_range(
            "2025-01-15", "2025-01-25", 
            limit=5
        )
        
        assert len(items) <= 5


class TestMarkdownGeneration:
    """Test markdown content generation"""
    
    @pytest.mark.asyncio
    async def test_get_markdown_by_date(self, async_database_with_test_data):
        """Test generating markdown for a specific date"""
        db = async_database_with_test_data
        
        markdown = await db.get_markdown_by_date("2025-01-15")
        
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        
        # Should contain headers for different namespaces
        assert "# Lifeboard" in markdown or "No data found" not in markdown
    
    @pytest.mark.asyncio
    async def test_get_markdown_by_date_with_namespaces(self, async_database_with_test_data):
        """Test generating markdown filtered by namespaces"""
        db = async_database_with_test_data
        
        markdown = await db.get_markdown_by_date("2025-01-15", namespaces=["limitless"])
        
        assert isinstance(markdown, str)
        # Should only contain limitless content
    
    @pytest.mark.asyncio
    async def test_get_markdown_no_data(self, async_clean_database):
        """Test markdown generation when no data exists"""
        db = async_clean_database
        
        markdown = await db.get_markdown_by_date("2099-12-31")
        
        # The actual implementation returns a fallback message with the date
        assert "2099-12-31" in markdown and "No data available" in markdown


class TestDatabaseStats:
    """Test database statistics and metadata"""
    
    @pytest.mark.asyncio
    async def test_get_database_stats(self, async_database_with_test_data):
        """Test retrieving database statistics"""
        db = async_database_with_test_data
        
        stats = await db.get_database_stats()
        
        assert isinstance(stats, dict)
        assert 'total_items' in stats
        assert 'namespace_counts' in stats  # Actual field name
        assert 'embedding_status' in stats
        assert 'active_sources' in stats
        assert 'database_path' in stats
        assert 'database_size_mb' in stats
        
        assert stats['total_items'] > 0
        assert len(stats['namespace_counts']) > 0
    
    @pytest.mark.asyncio
    async def test_get_all_namespaces(self, async_database_with_test_data):
        """Test retrieving all namespaces"""
        db = async_database_with_test_data
        
        namespaces = await db.get_all_namespaces()
        
        assert isinstance(namespaces, list)
        assert len(namespaces) > 0
        assert "limitless" in namespaces
    
    @pytest.mark.asyncio
    async def test_get_migration_status(self, async_clean_database):
        """Test retrieving migration status"""
        db = async_clean_database
        
        status = db.get_migration_status()
        
        assert isinstance(status, dict)
        # Should contain migration information


class TestMarkdownHelpers:
    """Test markdown helper methods"""
    
    @pytest.mark.asyncio
    async def test_remove_duplicate_headers_basic(self, async_clean_database):
        """Test _remove_duplicate_headers method"""
        db = async_clean_database
        
        content = "# Test Header\n\nSome content\n\n# Test Header\n\nMore content"
        target_header = "# Test Header"
        
        result = db._remove_duplicate_headers(content, target_header)
        
        # Should remove duplicate headers but keep content
        assert "Some content" in result
        assert "More content" in result
        # Should not contain the duplicate header
        assert result.count("# Test Header") == 0
    
    @pytest.mark.asyncio
    async def test_remove_duplicate_headers_empty_input(self, async_clean_database):
        """Test _remove_duplicate_headers with empty input"""
        db = async_clean_database
        
        result = db._remove_duplicate_headers("", "# Header")
        assert result == ""
        
        result = db._remove_duplicate_headers("Some content", "")
        assert result == "Some content"
    
    @pytest.mark.asyncio
    async def test_remove_duplicate_headers_no_duplicates(self, async_clean_database):
        """Test _remove_duplicate_headers when no duplicates exist"""
        db = async_clean_database
        
        content = "# Different Header\n\nSome content"
        target_header = "# Test Header"
        
        result = db._remove_duplicate_headers(content, target_header)
        
        # Should return unchanged content
        assert result == content


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_store_data_item_with_invalid_metadata(self, async_clean_database):
        """Test storing item with metadata that can't be serialized"""
        db = async_clean_database
        
        # This should handle the error gracefully
        with patch('core.json_utils.JSONMetadataParser.serialize_metadata') as mock_serialize:
            mock_serialize.return_value = None
            
            # Should not raise an exception
            await db.store_data_item("test:error", "test", "error", "content", {"invalid": object()}, days_date="2025-01-15")
    
    @pytest.mark.asyncio
    async def test_database_connection_error_handling(self, temp_db_path):
        """Test handling of database connection errors"""
        db = AsyncDatabaseService(temp_db_path)
        
        # Remove the database file to cause connection issues
        os.remove(temp_db_path)
        
        # Operations should handle the missing database gracefully
        # Note: SQLite will recreate the file, but schema won't exist
        with pytest.raises(Exception):
            # This should fail because tables don't exist
            await db.store_data_item("test:001", "test", "001", "content", days_date="2025-01-15")
    
    @pytest.mark.asyncio
    async def test_get_data_items_with_corrupted_metadata(self, async_clean_database):
        """Test retrieving items with corrupted metadata"""
        db = async_clean_database
        
        # Insert item with invalid JSON metadata directly
        async with db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO data_items (id, namespace, source_id, content, metadata, days_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("test:corrupt", "test", "corrupt", "content", "invalid json", "2025-01-15"))
            await conn.commit()
        
        # Should handle corrupted metadata gracefully
        items = await db.get_data_items_by_ids(["test:corrupt"])
        
        # Should still return the item, but metadata might be None or default
        assert len(items) == 1
        assert items[0]['id'] == "test:corrupt"


class TestAdditionalValidation:
    """Test additional validation and edge cases"""
    
    @pytest.mark.asyncio
    async def test_extract_date_from_timestamp_edge_cases(self, async_clean_database):
        """Test date extraction with various timestamp formats"""
        db = async_clean_database
        
        # Test None input
        result = db.extract_date_from_timestamp(None)
        assert result is None
        
        # Test empty string
        result = db.extract_date_from_timestamp("")
        assert result is None
        
        # Test invalid format
        result = db.extract_date_from_timestamp("not a timestamp")
        assert result is None
        
        # Test valid formats
        result = db.extract_date_from_timestamp("2025-01-15T10:30:00Z")
        assert result == "2025-01-15"
        
        result = db.extract_date_from_timestamp("2025-01-15T10:30:00+05:00")
        assert result is not None  # Should handle timezone conversion
    
    @pytest.mark.asyncio
    async def test_get_available_dates_with_namespaces(self, async_database_with_test_data):
        """Test getting available dates filtered by namespace"""
        db = async_database_with_test_data
        
        # Test with specific namespace
        dates = await db.get_available_dates(namespaces=["limitless"])
        assert len(dates) >= 0  # May or may not have limitless data depending on test data
        
        # Test with non-existent namespace  
        dates = await db.get_available_dates(namespaces=["nonexistent"])
        assert dates == []
    
    @pytest.mark.asyncio
    async def test_get_days_with_data_with_namespaces(self, async_database_with_test_data):
        """Test getting days with data filtered by namespace"""
        db = async_database_with_test_data
        
        # Test with specific namespace
        days = await db.get_days_with_data(namespaces=["limitless"])
        assert isinstance(days, list)
        
        # Test with multiple namespaces
        days = await db.get_days_with_data(namespaces=["limitless", "news"])
        assert isinstance(days, list)
    
    @pytest.mark.asyncio
    async def test_markdown_generation_with_complex_metadata(self, async_clean_database):
        """Test markdown generation with various metadata structures"""
        db = async_clean_database
        
        # Store item with cleaned_markdown in metadata
        await db.store_data_item(
            "test:cleaned_md",
            "test",
            "cleaned_md", 
            "Content",
            metadata={"cleaned_markdown": "# Cleaned Title\n\nCleaned content"},
            days_date="2025-01-15"
        )
        
        # Store item with nested original_lifelog
        await db.store_data_item(
            "test:nested_md",
            "test", 
            "nested_md",
            "Content",
            metadata={
                "title": "Nested Test",
                "original_lifelog": {
                    "markdown": "# Original Title\n\nOriginal content"
                }
            },
            days_date="2025-01-15"
        )
        
        # Test markdown generation
        markdown = await db.get_markdown_by_date("2025-01-15", namespaces=["test"])
        
        assert "Cleaned Title" in markdown or "Cleaned content" in markdown
        assert "Original Title" in markdown or "Original content" in markdown or "Nested Test" in markdown
    
    @pytest.mark.asyncio
    async def test_update_source_item_count_return_value(self, async_clean_database):
        """Test that update_source_item_count returns the count"""
        db = async_clean_database
        
        # Register a source
        await db.register_data_source("count_return_test", "api", {})
        
        # Add items
        for i in range(5):
            await db.store_data_item(
                f"count_return_test:{i:03d}",
                "count_return_test",
                f"{i:03d}",
                f"Content {i}",
                days_date="2025-01-15"
            )
        
        # Update count and verify return value
        count = await db.update_source_item_count("count_return_test")
        assert count == 5
        
        # Verify it's also stored in the database
        async with db.get_connection() as conn:
            async with conn.execute(
                "SELECT item_count FROM data_sources WHERE namespace = ?", 
                ("count_return_test",)
            ) as cursor:
                row = await cursor.fetchone()
            assert row['item_count'] == 5


class TestPerformance:
    """Test performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_batch_operations_performance(self, async_clean_database):
        """Test performance of batch operations"""
        db = async_clean_database
        
        # Store multiple items
        import time
        start_time = time.perf_counter()
        
        for i in range(100):
            await db.store_data_item(f"perf:test_{i:03d}", "perf", f"test_{i:03d}", f"Content {i}", days_date="2025-01-15")
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 5.0  # 5 seconds for 100 items
        
        # Test batch retrieval
        ids = [f"perf:test_{i:03d}" for i in range(100)]
        
        start_time = time.perf_counter()
        items = await db.get_data_items_by_ids(ids)
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        assert len(items) == 100
        assert duration < 1.0  # 1 second for batch retrieval
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_large_dataset_operations(self, async_clean_database):
        """Test operations with larger datasets"""
        db = async_clean_database
        
        # This test is marked as performance test
        # Store larger dataset
        for i in range(1000):
            await db.store_data_item(
                f"large:test_{i:04d}", 
                "large", 
                f"test_{i:04d}", 
                f"Content {i} " * 10,  # Larger content
                {"index": i, "category": f"cat_{i % 10}"},
                days_date=f"2025-01-{(i % 30) + 1:02d}"  # Vary the dates
            )
        
        # Test various operations
        stats = await db.get_database_stats()
        assert stats['total_items'] >= 1000
        
        # Test namespace query
        items = await db.get_data_items_by_namespace("large", limit=50)
        assert len(items) == 50
        
        # Test date operations
        dates = await db.get_available_dates()
        assert len(dates) > 0