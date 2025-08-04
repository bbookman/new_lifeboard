"""
Settings endpoints for Lifeboard

This module contains endpoints for application settings and configuration management.
"""

import logging
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from services.sync_manager_service import SyncManagerService
from sources.twitter import TwitterSource
from core.dependencies import get_dependency_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["settings"])

# Settings API - JSON endpoints only
# HTML settings page removed - frontend now uses React

from pydantic import BaseModel
from typing import Dict, Any

class SettingsResponse(BaseModel):
    settings: Dict[str, Any]

class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]

@router.get("/settings")
async def get_settings() -> SettingsResponse:
    """Get application settings"""
    # For now, return empty settings - this can be expanded later
    return SettingsResponse(settings={})

@router.put("/settings") 
async def update_settings(request: SettingsUpdateRequest) -> Dict[str, bool]:
    """Update application settings"""
    # For now, just return success - this can be expanded later
    return {"success": True}


def get_twitter_source() -> TwitterSource:
    registry = get_dependency_registry()
    startup_service = registry.get_startup_service()
    if not startup_service or not startup_service.ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not available")
    
    twitter_source = startup_service.ingestion_service.sources.get("twitter")
    if not twitter_source or not isinstance(twitter_source, TwitterSource):
        raise HTTPException(status_code=404, detail="Twitter source not found or not configured")
    return twitter_source


@router.post("/upload/twitter")
async def upload_twitter_archive(
    file: UploadFile = File(...),
    twitter_source: TwitterSource = Depends(get_twitter_source)
):
    """Upload and process Twitter archive"""
    temp_zip_path = f"/tmp/{file.filename}"
    try:
        with open(temp_zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await twitter_source.import_from_zip(temp_zip_path)

        if result["success"]:
            return JSONResponse(content={"message": result["message"]})
        else:
            logger.error(f"Twitter import failed: {result['message']}")
            return JSONResponse(content={"message": result["message"]}, status_code=500)
    except Exception as e:
        logger.error(f"Error uploading Twitter archive: {e}", exc_info=True)
        return JSONResponse(content={"message": "An unexpected error occurred during the upload process."}, status_code=500)
