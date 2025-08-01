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
import logging

logger = logging.getLogger(__name__)

class TwitterSource(BaseSource):
    """Twitter data source"""

    def __init__(self, config: TwitterConfig, db_service: DatabaseService):
        super().__init__("twitter")
        self.config = config
        self.db_service = db_service

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

            tweet_js_path = None
            for root, _, files in os.walk(temp_dir):
                if 'tweet.js' in files:
                    tweet_js_path = os.path.join(root, 'tweet.js')
                    logger.info(f"Found tweet.js at: {tweet_js_path}")
                    break
            
            if not tweet_js_path:
                logger.error(f"tweet.js not found in the extracted archive at {temp_dir}")
                return {
                    "success": False, 
                    "imported_count": 0, 
                    "message": "Could not find tweet.js in the archive."
                }

            with open(tweet_js_path, 'r', encoding='utf-8') as f:
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

            latest_date_in_db = self.db_service.get_latest_tweet_date()
            logger.info(f"Latest tweet date in database: {latest_date_in_db}")

            if latest_date_in_db:
                new_tweets = [p for p in parsed_tweets if p['days_date'] > latest_date_in_db]
                logger.info(f"Found {len(new_tweets)} new tweets to import.")
            else:
                new_tweets = parsed_tweets
                logger.info("No existing tweets found. Importing all parsed tweets.")

            if not new_tweets:
                logger.info("No new tweets to import. Skipping database storage.")
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "Twitter archive processed. No new tweets found to import."
                }

            await self._store_tweets(new_tweets)
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
            tweet_id = tweet.get('id_str')
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

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch data items from the Twitter source"""
        return
        yield

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
        """Test if Twitter source is accessible"""
        return self.config.is_configured()