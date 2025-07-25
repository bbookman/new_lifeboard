"""
Sync management endpoints

This module contains endpoints for managing data synchronization
from various sources.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from services.startup import StartupService
from services.sync_manager_service import SyncManagerService
from core.exception_handling import handle_api_exceptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncTriggerRequest(BaseModel):
    """Request model for triggering sync"""
    force_full_sync: bool = False
    limit: int = Field(default=1000, ge=1, le=10000)


class SyncResponse(BaseModel):
    """Response model for sync operations"""
    success: bool
    message: str
    namespace: str
    result: Optional[Dict[str, Any]] = None


class StatusResponse(BaseModel):
    """Response model for status endpoints"""
    timestamp: str
    data: Dict[str, Any]


# Dependency functions (will be injected from main server)
def get_startup_service_dependency():
    """This will be set by the main server module"""
    raise NotImplementedError("Startup service dependency not configured")


def get_sync_manager_dependency():
    """This will be set by the main server module"""
    raise NotImplementedError("Sync manager dependency not configured")


@router.get("/status")
@handle_api_exceptions("Failed to get sync status", 500)
async def get_sync_status(sync_manager: SyncManagerService = Depends(get_sync_manager_dependency)):
    """Get sync status for all sources"""
    status = sync_manager.get_all_sources_sync_status()
    
    return StatusResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=status
    )


@router.get("/{namespace}/status")
@handle_api_exceptions("Failed to get source sync status", 500)
async def get_source_sync_status(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager_dependency)
):
    """Get sync status for a specific source"""
    status = sync_manager.get_source_sync_status(namespace)
    
    if not status:
        raise HTTPException(
            status_code=404, 
            detail=f"Source {namespace} not found or not registered for sync"
        )
    
    return StatusResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=status
    )


@router.post("/{namespace}", response_model=SyncResponse)
@handle_api_exceptions("Sync operation failed", 500)
async def trigger_sync(
    namespace: str,
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Trigger immediate sync for a namespace"""
    if not startup_service.ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not available")
    
    # Check if source exists
    if namespace not in startup_service.ingestion_service.sources:
        raise HTTPException(status_code=404, detail=f"Source {namespace} not registered")
    
    # Trigger sync
    result = await startup_service.trigger_immediate_sync(
        namespace=namespace,
        force_full_sync=request.force_full_sync
    )
    
    return SyncResponse(
        success=result.success,
        message=f"Sync completed for {namespace}: {result.items_processed} processed, {result.items_stored} stored",
        namespace=namespace,
        result=result.to_dict()
    )


@router.post("/{namespace}/schedule")
@handle_api_exceptions("Failed to trigger scheduled job", 500)
async def trigger_scheduled_job(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager_dependency)
):
    """Trigger the scheduled job for a namespace immediately"""
    success = await sync_manager.trigger_scheduled_job(namespace)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"No scheduled job found for {namespace}"
        )
    
    return {"success": True, "message": f"Triggered scheduled job for {namespace}"}


@router.post("/{namespace}/pause")
@handle_api_exceptions("Failed to pause sync", 500)
async def pause_sync(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager_dependency)
):
    """Pause automatic syncing for a source"""
    success = sync_manager.pause_source_sync(namespace)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Source {namespace} not found or not registered for auto-sync"
        )
    
    return {"success": True, "message": f"Paused auto-sync for {namespace}"}


@router.post("/{namespace}/resume")
@handle_api_exceptions("Failed to resume sync", 500)
async def resume_sync(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager_dependency)
):
    """Resume automatic syncing for a source"""
    success = sync_manager.resume_source_sync(namespace)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Source {namespace} not found or not paused"
        )
    
    return {"success": True, "message": f"Resumed auto-sync for {namespace}"}