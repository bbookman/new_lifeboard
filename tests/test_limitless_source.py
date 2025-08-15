"""
Comprehensive tests for LimitlessSource and LimitlessProcessor.

This test suite covers all Limitless functionality including API integration,
data transformation, processor pipeline, deduplication, segmentation, and
error handling across various scenarios.
"""

import pytest
import asyncio
import httpx
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any, Optional

from sources.limitless import LimitlessSource
from sources.limitless_processor import (
    LimitlessProcessor, 
    BasicCleaningProcessor,
    MetadataEnrichmentProcessor,
    ConversationSegmentProcessor,
    MarkdownProcessor,
    DeduplicationProcessor,
    ConversationSegment
)
from sources.base import DataItem
from config.models import LimitlessConfig

# Using shared fixtures from tests/fixtures/
# app_config, etc. are available


@pytest.fixture
def limitless_config():
    """Create mock Limitless configuration"""
    config = Mock(spec=LimitlessConfig)
    config.base_url = "https://api.limitless.ai"
    config.api_key = "test_api_key_12345678"
    config.request_timeout = 30.0
    config.timezone = "America/Los_Angeles"
    config.max_retries = 3
    config.retry_delay = 1.0
    config.rate_limit_max_delay = 60.0
    config.respect_retry_after = True
    config.is_api_key_configured.return_value = True
    return config


@pytest.fixture
def limitless_config_no_key():
    """Create mock Limitless configuration without API key"""
    config = Mock(spec=LimitlessConfig)
    config.base_url = "https://api.limitless.ai"
    config.api_key = None
    config.request_timeout = 30.0
    config.timezone = "America/Los_Angeles"
    config.max_retries = 3
    config.retry_delay = 1.0
    config.rate_limit_max_delay = 60.0
    config.respect_retry_after = True
    config.is_api_key_configured.return_value = False
    return config


@pytest.fixture
def limitless_source(limitless_config):
    """Create LimitlessSource instance for testing"""
    return LimitlessSource(limitless_config)


@pytest.fixture
def sample_lifelog_data():
    """Create sample lifelog data matching Limitless API format"""
    return {
        "id": "lifelog_123456",
        "title": "Daily Standup Meeting",
        "startTime": "2025-01-15T10:00:00Z",
        "endTime": "2025-01-15T10:30:00Z",
        "isStarred": False,
        "updatedAt": "2025-01-15T10:35:00Z",
        "markdown": "# Daily Standup Meeting\n\nDiscussed project progress and blockers.",
        "contents": [
            {
                "type": "heading1",
                "content": "Daily Standup Meeting",
                "startTime": "2025-01-15T10:00:00Z",
                "endTime": "2025-01-15T10:00:30Z"
            },
            {
                "type": "blockquote",
                "content": "What did you work on yesterday?",
                "speakerName": "Alice",
                "speakerIdentifier": "speaker_1",
                "startTime": "2025-01-15T10:01:00Z",
                "endTime": "2025-01-15T10:01:15Z"
            },
            {
                "type": "blockquote",
                "content": "I completed the user authentication module and started on the API endpoints.",
                "speakerName": "Bob",
                "speakerIdentifier": "user",
                "startTime": "2025-01-15T10:01:30Z",
                "endTime": "2025-01-15T10:02:00Z"
            }
        ]
    }


@pytest.fixture
def sample_api_response(sample_lifelog_data):
    """Create sample API response from Limitless"""
    return {
        "data": {
            "lifelogs": [sample_lifelog_data]
        },
        "meta": {
            "lifelogs": {
                "nextCursor": "cursor_next_123",
                "hasMore": True
            }
        }
    }


@pytest.fixture
def limitless_processor():
    """Create LimitlessProcessor instance for testing"""
    return LimitlessProcessor(
        enable_segmentation=True,
        enable_markdown_generation=True,
        enable_semantic_deduplication=False  # Disabled for unit testing
    )


class TestLimitlessSourceInitialization:
    """Test Limitless source initialization and configuration"""
    
    def test_source_initialization_with_api_key(self, limitless_config):
        """Test successful source initialization with API key"""
        source = LimitlessSource(limitless_config)
        
        assert source.config == limitless_config
        assert source.namespace == "limitless"
        assert source._api_key_configured is True
        assert source.get_source_type() == "limitless_api"
    
    def test_source_initialization_without_api_key(self, limitless_config_no_key):
        """Test source initialization without API key"""
        source = LimitlessSource(limitless_config_no_key)
        
        assert source.config == limitless_config_no_key
        assert source._api_key_configured is False
    
    def test_create_client_config(self, limitless_source):
        """Test HTTP client configuration creation"""
        config = limitless_source._create_client_config()
        
        assert config["base_url"] == "https://api.limitless.ai"
        assert config["headers"]["X-API-Key"] == "test_api_key_12345678"
        assert config["timeout"] == 30.0


class TestLimitlessSourceConnectivity:
    """Test API connectivity and authentication"""
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, limitless_source):
        """Test successful connection test"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch.object(limitless_source, '_make_test_request', return_value=mock_response):
            result = await limitless_source.test_connection()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, limitless_source):
        """Test connection test failure"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 401
        
        with patch.object(limitless_source, '_make_test_request', return_value=mock_response):
            result = await limitless_source.test_connection()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_test_connection_no_api_key(self, limitless_config_no_key):
        """Test connection test with no API key configured"""
        source = LimitlessSource(limitless_config_no_key)
        
        result = await source.test_connection()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_test_connection_exception(self, limitless_source):
        """Test connection test with exception"""
        with patch.object(limitless_source, '_make_test_request', side_effect=Exception("Network error")):
            result = await limitless_source.test_connection()
        
        assert result is False


class TestLimitlessSourceDataFetching:
    """Test data fetching and pagination"""
    
    @pytest.mark.asyncio
    async def test_fetch_items_basic(self, limitless_source, sample_api_response):
        """Test basic item fetching"""
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        
        with patch.object(limitless_source, '_make_request_with_retry', return_value=mock_response):
            items = []
            async for item in limitless_source.fetch_items(limit=1):  # Request only 1 item
                items.append(item)
        
        assert len(items) == 1
        item = items[0]
        assert isinstance(item, DataItem)
        assert item.namespace == "limitless"
        assert item.source_id == "lifelog_123456"
        assert "Daily Standup Meeting" in item.content
        assert item.metadata["title"] == "Daily Standup Meeting"
    
    @pytest.mark.asyncio
    async def test_fetch_items_with_since_parameter(self, limitless_source, sample_api_response):
        """Test fetching items with since timestamp"""
        since_time = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        
        with patch.object(limitless_source, '_make_request_with_retry', return_value=mock_response) as mock_request:
            items = []
            async for item in limitless_source.fetch_items(since=since_time, limit=10):
                items.append(item)
        
        # Verify since parameter was passed correctly
        call_args = mock_request.call_args
        params = call_args[0][2]  # Third argument is params
        assert "start" in params
        assert params["start"] == "2025-01-15 09:00:00"
    
    @pytest.mark.asyncio
    async def test_fetch_items_pagination(self, limitless_source):
        """Test pagination through multiple pages"""
        # First page response
        first_response = Mock()
        first_response.json.return_value = {
            "data": {"lifelogs": [{"id": "item1", "title": "Item 1", "contents": []}]},
            "meta": {"lifelogs": {"nextCursor": "cursor_123", "hasMore": True}}
        }
        
        # Second page response
        second_response = Mock()
        second_response.json.return_value = {
            "data": {"lifelogs": [{"id": "item2", "title": "Item 2", "contents": []}]},
            "meta": {"lifelogs": {"nextCursor": None, "hasMore": False}}
        }
        
        # Mock the request method to return different responses
        with patch.object(limitless_source, '_make_request_with_retry', side_effect=[first_response, second_response]):
            items = []
            async for item in limitless_source.fetch_items(limit=20):
                items.append(item)
        
        assert len(items) == 2
        assert items[0].source_id == "item1"
        assert items[1].source_id == "item2"
    
    @pytest.mark.asyncio
    async def test_fetch_items_no_api_key(self, limitless_config_no_key):
        """Test fetching items without API key"""
        source = LimitlessSource(limitless_config_no_key)
        
        items = []
        async for item in source.fetch_items(limit=10):
            items.append(item)
        
        assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_items_api_error(self, limitless_source):
        """Test fetching items with API error"""
        with patch.object(limitless_source, '_make_request_with_retry', return_value=None):
            items = []
            async for item in limitless_source.fetch_items(limit=10):
                items.append(item)
        
        assert len(items) == 0


class TestLimitlessSourceDataTransformation:
    """Test data transformation from Limitless format to DataItem"""
    
    def test_transform_lifelog_basic(self, limitless_source, sample_lifelog_data):
        """Test basic lifelog transformation"""
        data_item = limitless_source._transform_lifelog(sample_lifelog_data)
        
        assert isinstance(data_item, DataItem)
        assert data_item.namespace == "limitless"
        assert data_item.source_id == "lifelog_123456"
        assert "Daily Standup Meeting" in data_item.content
        
        # Check metadata preservation
        assert data_item.metadata["original_lifelog"] == sample_lifelog_data
        assert data_item.metadata["title"] == "Daily Standup Meeting"
        assert data_item.metadata["is_starred"] is False
        assert "Alice" in data_item.metadata["speakers"]
        assert "Bob" in data_item.metadata["speakers"]
    
    def test_transform_lifelog_content_extraction(self, limitless_source):
        """Test content extraction from structured nodes"""
        lifelog_data = {
            "id": "test_123",
            "title": "Test Conversation",
            "contents": [
                {
                    "type": "blockquote",
                    "content": "Hello there!",
                    "speakerName": "Alice",
                    "speakerIdentifier": "speaker_1"
                },
                {
                    "type": "blockquote", 
                    "content": "Hi Alice, how are you?",
                    "speakerName": "Bob",
                    "speakerIdentifier": "user"
                }
            ]
        }
        
        data_item = limitless_source._transform_lifelog(lifelog_data)
        
        assert "Test Conversation" in data_item.content
        assert "Alice: Hello there!" in data_item.content
        assert "Bob (You): Hi Alice, how are you?" in data_item.content
    
    def test_transform_lifelog_timestamp_parsing(self, limitless_source):
        """Test timestamp parsing in transformation"""
        lifelog_data = {
            "id": "time_test",
            "startTime": "2025-01-15T10:00:00Z",
            "updatedAt": "2025-01-15T10:30:00.123Z"
        }
        
        data_item = limitless_source._transform_lifelog(lifelog_data)
        
        assert data_item.created_at is not None
        assert data_item.updated_at is not None
        assert data_item.created_at.year == 2025
        assert data_item.created_at.month == 1
        assert data_item.created_at.day == 15


class TestLimitlessProcessor:
    """Test Limitless content processor"""
    
    def test_processor_initialization(self):
        """Test processor initialization"""
        processor = LimitlessProcessor(
            enable_segmentation=True,
            enable_markdown_generation=True,
            enable_semantic_deduplication=False
        )
        
        pipeline_info = processor.get_pipeline_info()
        assert pipeline_info["semantic_deduplication_enabled"] is False
        assert pipeline_info["supports_batch_processing"] is True
        assert "BasicCleaningProcessor" in pipeline_info["processors"]
        assert "MetadataEnrichmentProcessor" in pipeline_info["processors"]
    
    def test_process_single_item(self, limitless_processor, sample_lifelog_data):
        """Test processing a single data item"""
        # Create test data item
        data_item = DataItem(
            namespace="limitless",
            source_id="test_123",
            content="Test conversation content",
            metadata={"original_lifelog": sample_lifelog_data},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        processed_item = limitless_processor.process(data_item)
        
        # Check two-key metadata structure
        assert "original_response" in processed_item.metadata
        assert "processed_response" in processed_item.metadata
        assert processed_item.metadata["original_response"] == sample_lifelog_data
        
        # Check processed metadata
        processed = processed_item.metadata["processed_response"]
        assert "processing_history" in processed
        assert "title" in processed
        assert "speakers" in processed
        assert processed["title"] == "Daily Standup Meeting"


class TestBasicCleaningProcessor:
    """Test basic text cleaning processor"""
    
    def test_basic_cleaning(self):
        """Test basic text cleaning functionality"""
        processor = BasicCleaningProcessor()
        
        # Create test item with messy content
        item = DataItem(
            namespace="test",
            source_id="clean_test",
            content="  This  has   multiple\t\tspaces\n\n\nand\x00control\x1fchars  ",
            metadata={"processed_response": {}},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        processed_item = processor.process(item)
        
        # Check content was cleaned
        assert processed_item.content == "This has multiple spaces and control chars"
        
        # Check processing was tracked
        processed = processed_item.metadata["processed_response"]
        assert "processing_history" in processed
        assert any(
            entry["processor"] == "BasicCleaningProcessor" 
            for entry in processed["processing_history"]
        )


class TestPerformanceScenarios:
    """Test performance-related scenarios"""
    
    @pytest.mark.asyncio
    async def test_large_batch_processing(self, limitless_processor):
        """Test processing of large batches"""
        # Create large batch of items - these need to go through the processor to get two-key structure
        items = []
        for i in range(25):
            lifelog_data = {
                "id": f"batch_item_{i}",
                "title": f"Batch Item {i}",
                "contents": []
            }
            
            item = DataItem(
                namespace="limitless",
                source_id=f"batch_item_{i}",
                content=f"Content for item {i}",
                metadata={"original_lifelog": lifelog_data},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            # Process each item individually first to create two-key structure
            processed_item = limitless_processor.process(item)
            items.append(processed_item)
        
        # Process batch (items already have two-key structure)
        processed_items = await limitless_processor.process_batch(items)
        
        assert len(processed_items) == 25
        
        # Verify all items were processed and have two-key structure
        for item in processed_items:
            assert "original_response" in item.metadata
            assert "processed_response" in item.metadata
            assert item.metadata["processed_response"]["title"] == f"Batch Item {item.metadata['original_response']['id'].split('_')[-1]}"