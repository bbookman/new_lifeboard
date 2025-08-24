"""
Enhanced logging configuration for Lifeboard cleanup and refactoring.

This module provides comprehensive logging setup including:
- Multiple log handlers for different purposes
- JSON and detailed formatters
- Rotating file handlers with size management
- Separate loggers for debug, refactor tracking, and performance

Usage:
    from core.enhanced_logging_config import setup_debug_logging
    setup_debug_logging()
"""

import logging.config
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


def setup_debug_logging(
    log_dir: str = "logs",
    debug_level: str = "DEBUG",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> None:
    """
    Setup enhanced debug logging configuration for the cleanup process.
    
    Args:
        log_dir: Directory to store log files
        debug_level: Minimum log level for debug logs
        max_file_size: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to also output logs to console
    """
    # Ensure log directory exists
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Create logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'json': {
                'format': '%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(pathname)s:%(lineno)d',
                'class': 'pythonjsonlogger.json.JsonFormatter'
            },
            'simple': {
                'format': '%(asctime)s | %(levelname)-8s | %(message)s',
                'datefmt': '%H:%M:%S'
            },
            'performance': {
                'format': '%(asctime)s | PERF | %(name)s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'debug_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': str(log_path / 'debug.log'),
                'maxBytes': max_file_size,
                'backupCount': backup_count,
                'formatter': 'json',
                'level': debug_level,
                'encoding': 'utf-8'
            },
            'refactor_tracking': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': str(log_path / 'refactor_tracking.log'),
                'maxBytes': max_file_size // 2,  # 5MB
                'backupCount': 3,
                'formatter': 'detailed',
                'level': 'INFO',
                'encoding': 'utf-8'
            },
            'performance': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': str(log_path / 'performance.log'),
                'maxBytes': max_file_size // 2,  # 5MB
                'backupCount': 3,
                'formatter': 'performance',
                'level': 'DEBUG',
                'encoding': 'utf-8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': str(log_path / 'errors.log'),
                'maxBytes': max_file_size // 4,  # 2.5MB
                'backupCount': 5,
                'formatter': 'detailed',
                'level': 'ERROR',
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            'debug': {
                'handlers': ['debug_file'],
                'level': debug_level,
                'propagate': False
            },
            'refactor': {
                'handlers': ['refactor_tracking'],
                'level': 'INFO',
                'propagate': False
            },
            'performance': {
                'handlers': ['performance'],
                'level': 'DEBUG',
                'propagate': False
            },
            'error': {
                'handlers': ['error_file'],
                'level': 'ERROR',
                'propagate': False
            }
        }
    }
    
    # Add console handler if requested
    if console_output:
        config['handlers']['console'] = {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'INFO',
            'stream': 'ext://sys.stdout'
        }
        
        # Add console to debug logger
        config['loggers']['debug']['handlers'].append('console')
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Log configuration success
    logger = logging.getLogger('refactor')
    logger.info(f"Enhanced logging configured", extra={
        'log_directory': str(log_path.absolute()),
        'debug_level': debug_level,
        'max_file_size_mb': max_file_size // (1024 * 1024),
        'backup_count': backup_count,
        'console_output': console_output,
        'timestamp': datetime.utcnow().isoformat()
    })


def setup_component_logging(component_name: str, level: str = "DEBUG") -> logging.Logger:
    """
    Setup logging for a specific component with standardized configuration.
    
    Args:
        component_name: Name of the component (e.g., 'process_manager', 'signal_handler')
        level: Log level for this component
        
    Returns:
        Configured logger for the component
    """
    logger_name = f"debug.{component_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    
    # If debug logging hasn't been setup, do basic configuration
    if not logger.handlers and not logging.getLogger('debug').handlers:
        setup_debug_logging()
    
    return logger


def get_refactor_logger() -> logging.Logger:
    """
    Get the refactor tracking logger.
    
    Returns:
        Logger configured for refactor milestone tracking
    """
    return logging.getLogger('refactor')


def get_performance_logger() -> logging.Logger:
    """
    Get the performance monitoring logger.
    
    Returns:
        Logger configured for performance metrics
    """
    return logging.getLogger('performance')


def log_cleanup_milestone(milestone: str, data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a cleanup milestone with standardized format.
    
    Args:
        milestone: Description of the milestone
        data: Optional additional data
    """
    refactor_logger = get_refactor_logger()
    refactor_logger.info(f"CLEANUP_MILESTONE: {milestone}", extra={
        'milestone': milestone,
        'data': data or {},
        'timestamp': datetime.utcnow().isoformat()
    })


def log_performance_metric(component: str, metric: str, value: float, unit: str = "ms") -> None:
    """
    Log a performance metric with standardized format.
    
    Args:
        component: Component being measured
        metric: Name of the metric
        value: Measured value
        unit: Unit of measurement
    """
    perf_logger = get_performance_logger()
    perf_logger.info(f"METRIC: {component}.{metric}", extra={
        'component': component,
        'metric': metric,
        'value': value,
        'unit': unit,
        'timestamp': datetime.utcnow().isoformat()
    })


class LoggingContext:
    """
    Context manager for enhanced logging during specific operations.
    
    Usage:
        with LoggingContext("api_server_refactor") as ctx:
            ctx.log_step("Starting ProcessManager extraction")
            # perform work
            ctx.log_metric("extraction_time", 1500, "ms")
    """
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.refactor_logger = get_refactor_logger()
        self.performance_logger = get_performance_logger()
        
    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.refactor_logger.info(f"OPERATION_START: {self.operation_name}", extra={
            'operation': self.operation_name,
            'start_time': self.start_time.isoformat()
        })
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds() * 1000  # ms
        
        if exc_type is None:
            self.refactor_logger.info(f"OPERATION_SUCCESS: {self.operation_name}", extra={
                'operation': self.operation_name,
                'duration_ms': duration,
                'end_time': end_time.isoformat()
            })
        else:
            self.refactor_logger.error(f"OPERATION_FAILED: {self.operation_name}", extra={
                'operation': self.operation_name,
                'duration_ms': duration,
                'error_type': exc_type.__name__ if exc_type else None,
                'error_message': str(exc_val) if exc_val else None,
                'end_time': end_time.isoformat()
            })
    
    def log_step(self, step_description: str, data: Optional[Dict[str, Any]] = None):
        """Log a step within the operation."""
        self.refactor_logger.info(f"STEP: {step_description}", extra={
            'operation': self.operation_name,
            'step': step_description,
            'data': data or {},
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def log_metric(self, metric_name: str, value: float, unit: str = "ms"):
        """Log a performance metric for this operation."""
        self.performance_logger.info(f"METRIC: {self.operation_name}.{metric_name}", extra={
            'operation': self.operation_name,
            'metric': metric_name,
            'value': value,
            'unit': unit,
            'timestamp': datetime.utcnow().isoformat()
        })


def create_test_logging_config() -> Dict[str, Any]:
    """
    Create a logging configuration optimized for testing.
    
    Returns:
        Logging configuration dictionary for test environments
    """
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'test': {
                'format': '%(levelname)s | %(name)s | %(message)s'
            }
        },
        'handlers': {
            'test_console': {
                'class': 'logging.StreamHandler',
                'formatter': 'test',
                'level': 'WARNING'  # Only show warnings and errors during tests
            }
        },
        'loggers': {
            'debug': {
                'handlers': ['test_console'],
                'level': 'WARNING',
                'propagate': False
            },
            'refactor': {
                'handlers': ['test_console'],
                'level': 'WARNING',
                'propagate': False
            },
            'performance': {
                'handlers': ['test_console'],
                'level': 'ERROR',
                'propagate': False
            }
        }
    }


# Initialize logging when module is imported
if not os.environ.get('TESTING'):
    setup_debug_logging()