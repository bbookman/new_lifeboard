import asyncio
import json
import logging
import time
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
    
    def _parse_tweet(self, tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a tweet dict and return None for unusable entries"""
        try:
            # Check required fields
            tweet_id = tweet.get('id')
            if not tweet_id:
                logger.debug("[TWITTER TRACE] Tweet missing 'id' field")
                return None
                
            text = tweet.get('text')
            if not text:
                logger.debug(f"[TWITTER TRACE] Tweet {tweet_id} missing 'text' field")
                return None
                
            created_at_str = tweet.get('created_at')
            if not created_at_str:
                logger.debug(f"[TWITTER TRACE] Tweet {tweet_id} missing 'created_at' field")
                return None
                
            # Parse timestamp with fallback handling
            try:
                if created_at_str.endswith('Z'):
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    created_at = datetime.fromisoformat(created_at_str)
            except (ValueError, TypeError) as e:
                logger.debug(f"[TWITTER TRACE] Tweet {tweet_id} has invalid timestamp '{created_at_str}': {e}")
                return None
                
            return {
                'tweet_id': tweet_id,
                'created_at': created_at.isoformat(),
                'days_date': created_at.strftime('%Y-%m-%d'),
                'text': text,
                'media_urls': '[]',  # No media support in this implementation
                'public_metrics': tweet.get('public_metrics', {}),
                'geo': tweet.get('geo'),
                'place_id': tweet.get('geo', {}).get('place_id') if tweet.get('geo') else None,
                'place': tweet.get('place'),
            }
            
        except Exception as e:
            logger.debug(f"[TWITTER TRACE] Error parsing tweet {tweet.get('id', 'unknown')}: {e}")
            return None
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an authenticated request to Twitter API with separate retry logic for rate limits and other errors"""
        if not self.session:
            raise RuntimeError("TwitterAPIService must be used as async context manager")
        
        # Start timing and log request start
        request_start_time = time.time()
        start_timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"[TWITTER TRACE] API Request starting at {start_timestamp}")
        
        # Log complete request details with sanitized headers
        sanitized_headers = dict(self.session.headers)
        if 'Authorization' in sanitized_headers:
            bearer_token = sanitized_headers['Authorization']
            if bearer_token.startswith('Bearer '):
                token_part = bearer_token[7:]  # Remove 'Bearer ' prefix
                if len(token_part) > 8:
                    # Show only first 4 characters, mask the rest
                    sanitized_headers['Authorization'] = f"Bearer {token_part[:4]}{'*' * (len(token_part) - 4)}"
                else:
                    # For short tokens, mask everything after first 2 chars
                    sanitized_headers['Authorization'] = f"Bearer {token_part[:2]}{'*' * max(0, len(token_part) - 2)}"
            else:
                # Non-bearer authorization, mask completely
                sanitized_headers['Authorization'] = "***MASKED***"
        
        logger.info(f"[TWITTER TRACE] Request URL: {url}")
        if self.config.diagnostic_mode:
            logger.info(f"[TWITTER TRACE] Request parameters: {json.dumps(params, indent=2) if params else 'None'}")
            logger.info(f"[TWITTER TRACE] Request headers (sanitized): {json.dumps(sanitized_headers, indent=2)}")
        else:
            logger.info(f"[TWITTER TRACE] Request parameters: {'Present' if params else 'None'}")
            logger.info(f"[TWITTER TRACE] Request headers: Configured")
        
        # Retry counter for server errors and network issues (not rate limits)
        other_error_attempts = 0
        
        while True:
            try:
                attempt_number = other_error_attempts + 1
                attempt_start_time = time.time()
                logger.info(f"[TWITTER TRACE] Making attempt {attempt_number}")
                
                async with self.session.get(url, params=params) as response:
                    try:
                        response_data = await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as json_error:
                        # Fallback to text if JSON parsing fails
                        response_text = await response.text()
                        logger.error(f"[TWITTER TRACE] Failed to parse JSON response: {json_error}")
                        logger.error(f"[TWITTER TRACE] Response text: {response_text[:1000]}...")  # Truncate for logging
                        raise TwitterAPIError(
                            f"Invalid JSON response from Twitter API (Status: {response.status}). Response: {response_text[:200]}...", 
                            status_code=response.status, 
                            response_data={'raw_text': response_text}
                        )
                    
                    # Calculate request duration
                    request_duration = (time.time() - request_start_time) * 1000  # Convert to milliseconds
                    
                    # Log response details (conditional on diagnostic mode)
                    logger.info(f"[TWITTER TRACE] Response status: {response.status}")
                    logger.info(f"[TWITTER TRACE] Request duration: {request_duration:.2f}ms")
                    if self.config.diagnostic_mode:
                        logger.info(f"[TWITTER TRACE] Response headers: {json.dumps(dict(response.headers), indent=2)}")
                        logger.info(f"[TWITTER TRACE] Response body: {json.dumps(response_data, indent=2)}")
                    else:
                        logger.info(f"[TWITTER TRACE] Response headers: Present")
                        logger.info(f"[TWITTER TRACE] Response body: Present")
                    
                    # Log rate limit info in structured format
                    try:
                        rate_limit_info = {
                            'remaining': response.headers.get('x-rate-limit-remaining'),
                            'reset': response.headers.get('x-rate-limit-reset'),
                            'limit': response.headers.get('x-rate-limit-limit')
                        }
                        if any(rate_limit_info.values()):
                            logger.info(f"[TWITTER TRACE] Rate limit info: {json.dumps(rate_limit_info, indent=2)}")
                    except Exception as e:
                        logger.debug(f"[TWITTER TRACE] Could not log rate limit headers: {e}")
                    
                    if response.status == 200:
                        return response_data
                    elif response.status == 429:  # Rate limited
                        # With Twitter Basic plan (1 request per 15 minutes), retrying is pointless
                        # The TwitterRateLimitService should prevent calls when rate limited
                        retry_after = int(response.headers.get('retry-after', 900))  # Default to 15 minutes
                        error_msg = f"Rate limit exceeded. Twitter Basic plan allows 1 request per 15 minutes. Next request allowed in {retry_after} seconds."
                        logger.error(f"[TWITTER TRACE] {error_msg}")
                        logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                        logger.warning(f"Twitter Rate Limit: {error_msg}")
                        raise TwitterRateLimitError(error_msg, retry_after=retry_after)
                    elif response.status == 401:
                        error_msg = "Authentication failed. Please check your Twitter bearer token is valid and has not expired."
                        error_details = response_data.get('detail', 'No additional details provided')
                        logger.error(f"[TWITTER TRACE] {error_msg} Details: {error_details}")
                        logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                        logger.warning(f"Twitter Auth Error: {error_msg}")
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
                        logger.error(f"[TWITTER TRACE] 403 Forbidden: {full_error_msg}")
                        logger.error(f"[TWITTER TRACE] Response details: {error_details}")
                        logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                        logger.warning(f"Twitter Permission Error: {error_msg}")
                        logger.warning("Check your API access level and token permissions")
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
                        logger.error(f"[TWITTER TRACE] {error_msg}")
                        logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                        logger.warning(f"Twitter Not Found Error: {error_msg}")
                        raise TwitterNotFoundError(error_msg, status_code=404, response_data=response_data)
                    elif response.status in [500, 502, 503, 504]:
                        # Server errors - retryable
                        other_error_attempts += 1
                        if other_error_attempts >= self.config.other_error_max_retries:
                            error_msg = f"Twitter API server error ({response.status}). Max retries ({self.config.other_error_max_retries}) exceeded. Twitter may be experiencing issues."
                            logger.error(f"[TWITTER TRACE] {error_msg}")
                            logger.error(f"[TWITTER TRACE] Final response data: {response_data}")
                            logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                            raise TwitterAPIError(error_msg, status_code=response.status, response_data=response_data)
                        
                        logger.warning(f"[TWITTER TRACE] Twitter API server error {response.status}: {response_data}. Retry {other_error_attempts}/{self.config.other_error_max_retries}")
                        logger.warning(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                        logger.warning(f"Twitter server error {response.status}. Retrying {other_error_attempts}/{self.config.other_error_max_retries}")
                        await asyncio.sleep(self.config.retry_delay * (2 ** (other_error_attempts - 1)))  # Exponential backoff
                        continue
                    else:
                        # Other HTTP errors - not retryable
                        error_msg = f"Twitter API error {response.status}: {response_data.get('detail', 'Unknown error')}"
                        logger.error(f"[TWITTER TRACE] Non-retryable Twitter API error: {error_msg}")
                        logger.error(f"[TWITTER TRACE] Response data: {response_data}")
                        logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                        logger.warning(f"Twitter API Error {response.status}: Check logs for details")
                        raise TwitterAPIError(error_msg, status_code=response.status, response_data=response_data)
                        
            except aiohttp.ClientError as e:
                # Network errors
                other_error_attempts += 1
                request_duration = (time.time() - request_start_time) * 1000
                if other_error_attempts >= self.config.other_error_max_retries:
                    logger.error(f"[TWITTER TRACE] Network error max retries ({self.config.other_error_max_retries}) exceeded")
                    logger.error(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                    raise
                
                logger.warning(f"[TWITTER TRACE] Network error on attempt {other_error_attempts}/{self.config.other_error_max_retries}: {e}")
                logger.warning(f"[TWITTER TRACE] Request details - URL: {url}, Duration: {request_duration:.2f}ms")
                logger.warning(f"Network error on attempt {other_error_attempts}/{self.config.other_error_max_retries}: {e}")
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
        logger.info(f"[TWITTER TRACE] Fetching user ID for username: {username}")
        logger.info(f"[TWITTER TRACE] Request URL: {url}")
        logger.info(f"[TWITTER TRACE] Headers: {self.session.headers if self.session else 'No session'}")
        
        try:
            response_data = await self._make_request(url)
            logger.info(f"[TWITTER TRACE] Response data: {response_data}")
            
            if 'data' not in response_data:
                logger.error(f"[TWITTER TRACE] User data not found in response: {response_data}")
                raise TwitterNotFoundError(f"User data not found for username: {username}", response_data=response_data)
                
            user_id = response_data['data']['id']
            logger.info(f"[TWITTER TRACE] Found user ID {user_id} for username {username}")
            return user_id
            
        except (TwitterAuthError, TwitterPermissionError, TwitterNotFoundError) as e:
            # Re-raise Twitter-specific errors with context
            logger.error(f"[TWITTER TRACE] Twitter API error in get_user_id for username '{username}': {str(e)}")
            raise
        except TwitterRateLimitError as e:
            logger.error(f"[TWITTER TRACE] Rate limit error in get_user_id for username '{username}': {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Unexpected error in get_user_id for username '{username}': {str(e)}", exc_info=True)
            raise TwitterAPIError(f"Failed to get user ID for '{username}': {str(e)}")
    
    async def get_todays_tweets(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tweets from configured lookback days prior to today until now for a user"""
        from datetime import timedelta
        
        method_start_time = time.time()
        logger.info(f"[TWITTER TRACE] get_todays_tweets starting at {datetime.now(timezone.utc).isoformat()}")
        
        user_id = user_id or self.config.user_id
        if not user_id or not str(user_id).strip():
            logger.error("[TWITTER TRACE] user_id is not configured. Please run tools/get_twitter_user_id.sh to obtain your user ID and set TWITTER_USER_ID in your .env file.")
            return []
            
        # Get UTC timestamps
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(days=self.config.lookback_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now

        url = f"{self.base_url}/users/{user_id}/tweets"
        params = {
            'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'end_time': end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'exclude': 'retweets,replies',
            'tweet.fields': 'created_at,text,public_metrics,geo',
            'place.fields': 'id,full_name,name,country,country_code,place_type,geo',
            'max_results': 100  # Maximum allowed by API
        }

        logger.info(f"[TWITTER TRACE] API call parameters:")
        logger.info(f"[TWITTER TRACE] - User ID: {user_id}")
        logger.info(f"[TWITTER TRACE] - Lookback days: {self.config.lookback_days}")
        logger.info(f"[TWITTER TRACE] - Time range: {start_time} to {end_time}")
        logger.info(f"[TWITTER TRACE] - URL: {url}")
        logger.info(f"[TWITTER TRACE] - Query parameters: {json.dumps(params, indent=2)}")
        
        # Time the API call phase
        api_call_start = time.time()
        response_data = await self._make_request(url, params)
        api_call_duration = (time.time() - api_call_start) * 1000
        
        logger.info(f"[TWITTER TRACE] API call completed in {api_call_duration:.2f}ms")
        
        # Time the processing phase
        processing_start = time.time()
        
        tweets = response_data.get('data', [])
        includes = response_data.get('includes', {})
        places = {place['id']: place for place in includes.get('places', [])}
        
        logger.info(f"[TWITTER TRACE] Response processing:")
        logger.info(f"[TWITTER TRACE] - Tweet count: {len(tweets)}")
        logger.info(f"[TWITTER TRACE] - Includes data: {json.dumps(includes, indent=2) if includes else 'None'}")
        logger.info(f"[TWITTER TRACE] - Places count: {len(places)}")
        if places:
            logger.info(f"[TWITTER TRACE] - Place IDs: {list(places.keys())}")

        # Add place data to tweets
        for tweet in tweets:
            if tweet.get('geo') and tweet['geo'].get('place_id'):
                place_id = tweet['geo']['place_id']
                if place_id in places:
                    tweet['place'] = places[place_id]
                    logger.info(f"[TWITTER TRACE] Added place data to tweet {tweet['id']}: {places[place_id].get('full_name', 'Unknown')}")

        processing_duration = (time.time() - processing_start) * 1000
        total_duration = (time.time() - method_start_time) * 1000
        
        logger.info(f"[TWITTER TRACE] Processing completed in {processing_duration:.2f}ms")
        logger.info(f"[TWITTER TRACE] get_todays_tweets total duration: {total_duration:.2f}ms")
        logger.info(f"[TWITTER TRACE] Returning {len(tweets)} tweets")

        return tweets
    
    async def fetch_user_tweets_today(self) -> List[Dict[str, Any]]:
        """Fetch today's tweets for the configured user"""
        method_start_time = time.time()
        start_timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"[TWITTER TRACE] fetch_user_tweets_today starting at {start_timestamp}")
        
        # Log configuration validation details
        logger.info(f"[TWITTER TRACE] Configuration validation:")
        logger.info(f"[TWITTER TRACE] - Bearer token present: {bool(self.config.bearer_token)}")
        logger.info(f"[TWITTER TRACE] - Bearer token length: {len(self.config.bearer_token or '')}")
        logger.info(f"[TWITTER TRACE] - User ID present: {bool(self.config.user_id)}")
        logger.info(f"[TWITTER TRACE] - User ID value: {self.config.user_id}")
        logger.info(f"[TWITTER TRACE] - Username: {self.config.username}")
        logger.info(f"[TWITTER TRACE] - API configured check: {self.config.is_api_configured()}")
        
        if not self.config.is_api_configured():
            logger.error("[TWITTER TRACE] API Configuration validation failed - returning empty list")
            return []
        
        logger.info(f"[TWITTER TRACE] Using configured user_id: {self.config.user_id}")
        try:
            # Time the tweet fetching phase
            fetch_start_time = time.time()
            tweets = await self.get_todays_tweets()
            fetch_duration = (time.time() - fetch_start_time) * 1000
            
            logger.info(f"[TWITTER TRACE] Fetched {len(tweets)} raw tweets in {fetch_duration:.2f}ms")
            
            # Time the tweet processing phase
            processing_start_time = time.time()
            transformed_tweets = []
            
            logger.info(f"[TWITTER TRACE] Starting transformation of {len(tweets)} tweets")

            for i, tweet in enumerate(tweets):
                tweet_start_time = time.time()
                transformed_tweet = self._parse_tweet(tweet)
                tweet_duration = (time.time() - tweet_start_time) * 1000
                
                if transformed_tweet is None:
                    logger.debug(f"[TWITTER TRACE] Skipped unusable tweet {i+1}/{len(tweets)} (ID: {tweet.get('id', 'unknown')})")
                    continue
                    
                if self.config.diagnostic_mode:
                    logger.info(f"[TWITTER TRACE] Transformed tweet {i+1}/{len(tweets)} (ID: {transformed_tweet['tweet_id']}):")
                    logger.info(f"[TWITTER TRACE] - Created at: {transformed_tweet['created_at']}")
                    logger.info(f"[TWITTER TRACE] - Text length: {len(transformed_tweet['text'])} chars")
                    logger.info(f"[TWITTER TRACE] - Text preview: {transformed_tweet['text'][:100]}...")
                    logger.info(f"[TWITTER TRACE] - Public metrics: {transformed_tweet['public_metrics']}")
                    logger.info(f"[TWITTER TRACE] - Has geo: {bool(transformed_tweet.get('geo'))}")
                    if transformed_tweet.get('place'):
                        logger.info(f"[TWITTER TRACE] - Place: {transformed_tweet['place'].get('full_name', 'Unknown')}")
                    logger.info(f"[TWITTER TRACE] - Transformation time: {tweet_duration:.2f}ms")
                else:
                    logger.debug(f"[TWITTER TRACE] Processed tweet {i+1}/{len(tweets)} (ID: {transformed_tweet['tweet_id']})")
                
                transformed_tweets.append(transformed_tweet)
            
            processing_duration = (time.time() - processing_start_time) * 1000
            total_duration = (time.time() - method_start_time) * 1000
            
            logger.info(f"[TWITTER TRACE] Processed {len(transformed_tweets)} tweets in {processing_duration:.2f}ms")
            logger.info(f"[TWITTER TRACE] fetch_user_tweets_today completed at {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"[TWITTER TRACE] Total duration: {total_duration:.2f}ms")
            
            return transformed_tweets
            
        except TwitterAuthError as e:
            total_duration = (time.time() - method_start_time) * 1000
            logger.error(f"[TWITTER TRACE] Authentication error after {total_duration:.2f}ms: {e}")
            logger.error(f"[TWITTER TRACE] Error context - user_id: {self.config.user_id}")
            logger.warning(f"[Twitter] Authentication failed - check your bearer token configuration")
            logger.warning(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except TwitterPermissionError as e:
            total_duration = (time.time() - method_start_time) * 1000
            logger.error(f"[TWITTER TRACE] Permission error after {total_duration:.2f}ms: {e}")
            logger.error(f"[TWITTER TRACE] Error context - user_id: {self.config.user_id}")
            logger.warning(f"[Twitter] Access denied - check API permissions and account status")
            logger.warning(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except TwitterNotFoundError as e:
            total_duration = (time.time() - method_start_time) * 1000
            logger.error(f"[TWITTER TRACE] Resource not found after {total_duration:.2f}ms: {e}")
            logger.error(f"[TWITTER TRACE] Error context - user_id: {self.config.user_id}, username: {self.config.username}")
            logger.warning(f"[Twitter] User '{self.config.username}' not found or inaccessible")
            logger.warning(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except TwitterRateLimitError as e:
            total_duration = (time.time() - method_start_time) * 1000
            logger.error(f"[TWITTER TRACE] Rate limit exceeded after {total_duration:.2f}ms: {e}")
            logger.error(f"[TWITTER TRACE] Error context - user_id: {self.config.user_id}")
            logger.warning(f"[Twitter] Rate limit exceeded - will retry later")
            logger.warning(f"[Twitter] Next retry in {getattr(e, 'retry_after', 'unknown')} seconds")
            return []
            
        except TwitterAPIError as e:
            total_duration = (time.time() - method_start_time) * 1000
            logger.error(f"[TWITTER TRACE] API error after {total_duration:.2f}ms: {e}")
            logger.error(f"[TWITTER TRACE] Error context - user_id: {self.config.user_id}, status_code: {getattr(e, 'status_code', 'unknown')}")
            logger.warning(f"[Twitter] API error ({getattr(e, 'status_code', 'unknown')}): Check logs for details")
            logger.warning(f"[Twitter] Skipping Twitter data collection")
            return []
            
        except Exception as e:
            total_duration = (time.time() - method_start_time) * 1000
            logger.error(f"[TWITTER TRACE] Unexpected error after {total_duration:.2f}ms: {e}", exc_info=True)
            logger.error(f"[TWITTER TRACE] Error context - user_id: {self.config.user_id}")
            logger.warning(f"[Twitter] Unexpected error: {type(e).__name__}: {e}")
            logger.warning(f"[Twitter] Skipping Twitter data collection")
            return []
    
    def log_configuration_diagnostics(self) -> None:
        """Log comprehensive configuration state for diagnostics"""
        logger.info("[TWITTER TRACE] Configuration Diagnostics:")
        logger.info(f"[TWITTER TRACE] - Bearer token present: {bool(self.config.bearer_token)}")
        if self.config.bearer_token:
            token_length = len(self.config.bearer_token)
            logger.info(f"[TWITTER TRACE] - Bearer token length: {token_length}")
            logger.info(f"[TWITTER TRACE] - Bearer token format: {'Valid' if token_length > 10 else 'Invalid'}")
        else:
            logger.info("[TWITTER TRACE] - Bearer token: None")
        
        logger.info(f"[TWITTER TRACE] - Username present: {bool(self.config.username)}")
        logger.info(f"[TWITTER TRACE] - Username value: {self.config.username}")
        logger.info(f"[TWITTER TRACE] - User ID present: {bool(self.config.user_id)}")
        logger.info(f"[TWITTER TRACE] - User ID value: {self.config.user_id}")
        logger.info(f"[TWITTER TRACE] - Request timeout: {self.config.request_timeout}")
        logger.info(f"[TWITTER TRACE] - Retry delay: {self.config.retry_delay}")
        logger.info(f"[TWITTER TRACE] - Max retries: {self.config.other_error_max_retries}")
        logger.info(f"[TWITTER TRACE] - API configured check: {self.config.is_api_configured()}")
        logger.info(f"[TWITTER TRACE] - Base URL: {self.base_url}")
        
    def is_configured(self) -> bool:
        """Check if the service is properly configured"""
        logger.info("[TWITTER TRACE] Checking if Twitter API is configured...")
        self.log_configuration_diagnostics()
        result = self.config.is_api_configured()
        logger.info(f"[TWITTER TRACE] Final configuration result: {result}")
        return result
    
    async def test_api_connectivity(self) -> Dict[str, Any]:
        """Test API connectivity and return detailed results for diagnostics"""
        logger.info("[TWITTER TRACE] Testing API connectivity...")
        test_start_time = time.time()
        
        if not self.config.is_api_configured():
            result = {
                'success': False,
                'error': 'API not configured',
                'details': 'Missing bearer token or user ID',
                'duration_ms': 0
            }
            logger.error(f"[TWITTER TRACE] API connectivity test failed: {result}")
            return result
        
        try:
            # Test with a simple user lookup
            url = f"{self.base_url}/users/{self.config.user_id}"
            params = {'user.fields': 'id,username,name'}
            
            logger.info(f"[TWITTER TRACE] Testing connectivity with URL: {url}")
            response_data = await self._make_request(url, params)
            
            test_duration = (time.time() - test_start_time) * 1000
            result = {
                'success': True,
                'response_data': response_data,
                'duration_ms': test_duration,
                'user_info': response_data.get('data', {})
            }
            logger.info(f"[TWITTER TRACE] API connectivity test successful: {result}")
            return result
            
        except Exception as e:
            test_duration = (time.time() - test_start_time) * 1000
            result = {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'duration_ms': test_duration
            }
            logger.error(f"[TWITTER TRACE] API connectivity test failed: {result}")
            return result
