"""
Tests for ServiceDebugMixin - Enhanced debug logging for services.

This module tests the service debug extensions that provide comprehensive
logging and monitoring capabilities for service operations.
"""

import pytest
import time
import logging
from unittest.mock import Mock, patch, MagicMock
import psutil
from services.debug_mixin import ServiceDebugMixin


class TestServiceDebugMixin:
    """Test cases for ServiceDebugMixin functionality."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mixin = ServiceDebugMixin("test_service")
        
    def test_initialization(self):
        """Test ServiceDebugMixin initialization."""
        # Test basic initialization
        mixin = ServiceDebugMixin("test_service")
        assert mixin.service_name == "test_service"
        assert hasattr(mixin, 'debug')
        assert hasattr(mixin, 'performance_logger')
        
    def test_initialization_with_different_service_names(self):
        """Test initialization with various service names."""
        service_names = ["database", "http_client", "embedding_service"]
        
        for name in service_names:
            mixin = ServiceDebugMixin(name)
            assert mixin.service_name == name
            
    def test_log_service_call_basic(self):
        """Test basic service call logging."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                # Mock psutil data
                mock_process.return_value.memory_info.return_value.rss = 104857600  # 100MB
                mock_process.return_value.cpu_percent.return_value = 15.5
                
                self.mixin.log_service_call("test_method")
                
                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                
                # Verify log message
                assert "SERVICE_CALL test_service.test_method" in call_args[0][0]
                
                # Verify extra data
                extra_data = call_args[1]['extra']
                assert extra_data['service'] == "test_service"
                assert extra_data['method'] == "test_method"
                assert 'memory_mb' in extra_data
                assert 'cpu_percent' in extra_data
                assert 'timestamp' in extra_data
                
    def test_log_service_call_with_params(self):
        """Test service call logging with parameters."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 52428800  # 50MB
                mock_process.return_value.cpu_percent.return_value = 25.0
                
                params = {"user_id": 123, "action": "fetch"}
                self.mixin.log_service_call("get_user_data", params)
                
                call_args = mock_logger.call_args[1]['extra']
                assert call_args['params'] == params
                
    def test_log_service_call_empty_params(self):
        """Test service call logging with empty parameters."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 52428800
                mock_process.return_value.cpu_percent.return_value = 10.0
                
                self.mixin.log_service_call("test_method", {})
                
                call_args = mock_logger.call_args[1]['extra']
                assert call_args['params'] == {}
                
    def test_log_service_call_none_params(self):
        """Test service call logging with None parameters."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 52428800
                mock_process.return_value.cpu_percent.return_value = 5.0
                
                self.mixin.log_service_call("test_method", None)
                
                call_args = mock_logger.call_args[1]['extra']
                assert call_args['params'] == {}
                
    def test_log_service_call_memory_calculation(self):
        """Test memory calculation in service call logging."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                # Test with specific memory value (200MB)
                mock_process.return_value.memory_info.return_value.rss = 209715200
                mock_process.return_value.cpu_percent.return_value = 30.0
                
                self.mixin.log_service_call("memory_test")
                
                call_args = mock_logger.call_args[1]['extra']
                assert call_args['memory_mb'] == 200.0
                
    def test_log_service_call_cpu_percentage(self):
        """Test CPU percentage logging in service calls."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 52428800
                mock_process.return_value.cpu_percent.return_value = 45.75
                
                self.mixin.log_service_call("cpu_test")
                
                call_args = mock_logger.call_args[1]['extra']
                assert call_args['cpu_percent'] == 45.75
                
    def test_log_database_operation_basic(self):
        """Test basic database operation logging."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            self.mixin.log_database_operation("SELECT", "users", 150.5)
            
            mock_logger.assert_called_once()
            call_args = mock_logger.call_args
            
            # Verify log message
            assert "DB_OPERATION SELECT" in call_args[0][0]
            
            # Verify extra data
            extra_data = call_args[1]['extra']
            assert extra_data['service'] == "test_service"
            assert extra_data['operation'] == "SELECT"
            assert extra_data['table'] == "users"
            assert extra_data['duration_ms'] == 150.5
            assert 'timestamp' in extra_data
            
    def test_log_database_operation_different_operations(self):
        """Test database operation logging with different operations."""
        operations = [
            ("INSERT", "orders", 250.0),
            ("UPDATE", "products", 75.25),
            ("DELETE", "logs", 50.0),
            ("CREATE INDEX", "users", 1500.75)
        ]
        
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            for operation, table, duration in operations:
                self.mixin.log_database_operation(operation, table, duration)
                
            assert mock_logger.call_count == len(operations)
            
            # Check last call details
            last_call = mock_logger.call_args[1]['extra']
            assert last_call['operation'] == "CREATE INDEX"
            assert last_call['table'] == "users"
            assert last_call['duration_ms'] == 1500.75
            
    def test_log_database_operation_zero_duration(self):
        """Test database operation logging with zero duration."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            self.mixin.log_database_operation("SELECT", "cache", 0.0)
            
            extra_data = mock_logger.call_args[1]['extra']
            assert extra_data['duration_ms'] == 0.0
            
    def test_log_external_api_call_basic(self):
        """Test basic external API call logging."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            self.mixin.log_external_api_call("weather_api", "/forecast", 200, 500.0)
            
            mock_logger.assert_called_once()
            call_args = mock_logger.call_args
            
            # Verify log message
            assert "API_CALL weather_api" in call_args[0][0]
            
            # Verify extra data
            extra_data = call_args[1]['extra']
            assert extra_data['service'] == "test_service"
            assert extra_data['api'] == "weather_api"
            assert extra_data['endpoint'] == "/forecast"
            assert extra_data['status_code'] == 200
            assert extra_data['duration_ms'] == 500.0
            assert 'timestamp' in extra_data
            
    def test_log_external_api_call_different_status_codes(self):
        """Test API call logging with different status codes."""
        status_codes = [200, 201, 400, 404, 500, 503]
        
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            for status_code in status_codes:
                self.mixin.log_external_api_call("test_api", "/test", status_code, 100.0)
                
            assert mock_logger.call_count == len(status_codes)
            
    def test_log_external_api_call_various_endpoints(self):
        """Test API call logging with various endpoints."""
        endpoints = ["/users", "/api/v1/data", "/health", "/auth/login"]
        
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            for endpoint in endpoints:
                self.mixin.log_external_api_call("api", endpoint, 200, 150.0)
                
            # Check last call
            last_call = mock_logger.call_args[1]['extra']
            assert last_call['endpoint'] == "/auth/login"
            
    def test_log_external_api_call_timing_variation(self):
        """Test API call logging with different timing values."""
        timings = [10.0, 250.5, 1500.75, 5000.0]
        
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            for timing in timings:
                self.mixin.log_external_api_call("timing_api", "/test", 200, timing)
                
            # Check calls were made with correct timing
            calls = mock_logger.call_args_list
            for i, timing in enumerate(timings):
                assert calls[i][1]['extra']['duration_ms'] == timing
                
    def test_log_service_call_psutil_error_handling(self):
        """Test service call logging handles psutil errors gracefully."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process', side_effect=psutil.NoSuchProcess(123)):
                # Should not raise exception
                self.mixin.log_service_call("test_method")
                
                # Should still log, but with None/default values for metrics
                mock_logger.assert_called_once()
                
    def test_timestamp_accuracy(self):
        """Test that timestamps are reasonably accurate."""
        with patch.object(self.mixin.performance_logger, 'debug') as mock_logger:
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 52428800
                mock_process.return_value.cpu_percent.return_value = 10.0
                
                before_time = time.time()
                self.mixin.log_service_call("timestamp_test")
                after_time = time.time()
                
                call_args = mock_logger.call_args[1]['extra']
                logged_timestamp = call_args['timestamp']
                
                # Timestamp should be between before and after
                assert before_time <= logged_timestamp <= after_time
                
    def test_multiple_instances_independence(self):
        """Test that multiple ServiceDebugMixin instances are independent."""
        mixin1 = ServiceDebugMixin("service1")
        mixin2 = ServiceDebugMixin("service2")
        
        assert mixin1.service_name != mixin2.service_name
        assert mixin1.debug != mixin2.debug
        
    def test_logger_configuration(self):
        """Test that loggers are properly configured."""
        mixin = ServiceDebugMixin("config_test")
        
        # Debug logger should be configured with correct name
        assert mixin.debug.module_name == "service.config_test"
        
        # Performance logger should be properly initialized
        assert mixin.performance_logger.name == "performance"


class TestServiceDebugMixinIntegration:
    """Integration tests for ServiceDebugMixin with real logging."""
    
    def test_actual_logging_output(self, caplog):
        """Test actual logging output with caplog."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 104857600
                mock_process.return_value.cpu_percent.return_value = 20.0
                
                mixin = ServiceDebugMixin("integration_test")
                mixin.log_service_call("test_method", {"param": "value"})
                
        # Check that log was actually created
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert "SERVICE_CALL integration_test.test_method" in log_record.message
        
    def test_database_logging_output(self, caplog):
        """Test database operation logging output."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            mixin = ServiceDebugMixin("db_test")
            mixin.log_database_operation("SELECT", "users", 123.45)
            
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert "DB_OPERATION SELECT" in log_record.message
        
    def test_api_call_logging_output(self, caplog):
        """Test API call logging output."""
        with caplog.at_level(logging.DEBUG, logger="performance"):
            mixin = ServiceDebugMixin("api_test")
            mixin.log_external_api_call("weather", "/forecast", 200, 300.0)
            
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert "API_CALL weather" in log_record.message


@pytest.fixture
def mock_psutil_process():
    """Fixture to mock psutil.Process with default values."""
    with patch('psutil.Process') as mock_process:
        mock_process.return_value.memory_info.return_value.rss = 52428800  # 50MB
        mock_process.return_value.cpu_percent.return_value = 15.0
        yield mock_process


class TestServiceDebugMixinWithFixtures:
    """Test ServiceDebugMixin using fixtures."""
    
    def test_with_mock_psutil(self, mock_psutil_process):
        """Test using the mock psutil fixture."""
        mixin = ServiceDebugMixin("fixture_test")
        
        with patch.object(mixin.performance_logger, 'debug') as mock_logger:
            mixin.log_service_call("test_with_fixture")
            
            extra_data = mock_logger.call_args[1]['extra']
            assert extra_data['memory_mb'] == 50.0
            assert extra_data['cpu_percent'] == 15.0