
import pytest
import asyncio
import time
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.retry_utils import (
    RetryConfig,
    BackoffStrategy,
    RetryExecutor,
    NetworkErrorRetryCondition,
    HTTPStatusRetryCondition,
    RateLimitRetryCondition,
    CompositeRetryCondition,
    with_retry,
    with_retry_sync,
    parse_retry_after_header,
)

# --- Fixtures ---

@pytest.fixture
def default_config():
    return RetryConfig(base_delay=0.01, max_delay=0.1) # Use short delays for testing

# --- Test Functions ---

@pytest.mark.asyncio
async def test_successful_async_execution(default_config):
    """Tests that a function that succeeds on the first try is executed once."""
    mock_func = AsyncMock(return_value="success")
    executor = RetryExecutor(default_config, NetworkErrorRetryCondition())

    result = await executor.execute_async(mock_func)

    assert result.success is True
    assert result.result == "success"
    assert result.attempts == 1
    mock_func.assert_awaited_once()

def test_successful_sync_execution(default_config):
    """Tests that a sync function that succeeds on the first try is executed once."""
    mock_func = MagicMock(return_value="success")
    executor = RetryExecutor(default_config, NetworkErrorRetryCondition())

    result = executor.execute_sync(mock_func)

    assert result.success is True
    assert result.result == "success"
    assert result.attempts == 1
    mock_func.assert_called_once()

@pytest.mark.asyncio
async def test_async_retry_and_succeed(default_config):
    """Tests that a function is retried and eventually succeeds."""
    mock_func = AsyncMock(side_effect=[httpx.ConnectError("Connection failed"), "success"])
    executor = RetryExecutor(default_config, NetworkErrorRetryCondition())

    result = await executor.execute_async(mock_func)

    assert result.success is True
    assert result.result == "success"
    assert result.attempts == 2
    assert mock_func.await_count == 2

@pytest.mark.asyncio
async def test_async_retry_and_fail(default_config):
    """Tests that a function fails after all retry attempts are exhausted."""
    default_config.max_retries = 2
    mock_func = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
    executor = RetryExecutor(default_config, NetworkErrorRetryCondition())

    result = await executor.execute_async(mock_func)

    assert result.success is False
    assert isinstance(result.exception, httpx.ConnectError)
    assert result.attempts == 3 # 1 initial + 2 retries
    assert mock_func.await_count == 3

# --- Backoff Strategy Tests ---

@patch('time.sleep', return_value=None)
@patch('asyncio.sleep', return_value=None)
def test_backoff_strategies(mock_async_sleep, mock_sync_sleep, default_config):
    """Tests the different backoff strategies."""
    # This is a simplified test focusing on the delay calculation.
    # A more thorough test would involve mocking time and checking sleep durations.

    executor = RetryExecutor(default_config, NetworkErrorRetryCondition())

    # Fixed
    default_config.backoff_strategy = BackoffStrategy.FIXED
    delay = executor._calculate_delay(0)
    assert delay == pytest.approx(default_config.base_delay, rel=0.1)

    # Linear
    default_config.backoff_strategy = BackoffStrategy.LINEAR
    delay = executor._calculate_delay(1)
    assert delay == pytest.approx(default_config.base_delay * 2, rel=0.1)

    # Exponential
    default_config.backoff_strategy = BackoffStrategy.EXPONENTIAL
    delay = executor._calculate_delay(2)
    assert delay == pytest.approx(default_config.base_delay * 4, rel=0.1)

# --- Retry Condition Tests ---

def test_network_error_retry_condition():
    condition = NetworkErrorRetryCondition()
    assert condition.should_retry(httpx.ConnectError("..."), 0) is True
    assert condition.should_retry(httpx.TimeoutException("..."), 0) is True
    assert condition.should_retry(ValueError("..."), 0) is False

def test_http_status_retry_condition():
    condition = HTTPStatusRetryCondition(retryable_status_codes=[500, 503])
    mock_response_500 = MagicMock(spec=httpx.Response, status_code=500)
    mock_response_404 = MagicMock(spec=httpx.Response, status_code=404)

    assert condition.should_retry(httpx.HTTPStatusError("", request=MagicMock(), response=mock_response_500), 0) is True
    assert condition.should_retry(httpx.HTTPStatusError("", request=MagicMock(), response=mock_response_404), 0) is False
    assert condition.should_retry(ValueError("..."), 0) is False

# --- Decorator Tests ---

@pytest.mark.asyncio
async def test_with_retry_decorator_success():
    """Tests the async retry decorator on a function that succeeds."""
    @with_retry(config=RetryConfig(base_delay=0.01))
    async def func_to_decorate():
        return "ok"

    result = await func_to_decorate()
    assert result == "ok"

@pytest.mark.asyncio
async def test_with_retry_decorator_failure():
    """Tests the async retry decorator on a function that fails."""
    mock_func = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

    @with_retry(config=RetryConfig(max_retries=1, base_delay=0.01), retry_condition=NetworkErrorRetryCondition())
    async def func_to_decorate():
        await mock_func()

    with pytest.raises(httpx.ConnectError):
        await func_to_decorate()
    assert mock_func.await_count == 2 # 1 initial + 1 retry

def test_with_retry_sync_decorator():
    """Tests the sync retry decorator."""
    mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])

    class CustomRetryCondition(NetworkErrorRetryCondition):
        def should_retry(self, exception, attempt):
            return isinstance(exception, ValueError)

    @with_retry_sync(config=RetryConfig(max_retries=1, base_delay=0.01), retry_condition=CustomRetryCondition())
    def func_to_decorate():
        return mock_func()

    result = func_to_decorate()
    assert result == "success"
    assert mock_func.call_count == 2

# --- Header Parsing Tests ---

def test_parse_retry_after_header():
    """Tests parsing of the Retry-After header."""
    # Integer value
    response_int = httpx.Response(200, headers={'Retry-After': '120'})
    assert parse_retry_after_header(response_int) == 120

    # HTTP-date value
    # Note: This is a simplified test. A real test would use a library like `freezegun`
    # to control the current time for accurate date parsing.
    in_two_minutes = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + 120))
    response_date = httpx.Response(200, headers={'Retry-After': in_two_minutes})
    delay = parse_retry_after_header(response_date)
    assert delay is not None and 119 <= delay <= 120

    # Invalid header
    response_invalid = httpx.Response(200, headers={'Retry-After': 'invalid'})
    assert parse_retry_after_header(response_invalid) is None

    # No header
    response_none = httpx.Response(200)
    assert parse_retry_after_header(response_none) is None

