"""
Reusable retry utilities for handling transient failures across all services

This module provides a unified retry framework that consolidates retry logic
previously duplicated across API sources, LLM providers, and other services.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Type, Union, List, Dict
from datetime import datetime, timezone, timedelta
import httpx

from core.logging_config import get_logger

logger = get_logger(__name__)


def parse_retry_after_header(response: httpx.Response) -> Optional[int]:
    """
    Parse Retry-After header from HTTP response
    
    Args:
        response: HTTP response object
        
    Returns:
        Delay in seconds if header present, None otherwise
    """
    retry_after = response.headers.get('retry-after') or response.headers.get('Retry-After')
    if not retry_after:
        return None
        
    try:
        # Retry-After can be in seconds (integer) or HTTP date
        return int(retry_after)
    except ValueError:
        # If it's a date, calculate seconds from now
        try:
            from email.utils import parsedate_to_datetime
            retry_time = parsedate_to_datetime(retry_after)
            delay = (retry_time - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(delay))
        except Exception:
            return None


def parse_rate_limit_headers(response: httpx.Response) -> Dict[str, Optional[int]]:
    """
    Parse common rate limit headers from HTTP response
    
    Args:
        response: HTTP response object
        
    Returns:
        Dictionary with rate limit information
    """
    headers = response.headers
    rate_limit_info = {
        'limit': None,           # Total requests allowed
        'remaining': None,       # Requests remaining in window
        'reset': None,          # When the window resets (timestamp)
        'retry_after': None     # Seconds to wait before retry
    }
    
    # Parse X-RateLimit-* headers (common standard)
    if 'x-ratelimit-limit' in headers:
        try:
            rate_limit_info['limit'] = int(headers['x-ratelimit-limit'])
        except ValueError:
            pass
            
    if 'x-ratelimit-remaining' in headers:
        try:
            rate_limit_info['remaining'] = int(headers['x-ratelimit-remaining'])
        except ValueError:
            pass
            
    if 'x-ratelimit-reset' in headers:
        try:
            rate_limit_info['reset'] = int(headers['x-ratelimit-reset'])
        except ValueError:
            pass
    
    # Parse Retry-After header
    rate_limit_info['retry_after'] = parse_retry_after_header(response)
    
    return rate_limit_info


class BackoffStrategy(Enum):
    """Backoff strategy types for retry operations"""
    FIXED = "fixed"           # Fixed delay between retries
    LINEAR = "linear"         # Linearly increasing delay
    EXPONENTIAL = "exponential"  # Exponential backoff (2^attempt)
    CUSTOM_EXPONENTIAL = "custom_exponential"  # Configurable exponential base
    RATE_LIMIT_BACKOFF = "rate_limit_backoff"  # Specialized backoff for rate limiting


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
    
    # Rate limiting specific configuration
    rate_limit_base_delay: float = 30.0  # Base delay for rate limiting (longer)
    rate_limit_max_delay: float = 300.0  # Max delay for rate limiting (5 minutes)
    respect_retry_after: bool = True  # Honor Retry-After header if present
    
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


class RateLimitRetryCondition(RetryCondition):
    """Specialized retry condition for rate limiting with intelligent detection"""
    
    def __init__(self, max_rate_limit_delay: int = 300):
        """
        Initialize rate limit retry condition
        
        Args:
            max_rate_limit_delay: Maximum delay in seconds to accept for rate limiting
        """
        self.max_rate_limit_delay = max_rate_limit_delay
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if we should retry based on rate limiting indicators
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-indexed)
            
        Returns:
            True if we should retry due to rate limiting
        """
        # Check for HTTP 429 status code
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            response = exception.response
            
            if response.status_code == 429:
                # Check if Retry-After header suggests a reasonable delay
                retry_after = parse_retry_after_header(response)
                if retry_after is not None:
                    if retry_after <= self.max_rate_limit_delay:
                        logger.info(f"Rate limited (429) - Retry-After: {retry_after}s")
                        return True
                    else:
                        logger.warning(f"Rate limited with excessive Retry-After: {retry_after}s (max: {self.max_rate_limit_delay}s)")
                        return False
                
                # If no Retry-After header, still retry with exponential backoff
                logger.info("Rate limited (429) - no Retry-After header, using exponential backoff")
                return True
            
            # Check for other rate limiting indicators
            if response.status_code in [503, 502]:  # Service unavailable, bad gateway (could be rate limiting)
                rate_limit_info = parse_rate_limit_headers(response)
                if rate_limit_info['remaining'] is not None and rate_limit_info['remaining'] == 0:
                    logger.info(f"Rate limited ({response.status_code}) - X-RateLimit-Remaining: 0")
                    return True
        
        return False
    
    def get_rate_limit_delay(self, exception: Exception, attempt: int) -> Optional[int]:
        """
        Get the suggested delay for rate limiting
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Suggested delay in seconds, or None if not rate limited
        """
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            response = exception.response
            
            if response.status_code == 429:
                # Use Retry-After header if present
                retry_after = parse_retry_after_header(response)
                if retry_after is not None and retry_after <= self.max_rate_limit_delay:
                    return retry_after
        
        return None


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
    
    def _calculate_delay(self, attempt: int, exception: Exception = None) -> float:
        """Calculate delay for the given attempt based on backoff strategy"""
        
        # Check for rate limiting first and honor Retry-After header
        if exception and isinstance(self.retry_condition, RateLimitRetryCondition):
            rate_limit_delay = self.retry_condition.get_rate_limit_delay(exception, attempt)
            if rate_limit_delay is not None and self.config.respect_retry_after:
                logger.info(f"Using Retry-After header delay: {rate_limit_delay}s")
                return float(rate_limit_delay)
        
        # Use rate limit backoff strategy for rate limiting conditions
        if (self.config.backoff_strategy == BackoffStrategy.RATE_LIMIT_BACKOFF or 
            (exception and isinstance(self.retry_condition, RateLimitRetryCondition) and 
             self.retry_condition.should_retry(exception, attempt))):
            
            # Use exponential backoff with rate limit base delay
            delay = self.config.rate_limit_base_delay * (2 ** attempt)
            max_delay = self.config.rate_limit_max_delay
            
        elif self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.base_delay
            max_delay = self.config.max_delay
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * (attempt + 1)
            max_delay = self.config.max_delay
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (2 ** attempt)
            max_delay = self.config.max_delay
        elif self.config.backoff_strategy == BackoffStrategy.CUSTOM_EXPONENTIAL:
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)
            max_delay = self.config.max_delay
        else:
            delay = self.config.base_delay
            max_delay = self.config.max_delay
        
        # Apply maximum delay cap
        delay = min(delay, max_delay)
        
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
                logger.debug(f"Retry attempt {attempt + 1}/{self.config.max_retries + 1} for {getattr(func, '__name__', 'unknown_function')}")
                
                # Apply timeout if configured
                if self.config.timeout:
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
                else:
                    result = await func(*args, **kwargs)
                
                total_time = time.time() - start_time
                logger.debug(f"Operation {getattr(func, '__name__', 'unknown_function')} succeeded on attempt {attempt + 1}")
                
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
                    delay = self._calculate_delay(attempt, e)
                    
                    # Enhanced logging for rate limiting
                    if isinstance(self.retry_condition, RateLimitRetryCondition) and hasattr(e, 'response'):
                        rate_limit_info = parse_rate_limit_headers(e.response) if hasattr(e, 'response') else {}
                        logger.warning(
                            f"Rate limited on attempt {attempt + 1} for {getattr(func, '__name__', 'unknown_function')}: {str(e)}. "
                            f"Rate limit info: {rate_limit_info}. Retrying in {delay:.2f} seconds..."
                        )
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {getattr(func, '__name__', 'unknown_function')}: {str(e)}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # No more retries or non-retryable error
                    if attempt >= self.config.max_retries:
                        logger.error(f"All {self.config.max_retries + 1} attempts failed for {getattr(func, '__name__', 'unknown_function')}")
                    else:
                        logger.error(f"Non-retryable error in {getattr(func, '__name__', 'unknown_function')}: {str(e)}")
                    
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
                logger.debug(f"Retry attempt {attempt + 1}/{self.config.max_retries + 1} for {getattr(func, '__name__', 'unknown_function')}")
                
                result = func(*args, **kwargs)
                total_time = time.time() - start_time
                logger.debug(f"Operation {getattr(func, '__name__', 'unknown_function')} succeeded on attempt {attempt + 1}")
                
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
                    delay = self._calculate_delay(attempt, e)
                    
                    # Enhanced logging for rate limiting
                    if isinstance(self.retry_condition, RateLimitRetryCondition) and hasattr(e, 'response'):
                        rate_limit_info = parse_rate_limit_headers(e.response) if hasattr(e, 'response') else {}
                        logger.warning(
                            f"Rate limited on attempt {attempt + 1} for {getattr(func, '__name__', 'unknown_function')}: {str(e)}. "
                            f"Rate limit info: {rate_limit_info}. Retrying in {delay:.2f} seconds..."
                        )
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {getattr(func, '__name__', 'unknown_function')}: {str(e)}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                    time.sleep(delay)
                    continue
                else:
                    if attempt >= self.config.max_retries:
                        logger.error(f"All {self.config.max_retries + 1} attempts failed for {getattr(func, '__name__', 'unknown_function')}")
                    else:
                        logger.error(f"Non-retryable error in {getattr(func, '__name__', 'unknown_function')}: {str(e)}")
                    
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
        
        wrapper.__name__ = getattr(func, '__name__', 'unknown_function')
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
        
        wrapper.__name__ = getattr(func, '__name__', 'unknown_function')
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


def create_rate_limit_retry_config(max_retries: int = 5, base_delay: float = 30.0) -> RetryConfig:
    """Create retry config optimized for rate limiting scenarios"""
    return RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=60.0,  # Standard max for normal operations
        backoff_strategy=BackoffStrategy.RATE_LIMIT_BACKOFF,
        rate_limit_base_delay=30.0,  # Start with 30 second delays for rate limits
        rate_limit_max_delay=300.0,  # Max 5 minutes for rate limits
        respect_retry_after=True,
        jitter=True
    )


def create_rate_limit_retry_condition(max_delay: int = 300) -> RateLimitRetryCondition:
    """Create specialized retry condition for rate limiting"""
    return RateLimitRetryCondition(max_rate_limit_delay=max_delay)


def create_enhanced_api_retry_condition() -> RetryCondition:
    """Create enhanced retry condition that combines network errors, HTTP errors, and intelligent rate limiting"""
    return CompositeRetryCondition([
        NetworkErrorRetryCondition(),
        HTTPStatusRetryCondition([500, 502, 503, 504]),  # Exclude 429 since we handle it specially
        RateLimitRetryCondition(max_rate_limit_delay=300)
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