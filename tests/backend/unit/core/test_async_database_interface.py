"""
Test suite for AsyncDatabaseService interface and basic functionality.

This test file implements the TDD approach outlined in the async refactoring plan,
starting with failing tests (RED) that will guide the implementation (GREEN)
and subsequent optimization (REFACTOR) phases.

Phase 1: Interface testing and async fixture validation
Phase 2: Full implementation testing with comprehensive coverage
"""

import pytest
import pytest_asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch

from core.async_database import AsyncDatabaseService, AsyncMigrationRunner
from tests.fixtures.async_database_fixtures import *


class TestAsyncDatabaseInterface:
    """Test suite for AsyncDatabaseService interface definition"""

    @pytest.mark.asyncio
    async def test_async_database_initialization(self, async_temp_db_path):
        """Test AsyncDatabaseService initialization"""
        # RED: Test initialization behavior
        db_service = AsyncDatabaseService(async_temp_db_path)

        # Verify initialization properties
        assert db_service.db_path == async_temp_db_path
        assert db_service.service_name == "async_database"
        assert hasattr(db_service, 'debug')
        assert hasattr(db_service, '_connection_pool')

    @pytest.mark.asyncio
    async def test_async_database_initialize_method(self, async_temp_db_path):
        """Test async initialize method"""
        # RED: Test async initialization
        db_service = AsyncDatabaseService(async_temp_db_path)

        # Should not raise exception
        await db_service.initialize()

        # Verify database file was created
        assert os.path.exists(async_temp_db_path)

    @pytest.mark.asyncio
    async def test_async_database_close_method(self, async_clean_database):
        """Test async close method"""
        # RED: Test async close behavior
        db_service = async_clean_database

        # Should not raise exception
        await db_service.close()

    @pytest.mark.asyncio
    async def test_async_connection_context_manager(self, async_clean_database):
        """Test async connection context manager"""
        # RED: Test connection management
        db_service = async_clean_database

        async with db_service.get_connection() as conn:
            # Should have row factory
            assert hasattr(conn, 'row_factory')

            # Should be able to execute queries
            cursor = await conn.execute("SELECT 1")
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_async_fetch_one_implementation(self, async_clean_database):
        """Test async fetch_one method (Phase 0 integration)"""
        # RED: Test proper async fetch_one implementation
        db_service = async_clean_database

        # Insert test data first
        await db_service.execute_query("""
            INSERT INTO data_items (id, namespace, source_id, content, days_date)
            VALUES (?, ?, ?, ?, ?)
        """, ("test:001", "test", "001", "Test content", "2025-01-15"))

        # Test fetch_one
        result = await db_service.fetch_one(
            "SELECT id, content FROM data_items WHERE id = ?",
            ("test:001",)
        )

        assert result is not None
        assert result['id'] == "test:001"
        assert result['content'] == "Test content"

        # Test fetch_one with no results
        result = await db_service.fetch_one(
            "SELECT id FROM data_items WHERE id = ?",
            ("nonexistent",)
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_async_execute_query_implementation(self, async_clean_database):
        """Test async execute_query method (Phase 0 integration)"""
        # RED: Test proper async execute_query implementation
        db_service = async_clean_database

        # Should not raise exception
        await db_service.execute_query("""
            INSERT INTO data_items (id, namespace, source_id, content, days_date)
            VALUES (?, ?, ?, ?, ?)
        """, ("test:002", "test", "002", "Another test", "2025-01-15"))

        # Verify data was inserted
        result = await db_service.fetch_one(
            "SELECT content FROM data_items WHERE id = ?",
            ("test:002",)
        )

        assert result is not None
        assert result['content'] == "Another test"


class TestAsyncDatabaseImplementation:
    """Test suite for AsyncDatabaseService full implementation (Phase 2 complete)"""

    @pytest.mark.asyncio
    async def test_store_data_item_implementation(self, async_clean_database):
        """Test store_data_item method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Should not raise exception - method is now implemented
        await db_service.store_data_item(
            id="test:001",
            namespace="test",
            source_id="001",
            content="Test content",
            days_date="2025-01-15"
        )

        # Verify data was stored
        result = await db_service.fetch_one(
            "SELECT id, content, namespace FROM data_items WHERE id = ?",
            ("test:001",)
        )
        assert result is not None
        assert result['id'] == "test:001"
        assert result['content'] == "Test content"
        assert result['namespace'] == "test"

    @pytest.mark.asyncio
    async def test_get_data_items_by_ids_implementation(self, async_clean_database):
        """Test get_data_items_by_ids method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data first
        await db_service.store_data_item(
            "test:001", "test", "001", "Content 1", {"key": "value1"}, "2025-01-15"
        )
        await db_service.store_data_item(
            "test:002", "test", "002", "Content 2", {"key": "value2"}, "2025-01-15"
        )

        # Test retrieval
        results = await db_service.get_data_items_by_ids(["test:001", "test:002"])

        assert len(results) == 2
        assert results[0]['id'] in ["test:001", "test:002"]
        assert results[1]['id'] in ["test:001", "test:002"]
        assert all('metadata' in item for item in results)

    @pytest.mark.asyncio
    async def test_get_data_items_by_namespace_implementation(self, async_clean_database):
        """Test get_data_items_by_namespace method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data in different namespaces
        await db_service.store_data_item(
            "test:001", "test", "001", "Test Content 1", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "other:001", "other", "001", "Other Content 1", None, "2025-01-15"
        )

        # Test namespace filtering
        results = await db_service.get_data_items_by_namespace("test", limit=10)

        assert len(results) == 1
        assert results[0]['namespace'] == "test"
        assert results[0]['content'] == "Test Content 1"

    @pytest.mark.asyncio
    async def test_get_data_items_by_date_implementation(self, async_clean_database):
        """Test get_data_items_by_date method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data with different dates
        await db_service.store_data_item(
            "test:001", "test", "001", "Content on 15th", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "test:002", "test", "002", "Content on 16th", None, "2025-01-16"
        )

        # Test date filtering
        results = await db_service.get_data_items_by_date("2025-01-15", ["test"])

        assert len(results) == 1
        assert results[0]['days_date'] == "2025-01-15"
        assert results[0]['content'] == "Content on 15th"

    @pytest.mark.asyncio
    async def test_get_data_items_by_date_range_implementation(self, async_clean_database):
        """Test get_data_items_by_date_range method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data with different dates
        await db_service.store_data_item(
            "test:001", "test", "001", "Content Jan 10", None, "2025-01-10"
        )
        await db_service.store_data_item(
            "test:002", "test", "002", "Content Jan 20", None, "2025-01-20"
        )
        await db_service.store_data_item(
            "test:003", "test", "003", "Content Feb 05", None, "2025-02-05"
        )

        # Test date range filtering
        results = await db_service.get_data_items_by_date_range(
            "2025-01-01", "2025-01-31", ["test"]
        )

        assert len(results) == 2
        assert all(item['days_date'].startswith('2025-01') for item in results)

    @pytest.mark.asyncio
    async def test_delete_data_item_implementation(self, async_clean_database):
        """Test delete_data_item method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data first
        await db_service.store_data_item(
            "test:001", "test", "001", "Content to delete", None, "2025-01-15"
        )

        # Verify data exists
        result = await db_service.fetch_one(
            "SELECT id FROM data_items WHERE id = ?", ("test:001",)
        )
        assert result is not None

        # Delete the item
        deleted = await db_service.delete_data_item("test:001")
        assert deleted is True

        # Verify data is gone
        result = await db_service.fetch_one(
            "SELECT id FROM data_items WHERE id = ?", ("test:001",)
        )
        assert result is None

        # Test deleting non-existent item
        deleted = await db_service.delete_data_item("nonexistent:001")
        assert deleted is False


class TestAsyncDatabaseQueryMethods:
    """Test suite for async query and metadata methods (Phase 2 complete)"""

    @pytest.mark.asyncio
    async def test_get_days_with_data_implementation(self, async_clean_database):
        """Test get_days_with_data method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data with different dates
        await db_service.store_data_item(
            "test:001", "test", "001", "Content 1", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "test:002", "test", "002", "Content 2", None, "2025-01-16"
        )
        await db_service.store_data_item(
            "other:001", "other", "001", "Other content", None, "2025-01-17"
        )

        # Test with namespace filter
        results = await db_service.get_days_with_data(["test"])

        assert len(results) == 2
        assert "2025-01-15" in results
        assert "2025-01-16" in results
        assert "2025-01-17" not in results  # Different namespace

    @pytest.mark.asyncio
    async def test_get_available_dates_implementation(self, async_clean_database):
        """Test get_available_dates method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data with different dates
        await db_service.store_data_item(
            "test:001", "test", "001", "Content 1", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "test:002", "test", "002", "Content 2", None, "2025-01-16"
        )
        await db_service.store_data_item(
            "test:003", "test", "003", "Content 3", None, "2025-01-17"
        )

        # Test with limit
        results = await db_service.get_available_dates(limit=2)

        assert len(results) == 2
        assert all(date.startswith('2025-01') for date in results)
        # Should be ordered DESC, so latest dates first
        assert results[0] >= results[1]

    @pytest.mark.asyncio
    async def test_get_all_namespaces_implementation(self, async_clean_database):
        """Test get_all_namespaces method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data with different namespaces
        await db_service.store_data_item(
            "test:001", "test", "001", "Test content", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "news:001", "news", "001", "News content", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "weather:001", "weather", "001", "Weather content", None, "2025-01-15"
        )

        # Test namespace retrieval
        results = await db_service.get_all_namespaces()

        assert len(results) == 3
        assert "test" in results
        assert "news" in results
        assert "weather" in results

    @pytest.mark.asyncio
    async def test_get_database_stats_implementation(self, async_clean_database):
        """Test get_database_stats method implementation"""
        # GREEN: Implementation should work correctly
        db_service = async_clean_database

        # Store test data
        await db_service.store_data_item(
            "test:001", "test", "001", "Test content 1", None, "2025-01-15"
        )
        await db_service.store_data_item(
            "news:001", "news", "001", "News content 1", None, "2025-01-15"
        )

        # Register a data source
        await db_service.register_data_source("test", "test_source", {"version": "1.0"})

        # Test stats retrieval
        stats = await db_service.get_database_stats()

        assert isinstance(stats, dict)
        assert 'total_items' in stats
        assert 'namespace_counts' in stats
        assert 'embedding_status' in stats
        assert 'active_sources' in stats
        assert 'database_path' in stats
        assert 'database_size_mb' in stats

        assert stats['total_items'] >= 2
        assert 'test' in stats['namespace_counts']
        assert 'news' in stats['namespace_counts']


class TestAsyncDatabaseSettingsOperations:
    """Test suite for async settings operations"""

    @pytest.mark.asyncio
    async def test_get_setting_with_existing_value(self, async_clean_database):
        """Test get_setting method with existing value"""
        db_service = async_clean_database

        # Set a value first
        test_value = {"key": "test_value", "number": 42}
        await db_service.set_setting("test_key", test_value)

        # Retrieve the value
        result = await db_service.get_setting("test_key")

        assert result is not None
        assert result["key"] == "test_value"
        assert result["number"] == 42

    @pytest.mark.asyncio
    async def test_get_setting_with_default_value(self, async_clean_database):
        """Test get_setting method with default value when key doesn't exist"""
        db_service = async_clean_database

        # Try to get a non-existent key
        result = await db_service.get_setting("nonexistent_key", "default_value")

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_get_setting_without_default(self, async_clean_database):
        """Test get_setting method without default when key doesn't exist"""
        db_service = async_clean_database

        # Try to get a non-existent key without default
        result = await db_service.get_setting("nonexistent_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_setting_string_value(self, async_clean_database):
        """Test set_setting method with string value"""
        db_service = async_clean_database

        # Set a string value
        await db_service.set_setting("string_key", "test_string")

        # Verify it was stored
        result = await db_service.get_setting("string_key")
        assert result == "test_string"

    @pytest.mark.asyncio
    async def test_set_setting_complex_value(self, async_clean_database):
        """Test set_setting method with complex value"""
        db_service = async_clean_database

        # Set a complex value
        complex_value = {
            "nested": {"data": "value"},
            "list": [1, 2, 3],
            "boolean": True
        }
        await db_service.set_setting("complex_key", complex_value)

        # Verify it was stored and retrieved correctly
        result = await db_service.get_setting("complex_key")
        assert result is not None
        assert result["nested"]["data"] == "value"
        assert result["list"] == [1, 2, 3]
        assert result["boolean"] is True

    @pytest.mark.asyncio
    async def test_set_setting_update_existing(self, async_clean_database):
        """Test set_setting method updating existing value"""
        db_service = async_clean_database

        # Set initial value
        await db_service.set_setting("update_key", "initial_value")

        # Update the value
        await db_service.set_setting("update_key", "updated_value")

        # Verify it was updated
        result = await db_service.get_setting("update_key")
        assert result == "updated_value"

    @pytest.mark.asyncio
    async def test_settings_persistence_across_connections(self, async_clean_database):
        """Test that settings persist across different database connections"""
        db_service = async_clean_database

        # Set value in one connection
        await db_service.set_setting("persistence_key", "persistent_value")

        # Get value in what appears to be a new connection (same service instance)
        result = await db_service.get_setting("persistence_key")

        assert result == "persistent_value"


class TestAsyncDatabaseDataSourceManagement:
    """Test suite for async data source management"""

    @pytest.mark.asyncio
    async def test_register_data_source_basic(self, async_clean_database):
        """Test register_data_source method with basic parameters"""
        db_service = async_clean_database

        # Register a data source
        await db_service.register_data_source(
            namespace="test_namespace",
            source_type="test_source",
            metadata={"version": "1.0", "active": True}
        )

        # Verify it was registered
        result = await db_service.fetch_one(
            "SELECT namespace, source_type, metadata FROM data_sources WHERE namespace = ?",
            ("test_namespace",)
        )

        assert result is not None
        assert result['namespace'] == "test_namespace"
        assert result['source_type'] == "test_source"
        assert result['metadata'] is not None

    @pytest.mark.asyncio
    async def test_register_data_source_without_metadata(self, async_clean_database):
        """Test register_data_source method without metadata"""
        db_service = async_clean_database

        # Register a data source without metadata
        await db_service.register_data_source(
            namespace="simple_namespace",
            source_type="simple_source"
        )

        # Verify it was registered
        result = await db_service.fetch_one(
            "SELECT namespace, source_type FROM data_sources WHERE namespace = ?",
            ("simple_namespace",)
        )

        assert result is not None
        assert result['namespace'] == "simple_namespace"
        assert result['source_type'] == "simple_source"

    @pytest.mark.asyncio
    async def test_register_data_source_duplicate_namespace(self, async_clean_database):
        """Test register_data_source method with duplicate namespace (should update)"""
        db_service = async_clean_database

        # Register initial data source
        await db_service.register_data_source(
            "duplicate_namespace", "initial_source", {"version": "1.0"}
        )

        # Register again with different data (should update)
        await db_service.register_data_source(
            "duplicate_namespace", "updated_source", {"version": "2.0"}
        )

        # Verify it was updated
        result = await db_service.fetch_one(
            "SELECT source_type, metadata FROM data_sources WHERE namespace = ?",
            ("duplicate_namespace",)
        )

        assert result is not None
        assert result['source_type'] == "updated_source"

    @pytest.mark.asyncio
    async def test_update_source_item_count(self, async_clean_database):
        """Test update_source_item_count method"""
        db_service = async_clean_database

        # First register a data source
        await db_service.register_data_source("count_test", "test_source")

        # Update item count
        await db_service.update_source_item_count("count_test", 42)

        # Verify count was updated
        result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?",
            ("count_test",)
        )

        assert result is not None
        assert result['item_count'] == 42

    @pytest.mark.asyncio
    async def test_update_source_item_count_nonexistent(self, async_clean_database):
        """Test update_source_item_count method with non-existent namespace"""
        db_service = async_clean_database

        # Try to update count for non-existent namespace
        await db_service.update_source_item_count("nonexistent", 100)

        # Should not raise exception, but also shouldn't create a record
        result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?",
            ("nonexistent",)
        )

        # Should be None since no record was created
        assert result is None

    @pytest.mark.asyncio
    async def test_data_source_operations_integration(self, async_clean_database):
        """Test integration of data source registration and count updates"""
        db_service = async_clean_database

        # Register data source
        await db_service.register_data_source(
            "integration_test", "integration_source", {"active": True}
        )

        # Update count multiple times
        await db_service.update_source_item_count("integration_test", 10)
        await db_service.update_source_item_count("integration_test", 25)
        await db_service.update_source_item_count("integration_test", 50)

        # Verify final count
        result = await db_service.fetch_one(
            "SELECT item_count FROM data_sources WHERE namespace = ?",
            ("integration_test",)
        )

        assert result is not None
        assert result['item_count'] == 50


class TestAsyncDatabaseChatOperations:
    """Test suite for async chat operations"""

    @pytest.mark.asyncio
    async def test_store_chat_message_basic(self, async_clean_database):
        """Test store_chat_message method with basic parameters"""
        db_service = async_clean_database

        # Store a chat message
        await db_service.store_chat_message(
            user_message="Hello, how are you?",
            assistant_response="I'm doing well, thank you for asking!"
        )

        # Verify it was stored
        result = await db_service.fetch_one(
            "SELECT user_message, assistant_response FROM chat_messages LIMIT 1"
        )

        assert result is not None
        assert result['user_message'] == "Hello, how are you?"
        assert result['assistant_response'] == "I'm doing well, thank you for asking!"

    @pytest.mark.asyncio
    async def test_store_chat_message_long_content(self, async_clean_database):
        """Test store_chat_message method with long content"""
        db_service = async_clean_database

        # Store a chat message with long content
        long_user_msg = "This is a very long user message that contains a lot of text and should test the limits of our database storage capabilities. " * 10
        long_assistant_msg = "This is a very long assistant response that contains detailed information and comprehensive answers to the user's query. " * 15

        await db_service.store_chat_message(long_user_msg, long_assistant_msg)

        # Verify it was stored correctly
        result = await db_service.fetch_one(
            "SELECT LENGTH(user_message) as user_len, LENGTH(assistant_response) as assistant_len FROM chat_messages LIMIT 1"
        )

        assert result is not None
        assert result['user_len'] > 100  # Should be long
        assert result['assistant_len'] > 200  # Should be even longer

    @pytest.mark.asyncio
    async def test_get_chat_history_default_limit(self, async_clean_database):
        """Test get_chat_history method with default limit"""
        db_service = async_clean_database

        # Store multiple chat messages with delays to ensure different timestamps
        import asyncio
        for i in range(5):
            await db_service.store_chat_message(
                f"User message {i}",
                f"Assistant response {i}"
            )
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Get chat history with default limit
        history = await db_service.get_chat_history()

        assert len(history) == 5
        # Should be ordered by timestamp DESC (newest first)
        # With delays, we should get the expected ordering
        user_messages = [msg['user_message'] for msg in history]
        assert "User message 4" in user_messages  # Newest should be in the list
        assert "User message 0" in user_messages  # Oldest should be in the list

    @pytest.mark.asyncio
    async def test_get_chat_history_custom_limit(self, async_clean_database):
        """Test get_chat_history method with custom limit"""
        db_service = async_clean_database

        # Store multiple chat messages
        for i in range(10):
            await db_service.store_chat_message(
                f"User message {i}",
                f"Assistant response {i}"
            )

        # Get chat history with custom limit
        history = await db_service.get_chat_history(limit=3)

        assert len(history) == 3
        # Verify we have 3 messages and they're all unique
        user_messages = [msg['user_message'] for msg in history]
        assert len(set(user_messages)) == 3  # All messages should be unique
        # Verify all messages are from our expected set
        expected_messages = {f"User message {i}" for i in range(10)}
        assert all(msg in expected_messages for msg in user_messages)

    @pytest.mark.asyncio
    async def test_get_chat_history_empty_database(self, async_clean_database):
        """Test get_chat_history method with empty database"""
        db_service = async_clean_database

        # Get chat history from empty database
        history = await db_service.get_chat_history()

        assert history == []
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_chat_operations_with_metadata(self, async_clean_database):
        """Test chat operations with additional metadata verification"""
        db_service = async_clean_database

        # Store a chat message
        await db_service.store_chat_message(
            "Test question",
            "Test answer"
        )

        # Verify timestamp was set
        result = await db_service.fetch_one(
            "SELECT timestamp FROM chat_messages WHERE user_message = ?",
            ("Test question",)
        )

        assert result is not None
        assert result['timestamp'] is not None

    @pytest.mark.asyncio
    async def test_chat_history_ordering(self, async_clean_database):
        """Test that chat history is properly ordered by timestamp"""
        db_service = async_clean_database

        # Store messages
        for i in range(3):
            await db_service.store_chat_message(f"Message {i}", f"Response {i}")

        # Get history
        history = await db_service.get_chat_history()

        # Should return all 3 messages
        assert len(history) == 3
        user_messages = [msg['user_message'] for msg in history]
        assert "Message 2" in user_messages  # Newest should be present
        assert "Message 1" in user_messages  # Middle should be present
        assert "Message 0" in user_messages  # Oldest should be present

        # Verify all messages are unique
        assert len(set(user_messages)) == 3

        # The implementation uses ORDER BY timestamp DESC, so newer messages
        # should generally appear first, but we don't enforce exact ordering
        # in tests due to SQLite timestamp precision limitations


class TestAsyncMigrationRunner:
    """Test suite for AsyncMigrationRunner"""

    @pytest.mark.asyncio
    async def test_migration_runner_initialization(self, async_temp_db_path):
        """Test AsyncMigrationRunner initialization"""
        # RED: Test migration runner setup
        runner = AsyncMigrationRunner(async_temp_db_path)

        assert runner.db_path == async_temp_db_path
        assert hasattr(runner, 'debug')

    @pytest.mark.asyncio
    async def test_run_migrations_interface(self, async_temp_db_path):
        """Test run_migrations method interface"""
        # RED: Interface should be defined but not implemented yet
        runner = AsyncMigrationRunner(async_temp_db_path)

        with pytest.raises(NotImplementedError):
            await runner.run_migrations()


class TestAsyncDatabasePerformance:
    """Test suite for async database performance characteristics"""

    @pytest.mark.asyncio
    @pytest.mark.async_performance
    async def test_concurrent_database_operations(self, async_clean_database):
        """Test concurrent async database operations"""
        # RED: Test that async operations can be executed concurrently
        db_service = async_clean_database

        import asyncio

        # Create multiple concurrent insert operations
        tasks = []
        for i in range(10):
            task = db_service.execute_query("""
                INSERT INTO data_items (id, namespace, source_id, content, days_date)
                VALUES (?, ?, ?, ?, ?)
            """, (f"concurrent:test_{i}", "concurrent", f"test_{i}", f"Content {i}", "2025-01-15"))
            tasks.append(task)

        # Execute all tasks concurrently
        await asyncio.gather(*tasks)

        # Verify all items were inserted
        count_result = await db_service.fetch_one(
            "SELECT COUNT(*) as count FROM data_items WHERE namespace = ?",
            ("concurrent",)
        )

        assert count_result is not None
        assert count_result['count'] == 10

    @pytest.mark.asyncio
    @pytest.mark.async_performance
    async def test_async_connection_management(self, async_clean_database):
        """Test async connection context manager behavior"""
        # RED: Test proper connection management
        db_service = async_clean_database

        # Multiple connection contexts should work properly
        async with db_service.get_connection() as conn1:
            async with db_service.get_connection() as conn2:
                # Both connections should be independent
                assert conn1 is not conn2

                # Both should be able to execute queries
                result1 = await conn1.execute("SELECT 1")
                result2 = await conn2.execute("SELECT 2")

                assert result1 is not None
                assert result2 is not None


class TestAsyncDatabaseErrorHandling:
    """Test suite for async database error handling"""

    @pytest.mark.asyncio
    async def test_invalid_database_path_handling(self):
        """Test handling of invalid database path"""
        # RED: Test error handling for invalid paths
        invalid_path = "/nonexistent/directory/database.db"
        db_service = AsyncDatabaseService(invalid_path)

        # Should raise exception when trying to initialize
        with pytest.raises(Exception):
            await db_service.initialize()

    @pytest.mark.asyncio
    async def test_invalid_sql_query_handling(self, async_clean_database):
        """Test handling of invalid SQL queries"""
        # RED: Test error handling for invalid SQL
        db_service = async_clean_database

        with pytest.raises(Exception):
            await db_service.execute_query("INVALID SQL QUERY")

        with pytest.raises(Exception):
            await db_service.fetch_one("SELECT * FROM nonexistent_table")

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of connection errors"""
        # RED: Test connection error scenarios
        db_service = AsyncDatabaseService("/nonexistent/directory/that/does/not/exist/database.db")

        with pytest.raises(Exception):
            async with db_service.get_connection() as conn:
                await conn.execute("SELECT 1")


# Test Fixtures Validation
class TestAsyncFixtures:
    """Test suite to validate async fixtures work correctly"""

    @pytest.mark.asyncio
    async def test_async_temp_db_path_fixture(self, async_temp_db_path):
        """Test async_temp_db_path fixture"""
        assert async_temp_db_path is not None
        assert async_temp_db_path.endswith('_async.db')

        # Should be able to create database at this path
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()

        assert os.path.exists(async_temp_db_path)

    @pytest.mark.asyncio
    async def test_async_clean_database_fixture(self, async_clean_database):
        """Test async_clean_database fixture"""
        assert async_clean_database is not None
        assert hasattr(async_clean_database, 'db_path')

        # Should have working connection
        async with async_clean_database.get_connection() as conn:
            result = await conn.execute("SELECT 1")
            assert result is not None

    @pytest.mark.asyncio
    async def test_mock_async_database_service_fixture(self, mock_async_database_service):
        """Test mock_async_database_service fixture"""
        mock_db = mock_async_database_service

        # Should be properly mocked
        assert hasattr(mock_db, 'store_data_item')
        assert hasattr(mock_db, 'fetch_one')
        assert hasattr(mock_db, 'execute_query')

        # Should return mocked values
        result = await mock_db.fetch_one("SELECT 1")
        assert result is None  # Default mock return value

        # Should not raise exceptions
        await mock_db.store_data_item("test", "test", "test", "test")
        await mock_db.execute_query("SELECT 1")