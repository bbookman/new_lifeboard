"""
Integration test for WeatherService with Enhanced Debug Logging.
"""

import pytest
import logging
from unittest.mock import Mock

from services.weather_service import WeatherService


class TestWeatherServiceIntegration:
    """Integration tests for WeatherService debug logging."""

    def test_weather_service_basic_functionality(self, caplog):
        """Test that WeatherService maintains original functionality with debug logging."""
        # Create mock dependencies (without db_path to avoid DebugDatabaseConnection)
        mock_db_service = Mock()
        # Explicitly remove db_path attribute to ensure graceful fallback
        if hasattr(mock_db_service, 'db_path'):
            delattr(mock_db_service, 'db_path')
        
        mock_config = Mock()
        mock_config.weather = Mock()
        mock_config.weather.units = 'metric'
        
        # Mock database response
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No weather data
        mock_conn.execute.return_value = mock_cursor
        
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_db_service.get_connection.return_value = mock_context
        
        # Create service and verify logging works
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(mock_db_service, mock_config)
            
            # Test method call
            result = weather_service.get_latest_weather()
        
        # Verify functionality
        assert result is None  # No data returned as expected
        assert hasattr(weather_service, 'service_name')
        assert weather_service.service_name == "weather_service"
        
        # Verify logging occurred
        log_messages = [record.message for record in caplog.records]
        assert any("SERVICE_CALL" in msg for msg in log_messages)

    def test_weather_service_preserves_original_api(self):
        """Test that WeatherService API is preserved after refactoring."""
        mock_db_service = Mock()
        mock_config = Mock()
        mock_config.weather = Mock()
        mock_config.weather.units = 'metric'
        
        weather_service = WeatherService(mock_db_service, mock_config)
        
        # Verify all original methods are still available
        assert hasattr(weather_service, 'get_latest_weather')
        assert hasattr(weather_service, 'get_weather_by_date')
        assert hasattr(weather_service, 'get_weather_for_specific_date')
        assert hasattr(weather_service, 'get_weather_for_date_range')
        assert hasattr(weather_service, 'parse_weather_data')
        
        # Verify enhanced debug capabilities added
        assert hasattr(weather_service, 'log_service_call')
        assert hasattr(weather_service, 'log_database_operation')
        assert hasattr(weather_service, 'log_service_performance_metric')
        assert hasattr(weather_service, 'get_service_health_metrics')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])