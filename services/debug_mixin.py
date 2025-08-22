"""
Service debug mixin for performance tracking during Lifeboard cleanup.

This module provides a mixin class that can be added to any service
to provide comprehensive debugging and performance monitoring capabilities.

Usage:
    class MyService(ServiceDebugMixin):
        def __init__(self):
            super().__init__("my_service")
            
        def my_method(self):
            self.log_service_call("my_method", {"param": "value"})
            # service implementation
"""

import time
import psutil
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from contextlib import contextmanager
from core.debug_logger import DebugLogger


class ServiceDebugMixin:
    """
    Mixin class providing comprehensive debugging capabilities for services.
    
    Provides automatic performance monitoring, resource tracking,
    and standardized logging for service operations during cleanup.
    """
    
    def __init__(self, service_name: str):
        """
        Initialize service debug capabilities.
        
        Args:
            service_name: Name of the service for logging identification
        """
        self.service_name = service_name
        self.debug = DebugLogger(f"service.{service_name}")
        self.performance_logger = logging.getLogger("performance")
        
        # Performance tracking
        self.operation_count = 0
        self.total_operation_time = 0.0
        self.error_count = 0
        self.start_time = datetime.utcnow()
        
        # Resource baseline
        self.baseline_memory = self._get_memory_usage()
        self.baseline_cpu = psutil.Process().cpu_percent()
        
        self.debug.log_milestone(f"{service_name}_service_initialized", {
            'baseline_memory_mb': self.baseline_memory,
            'baseline_cpu_percent': self.baseline_cpu
        })
        
    def log_service_call(
        self, 
        method: str, 
        params: Optional[Dict[str, Any]] = None,
        log_resources: bool = True
    ) -> None:
        """
        Log service method calls with system metrics.
        
        Args:
            method: Name of the method being called
            params: Optional parameters passed to the method
            log_resources: Whether to log current resource usage
        """
        self.operation_count += 1
        
        log_data = {
            'service': self.service_name,
            'method': method,
            'operation_number': self.operation_count,
            'params': self._sanitize_params(params or {}),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if log_resources:
            memory_usage = self._get_memory_usage()
            cpu_percent = psutil.Process().cpu_percent()
            
            log_data.update({
                'memory_mb': memory_usage,
                'memory_delta_mb': round(memory_usage - self.baseline_memory, 2),
                'cpu_percent': cpu_percent,
                'cpu_delta_percent': round(cpu_percent - self.baseline_cpu, 2)
            })
        
        self.performance_logger.debug(f"SERVICE_CALL {self.service_name}.{method}", extra=log_data)
        
    @contextmanager
    def track_operation(self, operation_name: str, **context):
        """
        Context manager for tracking operation performance.
        
        Args:
            operation_name: Name of the operation being tracked
            **context: Additional context data
            
        Usage:
            with self.track_operation("data_processing", record_count=100):
                # operation implementation
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        self.debug.log_state(f"{operation_name}_started", {
            'operation': operation_name,
            'context': context,
            'start_memory_mb': start_memory
        })
        
        try:
            yield
            
            # Log successful completion
            duration = time.time() - start_time
            end_memory = self._get_memory_usage()
            self.total_operation_time += duration
            
            self.debug.log_state(f"{operation_name}_completed", {
                'operation': operation_name,
                'duration_ms': round(duration * 1000, 2),
                'memory_delta_mb': round(end_memory - start_memory, 2),
                'context': context
            })
            
            self.performance_logger.info(f"OPERATION_SUCCESS {operation_name}", extra={
                'service': self.service_name,
                'operation': operation_name,
                'duration_ms': round(duration * 1000, 2),
                'memory_delta_mb': round(end_memory - start_memory, 2),
                'context': context
            })
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            end_memory = self._get_memory_usage()
            self.error_count += 1
            
            error_data = {
                'service': self.service_name,
                'operation': operation_name,
                'duration_ms': round(duration * 1000, 2),
                'memory_delta_mb': round(end_memory - start_memory, 2),
                'error_type': type(e).__name__,
                'error_message': str(e),
                'error_count_total': self.error_count,
                'context': context
            }
            
            self.debug.logger.error(f"OPERATION_FAILED {operation_name}", extra=error_data)
            raise
            
    def log_database_operation(
        self, 
        operation: str, 
        table: str, 
        duration_ms: float,
        record_count: Optional[int] = None,
        query_preview: Optional[str] = None
    ) -> None:
        """
        Log database operations with performance metrics.
        
        Args:
            operation: Type of database operation (SELECT, INSERT, UPDATE, DELETE)
            table: Database table being operated on
            duration_ms: Operation duration in milliseconds
            record_count: Number of records affected (optional)
            query_preview: Preview of the SQL query (optional)
        """
        log_data = {
            'service': self.service_name,
            'operation': operation,
            'table': table,
            'duration_ms': duration_ms,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if record_count is not None:
            log_data['record_count'] = record_count
            log_data['records_per_second'] = round(
                (record_count / (duration_ms / 1000)) if duration_ms > 0 else 0, 2
            )
            
        if query_preview:
            log_data['query_preview'] = query_preview[:200] + "..." if len(query_preview) > 200 else query_preview
            
        self.performance_logger.debug(f"DB_OPERATION {operation}", extra=log_data)
        
        # Log slow database operations
        if duration_ms > 1000:  # Operations taking more than 1 second
            self.debug.logger.warning(f"SLOW_DB_OPERATION {operation}", extra=log_data)
            
    def log_external_api_call(
        self, 
        api: str, 
        endpoint: str, 
        status_code: int, 
        duration_ms: float,
        method: str = "GET",
        response_size_bytes: Optional[int] = None
    ) -> None:
        """
        Log external API calls with timing and status.
        
        Args:
            api: Name of the external API (e.g., "limitless", "weather")
            endpoint: API endpoint called
            status_code: HTTP status code returned
            duration_ms: Request duration in milliseconds
            method: HTTP method used
            response_size_bytes: Size of response in bytes (optional)
        """
        log_data = {
            'service': self.service_name,
            'api': api,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'duration_ms': duration_ms,
            'success': 200 <= status_code < 300,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if response_size_bytes is not None:
            log_data['response_size_bytes'] = response_size_bytes
            log_data['throughput_bytes_per_second'] = round(
                (response_size_bytes / (duration_ms / 1000)) if duration_ms > 0 else 0, 2
            )
            
        level = "info" if log_data['success'] else "warning"
        
        self.performance_logger.log(
            getattr(logging, level.upper()),
            f"API_CALL {api}",
            extra=log_data
        )
        
        # Log slow API calls
        if duration_ms > 5000:  # API calls taking more than 5 seconds
            self.debug.logger.warning(f"SLOW_API_CALL {api}", extra=log_data)
            
    def log_cache_operation(
        self, 
        operation: str, 
        cache_key: str, 
        hit: bool,
        duration_ms: Optional[float] = None
    ) -> None:
        """
        Log cache operations for performance analysis.
        
        Args:
            operation: Cache operation (get, set, delete, clear)
            cache_key: Key being operated on
            hit: Whether operation was a cache hit
            duration_ms: Operation duration in milliseconds
        """
        log_data = {
            'service': self.service_name,
            'cache_operation': operation,
            'cache_key': cache_key[:100] + "..." if len(cache_key) > 100 else cache_key,
            'cache_hit': hit,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if duration_ms is not None:
            log_data['duration_ms'] = duration_ms
            
        self.performance_logger.debug(f"CACHE_{operation.upper()}", extra=log_data)
        
    def get_service_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive service performance metrics.
        
        Returns:
            Dictionary containing service performance data
        """
        current_time = datetime.utcnow()
        uptime_seconds = (current_time - self.start_time).total_seconds()
        current_memory = self._get_memory_usage()
        
        return {
            'service_name': self.service_name,
            'uptime_seconds': round(uptime_seconds, 2),
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'error_rate_percent': round(
                (self.error_count / max(self.operation_count, 1)) * 100, 2
            ),
            'total_operation_time_seconds': round(self.total_operation_time, 2),
            'average_operation_time_ms': round(
                (self.total_operation_time / max(self.operation_count, 1)) * 1000, 2
            ),
            'operations_per_second': round(
                self.operation_count / max(uptime_seconds, 1), 2
            ),
            'current_memory_mb': current_memory,
            'memory_delta_mb': round(current_memory - self.baseline_memory, 2),
            'memory_growth_rate_mb_per_hour': round(
                ((current_memory - self.baseline_memory) / max(uptime_seconds / 3600, 0.001)), 2
            ),
            'timestamp': current_time.isoformat()
        }
        
    def log_service_health_check(self) -> Dict[str, Any]:
        """
        Perform and log service health check.
        
        Returns:
            Health check results
        """
        metrics = self.get_service_metrics()
        
        # Determine health status
        health_issues = []
        
        if metrics['error_rate_percent'] > 10:
            health_issues.append(f"High error rate: {metrics['error_rate_percent']}%")
            
        if metrics['memory_growth_rate_mb_per_hour'] > 100:
            health_issues.append(f"High memory growth: {metrics['memory_growth_rate_mb_per_hour']} MB/hour")
            
        if metrics['average_operation_time_ms'] > 5000:
            health_issues.append(f"Slow operations: {metrics['average_operation_time_ms']} ms average")
            
        health_status = {
            'status': 'healthy' if not health_issues else 'degraded',
            'issues': health_issues,
            'metrics': metrics
        }
        
        self.debug.log_state("health_check", health_status)
        
        return health_status
        
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return round(process.memory_info().rss / 1024 / 1024, 2)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
            
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize parameters to remove sensitive information.
        
        Args:
            params: Original parameters dictionary
            
        Returns:
            Sanitized parameters safe for logging
        """
        sanitized = {}
        sensitive_keys = {'password', 'token', 'key', 'secret', 'auth', 'credential', 'api_key'}
        
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)) and len(str(value)) > 500:
                sanitized[key] = f"<{type(value).__name__} with {len(value) if hasattr(value, '__len__') else '?'} items>"
            else:
                sanitized[key] = value
                
        return sanitized


class ServicePerformanceCollector:
    """
    Collector for aggregating performance data across multiple services.
    """
    
    def __init__(self):
        self.services: List[ServiceDebugMixin] = []
        self.debug = DebugLogger("performance_collector")
        
    def register_service(self, service: ServiceDebugMixin):
        """Register a service for performance monitoring."""
        self.services.append(service)
        self.debug.log_state("service_registered", {
            'service_name': service.service_name,
            'total_services': len(self.services)
        })
        
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all registered services."""
        all_metrics = {}
        
        for service in self.services:
            try:
                all_metrics[service.service_name] = service.get_service_metrics()
            except Exception as e:
                all_metrics[service.service_name] = {
                    'error': f"Failed to collect metrics: {str(e)}"
                }
                
        self.debug.log_state("metrics_collected", {
            'services_count': len(self.services),
            'successful_collections': len([m for m in all_metrics.values() if 'error' not in m])
        })
        
        return all_metrics
        
    def get_system_performance_summary(self) -> Dict[str, Any]:
        """Get system-wide performance summary."""
        all_metrics = self.collect_all_metrics()
        
        total_operations = sum(
            m.get('operation_count', 0) for m in all_metrics.values() if 'error' not in m
        )
        total_errors = sum(
            m.get('error_count', 0) for m in all_metrics.values() if 'error' not in m
        )
        total_memory = sum(
            m.get('current_memory_mb', 0) for m in all_metrics.values() if 'error' not in m
        )
        
        return {
            'services_monitored': len(self.services),
            'total_operations': total_operations,
            'total_errors': total_errors,
            'system_error_rate_percent': round(
                (total_errors / max(total_operations, 1)) * 100, 2
            ),
            'total_memory_mb': round(total_memory, 2),
            'services_metrics': all_metrics,
            'timestamp': datetime.utcnow().isoformat()
        }


# Global performance collector instance
performance_collector = ServicePerformanceCollector()