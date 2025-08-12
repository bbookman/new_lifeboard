"""
Calendar API routes for Lifeboard

Provides calendar interface with month view navigation and day detail views.
"""

import logging
import os
import re
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
import pytz

from services.startup import StartupService
from services.weather_service import WeatherService
from services.news_service import NewsService
from core.database import DatabaseService
from core.dependencies import get_startup_service_dependency
from config.factory import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Calendar API - JSON endpoints only


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


# Calendar HTML endpoints removed - frontend now uses React
# Use /calendar/api/days-with-data for calendar data


@router.get("/api/today")
async def get_today_date(
    startup_service: StartupService = Depends(get_startup_service_dependency)
) -> Dict[str, str]:
    """Get today's date in the server's configured timezone"""
    try:
        today = get_user_timezone_aware_now(startup_service)
        today_str = today.strftime("%Y-%m-%d")
        
        logger.debug(f"[CALENDAR API] Today's date in configured timezone: {today_str}")
        
        return {
            "today": today_str,
            "timezone": os.getenv('TIME_ZONE', 'America/New_York'),
            "timestamp": today.isoformat()
        }
    except Exception as e:
        logger.error(f"[CALENDAR API] Error getting today's date: {e}")
        raise HTTPException(status_code=500, detail="Failed to get today's date")


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
        
        # Get all distinct namespaces from the database
        all_namespaces = database.get_all_namespaces()
        
        # Prepare the result dictionary with 'all' days initially
        result_data: Dict[str, List[str]] = {"all": all_days}
        
        # Fetch days with data for each namespace dynamically
        for namespace in all_namespaces:
            logger.info(f"[CALENDAR API] Calling database.get_days_with_data(namespaces=['{namespace}'])")
            namespace_days = database.get_days_with_data(namespaces=[namespace])
            result_data[namespace] = namespace_days
            logger.info(f"[CALENDAR DEBUG] {namespace} days count: {len(namespace_days) if namespace_days else 0}")
        
        logger.info(f"[CALENDAR DEBUG] Total all_days count: {len(all_days) if all_days else 0}")
        
        # Filter by year/month if specified
        if year is not None and month is not None:
            target_prefix = f"{year:04d}-{month:02d}"
            logger.info(f"[CALENDAR DEBUG] Filtering with target_prefix: {target_prefix}")
            
            filtered_result_data: Dict[str, List[str]] = {}
            for key, days_list in result_data.items():
                filtered_result_data[key] = [day for day in days_list if day.startswith(target_prefix)]
                logger.info(f"[CALENDAR DEBUG] Filtered {key}: {filtered_result_data[key]}")
            
            result = filtered_result_data
        else:
            result = result_data
        
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
                "raw_items": limitless_items,
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


# Day view HTML endpoint removed - frontend now uses React
# Use /calendar/api/day/{date} for day data



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


@router.get("/debug/markdown/{date}")
async def debug_markdown_content(
    date: str,
    namespaces: Optional[str] = "limitless",
    database: DatabaseService = Depends(get_database_service)
) -> Dict[str, Any]:
    """
    Debug endpoint to inspect raw markdown content from database for a specific date.
    Useful for troubleshooting markdown rendering issues.
    """
    try:
        logger.info(f"[MARKDOWN DEBUG API] Debugging markdown for date: {date}")
        
        # Parse namespaces parameter
        namespace_list = None
        if namespaces:
            namespace_list = [ns.strip() for ns in namespaces.split(",")]
        
        # Get raw data items
        data_items = database.get_data_items_by_date(date, namespace_list)
        
        # Get processed markdown
        markdown_content = database.get_markdown_by_date(date, namespace_list)
        
        # Analyze each item
        item_analysis = []
        for i, item in enumerate(data_items):
            metadata = item.get('metadata', {})
            
            analysis = {
                'item_index': i + 1,
                'id': item.get('id', 'unknown'),
                'namespace': item.get('namespace'),
                'source_id': item.get('source_id'),
                'content_length': len(item.get('content', '')),
                'content_preview': item.get('content', '')[:100] + '...' if item.get('content', '') else None,
                'has_metadata': bool(metadata),
                'metadata_keys': list(metadata.keys()) if isinstance(metadata, dict) else [],
                'has_cleaned_markdown': 'cleaned_markdown' in metadata if isinstance(metadata, dict) else False,
                'has_title': 'title' in metadata if isinstance(metadata, dict) else False,
                'title': metadata.get('title') if isinstance(metadata, dict) else None,
                'cleaned_markdown_preview': None,
                'cleaned_markdown_has_headers': False
            }
            
            # Analyze cleaned markdown if present
            if isinstance(metadata, dict) and 'cleaned_markdown' in metadata:
                cleaned_md = metadata['cleaned_markdown']
                analysis['cleaned_markdown_preview'] = cleaned_md[:200] + '...' if len(cleaned_md) > 200 else cleaned_md
                analysis['cleaned_markdown_length'] = len(cleaned_md)
                analysis['cleaned_markdown_has_headers'] = bool(re.search(r'^#+\s', cleaned_md, re.MULTILINE))
                
                # Count header types
                header_counts = {}
                for level in range(1, 7):
                    pattern = f"^{'#' * level} .+$"
                    matches = re.findall(pattern, cleaned_md, re.MULTILINE)
                    if matches:
                        header_counts[f'h{level}'] = len(matches)
                        analysis[f'h{level}_headers'] = matches[:3]  # First 3 headers of each type
                
                analysis['header_counts'] = header_counts
            
            item_analysis.append(analysis)
        
        # Analyze final markdown output
        final_analysis = {
            'total_length': len(markdown_content),
            'preview': markdown_content[:300] + '...' if len(markdown_content) > 300 else markdown_content,
            'has_headers': bool(re.search(r'^#+\s', markdown_content, re.MULTILINE)),
            'line_count': len(markdown_content.split('\n')),
            'contains_separators': '---' in markdown_content
        }
        
        # Count final header types
        final_header_counts = {}
        for level in range(1, 7):
            pattern = f"^{'#' * level} .+$"
            matches = re.findall(pattern, markdown_content, re.MULTILINE)
            if matches:
                final_header_counts[f'h{level}'] = len(matches)
                final_analysis[f'h{level}_headers'] = matches[:5]  # First 5 headers of each type
        
        final_analysis['header_counts'] = final_header_counts
        
        return {
            'debug_info': {
                'date': date,
                'namespaces_requested': namespace_list,
                'timestamp': datetime.now().isoformat()
            },
            'data_items': {
                'count': len(data_items),
                'analysis': item_analysis
            },
            'final_markdown': final_analysis,
            'raw_markdown_content': markdown_content  # Full content for debugging
        }
        
    except Exception as e:
        logger.error(f"Error in markdown debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Debug endpoint error: {str(e)}")


@router.get("/debug/markdown/{date}/raw")
async def debug_markdown_raw(
    date: str,
    namespaces: Optional[str] = "limitless",
    database: DatabaseService = Depends(get_database_service)
) -> Dict[str, str]:
    """
    Get raw markdown content only (for easy copying/testing)
    """
    try:
        namespace_list = None
        if namespaces:
            namespace_list = [ns.strip() for ns in namespaces.split(",")]
        
        markdown_content = database.get_markdown_by_date(date, namespace_list)
        
        return {
            'date': date,
            'namespaces': namespaces,
            'markdown': markdown_content
        }
        
    except Exception as e:
        logger.error(f"Error in raw markdown debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Debug endpoint error: {str(e)}")


@router.get("/api/data_items/{date}")
async def get_data_items_for_date(
    date: str, 
    namespaces: Optional[str] = None,
    database: DatabaseService = Depends(get_database_service)
) -> List[Dict[str, Any]]:
    """Get all data_items for a specific date, optionally filtered by namespaces"""
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Parse namespaces parameter if provided
        namespace_list = None
        if namespaces:
            namespace_list = [ns.strip() for ns in namespaces.split(",")]
        
        # Get data items for the date
        logger.info(f"[DATA_ITEMS API] Requesting data items for date {date} with namespaces {namespace_list}")
        data_items = database.get_data_items_by_date(date, namespace_list)
        
        logger.info(f"[DATA_ITEMS API] Retrieved {len(data_items)} data items for date {date}")
        
        # Log first item details for debugging
        if data_items:
            first_item = data_items[0]
            logger.info(f"[DATA_ITEMS API] First item: id={first_item.get('id')}, namespace={first_item.get('namespace')}, has_content={bool(first_item.get('content'))}, has_metadata={bool(first_item.get('metadata'))}")
            
            metadata = first_item.get('metadata', {})
            if isinstance(metadata, dict):
                logger.info(f"[DATA_ITEMS API] First item metadata keys: {list(metadata.keys())}")
                if 'cleaned_markdown' in metadata:
                    cleaned_md = metadata['cleaned_markdown']
                    logger.info(f"[DATA_ITEMS API] First item cleaned_markdown length: {len(cleaned_md)}")
                    logger.info(f"[DATA_ITEMS API] First item cleaned_markdown preview: {cleaned_md[:200]}...")
        else:
            logger.warning(f"[DATA_ITEMS API] No data items found for date {date} with namespaces {namespace_list}")
        
        return data_items
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting data items for {date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get data items")