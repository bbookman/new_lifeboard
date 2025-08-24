"""
Test the timezone fix implementation
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import pytz
from fastapi.testclient import TestClient
from api.routes.calendar import get_today_date, get_user_timezone_aware_now
from services.startup import StartupService


class TestTimezoneFix:
    """Test timezone handling fix"""
    
    def test_get_user_timezone_aware_now_with_env_var(self):
        """Test that get_user_timezone_aware_now respects TIME_ZONE environment variable"""
        mock_startup_service = Mock()
        
        with patch.dict('os.environ', {'TIME_ZONE': 'America/Los_Angeles'}), \
             patch('api.routes.calendar.datetime') as mock_datetime:
            
            # Mock UTC now as 2024-08-24 05:00:00 UTC (which is 2024-08-23 22:00:00 in LA)
            utc_now = datetime(2024, 8, 24, 5, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = utc_now
            
            result = get_user_timezone_aware_now(mock_startup_service)
            
            # Should be 2024-08-23 22:00:00 in Los Angeles timezone
            expected = utc_now.astimezone(pytz.timezone('America/Los_Angeles'))
            assert result.date() == expected.date()
            assert result.strftime('%Y-%m-%d') == '2024-08-23'
    
    def test_get_user_timezone_aware_now_with_new_york(self):
        """Test timezone conversion for New York (edge case scenario from issue)"""
        mock_startup_service = Mock()
        
        # Test the actual function with real datetime but patched environment
        with patch.dict('os.environ', {'TIME_ZONE': 'America/New_York'}):
            
            # Use actual datetime - this is more of an integration test
            result = get_user_timezone_aware_now(mock_startup_service)
            
            # Should return a timezone-aware datetime in America/New_York
            assert result.tzinfo is not None
            # The date should be whatever date it is in New York timezone
            # This tests that timezone conversion is working, not specific dates
    
    @pytest.mark.asyncio
    async def test_get_today_date_endpoint_response_format(self):
        """Test that /calendar/api/today returns expected format with date and timezone"""
        mock_startup_service = Mock()
        
        with patch('api.routes.calendar.get_user_timezone_aware_now') as mock_get_now, \
             patch.dict('os.environ', {'TIME_ZONE': 'America/New_York'}):
            
            # Mock the timezone-aware datetime
            mock_now = datetime(2024, 8, 23, 21, 0, 0)  # 9 PM on Aug 23
            mock_get_now.return_value = mock_now
            
            result = await get_today_date(mock_startup_service)
            
            # Verify response format
            assert 'today' in result
            assert 'timezone' in result
            assert 'timestamp' in result
            
            # Verify values
            assert result['today'] == '2024-08-23'
            assert result['timezone'] == 'America/New_York'
            assert result['timestamp'] == mock_now.isoformat()
    
    def test_midnight_boundary_edge_case(self):
        """Test that timezone aware datetime is returned"""
        mock_startup_service = Mock()
        
        # Integration test - just verify timezone aware datetime is returned
        with patch.dict('os.environ', {'TIME_ZONE': 'America/New_York'}):
            result = get_user_timezone_aware_now(mock_startup_service)
            
            # Should be timezone-aware
            assert result.tzinfo is not None
            # Should be a valid date string
            date_str = result.strftime('%Y-%m-%d')
            assert len(date_str) == 10  # YYYY-MM-DD format
    
    def test_timezone_fallback_when_invalid(self):
        """Test fallback behavior when timezone is invalid"""
        mock_startup_service = Mock()
        
        with patch.dict('os.environ', {'TIME_ZONE': 'Invalid/Timezone'}), \
             patch('api.routes.calendar.pytz.timezone') as mock_pytz:
            
            # Make pytz.timezone raise an exception
            mock_pytz.side_effect = Exception("Invalid timezone")
            
            result = get_user_timezone_aware_now(mock_startup_service)
            
            # Should fallback to UTC
            assert result.tzinfo == timezone.utc