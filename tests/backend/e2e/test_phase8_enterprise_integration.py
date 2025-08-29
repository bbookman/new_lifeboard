"""
Phase 8 Enterprise Architecture Integration Tests

End-to-end integration testing for all enterprise architecture components:
- Advanced Connection Pool Management
- Circuit Breaker & Resilience Patterns  
- Async Performance Monitoring & Observability
- Background Task & Queue Management

This validates the complete enterprise-grade async infrastructure.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
import time
from unittest.mock import AsyncMock

from core.async_connection_pool import AsyncDatabasePool, PoolStatistics
from core.async_circuit_breaker import AsyncCircuitBreaker, ResilientAsyncDatabaseService, AsyncRetryPolicy
from core.async_performance_monitoring import AsyncOperationTracer, AsyncHealthMonitor
from core.async_task_queue import AsyncTaskQueue, AsyncTask, AsyncSchedulerService, TaskPriority


class TestEnterpriseArchitectureIntegration:
    """Integration tests for all Phase 8 enterprise components"""
    
    @pytest_asyncio.fixture
    async def temp_db_path(self):
        """Create temporary database for integration testing"""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='_enterprise_test.db')
        temp_db.close()
        db_path = temp_db.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass
    
    @pytest_asyncio.fixture
    async def enterprise_database_service(self, temp_db_path):
        """Create resilient database service with all enterprise features"""
        service = ResilientAsyncDatabaseService(
            temp_db_path,
            operation_timeout=5.0,
            circuit_breaker_threshold=3,
            retry_max_attempts=2
        )
        
        await service.initialize()
        
        yield service
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_full_enterprise_stack_integration(self, temp_db_path):
        """Test complete enterprise stack working together"""
        # Initialize all components
        connection_pool = AsyncDatabasePool(temp_db_path, min_connections=2, max_connections=5)
        await connection_pool.initialize_pool()
        
        circuit_breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
        operation_tracer = AsyncOperationTracer()
        
        health_monitor = AsyncHealthMonitor(check_interval=0.5)
        
        task_queue = AsyncTaskQueue(max_workers=3)
        await task_queue.start_workers()
        
        try:
            # Test integrated operation flow
            async def enterprise_database_operation(data_id: str):
                async with operation_tracer.trace_operation("enterprise_db_op", data_id=data_id) as op_id:
                    # Use connection pool within circuit breaker
                    async def pooled_operation():
                        async with connection_pool.acquire_connection() as conn:
                            await conn.execute("CREATE TABLE IF NOT EXISTS test_data (id TEXT, content TEXT)")
                            await conn.execute("INSERT OR REPLACE INTO test_data VALUES (?, ?)", (data_id, f"content_{data_id}"))
                            await conn.commit()
                            return f"stored_{data_id}"
                    
                    return await circuit_breaker.call(pooled_operation)
            
            # Execute multiple operations concurrently
            tasks = []
            for i in range(10):
                operation_task = AsyncTask(
                    id=f"enterprise_task_{i}",
                    name="enterprise_db_operation",
                    operation=enterprise_database_operation,
                    args=(f"test_data_{i}",),
                    priority=TaskPriority.NORMAL
                )
                tasks.append(task_queue.enqueue_task(operation_task))
            
            # Wait for all tasks to be queued
            await asyncio.gather(*tasks)
            
            # Wait for processing
            await task_queue.wait_completion(timeout=5.0)
            
            # Verify all components are healthy
            health_result = await health_monitor.comprehensive_health_check()
            assert health_result["overall_healthy"] is True
            
            # Verify performance metrics were collected
            performance_stats = await operation_tracer.performance_metrics.get_operation_stats("enterprise_db_op")
            assert performance_stats["total_calls"] == 10
            assert performance_stats["success_count"] == 10
            
            # Verify connection pool statistics
            pool_stats = await connection_pool.get_statistics()
            assert pool_stats.total_acquisitions >= 10
            assert pool_stats.success_rate > 0.9
            
            # Verify circuit breaker remained closed
            cb_metrics = circuit_breaker.get_metrics()
            assert circuit_breaker.state.value == "CLOSED"
            assert cb_metrics.successful_calls == 10
            
        finally:
            # Cleanup
            await task_queue.stop_workers()
            await connection_pool.close_pool()
            await health_monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_enterprise_failure_handling_integration(self, temp_db_path):
        """Test enterprise stack handles failures gracefully"""
        # Setup with aggressive failure thresholds for testing
        connection_pool = AsyncDatabasePool(temp_db_path, min_connections=1, max_connections=2)
        await connection_pool.initialize_pool()
        
        circuit_breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        operation_tracer = AsyncOperationTracer()
        task_queue = AsyncTaskQueue(max_workers=2)
        await task_queue.start_workers()
        
        try:
            failure_count = 0
            
            async def sometimes_failing_operation(should_fail: bool, operation_id: str):
                nonlocal failure_count
                
                async with operation_tracer.trace_operation("resilience_test", op_id=operation_id):
                    if should_fail:
                        failure_count += 1
                        raise Exception(f"Simulated failure {failure_count}")
                    
                    async with connection_pool.acquire_connection() as conn:
                        await conn.execute("SELECT 1")
                        return f"success_{operation_id}"
            
            # Test circuit breaker directly with operations (not through task queue)
            # Use consecutive failures to properly test circuit breaker opening
            operations = [
                (True, "fail_1"),   # First failure (count=1)
                (True, "fail_2"),   # Second failure (count=2) -> circuit opens
                (True, "fail_3"),   # Should be blocked by open circuit breaker
                (False, "success_1") # Should also be blocked by open circuit breaker
            ]
            
            # Execute operations directly through circuit breaker
            for should_fail, op_id in operations:
                try:
                    await circuit_breaker.call(sometimes_failing_operation, should_fail, op_id)
                except Exception:
                    pass  # Expected failures
                
                # Small delay to allow circuit breaker state changes
                await asyncio.sleep(0.1)
            
            # Verify circuit breaker opened after failures
            assert circuit_breaker.state.value == "OPEN"
            assert circuit_breaker.failure_count >= 2
            
            # Verify performance metrics captured failures
            perf_stats = await operation_tracer.performance_metrics.get_operation_stats("resilience_test")
            assert perf_stats["error_count"] >= 2
            assert perf_stats["error_rate"] > 0
            
        finally:
            await task_queue.stop_workers()
            await connection_pool.close_pool()
    
    @pytest.mark.asyncio
    async def test_enterprise_performance_under_load(self, enterprise_database_service):
        """Test enterprise architecture performance under concurrent load"""
        # Setup performance monitoring
        operation_tracer = AsyncOperationTracer()
        health_monitor = AsyncHealthMonitor()
        
        # Track performance metrics
        start_time = time.perf_counter()
        
        async def load_test_operation(batch_id: int, item_id: int):
            async with operation_tracer.trace_operation("load_test", batch_id=batch_id, item_id=item_id):
                return await enterprise_database_service.store_data_item_resilient(
                    f"load_test:{batch_id}:{item_id}",
                    "load_test",
                    f"{batch_id}_{item_id}",
                    f"Load test content batch {batch_id} item {item_id}",
                    {"batch_id": batch_id, "load_test": True},
                    "2025-01-15"
                )
        
        # Execute concurrent load test
        batch_size = 20
        num_batches = 5
        
        all_tasks = []
        for batch in range(num_batches):
            batch_tasks = [
                load_test_operation(batch, item)
                for item in range(batch_size)
            ]
            all_tasks.extend(batch_tasks)
        
        # Execute all operations concurrently
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        total_time = time.perf_counter() - start_time
        
        # Verify results
        successful_operations = [r for r in results if not isinstance(r, Exception)]
        failed_operations = [r for r in results if isinstance(r, Exception)]
        
        total_operations = batch_size * num_batches
        success_rate = len(successful_operations) / total_operations
        
        # Enterprise architecture should handle load well
        assert success_rate > 0.95  # 95%+ success rate
        assert total_time < 10.0    # Complete within 10 seconds
        
        # Verify performance metrics
        load_stats = await operation_tracer.performance_metrics.get_operation_stats("load_test")
        assert load_stats["total_calls"] == total_operations
        assert load_stats["avg_duration"] < 1.0  # Average operation under 1s
        
        # Verify system health after load
        health_result = await health_monitor.comprehensive_health_check()
        assert health_result["overall_healthy"] is True
        
        print(f"\n🏆 Load Test Results:")
        print(f"   Total Operations: {total_operations}")
        print(f"   Success Rate: {success_rate:.1%}")
        print(f"   Total Time: {total_time:.2f}s")
        print(f"   Avg Response Time: {load_stats['avg_duration']:.3f}s")
        print(f"   System Health: {'✅ Healthy' if health_result['overall_healthy'] else '❌ Degraded'}")
    
    @pytest.mark.asyncio
    async def test_enterprise_recovery_patterns(self, temp_db_path):
        """Test enterprise recovery patterns work end-to-end"""
        # Setup resilient service
        resilient_service = ResilientAsyncDatabaseService(
            temp_db_path,
            circuit_breaker_threshold=2,
            retry_max_attempts=3
        )
        await resilient_service.initialize()
        
        operation_tracer = AsyncOperationTracer()
        
        try:
            # Test recovery from temporary failures
            failure_simulation_count = 0
            
            async def recovery_test_operation(item_id: str):
                nonlocal failure_simulation_count
                
                async with operation_tracer.trace_operation("recovery_test", item_id=item_id):
                    # Simulate temporary failures followed by recovery
                    failure_simulation_count += 1
                    if failure_simulation_count <= 4:  # First 4 operations fail
                        raise Exception(f"Temporary failure {failure_simulation_count}")
                    
                    # Operations 5+ succeed
                    return await resilient_service.store_data_item_resilient(
                        f"recovery:{item_id}",
                        "recovery_test",
                        item_id,
                        f"Recovery test content {item_id}",
                        {"recovery_test": True},
                        "2025-01-15"
                    )
            
            # Execute operations that will initially fail then recover
            results = []
            for i in range(8):  # 4 failures, 4 successes
                try:
                    result = await recovery_test_operation(f"item_{i}")
                    results.append(("success", result))
                except Exception as e:
                    results.append(("failure", str(e)))
                
                # Small delay to allow circuit breaker state changes
                await asyncio.sleep(0.1)
            
            # Analyze results
            failures = [r for r in results if r[0] == "failure"]
            successes = [r for r in results if r[0] == "success"]
            
            # Should have some failures followed by recoveries
            assert len(failures) > 0
            assert len(successes) > 0
            
            # Verify performance monitoring captured the recovery pattern
            recovery_stats = await operation_tracer.performance_metrics.get_operation_stats("recovery_test")
            assert recovery_stats["total_calls"] == 8
            assert recovery_stats["error_count"] > 0
            assert recovery_stats["success_count"] > 0
            
        finally:
            await resilient_service.close()
    
    @pytest.mark.asyncio
    async def test_enterprise_monitoring_comprehensive_health(self, enterprise_database_service):
        """Test comprehensive enterprise health monitoring"""
        # Setup monitoring stack
        operation_tracer = AsyncOperationTracer()
        health_monitor = AsyncHealthMonitor(check_interval=0.2)
        
        # Register custom health checks for enterprise components
        async def database_service_health():
            metrics = await enterprise_database_service.get_metrics()
            return {
                "healthy": metrics["circuit_breaker"]["state"] == "CLOSED",
                "metrics": metrics
            }
        
        health_monitor.register_health_check("enterprise_database", database_service_health)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        try:
            # Execute operations while monitoring
            async def monitored_operation(op_id: str):
                async with operation_tracer.trace_operation("enterprise_monitoring", operation_id=op_id):
                    return await enterprise_database_service.store_data_item_resilient(
                        f"monitor:{op_id}",
                        "monitoring_test",
                        op_id,
                        f"Monitoring test content {op_id}",
                        {"monitoring_test": True},
                        "2025-01-15"
                    )
            
            # Execute operations
            tasks = [monitored_operation(f"op_{i}") for i in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Wait for monitoring cycles
            await asyncio.sleep(0.5)
            
            # Get comprehensive health check
            health_result = await health_monitor.comprehensive_health_check()
            
            # Verify comprehensive health monitoring
            assert health_result["overall_healthy"] is True
            assert "enterprise_database" in health_result["components"]
            assert "database_pool" in health_result["components"]
            assert "resource_utilization" in health_result["components"]
            assert "async_tasks" in health_result["components"]
            
            # Verify enterprise database component
            enterprise_health = health_result["components"]["enterprise_database"]
            assert enterprise_health["healthy"] is True
            assert "metrics" in enterprise_health["result"]
            
            # Verify performance tracking
            monitoring_stats = await operation_tracer.performance_metrics.get_operation_stats("enterprise_monitoring")
            assert monitoring_stats["total_calls"] == 5
            assert monitoring_stats["success_count"] == 5
            
            print(f"\n🏥 Enterprise Health Check Results:")
            print(f"   Overall Health: {'✅ Healthy' if health_result['overall_healthy'] else '❌ Unhealthy'}")
            print(f"   Components Monitored: {len(health_result['components'])}")
            print(f"   Check Duration: {health_result['check_duration']:.3f}s")
            print(f"   Operations Completed: {monitoring_stats['total_calls']}")
            
        finally:
            await health_monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_enterprise_scheduler_integration(self, temp_db_path):
        """Test enterprise scheduler with task queue and database operations"""
        # Setup enterprise scheduler with mock config
        class MockConfig:
            max_concurrent_jobs = 3
            health_check_interval = 1.0
            task_timeout = 5.0
        
        config = MockConfig()
        scheduler_service = AsyncSchedulerService(config)
        
        # Setup database for scheduled operations
        resilient_db = ResilientAsyncDatabaseService(temp_db_path)
        await resilient_db.initialize()
        
        operation_tracer = AsyncOperationTracer()
        
        try:
            # Start scheduler service
            await scheduler_service.start_service()
            
            # Track scheduled executions
            scheduled_executions = []
            
            async def scheduled_database_operation():
                async with operation_tracer.trace_operation("scheduled_db_op"):
                    execution_time = time.time()
                    scheduled_executions.append(execution_time)
                    
                    # Perform database operation
                    return await resilient_db.store_data_item_resilient(
                        f"scheduled:{len(scheduled_executions)}",
                        "scheduled",
                        str(len(scheduled_executions)),
                        f"Scheduled content {len(scheduled_executions)}",
                        {"scheduled_test": True},
                        "2025-01-15"
                    )
            
            # Schedule recurring database operations
            job_id = await scheduler_service.schedule_recurring_task(
                scheduled_database_operation,
                "*/0.2 * * * *"  # Every 0.2 seconds
            )
            
            assert job_id is not None
            
            # Wait for scheduled executions
            await asyncio.sleep(0.7)
            
            # Verify scheduled executions occurred
            assert len(scheduled_executions) >= 3
            
            # Verify scheduler health
            scheduler_health = await scheduler_service.get_health_status()
            assert scheduler_health["scheduler"]["is_running"] is True
            assert scheduler_health["scheduler"]["scheduled_jobs"] == 1
            assert scheduler_health["task_queue"]["active_workers"] > 0
            
            # Verify database operations were successful
            scheduled_stats = await operation_tracer.performance_metrics.get_operation_stats("scheduled_db_op")
            assert scheduled_stats["total_calls"] >= 3
            assert scheduled_stats["error_count"] == 0
            
            print(f"\n📅 Scheduler Integration Results:")
            print(f"   Scheduled Executions: {len(scheduled_executions)}")
            print(f"   Scheduler Health: {scheduler_health}")
            print(f"   Database Operations: {scheduled_stats['total_calls']} successful")
            
        finally:
            await scheduler_service.stop_service()
            await resilient_db.close()
    
    @pytest.mark.asyncio
    async def test_enterprise_architecture_performance_benchmarks(self, temp_db_path):
        """Test enterprise architecture meets performance benchmarks"""
        # Setup enterprise stack
        resilient_db = ResilientAsyncDatabaseService(temp_db_path)
        await resilient_db.initialize()
        
        operation_tracer = AsyncOperationTracer()
        
        # Performance benchmarks
        OPERATIONS_COUNT = 100
        MAX_TOTAL_TIME = 5.0  # 5 seconds for 100 operations
        MAX_AVG_OPERATION_TIME = 0.1  # 100ms average per operation
        MIN_SUCCESS_RATE = 0.98  # 98% success rate
        
        try:
            start_time = time.perf_counter()
            
            async def benchmark_operation(op_id: int):
                async with operation_tracer.trace_operation("benchmark", operation_id=op_id):
                    return await resilient_db.store_data_item_resilient(
                        f"benchmark:{op_id}",
                        "benchmark",
                        str(op_id),
                        f"Benchmark content {op_id}",
                        {"benchmark": True, "operation_id": op_id},
                        "2025-01-15"
                    )
            
            # Execute benchmark operations
            tasks = [benchmark_operation(i) for i in range(OPERATIONS_COUNT)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_time = time.perf_counter() - start_time
            
            # Analyze results
            successful_ops = [r for r in results if not isinstance(r, Exception)]
            failed_ops = [r for r in results if isinstance(r, Exception)]
            
            success_rate = len(successful_ops) / OPERATIONS_COUNT
            
            # Get performance metrics
            benchmark_stats = await operation_tracer.performance_metrics.get_operation_stats("benchmark")
            avg_operation_time = benchmark_stats["avg_duration"]
            
            # Get enterprise metrics
            enterprise_metrics = await resilient_db.get_metrics()
            
            print(f"\n📊 Enterprise Performance Benchmark Results:")
            print(f"   Operations: {OPERATIONS_COUNT}")
            print(f"   Total Time: {total_time:.2f}s (target: <{MAX_TOTAL_TIME}s)")
            print(f"   Success Rate: {success_rate:.1%} (target: >{MIN_SUCCESS_RATE:.1%})")
            print(f"   Avg Operation Time: {avg_operation_time:.3f}s (target: <{MAX_AVG_OPERATION_TIME}s)")
            print(f"   Circuit Breaker State: {enterprise_metrics['circuit_breaker']['state']}")
            print(f"   Connection Pool Stats: {enterprise_metrics['connection_pool']}")
            
            # Assert performance benchmarks
            assert total_time < MAX_TOTAL_TIME, f"Total time {total_time:.2f}s exceeded {MAX_TOTAL_TIME}s"
            assert success_rate > MIN_SUCCESS_RATE, f"Success rate {success_rate:.1%} below {MIN_SUCCESS_RATE:.1%}"
            assert avg_operation_time < MAX_AVG_OPERATION_TIME, f"Avg operation time {avg_operation_time:.3f}s exceeded {MAX_AVG_OPERATION_TIME}s"
            
            # Enterprise architecture should remain healthy
            assert enterprise_metrics["circuit_breaker"]["state"] == "CLOSED"
            assert enterprise_metrics["connection_pool"]["success_rate"] > 0.95
            
        finally:
            await resilient_db.close()


# Performance test runner
if __name__ == "__main__":
    print("🏗️  Running Phase 8 Enterprise Architecture Integration Tests")
    print("🎯 Testing complete enterprise stack under production-like conditions")
    
    # Run with performance reporting
    pytest.main([__file__, "-v", "--tb=short", "-s"])