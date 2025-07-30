import json
import os
import re
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator

from config.models import TwitterConfig
from core.database import DatabaseService
from sources.base import BaseSource, DataItem
import logging

logger = logging.getLogger(__name__)

class TwitterSource(BaseSource):
    """Twitter data source"""

    def __init__(self, config: TwitterConfig, db_service: DatabaseService):
        super().__init__("twitter")
        self.config = config
        self.db_service = db_service

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch and parse Twitter data"""
        if not self.config.is_configured():
            logger.warning("Twitter data path not configured. Skipping fetch.")
            return []

        tweet_js_path = os.path.join(self.config.data_path, 'data', 'tweet.js')
        if not os.path.exists(tweet_js_path):
            logger.warning(f"tweet.js not found at {tweet_js_path}. Skipping fetch.")
            return []

        try:
            with open(tweet_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Remove JavaScript wrapper
                if 'window.YTD.tweet.part0 = [' in content:
                    content = content.split('window.YTD.tweet.part0 = [', 1)[1]
                    content = content.rsplit(']', 1)[0]

                tweets = json.loads(f'[{content}]')

            parsed_tweets = self._parse_tweets(tweets)
            await self._store_tweets(parsed_tweets)

            if self.config.delete_after_import:
                logger.info(f"Deleting Twitter data directory: {self.config.data_path}")
                shutil.rmtree(self.config.data_path)

            return parsed_tweets
        except Exception as e:
            logger.error(f"Error processing Twitter data: {e}")
            return []

    def _parse_tweets(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse raw tweet objects"""
        parsed_tweets = []
        for item in tweets:
            tweet = item.get('tweet', {})
            tweet_id = tweet.get('id_str')
            if not tweet_id:
                continue

            created_at_str = tweet.get('created_at')
            created_at = datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y')

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

    async def _store_tweets(self, tweets: List[Dict[str, Any]]):
        """Store parsed tweets in the database"""
        if not tweets:
            return

        with self.db_service.get_connection() as conn:
            cursor = conn.cursor()
            for tweet in tweets:
                cursor.execute("""
                    INSERT OR IGNORE INTO tweets (tweet_id, created_at, days_date, text, media_urls)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    tweet['tweet_id'],
                    tweet['created_at'],
                    tweet['days_date'],
                    tweet['text'],
                    tweet['media_urls']
                ))
            conn.commit()
            logger.info(f"Stored {len(tweets)} tweets in the database.")

    async def get_data_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Get tweets for a specific date"""
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT tweet_id, created_at, text, media_urls
                FROM tweets
                WHERE days_date = ?
                ORDER BY created_at DESC
            """, (date,))
            return [dict(row) for row in cursor.fetchall()]
    
    # Required abstract methods from BaseSource
    
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch data items from the Twitter source"""
        # This source works by importing data once, not streaming
        # Return empty iterator for now - actual data is accessed via get_data_for_date
        return
        yield  # Make this a generator function
    
    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get specific tweet by ID"""
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT tweet_id, created_at, text, media_urls, days_date
                FROM tweets 
                WHERE tweet_id = ?
            """, (source_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return DataItem(
                namespace=self.namespace,
                source_id=row['tweet_id'],
                content=row['text'],
                metadata={
                    'media_urls': row['media_urls'],
                    'days_date': row['days_date']
                },
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            )
    
    def get_source_type(self) -> str:
        """Return the source type identifier"""
        return "twitter_archive"
    
    async def test_connection(self) -> bool:
        """Test if Twitter data source is accessible"""
        if not self.config.is_configured():
            return False
        
        # Check if the data path exists
        if not os.path.exists(self.config.data_path):
            return False
        
        # Check if tweet.js exists
        tweet_js_path = os.path.join(self.config.data_path, 'data', 'tweet.js')
        return os.path.exists(tweet_js_path)