import asyncio
import logging
from typing import Dict, List, Optional, Set, Any, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import json

from core.database import DatabaseService
from services.scheduler import AsyncScheduler
from services.semantic_deduplication_service import SemanticDeduplicationService

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Status of semantic processing for days/batches"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DayProcessingResult:
    """Result of processing a specific day"""
    days_date: str
    status: ProcessingStatus
    items_processed: int
    clusters_created: int
    processing_time: float
    error_message: Optional[str] = None


@dataclass
class ProcessingStats:
    """Overall processing statistics"""
    total_days_processed: int
    total_items_processed: int
    total_clusters_created: int
    avg_processing_time: float
    success_rate: float
    last_updated: datetime


class CleanUpCrewService:
    """
    Orchestration service for aggressive background semantic deduplication processing.
    
    This service acts as the "brain" that coordinates all semantic deduplication activities:
    - Queue management using single-table status tracking
    - Background job scheduling and execution
    - Real-time progress tracking and WebSocket updates
    - Performance optimization and caching strategies
    - Error handling and recovery mechanisms
    """
    
    def __init__(self, 
                 database_service: DatabaseService,
                 scheduler_service: AsyncScheduler,
                 semantic_service: SemanticDeduplicationService,
                 websocket_manager: Optional[Any] = None):
        self.database = database_service
        self.scheduler = scheduler_service
        self.semantic_service = semantic_service
        self.websocket_manager = websocket_manager
        
        # Processing configuration
        self.batch_size = 50
        self.max_concurrent_days = 3
        self.processing_interval_seconds = 300  # 5 minutes
        self.retry_delay_seconds = 900  # 15 minutes
        
        # Runtime state
        self.is_initialized = False
        self.background_job_id: Optional[str] = None
        self.processing_lock = asyncio.Lock()
        self.active_day_processing: Set[str] = set()
        self.processing_callbacks: List[Callable[[str, ProcessingStatus], Awaitable[None]]] = []
        
        logger.info("Initialized CleanUpCrewService")
    
    async def initialize(self):
        """Initialize the service and start background processing"""
        if self.is_initialized:
            logger.warning("CleanUpCrewService already initialized")
            return
        
        try:
            # Register background processing job
            self.background_job_id = self.scheduler.add_job(
                name="semantic_deduplication_processing",
                namespace="clean_up_crew",
                func=self._background_processing_cycle,
                interval_seconds=self.processing_interval_seconds,
                max_retries=3,
                timeout_seconds=1800  # 30 minutes
            )
            
            logger.info(f"Registered background job: {self.background_job_id}")
            
            # Perform initial queue assessment
            await self._assess_processing_queue()
            
            self.is_initialized = True
            logger.info("CleanUpCrewService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CleanUpCrewService: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the service and clean up resources"""
        logger.info("Shutting down CleanUpCrewService...")
        
        # Remove background job
        if self.background_job_id:
            self.scheduler.remove_job(self.background_job_id)
            self.background_job_id = None
        
        # Cancel any active processing
        self.active_day_processing.clear()
        self.is_initialized = False
        
        logger.info("CleanUpCrewService shutdown complete")
    
    async def get_day_status(self, days_date: str) -> ProcessingStatus:
        """Get processing status for a specific day"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT semantic_status, COUNT(*) as count
                    FROM data_items 
                    WHERE days_date = ? AND namespace = 'limitless'
                    GROUP BY semantic_status
                """, (days_date,))
                
                status_counts = {row['semantic_status']: row['count'] for row in cursor.fetchall()}
                
                if not status_counts:
                    return ProcessingStatus.PENDING
                
                # Determine overall status based on item statuses
                total_items = sum(status_counts.values())
                completed_items = status_counts.get('completed', 0)
                failed_items = status_counts.get('failed', 0)
                processing_items = status_counts.get('processing', 0)
                
                if processing_items > 0:
                    return ProcessingStatus.PROCESSING
                elif completed_items == total_items:
                    return ProcessingStatus.COMPLETED
                elif failed_items > 0:
                    return ProcessingStatus.FAILED
                else:
                    return ProcessingStatus.PENDING
                    
        except Exception as e:
            logger.error(f"Error getting day status for {days_date}: {e}")
            return ProcessingStatus.PENDING
    
    async def get_processing_queue_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the processing queue"""
        try:
            with self.database.get_connection() as conn:
                # Get status breakdown by day
                cursor = conn.execute("""
                    SELECT days_date, semantic_status, COUNT(*) as count
                    FROM data_items 
                    WHERE namespace = 'limitless'
                    GROUP BY days_date, semantic_status
                    ORDER BY days_date DESC
                """)
                
                day_status = {}
                for row in cursor.fetchall():
                    days_date = row['days_date']
                    if days_date not in day_status:
                        day_status[days_date] = {}
                    day_status[days_date][row['semantic_status']] = row['count']
                
                # Calculate summary statistics
                total_days = len(day_status)
                completed_days = 0
                pending_days = 0
                processing_days = 0
                failed_days = 0
                
                for day_data in day_status.values():
                    total_items = sum(day_data.values())
                    completed_items = day_data.get('completed', 0)
                    failed_items = day_data.get('failed', 0)
                    processing_items = day_data.get('processing', 0)
                    
                    if processing_items > 0:
                        processing_days += 1
                    elif completed_items == total_items:
                        completed_days += 1
                    elif failed_items > 0:
                        failed_days += 1
                    else:
                        pending_days += 1
                
                return {
                    "total_days": total_days,
                    "completed_days": completed_days,
                    "pending_days": pending_days,
                    "processing_days": processing_days,
                    "failed_days": failed_days,
                    "active_processing": list(self.active_day_processing),
                    "day_breakdown": day_status,
                    "background_job_id": self.background_job_id,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {"error": str(e)}
    
    async def trigger_day_processing(self, days_date: str, force: bool = False) -> DayProcessingResult:
        """Trigger immediate processing for a specific day"""
        
        if not force and days_date in self.active_day_processing:
            logger.warning(f"Day {days_date} is already being processed")
            return DayProcessingResult(
                days_date=days_date,
                status=ProcessingStatus.PROCESSING,
                items_processed=0,
                clusters_created=0,
                processing_time=0.0,
                error_message="Already processing"
            )
        
        async with self.processing_lock:
            return await self._process_single_day(days_date)
    
    async def trigger_batch_processing(self, max_days: Optional[int] = None) -> List[DayProcessingResult]:
        """Trigger immediate processing for multiple pending days"""
        
        pending_days = await self._get_pending_days(limit=max_days)
        results = []
        
        # Process days with concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent_days)
        
        async def process_day_with_semaphore(days_date: str):
            async with semaphore:
                return await self._process_single_day(days_date)
        
        # Execute processing tasks
        tasks = [process_day_with_semaphore(day) for day in pending_days]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(DayProcessingResult(
                    days_date=pending_days[i],
                    status=ProcessingStatus.FAILED,
                    items_processed=0,
                    clusters_created=0,
                    processing_time=0.0,
                    error_message=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def add_progress_callback(self, callback: Callable[[str, ProcessingStatus], Awaitable[None]]):
        """Add callback for processing progress updates"""
        self.processing_callbacks.append(callback)
    
    async def remove_progress_callback(self, callback: Callable[[str, ProcessingStatus], Awaitable[None]]):
        """Remove progress callback"""
        if callback in self.processing_callbacks:
            self.processing_callbacks.remove(callback)
    
    async def get_processing_statistics(self) -> ProcessingStats:
        """Get comprehensive processing statistics"""
        try:
            with self.database.get_connection() as conn:
                # Basic statistics
                cursor = conn.execute("""
                    SELECT 
                        COUNT(DISTINCT days_date) as total_days,
                        COUNT(*) as total_items,
                        semantic_status
                    FROM data_items 
                    WHERE namespace = 'limitless'
                    GROUP BY semantic_status
                """)
                
                status_stats = {row['semantic_status']: {
                    'days': row['total_days'], 
                    'items': row['total_items']
                } for row in cursor.fetchall()}
                
                # Calculate totals and success rate
                total_items = sum(stats['items'] for stats in status_stats.values())
                completed_items = status_stats.get('completed', {}).get('items', 0)
                success_rate = completed_items / total_items if total_items > 0 else 0
                
                # Get cluster statistics
                cursor = conn.execute("SELECT COUNT(*) as cluster_count FROM semantic_clusters")
                cluster_count = cursor.fetchone()['cluster_count']
                
                return ProcessingStats(
                    total_days_processed=sum(stats['days'] for stats in status_stats.values()),
                    total_items_processed=total_items,
                    total_clusters_created=cluster_count,
                    avg_processing_time=0.0,  # TODO: Calculate from processing logs
                    success_rate=success_rate,
                    last_updated=datetime.now(timezone.utc)
                )
                
        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return ProcessingStats(0, 0, 0, 0.0, 0.0, datetime.now(timezone.utc))
    
    async def _background_processing_cycle(self):
        """Main background processing cycle executed by scheduler"""
        logger.info("Starting background semantic deduplication processing cycle")
        
        try:
            # Get pending days that need processing
            pending_days = await self._get_pending_days(limit=self.max_concurrent_days)
            
            if not pending_days:
                logger.debug("No pending days found for processing")
                return
            
            logger.info(f"Processing {len(pending_days)} pending days: {pending_days}")
            
            # Process days with concurrency control
            results = await self.trigger_batch_processing(max_days=len(pending_days))
            
            # Log results
            successful = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
            failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
            
            logger.info(f"Background processing cycle completed: {successful} successful, {failed} failed")
            
        except Exception as e:
            logger.error(f"Error in background processing cycle: {e}")
            raise
    
    async def _process_single_day(self, days_date: str) -> DayProcessingResult:
        """Process semantic deduplication for a single day"""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Mark day as being processed
            self.active_day_processing.add(days_date)
            await self._notify_progress_callbacks(days_date, ProcessingStatus.PROCESSING)
            
            # Mark all items for this day as processing
            await self._update_day_items_status(days_date, ProcessingStatus.PROCESSING)
            
            # Get items for this day
            items = await self._get_day_items(days_date)
            
            if not items:
                logger.info(f"No items found for day {days_date}")
                result = DayProcessingResult(
                    days_date=days_date,
                    status=ProcessingStatus.COMPLETED,
                    items_processed=0,
                    clusters_created=0,
                    processing_time=0.0
                )
                await self._update_day_items_status(days_date, ProcessingStatus.COMPLETED)
                return result
            
            logger.info(f"Processing {len(items)} items for day {days_date}")
            
            # Process with semantic deduplication service
            processing_result = await self.semantic_service.process_data_items(items)
            
            if processing_result.errors:
                logger.warning(f"Processing completed with errors for {days_date}: {processing_result.errors}")
                await self._update_day_items_status(days_date, ProcessingStatus.FAILED)
                status = ProcessingStatus.FAILED
                error_message = "; ".join(processing_result.errors)
            else:
                logger.info(f"Successfully processed day {days_date}")
                await self._update_day_items_status(days_date, ProcessingStatus.COMPLETED)
                status = ProcessingStatus.COMPLETED
                error_message = None
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = DayProcessingResult(
                days_date=days_date,
                status=status,
                items_processed=processing_result.total_processed,
                clusters_created=processing_result.clusters_created,
                processing_time=processing_time,
                error_message=error_message
            )
            
            await self._notify_progress_callbacks(days_date, status)
            return result
            
        except Exception as e:
            logger.error(f"Error processing day {days_date}: {e}")
            await self._update_day_items_status(days_date, ProcessingStatus.FAILED)
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result = DayProcessingResult(
                days_date=days_date,
                status=ProcessingStatus.FAILED,
                items_processed=0,
                clusters_created=0,
                processing_time=processing_time,
                error_message=str(e)
            )
            
            await self._notify_progress_callbacks(days_date, ProcessingStatus.FAILED)
            return result
            
        finally:
            # Remove from active processing
            self.active_day_processing.discard(days_date)
    
    async def _get_pending_days(self, limit: Optional[int] = None) -> List[str]:
        """Get list of days with pending semantic processing"""
        try:
            with self.database.get_connection() as conn:
                query = """
                    SELECT DISTINCT days_date
                    FROM data_items 
                    WHERE namespace = 'limitless' 
                    AND semantic_status = 'pending'
                    ORDER BY days_date DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                return [row['days_date'] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting pending days: {e}")
            return []
    
    async def _get_day_items(self, days_date: str) -> List[Dict[str, Any]]:
        """Get all data items for a specific day"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                    FROM data_items
                    WHERE days_date = ? AND namespace = 'limitless'
                    ORDER BY created_at
                """, (days_date,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting items for day {days_date}: {e}")
            return []
    
    async def _update_day_items_status(self, days_date: str, status: ProcessingStatus):
        """Update semantic_status for all items in a day"""
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    UPDATE data_items 
                    SET semantic_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE days_date = ? AND namespace = 'limitless'
                """, (status.value, days_date))
                conn.commit()
                
                logger.debug(f"Updated {days_date} items to status: {status.value}")
                
        except Exception as e:
            logger.error(f"Error updating day items status for {days_date}: {e}")
            raise
    
    async def _assess_processing_queue(self):
        """Initial assessment of the processing queue on startup"""
        try:
            queue_status = await self.get_processing_queue_status()
            logger.info(f"Queue assessment: {queue_status['pending_days']} pending days, "
                       f"{queue_status['completed_days']} completed days")
            
            # Reset any items stuck in 'processing' state (from previous crash/restart)
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE data_items 
                    SET semantic_status = 'pending', updated_at = CURRENT_TIMESTAMP
                    WHERE semantic_status = 'processing' AND namespace = 'limitless'
                """)
                reset_count = cursor.rowcount
                conn.commit()
                
                if reset_count > 0:
                    logger.info(f"Reset {reset_count} items from 'processing' to 'pending' status")
            
        except Exception as e:
            logger.error(f"Error in queue assessment: {e}")
    
    async def _notify_progress_callbacks(self, days_date: str, status: ProcessingStatus):
        """Notify all registered progress callbacks"""
        for callback in self.processing_callbacks:
            try:
                await callback(days_date, status)
            except Exception as e:
                logger.warning(f"Error in progress callback: {e}")