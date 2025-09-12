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
        
        # Check LLM configuration status
        llm_configured = False
        llm_provider_name = "none"
        llm_model = "none"
        try:
            if config.llm_provider and config.llm_provider.is_active_provider_configured():
                llm_configured = True
                llm_provider_name = config.llm_provider.provider
                active_config = config.llm_provider.get_active_provider_config()
                llm_model = getattr(active_config, 'model', 'unknown')
        except Exception as e:
            logger.warning(f"Error checking LLM configuration: {e}")

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
            },
            "llm": {
                "configured": llm_configured,
                "provider": llm_provider_name,
                "model": llm_model
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")