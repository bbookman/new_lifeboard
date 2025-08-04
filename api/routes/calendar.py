"""
Calendar API routes for Lifeboard

Provides calendar interface with month view navigation and day detail views.
"""

import logging
import os
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pytz

from services.startup import StartupService
from services.weather_service import WeatherService
from services.news_service import NewsService
from core.database import DatabaseService
from core.dependencies import get_startup_service_dependency
from config.factory import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Templates will be set by the main server
templates = None


def set_templates(template_instance):
    """Set the templates instance (called from main server)"""
    global templates
    templates = template_instance


def get_database_service(startup_service: StartupService = Depends(get_startup_service_dependency)) -> DatabaseService:
    """Get database service from startup service"""
    if not startup_service.database:
        raise HTTPException(status_code=503, detail="Database service not available")
    return startup_service.database


def get_weather_service(database: DatabaseService = Depends(get_database_service)) -> WeatherService:
    """Get weather service instance"""
    config = get_config()
    return WeatherService(database, config)


def get_news_service(database: DatabaseService = Depends(get_database_service)) -> NewsService:
    """Get news service instance"""
    config = get_config()
    return NewsService(database, config.news)


def get_user_timezone_aware_now(startup_service: StartupService) -> datetime:
    """Get current datetime in user's configured timezone"""
    try:
        # Get user timezone from environment variable first, then config, then default
        user_timezone = os.getenv('TIME_ZONE', 'America/New_York')
        
        # Also try config as fallback if env var not available
        if not user_timezone or user_timezone == 'America/New_York':
            if hasattr(startup_service, 'config') and startup_service.config:
                user_timezone = getattr(startup_service.config.limitless, 'timezone', user_timezone)
        
        # Convert UTC time to user timezone
        utc_now = datetime.now(timezone.utc)
        user_tz = pytz.timezone(user_timezone)
        user_now = utc_now.astimezone(user_tz)
        
        logger.debug(f"Current time: UTC={utc_now.isoformat()}, User({user_timezone})={user_now.isoformat()}")
        return user_now
        
    except Exception as e:
        logger.warning(f"Error getting timezone-aware time: {e}. Falling back to UTC.")
        # Fallback to UTC if timezone conversion fails
        return datetime.now(timezone.utc)


@router.get("/", response_class=HTMLResponse)
async def calendar_month_view(
    request: Request,
    database: DatabaseService = Depends(get_database_service),
    startup_service: StartupService = Depends(lambda: get_startup_service_dependency())
):
    """Serve the calendar month view HTML template"""
    try:
        # Get current date in user's timezone for default view
        current_date = get_user_timezone_aware_now(startup_service)
        current_month = current_date.strftime("%Y-%m")
        
        # Get days with data for initial load
        days_with_data = database.get_days_with_data()
        days_with_twitter_data = database.get_days_with_data(namespaces=['twitter'])
        
        logger.info(f"Calendar displaying current date: {current_date.strftime('%Y-%m-%d')} "
                   f"({current_date.strftime('%A, %B %d, %Y')})")
        
        return templates.TemplateResponse("calendar.html", {
            "request": request,
            "current_month": current_month,
            "current_year": current_date.year,
            "current_month_name": current_date.strftime("%B"),
            "current_date": current_date.strftime("%Y-%m-%d"),
            "days_with_data": days_with_data,
            "days_with_twitter_data": days_with_twitter_data
        })
    except Exception as e:
        logger.error(f"Error serving calendar template: {e}")
        raise HTTPException(status_code=500, detail="Failed to load calendar")


@router.get("/api/days-with-data")
async def get_days_with_data(
    year: Optional[int] = None,
    month: Optional[int] = None,
    database: DatabaseService = Depends(get_database_service)
) -> Dict[str, List[str]]:
    """Get list of dates that have data available"""
    logger.info(f"[CALENDAR API] Request received - year: {year}, month: {month}")
    
    try:
        # Get all days with data
        logger.info("[CALENDAR API] Calling database.get_days_with_data()")
        all_days = database.get_days_with_data()
        logger.info("[CALENDAR API] Calling database.get_days_with_data(namespaces=['twitter'])")
        twitter_days = database.get_days_with_data(namespaces=['twitter'])
        
        logger.info(f"[CALENDAR DEBUG] Raw all_days from database: {all_days[:10] if all_days else 'Empty'}")
        logger.info(f"[CALENDAR DEBUG] Total all_days count: {len(all_days) if all_days else 0}")
        logger.info(f"[CALENDAR DEBUG] Twitter days count: {len(twitter_days) if twitter_days else 0}")
        
        # Filter by year/month if specified
        if year is not None and month is not None:
            target_prefix = f"{year:04d}-{month:02d}"
            logger.info(f"[CALENDAR DEBUG] Filtering with target_prefix: {target_prefix}")
            filtered_days = [day for day in all_days if day.startswith(target_prefix)]
            filtered_twitter_days = [day for day in twitter_days if day.startswith(target_prefix)]
            logger.info(f"[CALENDAR DEBUG] Filtered all_days: {filtered_days}")
            logger.info(f"[CALENDAR DEBUG] Filtered twitter_days: {filtered_twitter_days}")
            result = {"all": filtered_days, "twitter": filtered_twitter_days}
        else:
            result = {"all": all_days, "twitter": twitter_days}
        
        logger.info(f"[CALENDAR API] Returning response: {result}")
        return result
        
    except Exception as e:
        logger.error(f"[CALENDAR API] Error getting days with data: {e}")
        logger.error(f"[CALENDAR DEBUG] Exception details: {str(e)}")
        logger.exception("[CALENDAR API] Full exception traceback:")
        raise HTTPException(status_code=500, detail="Failed to get calendar data")


@router.get("/api/day/{date}")
async def get_day_details(date: str, database: DatabaseService = Depends(get_database_service)) -> Dict[str, Any]:
    """Get details and markdown content for a specific date"""
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Get limitless data items from unified table
        limitless_items = database.get_data_items_by_date(date, namespaces=['limitless'])
        
        # Get markdown content from limitless items
        markdown_content = database.get_markdown_by_date(date, namespaces=['limitless'])
        
        return {
            "date": date,
            "formatted_date": parsed_date.strftime("%B %d, %Y"),
            "day_of_week": parsed_date.strftime("%A"),
            "markdown_content": markdown_content,
            "item_count": len(limitless_items),
            "has_data": len(limitless_items) > 0  # Correctly base has_data on filtered items
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting day details for {date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get day details")


@router.get("/api/day/{date}/enhanced")
async def get_enhanced_day_data(
    date: str, 
    database: DatabaseService = Depends(get_database_service),
    weather_service: WeatherService = Depends(get_weather_service),
    news_service: NewsService = Depends(get_news_service)
) -> Dict[str, Any]:
    """Get enhanced day data including weather, news, and limitless content"""
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Get basic day details
        markdown_content = database.get_markdown_by_date(date, namespaces=['limitless'])
        limitless_items = database.get_data_items_by_date(date, namespaces=['limitless'])
        
        # Get 5-day weather forecast starting from this date
        weather_data = weather_service.get_weather_for_date_range(date, 5)
        
        # Get news data for the date
        news_data = news_service.get_news_by_date(date)
        
        # If no news for specific date, get recent news as fallback
        if not news_data:
            news_data = news_service.get_latest_news(limit=5)
        
        return {
            "date": date,
            "formatted_date": parsed_date.strftime("%B %d, %Y"),
            "day_of_week": parsed_date.strftime("%A"),
            "weather": {
                "forecast_days": weather_data,
                "has_data": len(weather_data) > 0
            },
            "news": {
                "articles": news_data,
                "count": len(news_data),
                "has_data": len(news_data) > 0
            },
            "limitless": {
                "markdown_content": markdown_content,
                "item_count": len(limitless_items),
                "has_data": len(limitless_items) > 0 or bool(markdown_content)
            },
            "summary": {
                "total_items": len(limitless_items),
                "has_any_data": len(limitless_items) > 0 or len(weather_data) > 0 or len(news_data) > 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced day data for {date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get enhanced day data")


@router.get("/day/{date}", response_class=HTMLResponse)
async def day_view(
    request: Request, 
    date: str, 
    database: DatabaseService = Depends(get_database_service)
):
    """Serve the day view HTML template"""
    try:
        # Get day details
        day_details = await get_day_details(date, database)
        
        return templates.TemplateResponse("day_view.html", {
            "request": request,
            **day_details
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving day view for {date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load day view")



@router.get("/api/month/{year}/{month}")
async def get_month_data(
    year: int, 
    month: int, 
    database: DatabaseService = Depends(get_database_service)
) -> Dict[str, Any]:
    """Get calendar data for a specific month"""
    try:
        # Validate month/year
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="Invalid month. Must be 1-12")
        if year < 1900 or year > 2100:
            raise HTTPException(status_code=400, detail="Invalid year. Must be 1900-2100")
        
        # Get days with data for this month
        days_with_data = await get_days_with_data(year, month, database)
        
        # Create month info
        month_date = datetime(year, month, 1)
        
        return {
            "year": year,
            "month": month,
            "month_name": month_date.strftime("%B"),
            "days_with_data": days_with_data,
            "total_days_with_data": len(days_with_data)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting month data for {year}-{month}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get month data")