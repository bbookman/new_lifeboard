"""
Sources API routes

Provides endpoints for data source management and status
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from core.dependencies import get_dependency_registry
from services.sync_manager_service import SyncManagerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])

@router.get("/twitter/status")
async def get_twitter_status_for_day(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    registry = Depends(get_dependency_registry)
) -> Optional[Dict[str, Any]]:
    """Get Twitter fetch status for a specific day"""
    try:
        sync_manager: SyncManagerService = registry.get('sync_manager_service')
        
        # Get the Twitter source from the sync manager
        twitter_source = None
        for source in sync_manager.sources:
            if hasattr(source, 'namespace') and source.namespace == 'twitter':
                twitter_source = source
                break
        
        if not twitter_source:
            logger.warning("[TwitterStatus] Twitter source not found")
            return None
        
        # Get status for the requested day
        if hasattr(twitter_source, 'get_status_for_day'):
            status = await twitter_source.get_status_for_day(date)
            logger.info(f"[TwitterStatus] Retrieved status for {date}: {status}")
            return status
        else:
            logger.warning("[TwitterStatus] Twitter source does not support status queries")
            return None
            
    except Exception as e:
        logger.error(f"[TwitterStatus] Error getting status for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving Twitter status: {str(e)}")

@router.post("/twitter/manual-fetch")
async def manual_twitter_fetch(
    registry = Depends(get_dependency_registry)
) -> Dict[str, Any]:
    """Manually trigger a Twitter data fetch (respects rate limits)"""
    try:
        sync_manager: SyncManagerService = registry.get('sync_manager_service')
        
        # Get the Twitter source from the sync manager
        twitter_source = None
        for source in sync_manager.sources:
            if hasattr(source, 'namespace') and source.namespace == 'twitter':
                twitter_source = source
                break
        
        if not twitter_source:
            logger.warning("[TwitterStatus] Twitter source not found")
            raise HTTPException(status_code=404, detail="Twitter source not configured")
        
        # Check if we can fetch now
        if hasattr(twitter_source, 'rate_limit_service'):
            can_fetch, minutes_until = await twitter_source.rate_limit_service.can_fetch_now()
            if not can_fetch:
                return {
                    "success": False,
                    "message": f"Rate limited. Try again in {minutes_until} minutes.",
                    "minutes_until_next": minutes_until
                }
        
        # Trigger a manual fetch
        if hasattr(twitter_source, 'fetch_today_tweets'):
            tweets = await twitter_source.fetch_today_tweets()
            return {
                "success": True,
                "message": f"Successfully fetched {len(tweets)} tweets",
                "tweets_count": len(tweets)
            }
        else:
            raise HTTPException(status_code=500, detail="Twitter source does not support manual fetching")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TwitterStatus] Error during manual fetch: {e}")
        raise HTTPException(status_code=500, detail=f"Error during manual fetch: {str(e)}")