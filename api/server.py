"""
Main FastAPI server with modular route organization

This is the refactored server that uses separate route modules
for better organization and maintainability.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import signal
import subprocess
import time

from services.startup import get_startup_service, StartupService
from services.sync_manager_service import SyncManagerService
from services.chat_service import ChatService
from config.factory import create_production_config

# Import route modules
from api.routes import health, sync, chat, embeddings, system, calendar

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="templates")


# Dependency functions
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


# Configure dependencies in route modules
def configure_route_dependencies():
    """Configure dependency injection for route modules"""
    # Health routes
    health.get_startup_service_dependency = get_startup_service_dependency
    
    # Sync routes
    sync.get_startup_service_dependency = get_startup_service_dependency
    sync.get_sync_manager_dependency = get_sync_manager
    
    # Chat routes
    chat.set_templates(templates)
    
    # Embeddings routes
    embeddings.get_startup_service_dependency = get_startup_service_dependency


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

# Configure route dependencies
configure_route_dependencies()

# Include route modules
app.include_router(health.router)
app.include_router(sync.router)
app.include_router(chat.router)
app.include_router(embeddings.router)
app.include_router(system.router)
app.include_router(calendar.router)


# Global error handlers
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


def release_port_if_needed(port: int):
    """
    Check if a port is in use and, if so, terminate the process using it.
    """
    logger.info(f"Checking if port {port} is in use...")
    command = f"lsof -ti :{port}"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        pids = result.stdout.strip().split()
        if not pids:
            logger.info(f"Port {port} is free.")
            return

        for pid_str in pids:
            try:
                pid = int(pid_str)
                logger.warning(f"Port {port} is in use by PID {pid}. Terminating process...")
                os.kill(pid, signal.SIGTERM)
                time.sleep(1) # Give the process a moment to terminate
                logger.info(f"Process {pid} terminated.")
            except (ValueError, ProcessLookupError) as e:
                logger.warning(f"Could not terminate process {pid_str}: {e}")

    except Exception as e:
        logger.error(f"An error occurred while checking port {port}: {e}")


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

    release_port_if_needed(args.port)
    
    run_server(host=args.host, port=args.port, debug=args.debug)