"""
Embeddings management endpoints

This module contains endpoints for managing vector embeddings
and processing operations.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.startup import StartupService
from core.exception_handling import handle_api_exceptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


class EmbeddingProcessResponse(BaseModel):
    """Response model for embedding processing operations"""
    success: bool
    message: str
    result: Dict[str, Any]


# Dependency function (will be injected from main server)
def get_startup_service_dependency():
    """This will be set by the main server module"""
    raise NotImplementedError("Startup service dependency not configured")


@router.post("/process", response_model=EmbeddingProcessResponse)
@handle_api_exceptions("Failed to process embeddings", 500)
async def process_pending_embeddings(
    batch_size: int = 32,
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Process pending embeddings"""
    if not startup_service.ingestion_service:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Ingestion service not available")
    
    result = await startup_service.process_pending_embeddings(batch_size)
    
    return EmbeddingProcessResponse(
        success=True,
        message=f"Processed {result['processed']} items",
        result=result
    )