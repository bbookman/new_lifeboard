import httpx
import asyncio
import logging
import urllib.parse
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .base import BaseSource, DataItem
from config.models import NewsConfig
from core.retry_utils import RetryExecutor, create_api_retry_config, create_api_retry_condition

logger = logging.getLogger(__name__)


class NewsSource(BaseSource):
    """Real-time News Data API source for news articles"""
    
    def __init__(self, config: NewsConfig):
        """
        Initialize NewsSource with configuration.
        
        Args:
            config: NewsConfig instance containing API configuration
        """
        super().__init__("news")
        self.config = config
        self.client = None
        self._api_key_configured = config.is_api_key_configured()
    
    def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client.
        
        Returns:
            Configured httpx.AsyncClient instance
        """
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=f"https://{self.config.endpoint}",
                headers={
                    "x-rapidapi-key": self.config.api_key,
                    "x-rapidapi-host": self.config.endpoint
                },
                timeout=self.config.request_timeout
            )
        return self.client
    
    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    def get_source_type(self) -> str:
        """
        Return the source type identifier.
        
        Returns:
            Source type string
        """
        return "news_api"
    
    async def test_connection(self) -> bool:
        """
        Test API connectivity.
        
        Returns:
            True if connection is successful, False otherwise
        """
        if not self._api_key_configured:
            logger.warning("RAPID_API_KEY is not configured. Connection test skipped.")
            return False
        
        try:
            client = self._get_client()
            response = await client.get("/top-headlines", params={
                "limit": "1",
                "country": self.config.country,
                "lang": self.config.language
            })
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """
        Fetch news articles with pagination.
        
        Args:
            since: Optional datetime to fetch items since (not used by this API)
            limit: Maximum number of items to fetch (will use config.unique_items_per_day)
            
        Yields:
            DataItem instances containing news articles
        """
        if not self._api_key_configured:
            logger.warning("RAPID_API_KEY is not configured. Skipping data fetch.")
            return
        
        # Use unique_items_per_day as the actual limit instead of the limit parameter
        actual_limit = self.config.unique_items_per_day
        client = self._get_client()
        
        # Build request parameters
        params = {
            "limit": str(self.config.items_to_retrieve),  # Fetch more to select from
            "country": self.config.country,
            "lang": self.config.language
        }
        
        logger.info(f"Fetching up to {actual_limit} news items from API (retrieving {self.config.items_to_retrieve})")
        
        # Make API request with retries
        response = await self._make_request_with_retry(client, "/top-headlines", params)
        
        if not response:
            logger.error("Failed to fetch news data from API")
            return
        
        try:
            data = response.json()
            articles = data.get("data", [])
            
            if not articles:
                logger.info("No news articles returned from API")
                return
            
            # Yield up to unique_items_per_day articles
            count = 0
            for article in articles:
                if count >= actual_limit:
                    break
                
                data_item = self._transform_article(article)
                if data_item:
                    yield data_item
                    count += 1
                    
            logger.info(f"Successfully fetched {count} news articles")
            
        except Exception as e:
            logger.error(f"Error processing news response: {e}")
    
    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """
        Get specific news article by ID.
        
        Note: The Real-time News Data API doesn't support fetching individual articles by ID,
        so this method returns None.
        
        Args:
            source_id: Article ID (unused)
            
        Returns:
            None (not supported by this API)
        """
        logger.warning("Individual article fetching not supported by Real-time News Data API")
        return None
    
    def _transform_article(self, article: Dict[str, Any]) -> Optional[DataItem]:
        """
        Transform news article to standardized DataItem.
        
        Args:
            article: Raw article data from API
            
        Returns:
            DataItem instance or None if transformation fails
        """
        try:
            # Extract required fields
            title = article.get("title", "")
            link = article.get("link", "")
            snippet = article.get("snippet", "")
            thumbnail_url = article.get("thumbnail_url", "")
            published_datetime = article.get("published_datetime_utc", "")
            
            if not title or not link:
                logger.warning("Skipping article missing title or link")
                return None
            
            # Create searchable content combining title and snippet
            content_parts = [title]
            if snippet:
                content_parts.append(snippet)
            content = "\n\n".join(content_parts)
            
            # Prepare metadata with core fields only
            metadata = {
                "title": title,
                "link": link,
                "snippet": snippet,
                "thumbnail_url": thumbnail_url,
                "published_datetime_utc": published_datetime,
                "source_type": "news_api"
            }
            
            # Parse published datetime
            created_at = None
            if published_datetime:
                try:
                    # Handle ISO format datetime
                    if published_datetime.endswith('Z'):
                        created_at = datetime.fromisoformat(published_datetime.replace('Z', '+00:00'))
                    else:
                        created_at = datetime.fromisoformat(published_datetime)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse datetime '{published_datetime}': {e}")
            
            # Use link as source_id since API doesn't provide unique IDs
            source_id = link
            
            return DataItem(
                namespace=self.namespace,
                source_id=source_id,
                content=content,
                metadata=metadata,
                created_at=created_at,
                updated_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error transforming article: {e}")
            return None
    
    async def _make_request_with_retry(
        self, 
        client: httpx.AsyncClient, 
        endpoint: str, 
        params: Dict[str, Any]
    ) -> Optional[httpx.Response]:
        """
        Make HTTP request with retry logic using the unified retry framework.
        
        Args:
            client: HTTP client instance
            endpoint: API endpoint to call
            params: Request parameters
            
        Returns:
            Response object or None if all retries failed
        """
        # Log the request for debugging
        query_string = urllib.parse.urlencode(params)
        full_url = f"https://{self.config.endpoint}{endpoint}?{query_string}"
        logger.info(f"API Request: {full_url}")
        
        # Create retry configuration using the new utility
        retry_config = create_api_retry_config(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_delay
        )
        retry_condition = create_api_retry_condition()
        retry_executor = RetryExecutor(retry_config, retry_condition)
        
        async def make_request():
            response = await client.get(endpoint, params=params)
            
            if response.status_code == 200:
                return response
            elif response.status_code in [429, 500, 502, 503, 504]:
                # These status codes will be retried by the retry condition
                response.raise_for_status()
            else:
                # Non-retryable error (e.g., 400, 401, 404)
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return None
        
        try:
            result = await retry_executor.execute_async(make_request)
            return result.result if result.success else None
        except Exception as e:
            logger.error(f"Request failed after all retries: {e}")
            return None
    
    async def get_sync_metadata(self) -> Dict[str, Any]:
        """
        Return sync metadata.
        
        Returns:
            Dictionary containing sync metadata
        """
        return {
            "source_type": self.get_source_type(),
            "namespace": self.namespace,
            "api_endpoint": self.config.endpoint,
            "country": self.config.country,
            "language": self.config.language,
            "unique_items_per_day": self.config.unique_items_per_day,
            "items_to_retrieve": self.config.items_to_retrieve,
            "last_sync": datetime.now(timezone.utc).isoformat()
        }