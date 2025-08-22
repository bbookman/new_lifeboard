"""
Calendar API routes for Lifeboard

Provides calendar interface with month view navigation and day detail views.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytz
from fastapi import APIRouter, Depends, HTTPException

from config.factory import get_config
from core.database import DatabaseService
from core.dependencies import get_startup_service_dependency
from services.ingestion import IngestionService
from services.news_service import NewsService
from services.startup import StartupService
from services.sync_status_service import get_sync_status_service
from services.weather_service import WeatherService
from sources.limitless import LimitlessSource

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


def get_ingestion_service(startup_service: StartupService = Depends(get_startup_service_dependency)) -> IngestionService:
    """Get ingestion service from startup service (fixed dependency injection)"""
    if not startup_service.ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not available")
    return startup_service.ingestion_service


def get_user_timezone_aware_now(startup_service: StartupService) -> datetime:
    """Get current datetime in user's configured timezone"""
    try:
        # Get user timezone from environment variable first, then config, then default
        user_timezone = os.getenv("TIME_ZONE", "America/New_York")

        # Also try config as fallback if env var not available
        if not user_timezone or user_timezone == "America/New_York":
            if hasattr(startup_service, "config") and startup_service.config:
                user_timezone = getattr(startup_service.config.limitless, "timezone", user_timezone)

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
    startup_service: StartupService = Depends(get_startup_service_dependency),
) -> Dict[str, str]:
    """Get today's date in the server's configured timezone"""
    try:
        today = get_user_timezone_aware_now(startup_service)
        today_str = today.strftime("%Y-%m-%d")

        logger.debug(f"[CALENDAR API] Today's date in configured timezone: {today_str}")

        return {
            "today": today_str,
            "timezone": os.getenv("TIME_ZONE", "America/New_York"),
            "timestamp": today.isoformat(),
        }
    except Exception as e:
        logger.error(f"[CALENDAR API] Error getting today's date: {e}")
        raise HTTPException(status_code=500, detail="Failed to get today's date")


@router.get("/api/days-with-data")
async def get_days_with_data(
    year: Optional[int] = None,
    month: Optional[int] = None,
    database: DatabaseService = Depends(get_database_service),
) -> Dict[str, Any]:
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
            "sync_status": sync_status,
        }

        logger.info(f"[CALENDAR API] Returning response with sync status: data={len(result)} namespaces, sync_complete={sync_status['is_complete'] if sync_status else 'unknown'}")
        return response

    except Exception as e:
        logger.error(f"[CALENDAR API] Error getting days with data: {e}")
        logger.error(f"[CALENDAR DEBUG] Exception details: {e!s}")
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
        limitless_items = database.get_data_items_by_date(date, namespaces=["limitless"])

        # Get markdown content from limitless items
        markdown_content = database.get_markdown_by_date(date, namespaces=["limitless"])

        return {
            "date": date,
            "formatted_date": parsed_date.strftime("%B %d, %Y"),
            "day_of_week": parsed_date.strftime("%A"),
            "markdown_content": markdown_content,
            "item_count": len(limitless_items),
            "has_data": len(limitless_items) > 0,  # Correctly base has_data on filtered items
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
    news_service: NewsService = Depends(get_news_service),
) -> Dict[str, Any]:
    """Get enhanced day data including weather, news, and limitless content"""
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Get basic day details
        markdown_content = database.get_markdown_by_date(date, namespaces=["limitless"])
        limitless_items = database.get_data_items_by_date(date, namespaces=["limitless"])

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
                "has_data": len(weather_data) > 0,
            },
            "news": {
                "articles": news_data,
                "count": len(news_data),
                "has_data": len(news_data) > 0,
            },
            "limitless": {
                "markdown_content": markdown_content,
                "raw_items": limitless_items,
                "item_count": len(limitless_items),
                "has_data": len(limitless_items) > 0 or bool(markdown_content),
            },
            "summary": {
                "total_items": len(limitless_items),
                "has_any_data": len(limitless_items) > 0 or len(weather_data) > 0 or len(news_data) > 0,
            },
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
    database: DatabaseService = Depends(get_database_service),
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
            "total_days_with_data": len(days_with_data),
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
    database: DatabaseService = Depends(get_database_service),
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
            metadata = item.get("metadata", {})

            analysis = {
                "item_index": i + 1,
                "id": item.get("id", "unknown"),
                "namespace": item.get("namespace"),
                "source_id": item.get("source_id"),
                "content_length": len(item.get("content", "")),
                "content_preview": item.get("content", "")[:100] + "..." if item.get("content", "") else None,
                "has_metadata": bool(metadata),
                "metadata_keys": list(metadata.keys()) if isinstance(metadata, dict) else [],
                "has_cleaned_markdown": "cleaned_markdown" in metadata if isinstance(metadata, dict) else False,
                "has_title": "title" in metadata if isinstance(metadata, dict) else False,
                "title": metadata.get("title") if isinstance(metadata, dict) else None,
                "cleaned_markdown_preview": None,
                "cleaned_markdown_has_headers": False,
            }

            # Analyze cleaned markdown if present
            if isinstance(metadata, dict) and "cleaned_markdown" in metadata:
                cleaned_md = metadata["cleaned_markdown"]
                analysis["cleaned_markdown_preview"] = cleaned_md[:200] + "..." if len(cleaned_md) > 200 else cleaned_md
                analysis["cleaned_markdown_length"] = len(cleaned_md)
                analysis["cleaned_markdown_has_headers"] = bool(re.search(r"^#+\s", cleaned_md, re.MULTILINE))

                # Count header types
                header_counts = {}
                for level in range(1, 7):
                    pattern = f"^{'#' * level} .+$"
                    matches = re.findall(pattern, cleaned_md, re.MULTILINE)
                    if matches:
                        header_counts[f"h{level}"] = len(matches)
                        analysis[f"h{level}_headers"] = matches[:3]  # First 3 headers of each type

                analysis["header_counts"] = header_counts

            item_analysis.append(analysis)

        # Analyze final markdown output
        final_analysis = {
            "total_length": len(markdown_content),
            "preview": markdown_content[:300] + "..." if len(markdown_content) > 300 else markdown_content,
            "has_headers": bool(re.search(r"^#+\s", markdown_content, re.MULTILINE)),
            "line_count": len(markdown_content.split("\n")),
            "contains_separators": "---" in markdown_content,
        }

        # Count final header types
        final_header_counts = {}
        for level in range(1, 7):
            pattern = f"^{'#' * level} .+$"
            matches = re.findall(pattern, markdown_content, re.MULTILINE)
            if matches:
                final_header_counts[f"h{level}"] = len(matches)
                final_analysis[f"h{level}_headers"] = matches[:5]  # First 5 headers of each type

        final_analysis["header_counts"] = final_header_counts

        return {
            "debug_info": {
                "date": date,
                "namespaces_requested": namespace_list,
                "timestamp": datetime.now().isoformat(),
            },
            "data_items": {
                "count": len(data_items),
                "analysis": item_analysis,
            },
            "final_markdown": final_analysis,
            "raw_markdown_content": markdown_content,  # Full content for debugging
        }

    except Exception as e:
        logger.error(f"Error in markdown debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Debug endpoint error: {e!s}")


@router.get("/debug/markdown/{date}/raw")
async def debug_markdown_raw(
    date: str,
    namespaces: Optional[str] = "limitless",
    database: DatabaseService = Depends(get_database_service),
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
            "date": date,
            "namespaces": namespaces,
            "markdown": markdown_content,
        }

    except Exception as e:
        logger.error(f"Error in raw markdown debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Debug endpoint error: {e!s}")


@router.post("/api/limitless/fetch/{date}")
async def fetch_limitless_for_date(
    date: str,
    database: DatabaseService = Depends(get_database_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
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
        existing_items = database.get_data_items_by_date(date, namespaces=["limitless"])
        if existing_items:
            logger.info(f"[OnDemandFetch] Data already exists for {date}: {len(existing_items)} items")
            return {
                "success": True,
                "message": f"Data already exists for {date}",
                "items_processed": 0,
                "items_existing": len(existing_items),
                "date": date,
            }

        logger.debug(f"[OnDemandFetch] No existing data found for {date}, proceeding with fetch")

        # Get configuration and create Limitless source
        config = get_config()
        if not config.limitless.is_api_key_configured():
            logger.error("[OnDemandFetch] Limitless API key not configured")
            raise HTTPException(status_code=503, detail="Limitless API key not configured")

        logger.debug("[OnDemandFetch] Creating LimitlessSource with config")
        limitless_source = LimitlessSource(config.limitless)

        # Test API connectivity first
        logger.debug("[OnDemandFetch] Testing Limitless API connectivity")
        connection_ok = await limitless_source.test_connection()
        if not connection_ok:
            logger.error("[OnDemandFetch] Failed to connect to Limitless API")
            raise HTTPException(status_code=503, detail="Failed to connect to Limitless API")

        logger.info("[OnDemandFetch] Successfully connected to Limitless API")

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

        # Fetch data from Limitless API for the specific date range
        logger.info("[OnDemandFetch] Fetching data from Limitless API for date range")
        items_fetched = []

        try:
            # Use the existing fetch_items method with since parameter
            # Note: Limitless API might not support end date filtering, so we'll filter afterwards
            async for item in limitless_source.fetch_items(since=start_utc, limit=1000):
                # Filter items that fall within our target date
                if item.created_at:
                    item_date_utc = item.created_at
                    if item_date_utc.tzinfo is None:
                        item_date_utc = item_date_utc.replace(tzinfo=timezone.utc)

                    # Check if item falls within our target date range
                    if start_utc <= item_date_utc <= end_utc:
                        items_fetched.append(item)
                        logger.debug(f"[OnDemandFetch] Item {item.source_id} matches date range")
                    elif item_date_utc > end_utc:
                        # We've moved past our target date, stop fetching
                        logger.debug(f"[OnDemandFetch] Item {item.source_id} past target date, stopping fetch")
                        break
                    else:
                        logger.debug(f"[OnDemandFetch] Item {item.source_id} before target date, continuing")
                else:
                    # If no created_at, include it (fallback)
                    items_fetched.append(item)
                    logger.debug(f"[OnDemandFetch] Item {item.source_id} has no created_at, including")

            logger.info(f"[OnDemandFetch] Fetched {len(items_fetched)} items for {date}")

        except Exception as e:
            logger.error(f"[OnDemandFetch] Error fetching data from Limitless API: {e}")
            raise HTTPException(status_code=503, detail=f"Error fetching data from Limitless API: {e!s}")

        if not items_fetched:
            logger.info(f"[OnDemandFetch] No data found for {date}")
            return {
                "success": True,
                "message": f"No data found for {date}",
                "items_processed": 0,
                "items_existing": 0,
                "date": date,
            }

        # Register the source with ingestion service if not already registered
        if "limitless" not in ingestion_service.sources:
            logger.debug("[OnDemandFetch] Registering Limitless source with ingestion service")
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
            raise HTTPException(status_code=500, detail=f"Error processing data: {e!s}")

        # Process embeddings for the newly stored items
        logger.info("[OnDemandFetch] Processing embeddings for newly stored items")
        try:
            embedding_result = await ingestion_service.process_pending_embeddings(batch_size=32)
            logger.debug(f"[OnDemandFetch] Embedding processing result: {embedding_result}")
        except Exception as e:
            logger.warning(f"[OnDemandFetch] Error processing embeddings (non-critical): {e}")

        # Verify final result
        final_items = database.get_data_items_by_date(date, namespaces=["limitless"])

        logger.info(f"[OnDemandFetch] On-demand fetch completed for {date}: processed={processed_count}, stored={stored_count}, final_count={len(final_items)}")

        return {
            "success": True,
            "message": f"Successfully fetched and processed data for {date}",
            "items_processed": processed_count,
            "items_stored": stored_count,
            "items_final": len(final_items),
            "errors": errors,
            "date": date,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OnDemandFetch] Critical error in fetch endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e!s}")


@router.get("/api/data_items/{date}")
async def get_data_items_for_date(
    date: str,
    namespaces: Optional[str] = None,
    database: DatabaseService = Depends(get_database_service),
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

            metadata = first_item.get("metadata", {})
            if isinstance(metadata, dict):
                logger.info(f"[DATA_ITEMS API] First item metadata keys: {list(metadata.keys())}")
                if "cleaned_markdown" in metadata:
                    cleaned_md = metadata["cleaned_markdown"]
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
