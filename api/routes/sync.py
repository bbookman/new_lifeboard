from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from core.dependencies import get_startup_service_dependency
from services.startup import StartupService

router = APIRouter(prefix="", tags=["sync"])

class SyncTriggerRequest(BaseModel):
    source: Optional[str] = None

class SyncResponse(BaseModel):
    status: str
    message: Optional[str] = None

@router.post("/sync/trigger")
async def trigger_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    startup_service: StartupService = Depends(get_startup_service_dependency),
):
    """Trigger a manual sync for a specific source or all sources"""
    try:
        sync_manager = startup_service.sync_manager
        if not sync_manager:
            raise HTTPException(status_code=503, detail="Sync manager not available")

        if request.source:
            # Trigger sync for specific source
            if request.source not in startup_service.ingestion_service.sources:
                raise HTTPException(status_code=404, detail=f"Source '{request.source}' not found")

            # Add sync job to background tasks
            background_tasks.add_task(sync_manager.sync_source, request.source)
            return SyncResponse(status="triggered", message=f"Sync triggered for {request.source}")
        # Trigger sync for all sources
        available_sources = list(startup_service.ingestion_service.sources.keys())
        for source in available_sources:
            background_tasks.add_task(sync_manager.sync_source, source)
        return SyncResponse(status="triggered", message=f"Sync triggered for all sources: {available_sources}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger sync: {e!s}")


@router.get("/sync/status")
async def get_sync_status(
    startup_service: StartupService = Depends(get_startup_service_dependency),
) -> Dict[str, Any]:
    """Get sync status for all sources"""
    try:
        sync_manager = startup_service.sync_manager
        if not sync_manager:
            raise HTTPException(status_code=503, detail="Sync manager not available")

        # Get source status information
        sources_status = {}
        if hasattr(startup_service, "ingestion_service") and startup_service.ingestion_service:
            for source_name in startup_service.ingestion_service.sources.keys():
                # Get basic source info
                sources_status[source_name] = {
                    "available": True,
                    "last_sync": "unknown",  # Could be enhanced with actual last sync time
                    "status": "available",
                }

        return {
            "sync_manager_healthy": True,
            "sources": sources_status,
            "scheduler_running": hasattr(sync_manager, "scheduler") and sync_manager.scheduler is not None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {e!s}")


@router.post("/api/sync/twitter")
async def sync_twitter(
    background_tasks: BackgroundTasks,
    startup_service: StartupService = Depends(get_startup_service_dependency),
):
    """Trigger a manual sync of Twitter data"""
    if "twitter" not in startup_service.ingestion_service.sources:
        raise HTTPException(status_code=404, detail="Twitter source not available or not configured")

    # For Twitter, sync is done through manual upload, not automatic fetching
    # This endpoint exists for API consistency but doesn't do anything for Twitter
    return {"message": "Twitter data sync is done through manual archive upload. Use the upload endpoint instead."}
