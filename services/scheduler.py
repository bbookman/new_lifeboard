import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from core.logging_config import get_logger

logger = get_logger(__name__)


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class ScheduledJob:
    """Represents a scheduled job"""
    id: str
    name: str
    namespace: str
    interval_seconds: int
    func: Callable[[], Awaitable[Any]]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_result: Optional[Any] = None
    error_count: int = 0
    last_error: Optional[str] = None
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 1800  # 30 minutes
    
    def __post_init__(self):
        if self.next_run is None:
            self.next_run = datetime.now(timezone.utc)
    
    def is_due(self) -> bool:
        """Check if job is due for execution"""
        if self.status not in [JobStatus.PENDING, JobStatus.COMPLETED]:
            return False
        return self.next_run and datetime.now(timezone.utc) >= self.next_run
    
    def calculate_next_run(self):
        """Calculate next execution time"""
        if self.status == JobStatus.PAUSED:
            return
        self.next_run = datetime.now(timezone.utc) + timedelta(seconds=self.interval_seconds)
    
    def should_retry(self) -> bool:
        """Check if job should be retried after failure"""
        return self.error_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for status reporting"""
        return {
            "id": self.id,
            "name": self.name,
            "namespace": self.namespace,
            "status": self.status.value,
            "interval_seconds": self.interval_seconds,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "max_retries": self.max_retries
        }


class AsyncScheduler:
    """Async scheduler service for background job execution"""
    
    def __init__(self, check_interval_seconds: int = 300, max_concurrent_jobs: int = 3):
        self.check_interval_seconds = check_interval_seconds
        self.max_concurrent_jobs = max_concurrent_jobs
        self.jobs: Dict[str, ScheduledJob] = {}
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.stats = {
            "total_jobs_executed": 0,
            "total_jobs_failed": 0,
            "scheduler_start_time": None,
            "last_check_time": None
        }
    
    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.stats["scheduler_start_time"] = datetime.now(timezone.utc)
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"Scheduler started with check interval: {self.check_interval_seconds}s")
    
    async def stop(self):
        """Stop the scheduler and cancel running jobs"""
        logger.info("Stopping scheduler...")
        self.is_running = False
        
        # Cancel scheduler task
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel running jobs
        for job_id, task in list(self.running_jobs.items()):
            logger.info(f"Cancelling running job: {job_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.running_jobs.clear()
        logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                self.stats["last_check_time"] = datetime.now(timezone.utc)
                
                # Clean up completed jobs
                await self._cleanup_completed_jobs()
                
                # Check for due jobs
                due_jobs = self._get_due_jobs()
                
                if due_jobs:
                    logger.debug(f"Found {len(due_jobs)} due jobs")
                    
                    for job in due_jobs:
                        if len(self.running_jobs) >= self.max_concurrent_jobs:
                            logger.debug("Max concurrent jobs reached, skipping execution")
                            break
                        
                        await self._execute_job(job)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval_seconds)
    
    async def _cleanup_completed_jobs(self):
        """Clean up completed job tasks"""
        completed_jobs = []
        
        for job_id, task in list(self.running_jobs.items()):
            if task.done():
                completed_jobs.append(job_id)
                
                job = self.jobs.get(job_id)
                if job:
                    try:
                        result = await task
                        job.last_result = result
                        job.status = JobStatus.COMPLETED
                        job.last_run = datetime.now(timezone.utc)
                        job.calculate_next_run()
                        self.stats["total_jobs_executed"] += 1
                        logger.info(f"Job {job_id} completed successfully")
                        
                    except Exception as e:
                        job.status = JobStatus.FAILED
                        job.error_count += 1
                        job.last_error = str(e)
                        self.stats["total_jobs_failed"] += 1
                        
                        logger.error(f"Job {job_id} failed: {e}")
                        
                        # Schedule retry if applicable
                        if job.should_retry():
                            retry_delay = min(
                                job.retry_delay_seconds * (2 ** (job.error_count - 1)),  # Exponential backoff
                                3600  # Max 1 hour delay
                            )
                            job.next_run = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                            job.status = JobStatus.PENDING
                            logger.info(f"Job {job_id} scheduled for retry {job.error_count}/{job.max_retries} in {retry_delay}s")
                        else:
                            job.status = JobStatus.FAILED
                            logger.error(f"Job {job_id} failed permanently after {job.error_count} attempts")
                            
                            # For permanently failed jobs, schedule next attempt after the regular interval
                            # This allows recovery if the issue is resolved
                            job.next_run = datetime.now(timezone.utc) + timedelta(seconds=job.interval_seconds)
                            job.error_count = 0  # Reset error count for fresh start
                            job.status = JobStatus.PENDING
                            logger.info(f"Job {job_id} reset for next regular cycle in {job.interval_seconds}s")
        
        # Remove completed tasks
        for job_id in completed_jobs:
            del self.running_jobs[job_id]
    
    def _get_due_jobs(self) -> List[ScheduledJob]:
        """Get jobs that are due for execution"""
        due_jobs = []
        for job in self.jobs.values():
            if job.is_due() and job.id not in self.running_jobs:
                due_jobs.append(job)
        
        # Sort by next_run time
        due_jobs.sort(key=lambda j: j.next_run or datetime.min.replace(tzinfo=timezone.utc))
        return due_jobs
    
    async def _execute_job(self, job: ScheduledJob):
        """Execute a scheduled job"""
        logger.info(f"Executing job: {job.id} ({job.name})")
        
        job.status = JobStatus.RUNNING
        
        # Create task with timeout
        task = asyncio.create_task(
            asyncio.wait_for(job.func(), timeout=job.timeout_seconds)
        )
        
        self.running_jobs[job.id] = task
    
    def add_job(self, 
                name: str,
                namespace: str,
                func: Callable[[], Awaitable[Any]], 
                interval_seconds: int,
                max_retries: int = 3,
                timeout_seconds: int = 1800) -> str:
        """Add a new scheduled job"""
        job_id = str(uuid.uuid4())
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            namespace=namespace,
            func=func,
            interval_seconds=interval_seconds,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        self.jobs[job_id] = job
        logger.info(f"Added job: {job_id} ({name}) - interval: {interval_seconds}s")
        
        return job_id
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        if job_id not in self.jobs:
            return False
        
        # Cancel if running
        if job_id in self.running_jobs:
            self.running_jobs[job_id].cancel()
            del self.running_jobs[job_id]
        
        del self.jobs[job_id]
        logger.info(f"Removed job: {job_id}")
        return True
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        job.status = JobStatus.PAUSED
        job.next_run = None
        logger.info(f"Paused job: {job_id}")
        return True
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.PAUSED:
            return False
        
        job.status = JobStatus.PENDING
        job.next_run = datetime.now(timezone.utc)
        logger.info(f"Resumed job: {job_id}")
        return True
    
    async def trigger_job(self, job_id: str) -> bool:
        """Trigger immediate execution of a job"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.id in self.running_jobs:
            logger.warning(f"Job {job_id} is already running")
            return False
        
        if len(self.running_jobs) >= self.max_concurrent_jobs:
            logger.warning("Max concurrent jobs reached, cannot trigger job")
            return False
        
        logger.info(f"Triggering immediate execution of job: {job_id}")
        await self._execute_job(job)
        return True
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        status = job.to_dict()
        status["is_running"] = job_id in self.running_jobs
        return status
    
    def get_all_jobs_status(self) -> Dict[str, Any]:
        """Get status of all jobs"""
        jobs_status = {}
        for job_id, job in self.jobs.items():
            status = job.to_dict()
            status["is_running"] = job_id in self.running_jobs
            jobs_status[job_id] = status
        
        return {
            "jobs": jobs_status,
            "summary": {
                "total_jobs": len(self.jobs),
                "running_jobs": len(self.running_jobs),
                "paused_jobs": sum(1 for j in self.jobs.values() if j.status == JobStatus.PAUSED),
                "failed_jobs": sum(1 for j in self.jobs.values() if j.status == JobStatus.FAILED),
                "scheduler_running": self.is_running,
                "stats": self.stats
            }
        }
    
    def get_jobs_by_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """Get all jobs for a specific namespace"""
        namespace_jobs = []
        for job in self.jobs.values():
            if job.namespace == namespace:
                status = job.to_dict()
                status["is_running"] = job.id in self.running_jobs
                namespace_jobs.append(status)
        
        return namespace_jobs
    
    def reset_job_errors(self, job_id: str) -> bool:
        """Reset error count for a job (useful for manual recovery)"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        job.error_count = 0
        job.last_error = None
        if job.status == JobStatus.FAILED:
            job.status = JobStatus.PENDING
            job.next_run = datetime.now(timezone.utc)
        
        logger.info(f"Reset errors for job: {job_id}")
        return True
    
    def update_job_interval(self, job_id: str, new_interval_seconds: int) -> bool:
        """Update the interval for a job"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        old_interval = job.interval_seconds
        job.interval_seconds = new_interval_seconds
        
        # Recalculate next run time if job is pending
        if job.status == JobStatus.PENDING:
            job.calculate_next_run()
        
        logger.info(f"Updated job {job_id} interval from {old_interval}s to {new_interval_seconds}s")
        return True
    
    def get_failed_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs that have failed"""
        failed_jobs = []
        for job in self.jobs.values():
            if job.error_count > 0 or job.status == JobStatus.FAILED:
                status = job.to_dict()
                status["is_running"] = job.id in self.running_jobs
                failed_jobs.append(status)
        
        return failed_jobs
    
    def get_overdue_jobs(self) -> List[Dict[str, Any]]:
        """Get jobs that are overdue for execution"""
        now = datetime.now(timezone.utc)
        overdue_jobs = []
        
        for job in self.jobs.values():
            if (job.next_run and 
                job.status == JobStatus.PENDING and 
                now > job.next_run and
                job.id not in self.running_jobs):
                
                overdue_duration = now - job.next_run
                status = job.to_dict()
                status["overdue_seconds"] = overdue_duration.total_seconds()
                overdue_jobs.append(status)
        
        return overdue_jobs
    
    async def force_restart_job(self, job_id: str) -> bool:
        """Force restart a job (cancel if running, reset errors, trigger immediately)"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        # Cancel if currently running
        if job_id in self.running_jobs:
            task = self.running_jobs[job_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.running_jobs[job_id]
        
        # Reset job state
        job.error_count = 0
        job.last_error = None
        job.status = JobStatus.PENDING
        job.next_run = datetime.now(timezone.utc)
        
        logger.info(f"Force restarted job: {job_id}")
        return True
    
    def get_scheduler_health(self) -> Dict[str, Any]:
        """Get scheduler health information"""
        now = datetime.now(timezone.utc)
        
        # Count jobs by status
        status_counts = {}
        overdue_count = 0
        failed_count = 0
        
        for job in self.jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if job.error_count >= job.max_retries:
                failed_count += 1
            
            if (job.next_run and 
                job.status == JobStatus.PENDING and 
                now > job.next_run and
                job.id not in self.running_jobs):
                overdue_count += 1
        
        uptime_seconds = 0
        if self.stats.get("scheduler_start_time"):
            start_time = self.stats["scheduler_start_time"]
            uptime_seconds = (now - start_time).total_seconds()
        
        return {
            "scheduler_running": self.is_running,
            "uptime_seconds": uptime_seconds,
            "uptime_hours": uptime_seconds / 3600,
            "total_jobs": len(self.jobs),
            "running_jobs": len(self.running_jobs),
            "status_breakdown": status_counts,
            "overdue_jobs": overdue_count,
            "permanently_failed_jobs": failed_count,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "check_interval_seconds": self.check_interval_seconds,
            "stats": self.stats,
            "last_check": self.stats.get("last_check_time"),
            "health_issues": self._identify_health_issues()
        }
    
    def _identify_health_issues(self) -> List[Dict[str, Any]]:
        """Identify potential health issues with the scheduler"""
        issues = []
        now = datetime.now(timezone.utc)
        
        # Check if scheduler is not running
        if not self.is_running:
            issues.append({
                "type": "scheduler_not_running",
                "severity": "critical",
                "message": "Scheduler is not running"
            })
        
        # Check for overdue jobs
        overdue_jobs = self.get_overdue_jobs()
        if len(overdue_jobs) > 0:
            max_overdue = max(job["overdue_seconds"] for job in overdue_jobs)
            issues.append({
                "type": "overdue_jobs",
                "severity": "warning" if max_overdue < 3600 else "critical",
                "message": f"{len(overdue_jobs)} jobs are overdue, max {max_overdue/60:.1f} minutes",
                "count": len(overdue_jobs),
                "max_overdue_seconds": max_overdue
            })
        
        # Check for many failed jobs
        failed_jobs = self.get_failed_jobs()
        if len(failed_jobs) > len(self.jobs) * 0.5:  # More than 50% failed
            issues.append({
                "type": "high_failure_rate",
                "severity": "critical",
                "message": f"{len(failed_jobs)}/{len(self.jobs)} jobs have errors",
                "failed_count": len(failed_jobs),
                "total_count": len(self.jobs)
            })
        
        # Check if no jobs are scheduled
        if len(self.jobs) == 0:
            issues.append({
                "type": "no_jobs_scheduled",
                "severity": "warning",
                "message": "No jobs are scheduled"
            })
        
        return issues