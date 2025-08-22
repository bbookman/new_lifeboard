import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from config.factory import ConfigFactory
from core.database import DatabaseService
from core.embeddings import EmbeddingService
from services.semantic_deduplication_service import SemanticDeduplicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/semantic-patterns", tags=["semantic-patterns"])

def get_semantic_service() -> SemanticDeduplicationService:
    """Get semantic deduplication service instance"""
    config = ConfigFactory.create_config()
    database = DatabaseService(config.database.path)
    embedding_service = EmbeddingService(config.embeddings)
    return SemanticDeduplicationService(database, embedding_service)


@router.get("/clusters")
async def get_semantic_clusters(
    limit: int = Query(50, ge=1, le=100),
    theme: Optional[str] = Query(None, description="Filter by theme"),
    min_frequency: Optional[int] = Query(None, ge=1, description="Minimum frequency"),
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Get semantic clusters with optional filtering
    
    Returns:
        List of semantic clusters with metadata
    """
    try:
        with service.database.get_connection() as conn:
            # Build query with filters
            where_conditions = []
            params = []

            if theme:
                where_conditions.append("theme = ?")
                params.append(theme)

            if min_frequency:
                where_conditions.append("frequency_count >= ?")
                params.append(min_frequency)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # Get clusters
            cursor = conn.execute(f"""
                SELECT id, theme, canonical_line, confidence_score, frequency_count, 
                       created_at, updated_at
                FROM semantic_clusters
                {where_clause}
                ORDER BY frequency_count DESC
                LIMIT ?
            """, params + [limit])

            clusters = []
            for row in cursor.fetchall():
                cluster_dict = dict(row)

                # Get variations for this cluster
                variations_cursor = conn.execute("""
                    SELECT line_content, speaker, line_timestamp, similarity_score
                    FROM line_cluster_mapping
                    WHERE cluster_id = ? AND is_canonical = FALSE
                    ORDER BY similarity_score DESC
                """, (row["id"],))

                variations = [dict(var_row) for var_row in variations_cursor.fetchall()]
                cluster_dict["variations"] = variations

                clusters.append(cluster_dict)

        return {
            "clusters": clusters,
            "total_found": len(clusters),
            "filters_applied": {
                "theme": theme,
                "min_frequency": min_frequency,
            },
        }

    except Exception as e:
        logger.error(f"Error fetching semantic clusters: {e}")
        raise HTTPException(status_code=500, detail="Error fetching semantic clusters")


@router.get("/statistics")
async def get_pattern_statistics(
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Get comprehensive statistics about conversation patterns
    
    Returns:
        Statistics about clusters, themes, and patterns
    """
    try:
        stats = await service.get_cluster_statistics()

        if not stats:
            return {
                "cluster_stats": {"total_clusters": 0},
                "theme_distribution": [],
                "mapping_stats": {"total_mappings": 0},
                "generated_at": datetime.now().isoformat(),
            }

        return stats

    except Exception as e:
        logger.error(f"Error getting pattern statistics: {e}")
        raise HTTPException(status_code=500, detail="Error getting pattern statistics")


@router.get("/themes")
async def get_available_themes(
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Get list of available themes with counts
    
    Returns:
        List of themes and their frequencies
    """
    try:
        with service.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT theme, 
                       COUNT(*) as cluster_count,
                       SUM(frequency_count) as total_occurrences,
                       AVG(confidence_score) as avg_confidence
                FROM semantic_clusters
                GROUP BY theme
                ORDER BY total_occurrences DESC
            """)

            themes = [dict(row) for row in cursor.fetchall()]

        return {
            "themes": themes,
            "total_themes": len(themes),
        }

    except Exception as e:
        logger.error(f"Error fetching themes: {e}")
        raise HTTPException(status_code=500, detail="Error fetching themes")


@router.get("/conversations/{conversation_id}/patterns")
async def get_conversation_patterns(
    conversation_id: str,
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Get semantic patterns for a specific conversation
    
    Args:
        conversation_id: The conversation ID to analyze
        
    Returns:
        Patterns and clusters found in the conversation
    """
    try:
        # Get conversation data
        item_id = f"limitless:{conversation_id}"
        items = service.database.get_data_items_by_ids([item_id])

        if not items:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation = items[0]

        # Extract semantic metadata
        semantic_metadata = conversation["metadata"].get("semantic_metadata", {})
        semantic_clusters = conversation["metadata"].get("semantic_clusters", {})
        display_conversation = conversation["metadata"].get("display_conversation", [])

        return {
            "conversation_id": conversation_id,
            "title": conversation["metadata"].get("original_lifelog", {}).get("title"),
            "semantic_metadata": semantic_metadata,
            "clusters_found": semantic_clusters,
            "display_conversation": display_conversation,
            "processed": semantic_metadata.get("processed", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation patterns: {e}")
        raise HTTPException(status_code=500, detail="Error fetching conversation patterns")


@router.post("/process")
async def trigger_semantic_processing(
    namespace: str = Query("limitless", description="Namespace to process"),
    batch_size: int = Query(50, ge=1, le=100, description="Batch size for processing"),
    max_items: Optional[int] = Query(None, ge=1, description="Maximum items to process"),
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Trigger semantic deduplication processing for historical conversations
    
    Args:
        namespace: Namespace to process (default: limitless)
        batch_size: Number of items to process per batch
        max_items: Maximum number of items to process
        
    Returns:
        Processing result with statistics
    """
    try:
        logger.info(f"Starting semantic processing for namespace '{namespace}'")

        result = await service.process_historical_conversations(
            namespace=namespace,
            batch_size=batch_size,
            max_items=max_items,
        )

        return {
            "processing_result": {
                "total_processed": result.total_processed,
                "clusters_created": result.clusters_created,
                "processing_time_seconds": result.processing_time,
                "items_modified": result.items_modified,
                "errors": result.errors,
            },
            "success": len(result.errors) == 0,
            "message": f"Processed {result.total_processed} conversations, created {result.clusters_created} clusters",
        }

    except Exception as e:
        logger.error(f"Error in semantic processing: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing conversations: {e!s}")


@router.get("/clusters/{cluster_id}")
async def get_cluster_details(
    cluster_id: str,
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Get detailed information about a specific cluster
    
    Args:
        cluster_id: The cluster ID to retrieve
        
    Returns:
        Detailed cluster information with all variations and conversations
    """
    try:
        with service.database.get_connection() as conn:
            # Get cluster info
            cursor = conn.execute("""
                SELECT id, theme, canonical_line, confidence_score, frequency_count, 
                       created_at, updated_at
                FROM semantic_clusters
                WHERE id = ?
            """, (cluster_id,))

            cluster_row = cursor.fetchone()
            if not cluster_row:
                raise HTTPException(status_code=404, detail="Cluster not found")

            cluster = dict(cluster_row)

            # Get all line mappings for this cluster
            cursor = conn.execute("""
                SELECT data_item_id, line_content, similarity_score, speaker, 
                       line_timestamp, is_canonical
                FROM line_cluster_mapping
                WHERE cluster_id = ?
                ORDER BY similarity_score DESC
            """, (cluster_id,))

            mappings = [dict(row) for row in cursor.fetchall()]

            # Group by conversation
            conversations = {}
            for mapping in mappings:
                item_id = mapping["data_item_id"]
                if item_id not in conversations:
                    conversations[item_id] = {
                        "conversation_id": item_id,
                        "lines": [],
                    }
                conversations[item_id]["lines"].append(mapping)

            cluster["conversations"] = list(conversations.values())
            cluster["total_conversations"] = len(conversations)

        return cluster

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cluster details: {e}")
        raise HTTPException(status_code=500, detail="Error fetching cluster details")


@router.delete("/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: str,
    service: SemanticDeduplicationService = Depends(get_semantic_service),
) -> Dict[str, Any]:
    """
    Delete a semantic cluster and its mappings
    
    Args:
        cluster_id: The cluster ID to delete
        
    Returns:
        Deletion result
    """
    try:
        with service.database.get_connection() as conn:
            # Check if cluster exists
            cursor = conn.execute(
                "SELECT COUNT(*) FROM semantic_clusters WHERE id = ?",
                (cluster_id,),
            )

            if cursor.fetchone()[0] == 0:
                raise HTTPException(status_code=404, detail="Cluster not found")

            # Delete line mappings first (foreign key constraint)
            cursor = conn.execute(
                "DELETE FROM line_cluster_mapping WHERE cluster_id = ?",
                (cluster_id,),
            )
            mappings_deleted = cursor.rowcount

            # Delete cluster
            cursor = conn.execute(
                "DELETE FROM semantic_clusters WHERE id = ?",
                (cluster_id,),
            )

            conn.commit()

        logger.info(f"Deleted cluster {cluster_id} and {mappings_deleted} line mappings")

        return {
            "cluster_id": cluster_id,
            "deleted": True,
            "mappings_deleted": mappings_deleted,
            "message": f"Successfully deleted cluster {cluster_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cluster: {e}")
        raise HTTPException(status_code=500, detail="Error deleting cluster")
