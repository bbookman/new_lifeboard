"""
ProcessManager - Manages subprocess lifecycle for Lifeboard application.

Extracted from api/server.py as part of TDD-driven architecture cleanup.
Handles process creation, monitoring, and graceful termination.
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a managed process."""
    name: str
    process: subprocess.Popen
    command: List[str]
    cwd: Optional[str]
    started_at: float

    @property
    def pid(self) -> int:
        """Get the process ID."""
        return self.process.pid

    @property
    def is_running(self) -> bool:
        """Check if the process is still running."""
        return self.process.poll() is None


class ProcessManager:
    """Manages subprocess lifecycle with monitoring and graceful shutdown."""

    def __init__(self):
        """Initialize ProcessManager with empty process registry."""
        self.processes: Dict[str, ProcessInfo] = {}
        logger.info("PROCESS: ProcessManager initialized")

    def start_process(
        self,
        name: str,
        command: List[str],
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        stdout: Optional[Any] = None,
        stderr: Optional[Any] = None,
    ) -> ProcessInfo:
        """
        Start a new process and register it for management.
        
        Args:
            name: Unique name for the process
            command: Command and arguments to execute
            cwd: Working directory for the process
            env: Environment variables
            stdout: Stdout redirection
            stderr: Stderr redirection
            
        Returns:
            ProcessInfo: Information about the started process
            
        Raises:
            RuntimeError: If process fails to start
        """
        if name in self.processes:
            raise ValueError(f"Process '{name}' already exists")

        try:
            logger.info(f"PROCESS: Starting process '{name}' with command: {' '.join(command)}")

            process = subprocess.Popen(
                command,
                cwd=str(cwd) if cwd else None,
                env=env,
                stdout=stdout,
                stderr=stderr,
            )

            process_info = ProcessInfo(
                name=name,
                process=process,
                command=command,
                cwd=str(cwd) if cwd else None,
                started_at=time.time(),
            )

            self.processes[name] = process_info
            logger.info(f"PROCESS: Started process '{name}' with PID {process.pid}")

            return process_info

        except (subprocess.CalledProcessError, OSError) as e:
            logger.error(f"PROCESS: Failed to start process '{name}': {e}")
            raise RuntimeError(f"Failed to start process '{name}': {e}")

    def stop_process(self, name: str, timeout: int = 10) -> bool:
        """
        Stop a managed process gracefully, with forced termination if needed.
        
        Args:
            name: Name of the process to stop
            timeout: Seconds to wait for graceful termination
            
        Returns:
            bool: True if process stopped successfully, False otherwise
        """
        if name not in self.processes:
            logger.warning(f"PROCESS: Cannot stop unknown process '{name}'")
            return False

        process_info = self.processes[name]
        process = process_info.process

        try:
            # Check if already terminated
            if process.poll() is not None:
                logger.info(f"PROCESS: Process '{name}' already terminated")
                del self.processes[name]
                return True

            # Try graceful termination first
            logger.info(f"PROCESS: Sending SIGTERM to process '{name}' (PID {process.pid})")
            process.terminate()

            # Wait for graceful termination
            start_time = time.time()
            graceful_terminated = False
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    logger.info(f"PROCESS: Process '{name}' terminated gracefully")
                    del self.processes[name]
                    graceful_terminated = True
                    return True
                time.sleep(0.1)

            # Force kill if graceful termination failed
            if not graceful_terminated:
                logger.warning(f"PROCESS: Process '{name}' didn't terminate gracefully, using SIGKILL")
                process.kill()

                # Wait a bit more for forced termination
                time.sleep(1)
                if process.poll() is not None:
                    logger.info(f"PROCESS: Process '{name}' terminated forcefully")
                    del self.processes[name]
                    return True
                logger.error(f"PROCESS: Failed to terminate process '{name}'")
                return False

        except Exception as e:
            logger.error(f"PROCESS: Error stopping process '{name}': {e}")
            return False

    def is_process_healthy(self, name: str) -> bool:
        """
        Check if a managed process is healthy (running).
        
        Args:
            name: Name of the process to check
            
        Returns:
            bool: True if process is running, False otherwise
        """
        if name not in self.processes:
            return False

        process_info = self.processes[name]
        is_running = process_info.is_running

        if not is_running:
            logger.info(f"PROCESS: Process '{name}' is no longer running")
            # Clean up dead process from registry
            del self.processes[name]

        return is_running

    def get_all_processes(self) -> Dict[str, ProcessInfo]:
        """
        Get information about all managed processes.
        
        Returns:
            Dict[str, ProcessInfo]: Dictionary of process names to ProcessInfo
        """
        # Clean up dead processes first
        dead_processes = []
        for name, process_info in self.processes.items():
            if not process_info.is_running:
                dead_processes.append(name)

        for name in dead_processes:
            logger.debug(f"PROCESS: Cleaning up dead process '{name}' from registry")
            del self.processes[name]

        return self.processes.copy()

    def cleanup_all_processes(self, timeout: int = 10) -> Dict[str, bool]:
        """
        Stop all managed processes and clean up.
        
        Args:
            timeout: Seconds to wait for each process to terminate
            
        Returns:
            Dict[str, bool]: Results of stopping each process
        """
        results = {}
        process_names = list(self.processes.keys())

        logger.info(f"PROCESS: Cleaning up {len(process_names)} managed processes")

        for name in process_names:
            success = self.stop_process(name, timeout=timeout)
            results[name] = success

        logger.info(f"PROCESS: Cleanup complete. Results: {results}")
        return results

    def get_process_info(self, name: str) -> Optional[ProcessInfo]:
        """
        Get information about a specific process.
        
        Args:
            name: Name of the process
            
        Returns:
            ProcessInfo or None if process not found
        """
        return self.processes.get(name)
