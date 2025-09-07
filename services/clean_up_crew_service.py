import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
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
    - Real-time progress tracking via HTTP endpoints
    - Performance optimization and caching strategies
    - Error handling and recovery mechanisms
    """
    
    def __init__(self, 
                 database_service: DatabaseService,
                 scheduler_service: AsyncScheduler,
                 semantic_service: SemanticDeduplicationService):
        self.database = database_service
        self.scheduler = scheduler_service
        self.semantic_service = semantic_service
        
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
    
    
    async def get_processing_queue_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the processing queue"""
        try:
            async with self.database.get_async_connection() as conn:
                # Get status breakdown by day
                async with conn.execute("""
                    SELECT days_date, semantic_status, COUNT(*) as count
                    FROM data_items 
                    WHERE namespace = 'limitless'
                    GROUP BY days_date, semantic_status
                    ORDER BY days_date DESC
                """) as cursor:
                    
                    rows = await cursor.fetchall()
                    day_status = {}
                    for row in rows:
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
                    "active_processing": bool(self.active_day_processing),
                    "active_processing_days": list(self.active_day_processing),
                    "day_breakdown": day_status,
                    "background_job_id": self.background_job_id,
                    "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
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
    
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get current processing queue statistics (synchronous version for HTTP API)
        Returns statistics structure expected by HTTP endpoints
        """
        try:
            with self.database.get_connection() as conn:
                # Get counts for each status
                cursor = conn.execute("""
                    SELECT 
                        (SELECT COUNT(DISTINCT days_date) 
                         FROM data_items 
                         WHERE namespace = 'limitless' 
                         AND semantic_status = 'completed') as completed_days,
                        (SELECT COUNT(DISTINCT days_date) 
                         FROM data_items 
                         WHERE namespace = 'limitless' 
                         AND semantic_status = 'pending') as pending_days,
                        (SELECT COUNT(DISTINCT days_date) 
                         FROM data_items 
                         WHERE namespace = 'limitless' 
                         AND semantic_status = 'processing') as processing_days,
                        (SELECT COUNT(DISTINCT days_date) 
                         FROM data_items 
                         WHERE namespace = 'limitless' 
                         AND semantic_status = 'failed') as failed_days
                """)
                
                row = cursor.fetchone()
                
                completed_days = row['completed_days'] if row['completed_days'] is not None else 0
                pending_days = row['pending_days'] if row['pending_days'] is not None else 0
                processing_days = row['processing_days'] if row['processing_days'] is not None else 0
                failed_days = row['failed_days'] if row['failed_days'] is not None else 0
                
                total_days = completed_days + pending_days + processing_days + failed_days
                active_processing = processing_days > 0
                
                return {
                    "total_days": total_days,
                    "completed_days": completed_days,
                    "pending_days": pending_days,
                    "processing_days": processing_days,
                    "failed_days": failed_days,
                    "active_processing": active_processing,
                    "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                }
                
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            raise
    
    def get_day_status(self, date: str) -> Optional[Dict[str, Any]]:
        """
        Get processing status for a specific day (synchronous version for HTTP API)
        Returns day-specific processing information
        """
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        semantic_status,
                        COUNT(*) as total_items,
                        SUM(CASE WHEN semantic_status = 'completed' THEN 1 ELSE 0 END) as processed_items,
                        SUM(CASE WHEN semantic_status = 'failed' THEN 1 ELSE 0 END) as failed_items,
                        MAX(updated_at) as last_updated
                    FROM data_items 
                    WHERE days_date = ? AND namespace = 'limitless'
                    GROUP BY days_date
                """, (date,))
                
                row = cursor.fetchone()
                
                if not row or row['total_items'] == 0:
                    return None
                
                total_items = row['total_items']
                processed_items = row['processed_items'] if row['processed_items'] is not None else 0
                failed_items = row['failed_items'] if row['failed_items'] is not None else 0
                last_updated = row['last_updated'] if row['last_updated'] else datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                
                # Determine status based on items
                if processed_items == total_items:
                    status = "completed"
                elif failed_items > 0:
                    status = "failed"
                elif processed_items > 0:
                    status = "processing"
                else:
                    status = "pending"
                
                # Mock processing time (in real implementation, this would come from processing logs)
                processing_time_seconds = 0.0
                if status in ["completed", "failed"]:
                    processing_time_seconds = min(total_items * 0.5, 60.0)  # Estimate based on item count
                
                return {
                    "status": status,
                    "total_items": total_items,
                    "processed_items": processed_items,
                    "failed_items": failed_items,
                    "processing_time_seconds": processing_time_seconds,
                    "last_updated": last_updated
                }
                
        except Exception as e:
            logger.error(f"Error getting day status for {date}: {e}")
            raise
    
    async def get_processing_statistics(self) -> ProcessingStats:
        """Get comprehensive processing statistics"""
        try:
            async with self.database.get_async_connection() as conn:
                # Basic statistics
                async with conn.execute("""
                    SELECT 
                        COUNT(DISTINCT days_date) as total_days,
                        COUNT(*) as total_items,
                        semantic_status
                    FROM data_items 
                    WHERE namespace = 'limitless'
                    GROUP BY semantic_status
                """) as cursor:
                    
                    rows = await cursor.fetchall()
                    status_stats = {row['semantic_status']: {
                        'days': row['total_days'], 
                        'items': row['total_items']
                    } for row in rows}
                
                # Calculate totals and success rate
                total_items = sum(stats['items'] for stats in status_stats.values())
                completed_items = status_stats.get('completed', {}).get('items', 0)
                success_rate = completed_items / total_items if total_items > 0 else 0
                
                # Get cluster statistics
                async with conn.execute("SELECT COUNT(*) as cluster_count FROM semantic_clusters") as cursor:
                    row = await cursor.fetchone()
                    cluster_count = row['cluster_count']
                
                return ProcessingStats(
                    total_days_processed=sum(stats['days'] for stats in status_stats.values()),
                    total_items_processed=total_items,
                    total_clusters_created=cluster_count,
                    avg_processing_time=0.0,  # Processing time calculation not yet implemented
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
            
            return result
            
        finally:
            # Remove from active processing
            self.active_day_processing.discard(days_date)
    
    async def _get_pending_days(self, limit: Optional[int] = None) -> List[str]:
        """Get list of days with pending semantic processing"""
        try:
            async with self.database.get_async_connection() as conn:
                query = """
                    SELECT DISTINCT days_date
                    FROM data_items 
                    WHERE namespace = 'limitless' 
                    AND semantic_status = 'pending'
                    ORDER BY days_date DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                async with conn.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [row['days_date'] for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting pending days: {e}")
            return []
    
    async def _get_day_items(self, days_date: str) -> List[Dict[str, Any]]:
        """Get all data items for a specific day"""
        try:
            async with self.database.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                    FROM data_items
                    WHERE days_date = ? AND namespace = 'limitless'
                    ORDER BY created_at
                """, (days_date,)) as cursor:
                    
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting items for day {days_date}: {e}")
            return []
    
    async def _update_day_items_status(self, days_date: str, status: ProcessingStatus):
        """Update semantic_status for all items in a day"""
        try:
            async with self.database.get_async_connection() as conn:
                await conn.execute("""
                    UPDATE data_items 
                    SET semantic_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE days_date = ? AND namespace = 'limitless'
                """, (status.value, days_date))
                await conn.commit()
                
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
            async with self.database.get_async_connection() as conn:
                async with conn.execute("""
                    UPDATE data_items 
                    SET semantic_status = 'pending', updated_at = CURRENT_TIMESTAMP
                    WHERE semantic_status = 'processing' AND namespace = 'limitless'
                """) as cursor:
                    reset_count = cursor.rowcount
                await conn.commit()
                
                if reset_count > 0:
                    logger.info(f"Reset {reset_count} items from 'processing' to 'pending' status")
            
        except Exception as e:
            logger.error(f"Error in queue assessment: {e}")
    
