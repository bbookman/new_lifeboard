"""
Settings endpoints for Lifeboard

This module contains endpoints for application settings and configuration management.
"""

import logging
import os
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
    if not startup_service:
        logger.error("Startup service not available in dependency registry")
        raise HTTPException(status_code=503, detail="Application not properly initialized")
    
    if not startup_service.ingestion_service:
        logger.error("Ingestion service not available in startup service")
        raise HTTPException(status_code=503, detail="Ingestion service not available")
    
    twitter_source = startup_service.ingestion_service.sources.get("twitter")
    if not twitter_source:
        available_sources = list(startup_service.ingestion_service.sources.keys())
        logger.error(f"Twitter source not found. Available sources: {available_sources}")
        raise HTTPException(status_code=404, detail="Twitter source not found or not configured")
    
    if not isinstance(twitter_source, TwitterSource):
        logger.error(f"Twitter source is wrong type: {type(twitter_source)}")
        raise HTTPException(status_code=404, detail="Twitter source not properly configured")
    
    return twitter_source


@router.post("/upload/twitter")
async def upload_twitter_archive(
    file: UploadFile = File(...),
    twitter_source: TwitterSource = Depends(get_twitter_source)
):
    """Upload and process Twitter archive"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")
    
    temp_zip_path = f"/tmp/{file.filename}"
    logger.info(f"Starting Twitter archive upload: {file.filename}")
    
    try:
        # Save uploaded file
        with open(temp_zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Saved uploaded file to: {temp_zip_path}")

        # Process the Twitter archive
        result = await twitter_source.import_from_zip(temp_zip_path)

        if result["success"]:
            logger.info(f"Twitter import successful: {result['message']}")
            return JSONResponse(content={"message": result["message"]})
        else:
            logger.error(f"Twitter import failed: {result['message']}")
            return JSONResponse(content={"message": result["message"]}, status_code=500)
            
    except HTTPException:
        # Re-raise HTTP exceptions (like dependency injection failures)
        raise
    except FileNotFoundError as e:
        logger.error(f"File not found during Twitter upload: {e}")
        return JSONResponse(content={"message": "Uploaded file could not be found or processed."}, status_code=500)
    except Exception as e:
        logger.error(f"Error uploading Twitter archive: {e}", exc_info=True)
        # Provide more specific error message based on the exception
        if "ingest_items" in str(e):
            error_msg = "Internal service error: ingestion method not available. Please contact support."
        elif "zip" in str(e).lower():
            error_msg = "Invalid ZIP file format. Please ensure you're uploading a valid Twitter archive."
        else:
            error_msg = "An unexpected error occurred during the upload process."
        
        return JSONResponse(content={"message": error_msg}, status_code=500)
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
                logger.debug(f"Cleaned up temporary file: {temp_zip_path}")
        except Exception as cleanup_error:
            logger.warning(f"Could not clean up temporary file {temp_zip_path}: {cleanup_error}")
