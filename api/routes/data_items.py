"""
Data Items API routes for retrieving unified data items by namespace and date.
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_async_database_service
from core.async_database import AsyncDatabaseService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data_items", tags=["data_items"])


@router.get("", response_model=List[Dict[str, Any]])
async def get_data_items(
    namespace: Optional[str] = Query(None, description="Filter by namespace (e.g., 'twitter', 'news', 'limitless')"),
    date: Optional[str] = Query(None, description="Filter by date in YYYY-MM-DD format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    database: AsyncDatabaseService = Depends(get_async_database_service)
):
    """Get data items filtered by namespace and/or date."""
    try:
        logger.info(f"Getting data items - namespace: {namespace}, date: {date}, limit: {limit}")
        
        # Use existing async database service methods instead of raw SQL
        if date and namespace:
            # Get items for specific date and namespace
            items = await database.get_data_items_by_date(date, [namespace])
            # Apply limit manually since the database method doesn't support it
            items = items[:limit] if len(items) > limit else items
        elif date:
            # Get items for specific date, all namespaces
            items = await database.get_data_items_by_date(date)
            items = items[:limit] if len(items) > limit else items
        elif namespace:
            # Get items for specific namespace
            items = await database.get_data_items_by_namespace(namespace, limit=limit)
        else:
            # Get recent items across all namespaces (limited)
            # Since there's no direct method for this, we'll get by date range or use a custom query
            async with database.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, 
                           embedding_status, created_at, updated_at, days_date
                    FROM data_items
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                rows = await cursor.fetchall()
                items = []
                for row in rows:
                    items.append({
                        "id": row["id"],
                        "namespace": row["namespace"],
                        "source_id": row["source_id"],
                        "content": row["content"],
                        "metadata": row["metadata"],
                        "embedding_status": row["embedding_status"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "days_date": row["days_date"]
                    })
        
        logger.info(f"Retrieved {len(items)} data items")
        return items
        
    except Exception as e:
        logger.error(f"Error fetching data items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces", response_model=List[str])
async def get_namespaces(
    database: AsyncDatabaseService = Depends(get_async_database_service)
):
    """Get all available namespaces."""
    try:
        logger.info("Getting all namespaces")
        
        namespaces = await database.get_all_namespaces()
        
        logger.info(f"Retrieved {len(namespaces)} namespaces")
        return namespaces
        
    except Exception as e:
        logger.error(f"Error fetching namespaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count", response_model=Dict[str, int])
async def get_data_items_count(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    date: Optional[str] = Query(None, description="Filter by date in YYYY-MM-DD format"),
    database: AsyncDatabaseService = Depends(get_async_database_service)
):
    """Get count of data items filtered by namespace and/or date."""
    try:
        logger.info(f"Getting data items count - namespace: {namespace}, date: {date}")
        
        # Use the database methods to get items and count them
        # This is less efficient than a direct COUNT query but leverages existing methods
        if date and namespace:
            items = await database.get_data_items_by_date(date, [namespace])
            count = len(items)
        elif date:
            items = await database.get_data_items_by_date(date)
            count = len(items)
        elif namespace:
            # For namespace-only count, we'll need a custom query
            async with database.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count
                    FROM data_items
                    WHERE namespace = ?
                """, (namespace,))
                row = await cursor.fetchone()
                count = row["count"]
        else:
            # Get total count
            async with database.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) as count FROM data_items")
                row = await cursor.fetchone()
                count = row["count"]
        
        logger.info(f"Data items count: {count}")
        return {"count": count}
        
    except Exception as e:
        logger.error(f"Error getting data items count: {e}")
        raise HTTPException(status_code=500, detail=str(e))