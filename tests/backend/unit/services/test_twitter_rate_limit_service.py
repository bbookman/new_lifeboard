import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from services.twitter_rate_limit_service import TwitterRateLimitService
from core.database import DatabaseService


@pytest.fixture
def mock_db_service():
    """Mock database service for testing"""
    mock_db = AsyncMock()
    # Add the methods we need for TwitterRateLimitService
    mock_db.fetch_one = AsyncMock()
    mock_db.execute_query = AsyncMock()
    return mock_db


@pytest.fixture
def rate_limit_service(mock_db_service):
    """TwitterRateLimitService instance for testing"""
    return TwitterRateLimitService(mock_db_service)


class TestTwitterRateLimitService:
    """Test suite for TwitterRateLimitService"""
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_db_service):
        """Test service initialization"""
        service = TwitterRateLimitService(mock_db_service)
        assert service.db_service == mock_db_service
        assert service.rate_limit_minutes == 15
        assert service.twitter_namespace == "twitter"
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_can_fetch_now_no_previous_fetch(self, rate_limit_service, mock_db_service):
        """Test can_fetch_now when no previous fetch exists"""
        mock_db_service.fetch_one.return_value = None
        
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        
        assert can_fetch is True
        assert minutes_until == 0
        mock_db_service.fetch_one.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_can_fetch_now_within_rate_limit(self, rate_limit_service, mock_db_service):
        """Test can_fetch_now when within rate limit window"""
        # Set last fetch to 5 minutes ago
        last_fetch_time = datetime.utcnow() - timedelta(minutes=5)
        mock_db_service.fetch_one.return_value = {
            'last_synced': last_fetch_time.isoformat()
        }
        
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        
        assert can_fetch is False
        assert minutes_until > 0
        assert minutes_until <= 11  # Should be around 10-11 minutes
    
    @pytest.mark.asyncio
    async def test_can_fetch_now_rate_limit_expired(self, rate_limit_service, mock_db_service):
        """Test can_fetch_now when rate limit has expired"""
        # Set last fetch to 20 minutes ago
        last_fetch_time = datetime.utcnow() - timedelta(minutes=20)
        mock_db_service.fetch_one.return_value = {
            'last_synced': last_fetch_time.isoformat()
        }
        
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        
        assert can_fetch is True
        assert minutes_until == 0
    
    @pytest.mark.asyncio
    async def test_can_fetch_now_database_error(self, rate_limit_service, mock_db_service):
        """Test can_fetch_now handles database errors gracefully"""
        mock_db_service.fetch_one.side_effect = Exception("Database error")
        
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        
        # Should allow fetch on error to avoid blocking the system
        assert can_fetch is True
        assert minutes_until == 0
    
    @pytest.mark.asyncio
    async def test_record_fetch_attempt_success(self, rate_limit_service, mock_db_service):
        """Test recording successful fetch attempt"""
        await rate_limit_service.record_fetch_attempt(success=True)
        
        mock_db_service.execute_query.assert_called_once()
        call_args = mock_db_service.execute_query.call_args
        assert "UPDATE data_sources" in call_args[0][0]
        assert call_args[0][1][1] == "twitter"  # namespace parameter
    
    @pytest.mark.asyncio
    async def test_record_fetch_attempt_failure(self, rate_limit_service, mock_db_service):
        """Test recording failed fetch attempt doesn't update rate limit"""
        await rate_limit_service.record_fetch_attempt(success=False)
        
        # Failed fetches should not count against rate limits
        mock_db_service.execute_query.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_today(self, rate_limit_service, mock_db_service):
        """Test getting status for today's date"""
        last_fetch_time = datetime.utcnow() - timedelta(minutes=5)
        mock_db_service.fetch_one.return_value = {
            'last_synced': last_fetch_time.isoformat()
        }
        
        today = datetime.utcnow().strftime('%Y-%m-%d')
        status = await rate_limit_service.get_status_for_day(today)
        
        assert status is not None
        assert status['type'] == 'active'
        assert status['icon'] == '🔄'
        assert 'minutes or less' in status['status']
        assert 'minutes_until_next' in status
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_old_date(self, rate_limit_service, mock_db_service):
        """Test getting status for old date shows complete"""
        last_fetch_time = datetime.utcnow() - timedelta(minutes=5)
        mock_db_service.fetch_one.return_value = {
            'last_synced': last_fetch_time.isoformat()
        }
        
        old_date = (datetime.utcnow() - timedelta(days=5)).strftime('%Y-%m-%d')
        status = await rate_limit_service.get_status_for_day(old_date)
        
        assert status is not None
        assert status['type'] == 'complete'
        assert status['icon'] == '✅'
        assert 'Data complete' in status['status']
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_no_previous_fetch(self, rate_limit_service, mock_db_service):
        """Test getting status when no previous fetch exists"""
        mock_db_service.fetch_one.return_value = None
        
        today = datetime.utcnow().strftime('%Y-%m-%d')
        status = await rate_limit_service.get_status_for_day(today)
        
        assert status is None
    
    @pytest.mark.asyncio
    async def test_format_time_ago(self, rate_limit_service):
        """Test time formatting function"""
        now = datetime.utcnow()
        
        # Test just now
        recent_time = now - timedelta(seconds=30)
        assert rate_limit_service._format_time_ago(recent_time) == "just now"
        
        # Test minutes
        minutes_ago = now - timedelta(minutes=5)
        assert rate_limit_service._format_time_ago(minutes_ago) == "5 min ago"
        
        # Test hours
        hours_ago = now - timedelta(hours=2)
        assert rate_limit_service._format_time_ago(hours_ago) == "2h ago"
        
        # Test days
        days_ago = now - timedelta(days=3)
        assert rate_limit_service._format_time_ago(days_ago) == "3d ago"
    
    @pytest.mark.asyncio
    async def test_get_status_for_day_database_error(self, rate_limit_service, mock_db_service):
        """Test get_status_for_day handles database errors gracefully"""
        mock_db_service.fetch_one.side_effect = Exception("Database error")
        
        today = datetime.utcnow().strftime('%Y-%m-%d')
        status = await rate_limit_service.get_status_for_day(today)
        
        assert status is None


class TestTwitterRateLimitIntegration:
    """Integration tests for Twitter rate limiting"""
    
    @pytest.mark.asyncio
    async def test_fifteen_minute_rate_limit_cycle(self, rate_limit_service, mock_db_service):
        """Test complete 15-minute rate limit cycle"""
        # Initially can fetch
        mock_db_service.fetch_one.return_value = None
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        assert can_fetch is True
        
        # After successful fetch, should be rate limited
        current_time = datetime.utcnow()
        mock_db_service.fetch_one.return_value = {
            'last_synced': current_time.isoformat()
        }
        
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        assert can_fetch is False
        assert minutes_until > 0
        
        # After 15+ minutes, should be able to fetch again
        old_time = current_time - timedelta(minutes=16)
        mock_db_service.fetch_one.return_value = {
            'last_synced': old_time.isoformat()
        }
        
        can_fetch, minutes_until = await rate_limit_service.can_fetch_now()
        assert can_fetch is True
        assert minutes_until == 0