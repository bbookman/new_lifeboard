"""
System management endpoints

This module contains endpoints for system initialization,
shutdown, and management operations.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from config.factory import create_production_config
from core.exception_handling import handle_api_exceptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


class SystemResponse(BaseModel):
    """Response model for system operations"""
    success: bool
    message: str
    result: Dict[str, Any] = None


@router.post("/startup", response_model=SystemResponse)
@handle_api_exceptions("System initialization failed", 500)
async def initialize_system():
    """Initialize the application system"""
    from services.startup import initialize_application
    
    config = create_production_config()
    result = await initialize_application(config, enable_auto_sync=True)
    
    return SystemResponse(
        success=result["success"],
        message="System initialization completed" if result["success"] else "System initialization failed",
        result=result
    )


@router.post("/shutdown", response_model=SystemResponse)
@handle_api_exceptions("System shutdown failed", 500)
async def shutdown_system():
    """Shutdown the application system gracefully"""
    from services.startup import shutdown_application
    
    await shutdown_application()
    
    return SystemResponse(
        success=True,
        message="System shutdown completed"
    )