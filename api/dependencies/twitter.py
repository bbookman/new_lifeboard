"""
Twitter dependency injection utilities

Provides centralized Twitter source dependency injection for API routes.
"""

import logging
from fastapi import HTTPException

from services.twitter_api_service import TwitterAPIService
from services.twitter_rate_limit_service import TwitterRateLimitService
from sources.twitter import TwitterSource
from core.dependencies import get_dependency_registry

logger = logging.getLogger(__name__)


def get_twitter_source() -> TwitterSource:
    """Get Twitter source instance with on-demand creation"""
    registry = get_dependency_registry()
    startup_service = registry.get_startup_service()
    if not startup_service:
        logger.error("Startup service not available in dependency registry")
        raise HTTPException(status_code=503, detail="Application not properly initialized")

    if not startup_service.ingestion_service:
        logger.error("Ingestion service not available in startup service")
        raise HTTPException(status_code=503, detail="Ingestion service not available")

    # First, try to get existing Twitter source from ingestion service
    twitter_source = startup_service.ingestion_service.sources.get("twitter")
    if twitter_source and isinstance(twitter_source, TwitterSource):
        logger.info("Using existing registered Twitter source")
        return twitter_source

    # If no registered source exists, create one on-demand
    logger.info("No registered Twitter source found, creating on-demand instance")

    # Get Twitter configuration from startup service
    if not startup_service.config or not startup_service.config.twitter:
        logger.error("Twitter configuration not available")
        raise HTTPException(status_code=404, detail="Twitter source not configured")

    twitter_config = startup_service.config.twitter

    # Check if Twitter is configured at all
    if not twitter_config.is_configured():
        logger.error("Twitter source is not configured in application settings")
        raise HTTPException(status_code=404, detail="Twitter source not configured")

    try:
        # Create Twitter services
        twitter_api_service = TwitterAPIService(twitter_config) if twitter_config.is_api_configured() else None
        twitter_rate_limit_service = TwitterRateLimitService(
            startup_service.database,
            twitter_config.rate_limit_minutes
        )

        # Create TwitterSource instance
        twitter_source = TwitterSource(
            config=twitter_config,
            twitter_api_service=twitter_api_service,
            rate_limit_service=twitter_rate_limit_service
        )

        logger.info("Successfully created on-demand Twitter source")
        return twitter_source

    except Exception as e:
        logger.error(f"Failed to create on-demand Twitter source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize Twitter source")