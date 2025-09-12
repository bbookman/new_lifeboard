import json
import os
import re
import shutil
import zipfile
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, AsyncIterator

from config.models import TwitterConfig
from core.database import DatabaseService
from sources.base import BaseSource, DataItem
from sources.twitter_processor import TwitterProcessor
from services.twitter_api_service import TwitterAPIService
from services.twitter_rate_limit_service import TwitterRateLimitService
import logging

logger = logging.getLogger(__name__)

class TwitterSource(BaseSource):
    """Twitter data source"""

    def __init__(self, config: TwitterConfig, twitter_api_service: TwitterAPIService = None, rate_limit_service: TwitterRateLimitService = None):
        super().__init__("twitter")
        self.config = config
        self.processor = TwitterProcessor()
        # Initialize a local database service for consistency
        self.db_service = DatabaseService()
        # Initialize services in correct order
        self.rate_limit_service = rate_limit_service or TwitterRateLimitService(self.db_service, self.config.rate_limit_minutes)
        self.api_service = twitter_api_service or TwitterAPIService(config)
    
    async def cleanup(self):
        """Clean up resources - TwitterAPIService manages its own session lifecycle via context manager"""
        # TwitterAPIService handles session cleanup via __aexit__ when used with async context manager
        # No manual session cleanup needed here
        logger.info("[TWITTER] Cleanup called - TwitterAPIService manages its own session lifecycle")

    async def import_from_zip(self, zip_path: str) -> Dict[str, Any]:
        """Import Twitter data from a zip archive, only adding new tweets."""
        if not self.config.is_configured():
            logger.warning("[TWITTER IMPORT] Twitter source not enabled. Skipping import.")
            return {
                "success": False,
                "imported_count": 0,
                "message": "Twitter source is not enabled in the configuration."
            }

        temp_dir = "twitter_data"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        try:
            logger.info(f"[TWITTER IMPORT] Starting Twitter import from zip: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                logger.info(f"[TWITTER IMPORT] Extracted zip to: {temp_dir}")

            # PERMANENT FIX: Robust file discovery that prioritizes tweets.js and never looks for tweet.js
            tweets_js_path = None
            possible_filenames = ['tweets.js']  # Correct filename only - NEVER look for tweet.js
            
            for root, _, files in os.walk(temp_dir):
                logger.info(f"[TWITTER IMPORT] DEBUG: Files found in {root}: {files}")
                for filename in possible_filenames:
                    if filename in files:
                        tweets_js_path = os.path.join(root, filename)
                        logger.info(f"[TWITTER IMPORT] Found Twitter data file: {filename} at: {tweets_js_path}")
                        break
                if tweets_js_path:
                    break
            
            if not tweets_js_path:
                logger.error(f"[TWITTER IMPORT] tweets.js not found in the extracted archive at {temp_dir}")
                logger.error(f"[TWITTER IMPORT] Searched for files: {possible_filenames}")
                return {
                    "success": False,
                    "imported_count": 0,
                    "message": "Could not find tweets.js in the archive. Make sure you're using the correct Twitter archive format."
                }

            with open(tweets_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'window.YTD.tweet.part0 = [' in content:
                    content = content.split('window.YTD.tweet.part0 = [', 1)[1]
                    content = content.rsplit(']', 1)[0]
                elif 'window.YTD.tweets.part0 = [' in content: # Handle plural 'tweets'
                    content = content.split('window.YTD.tweets.part0 = [', 1)[1]
                    content = content.rsplit(']', 1)[0]

                tweets = json.loads(f'[{content}]')

            parsed_tweets = self._parse_tweets(tweets)
            logger.info(f"[TWITTER IMPORT] Parsed {len(parsed_tweets)} total tweets from the archive.")

            # Get existing tweets from data_items table
            existing_tweet_ids = await self._get_existing_tweet_ids()
            logger.info(f"[TWITTER IMPORT] Found {len(existing_tweet_ids)} existing tweets in database.")

            # Filter out existing tweets
            new_tweets = [t for t in parsed_tweets if t['tweet_id'] not in existing_tweet_ids]
            logger.info(f"[TWITTER IMPORT] Found {len(new_tweets)} new tweets to import.")

            if not new_tweets:
                logger.info("[TWITTER IMPORT] No new tweets to import. Skipping database storage.")
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "Twitter archive processed. No new tweets found to import."
                }

            # Transform tweets to DataItems (but don't ingest directly)
            data_items = self._transform_tweets_to_items(new_tweets, 'twitter_archive')
            logger.info(f"[TWITTER IMPORT] Transformed {len(data_items)} tweets to DataItems - ready for external ingestion")
            
            return {
                "success": True,
                "imported_count": len(new_tweets),
                "message": f"Successfully imported {len(new_tweets)} new tweets.",
                "data_items": data_items  # Return the items for external ingestion
            }
        except Exception as e:
            logger.error(f"[TWITTER IMPORT] Error processing Twitter zip import: {e}", exc_info=True)
            return {
                "success": False, 
                "imported_count": 0, 
                "message": f"An error occurred during import: {e}"
            }
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def _parse_tweets(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse raw tweet objects"""
        parsed_tweets = []
        for item in tweets:
            tweet = item.get('tweet', {})
            tweet_id = tweet.get('id_str') or tweet.get('id')
            if not tweet_id:
                continue

            created_at_str = tweet.get('created_at')
            try:
                created_at_naive = datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y')
                created_at = created_at_naive.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.warning(f"[TWITTER IMPORT] Could not parse date for tweet {tweet_id}, skipping.")
                continue

            media_urls = []
            if 'media' in tweet.get('entities', {}):
                for media in tweet['entities']['media']:
                    media_urls.append(media.get('media_url_https'))

            parsed_tweets.append({
                'tweet_id': tweet_id,
                'created_at': created_at.isoformat(),
                'days_date': created_at.strftime('%Y-%m-%d'),
                'text': tweet.get('full_text'),
                'media_urls': json.dumps(media_urls)
            })
        return parsed_tweets

    async def _get_existing_tweet_ids(self) -> set:
        """Get existing tweet IDs from data_items table"""
        logger.info(f"[TWITTER TRACE] Querying existing tweets: namespace={self.namespace}, limit=10000")
        start_time = time.time()
        
        existing_tweets = await self.db_service.async_get_data_items_by_namespace(self.namespace, limit=10000)
        existing_ids = {item['source_id'] for item in existing_tweets}
        
        query_duration = (time.time() - start_time) * 1000
        logger.info(f"[TWITTER TRACE] Database returned {len(existing_ids)} existing tweet IDs in {query_duration:.2f}ms")
        
        # Log sample of existing IDs for verification (first 5)
        if existing_ids:
            sample_ids = list(existing_ids)[:5]
            logger.info(f"[TWITTER TRACE] Sample existing tweet IDs: {sample_ids}")
        
        return existing_ids

    def _transform_tweets_to_items(self, tweets: List[Dict[str, Any]], source_type: str = 'twitter_archive') -> List[DataItem]:
        """Transform tweet dicts to DataItem objects and return them"""
        logger.info(f"[TWITTER TRACE] Transforming {len(tweets)} tweets to DataItems with source_type={source_type}")
        start_time = time.time()
        
        if not tweets:
            logger.warning(f"[TWITTER TRACE] No tweets to transform")
            return []

        # Convert tweet dicts to DataItem objects
        data_items = []
        for i, tweet in enumerate(tweets):
            try:
                tweet_id = tweet.get('tweet_id', 'unknown')
                logger.debug(f"[TWITTER TRACE] Creating DataItem {i+1}/{len(tweets)} for tweet_id={tweet_id}")
                
                # Parse timestamp
                created_at = None
                if tweet.get('created_at'):
                    created_at = datetime.fromisoformat(tweet['created_at'])

                # Create DataItem
                data_item = DataItem(
                    namespace=self.namespace,
                    source_id=tweet_id,
                    content=tweet['text'] or "",
                    metadata={
                        'media_urls': tweet.get('media_urls', '[]'),
                        'original_created_at': tweet.get('created_at'),
                        'days_date': tweet.get('days_date'),
                        'source_type': source_type
                    },
                    created_at=created_at,
                    updated_at=datetime.now()
                )

                logger.debug(f"[TWITTER TRACE] DataItem created: source_id={tweet_id}, content_length={len(data_item.content)}, metadata_keys={list(data_item.metadata.keys())}")

                # Process the item
                processed_item = self.processor.process(data_item)
                data_items.append(processed_item)

            except Exception as e:
                logger.error(f"[TWITTER TRACE] Error creating DataItem for tweet {tweet.get('tweet_id', 'unknown')}: {e}")
                continue

        total_duration = (time.time() - start_time) * 1000
        logger.info(f"[TWITTER TRACE] Tweet transformation complete: {len(data_items)} DataItems created in {total_duration:.2f}ms")
        return data_items

    async def fetch_today_tweets(self) -> List[Dict[str, Any]]:
        """Fetch today's tweets from Twitter API with rate limiting"""
        start_time = time.time()
        logger.info(f"[TWITTER TRACE] fetch_today_tweets starting at {datetime.now().isoformat()}")
        
        # Log configuration details
        logger.info(f"[TWITTER TRACE] Twitter config state: enabled={self.config.enabled}")
        logger.info(f"[TWITTER TRACE] Bearer token configured: {bool(self.config.bearer_token)}")
        logger.info(f"[TWITTER TRACE] Username configured: {bool(self.config.username)}")
        logger.info(f"[TWITTER TRACE] User ID configured: {bool(self.config.user_id)}")
        logger.info(f"[TWITTER TRACE] is_api_configured() result: {self.config.is_api_configured()}")
        
        if not self.config.is_api_configured():
            logger.warning("[TWITTER TRACE] Twitter API not configured. Skipping real-time tweet fetch.")
            return []
        
        # Check rate limiting before attempting fetch
        logger.info("[TWITTER TRACE] Checking rate limiting status...")
        rate_limit_start = time.time()
        can_fetch, minutes_until = await self.rate_limit_service.can_fetch_now()
        rate_limit_duration = (time.time() - rate_limit_start) * 1000
        
        logger.info(f"[TWITTER TRACE] Rate limit check completed in {rate_limit_duration:.2f}ms: can_fetch={can_fetch}, minutes_until={minutes_until}")
        
        if not can_fetch:
            logger.info(f"[TWITTER TRACE] Rate limited. Next fetch available in {minutes_until} minutes. Returning empty list.")
            return []
        
        try:
            logger.info("[TWITTER TRACE] Opening API service context manager...")
            context_start = time.time()
            
            # Check if api_service is the correct type
            if not hasattr(self.api_service, '__aenter__'):
                logger.error(f"[TWITTER TRACE] api_service is not an async context manager: {type(self.api_service)}")
                raise ValueError(f"api_service must be TwitterAPIService, got {type(self.api_service)}")
            
            async with self.api_service:
                context_duration = (time.time() - context_start) * 1000
                logger.info(f"[TWITTER TRACE] API service context opened in {context_duration:.2f}ms")
                
                api_call_start = time.time()
                logger.info("[TWITTER TRACE] Calling fetch_user_tweets_today...")
                tweets = await self.api_service.fetch_user_tweets_today()
                api_call_duration = (time.time() - api_call_start) * 1000
                
                logger.info(f"[TWITTER TRACE] API call completed in {api_call_duration:.2f}ms: fetched {len(tweets)} tweets")
                
                if tweets:
                    tweet_ids = [t.get('tweet_id') for t in tweets]
                    logger.info(f"[TWITTER TRACE] Tweet IDs fetched: {tweet_ids}")
                    # Record successful fetch only when we actually got tweets
                    logger.info("[TWITTER TRACE] Recording successful fetch attempt for rate limiting")
                    await self.rate_limit_service.record_fetch_attempt(success=True)
                else:
                    logger.info("[TWITTER TRACE] No tweets returned from API")
                    # Don't record as successful if no tweets - could be rate limited or API returned empty
                    logger.info("[TWITTER TRACE] No tweets received - not recording as successful fetch to avoid rate limit confusion")
                
                total_duration = (time.time() - start_time) * 1000
                logger.info(f"[TWITTER TRACE] fetch_today_tweets completed successfully in {total_duration:.2f}ms")
                return tweets
                
        except Exception as e:
            error_duration = (time.time() - start_time) * 1000
            logger.error(f"[TWITTER TRACE] Error in fetch_today_tweets after {error_duration:.2f}ms: {e}", exc_info=True)
            
            # Record failed fetch (doesn't count against rate limit)
            logger.info("[TWITTER TRACE] Recording failed fetch attempt for rate limiting")
            await self.rate_limit_service.record_fetch_attempt(success=False)
            return []

    async def get_data_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Get tweets for a specific date"""
        logger.info(f"[TWITTER TRACE] Getting data for date: {date}, namespace={self.namespace}")
        start_time = time.time()
        
        result = await self.db_service.async_get_data_items_by_date(date, [self.namespace])
        
        duration = (time.time() - start_time) * 1000
        logger.info(f"[TWITTER TRACE] Retrieved {len(result)} items for date {date} in {duration:.2f}ms")
        
        return result
    
    async def get_status_for_day(self, days_date: str) -> Optional[Dict[str, str]]:
        """Get Twitter fetch status for a specific day for UI display"""
        if not self.config.is_api_configured():
            return None
        return await self.rate_limit_service.get_status_for_day(days_date)

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch data items from the Twitter source"""
        start_time = time.time()
        logger.info(f"[TWITTER TRACE] TwitterSource.fetch_items starting at {datetime.now().isoformat()}")
        logger.info(f"[TWITTER TRACE] Parameters: since={since}, limit={limit}")
        
        api_items_yielded = 0
        db_items_yielded = 0
        
        # Check API configuration and decide on flow
        is_api_configured = self.config.is_api_configured()
        will_attempt_api_fetch = is_api_configured
        logger.info(f"[TWITTER TRACE] API configured: {is_api_configured}, will attempt API fetch: {will_attempt_api_fetch}")
        
        # First, try to fetch new tweets from API if configured and rate limits allow
        if will_attempt_api_fetch:
            try:
                api_phase_start = time.time()
                logger.info("[TWITTER TRACE] Starting API fetch phase...")
                
                api_tweets = await self.fetch_today_tweets()  # This now handles rate limiting internally
                api_fetch_duration = (time.time() - api_phase_start) * 1000
                logger.info(f"[TWITTER TRACE] API fetch phase completed in {api_fetch_duration:.2f}ms: received {len(api_tweets)} tweets")
                
                if api_tweets:
                    # Get existing tweet IDs to avoid duplicates
                    logger.info("[TWITTER TRACE] Getting existing tweet IDs to filter duplicates...")
                    existing_tweet_ids = await self._get_existing_tweet_ids()
                    
                    # Filter out existing tweets
                    new_tweets = [t for t in api_tweets if t['tweet_id'] not in existing_tweet_ids]
                    logger.info(f"[TWITTER TRACE] Filtered to {len(new_tweets)} new tweets for ingestion (from {len(api_tweets)} total)")
                    
                    if new_tweets:
                        logger.info(f"[TWITTER TRACE] Processing {len(new_tweets)} new tweets from API")
                        
                        # Transform tweets to DataItems and yield them (let IngestionService handle storage)
                        data_items = self._transform_tweets_to_items(new_tweets, 'twitter_api')
                        for data_item in data_items:
                            api_items_yielded += 1
                            logger.debug(f"[TWITTER TRACE] Yielding API tweet DataItem {api_items_yielded}: {data_item.source_id}")
                            yield data_item
                    else:
                        logger.info("[TWITTER TRACE] No new tweets to process from API")
                else:
                    logger.info("[TWITTER TRACE] No tweets returned from API fetch")
                    
            except Exception as e:
                api_error_duration = (time.time() - start_time) * 1000
                logger.error(f"[TWITTER TRACE] Error in API fetch phase after {api_error_duration:.2f}ms: {e}")
        else:
            logger.info("[TWITTER TRACE] Skipping API fetch phase - API not configured")
        
        # Then get existing Twitter data from the unified data_items table
        db_phase_start = time.time()
        logger.info(f"[TWITTER TRACE] Starting database fetch phase: namespace={self.namespace}, limit={limit}")
        
        items = await self.db_service.async_get_data_items_by_namespace(self.namespace, limit)
        db_fetch_duration = (time.time() - db_phase_start) * 1000
        logger.info(f"[TWITTER TRACE] Database fetch completed in {db_fetch_duration:.2f}ms: retrieved {len(items)} items")
        
        for item in items:
            # Filter by since if provided
            if since and item.get('created_at'):
                item_date = datetime.fromisoformat(item['created_at'])
                if item_date <= since:
                    logger.debug(f"[TWITTER TRACE] Skipping item {item['source_id']} - created_at {item_date} <= since {since}")
                    continue
            
            # Parse metadata if it's a string
            metadata = item.get('metadata', {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"[TWITTER TRACE] Failed to parse metadata for item {item['source_id']}")
                    metadata = {}
            
            db_items_yielded += 1
            logger.debug(f"[TWITTER TRACE] Yielding database DataItem {db_items_yielded}: {item['source_id']}")
            
            yield DataItem(
                namespace=item['namespace'],
                source_id=item['source_id'],
                content=item['content'],
                metadata=metadata,
                created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
                updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
            )
        
        total_duration = (time.time() - start_time) * 1000
        logger.info(f"[TWITTER TRACE] TwitterSource.fetch_items completed in {total_duration:.2f}ms: yielded {api_items_yielded} API items + {db_items_yielded} database items = {api_items_yielded + db_items_yielded} total")

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get specific tweet by ID"""
        logger.info(f"[TWITTER TRACE] Getting specific item: source_id={source_id}")
        start_time = time.time()
        
        namespaced_id = f"{self.namespace}:{source_id}"
        items = await self.db_service.async_get_data_items_by_ids([namespaced_id])
        
        duration = (time.time() - start_time) * 1000
        
        if not items:
            logger.info(f"[TWITTER TRACE] Item not found: {source_id} in {duration:.2f}ms")
            return None
        
        logger.info(f"[TWITTER TRACE] Item retrieved: {source_id} in {duration:.2f}ms")
        
        item = items[0]
        return DataItem(
            namespace=item['namespace'],
            source_id=item['source_id'],
            content=item['content'],
            metadata=item.get('metadata', {}),
            created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
            updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
        )

    def get_source_type(self) -> str:
        """Return the source type identifier"""
        return "twitter_archive"

    async def test_connection(self) -> bool:
        """Test if Twitter source is accessible"""
        logger.info("[TWITTER TRACE] Starting connection test")
        start_time = time.time()
        
        # Test basic configuration
        is_configured = self.config.is_configured()
        logger.info(f"[TWITTER TRACE] Basic configuration check: {is_configured}")
        
        if not is_configured:
            logger.info("[TWITTER TRACE] Connection test failed - not configured")
            return False
        
        # If API is configured, test the connection by attempting to fetch tweets
        is_api_configured = self.config.is_api_configured()
        logger.info(f"[TWITTER TRACE] API configuration check: {is_api_configured}")
        
        if is_api_configured:
            try:
                logger.info("[TWITTER TRACE] Testing API connection...")
                async with self.api_service:
                    # Test the connection using the actual production API call
                    await self.api_service.fetch_user_tweets_today()
                    
                    duration = (time.time() - start_time) * 1000
                    logger.info(f"[TWITTER TRACE] Twitter API connection test successful in {duration:.2f}ms using configured user_id: {self.config.user_id}")
                    return True
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"[TWITTER TRACE] Twitter API connection test failed after {duration:.2f}ms: {e}")
                return False
        
        # If only archive import is configured, return True
        duration = (time.time() - start_time) * 1000
        logger.info(f"[TWITTER TRACE] Connection test passed (archive-only mode) in {duration:.2f}ms")
        return True
