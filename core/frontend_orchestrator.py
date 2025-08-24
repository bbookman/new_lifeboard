"""
FrontendOrchestrator - Extracted from api/server.py for Phase 1.1.3 refactoring

Handles frontend server lifecycle, dependency management, and process coordination.
Part of TDD-driven cleanup plan for Lifeboard codebase.
"""

import os
import subprocess
import socket
import time
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.debug_logger import DebugLogger


class FrontendOrchestratorInterface(ABC):
    """Abstract interface for frontend orchestration"""
    
    @abstractmethod
    def check_dependencies(self) -> bool:
        """Check if frontend dependencies are installed"""
        pass
    
    @abstractmethod
    def install_dependencies(self) -> bool:
        """Install frontend dependencies"""
        pass
    
    @abstractmethod
    def kill_existing_processes(self) -> bool:
        """Kill existing frontend development server processes"""
        pass
    
    @abstractmethod
    def start_frontend_server(self, port: int = 5173, backend_port: int = 8000) -> Dict[str, Any]:
        """Start the frontend development server"""
        pass
    
    @abstractmethod
    def stop_frontend_server(self, timeout: int = 10) -> bool:
        """Stop the frontend development server"""
        pass
    
    @abstractmethod
    def get_frontend_status(self) -> Dict[str, Any]:
        """Get current frontend server status"""
        pass
    
    @abstractmethod
    def cleanup_all_processes(self) -> bool:
        """Cleanup all frontend processes"""
        pass


class FrontendOrchestrator(FrontendOrchestratorInterface):
    """
    Manages frontend development server lifecycle with comprehensive process management.
    
    Features:
    - Frontend dependency validation and installation
    - Development server startup and shutdown
    - Process lifecycle management with graceful termination
    - Port conflict detection and resolution
    - Environment variable configuration
    - Thread-safe operations
    - Comprehensive error handling and recovery
    - Debug logging integration
    """
    
    class FrontendError(Exception):
        """Base exception for frontend orchestration errors"""
        pass
    
    class DependencyError(FrontendError):
        """Raised when frontend dependency issues occur"""
        pass
    
    class ProcessError(FrontendError):
        """Raised when frontend process management fails"""
        pass
    
    class PortError(FrontendError):
        """Raised when port-related issues occur"""
        pass
    
    def __init__(self, frontend_dir: Optional[Path] = None):
        """
        Initialize FrontendOrchestrator with debug logging and thread safety.
        
        Args:
            frontend_dir: Path to frontend directory. If None, defaults to ../frontend
        """
        self.debug = DebugLogger("frontend_orchestrator")
        
        # Set frontend directory
        if frontend_dir is None:
            # Default to frontend directory relative to this file
            self._frontend_dir = Path(__file__).parent.parent / "frontend"
        else:
            self._frontend_dir = Path(frontend_dir)
        
        # Thread-safe process management
        self._lock = threading.RLock()
        self._current_process: Optional[subprocess.Popen] = None
        self._current_port: Optional[int] = None
        
        self.debug.log_state("frontend_orchestrator_init", {
            'frontend_dir': str(self._frontend_dir),
            'frontend_dir_exists': self._frontend_dir.exists(),
            'initialized_at': datetime.now(timezone.utc).isoformat(),
            'thread_safe': True,
            'debug_enabled': True
        })
    
    @DebugLogger("frontend_orchestrator").trace_function("check_dependencies")
    def check_dependencies(self) -> bool:
        """
        Check if frontend dependencies are installed.
        
        Returns:
            bool: True if dependencies are ready, False otherwise
        """
        with self._lock:
            try:
                # Check if frontend directory exists
                if not self._frontend_dir.exists():
                    self.debug.log_state("dependency_check_failed", {
                        'reason': 'frontend_directory_missing',
                        'expected_path': str(self._frontend_dir)
                    })
                    return False
                
                # Check for package.json
                package_json = self._frontend_dir / "package.json"
                if not package_json.exists():
                    self.debug.log_state("dependency_check_failed", {
                        'reason': 'package_json_missing',
                        'expected_path': str(package_json)
                    })
                    return False
                
                # Check for node_modules
                node_modules = self._frontend_dir / "node_modules"
                if not node_modules.exists():
                    self.debug.log_state("dependency_check_failed", {
                        'reason': 'node_modules_missing',
                        'expected_path': str(node_modules)
                    })
                    return False
                
                # Basic validation passed
                self.debug.log_state("dependency_check_success", {
                    'frontend_dir': str(self._frontend_dir),
                    'package_json_exists': True,
                    'node_modules_exists': True
                })
                
                return True
                
            except Exception as e:
                self.debug.log_state("dependency_check_error", {
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                return False
    
    @DebugLogger("frontend_orchestrator").trace_function("install_dependencies")
    def install_dependencies(self) -> bool:
        """
        Install frontend dependencies using npm.
        
        Returns:
            bool: True if installation succeeded, False otherwise
        """
        with self._lock:
            try:
                if not self._frontend_dir.exists():
                    self.debug.log_state("install_failed", {
                        'reason': 'frontend_directory_missing',
                        'frontend_dir': str(self._frontend_dir)
                    })
                    return False
                
                self.debug.log_state("install_dependencies_start", {
                    'frontend_dir': str(self._frontend_dir),
                    'command': 'npm install'
                })
                
                # Run npm install
                result = subprocess.run(
                    ['npm', 'install'],
                    cwd=self._frontend_dir,
                    capture_output=True,
                    text=True,
                    timeout=180  # 3 minute timeout
                )
                
                if result.returncode == 0:
                    self.debug.log_state("install_dependencies_success", {
                        'return_code': result.returncode,
                        'stdout_length': len(result.stdout),
                        'duration': 'completed'
                    })
                    return True
                else:
                    self.debug.log_state("install_dependencies_failed", {
                        'return_code': result.returncode,
                        'stderr': result.stderr[:500],  # Limit error output
                        'stdout': result.stdout[:500]
                    })
                    return False
                    
            except subprocess.TimeoutExpired:
                self.debug.log_state("install_dependencies_timeout", {
                    'timeout_seconds': 180,
                    'command': 'npm install'
                })
                return False
                
            except (OSError, PermissionError, subprocess.SubprocessError) as e:
                self.debug.log_state("install_dependencies_error", {
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'frontend_dir': str(self._frontend_dir)
                })
                return False
    
    @DebugLogger("frontend_orchestrator").trace_function("kill_existing_processes")
    def kill_existing_processes(self) -> bool:
        """
        Kill existing frontend development server processes.
        
        Returns:
            bool: True if processes were killed successfully or none existed
        """
        with self._lock:
            try:
                killed_processes = 0
                
                self.debug.log_state("kill_existing_start", {
                    'target_processes': ['vite', 'npm dev']
                })
                
                # Kill Vite dev servers
                try:
                    result = subprocess.run(
                        ['pkill', '-f', 'vite'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        killed_processes += 1
                        self.debug.log_state("killed_vite_processes", {
                            'success': True,
                            'return_code': result.returncode
                        })
                except subprocess.TimeoutExpired:
                    self.debug.log_state("kill_vite_timeout", {
                        'timeout_seconds': 10
                    })
                except Exception as e:
                    self.debug.log_state("kill_vite_error", {
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
                
                # Kill npm dev processes
                try:
                    result = subprocess.run(
                        ['pkill', '-f', 'npm.*dev'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        killed_processes += 1
                        self.debug.log_state("killed_npm_processes", {
                            'success': True,
                            'return_code': result.returncode
                        })
                except subprocess.TimeoutExpired:
                    self.debug.log_state("kill_npm_timeout", {
                        'timeout_seconds': 10
                    })
                except Exception as e:
                    self.debug.log_state("kill_npm_error", {
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
                
                # Wait for processes to terminate
                time.sleep(2)
                
                self.debug.log_state("kill_existing_complete", {
                    'killed_process_types': killed_processes,
                    'success': True
                })
                
                return True
                
            except Exception as e:
                self.debug.log_state("kill_existing_error", {
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                return True  # Not finding processes to kill is still success
    
    def _check_port_available(self, port: int, host: str = "0.0.0.0") -> bool:
        """Check if a port is available for binding"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except (OSError, socket.error):
            return False
    
    @DebugLogger("frontend_orchestrator").trace_function("start_frontend_server")
    def start_frontend_server(self, port: int = 5173, backend_port: int = 8000) -> Dict[str, Any]:
        """
        Start the frontend development server.
        
        Args:
            port: Port for frontend server (default: 5173)
            backend_port: Backend API port for CORS configuration (default: 8000)
            
        Returns:
            Dict with keys: success, port, process, error
        """
        with self._lock:
            try:
                # Check if we already have a running process
                if self._current_process and self._current_process.poll() is None:
                    self.debug.log_state("start_server_already_running", {
                        'current_port': self._current_port,
                        'current_pid': self._current_process.pid
                    })
                    return {
                        'success': False,
                        'error': f'Frontend server already running on port {self._current_port}',
                        'port': self._current_port,
                        'process': self._current_process
                    }
                
                # Check if frontend directory exists
                if not self._frontend_dir.exists():
                    error_msg = f"Frontend directory not found: {self._frontend_dir}"
                    self.debug.log_state("start_server_no_directory", {
                        'frontend_dir': str(self._frontend_dir),
                        'error': error_msg
                    })
                    return {
                        'success': False,
                        'error': error_msg,
                        'port': None,
                        'process': None
                    }
                
                # Check port availability
                if not self._check_port_available(port):
                    error_msg = f"Port {port} is not available"
                    self.debug.log_state("start_server_port_unavailable", {
                        'requested_port': port,
                        'error': error_msg
                    })
                    return {
                        'success': False,
                        'error': error_msg,
                        'port': port,
                        'process': None
                    }
                
                # Set up environment variables
                env = os.environ.copy()
                env['VITE_API_URL'] = f'http://localhost:{backend_port}'
                
                self.debug.log_state("start_server_begin", {
                    'port': port,
                    'backend_port': backend_port,
                    'frontend_dir': str(self._frontend_dir),
                    'vite_api_url': env['VITE_API_URL']
                })
                
                # Start the frontend dev server
                process = subprocess.Popen(
                    ['npm', 'run', 'dev', '--', '--port', str(port), '--host', '0.0.0.0'],
                    cwd=self._frontend_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Give the process a moment to start
                time.sleep(2)
                
                # Check if process is still running
                if process.poll() is None:
                    # Process is running
                    self._current_process = process
                    self._current_port = port
                    
                    self.debug.log_state("start_server_success", {
                        'port': port,
                        'pid': process.pid,
                        'backend_port': backend_port,
                        'process_status': 'running'
                    })
                    
                    return {
                        'success': True,
                        'port': port,
                        'process': process,
                        'pid': process.pid,
                        'backend_port': backend_port
                    }
                else:
                    # Process terminated
                    stdout, stderr = process.communicate(timeout=5)
                    error_msg = f"Frontend server failed to start (exit code: {process.returncode})"
                    if stderr:
                        error_msg += f": {stderr.strip()}"
                    
                    self.debug.log_state("start_server_process_failed", {
                        'port': port,
                        'exit_code': process.returncode,
                        'stderr': stderr[:500] if stderr else None,
                        'stdout': stdout[:500] if stdout else None
                    })
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'port': port,
                        'process': None,
                        'exit_code': process.returncode
                    }
                    
            except (OSError, subprocess.SubprocessError) as e:
                error_msg = f"Error starting frontend server: {e}"
                self.debug.log_state("start_server_error", {
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'port': port
                })
                
                return {
                    'success': False,
                    'error': error_msg,
                    'port': port,
                    'process': None
                }
    
    @DebugLogger("frontend_orchestrator").trace_function("stop_frontend_server")
    def stop_frontend_server(self, timeout: int = 10) -> bool:
        """
        Stop the frontend development server gracefully.
        
        Args:
            timeout: Seconds to wait for graceful termination before force kill
            
        Returns:
            bool: True if server was stopped successfully
        """
        with self._lock:
            if self._current_process is None:
                self.debug.log_state("stop_server_no_process", {
                    'reason': 'no_current_process'
                })
                return True  # No process to stop is success
            
            process = self._current_process
            
            self.debug.log_state("stop_server_start", {
                'pid': getattr(process, 'pid', 'unknown'),
                'port': self._current_port,
                'timeout': timeout
            })
            
            try:
                # Check if process is already terminated
                if process.poll() is not None:
                    self.debug.log_state("stop_server_already_stopped", {
                        'pid': process.pid,
                        'exit_code': process.returncode
                    })
                    self._current_process = None
                    self._current_port = None
                    return True
                
                # Try graceful termination
                process.terminate()
                self.debug.log_state("stop_server_terminate_sent", {
                    'pid': process.pid
                })
                
                # Wait for graceful termination
                start_time = time.time()
                while (time.time() - start_time) < timeout:
                    if process.poll() is not None:
                        self.debug.log_state("stop_server_terminated_gracefully", {
                            'pid': process.pid,
                            'duration': time.time() - start_time,
                            'exit_code': process.returncode
                        })
                        self._current_process = None
                        self._current_port = None
                        return True
                    time.sleep(0.1)
                
                # Graceful termination failed, force kill
                self.debug.log_state("stop_server_force_kill", {
                    'pid': process.pid,
                    'graceful_timeout': timeout
                })
                
                process.kill()
                
                # Wait briefly for kill to take effect
                start_time = time.time()
                kill_timeout = 5
                while (time.time() - start_time) < kill_timeout:
                    if process.poll() is not None:
                        self.debug.log_state("stop_server_force_killed", {
                            'pid': process.pid,
                            'duration': time.time() - start_time,
                            'exit_code': process.returncode
                        })
                        self._current_process = None
                        self._current_port = None
                        return True
                    time.sleep(0.1)
                
                # Even force kill failed
                self.debug.log_state("stop_server_kill_failed", {
                    'pid': process.pid,
                    'still_running': process.poll() is None
                })
                
                return False
                
            except Exception as e:
                self.debug.log_state("stop_server_error", {
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'pid': getattr(process, 'pid', 'unknown')
                })
                
                # Reset state even on error
                self._current_process = None
                self._current_port = None
                
                return False
    
    def get_frontend_status(self) -> Dict[str, Any]:
        """
        Get current frontend server status.
        
        Returns:
            Dict with status information including running state, port, pid, etc.
        """
        with self._lock:
            try:
                if self._current_process is None:
                    return {
                        'running': False,
                        'process': None,
                        'pid': None,
                        'port': None,
                        'status': 'not_started'
                    }
                
                # Check if process is still running
                poll_result = self._current_process.poll()
                is_running = poll_result is None
                
                status = {
                    'running': is_running,
                    'process': self._current_process,
                    'pid': self._current_process.pid,
                    'port': self._current_port,
                    'status': 'running' if is_running else 'terminated'
                }
                
                if not is_running:
                    status['exit_code'] = poll_result
                    # Clean up terminated process
                    self._current_process = None
                    self._current_port = None
                
                return status
                
            except Exception as e:
                return {
                    'running': False,
                    'process': self._current_process,
                    'pid': getattr(self._current_process, 'pid', None),
                    'port': self._current_port,
                    'status': 'error',
                    'error': str(e)
                }
    
    @DebugLogger("frontend_orchestrator").trace_function("cleanup_all_processes")
    def cleanup_all_processes(self) -> bool:
        """
        Cleanup all frontend processes (current + system-wide).
        
        Returns:
            bool: True if cleanup succeeded
        """
        with self._lock:
            success = True
            
            self.debug.log_state("cleanup_all_start", {
                'has_current_process': self._current_process is not None,
                'current_port': self._current_port
            })
            
            # Stop current process
            if self._current_process:
                if not self.stop_frontend_server():
                    success = False
                    self.debug.log_state("cleanup_current_failed", {
                        'pid': getattr(self._current_process, 'pid', 'unknown')
                    })
            
            # Kill any remaining frontend processes system-wide
            if not self.kill_existing_processes():
                success = False
                self.debug.log_state("cleanup_system_wide_failed", {})
            
            self.debug.log_state("cleanup_all_complete", {
                'success': success,
                'current_process_cleaned': self._current_process is None,
                'current_port_reset': self._current_port is None
            })
            
            return success
    
    @classmethod
    def create_orchestrator(cls, frontend_dir: Optional[Path] = None) -> 'FrontendOrchestrator':
        """
        Factory method to create a FrontendOrchestrator instance.
        
        Args:
            frontend_dir: Optional path to frontend directory
            
        Returns:
            FrontendOrchestrator: New instance configured with debug logging
        """
        return cls(frontend_dir=frontend_dir)
    
    def __del__(self):
        """Cleanup processes when FrontendOrchestrator is destroyed"""
        try:
            if self._current_process:
                self.stop_frontend_server(timeout=5)
        except:
            # Ignore all errors during destructor cleanup
            pass