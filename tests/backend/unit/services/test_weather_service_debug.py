"""
Test suite for WeatherService with Enhanced Debug Logging capabilities.
"""

import pytest
import logging
import tempfile
import os
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from services.weather_service import WeatherService
from services.debug_mixin import ServiceDebugMixin
from core.database_debug import DebugDatabaseConnection


class TestWeatherServiceDebugIntegration:
    """Test WeatherService enhanced debug logging integration."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_db_service = Mock()
        self.mock_config = Mock()
        self.mock_config.weather = Mock()
        self.mock_config.weather.units = 'metric'
        
        # For most tests, don't use DebugDatabaseConnection to avoid complications
        # Tests will explicitly set db_path when needed
        
        # Set up mock database connection
        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_conn.execute.return_value = self.mock_cursor
        
        # Set up context manager
        self.mock_context = Mock()
        self.mock_context.__enter__ = Mock(return_value=self.mock_conn)
        self.mock_context.__exit__ = Mock(return_value=False)
        self.mock_db_service.get_connection.return_value = self.mock_context

    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up any temp files created by individual tests
        if hasattr(self, 'temp_db') and self.temp_db and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_weather_service_inherits_debug_mixin(self):
        """Test that WeatherService properly inherits from ServiceDebugMixin."""
        weather_service = WeatherService(self.mock_db_service, self.mock_config)
        
        # Verify inheritance
        assert isinstance(weather_service, ServiceDebugMixin)
        assert hasattr(weather_service, 'log_service_call')
        assert hasattr(weather_service, 'log_database_operation')
        assert hasattr(weather_service, 'log_service_performance_metric')
        assert hasattr(weather_service, 'service_name')
        
        # Verify service name
        assert weather_service.service_name == "weather_service"

    def test_weather_service_debug_database_integration(self):
        """Test that WeatherService integrates DebugDatabaseConnection when available."""
        # Create temporary database for this test
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        self.temp_db = temp_db  # Store for cleanup
        
        self.mock_db_service.db_path = temp_db.name
        weather_service = WeatherService(self.mock_db_service, self.mock_config)
        
        # Should have debug_db when db_path is available
        assert weather_service.debug_db is not None
        assert isinstance(weather_service.debug_db, DebugDatabaseConnection)

    def test_weather_service_fallback_without_debug_db(self):
        """Test that WeatherService works without DebugDatabaseConnection."""
        # Remove db_path attribute
        delattr(self.mock_db_service, 'db_path')
        
        weather_service = WeatherService(self.mock_db_service, self.mock_config)
        
        # Should fallback gracefully
        assert weather_service.debug_db is None

    def test_initialization_logging(self, caplog):
        """Test that service initialization is logged with proper parameters."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(self.mock_db_service, self.mock_config)
        
        # Check for initialization log
        log_messages = [record.message for record in caplog.records]
        assert any("SERVICE_CALL weather_service.__init__" in msg for msg in log_messages)

    @patch('services.weather_service.time.time')
    def test_get_latest_weather_logging(self, mock_time, caplog):
        """Test that get_latest_weather method logs operations correctly."""
        # Mock time progression - provide more values to avoid StopIteration
        mock_time.side_effect = [1000.0, 1000.05, 1000.1, 1000.15, 1000.2, 1000.25, 1000.3, 1000.35]
        
        # Mock database response
        sample_weather_data = {
            'forecastDaily': {
                'reportedTime': '2024-01-15T12:00:00Z',
                'days': [
                    {
                        'forecastStart': '2024-01-15T06:00:00Z',
                        'temperatureMax': 20.0,
                        'temperatureMin': 10.0,
                        'conditionCode': 'PartlyCloudyDay'
                    }
                ]
            }
        }
        
        self.mock_cursor.fetchone.return_value = {
            'response_json': json.dumps(sample_weather_data)
        }
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(self.mock_db_service, self.mock_config)
            result = weather_service.get_latest_weather()
        
        # Verify method was called and returned data
        assert result is not None
        assert 'days' in result
        
        # Check logging output
        log_messages = [record.message for record in caplog.records]
        
        # Should log service call
        assert any("SERVICE_CALL weather_service.get_latest_weather" in msg for msg in log_messages)
        
        # Should log database operation
        assert any("DB_OPERATION SELECT" in msg and "weather" in msg for msg in log_messages)
        
        # Should log performance metrics
        metric_logs = [msg for msg in log_messages if "SERVICE_METRIC" in msg]
        assert len(metric_logs) >= 2  # parse_duration and weather_data_found metrics

    @patch('services.weather_service.time.time')
    def test_get_weather_by_date_logging(self, mock_time, caplog):
        """Test that get_weather_by_date method logs operations correctly."""
        mock_time.side_effect = [1000.0, 1000.05, 1000.1, 1000.15, 1000.2, 1000.25, 1000.3, 1000.35]
        
        # Mock exact match found
        sample_weather_data = {
            'forecastDaily': {
                'reportedTime': '2024-01-15T12:00:00Z',
                'days': [
                    {
                        'forecastStart': '2024-01-15T06:00:00Z',
                        'temperatureMax': 15.0,
                        'temperatureMin': 5.0,
                        'conditionCode': 'Clear'
                    }
                ]
            }
        }
        
        self.mock_cursor.fetchone.return_value = {
            'response_json': json.dumps(sample_weather_data)
        }
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(self.mock_db_service, self.mock_config)
            result = weather_service.get_weather_by_date("2024-01-15")
        
        # Verify result
        assert result is not None
        
        # Check logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log service call with parameters
        service_call_logs = [msg for msg in log_messages if "SERVICE_CALL weather_service.get_weather_by_date" in msg]
        assert len(service_call_logs) >= 1
        
        # Should log exact match success
        exact_match_logs = [msg for msg in log_messages if "weather_exact_match" in msg]
        assert len(exact_match_logs) >= 1

    def test_error_logging(self, caplog):
        """Test that service errors are logged with proper context."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(self.mock_db_service, self.mock_config)
            
            # Mock database error during get_connection
            self.mock_db_service.get_connection.side_effect = Exception("Database connection failed")
            
            with pytest.raises(Exception, match="Database connection failed"):
                weather_service.get_latest_weather()
        
        # Check error logging
        log_messages = [record.message for record in caplog.records]
        assert any("SERVICE_ERROR weather_service.get_latest_weather" in msg for msg in log_messages)

    def test_temperature_conversion_logging(self, caplog):
        """Test that temperature conversions are logged correctly."""
        # Set config to use Fahrenheit
        self.mock_config.weather.units = 'standard'
        
        sample_weather_data = {
            'forecastDaily': {
                'reportedTime': '2024-01-15T12:00:00Z',
                'days': [
                    {
                        'forecastStart': '2024-01-15T06:00:00Z',
                        'temperatureMax': 20.0,  # Celsius
                        'temperatureMin': 10.0,  # Celsius
                        'conditionCode': 'Clear'
                    }
                ]
            }
        }
        
        self.mock_cursor.fetchone.return_value = {
            'response_json': json.dumps(sample_weather_data)
        }
        
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(self.mock_db_service, self.mock_config)
            result = weather_service.get_latest_weather()
        
        # Verify temperature conversion
        assert result['days'][0]['temperatureMax'] == 68.0  # 20°C to °F
        assert result['days'][0]['temperatureMin'] == 50.0  # 10°C to °F
        
        # Check temperature conversion logging
        log_messages = [record.message for record in caplog.records]
        conversion_logs = [msg for msg in log_messages if "weather_temperature_conversions" in msg]
        assert len(conversion_logs) >= 1

    def test_date_range_logging(self, caplog):
        """Test that date range operations are logged with comprehensive metrics."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            weather_service = WeatherService(self.mock_db_service, self.mock_config)
            
            # Mock get_weather_for_specific_date to return data for some dates
            with patch.object(weather_service, 'get_weather_for_specific_date') as mock_specific:
                mock_specific.side_effect = [
                    {'forecast_date': '2024-01-15', 'temperatureMax': 20},  # Found
                    None,  # Not found
                    {'forecast_date': '2024-01-17', 'temperatureMax': 22},  # Found
                ]
                
                result = weather_service.get_weather_for_date_range("2024-01-15", 3)
        
        # Verify results
        assert len(result) == 2  # 2 out of 3 dates found
        
        # Check comprehensive logging
        log_messages = [record.message for record in caplog.records]
        
        # Should log range operation
        assert any("SERVICE_CALL weather_service.get_weather_for_date_range" in msg for msg in log_messages)
        
        # Should log success rate
        success_rate_logs = [msg for msg in log_messages if "weather_range_success_rate" in msg]
        assert len(success_rate_logs) >= 1

    def test_service_health_metrics(self):
        """Test that service health metrics are available."""
        weather_service = WeatherService(self.mock_db_service, self.mock_config)
        
        # Get health metrics
        health_metrics = weather_service.get_service_health_metrics()
        
        # Verify health metrics structure
        assert 'service' in health_metrics
        assert health_metrics['service'] == 'weather_service'
        assert 'status' in health_metrics
        assert 'timestamp' in health_metrics


class TestWeatherServicePerformanceImpact:
    """Test performance impact of debug logging in WeatherService."""

    def setup_method(self):
        """Set up performance test fixtures."""
        self.mock_db_service = Mock()
        self.mock_config = Mock()
        self.mock_config.weather = Mock()
        self.mock_config.weather.units = 'metric'
        
        # Don't set db_path to avoid DebugDatabaseConnection overhead
        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_conn.execute.return_value = self.mock_cursor
        
        self.mock_context = Mock()
        self.mock_context.__enter__ = Mock(return_value=self.mock_conn)
        self.mock_context.__exit__ = Mock(return_value=False)
        self.mock_db_service.get_connection.return_value = self.mock_context

    def test_logging_performance_overhead(self):
        """Test that debug logging has minimal performance impact."""
        import time
        
        # Mock successful database response
        sample_weather_data = {
            'forecastDaily': {
                'reportedTime': '2024-01-15T12:00:00Z',
                'days': [{'forecastStart': '2024-01-15T06:00:00Z', 'temperatureMax': 20.0}]
            }
        }
        
        self.mock_cursor.fetchone.return_value = {
            'response_json': json.dumps(sample_weather_data)
        }
        
        weather_service = WeatherService(self.mock_db_service, self.mock_config)
        
        # Benchmark method calls
        start_time = time.time()
        for _ in range(100):
            weather_service.get_latest_weather()
        duration = time.time() - start_time
        
        # Should complete 100 calls in reasonable time (< 1 second for mock operations)
        assert duration < 1.0, f"100 service calls took {duration:.3f}s - too slow"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])