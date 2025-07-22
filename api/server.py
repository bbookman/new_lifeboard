import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import socket

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import uvicorn

from services.startup import get_startup_service, StartupService
from services.sync_manager_service import SyncManagerService
from services.ingestion import IngestionResult
from services.chat_service import ChatService
from config.factory import create_production_config

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="templates")

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

def get_chat_service(startup_service: StartupService = Depends(get_startup_service_dependency)) -> ChatService:
    if not startup_service.chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    return startup_service.chat_service

# Global variable to store server info for banner
_server_info = {"host": None, "port": None}

def print_startup_banner(host: str, port: int):
    """Print the startup banner with server URL"""
    # Convert 0.0.0.0 to localhost for user-friendly display
    display_host = "localhost" if host == "0.0.0.0" else host
    print("\n" + "*" * 51)
    print("*" * 51)
    print(f"Visit http://{display_host}:{port} for home ui")
    print("*" * 51)
    print("*" * 51 + "\n")

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
            
            # Show startup banner with server URL
            import threading
            import time
            
            def delayed_banner():
                # Wait for uvicorn to fully start and print its messages
                time.sleep(3)
                # Try to detect the server port from uvicorn or use default
                server_port = 8000  # Default port
                # Check if uvicorn server info is available
                try:
                    import uvicorn
                    # Try to get the actual port if possible
                    pass  # Keep default for now
                except:
                    pass
                print_startup_banner("localhost", server_port)
            
            # Start the banner in a separate thread
            banner_thread = threading.Thread(target=delayed_banner)
            banner_thread.daemon = True
            banner_thread.start()
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

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint with API overview"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lifeboard API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 2px solid #007acc; padding-bottom: 10px; }
            h2 { color: #555; margin-top: 30px; }
            .endpoint { margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 4px solid #007acc; }
            .method { font-weight: bold; color: #007acc; }
            a { color: #007acc; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏠 Lifeboard API</h1>
            <p>Personal data management system with AI-powered chat and memory integration.</p>
            
            <h2>Available Endpoints</h2>
            
            <div class="endpoint">
                <span class="method">GET</span> <a href="/health">/health</a> - Application health status
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <a href="/status">/status</a> - Detailed application status
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <a href="/chat">/chat</a> - Interactive chat interface
            </div>
            
            <h3>API Endpoints</h3>
            
            <div class="endpoint">
                <span class="method">GET</span> /api/sync/status - All sources sync status
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> /api/sync/{namespace}/status - Specific source sync status
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> /api/sync/{namespace} - Trigger sync for namespace
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> /api/embeddings/process - Process pending embeddings
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> /api/system/startup - Initialize system
            </div>
            
            <div class="endpoint">
                <span class="method">POST</span> /api/system/shutdown - Shutdown system
            </div>
            
            <p style="margin-top: 30px; color: #666;">
                Visit <a href="/chat">/chat</a> to start interacting with your personal data assistant.
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

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

# Chat endpoints (Phase 7)

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, chat_service: ChatService = Depends(get_chat_service)):
    """Get the chat page with recent history"""
    try:
        # Get recent chat history
        history = chat_service.get_chat_history(limit=10)
        
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "history": history
        })
    
    except Exception as e:
        logger.error(f"Failed to load chat page: {e}")
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "error": "Failed to load chat history",
            "history": []
        })

@app.post("/chat", response_class=HTMLResponse)
async def process_chat(
    request: Request, 
    message: str = Form(...),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Process a chat message and return the response"""
    try:
        # Process the chat message
        response = await chat_service.process_chat_message(message)
        
        # Get updated chat history
        history = chat_service.get_chat_history(limit=10)
        
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "user_message": message,
            "response": response,
            "history": history
        })
    
    except Exception as e:
        logger.error(f"Failed to process chat message: {e}")
        
        # Get chat history for the error response
        try:
            history = chat_service.get_chat_history(limit=10)
        except Exception:
            history = []
        
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "user_message": message,
            "error": "Failed to process your message. Please try again.",
            "history": history
        })

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


def is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except (OSError, socket.error):
        return False

def find_available_port(host: str, preferred_port: int, max_attempts: int = 10) -> Optional[int]:
    """Find an available port starting from the preferred port"""
    # First, try the preferred port
    if is_port_available(host, preferred_port):
        return preferred_port
    
    logger.warning(f"Port {preferred_port} is not available, searching for alternatives...")
    
    # Try ports in a reasonable range around the preferred port
    for offset in range(1, max_attempts):
        candidate_port = preferred_port + offset
        if candidate_port > 65535:  # Max port number
            continue
            
        if is_port_available(host, candidate_port):
            logger.info(f"Found available port: {candidate_port}")
            return candidate_port
    
    # If no port found in the preferred range, try some common fallback ports
    fallback_ports = [3000, 5000, 8080, 8888, 9000]
    for fallback_port in fallback_ports:
        if fallback_port != preferred_port and is_port_available(host, fallback_port):
            logger.info(f"Using fallback port: {fallback_port}")
            return fallback_port
    
    return None

# Development server runner
def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the development server with automatic port conflict resolution"""
    log_level = "debug" if debug else "info"
    
    # Find an available port
    available_port = find_available_port(host, port)
    
    if available_port is None:
        logger.error(f"Could not find an available port starting from {port}")
        raise RuntimeError(f"No available ports found for binding on {host}")
    
    if available_port != port:
        logger.info(f"Port {port} was not available, using port {available_port} instead")
    
    logger.info(f"Starting Lifeboard API server on {host}:{available_port}")
    
    # Store server info for the startup banner
    _server_info["host"] = host
    _server_info["port"] = available_port
    
    try:
        import threading
        import time
        
        def delayed_banner():
            # Wait for uvicorn to fully start and print its messages
            time.sleep(2)
            print_startup_banner(host, available_port)
        
        # Start the banner in a separate thread
        banner_thread = threading.Thread(target=delayed_banner)
        banner_thread.daemon = True
        banner_thread.start()
        
        uvicorn.run(
            "api.server:app",
            host=host,
            port=available_port,
            log_level=log_level,
            reload=debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lifeboard API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port, debug=args.debug)