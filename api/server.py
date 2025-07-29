"""
Main FastAPI server with modular route organization

This is the refactored server that uses separate route modules
for better organization and maintainability.
"""

import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from services.startup import get_startup_service, StartupService
from services.sync_manager_service import SyncManagerService
from services.chat_service import ChatService
from config.factory import create_production_config

# Import route modules
from api.routes import health, sync, chat, embeddings, system, calendar, weather

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Signal handling for debugging
def signal_handler(signum, frame):
    """Handle signals and log them"""
    logger.warning(f"SIGNAL: Received signal {signum} ({signal.Signals(signum).name})")
    logger.warning(f"SIGNAL: Frame: {frame}")
    logger.warning(f"SIGNAL: Frame info: file={frame.f_code.co_filename}, line={frame.f_lineno}, function={frame.f_code.co_name}")
    logger.warning("SIGNAL: This may be causing the application to shut down")
    # Don't actually handle the signal, just log it
    
# Register signal handlers for common signals
signals_to_monitor = [signal.SIGTERM, signal.SIGINT]
if hasattr(signal, 'SIGHUP'):
    signals_to_monitor.append(signal.SIGHUP)
if hasattr(signal, 'SIGQUIT'):
    signals_to_monitor.append(signal.SIGQUIT)
if hasattr(signal, 'SIGUSR1'):
    signals_to_monitor.append(signal.SIGUSR1)
if hasattr(signal, 'SIGUSR2'):
    signals_to_monitor.append(signal.SIGUSR2)

for sig in signals_to_monitor:
    signal.signal(sig, signal_handler)
    logger.info(f"SIGNAL: Registered handler for {signal.Signals(sig).name} ({sig})")


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
    chat.get_chat_service_dependency = get_chat_service
    chat.set_templates(templates)
    
    # Calendar routes
    calendar.get_startup_service_dependency = get_startup_service_dependency
    calendar.set_templates(templates)
    
    # Embeddings routes
    embeddings.get_startup_service_dependency = get_startup_service_dependency
    
    # Weather routes (using its own dependency pattern)
    # Note: Weather routes use their own dependency injection pattern


# Lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    startup_success = False
    try:
        logger.info("=" * 60)
        logger.info("LIFESPAN: Starting Lifeboard API server...")
        logger.info(f"LIFESPAN: Current working directory: {os.getcwd()}")
        logger.info(f"LIFESPAN: Process ID: {os.getpid()}")
        
        # Initialize application
        from services.startup import initialize_application
        config = create_production_config()
        
        logger.info("LIFESPAN: About to initialize application...")
        result = await initialize_application(config, enable_auto_sync=True)
        
        if result["success"]:
            startup_success = True
            logger.info("LIFESPAN: Application initialized successfully")
            logger.info("LIFESPAN: Entering yield phase - server is now ready")
        else:
            logger.error(f"LIFESPAN: Application initialization failed: {result.get('errors', [])}")
            logger.error("LIFESPAN: Server will continue but may not function properly")
    
    except Exception as e:
        logger.error(f"LIFESPAN: Failed to initialize application on startup: {e}")
        logger.exception("LIFESPAN: Full exception details:")
    
    logger.info("LIFESPAN: *** YIELD POINT REACHED - Server should now stay running ***")
    
    try:
        logger.info("LIFESPAN: Entering yield block - server will run until signal received")
        yield  # Server runs here
        logger.info("LIFESPAN: Yield block exited normally (this should not happen unless shutdown)")
    except KeyboardInterrupt as e:
        logger.warning(f"LIFESPAN: KeyboardInterrupt received: {e}")
    except SystemExit as e:
        logger.warning(f"LIFESPAN: SystemExit received: {e}")
    except Exception as e:
        logger.error(f"LIFESPAN: Exception during yield phase: {e}")
        logger.exception("LIFESPAN: Full yield exception details:")
    finally:
        logger.info("LIFESPAN: *** YIELD PHASE ENDED - Shutdown triggered ***")
    
    # Shutdown
    try:
        logger.info("LIFESPAN: *** SHUTDOWN PHASE STARTED ***")
        logger.info("LIFESPAN: Shutting down Lifeboard API server...")
        
        from services.startup import shutdown_application
        await shutdown_application()
        
        logger.info("LIFESPAN: Application shutdown completed")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"LIFESPAN: Error during application shutdown: {e}")
        logger.exception("LIFESPAN: Full shutdown exception details:")


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
app.include_router(calendar.router)
app.include_router(embeddings.router)
app.include_router(system.router)
app.include_router(weather.router)


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


# Development server runner
def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the development server"""
    log_level = "debug" if debug else "info"
    
    logger.info(f"UVICORN: Starting server on {host}:{port}")
    logger.info(f"UVICORN: Debug mode: {debug}")
    logger.info(f"UVICORN: Log level: {log_level}")
    logger.info(f"UVICORN: Reload: {debug}")
    
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=debug
    )
    
    logger.info("UVICORN: Server has stopped running")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lifeboard API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port, debug=args.debug)