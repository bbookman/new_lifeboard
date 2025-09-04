import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import aiohttp

from config.models import TwitterConfig

logger = logging.getLogger(__name__)


class TwitterAPIError(Exception):
    """Base exception for Twitter API errors"""
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class TwitterAuthError(TwitterAPIError):
    """Twitter authentication/authorization error"""
    pass


class TwitterRateLimitError(TwitterAPIError):
    """Twitter rate limit exceeded error"""
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class TwitterNotFoundError(TwitterAPIError):
    """Twitter resource not found error"""
    pass


class TwitterPermissionError(TwitterAPIError):
    """Twitter permission/access denied error"""
    pass

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
                "User-Agent": "Lifeboard/1.0"
            }
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
        
        # Retry counter for server errors and network issues (not rate limits)
        other_error_attempts = 0
        
        while True:
            try:
                attempt_number = other_error_attempts + 1
                logger.info(f"[Twitter API] Making attempt {attempt_number}")
                
                async with self.session.get(url, params=params) as response:
                    response_data = await response.json()
                    
                    # Detailed logging of response
                    logger.info(f"[Twitter API Response] Status: {response.status}")
                    logger.info(f"[Twitter API Response] Data: {json.dumps(response_data, indent=2)}")
                    
                    # Log rate limit info if available
                    try:
                        rate_limit_remaining = response.headers.get('x-rate-limit-remaining')
                        rate_limit_reset = response.headers.get('x-rate-limit-reset')
                        if rate_limit_remaining:
                            logger.info(f"[Twitter API] Rate limit remaining: {rate_limit_remaining}")
                            logger.info(f"[Twitter API] Rate limit reset: {rate_limit_reset}")
                    except Exception as e:
                        logger.debug(f"[Twitter API] Could not log rate limit headers: {e}")
                    
                    if response.status == 200:
                        return response_data
                    elif response.status == 429:  # Rate limited
                        # With Twitter Basic plan (1 request per 15 minutes), retrying is pointless
                        # The TwitterRateLimitService should prevent calls when rate limited
                        retry_after = int(response.headers.get('retry-after', 900))  # Default to 15 minutes
                        error_msg = f"Rate limit exceeded. Twitter Basic plan allows 1 request per 15 minutes. Next request allowed in {retry_after} seconds."
                        logger.error(error_msg)
                        print(f"Twitter Rate Limit: {error_msg}")
                        raise TwitterRateLimitError(error_msg, retry_after=retry_after)
                    elif response.status == 401:
                        error_msg = "Authentication failed. Please check your Twitter bearer token is valid and has not expired."
                        error_details = response_data.get('detail', 'No additional details provided')
                        logger.error(f"{error_msg} Details: {error_details}")
                        print(f"Twitter Auth Error: {error_msg}")
                        raise TwitterAuthError(f"{error_msg} Details: {error_details}", status_code=401, response_data=response_data)
                    elif response.status == 403:
                        error_msg = "Access forbidden. This could be due to:"
                        possible_reasons = [
                            "• Invalid or insufficient API permissions",
                            "• Account suspended or restricted", 
                            "• API access level doesn't allow this operation",
                            "• Bearer token doesn't have required scopes",
                            "• Resource access restricted by privacy settings"
                        ]
                        full_error_msg = f"{error_msg}\n" + "\n".join(possible_reasons)
                        error_details = response_data.get('detail', response_data.get('errors', []))
                        logger.error(f"403 Forbidden: {full_error_msg}")
                        logger.error(f"Response details: {error_details}")
                        print(f"Twitter Permission Error: {error_msg}")
                        print("Check your API access level and token permissions")
                        raise TwitterPermissionError(full_error_msg, status_code=403, response_data=response_data)
                    elif response.status == 404:
                        if "/users/by/username/" in url:
                            resource_type = "user"
                            resource_id = self.config.username
                        elif "/users/" in url:
                            resource_type = "user"
                            resource_id = self.config.user_id
                        else:
                            resource_type = "resource"
                            resource_id = "unknown"
                        error_msg = f"Twitter {resource_type} '{resource_id}' not found. This could mean the account doesn't exist, is suspended, or is private."
                        logger.error(error_msg)
                        print(f"Twitter Not Found Error: {error_msg}")
                        raise TwitterNotFoundError(error_msg, status_code=404, response_data=response_data)
                    elif response.status in [500, 502, 503, 504]:
                        # Server errors - retryable
                        other_error_attempts += 1
                        if other_error_attempts >= self.config.other_error_max_retries:
                            error_msg = f"Twitter API server error ({response.status}). Max retries ({self.config.other_error_max_retries}) exceeded. Twitter may be experiencing issues."
                            logger.error(error_msg)
                            logger.error(f"Final response data: {response_data}")
                            raise TwitterAPIError(error_msg, status_code=response.status, response_data=response_data)
                        
                        logger.warning(f"Twitter API server error {response.status}: {response_data}. Retry {other_error_attempts}/{self.config.other_error_max_retries}")
                        print(f"Twitter server error {response.status}. Retrying {other_error_attempts}/{self.config.other_error_max_retries}")
                        await asyncio.sleep(self.config.retry_delay * (2 ** (other_error_attempts - 1)))  # Exponential backoff
                        continue
                    else:
                        # Other HTTP errors - not retryable
                        error_msg = f"Twitter API error {response.status}: {response_data.get('detail', 'Unknown error')}"
                        logger.error(f"Non-retryable Twitter API error: {error_msg}")
                        logger.error(f"Response data: {response_data}")
                        print(f"Twitter API Error {response.status}: Check logs for details")
                        raise TwitterAPIError(error_msg, status_code=response.status, response_data=response_data)
                        
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
        """
        LEGACY: Get user ID for a given username
        
        This method is deprecated in favor of configuring user_id directly 
        via TWITTER_USER_ID environment variable. New code should use
        self.config.user_id instead of calling this method.
        
        Kept for backwards compatibility and testing purposes.
        """
        url = f"{self.base_url}/users/by/username/{username}"
        logger.info(f"Fetching user ID for username: {username}")
        logger.info(f"Request URL: {url}")
        logger.info(f"Headers: {self.session.headers if self.session else 'No session'}")
        
        try:
            response_data = await self._make_request(url)
            logger.info(f"Response data: {response_data}")
            
            if 'data' not in response_data:
                logger.error(f"User data not found in response: {response_data}")
                raise TwitterNotFoundError(f"User data not found for username: {username}", response_data=response_data)
                
            user_id = response_data['data']['id']
            logger.info(f"Found user ID {user_id} for username {username}")
            return user_id
            
        except (TwitterAuthError, TwitterPermissionError, TwitterNotFoundError) as e:
            # Re-raise Twitter-specific errors with context
            logger.error(f"Twitter API error in get_user_id for username '{username}': {str(e)}")
            raise
        except TwitterRateLimitError as e:
            logger.error(f"Rate limit error in get_user_id for username '{username}': {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_user_id for username '{username}': {str(e)}", exc_info=True)
            raise TwitterAPIError(f"Failed to get user ID for '{username}': {str(e)}")
    
    async def get_todays_tweets(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tweets from 5 days prior to today until now for a user"""
        from datetime import timedelta
        user_id = user_id or self.config.user_id
        if not user_id or not str(user_id).strip():
            logger.error("[Twitter] user_id is not configured. Please run tools/get_twitter_user_id.sh to obtain your user ID and set TWITTER_USER_ID in your .env file.")
            return []
        # Get UTC timestamps
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(days=5)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now

        url = f"{self.base_url}/users/{user_id}/tweets"
        params = {
            'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z',
            'end_time': end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z',
            'exclude': 'retweets,replies',
            'tweet.fields': 'created_at,text,public_metrics,geo',
            'place.fields': 'id,full_name,name,country,country_code,place_type,geo',
            'max_results': 100  # Maximum allowed by API
        }

        logger.info(f"Fetching tweets for user {user_id} from {start_time} to {end_time}")
        print(f"[get_todays_tweets] Fetching tweets for user {user_id} from {start_time} to {end_time}")
        print(f"[get_todays_tweets] Params: {params}")
        response_data = await self._make_request(url, params)
        print(f"[get_todays_tweets] Response data: {response_data}")

        tweets = response_data.get('data', [])
        includes = response_data.get('includes', {})
        places = {place['id']: place for place in includes.get('places', [])}
        
        logger.info(f"Retrieved {len(tweets)} tweets in the last 5 days")
        logger.info(f"Retrieved {len(places)} places in includes")
        print(f"[get_todays_tweets] Retrieved {len(tweets)} tweets in the last 5 days")
        print(f"[get_todays_tweets] Retrieved {len(places)} places in includes")

        # Add place data to tweets
        for tweet in tweets:
            if tweet.get('geo') and tweet['geo'].get('place_id'):
                place_id = tweet['geo']['place_id']
                if place_id in places:
                    tweet['place'] = places[place_id]

        return tweets
    
    async def fetch_user_tweets_today(self) -> List[Dict[str, Any]]:
        """Fetch today's tweets for the configured user"""
        logger.info("[Twitter] Starting fetch_user_tweets_today")
        
        if not self.config.is_api_configured():
            logger.error("[Twitter] API Configuration validation failed:")
            logger.error(f"[Twitter] Bearer token present: {bool(self.config.bearer_token)}")
            logger.error(f"[Twitter] Bearer token format valid: {len(self.config.bearer_token or '') > 0}")
            logger.error(f"[Twitter] User ID present: {bool(self.config.user_id)}")
            logger.error(f"[Twitter] User ID: {self.config.user_id}")
            logger.error(f"[Twitter] API configured check result: {self.config.is_api_configured()}")
            return []
        
        logger.info("[Twitter] Configuration validated successfully")
        logger.info(f"[Twitter] Will fetch tweets for user_id: {self.config.user_id}")
        try:
            tweets = await self.get_todays_tweets()
            print(f"[fetch_user_tweets_today] Got {len(tweets)} tweets")
            # Transform tweets to match expected format
            transformed_tweets = []
            logger.info(f"[Twitter] Processing {len(tweets)} tweets")

            for tweet in tweets:
                try:
                    created_at = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                    transformed_tweet = {
                        'tweet_id': tweet['id'],
                        'created_at': created_at.isoformat(),
                        'days_date': created_at.strftime('%Y-%m-%d'),
                        'text': tweet['text'],
                        'media_urls': '[]',  # No media support in this implementation
                        'public_metrics': tweet.get('public_metrics', {}),
                        'geo': tweet.get('geo'),
                        'place_id': tweet.get('geo', {}).get('place_id') if tweet.get('geo') else None,
                        'place': tweet.get('place'),
                    }
                    logger.info(f"[Twitter] Processed tweet {tweet['id']}:")
                    logger.info(f"[Twitter] Created at: {transformed_tweet['created_at']}")
                    logger.info(f"[Twitter] Text: {transformed_tweet['text'][:100]}...")
                    logger.info(f"[Twitter] Metrics: {transformed_tweet['public_metrics']}")
                    if transformed_tweet.get('place'):
                        logger.info(f"[Twitter] Place: {transformed_tweet['place'].get('full_name', 'Unknown')}")
                    transformed_tweets.append(transformed_tweet)
                except Exception as e:
                    logger.error(f"[Twitter] Error transforming tweet {tweet.get('id', 'unknown')}:")
                    logger.error(f"[Twitter] Raw tweet data: {json.dumps(tweet, indent=2)}")
                    logger.error(f"[Twitter] Error: {str(e)}")
                    continue
            
            logger.info(f"[Twitter] Successfully transformed {len(transformed_tweets)} tweets")
            return transformed_tweets
            
        except TwitterAuthError as e:
            logger.error(f"[Twitter] Authentication error: {e}")
            print(f"[Twitter] Authentication failed - check your bearer token configuration")
            print(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except TwitterPermissionError as e:
            logger.error(f"[Twitter] Permission error: {e}")
            print(f"[Twitter] Access denied - check API permissions and account status")
            print(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except TwitterNotFoundError as e:
            logger.error(f"[Twitter] Resource not found: {e}")
            print(f"[Twitter] User '{self.config.username}' not found or inaccessible")
            print(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except TwitterRateLimitError as e:
            logger.error(f"[Twitter] Rate limit exceeded: {e}")
            print(f"[Twitter] Rate limit exceeded - will retry later")
            print(f"[Twitter] Next retry in {getattr(e, 'retry_after', 'unknown')} seconds")
            return []
            
        except TwitterAPIError as e:
            logger.error(f"[Twitter] API error: {e}")
            print(f"[Twitter] API error ({getattr(e, 'status_code', 'unknown')}): Check logs for details")
            print(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except Exception as e:
            logger.error(f"[Twitter] Unexpected error fetching user tweets: {e}", exc_info=True)
            print(f"[Twitter] Unexpected error: {type(e).__name__}: {e}")
            print(f"[Twitter] Skipping Twitter data collection")
            return []
    
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