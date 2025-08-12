"""
Headings API routes for Lifeboard

Provides heading1 and heading2 content from limitless namespace data,
with fallback from cleaned/semantic processed content to raw content.
"""

import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends

from services.startup import StartupService
from core.database import DatabaseService
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/headings", tags=["headings"])


def get_database_service(startup_service: StartupService = Depends(get_startup_service_dependency)) -> DatabaseService:
    """Get database service from startup service"""
    if not startup_service.database:
        raise HTTPException(status_code=503, detail="Database service not available")
    return startup_service.database


@router.get("/day/{days_date}")
async def get_day_headings(
    days_date: str,
    database: DatabaseService = Depends(get_database_service)
) -> Dict[str, Any]:
    """
    Get heading1 and heading2 content for a specific day from limitless namespace.
    Prefers cleaned/semantic processed content, falls back to raw content.
    """
    try:
        with database.get_connection() as conn:
            # Fetch all limitless data for the specified date
            cursor = conn.execute("""
                SELECT id, metadata, semantic_status
                FROM data_items
                WHERE namespace = 'limitless' 
                AND days_date = ?
                ORDER BY created_at
            """, (days_date,))
            
            items = cursor.fetchall()
            
            if not items:
                return {
                    "days_date": days_date,
                    "headings": [],
                    "source": "none",
                    "total_items": 0
                }
            
            all_headings = []
            cleaned_count = 0
            raw_count = 0
            
            for item in items:
                try:
                    metadata = json.loads(item['metadata'])
                    headings_from_item = []
                    item_source = "raw"
                    
                    # Try to get cleaned headings first (from semantic processing)
                    if 'processed_response' in metadata:
                        processed = metadata['processed_response']
                        semantic_meta = processed.get('semantic_metadata', {})
                        
                        # Check if semantic processing is complete and display_conversation exists
                        if (semantic_meta.get('processed') and 
                            processed.get('display_conversation')):
                            
                            logger.debug(f"Using cleaned headings for item {item['id']}")
                            headings_from_item = extract_headings_from_contents(
                                processed['display_conversation']
                            )
                            item_source = "cleaned"
                            cleaned_count += 1
                    
                    # Fall back to raw headings if no cleaned data available
                    if not headings_from_item:
                        # Handle both new two-key structure and legacy structure
                        if 'original_response' in metadata:
                            # New structure
                            original_contents = metadata['original_response'].get('contents', [])
                        else:
                            # Legacy structure
                            original_lifelog = metadata.get('original_lifelog', {})
                            original_contents = original_lifelog.get('contents', [])
                        
                        if original_contents:
                            logger.debug(f"Using raw headings for item {item['id']}")
                            headings_from_item = extract_headings_from_contents(original_contents)
                            item_source = "raw"
                            raw_count += 1
                    
                    # Add headings with source metadata
                    for heading in headings_from_item:
                        heading['source'] = item_source
                        heading['item_id'] = item['id']
                        heading['semantic_status'] = item['semantic_status']
                        all_headings.append(heading)
                        
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"Error processing item {item['id']}: {e}")
                    continue
            
            # Determine primary source
            primary_source = "cleaned" if cleaned_count > 0 else "raw" if raw_count > 0 else "none"
            
            return {
                "days_date": days_date,
                "headings": all_headings,
                "source": primary_source,
                "total_items": len(items),
                "stats": {
                    "cleaned_items": cleaned_count,
                    "raw_items": raw_count,
                    "total_headings": len(all_headings)
                }
            }
            
    except Exception as e:
        logger.error(f"Error fetching headings for {days_date}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch headings: {str(e)}"
        )


def extract_headings_from_contents(contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract heading1 and heading2 items from contents array"""
    headings = []
    
    for item in contents:
        content_type = item.get('type', '')
        content_text = item.get('content', '').strip()
        
        if content_type in ['heading1', 'heading2'] and content_text:
            heading_data = {
                'type': content_type,
                'content': content_text,
                'level': 1 if content_type == 'heading1' else 2
            }
            
            # Include semantic deduplication info if available
            if item.get('is_deduplicated'):
                heading_data['is_deduplicated'] = True
                heading_data['hidden_variations'] = item.get('hidden_variations', 0)
                heading_data['represents_cluster'] = item.get('represents_cluster')
                heading_data['canonical_confidence'] = item.get('canonical_confidence')
            
            headings.append(heading_data)
    
    return headings


@router.get("/status/{days_date}")
async def get_day_headings_status(
    days_date: str,
    database: DatabaseService = Depends(get_database_service)
) -> Dict[str, Any]:
    """
    Get status information about headings data for a specific day.
    Useful for UI to show processing status and decide on refresh behavior.
    """
    try:
        with database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    semantic_status,
                    COUNT(*) as count,
                    MAX(updated_at) as last_updated
                FROM data_items
                WHERE namespace = 'limitless' 
                AND days_date = ?
                GROUP BY semantic_status
            """, (days_date,))
            
            status_breakdown = {row['semantic_status']: {
                'count': row['count'],
                'last_updated': row['last_updated']
            } for row in cursor.fetchall()}
            
            # Determine overall status
            total_items = sum(status['count'] for status in status_breakdown.values())
            if not total_items:
                overall_status = "no_data"
            elif status_breakdown.get('completed', {}).get('count', 0) == total_items:
                overall_status = "fully_processed"
            elif status_breakdown.get('processing', {}).get('count', 0) > 0:
                overall_status = "processing"
            elif status_breakdown.get('failed', {}).get('count', 0) > 0:
                overall_status = "partially_failed"
            else:
                overall_status = "pending_processing"
            
            return {
                "days_date": days_date,
                "overall_status": overall_status,
                "total_items": total_items,
                "status_breakdown": status_breakdown,
                "has_cleaned_data": status_breakdown.get('completed', {}).get('count', 0) > 0
            }
            
    except Exception as e:
        logger.error(f"Error fetching headings status for {days_date}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch headings status: {str(e)}"
        )