"""
Tests for the async scheduler service
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
from datetime import datetime, timezone, timedelta

from services.scheduler import AsyncScheduler, JobStatus, ScheduledJob


@pytest.fixture
def scheduler():
    """Create scheduler for testing"""
    return AsyncScheduler(check_interval_seconds=1, max_concurrent_jobs=2)


@pytest.fixture
async def running_scheduler(scheduler):
    """Create and start scheduler for testing"""
    await scheduler.start()
    yield scheduler
    await scheduler.stop()


class TestScheduledJob:
    """Test ScheduledJob class"""
    
    def test_job_initialization(self):
        """Test job initialization"""
        async def test_func():
            return "test"
        
        job = ScheduledJob(
            id="test-job",
            name="Test Job",
            namespace="test",
            interval_seconds=60,
            func=test_func
        )
        
        assert job.id == "test-job"
        assert job.name == "Test Job"
        assert job.namespace == "test"
        assert job.interval_seconds == 60
        assert job.status == JobStatus.PENDING
        assert job.next_run is not None
        assert job.error_count == 0
    
    def test_job_is_due(self):
        """Test job due check"""
        async def test_func():
            return "test"
        
        # Job that's due
        job = ScheduledJob(
            id="test-job",
            name="Test Job", 
            namespace="test",
            interval_seconds=60,
            func=test_func
        )
        job.next_run = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        assert job.is_due() is True
        
        # Job that's not due
        job.next_run = datetime.now(timezone.utc) + timedelta(seconds=60)
        assert job.is_due() is False
        
        # Paused job should not be due
        job.status = JobStatus.PAUSED
        job.next_run = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert job.is_due() is False
    
    def test_job_should_retry(self):
        """Test retry logic"""
        async def test_func():
            return "test"
        
        job = ScheduledJob(
            id="test-job",
            name="Test Job",
            namespace="test", 
            interval_seconds=60,
            func=test_func,
            max_retries=3
        )
        
        # Should retry with no errors
        assert job.should_retry() is True
        
        # Should retry with some errors
        job.error_count = 2
        assert job.should_retry() is True
        
        # Should not retry when at max
        job.error_count = 3
        assert job.should_retry() is False
    
    def test_calculate_next_run(self):
        """Test next run calculation"""
        async def test_func():
            return "test"
        
        job = ScheduledJob(
            id="test-job",
            name="Test Job",
            namespace="test",
            interval_seconds=3600,  # 1 hour
            func=test_func
        )
        
        before = datetime.now(timezone.utc)
        job.calculate_next_run()
        after = datetime.now(timezone.utc)
        
        # Should be approximately 1 hour from now
        expected_time = before + timedelta(seconds=3600)
        assert abs((job.next_run - expected_time).total_seconds()) < 10


class TestAsyncScheduler:
    """Test AsyncScheduler class"""
    
    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initialization"""
        assert scheduler.check_interval_seconds == 1
        assert scheduler.max_concurrent_jobs == 2
        assert scheduler.is_running is False
        assert len(scheduler.jobs) == 0
    
    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self, scheduler):
        """Test scheduler start and stop"""
        assert scheduler.is_running is False
        
        await scheduler.start()
        assert scheduler.is_running is True
        assert scheduler.scheduler_task is not None
        
        await scheduler.stop()
        assert scheduler.is_running is False
    
    def test_add_job(self, scheduler):
        """Test adding jobs"""
        async def test_func():
            return "test result"
        
        job_id = scheduler.add_job(
            name="Test Job",
            namespace="test",
            func=test_func,
            interval_seconds=60
        )
        
        assert job_id in scheduler.jobs
        job = scheduler.jobs[job_id]
        assert job.name == "Test Job"
        assert job.namespace == "test"
        assert job.interval_seconds == 60
    
    def test_remove_job(self, scheduler):
        """Test removing jobs"""
        async def test_func():
            return "test"
        
        job_id = scheduler.add_job(
            name="Test Job",
            namespace="test", 
            func=test_func,
            interval_seconds=60
        )
        
        assert job_id in scheduler.jobs
        
        success = scheduler.remove_job(job_id)
        assert success is True
        assert job_id not in scheduler.jobs
        
        # Try to remove non-existent job
        success = scheduler.remove_job("non-existent")
        assert success is False
    
    def test_pause_resume_job(self, scheduler):
        """Test pausing and resuming jobs"""
        async def test_func():
            return "test"
        
        job_id = scheduler.add_job(
            name="Test Job",
            namespace="test",
            func=test_func,
            interval_seconds=60
        )
        
        job = scheduler.jobs[job_id]
        assert job.status == JobStatus.PENDING
        
        # Pause job
        success = scheduler.pause_job(job_id)
        assert success is True
        assert job.status == JobStatus.PAUSED
        assert job.next_run is None
        
        # Resume job
        success = scheduler.resume_job(job_id)
        assert success is True
        assert job.status == JobStatus.PENDING
        assert job.next_run is not None
    
    @pytest.mark.asyncio
    async def test_trigger_job(self, running_scheduler):
        """Test manually triggering a job"""
        result_store = []
        
        async def test_func():
            result_store.append("executed")
            return "test result"
        
        job_id = running_scheduler.add_job(
            name="Test Job",
            namespace="test",
            func=test_func,
            interval_seconds=3600  # Long interval
        )
        
        # Trigger job immediately
        success = await running_scheduler.trigger_job(job_id)
        assert success is True
        
        # Wait for execution
        await asyncio.sleep(0.1)
        
        # Check that function was called
        assert len(result_store) == 1
        assert result_store[0] == "executed"
    
    def test_get_job_status(self, scheduler):
        """Test getting job status"""
        async def test_func():
            return "test"
        
        job_id = scheduler.add_job(
            name="Test Job",
            namespace="test",
            func=test_func,
            interval_seconds=60
        )
        
        status = scheduler.get_job_status(job_id)
        assert status is not None
        assert status["id"] == job_id
        assert status["name"] == "Test Job"
        assert status["namespace"] == "test"
        assert status["status"] == JobStatus.PENDING.value
        
        # Non-existent job
        status = scheduler.get_job_status("non-existent")
        assert status is None
    
    def test_get_all_jobs_status(self, scheduler):
        """Test getting all jobs status"""
        async def test_func():
            return "test"
        
        # Add multiple jobs
        job_id1 = scheduler.add_job("Job 1", "test1", test_func, 60)
        job_id2 = scheduler.add_job("Job 2", "test2", test_func, 120)
        
        all_status = scheduler.get_all_jobs_status()
        
        assert "jobs" in all_status
        assert "summary" in all_status
        assert len(all_status["jobs"]) == 2
        assert job_id1 in all_status["jobs"]
        assert job_id2 in all_status["jobs"]
        
        summary = all_status["summary"]
        assert summary["total_jobs"] == 2
        assert summary["running_jobs"] == 0
        assert summary["scheduler_running"] == scheduler.is_running
    
    def test_get_jobs_by_namespace(self, scheduler):
        """Test getting jobs by namespace"""
        async def test_func():
            return "test"
        
        # Add jobs to different namespaces
        job_id1 = scheduler.add_job("Job 1", "namespace1", test_func, 60)
        job_id2 = scheduler.add_job("Job 2", "namespace2", test_func, 60)
        job_id3 = scheduler.add_job("Job 3", "namespace1", test_func, 60)
        
        # Get jobs for namespace1
        namespace1_jobs = scheduler.get_jobs_by_namespace("namespace1")
        assert len(namespace1_jobs) == 2
        
        job_ids = [job["id"] for job in namespace1_jobs]
        assert job_id1 in job_ids
        assert job_id3 in job_ids
        assert job_id2 not in job_ids
        
        # Get jobs for namespace2
        namespace2_jobs = scheduler.get_jobs_by_namespace("namespace2")
        assert len(namespace2_jobs) == 1
        assert namespace2_jobs[0]["id"] == job_id2
    
    @pytest.mark.asyncio
    async def test_job_execution_success(self, running_scheduler):
        """Test successful job execution"""
        execution_count = 0
        
        async def test_func():
            nonlocal execution_count
            execution_count += 1
            return f"result_{execution_count}"
        
        job_id = running_scheduler.add_job(
            name="Test Job",
            namespace="test",
            func=test_func,
            interval_seconds=1  # Very short interval for testing
        )
        
        # Wait for a few executions
        await asyncio.sleep(2.5)
        
        # Should have executed multiple times
        assert execution_count >= 2
        
        # Check job status
        status = running_scheduler.get_job_status(job_id)
        assert status["status"] in [JobStatus.PENDING.value, JobStatus.COMPLETED.value]
        assert status["error_count"] == 0
    
    @pytest.mark.asyncio
    async def test_job_execution_failure_and_retry(self, running_scheduler):
        """Test job failure and retry logic"""
        execution_count = 0
        
        async def failing_func():
            nonlocal execution_count
            execution_count += 1
            if execution_count <= 2:  # Fail first 2 times
                raise Exception(f"Test failure {execution_count}")
            return "success"
        
        job_id = running_scheduler.add_job(
            name="Failing Job",
            namespace="test",
            func=failing_func,
            interval_seconds=1,
            max_retries=3
        )
        
        # Wait for retries
        await asyncio.sleep(5)
        
        # Should have attempted multiple times
        assert execution_count >= 3
        
        # Check job status
        status = running_scheduler.get_job_status(job_id)
        
        # Job should eventually succeed
        if execution_count > 2:
            assert status["error_count"] == 0  # Errors reset after success
        else:
            assert status["error_count"] > 0
    
    def test_error_handling_methods(self, scheduler):
        """Test error handling and recovery methods"""
        async def test_func():
            raise Exception("Test error")
        
        job_id = scheduler.add_job(
            name="Error Job", 
            namespace="test",
            func=test_func,
            interval_seconds=60,
            max_retries=1
        )
        
        job = scheduler.jobs[job_id]
        
        # Simulate errors
        job.error_count = 3
        job.last_error = "Test error"
        job.status = JobStatus.FAILED
        
        # Test reset errors
        success = scheduler.reset_job_errors(job_id)
        assert success is True
        assert job.error_count == 0
        assert job.last_error is None
        assert job.status == JobStatus.PENDING
        
        # Test update interval
        success = scheduler.update_job_interval(job_id, 120)
        assert success is True
        assert job.interval_seconds == 120
    
    def test_scheduler_health(self, scheduler):
        """Test scheduler health monitoring"""
        async def test_func():
            return "test"
        
        # Add some jobs
        job_id1 = scheduler.add_job("Job 1", "test", test_func, 60)
        job_id2 = scheduler.add_job("Job 2", "test", test_func, 60)
        
        # Simulate some failures
        job1 = scheduler.jobs[job_id1]
        job1.error_count = 5
        job1.status = JobStatus.FAILED
        
        health = scheduler.get_scheduler_health()
        
        assert "scheduler_running" in health
        assert "total_jobs" in health
        assert "status_breakdown" in health
        assert "health_issues" in health
        
        assert health["total_jobs"] == 2
        assert health["permanently_failed_jobs"] >= 1
        
        # Should have health issues
        issues = health["health_issues"]
        assert len(issues) > 0