"""
Debug logging infrastructure for Lifeboard cleanup refactoring.

This module provides comprehensive debugging capabilities including:
- Function entry/exit tracing with timing
- Component state logging
- Performance monitoring
- Error tracking with full context

Usage:
    debug = DebugLogger("component_name")
    
    @debug.trace_function()
    def my_function():
        debug.log_state("initialization", {"status": "starting"})
        # function implementation
"""

import logging
import json
import time
import traceback
from functools import wraps
from typing import Any, Dict, Optional, Callable
from datetime import datetime


class DebugLogger:
    """
    Enhanced debug logger for tracking component behavior during refactoring.
    
    Provides decorators and methods for comprehensive debugging including:
    - Function timing and tracing
    - State monitoring
    - Error context capture
    """
    
    def __init__(self, module_name: str):
        """
        Initialize debug logger for a specific module.
        
        Args:
            module_name: Name of the module/component being debugged
        """
        self.module_name = module_name
        self.logger = logging.getLogger(f"debug.{module_name}")
        self.logger.setLevel(logging.DEBUG)
        
    def trace_function(self, func_name: Optional[str] = None) -> Callable:
        """
        Decorator to trace function entry/exit with timing and error handling.
        
        Args:
            func_name: Optional custom name for the function (defaults to module.function)
            
        Returns:
            Decorated function with tracing capabilities
            
        Example:
            @debug.trace_function("custom_name")
            def my_function(arg1, arg2):
                return result
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                name = func_name or f"{func.__module__}.{func.__name__}"
                
                # Log function entry
                self.logger.debug(f"ENTER {name}", extra={
                    'function': name,
                    'module': self.module_name,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()),
                    'timestamp': datetime.utcnow().isoformat(),
                    'thread_id': self._get_thread_id()
                })
                
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Log successful exit
                    self.logger.debug(f"EXIT {name} [SUCCESS]", extra={
                        'function': name,
                        'module': self.module_name,
                        'duration_ms': round(duration * 1000, 2),
                        'result_type': type(result).__name__,
                        'timestamp': datetime.utcnow().isoformat(),
                        'thread_id': self._get_thread_id()
                    })
                    return result
                    
                except Exception as e:
                    duration = time.time() - start_time
                    
                    # Log error exit with full context
                    self.logger.error(f"EXIT {name} [ERROR]", extra={
                        'function': name,
                        'module': self.module_name,
                        'duration_ms': round(duration * 1000, 2),
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'traceback': traceback.format_exc(),
                        'timestamp': datetime.utcnow().isoformat(),
                        'thread_id': self._get_thread_id(),
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    })
                    raise
                    
            return wrapper
        return decorator
        
    def log_state(self, component: str, state: Dict[str, Any], level: str = "DEBUG") -> None:
        """
        Log component state for debugging purposes.
        
        Args:
            component: Name of the component whose state is being logged
            state: Dictionary containing the current state information
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        log_level = getattr(logging, level.upper(), logging.DEBUG)
        
        self.logger.log(log_level, f"STATE {component}", extra={
            'component': component,
            'module': self.module_name,
            'state': self._sanitize_state(state),
            'timestamp': datetime.utcnow().isoformat(),
            'thread_id': self._get_thread_id()
        })
        
    def log_performance_metric(self, metric_name: str, value: float, unit: str = "ms") -> None:
        """
        Log performance metrics for monitoring during refactoring.
        
        Args:
            metric_name: Name of the performance metric
            value: Measured value
            unit: Unit of measurement (ms, bytes, etc.)
        """
        self.logger.info(f"PERFORMANCE {metric_name}", extra={
            'metric_name': metric_name,
            'module': self.module_name,
            'value': value,
            'unit': unit,
            'timestamp': datetime.utcnow().isoformat(),
            'thread_id': self._get_thread_id()
        })
        
    def log_milestone(self, milestone: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log refactoring milestones and progress.
        
        Args:
            milestone: Description of the milestone reached
            data: Optional additional data about the milestone
        """
        refactor_logger = logging.getLogger("refactor")
        refactor_logger.info(f"MILESTONE {milestone}", extra={
            'milestone': milestone,
            'module': self.module_name,
            'data': self._sanitize_state(data or {}),
            'timestamp': datetime.utcnow().isoformat(),
            'thread_id': self._get_thread_id()
        })
        
    def _sanitize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize state data to remove sensitive information and ensure JSON serialization.
        
        Args:
            state: Raw state dictionary
            
        Returns:
            Sanitized state dictionary safe for logging
        """
        sanitized = {}
        sensitive_keys = {'password', 'token', 'key', 'secret', 'auth', 'credential'}
        
        for key, value in state.items():
            # Check for sensitive keys
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
                continue
                
            # Handle different data types
            try:
                # Attempt JSON serialization to check if value is serializable
                json.dumps(value)
                sanitized[key] = value
            except (TypeError, ValueError):
                # If not serializable, convert to string representation
                sanitized[key] = str(type(value).__name__)
                
        return sanitized
        
    def _get_thread_id(self) -> str:
        """Get current thread ID for debugging multi-threaded operations."""
        import threading
        return str(threading.current_thread().ident)
        
    @classmethod
    def get_logger_for_module(cls, module_name: str) -> 'DebugLogger':
        """
        Factory method to get or create a debug logger for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            DebugLogger instance for the module
        """
        # This could be extended with caching if needed
        return cls(module_name)


# Convenience function for quick logger creation
def get_debug_logger(module_name: str) -> DebugLogger:
    """
    Convenience function to create a debug logger.
    
    Args:
        module_name: Name of the module/component
        
    Returns:
        DebugLogger instance
    """
    return DebugLogger(module_name)


# Example usage patterns for different scenarios
class ExampleUsage:
    """Example usage patterns for the DebugLogger."""
    
    def __init__(self):
        self.debug = DebugLogger("example")
    
    @DebugLogger("example").trace_function("example_method")
    def method_with_tracing(self, param1: str, param2: int = 0) -> str:
        """Example method showing tracing usage."""
        self.debug.log_state("method_start", {
            'param1': param1,
            'param2': param2,
            'method': 'method_with_tracing'
        })
        
        # Simulate some work
        time.sleep(0.1)
        
        result = f"processed {param1} with {param2}"
        
        self.debug.log_performance_metric("processing_time", 100, "ms")
        
        return result
        
    def method_with_error_handling(self):
        """Example showing error handling in traced functions."""
        debug = DebugLogger("error_example")
        
        @debug.trace_function()
        def risky_operation():
            self.debug.log_state("before_risk", {"status": "attempting"})
            raise ValueError("Something went wrong")
        
        try:
            risky_operation()
        except ValueError:
            self.debug.log_milestone("error_handled", {"recovery": "successful"})