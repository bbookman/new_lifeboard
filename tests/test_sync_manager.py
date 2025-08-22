"""
Tests for Limitless sync manager
"""

import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from config.models import LimitlessConfig
from core.database import DatabaseService
from sources.base import DataItem
from sources.limitless import LimitlessSource
from sources.sync_manager import SyncManager, SyncResult


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = DatabaseService(db_path)
    yield db

    # Cleanup
    import os
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def limitless_config():
    """Test Limitless configuration"""
    return LimitlessConfig(
        api_key="test-key",
        sync_interval_hours=6,
    )


@pytest.fixture
def mock_limitless_source():
    """Mock Limitless source"""
    source = AsyncMock(spec=LimitlessSource)
    source.namespace = "limitless"
    return source


@pytest.fixture
def sync_manager(mock_limitless_source, temp_db, limitless_config):
    """Create sync manager for testing"""
    from config.models import AppConfig
    app_config = AppConfig(limitless=limitless_config)
    manager = SyncManager(database=temp_db, app_config=app_config)
    manager.register_source(mock_limitless_source)
    return manager


@pytest.fixture
def sample_data_items():
    """Sample data items for testing"""
    base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    return [
        DataItem(
            namespace="limitless",
            source_id="item1",
            content="First conversation",
            metadata={"title": "Meeting 1"},
            created_at=base_time,
            updated_at=base_time,
        ),
        DataItem(
            namespace="limitless",
            source_id="item2",
            content="Second conversation",
            metadata={"title": "Meeting 2"},
            created_at=base_time + timedelta(hours=1),
            updated_at=base_time + timedelta(hours=1),
        ),
        DataItem(
            namespace="limitless",
            source_id="item3",
            content="Third conversation",
            metadata={"title": "Meeting 3"},
            created_at=base_time + timedelta(hours=2),
            updated_at=base_time + timedelta(hours=2),
        ),
    ]


class TestSyncResult:
    """Test SyncResult class"""

    def test_sync_result_initialization(self):
        """Test SyncResult initialization"""
        result = SyncResult("test_namespace")
        assert result.namespace == "test_namespace"
        assert result.items_processed == 0
        assert result.items_new == 0
        assert result.items_updated == 0
        assert result.items_skipped == 0
        assert result.errors == []
        assert result.start_time is None
        assert result.end_time is None

    def test_sync_result_duration(self):
        """Test duration calculation"""
        result = SyncResult("test_namespace")
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=5)

        result.start_time = start
        result.end_time = end

        assert result.duration == timedelta(minutes=5)

    def test_sync_result_success(self):
        """Test success determination"""
        result = SyncResult()
        assert result.success is True

        result.errors.append("Some error")
        assert result.success is False

    def test_sync_result_to_dict(self):
        """Test converting result to dictionary"""
        result = SyncResult()
        result.items_processed = 10
        result.items_new = 5
        result.errors = ["test error"]
        result.start_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result.end_time = datetime(2024, 1, 15, 10, 5, 0, tzinfo=timezone.utc)

        result_dict = result.to_dict()

        assert result_dict["items_processed"] == 10
        assert result_dict["items_new"] == 5
        assert result_dict["errors"] == ["test error"]
        assert result_dict["duration_seconds"] == 300.0
        assert result_dict["success"] is False


class TestLimitlessSyncManager:
    """Test sync manager functionality"""

    @pytest.mark.asyncio
    async def test_sync_manager_initialization(self, sync_manager):
        """Test sync manager initialization"""
        assert sync_manager.overlap_hours == 1
        assert sync_manager.SETTINGS_LAST_SYNC == "limitless_last_sync_timestamp"
        assert sync_manager.SETTINGS_LAST_ID == "limitless_last_processed_id"

    @pytest.mark.asyncio
    async def test_last_sync_time_storage(self, sync_manager):
        """Test storing and retrieving last sync time"""
        # Initially no last sync time
        last_sync = await sync_manager.get_last_sync_time()
        assert last_sync is None

        # Set sync time
        test_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        await sync_manager.set_last_sync_time(test_time)

        # Retrieve sync time
        retrieved_time = await sync_manager.get_last_sync_time()
        assert retrieved_time == test_time

    @pytest.mark.asyncio
    async def test_last_processed_id_storage(self, sync_manager):
        """Test storing and retrieving last processed ID"""
        # Initially no last processed ID
        last_id = await sync_manager.get_last_processed_id()
        assert last_id is None

        # Set processed ID
        test_id = "lifelog_123"
        await sync_manager.set_last_processed_id(test_id)

        # Retrieve processed ID
        retrieved_id = await sync_manager.get_last_processed_id()
        assert retrieved_id == test_id

    @pytest.mark.asyncio
    async def test_calculate_sync_start_time(self, sync_manager):
        """Test sync start time calculation with overlap"""
        # No previous sync
        start_time = sync_manager.calculate_sync_start_time(None)
        assert start_time is None

        # With previous sync - should subtract overlap
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        start_time = sync_manager.calculate_sync_start_time(last_sync)
        expected = last_sync - timedelta(hours=1)
        assert start_time == expected

    @pytest.mark.asyncio
    async def test_should_process_item_new_item(self, sync_manager, sample_data_items):
        """Test should_process_item with new item"""
        item = sample_data_items[0]

        # New item should be processed
        should_process = await sync_manager.should_process_item(item)
        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_process_item_existing_unchanged(self, sync_manager, sample_data_items):
        """Test should_process_item with existing unchanged item"""
        item = sample_data_items[0]

        # Store item in database first
        sync_manager.database.store_data_item(
            id=f"limitless:{item.source_id}",
            namespace=item.namespace,
            source_id=item.source_id,
            content=item.content,
            metadata=item.metadata,
        )

        # Existing unchanged item should not be processed
        should_process = await sync_manager.should_process_item(item)
        assert should_process is False

    @pytest.mark.asyncio
    async def test_should_process_item_existing_updated(self, sync_manager, sample_data_items):
        """Test should_process_item with existing updated item"""
        item = sample_data_items[0]

        # Store item with older timestamp
        old_time = item.updated_at - timedelta(hours=1)
        sync_manager.database.store_data_item(
            id=f"limitless:{item.source_id}",
            namespace=item.namespace,
            source_id=item.source_id,
            content=item.content,
            metadata=item.metadata,
        )

        # Update the database entry to have old timestamp
        with sync_manager.database.get_connection() as conn:
            conn.execute(
                "UPDATE data_items SET updated_at = ? WHERE id = ?",
                (old_time.isoformat(), f"limitless:{item.source_id}"),
            )
            conn.commit()

        # Updated item should be processed
        should_process = await sync_manager.should_process_item(item)
        assert should_process is True

    @pytest.mark.asyncio
    async def test_full_sync(self, sync_manager, mock_limitless_source, sample_data_items):
        """Test full sync operation"""
        # Mock the source to return sample items
        async def mock_fetch_items(*args, **kwargs):
            for item in sample_data_items:
                yield item

        mock_limitless_source.fetch_items = mock_fetch_items

        # Collect sync results
        synced_items = []
        async for item in sync_manager.perform_full_sync(limit=100):
            synced_items.append(item)

        # Verify results
        assert len(synced_items) == 3
        assert all(item.namespace == "limitless" for item in synced_items)

        # Check that sync state was updated
        last_sync = await sync_manager.get_last_sync_time()
        assert last_sync is not None

        last_id = await sync_manager.get_last_processed_id()
        assert last_id == "item3"  # Last item processed

    @pytest.mark.asyncio
    async def test_incremental_sync_no_previous_sync(self, sync_manager, mock_limitless_source, sample_data_items):
        """Test incremental sync when no previous sync exists"""
        # Mock the source
        async def mock_fetch_items(*args, **kwargs):
            for item in sample_data_items:
                yield item

        mock_limitless_source.fetch_items = mock_fetch_items

        # Should behave like full sync when no previous sync
        synced_items = []
        async for item in sync_manager.perform_incremental_sync(limit=100):
            synced_items.append(item)

        assert len(synced_items) == 3

    @pytest.mark.asyncio
    async def test_incremental_sync_with_existing_data(self, sync_manager, mock_limitless_source, sample_data_items):
        """Test incremental sync with some existing data"""
        # Store first item as existing
        existing_item = sample_data_items[0]
        sync_manager.database.store_data_item(
            id=f"limitless:{existing_item.source_id}",
            namespace=existing_item.namespace,
            source_id=existing_item.source_id,
            content=existing_item.content,
            metadata=existing_item.metadata,
        )

        # Mock source to return all items
        async def mock_fetch_items(*args, **kwargs):
            for item in sample_data_items:
                yield item

        mock_limitless_source.fetch_items = mock_fetch_items

        # Run incremental sync
        synced_items = []
        async for item in sync_manager.perform_incremental_sync(limit=100):
            synced_items.append(item)

        # Should only sync new items (items 2 and 3)
        assert len(synced_items) == 2
        assert synced_items[0].source_id == "item2"
        assert synced_items[1].source_id == "item3"

    @pytest.mark.asyncio
    async def test_sync_with_force_full_sync(self, sync_manager, mock_limitless_source, sample_data_items):
        """Test sync with force_full_sync flag"""
        # Set up previous sync
        await sync_manager.set_last_sync_time(datetime.now(timezone.utc))

        # Mock source
        async def mock_fetch_items(*args, **kwargs):
            for item in sample_data_items:
                yield item

        mock_limitless_source.fetch_items = mock_fetch_items

        # Force full sync even though we have previous sync
        synced_items = []
        async for item in sync_manager.sync(force_full_sync=True, limit=100):
            synced_items.append(item)

        assert len(synced_items) == 3

    @pytest.mark.asyncio
    async def test_sync_status(self, sync_manager):
        """Test getting sync status"""
        # Initial status
        status = await sync_manager.get_sync_status()
        assert status["last_sync_time"] is None
        assert status["is_initial_sync"] is True
        assert status["next_sync_recommended"] is True

        # After setting sync time
        sync_time = datetime.now(timezone.utc)
        await sync_manager.set_last_sync_time(sync_time)
        await sync_manager.set_last_processed_id("test_id")

        status = await sync_manager.get_sync_status()
        assert status["last_sync_time"] == sync_time.isoformat()
        assert status["last_processed_id"] == "test_id"
        assert status["is_initial_sync"] is False

    @pytest.mark.asyncio
    async def test_sync_result_storage(self, sync_manager):
        """Test storing and retrieving sync results"""
        result = SyncResult()
        result.items_processed = 10
        result.items_new = 5
        result.errors = ["test error"]

        await sync_manager.store_sync_result(result)

        retrieved_result = await sync_manager.get_last_sync_result()
        assert retrieved_result["items_processed"] == 10
        assert retrieved_result["items_new"] == 5
        assert retrieved_result["errors"] == ["test error"]

    @pytest.mark.asyncio
    async def test_sync_with_api_errors(self, sync_manager, mock_limitless_source):
        """Test sync handling API errors gracefully"""
        # Mock source to raise an error
        async def mock_fetch_items_with_error(*args, **kwargs):
            yield DataItem(
                namespace="limitless",
                source_id="good_item",
                content="Good item",
                metadata={},
            )
            raise Exception("API Error")

        mock_limitless_source.fetch_items = mock_fetch_items_with_error

        # Should handle error gracefully
        synced_items = []
        try:
            async for item in sync_manager.perform_full_sync(limit=100):
                synced_items.append(item)
        except Exception:
            pass  # Expected to handle gracefully

        # Should have processed the good item before error
        assert len(synced_items) == 1

        # Check that error was recorded
        result = await sync_manager.get_last_sync_result()
        assert len(result["errors"]) > 0
        assert "API Error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_overlap_handling(self, sync_manager, mock_limitless_source, sample_data_items):
        """Test that overlap is properly applied to avoid missing data"""
        # Set previous sync time
        last_sync = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        await sync_manager.set_last_sync_time(last_sync)

        # Track what parameters were passed to fetch_items
        fetch_calls = []

        async def mock_fetch_items(since=None, limit=100):
            fetch_calls.append({"since": since, "limit": limit})
            for item in sample_data_items:
                yield item

        mock_limitless_source.fetch_items = mock_fetch_items

        # Run incremental sync
        synced_items = []
        async for item in sync_manager.perform_incremental_sync(limit=100):
            synced_items.append(item)

        # Verify that fetch_items was called with overlap applied
        assert len(fetch_calls) == 1
        expected_since = last_sync - timedelta(hours=1)  # overlap_hours = 1
        assert fetch_calls[0]["since"] == expected_since
