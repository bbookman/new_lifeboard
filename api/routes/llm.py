"""
LLM API routes for content generation

This module provides REST API endpoints for LLM-powered content generation,
specifically for daily summaries and other AI-generated content.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query

from services.llm_service import LLMService, LLMGenerationResult
from services.startup import StartupService
from core.exception_handling import handle_api_exceptions
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm"])

def get_llm_service_for_route(startup_service: StartupService = Depends(get_startup_service_dependency)) -> LLMService:
    """Get the LLM service instance for route dependency injection"""
    if not startup_service.llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    return startup_service.llm_service


# Pydantic models for API requests and responses
class GenerateSummaryRequest(BaseModel):
    days_date: str = Field(..., description="Date for summary generation (YYYY-MM-DD)")
    force_regenerate: bool = Field(False, description="Force regeneration even if cached")


class GenerateSummaryResponse(BaseModel):
    success: bool
    content: str
    days_date: str
    prompt_used: str
    model_info: Dict[str, Any]
    generation_time: float
    error_message: Optional[str] = None
    cached: bool = False

    @classmethod
    def from_generation_result(cls, result: LLMGenerationResult, days_date: str, cached: bool = False) -> 'GenerateSummaryResponse':
        return cls(
            success=result.success,
            content=result.content,
            days_date=days_date,
            prompt_used=result.prompt_used,
            model_info=result.model_info,
            generation_time=result.generation_time,
            error_message=result.error_message,
            cached=cached
        )


class GetSummaryResponse(BaseModel):
    content: Optional[str]
    days_date: str
    cached: bool


# API Endpoints
@router.post("/generate-summary", response_model=GenerateSummaryResponse)
@handle_api_exceptions("Failed to generate summary", 500, include_details=True)
async def generate_daily_summary(
    request: GenerateSummaryRequest,
    llm_service: LLMService = Depends(get_llm_service_for_route)
) -> GenerateSummaryResponse:
    """Generate daily summary using selected prompt and daily data"""
    logger.info(f"Received request to generate summary for date: {request.days_date}, force_regenerate: {request.force_regenerate}")
    try:
        # Check for cached content first (unless force regenerate)
        if not request.force_regenerate:
            logger.debug(f"Checking for cached summary for date: {request.days_date}")
            cached_content = await llm_service.get_cached_summary(request.days_date)
            if cached_content:
                logger.info(f"Found cached summary for {request.days_date}. Returning cached content.")
                return GenerateSummaryResponse(
                    success=True,
                    content=cached_content,
                    days_date=request.days_date,
                    prompt_used="Cached",
                    model_info={"provider": "cache"},
                    generation_time=0.0,
                    cached=True
                )
            logger.info(f"No cached summary found for {request.days_date}.")

        logger.info(f"Proceeding with new summary generation for {request.days_date}.")
        # Generate new summary
        result = await llm_service.generate_daily_summary(
            days_date=request.days_date,
            force_regenerate=request.force_regenerate
        )
        
        logger.info(f"Successfully generated summary for {request.days_date}. Generation time: {result.generation_time:.2f}s")
        return GenerateSummaryResponse.from_generation_result(result, request.days_date)
        
    except Exception as e:
        logger.error(f"Fatal error in generate_daily_summary endpoint for date {request.days_date}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate daily summary: {e}")


@router.get("/summary/{days_date}", response_model=GetSummaryResponse)
@handle_api_exceptions("Failed to get summary", 500, include_details=True)
async def get_daily_summary(
    days_date: str,
    llm_service: LLMService = Depends(get_llm_service_for_route)
) -> GetSummaryResponse:
    """Get daily summary for a specific date (cached only)"""
    try:
        cached_content = await llm_service.get_cached_summary(days_date)
        
        return GetSummaryResponse(
            content=cached_content,
            days_date=days_date,
            cached=True
        )
        
    except Exception as e:
        logger.error(f"Error getting daily summary for {days_date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get daily summary")


@router.get("/health", response_model=Dict[str, Any])
@handle_api_exceptions("Failed to get LLM service health", 500, include_details=True)
async def get_llm_service_health(
    llm_service: LLMService = Depends(get_llm_service_for_route)
) -> Dict[str, Any]:
    """Get LLM service health status"""
    try:
        health_info = await llm_service._check_service_health()
        return health_info
        
    except Exception as e:
        logger.error(f"Error getting LLM service health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service health")