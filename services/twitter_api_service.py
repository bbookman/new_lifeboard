import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.models import TwitterConfig

logger = logging.getLogger(__name__)

class TwitterAPIService:
    """Service for interacting with Twitter API v2"""

    def __init__(self, config: TwitterConfig):
        self.config = config
        self.base_url = "https://api.twitter.com/2"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout),
            headers={
                "Authorization": f"Bearer {self.config.bearer_token}",
                "User-Agent": "Lifeboard/1.0",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an authenticated request to Twitter API with separate retry logic for rate limits and other errors"""
        if not self.session:
            raise RuntimeError("TwitterAPIService must be used as async context manager")

        # Log request details
        logger.info(f"[Twitter API Request] URL: {url}")
        logger.info(f"[Twitter API Request] Parameters: {json.dumps(params, indent=2) if params else 'None'}")
        logger.info(f"[Twitter API Request] Headers: {json.dumps(dict(self.session.headers), indent=2)}")

        # Separate retry counters for different error types
        rate_limit_attempts = 0
        other_error_attempts = 0

        while True:
            try:
                total_attempts = rate_limit_attempts + other_error_attempts + 1
                logger.info(f"[Twitter API] Making attempt {total_attempts} (rate limit: {rate_limit_attempts}, other: {other_error_attempts})")

                async with self.session.get(url, params=params) as response:
                    response_data = await response.json()

                    # Detailed logging of response
                    logger.info(f"[Twitter API Response] Status: {response.status}")
                    logger.info(f"[Twitter API Response] Headers: {json.dumps(dict(response.headers), indent=2)}")
                    logger.info(f"[Twitter API Response] Data: {json.dumps(response_data, indent=2)}")

                    # Log rate limit info if available
                    rate_limit_remaining = response.headers.get("x-rate-limit-remaining")
                    rate_limit_reset = response.headers.get("x-rate-limit-reset")
                    if rate_limit_remaining:
                        logger.info(f"[Twitter API] Rate limit remaining: {rate_limit_remaining}")
                        logger.info(f"[Twitter API] Rate limit reset: {rate_limit_reset}")

                    if response.status == 200:
                        return response_data
                    if response.status == 429:  # Rate limited
                        rate_limit_attempts += 1
                        if rate_limit_attempts >= self.config.rate_limit_max_retries:
                            logger.error(f"Rate limit max retries ({self.config.rate_limit_max_retries}) exceeded")
                            raise Exception(f"Rate limit max retries ({self.config.rate_limit_max_retries}) exceeded")

                        retry_after = int(response.headers.get("retry-after", 60))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds before retry {rate_limit_attempts}/{self.config.rate_limit_max_retries}")
                        print(f"Rate limited. Waiting {retry_after} seconds before retry {rate_limit_attempts}/{self.config.rate_limit_max_retries}")
                        await asyncio.sleep(retry_after)
                        continue
                    if response.status == 401:
                        logger.error("Unauthorized: Check your Twitter bearer token")
                        print("Unauthorized: Check your Twitter bearer token")
                        raise ValueError("Unauthorized: Check your Twitter bearer token")
                    if response.status == 404:
                        logger.error(f"User '{self.config.username}' not found")
                        print(f"User '{self.config.username}' not found")
                        raise ValueError(f"User '{self.config.username}' not found")
                    # Other HTTP errors (500, 502, etc.)
                    other_error_attempts += 1
                    if other_error_attempts >= self.config.other_error_max_retries:
                        logger.error(f"Other error max retries ({self.config.other_error_max_retries}) exceeded")
                        raise Exception(f"Twitter API error {response.status}: {response_data}")

                    logger.warning(f"Twitter API error {response.status}: {response_data}. Retry {other_error_attempts}/{self.config.other_error_max_retries}")
                    print(f"Twitter API error {response.status}. Retry {other_error_attempts}/{self.config.other_error_max_retries}")
                    await asyncio.sleep(self.config.retry_delay * (2 ** (other_error_attempts - 1)))  # Exponential backoff
                    continue

            except aiohttp.ClientError as e:
                # Network errors
                other_error_attempts += 1
                if other_error_attempts >= self.config.other_error_max_retries:
                    logger.error(f"Network error max retries ({self.config.other_error_max_retries}) exceeded")
                    raise

                logger.warning(f"Network error on attempt {other_error_attempts}/{self.config.other_error_max_retries}: {e}")
                print(f"Network error on attempt {other_error_attempts}/{self.config.other_error_max_retries}: {e}")
                await asyncio.sleep(self.config.retry_delay * (2 ** (other_error_attempts - 1)))  # Exponential backoff

    async def get_user_id(self, username: str) -> str:
        """Get user ID for a given username"""
        url = f"{self.base_url}/users/by/username/{username}"
        logger.info(f"Fetching user ID for username: {username}")
        logger.info(f"Request URL: {url}")
        logger.info(f"Headers: {self.session.headers if self.session else 'No session'}")

        try:
            response_data = await self._make_request(url)
            logger.info(f"Response data: {response_data}")

            if "data" not in response_data:
                logger.error(f"User data not found in response: {response_data}")
                raise ValueError(f"User data not found for username: {username}")

            user_id = response_data["data"]["id"]
            logger.info(f"Found user ID {user_id} for username {username}")
            return user_id

        except Exception as e:
            logger.error(f"Error in get_user_id: {e!s}", exc_info=True)
            raise

    async def get_todays_tweets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get tweets from 5 days prior to today until now for a user"""
        from datetime import timedelta
        # Get UTC timestamps
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(days=5)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now

        url = f"{self.base_url}/users/{user_id}/tweets"
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,text,public_metrics,context_annotations",
            "max_results": 100,  # Maximum allowed by API
        }

        logger.info(f"Fetching tweets for user {user_id} from {start_time} to {end_time}")
        print(f"[get_todays_tweets] Fetching tweets for user {user_id} from {start_time} to {end_time}")
        print(f"[get_todays_tweets] Params: {params}")
        response_data = await self._make_request(url, params)
        print(f"[get_todays_tweets] Response data: {response_data}")

        tweets = response_data.get("data", [])
        logger.info(f"Retrieved {len(tweets)} tweets in the last 5 days")
        print(f"[get_todays_tweets] Retrieved {len(tweets)} tweets in the last 5 days")

        return tweets

    async def fetch_user_tweets_today(self) -> List[Dict[str, Any]]:
        """Fetch today's tweets for the configured user"""
        logger.info("[Twitter] Starting fetch_user_tweets_today")

        if not self.config.is_api_configured():
            logger.error("[Twitter] API Configuration validation failed:")
            logger.error(f"[Twitter] Bearer token present: {bool(self.config.bearer_token)}")
            logger.error(f"[Twitter] Bearer token format valid: {len(self.config.bearer_token or '') > 0}")
            logger.error(f"[Twitter] Username present: {bool(self.config.username)}")
            logger.error(f"[Twitter] Username: {self.config.username}")
            logger.error(f"[Twitter] API configured check result: {self.config.is_api_configured()}")
            return []

        logger.info("[Twitter] Configuration validated successfully")
        logger.info(f"[Twitter] Will fetch tweets for user: {self.config.username}")
        try:
            print(f"[fetch_user_tweets_today] Getting user ID for {self.config.username}")
            # Get user ID
            user_id = await self.get_user_id(self.config.username)
            print(f"[fetch_user_tweets_today] Got user ID: {user_id}")

            # Add inter-call delay to prevent rate limiting
            if self.config.inter_call_delay > 0:
                logger.info(f"[Twitter] Adding {self.config.inter_call_delay}s delay between API calls")
                print(f"[fetch_user_tweets_today] Waiting {self.config.inter_call_delay}s between API calls...")
                await asyncio.sleep(self.config.inter_call_delay)

            # Get today's tweets
            tweets = await self.get_todays_tweets(user_id)
            print(f"[fetch_user_tweets_today] Got {len(tweets)} tweets")
            # Transform tweets to match expected format
            transformed_tweets = []
            logger.info(f"[Twitter] Processing {len(tweets)} tweets")

            for tweet in tweets:
                try:
                    created_at = datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
                    transformed_tweet = {
                        "tweet_id": tweet["id"],
                        "created_at": created_at.isoformat(),
                        "days_date": created_at.strftime("%Y-%m-%d"),
                        "text": tweet["text"],
                        "media_urls": "[]",  # No media support in this implementation
                        "public_metrics": tweet.get("public_metrics", {}),
                        "context_annotations": tweet.get("context_annotations", []),
                    }
                    logger.info(f"[Twitter] Processed tweet {tweet['id']}:")
                    logger.info(f"[Twitter] Created at: {transformed_tweet['created_at']}")
                    logger.info(f"[Twitter] Text: {transformed_tweet['text'][:100]}...")
                    logger.info(f"[Twitter] Metrics: {transformed_tweet['public_metrics']}")
                    transformed_tweets.append(transformed_tweet)
                except Exception as e:
                    logger.error(f"[Twitter] Error transforming tweet {tweet.get('id', 'unknown')}:")
                    logger.error(f"[Twitter] Raw tweet data: {json.dumps(tweet, indent=2)}")
                    logger.error(f"[Twitter] Error: {e!s}")
                    continue

            logger.info(f"[Twitter] Successfully transformed {len(transformed_tweets)} tweets")
            return transformed_tweets
        except Exception as e:
            logger.error(f"Error fetching user tweets: {e}")
            print(f"[fetch_user_tweets_today] Error: {e}")
            raise

    def is_configured(self) -> bool:
        """Check if the service is properly configured"""
        logger.info("Checking if Twitter API is configured...")
        logger.info(f"Bearer token present: {bool(self.config.bearer_token)}")
        logger.info(f"Bearer token: {self.config.bearer_token!r}")
        logger.info(f"Username present: {bool(self.config.username)}")
        logger.info(f"Username: {self.config.username!r}")
        result = self.config.is_api_configured()
        logger.info(f"is_api_configured() result: {result}")
        return result
