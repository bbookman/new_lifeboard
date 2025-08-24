import os
import tempfile
import logging
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from core.logging_config import LoggingConfig, setup_application_logging
from config.models import LoggingConfig as PydanticLoggingConfig


class TestLoggingConfigClass:
    """Test the LoggingConfig class functionality"""
    
    def test_logging_config_initialization_with_defaults(self):
        """Test LoggingConfig initialization with default values"""
        config = LoggingConfig()
        
        assert config.log_level == "INFO"
        assert config.log_file_path == "logs/lifeboard.log"
        assert config.max_file_size == 10 * 1024 * 1024  # 10MB
        assert config.backup_count == 5
        assert config.console_logging is True
        assert config.include_correlation_ids is False
    
    def test_logging_config_initialization_with_custom_values(self):
        """Test LoggingConfig initialization with custom values"""
        config = LoggingConfig(
            log_level="DEBUG",
            log_file_path="custom/path.log",
            max_file_size=5 * 1024 * 1024,
            backup_count=3,
            console_logging=False,
            include_correlation_ids=True
        )
        
        assert config.log_level == "DEBUG"
        assert config.log_file_path == "custom/path.log"
        assert config.max_file_size == 5 * 1024 * 1024
        assert config.backup_count == 3
        assert config.console_logging is False
        assert config.include_correlation_ids is True
    
    def test_logging_config_invalid_log_level(self):
        """Test LoggingConfig with invalid log level"""
        with pytest.raises(ValueError, match="Invalid log level"):
            LoggingConfig(log_level="INVALID")
    
    def test_logging_config_negative_file_size(self):
        """Test LoggingConfig with negative file size"""
        with pytest.raises(ValueError, match="max_file_size must be positive"):
            LoggingConfig(max_file_size=-1)
    
    def test_logging_config_zero_backup_count(self):
        """Test LoggingConfig with zero backup count"""
        with pytest.raises(ValueError, match="backup_count must be positive"):
            LoggingConfig(backup_count=0)


class TestSetupApplicationLogging:
    """Test the setup_application_logging function"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_log_file = os.path.join(self.temp_dir, "test.log")
    
    def teardown_method(self):
        """Clean up test environment"""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        
        # Clean up temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_setup_application_logging_success(self):
        """Test successful logging setup"""
        result = setup_application_logging(
            log_level="INFO",
            log_file_path=self.temp_log_file,
            max_file_size=1024 * 1024,
            backup_count=3,
            console_logging=True
        )
        
        assert result["success"] is True
        assert result["log_file_path"] == self.temp_log_file
        assert result["log_level"] == "INFO"
        assert "handlers_configured" in result
        assert len(result["handlers_configured"]) >= 1
    
    def test_setup_application_logging_creates_directory(self):
        """Test that logging setup creates log directory"""
        nested_log_file = os.path.join(self.temp_dir, "nested", "test.log")
        
        result = setup_application_logging(
            log_level="DEBUG",
            log_file_path=nested_log_file
        )
        
        assert result["success"] is True
        assert os.path.exists(os.path.dirname(nested_log_file))
    
    def test_setup_application_logging_with_console_disabled(self):
        """Test logging setup with console logging disabled"""
        result = setup_application_logging(
            log_level="INFO",
            log_file_path=self.temp_log_file,
            console_logging=False
        )
        
        assert result["success"] is True
        # Should have only file handler
        handlers = result["handlers_configured"]
        assert len(handlers) == 1
        assert "file" in handlers[0].lower()
    
    def test_setup_application_logging_with_correlation_ids(self):
        """Test logging setup with correlation IDs enabled"""
        result = setup_application_logging(
            log_level="INFO",
            log_file_path=self.temp_log_file,
            include_correlation_ids=True
        )
        
        assert result["success"] is True
        assert result["correlation_ids_enabled"] is True
    
    def test_setup_application_logging_invalid_log_level(self):
        """Test logging setup with invalid log level"""
        result = setup_application_logging(
            log_level="INVALID",
            log_file_path=self.temp_log_file
        )
        
        assert result["success"] is False
        assert "Invalid log level" in result["error"]
    
    def test_setup_application_logging_permission_error(self):
        """Test logging setup with permission error"""
        # Try to write to a read-only directory
        readonly_file = "/root/readonly.log"  # This should fail on most systems
        
        result = setup_application_logging(
            log_level="INFO",
            log_file_path=readonly_file
        )
        
        # Should gracefully handle the error
        assert result["success"] is False
        assert "error" in result
    
    def test_logging_actually_works(self):
        """Test that logging actually writes to file"""
        result = setup_application_logging(
            log_level="DEBUG",
            log_file_path=self.temp_log_file,
            console_logging=False
        )
        
        assert result["success"] is True
        
        # Test that logging works
        test_logger = logging.getLogger("test_logger")
        test_message = "Test log message for verification"
        test_logger.info(test_message)
        
        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # Check file contents
        assert os.path.exists(self.temp_log_file)
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert test_message in content
            assert "test_logger" in content
    
    def test_log_rotation_configuration(self):
        """Test that log rotation is properly configured"""
        result = setup_application_logging(
            log_level="INFO",
            log_file_path=self.temp_log_file,
            max_file_size=1024,  # 1KB for easy testing
            backup_count=2
        )
        
        assert result["success"] is True
        
        # Get the rotating file handler
        root_logger = logging.getLogger()
        file_handler = None
        for handler in root_logger.handlers:
            if hasattr(handler, 'maxBytes'):
                file_handler = handler
                break
        
        assert file_handler is not None
        assert file_handler.maxBytes == 1024
        assert file_handler.backupCount == 2


class TestPydanticLoggingConfig:
    """Test the Pydantic LoggingConfig model"""
    
    def test_pydantic_logging_config_defaults(self):
        """Test Pydantic LoggingConfig with defaults"""
        config = PydanticLoggingConfig()
        
        assert config.level == "INFO"
        assert config.file_path == "logs/lifeboard.log"
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5
        assert config.console_logging is True
        assert config.include_correlation_ids is False
    
    def test_pydantic_logging_config_validation(self):
        """Test Pydantic LoggingConfig validation"""
        # Test valid config
        config = PydanticLoggingConfig(
            level="DEBUG",
            file_path="test.log",
            max_file_size=1024,
            backup_count=1
        )
        assert config.level == "DEBUG"
        
        # Test invalid log level
        with pytest.raises(ValueError):
            PydanticLoggingConfig(level="INVALID")
        
        # Test invalid file size
        with pytest.raises(ValueError):
            PydanticLoggingConfig(max_file_size=0)
        
        # Test invalid backup count
        with pytest.raises(ValueError):
            PydanticLoggingConfig(backup_count=-1)
    
    def test_pydantic_environment_variable_integration(self):
        """Test that Pydantic config can load from environment variables"""
        env_vars = {
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE_PATH": "env_test.log",
            "LOG_MAX_FILE_SIZE": "5242880",  # 5MB
            "LOG_BACKUP_COUNT": "3",
            "LOG_CONSOLE_LOGGING": "false",
            "LOG_INCLUDE_CORRELATION_IDS": "true"
        }
        
        with patch.dict(os.environ, env_vars):
            # This would typically be tested in integration with config factory
            config = PydanticLoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                file_path=os.getenv("LOG_FILE_PATH", "logs/lifeboard.log"),
                max_file_size=int(os.getenv("LOG_MAX_FILE_SIZE", "10485760")),
                backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
                console_logging=os.getenv("LOG_CONSOLE_LOGGING", "true").lower() == "true",
                include_correlation_ids=os.getenv("LOG_INCLUDE_CORRELATION_IDS", "false").lower() == "true"
            )
            
            assert config.level == "DEBUG"
            assert config.file_path == "env_test.log"
            assert config.max_file_size == 5242880
            assert config.backup_count == 3
            assert config.console_logging is False
            assert config.include_correlation_ids is True


class TestLoggingIntegration:
    """Test logging integration scenarios"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_log_file = os.path.join(self.temp_dir, "integration.log")
    
    def teardown_method(self):
        """Clean up test environment"""
        # Reset logging
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        
        # Clean up temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_multiple_loggers_use_same_config(self):
        """Test that multiple loggers use the same centralized config"""
        result = setup_application_logging(
            log_level="DEBUG",
            log_file_path=self.temp_log_file,
            console_logging=False
        )
        
        assert result["success"] is True
        
        # Create multiple loggers
        logger1 = logging.getLogger("service1")
        logger2 = logging.getLogger("service2")
        logger3 = logging.getLogger("service3.submodule")
        
        # Log messages from different loggers
        logger1.info("Message from service1")
        logger2.error("Error from service2")
        logger3.debug("Debug from service3.submodule")
        
        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # Check that all messages are in the same log file
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "service1" in content
            assert "service2" in content
            assert "service3.submodule" in content
            assert "Message from service1" in content
            assert "Error from service2" in content
            assert "Debug from service3.submodule" in content
    
    def test_log_level_filtering(self):
        """Test that log level filtering works correctly"""
        result = setup_application_logging(
            log_level="WARNING",
            log_file_path=self.temp_log_file,
            console_logging=False
        )
        
        assert result["success"] is True
        
        logger = logging.getLogger("test_filtering")
        
        # Log messages at different levels
        logger.debug("This should not appear")
        logger.info("This should not appear either")
        logger.warning("This should appear")
        logger.error("This should also appear")
        
        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # Check file contents
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "This should not appear" not in content
            assert "This should appear" in content
            assert "This should also appear" in content
    
    def test_logging_with_system_info(self):
        """Test that system info is logged when enabled"""
        result = setup_application_logging(
            log_level="INFO",
            log_file_path=self.temp_log_file,
            console_logging=False
        )
        
        assert result["success"] is True
        
        # Check that system info was logged during setup
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            # Should contain system information
            assert any(keyword in content.lower() for keyword in ["python", "platform", "logging", "initialized"])
    
    def test_fallback_logging_on_error(self):
        """Test fallback logging behavior when setup fails"""
        # Test with invalid configuration that should trigger fallback
        with patch('core.logging_config.logging.basicConfig') as mock_basic_config:
            result = setup_application_logging(
                log_level="INVALID_LEVEL",
                log_file_path="/invalid/path/that/cannot/be/created.log"
            )
            
            assert result["success"] is False
            # Should have attempted to set up basic logging as fallback
            mock_basic_config.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])