"""
News API routes for retrieving news data by date.
"""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_database_service
from core.database import DatabaseService
from services.news_service import NewsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


def get_news_service(database: DatabaseService = Depends(get_database_service)) -> NewsService:
    """Dependency injection for NewsService."""
    return NewsService(database)


@router.get("", response_model=List[Dict[str, Any]])
async def get_news(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    news_service: NewsService = Depends(get_news_service)
):
    """Get news articles for a specific date."""
    try:
        logger.info(f"Getting news for date: {date}")
        news_items = news_service.get_news_by_date(date)
        return news_items
    except Exception as e:
        logger.error(f"Error fetching news for date {date}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest", response_model=List[Dict[str, Any]])
async def get_latest_news(
    limit: int = Query(10, ge=1, le=50, description="Number of latest articles to retrieve"),
    news_service: NewsService = Depends(get_news_service)
):
    """Get the most recent news articles."""
    try:
        logger.info(f"Getting latest {limit} news articles")
        news_items = news_service.get_latest_news(limit)
        return news_items
    except Exception as e:
        logger.error(f"Error fetching latest news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count", response_model=Dict[str, int])
async def get_news_count(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    news_service: NewsService = Depends(get_news_service)
):
    """Get count of news articles for a specific date."""
    try:
        logger.info(f"Getting news count for date: {date}")
        count = news_service.get_news_count_by_date(date)
        return {"count": count}
    except Exception as e:
        logger.error(f"Error getting news count for date {date}: {e}")
        raise HTTPException(status_code=500, detail=str(e))