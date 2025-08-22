"""
Data Items API routes for retrieving unified data items by namespace and date.
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_database_service
from core.database import DatabaseService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data_items", tags=["data_items"])


@router.get("", response_model=List[Dict[str, Any]])
async def get_data_items(
    namespace: Optional[str] = Query(None, description="Filter by namespace (e.g., 'twitter', 'news', 'limitless')"),
    date: Optional[str] = Query(None, description="Filter by date in YYYY-MM-DD format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    database: DatabaseService = Depends(get_database_service)
):
    """Get data items filtered by namespace and/or date."""
    try:
        logger.info(f"Getting data items - namespace: {namespace}, date: {date}, limit: {limit}")
        
        # Build query conditions
        conditions = []
        params = []
        
        if namespace:
            conditions.append("namespace = ?")
            params.append(namespace)
        
        if date:
            conditions.append("days_date = ?")
            params.append(date)
        
        # Build the query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT id, namespace, source_id, content, metadata, 
                   embedding_status, created_at, updated_at, days_date
            FROM data_items
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        with database.get_connection() as conn:
            cursor = conn.execute(query, params)
            items = []
            
            for row in cursor.fetchall():
                # Convert row to dict
                item = {
                    "id": row["id"],
                    "namespace": row["namespace"],
                    "source_id": row["source_id"],
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "embedding_status": row["embedding_status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "days_date": row["days_date"]
                }
                items.append(item)
        
        logger.info(f"Retrieved {len(items)} data items")
        return items
        
    except Exception as e:
        logger.error(f"Error fetching data items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces", response_model=List[str])
async def get_namespaces(
    database: DatabaseService = Depends(get_database_service)
):
    """Get all available namespaces."""
    try:
        logger.info("Getting all namespaces")
        
        with database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT namespace 
                FROM data_items 
                ORDER BY namespace
            """)
            namespaces = [row["namespace"] for row in cursor.fetchall()]
        
        logger.info(f"Retrieved {len(namespaces)} namespaces")
        return namespaces
        
    except Exception as e:
        logger.error(f"Error fetching namespaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count", response_model=Dict[str, int])
async def get_data_items_count(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    date: Optional[str] = Query(None, description="Filter by date in YYYY-MM-DD format"),
    database: DatabaseService = Depends(get_database_service)
):
    """Get count of data items filtered by namespace and/or date."""
    try:
        logger.info(f"Getting data items count - namespace: {namespace}, date: {date}")
        
        # Build query conditions
        conditions = []
        params = []
        
        if namespace:
            conditions.append("namespace = ?")
            params.append(namespace)
        
        if date:
            conditions.append("days_date = ?")
            params.append(date)
        
        # Build the query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT COUNT(*) as count
            FROM data_items
            WHERE {where_clause}
        """
        
        with database.get_connection() as conn:
            cursor = conn.execute(query, params)
            count = cursor.fetchone()["count"]
        
        logger.info(f"Data items count: {count}")
        return {"count": count}
        
    except Exception as e:
        logger.error(f"Error getting data items count: {e}")
        raise HTTPException(status_code=500, detail=str(e))