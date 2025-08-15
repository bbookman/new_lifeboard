"""
Tests for Limitless API source implementation
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import httpx

from sources.limitless import LimitlessSource
from sources.base import DataItem
from config.models import LimitlessConfig

# Using shared fixtures from tests/fixtures/
# limitless_config fixture is imported via conftest.py
# limitless_client_mock, limitless_api_responses are also available


@pytest.fixture
def sample_lifelog():
    """Sample lifelog data from Limitless API"""
    return {
        "id": "lifelog_123",
        "title": "Meeting with Sarah",
        "markdown": "# Meeting with Sarah\n\n**Sarah:** The deadline has been moved to next Friday.\n\n**User:** That gives us more time to polish the presentation.",
        "startTime": "2024-01-15T14:30:00Z",
        "endTime": "2024-01-15T15:00:00Z",
        "isStarred": False,
        "updatedAt": "2024-01-15T15:05:00Z",
        "contents": [
            {
                "type": "heading1",
                "content": "Meeting with Sarah",
                "startTime": "2024-01-15T14:30:00Z",
                "endTime": "2024-01-15T14:30:05Z",
                "startOffsetMs": 0,
                "endOffsetMs": 5000,
                "children": [],
                "speakerName": None,
                "speakerIdentifier": None
            },
            {
                "type": "blockquote",
                "content": "The deadline has been moved to next Friday.",
                "startTime": "2024-01-15T14:30:10Z",
                "endTime": "2024-01-15T14:30:15Z",
                "startOffsetMs": 10000,
                "endOffsetMs": 15000,
                "children": [],
                "speakerName": "Sarah",
                "speakerIdentifier": None
            },
            {
                "type": "blockquote",
                "content": "That gives us more time to polish the presentation.",
                "startTime": "2024-01-15T14:30:20Z",
                "endTime": "2024-01-15T14:30:25Z",
                "startOffsetMs": 20000,
                "endOffsetMs": 25000,
                "children": [],
                "speakerName": "User",
                "speakerIdentifier": "user"
            }
        ]
    }


@pytest.fixture
def sample_api_response(sample_lifelog):
    """Sample API response with lifelogs"""
    return {
        "data": {
            "lifelogs": [sample_lifelog]
        },
        "meta": {
            "lifelogs": {
                "nextCursor": "next_page_cursor",
                "count": 1
            }
        }
    }


class TestLimitlessConfig:
    """Test Limitless configuration"""
    
    def test_config_creation(self):
        """Test basic configuration creation"""
        config = LimitlessConfig(api_key="test_key")
        assert config.api_key == "test_key"
        assert config.base_url == "https://api.limitless.ai"
        assert config.timezone == "UTC"
        assert config.max_retries == 3
        
    def test_config_customization(self):
        """Test configuration with custom values"""
        config = LimitlessConfig(
            api_key="custom_key",
            base_url="https://custom.api.com",
            timezone="America/New_York",
            max_retries=5
        )
        assert config.api_key == "custom_key"
        assert config.base_url == "https://custom.api.com"
        assert config.timezone == "America/New_York"
        assert config.max_retries == 5


class TestLimitlessSource:
    """Test Limitless source functionality"""
    
    @pytest.mark.asyncio
    async def test_source_initialization(self, limitless_config):
        """Test source initialization"""
        source = LimitlessSource(limitless_config)
        assert source.namespace == "limitless"
        assert source.config == limitless_config
        assert source.get_source_type() == "limitless_api"
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, limitless_config, limitless_client_mock):
        """Test successful connection test using shared fixtures"""
        with limitless_client_mock as mock_client:
            source = LimitlessSource(limitless_config)
            result = await source.test_connection()
            
            assert result is True
            # Verify the mock was called correctly
            assert len(mock_client.call_history) > 0
            method, url, kwargs = mock_client.call_history[0]
            assert method == 'GET'
            assert '/v1/lifelogs' in url
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, limitless_config):
        """Test connection test failure"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock failed response
            mock_client.get.side_effect = httpx.RequestError("Connection failed")
            
            source = LimitlessSource(limitless_config)
            result = await source.test_connection()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_client_creation(self, limitless_config):
        """Test HTTP client creation and headers"""
        source = LimitlessSource(limitless_config)
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            client = source._get_client()
            
            mock_client_class.assert_called_once_with(
                base_url="https://api.limitless.ai",
                headers={"X-API-Key": "test_api_key"},
                timeout=5.0
            )
    
    @pytest.mark.asyncio
    async def test_fetch_items_success(self, limitless_config, sample_api_response):
        """Test successful item fetching"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock successful API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_client.get.return_value = mock_response
            
            source = LimitlessSource(limitless_config)
            items = []
            
            async for item in source.fetch_items(limit=1):
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            
            # Verify DataItem structure
            assert isinstance(item, DataItem)
            assert item.namespace == "limitless"
            assert item.source_id == "lifelog_123"
            assert "Meeting with Sarah" in item.content
            assert "Sarah: The deadline has been moved" in item.content
            assert "User (You): That gives us more time" in item.content
            
            # Verify metadata preservation
            assert "original_lifelog" in item.metadata
            assert item.metadata["title"] == "Meeting with Sarah"
            assert set(item.metadata["speakers"]) == {"Sarah", "User"}
            assert "blockquote" in item.metadata["content_types"]
            assert item.metadata["has_markdown"] is True
    
    @pytest.mark.asyncio
    async def test_fetch_items_with_pagination(self, limitless_config):
        """Test fetching items with pagination"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock paginated responses
            page1_response = {
                "data": {"lifelogs": [{"id": "item1", "title": "Item 1", "contents": []}]},
                "meta": {"lifelogs": {"nextCursor": "cursor2", "count": 1}}
            }
            page2_response = {
                "data": {"lifelogs": [{"id": "item2", "title": "Item 2", "contents": []}]},
                "meta": {"lifelogs": {"nextCursor": None, "count": 1}}
            }
            
            responses = [page1_response, page2_response]
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = responses
            mock_client.get.return_value = mock_response
            
            source = LimitlessSource(limitless_config)
            items = []
            
            async for item in source.fetch_items(limit=2):
                items.append(item)
            
            assert len(items) == 2
            assert items[0].source_id == "item1"
            assert items[1].source_id == "item2"
            
            # Verify pagination calls
            assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_items_with_since_parameter(self, limitless_config, sample_api_response):
        """Test fetching items with since datetime"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_client.get.return_value = mock_response
            
            source = LimitlessSource(limitless_config)
            since_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
            
            items = []
            async for item in source.fetch_items(since=since_time, limit=1):
                items.append(item)
            
            # Verify API call parameters
            call_args = mock_client.get.call_args
            params = call_args[1]['params']
            assert params["start"] == "2024-01-15 10:00:00"
            assert params["timezone"] == "America/Los_Angeles"
    
    @pytest.mark.asyncio
    async def test_get_item_success(self, limitless_config, sample_lifelog):
        """Test getting specific item by ID"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            api_response = {"data": {"lifelog": sample_lifelog}}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response
            
            source = LimitlessSource(limitless_config)
            item = await source.get_item("lifelog_123")
            
            assert item is not None
            assert item.source_id == "lifelog_123"
            assert item.metadata["title"] == "Meeting with Sarah"
            
            # Verify API call
            mock_client.get.assert_called_once_with(
                "/v1/lifelogs/lifelog_123",
                params={"includeMarkdown": True, "includeHeadings": True}
            )
    
    @pytest.mark.asyncio
    async def test_get_item_not_found(self, limitless_config):
        """Test getting non-existent item"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock empty response
            api_response = {"data": {"lifelog": None}}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response
            
            source = LimitlessSource(limitless_config)
            item = await source.get_item("nonexistent")
            
            assert item is None
    
    @pytest.mark.asyncio
    async def test_retry_logic_on_rate_limit(self, limitless_config, sample_api_response):
        """Test retry logic when rate limited"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # First call returns 429 (rate limited), second succeeds
            rate_limit_response = MagicMock()
            rate_limit_response.status_code = 429
            
            success_response = MagicMock()
            success_response.status_code = 200
            success_response.json.return_value = sample_api_response
            
            mock_client.get.side_effect = [rate_limit_response, success_response]
            
            source = LimitlessSource(limitless_config)
            
            with patch('asyncio.sleep') as mock_sleep:
                items = []
                async for item in source.fetch_items(limit=1):
                    items.append(item)
                
                # Should have retried once
                assert len(items) == 1
                assert mock_client.get.call_count == 2
                mock_sleep.assert_called_once()  # Should have slept before retry
    
    @pytest.mark.asyncio
    async def test_data_transformation_edge_cases(self, limitless_config):
        """Test data transformation with edge cases"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Lifelog with minimal data
            minimal_lifelog = {
                "id": "minimal_123",
                "title": None,
                "markdown": None,
                "contents": [],
                "startTime": None,
                "endTime": None
            }
            
            api_response = {"data": {"lifelogs": [minimal_lifelog]}}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_client.get.return_value = mock_response
            
            source = LimitlessSource(limitless_config)
            items = []
            
            async for item in source.fetch_items(limit=1):
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            
            # Should handle empty content gracefully
            assert item.source_id == "minimal_123"
            assert item.content == ""  # Empty content
            assert item.metadata["speakers"] == []
            assert item.metadata["content_types"] == []
            assert item.created_at is None
            assert item.updated_at is None
    
    @pytest.mark.asyncio
    async def test_speaker_extraction(self, limitless_config):
        """Test speaker extraction from content nodes"""
        source = LimitlessSource(limitless_config)
        
        nodes = [
            {"speakerName": "Alice", "children": []},
            {"speakerName": "Bob", "children": []},
            {"speakerName": "Alice", "children": []},  # Duplicate
            {"children": [{"speakerName": "Charlie"}]}  # Nested
        ]
        
        speakers = source._extract_speakers(nodes)
        assert set(speakers) == {"Alice", "Bob", "Charlie"}
    
    @pytest.mark.asyncio
    async def test_content_type_extraction(self, limitless_config):
        """Test content type extraction from nodes"""
        source = LimitlessSource(limitless_config)
        
        nodes = [
            {"type": "heading1", "children": []},
            {"type": "blockquote", "children": []},
            {"type": "heading1", "children": []},  # Duplicate
            {"children": [{"type": "paragraph"}]}  # Nested
        ]
        
        types = source._extract_content_types(nodes)
        assert set(types) == {"heading1", "blockquote", "paragraph"}
    
    @pytest.mark.asyncio
    async def test_client_cleanup(self, limitless_config):
        """Test HTTP client cleanup"""
        source = LimitlessSource(limitless_config)
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Get client (creates it)
            client = source._get_client()
            assert source.client is not None
            
            # Close should clean up
            await source.close()
            mock_client.aclose.assert_called_once()
            assert source.client is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, limitless_config):
        """Test using source as async context manager"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            async with LimitlessSource(limitless_config) as source:
                assert source is not None
                # Use source here
                client = source._get_client()
            
            # Should have closed automatically
            mock_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_metadata(self, limitless_config):
        """Test sync metadata generation"""
        source = LimitlessSource(limitless_config)
        metadata = await source.get_sync_metadata()
        
        assert metadata["source_type"] == "limitless_api"
        assert metadata["namespace"] == "limitless"
        assert metadata["api_base_url"] == "https://api.limitless.ai"
        assert metadata["timezone"] == "America/Los_Angeles"
        assert "last_sync" in metadata
        
        # Verify last_sync is valid ISO timestamp
        datetime.fromisoformat(metadata["last_sync"])  # Should not raise