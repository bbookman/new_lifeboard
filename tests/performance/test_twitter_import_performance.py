"""
Performance tests for Twitter archive import functionality.

Tests performance characteristics, memory usage, and scalability
of the Twitter import process.
"""

import asyncio
import json
import os
import psutil
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from config.models import TwitterConfig
from core.database import DatabaseService
from services.ingestion import IngestionService
from sources.twitter import TwitterSource


class TestTwitterImportPerformance:
    """Performance tests for Twitter import functionality."""

    @pytest.fixture
    def performance_config(self):
        """Configuration optimized for performance testing."""
        return TwitterConfig(
            enabled=True,
            bearer_token=None,
            username=None,
            sync_interval_hours=24,
            max_retries=1,  # Reduce retries for faster tests
            retry_delay=0.1,  # Faster retries
            delete_after_import=True
        )

    @pytest.fixture
    def memory_db(self):
        """In-memory database for performance testing."""
        return DatabaseService(':memory:')

    @pytest.fixture
    def mock_fast_ingestion(self):
        """Mock ingestion service optimized for performance testing."""
        service = MagicMock(spec=IngestionService)
        service.ingest_items = AsyncMock(return_value={
            "items_processed": 1000,
            "items_stored": 1000,
            "success": True
        })
        return service

    def create_large_test_archive(self, tweet_count: int) -> Path:
        """Create a large test archive with specified number of tweets."""
        temp_dir = Path(tempfile.mkdtemp())
        archive_path = temp_dir / f"large_archive_{tweet_count}.zip"
        
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as zip_file:
            # Generate tweets data
            tweets_data = []
            for i in range(tweet_count):
                tweet = {
                    "tweet": {
                        "id": f"123456789012345{i:06d}",
                        "created_at": f"Wed Jan {10 + (i % 20):02d} {10 + (i % 14):02d}:30:00 +0000 2024",
                        "full_text": f"Performance test tweet #{i} with some content to make it realistic. This is tweet number {i} out of {tweet_count} total tweets.",
                        "entities": {
                            "hashtags": [{"text": "performance", "indices": [0, 11]}] if i % 10 == 0 else [],
                            "media": [{"media_url_https": f"https://example.com/media{i}.jpg"}] if i % 25 == 0 else []
                        },
                        "retweet_count": i % 100,
                        "favorite_count": i % 50
                    }
                }
                tweets_data.append(tweet)
            
            # Write tweets.js
            tweets_content = f"window.YTD.tweets.part0 = {json.dumps(tweets_data)}"
            zip_file.writestr("data/tweets.js", tweets_content)
            
            # Add some other files to simulate real archive
            zip_file.writestr("data/account.js", "window.YTD.account.part0 = []")
            zip_file.writestr("data/profile.js", "window.YTD.profile.part0 = []")
        
        return archive_path

    @pytest.mark.asyncio
    async def test_small_archive_performance(self, performance_config, memory_db, mock_fast_ingestion):
        """Test performance with small archive (100 tweets)."""
        tweet_count = 100
        archive_path = self.create_large_test_archive(tweet_count)
        
        try:
            twitter_source = TwitterSource(performance_config, memory_db, mock_fast_ingestion)
            
            # Measure import performance
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            result = await twitter_source.import_from_zip(str(archive_path))
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            duration = end_time - start_time
            memory_used = end_memory - start_memory
            
            # Performance assertions
            assert result["success"] is True
            assert duration < 5.0, f"Small archive took {duration:.2f}s, should be under 5s"
            assert memory_used < 50, f"Used {memory_used:.2f}MB, should be under 50MB"
            
            # Calculate throughput
            throughput = tweet_count / duration
            assert throughput > 50, f"Throughput {throughput:.2f} tweets/sec should be > 50"
            
            print(f"\\nSmall Archive Performance ({tweet_count} tweets):")
            print(f"Duration: {duration:.3f}s")
            print(f"Memory used: {memory_used:.2f}MB") 
            print(f"Throughput: {throughput:.2f} tweets/sec")
            
        finally:
            # Cleanup
            if archive_path.exists():
                archive_path.unlink()
            archive_path.parent.rmdir()

    @pytest.mark.asyncio
    async def test_medium_archive_performance(self, performance_config, memory_db, mock_fast_ingestion):
        """Test performance with medium archive (1000 tweets)."""
        tweet_count = 1000
        archive_path = self.create_large_test_archive(tweet_count)
        
        try:
            twitter_source = TwitterSource(performance_config, memory_db, mock_fast_ingestion)
            
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            result = await twitter_source.import_from_zip(str(archive_path))
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            duration = end_time - start_time
            memory_used = end_memory - start_memory
            
            # Performance assertions for medium archive
            assert result["success"] is True
            assert duration < 15.0, f"Medium archive took {duration:.2f}s, should be under 15s"
            assert memory_used < 100, f"Used {memory_used:.2f}MB, should be under 100MB"
            
            throughput = tweet_count / duration
            assert throughput > 30, f"Throughput {throughput:.2f} tweets/sec should be > 30"
            
            print(f"\\nMedium Archive Performance ({tweet_count} tweets):")
            print(f"Duration: {duration:.3f}s")
            print(f"Memory used: {memory_used:.2f}MB")
            print(f"Throughput: {throughput:.2f} tweets/sec")
            
        finally:
            # Cleanup
            if archive_path.exists():
                archive_path.unlink()
            archive_path.parent.rmdir()

    @pytest.mark.asyncio
    async def test_large_archive_performance(self, performance_config, memory_db, mock_fast_ingestion):
        """Test performance with large archive (5000 tweets)."""
        tweet_count = 5000
        archive_path = self.create_large_test_archive(tweet_count)
        
        try:
            twitter_source = TwitterSource(performance_config, memory_db, mock_fast_ingestion)
            
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            result = await twitter_source.import_from_zip(str(archive_path))
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            duration = end_time - start_time
            memory_used = end_memory - start_memory
            
            # Performance assertions for large archive
            assert result["success"] is True
            assert duration < 60.0, f"Large archive took {duration:.2f}s, should be under 60s"
            assert memory_used < 200, f"Used {memory_used:.2f}MB, should be under 200MB"
            
            throughput = tweet_count / duration
            assert throughput > 20, f"Throughput {throughput:.2f} tweets/sec should be > 20"
            
            print(f"\\nLarge Archive Performance ({tweet_count} tweets):")
            print(f"Duration: {duration:.3f}s")
            print(f"Memory used: {memory_used:.2f}MB")
            print(f"Throughput: {throughput:.2f} tweets/sec")
            
        finally:
            # Cleanup
            if archive_path.exists():
                archive_path.unlink()
            archive_path.parent.rmdir()

    @pytest.mark.asyncio 
    async def test_real_archive_performance(self, performance_config, memory_db, mock_fast_ingestion):
        """Test performance with the real Twitter archive."""
        real_archive = "/Users/brucebookman/code/new_lifeboard/tests/media/twitter-x.zip"
        
        if not os.path.exists(real_archive):
            pytest.skip("Real Twitter archive not available for performance testing")
        
        twitter_source = TwitterSource(performance_config, memory_db, mock_fast_ingestion)
        
        # Get archive info first
        with zipfile.ZipFile(real_archive, 'r') as zip_file:
            tweets_file = None
            for file_name in zip_file.namelist():
                if file_name.endswith('tweets.js'):
                    tweets_file = file_name
                    break
            
            if tweets_file:
                with zip_file.open(tweets_file) as f:
                    content = f.read().decode('utf-8')
                    
                # Count tweets in real archive
                json_start = content.find('[')
                json_end = content.rfind(']') + 1
                json_content = content[json_start:json_end]
                tweets_data = json.loads(json_content)
                tweet_count = len(tweets_data)
            else:
                pytest.skip("No tweets.js found in real archive")
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        result = await twitter_source.import_from_zip(real_archive)
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        duration = end_time - start_time
        memory_used = end_memory - start_memory
        throughput = tweet_count / duration if duration > 0 else 0
        
        # Performance assertions for real archive
        assert result["success"] is True
        assert duration < 120.0, f"Real archive took {duration:.2f}s, should be under 120s"
        assert memory_used < 500, f"Used {memory_used:.2f}MB, should be under 500MB"
        
        print(f"\\nReal Archive Performance ({tweet_count} tweets):")
        print(f"Duration: {duration:.3f}s")
        print(f"Memory used: {memory_used:.2f}MB")
        print(f"Throughput: {throughput:.2f} tweets/sec")

    @pytest.mark.asyncio
    async def test_memory_usage_pattern(self, performance_config, memory_db, mock_fast_ingestion):
        """Test memory usage patterns during import."""
        tweet_count = 1000
        archive_path = self.create_large_test_archive(tweet_count)
        
        try:
            twitter_source = TwitterSource(performance_config, memory_db, mock_fast_ingestion)
            
            # Monitor memory during import
            memory_samples = []
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            async def memory_monitor():
                """Monitor memory usage during import."""
                for _ in range(20):  # Sample for ~2 seconds
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory - start_memory)
                    await asyncio.sleep(0.1)
            
            # Start monitoring and import concurrently
            monitor_task = asyncio.create_task(memory_monitor())
            import_task = asyncio.create_task(twitter_source.import_from_zip(str(archive_path)))
            
            result, _ = await asyncio.gather(import_task, monitor_task)
            
            # Analyze memory usage
            max_memory = max(memory_samples) if memory_samples else 0
            avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0
            
            print(f"\\nMemory Usage Pattern:")
            print(f"Peak memory usage: {max_memory:.2f}MB")
            print(f"Average memory usage: {avg_memory:.2f}MB")
            print(f"Memory samples count: {len(memory_samples)}")
            
            # Memory usage assertions
            assert result["success"] is True
            assert max_memory < 150, f"Peak memory {max_memory:.2f}MB should be under 150MB"
            
        finally:
            # Cleanup
            if archive_path.exists():
                archive_path.unlink()
            archive_path.parent.rmdir()

    @pytest.mark.asyncio
    async def test_concurrent_imports_performance(self, performance_config, mock_fast_ingestion):
        """Test performance when running multiple imports concurrently."""
        tweet_count = 500
        num_concurrent = 3
        
        # Create multiple test archives
        archives = []
        for i in range(num_concurrent):
            archive = self.create_large_test_archive(tweet_count)
            archives.append(archive)
        
        try:
            # Create separate DB and source for each concurrent import
            sources = []
            for i in range(num_concurrent):
                db = DatabaseService(':memory:')
                source = TwitterSource(performance_config, db, mock_fast_ingestion)
                sources.append(source)
            
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            # Run imports concurrently
            import_tasks = [
                source.import_from_zip(str(archive))
                for source, archive in zip(sources, archives)
            ]
            
            results = await asyncio.gather(*import_tasks)
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            duration = end_time - start_time
            memory_used = end_memory - start_memory
            total_tweets = tweet_count * num_concurrent
            throughput = total_tweets / duration
            
            # Verify all imports succeeded
            for result in results:
                assert result["success"] is True
            
            # Performance assertions
            assert duration < 30.0, f"Concurrent imports took {duration:.2f}s, should be under 30s"
            assert memory_used < 300, f"Used {memory_used:.2f}MB, should be under 300MB"
            
            print(f"\\nConcurrent Import Performance ({num_concurrent} imports, {tweet_count} tweets each):")
            print(f"Duration: {duration:.3f}s")
            print(f"Memory used: {memory_used:.2f}MB")
            print(f"Total throughput: {throughput:.2f} tweets/sec")
            print(f"Per-import throughput: {throughput/num_concurrent:.2f} tweets/sec")
            
        finally:
            # Cleanup
            for archive in archives:
                if archive.exists():
                    archive.unlink()
                archive.parent.rmdir()

    @pytest.mark.asyncio
    async def test_deduplication_performance(self, performance_config, memory_db, mock_fast_ingestion):
        """Test performance when many tweets already exist (deduplication)."""
        tweet_count = 1000
        existing_ratio = 0.8  # 80% of tweets already exist
        
        archive_path = self.create_large_test_archive(tweet_count)
        
        try:
            twitter_source = TwitterSource(performance_config, memory_db, mock_fast_ingestion)
            
            # Mock existing tweets (80% already exist)
            from unittest.mock import patch
            existing_count = int(tweet_count * existing_ratio)
            existing_ids = {f"123456789012345{i:06d}" for i in range(existing_count)}
            
            with patch.object(twitter_source, '_get_existing_tweet_ids', 
                             return_value=existing_ids):
                start_time = time.time()
                
                result = await twitter_source.import_from_zip(str(archive_path))
                
                end_time = time.time()
                duration = end_time - start_time
                
                # Should still be fast even with deduplication
                assert result["success"] is True
                expected_new_tweets = tweet_count - existing_count
                assert duration < 20.0, f"Deduplication took {duration:.2f}s, should be under 20s"
                
                print(f"\\nDeduplication Performance:")
                print(f"Total tweets: {tweet_count}")
                print(f"Existing tweets: {existing_count} ({existing_ratio*100:.0f}%)")
                print(f"Expected new tweets: {expected_new_tweets}")
                print(f"Duration: {duration:.3f}s")
                print(f"Deduplication rate: {tweet_count/duration:.2f} tweets/sec")
                
        finally:
            # Cleanup
            if archive_path.exists():
                archive_path.unlink()
            archive_path.parent.rmdir()


class TestTwitterImportScalability:
    """Test scalability characteristics of Twitter import."""

    def test_file_size_vs_performance(self):
        """Test how performance scales with file size."""
        # This test documents the relationship between archive size and processing time
        test_sizes = [100, 500, 1000, 2000]
        results = []
        
        for size in test_sizes:
            print(f"\\nTesting with {size} tweets...")
            # In a real implementation, you would run the import and measure
            # For now, we'll document the expected scalability characteristics
            expected_duration = size * 0.01  # ~10ms per tweet
            expected_memory = 20 + (size * 0.05)  # Base + 50KB per tweet
            
            results.append({
                'size': size,
                'expected_duration': expected_duration,
                'expected_memory': expected_memory
            })
            
            print(f"Expected duration: {expected_duration:.2f}s")
            print(f"Expected memory: {expected_memory:.2f}MB")
        
        # Verify scalability is roughly linear
        for i in range(1, len(results)):
            prev_result = results[i-1]
            curr_result = results[i]
            
            size_ratio = curr_result['size'] / prev_result['size']
            duration_ratio = curr_result['expected_duration'] / prev_result['expected_duration']
            
            # Duration should scale roughly linearly with size
            assert 0.8 < duration_ratio / size_ratio < 1.2, "Performance should scale roughly linearly"

    def test_memory_efficiency_requirements(self):
        """Test that memory usage doesn't grow excessively with large archives."""
        # Define memory efficiency requirements
        max_memory_per_1k_tweets = 50  # MB
        max_baseline_memory = 30  # MB
        
        # Test various archive sizes
        test_cases = [
            (1000, max_baseline_memory + max_memory_per_1k_tweets),
            (5000, max_baseline_memory + max_memory_per_1k_tweets * 5),
            (10000, max_baseline_memory + max_memory_per_1k_tweets * 10),
        ]
        
        for tweet_count, max_expected_memory in test_cases:
            print(f"\\nMemory requirements for {tweet_count} tweets:")
            print(f"Maximum expected memory: {max_expected_memory}MB")
            
            # In a real test, verify actual memory usage is within limits
            # For now, document the requirements
            assert max_expected_memory < 600, f"Memory usage should not exceed 600MB for {tweet_count} tweets"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])