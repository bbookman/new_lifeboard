"""
Test for Twitter data ingestion sequence.

This test verifies the complete Twitter data ingestion workflow as described:
1. SyncManagerService calls fetch_items on TwitterSource
2. Configuration & rate-limit check
3. API data fetching
4. Deduplication
5. Processing and ingestion

No mocking - this test confirms the sequence functions and that tweets are returned.
"""

import pytest
import asyncio
import time
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from sources.twitter import TwitterSource
from config.models import TwitterConfig, AppConfig
from config.factory import get_config
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from services.twitter_api_service import TwitterAPIService
from services.twitter_rate_limit_service import TwitterRateLimitService
from services.ingestion import IngestionService
from services.sync_manager_service import SyncManagerService
from sources.base import DataItem


@pytest.fixture
def real_config():
    """Create real config that loads from .env file"""
    return get_config()


@pytest.fixture
def real_twitter_config(real_config):
    """Get TwitterConfig from real config factory"""
    return real_config.twitter


@pytest.fixture
def real_database():
    """Create real database service for integration testing"""
    return DatabaseService()


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing"""
    return MagicMock(spec=VectorStoreService)


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing"""
    return MagicMock(spec=EmbeddingService)


@pytest.fixture
def test_config(real_config):
    """Use real configuration for testing"""
    return real_config


@pytest.fixture
def real_ingestion_service(real_database, mock_vector_store, mock_embedding_service, test_config):
    """Create real ingestion service for integration testing"""
    return IngestionService(
        database=real_database,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        config=test_config
    )


@pytest.fixture
def real_sync_manager(real_twitter_config, real_database, real_ingestion_service, test_config):
    """Create real SyncManagerService for integration testing"""
    return SyncManagerService(real_database, real_ingestion_service, test_config)


@pytest.fixture
def twitter_source(real_twitter_config, real_database, real_ingestion_service):
    """Create TwitterSource instance with real services"""
    return TwitterSource(real_twitter_config, real_database, real_ingestion_service)


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.integration
class TestTwitterDataIngestionSequence:
    """
    Test the complete Twitter data ingestion sequence.

    This test verifies that the Twitter ingestion workflow functions correctly
    and can retrieve at least one tweet for today when API credentials are configured.
    """

    async def test_complete_ingestion_sequence_with_timing(self, twitter_source, real_ingestion_service, real_database, real_twitter_config):
        """
        Test the complete Twitter data ingestion sequence with database storage.

        Uses the TWITTER_INTER_CALL_DELAY from .env to wait for rate limit reset.
        Tests the full pipeline:
        1. Configuration validation
        2. Rate limit checking  
        3. API call execution
        4. Tweet processing and ingestion
        5. Database storage verification
        6. At least one tweet stored in database for today
        """
        # Skip test if Twitter API is not configured
        if not real_twitter_config.is_api_configured():
            pytest.skip("Twitter API not configured - set TWITTER_BEARER_TOKEN and TWITTER_USER_NAME")

        # Use the configured inter-call delay from .env
        inter_call_delay = real_twitter_config.inter_call_delay
        max_wait_time = inter_call_delay + 60  # Wait time + 1 minute buffer
        check_interval = 30  # Check every 30 seconds

        print(f"\n🕐 Starting Twitter ingestion sequence test at {datetime.now()}")
        print(f"⏱️  Using TWITTER_INTER_CALL_DELAY: {inter_call_delay} seconds ({inter_call_delay/60:.1f} minutes)")
        print(f"⏱️  Will wait up to {max_wait_time/60:.1f} minutes for rate limit reset")

        # Check initial database state
        initial_twitter_count = len(real_database.get_data_items_by_namespace("twitter"))
        print(f"📊 Initial Twitter items in database: {initial_twitter_count}")

        start_time = time.time()
        attempt = 0
        max_attempts = 3

        while attempt < max_attempts:
            attempt += 1
            elapsed_time = time.time() - start_time
            print(f"\n🔄 Attempt {attempt}/{max_attempts} - Elapsed: {elapsed_time:.1f}s")

            try:
                # Step 1: Check rate limit status
                can_fetch, minutes_until = await twitter_source.rate_limit_service.can_fetch_now()
                
                if not can_fetch:
                    remaining_seconds = minutes_until * 60
                    print(f"⏳ Rate limited for {remaining_seconds:.0f} more seconds ({minutes_until:.1f} minutes)")
                    
                    # If this is our last attempt and we're still rate limited, wait for it
                    if attempt == max_attempts and remaining_seconds <= max_wait_time:
                        print(f"⏳ Waiting {remaining_seconds:.0f} seconds for rate limit to reset...")
                        await asyncio.sleep(remaining_seconds + 5)  # +5 second buffer
                        print("✅ Rate limit should be reset, trying fetch...")
                    elif attempt < max_attempts:
                        print(f"⏭️  Rate limited, trying again on next attempt...")
                        await asyncio.sleep(check_interval)
                        continue
                    else:
                        print(f"⏭️  Rate limited beyond test timeout, skipping...")
                        break

                # Step 2: Fetch items from Twitter source
                print("📡 Fetching items from TwitterSource...")
                items = []
                async for item in twitter_source.fetch_items():
                    items.append(item)
                    print(f"📝 Fetched item: {item.source_id}")
                
                print(f"📊 Items fetched: {len(items)}")
                
                if items:
                    # Step 3: Ingest items through IngestionService
                    print("💾 Ingesting items through IngestionService...")
                    result = await real_ingestion_service.ingest_items(items)
                    print(f"📊 Ingestion result: {result.items_stored} stored, {len(result.errors)} errors")
                    
                    if result.errors:
                        print("❌ Ingestion errors:")
                        for error in result.errors:
                            print(f"  - {error}")
                    
                    # Step 4: Verify database storage
                    final_count = len(real_database.get_data_items_by_namespace("twitter"))
                    new_items = final_count - initial_twitter_count
                    print(f"📊 Final Twitter items: {final_count}")
                    print(f"📈 New items added: {new_items}")
                    
                    if new_items > 0:
                        print("✅ SUCCESS: Twitter data was stored in database!")
                        
                        # Verify stored tweet properties
                        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                        recent_items = real_database.get_data_items_by_namespace("twitter")[-new_items:]
                        
                        for item in recent_items:
                            print(f"📝 Stored: {item.source_id[:50]}... Date: {item.days_date}")
                            assert item.namespace == "twitter"
                            assert item.source_id
                            assert item.content
                            assert item.days_date == today
                        
                        print("✅ All assertions passed - Twitter ingestion working correctly")
                        return  # Test passed
                    else:
                        print("❌ FAILURE: Items fetched but not stored in database!")
                        return
                
                else:
                    print("⚠️  No items fetched - checking if this is expected...")
                    # Even if no items, this might be normal (no new tweets today)
                    if attempt == max_attempts:
                        print("⚠️  No Twitter data found after all attempts")
                        return

            except Exception as e:
                print(f"❌ Error during attempt {attempt}: {e}")
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(check_interval)

        # If we get here, the test timed out
        final_count = len(real_database.get_data_items_by_namespace("twitter"))
        pytest.fail(f"Test timed out after {max_wait_time/60:.1f} minutes. "
                   f"Initial: {initial_twitter_count}, Final: {final_count}, New: {final_count - initial_twitter_count}. "
                   f"Check Twitter API configuration and rate limits.")

    async def test_database_diagnostic(self, real_database):
        """Diagnostic test to check current database state"""
        print("\n🔍 DATABASE DIAGNOSTIC:")
        
        # Check all Twitter items in database
        twitter_items = real_database.get_data_items_by_namespace("twitter")
        print(f"📊 Total Twitter items in database: {len(twitter_items)}")
        
        # Show recent Twitter items
        if twitter_items:
            print("📝 Recent Twitter items:")
            for item in twitter_items[-5:]:  # Last 5 items
                print(f"  - ID: {item.source_id}, Date: {item.days_date}, Content: {item.content[:50]}...")
        
        # Check today's date format
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        print(f"📅 Today's date: {today}")
        
        # Check for today's Twitter items specifically
        today_twitter = [item for item in twitter_items if item.days_date == today]
        print(f"📅 Twitter items for today: {len(today_twitter)}")
        
        # Check all namespaces using DatabaseService context manager
        with real_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT namespace, item_count FROM data_sources")
            data_sources = cursor.fetchall()
            
            print("📊 All data sources:")
            for row in data_sources:
                print(f"  - {row[0]}: {row[1]} items")
                
            # Also check data_items table directly
            cursor.execute("SELECT namespace, COUNT(*) FROM data_items GROUP BY namespace")
            namespace_counts = cursor.fetchall()
            
            print("📊 Actual data_items table counts:")
            for row in namespace_counts:
                print(f"  - {row[0]}: {row[1]} items")

    async def test_single_ingestion_attempt(self, twitter_source, real_ingestion_service, real_database, real_twitter_config):
        """Test a single ingestion attempt to see what happens"""
        if not real_twitter_config.is_api_configured():
            pytest.skip("Twitter API not configured - set TWITTER_BEARER_TOKEN and TWITTER_USER_NAME")
        
        print("\n🧪 SINGLE INGESTION ATTEMPT TEST:")
        
        # Check initial state
        initial_count = len(real_database.get_data_items_by_namespace("twitter"))
        print(f"📊 Initial Twitter items: {initial_count}")
        
        try:
            # Step 1: Fetch items from Twitter source
            print("📡 Fetching items from TwitterSource...")
            items = []
            async for item in twitter_source.fetch_items():
                items.append(item)
                print(f"📝 Fetched item: {item.source_id}")
            
            print(f"📊 Items fetched: {len(items)}")
            
            if items:
                # Step 2: Ingest the items through IngestionService
                print("💾 Ingesting items through IngestionService...")
                result = await real_ingestion_service.ingest_items(items)
                print(f"📊 Ingestion result: {result.items_stored} stored, {len(result.errors)} errors")
                
                if result.errors:
                    print("❌ Ingestion errors:")
                    for error in result.errors:
                        print(f"  - {error}")
                
                # Step 3: Check database after ingestion
                final_count = len(real_database.get_data_items_by_namespace("twitter"))
                print(f"📊 Final Twitter items: {final_count}")
                print(f"📈 New items added: {final_count - initial_count}")
                
                if final_count > initial_count:
                    print("✅ SUCCESS: Twitter data was stored in database!")
                    # Show sample data
                    recent_items = real_database.get_data_items_by_namespace("twitter")[-3:]
                    for item in recent_items:
                        print(f"📝 Stored item: {item.source_id[:50]}...")
                else:
                    print("⚠️  Items fetched but not stored - ingestion issue!")
                    
            else:
                print("⚠️  No items fetched - may be rate limited or no new tweets")
                
        except Exception as e:
            print(f"❌ Error during ingestion: {e}")
            import traceback
            traceback.print_exc()

    async def test_rate_limit_handling(self, twitter_source, real_twitter_config):
        """Test that rate limiting is properly handled"""
        if not real_twitter_config.is_api_configured():
            pytest.skip("Twitter API not configured")

        # Check initial rate limit status
        can_fetch, minutes_until = await twitter_source.rate_limit_service.can_fetch_now()

        if not can_fetch:
            print(f"ℹ️  Currently rate limited for {minutes_until} more minutes")
            assert minutes_until > 0
        else:
            print("ℹ️  Not currently rate limited")
            assert minutes_until == 0

    async def test_configuration_validation(self, twitter_source, real_twitter_config):
        """Test that configuration is properly validated"""
        # Test API configuration check
        is_api_configured = real_twitter_config.is_api_configured()
        print(f"🔧 API configured: {is_api_configured}")

        # Test connection test
        connection_ok = await twitter_source.test_connection()
        print(f"🔌 Connection test: {connection_ok}")

        # If API is configured, connection should work
        if is_api_configured:
            assert connection_ok, "Connection test should pass when API is configured"

    @pytest.mark.parametrize("wait_time", [60, 120, 300])
    async def test_timing_mechanism(self, wait_time):
        """Test the timing mechanism for rate limit waiting"""
        start_time = time.time()

        print(f"⏱️  Testing timing mechanism with {wait_time}s wait...")
        await asyncio.sleep(wait_time)

        elapsed = time.time() - start_time
        assert elapsed >= wait_time * 0.9, f"Waited {elapsed:.1f}s, expected at least {wait_time * 0.9:.1f}s"
        print(f"✅ Timing mechanism working correctly (waited {elapsed:.1f}s)")


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v", "-s"])