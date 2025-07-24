import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator

from sources.base import BaseSource, DataItem

def _parse_twitter_export(data_path: str) -> List[Dict[str, Any]]:
    """
    Parses a Twitter export directory to extract tweet information.
    """
    tweets_file = os.path.join(data_path, 'data', 'tweet.js')
    if not os.path.exists(tweets_file):
        return []

    with open(tweets_file, 'r') as f:
        content = f.read()
        json_content = content.split('=', 1)[1].strip()
        tweets_data = json.loads(json_content)

    parsed_tweets = []
    for tweet_data in tweets_data:
        tweet = tweet_data.get('tweet', {})
        media_urls = []
        if 'entities' in tweet and 'media' in tweet['entities']:
            for media_item in tweet['entities']['media']:
                media_urls.append(media_item.get('media_url_https'))

        parsed_tweets.append({
            'tweet_id': tweet.get('id'),
            'created_at': tweet.get('created_at'),
            'text': tweet.get('full_text'),
            'media_urls': media_urls
        })

    return parsed_tweets

class TwitterSource(BaseSource):
    """
    Data source for Twitter exports.
    """
    def __init__(self, namespace: str, data_path: str):
        super().__init__(namespace)
        self.data_path = data_path

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch data items from the Twitter export."""
        tweets = _parse_twitter_export(self.data_path)

        for tweet in tweets:
            created_at = datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S %z %Y')
            if since and created_at < since:
                continue

            yield DataItem(
                namespace=self.namespace,
                source_id=tweet['tweet_id'],
                content=tweet['text'],
                metadata={
                    'created_at': tweet['created_at'],
                    'media_urls': tweet['media_urls']
                },
                created_at=created_at
            )

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get a specific item by source ID."""
        # This is not easily implemented for a file-based export,
        # so we'll leave it as not implemented for now.
        return None

    def get_source_type(self) -> str:
        """Return the source type identifier."""
        return "twitter"

    async def test_connection(self) -> bool:
        """Test if the source is accessible."""
        return os.path.exists(os.path.join(self.data_path, 'data', 'tweet.js'))
