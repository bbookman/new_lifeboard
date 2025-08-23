"""
ProcessManager - Extracted from api/server.py for Phase 1 refactoring

Handles subprocess lifecycle management with debug logging integration.
Part of TDD-driven cleanup plan for Lifeboard codebase.
"""

import subprocess
import signal
import time
import threading
import uuid
import psutil
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from core.debug_logger import DebugLogger


class ProcessManagerInterface(ABC):
    """Abstract interface for process management"""
    
    @abstractmethod
    def start_process(self, command: List[str], **kwargs) -> str:
        """Start a new process and return process ID"""
        pass
    
    @abstractmethod
    def stop_process(self, process_id: str, timeout: int = 10) -> bool:
        """Stop a process gracefully, with optional force kill"""
        pass
    
    @abstractmethod
    def monitor_health(self) -> Dict[str, Any]:
        """Get health information for all managed processes"""
        pass


class ProcessManager(ProcessManagerInterface):
    """
    Manages subprocess lifecycle with health monitoring and graceful shutdown.
    
    Features:
    - Process lifecycle management (start, stop, monitor)
    - Health monitoring with CPU and memory tracking
    - Graceful shutdown with configurable timeout
    - Debug logging integration
    - Thread-safe operations
    - Custom exception handling
    """
    
    class ProcessStartError(Exception):
        """Raised when process fails to start"""
        pass
    
    class ProcessStopError(Exception):
        """Raised when process fails to stop properly"""
        pass
    
    def __init__(self):
        """Initialize ProcessManager with debug logging"""
        self.debug = DebugLogger("process_manager")
        self.processes: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        
        self.debug.log_state("process_manager_init", {
            'initialized_at': datetime.now(timezone.utc).isoformat(),
            'thread_safe': True,
            'debug_enabled': True
        })
    
    @DebugLogger("process_manager").trace_function("start_process")
    def start_process(self, command: List[str], **kwargs) -> str:
        """
        Start a new process with the given command and options.
        
        Args:
            command: List of command and arguments to execute
            **kwargs: Additional arguments passed to subprocess.Popen
                     Common options: env, cwd, stdout, stderr, text
        
        Returns:
            str: Unique process ID for tracking
            
        Raises:
            ProcessStartError: If process fails to start
        """
        with self._lock:
            process_id = str(uuid.uuid4())
            start_time = time.time()
            
            # Set default subprocess options
            subprocess_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'text': True
            }
            subprocess_kwargs.update(kwargs)
            
            self.debug.log_state("process_start_attempt", {
                'process_id': process_id,
                'command': command,
                'kwargs': list(subprocess_kwargs.keys()),
                'active_processes': len(self.processes)
            })
            
            try:
                # Start the process
                process = subprocess.Popen(command, **subprocess_kwargs)
                
                # Store process information
                self.processes[process_id] = {
                    'process': process,
                    'command': command,
                    'start_time': start_time,
                    'status': 'running',
                    'pid': process.pid,
                    'env': subprocess_kwargs.get('env'),
                    'cwd': subprocess_kwargs.get('cwd')
                }
                
                self.debug.log_state("process_started", {
                    'process_id': process_id,
                    'pid': process.pid,
                    'command': ' '.join(command),
                    'total_processes': len(self.processes)
                })
                
                return process_id
                
            except (OSError, subprocess.SubprocessError, FileNotFoundError) as e:
                self.debug.log_state("process_start_failed", {
                    'process_id': process_id,
                    'command': command,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                raise self.ProcessStartError(f"Failed to start process {' '.join(command)}: {e}")
    
    @DebugLogger("process_manager").trace_function("stop_process")
    def stop_process(self, process_id: str, timeout: int = 10) -> bool:
        """
        Stop a process gracefully with optional force kill.
        
        Args:
            process_id: Process ID returned by start_process
            timeout: Seconds to wait for graceful termination before force kill
            
        Returns:
            bool: True if process was stopped successfully, False if not found
            
        Raises:
            ProcessStopError: If process exists but cannot be stopped
        """
        with self._lock:
            if process_id not in self.processes:
                self.debug.log_state("process_stop_not_found", {
                    'process_id': process_id,
                    'active_processes': list(self.processes.keys())
                })
                return False
            
            process_info = self.processes[process_id]
            process = process_info['process']
            
            self.debug.log_state("process_stop_attempt", {
                'process_id': process_id,
                'pid': process.pid,
                'timeout': timeout,
                'current_status': process_info['status']
            })
            
            try:
                # Check if process is already terminated
                if process.poll() is not None:
                    process_info['status'] = 'already_stopped'
                    self.debug.log_state("process_already_stopped", {
                        'process_id': process_id,
                        'exit_code': process.returncode
                    })
                    return True
                
                # Try graceful termination first
                process.terminate()
                
                try:
                    # Wait for graceful termination
                    process.wait(timeout=timeout)
                    process_info['status'] = 'stopped'
                    
                    self.debug.log_state("process_stopped_gracefully", {
                        'process_id': process_id,
                        'pid': process.pid,
                        'exit_code': process.returncode
                    })
                    return True
                    
                except subprocess.TimeoutExpired:
                    # Graceful termination failed, force kill
                    self.debug.log_state("process_graceful_timeout", {
                        'process_id': process_id,
                        'timeout': timeout,
                        'attempting_force_kill': True
                    })
                    
                    process.kill()
                    try:
                        process.wait(timeout=5)  # Short timeout for kill
                        process_info['status'] = 'force_killed'
                        
                        self.debug.log_state("process_force_killed", {
                            'process_id': process_id,
                            'pid': process.pid,
                            'exit_code': process.returncode
                        })
                        return True
                        
                    except subprocess.TimeoutExpired:
                        # Even force kill failed
                        process_info['status'] = 'kill_failed'
                        self.debug.log_state("process_kill_failed", {
                            'process_id': process_id,
                            'pid': process.pid
                        })
                        raise self.ProcessStopError(
                            f"Process {process_id} (PID {process.pid}) could not be stopped"
                        )
                        
            except (OSError, ProcessLookupError) as e:
                # Process might have already been terminated externally
                process_info['status'] = 'external_termination'
                self.debug.log_state("process_external_termination", {
                    'process_id': process_id,
                    'error': str(e)
                })
                return True
    
    @DebugLogger("process_manager").trace_function("monitor_health")
    def monitor_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health information for all managed processes.
        
        Returns:
            Dict containing:
            - total_processes: Total number of managed processes
            - running_processes: Number of currently running processes
            - stopped_processes: Number of stopped processes
            - processes: Detailed info for each process
        """
        with self._lock:
            health_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_processes': len(self.processes),
                'running_processes': 0,
                'stopped_processes': 0,
                'processes': {}
            }
            
            for process_id, process_info in self.processes.items():
                process = process_info['process']
                current_time = time.time()
                
                # Get basic process status
                poll_result = process.poll()
                is_running = poll_result is None
                
                if is_running:
                    health_data['running_processes'] += 1
                    status = 'running'
                else:
                    health_data['stopped_processes'] += 1
                    status = 'stopped'
                    
                # Calculate uptime
                uptime_seconds = current_time - process_info['start_time']
                
                process_health = {
                    'status': status,
                    'pid': process.pid,
                    'uptime_seconds': round(uptime_seconds, 2),
                    'command': ' '.join(process_info['command']),
                    'exit_code': poll_result
                }
                
                # Get CPU and memory usage for running processes
                if is_running:
                    try:
                        proc = psutil.Process(process.pid)
                        process_health.update({
                            'cpu_percent': round(proc.cpu_percent(), 2),
                            'memory_mb': round(proc.memory_info().rss / 1024 / 1024, 2),
                            'memory_percent': round(proc.memory_percent(), 2)
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        # Process might have terminated or we don't have permission
                        process_health.update({
                            'cpu_percent': 0.0,
                            'memory_mb': 0.0,
                            'memory_percent': 0.0,
                            'monitoring_error': 'Process not accessible for monitoring'
                        })
                
                health_data['processes'][process_id] = process_health
            
            self.debug.log_state("health_monitoring_complete", {
                'total_processes': health_data['total_processes'],
                'running': health_data['running_processes'],
                'stopped': health_data['stopped_processes']
            })
            
            return health_data
    
    def get_cpu_usage(self, pid: int) -> float:
        """Get CPU usage percentage for a process"""
        try:
            proc = psutil.Process(pid)
            return round(proc.cpu_percent(), 2)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return 0.0
    
    def get_memory_usage(self, pid: int) -> float:
        """Get memory usage in MB for a process"""
        try:
            proc = psutil.Process(pid)
            return round(proc.memory_info().rss / 1024 / 1024, 2)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return 0.0
    
    def cleanup_all_processes(self, timeout: int = 10) -> Dict[str, bool]:
        """
        Stop all managed processes gracefully.
        
        Args:
            timeout: Seconds to wait for each process to stop gracefully
            
        Returns:
            Dict mapping process_id to success status
        """
        with self._lock:
            results = {}
            
            self.debug.log_state("cleanup_all_start", {
                'total_processes': len(self.processes),
                'timeout': timeout
            })
            
            for process_id in list(self.processes.keys()):
                try:
                    results[process_id] = self.stop_process(process_id, timeout)
                except Exception as e:
                    self.debug.log_state("cleanup_error", {
                        'process_id': process_id,
                        'error': str(e)
                    })
                    results[process_id] = False
            
            successful_stops = sum(results.values())
            self.debug.log_state("cleanup_all_complete", {
                'total_processes': len(results),
                'successful_stops': successful_stops,
                'failed_stops': len(results) - successful_stops
            })
            
            return results
    
    def get_process_info(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific process"""
        with self._lock:
            if process_id not in self.processes:
                return None
            
            process_info = self.processes[process_id].copy()
            # Remove the actual process object from the returned info
            process_info.pop('process', None)
            return process_info
    
    def list_process_ids(self) -> List[str]:
        """Get list of all managed process IDs"""
        with self._lock:
            return list(self.processes.keys())
    
    def __del__(self):
        """Cleanup processes when ProcessManager is destroyed"""
        try:
            self.cleanup_all_processes(timeout=5)
        except:
            # Ignore errors during cleanup in destructor
            pass