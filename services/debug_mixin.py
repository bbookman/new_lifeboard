"""
Service Debug Extensions for Enhanced Debug Logging.

This module provides the ServiceDebugMixin class that extends services with
comprehensive logging and monitoring capabilities for service operations,
database queries, and external API calls.
"""

import logging
import time
from typing import Any, Dict, Optional
import psutil
from core.debug_logger import DebugLogger


class ServiceDebugMixin:
    """
    Debug mixin for services providing comprehensive logging and monitoring.
    
    This mixin provides services with enhanced debugging capabilities including:
    - Service method call logging with system metrics
    - Database operation performance tracking
    - External API call monitoring
    - Resource usage monitoring (CPU, memory)
    - Timing and performance metrics
    
    Usage:
        class MyService(ServiceDebugMixin):
            def __init__(self, service_name: str):
                super().__init__(service_name)
                
            def my_method(self, param1, param2=None):
                self.log_service_call("my_method", {"param1": param1, "param2": param2})
                # ... method implementation
    """
    
    def __init__(self, service_name: str):
        """
        Initialize the service debug mixin.
        
        Args:
            service_name: Name of the service for logging identification
        """
        self.service_name = service_name
        self.debug = DebugLogger(f"service.{service_name}")
        self.performance_logger = logging.getLogger("performance")
        
    def log_service_call(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Log service method calls with system metrics.
        
        This method captures and logs:
        - Service and method name
        - Method parameters (sanitized)
        - Current memory usage
        - Current CPU percentage
        - Timestamp
        
        Args:
            method: Name of the service method being called
            params: Optional dictionary of method parameters
        """
        # Get system metrics (with error handling)
        try:
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
            cpu_percent = process.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Handle psutil errors gracefully
            memory_usage = None
            cpu_percent = None
        
        # Prepare log data
        log_data = {
            'service': self.service_name,
            'method': method,
            'params': params or {},
            'timestamp': time.time()
        }
        
        # Add system metrics if available
        if memory_usage is not None:
            log_data['memory_mb'] = round(memory_usage, 2)
        if cpu_percent is not None:
            log_data['cpu_percent'] = cpu_percent
            
        # Log the service call
        self.performance_logger.debug(
            f"SERVICE_CALL {self.service_name}.{method}",
            extra=log_data
        )
        
    def log_database_operation(self, operation: str, table: str, duration_ms: float) -> None:
        """
        Log database operations with performance metrics.
        
        This method captures and logs:
        - Database operation type (SELECT, INSERT, UPDATE, etc.)
        - Target table name
        - Operation duration in milliseconds
        - Service context
        
        Args:
            operation: Type of database operation (e.g., "SELECT", "INSERT", "UPDATE")
            table: Name of the database table involved
            duration_ms: Duration of the operation in milliseconds
        """
        log_data = {
            'service': self.service_name,
            'operation': operation,
            'table': table,
            'duration_ms': duration_ms,
            'timestamp': time.time()
        }
        
        self.performance_logger.debug(
            f"DB_OPERATION {operation}",
            extra=log_data
        )
        
    def log_external_api_call(self, api: str, endpoint: str, status_code: int, duration_ms: float) -> None:
        """
        Log external API calls with timing and status information.
        
        This method captures and logs:
        - API service name
        - Endpoint called
        - HTTP status code
        - Call duration in milliseconds
        - Service context
        
        Args:
            api: Name of the external API service
            endpoint: API endpoint that was called
            status_code: HTTP status code returned
            duration_ms: Duration of the API call in milliseconds
        """
        log_data = {
            'service': self.service_name,
            'api': api,
            'endpoint': endpoint,
            'status_code': status_code,
            'duration_ms': duration_ms,
            'timestamp': time.time()
        }
        
        self.performance_logger.debug(
            f"API_CALL {api}",
            extra=log_data
        )
        
    def log_service_error(self, method: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log service errors with full context for debugging.
        
        Args:
            method: Name of the method where the error occurred
            error: The exception that was raised
            context: Optional additional context about the error
        """
        log_data = {
            'service': self.service_name,
            'method': method,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'timestamp': time.time()
        }
        
        self.debug.logger.error(
            f"SERVICE_ERROR {self.service_name}.{method}",
            extra=log_data,
            exc_info=True
        )
        
    def log_service_performance_metric(self, metric_name: str, value: float, unit: str = "ms") -> None:
        """
        Log custom performance metrics for the service.
        
        Args:
            metric_name: Name of the performance metric
            value: Measured value
            unit: Unit of measurement (e.g., "ms", "bytes", "count")
        """
        log_data = {
            'service': self.service_name,
            'metric_name': metric_name,
            'value': value,
            'unit': unit,
            'timestamp': time.time()
        }
        
        self.performance_logger.info(
            f"SERVICE_METRIC {self.service_name}.{metric_name}",
            extra=log_data
        )
        
    def get_service_health_metrics(self) -> Dict[str, Any]:
        """
        Get current health metrics for the service.
        
        Returns:
            Dictionary containing current health and performance metrics
        """
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            metrics = {
                'service': self.service_name,
                'memory_mb': round(memory_info.rss / 1024 / 1024, 2),
                'memory_percent': process.memory_percent(),
                'cpu_percent': process.cpu_percent(),
                'num_threads': process.num_threads(),
                'status': process.status(),
                'timestamp': time.time()
            }
            
            # Log the health check
            self.debug.log_state("health_check", metrics, "INFO")
            
            return metrics
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            # Handle psutil errors
            error_metrics = {
                'service': self.service_name,
                'error': str(e),
                'status': 'error',
                'timestamp': time.time()
            }
            
            self.debug.log_state("health_check_error", error_metrics, "WARNING")
            return error_metrics


# Convenience function to create service with debug capabilities
def create_debug_enabled_service(service_class, service_name: str, *args, **kwargs):
    """
    Factory function to create a service instance with debug capabilities.
    
    Args:
        service_class: The service class to instantiate
        service_name: Name for debug logging
        *args: Positional arguments for the service constructor
        **kwargs: Keyword arguments for the service constructor
        
    Returns:
        Service instance with debug capabilities mixed in
    """
    class DebugEnabledService(service_class, ServiceDebugMixin):
        def __init__(self, *args, **kwargs):
            service_class.__init__(self, *args, **kwargs)
            ServiceDebugMixin.__init__(self, service_name)
            
    return DebugEnabledService(*args, **kwargs)


# Example usage and integration patterns
class ExampleServiceWithDebug(ServiceDebugMixin):
    """Example service showing how to integrate ServiceDebugMixin."""
    
    def __init__(self):
        super().__init__("example_service")
        self.data_cache = {}
        
    def fetch_data(self, user_id: int, include_details: bool = False) -> Dict[str, Any]:
        """Example method showing debug integration."""
        # Log the service call
        self.log_service_call("fetch_data", {
            "user_id": user_id,
            "include_details": include_details
        })
        
        try:
            # Simulate database operation
            start_time = time.time()
            
            # Simulate query
            time.sleep(0.1)
            
            # Log database operation
            db_duration = (time.time() - start_time) * 1000
            self.log_database_operation("SELECT", "users", db_duration)
            
            # Simulate API call for additional details
            if include_details:
                api_start = time.time()
                # Simulate external API call
                time.sleep(0.05)
                api_duration = (time.time() - api_start) * 1000
                self.log_external_api_call("user_details_api", f"/users/{user_id}/details", 200, api_duration)
            
            # Return mock data
            return {"user_id": user_id, "name": f"User {user_id}", "details": include_details}
            
        except Exception as e:
            # Log service errors
            self.log_service_error("fetch_data", e, {
                "user_id": user_id,
                "include_details": include_details
            })
            raise
            
    def get_health_status(self) -> Dict[str, Any]:
        """Example health check method."""
        return self.get_service_health_metrics()