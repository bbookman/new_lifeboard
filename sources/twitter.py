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

    async def import_from_zip(self, zip_path: str) -> bool:
        """Import Twitter data from a zip archive."""
        if not self.config.is_configured():
            logger.warning("Twitter source not enabled. Skipping import.")
            return False

        temp_dir = "twitter_data"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Created temporary directory for Twitter data import {temp_dir}")
        os.makedirs(temp_dir)

        try:
            logger.info(f"Starting Twitter import from zip: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                logger.info(f"Extracted zip to: {temp_dir}")
                
                # List extracted files for debugging
                extracted_files = []
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        extracted_files.append(os.path.relpath(os.path.join(root, file), temp_dir))
                #logger.info(f"Extracted files: {extracted_files}")

            # Find the tweets.js file - it might be in a subdirectory like 'twitter-x/data/tweets.js'
            tweet_js_path = None
            for root, dirs, files in os.walk(temp_dir):
                if 'tweets.js' in files:
                    tweet_js_path = os.path.join(root, 'tweets.js')
                    logger.info(f"Found tweets.js at: {tweet_js_path}")
                    break
            
            if not tweet_js_path or not os.path.exists(tweet_js_path):
                logger.error(f"tweets.js not found in the extracted archive")
                logger.error(f"Searched all directories in: {temp_dir}")
                return False

            with open(tweet_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"Read tweet.js file, size: {len(content)} characters")
                #logger.info(f"First 200 characters: {content[:200]}")
                
                if 'window.YTD.tweets.part0 = [' in content:
                    logger.info("Found expected Twitter export format (tweets.part0)")
                    content = content.split('window.YTD.tweets.part0 = [', 1)[1]
                    content = content.rsplit(']', 1)[0]
                elif 'window.YTD.tweet.part0 = [' in content:
                    logger.info("Found expected Twitter export format (tweet.part0)")
                    content = content.split('window.YTD.tweet.part0 = [', 1)[1]
                    content = content.rsplit(']', 1)[0]
                else:
                    logger.warning("Expected Twitter export format not found, trying to parse as JSON array directly")

                tweets = json.loads(f'[{content}]')
                logger.info(f"Successfully parsed {len(tweets)} tweets from tweet.js")



            parsed_tweets = self._parse_tweets(tweets)
            logger.info(f"Parsed {len(parsed_tweets)} tweets for storage")
            
            await self._store_tweets(parsed_tweets)
            logger.info(f"Successfully imported {len(parsed_tweets)} tweets to database")
            return True
        except Exception as e:
            logger.error(f"Error processing Twitter zip import: {e}")
            logger.exception("Full traceback for Twitter import error:")
            return False
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Removed temporary directory {temp_dir}")
            if os.path.exists(zip_path):
                os.remove(zip_path)


    def _parse_tweets(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse raw tweet objects"""
        parsed_tweets = []
        for i, item in enumerate(tweets):
            if not isinstance(item, dict):
                logger.warning(f"Tweet item {i} is not a dictionary, skipping")
                continue
                
            tweet = item.get('tweet', {})
            if not isinstance(tweet, dict):
                logger.warning(f"Tweet item {i} does not contain a valid tweet object, skipping")
                continue
                
            tweet_id = tweet.get('id_str')
            if not tweet_id:
                logger.warning(f"Tweet item {i} missing id_str field, skipping")
                continue

            created_at_str = tweet.get('created_at')
            if not created_at_str:
                logger.warning(f"Tweet {tweet_id} missing created_at field, skipping")
                continue
                
            try:
                created_at = datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y')
                logger.debug(f"Parsed tweet {tweet_id} date: {created_at}")
            except ValueError as e:
                logger.error(f"Failed to parse date '{created_at_str}' for tweet {tweet_id}: {e}")
                continue

            media_urls = []
            if 'media' in tweet.get('entities', {}):
                for media in tweet['entities']['media']:
                    media_urls.append(media.get('media_url_https'))
                    logger.debug(f"Found media {media_urls}")


            parsed_tweets.append({
                'tweet_id': tweet_id,
                'created_at': created_at.isoformat(),
                'days_date': created_at.strftime('%Y-%m-%d'),
                'text': tweet.get('full_text'),
                'media_urls': json.dumps(media_urls)
            })
            #logger.debug(f"Parsed tweet {parsed_tweets}")

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
                #logger.debug(f"Inserted tweet {tweet}")
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
