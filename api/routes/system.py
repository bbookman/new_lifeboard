"""
System management endpoints

This module contains endpoints for system initialization,
shutdown, and management operations.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List

from config.factory import create_production_config
from core.exception_handling import handle_api_exceptions
from services.startup import StartupService, initialize_application, shutdown_application
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


class SystemResponse(BaseModel):
    """Response model for system operations"""
    success: bool
    message: str
    result: Dict[str, Any] = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 20

class SearchResult(BaseModel):
    id: str
    content: str
    score: float
    source: str
    date: str

@router.post("/search")
async def search_data(
    request: SearchRequest,
    startup_service: StartupService = Depends(get_startup_service_dependency)
) -> List[SearchResult]:
    """Search through data using embeddings"""
    from fastapi import HTTPException
    
    try:
        chat_service = startup_service.chat_service
        if not chat_service:
            raise HTTPException(status_code=503, detail="Chat service not available")
        
        # Use the chat service's search functionality
        results = await chat_service.search_data(request.query, limit=request.limit)
        
        # Convert results to SearchResult format
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                id=result.get('id', ''),
                content=result.get('content', ''),
                score=result.get('score', 0.0),
                source=result.get('namespace', ''),
                date=result.get('days_date', '')
            ))
        
        return search_results
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is (preserve status codes)
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/startup", response_model=SystemResponse)
@handle_api_exceptions("System initialization failed", 500)
async def initialize_system():
    """Initialize the application system"""
    config = create_production_config()
    result = await initialize_application(config)
    
    return SystemResponse(
        success=result["success"],
        message="System initialization completed" if result["success"] else "System initialization failed",
        result=result
    )


@router.post("/shutdown", response_model=SystemResponse)
@handle_api_exceptions("System shutdown failed", 500)
async def shutdown_system():
    """Shutdown the application system gracefully"""
    await shutdown_application()
    
    return SystemResponse(
        success=True,
        message="System shutdown completed"
    )