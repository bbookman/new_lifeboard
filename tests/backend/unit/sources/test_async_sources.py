"""
Tests for Phase 3 async source implementations
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from sources.twitter import TwitterSource
from sources.weather import WeatherSource
from sources.news import NewsSource
from config.models import TwitterConfig, WeatherConfig, NewsConfig


@pytest.mark.asyncio
class TestAsyncTwitterSource:
    """Test TwitterSource async database operations"""

    @pytest_asyncio.fixture
    async def mock_database(self):
        """Create mock async database service"""
        db = AsyncMock()
        db.async_get_data_items_by_namespace = AsyncMock(return_value=[
            {'source_id': 'tweet1', 'content': 'Test tweet 1', 'namespace': 'twitter', 'created_at': '2024-01-01T00:00:00Z'},
            {'source_id': 'tweet2', 'content': 'Test tweet 2', 'namespace': 'twitter', 'created_at': '2024-01-01T01:00:00Z'}
        ])
        db.async_get_data_items_by_date = AsyncMock(return_value=[
            {'source_id': 'tweet1', 'content': 'Test tweet 1', 'namespace': 'twitter', 'created_at': '2024-01-01T00:00:00Z'}
        ])
        db.async_get_data_items_by_ids = AsyncMock(return_value=[
            {'source_id': 'tweet1', 'content': 'Test tweet 1', 'namespace': 'twitter', 'metadata': '{}', 'created_at': '2024-01-01T00:00:00Z', 'updated_at': '2024-01-01T00:00:00Z'}
        ])
        return db

    @pytest.fixture
    def twitter_config(self):
        """Create Twitter configuration"""
        return TwitterConfig(
            enabled=True,
            bearer_token="test_token",
            username="testuser"
        )

    @pytest_asyncio.fixture
    async def twitter_source(self, twitter_config, mock_database):
        """Create TwitterSource instance"""
        return TwitterSource(twitter_config, mock_database)

    async def test_get_existing_tweet_ids_async(self, twitter_source, mock_database):
        """Test _get_existing_tweet_ids uses async database operations"""
        result = await twitter_source._get_existing_tweet_ids()
        
        mock_database.async_get_data_items_by_namespace.assert_called_once_with('twitter', limit=10000)
        assert result == {'tweet1', 'tweet2'}

    async def test_get_data_for_date_async(self, twitter_source, mock_database):
        """Test get_data_for_date uses async database operations"""
        result = await twitter_source.get_data_for_date('2024-01-01')
        
        mock_database.async_get_data_items_by_date.assert_called_once_with('2024-01-01', ['twitter'])
        assert len(result) == 1
        assert result[0]['source_id'] == 'tweet1'

    async def test_get_item_async(self, twitter_source, mock_database):
        """Test get_item uses async database operations"""
        result = await twitter_source.get_item('tweet1')
        
        mock_database.async_get_data_items_by_ids.assert_called_once_with(['twitter:tweet1'])
        assert result is not None
        assert result.source_id == 'tweet1'

    async def test_fetch_items_async(self, twitter_source, mock_database):
        """Test fetch_items uses async database operations"""
        items = []
        async for item in twitter_source.fetch_items(limit=10):
            items.append(item)
        
        mock_database.async_get_data_items_by_namespace.assert_called_once_with('twitter', 10)
        assert len(items) == 2


@pytest.mark.asyncio
class TestAsyncWeatherSource:
    """Test WeatherSource async database operations"""

    @pytest_asyncio.fixture
    async def mock_database(self):
        """Create mock async database service"""
        db = AsyncMock()
        
        # Mock connection context manager
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={'count': 1})
        mock_cursor.fetchall = AsyncMock(return_value=[
            {'response_json': '{"forecastDaily": {"readTime": "2024-01-01", "days": []}}'}
        ])
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        
        db.get_connection = AsyncMock()
        db.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.get_connection.return_value.__aexit__ = AsyncMock(return_value=None)
        
        return db

    @pytest.fixture
    def weather_config(self):
        """Create Weather configuration"""
        return WeatherConfig(
            enabled=True,
            api_key="test_key",
            endpoint="test.endpoint.com",
            latitude="40.7128",
            longitude="-74.0060",
            units="metric"
        )

    @pytest_asyncio.fixture
    async def weather_source(self, weather_config, mock_database):
        """Create WeatherSource instance"""
        return WeatherSource(weather_config, mock_database)

    async def test_has_weather_data_for_date_async(self, weather_source):
        """Test _has_weather_data_for_date uses async database operations"""
        result = await weather_source._has_weather_data_for_date('2024-01-01')
        
        assert result is True

    async def test_store_weather_data_async(self, weather_source, mock_database):
        """Test _store_weather_data uses async database operations"""
        test_data = {
            'forecastDaily': {
                'readTime': '2024-01-01',
                'days': []
            }
        }
        
        await weather_source._store_weather_data(test_data)
        
        # Verify async database operations were called
        mock_database.get_connection.assert_called_once()

    async def test_get_latest_weather_async(self, weather_source, mock_database):
        """Test get_latest_weather uses async database operations"""
        result = await weather_source.get_latest_weather(mock_database)
        
        mock_database.get_connection.assert_called_once()
        assert result is not None

    async def test_get_weather_by_date_async(self, weather_source, mock_database):
        """Test get_weather_by_date uses async database operations"""
        result = await weather_source.get_weather_by_date(mock_database, '2024-01-01')
        
        mock_database.get_connection.assert_called()
        assert result is not None

    async def test_get_weather_for_specific_date_async(self, weather_source, mock_database):
        """Test get_weather_for_specific_date uses async database operations"""
        result = await weather_source.get_weather_for_specific_date(mock_database, '2024-01-01')
        
        mock_database.get_connection.assert_called()

    async def test_get_weather_for_date_range_async(self, weather_source, mock_database):
        """Test get_weather_for_date_range uses async database operations"""
        result = await weather_source.get_weather_for_date_range(mock_database, '2024-01-01', 3)
        
        assert mock_database.get_connection.call_count >= 3  # Called for each date in range
        assert isinstance(result, list)


@pytest.mark.asyncio
class TestAsyncNewsSource:
    """Test NewsSource async database operations"""

    @pytest_asyncio.fixture
    async def mock_database(self):
        """Create mock async database service"""
        db = AsyncMock()
        
        # Mock connection context manager
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={'count': 2})
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                'id': 'news:1',
                'source_id': 'article1',
                'content': 'Test news article 1',
                'metadata': '{"title": "Test Article 1", "link": "http://test.com/1"}',
                'created_at': '2024-01-01T00:00:00Z',
                'days_date': '2024-01-01'
            },
            {
                'id': 'news:2',
                'source_id': 'article2',
                'content': 'Test news article 2',
                'metadata': '{"title": "Test Article 2", "link": "http://test.com/2"}',
                'created_at': '2024-01-01T01:00:00Z',
                'days_date': '2024-01-01'
            }
        ])
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        
        db.get_connection = AsyncMock()
        db.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.get_connection.return_value.__aexit__ = AsyncMock(return_value=None)
        
        return db

    @pytest.fixture
    def news_config(self):
        """Create News configuration"""
        return NewsConfig(
            enabled=True,
            api_key="test_key",
            endpoint="test.endpoint.com",
            country="US",
            language="en",
            unique_items_per_day=5,
            items_to_retrieve=20
        )

    @pytest_asyncio.fixture
    async def news_source(self, news_config, mock_database):
        """Create NewsSource instance"""
        return NewsSource(news_config, mock_database)

    async def test_has_news_data_for_date_async(self, news_source):
        """Test _has_news_data_for_date uses async database operations"""
        result = await news_source._has_news_data_for_date('2024-01-01')
        
        assert result is True

    async def test_get_news_by_date_async(self, news_source, mock_database):
        """Test get_news_by_date uses async database operations"""
        result = await news_source.get_news_by_date(mock_database, '2024-01-01')
        
        mock_database.get_connection.assert_called_once()
        assert len(result) == 2
        assert result[0]['title'] == 'Test Article 1'
        assert result[1]['title'] == 'Test Article 2'

    async def test_get_latest_news_async(self, news_source, mock_database):
        """Test get_latest_news uses async database operations"""
        result = await news_source.get_latest_news(mock_database, limit=10)
        
        mock_database.get_connection.assert_called_once()
        assert len(result) == 2
        assert all('title' in item for item in result)

    async def test_get_news_count_by_date_async(self, news_source, mock_database):
        """Test get_news_count_by_date uses async database operations"""
        result = await news_source.get_news_count_by_date(mock_database, '2024-01-01')
        
        mock_database.get_connection.assert_called_once()
        assert result == 2


@pytest.mark.asyncio
class TestAsyncSourceIntegration:
    """Integration tests for async source operations"""

    async def test_concurrent_source_operations(self):
        """Test concurrent async source operations don't interfere with each other"""
        # Mock database service
        mock_db = AsyncMock()
        mock_db.async_get_data_items_by_namespace = AsyncMock(return_value=[])
        mock_db.async_get_data_items_by_date = AsyncMock(return_value=[])
        mock_db.async_get_data_items_by_ids = AsyncMock(return_value=[])
        
        # Create source instances
        twitter_config = TwitterConfig(enabled=True, bearer_token="test", username="test")
        twitter_source = TwitterSource(twitter_config, mock_db)
        
        # Run concurrent operations
        tasks = [
            twitter_source._get_existing_tweet_ids(),
            twitter_source.get_data_for_date('2024-01-01'),
            twitter_source.get_item('test_tweet')
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all operations completed successfully
        assert len(results) == 3
        assert isinstance(results[0], set)  # _get_existing_tweet_ids returns set
        assert isinstance(results[1], list)  # get_data_for_date returns list
        
        # Verify async methods were called
        mock_db.async_get_data_items_by_namespace.assert_called()
        mock_db.async_get_data_items_by_date.assert_called()
        mock_db.async_get_data_items_by_ids.assert_called()

    async def test_async_error_handling(self):
        """Test async error handling in source operations"""
        mock_db = AsyncMock()
        mock_db.async_get_data_items_by_namespace.side_effect = Exception("Database error")
        
        twitter_config = TwitterConfig(enabled=True, bearer_token="test", username="test")
        twitter_source = TwitterSource(twitter_config, mock_db)
        
        # Verify exception is propagated correctly
        with pytest.raises(Exception, match="Database error"):
            await twitter_source._get_existing_tweet_ids()