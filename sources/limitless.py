import httpx
import asyncio
import logging
import urllib.parse
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .base import BaseSource, DataItem
from config.models import LimitlessConfig
from core.retry_utils import (RetryExecutor, create_api_retry_config, create_enhanced_api_retry_condition, 
                              create_rate_limit_retry_config, RetryConfig, BackoffStrategy)

logger = logging.getLogger(__name__)


class LimitlessSource(BaseSource):
    """Limitless API data source for lifelogs"""
    
    def __init__(self, config: LimitlessConfig):
        super().__init__("limitless")
        self.config = config
        self.client = None
        self._api_key_configured = config.is_api_key_configured()
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"X-API-Key": self.config.api_key},
                timeout=self.config.request_timeout
            )
        return self.client
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def get_source_type(self) -> str:
        return "limitless_api"
    
    async def test_connection(self) -> bool:
        """Test API connectivity"""
        if not self._api_key_configured:
            logger.warning("LIMITLESS_API_KEY is not configured in .env file. Connection test skipped.")
            return False
        
        try:
            client = self._get_client()
            response = await client.get("/v1/lifelogs", params={"limit": 1})
            return response.status_code == 200
        except Exception:
            return False
    
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch lifelogs with pagination"""
        if not self._api_key_configured:
            logger.warning("LIMITLESS_API_KEY is not configured in .env file. Skipping data fetch. Please set a valid API key.")
            return
        
        client = self._get_client()
        cursor = None
        fetched_count = 0
        
        while fetched_count < limit:
            # Calculate remaining items to fetch
            remaining = min(10, limit - fetched_count)  # Limitless API max is 10 per request
            
            # Build request parameters
            params = {
                "limit": remaining,
                "includeMarkdown": True,
                "includeHeadings": True,
                "timezone": self.config.timezone
            }
            
            if cursor:
                params["cursor"] = cursor
            
            if since:
                # Format datetime for Limitless API
                params["start"] = since.strftime("%Y-%m-%d %H:%M:%S")
            
            # Make API request with retries
            response = await self._make_request_with_retry(client, "/v1/lifelogs", params)
            
            if not response:
                break
            
            data = response.json()
            lifelogs = data.get("data", {}).get("lifelogs", [])
            
            if not lifelogs:
                break
            
            # Transform and yield data items
            for lifelog in lifelogs:
                data_item = self._transform_lifelog(lifelog)
                yield data_item
                fetched_count += 1
                
                if fetched_count >= limit:
                    break
            
            # Check for next page
            next_cursor = data.get("meta", {}).get("lifelogs", {}).get("nextCursor")
            if not next_cursor:
                break
            
            cursor = next_cursor
    
    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get specific lifelog by ID"""
        if not self._api_key_configured:
            logger.warning("LIMITLESS_API_KEY is not configured in .env file. Skipping item fetch.")
            return None
        
        try:
            client = self._get_client()
            params = {
                "includeMarkdown": True,
                "includeHeadings": True
            }
            
            response = await self._make_request_with_retry(
                client, f"/v1/lifelogs/{source_id}", params
            )
            
            if not response:
                return None
            
            data = response.json()
            lifelog = data.get("data", {}).get("lifelog")
            
            if not lifelog:
                return None
            
            return self._transform_lifelog(lifelog)
            
        except Exception:
            return None
    
    def _transform_lifelog(self, lifelog: Dict[str, Any]) -> DataItem:
        """Transform Limitless lifelog to standardized DataItem"""
        # Extract searchable content
        content_parts = []
        
        # Add title
        if lifelog.get("title"):
            content_parts.append(lifelog["title"])
        
        # Extract content from structured nodes
        if lifelog.get("contents"):
            content_parts.extend(self._extract_content_from_nodes(lifelog["contents"]))
        
        # Fallback to markdown if no structured content
        if not content_parts and lifelog.get("markdown"):
            content_parts.append(lifelog["markdown"])
        
        # Combine all content
        content = "\n\n".join(filter(None, content_parts))
        
        # Prepare metadata with full preservation
        metadata = {
            "original_lifelog": lifelog,  # Preserve complete original data
            "title": lifelog.get("title"),
            "start_time": lifelog.get("startTime"),
            "end_time": lifelog.get("endTime"),
            "is_starred": lifelog.get("isStarred", False),
            "updated_at": lifelog.get("updatedAt"),
            "speakers": self._extract_speakers(lifelog.get("contents", [])),
            "content_types": self._extract_content_types(lifelog.get("contents", [])),
            "has_markdown": bool(lifelog.get("markdown")),
            "node_count": len(lifelog.get("contents", []))
        }
        
        # Parse timestamps
        created_at = None
        updated_at = None
        
        try:
            if lifelog.get("startTime"):
                created_at = datetime.fromisoformat(lifelog["startTime"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
        
        try:
            if lifelog.get("updatedAt"):
                updated_at = datetime.fromisoformat(lifelog["updatedAt"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
        
        return DataItem(
            namespace=self.namespace,
            source_id=lifelog["id"],
            content=content,
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at
        )
    
    def _extract_content_from_nodes(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Extract text content from content nodes"""
        content_parts = []
        
        for node in nodes:
            if node.get("content"):
                # Add speaker identification for blockquotes
                if node.get("type") == "blockquote" and node.get("speakerName"):
                    speaker = node["speakerName"]
                    if node.get("speakerIdentifier") == "user":
                        speaker = f"{speaker} (You)"
                    content_parts.append(f"{speaker}: {node['content']}")
                else:
                    content_parts.append(node["content"])
            
            # Recursively extract from children
            if node.get("children"):
                content_parts.extend(self._extract_content_from_nodes(node["children"]))
        
        return content_parts
    
    def _extract_speakers(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Extract unique speakers from content nodes"""
        speakers = set()
        
        for node in nodes:
            if node.get("speakerName"):
                speakers.add(node["speakerName"])
            
            if node.get("children"):
                speakers.update(self._extract_speakers(node["children"]))
        
        return list(speakers)
    
    def _extract_content_types(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Extract unique content types from nodes"""
        types = set()
        
        for node in nodes:
            if node.get("type"):
                types.add(node["type"])
            
            if node.get("children"):
                types.update(self._extract_content_types(node["children"]))
        
        return list(types)
    
    def _generate_curl_command(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate curl command equivalent for debugging"""
        # Build full URL with parameters
        base_url = self.config.base_url.rstrip('/')
        full_url = f"{base_url}{endpoint}"
        
        if params:
            query_string = urllib.parse.urlencode(params)
            full_url = f"{full_url}?{query_string}"
        
        # Build curl command
        curl_cmd = f'curl -H "X-API-Key: {self.config.api_key}" "{full_url}"'
        
        return curl_cmd
    
    async def _make_request_with_retry(
        self, 
        client: httpx.AsyncClient, 
        endpoint: str, 
        params: Dict[str, Any]
    ) -> Optional[httpx.Response]:
        """Make HTTP request with retry logic using unified retry framework"""
        # Log the curl equivalent for debugging
        curl_cmd = self._generate_curl_command(endpoint, params)
        logger.info(f"API Request (curl equivalent): {curl_cmd}")
        
        # Create enhanced retry configuration with intelligent rate limiting
        retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_delay,
            max_delay=60.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            # Rate limiting specific settings
            rate_limit_base_delay=30.0,
            rate_limit_max_delay=self.config.rate_limit_max_delay,
            respect_retry_after=self.config.respect_retry_after,
            jitter=True
        )
        retry_condition = create_enhanced_api_retry_condition()
        retry_executor = RetryExecutor(retry_config, retry_condition)
        
        async def make_request():
            response = await client.get(endpoint, params=params)
            
            if response.status_code == 200:
                return response
            elif response.status_code in [429, 500, 502, 503, 504]:
                # These status codes will be retried by the retry condition
                response.raise_for_status()
            else:
                # Non-retryable error
                logger.error(f"API request failed with status {response.status_code}")
                return None
        
        try:
            result = await retry_executor.execute_async(make_request)
            return result.result if result.success else None
        except Exception as e:
            logger.error(f"Request failed after all retries: {e}")
            return None
    
    async def get_sync_metadata(self) -> Dict[str, Any]:
        """Return sync metadata"""
        return {
            "source_type": self.get_source_type(),
            "namespace": self.namespace,
            "api_base_url": self.config.base_url,
            "timezone": self.config.timezone,
            "last_sync": datetime.now(timezone.utc).isoformat()
        }