import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.clean_up_crew_service import (
    CleanUpCrewService, 
    ProcessingStatus, 
    DayProcessingResult,
    ProcessingStats
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clean-up-crew", tags=["clean_up_crew"])


class ProcessingTriggerRequest(BaseModel):
    """Request model for triggering processing"""
    force: bool = Field(default=False, description="Force processing even if already in progress")
    max_days: Optional[int] = Field(default=None, description="Maximum number of days to process")


class ProcessingResponse(BaseModel):
    """Response model for processing operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


async def get_clean_up_crew_service() -> CleanUpCrewService:
    """Get CleanUpCrewService instance (dependency injection)"""
    # This would be properly injected in a real application
    from services.startup import get_service_container
    container = get_service_container()
    return container.get('clean_up_crew_service')


@router.get("/status")
async def get_service_status(
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Get overall status of the CleanUpCrew service"""
    try:
        queue_status = await crew_service.get_processing_queue_status()
        stats = await crew_service.get_processing_statistics()
        
        return JSONResponse(content={
            "service_initialized": crew_service.is_initialized,
            "background_job_id": crew_service.background_job_id,
            "queue_status": queue_status,
            "statistics": {
                "total_days_processed": stats.total_days_processed,
                "total_items_processed": stats.total_items_processed,
                "total_clusters_created": stats.total_clusters_created,
                "success_rate": stats.success_rate,
                "last_updated": stats.last_updated.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service status: {e}"
        )


@router.get("/queue")
async def get_queue_status(
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Get detailed processing queue status"""
    try:
        queue_status = await crew_service.get_processing_queue_status()
        return JSONResponse(content=queue_status)
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {e}"
        )


@router.get("/day/{days_date}/status")
async def get_day_status(
    days_date: str,
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Get processing status for a specific day"""
    try:
        status = await crew_service.get_day_status(days_date)
        is_processing = days_date in crew_service.active_day_processing
        
        return JSONResponse(content={
            "days_date": days_date,
            "status": status.value,
            "is_processing": is_processing,
            "checked_at": "now"
        })
        
    except Exception as e:
        logger.error(f"Error getting day status for {days_date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get day status: {e}"
        )


@router.post("/day/{days_date}/process")
async def trigger_day_processing(
    days_date: str,
    request: ProcessingTriggerRequest = ProcessingTriggerRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Trigger semantic deduplication processing for a specific day"""
    try:
        # Check if already processing (unless forced)
        if not request.force and days_date in crew_service.active_day_processing:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "success": False,
                    "message": f"Day {days_date} is already being processed",
                    "data": {"days_date": days_date, "status": "processing"}
                }
            )
        
        # Trigger processing
        result = await crew_service.trigger_day_processing(days_date, force=request.force)
        
        return JSONResponse(content={
            "success": result.status != ProcessingStatus.FAILED,
            "message": f"Processing {'completed' if result.status == ProcessingStatus.COMPLETED else 'failed'} for {days_date}",
            "data": {
                "days_date": result.days_date,
                "status": result.status.value,
                "items_processed": result.items_processed,
                "clusters_created": result.clusters_created,
                "processing_time": result.processing_time,
                "error_message": result.error_message
            }
        })
        
    except Exception as e:
        logger.error(f"Error triggering processing for {days_date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger processing: {e}"
        )


@router.post("/batch/process")
async def trigger_batch_processing(
    request: ProcessingTriggerRequest = ProcessingTriggerRequest(),
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Trigger batch processing for multiple pending days"""
    try:
        results = await crew_service.trigger_batch_processing(max_days=request.max_days)
        
        # Summarize results
        successful = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
        total_items = sum(r.items_processed for r in results)
        total_clusters = sum(r.clusters_created for r in results)
        
        return JSONResponse(content={
            "success": failed == 0,
            "message": f"Batch processing completed: {successful} successful, {failed} failed",
            "data": {
                "total_days": len(results),
                "successful_days": successful,
                "failed_days": failed,
                "total_items_processed": total_items,
                "total_clusters_created": total_clusters,
                "results": [
                    {
                        "days_date": r.days_date,
                        "status": r.status.value,
                        "items_processed": r.items_processed,
                        "clusters_created": r.clusters_created,
                        "processing_time": r.processing_time,
                        "error_message": r.error_message
                    } for r in results
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"Error triggering batch processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger batch processing: {e}"
        )


@router.get("/statistics")
async def get_processing_statistics(
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Get comprehensive processing statistics"""
    try:
        stats = await crew_service.get_processing_statistics()
        
        return JSONResponse(content={
            "total_days_processed": stats.total_days_processed,
            "total_items_processed": stats.total_items_processed,
            "total_clusters_created": stats.total_clusters_created,
            "avg_processing_time": stats.avg_processing_time,
            "success_rate": stats.success_rate,
            "last_updated": stats.last_updated.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {e}"
        )


@router.get("/health")
async def get_service_health(
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Get service health check information"""
    try:
        # Basic health checks
        is_initialized = crew_service.is_initialized
        has_background_job = crew_service.background_job_id is not None
        active_processing_count = len(crew_service.active_day_processing)
        
        # Get queue status for health assessment
        queue_status = await crew_service.get_processing_queue_status()
        
        health_issues = []
        health_score = 100
        
        if not is_initialized:
            health_issues.append("Service not initialized")
            health_score -= 50
        
        if not has_background_job:
            health_issues.append("Background job not registered")
            health_score -= 30
        
        if queue_status.get("failed_days", 0) > 0:
            health_issues.append(f"{queue_status['failed_days']} days in failed status")
            health_score -= 10
        
        if active_processing_count > crew_service.max_concurrent_days:
            health_issues.append(f"Too many concurrent processing operations: {active_processing_count}")
            health_score -= 10
        
        health_status = "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "unhealthy"
        
        return JSONResponse(content={
            "status": health_status,
            "score": max(0, health_score),
            "checks": {
                "initialized": is_initialized,
                "background_job_registered": has_background_job,
                "active_processing_count": active_processing_count,
                "max_concurrent_allowed": crew_service.max_concurrent_days
            },
            "issues": health_issues,
            "queue_summary": {
                "total_days": queue_status.get("total_days", 0),
                "pending_days": queue_status.get("pending_days", 0),
                "completed_days": queue_status.get("completed_days", 0),
                "failed_days": queue_status.get("failed_days", 0)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting service health: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "score": 0,
                "error": str(e)
            }
        )


@router.post("/config/update")
async def update_service_config(
    batch_size: Optional[int] = Query(default=None, ge=10, le=200, description="Processing batch size"),
    max_concurrent_days: Optional[int] = Query(default=None, ge=1, le=10, description="Max concurrent day processing"),
    processing_interval: Optional[int] = Query(default=None, ge=60, le=3600, description="Background processing interval in seconds"),
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
) -> JSONResponse:
    """Update service configuration parameters"""
    try:
        updates = {}
        
        if batch_size is not None:
            crew_service.batch_size = batch_size
            updates["batch_size"] = batch_size
        
        if max_concurrent_days is not None:
            crew_service.max_concurrent_days = max_concurrent_days
            updates["max_concurrent_days"] = max_concurrent_days
        
        if processing_interval is not None:
            crew_service.processing_interval_seconds = processing_interval
            updates["processing_interval_seconds"] = processing_interval
            
            # Update scheduler job interval if background job exists
            if crew_service.background_job_id:
                crew_service.scheduler.update_job_interval(
                    crew_service.background_job_id, 
                    processing_interval
                )
        
        return JSONResponse(content={
            "success": True,
            "message": "Configuration updated successfully",
            "updates": updates,
            "current_config": {
                "batch_size": crew_service.batch_size,
                "max_concurrent_days": crew_service.max_concurrent_days,
                "processing_interval_seconds": crew_service.processing_interval_seconds
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating service config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {e}"
        )