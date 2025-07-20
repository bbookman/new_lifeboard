#!/usr/bin/env python3
"""
Lifeboard API Server

FastAPI-based web API for the Lifeboard application.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from main import LifeboardApplication
from services.search import SearchResponse
from config.models import SourceConfig


logger = logging.getLogger(__name__)

# Global application instance
lifeboard_app: Optional[LifeboardApplication] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global lifeboard_app
    
    logger.info("Starting Lifeboard API server...")
    
    try:
        # Initialize Lifeboard application
        lifeboard_app = LifeboardApplication()
        await lifeboard_app.start()
        logger.info("Lifeboard application started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start Lifeboard application: {e}")
        raise
    finally:
        # Cleanup
        if lifeboard_app:
            await lifeboard_app.shutdown()
            logger.info("Lifeboard application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Lifeboard API",
    description="Interactive reflection space and planning assistant API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query text")
    top_k: Optional[int] = Field(default=None, ge=1, le=100, description="Number of results to return")
    namespace_filter: Optional[List[str]] = Field(default=None, description="Filter by specific namespaces")
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum similarity score")


class SearchResultModel(BaseModel):
    namespaced_id: str
    namespace: str
    source_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any] = {}


class SearchResponseModel(BaseModel):
    query: str
    results: List[SearchResultModel]
    total_results: int
    predicted_sources: List[str]
    priority_order: List[str]
    namespaces_found: List[str]
    search_config: Dict[str, Any]
    search_duration_seconds: float
    timestamp: str


class IngestRequest(BaseModel):
    namespace: str = Field(..., description="Target namespace")
    content: str = Field(..., description="Content to ingest")
    source_id: Optional[str] = Field(default=None, description="Optional source ID")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class IngestResponse(BaseModel):
    namespaced_id: str
    message: str
    success: bool


class SourceInfoModel(BaseModel):
    namespace: str
    source_type: str
    enabled: bool
    item_count: int
    metadata: Dict[str, Any] = {}


class StatsResponse(BaseModel):
    status: str
    database: Dict[str, Any]
    vector_store: Dict[str, Any]
    sources: Dict[str, Any]
    search: Dict[str, Any]
    ingestion: Dict[str, Any]


# Dependency to get application instance
async def get_lifeboard_app() -> LifeboardApplication:
    """Get the Lifeboard application instance"""
    if lifeboard_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    return lifeboard_app


# API Endpoints

@app.get("/", summary="API Information")
async def root():
    """Get API information"""
    return {
        "name": "Lifeboard API",
        "version": "1.0.0",
        "description": "Interactive reflection space and planning assistant",
        "status": "running" if lifeboard_app else "initializing"
    }


@app.get("/health", summary="Health Check")
async def health_check():
    """Health check endpoint"""
    if lifeboard_app is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "Application not initialized"}
        )
    
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/search", response_model=SearchResponseModel, summary="Search Content")
async def search(
    request: SearchRequest,
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """
    Search for content across all data sources
    
    Performs semantic search using embeddings and returns ranked results
    with similarity scores and metadata.
    """
    try:
        # Perform search
        search_response = await app_instance.search(
            query=request.query,
            top_k=request.top_k,
            namespace_filter=request.namespace_filter,
            similarity_threshold=request.similarity_threshold
        )
        
        # Convert to API response model
        results = [
            SearchResultModel(
                namespaced_id=result.namespaced_id,
                namespace=result.namespace,
                source_id=result.source_id,
                content=result.content,
                similarity_score=result.similarity_score,
                metadata=result.metadata
            )
            for result in search_response.results
        ]
        
        return SearchResponseModel(
            query=search_response.query,
            results=results,
            total_results=search_response.total_results,
            predicted_sources=search_response.predicted_sources,
            priority_order=search_response.priority_order,
            namespaces_found=search_response.namespaces_found,
            search_config=search_response.search_config,
            search_duration_seconds=search_response.search_duration_seconds,
            timestamp=search_response.timestamp.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/ingest", response_model=IngestResponse, summary="Ingest Content")
async def ingest_content(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """
    Manually ingest content into the system
    
    Adds content to the specified namespace and processes it for search.
    Embedding generation happens in the background.
    """
    try:
        namespaced_id = await app_instance.ingest_manual_item(
            namespace=request.namespace,
            content=request.content,
            source_id=request.source_id,
            metadata=request.metadata
        )
        
        return IngestResponse(
            namespaced_id=namespaced_id,
            message="Content ingested successfully",
            success=True
        )
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/search/similar/{namespaced_id}", response_model=List[SearchResultModel], summary="Find Similar Content")
async def find_similar(
    namespaced_id: str,
    top_k: int = Query(default=5, ge=1, le=50, description="Number of similar results"),
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """
    Find content similar to a specific item
    
    Uses the content of the specified item to find semantically similar content.
    """
    try:
        # Get the original item
        items = app_instance.db.get_data_items_by_ids([namespaced_id])
        if not items:
            raise HTTPException(status_code=404, detail="Item not found")
        
        content = items[0]['content']
        
        # Find similar content
        similar_results = await app_instance.search_service.search_similar_content(
            content=content,
            top_k=top_k,
            exclude_namespaced_id=namespaced_id
        )
        
        # Convert to API response model
        results = [
            SearchResultModel(
                namespaced_id=result.namespaced_id,
                namespace=result.namespace,
                source_id=result.source_id,
                content=result.content,
                similarity_score=result.similarity_score,
                metadata=result.metadata
            )
            for result in similar_results
        ]
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similar content search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Similar search failed: {str(e)}")


@app.get("/sources", response_model=List[SourceInfoModel], summary="List Data Sources")
async def list_sources(app_instance: LifeboardApplication = Depends(get_lifeboard_app)):
    """Get information about all configured data sources"""
    try:
        sources = []
        active_sources = app_instance.source_registry.get_active_sources()
        
        for source in active_sources:
            try:
                source_info = await source.get_source_info()
                item_count = app_instance.vector_store.get_namespace_count(source.namespace)
                
                sources.append(SourceInfoModel(
                    namespace=source.namespace,
                    source_type=source.get_source_type(),
                    enabled=True,
                    item_count=item_count,
                    metadata=source_info
                ))
            except Exception as e:
                logger.warning(f"Failed to get info for source {source.namespace}: {e}")
                sources.append(SourceInfoModel(
                    namespace=source.namespace,
                    source_type=source.get_source_type(),
                    enabled=True,
                    item_count=0,
                    metadata={"error": str(e)}
                ))
        
        return sources
        
    except Exception as e:
        logger.error(f"Failed to list sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sources: {str(e)}")


@app.get("/sources/{namespace}/recent", response_model=List[SearchResultModel], summary="Get Recent Items from Source")
async def get_recent_items(
    namespace: str,
    limit: int = Query(default=10, ge=1, le=100, description="Number of recent items"),
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """Get recent items from a specific data source"""
    try:
        recent_items = await app_instance.search_service.get_recent_items(
            namespace=namespace,
            limit=limit
        )
        
        results = [
            SearchResultModel(
                namespaced_id=result.namespaced_id,
                namespace=result.namespace,
                source_id=result.source_id,
                content=result.content,
                similarity_score=result.similarity_score,
                metadata=result.metadata
            )
            for result in recent_items
        ]
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get recent items for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent items: {str(e)}")


@app.post("/sources/sync", summary="Sync Data Sources")
async def sync_sources(
    background_tasks: BackgroundTasks,
    namespaces: Optional[List[str]] = Query(default=None, description="Specific namespaces to sync"),
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """
    Trigger synchronization of data sources
    
    Runs in the background and returns immediately with sync job ID.
    """
    try:
        # Start sync in background
        if namespaces:
            # Sync specific sources
            background_tasks.add_task(_sync_specific_sources, app_instance, namespaces)
            message = f"Started sync for {len(namespaces)} sources"
        else:
            # Sync all sources
            background_tasks.add_task(_sync_all_sources, app_instance)
            message = "Started sync for all sources"
        
        return {
            "message": message,
            "status": "started",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to start sync: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {str(e)}")


@app.get("/stats", response_model=StatsResponse, summary="Get System Statistics")
async def get_stats(app_instance: LifeboardApplication = Depends(get_lifeboard_app)):
    """Get comprehensive system statistics"""
    try:
        stats = await app_instance.get_stats()
        
        return StatsResponse(
            status=stats["status"],
            database=stats["database"],
            vector_store=stats["vector_store"],
            sources=stats["sources"],
            search=stats["search"],
            ingestion=stats["ingestion"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.delete("/items/{namespaced_id}", summary="Delete Item")
async def delete_item(
    namespaced_id: str,
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """Delete a specific item from the system"""
    try:
        success = await app_instance.ingestion_service.delete_item(namespaced_id)
        
        if success:
            return {"message": "Item deleted successfully", "success": True}
        else:
            raise HTTPException(status_code=404, detail="Item not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete item {namespaced_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {str(e)}")


@app.post("/test/search-pipeline", summary="Test Search Pipeline")
async def test_search_pipeline(
    test_query: str = Query(default="test query", description="Test query to use"),
    app_instance: LifeboardApplication = Depends(get_lifeboard_app)
):
    """Test the complete search pipeline"""
    try:
        test_result = await app_instance.search_service.test_search_pipeline(test_query)
        return test_result
        
    except Exception as e:
        logger.error(f"Search pipeline test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


# Background task functions
async def _sync_all_sources(app_instance: LifeboardApplication):
    """Background task to sync all sources"""
    try:
        logger.info("Starting background sync of all sources")
        sync_results = await app_instance.ingestion_service.ingest_from_all_sources()
        
        total_items = sum(r.items_added + r.items_updated for r in sync_results.values())
        logger.info(f"Background sync completed: {total_items} items processed")
        
        # Process embeddings
        if total_items > 0:
            embedding_result = await app_instance.ingestion_service.process_pending_embeddings()
            logger.info(f"Background embedding processing: {embedding_result['succeeded']} succeeded")
            
    except Exception as e:
        logger.error(f"Background sync failed: {e}")


async def _sync_specific_sources(app_instance: LifeboardApplication, namespaces: List[str]):
    """Background task to sync specific sources"""
    try:
        logger.info(f"Starting background sync of sources: {namespaces}")
        
        for namespace in namespaces:
            result = await app_instance.ingestion_service.ingest_from_source(namespace)
            logger.info(f"Synced {namespace}: {result.items_added + result.items_updated} items")
        
        # Process embeddings
        embedding_result = await app_instance.ingestion_service.process_pending_embeddings()
        logger.info(f"Background embedding processing: {embedding_result['succeeded']} succeeded")
        
    except Exception as e:
        logger.error(f"Background sync failed: {e}")


if __name__ == "__main__":
    import uvicorn
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the server
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )