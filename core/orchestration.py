"""
Core orchestration classes for managing full-stack application lifecycle.

This module contains the refactored components that were extracted from the 300-line
run_full_stack() method to improve maintainability and testability.
"""

import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a managed process"""
    process: Optional[subprocess.Popen]
    pid: Optional[int]
    port: int
    success: bool
    error: Optional[str] = None
    warning: Optional[str] = None


@dataclass
class PortResolution:
    """Result of port resolution process"""
    requested_port: int
    resolved_port: int
    auto_port_used: bool
    available: bool
    error: Optional[str] = None


class PortManager:
    """Manages port availability and resolution"""

    @staticmethod
    def check_port_available(port: int, host: str = "0.0.0.0") -> bool:
        """Check if a port is available for binding"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False

    @staticmethod
    def find_available_port(start_port: int, host: str = "0.0.0.0", max_attempts: int = 100) -> int:
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            if PortManager.check_port_available(port, host):
                return port
        raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")

    @staticmethod
    def resolve_port(requested_port: int, host: str = "0.0.0.0", no_auto_port: bool = False) -> PortResolution:
        """Resolve port with auto-port logic"""
        if no_auto_port:
            # Exact port mode - check availability but don't auto-resolve
            available = PortManager.check_port_available(requested_port, host)
            return PortResolution(
                requested_port=requested_port,
                resolved_port=requested_port,
                auto_port_used=False,
                available=available,
                error=None if available else f"Port {requested_port} is in use (auto-port disabled)",
            )

        # Auto-port mode - find available port if requested is unavailable
        try:
            if PortManager.check_port_available(requested_port, host):
                return PortResolution(
                    requested_port=requested_port,
                    resolved_port=requested_port,
                    auto_port_used=False,
                    available=True,
                )
            resolved_port = PortManager.find_available_port(requested_port, host)
            return PortResolution(
                requested_port=requested_port,
                resolved_port=resolved_port,
                auto_port_used=True,
                available=True,
            )
        except RuntimeError as e:
            return PortResolution(
                requested_port=requested_port,
                resolved_port=requested_port,
                auto_port_used=False,
                available=False,
                error=str(e),
            )


class ProcessTerminator:
    """Handles graceful process termination with fallback to force kill"""

    @staticmethod
    def terminate_process_gracefully(process: subprocess.Popen, timeout: int = 2) -> bool:
        """Terminate a process gracefully with SIGTERM, then SIGKILL if needed"""
        if not process or process.poll() is not None:
            return True  # Already terminated

        try:
            # Send SIGTERM
            process.terminate()

            # Wait for graceful shutdown
            try:
                process.wait(timeout=timeout)
                return True
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown failed
                process.kill()
                process.wait(timeout=timeout)
                return True

        except Exception as e:
            logger.warning(f"Error terminating process {process.pid}: {e}")
            return False

    @staticmethod
    def cleanup_processes(processes: List[subprocess.Popen]) -> Dict[str, int]:
        """Clean up multiple processes and return statistics"""
        stats = {"terminated": 0, "killed": 0, "failed": 0}

        for process in processes:
            if ProcessTerminator.terminate_process_gracefully(process):
                if process.poll() is not None:
                    stats["terminated"] += 1
                else:
                    stats["killed"] += 1
            else:
                stats["failed"] += 1

        return stats


class FrontendEnvironmentValidator:
    """Validates frontend environment requirements"""

    @staticmethod
    def is_node_installed() -> bool:
        """Check if Node.js is installed and available"""
        try:
            result = subprocess.run(
                ["node", "--version"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @staticmethod
    def check_frontend_dependencies() -> bool:
        """Check if frontend dependencies are installed"""
        frontend_dir = Path("frontend")
        node_modules = frontend_dir / "node_modules"
        package_lock = frontend_dir / "package-lock.json"

        return (
            frontend_dir.exists() and
            node_modules.exists() and
            node_modules.is_dir() and
            (package_lock.exists() or (frontend_dir / "yarn.lock").exists())
        )

    @staticmethod
    def install_frontend_dependencies() -> bool:
        """Install frontend dependencies using npm"""
        try:
            result = subprocess.run(
                ["npm", "install"],
                check=False, cwd="frontend",
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @staticmethod
    def validate_environment() -> Dict[str, Any]:
        """Comprehensive frontend environment validation"""
        return {
            "node_installed": FrontendEnvironmentValidator.is_node_installed(),
            "dependencies_ready": FrontendEnvironmentValidator.check_frontend_dependencies(),
            "frontend_dir_exists": Path("frontend").exists(),
        }


class FrontendService:
    """Manages frontend server lifecycle"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None

    def setup_frontend_environment(self, backend_port: int) -> Dict[str, Any]:
        """Setup frontend environment variables for backend communication"""
        env = {
            "REACT_APP_BACKEND_URL": f"http://localhost:{backend_port}",
            "REACT_APP_BACKEND_PORT": str(backend_port),
            "NODE_ENV": "development",
        }
        return env

    def start_frontend_server(self, port: int, backend_port: int) -> ProcessInfo:
        """Start the frontend development server"""
        try:
            # Setup environment
            env = self.setup_frontend_environment(backend_port)

            # Prepare process environment
            import os
            process_env = os.environ.copy()
            process_env.update(env)
            process_env["PORT"] = str(port)

            # Start the process
            self.process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd="frontend",
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.port = port

            # Wait for startup validation
            if self.validate_frontend_startup(port):
                return ProcessInfo(
                    process=self.process,
                    pid=self.process.pid,
                    port=port,
                    success=True,
                )
            return ProcessInfo(
                process=self.process,
                pid=self.process.pid,
                port=port,
                success=False,
                warning="Frontend server started but responsiveness check failed",
            )

        except Exception as e:
            logger.error(f"Failed to start frontend server: {e}")
            return ProcessInfo(
                process=None,
                pid=None,
                port=port,
                success=False,
                error=str(e),
            )

    def validate_frontend_startup(self, port: int, timeout: int = 3) -> bool:
        """Validate that frontend server is responsive"""
        # Simple validation - just check if process is still running after a brief wait
        time.sleep(timeout)

        if not self.process or self.process.poll() is not None:
            return False

        # More sophisticated validation could check HTTP response
        return self.check_port_responsiveness(port)

    def check_port_responsiveness(self, port: int) -> bool:
        """Check if port is responsive to connections"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result == 0
        except Exception:
            return False

    def stop(self) -> bool:
        """Stop the frontend server"""
        if self.process:
            return ProcessTerminator.terminate_process_gracefully(self.process)
        return True


class FullStackOrchestrator:
    """Main orchestrator for full-stack application lifecycle"""

    def __init__(self):
        self.frontend_service = FrontendService()
        self.backend_started = False
        self.frontend_info: Optional[ProcessInfo] = None

    def validate_frontend_environment(self) -> bool:
        """Validate frontend environment and dependencies"""
        print("📦 Checking frontend environment...")

        validation_result = FrontendEnvironmentValidator.validate_environment()

        if not validation_result["node_installed"]:
            print("❌ Node.js is not installed or not available in PATH")
            print("💡 Install Node.js or use --no-frontend to start backend only")
            return False

        if not validation_result["dependencies_ready"]:
            print("📦 Frontend dependencies not found, installing...")
            if not FrontendEnvironmentValidator.install_frontend_dependencies():
                print("❌ Failed to install frontend dependencies")
                print("💡 Try running 'npm install' in the frontend directory manually")
                print("💡 Or use --no-frontend to start backend only")
                return False

        return True

    def resolve_ports(self, backend_port: int, frontend_port: int, no_auto_port: bool) -> tuple[int, int]:
        """Resolve both backend and frontend ports"""
        # Resolve backend port
        backend_resolution = PortManager.resolve_port(backend_port, no_auto_port=no_auto_port)

        if not backend_resolution.available:
            print(f"❌ Backend port resolution failed: {backend_resolution.error}")
            if not no_auto_port:
                print("💡 Try --no-frontend to start backend only")
            raise RuntimeError(backend_resolution.error)

        if backend_resolution.auto_port_used:
            print(f"🔄 Backend port {backend_port} was in use, using: {backend_resolution.resolved_port}")
        else:
            print(f"✅ Backend using requested port: {backend_resolution.resolved_port}")

        # Resolve frontend port
        frontend_resolution = PortManager.resolve_port(frontend_port, no_auto_port=no_auto_port)

        if not frontend_resolution.available:
            print(f"❌ Frontend port resolution failed: {frontend_resolution.error}")
            raise RuntimeError(frontend_resolution.error)

        if frontend_resolution.auto_port_used:
            print(f"🔄 Frontend port {frontend_port} was in use, using: {frontend_resolution.resolved_port}")
        else:
            print(f"✅ Frontend using requested port: {frontend_resolution.resolved_port}")

        return backend_resolution.resolved_port, frontend_resolution.resolved_port

    def start_frontend_if_enabled(self, port: int, backend_port: int) -> ProcessInfo:
        """Start frontend server if environment is valid"""
        if not self.validate_frontend_environment():
            raise RuntimeError("Frontend environment validation failed")

        print("\n🌐 Starting frontend development server...")
        frontend_info = self.frontend_service.start_frontend_server(port, backend_port)

        if not frontend_info.success:
            error_msg = f"Frontend server failed to start: {frontend_info.error}"
            print(f"❌ {error_msg}")
            print("💡 Check the error above or use --no-frontend to start backend only")
            raise RuntimeError(error_msg)

        print("✅ Frontend server started successfully!")
        if frontend_info.warning:
            print(f"⚠️  {frontend_info.warning}")

        self.frontend_info = frontend_info
        return frontend_info

    def cleanup_processes_on_exit(self, frontend_info: Optional[ProcessInfo] = None) -> None:
        """Clean up processes on application exit"""
        if frontend_info and frontend_info.process:
            try:
                print("🧹 Stopping frontend server...")
                if ProcessTerminator.terminate_process_gracefully(frontend_info.process):
                    print("✅ Frontend server stopped")
                else:
                    print("⚠️ Frontend server stop had issues")
            except Exception as e:
                logger.warning(f"FRONTEND: Error stopping frontend process: {e}")

    async def orchestrate_startup(
        self,
        host: str,
        backend_port: int,
        frontend_port: int,
        no_auto_port: bool,
        no_frontend: bool,
        kill_existing: bool,
    ) -> Dict[str, Any]:
        """Main orchestration method for application startup"""
        startup_info = {
            "backend_port": None,
            "frontend_port": None,
            "frontend_info": None,
            "success": False,
        }

        try:
            # Step 1: Handle existing processes
            if kill_existing:
                print("🧹 Cleaning up existing processes...")
                # Import and call existing cleanup functions
                try:
                    # These functions should be imported from the server module
                    from api.server import kill_frontend_processes
                    kill_frontend_processes()
                except ImportError:
                    logger.warning("Could not import kill_frontend_processes function")

            # Step 2: Resolve ports
            resolved_backend_port, resolved_frontend_port = self.resolve_ports(
                backend_port, frontend_port, no_auto_port,
            )
            startup_info["backend_port"] = resolved_backend_port
            startup_info["frontend_port"] = resolved_frontend_port

            # Step 3: Handle frontend setup (unless disabled)
            if not no_frontend:
                frontend_info = self.start_frontend_if_enabled(resolved_frontend_port, resolved_backend_port)
                startup_info["frontend_info"] = frontend_info

            startup_info["success"] = True
            return startup_info

        except Exception as e:
            logger.error(f"Orchestration startup failed: {e}")
            startup_info["error"] = str(e)
            return startup_info
