"""
Calendar API routes for Lifeboard

Provides calendar interface with month view navigation and day detail views.
"""

import logging
import os
import re
import json
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
import pytz

from services.startup import StartupService
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.ingestion import IngestionService
from services.sync_status_service import get_sync_status_service, SyncStatusService
from core.database import DatabaseService
from core.dependencies import get_startup_service_dependency, get_database_service_dependency
from config.factory import get_config
from sources.limitless import LimitlessSource
from sources.twitter import TwitterSource
from services.twitter_api_service import TwitterRateLimitError
from core.dependencies import get_dependency_registry
from api.dependencies.twitter import get_twitter_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# Calendar API - JSON endpoints only


# Removed: using centralized dependency function from core.dependencies


def get_weather_service(database: DatabaseService = Depends(get_database_service_dependency)) -> WeatherService:
    """Get weather service instance"""
    config = get_config()
    return WeatherService(database, config)


def get_news_service(database: DatabaseService = Depends(get_database_service_dependency)) -> NewsService:
    """Get news service instance"""
    config = get_config()
    return NewsService(database, config.news)


def get_ingestion_service(startup_service: StartupService = Depends(get_startup_service_dependency)) -> IngestionService:
    """Get ingestion service from startup service (fixed dependency injection)"""
    if not startup_service.ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not available")
    return startup_service.ingestion_service


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


@router.get("/today")
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


@router.get("/days-with-data")
async def get_days_with_data(
    year: Optional[int] = None,
    month: Optional[int] = None,
    database: DatabaseService = Depends(get_database_service_dependency)
) -> Dict[str, Any]:
    """Get list of dates that have data available"""
    logger.info(f"[CALENDAR API] Request received - year: {year}, month: {month}")
    
    try:
        # Get all days with data
        logger.info("[CALENDAR API] Calling database.async_get_days_with_data()")
        all_days = await database.async_get_days_with_data()
        
        # Get all distinct namespaces from the database
        all_namespaces = await database.async_get_all_namespaces()
        
        # Prepare the result dictionary with 'all' days initially
        result_data: Dict[str, List[str]] = {"all": all_days}
        
        # Fetch days with data for each namespace dynamically
        for namespace in all_namespaces:
            logger.info(f"[CALENDAR API] Calling database.async_get_days_with_data(namespaces=['{namespace}'])")
            namespace_days = await database.async_get_days_with_data(namespaces=[namespace])
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
        
        # Get sync status if available
        sync_status = None
        try:
            sync_service = get_sync_status_service()
            if sync_service:
                sync_status = sync_service.get_overall_status()
        except Exception as e:
            logger.warning(f"[CALENDAR API] Could not get sync status: {e}")
        
        # Combine data with sync status
        response = {
            "data": result,
            "sync_status": sync_status
        }
        
        logger.info(f"[CALENDAR API] Returning response with sync status: data={len(result)} namespaces, sync_complete={sync_status['is_complete'] if sync_status else 'unknown'}")
        return response
        
    except Exception as e:
        logger.error(f"[CALENDAR API] Error getting days with data: {e}")
        logger.error(f"[CALENDAR DEBUG] Exception details: {str(e)}")
        logger.exception("[CALENDAR API] Full exception traceback:")
        raise HTTPException(status_code=500, detail="Failed to get calendar data")


@router.get("/day/{date}")
async def get_day_details(date: str, database: DatabaseService = Depends(get_database_service_dependency)) -> Dict[str, Any]:
    """Get details and markdown content for a specific date"""
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Get limitless data items from unified table
        limitless_items = await database.async_get_data_items_by_date(date, namespaces=['limitless'])
        
        # Get markdown content from limitless items - Note: keeping sync method as no async version exists
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


@router.get("/day/{date}/enhanced")
async def get_enhanced_day_data(
    date: str, 
    database: DatabaseService = Depends(get_database_service_dependency),
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
        limitless_items = await database.async_get_data_items_by_date(date, namespaces=['limitless'])
        
        # Get 5-day weather forecast starting from this date
        weather_data = weather_service.get_weather_for_date_range(date, 5)
        
        # Get news data for the date (no fallback - show empty if no news for this date)
        news_data = news_service.get_news_by_date(date)
        
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



@router.get("/month/{year}/{month}")
async def get_month_data(
    year: int, 
    month: int, 
    database: DatabaseService = Depends(get_database_service_dependency)
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
    database: DatabaseService = Depends(get_database_service_dependency)
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
        data_items = await database.async_get_data_items_by_date(date, namespace_list)
        
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
    database: DatabaseService = Depends(get_database_service_dependency)
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


@router.post("/limitless/fetch/{date}")
async def fetch_limitless_for_date(
    date: str,
    database: DatabaseService = Depends(get_database_service_dependency),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> Dict[str, Any]:
    """
    Fetch Limitless data for a specific date on-demand.
    This endpoint automatically fetches data from the Limitless API for the specified date,
    processes it through the existing pipeline, and stores it in the database.
    """
    try:
        logger.info(f"[OnDemandFetch] Starting on-demand fetch for date: {date}")
        
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            logger.debug(f"[OnDemandFetch] Parsed date: {parsed_date}")
        except ValueError:
            logger.error(f"[OnDemandFetch] Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if data already exists (optional optimization)
        existing_items = await database.async_get_data_items_by_date(date, namespaces=['limitless'])
        if existing_items:
            logger.info(f"[OnDemandFetch] Data already exists for {date}: {len(existing_items)} items")
            return {
                "success": True,
                "message": f"Data already exists for {date}",
                "items_processed": 0,
                "items_existing": len(existing_items),
                "date": date
            }
        
        logger.debug(f"[OnDemandFetch] No existing data found for {date}, proceeding with fetch")
        
        # Get configuration and create Limitless source
        config = get_config()
        if not config.limitless.is_api_key_configured():
            logger.error("[OnDemandFetch] Limitless API key not configured")
            raise HTTPException(status_code=503, detail="Limitless API key not configured")
        
        logger.debug(f"[OnDemandFetch] Creating LimitlessSource with config")
        limitless_source = LimitlessSource(config.limitless)
        
        # Test API connectivity first
        logger.debug(f"[OnDemandFetch] Testing Limitless API connectivity")
        connection_ok = await limitless_source.test_connection()
        if not connection_ok:
            logger.error("[OnDemandFetch] Failed to connect to Limitless API")
            raise HTTPException(status_code=503, detail="Failed to connect to Limitless API")
        
        logger.info(f"[OnDemandFetch] Successfully connected to Limitless API")
        
        # Calculate date range for fetching (fetch for the entire day in user's timezone)
        user_timezone = config.limitless.timezone
        logger.debug(f"[OnDemandFetch] User timezone: {user_timezone}")
        
        try:
            tz = pytz.timezone(user_timezone)
            # Start of day in user timezone
            start_of_day = tz.localize(datetime.combine(parsed_date, datetime.min.time()))
            # End of day in user timezone  
            end_of_day = tz.localize(datetime.combine(parsed_date, datetime.max.time()))
            
            # Convert to UTC for API call
            start_utc = start_of_day.astimezone(pytz.UTC)
            end_utc = end_of_day.astimezone(pytz.UTC)
            
            logger.debug(f"[OnDemandFetch] Date range: {start_utc} to {end_utc}")
            
        except Exception as e:
            logger.error(f"[OnDemandFetch] Error calculating date range: {e}")
            raise HTTPException(status_code=500, detail="Error calculating date range")
        
        # Fetch data from Limitless API for the specific date
        logger.info(f"[OnDemandFetch] Fetching data from Limitless API for date: {date}")
        items_fetched = []
        
        try:
            # Use the date-specific fetch method instead of since parameter
            async for item in limitless_source.fetch_items_for_date(date, limit=1000):
                items_fetched.append(item)
                logger.debug(f"[OnDemandFetch] Item {item.source_id} fetched for date {date}")
            
            logger.info(f"[OnDemandFetch] Fetched {len(items_fetched)} items for {date}")
            
        except Exception as e:
            logger.error(f"[OnDemandFetch] Error fetching data from Limitless API: {e}")
            raise HTTPException(status_code=503, detail=f"Error fetching data from Limitless API: {str(e)}")
        
        if not items_fetched:
            logger.info(f"[OnDemandFetch] No data found for {date}")
            return {
                "success": True,
                "message": f"No data found for {date}",
                "items_processed": 0,
                "items_existing": 0,
                "date": date
            }
        
        # Register the source with ingestion service if not already registered
        if 'limitless' not in ingestion_service.sources:
            logger.debug(f"[OnDemandFetch] Registering Limitless source with ingestion service")
            ingestion_service.register_source(limitless_source)
        
        # Process items through existing pipeline using proper ingestion service methods
        logger.info(f"[OnDemandFetch] Processing {len(items_fetched)} items through ingestion pipeline")
        
        # Import IngestionResult for proper result tracking
        from services.ingestion import IngestionResult
        result = IngestionResult()
        result.start_time = datetime.now(timezone.utc)
        
        try:
            # Process each item using the ingestion service's standard processing method
            for item in items_fetched:
                logger.debug(f"[OnDemandFetch] Processing item: {item.source_id}")
                await ingestion_service._process_and_store_item(item, result)
                result.items_processed += 1  # Manually track processed count
                logger.debug(f"[OnDemandFetch] Successfully processed item: {item.source_id}")
            
            result.end_time = datetime.now(timezone.utc)
            processed_count = result.items_processed
            stored_count = result.items_stored 
            errors = result.errors
            
            logger.info(f"[OnDemandFetch] Processing completed: {processed_count} processed, {stored_count} stored, {len(errors)} errors")
            
        except Exception as e:
            logger.error(f"[OnDemandFetch] Critical error during processing: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")
        
        # Process embeddings for the newly stored items
        logger.info(f"[OnDemandFetch] Processing embeddings for newly stored items")
        try:
            embedding_result = await ingestion_service.process_pending_embeddings(batch_size=32)
            logger.debug(f"[OnDemandFetch] Embedding processing result: {embedding_result}")
        except Exception as e:
            logger.warning(f"[OnDemandFetch] Error processing embeddings (non-critical): {e}")
        
        # Verify final result
        final_items = await database.async_get_data_items_by_date(date, namespaces=['limitless'])
        
        logger.info(f"[OnDemandFetch] On-demand fetch completed for {date}: processed={processed_count}, stored={stored_count}, final_count={len(final_items)}")
        
        return {
            "success": True,
            "message": f"Successfully fetched and processed data for {date}",
            "items_processed": processed_count,
            "items_stored": stored_count,
            "items_final": len(final_items),
            "errors": errors,
            "date": date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OnDemandFetch] Critical error in fetch endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")




@router.get("/twitter/status/{date}")
async def get_twitter_rate_limit_status(
    date: str,
    twitter_source: TwitterSource = Depends(get_twitter_source)
) -> Dict[str, Any]:
    """
    Check Twitter API rate limit status for a specific date.
    
    Returns:
        Dict containing:
        - can_fetch_now: boolean indicating if fetch is currently allowed
        - minutes_until_next: minutes until next fetch is allowed (0 if can_fetch_now is true)
        - last_fetch_time: ISO format string of last successful fetch or null
    """
    try:
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check rate limit status using the TwitterRateLimitService
        can_fetch, minutes_until = await twitter_source.rate_limit_service.can_fetch_now()
        
        # Get last fetch time
        last_fetch_time = await twitter_source.rate_limit_service.get_last_fetch_time()
        last_fetch_time_str = last_fetch_time.isoformat() if last_fetch_time else None
        
        return {
            "can_fetch_now": can_fetch,
            "minutes_until_next": minutes_until,
            "last_fetch_time": last_fetch_time_str
        }
        
    except Exception as e:
        logger.error(f"Error checking Twitter rate limit status for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/twitter/fetch/{date}")
async def fetch_twitter_for_date(
    date: str,
    database: DatabaseService = Depends(get_database_service_dependency),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    twitter_source: TwitterSource = Depends(get_twitter_source)
) -> Dict[str, Any]:
    """
    Fetch Twitter data for a specific date on-demand.
    This endpoint automatically fetches data from the Twitter API for the specified date,
    processes it through the existing pipeline, and stores it in the database.
    """
    try:
        logger.info(f"[TwitterOnDemandFetch] Starting on-demand fetch for date: {date}")
        
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            logger.debug(f"[TwitterOnDemandFetch] Parsed date: {parsed_date}")
        except ValueError:
            logger.error(f"[TwitterOnDemandFetch] Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if data already exists (short-circuit before rate limit check)
        existing_items = await database.async_get_data_items_by_date(date, namespaces=['twitter'])
        if existing_items:
            logger.info(f"[TwitterOnDemandFetch] Data already exists for {date}: {len(existing_items)} items")
            return {
                "success": True,
                "message": f"Data already exists for {date}",
                "items_processed": 0,
                "items_existing": len(existing_items),
                "date": date
            }
        
        # Check rate limit before attempting fetch
        can_fetch, minutes_until = await twitter_source.rate_limit_service.can_fetch_now()
        if not can_fetch:
            logger.warning(f"[TwitterOnDemandFetch] Rate limited for {date}, {minutes_until} minutes remaining")
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limited. Please wait {minutes_until} minutes before next fetch.",
                headers={"Retry-After": str(minutes_until * 60)}
            )
        
        logger.info(f"[TwitterOnDemandFetch] Rate limit check passed for {date}")
        
        logger.debug(f"[TwitterOnDemandFetch] No existing data found for {date}, proceeding with fetch")
        
        # Check if Twitter API is configured
        config = get_config()
        if not config.twitter.is_api_configured():
            logger.error("[TwitterOnDemandFetch] Twitter API not configured")
            raise HTTPException(status_code=503, detail="Twitter API not configured")
        
        # Fetch tweets for today (Twitter API typically only returns recent tweets)
        logger.info(f"[TwitterOnDemandFetch] Fetching tweets from Twitter API")
        try:
            tweets = await twitter_source.fetch_today_tweets()
        except TwitterRateLimitError as e:
            logger.warning(f"[TwitterOnDemandFetch] Rate limit error during fetch: {e}")
            raise HTTPException(
                status_code=429, 
                detail=str(e), 
                headers={"Retry-After": str(getattr(e, "retry_after", 900))}
            )
        
        if not tweets:
            logger.info(f"[TwitterOnDemandFetch] No tweets found for {date}")
            return {
                "success": True,
                "message": f"No tweets found for {date}",
                "items_processed": 0,
                "items_existing": 0,
                "date": date
            }
        
        logger.info(f"[TwitterOnDemandFetch] Fetched {len(tweets)} tweets from Twitter API")
        
        # Filter tweets that match the target date
        target_tweets = []
        for tweet in tweets:
            tweet_date = tweet.get('days_date')
            if tweet_date == date:
                target_tweets.append(tweet)
                logger.debug(f"[TwitterOnDemandFetch] Tweet {tweet['tweet_id']} matches date {date}")
        
        if not target_tweets:
            logger.info(f"[TwitterOnDemandFetch] No tweets found matching date {date}")
            return {
                "success": True,
                "message": f"No tweets found matching date {date}",
                "items_processed": 0,
                "items_existing": 0,
                "date": date
            }
        
        logger.info(f"[TwitterOnDemandFetch] Found {len(target_tweets)} tweets matching date {date}")
        
        # Process tweets through the existing ingestion pipeline
        logger.info(f"[TwitterOnDemandFetch] Processing {len(target_tweets)} tweets through ingestion pipeline")
        
        # Import IngestionResult for proper result tracking
        from services.ingestion import IngestionResult
        result = IngestionResult()
        result.start_time = datetime.now(timezone.utc)
        
        try:
            # Get existing tweet IDs to avoid duplicates
            existing_tweet_ids = await twitter_source._get_existing_tweet_ids()
            
            # Convert tweets to DataItems for batch processing
            data_items = []
            for tweet in target_tweets:
                if tweet['tweet_id'] in existing_tweet_ids:
                    logger.debug(f"[TwitterOnDemandFetch] Tweet {tweet['tweet_id']} already exists, skipping")
                    continue
                
                try:
                    # Parse timestamp
                    created_at = datetime.fromisoformat(tweet['created_at']) if tweet.get('created_at') else None
                    
                    # Create DataItem
                    from sources.base import DataItem
                    data_item = DataItem(
                        namespace=twitter_source.namespace,
                        source_id=tweet['tweet_id'],
                        content=tweet['text'] or "",
                        metadata={
                            'media_urls': tweet.get('media_urls', '[]'),
                            'original_created_at': tweet.get('created_at'),
                            'days_date': tweet.get('days_date'),
                            'source_type': 'twitter_api'
                        },
                        created_at=created_at,
                        updated_at=datetime.now()
                    )
                    
                    # Process through the processor
                    processed_item = twitter_source.processor.process(data_item)
                    data_items.append(processed_item)
                    
                except Exception as e:
                    logger.error(f"[TwitterOnDemandFetch] Error creating DataItem for tweet {tweet.get('tweet_id', 'unknown')}: {e}")
                    result.errors.append(f"Error creating DataItem for tweet {tweet.get('tweet_id', 'unknown')}: {str(e)}")
            
            # Use public ingestion method for batch processing
            if data_items:
                logger.info(f"[TwitterOnDemandFetch] Processing {len(data_items)} items through ingestion service")
                result = await ingestion_service.ingest_items("twitter", data_items)
                
            processed_count = result.items_processed
            stored_count = result.items_stored 
            errors = result.errors
            
            logger.info(f"[TwitterOnDemandFetch] Processing completed: {processed_count} processed, {stored_count} stored, {len(errors)} errors")
            
        except Exception as e:
            logger.error(f"[TwitterOnDemandFetch] Critical error during processing: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")
        
        # Process embeddings for the newly stored items
        logger.info(f"[TwitterOnDemandFetch] Processing embeddings for newly stored items")
        try:
            embedding_result = await ingestion_service.process_pending_embeddings(batch_size=32)
            logger.debug(f"[TwitterOnDemandFetch] Embedding processing result: {embedding_result}")
        except Exception as e:
            logger.warning(f"[TwitterOnDemandFetch] Error processing embeddings (non-critical): {e}")
        
        # Verify final result
        final_items = await database.async_get_data_items_by_date(date, namespaces=['twitter'])
        
        logger.info(f"[TwitterOnDemandFetch] On-demand fetch completed for {date}: processed={processed_count}, stored={stored_count}, final_count={len(final_items)}")
        
        # Record successful fetch for rate limiting only if items were actually stored
        if stored_count and stored_count > 0:
            try:
                await twitter_source.rate_limit_service.record_fetch_attempt(success=True)
                logger.info(f"[TwitterOnDemandFetch] Recorded successful fetch for rate limiting")
            except Exception as e:
                logger.warning(f"[TwitterOnDemandFetch] Failed to record fetch attempt (non-critical): {e}")
        else:
            logger.info(f"[TwitterOnDemandFetch] No items stored, skipping rate limit recording")
        
        return {
            "success": True,
            "message": f"Successfully fetched and processed Twitter data for {date}",
            "items_processed": processed_count,
            "items_stored": stored_count,
            "items_final": len(final_items),
            "errors": errors,
            "date": date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TwitterOnDemandFetch] Critical error in fetch endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/news/fetch/{date}")
async def fetch_news_for_date(
    date: str,
    database: DatabaseService = Depends(get_database_service_dependency),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> Dict[str, Any]:
    """
    Fetch news data for a specific date on-demand.
    This endpoint automatically fetches current news and stores it with the specified date.
    """
    try:
        logger.info(f"[OnDemandNewsFetch] Starting on-demand news fetch for date: {date}")
        
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            logger.debug(f"[OnDemandNewsFetch] Parsed date: {parsed_date}")
        except ValueError:
            logger.error(f"[OnDemandNewsFetch] Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if news data already exists for this date
        existing_items = await database.async_get_data_items_by_date(date, namespaces=['news'])
        if existing_items:
            logger.info(f"[OnDemandNewsFetch] News data already exists for {date}: {len(existing_items)} items")
            return {
                "success": True,
                "message": f"News data already exists for {date}",
                "items_processed": 0,
                "items_existing": len(existing_items),
                "date": date
            }
        
        logger.debug(f"[OnDemandNewsFetch] No existing news data found for {date}, proceeding with fetch")
        
        # Get configuration and create News source
        config = get_config()
        if not config.news.is_api_key_configured():
            logger.error("[OnDemandNewsFetch] News API key not configured")
            raise HTTPException(status_code=503, detail="News API key not configured")
        
        logger.debug(f"[OnDemandNewsFetch] Creating NewsSource with config")
        from sources.news import NewsSource
        news_source = NewsSource(config.news, database)
        
        # Test API connectivity first
        logger.debug(f"[OnDemandNewsFetch] Testing News API connectivity")
        connection_ok = await news_source.test_connection()
        if not connection_ok:
            logger.error("[OnDemandNewsFetch] Failed to connect to News API")
            raise HTTPException(status_code=503, detail="Failed to connect to News API")
        
        logger.info(f"[OnDemandNewsFetch] Successfully connected to News API")
        
        # Fetch news data
        logger.info(f"[OnDemandNewsFetch] Fetching news data from API")
        items_fetched = []
        
        try:
            # Use the existing fetch_items method
            async for item in news_source.fetch_items(limit=config.news.unique_items_per_day):
                # Override the days_date to match the requested date
                item.days_date = date
                items_fetched.append(item)
                logger.debug(f"[OnDemandNewsFetch] Fetched item: {item.source_id}")
            
            logger.info(f"[OnDemandNewsFetch] Fetched {len(items_fetched)} news items")
            
        except Exception as e:
            logger.error(f"[OnDemandNewsFetch] Error fetching news data from API: {e}")
            raise HTTPException(status_code=503, detail=f"Error fetching news data from API: {str(e)}")
        
        if not items_fetched:
            logger.info(f"[OnDemandNewsFetch] No news data found")
            return {
                "success": True,
                "message": f"No news data available for {date}",
                "items_processed": 0,
                "items_existing": 0,
                "date": date
            }
        
        # Register the source with ingestion service if not already registered
        if 'news' not in ingestion_service.sources:
            logger.debug(f"[OnDemandNewsFetch] Registering News source with ingestion service")
            ingestion_service.register_source(news_source)
        
        # Process items through existing pipeline using proper ingestion service methods
        logger.info(f"[OnDemandNewsFetch] Processing {len(items_fetched)} items through ingestion pipeline")
        
        # Import IngestionResult for proper result tracking
        from services.ingestion import IngestionResult
        result = IngestionResult()
        result.start_time = datetime.now(timezone.utc)
        
        try:
            # Process each item using the ingestion service's standard processing method
            for item in items_fetched:
                logger.debug(f"[OnDemandNewsFetch] Processing item: {item.source_id}")
                await ingestion_service._process_and_store_item(item, result)
                result.items_processed += 1  # Manually track processed count
                logger.debug(f"[OnDemandNewsFetch] Successfully processed item: {item.source_id}")
            
            result.end_time = datetime.now(timezone.utc)
            processed_count = result.items_processed
            stored_count = result.items_stored 
            errors = result.errors
            
            logger.info(f"[OnDemandNewsFetch] Processing completed: {processed_count} processed, {stored_count} stored, {len(errors)} errors")
            
        except Exception as e:
            logger.error(f"[OnDemandNewsFetch] Critical error during processing: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")
        
        # Process embeddings for the newly stored items
        logger.info(f"[OnDemandNewsFetch] Processing embeddings for newly stored items")
        try:
            embedding_result = await ingestion_service.process_pending_embeddings(batch_size=32)
            logger.debug(f"[OnDemandNewsFetch] Embedding processing result: {embedding_result}")
        except Exception as e:
            logger.warning(f"[OnDemandNewsFetch] Error processing embeddings (non-critical): {e}")
        
        # Verify final result
        final_items = await database.async_get_data_items_by_date(date, namespaces=['news'])
        
        logger.info(f"[OnDemandNewsFetch] On-demand news fetch completed for {date}: processed={processed_count}, stored={stored_count}, final_count={len(final_items)}")
        
        return {
            "success": True,
            "message": f"Successfully fetched and processed news data for {date}",
            "items_processed": processed_count,
            "items_stored": stored_count,
            "items_final": len(final_items),
            "errors": errors,
            "date": date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OnDemandNewsFetch] Critical error in news fetch endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/data_items/{date}")
async def get_data_items_for_date(
    date: str, 
    namespaces: Optional[str] = None,
    database: DatabaseService = Depends(get_database_service_dependency)
) -> List[Dict[str, Any]]:
    """Get all data_items for a specific date, optionally filtered by namespaces"""
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"[DATA_ITEMS API DEBUG] Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Parse namespaces parameter if provided
        namespace_list = None
        if namespaces:
            namespace_list = [ns.strip() for ns in namespaces.split(",")]
        
        # Enhanced debug logging
        logger.info(f"[DATA_ITEMS API DEBUG] === REQUEST START ===")
        logger.info(f"[DATA_ITEMS API DEBUG] Date: {date} (parsed: {parsed_date})")
        logger.info(f"[DATA_ITEMS API DEBUG] Namespaces param: '{namespaces}'")
        logger.info(f"[DATA_ITEMS API DEBUG] Namespace list: {namespace_list}")
        
        # Check what Twitter data exists in database
        if namespace_list and 'twitter' in namespace_list:
            logger.info(f"[DATA_ITEMS API DEBUG] Checking Twitter data in database...")
            
            # Get all Twitter data for debugging
            all_twitter_items = await database.async_get_data_items_by_date(date, ['twitter'])
            logger.info(f"[DATA_ITEMS API DEBUG] Found {len(all_twitter_items)} Twitter items for {date}")
            
            # Check for different Twitter source types
            if all_twitter_items:
                source_types = {}
                for item in all_twitter_items:
                    metadata = item.get('metadata', {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except:
                            metadata = {}
                    
                    source_type = metadata.get('source_type', 'unknown')
                    if source_type not in source_types:
                        source_types[source_type] = []
                    source_types[source_type].append(item.get('id'))
                
                logger.info(f"[DATA_ITEMS API DEBUG] Twitter source types found:")
                for source_type, item_ids in source_types.items():
                    logger.info(f"[DATA_ITEMS API DEBUG]   - {source_type}: {len(item_ids)} items")
                    logger.info(f"[DATA_ITEMS API DEBUG]     Sample IDs: {item_ids[:3]}")
        
        # Get data items for the date
        logger.info(f"[DATA_ITEMS API DEBUG] Calling database.async_get_data_items_by_date...")
        data_items = await database.async_get_data_items_by_date(date, namespace_list)
        
        logger.info(f"[DATA_ITEMS API DEBUG] Retrieved {len(data_items)} data items for date {date}")
        
        # Enhanced item analysis for debugging
        if data_items:
            logger.info(f"[DATA_ITEMS API DEBUG] === ITEM ANALYSIS ===")
            
            # Analyze first few items
            for i, item in enumerate(data_items[:3]):
                logger.info(f"[DATA_ITEMS API DEBUG] Item {i+1}:")
                logger.info(f"[DATA_ITEMS API DEBUG]   ID: {item.get('id')}")
                logger.info(f"[DATA_ITEMS API DEBUG]   Namespace: {item.get('namespace')}")
                logger.info(f"[DATA_ITEMS API DEBUG]   Source ID: {item.get('source_id')}")
                logger.info(f"[DATA_ITEMS API DEBUG]   Content length: {len(item.get('content', ''))}")
                logger.info(f"[DATA_ITEMS API DEBUG]   Content preview: {repr(item.get('content', '')[:50])}")
                logger.info(f"[DATA_ITEMS API DEBUG]   Days date: {item.get('days_date')}")
                logger.info(f"[DATA_ITEMS API DEBUG]   Created at: {item.get('created_at')}")
                
                metadata = item.get('metadata', {})
                metadata_type = type(metadata).__name__
                logger.info(f"[DATA_ITEMS API DEBUG]   Metadata type: {metadata_type}")
                
                # Parse metadata if it's a string
                if isinstance(metadata, str):
                    try:
                        parsed_metadata = json.loads(metadata)
                        logger.info(f"[DATA_ITEMS API DEBUG]   Metadata keys: {list(parsed_metadata.keys())}")
                        logger.info(f"[DATA_ITEMS API DEBUG]   Source type: {parsed_metadata.get('source_type')}")
                        
                        # Check for media info
                        if 'media' in parsed_metadata:
                            media_info = parsed_metadata['media']
                            logger.info(f"[DATA_ITEMS API DEBUG]   Media info: {media_info}")
                        
                    except Exception as parse_error:
                        logger.warning(f"[DATA_ITEMS API DEBUG]   Failed to parse metadata: {parse_error}")
                        logger.info(f"[DATA_ITEMS API DEBUG]   Raw metadata (first 100 chars): {repr(metadata[:100])}")
                elif isinstance(metadata, dict):
                    logger.info(f"[DATA_ITEMS API DEBUG]   Metadata keys: {list(metadata.keys())}")
                    logger.info(f"[DATA_ITEMS API DEBUG]   Source type: {metadata.get('source_type')}")
                    
                    # Check for media info
                    if 'media' in metadata:
                        media_info = metadata['media']
                        logger.info(f"[DATA_ITEMS API DEBUG]   Media info: {media_info}")
                else:
                    logger.info(f"[DATA_ITEMS API DEBUG]   Metadata: {repr(metadata)}")
        
        else:
            logger.warning(f"[DATA_ITEMS API DEBUG] No data items found for date {date} with namespaces {namespace_list}")
            
            # Debug: Check if data exists for this date with any namespace
            all_date_items = await database.async_get_data_items_by_date(date, None)
            logger.info(f"[DATA_ITEMS API DEBUG] Total items for {date} (all namespaces): {len(all_date_items)}")
            
            if all_date_items:
                namespaces_found = set()
                for item in all_date_items:
                    namespaces_found.add(item.get('namespace'))
                logger.info(f"[DATA_ITEMS API DEBUG] Namespaces available for {date}: {sorted(namespaces_found)}")
        
        logger.info(f"[DATA_ITEMS API DEBUG] === REQUEST END ===")
        return data_items
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DATA_ITEMS API DEBUG] Error getting data items for {date}: {e}")
        logger.exception("Full exception details:")
        raise HTTPException(status_code=500, detail="Failed to get data items")