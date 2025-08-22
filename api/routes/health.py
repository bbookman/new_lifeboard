"""
Health and status endpoints

This module contains endpoints for application health monitoring
and status checking.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.dependencies import get_startup_service_dependency
from core.exception_handling import handle_api_exceptions
from services.startup import StartupService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["health"])


class HealthResponse(BaseModel):
    """Response model for health checks"""
    healthy: bool
    services: Dict[str, bool]
    details: Dict[str, Any] = None


class StatusResponse(BaseModel):
    """Response model for status endpoints"""
    timestamp: str
    data: Dict[str, Any]


# Dependency function is imported from core.dependencies


@router.get("/health", response_model=HealthResponse)
@handle_api_exceptions("Health check failed", 503)
async def health_check(startup_service: StartupService = Depends(get_startup_service_dependency)):
    """Get application health status"""
    app_status = startup_service.get_application_status()

    return HealthResponse(
        healthy=app_status.get("startup_complete", False),
        services=app_status.get("services", {}),
        details=app_status,
    )


@router.get("/status", response_model=StatusResponse)
@handle_api_exceptions("Status check failed", 500)
async def get_application_status(startup_service: StartupService = Depends(get_startup_service_dependency)):
    """Get detailed application status"""
    status_data = startup_service.get_application_status()

    return StatusResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=status_data,
    )
