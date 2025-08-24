import os
import tempfile
import logging
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from pathlib import Path

from services.startup import StartupService
from config.factory import create_test_config
from config.models import AppConfig, LoggingConfig


class TestStartupServiceLoggingIntegration:
    """Test startup service integration with centralized logging"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_log_file = os.path.join(self.temp_dir, "startup_test.log")
        
        # Reset logging state
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
    
    def teardown_method(self):
        """Clean up test environment"""
        # Reset logging
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        
        # Clean up temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_startup_service_initializes_logging_first(self):
        """Test that startup service initializes logging before other services"""
        # Create config with test logging settings
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        config.logging.console_logging = False
        config.logging.level = "DEBUG"
        
        startup_service = StartupService(config)
        
        # Mock other services to focus on logging
        with patch('services.startup.DatabaseService') as mock_db, \
             patch('services.startup.EmbeddingService') as mock_embed, \
             patch('services.startup.VectorStoreService') as mock_vector:
            
            # Run startup
            result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Check that logging was initialized successfully
        assert result["success"] is True
        assert "logging" in result["services_initialized"]
        assert startup_service.logging_setup_result is not None
        assert startup_service.logging_setup_result["success"] is True
        
        # Verify log file was created and contains initialization messages
        assert os.path.exists(self.temp_log_file)
        
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "Centralized logging system initialized successfully" in content
            assert "Starting application initialization" in content
    
    def test_startup_service_logging_configuration_applied(self):
        """Test that logging configuration is properly applied"""
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        config.logging.console_logging = False
        config.logging.level = "INFO"
        config.logging.include_correlation_ids = True
        
        startup_service = StartupService(config)
        
        with patch('services.startup.DatabaseService'), \
             patch('services.startup.EmbeddingService'), \
             patch('services.startup.VectorStoreService'):
            
            result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Test that a logger from any service uses the configured settings
        test_logger = logging.getLogger("test_service")
        test_logger.info("Test message from service")
        
        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # Check that the message appears in the log file
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "Test message from service" in content
            assert "test_service" in content
    
    def test_startup_service_logging_failure_fallback(self):
        """Test startup service handles logging initialization failure gracefully"""
        config = create_test_config()
        # Set an invalid log file path that should fail
        config.logging.file_path = "/root/impossible_path.log"
        
        startup_service = StartupService(config)
        
        with patch('services.startup.DatabaseService'), \
             patch('services.startup.EmbeddingService'), \
             patch('services.startup.VectorStoreService'):
            
            result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Application should still succeed even if logging setup fails
        assert result["success"] is True  # Core services still work
        assert len(result["errors"]) > 0  # But there should be logging errors
        
        # Logging setup should have failed
        assert startup_service.logging_setup_result is not None
        assert startup_service.logging_setup_result["success"] is False
    
    def test_startup_service_status_includes_logging_details(self):
        """Test that application status includes logging information"""
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        config.logging.console_logging = False
        
        startup_service = StartupService(config)
        
        with patch('services.startup.DatabaseService'), \
             patch('services.startup.EmbeddingService'), \
             patch('services.startup.VectorStoreService'):
            
            asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Get application status
        status = startup_service.get_application_status()
        
        # Should include logging service status
        assert "logging" in status["services"]
        assert status["services"]["logging"] is True
        
        # Should include logging details
        assert "logging_details" in status
        assert status["logging_details"]["success"] is True
        assert status["logging_details"]["log_file_path"] == self.temp_log_file
    
    def test_multiple_services_use_centralized_logging(self):
        """Test that all services use the centralized logging configuration"""
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        config.logging.console_logging = False
        config.logging.level = "DEBUG"
        
        startup_service = StartupService(config)
        
        # Mock services but let them create loggers
        mock_db = MagicMock()
        mock_embed = MagicMock()
        mock_vector = MagicMock()
        
        with patch('services.startup.DatabaseService', return_value=mock_db), \
             patch('services.startup.EmbeddingService', return_value=mock_embed), \
             patch('services.startup.VectorStoreService', return_value=mock_vector):
            
            result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Simulate logging from different services
        db_logger = logging.getLogger("core.database")
        scheduler_logger = logging.getLogger("services.scheduler")
        ingestion_logger = logging.getLogger("services.ingestion")
        
        db_logger.info("Database service message")
        scheduler_logger.debug("Scheduler service debug")
        ingestion_logger.warning("Ingestion service warning")
        
        # Force flush all handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # All messages should appear in the same log file
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "Database service message" in content
            assert "Scheduler service debug" in content
            assert "Ingestion service warning" in content
            assert "core.database" in content
            assert "services.scheduler" in content
            assert "services.ingestion" in content
    
    def test_logging_respects_level_configuration(self):
        """Test that logging level configuration is respected"""
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        config.logging.console_logging = False
        config.logging.level = "WARNING"  # Only WARNING and above
        
        startup_service = StartupService(config)
        
        with patch('services.startup.DatabaseService'), \
             patch('services.startup.EmbeddingService'), \
             patch('services.startup.VectorStoreService'):
            
            result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Test different log levels
        test_logger = logging.getLogger("test_levels")
        test_logger.debug("This debug should not appear")
        test_logger.info("This info should not appear")
        test_logger.warning("This warning should appear")
        test_logger.error("This error should appear")
        
        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # Check what appears in the log
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "This debug should not appear" not in content
            assert "This info should not appear" not in content
            assert "This warning should appear" in content
            assert "This error should appear" in content
    
    def test_startup_logging_with_auto_sync_disabled(self):
        """Test startup logging when auto-sync is disabled"""
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        config.logging.console_logging = False
        
        startup_service = StartupService(config)
        
        with patch('services.startup.DatabaseService'), \
             patch('services.startup.EmbeddingService'), \
             patch('services.startup.VectorStoreService'):
            
            result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        assert result["success"] is True
        
        # Check that logging initialization is mentioned but sync services are not
        with open(self.temp_log_file, 'r') as f:
            content = f.read()
            assert "Centralized logging system initialized successfully" in content
            assert "Starting application initialization" in content
            # Should not have sync-related messages since auto_sync=False
            assert result.get("auto_sync_enabled") is False
    
    def test_startup_logging_error_handling(self):
        """Test that startup continues even if logging has issues"""
        config = create_test_config()
        config.logging.file_path = self.temp_log_file
        
        startup_service = StartupService(config)
        
        # Mock the logging setup to fail
        with patch('services.startup.setup_application_logging') as mock_setup:
            mock_setup.side_effect = Exception("Logging setup failed")
            
            with patch('services.startup.DatabaseService'), \
                 patch('services.startup.EmbeddingService'), \
                 patch('services.startup.VectorStoreService'):
                
                result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        # Application should still succeed (core functionality)
        # But logging errors should be recorded
        assert len(result["errors"]) > 0
        assert any("logging" in error.lower() for error in result["errors"])


class TestStartupServiceLoggingEnvironmentVariables:
    """Test startup service with environment variable logging configuration"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_log_file = os.path.join(self.temp_dir, "env_test.log")
        
        # Reset logging state
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
    
    def teardown_method(self):
        """Clean up test environment"""
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_startup_with_environment_logging_config(self):
        """Test startup service with logging configured via environment variables"""
        env_vars = {
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE_PATH": self.temp_log_file,
            "LOG_CONSOLE_LOGGING": "false",
            "LOG_INCLUDE_CORRELATION_IDS": "true"
        }
        
        with patch.dict(os.environ, env_vars):
            # Create config that should pick up environment variables
            config = create_test_config()
            # In a real scenario, the factory would read these env vars
            config.logging.level = os.getenv("LOG_LEVEL", "INFO")
            config.logging.file_path = os.getenv("LOG_FILE_PATH", "logs/test.log")
            config.logging.console_logging = os.getenv("LOG_CONSOLE_LOGGING", "true").lower() == "true"
            config.logging.include_correlation_ids = os.getenv("LOG_INCLUDE_CORRELATION_IDS", "false").lower() == "true"
            
            startup_service = StartupService(config)
            
            with patch('services.startup.DatabaseService'), \
                 patch('services.startup.EmbeddingService'), \
                 patch('services.startup.VectorStoreService'):
                
                result = asyncio.run(startup_service.initialize_application(enable_auto_sync=False))
        
        assert result["success"] is True
        assert startup_service.logging_setup_result["success"] is True
        
        # Verify the environment configuration was applied
        assert startup_service.logging_setup_result["log_level"] == "DEBUG"
        assert startup_service.logging_setup_result["correlation_ids_enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])