import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone


class LoggingConfig:
    """Centralized logging configuration for the Lifeboard application"""
    
    def __init__(
        self,
        log_level: str = "INFO",
        log_file_path: str = "logs/lifeboard.log",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        log_format: Optional[str] = None,
        console_logging: bool = True,
        include_correlation_ids: bool = False
    ):
        """
        Initialize logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file_path: Path to the log file
            max_file_size: Maximum size per log file in bytes
            backup_count: Number of backup files to keep
            log_format: Custom log format string
            console_logging: Whether to also log to console
            include_correlation_ids: Whether to include correlation ID support
        """
        self.log_level = log_level.upper()
        self.log_file_path = log_file_path
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.console_logging = console_logging
        self.include_correlation_ids = include_correlation_ids
        
        # Default format includes timestamp, logger name, level, and message
        self.log_format = log_format or (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate logging configuration parameters"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of: {valid_levels}")
        
        if self.max_file_size <= 0:
            raise ValueError("max_file_size must be positive")
        
        if self.backup_count <= 0:
            raise ValueError("backup_count must be positive")
    
    def setup_logging(self) -> Dict[str, Any]:
        """
        Set up centralized logging for the entire application.
        
        Returns:
            Dictionary with setup results and configuration details
        """
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path(self.log_file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Get root logger
            root_logger = logging.getLogger()
            
            # Clear any existing handlers to avoid duplicates
            root_logger.handlers.clear()
            
            # Set logging level
            root_logger.setLevel(getattr(logging, self.log_level))
            
            # Create formatter
            formatter = logging.Formatter(
                fmt=self.log_format,
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            
            # Set up rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=self.log_file_path,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(getattr(logging, self.log_level))
            root_logger.addHandler(file_handler)
            
            # Set up console handler if enabled
            if self.console_logging:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                console_handler.setLevel(getattr(logging, self.log_level))
                root_logger.addHandler(console_handler)
            
            # Log the successful setup
            setup_logger = logging.getLogger("logging_config")
            setup_logger.info(
                f"Centralized logging initialized - Level: {self.log_level}, "
                f"File: {self.log_file_path}, Max Size: {self.max_file_size/1024/1024:.1f}MB, "
                f"Backups: {self.backup_count}, Console: {self.console_logging}"
            )
            
            # Build handlers list for test compatibility
            handlers_configured = []
            for handler in root_logger.handlers:
                if hasattr(handler, 'maxBytes'):  # RotatingFileHandler (check this first)
                    handlers_configured.append("file")
                elif hasattr(handler, 'stream'):  # Console handler
                    handlers_configured.append("console")
                else:
                    handlers_configured.append("other")
            
            return {
                "success": True,
                "log_level": self.log_level,
                "log_file_path": self.log_file_path,
                "max_file_size": self.max_file_size,
                "backup_count": self.backup_count,
                "console_logging": self.console_logging,
                "handlers_count": len(root_logger.handlers),
                "handlers_configured": handlers_configured
            }
            
        except Exception as e:
            # Fallback to basic logging if setup fails
            logging.basicConfig(
                level=logging.WARNING,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            
            fallback_logger = logging.getLogger("logging_config")
            fallback_logger.error(f"Failed to set up centralized logging: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "fallback_active": True
            }
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module or service.
        
        Args:
            name: Logger name (typically __name__ of the module)
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)
    
    def add_correlation_id_filter(self):
        """
        Add a filter to include correlation IDs in log messages.
        This is useful for tracing operations across services.
        """
        class CorrelationFilter(logging.Filter):
            def filter(self, record):
                # Add correlation ID from context if available
                # This can be enhanced later with async context or thread-local storage
                correlation_id = getattr(record, 'correlation_id', None)
                if correlation_id:
                    record.msg = f"[{correlation_id}] {record.msg}"
                return True
        
        # Apply filter to all handlers
        root_logger = logging.getLogger()
        correlation_filter = CorrelationFilter()
        
        for handler in root_logger.handlers:
            handler.addFilter(correlation_filter)
    
    def log_system_info(self):
        """Log system information and configuration at startup"""
        info_logger = logging.getLogger("system")
        info_logger.info(f"Lifeboard application starting - {datetime.now(timezone.utc).isoformat()}")
        info_logger.info(f"Python logging configured - Level: {self.log_level}")
        info_logger.info(f"Log file location: {os.path.abspath(self.log_file_path)}")
        info_logger.info(f"Log rotation: {self.max_file_size/1024/1024:.1f}MB per file, {self.backup_count} backups")


def setup_application_logging(
    log_level: str = "INFO",
    log_file_path: str = "logs/lifeboard.log",
    max_file_size: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console_logging: bool = True,
    include_correlation_ids: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to set up logging for the entire application.
    
    Args:
        log_level: Logging level
        log_file_path: Path to log file
        max_file_size: Maximum file size in bytes
        backup_count: Number of backup files
        console_logging: Enable console logging
        include_correlation_ids: Add correlation ID support
        
    Returns:
        Setup results dictionary
    """
    try:
        config = LoggingConfig(
            log_level=log_level,
            log_file_path=log_file_path,
            max_file_size=max_file_size,
            backup_count=backup_count,
            console_logging=console_logging,
            include_correlation_ids=include_correlation_ids
        )
        
        result = config.setup_logging()
        
        if result["success"] and include_correlation_ids:
            config.add_correlation_id_filter()
            result["correlation_ids_enabled"] = True
        else:
            result["correlation_ids_enabled"] = False
        
        if result["success"]:
            config.log_system_info()
        
        return result
        
    except Exception as e:
        # Fallback to basic logging if setup fails
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        fallback_logger = logging.getLogger("logging_config")
        fallback_logger.error(f"Failed to set up centralized logging: {e}")
        
        return {
            "success": False,
            "error": str(e),
            "fallback_active": True,
            "correlation_ids_enabled": False
        }


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module or service.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)