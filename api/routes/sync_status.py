"""
Sync Status API routes for real-time synchronization progress tracking

Provides endpoints for monitoring data source synchronization progress
and overall system sync status.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from services.sync_status_service import get_sync_status_service, SyncStatusService
from services.startup import StartupService
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync-status", tags=["sync-status"])


class SyncStatusResponse(BaseModel):
    """Response model for sync status"""
    is_complete: bool
    is_in_progress: bool
    completed_sources: int
    failed_sources: int
    in_progress_sources: int
    total_sources: int
    overall_progress: float
    global_started_at: Optional[str] = None
    global_completed_at: Optional[str] = None
    global_duration_seconds: Optional[float] = None
    sources: Dict[str, Any]


class SourceStatusResponse(BaseModel):
    """Response model for individual source status"""
    namespace: str
    source_type: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_updated: Optional[str] = None
    error_message: Optional[str] = None
    items_processed: int
    items_stored: int
    progress_percentage: float
    duration_seconds: Optional[float] = None


def get_sync_status_service_dependency() -> SyncStatusService:
    """Get sync status service dependency"""
    service = get_sync_status_service()
    if not service:
        raise HTTPException(
            status_code=503, 
            detail="Sync status service not available"
        )
    return service


@router.get("/", response_model=SyncStatusResponse)
async def get_overall_sync_status(
    sync_status_service: SyncStatusService = Depends(get_sync_status_service_dependency)
) -> Dict[str, Any]:
    """
    Get overall synchronization status for all data sources.
    
    Returns comprehensive sync progress including:
    - Overall completion status
    - Progress percentage
    - Individual source statuses
    - Timing information
    """
    try:
        status = sync_status_service.get_overall_status()
        logger.debug(f"Returning overall sync status: {status['completed_sources']}/{status['total_sources']} complete")
        return status
    except Exception as e:
        logger.error(f"Error getting overall sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sync status")


@router.get("/source/{namespace}", response_model=SourceStatusResponse)
async def get_source_sync_status(
    namespace: str,
    sync_status_service: SyncStatusService = Depends(get_sync_status_service_dependency)
) -> Dict[str, Any]:
    """
    Get synchronization status for a specific data source.
    
    Args:
        namespace: The namespace/identifier of the data source (e.g., 'limitless', 'news')
    
    Returns:
        Detailed sync status for the specified source
    """
    try:
        status = sync_status_service.get_source_status(namespace)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Source '{namespace}' not found"
            )
        
        logger.debug(f"Returning sync status for {namespace}: {status['status']}")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync status for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync status for {namespace}")


@router.get("/health")
async def get_sync_status_service_health(
    sync_status_service: SyncStatusService = Depends(get_sync_status_service_dependency)
) -> Dict[str, Any]:
    """
    Get health status of the sync status service itself.
    
    Returns:
        Service health information and basic metrics
    """
    try:
        health = await sync_status_service.get_service_health()
        return health
    except Exception as e:
        logger.error(f"Error getting sync status service health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service health")


@router.post("/reset")
async def reset_sync_status(
    sync_status_service: SyncStatusService = Depends(get_sync_status_service_dependency)
) -> Dict[str, str]:
    """
    Reset all source sync statuses to pending (useful for testing and debugging).
    
    WARNING: This will reset all sync progress tracking.
    """
    try:
        await sync_status_service.reset_all_sources()
        logger.info("Reset all sync statuses via API request")
        return {
            "message": "All sync statuses reset to pending",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error resetting sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset sync status")