import httpx
import asyncio
import logging
import urllib.parse
import json
import hashlib
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .base import BaseSource, DataItem
from config.models import NewsConfig
from core.database import DatabaseService
from core.retry_utils import (
    RetryExecutor,
    create_api_retry_config,
    create_enhanced_api_retry_condition,
    create_rate_limit_retry_config,
    RetryConfig,
    BackoffStrategy,
)
from core.http_client_mixin import BaseHTTPSource

logger = logging.getLogger(__name__)


class NewsSource(BaseHTTPSource, BaseSource):
    """Real-time News Data API source for news articles"""
    
    def __init__(self, config: NewsConfig, db_service: DatabaseService = None):
        """
        Initialize NewsSource with configuration.
        
        Args:
            config: NewsConfig instance containing API configuration
            db_service: DatabaseService instance for data operations
        """
        super().__init__(config, "news")
        self.config = config
        self.db_service = db_service
        self._api_key_configured = self.config.is_api_key_configured()
        self._endpoint_configured = self.config.is_endpoint_configured()

    def is_configured(self) -> bool:
        """Check if the source is fully configured"""
        return self._api_key_configured and self._endpoint_configured
    
    def _create_client_config(self) -> Dict[str, Any]:
        """Create HTTP client configuration for News API"""
        if not self.is_configured():
            raise ValueError("News source is not configured.")
        
        return {
            "base_url": f"https://{self.config.endpoint}",
            "headers": {
                "x-rapidapi-key": self.config.api_key,
                "x-rapidapi-host": self.config.endpoint
            },
            "timeout": self.config.request_timeout
        }
    
    def get_source_type(self) -> str:
        """
        Return the source type identifier.
        
        Returns:
            Source type string
        """
        return "news_api"
    
    async def _make_test_request(self, client: httpx.AsyncClient) -> httpx.Response:
        """Make a test request to verify News API connectivity"""
        return await client.get("/top-headlines", params={
            "limit": "1",
            "country": self.config.country,
            "lang": self.config.language
        })
    
    async def test_connection(self) -> bool:
        """
        Test API connectivity.
        
        Returns:
            True if connection is successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("News source is not configured. Connection test skipped.")
            return False
        
        return await super().test_connection()

    def _has_news_data_for_date(self, date: str) -> bool:
        """Check if news data already exists for the given date"""
        if not self.db_service:
            return False
        
        count = self.get_news_count_by_date(self.db_service, date)
        return count > 0
    
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """
        Fetch news articles with pagination.
        
        Args:
            since: Optional datetime to fetch items since (not used by this API)
            limit: Maximum number of items to fetch (will use config.unique_items_per_day)
            
        Yields:
            DataItem instances containing news articles
        """
        logger.info(f"Starting news fetch - configured: {self.is_configured()}, endpoint: {self.config.endpoint}")
        
        if not self.is_configured():
            logger.warning("News source is not configured. Skipping data fetch.")
            logger.warning(f"API key configured: {self._api_key_configured}, Endpoint configured: {self._endpoint_configured}")
            return

        # Check if we already have news data for today
        today = datetime.now().strftime("%Y-%m-%d")
        if self._has_news_data_for_date(today):
            logger.info(f"News data already exists for {today}. Skipping API call.")
            # Yield a dummy item to indicate we checked but didn't fetch new data
            yield DataItem(
                namespace=self.namespace,
                source_id="news_check",
                content="News data already exists for today",
                metadata={"check_date": today, "status": "skipped"}
            )
            return
        
        # Use unique_items_per_day as the actual limit instead of the limit parameter
        actual_limit = self.config.unique_items_per_day
        logger.debug(f"Fetching up to {actual_limit} unique news items for {today}")
        client = await self._ensure_client()
        
        # Build request parameters
        params = {
            "limit": str(self.config.items_to_retrieve),  # Fetch more to select from
            "country": self.config.country,
            "lang": self.config.language
        }
        
        logger.info(f"Fetching up to {actual_limit} news items from API (retrieving {self.config.items_to_retrieve})")
        
        # Make API request with retries
        logger.debug(f"Making API request to /top-headlines with params: {params}")
        response = await self._make_request_with_retry(client, "/top-headlines", params)
        
        if not response:
            logger.error("Failed to fetch news data from API")
            return
        
        try:
            logger.debug(f"API response status: {response.status_code}")
            data = response.json()
            logger.debug(f"API response data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            articles = data.get("data", [])
            logger.info(f"API returned {len(articles)} articles")
            
            if not articles:
                logger.info("No news articles returned from API")
                logger.debug(f"Full API response: {data}")
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
            logger.debug(f"Transforming article with title: '{article.get('title')}'")
            # Extract required fields
            title = article.get("title", "")
            link = article.get("link", "")
            snippet = article.get("snippet", "")
            thumbnail_url = article.get("thumbnail_url", "")
            published_datetime = article.get("published_datetime_utc", "")
            
            if not title or not link:
                logger.warning(f"Skipping article missing title or link: {article}")
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
            if published_datetime and isinstance(published_datetime, str):
                try:
                    # Handle ISO format datetime
                    if published_datetime.endswith('Z'):
                        created_at = datetime.fromisoformat(published_datetime.replace('Z', '+00:00'))
                    else:
                        created_at = datetime.fromisoformat(published_datetime)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse datetime '{published_datetime}': {e}")
            elif published_datetime:
                logger.warning(f"published_datetime is not a string: {type(published_datetime)} = {published_datetime}")
            
            # Use a hash of the link as the source_id for a stable, unique identifier
            logger.debug(f"Hashing link: {link}")
            source_id = hashlib.sha1(link.encode()).hexdigest()
            
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
                # Non-retryable error (e.g., 400, 401, 404)
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return None
        
        try:
            result = await retry_executor.execute_async(make_request)
            return result.result if result.success else None
        except Exception as e:
            logger.error(f"Request failed after all retries: {e}")
            return None
    
    def get_news_by_date(self, db_service, date: str) -> List[Dict[str, Any]]:
        """Get news articles for a specific date (YYYY-MM-DD format)"""
        with db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, source_id, content, metadata, created_at, days_date
                FROM data_items 
                WHERE namespace = 'news' AND days_date = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (date, self.config.unique_items_per_day))
            
            news_items = []
            for row in cursor.fetchall():
                # Parse metadata to extract title and other fields
                from core.json_utils import JSONMetadataParser
                metadata = JSONMetadataParser.parse_metadata(row["metadata"]) or {}
                
                news_items.append({
                    "title": metadata.get("title", row["content"][:100] + "..."),
                    "link": metadata.get("link", row["source_id"]),
                    "snippet": metadata.get("snippet", ""),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "published_datetime_utc": metadata.get("published_datetime_utc"),
                    "created_at": row["created_at"],
                    "content": row["content"],
                    "source": "data_items"
                })
            
            return news_items

    def get_latest_news(self, db_service, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent news articles"""
        with db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, source_id, content, metadata, created_at, days_date
                FROM data_items 
                WHERE namespace = 'news'
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            news_items = []
            for row in cursor.fetchall():
                # Parse metadata to extract title and other fields
                from core.json_utils import JSONMetadataParser
                metadata = JSONMetadataParser.parse_metadata(row["metadata"]) or {}
                
                news_items.append({
                    "title": metadata.get("title", row["content"][:100] + "..."),
                    "link": metadata.get("link", row["source_id"]),
                    "snippet": metadata.get("snippet", ""),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "published_datetime_utc": metadata.get("published_datetime_utc"),
                    "created_at": row["created_at"],
                    "content": row["content"],
                    "source": "data_items"
                })
            
            return news_items

    def get_news_count_by_date(self, db_service, date: str) -> int:
        """Get count of news articles for a specific date"""
        with db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM data_items 
                WHERE namespace = 'news' AND days_date = ?
            """, (date,))
            
            return cursor.fetchone()["count"]

    async def get_sync_metadata(self) -> Dict[str, Any]:
        """
        Return sync metadata.
        
        Returns:
            Dictionary containing sync metadata
        """
        return {
            "source_type": self.get_source_type(),
            "namespace": self.namespace,
            "is_configured": self.is_configured(),
            "api_endpoint": self.config.endpoint,
            "country": self.config.country,
            "language": self.config.language,
            "unique_items_per_day": self.config.unique_items_per_day,
            "items_to_retrieve": self.config.items_to_retrieve,
            "last_sync": datetime.now(timezone.utc).isoformat()
        }