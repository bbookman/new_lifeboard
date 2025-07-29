from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from services.startup import StartupService

router = APIRouter(prefix="/api/sync", tags=["sync"])

# This will be set by the main server
get_startup_service_dependency = None

@router.post("/twitter")
async def sync_twitter(
    background_tasks: BackgroundTasks,
    startup_service: StartupService = Depends(lambda: get_startup_service_dependency())
):
    """Trigger a manual sync of Twitter data"""
    if "twitter" not in startup_service.ingestion_service.sources:
        raise HTTPException(status_code=404, detail="Twitter source not available or not configured")

    twitter_source = startup_service.ingestion_service.sources["twitter"]
    background_tasks.add_task(twitter_source.fetch_data)

    return {"message": "Twitter import started successfully. The data will be available shortly."}
