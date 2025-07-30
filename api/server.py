"""
Main FastAPI server with modular route organization

This is the refactored server that uses separate route modules
for better organization and maintainability.
"""

import logging
import os
import signal
import sys
import asyncio
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

# Initialize templates with absolute path
templates_dir = project_root / "templates"
logger.info(f"SERVER: Templates directory: {templates_dir}")
logger.info(f"SERVER: Templates directory exists: {templates_dir.exists()}")

if not templates_dir.exists():
    logger.error(f"SERVER: Templates directory not found: {templates_dir}")
    raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

templates = Jinja2Templates(directory=str(templates_dir))

# Verify critical template files exist
chat_template = templates_dir / "chat.html"
if not chat_template.exists():
    logger.error(f"SERVER: chat.html template not found: {chat_template}")
    raise FileNotFoundError(f"chat.html template not found: {chat_template}")

logger.info("SERVER: Templates initialized successfully")

# Global shutdown flag
_shutdown_requested = False
_server_instance = None

# Signal handling for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_requested, _server_instance
    
    signal_name = signal.Signals(signum).name if hasattr(signal.Signals, '__getitem__') else str(signum)
    logger.info(f"SIGNAL: Received shutdown signal {signal_name} ({signum})")
    logger.info(f"SIGNAL: Initiating graceful shutdown...")
    
    _shutdown_requested = True
    
    # If this is SIGINT (CTRL-C), handle it gracefully
    if signum == signal.SIGINT:
        logger.info("SIGNAL: CTRL-C detected - starting graceful shutdown")
        print("\n\n🛑 Graceful shutdown initiated... Please wait for cleanup to complete.")
        print("⏳ Shutting down services and releasing port bindings...")
        
        # Trigger uvicorn shutdown if server instance is available
        if _server_instance:
            logger.info("SIGNAL: Triggering uvicorn server shutdown...")
            try:
                _server_instance.should_exit = True
                if hasattr(_server_instance, 'force_exit'):
                    _server_instance.force_exit = False  # Graceful shutdown, not forced
                logger.info("SIGNAL: Uvicorn shutdown signal sent")
            except Exception as e:
                logger.error(f"SIGNAL: Error triggering uvicorn shutdown: {e}")
        else:
            logger.warning("SIGNAL: No server instance available to shutdown")
    
    # For other signals, just set the flag
    elif signum == signal.SIGTERM:
        logger.info("SIGNAL: SIGTERM received - initiating shutdown")
        if _server_instance:
            _server_instance.should_exit = True

# Setup graceful shutdown handling
def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    # Handle SIGINT (CTRL-C) and SIGTERM gracefully
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("SIGNAL: Registered graceful shutdown handlers for SIGINT and SIGTERM")
    
    # Optional: Handle other signals for logging only
    optional_signals = []
    if hasattr(signal, 'SIGHUP'):
        optional_signals.append(signal.SIGHUP)
    if hasattr(signal, 'SIGQUIT'):
        optional_signals.append(signal.SIGQUIT)
    
    def log_only_handler(signum, frame):
        signal_name = signal.Signals(signum).name if hasattr(signal.Signals, '__getitem__') else str(signum)
        logger.info(f"SIGNAL: Received {signal_name} ({signum}) - logging only")
    
    for sig in optional_signals:
        try:
            signal.signal(sig, log_only_handler)
            logger.debug(f"SIGNAL: Registered logging handler for {signal.Signals(sig).name} ({sig})")
        except (OSError, ValueError):
            # Some signals might not be available on all platforms
            pass

# Signal handlers will be configured by uvicorn server function
# setup_signal_handlers()  # Disabled - handled by uvicorn runner


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
    logger.info("ROUTE_CONFIG: Starting route dependency configuration...")
    
    # Health routes
    health.get_startup_service_dependency = get_startup_service_dependency
    logger.debug("ROUTE_CONFIG: Health routes configured")
    
    # Sync routes
    sync.get_startup_service_dependency = get_startup_service_dependency
    sync.get_sync_manager_dependency = get_sync_manager
    logger.debug("ROUTE_CONFIG: Sync routes configured")
    
    # Chat routes - ensure proper order of dependency injection
    logger.info("ROUTE_CONFIG: Configuring chat route dependencies...")
    
    # First, set templates
    try:
        chat.set_templates(templates)
        logger.debug("ROUTE_CONFIG: Templates configured for chat routes")
    except Exception as template_error:
        logger.error(f"ROUTE_CONFIG: Failed to set chat templates: {template_error}")
        raise
    
    # Then, set chat service instance
    startup_service = get_startup_service()
    logger.info(f"ROUTE_CONFIG: Retrieved startup service: {startup_service is not None}")
    
    if startup_service:
        logger.info(f"ROUTE_CONFIG: Startup service type: {type(startup_service)}")
        has_chat_attr = hasattr(startup_service, 'chat_service')
        logger.info(f"ROUTE_CONFIG: Startup service has chat_service attribute: {has_chat_attr}")
        
        if has_chat_attr:
            chat_service = startup_service.chat_service
            logger.info(f"ROUTE_CONFIG: Chat service instance: {chat_service is not None}")
            if chat_service:
                logger.info(f"ROUTE_CONFIG: Chat service type: {type(chat_service)}")
                
        if startup_service.chat_service:
            try:
                chat.set_chat_service_instance(startup_service.chat_service)
                logger.info("ROUTE_CONFIG: Chat service dependency configured successfully")
            except Exception as chat_config_error:
                logger.error(f"ROUTE_CONFIG: Failed to set chat service instance: {chat_config_error}")
                logger.exception("ROUTE_CONFIG: Chat service configuration exception:")
        else:
            logger.error("ROUTE_CONFIG: Chat service is None in startup service")
    else:
        logger.error("ROUTE_CONFIG: Startup service is None - cannot configure chat routes")
    
    logger.debug("ROUTE_CONFIG: Chat route dependency configuration completed")
    
    # Calendar routes
    calendar.get_startup_service_dependency = get_startup_service_dependency
    calendar.set_templates(templates)
    logger.debug("ROUTE_CONFIG: Calendar routes configured")
    
    # Embeddings routes
    embeddings.get_startup_service_dependency = get_startup_service_dependency
    logger.debug("ROUTE_CONFIG: Embeddings routes configured")
    
    # Weather routes (using its own dependency pattern)
    # Note: Weather routes use their own dependency injection pattern
    logger.debug("ROUTE_CONFIG: Weather routes use own dependency pattern")
    
    logger.info("ROUTE_CONFIG: Route dependency configuration completed")


# Global task monitor
def setup_asyncio_exception_handler():
    """Set up global asyncio exception handler to catch unhandled exceptions"""
    def exception_handler(loop, context):
        exception = context.get('exception')
        if exception:
            logger.error(f"ASYNCIO: Unhandled exception in asyncio task: {exception}")
            logger.error(f"ASYNCIO: Exception context: {context}")
            logger.exception("ASYNCIO: Full exception details:")
        else:
            logger.error(f"ASYNCIO: Unhandled error in asyncio: {context}")
    
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(exception_handler)
    logger.info("ASYNCIO: Exception handler configured")

def monitor_running_tasks():
    """Monitor and log all currently running asyncio tasks"""
    try:
        tasks = asyncio.all_tasks()
        logger.info(f"ASYNCIO: Currently running {len(tasks)} tasks")
        for i, task in enumerate(tasks):
            logger.debug(f"ASYNCIO: Task {i+1}: {task.get_name()} - {'done' if task.done() else 'running'}")
            if task.done() and task.exception():
                logger.error(f"ASYNCIO: Task {task.get_name()} failed with exception: {task.exception()}")
    except Exception as e:
        logger.error(f"ASYNCIO: Error monitoring tasks: {e}")

# Lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    startup_success = False
    startup_diagnostics = []
    
    try:
        logger.info("=" * 60)
        logger.info("LIFESPAN: Starting Lifeboard API server...")
        logger.info(f"LIFESPAN: Current working directory: {os.getcwd()}")
        logger.info(f"LIFESPAN: Process ID: {os.getpid()}")
        startup_diagnostics.append("Lifespan startup initiated")
        
        # Setup asyncio monitoring
        setup_asyncio_exception_handler()
        startup_diagnostics.append("Asyncio exception handler configured")
        
        # Check initial startup service state
        from services.startup import get_startup_service
        initial_service = get_startup_service()
        logger.info(f"LIFESPAN: Initial startup service state: {initial_service is not None}")
        startup_diagnostics.append(f"Initial startup service: {'available' if initial_service else 'None'}")
        
        # Initialize application
        from services.startup import initialize_application
        config = create_production_config()
        logger.info(f"LIFESPAN: Configuration created: {config is not None}")
        startup_diagnostics.append(f"Config created: {config is not None}")
        
        logger.info("LIFESPAN: About to initialize application...")
        startup_diagnostics.append("Calling initialize_application...")
        
        try:
            result = await initialize_application(config, enable_auto_sync=True)
            logger.info(f"LIFESPAN: Initialize_application returned: {result}")
            startup_diagnostics.append(f"Initialize result: {result}")
        except Exception as init_error:
            logger.error(f"LIFESPAN: Exception during initialize_application: {init_error}")
            logger.exception("LIFESPAN: Initialize_application exception details:")
            startup_diagnostics.append(f"Initialize exception: {init_error}")
            result = {"success": False, "errors": [str(init_error)]}
        
        # Check startup service state after initialization
        post_init_service = get_startup_service()
        logger.info(f"LIFESPAN: Post-init startup service state: {post_init_service is not None}")
        startup_diagnostics.append(f"Post-init startup service: {'available' if post_init_service else 'None'}")
        
        if result.get("success", False):
            startup_success = True
            logger.info("LIFESPAN: Application initialized successfully")
            startup_diagnostics.append("Application initialization successful")
            
            # Verify services are available
            if post_init_service:
                logger.info(f"LIFESPAN: Checking available services in startup service...")
                chat_available = hasattr(post_init_service, 'chat_service') and post_init_service.chat_service is not None
                db_available = hasattr(post_init_service, 'database') and post_init_service.database is not None
                logger.info(f"LIFESPAN: Chat service available: {chat_available}")
                logger.info(f"LIFESPAN: Database service available: {db_available}")
                startup_diagnostics.append(f"Chat service: {'available' if chat_available else 'missing'}")
                startup_diagnostics.append(f"Database service: {'available' if db_available else 'missing'}")
            
            # Configure route dependencies now that services are available
            logger.info("LIFESPAN: Configuring route dependencies...")
            startup_diagnostics.append("Configuring route dependencies...")
            
            try:
                configure_route_dependencies()
                logger.info("LIFESPAN: Route dependencies configured successfully")
                startup_diagnostics.append("Route dependencies configured successfully")
            except Exception as config_error:
                logger.error(f"LIFESPAN: Failed to configure route dependencies: {config_error}")
                logger.exception("LIFESPAN: Route dependency configuration exception:")
                startup_diagnostics.append(f"Route config failed: {config_error}")
            
            logger.info("LIFESPAN: Entering yield phase - server is now ready")
        else:
            logger.error(f"LIFESPAN: Application initialization failed: {result.get('errors', [])}")
            logger.error("LIFESPAN: Server will continue but may not function properly")
            startup_diagnostics.append(f"Initialization failed: {result.get('errors', [])}")
    
    except Exception as e:
        logger.error(f"LIFESPAN: Failed to initialize application on startup: {e}")
        logger.exception("LIFESPAN: Full exception details:")
        startup_diagnostics.append(f"Lifespan exception: {e}")
    
    # Log comprehensive startup diagnostics
    logger.info("LIFESPAN: *** STARTUP DIAGNOSTICS SUMMARY ***")
    for i, diagnostic in enumerate(startup_diagnostics, 1):
        logger.info(f"LIFESPAN: {i:2d}. {diagnostic}")
    logger.info("LIFESPAN: *** END STARTUP DIAGNOSTICS ***")
    
    # Write diagnostics to file for analysis
    diagnostics_file = "/Users/brucebookman/code/new_lifeboard/logs/startup_diagnostics.log"
    try:
        with open(diagnostics_file, "w") as f:
            f.write("=== STARTUP DIAGNOSTICS LOG ===\n")
            for diagnostic in startup_diagnostics:
                f.write(f"{diagnostic}\n")
            f.write(f"=== STARTUP SUCCESS: {startup_success} ===\n")
        logger.info(f"LIFESPAN: Diagnostics written to {diagnostics_file}")
    except Exception as diag_error:
        logger.error(f"LIFESPAN: Failed to write diagnostics: {diag_error}")
    
    logger.info("LIFESPAN: *** YIELD POINT REACHED - Server should now stay running ***")
    monitor_running_tasks()
    
    try:
        logger.info("LIFESPAN: Entering yield block - server will run until signal received")
        
        # Create a monitoring task to track asyncio health
        async def monitor_loop():
            global _shutdown_requested
            monitor_count = 0
            while not _shutdown_requested:
                await asyncio.sleep(30)  # Monitor every 30 seconds
                monitor_count += 1
                
                if _shutdown_requested:
                    logger.info("LIFESPAN: Shutdown requested - stopping monitoring loop")
                    break
                    
                monitor_running_tasks()
                logger.debug(f"LIFESPAN: Monitoring loop - server still running (check #{monitor_count})")
                
                # Check if server should exit (additional safety check)
                if hasattr(_server_instance, 'should_exit') and _server_instance and _server_instance.should_exit:
                    logger.info("LIFESPAN: Server should_exit flag detected - stopping monitoring")
                    break
                    
            logger.info("LIFESPAN: Monitoring loop stopped")
        
        monitor_task = asyncio.create_task(monitor_loop(), name="lifespan_monitor")
        
        try:
            yield  # Server runs here
            logger.info("LIFESPAN: Yield block exited - shutdown initiated")
        finally:
            logger.info("LIFESPAN: Entering shutdown cleanup...")
            logger.info("LIFESPAN: Cancelling monitoring task...")
            monitor_task.cancel()
            try:
                await asyncio.wait_for(monitor_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("LIFESPAN: Monitoring task cancelled successfully")
            except Exception as e:
                logger.warning(f"LIFESPAN: Error cancelling monitoring task: {e}")
    
    except KeyboardInterrupt as e:
        logger.warning(f"LIFESPAN: KeyboardInterrupt received: {e}")
    except SystemExit as e:
        logger.warning(f"LIFESPAN: SystemExit received: {e}")
    except Exception as e:
        logger.error(f"LIFESPAN: Exception during yield phase: {e}")
        logger.exception("LIFESPAN: Full yield exception details:")
    finally:
        logger.info("LIFESPAN: *** YIELD PHASE ENDED - Shutdown triggered ***")
        monitor_running_tasks()
    
    # Shutdown
    shutdown_success = False
    try:
        logger.info("LIFESPAN: *** SHUTDOWN PHASE STARTED ***")
        logger.info("LIFESPAN: Shutting down Lifeboard API server...")
        
        # Cancel any remaining asyncio tasks
        logger.info("LIFESPAN: Cancelling remaining asyncio tasks...")
        tasks = [task for task in asyncio.all_tasks() if not task.done() and task != asyncio.current_task()]
        if tasks:
            logger.info(f"LIFESPAN: Found {len(tasks)} tasks to cancel")
            for task in tasks:
                task.cancel()
                logger.debug(f"LIFESPAN: Cancelled task: {task.get_name()}")
            
            # Wait for tasks to complete cancellation
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10.0)
                logger.info("LIFESPAN: All tasks cancelled successfully")
            except asyncio.TimeoutError:
                logger.warning("LIFESPAN: Timeout waiting for task cancellation - proceeding with shutdown")
            except Exception as task_error:
                logger.warning(f"LIFESPAN: Error during task cancellation: {task_error}")
        else:
            logger.info("LIFESPAN: No additional tasks to cancel")
        
        # Shutdown application services
        logger.info("LIFESPAN: Shutting down application services...")
        from services.startup import shutdown_application
        await asyncio.wait_for(shutdown_application(), timeout=15.0)
        
        shutdown_success = True
        logger.info("LIFESPAN: Application shutdown completed successfully")
        logger.info("LIFESPAN: Port bindings have been released")
        logger.info("=" * 60)
    
    except asyncio.TimeoutError:
        logger.error("LIFESPAN: Shutdown timeout - forcing cleanup")
        logger.error("LIFESPAN: Some resources may not have been properly released")
    except Exception as e:
        logger.error(f"LIFESPAN: Error during application shutdown: {e}")
        logger.exception("LIFESPAN: Full shutdown exception details:")
    finally:
        if shutdown_success:
            logger.info("LIFESPAN: Graceful shutdown completed")
        else:
            logger.warning("LIFESPAN: Shutdown completed with warnings/errors")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Lifeboard API",
    description="API for Lifeboard personal data management system",
    version="1.0.0",
    lifespan=lifespan
)

# Route dependencies will be configured after services are initialized in lifespan

# Include route modules
app.include_router(health.router)
app.include_router(sync.router)
app.include_router(chat.router)
app.include_router(calendar.router)
app.include_router(embeddings.router)
app.include_router(system.router)
app.include_router(weather.router)
app.include_router(sync.router)


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


# Process management utilities
def find_server_processes_basic():
    """Basic process detection using pgrep (fallback when psutil unavailable)"""
    import subprocess
    
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*api/server.py'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
            return pids
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    
    return []

def find_server_processes():
    """Find existing server processes"""
    try:
        import psutil
    except ImportError:
        logger.warning("PROCESS: psutil not available - using basic process detection")
        return find_server_processes_basic()
    
    import os
    
    server_processes = []
    current_pid = os.getpid()  # Don't include current process
    
    try:
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if (cmdline and 
                    len(cmdline) >= 2 and
                    'python' in cmdline[0] and 
                    'api/server.py' in ' '.join(cmdline) and
                    proc.info['pid'] != current_pid):
                    server_processes.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.warning(f"PROCESS: Error finding server processes: {e}")
    
    return server_processes

def kill_existing_processes_basic(server_pids, graceful_timeout: int = 10):
    """Basic process termination without psutil"""
    import subprocess
    import time
    
    if not server_pids:
        return True
    
    # Step 1: Send SIGTERM
    for pid in server_pids:
        try:
            subprocess.run(['kill', '-TERM', str(pid)], timeout=5)
            logger.info(f"PROCESS: Sent SIGTERM to process {pid}")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            logger.warning(f"PROCESS: Error sending SIGTERM to {pid}: {e}")
    
    # Step 2: Wait and check
    time.sleep(graceful_timeout)
    
    # Step 3: Check what's still running
    remaining_pids = find_server_processes_basic()
    still_running = [pid for pid in server_pids if pid in remaining_pids]
    
    # Step 4: Force kill if needed
    if still_running:
        logger.warning(f"PROCESS: Force killing {len(still_running)} remaining processes")
        for pid in still_running:
            try:
                subprocess.run(['kill', '-KILL', str(pid)], timeout=5)
                logger.info(f"PROCESS: Sent SIGKILL to process {pid}")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                logger.error(f"PROCESS: Error sending SIGKILL to {pid}: {e}")
    
    # Final verification
    final_check = find_server_processes_basic()
    remaining_after_kill = [pid for pid in server_pids if pid in final_check]
    
    if remaining_after_kill:
        logger.error(f"PROCESS: {len(remaining_after_kill)} processes still running: {remaining_after_kill}")
        return False
    else:
        logger.info("PROCESS: All processes terminated successfully")
        return True

def kill_existing_processes(graceful_timeout: int = 10):
    """Kill existing server processes gracefully then forcefully if needed"""
    server_pids = find_server_processes()
    if not server_pids:
        logger.info("PROCESS: No existing server processes found")
        return True
    
    logger.info(f"PROCESS: Found {len(server_pids)} existing server processes: {server_pids}")
    
    try:
        import psutil
    except ImportError:
        logger.warning("PROCESS: psutil not available - using basic process termination")
        return kill_existing_processes_basic(server_pids, graceful_timeout)
    
    import time
    
    # Step 1: Send SIGTERM for graceful shutdown
    terminated_processes = []
    for pid in server_pids:
        try:
            proc = psutil.Process(pid)
            logger.info(f"PROCESS: Sending SIGTERM to process {pid}")
            proc.terminate()
            terminated_processes.append(proc)
        except psutil.NoSuchProcess:
            logger.debug(f"PROCESS: Process {pid} already gone")
        except psutil.AccessDenied:
            logger.warning(f"PROCESS: Access denied to terminate process {pid}")
        except Exception as e:
            logger.error(f"PROCESS: Error terminating process {pid}: {e}")
    
    # Step 2: Wait for graceful shutdown
    if terminated_processes:
        logger.info(f"PROCESS: Waiting up to {graceful_timeout}s for graceful shutdown...")
        try:
            psutil.wait_procs(terminated_processes, timeout=graceful_timeout)
            logger.info("PROCESS: All processes terminated gracefully")
        except psutil.TimeoutExpired as e:
            logger.warning(f"PROCESS: {len(e.alive)} processes didn't terminate gracefully")
            
            # Step 3: Force kill remaining processes
            for proc in e.alive:
                try:
                    logger.warning(f"PROCESS: Force killing process {proc.pid}")
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
                except Exception as kill_error:
                    logger.error(f"PROCESS: Error force killing process {proc.pid}: {kill_error}")
    
    # Verify cleanup
    remaining_pids = find_server_processes()
    if remaining_pids:
        logger.error(f"PROCESS: {len(remaining_pids)} processes still running: {remaining_pids}")
        return False
    else:
        logger.info("PROCESS: All existing server processes terminated successfully")
        return True

# Development server runner
def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False, kill_existing: bool = False):
    """Run the development server with enhanced port conflict detection and cleanup"""
    import socket
    
    # Kill existing processes if requested
    if kill_existing:
        logger.info("PROCESS: Killing existing server processes...")
        if not kill_existing_processes():
            logger.error("PROCESS: Failed to clean up all existing processes")
            print("❌ Failed to clean up existing processes. Some may still be running.")
            print("💡 Try running with sudo or check for processes manually with: ps aux | grep server.py")
            return
        else:
            print("✅ Existing server processes cleaned up successfully")
    
    # Check if port is already in use
    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return False
            except OSError:
                return True
    
    # Check for port conflicts
    if is_port_in_use(port):
        logger.error(f"UVICORN: Port {port} is already in use!")
        
        # Show what's using the port
        try:
            import subprocess
            result = subprocess.run(['lsof', '-i', f':{port}'], 
                                 capture_output=True, text=True, timeout=5)
            if result.stdout:
                logger.error(f"UVICORN: Process using port {port}:")
                for line in result.stdout.strip().split('\n'):
                    logger.error(f"UVICORN:   {line}")
                
                # Try to detect if it's one of our server processes
                server_pids = find_server_processes()
                if server_pids:
                    logger.warning(f"UVICORN: Detected {len(server_pids)} existing server processes")
                    print("\n💡 Suggestions:")
                    print("  • Use --kill-existing to automatically clean up old processes")
                    print("  • Use --auto-port to automatically find an available port")
                    print(f"  • Use --port {port + 1} to try a different port")
                    print("  • Run: ./start_server.sh --kill-existing")
                else:
                    logger.error(f"UVICORN: Port {port} is used by another application")
                    print("\n💡 Suggestions:")
                    print(f"  • Use --port {port + 1} to try a different port")
                    print("  • Use --auto-port to automatically find an available port")
        except Exception as e:
            logger.debug(f"UVICORN: Error checking port usage: {e}")
            print("\n💡 Suggestions:")
            print("  • Use --kill-existing to clean up any old server processes")
            print("  • Use --auto-port to automatically find an available port")
            print(f"  • Use --port {port + 1} to try a different port")
        
        return
    
    log_level = "debug" if debug else "info"
    
    # Enhanced startup logging
    logger.info("=" * 60)
    logger.info(f"UVICORN: Starting Lifeboard API server")
    logger.info(f"UVICORN: Host: {host}")
    logger.info(f"UVICORN: Port: {port}")
    logger.info(f"UVICORN: Debug mode: {debug}")
    logger.info(f"UVICORN: Log level: {log_level}")
    logger.info(f"UVICORN: Reload: {debug}")
    logger.info(f"UVICORN: Process cleanup: {'enabled' if kill_existing else 'disabled'}")
    logger.info("=" * 60)
    
    # User-friendly console output
    print(f"\n🚀 Starting Lifeboard API server...")
    print(f"📍 Server will be available at: http://{host}:{port}")
    print(f"📋 Process ID: {os.getpid()}")
    if debug:
        print("🐛 Debug mode: ON")
    print("\n💡 Press CTRL+C to stop the server gracefully\n")
    
    try:
        # Configure uvicorn for graceful shutdown
        config = uvicorn.Config(
            "api.server:app",
            host=host,
            port=port,
            log_level=log_level,
            reload=debug,
            # Enable graceful shutdown with timeout
            timeout_graceful_shutdown=30,  # 30 seconds for graceful shutdown
            timeout_keep_alive=5
        )
        server = uvicorn.Server(config)
        
        # Store server instance for potential external shutdown
        global _server_instance
        _server_instance = server
        logger.info(f"UVICORN: Server instance stored for graceful shutdown")
        logger.info(f"UVICORN: Server starting with graceful shutdown timeout: 30s")
        
        print("✅ Server configuration complete")
        print("⏳ Initializing application services...")
        
        # Install custom signal handlers that work with uvicorn
        original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
        original_sigterm_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        
        def uvicorn_signal_handler(signum, frame):
            """Signal handler that properly triggers uvicorn shutdown"""
            signal_name = signal.Signals(signum).name
            logger.info(f"UVICORN: Received {signal_name} - initiating graceful shutdown")
            print(f"\n\n🛑 Graceful shutdown initiated by {signal_name}...")
            print("⏳ Shutting down services and releasing port bindings...")
            
            # Set the shutdown flag and trigger uvicorn shutdown
            global _shutdown_requested
            _shutdown_requested = True
            server.should_exit = True
            
            # For SIGINT, we want graceful shutdown
            if signum == signal.SIGINT:
                server.force_exit = False
            # For SIGTERM, also graceful but faster
            elif signum == signal.SIGTERM:
                server.force_exit = False
        
        # Install our custom handlers
        signal.signal(signal.SIGINT, uvicorn_signal_handler)
        signal.signal(signal.SIGTERM, uvicorn_signal_handler)
        
        try:
            server.run()
        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint_handler)
            signal.signal(signal.SIGTERM, original_sigterm_handler)
        
    except KeyboardInterrupt:
        logger.info("UVICORN: KeyboardInterrupt received - server shutting down gracefully")
        print("\n\n🛑 Graceful shutdown completed")
        print("✅ Server stopped successfully")
        print("🔓 Port bindings have been released")
        print("📋 Server can be restarted safely")
    except Exception as e:
        logger.error(f"UVICORN: Server failed to start: {e}")
        if "address already in use" in str(e).lower():
            logger.error(f"UVICORN: Port {port} became unavailable during startup")
            logger.error(f"UVICORN: Try killing existing processes: pkill -f 'python.*server.py'")
        raise
    finally:
        logger.info("UVICORN: Server has stopped running")
        logger.info("=" * 60)
        print("\n🏁 Lifeboard API server stopped")
        print("👋 Thank you for using Lifeboard!\n")


def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port"""
    import socket
    
    logger.info(f"PORT: Searching for available port starting from {start_port}")
    
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                logger.info(f"PORT: Found available port {port}")
                return port
            except OSError:
                logger.debug(f"PORT: Port {port} is in use, trying next")
                continue
    
    error_msg = f"No available ports found in range {start_port}-{start_port + max_attempts}"
    logger.error(f"PORT: {error_msg}")
    raise RuntimeError(error_msg)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lifeboard API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--auto-port", action="store_true", 
                       help="Automatically find an available port starting from --port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--kill-existing", action="store_true", 
                       help="Kill existing server processes before starting")
    
    args = parser.parse_args()
    
    port = args.port
    if args.auto_port:
        try:
            port = find_available_port(args.port)
            print(f"Using available port: {port}")
        except RuntimeError as e:
            print(f"Error: {e}")
            exit(1)
    
    run_server(host=args.host, port=port, debug=args.debug, kill_existing=args.kill_existing)