"""
Refactored FastAPI server with modular architecture.

This is the cleaned-up server that delegates complex operations to specialized
core components for improved maintainability and testability.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Import route modules
from api.routes import (
    calendar,
    chat,
    documents,
    embeddings,
    headings,
    health,
    llm,
    settings,
    sync,
    sync_status,
    system,
    weather,
    websocket,
)
from config.factory import create_production_config
from core.dependencies import get_dependency_registry
from core.frontend_orchestrator import FrontendConfig, FrontendOrchestrator
from core.process_manager import ProcessManager
from core.signal_handler import SignalHandler
from services.startup import StartupService, get_startup_service

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

# Global instances
_process_manager = ProcessManager()
_signal_handler = SignalHandler()
_frontend_orchestrator = FrontendOrchestrator()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    _signal_handler.setup_handlers()
    _signal_handler.set_callbacks({
        "process_cleanup": _process_manager.cleanup_all_processes,
        "frontend_cleanup": _frontend_orchestrator.stop_server,
    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    try:
        setup_signal_handlers()
        startup_service = get_startup_service()
        if startup_service:
            logger.info("LIFESPAN: Application starting up...")
            await startup_service.initialize()
            logger.info("LIFESPAN: Application startup complete")
        yield
    finally:
        logger.info("LIFESPAN: Application shutting down...")
        _frontend_orchestrator.stop_server()
        _process_manager.cleanup_all_processes()
        if startup_service:
            await startup_service.shutdown()
        logger.info("LIFESPAN: Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Lifeboard API",
        description="Interactive reflection space and AI-powered planning assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include route modules with /api prefix
    routers = [health, sync, sync_status, chat, documents, embeddings, llm, 
               system, calendar, weather, headings, settings]
    for router_module in routers:
        app.include_router(router_module.router, prefix="/api")
    app.include_router(websocket.router)

    @app.get("/")
    async def root():
        return {"message": "Lifeboard API", "version": "1.0.0"}

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse("static/favicon.ico")

    return app


def get_startup_service_dependency() -> StartupService:
    """Dependency injection for startup service."""
    return get_startup_service()


async def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the API server."""
    app = create_app()
    
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info" if not debug else "debug",
        access_log=debug,
    )
    
    server = uvicorn.Server(config)
    await server.serve()


async def run_full_stack(
    host: str = "0.0.0.0",
    backend_port: int = 8000,
    frontend_port: int = 5173,
    no_frontend: bool = False,
):
    """Run the full stack application with frontend and backend."""
    try:
        # Start frontend if enabled
        if not no_frontend:
            logger.info("Starting frontend server...")
            frontend_config = FrontendConfig(
                frontend_port=frontend_port,
                backend_port=backend_port,
                host=host,
            )
            
            result = _frontend_orchestrator.orchestrate_startup(frontend_config)
            if not result["success"]:
                logger.error(f"Frontend startup failed: {result.get('error')}")
                logger.info("Starting backend only...")
            else:
                logger.info(f"Frontend started on port {result['port']}")
        
        # Start backend server
        logger.info(f"Starting backend server on {host}:{backend_port}")
        await run_server(host=host, port=backend_port)
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        # Cleanup handled by lifespan context manager
        pass


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Lifeboard Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--no-frontend", action="store_true")
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    asyncio.run(run_full_stack(
        host=args.host,
        backend_port=args.port,
        frontend_port=args.frontend_port,
        no_frontend=args.no_frontend,
    ))


if __name__ == "__main__":
    main()