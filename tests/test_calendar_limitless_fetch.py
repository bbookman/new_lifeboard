"""
Tests for the on-demand Limitless fetch endpoint in calendar API routes.
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.routes.calendar import fetch_limitless_for_date
from config.models import LimitlessConfig
from core.database import DatabaseService
from services.ingestion import IngestionService
from sources.base import DataItem


class TestLimitlessFetchEndpoint:
    """Test suite for the on-demand Limitless fetch endpoint"""

    @pytest.fixture
    def mock_database(self):
        """Create a mock DatabaseService"""
        db = MagicMock(spec=DatabaseService)
        db.get_data_items_by_date.return_value = []
        return db

    @pytest.fixture
    def mock_ingestion_service(self):
        """Create a mock IngestionService"""
        service = MagicMock(spec=IngestionService)
        service.sources = {}
        service.processors = {"limitless": MagicMock()}
        service.default_processor = MagicMock()

        # Mock the _store_processed_item method as async
        async def mock_store_item(item, result):
            pass
        service._store_processed_item = AsyncMock(side_effect=mock_store_item)
        service.register_source = MagicMock()

        # Mock embedding processing
        service.process_pending_embeddings = AsyncMock(return_value={
            "processed": 1,
            "successful": 1,
            "failed": 0,
            "errors": [],
        })

        return service

    @pytest.fixture
    def mock_limitless_source(self):
        """Create a mock LimitlessSource"""
        source = MagicMock()
        source.test_connection = AsyncMock(return_value=True)
        source.namespace = "limitless"
        source.get_source_type.return_value = "limitless_api"

        # Create sample DataItem for fetch_items
        sample_item = DataItem(
            namespace="limitless",
            source_id="test-123",
            content="Test content",
            metadata={"title": "Test Item"},
            created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )

        async def mock_fetch_items(since=None, limit=100):
            yield sample_item

        source.fetch_items = mock_fetch_items
        return source

    @pytest.fixture
    def mock_limitless_config(self):
        """Create a mock LimitlessConfig"""
        config = MagicMock(spec=LimitlessConfig)
        config.is_api_key_configured.return_value = True
        config.timezone = "America/New_York"
        return config

    @pytest.fixture
    def mock_config(self, mock_limitless_config):
        """Create a mock app config"""
        config = MagicMock()
        config.limitless = mock_limitless_config
        return config

    @pytest.mark.asyncio
    async def test_fetch_limitless_for_date_success(self, mock_database, mock_ingestion_service):
        """Test successful on-demand fetch for a date with no existing data"""

        with patch("api.routes.calendar.get_config") as mock_get_config, \
             patch("api.routes.calendar.LimitlessSource") as mock_limitless_source_class:

            # Setup mocks
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config

            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)
            mock_source.namespace = "limitless"

            # Create sample DataItem
            sample_item = DataItem(
                namespace="limitless",
                source_id="test-123",
                content="Test content",
                metadata={"title": "Test Item"},
                created_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),  # 3:30 PM UTC
                updated_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),
            )

            async def mock_fetch_items(since=None, limit=100):
                yield sample_item

            mock_source.fetch_items = mock_fetch_items
            mock_limitless_source_class.return_value = mock_source

            # Setup ingestion service mocks
            mock_processor = MagicMock()
            mock_processor.process.return_value = sample_item
            mock_ingestion_service.processors = {"limitless": mock_processor}

            # Call the endpoint
            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database,
                ingestion_service=mock_ingestion_service,
            )

            # Verify result
            assert result["success"] is True
            assert result["date"] == "2024-01-15"
            assert result["items_processed"] == 1
            assert result["items_stored"] == 1
            assert "Successfully fetched and processed data" in result["message"]

            # Verify database calls
            mock_database.get_data_items_by_date.assert_called_with("2024-01-15", namespaces=["limitless"])

            # Verify source was tested
            mock_source.test_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_limitless_existing_data(self, mock_database, mock_ingestion_service):
        """Test fetch when data already exists for the date"""

        # Setup database to return existing data
        existing_items = [{"id": "limitless:existing-123", "content": "Existing content"}]
        mock_database.get_data_items_by_date.return_value = existing_items

        result = await fetch_limitless_for_date(
            date="2024-01-15",
            database=mock_database,
            ingestion_service=mock_ingestion_service,
        )

        # Verify result
        assert result["success"] is True
        assert result["date"] == "2024-01-15"
        assert result["items_processed"] == 0
        assert result["items_existing"] == 1
        assert "Data already exists" in result["message"]

    @pytest.mark.asyncio
    async def test_fetch_limitless_invalid_date(self, mock_database, mock_ingestion_service):
        """Test fetch with invalid date format"""

        with pytest.raises(HTTPException) as exc_info:
            await fetch_limitless_for_date(
                date="invalid-date",
                database=mock_database,
                ingestion_service=mock_ingestion_service,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid date format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_limitless_api_key_not_configured(self, mock_database, mock_ingestion_service):
        """Test fetch when Limitless API key is not configured"""

        with patch("api.routes.calendar.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = False
            mock_get_config.return_value = mock_config

            with pytest.raises(HTTPException) as exc_info:
                await fetch_limitless_for_date(
                    date="2024-01-15",
                    database=mock_database,
                    ingestion_service=mock_ingestion_service,
                )

            assert exc_info.value.status_code == 503
            assert "Limitless API key not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_limitless_api_connection_failed(self, mock_database, mock_ingestion_service):
        """Test fetch when Limitless API connection fails"""

        with patch("api.routes.calendar.get_config") as mock_get_config, \
             patch("api.routes.calendar.LimitlessSource") as mock_limitless_source_class:

            # Setup config
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_get_config.return_value = mock_config

            # Setup source with failed connection
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=False)
            mock_limitless_source_class.return_value = mock_source

            with pytest.raises(HTTPException) as exc_info:
                await fetch_limitless_for_date(
                    date="2024-01-15",
                    database=mock_database,
                    ingestion_service=mock_ingestion_service,
                )

            assert exc_info.value.status_code == 503
            assert "Failed to connect to Limitless API" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_limitless_no_data_found(self, mock_database, mock_ingestion_service):
        """Test fetch when no data is found for the date"""

        with patch("api.routes.calendar.get_config") as mock_get_config, \
             patch("api.routes.calendar.LimitlessSource") as mock_limitless_source_class:

            # Setup config
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config

            # Setup source with no items
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)

            async def mock_fetch_items(since=None, limit=100):
                # Empty generator - no items
                return
                yield  # unreachable

            mock_source.fetch_items = mock_fetch_items
            mock_limitless_source_class.return_value = mock_source

            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database,
                ingestion_service=mock_ingestion_service,
            )

            # Verify result
            assert result["success"] is True
            assert result["date"] == "2024-01-15"
            assert result["items_processed"] == 0
            assert "No data found" in result["message"]

    @pytest.mark.asyncio
    async def test_fetch_limitless_batch_processing(self, mock_database, mock_ingestion_service):
        """Test fetch with batch processing capability"""

        with patch("api.routes.calendar.get_config") as mock_get_config, \
             patch("api.routes.calendar.LimitlessSource") as mock_limitless_source_class:

            # Setup config
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config

            # Setup source
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)
            mock_source.namespace = "limitless"

            sample_item = DataItem(
                namespace="limitless",
                source_id="test-123",
                content="Test content",
                metadata={"title": "Test Item"},
                created_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),
            )

            async def mock_fetch_items(since=None, limit=100):
                yield sample_item

            mock_source.fetch_items = mock_fetch_items
            mock_limitless_source_class.return_value = mock_source

            # Setup processor with batch processing capability
            mock_processor = MagicMock()
            mock_processor.process_batch = AsyncMock(return_value=[sample_item])
            mock_ingestion_service.processors = {"limitless": mock_processor}

            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database,
                ingestion_service=mock_ingestion_service,
            )

            # Verify batch processing was used
            mock_processor.process_batch.assert_called_once()

            # Verify result
            assert result["success"] is True
            assert result["items_processed"] == 1

    @pytest.mark.asyncio
    async def test_fetch_limitless_processing_error(self, mock_database, mock_ingestion_service):
        """Test fetch when processing encounters errors"""

        with patch("api.routes.calendar.get_config") as mock_get_config, \
             patch("api.routes.calendar.LimitlessSource") as mock_limitless_source_class:

            # Setup config
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config

            # Setup source
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)

            sample_item = DataItem(
                namespace="limitless",
                source_id="test-123",
                content="Test content",
                metadata={"title": "Test Item"},
                created_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),
            )

            async def mock_fetch_items(since=None, limit=100):
                yield sample_item

            mock_source.fetch_items = mock_fetch_items
            mock_limitless_source_class.return_value = mock_source

            # Setup processor that raises an error
            mock_processor = MagicMock()
            mock_processor.process.side_effect = Exception("Processing error")
            mock_ingestion_service.processors = {"limitless": mock_processor}

            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database,
                ingestion_service=mock_ingestion_service,
            )

            # Verify result includes errors
            assert result["success"] is True  # Endpoint still succeeds
            assert result["items_processed"] == 1
            assert result["items_stored"] == 0  # Nothing stored due to error
            assert len(result["errors"]) > 0
            assert "Processing error" in str(result["errors"])

    @pytest.mark.asyncio
    async def test_fetch_limitless_date_range_filtering(self, mock_database, mock_ingestion_service):
        """Test that items are correctly filtered by date range"""

        with patch("api.routes.calendar.get_config") as mock_get_config, \
             patch("api.routes.calendar.LimitlessSource") as mock_limitless_source_class:

            # Setup config
            mock_config = MagicMock()
            mock_config.limitless.is_api_key_configured.return_value = True
            mock_config.limitless.timezone = "America/New_York"
            mock_get_config.return_value = mock_config

            # Setup source with items from different dates
            mock_source = MagicMock()
            mock_source.test_connection = AsyncMock(return_value=True)
            mock_source.namespace = "limitless"

            # Item from target date (should be included)
            target_item = DataItem(
                namespace="limitless",
                source_id="target-123",
                content="Target date content",
                metadata={"title": "Target Item"},
                created_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),  # Within range
                updated_at=datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc),
            )

            # Item from different date (should be excluded)
            other_item = DataItem(
                namespace="limitless",
                source_id="other-123",
                content="Other date content",
                metadata={"title": "Other Item"},
                created_at=datetime(2024, 1, 16, 15, 30, 0, tzinfo=timezone.utc),  # Outside range
                updated_at=datetime(2024, 1, 16, 15, 30, 0, tzinfo=timezone.utc),
            )

            async def mock_fetch_items(since=None, limit=100):
                yield target_item
                yield other_item  # This should be filtered out by date range logic

            mock_source.fetch_items = mock_fetch_items
            mock_limitless_source_class.return_value = mock_source

            # Setup processor
            mock_processor = MagicMock()
            mock_processor.process.return_value = target_item
            mock_ingestion_service.processors = {"limitless": mock_processor}

            result = await fetch_limitless_for_date(
                date="2024-01-15",
                database=mock_database,
                ingestion_service=mock_ingestion_service,
            )

            # Should only process the target item (1 item), not the other item
            assert result["success"] is True
            assert result["items_processed"] == 1  # Only target_item should be processed
            assert result["items_stored"] == 1

    def test_debug_logging_coverage(self):
        """Test that debug logging is comprehensively covered"""

        # Read the endpoint source code to verify logging statements
        import inspect
        source_lines = inspect.getsource(fetch_limitless_for_date)

        # Check for key debug logging patterns
        debug_patterns = [
            "[OnDemandFetch]",  # Consistent logging prefix
            "logger.info",      # Info level logging
            "logger.debug",     # Debug level logging
            "logger.error",     # Error level logging
            "logger.warning",   # Warning level logging
        ]

        for pattern in debug_patterns:
            assert pattern in source_lines, f"Missing debug logging pattern: {pattern}"

        # Check for specific debug scenarios
        debug_scenarios = [
            "Starting on-demand fetch",
            "Parsed date:",
            "No existing data found",
            "Creating LimitlessSource",
            "Testing Limitless API connectivity",
            "Successfully connected to Limitless API",
            "User timezone:",
            "Date range:",
            "Fetching data from Limitless API",
            "Fetched .* items for",
            "Using batch processing",
            "Processing .* items through ingestion pipeline",
            "On-demand fetch completed",
        ]

        for scenario in debug_scenarios:
            # Use regex-like checking for dynamic content
            if ".*" in scenario:
                base_scenario = scenario.replace(".*", "")
                assert base_scenario in source_lines, f"Missing debug scenario: {scenario}"
            else:
                assert scenario in source_lines, f"Missing debug scenario: {scenario}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
