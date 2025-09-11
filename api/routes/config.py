"""
Configuration API routes

Provides endpoints for accessing application configuration
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from core.dependencies import get_dependency_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("/")
async def get_config(registry = Depends(get_dependency_registry)) -> Dict[str, Any]:
    """Get application configuration settings"""
    try:
        startup_service = registry.get_startup_service()
        if not startup_service or not startup_service.config:
            raise HTTPException(status_code=503, detail="Configuration not available")
        
        config = startup_service.config
        
        # Return relevant config settings for frontend
        return {
            "news": {
                "enabled": config.news.enabled,
                "language": config.news.language,
                "country": config.news.country,
                "unique_items_per_day": config.news.unique_items_per_day
            },
            "weather": {
                "enabled": config.weather.enabled,
                "units": config.weather.units
            },
            "twitter": {
                "enabled": config.twitter.enabled
            },
            "spotify": {
                "enabled": config.spotify.enabled
            },
            "limitless": {
                "timezone": config.limitless.timezone
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")