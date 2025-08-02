import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator

from config.models import TwitterConfig
from core.database import DatabaseService
from sources.base import BaseSource, DataItem
from sources.twitter_processor import TwitterProcessor
import logging

logger = logging.getLogger(__name__)

class TwitterSource(BaseSource):
    """Twitter data source"""

    def __init__(self, config: TwitterConfig, db_service: DatabaseService, ingestion_service=None):
        super().__init__("twitter")
        self.config = config
        self.db_service = db_service
        self.ingestion_service = ingestion_service
        self.processor = TwitterProcessor()

    async def import_from_zip(self, zip_path: str) -> Dict[str, Any]:
        """Import Twitter data from a zip archive, only adding new tweets."""
        if not self.config.is_configured():
            logger.warning("Twitter source not enabled. Skipping import.")
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
            logger.info(f"Starting Twitter import from zip: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                logger.info(f"Extracted zip to: {temp_dir}")

            # PERMANENT FIX: Robust file discovery that prioritizes tweets.js and never looks for tweet.js
            tweets_js_path = None
            possible_filenames = ['tweets.js']  # Correct filename only - NEVER look for tweet.js
            
            for root, _, files in os.walk(temp_dir):
                logger.info(f"DEBUG: Files found in {root}: {files}")
                for filename in possible_filenames:
                    if filename in files:
                        tweets_js_path = os.path.join(root, filename)
                        logger.info(f"Found Twitter data file: {filename} at: {tweets_js_path}")
                        break
                if tweets_js_path:
                    break
            
            if not tweets_js_path:
                logger.error(f"tweets.js not found in the extracted archive at {temp_dir}")
                logger.error(f"Searched for files: {possible_filenames}")
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
            logger.info(f"Parsed {len(parsed_tweets)} total tweets from the archive.")

            # Get existing tweets from data_items table
            existing_tweet_ids = await self._get_existing_tweet_ids()
            logger.info(f"Found {len(existing_tweet_ids)} existing tweets in database.")

            # Filter out existing tweets
            new_tweets = [t for t in parsed_tweets if t['tweet_id'] not in existing_tweet_ids]
            logger.info(f"Found {len(new_tweets)} new tweets to import.")

            if not new_tweets:
                logger.info("No new tweets to import. Skipping database storage.")
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "Twitter archive processed. No new tweets found to import."
                }

            await self._ingest_tweets(new_tweets)
            return {
                "success": True,
                "imported_count": len(new_tweets),
                "message": f"Successfully imported {len(new_tweets)} new tweets."
            }
        except Exception as e:
            logger.error(f"Error processing Twitter zip import: {e}", exc_info=True)
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
                created_at = datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y')
            except (ValueError, TypeError):
                logger.warning(f"Could not parse date for tweet {tweet_id}, skipping.")
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
        existing_tweets = self.db_service.get_data_items_by_namespace(self.namespace, limit=10000)
        return {item['source_id'] for item in existing_tweets}

    async def _ingest_tweets(self, tweets: List[Dict[str, Any]]):
        """Ingest tweets through the ingestion service"""
        if not tweets or not self.ingestion_service:
            logger.warning("Cannot ingest tweets: missing tweets or ingestion service")
            return

        # Convert tweet dicts to DataItem objects
        data_items = []
        for tweet in tweets:
            try:
                # Parse timestamp
                created_at = None
                if tweet.get('created_at'):
                    created_at = datetime.fromisoformat(tweet['created_at'])

                # Create DataItem
                data_item = DataItem(
                    namespace=self.namespace,
                    source_id=tweet['tweet_id'],
                    content=tweet['text'] or "",
                    metadata={
                        'media_urls': tweet.get('media_urls', '[]'),
                        'original_created_at': tweet.get('created_at'),
                        'days_date': tweet.get('days_date'),
                        'source_type': 'twitter_archive'
                    },
                    created_at=created_at,
                    updated_at=datetime.now()
                )

                # Process the item
                processed_item = self.processor.process(data_item)
                data_items.append(processed_item)

            except Exception as e:
                logger.error(f"Error creating DataItem for tweet {tweet.get('tweet_id', 'unknown')}: {e}")
                continue

        # Ingest through the ingestion service
        logger.info(f"Ingesting {len(data_items)} tweets through ingestion service")
        
        # Process items in batches
        result = await self.ingestion_service.ingest_items("twitter", data_items)
        
        if result.errors:
            logger.warning(f"Some tweets failed to ingest: {result.errors}")
        
        logger.info(f"Ingestion complete: {result.items_stored} stored, {len(result.errors)} errors")

        logger.info(f"Successfully ingested {len(data_items)} tweets")

    async def get_data_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Get tweets for a specific date"""
        return self.db_service.get_data_items_by_date(date, [self.namespace])

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch data items from the Twitter source"""
        # Get Twitter data from the unified data_items table
        items = self.db_service.get_data_items_by_namespace(self.namespace, limit)
        
        for item in items:
            # Filter by since if provided
            if since and item.get('created_at'):
                item_date = datetime.fromisoformat(item['created_at'])
                if item_date <= since:
                    continue
            
            # Parse metadata if it's a string
            metadata = item.get('metadata', {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            
            yield DataItem(
                namespace=item['namespace'],
                source_id=item['source_id'],
                content=item['content'],
                metadata=metadata,
                created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
                updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
            )

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get specific tweet by ID"""
        namespaced_id = f"{self.namespace}:{source_id}"
        items = self.db_service.get_data_items_by_ids([namespaced_id])
        
        if not items:
            return None
        
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
        return self.config.is_configured()