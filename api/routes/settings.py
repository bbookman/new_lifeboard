"""
Settings endpoints for Lifeboard

This module contains endpoints for application settings and configuration management.
"""

import logging
import shutil
from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from services.sync_manager_service import SyncManagerService
from sources.twitter import TwitterSource
from core.dependencies import get_dependency_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["settings"])

# Templates will be set by the main server
templates = None


def set_templates(template_instance):
    """Set the templates instance from main server"""
    global templates
    templates = template_instance


@router.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request):
    """Serve the main settings page"""
    return templates.TemplateResponse("settings.html", {"request": request})


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

        success = await twitter_source.import_from_zip(temp_zip_path)

        if success:
            return JSONResponse(content={"message": "Twitter archive imported successfully."})
        else:
            logger.error(f"Twitter import failed for file: {file.filename}")
            return JSONResponse(content={"message": "Failed to import Twitter archive."}, status_code=500)
    except Exception as e:
        logger.error(f"Error uploading Twitter archive: {e}")
        return JSONResponse(content={"message": "An error occurred during the upload process."}, status_code=500)
