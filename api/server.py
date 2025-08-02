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
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from datetime import datetime

from services.startup import get_startup_service, StartupService
from services.sync_manager_service import SyncManagerService
from services.chat_service import ChatService
from config.factory import create_production_config
from core.dependencies import get_dependency_registry

# Import route modules
from api.routes import health, sync, chat, embeddings, system, calendar, weather, settings

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

# Signal handling for graceful shutdown with safety checks
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully with enhanced safety checks"""
    global _shutdown_requested, _server_instance
    
    # Safety check for signal number
    try:
        if hasattr(signal, 'Signals') and hasattr(signal.Signals, '__getitem__'):
            signal_name = signal.Signals(signum).name
        else:
            signal_name = f"signal-{signum}"
    except (ValueError, AttributeError):
        signal_name = f"unknown-signal-{signum}"
    
    logger.info(f"SIGNAL: Received shutdown signal {signal_name} ({signum})")
    logger.info(f"SIGNAL: Initiating graceful shutdown...")
    
    # Set shutdown flag atomically
    _shutdown_requested = True
    
    # Handle SIGINT (CTRL-C) specially
    if signum == signal.SIGINT:
        logger.info("SIGNAL: CTRL-C detected - starting graceful shutdown")
        try:
            print("\n\n🛑 Graceful shutdown initiated... Please wait for cleanup to complete.")
            print("⏳ Shutting down services and releasing port bindings...")
        except Exception as print_error:
            logger.debug(f"SIGNAL: Error printing shutdown message: {print_error}")
        
        # Trigger uvicorn shutdown if server instance is available
        if _server_instance is not None:
            logger.info("SIGNAL: Triggering uvicorn server shutdown...")
            try:
                # Safety checks before accessing server instance attributes
                if hasattr(_server_instance, 'should_exit'):
                    _server_instance.should_exit = True
                    logger.debug("SIGNAL: Set server.should_exit = True")
                else:
                    logger.warning("SIGNAL: Server instance has no 'should_exit' attribute")
                
                if hasattr(_server_instance, 'force_exit'):
                    _server_instance.force_exit = False  # Graceful shutdown, not forced
                    logger.debug("SIGNAL: Set server.force_exit = False")
                else:
                    logger.debug("SIGNAL: Server instance has no 'force_exit' attribute")
                
                logger.info("SIGNAL: Uvicorn shutdown signal sent successfully")
            except AttributeError as attr_error:
                logger.error(f"SIGNAL: Server instance missing expected attributes: {attr_error}")
            except Exception as e:
                logger.error(f"SIGNAL: Error triggering uvicorn shutdown: {e}")
                logger.exception("SIGNAL: Full exception details:")
        else:
            logger.warning("SIGNAL: No server instance available to shutdown")
    
    # Handle SIGTERM
    elif signum == signal.SIGTERM:
        logger.info("SIGNAL: SIGTERM received - initiating shutdown")
        if _server_instance is not None:
            try:
                if hasattr(_server_instance, 'should_exit'):
                    _server_instance.should_exit = True
                    logger.info("SIGNAL: Set server.should_exit = True for SIGTERM")
                else:
                    logger.warning("SIGNAL: Server instance has no 'should_exit' attribute for SIGTERM")
            except Exception as e:
                logger.error(f"SIGNAL: Error handling SIGTERM: {e}")
        else:
            logger.warning("SIGNAL: No server instance available for SIGTERM handling")
    
    # Handle other signals
    else:
        logger.info(f"SIGNAL: Received {signal_name} - setting shutdown flag only")
        # For other signals, we just set the shutdown flag and let the application handle it
    
    logger.debug(f"SIGNAL: Signal handler for {signal_name} completed successfully")

# Setup graceful shutdown handling with enhanced safety
def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown with enhanced safety checks"""
    logger.info("SIGNAL: Setting up signal handlers...")
    
    # Handle SIGINT (CTRL-C) and SIGTERM gracefully
    try:
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("SIGNAL: Registered graceful shutdown handler for SIGINT")
    except (OSError, ValueError) as e:
        logger.error(f"SIGNAL: Failed to register SIGINT handler: {e}")
    
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("SIGNAL: Registered graceful shutdown handler for SIGTERM")
    except (OSError, ValueError) as e:
        logger.error(f"SIGNAL: Failed to register SIGTERM handler: {e}")
    
    # Optional: Handle other signals for logging only with better error handling
    optional_signals = []
    
    # Check for platform-specific signals safely
    for signal_name in ['SIGHUP', 'SIGQUIT', 'SIGUSR1', 'SIGUSR2']:
        if hasattr(signal, signal_name):
            sig_value = getattr(signal, signal_name)
            optional_signals.append((signal_name, sig_value))
            logger.debug(f"SIGNAL: Found optional signal {signal_name} = {sig_value}")
    
    def log_only_handler(signum, frame):
        """Safe logging-only signal handler"""
        try:
            if hasattr(signal, 'Signals') and hasattr(signal.Signals, '__getitem__'):
                signal_name = signal.Signals(signum).name
            else:
                signal_name = f"signal-{signum}"
        except (ValueError, AttributeError):
            signal_name = f"unknown-signal-{signum}"
        
        logger.info(f"SIGNAL: Received {signal_name} ({signum}) - logging only")
    
    # Register optional signal handlers
    registered_optional = 0
    for signal_name, sig_value in optional_signals:
        try:
            signal.signal(sig_value, log_only_handler)
            logger.debug(f"SIGNAL: Registered logging handler for {signal_name} ({sig_value})")
            registered_optional += 1
        except (OSError, ValueError) as e:
            logger.debug(f"SIGNAL: Could not register handler for {signal_name}: {e}")
            # Some signals might not be available on all platforms - this is expected
        except Exception as e:
            logger.warning(f"SIGNAL: Unexpected error registering handler for {signal_name}: {e}")
    
    logger.info(f"SIGNAL: Successfully registered {registered_optional} optional signal handlers")
    logger.info("SIGNAL: Signal handler setup completed")

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


# Configure dependencies using the central registry
def configure_route_dependencies():
    """Configure dependency injection for route modules using central registry"""
    logger.info("ROUTE_CONFIG: Starting route dependency configuration...")
    
    # Get the dependency registry
    registry = get_dependency_registry()
    
    # Register providers in the dependency registry
    logger.info("ROUTE_CONFIG: Registering dependency providers...")
    registry.register_startup_service_provider(get_startup_service)
    registry.register_sync_manager_provider(lambda startup_service: startup_service.sync_manager)
    registry.register_chat_service_provider(lambda startup_service: startup_service.chat_service)
    logger.info("ROUTE_CONFIG: Dependency providers registered successfully")
    
    # Configure templates for routes that need them
    logger.info("ROUTE_CONFIG: Configuring templates...")
    try:
        chat.set_templates(templates)
        calendar.set_templates(templates)
        settings.set_templates(templates)
        logger.info("ROUTE_CONFIG: Templates configured successfully")
    except Exception as template_error:
        logger.error(f"ROUTE_CONFIG: Failed to configure templates: {template_error}")
        raise
    
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
                if (_server_instance is not None and 
                    hasattr(_server_instance, 'should_exit') and 
                    _server_instance.should_exit):
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
app.include_router(settings.router)


@app.get("/")
async def root():
    """Redirect to today's calendar day view"""
    today = datetime.now().strftime("%Y-%m-%d")
    return RedirectResponse(url=f"/calendar/day/{today}")


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
    import os
    
    current_pid = os.getpid()
    logger.debug(f"PROCESS: Finding server processes (excluding current PID {current_pid})")
    
    try:
        # Use more specific pattern and include command line args
        result = subprocess.run(['pgrep', '-f', 'python.*api/server.py'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            pids = []
            for pid_str in result.stdout.strip().split('\n'):
                if pid_str.strip():
                    try:
                        pid = int(pid_str.strip())
                        if pid != current_pid:  # Exclude current process
                            pids.append(pid)
                            logger.debug(f"PROCESS: Found server process PID {pid}")
                        else:
                            logger.debug(f"PROCESS: Skipping current process PID {pid}")
                    except ValueError:
                        logger.warning(f"PROCESS: Invalid PID format: '{pid_str.strip()}'")
                        continue
            
            # Verify processes are still running
            verified_pids = []
            for pid in pids:
                try:
                    # Try to send signal 0 to check if process exists
                    os.kill(pid, 0)
                    verified_pids.append(pid)
                    logger.debug(f"PROCESS: Verified PID {pid} is running")
                except (OSError, ProcessLookupError):
                    logger.debug(f"PROCESS: PID {pid} no longer exists")
                    continue
            
            logger.info(f"PROCESS: Found {len(verified_pids)} verified server processes")
            return verified_pids
        else:
            logger.debug(f"PROCESS: pgrep returned code {result.returncode}, no processes found")
    except subprocess.TimeoutExpired:
        logger.warning("PROCESS: pgrep command timed out")
    except subprocess.CalledProcessError as e:
        logger.debug(f"PROCESS: pgrep failed with return code {e.returncode}")
    except FileNotFoundError:
        logger.warning("PROCESS: pgrep command not found - trying alternative methods")
        return find_server_processes_alternative()
    except ValueError as e:
        logger.warning(f"PROCESS: Error parsing pgrep output: {e}")
    
    return []

def find_server_processes_alternative():
    """Alternative process detection when pgrep is unavailable"""
    import subprocess
    import os
    
    current_pid = os.getpid()
    logger.debug("PROCESS: Using alternative process detection (ps + grep)")
    
    try:
        # Use ps with grep as fallback
        ps_result = subprocess.run(['ps', 'aux'], 
                                 capture_output=True, text=True, timeout=10)
        if ps_result.returncode != 0:
            logger.warning("PROCESS: ps command failed")
            return []
        
        grep_result = subprocess.run(['grep', '-E', r'python.*api/server\.py'], 
                                   input=ps_result.stdout, 
                                   capture_output=True, text=True, timeout=5)
        
        if grep_result.returncode == 0:
            pids = []
            for line in grep_result.stdout.strip().split('\n'):
                if line.strip() and 'grep' not in line:  # Exclude grep process itself
                    try:
                        # Extract PID from ps output (second column)
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = int(parts[1])
                            if pid != current_pid:
                                pids.append(pid)
                                logger.debug(f"PROCESS: Found server process PID {pid} via ps")
                    except (ValueError, IndexError):
                        continue
            
            logger.info(f"PROCESS: Alternative method found {len(pids)} server processes")
            return pids
        
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"PROCESS: Alternative process detection failed: {e}")
    
    return []

def find_server_processes():
    """Find existing server processes with enhanced reliability"""
    try:
        import psutil
        logger.debug("PROCESS: Using psutil for process detection")
    except ImportError:
        logger.warning("PROCESS: psutil not available - using basic process detection")
        return find_server_processes_basic()
    
    import os
    
    server_processes = []
    current_pid = os.getpid()  # Don't include current process
    logger.debug(f"PROCESS: Searching for server processes (excluding current PID {current_pid})")
    
    try:
        # Get process iterator with more attributes for better filtering
        for proc in psutil.process_iter(['pid', 'cmdline', 'name', 'status']):
            try:
                proc_info = proc.info
                pid = proc_info['pid']
                cmdline = proc_info['cmdline']
                name = proc_info['name']
                status = proc_info['status']
                
                # Skip current process
                if pid == current_pid:
                    continue
                
                # Skip zombie processes
                if status == psutil.STATUS_ZOMBIE:
                    logger.debug(f"PROCESS: Skipping zombie process PID {pid}")
                    continue
                
                # Check if this is a Python process running our server
                if (cmdline and 
                    len(cmdline) >= 2 and
                    ('python' in name.lower() or 'python' in cmdline[0]) and 
                    any('api/server.py' in arg for arg in cmdline)):
                    
                    # Double-check the process is actually running
                    try:
                        if proc.is_running():
                            server_processes.append(pid)
                            logger.debug(f"PROCESS: Found server process PID {pid} (status: {status})")
                            logger.debug(f"PROCESS: Process cmdline: {' '.join(cmdline[:3])}...")
                        else:
                            logger.debug(f"PROCESS: PID {pid} not running, skipping")
                    except psutil.NoSuchProcess:
                        logger.debug(f"PROCESS: PID {pid} disappeared during check")
                        continue
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process disappeared or access denied - skip silently
                continue
            except Exception as e:
                logger.debug(f"PROCESS: Error checking process {proc_info.get('pid', 'unknown')}: {e}")
                continue
    
    except Exception as e:
        logger.warning(f"PROCESS: Error during psutil process iteration: {e}")
        logger.info("PROCESS: Falling back to basic process detection")
        return find_server_processes_basic()
    
    logger.info(f"PROCESS: Found {len(server_processes)} server processes using psutil")
    return server_processes

def kill_existing_processes_basic(server_pids, graceful_timeout: int = 10):
    """Basic process termination without psutil with enhanced reliability"""
    import subprocess
    import time
    import os
    
    if not server_pids:
        logger.info("PROCESS: No processes to terminate")
        return True
    
    logger.info(f"PROCESS: Terminating {len(server_pids)} processes: {server_pids}")
    
    # Step 1: Send SIGTERM for graceful shutdown
    sigterm_sent = []
    sigterm_failed = []
    
    for pid in server_pids:
        try:
            # Verify process exists before attempting to kill
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
            subprocess.run(['kill', '-TERM', str(pid)], timeout=5, check=True)
            sigterm_sent.append(pid)
            logger.info(f"PROCESS: Sent SIGTERM to process {pid}")
        except ProcessLookupError:
            logger.debug(f"PROCESS: Process {pid} already gone")
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # Process not found
                logger.debug(f"PROCESS: Process {pid} not found during SIGTERM")
            else:
                logger.warning(f"PROCESS: Error sending SIGTERM to {pid}: return code {e.returncode}")
                sigterm_failed.append(pid)
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"PROCESS: Error sending SIGTERM to {pid}: {e}")
            sigterm_failed.append(pid)
    
    if sigterm_sent:
        logger.info(f"PROCESS: Waiting {graceful_timeout}s for {len(sigterm_sent)} processes to terminate gracefully")
    
    # Step 2: Wait for graceful shutdown with progressive checking
    wait_interval = min(2, graceful_timeout // 5)  # Check every 2s or graceful_timeout/5, whichever is smaller
    total_waited = 0
    
    while total_waited < graceful_timeout and sigterm_sent:
        time.sleep(wait_interval)
        total_waited += wait_interval
        
        # Check which processes are still running
        still_running = []
        for pid in sigterm_sent:
            try:
                os.kill(pid, 0)  # Check if process still exists
                still_running.append(pid)
            except ProcessLookupError:
                logger.debug(f"PROCESS: Process {pid} terminated gracefully")
        
        sigterm_sent = still_running
        if not sigterm_sent:
            logger.info(f"PROCESS: All processes terminated gracefully after {total_waited}s")
            break
        else:
            logger.debug(f"PROCESS: {len(sigterm_sent)} processes still running after {total_waited}s")
    
    # Step 3: Force kill remaining processes
    all_remaining = sigterm_sent + sigterm_failed
    if all_remaining:
        logger.warning(f"PROCESS: Force killing {len(all_remaining)} remaining processes: {all_remaining}")
        
        for pid in all_remaining:
            try:
                os.kill(pid, 0)  # Check if process still exists
                subprocess.run(['kill', '-KILL', str(pid)], timeout=5, check=True)
                logger.info(f"PROCESS: Sent SIGKILL to process {pid}")
            except ProcessLookupError:
                logger.debug(f"PROCESS: Process {pid} already gone before SIGKILL")
            except subprocess.CalledProcessError as e:
                logger.error(f"PROCESS: Error sending SIGKILL to {pid}: return code {e.returncode}")
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.error(f"PROCESS: Error sending SIGKILL to {pid}: {e}")
        
        # Wait briefly for SIGKILL to take effect
        time.sleep(2)
    
    # Step 4: Final verification
    final_check = find_server_processes_basic()
    remaining_after_kill = [pid for pid in server_pids if pid in final_check]
    
    if remaining_after_kill:
        logger.error(f"PROCESS: {len(remaining_after_kill)} processes still running after termination attempts: {remaining_after_kill}")
        logger.error("PROCESS: Manual intervention may be required")
        return False
    else:
        logger.info("PROCESS: All processes terminated successfully")
        return True

def kill_existing_processes(graceful_timeout: int = 10):
    """Kill existing server processes gracefully then forcefully if needed with enhanced reliability"""
    server_pids = find_server_processes()
    if not server_pids:
        logger.info("PROCESS: No existing server processes found")
        return True
    
    logger.info(f"PROCESS: Found {len(server_pids)} existing server processes: {server_pids}")
    
    try:
        import psutil
        logger.debug("PROCESS: Using psutil for process termination")
    except ImportError:
        logger.warning("PROCESS: psutil not available - using basic process termination")
        return kill_existing_processes_basic(server_pids, graceful_timeout)
    
    import time
    
    # Step 1: Validate and send SIGTERM for graceful shutdown
    terminated_processes = []
    access_denied_pids = []
    already_gone_pids = []
    
    for pid in server_pids:
        try:
            proc = psutil.Process(pid)
            
            # Check if process is still our server process
            try:
                cmdline = proc.cmdline()
                if not (cmdline and any('api/server.py' in arg for arg in cmdline)):
                    logger.warning(f"PROCESS: PID {pid} no longer appears to be a server process, skipping")
                    continue
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass  # Will be handled below
            
            logger.info(f"PROCESS: Sending SIGTERM to process {pid} (status: {proc.status()})")
            proc.terminate()
            terminated_processes.append(proc)
            
        except psutil.NoSuchProcess:
            logger.debug(f"PROCESS: Process {pid} already gone")
            already_gone_pids.append(pid)
        except psutil.AccessDenied:
            logger.warning(f"PROCESS: Access denied to terminate process {pid}")
            access_denied_pids.append(pid)
        except Exception as e:
            logger.error(f"PROCESS: Error terminating process {pid}: {e}")
    
    if already_gone_pids:
        logger.info(f"PROCESS: {len(already_gone_pids)} processes already terminated")
    
    # Step 2: Wait for graceful shutdown with progress monitoring
    if terminated_processes:
        logger.info(f"PROCESS: Waiting up to {graceful_timeout}s for {len(terminated_processes)} processes to terminate gracefully...")
        
        try:
            gone, alive = psutil.wait_procs(terminated_processes, timeout=graceful_timeout)
            
            if gone:
                logger.info(f"PROCESS: {len(gone)} processes terminated gracefully")
                for proc in gone:
                    logger.debug(f"PROCESS: Process {proc.pid} terminated gracefully")
            
            if alive:
                logger.warning(f"PROCESS: {len(alive)} processes didn't terminate gracefully within {graceful_timeout}s")
                
                # Step 3: Force kill remaining processes
                for proc in alive:
                    try:
                        logger.warning(f"PROCESS: Force killing process {proc.pid}")
                        proc.kill()
                        logger.info(f"PROCESS: Sent SIGKILL to process {proc.pid}")
                    except psutil.NoSuchProcess:
                        logger.debug(f"PROCESS: Process {proc.pid} disappeared before SIGKILL")
                    except psutil.AccessDenied:
                        logger.error(f"PROCESS: Access denied for SIGKILL on process {proc.pid}")
                        access_denied_pids.append(proc.pid)
                    except Exception as kill_error:
                        logger.error(f"PROCESS: Error force killing process {proc.pid}: {kill_error}")
                
                # Wait briefly for SIGKILL to take effect
                if alive:
                    logger.info(f"PROCESS: Waiting 3s for SIGKILL to take effect on {len(alive)} processes...")
                    time.sleep(3)
                    
                    # Check if SIGKILL worked
                    still_alive = []
                    for proc in alive:
                        try:
                            if proc.is_running():
                                still_alive.append(proc)
                                logger.error(f"PROCESS: Process {proc.pid} survived SIGKILL")
                            else:
                                logger.debug(f"PROCESS: Process {proc.pid} terminated by SIGKILL")
                        except psutil.NoSuchProcess:
                            logger.debug(f"PROCESS: Process {proc.pid} terminated by SIGKILL")
                    
                    if still_alive:
                        logger.error(f"PROCESS: {len(still_alive)} processes survived SIGKILL - may need manual intervention")
                        
        except psutil.TimeoutExpired as e:
            logger.error(f"PROCESS: Timeout during process termination: {e}")
    
    # Handle access denied processes
    if access_denied_pids:
        logger.warning(f"PROCESS: Could not terminate {len(access_denied_pids)} processes due to access restrictions: {access_denied_pids}")
        logger.warning("PROCESS: These processes may need to be terminated manually or with elevated privileges")
    
    # Step 4: Final verification
    time.sleep(1)  # Brief pause before final check
    remaining_pids = find_server_processes()
    
    if remaining_pids:
        logger.error(f"PROCESS: {len(remaining_pids)} server processes still running after termination attempts: {remaining_pids}")
        
        # Provide helpful suggestions
        if access_denied_pids:
            logger.error("PROCESS: Some processes may require elevated privileges to terminate")
            logger.error("PROCESS: Try running with sudo if necessary")
        
        logger.error("PROCESS: Manual process cleanup may be required")
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
    
    # Check if port is already in use with enhanced error handling
    def is_port_in_use(port: int, host: str = host) -> bool:
        """Check if a port is in use on the specified host with detailed error reporting"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Set socket options for better reliability
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                try:
                    s.bind((host, port))
                    logger.debug(f"PORT: Port {port} is available on {host}")
                    return False
                except OSError as bind_error:
                    # More specific error handling
                    if bind_error.errno == 48:  # Address already in use (macOS/BSD)
                        logger.debug(f"PORT: Port {port} is in use on {host} (Address already in use)")
                    elif bind_error.errno == 98:  # Address already in use (Linux)
                        logger.debug(f"PORT: Port {port} is in use on {host} (Address already in use)")
                    elif bind_error.errno == 13:  # Permission denied
                        logger.warning(f"PORT: Permission denied for port {port} on {host} (may need elevated privileges)")
                    elif bind_error.errno == 99:  # Cannot assign requested address
                        logger.warning(f"PORT: Cannot assign requested address {host}:{port} (invalid host?)")
                    else:
                        logger.debug(f"PORT: Port {port} unavailable on {host}: {bind_error} (errno: {bind_error.errno})")
                    return True
        except Exception as e:
            logger.warning(f"PORT: Error checking port {port} on {host}: {e}")
            return True  # Assume port is in use if we can't check
    
    # Check for port conflicts with enhanced diagnostics
    if is_port_in_use(port, host):
        logger.error(f"UVICORN: Port {port} is already in use on host {host}!")
        
        # Enhanced port conflict diagnostics
        port_diagnostics = diagnose_port_conflict(port, host)
        
        # Show what's using the port
        try:
            import subprocess
            result = subprocess.run(['lsof', '-i', f':{port}'], 
                                 capture_output=True, text=True, timeout=5)
            if result.stdout:
                logger.error(f"UVICORN: Processes using port {port}:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():  # Skip empty lines
                        logger.error(f"UVICORN:   {line}")
                
                # Try to detect if it's one of our server processes
                server_pids = find_server_processes()
                if server_pids:
                    logger.warning(f"UVICORN: Detected {len(server_pids)} existing server processes")
                    print("\n💡 Suggestions for existing server processes:")
                    print("  • Use --kill-existing to automatically clean up old processes")
                    print("  • Use --auto-port to automatically find an available port")
                    print(f"  • Use --port {port + 1} to try a different port")
                    print("  • Run: ./start_server.sh --kill-existing")
                    print(f"  • Manual cleanup: kill {' '.join(map(str, server_pids))}")
                else:
                    logger.error(f"UVICORN: Port {port} is used by another application")
                    print("\n💡 Suggestions for external application conflict:")
                    print(f"  • Use --port {port + 1} to try a different port")
                    print("  • Use --auto-port to automatically find an available port")
                    if port_diagnostics.get('common_service'):
                        print(f"  • Port {port} is commonly used by: {port_diagnostics['common_service']}")
                    print(f"  • Stop the service using port {port} if it's not needed")
        except subprocess.TimeoutExpired:
            logger.warning("UVICORN: Timeout checking port usage with lsof")
            print("\n💡 Basic suggestions:")
            print("  • Use --kill-existing to clean up any old server processes")
            print("  • Use --auto-port to automatically find an available port")
            print(f"  • Use --port {port + 1} to try a different port")
        except FileNotFoundError:
            logger.debug("UVICORN: lsof command not available")
            print("\n💡 Suggestions (lsof unavailable):")
            print("  • Use --kill-existing to clean up any old server processes")
            print("  • Use --auto-port to automatically find an available port")
            print(f"  • Use --port {port + 1} to try a different port")
            print("  • Check manually: netstat -an | grep :8000")
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
        
        # Store server instance for potential external shutdown with safety checks
        global _server_instance
        if server is not None:
            _server_instance = server
            logger.info(f"UVICORN: Server instance stored for graceful shutdown")
            logger.info(f"UVICORN: Server starting with graceful shutdown timeout: 30s")
        else:
            logger.error("UVICORN: Server instance is None - cannot store for shutdown")
            _server_instance = None
        
        print("✅ Server configuration complete")
        print("⏳ Initializing application services...")
        
        # Install custom signal handlers that work with uvicorn with safety checks
        original_sigint_handler = None
        original_sigterm_handler = None
        
        try:
            original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
            logger.debug("UVICORN: Saved original SIGINT handler")
        except (OSError, ValueError) as e:
            logger.warning(f"UVICORN: Error saving original SIGINT handler: {e}")
        
        try:
            original_sigterm_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
            logger.debug("UVICORN: Saved original SIGTERM handler")
        except (OSError, ValueError) as e:
            logger.warning(f"UVICORN: Error saving original SIGTERM handler: {e}")
        
        def uvicorn_signal_handler(signum, frame):
            """Signal handler that properly triggers uvicorn shutdown with safety checks"""
            # Safe signal name resolution
            try:
                if hasattr(signal, 'Signals') and hasattr(signal.Signals, '__getitem__'):
                    signal_name = signal.Signals(signum).name
                else:
                    signal_name = f"signal-{signum}"
            except (ValueError, AttributeError):
                signal_name = f"unknown-signal-{signum}"
            
            logger.info(f"UVICORN: Received {signal_name} ({signum}) - initiating graceful shutdown")
            
            # Safe console output
            try:
                print(f"\n\n🛑 Graceful shutdown initiated by {signal_name}...")
                print("⏳ Shutting down services and releasing port bindings...")
            except Exception as print_error:
                logger.debug(f"UVICORN: Error printing shutdown message: {print_error}")
            
            # Set the shutdown flag and trigger uvicorn shutdown with safety checks
            global _shutdown_requested
            _shutdown_requested = True
            
            # Safely access server attributes
            try:
                if hasattr(server, 'should_exit'):
                    server.should_exit = True
                    logger.debug("UVICORN: Set server.should_exit = True")
                else:
                    logger.error("UVICORN: Server has no 'should_exit' attribute")
                
                # Configure graceful shutdown for both SIGINT and SIGTERM
                if hasattr(server, 'force_exit'):
                    if signum == signal.SIGINT:
                        server.force_exit = False  # Graceful shutdown for CTRL-C
                        logger.debug("UVICORN: Set graceful shutdown for SIGINT")
                    elif signum == signal.SIGTERM:
                        server.force_exit = False  # Also graceful for SIGTERM
                        logger.debug("UVICORN: Set graceful shutdown for SIGTERM")
                    else:
                        logger.debug(f"UVICORN: Using default force_exit setting for {signal_name}")
                else:
                    logger.warning("UVICORN: Server has no 'force_exit' attribute")
                    
            except AttributeError as attr_error:
                logger.error(f"UVICORN: Server missing expected attributes: {attr_error}")
            except Exception as e:
                logger.error(f"UVICORN: Error configuring server shutdown: {e}")
                logger.exception("UVICORN: Full exception details:")
            
            logger.info(f"UVICORN: Signal handler for {signal_name} completed")
        
        # Install our custom handlers with error handling
        try:
            signal.signal(signal.SIGINT, uvicorn_signal_handler)
            logger.info("UVICORN: Installed custom SIGINT handler")
        except (OSError, ValueError) as e:
            logger.error(f"UVICORN: Failed to install SIGINT handler: {e}")
        
        try:
            signal.signal(signal.SIGTERM, uvicorn_signal_handler)
            logger.info("UVICORN: Installed custom SIGTERM handler")
        except (OSError, ValueError) as e:
            logger.error(f"UVICORN: Failed to install SIGTERM handler: {e}")
        
        try:
            server.run()
        finally:
            # Restore original handlers with error handling
            try:
                if original_sigint_handler is not None:
                    signal.signal(signal.SIGINT, original_sigint_handler)
                    logger.debug("UVICORN: Restored original SIGINT handler")
            except (OSError, ValueError) as e:
                logger.warning(f"UVICORN: Error restoring SIGINT handler: {e}")
            
            try:
                if original_sigterm_handler is not None:
                    signal.signal(signal.SIGTERM, original_sigterm_handler)
                    logger.debug("UVICORN: Restored original SIGTERM handler")
            except (OSError, ValueError) as e:
                logger.warning(f"UVICORN: Error restoring SIGTERM handler: {e}")
            
            logger.debug("UVICORN: Signal handler cleanup completed")
        
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


def diagnose_port_conflict(port: int, host: str) -> dict:
    """Diagnose why a port is unavailable and provide helpful context"""
    diagnostics = {
        'port': port,
        'host': host,
        'common_service': None,
        'permission_issue': False,
        'network_issue': False
    }
    
    # Check for common services on well-known ports
    common_ports = {
        80: "HTTP web server (Apache, Nginx, etc.)",
        443: "HTTPS web server (Apache, Nginx, etc.)",
        8000: "Development server (Django, Flask, etc.)",
        8080: "HTTP proxy/web server (Tomcat, Jenkins, etc.)",
        3000: "Node.js development server (React, Next.js, etc.)",
        5000: "Flask development server",
        8888: "Jupyter Notebook",
        9000: "Various development tools"
    }
    
    if port in common_ports:
        diagnostics['common_service'] = common_ports[port]
        logger.debug(f"PORT: Port {port} is commonly used by: {common_ports[port]}")
    
    # Test for permission issues (ports < 1024 typically require root)
    if port < 1024:
        diagnostics['permission_issue'] = True
        logger.debug(f"PORT: Port {port} is a privileged port (< 1024), may require elevated privileges")
    
    # Test if host address is valid
    import socket
    try:
        socket.inet_aton(host)
    except socket.error:
        if host not in ['localhost', '0.0.0.0', '127.0.0.1']:
            diagnostics['network_issue'] = True
            logger.debug(f"PORT: Host '{host}' may not be a valid network address")
    
    return diagnostics

def find_available_port(start_port: int = 8000, host: str = "0.0.0.0", max_attempts: int = 100) -> int:
    """Find an available port starting from start_port on specified host with enhanced reliability"""
    import socket
    import time
    
    logger.info(f"PORT: Searching for available port starting from {start_port} on host {host}")
    logger.debug(f"PORT: Will check up to {max_attempts} ports in range {start_port}-{start_port + max_attempts - 1}")
    
    # Track any ports that had issues for reporting
    problematic_ports = []
    
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Set socket options for better reliability
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                try:
                    s.bind((host, port))
                    logger.info(f"PORT: Found available port {port} on host {host}")
                    
                    # Double-check by briefly testing the port
                    try:
                        s.listen(1)
                        logger.debug(f"PORT: Verified port {port} can accept connections")
                    except OSError as listen_error:
                        logger.warning(f"PORT: Port {port} bound but can't listen: {listen_error}")
                        problematic_ports.append((port, f"listen failed: {listen_error}"))
                        continue
                    
                    return port
                    
                except OSError as bind_error:
                    logger.debug(f"PORT: Port {port} is in use on {host}: {bind_error}")
                    
                    # Track specific error types for better diagnostics
                    if bind_error.errno == 13:  # Permission denied
                        problematic_ports.append((port, "permission denied"))
                    elif bind_error.errno in [48, 98]:  # Address already in use
                        problematic_ports.append((port, "in use"))
                    else:
                        problematic_ports.append((port, f"bind error: {bind_error}"))
                    continue
                    
        except Exception as socket_error:
            logger.debug(f"PORT: Error testing port {port}: {socket_error}")
            problematic_ports.append((port, f"socket error: {socket_error}"))
            continue
    
    # If we get here, no port was available
    logger.error(f"PORT: No available ports found in range {start_port}-{start_port + max_attempts - 1} on host {host}")
    
    # Provide detailed diagnostics
    if problematic_ports:
        logger.error(f"PORT: Encountered issues with {len(problematic_ports)} ports:")
        
        # Group by error type for cleaner reporting
        error_summary = {}
        for port, error in problematic_ports[:10]:  # Limit to first 10 for brevity
            if error not in error_summary:
                error_summary[error] = []
            error_summary[error].append(port)
        
        for error, ports in error_summary.items():
            logger.error(f"PORT:   {error}: ports {ports}")
        
        if len(problematic_ports) > 10:
            logger.error(f"PORT:   ... and {len(problematic_ports) - 10} more ports with issues")
    
    # Provide helpful suggestions
    suggestions = []
    if any("permission denied" in error for _, error in problematic_ports):
        suggestions.append("Try using ports > 1024 or run with elevated privileges")
    if host == "0.0.0.0":
        suggestions.append("Try using host '127.0.0.1' or 'localhost' instead")
    if start_port < 8000:
        suggestions.append("Try starting from a higher port number (e.g., 8000+)")
    
    error_msg = f"No available ports found in range {start_port}-{start_port + max_attempts - 1} on host {host}"
    if suggestions:
        error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
    
    logger.error(f"PORT: {error_msg}")
    raise RuntimeError(error_msg)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lifeboard API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--no-auto-port", action="store_true", 
                       help="Disable automatic port finding (use exact port specified)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--kill-existing", action="store_true", 
                       help="Kill existing server processes before starting")
    
    args = parser.parse_args()
    
    port = args.port
    if not args.no_auto_port:
        # Auto-port is the default behavior
        try:
            port = find_available_port(args.port, args.host)
            if port != args.port:
                print(f"🔄 Port {args.port} was in use, using available port: {port} on host {args.host}")
            else:
                print(f"✅ Using requested port: {port} on host {args.host}")
        except RuntimeError as e:
            print(f"❌ Auto-port failed: {e}")
            print(f"💡 Try using --no-auto-port to use exact port {args.port} (may fail if in use)")
            exit(1)
    else:
        print(f"🎯 Using exact port: {port} on host {args.host} (auto-port disabled)")
    
    run_server(host=args.host, port=port, debug=args.debug, kill_existing=args.kill_existing)