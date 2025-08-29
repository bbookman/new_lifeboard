"""
Test suite for Async Task Queue & Background Processing

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
    from core.async_task_queue import (
        AsyncTaskQueue,
        AsyncTask,
        AsyncTaskPersistence,
        AsyncCronScheduler,
        AsyncSchedulerService,
        TaskExecutionError,
        TaskTimeoutError,
        TaskPriority
    )
    from config.models import SchedulerConfig
except ImportError:
    # Expected during RED phase - these don't exist yet
    pass


class TestAsyncTask:
    """Test suite for Async Task abstraction"""
    
    @pytest.mark.asyncio
    async def test_async_task_creation(self):
        """RED: Test async task creation with metadata"""
        async def sample_operation(data: str):
            await asyncio.sleep(0.01)
            return f"processed_{data}"
        
        task = AsyncTask(
            id="test_task_001",
            name="sample_processing",
            operation=sample_operation,
            args=("test_data",),
            priority=TaskPriority.NORMAL,
            timeout=5.0,
            metadata={"source": "test", "retry_count": 0}
        )
        
        assert task.id == "test_task_001"
        assert task.name == "sample_processing"
        assert task.priority == TaskPriority.NORMAL
        assert task.timeout == 5.0
        assert task.metadata["source"] == "test"
        
        # Execute task
        result = await task.execute()
        assert result == "processed_test_data"
    
    @pytest.mark.asyncio
    async def test_async_task_timeout_handling(self):
        """RED: Test task timeout enforcement"""
        async def slow_operation():
            await asyncio.sleep(1.0)  # Slower than timeout
            return "completed"
        
        task = AsyncTask(
            id="slow_task",
            name="slow_processing",
            operation=slow_operation,
            timeout=0.1
        )
        
        start_time = time.perf_counter()
        with pytest.raises(TaskTimeoutError):
            await task.execute()
        
        duration = time.perf_counter() - start_time
        assert 0.05 < duration < 0.2  # Should timeout around 0.1s


class TestAsyncTaskQueue:
    """Test suite for Priority-based Async Task Queue"""
    
    @pytest.mark.asyncio
    async def test_task_queue_initialization(self):
        """RED: Test task queue initialization with workers"""
        queue = AsyncTaskQueue(max_workers=5)
        
        assert queue.max_workers == 5
        assert queue.priority_queue is not None
        assert queue.workers == []
        assert queue.task_persistence is not None
    
    @pytest.mark.asyncio
    async def test_task_queue_worker_startup(self):
        """RED: Test worker startup and management"""
        queue = AsyncTaskQueue(max_workers=3)
        
        # Start workers
        await queue.start_workers()
        
        assert len(queue.workers) == 3
        assert all(isinstance(worker, asyncio.Task) for worker in queue.workers)
        assert all(not worker.done() for worker in queue.workers)
        
        # Stop workers
        await queue.stop_workers()
        
        # All workers should be cancelled
        await asyncio.sleep(0.1)  # Allow cleanup
        assert all(worker.cancelled() or worker.done() for worker in queue.workers)
    
    @pytest.mark.asyncio
    async def test_task_queue_priority_processing(self):
        """RED: Test priority-based task processing order"""
        queue = AsyncTaskQueue(max_workers=1)  # Single worker for predictable order
        await queue.start_workers()
        
        execution_order = []
        
        async def create_test_task(name: str, priority: int):
            async def task_operation():
                execution_order.append(name)
                await asyncio.sleep(0.01)
                return f"completed_{name}"
            
            return AsyncTask(
                id=f"task_{name}",
                name=name,
                operation=task_operation,
                priority=priority
            )
        
        # Enqueue tasks with different priorities (lower number = higher priority)
        await queue.enqueue_task(await create_test_task("low_priority", 10))
        await queue.enqueue_task(await create_test_task("high_priority", 1))
        await queue.enqueue_task(await create_test_task("medium_priority", 5))
        
        # Wait for processing
        await queue.wait_completion(timeout=2.0)
        
        # Verify execution order
        assert execution_order == ["high_priority", "medium_priority", "low_priority"]
        
        await queue.stop_workers()
    
    @pytest.mark.asyncio
    async def test_task_queue_concurrent_processing(self):
        """RED: Test concurrent task processing with multiple workers"""
        queue = AsyncTaskQueue(max_workers=3)
        await queue.start_workers()
        
        completed_tasks = []
        
        async def create_concurrent_task(task_id: int):
            async def task_operation():
                await asyncio.sleep(0.02)  # Short operation
                completed_tasks.append(task_id)
                return f"task_{task_id}_done"
            
            return AsyncTask(
                id=f"concurrent_{task_id}",
                name=f"concurrent_task_{task_id}",
                operation=task_operation,
                priority=TaskPriority.NORMAL
            )
        
        # Enqueue 10 tasks
        tasks = []
        for i in range(10):
            task = await create_concurrent_task(i)
            tasks.append(task)
            await queue.enqueue_task(task)
        
        # Wait for all tasks to complete
        await queue.wait_completion(timeout=3.0)
        
        # All tasks should have completed
        assert len(completed_tasks) == 10
        assert set(completed_tasks) == set(range(10))
        
        await queue.stop_workers()
    
    @pytest.mark.asyncio
    async def test_task_queue_error_handling(self):
        """RED: Test task queue handles task failures gracefully"""
        queue = AsyncTaskQueue(max_workers=2)
        await queue.start_workers()
        
        results = []
        
        async def create_test_task(should_fail: bool, task_id: str):
            async def task_operation():
                if should_fail:
                    raise ValueError(f"Task {task_id} failed")
                results.append(f"success_{task_id}")
                return f"completed_{task_id}"
            
            return AsyncTask(
                id=task_id,
                name=f"test_task_{task_id}",
                operation=task_operation
            )
        
        # Mix of successful and failing tasks
        await queue.enqueue_task(await create_test_task(False, "success_1"))
        await queue.enqueue_task(await create_test_task(True, "fail_1"))
        await queue.enqueue_task(await create_test_task(False, "success_2"))
        await queue.enqueue_task(await create_test_task(True, "fail_2"))
        
        # Wait for processing
        await queue.wait_completion(timeout=2.0)
        
        # Successful tasks should complete, failures should be logged but not crash workers
        assert len(results) == 2
        assert "success_success_1" in results
        assert "success_success_2" in results
        
        # Workers should still be running
        assert all(not worker.done() for worker in queue.workers)
        
        await queue.stop_workers()
    
    @pytest.mark.asyncio
    async def test_task_persistence_integration(self):
        """RED: Test task persistence integration"""
        queue = AsyncTaskQueue(max_workers=1)
        
        async def persistent_task_operation():
            return "persistent_result"
        
        task = AsyncTask(
            id="persistent_task_001",
            name="persistent_operation",
            operation=persistent_task_operation
        )
        
        # Enqueue task (should be persisted)
        await queue.enqueue_task(task)
        
        # Verify task was persisted
        persisted_task = await queue.task_persistence.get_task("persistent_task_001")
        assert persisted_task is not None
        assert persisted_task.id == "persistent_task_001"
        
        # Start workers and process
        await queue.start_workers()
        await queue.wait_completion(timeout=1.0)
        
        # Task should be marked as completed in persistence
        task_status = await queue.task_persistence.get_task_status("persistent_task_001")
        assert task_status == "completed"
        
        await queue.stop_workers()


class TestAsyncTaskPersistence:
    """Test suite for Async Task Persistence"""
    
    @pytest.mark.asyncio
    async def test_task_persistence_save_and_retrieve(self):
        """RED: Test saving and retrieving tasks"""
        persistence = AsyncTaskPersistence()
        
        async def sample_operation():
            return "test"
        
        task = AsyncTask(
            id="persist_test_001",
            name="persistence_test",
            operation=sample_operation,
            priority=TaskPriority.HIGH,
            metadata={"source": "test_suite"}
        )
        
        # Save task
        await persistence.save_task(task)
        
        # Retrieve task
        retrieved_task = await persistence.get_task("persist_test_001")
        
        assert retrieved_task is not None
        assert retrieved_task.id == "persist_test_001"
        assert retrieved_task.name == "persistence_test"
        assert retrieved_task.priority == TaskPriority.HIGH
        assert retrieved_task.metadata["source"] == "test_suite"
    
    @pytest.mark.asyncio
    async def test_task_persistence_status_tracking(self):
        """RED: Test task status lifecycle tracking"""
        persistence = AsyncTaskPersistence()
        
        task = AsyncTask(id="status_test", name="status_tracking", operation=lambda: "done")
        
        # Save task (should start as pending)
        await persistence.save_task(task)
        status = await persistence.get_task_status("status_test")
        assert status == "pending"
        
        # Mark as running
        await persistence.mark_running("status_test")
        status = await persistence.get_task_status("status_test")
        assert status == "running"
        
        # Mark as completed
        await persistence.mark_completed("status_test")
        status = await persistence.get_task_status("status_test")
        assert status == "completed"
    
    @pytest.mark.asyncio
    async def test_task_persistence_failure_tracking(self):
        """RED: Test task failure tracking and retry logic"""
        persistence = AsyncTaskPersistence()
        
        task = AsyncTask(id="failure_test", name="failure_tracking", operation=lambda: "done")
        await persistence.save_task(task)
        
        # Mark as failed with error
        await persistence.mark_failed("failure_test", "Connection timeout", retry_count=1)
        
        status = await persistence.get_task_status("failure_test")
        assert status == "failed"
        
        failure_info = await persistence.get_failure_info("failure_test")
        assert failure_info["error"] == "Connection timeout"
        assert failure_info["retry_count"] == 1


class TestAsyncCronScheduler:
    """Test suite for Async Cron Scheduler"""
    
    @pytest.mark.asyncio
    async def test_cron_scheduler_initialization(self):
        """RED: Test cron scheduler initialization"""
        scheduler = AsyncCronScheduler()
        
        assert scheduler.jobs == {}
        assert scheduler.is_running is False
    
    @pytest.mark.asyncio
    async def test_cron_job_scheduling(self):
        """RED: Test cron job scheduling and execution"""
        scheduler = AsyncCronScheduler()
        
        execution_count = 0
        
        async def scheduled_task():
            nonlocal execution_count
            execution_count += 1
            return f"execution_{execution_count}"
        
        # Schedule task every 0.1 seconds (for testing)
        job_id = await scheduler.add_job(scheduled_task, "*/0.1 * * * *")  # Every 0.1 seconds
        
        assert job_id is not None
        assert len(scheduler.jobs) == 1
        
        # Start scheduler
        await scheduler.start()
        
        # Wait for executions
        await asyncio.sleep(0.35)
        
        # Stop scheduler
        await scheduler.stop()
        
        # Should have executed multiple times
        assert execution_count >= 3
    
    @pytest.mark.asyncio
    async def test_cron_job_removal(self):
        """RED: Test cron job removal"""
        scheduler = AsyncCronScheduler()
        
        async def dummy_task():
            return "dummy"
        
        # Add job
        job_id = await scheduler.add_job(dummy_task, "* * * * *")
        assert len(scheduler.jobs) == 1
        
        # Remove job
        await scheduler.remove_job(job_id)
        assert len(scheduler.jobs) == 0


class TestAsyncSchedulerService:
    """Test suite for Enhanced Async Scheduler Service"""
    
    @pytest_asyncio.fixture
    async def scheduler_config(self):
        """Mock scheduler configuration"""
        class MockSchedulerConfig:
            max_concurrent_jobs = 5
            health_check_interval = 1.0
            task_timeout = 30.0
        
        return MockSchedulerConfig()
    
    @pytest.mark.asyncio
    async def test_scheduler_service_initialization(self, scheduler_config):
        """RED: Test scheduler service initialization"""
        service = AsyncSchedulerService(scheduler_config)
        
        assert service.config == scheduler_config
        assert service.task_queue is not None
        assert service.cron_scheduler is not None
        assert service.max_workers == scheduler_config.max_concurrent_jobs
    
    @pytest.mark.asyncio
    async def test_scheduler_service_recurring_task(self, scheduler_config):
        """RED: Test recurring task scheduling through service"""
        service = AsyncSchedulerService(scheduler_config)
        
        execution_times = []
        
        async def recurring_operation():
            execution_times.append(time.time())
            return "recurring_completed"
        
        # Schedule recurring task
        job_id = await service.schedule_recurring_task(recurring_operation, "*/0.1 * * * *")
        
        assert job_id is not None
        
        # Start service
        await service.start_service()
        
        # Wait for several executions
        await asyncio.sleep(0.35)
        
        # Stop service
        await service.stop_service()
        
        # Verify recurring execution
        assert len(execution_times) >= 3
        
        # Verify timing intervals
        if len(execution_times) >= 2:
            intervals = [execution_times[i] - execution_times[i-1] for i in range(1, len(execution_times))]
            avg_interval = sum(intervals) / len(intervals)
            assert 0.08 < avg_interval < 0.15  # Around 0.1s interval
    
    @pytest.mark.asyncio
    async def test_scheduler_service_task_queue_integration(self, scheduler_config):
        """RED: Test integration between cron scheduler and task queue"""
        service = AsyncSchedulerService(scheduler_config)
        
        queued_tasks = []
        
        async def queue_monitoring_task():
            # This would add tasks to the queue
            task = AsyncTask(
                id=f"queued_{len(queued_tasks)}",
                name="queue_test",
                operation=lambda: "queue_result"
            )
            await service.task_queue.enqueue_task(task)
            queued_tasks.append(task.id)
        
        # Schedule recurring task that adds to queue
        await service.schedule_recurring_task(queue_monitoring_task, "*/0.1 * * * *")
        
        # Start service
        await service.start_service()
        
        # Wait for operations
        await asyncio.sleep(0.35)
        
        # Stop service
        await service.stop_service()
        
        # Verify tasks were queued and processed
        assert len(queued_tasks) >= 3
    
    @pytest.mark.asyncio 
    async def test_scheduler_service_health_monitoring(self, scheduler_config):
        """RED: Test scheduler service health monitoring"""
        service = AsyncSchedulerService(scheduler_config)
        
        # Get health status
        health = await service.get_health_status()
        
        assert "scheduler" in health
        assert "task_queue" in health
        assert "worker_status" in health
        
        # Should include metrics
        assert "scheduled_jobs" in health["scheduler"]
        assert "queue_size" in health["task_queue"]
        assert "active_workers" in health["worker_status"]


class TestTaskPriorityProcessing:
    """Test suite for Task Priority and Processing Logic"""
    
    @pytest.mark.asyncio
    async def test_task_priority_enum_ordering(self):
        """RED: Test task priority enum values and ordering"""
        # Priority ordering: CRITICAL < HIGH < NORMAL < LOW (lower number = higher priority)
        assert TaskPriority.CRITICAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.LOW
        
        # Numeric values for priority queue
        assert TaskPriority.CRITICAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.NORMAL.value == 5
        assert TaskPriority.LOW.value == 10
    
    @pytest.mark.asyncio
    async def test_mixed_priority_task_processing(self):
        """RED: Test processing tasks with mixed priorities"""
        queue = AsyncTaskQueue(max_workers=1)
        await queue.start_workers()
        
        execution_order = []
        
        async def priority_task(name: str, priority: TaskPriority):
            async def operation():
                execution_order.append(name)
                return f"done_{name}"
            
            return AsyncTask(
                id=f"priority_{name}",
                name=name,
                operation=operation,
                priority=priority
            )
        
        # Enqueue tasks in non-priority order
        await queue.enqueue_task(await priority_task("normal", TaskPriority.NORMAL))
        await queue.enqueue_task(await priority_task("critical", TaskPriority.CRITICAL))
        await queue.enqueue_task(await priority_task("low", TaskPriority.LOW))
        await queue.enqueue_task(await priority_task("high", TaskPriority.HIGH))
        
        # Wait for processing
        await queue.wait_completion(timeout=2.0)
        
        # Should execute in priority order
        expected_order = ["critical", "high", "normal", "low"]
        assert execution_order == expected_order
        
        await queue.stop_workers()


# Test runner for Phase 8 Task Queue RED phase validation
if __name__ == "__main__":
    print("🔴 Running Phase 8 Task Queue Tests (RED phase)")
    print("⚠️  These tests SHOULD FAIL since implementation doesn't exist yet")
    print("✅ This confirms TDD RED-GREEN-REFACTOR cycle is working correctly")
    
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])