"""
Test suite for AsyncCircuitBreaker - Circuit Breaker & Resilience Patterns

This test module follows TDD principles for Phase 8 enterprise architecture implementation.
All tests are written first (RED phase) before implementation (GREEN phase).
"""

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import AsyncMock
from typing import Any

# Import the classes we'll implement (will fail initially - RED phase)
try:
    from core.async_circuit_breaker import (
        AsyncCircuitBreaker,
        AsyncRetryPolicy,
        ResilientAsyncDatabaseService,
        CircuitBreakerOpenError,
        CircuitBreakerState,
        RetryExhaustedError
    )
except ImportError:
    # Expected during RED phase - these don't exist yet
    pass


class TestAsyncCircuitBreaker:
    """Test suite for Circuit Breaker patterns"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_initialization(self):
        """RED: Test circuit breaker initialization with configurable parameters"""
        breaker = AsyncCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            timeout=10.0
        )
        
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 60
        assert breaker.timeout == 10.0
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self):
        """RED: Test circuit breaker opens after failure threshold"""
        breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=5)
        
        async def failing_operation():
            raise Exception("Database operation failed")
        
        # Execute failing operations to reach threshold
        for i in range(3):
            with pytest.raises(Exception, match="Database operation failed"):
                await breaker.call(failing_operation)
            
            if i < 2:
                assert breaker.state == CircuitBreakerState.CLOSED
            else:
                assert breaker.state == CircuitBreakerState.OPEN
        
        # Next call should fail with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_cycle(self):
        """RED: Test circuit breaker recovery from OPEN to HALF_OPEN to CLOSED"""
        breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        async def failing_operation():
            raise Exception("Failure")
        
        async def successful_operation():
            return "success"
        
        # Trip circuit breaker
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_operation)
        
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Should fail while in recovery timeout
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(successful_operation)
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Should now be HALF_OPEN and accept calls
        result = await breaker.call(successful_operation)
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self):
        """RED: Test circuit breaker HALF_OPEN -> OPEN on failure"""
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def failing_operation():
            raise Exception("Still failing")
        
        # Trip circuit breaker
        with pytest.raises(Exception):
            await breaker.call(failing_operation)
        
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        
        # Fail in HALF_OPEN state
        with pytest.raises(Exception, match="Still failing"):
            await breaker.call(failing_operation)
        
        # Should go back to OPEN
        assert breaker.state == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_operation_timeout(self):
        """RED: Test circuit breaker operation timeout handling"""
        breaker = AsyncCircuitBreaker(timeout=0.5)
        
        async def slow_operation():
            await asyncio.sleep(1.0)  # Slower than timeout
            return "success"
        
        start_time = time.perf_counter()
        with pytest.raises(asyncio.TimeoutError):
            await breaker.call(slow_operation)
        
        duration = time.perf_counter() - start_time
        assert 0.4 < duration < 0.7  # Should timeout around 0.5s
        
        # Circuit breaker should record this as a failure
        assert breaker.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success_reset_counter(self):
        """RED: Test successful operations reset failure counter"""
        breaker = AsyncCircuitBreaker(failure_threshold=3)
        
        async def sometimes_failing_operation(should_fail: bool):
            if should_fail:
                raise Exception("Failure")
            return "success"
        
        # One failure
        with pytest.raises(Exception):
            await breaker.call(sometimes_failing_operation, True)
        assert breaker.failure_count == 1
        
        # One success should reset counter
        result = await breaker.call(sometimes_failing_operation, False)
        assert result == "success"
        assert breaker.failure_count == 0
        assert breaker.state == CircuitBreakerState.CLOSED


class TestAsyncRetryPolicy:
    """Test suite for Async Retry Policy"""
    
    @pytest.mark.asyncio
    async def test_retry_policy_initialization(self):
        """RED: Test retry policy with configurable parameters"""
        policy = AsyncRetryPolicy(
            max_retries=5,
            base_delay=1.0,
            max_delay=30.0,
            backoff_multiplier=2.0
        )
        
        assert policy.max_retries == 5
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.backoff_multiplier == 2.0
    
    @pytest.mark.asyncio
    async def test_retry_policy_exponential_backoff(self):
        """RED: Test exponential backoff timing"""
        policy = AsyncRetryPolicy(max_retries=3, base_delay=0.1, backoff_multiplier=2.0)
        
        call_times = []
        
        async def failing_operation():
            call_times.append(time.perf_counter())
            raise Exception("Temporary failure")
        
        start_time = time.perf_counter()
        
        with pytest.raises(RetryExhaustedError):
            await policy.execute(failing_operation)
        
        # Should have 4 calls (initial + 3 retries)
        assert len(call_times) == 4
        
        # Verify backoff timing (approximate due to execution overhead)
        time_between_calls = [call_times[i] - call_times[i-1] for i in range(1, len(call_times))]
        
        # First retry: ~0.1s, second: ~0.2s, third: ~0.4s
        assert 0.05 < time_between_calls[0] < 0.2
        assert 0.15 < time_between_calls[1] < 0.3
        assert 0.35 < time_between_calls[2] < 0.5
    
    @pytest.mark.asyncio
    async def test_retry_policy_success_after_retries(self):
        """RED: Test successful operation after retries"""
        policy = AsyncRetryPolicy(max_retries=3, base_delay=0.01)
        
        attempt_count = 0
        
        async def eventually_successful_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"Failure attempt {attempt_count}")
            return f"success_on_attempt_{attempt_count}"
        
        result = await policy.execute(eventually_successful_operation)
        
        assert result == "success_on_attempt_3"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_policy_max_delay_cap(self):
        """RED: Test retry delay is capped at max_delay"""
        policy = AsyncRetryPolicy(
            max_retries=5, 
            base_delay=1.0, 
            max_delay=2.0, 
            backoff_multiplier=10.0  # Would normally create very long delays
        )
        
        call_times = []
        
        async def failing_operation():
            call_times.append(time.perf_counter())
            raise Exception("Failure")
        
        with pytest.raises(RetryExhaustedError):
            await policy.execute(failing_operation)
        
        # All delays should be capped at max_delay
        time_between_calls = [call_times[i] - call_times[i-1] for i in range(1, len(call_times))]
        
        for delay in time_between_calls:
            assert delay <= 2.5  # max_delay + some overhead


class TestResilientAsyncDatabaseService:
    """Test suite for Resilient Database Service"""
    
    @pytest_asyncio.fixture
    async def mock_database_service(self):
        """Mock database service for testing"""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_resilient_service_initialization(self, mock_database_service):
        """RED: Test resilient service initialization"""
        service = ResilientAsyncDatabaseService("test.db")
        
        assert service.connection_pool is not None
        assert service.circuit_breaker is not None
        assert service.retry_policy is not None
        assert hasattr(service, 'operation_timeout')
    
    @pytest.mark.asyncio
    async def test_resilient_store_data_item_success(self, mock_database_service):
        """RED: Test resilient data storage with circuit breaker and retry"""
        service = ResilientAsyncDatabaseService("test.db")
        
        # Mock successful operation
        service._store_data_item_impl = AsyncMock(return_value=True)
        
        result = await service.store_data_item_resilient(
            "test:123", "test", "123", "content", {"key": "value"}, "2025-01-15"
        )
        
        assert result is True
        assert service.circuit_breaker.state == CircuitBreakerState.CLOSED
        service._store_data_item_impl.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resilient_service_circuit_breaker_protection(self):
        """RED: Test circuit breaker protects against cascading failures"""
        service = ResilientAsyncDatabaseService("test.db")
        
        # Mock failing operation
        async def failing_operation(*args, **kwargs):
            raise Exception("Database failure")
        
        service._store_data_item_impl = failing_operation
        
        # Trip circuit breaker
        for i in range(5):  # Default failure threshold
            with pytest.raises(Exception, match="Database failure"):
                await service.store_data_item_resilient("test", "test", "123", "content")
        
        # Circuit breaker should now be open
        assert service.circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Next call should fail with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await service.store_data_item_resilient("test", "test", "123", "content")
    
    @pytest.mark.asyncio
    async def test_resilient_service_retry_with_exponential_backoff(self):
        """RED: Test retry policy with exponential backoff"""
        service = ResilientAsyncDatabaseService("test.db")
        
        attempt_count = 0
        call_times = []
        
        async def eventually_successful_operation(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            call_times.append(time.perf_counter())
            
            if attempt_count < 3:
                raise Exception(f"Temporary failure {attempt_count}")
            return "success"
        
        service._store_data_item_impl = eventually_successful_operation
        
        start_time = time.perf_counter()
        result = await service.store_data_item_resilient("test", "test", "123", "content")
        total_time = time.perf_counter() - start_time
        
        assert result == "success"
        assert attempt_count == 3
        
        # Should have taken some time due to retries
        assert total_time > 0.02  # At least 2 retry delays
    
    @pytest.mark.asyncio
    async def test_resilient_service_operation_timeout(self):
        """RED: Test operation timeout handling in resilient service"""
        service = ResilientAsyncDatabaseService("test.db", operation_timeout=0.5)
        
        async def slow_operation(*args, **kwargs):
            await asyncio.sleep(1.0)  # Slower than timeout
            return "success"
        
        service._store_data_item_impl = slow_operation
        
        start_time = time.perf_counter()
        with pytest.raises(asyncio.TimeoutError):
            await service.store_data_item_resilient("test", "test", "123", "content")
        
        duration = time.perf_counter() - start_time
        assert 0.4 < duration < 0.7  # Should timeout around 0.5s


class TestCircuitBreakerStates:
    """Test suite for Circuit Breaker state transitions"""
    
    @pytest.mark.asyncio
    async def test_state_transition_closed_to_open(self):
        """RED: Test CLOSED -> OPEN state transition"""
        breaker = AsyncCircuitBreaker(failure_threshold=2)
        
        async def failing_operation():
            raise Exception("Failure")
        
        # Start in CLOSED state
        assert breaker.state == CircuitBreakerState.CLOSED
        
        # First failure - should stay CLOSED
        with pytest.raises(Exception):
            await breaker.call(failing_operation)
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 1
        
        # Second failure - should transition to OPEN
        with pytest.raises(Exception):
            await breaker.call(failing_operation)
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.failure_count == 2
        assert breaker.last_failure_time is not None
    
    @pytest.mark.asyncio
    async def test_state_transition_open_to_half_open(self):
        """RED: Test OPEN -> HALF_OPEN state transition after recovery timeout"""
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def operation():
            return "test"
        
        # Trip circuit breaker
        with pytest.raises(Exception):
            await breaker.call(lambda: (_ for _ in ()).throw(Exception("Failure")))
        
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Should fail immediately in OPEN state
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(operation)
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Next call should transition to HALF_OPEN and succeed
        result = await breaker.call(operation)
        assert result == "test"
        assert breaker.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_state_transition_half_open_to_open_on_failure(self):
        """RED: Test HALF_OPEN -> OPEN on failure"""
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        # Trip circuit breaker
        with pytest.raises(Exception):
            await breaker.call(lambda: (_ for _ in ()).throw(Exception("Initial failure")))
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        
        # Fail in HALF_OPEN state
        with pytest.raises(Exception, match="Recovery failure"):
            await breaker.call(lambda: (_ for _ in ()).throw(Exception("Recovery failure")))
        
        # Should go back to OPEN
        assert breaker.state == CircuitBreakerState.OPEN


class TestAsyncRetryPolicyIntegration:
    """Test suite for Retry Policy integration with Circuit Breaker"""
    
    @pytest.mark.asyncio
    async def test_retry_policy_with_circuit_breaker(self):
        """RED: Test retry policy works with circuit breaker protection"""
        breaker = AsyncCircuitBreaker(failure_threshold=10)  # High threshold
        retry_policy = AsyncRetryPolicy(max_retries=3, base_delay=0.01)
        
        attempt_count = 0
        
        async def eventually_successful_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"Retry attempt {attempt_count}")
            return "success_after_retries"
        
        # Execute with both retry and circuit breaker
        result = await breaker.call(retry_policy.execute, eventually_successful_operation)
        
        assert result == "success_after_retries"
        assert attempt_count == 3
        assert breaker.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_retry_exhausted_trips_circuit_breaker(self):
        """RED: Test retry exhaustion contributes to circuit breaker failure count"""
        breaker = AsyncCircuitBreaker(failure_threshold=2)
        retry_policy = AsyncRetryPolicy(max_retries=2, base_delay=0.01)
        
        async def always_failing_operation():
            raise Exception("Persistent failure")
        
        # First retry exhaustion
        with pytest.raises(RetryExhaustedError):
            await breaker.call(retry_policy.execute, always_failing_operation)
        
        assert breaker.failure_count == 1
        assert breaker.state == CircuitBreakerState.CLOSED
        
        # Second retry exhaustion should trip circuit breaker
        with pytest.raises(RetryExhaustedError):
            await breaker.call(retry_policy.execute, always_failing_operation)
        
        assert breaker.failure_count == 2
        assert breaker.state == CircuitBreakerState.OPEN


# Test runner for Phase 8 Circuit Breaker RED phase validation
if __name__ == "__main__":
    print("🔴 Running Phase 8 Circuit Breaker Tests (RED phase)")
    print("⚠️  These tests SHOULD FAIL since implementation doesn't exist yet")
    print("✅ This confirms TDD RED-GREEN-REFACTOR cycle is working correctly")
    
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])