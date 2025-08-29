"""
Circuit Breaker & Resilience Patterns for AsyncDatabaseService

Enterprise-grade async resilience patterns with circuit breakers,
retry policies, and graceful degradation.

Implementation for Phase 8 enterprise architecture patterns.
"""

import asyncio
import time
import random
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict
from contextlib import asynccontextmanager


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Blocking all requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class RetryExhaustedError(Exception):
    """Exception raised when retry attempts are exhausted"""
    pass


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker performance metrics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_opened_count: int = 0
    circuit_closed_count: int = 0
    average_response_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100


class AsyncCircuitBreaker:
    """Circuit breaker for database operations with configurable thresholds"""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 timeout: Optional[float] = None):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout = timeout
        
        # State management
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        
        # Metrics
        self.metrics = CircuitBreakerMetrics()
        self._logger = logging.getLogger(__name__)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        self.metrics.total_calls += 1
        
        # Check circuit breaker state
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self._logger.info("Circuit breaker transitioning to HALF_OPEN state")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        # Execute operation with timeout
        start_time = time.perf_counter()
        try:
            if self.timeout:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout)
            else:
                result = await func(*args, **kwargs)
            
            # Success - record metrics and reset if in HALF_OPEN
            duration = time.perf_counter() - start_time
            await self._record_success(duration)
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                await self._reset_circuit_breaker()
            
            return result
            
        except Exception as e:
            # Failure - record and potentially open circuit
            duration = time.perf_counter() - start_time
            await self._record_failure(duration)
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    async def _record_success(self, duration: float):
        """Record successful operation"""
        self.metrics.successful_calls += 1
        await self._update_average_response_time(duration)
        
        # Reset failure count on success
        self.failure_count = 0
        
        self._logger.debug(f"Circuit breaker success: duration={duration:.3f}s")
    
    async def _record_failure(self, duration: float):
        """Record failed operation and potentially open circuit"""
        self.metrics.failed_calls += 1
        await self._update_average_response_time(duration)
        
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        # Open circuit if threshold exceeded
        if self.failure_count >= self.failure_threshold:
            await self._open_circuit_breaker()
        
        self._logger.warning(f"Circuit breaker failure: count={self.failure_count}, duration={duration:.3f}s")
    
    async def _open_circuit_breaker(self):
        """Open circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.metrics.circuit_opened_count += 1
        self._logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
    
    async def _reset_circuit_breaker(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.metrics.circuit_closed_count += 1
        self._logger.info("Circuit breaker CLOSED - service recovered")
    
    async def _update_average_response_time(self, duration: float):
        """Update average response time"""
        total_calls = self.metrics.successful_calls + self.metrics.failed_calls
        if total_calls == 1:
            self.metrics.average_response_time = duration
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_response_time = (
                alpha * duration + (1 - alpha) * self.metrics.average_response_time
            )
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics"""
        return self.metrics


class AsyncRetryPolicy:
    """Async retry policy with exponential backoff"""
    
    def __init__(self,
                 max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_multiplier: float = 2.0,
                 jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self._logger = logging.getLogger(__name__)
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry policy"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    self._logger.info(f"Operation succeeded after {attempt} retries")
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    # No more retries
                    self._logger.error(f"Retry exhausted after {attempt} attempts: {e}")
                    raise RetryExhaustedError(f"Max retries ({self.max_retries}) exceeded") from e
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                self._logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        
        # Should never reach here, but just in case
        raise RetryExhaustedError("Unexpected retry exhaustion") from last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add jitter to prevent thundering herd
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)


class ResilientAsyncDatabaseService:
    """Database service with resilience patterns"""
    
    def __init__(self, 
                 db_path: str,
                 operation_timeout: float = 30.0,
                 circuit_breaker_threshold: int = 5,
                 retry_max_attempts: int = 3):
        self.db_path = db_path
        self.operation_timeout = operation_timeout
        
        # Resilience components
        from core.async_connection_pool import AsyncDatabasePool
        self.connection_pool = AsyncDatabasePool(db_path)
        
        self.circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout=operation_timeout
        )
        
        self.retry_policy = AsyncRetryPolicy(
            max_retries=retry_max_attempts,
            base_delay=0.1,
            max_delay=5.0
        )
        
        self._logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize resilient database service"""
        await self.connection_pool.initialize_pool()
        self._logger.info("ResilientAsyncDatabaseService initialized")
    
    async def store_data_item_resilient(self, 
                                       id: str, 
                                       namespace: str,
                                       source_id: str, 
                                       content: str,
                                       metadata: Optional[Dict] = None,
                                       days_date: Optional[str] = None) -> Any:
        """Store data item with circuit breaker and retry protection"""
        return await self.circuit_breaker.call(
            self.retry_policy.execute,
            self._store_data_item_impl,
            id, namespace, source_id, content, metadata, days_date
        )
    
    async def _store_data_item_impl(self, 
                                   id: str,
                                   namespace: str, 
                                   source_id: str,
                                   content: str,
                                   metadata: Optional[Dict] = None,
                                   days_date: Optional[str] = None) -> Any:
        """Implementation of store data item operation"""
        async with self.connection_pool.acquire_connection() as conn:
            # Create table if it doesn't exist (for testing)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS data_items (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    content TEXT,
                    metadata TEXT,
                    embedding_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    days_date TEXT NOT NULL
                )
            """)
            
            await conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, days_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (id, namespace, source_id, content, str(metadata) if metadata else None, days_date))
            await conn.commit()
            return True
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive resilience metrics"""
        pool_stats = await self.connection_pool.get_statistics()
        circuit_metrics = self.circuit_breaker.get_metrics()
        
        return {
            "connection_pool": {
                "total_connections": pool_stats.total_acquisitions,
                "active_connections": pool_stats.current_active_connections,
                "success_rate": pool_stats.success_rate
            },
            "circuit_breaker": {
                "state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker.failure_count,
                "success_rate": circuit_metrics.success_rate,
                "total_calls": circuit_metrics.total_calls
            }
        }
    
    async def close(self):
        """Close resilient database service"""
        await self.connection_pool.close_pool()
        self._logger.info("ResilientAsyncDatabaseService closed")