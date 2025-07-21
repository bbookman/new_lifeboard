import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from services.startup import get_startup_service, StartupService
from services.sync_manager_service import SyncManagerService
from services.ingestion import IngestionResult
from config.factory import create_production_config

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses

class SyncTriggerRequest(BaseModel):
    """Request model for triggering sync"""
    force_full_sync: bool = False
    limit: int = Field(default=1000, ge=1, le=10000)

class SyncResponse(BaseModel):
    """Response model for sync operations"""
    success: bool
    message: str
    namespace: str
    result: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    """Response model for health checks"""
    healthy: bool
    services: Dict[str, bool]
    details: Optional[Dict[str, Any]] = None

class StatusResponse(BaseModel):
    """Response model for status endpoints"""
    timestamp: str
    data: Dict[str, Any]

# Dependency to get startup service
def get_startup_service_dependency() -> StartupService:
    startup_service = get_startup_service()
    if not startup_service:
        raise HTTPException(status_code=503, detail="Application not initialized")
    return startup_service

def get_sync_manager(startup_service: StartupService = Depends(get_startup_service_dependency)) -> SyncManagerService:
    if not startup_service.sync_manager:
        raise HTTPException(status_code=503, detail="Sync manager not available")
    return startup_service.sync_manager

# Lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Starting Lifeboard API server...")
        
        # Initialize application
        from services.startup import initialize_application
        config = create_production_config()
        
        result = await initialize_application(config, enable_auto_sync=True)
        
        if result["success"]:
            logger.info("Application initialized successfully")
        else:
            logger.error(f"Application initialization failed: {result.get('errors', [])}")
    
    except Exception as e:
        logger.error(f"Failed to initialize application on startup: {e}")
    
    yield
    
    # Shutdown
    try:
        logger.info("Shutting down Lifeboard API server...")
        
        from services.startup import shutdown_application
        await shutdown_application()
        
        logger.info("Application shutdown completed")
    
    except Exception as e:
        logger.error(f"Error during application shutdown: {e}")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Lifeboard API",
    description="API for Lifeboard personal data management system",
    version="1.0.0",
    lifespan=lifespan
)

# Health and status endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check(startup_service: StartupService = Depends(get_startup_service_dependency)):
    """Get application health status"""
    try:
        app_status = startup_service.get_application_status()
        
        health_response = HealthResponse(
            healthy=app_status.get("startup_complete", False),
            services=app_status.get("services", {}),
            details=app_status
        )
        
        return health_response
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            healthy=False,
            services={},
            details={"error": str(e)}
        )

@app.get("/status", response_model=StatusResponse)
async def get_application_status(startup_service: StartupService = Depends(get_startup_service_dependency)):
    """Get detailed application status"""
    try:
        status_data = startup_service.get_application_status()
        
        return StatusResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=status_data
        )
    
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

# Sync management endpoints

@app.get("/api/sync/status")
async def get_sync_status(sync_manager: SyncManagerService = Depends(get_sync_manager)):
    """Get sync status for all sources"""
    try:
        status = sync_manager.get_all_sources_sync_status()
        
        return StatusResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=status
        )
    
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")

@app.get("/api/sync/{namespace}/status")
async def get_source_sync_status(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager)
):
    """Get sync status for a specific source"""
    try:
        status = sync_manager.get_source_sync_status(namespace)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Source {namespace} not found or not registered for sync")
        
        return StatusResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=status
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync status for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")

@app.post("/api/sync/{namespace}", response_model=SyncResponse)
async def trigger_sync(
    namespace: str,
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Trigger immediate sync for a namespace"""
    try:
        if not startup_service.ingestion_service:
            raise HTTPException(status_code=503, detail="Ingestion service not available")
        
        # Check if source exists
        if namespace not in startup_service.ingestion_service.sources:
            raise HTTPException(status_code=404, detail=f"Source {namespace} not registered")
        
        # Trigger sync
        result = await startup_service.trigger_immediate_sync(
            namespace=namespace,
            force_full_sync=request.force_full_sync
        )
        
        return SyncResponse(
            success=result.success,
            message=f"Sync completed for {namespace}: {result.items_processed} processed, {result.items_stored} stored",
            namespace=namespace,
            result=result.to_dict()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger sync for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@app.post("/api/sync/{namespace}/schedule")
async def trigger_scheduled_job(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager)
):
    """Trigger the scheduled job for a namespace immediately"""
    try:
        success = await sync_manager.trigger_scheduled_job(namespace)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"No scheduled job found for {namespace}")
        
        return {"success": True, "message": f"Triggered scheduled job for {namespace}"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger scheduled job for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger job: {str(e)}")

@app.post("/api/sync/{namespace}/pause")
async def pause_sync(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager)
):
    """Pause automatic syncing for a source"""
    try:
        success = sync_manager.pause_source_sync(namespace)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Source {namespace} not found or not registered for auto-sync")
        
        return {"success": True, "message": f"Paused auto-sync for {namespace}"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause sync for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause sync: {str(e)}")

@app.post("/api/sync/{namespace}/resume")
async def resume_sync(
    namespace: str,
    sync_manager: SyncManagerService = Depends(get_sync_manager)
):
    """Resume automatic syncing for a source"""
    try:
        success = sync_manager.resume_source_sync(namespace)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Source {namespace} not found or not paused")
        
        return {"success": True, "message": f"Resumed auto-sync for {namespace}"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume sync for {namespace}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume sync: {str(e)}")

# Embeddings management

@app.post("/api/embeddings/process")
async def process_pending_embeddings(
    batch_size: int = 32,
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """Process pending embeddings"""
    try:
        if not startup_service.ingestion_service:
            raise HTTPException(status_code=503, detail="Ingestion service not available")
        
        result = await startup_service.process_pending_embeddings(batch_size)
        
        return {
            "success": True,
            "message": f"Processed {result['processed']} items",
            "result": result
        }
    
    except Exception as e:
        logger.error(f"Failed to process embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process embeddings: {str(e)}")

# System management endpoints

@app.post("/api/system/startup")
async def initialize_system():
    """Initialize the application system"""
    try:
        from services.startup import initialize_application
        
        config = create_production_config()
        result = await initialize_application(config, enable_auto_sync=True)
        
        return {
            "success": result["success"],
            "message": "System initialization completed" if result["success"] else "System initialization failed",
            "result": result
        }
    
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        raise HTTPException(status_code=500, detail=f"System initialization failed: {str(e)}")

@app.post("/api/system/shutdown")
async def shutdown_system():
    """Shutdown the application system gracefully"""
    try:
        from services.startup import shutdown_application
        
        await shutdown_application()
        
        return {"success": True, "message": "System shutdown completed"}
    
    except Exception as e:
        logger.error(f"Failed to shutdown system: {e}")
        raise HTTPException(status_code=500, detail=f"System shutdown failed: {str(e)}")

# Error handlers

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": str(exc.detail) if hasattr(exc, 'detail') else "Resource not found"}
    )

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )


# Development server runner
def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the development server"""
    log_level = "debug" if debug else "info"
    
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=debug
    )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lifeboard API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port, debug=args.debug)