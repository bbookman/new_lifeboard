"""
Background Task & Queue Management for AsyncDatabaseService

Enterprise-grade async task processing with priority scheduling,
persistence, and comprehensive background worker management.

Implementation for Phase 8 enterprise architecture patterns.
"""

import asyncio
import time
import uuid
import json
import logging
from enum import IntEnum
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime


class TaskPriority(IntEnum):
    """Task priority levels (lower number = higher priority)"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 5
    LOW = 10


class TaskExecutionError(Exception):
    """Exception for task execution failures"""
    pass


class TaskTimeoutError(Exception):
    """Exception for task timeout"""
    pass


@dataclass
class AsyncTask:
    """Async task with metadata and execution capabilities"""
    id: str
    name: str
    operation: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    async def execute(self) -> Any:
        """Execute the task with timeout handling"""
        try:
            if self.timeout:
                result = await asyncio.wait_for(
                    self.operation(*self.args, **self.kwargs),
                    timeout=self.timeout
                )
            else:
                result = await self.operation(*self.args, **self.kwargs)
            
            return result
            
        except asyncio.TimeoutError as e:
            raise TaskTimeoutError(f"Task {self.id} timed out after {self.timeout}s") from e
        except Exception as e:
            raise TaskExecutionError(f"Task {self.id} execution failed: {e}") from e


class AsyncTaskPersistence:
    """Persistent storage for task state and recovery"""
    
    def __init__(self):
        # In-memory storage for testing (would use database in production)
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_status: Dict[str, str] = {}
        self._failure_info: Dict[str, Dict[str, Any]] = {}
        self._logger = logging.getLogger(__name__)
    
    async def save_task(self, task: AsyncTask):
        """Save task to persistent storage"""
        task_data = {
            "id": task.id,
            "name": task.name,
            "priority": task.priority.value,
            "timeout": task.timeout,
            "metadata": task.metadata,
            "created_at": task.created_at
        }
        
        self._tasks[task.id] = task_data
        self._task_status[task.id] = "pending"
        
        self._logger.debug(f"Saved task {task.id} to persistence")
    
    async def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """Retrieve task from persistent storage"""
        if task_id not in self._tasks:
            return None
        
        task_data = self._tasks[task_id]
        
        # Reconstruct task (operation would need to be re-registered)
        return AsyncTask(
            id=task_data["id"],
            name=task_data["name"],
            operation=lambda: "reconstructed",  # Placeholder
            priority=TaskPriority(task_data["priority"]),
            timeout=task_data["timeout"],
            metadata=task_data["metadata"],
            created_at=task_data["created_at"]
        )
    
    async def get_task_status(self, task_id: str) -> str:
        """Get current task status"""
        return self._task_status.get(task_id, "unknown")
    
    async def mark_running(self, task_id: str):
        """Mark task as running"""
        self._task_status[task_id] = "running"
        self._logger.debug(f"Task {task_id} marked as running")
    
    async def mark_completed(self, task_id: str):
        """Mark task as completed"""
        self._task_status[task_id] = "completed"
        self._logger.debug(f"Task {task_id} marked as completed")
    
    async def mark_failed(self, task_id: str, error: str, retry_count: int = 0):
        """Mark task as failed with error details"""
        self._task_status[task_id] = "failed"
        self._failure_info[task_id] = {
            "error": error,
            "retry_count": retry_count,
            "failed_at": time.time()
        }
        self._logger.error(f"Task {task_id} marked as failed: {error}")
    
    async def get_failure_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task failure information"""
        return self._failure_info.get(task_id)


class AsyncCronScheduler:
    """Async cron scheduler for recurring tasks"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)
    
    async def add_job(self, func: Callable, cron_expression: str) -> str:
        """Add recurring job with cron expression"""
        job_id = str(uuid.uuid4())
        
        # Parse cron expression (simplified for testing)
        interval = self._parse_cron_expression(cron_expression)
        
        self.jobs[job_id] = {
            "id": job_id,
            "function": func,
            "cron_expression": cron_expression,
            "interval": interval,
            "last_run": 0,
            "next_run": time.time() + interval
        }
        
        self._logger.info(f"Added cron job {job_id} with expression: {cron_expression}")
        return job_id
    
    async def remove_job(self, job_id: str):
        """Remove scheduled job"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._logger.info(f"Removed cron job {job_id}")
    
    async def start(self):
        """Start cron scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._logger.info("Started cron scheduler")
    
    async def stop(self):
        """Stop cron scheduler"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        self._logger.info("Stopped cron scheduler")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                current_time = time.time()
                
                for job_id, job in self.jobs.items():
                    if current_time >= job["next_run"]:
                        # Execute job
                        try:
                            await job["function"]()
                            job["last_run"] = current_time
                            job["next_run"] = current_time + job["interval"]
                            self._logger.debug(f"Executed cron job {job_id}")
                        except Exception as e:
                            self._logger.error(f"Cron job {job_id} failed: {e}")
                            # Still schedule next run
                            job["next_run"] = current_time + job["interval"]
                
                await asyncio.sleep(0.1)  # Check every 100ms
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(1)
    
    def _parse_cron_expression(self, expression: str) -> float:
        """Parse cron expression to interval (simplified for testing)"""
        # Simplified parser for testing - handle */X format
        if expression.startswith("*/"):
            try:
                value = float(expression[2:].split()[0])
                return value
            except (ValueError, IndexError):
                pass
        
        # Default to 60 seconds for standard expressions
        return 60.0


class AsyncTaskQueue:
    """Priority-based async task queue with persistence"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.priority_queue = asyncio.PriorityQueue()
        self.workers: List[asyncio.Task] = []
        self.task_persistence = AsyncTaskPersistence()
        self._shutdown_event = asyncio.Event()
        self._logger = logging.getLogger(__name__)
    
    async def start_workers(self):
        """Start background worker tasks"""
        if self.workers:
            return  # Already started
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        self._logger.info(f"Started {self.max_workers} task queue workers")
    
    async def stop_workers(self):
        """Stop all worker tasks"""
        if not self.workers:
            return
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers.clear()
        self._shutdown_event.clear()
        
        self._logger.info("Stopped all task queue workers")
    
    async def enqueue_task(self, task: AsyncTask):
        """Enqueue task with priority"""
        # Persist task
        await self.task_persistence.save_task(task)
        
        # Add to priority queue (priority, timestamp, task)
        await self.priority_queue.put((task.priority.value, time.time(), task))
        
        self._logger.debug(f"Enqueued task {task.id} with priority {task.priority.name}")
    
    async def wait_completion(self, timeout: float = 30.0):
        """Wait for all queued tasks to complete"""
        start_time = time.time()
        
        while not self.priority_queue.empty() and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.01)
        
        # Wait a bit more for workers to finish current tasks
        await asyncio.sleep(0.1)
    
    async def _worker(self, worker_name: str):
        """Background worker processing tasks"""
        self._logger.debug(f"Started worker {worker_name}")
        
        while not self._shutdown_event.is_set():
            try:
                # Get next task with timeout
                try:
                    priority, timestamp, task = await asyncio.wait_for(
                        self.priority_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue  # No tasks available, continue loop
                
                # Mark task as running
                await self.task_persistence.mark_running(task.id)
                
                # Execute task
                await self._execute_task_safely(task, worker_name)
                
                # Mark task done
                self.priority_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error
        
        self._logger.debug(f"Worker {worker_name} stopped")
    
    async def _execute_task_safely(self, task: AsyncTask, worker_name: str):
        """Execute task with error handling and logging"""
        try:
            self._logger.debug(f"Worker {worker_name} executing task {task.id}")
            
            start_time = time.perf_counter()
            result = await task.execute()
            duration = time.perf_counter() - start_time
            
            # Mark as completed
            await self.task_persistence.mark_completed(task.id)
            
            self._logger.debug(f"Worker {worker_name} completed task {task.id} in {duration:.3f}s")
            return result
            
        except (TaskTimeoutError, TaskExecutionError) as e:
            # Mark as failed
            await self.task_persistence.mark_failed(task.id, str(e))
            self._logger.error(f"Worker {worker_name} task {task.id} failed: {e}")
            
        except Exception as e:
            # Unexpected error
            await self.task_persistence.mark_failed(task.id, f"Unexpected error: {e}")
            self._logger.error(f"Worker {worker_name} task {task.id} unexpected error: {e}")


class AsyncSchedulerService:
    """Enhanced async scheduler with task queue integration"""
    
    def __init__(self, config):
        self.config = config
        self.max_workers = config.max_concurrent_jobs
        self.task_queue = AsyncTaskQueue(max_workers=self.max_workers)
        self.cron_scheduler = AsyncCronScheduler()
        self._logger = logging.getLogger(__name__)
    
    async def start_service(self):
        """Start scheduler service"""
        await self.task_queue.start_workers()
        await self.cron_scheduler.start()
        self._logger.info("AsyncSchedulerService started")
    
    async def stop_service(self):
        """Stop scheduler service"""
        await self.cron_scheduler.stop()
        await self.task_queue.stop_workers()
        self._logger.info("AsyncSchedulerService stopped")
    
    async def schedule_recurring_task(self, task: Callable, cron_expression: str) -> str:
        """Schedule recurring task with cron expression"""
        job_id = await self.cron_scheduler.add_job(task, cron_expression)
        self._logger.info(f"Scheduled recurring task {job_id} with expression: {cron_expression}")
        return job_id
    
    async def enqueue_one_time_task(self, task: AsyncTask):
        """Enqueue one-time task for execution"""
        await self.task_queue.enqueue_task(task)
        self._logger.info(f"Enqueued one-time task {task.id}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler service health status"""
        return {
            "scheduler": {
                "is_running": self.cron_scheduler.is_running,
                "scheduled_jobs": len(self.cron_scheduler.jobs)
            },
            "task_queue": {
                "queue_size": self.task_queue.priority_queue.qsize(),
                "active_workers": len([w for w in self.task_queue.workers if not w.done()])
            },
            "worker_status": {
                "max_workers": self.max_workers,
                "active_workers": len(self.task_queue.workers),
                "healthy_workers": len([w for w in self.task_queue.workers if not w.done() and not w.cancelled()])
            }
        }