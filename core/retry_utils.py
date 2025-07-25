"""
Reusable retry utilities for handling transient failures across all services

This module provides a unified retry framework that consolidates retry logic
previously duplicated across API sources, LLM providers, and other services.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Type, Union, List, Dict
from datetime import datetime, timezone, timedelta
import httpx

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Backoff strategy types for retry operations"""
    FIXED = "fixed"           # Fixed delay between retries
    LINEAR = "linear"         # Linearly increasing delay
    EXPONENTIAL = "exponential"  # Exponential backoff (2^attempt)
    CUSTOM_EXPONENTIAL = "custom_exponential"  # Configurable exponential base


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay cap in seconds
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    exponential_base: float = 2.0  # Base for exponential backoff
    jitter: bool = True  # Add random jitter to prevent thundering herd
    timeout: Optional[float] = None  # Optional timeout for individual attempts
    
    def __post_init__(self):
        """Validate configuration parameters"""
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.base_delay < 0:
            raise ValueError("base_delay must be non-negative")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if self.exponential_base <= 1:
            raise ValueError("exponential_base must be > 1")


class RetryCondition(ABC):
    """Abstract base class for retry conditions"""
    
    @abstractmethod
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if the operation should be retried based on the exception"""
        pass


class NetworkErrorRetryCondition(RetryCondition):
    """Retry on network-related errors (HTTP client errors, connection issues)"""
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        # HTTP client errors (connection, timeout, etc.)
        if isinstance(exception, (httpx.RequestError, httpx.ConnectError, httpx.TimeoutException)):
            return True
        
        # Generic network-related exceptions
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return True
            
        return False


class HTTPStatusRetryCondition(RetryCondition):
    """Retry on specific HTTP status codes"""
    
    def __init__(self, retryable_status_codes: List[int] = None):
        self.retryable_status_codes = retryable_status_codes or [429, 500, 502, 503, 504]
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            return exception.response.status_code in self.retryable_status_codes
        return False


class CompositeRetryCondition(RetryCondition):
    """Combine multiple retry conditions with OR logic"""
    
    def __init__(self, conditions: List[RetryCondition]):
        self.conditions = conditions
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        return any(condition.should_retry(exception, attempt) for condition in self.conditions)


class RetryResult:
    """Result of a retry operation"""
    
    def __init__(self, success: bool, result: Any = None, exception: Exception = None, 
                 attempts: int = 0, total_time: float = 0.0):
        self.success = success
        self.result = result
        self.exception = exception
        self.attempts = attempts
        self.total_time = total_time


class RetryExecutor:
    """Executor for retry operations with configurable strategies"""
    
    def __init__(self, config: RetryConfig, retry_condition: RetryCondition):
        self.config = config
        self.retry_condition = retry_condition
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt based on backoff strategy"""
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.base_delay
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * (attempt + 1)
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (2 ** attempt)
        elif self.config.backoff_strategy == BackoffStrategy.CUSTOM_EXPONENTIAL:
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        else:
            delay = self.config.base_delay
        
        # Apply maximum delay cap
        delay = min(delay, self.config.max_delay)
        
        # Add jitter if enabled (±10% random variation)
        if self.config.jitter:
            import random
            jitter_factor = 0.9 + (random.random() * 0.2)  # 0.9 to 1.1
            delay *= jitter_factor
        
        return delay
    
    async def execute_async(self, func: Callable, *args, **kwargs) -> RetryResult:
        """Execute an async function with retry logic"""
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):  # +1 for initial attempt
            try:
                logger.debug(f"Retry attempt {attempt + 1}/{self.config.max_retries + 1} for {func.__name__}")
                
                # Apply timeout if configured
                if self.config.timeout:
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
                else:
                    result = await func(*args, **kwargs)
                
                total_time = time.time() - start_time
                logger.debug(f"Operation {func.__name__} succeeded on attempt {attempt + 1}")
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=total_time
                )
                
            except Exception as e:
                last_exception = e
                total_time = time.time() - start_time
                
                # Check if we should retry
                if attempt < self.config.max_retries and self.retry_condition.should_retry(e, attempt):
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # No more retries or non-retryable error
                    if attempt >= self.config.max_retries:
                        logger.error(f"All {self.config.max_retries + 1} attempts failed for {func.__name__}")
                    else:
                        logger.error(f"Non-retryable error in {func.__name__}: {str(e)}")
                    
                    return RetryResult(
                        success=False,
                        exception=e,
                        attempts=attempt + 1,
                        total_time=total_time
                    )
        
        # Should never reach here, but just in case
        return RetryResult(
            success=False,
            exception=last_exception,
            attempts=self.config.max_retries + 1,
            total_time=time.time() - start_time
        )
    
    def execute_sync(self, func: Callable, *args, **kwargs) -> RetryResult:
        """Execute a synchronous function with retry logic"""
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Retry attempt {attempt + 1}/{self.config.max_retries + 1} for {func.__name__}")
                
                result = func(*args, **kwargs)
                total_time = time.time() - start_time
                logger.debug(f"Operation {func.__name__} succeeded on attempt {attempt + 1}")
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=total_time
                )
                
            except Exception as e:
                last_exception = e
                total_time = time.time() - start_time
                
                if attempt < self.config.max_retries and self.retry_condition.should_retry(e, attempt):
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    if attempt >= self.config.max_retries:
                        logger.error(f"All {self.config.max_retries + 1} attempts failed for {func.__name__}")
                    else:
                        logger.error(f"Non-retryable error in {func.__name__}: {str(e)}")
                    
                    return RetryResult(
                        success=False,
                        exception=e,
                        attempts=attempt + 1,
                        total_time=total_time
                    )
        
        return RetryResult(
            success=False,
            exception=last_exception,
            attempts=self.config.max_retries + 1,
            total_time=time.time() - start_time
        )


# Decorator functions for common retry patterns

def with_retry(config: RetryConfig = None, retry_condition: RetryCondition = None):
    """Decorator for adding retry logic to async functions"""
    if config is None:
        config = RetryConfig()
    if retry_condition is None:
        retry_condition = NetworkErrorRetryCondition()
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            executor = RetryExecutor(config, retry_condition)
            result = await executor.execute_async(func, *args, **kwargs)
            
            if result.success:
                return result.result
            else:
                raise result.exception
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


def with_retry_sync(config: RetryConfig = None, retry_condition: RetryCondition = None):
    """Decorator for adding retry logic to synchronous functions"""
    if config is None:
        config = RetryConfig()
    if retry_condition is None:
        retry_condition = NetworkErrorRetryCondition()
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            executor = RetryExecutor(config, retry_condition)
            result = executor.execute_sync(func, *args, **kwargs)
            
            if result.success:
                return result.result
            else:
                raise result.exception
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


# Convenience functions for common retry scenarios

def create_api_retry_config(max_retries: int = 3, base_delay: float = 1.0) -> RetryConfig:
    """Create retry config optimized for API calls"""
    return RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=60.0,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        jitter=True
    )


def create_api_retry_condition() -> RetryCondition:
    """Create retry condition for API calls (network errors + HTTP 429/5xx)"""
    return CompositeRetryCondition([
        NetworkErrorRetryCondition(),
        HTTPStatusRetryCondition([429, 500, 502, 503, 504])
    ])


def create_llm_retry_config(max_retries: int = 3) -> RetryConfig:
    """Create retry config optimized for LLM provider calls"""
    return RetryConfig(
        max_retries=max_retries,
        base_delay=1.0,
        max_delay=30.0,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        jitter=True,
        timeout=60.0  # LLM calls can be slower
    )


def create_database_retry_config(max_retries: int = 2) -> RetryConfig:
    """Create retry config for database operations"""
    return RetryConfig(
        max_retries=max_retries,
        base_delay=0.1,
        max_delay=5.0,
        backoff_strategy=BackoffStrategy.LINEAR,
        jitter=False  # Database operations should be predictable
    )


# High-level retry functions

async def retry_async(func: Callable, config: RetryConfig = None, 
                     retry_condition: RetryCondition = None, *args, **kwargs) -> Any:
    """High-level function to retry an async operation"""
    if config is None:
        config = RetryConfig()
    if retry_condition is None:
        retry_condition = NetworkErrorRetryCondition()
    
    executor = RetryExecutor(config, retry_condition)
    result = await executor.execute_async(func, *args, **kwargs)
    
    if result.success:
        return result.result
    else:
        raise result.exception


def retry_sync(func: Callable, config: RetryConfig = None, 
               retry_condition: RetryCondition = None, *args, **kwargs) -> Any:
    """High-level function to retry a synchronous operation"""
    if config is None:
        config = RetryConfig()
    if retry_condition is None:
        retry_condition = NetworkErrorRetryCondition()
    
    executor = RetryExecutor(config, retry_condition)
    result = executor.execute_sync(func, *args, **kwargs)
    
    if result.success:
        return result.result
    else:
        raise result.exception