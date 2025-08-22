"""
FrontendOrchestrator - Manages frontend development server lifecycle for Lifeboard application.

Extracted from api/server.py as part of TDD-driven architecture cleanup.
Handles frontend server startup, port resolution, environment validation, and graceful shutdown.
"""

import logging
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class FrontendConfig:
    """Configuration for frontend server orchestration."""
    frontend_port: int = 5173
    backend_port: int = 8000
    host: str = "localhost"
    auto_port_resolution: bool = True
    timeout_seconds: int = 30
    development_mode: bool = True


@dataclass
class FrontendProcessInfo:
    """Information about a frontend process."""
    success: bool
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    port: Optional[int] = None
    error_message: Optional[str] = None
    warning_message: Optional[str] = None


@dataclass
class PortResolutionResult:
    """Result of port resolution process."""
    requested_port: int
    resolved_port: int
    auto_resolution_used: bool
    success: bool
    error_message: Optional[str] = None


@dataclass
class EnvironmentValidationResult:
    """Result of frontend environment validation."""
    is_valid: bool
    node_installed: bool
    dependencies_installed: bool
    frontend_dir_exists: bool
    error_message: Optional[str] = None


class FrontendOrchestrator:
    """Orchestrates frontend development server lifecycle with comprehensive management."""

    def __init__(self, frontend_dir: Optional[Path] = None):
        """Initialize FrontendOrchestrator with optional custom frontend directory."""
        self.frontend_dir = frontend_dir or Path.cwd() / "frontend"
        self.config: Optional[FrontendConfig] = None
        self.process_info: Optional[FrontendProcessInfo] = None
        logger.info("FRONTEND: FrontendOrchestrator initialized")

    def validate_environment(self) -> EnvironmentValidationResult:
        """
        Validate frontend environment requirements.
        
        Returns:
            EnvironmentValidationResult: Validation results with detailed status
        """
        try:
            # Check Node.js installation
            node_installed = self._is_node_installed()

            # Check frontend directory exists
            frontend_dir_exists = self.frontend_dir.exists()

            # Check dependencies installation
            dependencies_installed = self._are_dependencies_installed()

            is_valid = node_installed and frontend_dir_exists and dependencies_installed

            error_message = None
            if not node_installed:
                error_message = "Node.js not found in PATH"
            elif not frontend_dir_exists:
                error_message = f"Frontend directory not found: {self.frontend_dir}"
            elif not dependencies_installed:
                error_message = "Frontend dependencies not installed (missing node_modules)"

            return EnvironmentValidationResult(
                is_valid=is_valid,
                node_installed=node_installed,
                dependencies_installed=dependencies_installed,
                frontend_dir_exists=frontend_dir_exists,
                error_message=error_message,
            )

        except Exception as e:
            logger.error(f"FRONTEND: Error validating environment: {e}")
            return EnvironmentValidationResult(
                is_valid=False,
                node_installed=False,
                dependencies_installed=False,
                frontend_dir_exists=False,
                error_message=f"Environment validation failed: {e}",
            )

    def resolve_port(self, requested_port: int, auto_resolve: bool = True) -> PortResolutionResult:
        """
        Resolve port for frontend server with optional auto-resolution.
        
        Args:
            requested_port: The desired port number
            auto_resolve: Whether to automatically find alternative port if requested is unavailable
            
        Returns:
            PortResolutionResult: Port resolution outcome
        """
        try:
            # Check if requested port is available
            if self._is_port_available(requested_port):
                logger.info(f"FRONTEND: Port {requested_port} is available")
                return PortResolutionResult(
                    requested_port=requested_port,
                    resolved_port=requested_port,
                    auto_resolution_used=False,
                    success=True,
                )

            # Port is not available
            if not auto_resolve:
                error_msg = f"Port {requested_port} is in use and auto-resolution is disabled"
                logger.warning(f"FRONTEND: {error_msg}")
                return PortResolutionResult(
                    requested_port=requested_port,
                    resolved_port=requested_port,
                    auto_resolution_used=False,
                    success=False,
                    error_message=error_msg,
                )

            # Auto-resolve to find available port
            logger.info(f"FRONTEND: Port {requested_port} in use, finding alternative...")
            resolved_port = self._find_available_port(requested_port)
            logger.info(f"FRONTEND: Resolved to port {resolved_port}")

            return PortResolutionResult(
                requested_port=requested_port,
                resolved_port=resolved_port,
                auto_resolution_used=True,
                success=True,
            )

        except Exception as e:
            error_msg = f"Port resolution failed: {e}"
            logger.error(f"FRONTEND: {error_msg}")
            return PortResolutionResult(
                requested_port=requested_port,
                resolved_port=requested_port,
                auto_resolution_used=False,
                success=False,
                error_message=error_msg,
            )

    def install_dependencies(self) -> bool:
        """
        Install frontend dependencies using npm.
        
        Returns:
            bool: True if installation succeeded, False otherwise
        """
        try:
            logger.info("FRONTEND: Installing dependencies...")

            result = subprocess.run(
                ["npm", "install"],
                cwd=self.frontend_dir,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            if result.returncode == 0:
                logger.info("FRONTEND: Dependencies installed successfully")
                return True
            logger.error(f"FRONTEND: npm install failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"FRONTEND: Error installing dependencies: {e}")
            return False

    def start_server(self, config: FrontendConfig) -> FrontendProcessInfo:
        """
        Start the frontend development server.
        
        Args:
            config: Frontend configuration
            
        Returns:
            FrontendProcessInfo: Information about the started process
        """
        try:
            self.config = config
            logger.info(f"FRONTEND: Starting server on port {config.frontend_port}")

            # Setup environment variables
            env_vars = self._setup_environment_variables(
                backend_port=config.backend_port,
                development_mode=config.development_mode,
            )

            # Prepare process environment
            process_env = os.environ.copy()
            process_env.update(env_vars)
            process_env["PORT"] = str(config.frontend_port)

            # Start the development server
            process = subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", str(config.frontend_port), "--host", config.host],
                cwd=self.frontend_dir,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Validate startup
            startup_success = self._validate_server_startup(
                process, config.frontend_port, timeout=config.timeout_seconds,
            )

            process_info = FrontendProcessInfo(
                success=startup_success,
                process=process,
                pid=process.pid,
                port=config.frontend_port,
                warning_message=None if startup_success else "Server started but responsiveness validation failed",
            )

            self.process_info = process_info

            if startup_success:
                logger.info(f"FRONTEND: Server started successfully on port {config.frontend_port}")
            else:
                logger.warning(f"FRONTEND: Server started but failed responsiveness check on port {config.frontend_port}")

            return process_info

        except Exception as e:
            error_msg = f"Failed to start frontend server: {e}"
            logger.error(f"FRONTEND: {error_msg}")

            return FrontendProcessInfo(
                success=False,
                process=None,
                pid=None,
                port=config.frontend_port,
                error_message=error_msg,
            )

    def stop_server(self, timeout: int = 10) -> bool:
        """
        Stop the frontend server gracefully.
        
        Args:
            timeout: Seconds to wait for graceful termination
            
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.process_info or not self.process_info.process:
            logger.debug("FRONTEND: No process to stop")
            return True

        process = self.process_info.process

        try:
            # Check if already terminated
            if process.poll() is not None:
                logger.info("FRONTEND: Process already terminated")
                self.process_info = None
                return True

            # Try graceful termination
            logger.info(f"FRONTEND: Sending SIGTERM to process {process.pid}")
            process.terminate()

            try:
                # Wait for graceful shutdown
                process.wait(timeout=timeout)
                logger.info("FRONTEND: Process terminated gracefully")
                self.process_info = None
                return True

            except subprocess.TimeoutExpired:
                # Force kill if graceful termination failed
                logger.warning("FRONTEND: Graceful termination timed out, using SIGKILL")
                process.kill()
                process.wait(timeout=timeout)
                logger.info("FRONTEND: Process killed forcefully")
                self.process_info = None
                return True

        except Exception as e:
            logger.error(f"FRONTEND: Error stopping server: {e}")
            return False

    def orchestrate_startup(self, config: FrontendConfig) -> Dict[str, Any]:
        """
        Complete frontend startup orchestration.
        
        Args:
            config: Frontend configuration
            
        Returns:
            Dict containing startup results and process information
        """
        result = {
            "success": False,
            "port": None,
            "process_info": None,
            "error": None,
        }

        try:
            # Step 1: Validate environment
            logger.info("FRONTEND: Validating environment...")
            env_validation = self.validate_environment()

            if not env_validation.is_valid:
                result["error"] = env_validation.error_message
                return result

            # Step 2: Resolve port
            logger.info("FRONTEND: Resolving port...")
            port_resolution = self.resolve_port(
                config.frontend_port,
                auto_resolve=config.auto_port_resolution,
            )

            if not port_resolution.success:
                result["error"] = port_resolution.error_message
                return result

            # Update config with resolved port
            config.frontend_port = port_resolution.resolved_port

            # Step 3: Start server
            logger.info("FRONTEND: Starting server...")
            process_info = self.start_server(config)

            if not process_info.success:
                result["error"] = process_info.error_message
                return result

            # Success
            result.update({
                "success": True,
                "port": config.frontend_port,
                "process_info": process_info,
            })

            logger.info(f"FRONTEND: Orchestration completed successfully on port {config.frontend_port}")
            return result

        except Exception as e:
            error_msg = f"Frontend orchestration failed: {e}"
            logger.error(f"FRONTEND: {error_msg}")
            result["error"] = error_msg
            return result

    def _is_node_installed(self) -> bool:
        """Check if Node.js is installed and available."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _are_dependencies_installed(self) -> bool:
        """Check if frontend dependencies are installed."""
        node_modules = self.frontend_dir / "node_modules"
        package_json = self.frontend_dir / "package.json"

        return (
            self.frontend_dir.exists() and
            package_json.exists() and
            node_modules.exists() and
            node_modules.is_dir()
        )

    def _is_port_available(self, port: int, host: str = "localhost") -> bool:
        """Check if a port is available for binding."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False

    def _find_available_port(self, start_port: int, max_attempts: int = 100) -> int:
        """Find an available port starting from start_port."""
        for port in range(start_port, start_port + max_attempts):
            if self._is_port_available(port):
                return port
        raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")

    def _setup_environment_variables(self, backend_port: int, development_mode: bool = True) -> Dict[str, str]:
        """Setup environment variables for frontend development."""
        base_url = f"http://localhost:{backend_port}"

        env_vars = {
            "VITE_API_URL": base_url,
            "VITE_API_BASE_URL": f"{base_url}/api",
            "NODE_ENV": "development" if development_mode else "production",
        }

        logger.debug(f"FRONTEND: Environment variables: {env_vars}")
        return env_vars

    def _validate_server_startup(self, process: subprocess.Popen, port: int, timeout: int = 10) -> bool:
        """
        Validate that the frontend server started successfully and is responsive.
        
        Args:
            process: The subprocess running the frontend server
            port: Port the server should be listening on
            timeout: Maximum time to wait for server responsiveness
            
        Returns:
            bool: True if server is responsive, False otherwise
        """
        # Give server time to start
        time.sleep(min(timeout // 2, 3))

        # Check if process is still running
        if process.poll() is not None:
            logger.warning("FRONTEND: Process terminated during startup")
            return False

        # Check port responsiveness
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(("localhost", port))
                    if result == 0:
                        logger.debug(f"FRONTEND: Port {port} is responsive")
                        return True
            except Exception:
                pass

            time.sleep(0.5)

        logger.warning(f"FRONTEND: Server not responsive on port {port} within {timeout} seconds")
        return False
