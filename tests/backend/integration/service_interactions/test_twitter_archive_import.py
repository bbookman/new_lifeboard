"""
Comprehensive integration tests for Twitter archive import functionality.

Tests the complete import workflow using real Twitter archive data from twitter-x.zip.
This test suite verifies:
1. Archive extraction and parsing
2. Tweet data processing and deduplication  
3. Database storage and retrieval
4. Integration with ingestion service
5. End-to-end import workflow
"""

import asyncio
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config.models import TwitterConfig
from core.database import DatabaseService  
from services.ingestion import IngestionService
from sources.twitter import TwitterSource


class TestTwitterArchiveImport:
    """Integration tests for Twitter archive import using real archive data."""

    @pytest.fixture
    def real_twitter_archive(self):
        """Path to the real Twitter archive for testing."""
        return "/Users/brucebookman/code/new_lifeboard/tests/media/twitter-x.zip"
    
    @pytest.fixture
    def twitter_config(self):
        """Twitter configuration for archive-only imports."""
        return TwitterConfig(
            enabled=True,
            bearer_token=None,  # No API needed for archive import
            username=None,
            delete_after_import=False,
            sync_interval_hours=24,
            max_retries=3,
            retry_delay=1.0
        )

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "test_twitter_import.db"
        return DatabaseService(str(db_path))

    @pytest.fixture
    def mock_ingestion_service(self):
        """Mock ingestion service for testing."""
        service = MagicMock(spec=IngestionService)
        service.ingest_items = AsyncMock(return_value={
            "items_processed": 0,
            "items_stored": 0, 
            "items_skipped": 0,
            "success": True
        })
        return service

    @pytest.fixture
    def twitter_source(self, twitter_config, temp_db, mock_ingestion_service):
        """Create TwitterSource instance for testing."""
        return TwitterSource(twitter_config, temp_db, mock_ingestion_service)

    def test_archive_exists_and_valid(self, real_twitter_archive):
        """Verify the test archive exists and is a valid zip file."""
        assert os.path.exists(real_twitter_archive), "Twitter archive test file not found"
        
        # Verify it's a valid zip file
        with zipfile.ZipFile(real_twitter_archive, 'r') as zip_file:
            file_list = zip_file.namelist()
            
        # Should contain tweets.js
        tweets_files = [f for f in file_list if f.endswith('tweets.js')]
        assert len(tweets_files) > 0, "Archive should contain tweets.js file"
        
        # Should contain tweets.js (correct filename)
        correct_tweets_files = [f for f in file_list if f.endswith('tweets.js')]
        assert len(correct_tweets_files) > 0, "Archive should contain tweets.js (correct filename)"

    def test_archive_structure_analysis(self, real_twitter_archive):
        """Analyze the structure of the real Twitter archive."""
        with zipfile.ZipFile(real_twitter_archive, 'r') as zip_file:
            file_list = zip_file.namelist()
            
            # Find tweets.js file
            tweets_files = [f for f in file_list if f.endswith('tweets.js')]
            tweets_file = tweets_files[0]
            
            # Read and analyze content
            with zip_file.open(tweets_file) as f:
                content = f.read().decode('utf-8')
                
            # Should start with the expected JavaScript wrapper
            assert content.startswith("window.YTD.tweets.part0 = ["), \
                "tweets.js should start with expected JavaScript wrapper"
                
            # Extract JSON data
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            json_content = content[json_start:json_end]
            
            tweets_data = json.loads(json_content)
            
            # Archive should contain tweets
            assert len(tweets_data) > 0, "Archive should contain tweet data"
            assert isinstance(tweets_data[0], dict), "Tweet data should be objects"
            assert 'tweet' in tweets_data[0], "Each item should have 'tweet' key"

    @pytest.mark.asyncio
    async def test_twitter_source_configuration(self, twitter_config):
        """Test Twitter source configuration for archive imports."""
        # Should be configured for archive import even without API credentials
        assert twitter_config.enabled is True
        assert twitter_config.is_configured() is True
        assert twitter_config.is_api_configured() is False
        
        # API-only operations should fail gracefully
        assert twitter_config.bearer_token is None
        assert twitter_config.username is None

    @pytest.mark.asyncio  
    async def test_parse_real_twitter_archive(self, twitter_source, real_twitter_archive):
        """Test parsing tweets from the real Twitter archive."""
        # Create temporary extraction directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract archive
            with zipfile.ZipFile(real_twitter_archive, 'r') as zip_file:
                zip_file.extractall(temp_dir)
            
            # Find tweets.js file
            tweets_js_path = None
            for root, dirs, files in os.walk(temp_dir):
                if 'tweets.js' in files:
                    tweets_js_path = os.path.join(root, 'tweets.js')
                    break
                    
            assert tweets_js_path is not None, "Should find tweets.js in extracted archive"
            
            # Read and parse tweets
            with open(tweets_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Remove JavaScript wrapper  
            if 'window.YTD.tweets.part0 = [' in content:
                content = content.split('window.YTD.tweets.part0 = [', 1)[1]
                content = content.rsplit(']', 1)[0]
                
            raw_tweets = json.loads(f'[{content}]')
            
            # Parse tweets using TwitterSource
            parsed_tweets = twitter_source._parse_tweets(raw_tweets)
            
            # Verify parsing results
            assert len(parsed_tweets) > 0, "Should parse tweets from archive"
            assert len(parsed_tweets) == len(raw_tweets), "Should parse all tweets"
            
            # Check parsed tweet structure
            sample_tweet = parsed_tweets[0]
            required_fields = ['tweet_id', 'text', 'created_at', 'days_date', 'media_urls']
            for field in required_fields:
                assert field in sample_tweet, f"Parsed tweet should have {field} field"
                
            # Verify data types
            assert isinstance(sample_tweet['tweet_id'], str)
            assert isinstance(sample_tweet['text'], str) 
            assert isinstance(sample_tweet['created_at'], str)
            assert isinstance(sample_tweet['days_date'], str)
            assert isinstance(sample_tweet['media_urls'], str)  # JSON string

    @pytest.mark.asyncio
    async def test_import_from_zip_success(self, twitter_source, real_twitter_archive, temp_db):
        """Test successful import from ZIP archive."""
        # Mock the database methods to avoid actual storage
        with patch.object(twitter_source, '_get_existing_tweet_ids', 
                         return_value=set()):
            with patch.object(twitter_source, '_store_tweets_in_database',
                             return_value=None):
                with patch.object(twitter_source.ingestion_service, 'ingest_items',
                                 new_callable=AsyncMock) as mock_ingest:
                    mock_ingest.return_value = {
                        "items_processed": 100,
                        "items_stored": 100,
                        "success": True
                    }
                    
                    # Perform import
                    result = await twitter_source.import_from_zip(real_twitter_archive)
                    
                    # Verify success
                    assert result["success"] is True
                    assert result["imported_count"] > 0
                    assert "imported successfully" in result["message"].lower()

    @pytest.mark.asyncio 
    async def test_import_with_deduplication(self, twitter_source, real_twitter_archive):
        """Test import with existing tweets (deduplication)."""
        # First, get some tweet IDs from the archive
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(real_twitter_archive, 'r') as zip_file:
                zip_file.extractall(temp_dir)
                
            # Find and read tweets
            tweets_js_path = None
            for root, dirs, files in os.walk(temp_dir):
                if 'tweets.js' in files:
                    tweets_js_path = os.path.join(root, 'tweets.js')
                    break
                    
            with open(tweets_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'window.YTD.tweets.part0 = [' in content:
                content = content.split('window.YTD.tweets.part0 = [', 1)[1] 
                content = content.rsplit(']', 1)[0]
                
            raw_tweets = json.loads(f'[{content}]')
            parsed_tweets = twitter_source._parse_tweets(raw_tweets)
            
            # Get some existing tweet IDs
            existing_ids = {parsed_tweets[0]['tweet_id'], parsed_tweets[1]['tweet_id']}
            
        # Mock existing tweets in database
        with patch.object(twitter_source, '_get_existing_tweet_ids',
                         return_value=existing_ids):
            with patch.object(twitter_source, '_store_tweets_in_database',
                             return_value=None):
                with patch.object(twitter_source.ingestion_service, 'ingest_items',
                                 new_callable=AsyncMock) as mock_ingest:
                    mock_ingest.return_value = {
                        "items_processed": len(parsed_tweets) - len(existing_ids),
                        "items_stored": len(parsed_tweets) - len(existing_ids),
                        "success": True
                    }
                    
                    result = await twitter_source.import_from_zip(real_twitter_archive)
                    
                    # Should skip existing tweets
                    assert result["success"] is True
                    expected_new_count = len(parsed_tweets) - len(existing_ids)
                    assert result["imported_count"] == expected_new_count

    @pytest.mark.asyncio
    async def test_import_no_new_tweets(self, twitter_source, real_twitter_archive):
        """Test import when all tweets already exist."""
        # Mock all tweets as existing
        with patch.object(twitter_source, '_parse_tweets') as mock_parse:
            sample_tweets = [
                {'tweet_id': '123', 'text': 'test1', 'created_at': '2024-01-01T12:00:00+00:00',
                 'days_date': '2024-01-01', 'media_urls': '[]'},
                {'tweet_id': '456', 'text': 'test2', 'created_at': '2024-01-01T13:00:00+00:00', 
                 'days_date': '2024-01-01', 'media_urls': '[]'}
            ]
            mock_parse.return_value = sample_tweets
            
            existing_ids = {'123', '456'}  # All tweets exist
            
            with patch.object(twitter_source, '_get_existing_tweet_ids',
                             return_value=existing_ids):
                result = await twitter_source.import_from_zip(real_twitter_archive)
                
                # Should succeed but import nothing
                assert result["success"] is True
                assert result["imported_count"] == 0
                assert "no new tweets" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_import_disabled_source(self, temp_db, mock_ingestion_service):
        """Test import when Twitter source is disabled."""
        # Create disabled config
        disabled_config = TwitterConfig(
            enabled=False,  # Disabled
            bearer_token=None,
            username=None 
        )
        
        twitter_source = TwitterSource(disabled_config, temp_db, mock_ingestion_service)
        
        result = await twitter_source.import_from_zip("/path/to/any/file.zip")
        
        # Should fail with appropriate message
        assert result["success"] is False
        assert result["imported_count"] == 0
        assert "not enabled" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_import_invalid_zip(self, twitter_source, tmp_path):
        """Test import with invalid or corrupted zip file."""
        # Create invalid zip file
        invalid_zip = tmp_path / "invalid.zip"
        with open(invalid_zip, 'w') as f:
            f.write("This is not a zip file")
            
        # Should handle gracefully
        result = await twitter_source.import_from_zip(str(invalid_zip))
        assert result["success"] is False
        assert result["imported_count"] == 0

    @pytest.mark.asyncio
    async def test_import_zip_without_tweets(self, twitter_source, tmp_path):
        """Test import with zip that doesn't contain tweets.js."""
        # Create zip without tweets.js
        empty_zip = tmp_path / "empty.zip"
        with zipfile.ZipFile(empty_zip, 'w') as zip_file:
            zip_file.writestr("data/account.js", "window.YTD.account.part0 = []")
            zip_file.writestr("data/profile.js", "window.YTD.profile.part0 = []")
            
        result = await twitter_source.import_from_zip(str(empty_zip))
        
        # Should fail with appropriate error
        assert result["success"] is False
        assert result["imported_count"] == 0 
        assert "tweets.js" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_database_integration(self, twitter_config, real_twitter_archive):
        """Test full database integration during import."""
        # Use real database (in-memory)
        db = DatabaseService(':memory:')
        mock_ingestion = MagicMock(spec=IngestionService)
        mock_ingestion.ingest_items = AsyncMock()
        
        twitter_source = TwitterSource(twitter_config, db, mock_ingestion)
        
        # Mock only the ingestion part to focus on database operations
        with patch.object(twitter_source.ingestion_service, 'ingest_items',
                         new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = {
                "items_processed": 10,
                "items_stored": 10,
                "success": True
            }
            
            # Import should succeed
            result = await twitter_source.import_from_zip(real_twitter_archive)
            assert result["success"] is True
            
            # Verify ingestion service was called
            mock_ingest.assert_called_once()
            call_args = mock_ingest.call_args[1]  # Get keyword arguments
            data_items = call_args['items']
            
            # Verify DataItems structure
            assert len(data_items) > 0
            sample_item = data_items[0]
            assert sample_item.namespace == "twitter"
            assert sample_item.source_id is not None
            assert sample_item.content is not None
            assert sample_item.days_date is not None

    def test_file_cleanup_after_import(self, twitter_source, real_twitter_archive):
        """Test that temporary files are cleaned up after import."""
        temp_dir = "twitter_data"
        
        async def run_import():
            try:
                # Mock to avoid actual processing but still test cleanup
                with patch.object(twitter_source, '_parse_tweets', return_value=[]):
                    with patch.object(twitter_source, '_get_existing_tweet_ids', 
                                     return_value=set()):
                        await twitter_source.import_from_zip(real_twitter_archive)
            except Exception:
                pass  # We just want to test cleanup
        
        # Run import
        asyncio.run(run_import())
        
        # Temporary directory should be cleaned up
        assert not os.path.exists(temp_dir), "Temporary directory should be cleaned up"

    @pytest.mark.asyncio
    async def test_error_handling_during_parsing(self, twitter_source, real_twitter_archive):
        """Test error handling when tweet parsing fails."""
        # Mock parsing to raise exception
        with patch.object(twitter_source, '_parse_tweets', 
                         side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
            result = await twitter_source.import_from_zip(real_twitter_archive)
            
            # Should handle error gracefully
            assert result["success"] is False
            assert result["imported_count"] == 0
            assert "error" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_database_error_handling(self, twitter_source, real_twitter_archive):
        """Test error handling when database operations fail."""
        # Mock database operation to fail
        with patch.object(twitter_source, '_get_existing_tweet_ids',
                         side_effect=Exception("Database error")):
            result = await twitter_source.import_from_zip(real_twitter_archive)
            
            # Should handle error gracefully
            assert result["success"] is False
            assert result["imported_count"] == 0

    def test_tweet_data_validation(self, twitter_source, real_twitter_archive):
        """Test validation of parsed tweet data structure."""
        # Extract and parse a few tweets to validate structure
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(real_twitter_archive, 'r') as zip_file:
                zip_file.extractall(temp_dir)
                
            tweets_js_path = None
            for root, dirs, files in os.walk(temp_dir):
                if 'tweets.js' in files:
                    tweets_js_path = os.path.join(root, 'tweets.js')
                    break
                    
            with open(tweets_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'window.YTD.tweets.part0 = [' in content:
                content = content.split('window.YTD.tweets.part0 = [', 1)[1]
                content = content.rsplit(']', 1)[0]
                
            # Parse just first few tweets for validation
            raw_tweets = json.loads(f'[{content}]')[:5]  
            parsed_tweets = twitter_source._parse_tweets(raw_tweets)
            
            for tweet in parsed_tweets:
                # Required fields
                assert 'tweet_id' in tweet
                assert 'text' in tweet
                assert 'created_at' in tweet
                assert 'days_date' in tweet
                assert 'media_urls' in tweet
                
                # Data type validation
                assert isinstance(tweet['tweet_id'], str)
                assert isinstance(tweet['text'], str)
                assert isinstance(tweet['created_at'], str)
                assert isinstance(tweet['days_date'], str)
                
                # Media URLs should be valid JSON string
                media_urls = json.loads(tweet['media_urls'])
                assert isinstance(media_urls, list)
                
                # Date format validation
                from datetime import datetime
                datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                
                # Days date should be YYYY-MM-DD format
                assert len(tweet['days_date']) == 10
                assert tweet['days_date'][4] == '-'
                assert tweet['days_date'][7] == '-'


class TestTwitterImportEndToEnd:
    """End-to-end tests for complete Twitter import workflow."""

    @pytest.fixture 
    def integration_config(self):
        """Configuration for end-to-end testing."""
        return TwitterConfig(
            enabled=True,
            bearer_token=None,
            username=None,
            delete_after_import=True,  # Test cleanup
            sync_interval_hours=24
        )

    @pytest.mark.asyncio
    async def test_complete_import_workflow(self, integration_config, tmp_path):
        """Test the complete import workflow from zip to database."""
        # Setup real components
        db_path = tmp_path / "e2e_test.db" 
        db = DatabaseService(str(db_path))
        
        # Mock minimal ingestion service for E2E test
        ingestion = MagicMock(spec=IngestionService)
        ingestion.ingest_items = AsyncMock(return_value={
            "items_processed": 5,
            "items_stored": 5,
            "success": True
        })
        
        twitter_source = TwitterSource(integration_config, db, ingestion)
        
        # Use real archive
        archive_path = "/Users/brucebookman/code/new_lifeboard/tests/media/twitter-x.zip"
        
        # Perform complete import
        result = await twitter_source.import_from_zip(archive_path)
        
        # Verify end-to-end success
        assert result["success"] is True
        assert result["imported_count"] > 0
        
        # Verify ingestion was called with proper data
        ingestion.ingest_items.assert_called_once()
        
        # Verify DataItems were created correctly
        call_args = ingestion.ingest_items.call_args[1]
        items = call_args['items']
        
        assert len(items) > 0
        sample_item = items[0]
        assert sample_item.namespace == "twitter"
        assert sample_item.content is not None
        assert sample_item.days_date is not None

    @pytest.mark.asyncio
    async def test_performance_with_large_archive(self, integration_config):
        """Test performance characteristics with the full archive."""
        import time
        
        # Setup for performance test
        db = DatabaseService(':memory:')
        ingestion = MagicMock(spec=IngestionService) 
        ingestion.ingest_items = AsyncMock(return_value={
            "items_processed": 1000,
            "items_stored": 1000,
            "success": True
        })
        
        twitter_source = TwitterSource(integration_config, db, ingestion)
        archive_path = "/Users/brucebookman/code/new_lifeboard/tests/media/twitter-x.zip"
        
        # Time the import
        start_time = time.time()
        result = await twitter_source.import_from_zip(archive_path)
        end_time = time.time()
        
        import_duration = end_time - start_time
        
        # Performance assertions
        assert result["success"] is True
        assert import_duration < 60.0, f"Import took {import_duration:.2f}s, should be under 60s"
        
        # Log performance metrics
        print(f"\\nPerformance metrics:")
        print(f"Import duration: {import_duration:.2f}s")
        print(f"Tweets processed: {result['imported_count']}")
        if result['imported_count'] > 0:
            print(f"Processing rate: {result['imported_count'] / import_duration:.2f} tweets/sec")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])