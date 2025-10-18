"""
Speaker Labeling API routes

This module provides REST API endpoints for speaker labeling operations,
including manual regeneration and status checking.
"""

import logging
from typing import Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from services.speaker_labeling_service import SpeakerLabelingService
from services.startup import StartupService
from core.exception_handling import handle_api_exceptions
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speaker-labeling", tags=["speaker_labeling"])


def get_speaker_labeling_service(
    startup_service: StartupService = Depends(get_startup_service_dependency)
) -> SpeakerLabelingService:
    """Get the speaker labeling service instance for route dependency injection"""
    if not startup_service.database:
        raise HTTPException(status_code=503, detail="Database service not available")

    return SpeakerLabelingService(
        database=startup_service.database,
        config=startup_service.config
    )


# Pydantic models for API requests and responses
class RegenerateRequest(BaseModel):
    days_date: str = Field(..., description="Date for regeneration (YYYY-MM-DD)")


class RegenerateResponse(BaseModel):
    success: bool
    days_date: str
    items_reprocessed: int
    items_improved: int
    items_skipped: int
    duration_seconds: float
    errors: list[str] = []


class ProcessBatchRequest(BaseModel):
    batch_size: int = Field(10, description="Number of items to process")
    force_reprocess: bool = Field(False, description="Force reprocess even if already completed")


class ProcessBatchResponse(BaseModel):
    items_processed: int
    items_completed: int
    items_skipped: int
    items_failed: int
    errors: list[str] = []


class StatisticsResponse(BaseModel):
    total: int
    by_status: Dict[str, int]
    pending_count: int
    completed_count: int
    skipped_count: int
    failed_count: int


# API Endpoints
@router.post("/regenerate", response_model=RegenerateResponse)
@handle_api_exceptions("Failed to regenerate speaker labeling", 500, include_details=True)
async def regenerate_speaker_labeling_for_date(
    request: RegenerateRequest,
    service: SpeakerLabelingService = Depends(get_speaker_labeling_service)
) -> RegenerateResponse:
    """
    Manually regenerate speaker labeling for a specific date

    This endpoint resets all limitless items for the specified date to pending status
    and reprocesses them through the speaker labeling pipeline.
    """
    import time
    from datetime import datetime

    logger.info("=" * 80)
    logger.info("[REGENERATE API] ===== REQUEST RECEIVED =====")
    logger.info(f"[REGENERATE API] Timestamp: {datetime.now().isoformat()}")
    logger.info(f"[REGENERATE API] Request days_date: {request.days_date}")
    logger.info(f"[REGENERATE API] Request object: {request}")

    try:
        start_time = time.time()
        logger.info(f"[REGENERATE API] Start time: {start_time}")

        # Regenerate for the date
        logger.info(f"[REGENERATE API] Calling service.regenerate_speaker_labeling_for_date('{request.days_date}')...")
        result = await service.regenerate_speaker_labeling_for_date(request.days_date)
        logger.info(f"[REGENERATE API] Service call returned")
        logger.info(f"[REGENERATE API] Result: {result}")

        duration = time.time() - start_time
        logger.info(f"[REGENERATE API] Duration: {duration:.2f} seconds")

        if result["success"]:
            logger.info("[REGENERATE API] ===== SUCCESS =====")
            logger.info(f"[REGENERATE API] Date: {request.days_date}")
            logger.info(f"[REGENERATE API] Items reprocessed: {result['items_reprocessed']}")
            logger.info(f"[REGENERATE API] Items improved: {result['items_improved']}")
            logger.info(f"[REGENERATE API] Items skipped: {result['items_skipped']}")
            logger.info(f"[REGENERATE API] Errors: {result.get('errors', [])}")
        else:
            logger.error("[REGENERATE API] ===== FAILURE =====")
            logger.error(f"[REGENERATE API] Failed to regenerate for {request.days_date}")
            logger.error(f"[REGENERATE API] Errors: {result.get('errors', [])}")

        response = RegenerateResponse(
            success=result["success"],
            days_date=request.days_date,
            items_reprocessed=result["items_reprocessed"],
            items_improved=result["items_improved"],
            items_skipped=result["items_skipped"],
            duration_seconds=duration,
            errors=result.get("errors", [])
        )
        logger.info(f"[REGENERATE API] Response object: {response}")
        logger.info("=" * 80)
        return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error("[REGENERATE API] ===== FATAL ERROR =====")
        logger.error(f"[REGENERATE API] Error type: {type(e).__name__}")
        logger.error(f"[REGENERATE API] Error message: {str(e)}")
        logger.error(f"[REGENERATE API] Date: {request.days_date}")
        logger.error("[REGENERATE API] Stack trace:", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=f"Failed to regenerate speaker labeling: {e}")


@router.post("/process-batch", response_model=ProcessBatchResponse)
@handle_api_exceptions("Failed to process speaker labeling batch", 500, include_details=True)
async def process_speaker_labeling_batch(
    request: ProcessBatchRequest,
    service: SpeakerLabelingService = Depends(get_speaker_labeling_service)
) -> ProcessBatchResponse:
    """
    Process a batch of pending speaker labeling items

    This endpoint processes pending items in batches, useful for manual triggering
    of the speaker labeling pipeline.
    """
    logger.info(f"Received request to process speaker labeling batch: "
               f"batch_size={request.batch_size}, force={request.force_reprocess}")

    try:
        result = await service.process_pending_speaker_labeling(
            batch_size=request.batch_size,
            force_reprocess=request.force_reprocess
        )

        logger.info(f"Batch processing complete: {result['items_completed']} completed, "
                   f"{result['items_skipped']} skipped, {result['items_failed']} failed")

        return ProcessBatchResponse(
            items_processed=result["items_processed"],
            items_completed=result["items_completed"],
            items_skipped=result["items_skipped"],
            items_failed=result["items_failed"],
            errors=result.get("errors", [])
        )

    except Exception as e:
        logger.error(f"Fatal error in process-batch endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process batch: {e}")


@router.get("/statistics", response_model=StatisticsResponse)
@handle_api_exceptions("Failed to get speaker labeling statistics", 500, include_details=True)
async def get_speaker_labeling_statistics(
    service: SpeakerLabelingService = Depends(get_speaker_labeling_service)
) -> StatisticsResponse:
    """
    Get statistics about speaker labeling processing status

    Returns counts of items in each processing state.
    """
    try:
        stats = await service.get_speaker_labeling_statistics()

        return StatisticsResponse(
            total=stats["total"],
            by_status=stats["by_status"],
            pending_count=stats["pending_count"],
            completed_count=stats["completed_count"],
            skipped_count=stats["skipped_count"],
            failed_count=stats["failed_count"]
        )

    except Exception as e:
        logger.error(f"Error getting speaker labeling statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get statistics")
