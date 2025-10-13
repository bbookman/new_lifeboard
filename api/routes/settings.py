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
from sources.apple_music import AppleMusicSource
from sources.yelp import YelpSource
from services.twitter_api_service import TwitterAPIService
from services.twitter_rate_limit_service import TwitterRateLimitService
from core.dependencies import get_dependency_registry
from api.dependencies.twitter import get_twitter_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Settings API - JSON endpoints only
# HTML settings page removed - frontend now uses React

from pydantic import BaseModel
from typing import Dict, Any, Optional

class SettingsResponse(BaseModel):
    settings: Dict[str, Any]

class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]

class PromptSelectionRequest(BaseModel):
    prompt_document_id: Optional[str] = None

class PromptSelectionResponse(BaseModel):
    prompt_document_id: Optional[str] = None
    is_active: bool = True

class YelpHtmlRequest(BaseModel):
    html_content: str

@router.get("/")
async def get_settings() -> SettingsResponse:
    """Get application settings"""
    # For now, return empty settings - this can be expanded later
    return SettingsResponse(settings={})

@router.put("/") 
async def update_settings(request: SettingsUpdateRequest) -> Dict[str, bool]:
    """Update application settings"""
    # For now, just return success - this can be expanded later
    return {"success": True}

@router.get("/prompt-selection")
async def get_prompt_selection() -> PromptSelectionResponse:
    """Get current prompt selection for daily summary"""
    from core.dependencies import get_dependency_registry
    
    registry = get_dependency_registry()
    startup_service = registry.get_startup_service()
    
    if not startup_service or not startup_service.database:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        with startup_service.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT prompt_document_id, is_active
                FROM prompt_settings 
                WHERE setting_key LIKE 'daily_summary_prompt_%' AND is_active = TRUE
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                return PromptSelectionResponse(
                    prompt_document_id=row['prompt_document_id'],
                    is_active=bool(row['is_active'])
                )
            else:
                return PromptSelectionResponse(
                    prompt_document_id=None,
                    is_active=True
                )
                
    except Exception as e:
        logger.error(f"Error getting prompt selection: {e}")
        raise HTTPException(status_code=500, detail="Failed to get prompt selection")

@router.post("/prompt-selection")
async def save_prompt_selection(request: PromptSelectionRequest) -> Dict[str, bool]:
    """Save prompt selection for daily summary"""
    from core.dependencies import get_dependency_registry
    
    registry = get_dependency_registry()
    startup_service = registry.get_startup_service()
    
    if not startup_service or not startup_service.database:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        with startup_service.database.get_connection() as conn:
            # First, deactivate any existing settings
            conn.execute("""
                UPDATE prompt_settings 
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE setting_key LIKE 'daily_summary_prompt_%'
            """)
            
            # Insert new setting if prompt_document_id provided
            # NOTE: This uses fixed key 'daily_summary_prompt' which may conflict with
            # Documents API pattern 'daily_summary_prompt_{document_id}'
            if request.prompt_document_id:
                conn.execute("""
                    INSERT INTO prompt_settings (setting_key, prompt_document_id, is_active)
                    VALUES ('daily_summary_prompt', ?, TRUE)
                """, (request.prompt_document_id,))
            
            conn.commit()
            logger.info(f"Saved prompt selection: {request.prompt_document_id}")
            return {"success": True}
            
    except Exception as e:
        logger.error(f"Error saving prompt selection: {e}")
        raise HTTPException(status_code=500, detail="Failed to save prompt selection")




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
    logger.info(f"[TWITTER IMPORT] Starting Twitter archive upload: {file.filename}")
    
    try:
        # Save uploaded file
        with open(temp_zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"[TWITTER IMPORT] Saved uploaded file to: {temp_zip_path}")

        # Process the Twitter archive
        result = await twitter_source.import_from_zip(temp_zip_path)

        if result["success"]:
            # Get the ingestion service to actually store the data items
            registry = get_dependency_registry()
            startup_service = registry.get_startup_service()
            
            if not startup_service or not startup_service.ingestion_service:
                logger.error("[TWITTER IMPORT] Ingestion service not available")
                return JSONResponse(content={"message": "Ingestion service not available"}, status_code=500)
            
            # Ingest the data items if they were returned
            if result.get("data_items"):
                logger.info(f"[TWITTER IMPORT] Ingesting {len(result['data_items'])} data items into database")
                ingestion_result = await startup_service.ingestion_service.ingest_items("twitter", result["data_items"])
                logger.info(f"[TWITTER IMPORT] Successfully ingested {ingestion_result.items_stored} tweets into database "
                          f"({ingestion_result.items_processed} processed, {ingestion_result.embeddings_generated} embeddings generated)")
            
            logger.info(f"[TWITTER IMPORT] Twitter import successful: {result['message']}")
            return JSONResponse(content={"message": result["message"]})
        else:
            logger.error(f"[TWITTER IMPORT] Twitter import failed: {result['message']}")
            return JSONResponse(content={"message": result["message"]}, status_code=500)
            
    except HTTPException:
        # Re-raise HTTP exceptions (like dependency injection failures)
        raise
    except FileNotFoundError as e:
        logger.error(f"[TWITTER IMPORT] File not found during Twitter upload: {e}")
        return JSONResponse(content={"message": "Uploaded file could not be found or processed."}, status_code=500)
    except Exception as e:
        logger.error(f"[TWITTER IMPORT] Error uploading Twitter archive: {e}", exc_info=True)
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


@router.post("/process/apple")
async def process_apple_music_directory(
    files: list[UploadFile] = File(...)
):
    """Process Apple Music directory files"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    logger.info(f"[APPLE MUSIC] Starting Apple Music directory processing with {len(files)} files")

    try:
        # Get the Apple Music source and config from dependency registry
        registry = get_dependency_registry()
        startup_service = registry.get_startup_service()

        if not startup_service:
            logger.error("[APPLE MUSIC] Startup service not available")
            return JSONResponse(content={"message": "Service not available"}, status_code=500)

        # Get config and create Apple Music source
        config = startup_service.config
        if not config or not hasattr(config, 'apple_music'):
            logger.error("[APPLE MUSIC] Apple Music configuration not found")
            return JSONResponse(content={"message": "Apple Music configuration not available"}, status_code=500)

        apple_music_source = AppleMusicSource(
            config=config.apple_music,
            db_service=startup_service.database
        )

        # Read all uploaded files into memory
        uploaded_files = []
        for file in files:
            filename = file.filename or "unknown"
            content = await file.read()
            uploaded_files.append((filename, content))
            logger.debug(f"[APPLE MUSIC] Read file: {filename} ({len(content)} bytes)")

        # Process the directory
        result = await apple_music_source.process_directory(uploaded_files)

        if result["success"]:
            # Ingest the data items if they were returned
            if result.get("data_items"):
                if not startup_service.ingestion_service:
                    logger.error("[APPLE MUSIC] Ingestion service not available")
                    return JSONResponse(content={"message": "Ingestion service not available"}, status_code=500)

                logger.info(f"[APPLE MUSIC] Ingesting {len(result['data_items'])} data items into database")
                ingestion_result = await startup_service.ingestion_service.ingest_items(
                    "apple_music",
                    result["data_items"]
                )
                logger.info(f"[APPLE MUSIC] Successfully ingested {ingestion_result.items_stored} track plays "
                          f"({ingestion_result.items_processed} processed, {ingestion_result.embeddings_generated} embeddings generated)")

            logger.info(f"[APPLE MUSIC] Apple Music import successful: {result['message']}")
            return JSONResponse(content={"message": result["message"]})
        else:
            logger.error(f"[APPLE MUSIC] Apple Music import failed: {result['message']}")
            return JSONResponse(content={"message": result["message"]}, status_code=400)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[APPLE MUSIC] Error processing Apple Music directory: {e}", exc_info=True)
        error_msg = f"An error occurred during Apple Music import: {str(e)}"
        return JSONResponse(content={"message": error_msg}, status_code=500)


@router.post("/process/yelp")
async def process_yelp_html(request: YelpHtmlRequest):
    """Process Yelp review HTML content"""
    if not request.html_content:
        raise HTTPException(status_code=400, detail="No HTML content provided")

    logger.info("[YELP] Starting Yelp review processing")

    try:
        # Get the Yelp source and config from dependency registry
        registry = get_dependency_registry()
        startup_service = registry.get_startup_service()

        if not startup_service:
            logger.error("[YELP] Startup service not available")
            return JSONResponse(content={"message": "Service not available"}, status_code=500)

        # Get config and create Yelp source
        config = startup_service.config
        if not config or not hasattr(config, 'yelp'):
            logger.error("[YELP] Yelp configuration not found")
            return JSONResponse(content={"message": "Yelp configuration not available"}, status_code=500)

        yelp_source = YelpSource(
            config=config.yelp,
            db_service=startup_service.database
        )

        # Process the HTML content
        result = await yelp_source.process_html_content(request.html_content)

        if result["success"]:
            # Ingest the data items if they were returned
            if result.get("data_items"):
                if not startup_service.ingestion_service:
                    logger.error("[YELP] Ingestion service not available")
                    return JSONResponse(content={"message": "Ingestion service not available"}, status_code=500)

                logger.info(f"[YELP] Ingesting {len(result['data_items'])} data items into database")
                ingestion_result = await startup_service.ingestion_service.ingest_items(
                    "yelp",
                    result["data_items"]
                )
                logger.info(f"[YELP] Successfully ingested {ingestion_result.items_stored} reviews "
                          f"({ingestion_result.items_processed} processed, {ingestion_result.embeddings_generated} embeddings generated)")

            logger.info(f"[YELP] Yelp import successful: {result['message']}")
            return JSONResponse(content={"message": result["message"]})
        else:
            logger.error(f"[YELP] Yelp import failed: {result['message']}")
            return JSONResponse(content={"message": result["message"]}, status_code=400)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[YELP] Error processing Yelp HTML: {e}", exc_info=True)
        error_msg = f"An error occurred during Yelp import: {str(e)}"
        return JSONResponse(content={"message": error_msg}, status_code=500)
