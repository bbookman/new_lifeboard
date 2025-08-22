"""
Network Recovery Service for handling network binding failures and recovery

This service provides automatic recovery mechanisms for network and port issues,
including hung states, zombie processes, and binding failures.
"""

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from services.port_state_service import (
    PortState,
    PortStateService,
)

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Network recovery strategies"""
    RESTART_SERVICE = "restart_service"
    KILL_PROCESS = "kill_process"
    REBIND_PORT = "rebind_port"
    USE_DIFFERENT_PORT = "use_different_port"
    WAIT_AND_RETRY = "wait_and_retry"
    NO_RECOVERY = "no_recovery"


class RecoveryOutcome(Enum):
    """Recovery attempt outcomes"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


@dataclass
class RecoveryResult:
    """Result of a recovery attempt"""
    strategy: RecoveryStrategy
    outcome: RecoveryOutcome
    message: str
    details: Dict[str, Any]
    recovery_time_seconds: float
    new_port: Optional[int] = None


class NetworkRecoveryService:
    """Service for recovering from network binding failures"""

    def __init__(self, port_service: Optional[PortStateService] = None):
        self.port_service = port_service or PortStateService()

        # Recovery configuration
        self.max_recovery_attempts = 3
        self.recovery_timeout_seconds = 30
        self.process_kill_timeout_seconds = 10
        self.port_rebind_delay_seconds = 2
        self.zombie_process_threshold_seconds = 300  # 5 minutes

    async def attempt_network_recovery(self, host: str, port: int,
                                     preferred_strategies: Optional[List[RecoveryStrategy]] = None) -> List[RecoveryResult]:
        """
        Attempt to recover from network binding issues
        
        Args:
            host: Target host address
            port: Target port number
            preferred_strategies: Ordered list of preferred recovery strategies
            
        Returns:
            List of recovery results attempted
        """
        logger.info(f"NETWORK_RECOVERY: Starting recovery for {host}:{port}")
        start_time = time.time()

        recovery_results = []

        try:
            # First, diagnose the current network state
            diagnosis = await self._diagnose_network_issue(host, port)
            logger.info(f"NETWORK_RECOVERY: Diagnosis: {diagnosis['issue_type']} - {diagnosis['description']}")

            # Determine recovery strategies based on diagnosis
            if preferred_strategies:
                strategies = preferred_strategies
            else:
                strategies = self._determine_recovery_strategies(diagnosis)

            logger.info(f"NETWORK_RECOVERY: Will attempt strategies: {[s.value for s in strategies]}")

            # Attempt each strategy until successful
            for strategy in strategies:
                if await self._should_stop_recovery(host, port):
                    logger.info("NETWORK_RECOVERY: Recovery no longer needed, stopping")
                    break

                result = await self._execute_recovery_strategy(strategy, host, port, diagnosis)
                recovery_results.append(result)

                logger.info(f"NETWORK_RECOVERY: Strategy {strategy.value} -> {result.outcome.value}: {result.message}")

                if result.outcome == RecoveryOutcome.SUCCESS:
                    logger.info(f"NETWORK_RECOVERY: Recovery successful with strategy: {strategy.value}")
                    break
                if result.outcome == RecoveryOutcome.PARTIAL_SUCCESS:
                    # Continue with next strategy but note partial success
                    logger.info(f"NETWORK_RECOVERY: Partial success with {strategy.value}, continuing...")
                    continue
                logger.warning(f"NETWORK_RECOVERY: Strategy {strategy.value} failed: {result.message}")
                continue

            total_time = time.time() - start_time
            logger.info(f"NETWORK_RECOVERY: Recovery attempt completed in {total_time:.2f}s")

        except Exception as e:
            logger.error(f"NETWORK_RECOVERY: Recovery attempt failed with exception: {e}")
            recovery_results.append(RecoveryResult(
                strategy=RecoveryStrategy.NO_RECOVERY,
                outcome=RecoveryOutcome.FAILED,
                message=f"Recovery failed with exception: {e!s}",
                details={"exception": str(e)},
                recovery_time_seconds=time.time() - start_time,
            ))

        return recovery_results

    async def _diagnose_network_issue(self, host: str, port: int) -> Dict[str, Any]:
        """Diagnose the specific network issue"""
        diagnosis = {
            "issue_type": "unknown",
            "description": "Unknown network issue",
            "severity": "medium",
            "suggested_strategies": [],
            "process_info": None,
            "port_state": None,
        }

        try:
            # Get detailed port validation
            validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=True)
            diagnosis["port_state"] = validation.state.value
            diagnosis["process_info"] = validation.process_info

            if validation.state == PortState.AVAILABLE:
                diagnosis["issue_type"] = "service_not_running"
                diagnosis["description"] = "No service bound to port"
                diagnosis["severity"] = "high"
                diagnosis["suggested_strategies"] = [RecoveryStrategy.RESTART_SERVICE]

            elif validation.state == PortState.CLOSED:
                diagnosis["issue_type"] = "service_hung"
                diagnosis["description"] = "Service bound but not responding"
                diagnosis["severity"] = "high"
                diagnosis["suggested_strategies"] = [RecoveryStrategy.RESTART_SERVICE, RecoveryStrategy.KILL_PROCESS]

            elif validation.state == PortState.CONFLICT:
                if validation.process_info and validation.process_info.get("is_our_server"):
                    diagnosis["issue_type"] = "duplicate_instance"
                    diagnosis["description"] = "Another instance of our server is running"
                    diagnosis["severity"] = "medium"
                    diagnosis["suggested_strategies"] = [RecoveryStrategy.KILL_PROCESS, RecoveryStrategy.USE_DIFFERENT_PORT]
                else:
                    diagnosis["issue_type"] = "external_conflict"
                    diagnosis["description"] = "External application using port"
                    diagnosis["severity"] = "medium"
                    diagnosis["suggested_strategies"] = [RecoveryStrategy.USE_DIFFERENT_PORT, RecoveryStrategy.WAIT_AND_RETRY]

            elif validation.state == PortState.LISTENING:
                # This shouldn't be an issue, but might indicate validation problems
                diagnosis["issue_type"] = "false_positive"
                diagnosis["description"] = "Port appears to be working normally"
                diagnosis["severity"] = "low"
                diagnosis["suggested_strategies"] = [RecoveryStrategy.NO_RECOVERY]

        except Exception as e:
            logger.warning(f"NETWORK_RECOVERY: Error during diagnosis: {e}")
            diagnosis["issue_type"] = "diagnosis_failed"
            diagnosis["description"] = f"Could not diagnose issue: {e!s}"
            diagnosis["severity"] = "high"
            diagnosis["suggested_strategies"] = [RecoveryStrategy.WAIT_AND_RETRY, RecoveryStrategy.USE_DIFFERENT_PORT]

        return diagnosis

    def _determine_recovery_strategies(self, diagnosis: Dict[str, Any]) -> List[RecoveryStrategy]:
        """Determine appropriate recovery strategies based on diagnosis"""
        strategies = []

        # Use suggested strategies from diagnosis
        suggested = diagnosis.get("suggested_strategies", [])
        for strategy in suggested:
            if strategy not in strategies:
                strategies.append(strategy)

        # Add fallback strategies
        fallbacks = [RecoveryStrategy.WAIT_AND_RETRY, RecoveryStrategy.USE_DIFFERENT_PORT]
        for fallback in fallbacks:
            if fallback not in strategies:
                strategies.append(fallback)

        return strategies

    async def _execute_recovery_strategy(self, strategy: RecoveryStrategy, host: str, port: int,
                                       diagnosis: Dict[str, Any]) -> RecoveryResult:
        """Execute a specific recovery strategy"""
        start_time = time.time()

        try:
            if strategy == RecoveryStrategy.RESTART_SERVICE:
                return await self._restart_service_recovery(host, port, diagnosis, start_time)
            if strategy == RecoveryStrategy.KILL_PROCESS:
                return await self._kill_process_recovery(host, port, diagnosis, start_time)
            if strategy == RecoveryStrategy.REBIND_PORT:
                return await self._rebind_port_recovery(host, port, diagnosis, start_time)
            if strategy == RecoveryStrategy.USE_DIFFERENT_PORT:
                return await self._different_port_recovery(host, port, diagnosis, start_time)
            if strategy == RecoveryStrategy.WAIT_AND_RETRY:
                return await self._wait_and_retry_recovery(host, port, diagnosis, start_time)
            if strategy == RecoveryStrategy.NO_RECOVERY:
                return RecoveryResult(
                    strategy=strategy,
                    outcome=RecoveryOutcome.NOT_ATTEMPTED,
                    message="No recovery needed or possible",
                    details={},
                    recovery_time_seconds=time.time() - start_time,
                )
            return RecoveryResult(
                strategy=strategy,
                outcome=RecoveryOutcome.FAILED,
                message=f"Unknown recovery strategy: {strategy}",
                details={},
                recovery_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            logger.error(f"NETWORK_RECOVERY: Error executing strategy {strategy.value}: {e}")
            return RecoveryResult(
                strategy=strategy,
                outcome=RecoveryOutcome.FAILED,
                message=f"Strategy execution failed: {e!s}",
                details={"exception": str(e)},
                recovery_time_seconds=time.time() - start_time,
            )

    async def _restart_service_recovery(self, host: str, port: int, diagnosis: Dict[str, Any],
                                      start_time: float) -> RecoveryResult:
        """Attempt to restart the service"""
        logger.info(f"NETWORK_RECOVERY: Attempting service restart for {host}:{port}")

        # This is a placeholder - in a real implementation, this would
        # coordinate with the service management system to restart the service

        # For now, we can try to kill existing process and let the caller restart
        process_info = diagnosis.get("process_info")
        if process_info and process_info.get("is_our_server"):
            try:
                pid = process_info["pid"]
                logger.info(f"NETWORK_RECOVERY: Terminating server process {pid}")

                # Try graceful shutdown first
                subprocess.run(["kill", "-TERM", str(pid)], timeout=5, check=True)
                await asyncio.sleep(3)

                # Check if still running
                try:
                    subprocess.run(["kill", "-0", str(pid)], timeout=2, check=True)
                    # Still running, force kill
                    subprocess.run(["kill", "-KILL", str(pid)], timeout=5, check=True)
                    logger.info(f"NETWORK_RECOVERY: Force killed process {pid}")
                except subprocess.CalledProcessError:
                    # Process already gone
                    logger.info(f"NETWORK_RECOVERY: Process {pid} terminated gracefully")

                # Wait for port to be released
                await asyncio.sleep(self.port_rebind_delay_seconds)

                # Verify port is now available
                validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=False)
                if validation.state == PortState.AVAILABLE:
                    return RecoveryResult(
                        strategy=RecoveryStrategy.RESTART_SERVICE,
                        outcome=RecoveryOutcome.SUCCESS,
                        message=f"Successfully killed conflicting process {pid}, port now available",
                        details={"killed_pid": pid, "port_state": validation.state.value},
                        recovery_time_seconds=time.time() - start_time,
                    )
                return RecoveryResult(
                    strategy=RecoveryStrategy.RESTART_SERVICE,
                    outcome=RecoveryOutcome.PARTIAL_SUCCESS,
                    message=f"Killed process {pid} but port still not available",
                    details={"killed_pid": pid, "port_state": validation.state.value},
                    recovery_time_seconds=time.time() - start_time,
                )

            except Exception as e:
                return RecoveryResult(
                    strategy=RecoveryStrategy.RESTART_SERVICE,
                    outcome=RecoveryOutcome.FAILED,
                    message=f"Failed to kill process: {e!s}",
                    details={"error": str(e)},
                    recovery_time_seconds=time.time() - start_time,
                )
        else:
            return RecoveryResult(
                strategy=RecoveryStrategy.RESTART_SERVICE,
                outcome=RecoveryOutcome.FAILED,
                message="No server process found to restart",
                details={},
                recovery_time_seconds=time.time() - start_time,
            )

    async def _kill_process_recovery(self, host: str, port: int, diagnosis: Dict[str, Any],
                                   start_time: float) -> RecoveryResult:
        """Kill conflicting process"""
        process_info = diagnosis.get("process_info")
        if not process_info:
            return RecoveryResult(
                strategy=RecoveryStrategy.KILL_PROCESS,
                outcome=RecoveryOutcome.FAILED,
                message="No process information available",
                details={},
                recovery_time_seconds=time.time() - start_time,
            )

        pid = process_info["pid"]
        logger.info(f"NETWORK_RECOVERY: Killing process {pid} using port {port}")

        try:
            # Try SIGTERM first
            subprocess.run(["kill", "-TERM", str(pid)], timeout=5, check=True)
            await asyncio.sleep(3)

            # Check if still running
            try:
                subprocess.run(["kill", "-0", str(pid)], timeout=2, check=True)
                # Still running, use SIGKILL
                subprocess.run(["kill", "-KILL", str(pid)], timeout=5, check=True)
                logger.info(f"NETWORK_RECOVERY: Force killed process {pid}")
            except subprocess.CalledProcessError:
                logger.info(f"NETWORK_RECOVERY: Process {pid} terminated gracefully")

            # Wait for port to be released
            await asyncio.sleep(self.port_rebind_delay_seconds)

            # Verify recovery
            validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=False)
            if validation.state == PortState.AVAILABLE:
                return RecoveryResult(
                    strategy=RecoveryStrategy.KILL_PROCESS,
                    outcome=RecoveryOutcome.SUCCESS,
                    message=f"Successfully killed process {pid}, port now available",
                    details={"killed_pid": pid},
                    recovery_time_seconds=time.time() - start_time,
                )
            return RecoveryResult(
                strategy=RecoveryStrategy.KILL_PROCESS,
                outcome=RecoveryOutcome.PARTIAL_SUCCESS,
                message=f"Killed process {pid} but port still not available",
                details={"killed_pid": pid, "port_state": validation.state.value},
                recovery_time_seconds=time.time() - start_time,
            )

        except subprocess.CalledProcessError as e:
            return RecoveryResult(
                strategy=RecoveryStrategy.KILL_PROCESS,
                outcome=RecoveryOutcome.FAILED,
                message=f"Failed to kill process {pid}: return code {e.returncode}",
                details={"pid": pid, "returncode": e.returncode},
                recovery_time_seconds=time.time() - start_time,
            )
        except Exception as e:
            return RecoveryResult(
                strategy=RecoveryStrategy.KILL_PROCESS,
                outcome=RecoveryOutcome.FAILED,
                message=f"Error killing process {pid}: {e!s}",
                details={"pid": pid, "error": str(e)},
                recovery_time_seconds=time.time() - start_time,
            )

    async def _rebind_port_recovery(self, host: str, port: int, diagnosis: Dict[str, Any],
                                  start_time: float) -> RecoveryResult:
        """Attempt to rebind to the same port"""
        logger.info(f"NETWORK_RECOVERY: Attempting port rebind for {host}:{port}")

        # Wait a moment for any lingering connections to close
        await asyncio.sleep(self.port_rebind_delay_seconds)

        # Test if port is now available
        validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=False)

        if validation.state == PortState.AVAILABLE:
            return RecoveryResult(
                strategy=RecoveryStrategy.REBIND_PORT,
                outcome=RecoveryOutcome.SUCCESS,
                message=f"Port {port} is now available for binding",
                details={"port_state": validation.state.value},
                recovery_time_seconds=time.time() - start_time,
            )
        return RecoveryResult(
            strategy=RecoveryStrategy.REBIND_PORT,
            outcome=RecoveryOutcome.FAILED,
            message=f"Port {port} still not available after waiting",
            details={"port_state": validation.state.value},
            recovery_time_seconds=time.time() - start_time,
        )

    async def _different_port_recovery(self, host: str, port: int, diagnosis: Dict[str, Any],
                                     start_time: float) -> RecoveryResult:
        """Find an alternative port"""
        logger.info(f"NETWORK_RECOVERY: Looking for alternative port starting from {port + 1}")

        try:
            # Find available port starting from the next port
            alternative_port = await self.port_service.find_available_port(port + 1, host)

            if alternative_port:
                return RecoveryResult(
                    strategy=RecoveryStrategy.USE_DIFFERENT_PORT,
                    outcome=RecoveryOutcome.SUCCESS,
                    message=f"Found alternative port: {alternative_port}",
                    details={"original_port": port, "alternative_port": alternative_port},
                    recovery_time_seconds=time.time() - start_time,
                    new_port=alternative_port,
                )
            return RecoveryResult(
                strategy=RecoveryStrategy.USE_DIFFERENT_PORT,
                outcome=RecoveryOutcome.FAILED,
                message="No alternative ports available",
                details={"search_start": port + 1},
                recovery_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            return RecoveryResult(
                strategy=RecoveryStrategy.USE_DIFFERENT_PORT,
                outcome=RecoveryOutcome.FAILED,
                message=f"Error finding alternative port: {e!s}",
                details={"error": str(e)},
                recovery_time_seconds=time.time() - start_time,
            )

    async def _wait_and_retry_recovery(self, host: str, port: int, diagnosis: Dict[str, Any],
                                     start_time: float) -> RecoveryResult:
        """Wait and retry approach"""
        wait_time = 5  # seconds
        logger.info(f"NETWORK_RECOVERY: Waiting {wait_time}s before retry")

        await asyncio.sleep(wait_time)

        # Test if issue has resolved itself
        validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=True)

        if validation.state == PortState.AVAILABLE:
            return RecoveryResult(
                strategy=RecoveryStrategy.WAIT_AND_RETRY,
                outcome=RecoveryOutcome.SUCCESS,
                message=f"Port {port} became available after waiting",
                details={"wait_time_seconds": wait_time, "port_state": validation.state.value},
                recovery_time_seconds=time.time() - start_time,
            )
        if validation.state == PortState.LISTENING and validation.can_connect:
            return RecoveryResult(
                strategy=RecoveryStrategy.WAIT_AND_RETRY,
                outcome=RecoveryOutcome.SUCCESS,
                message=f"Service on port {port} is now responding",
                details={"wait_time_seconds": wait_time, "port_state": validation.state.value},
                recovery_time_seconds=time.time() - start_time,
            )
        return RecoveryResult(
            strategy=RecoveryStrategy.WAIT_AND_RETRY,
            outcome=RecoveryOutcome.FAILED,
            message=f"Issue persists after waiting {wait_time}s",
            details={"wait_time_seconds": wait_time, "port_state": validation.state.value},
            recovery_time_seconds=time.time() - start_time,
        )

    async def _should_stop_recovery(self, host: str, port: int) -> bool:
        """Check if recovery should be stopped (issue resolved)"""
        try:
            validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=True)

            # Stop if port is available or if service is responding properly
            return (validation.state == PortState.AVAILABLE or
                   (validation.state == PortState.LISTENING and validation.can_connect))
        except Exception:
            # If we can't check, continue with recovery
            return False

    async def monitor_network_health(self, host: str, port: int,
                                   check_interval_seconds: int = 60,
                                   auto_recover: bool = True) -> None:
        """
        Continuously monitor network health and auto-recover if needed
        
        This is intended for long-running monitoring
        """
        logger.info(f"NETWORK_RECOVERY: Starting network health monitoring for {host}:{port}")

        consecutive_failures = 0
        max_consecutive_failures = 3

        try:
            while True:
                try:
                    validation = await self.port_service.validate_server_binding(host, port)

                    if validation["is_healthy"]:
                        if consecutive_failures > 0:
                            logger.info(f"NETWORK_RECOVERY: Network health restored after {consecutive_failures} failures")
                            consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"NETWORK_RECOVERY: Network health check failed ({consecutive_failures}/{max_consecutive_failures})")

                        for issue in validation.get("issues", []):
                            logger.warning(f"NETWORK_RECOVERY: Issue: {issue['message']}")

                        # Attempt recovery if enabled and threshold reached
                        if auto_recover and consecutive_failures >= max_consecutive_failures:
                            logger.error("NETWORK_RECOVERY: Max failures reached, attempting recovery...")

                            recovery_results = await self.attempt_network_recovery(host, port)

                            # Check if any recovery succeeded
                            recovery_succeeded = any(r.outcome == RecoveryOutcome.SUCCESS for r in recovery_results)

                            if recovery_succeeded:
                                logger.info("NETWORK_RECOVERY: Automatic recovery successful")
                                consecutive_failures = 0
                            else:
                                logger.error("NETWORK_RECOVERY: Automatic recovery failed")
                                # Could implement escalation here (alerts, etc.)

                except Exception as e:
                    logger.error(f"NETWORK_RECOVERY: Error during health monitoring: {e}")
                    consecutive_failures += 1

                await asyncio.sleep(check_interval_seconds)

        except asyncio.CancelledError:
            logger.info("NETWORK_RECOVERY: Network health monitoring cancelled")
        except Exception as e:
            logger.error(f"NETWORK_RECOVERY: Network health monitoring failed: {e}")
