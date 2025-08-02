from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from services.startup import StartupService
from core.dependencies import get_startup_service_dependency

router = APIRouter(prefix="/api/sync", tags=["sync"])

@router.post("/twitter")
async def sync_twitter(
    background_tasks: BackgroundTasks,
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Trigger a manual sync of Twitter data"""
    if "twitter" not in startup_service.ingestion_service.sources:
        raise HTTPException(status_code=404, detail="Twitter source not available or not configured")

    # For Twitter, sync is done through manual upload, not automatic fetching
    # This endpoint exists for API consistency but doesn't do anything for Twitter
    return {"message": "Twitter data sync is done through manual archive upload. Use the upload endpoint instead."}
