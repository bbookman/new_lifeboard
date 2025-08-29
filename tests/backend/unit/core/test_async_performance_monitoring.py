"""
Test suite for Async Performance Monitoring & Observability

This test module follows TDD principles for Phase 8 enterprise architecture implementation.
All tests are written first (RED phase) before implementation (GREEN phase).
"""

import pytest
import pytest_asyncio
import asyncio
import time
import uuid
from unittest.mock import AsyncMock, patch
from typing import Dict, Any

# Import the classes we'll implement (will fail initially - RED phase)
try:
    from core.async_performance_monitoring import (
        AsyncOperationTracer,
        AsyncPerformanceCollector,
        AsyncHealthMonitor,
        PerformanceMetrics,
        HealthCheckResult,
        OperationContext
    )
except ImportError:
    # Expected during RED phase - these don't exist yet
    pass


class TestAsyncOperationTracer:
    """Test suite for Async Operation Tracing"""
    
    @pytest.mark.asyncio
    async def test_operation_tracer_initialization(self):
        """RED: Test operation tracer initialization"""
        tracer = AsyncOperationTracer()
        
        assert tracer.operations == {}
        assert tracer.performance_metrics is not None
        assert hasattr(tracer, 'trace_operation')
    
    @pytest.mark.asyncio
    async def test_operation_tracing_basic_flow(self):
        """RED: Test basic operation tracing with context"""
        tracer = AsyncOperationTracer()
        
        async with tracer.trace_operation("test_operation", user_id="123", query_type="SELECT") as op_id:
            # Simulate some work
            await asyncio.sleep(0.1)
            
            # Verify operation is being tracked
            assert op_id in tracer.operations
            assert tracer.operations[op_id]["name"] == "test_operation"
            assert tracer.operations[op_id]["context"]["user_id"] == "123"
            assert tracer.operations[op_id]["context"]["query_type"] == "SELECT"
        
        # After context exit, operation should be cleaned up
        assert op_id not in tracer.operations
    
    @pytest.mark.asyncio
    async def test_operation_tracing_correlation_tracking(self):
        """RED: Test operation correlation and nested tracing"""
        tracer = AsyncOperationTracer()
        
        async with tracer.trace_operation("parent_operation", request_id="req_123") as parent_id:
            await asyncio.sleep(0.05)
            
            # Nested operation
            async with tracer.trace_operation("nested_db_call", query_type="INSERT", parent_id=parent_id) as nested_id:
                await asyncio.sleep(0.02)
                
                # Both operations should be tracked
                assert parent_id in tracer.operations
                assert nested_id in tracer.operations
                
                # Verify correlation
                assert tracer.operations[nested_id]["context"]["parent_id"] == parent_id
    
    @pytest.mark.asyncio
    async def test_operation_tracing_performance_recording(self):
        """RED: Test performance metrics are recorded correctly"""
        tracer = AsyncOperationTracer()
        
        async with tracer.trace_operation("performance_test", metric_type="latency"):
            await asyncio.sleep(0.1)  # Simulate 100ms operation
        
        # Check that performance metrics were recorded
        metrics = await tracer.performance_metrics.get_operation_stats("performance_test")
        
        assert metrics["total_calls"] == 1
        assert 0.08 < metrics["avg_duration"] < 0.15  # Around 100ms with overhead
        assert metrics["min_duration"] > 0
        assert metrics["max_duration"] > 0
    
    @pytest.mark.asyncio
    async def test_operation_tracing_exception_handling(self):
        """RED: Test operation tracing handles exceptions properly"""
        tracer = AsyncOperationTracer()
        
        with pytest.raises(ValueError, match="Test exception"):
            async with tracer.trace_operation("failing_operation", expected_to_fail=True):
                await asyncio.sleep(0.01)
                raise ValueError("Test exception")
        
        # Exception should be recorded in metrics
        metrics = await tracer.performance_metrics.get_operation_stats("failing_operation")
        assert metrics["total_calls"] == 1
        assert metrics["error_count"] == 1
        assert metrics["error_rate"] > 0


class TestAsyncPerformanceCollector:
    """Test suite for Async Performance Metrics Collection"""
    
    @pytest.mark.asyncio
    async def test_performance_collector_initialization(self):
        """RED: Test performance collector initialization"""
        collector = AsyncPerformanceCollector()
        
        assert collector.metrics == {}
        assert hasattr(collector, 'record_operation')
        assert hasattr(collector, 'get_operation_stats')
    
    @pytest.mark.asyncio
    async def test_performance_collector_record_operation(self):
        """RED: Test recording operation performance metrics"""
        collector = AsyncPerformanceCollector()
        
        # Record several operations
        await collector.record_operation("db_query", 0.150, query_type="SELECT", table="data_items")
        await collector.record_operation("db_query", 0.200, query_type="SELECT", table="data_items")
        await collector.record_operation("db_query", 0.100, query_type="INSERT", table="chat_messages")
        
        # Get aggregated stats
        stats = await collector.get_operation_stats("db_query")
        
        assert stats["total_calls"] == 3
        assert stats["avg_duration"] == 0.150  # (0.15 + 0.20 + 0.10) / 3
        assert stats["min_duration"] == 0.100
        assert stats["max_duration"] == 0.200
        
        # Get filtered stats
        select_stats = await collector.get_operation_stats("db_query", query_type="SELECT")
        assert select_stats["total_calls"] == 2
        assert select_stats["avg_duration"] == 0.175  # (0.15 + 0.20) / 2
    
    @pytest.mark.asyncio
    async def test_performance_collector_percentiles(self):
        """RED: Test performance percentile calculations"""
        collector = AsyncPerformanceCollector()
        
        # Record operations with known distribution
        durations = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for duration in durations:
            await collector.record_operation("test_op", duration)
        
        stats = await collector.get_operation_stats("test_op")
        
        # Verify percentile calculations
        assert abs(stats["p50"] - 0.55) < 0.1  # Median
        assert abs(stats["p95"] - 0.95) < 0.1  # 95th percentile
        assert abs(stats["p99"] - 0.99) < 0.1  # 99th percentile
    
    @pytest.mark.asyncio
    async def test_performance_collector_error_tracking(self):
        """RED: Test error rate tracking in performance metrics"""
        collector = AsyncPerformanceCollector()
        
        # Record mix of successful and failed operations
        await collector.record_operation("mixed_op", 0.1, success=True)
        await collector.record_operation("mixed_op", 0.2, success=False, error="Connection timeout")
        await collector.record_operation("mixed_op", 0.1, success=True)
        await collector.record_operation("mixed_op", 0.3, success=False, error="Database locked")
        
        stats = await collector.get_operation_stats("mixed_op")
        
        assert stats["total_calls"] == 4
        assert stats["success_count"] == 2
        assert stats["error_count"] == 2
        assert stats["error_rate"] == 0.5  # 2 errors / 4 total
        assert "Connection timeout" in stats["error_types"]
        assert "Database locked" in stats["error_types"]


class TestAsyncHealthMonitor:
    """Test suite for Async Health Monitoring"""
    
    @pytest.mark.asyncio
    async def test_health_monitor_initialization(self):
        """RED: Test health monitor initialization"""
        monitor = AsyncHealthMonitor(check_interval=30.0)
        
        assert monitor.check_interval == 30.0
        assert monitor.health_checks == {}
        assert monitor.is_monitoring is False
    
    @pytest.mark.asyncio
    async def test_health_monitor_comprehensive_health_check(self):
        """RED: Test comprehensive health check execution"""
        monitor = AsyncHealthMonitor()
        
        # Mock health check functions
        async def mock_database_health():
            return HealthCheckResult(
                component="database_pool",
                healthy=True,
                response_time=0.05,
                metadata={"connections": 5, "queue_size": 0}
            )
        
        async def mock_service_health():
            return HealthCheckResult(
                component="service_dependencies", 
                healthy=True,
                response_time=0.02,
                metadata={"services": ["chat", "ingestion", "sync"]}
            )
        
        # Register health checks
        monitor.register_health_check("database_pool", mock_database_health)
        monitor.register_health_check("service_dependencies", mock_service_health)
        
        # Execute comprehensive health check
        result = await monitor.comprehensive_health_check()
        
        assert result["overall_healthy"] is True
        assert len(result["components"]) == 2
        assert result["components"]["database_pool"]["healthy"] is True
        assert result["components"]["service_dependencies"]["healthy"] is True
        assert result["timestamp"] is not None
    
    @pytest.mark.asyncio
    async def test_health_monitor_failure_detection(self):
        """RED: Test health monitor detects and reports failures"""
        monitor = AsyncHealthMonitor()
        
        async def failing_health_check():
            raise Exception("Service unavailable")
        
        async def timeout_health_check():
            await asyncio.sleep(10)  # Will timeout
            return HealthCheckResult("timeout_service", True, 10.0)
        
        monitor.register_health_check("failing_service", failing_health_check)
        monitor.register_health_check("timeout_service", timeout_health_check)
        
        # Execute health check with timeout
        result = await monitor.comprehensive_health_check(timeout=1.0)
        
        assert result["overall_healthy"] is False
        assert result["components"]["failing_service"]["healthy"] is False
        assert "Service unavailable" in result["components"]["failing_service"]["error"]
        assert result["components"]["timeout_service"]["healthy"] is False
        assert result["components"]["timeout_service"]["status"] == "timeout"
    
    @pytest.mark.asyncio
    async def test_health_monitor_background_monitoring(self):
        """RED: Test background health monitoring with periodic checks"""
        monitor = AsyncHealthMonitor(check_interval=0.1)
        
        check_count = 0
        
        async def counting_health_check():
            nonlocal check_count
            check_count += 1
            return HealthCheckResult("test_service", True, 0.01)
        
        monitor.register_health_check("test_service", counting_health_check)
        
        # Start background monitoring
        await monitor.start_monitoring()
        assert monitor.is_monitoring is True
        
        # Wait for several checks
        await asyncio.sleep(0.35)
        
        # Stop monitoring
        await monitor.stop_monitoring()
        assert monitor.is_monitoring is False
        
        # Should have performed multiple checks
        assert check_count >= 3
    
    @pytest.mark.asyncio
    async def test_health_monitor_resource_utilization_check(self):
        """RED: Test resource utilization monitoring"""
        monitor = AsyncHealthMonitor()
        
        # Execute resource utilization check
        result = await monitor._check_resource_utilization()
        
        assert isinstance(result, HealthCheckResult)
        assert result.component == "resource_utilization"
        assert "cpu_percent" in result.metadata
        assert "memory_percent" in result.metadata
        assert "disk_usage" in result.metadata
        
        # Should include performance thresholds
        cpu_threshold = result.metadata.get("cpu_threshold", 80)
        memory_threshold = result.metadata.get("memory_threshold", 85)
        
        assert 0 < cpu_threshold <= 100
        assert 0 < memory_threshold <= 100
    
    @pytest.mark.asyncio
    async def test_health_monitor_background_task_monitoring(self):
        """RED: Test background asyncio task monitoring"""
        monitor = AsyncHealthMonitor()
        
        # Create some background tasks
        test_tasks = [
            asyncio.create_task(asyncio.sleep(1)),
            asyncio.create_task(asyncio.sleep(2)),
            asyncio.create_task(asyncio.sleep(0.1))
        ]
        
        # Check background tasks
        result = await monitor._check_background_tasks()
        
        assert isinstance(result, HealthCheckResult)
        assert result.component == "async_tasks"
        assert "total_tasks" in result.metadata
        assert "pending_tasks" in result.metadata
        assert "completed_tasks" in result.metadata
        
        # Should detect our test tasks
        total_tasks = result.metadata["total_tasks"]
        assert total_tasks >= 3  # At least our test tasks
        
        # Cleanup
        for task in test_tasks:
            task.cancel()
        
        try:
            await asyncio.gather(*test_tasks, return_exceptions=True)
        except:
            pass


class TestPerformanceMetrics:
    """Test suite for Performance Metrics data structures"""
    
    @pytest.mark.asyncio
    async def test_performance_metrics_creation(self):
        """RED: Test performance metrics data structure"""
        metrics = PerformanceMetrics(
            operation_name="test_operation",
            total_calls=100,
            successful_calls=95,
            failed_calls=5,
            avg_duration=0.150,
            min_duration=0.050,
            max_duration=0.500
        )
        
        assert metrics.operation_name == "test_operation"
        assert metrics.total_calls == 100
        assert metrics.success_rate == 0.95  # 95/100
        assert metrics.error_rate == 0.05   # 5/100
        assert metrics.avg_duration == 0.150
    
    @pytest.mark.asyncio
    async def test_health_check_result_structure(self):
        """RED: Test health check result data structure"""
        result = HealthCheckResult(
            component="database_pool",
            healthy=True,
            response_time=0.025,
            timestamp=time.time(),
            metadata={
                "connections": 5,
                "queue_size": 2,
                "utilization": 0.8
            }
        )
        
        assert result.component == "database_pool"
        assert result.healthy is True
        assert result.response_time == 0.025
        assert result.metadata["connections"] == 5
        assert result.metadata["utilization"] == 0.8
    
    @pytest.mark.asyncio
    async def test_operation_context_creation(self):
        """RED: Test operation context for tracing"""
        context = OperationContext(
            operation_id=str(uuid.uuid4()),
            operation_name="store_data_item",
            start_time=time.perf_counter(),
            user_id="user_123",
            request_id="req_456",
            metadata={"table": "data_items", "namespace": "limitless"}
        )
        
        assert context.operation_name == "store_data_item"
        assert context.user_id == "user_123"
        assert context.request_id == "req_456"
        assert context.metadata["table"] == "data_items"
        assert context.metadata["namespace"] == "limitless"
        
        # Calculate duration
        end_time = time.perf_counter()
        duration = context.calculate_duration(end_time)
        assert duration >= 0


class TestAsyncPerformanceIntegration:
    """Test suite for integrated performance monitoring"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_performance_tracking(self):
        """RED: Test complete performance tracking flow"""
        tracer = AsyncOperationTracer()
        monitor = AsyncHealthMonitor()
        
        # Simulate database operation with monitoring
        async def simulated_database_operation():
            async with tracer.trace_operation("db_operation", table="data_items") as op_id:
                await asyncio.sleep(0.05)  # Simulate DB work
                return {"id": "test:123", "status": "stored"}
        
        # Execute operation
        result = await simulated_database_operation()
        
        # Verify result
        assert result["id"] == "test:123"
        assert result["status"] == "stored"
        
        # Verify performance was tracked
        metrics = await tracer.performance_metrics.get_operation_stats("db_operation")
        assert metrics["total_calls"] == 1
        assert metrics["avg_duration"] > 0.04
        
        # Execute health check
        health_result = await monitor.comprehensive_health_check()
        assert "timestamp" in health_result
    
    @pytest.mark.asyncio
    async def test_concurrent_operation_performance_tracking(self):
        """RED: Test performance tracking under concurrent load"""
        tracer = AsyncOperationTracer()
        
        async def concurrent_operation(operation_id: int):
            async with tracer.trace_operation(f"concurrent_op_{operation_id}", worker_id=operation_id):
                await asyncio.sleep(0.01 * (operation_id % 3 + 1))  # Variable duration
                return f"result_{operation_id}"
        
        # Execute 20 concurrent operations
        tasks = [concurrent_operation(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        
        # Verify all operations completed
        assert len(results) == 20
        assert all("result_" in r for r in results)
        
        # Verify performance metrics for each operation
        for i in range(20):
            metrics = await tracer.performance_metrics.get_operation_stats(f"concurrent_op_{i}")
            assert metrics["total_calls"] == 1
            assert metrics["avg_duration"] > 0
    
    @pytest.mark.asyncio
    async def test_performance_metrics_aggregation(self):
        """RED: Test aggregated performance metrics across operations"""
        collector = AsyncPerformanceCollector()
        
        # Record various operations
        operations = [
            ("store_item", 0.1, {"table": "data_items"}),
            ("store_item", 0.15, {"table": "data_items"}),
            ("get_items", 0.05, {"table": "data_items"}),
            ("get_items", 0.08, {"table": "data_items"}),
            ("store_chat", 0.02, {"table": "chat_messages"}),
        ]
        
        for op_name, duration, metadata in operations:
            await collector.record_operation(op_name, duration, **metadata)
        
        # Get aggregated metrics
        all_metrics = await collector.get_all_metrics()
        
        assert "store_item" in all_metrics
        assert "get_items" in all_metrics
        assert "store_chat" in all_metrics
        
        # Verify store_item aggregation
        store_metrics = all_metrics["store_item"]
        assert store_metrics["total_calls"] == 2
        assert store_metrics["avg_duration"] == 0.125  # (0.1 + 0.15) / 2


# Test runner for Phase 8 Performance Monitoring RED phase validation
if __name__ == "__main__":
    print("🔴 Running Phase 8 Performance Monitoring Tests (RED phase)")
    print("⚠️  These tests SHOULD FAIL since implementation doesn't exist yet")
    print("✅ This confirms TDD RED-GREEN-REFACTOR cycle is working correctly")
    
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])