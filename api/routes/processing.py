"""
Processing endpoints for queue status and day-specific processing information
HTTP-based endpoints to replace WebSocket communication
"""

import logging
from datetime import datetime, date, timezone
from typing import Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from services.clean_up_crew_service import CleanUpCrewService
from services.startup import StartupService
from core.exception_handling import handle_api_exceptions
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processing", tags=["processing"])

def get_clean_up_crew_service_for_route(startup_service: StartupService = Depends(get_startup_service_dependency)) -> CleanUpCrewService:
    """Get the clean up crew service instance for route dependency injection"""
    if not startup_service.clean_up_crew_service:
        raise HTTPException(status_code=503, detail="Clean up crew service not available")
    return startup_service.clean_up_crew_service


# Pydantic models for JSON API endpoints
class ProcessingStats(BaseModel):
    total_days: int
    completed_days: int
    pending_days: int
    processing_days: int
    failed_days: int
    active_processing: bool
    last_updated: str

class DayStatus(BaseModel):
    date: str
    status: str
    progress: int
    total_items: int
    processed_items: int
    failed_items: int
    last_updated: str
    processing_time_seconds: float

class TriggerResponse(BaseModel):
    success: bool
    processed: int


# HTTP API endpoints for processing status
@router.get("/queue")
@handle_api_exceptions("Failed to get processing queue status", 500, include_details=True)
async def get_processing_queue(
    clean_up_crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service_for_route)
) -> ProcessingStats:
    """
    Get current processing queue statistics
    Returns overall processing status including total days, completed, pending, etc.
    """
    stats = clean_up_crew_service.get_queue_stats()
    
    return ProcessingStats(
        total_days=stats.get("total_days", 0),
        completed_days=stats.get("completed_days", 0),
        pending_days=stats.get("pending_days", 0),
        processing_days=stats.get("processing_days", 0),
        failed_days=stats.get("failed_days", 0),
        active_processing=stats.get("active_processing", False),
        last_updated=stats.get("last_updated", datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    )


@router.get("/day/{date}")
async def get_day_processing_status(
    date: str,
    clean_up_crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service_for_route)
) -> DayStatus:
    """
    Get processing status for a specific day
    Returns day-specific processing information including progress and item counts
    """
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if date is in the future
        if parsed_date > datetime.now().date():
            raise HTTPException(status_code=400, detail="Future dates not allowed")
        
        # Get day status from service
        day_status = clean_up_crew_service.get_day_status(date)
        
        if day_status is None:
            raise HTTPException(status_code=404, detail="Day not found in processing queue")
        
        # Calculate progress percentage
        total_items = day_status.get("total_items", 0)
        processed_items = day_status.get("processed_items", 0)
        progress = int((processed_items / total_items) * 100) if total_items > 0 else 0
        
        return DayStatus(
            date=date,
            status=day_status.get("status", "unknown"),
            progress=progress,
            total_items=total_items,
            processed_items=processed_items,
            failed_items=day_status.get("failed_items", 0),
            last_updated=day_status.get("last_updated", datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')),
            processing_time_seconds=day_status.get("processing_time_seconds", 0.0)
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error getting day processing status for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get day processing status: {str(e)}")


@router.post('/trigger')
@handle_api_exceptions('Failed to trigger processing', 500, include_details=True)
async def trigger_processing(clean_up_crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service_for_route)) -> TriggerResponse:
    """
    Trigger batch processing of pending items
    Returns success status and count of processed items
    """
    try:
        results = await clean_up_crew_service.trigger_batch_processing()
        return TriggerResponse(success=True, processed=len(results))
    except Exception as e:
        logger.error(f"Error triggering batch processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger processing: {str(e)}")