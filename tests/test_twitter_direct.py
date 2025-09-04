#!/usr/bin/env python3
"""
Direct Twitter API test script to bypass rate limiting and other layers
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Twitter API configuration - you'll need to set these
BEARER_TOKEN = "YOUR_BEARER_TOKEN_HERE"  # Replace with your actual bearer token
USER_ID = "YOUR_USER_ID_HERE"  # Replace with your actual user ID

class DirectTwitterTester:
    """Direct Twitter API tester bypassing all rate limiting"""

    def __init__(self, bearer_token: str, user_id: str):
        self.bearer_token = bearer_token
        self.user_id = user_id
        self.base_url = "https://api.twitter.com/2"
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "User-Agent": "TwitterDirectTest/1.0"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_user_id_validation(self):
        """Test that the configured user_id is valid"""
        logger.info("🔍 [DIRECT TEST] Testing user ID validation...")
        
        if not self.user_id.isdigit():
            logger.error(f"❌ [DIRECT TEST] Invalid user ID format: {self.user_id}")
            return False
            
        logger.info(f"✅ [DIRECT TEST] User ID validation successful: {self.user_id}")
        return True

    async def test_tweets_fetch(self):
        """Test tweets fetching for the configured user"""
        logger.info(f"🔍 [DIRECT TEST] Testing tweets fetch for user {self.user_id}...")

        # Get last 5 days
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(days=5)).replace(hour=0, minute=0, second=0, microsecond=0)

        url = f"{self.base_url}/users/{self.user_id}/tweets"
        params = {
            'start_time': start_time.isoformat(),
            'end_time': now.isoformat(),
            'exclude': 'retweets,replies',
            'tweet.fields': 'created_at,text,public_metrics,geo',
            'place.fields': 'id,full_name,name,country,country_code,place_type,geo',
            'max_results': 100
        }

        try:
            logger.info(f"🔍 [DIRECT TEST] Making request to: {url}")
            logger.info(f"🔍 [DIRECT TEST] Parameters: {json.dumps(params, indent=2)}")

            async with self.session.get(url, params=params) as response:
                logger.info(f"📊 [DIRECT TEST] Response status: {response.status}")

                # Log rate limit headers
                rate_limit_remaining = response.headers.get('x-rate-limit-remaining')
                rate_limit_reset = response.headers.get('x-rate-limit-reset')
                if rate_limit_remaining:
                    logger.info(f"📊 [DIRECT TEST] Rate limit remaining: {rate_limit_remaining}")
                    logger.info(f"📊 [DIRECT TEST] Rate limit reset: {rate_limit_reset}")

                response_data = await response.json()
                logger.info(f"📊 [DIRECT TEST] Response data: {json.dumps(response_data, indent=2)}")

                if response.status == 200:
                    tweets = response_data.get('data', [])
                    logger.info(f"✅ [DIRECT TEST] Tweets fetch successful! Retrieved {len(tweets)} tweets")

                    # Log first few tweets for inspection
                    for i, tweet in enumerate(tweets[:3]):
                        logger.info(f"📊 [DIRECT TEST] Tweet {i+1}: ID={tweet.get('id')}, Text={tweet.get('text')[:100]}...")

                    return tweets
                else:
                    logger.error(f"❌ [DIRECT TEST] Tweets fetch failed: {response_data}")
                    return []

        except Exception as e:
            logger.error(f"❌ [DIRECT TEST] Tweets fetch error: {e}")
            return []

async def main():
    """Main test function"""
    logger.info("🚀 [DIRECT TEST] ===== STARTING DIRECT TWITTER API TEST =====")

    # Check if tokens are configured
    if BEARER_TOKEN == "YOUR_BEARER_TOKEN_HERE" or USER_ID == "YOUR_USER_ID_HERE":
        logger.error("❌ [DIRECT TEST] Please configure BEARER_TOKEN and USER_ID in the script")
        logger.info("ℹ️ [DIRECT TEST] Run tools/get_twitter_user_id.sh to get your user ID")
        return

    async with DirectTwitterTester(BEARER_TOKEN, USER_ID) as tester:
        # Test 1: User ID validation
        user_id_valid = await tester.test_user_id_validation()
        if not user_id_valid:
            logger.error("❌ [DIRECT TEST] User ID validation failed, cannot proceed with tweets test")
            return

        # Test 2: Tweets fetch (directly using configured user_id)
        tweets = await tester.test_tweets_fetch()

        # Summary
        logger.info("🚀 [DIRECT TEST] ===== TEST SUMMARY =====")
        logger.info(f"📊 [DIRECT TEST] User ID validation: {'✅ SUCCESS' if user_id_valid else '❌ FAILED'}")
        logger.info(f"📊 [DIRECT TEST] Tweets fetch: {'✅ SUCCESS' if tweets else '❌ FAILED'} ({len(tweets)} tweets)")
        logger.info(f"📊 [DIRECT TEST] Using user_id: {USER_ID}")
        logger.info("🚀 [DIRECT TEST] ===== DIRECT TEST COMPLETED =====")

if __name__ == "__main__":
    asyncio.run(main())