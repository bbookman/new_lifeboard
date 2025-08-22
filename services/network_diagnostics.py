"""
Network Diagnostics Service for comprehensive network state analysis

This service provides detailed network diagnostics, debugging tools,
and comprehensive reporting for network-related issues.
"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.port_state_service import PortStateService
from services.session_lock_manager import SessionLockManager

logger = logging.getLogger(__name__)


@dataclass
class NetworkDiagnostic:
    """Individual network diagnostic result"""
    test_name: str
    status: str  # pass, fail, warning, info
    message: str
    details: Dict[str, Any]
    execution_time_ms: float
    timestamp: datetime


class NetworkDiagnosticsService:
    """Comprehensive network diagnostics and debugging service"""

    def __init__(self):
        self.port_service = PortStateService()
        self.session_manager = SessionLockManager()

        # Diagnostics configuration
        self.command_timeout_seconds = 10
        self.network_timeout_seconds = 5
        self.comprehensive_port_range = 50

    async def run_comprehensive_diagnostics(self, host: str = "127.0.0.1",
                                          port: int = 8000) -> Dict[str, Any]:
        """
        Run comprehensive network diagnostics
        
        Returns detailed diagnostic report
        """
        logger.info(f"NETWORK_DIAG: Starting comprehensive diagnostics for {host}:{port}")
        start_time = time.time()

        diagnostics = []
        summary = {
            "target_host": host,
            "target_port": port,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "warning_tests": 0,
            "execution_time_seconds": 0,
            "overall_status": "unknown",
        }

        try:
            # Basic connectivity tests
            diagnostics.extend(await self._run_basic_connectivity_tests(host, port))

            # Port state analysis
            diagnostics.extend(await self._run_port_state_analysis(host, port))

            # Process analysis
            diagnostics.extend(await self._run_process_analysis(port))

            # System network tests
            diagnostics.extend(await self._run_system_network_tests(host, port))

            # Session management tests
            diagnostics.extend(await self._run_session_management_tests(host, port))

            # Network interface tests
            diagnostics.extend(await self._run_network_interface_tests(host))

            # Security and firewall tests
            diagnostics.extend(await self._run_security_tests(host, port))

            # Performance tests
            diagnostics.extend(await self._run_performance_tests(host, port))

            # Analyze results
            summary.update(self._analyze_diagnostic_results(diagnostics))
            summary["execution_time_seconds"] = time.time() - start_time

            logger.info(f"NETWORK_DIAG: Completed {summary['total_tests']} tests in {summary['execution_time_seconds']:.2f}s")

        except Exception as e:
            logger.error(f"NETWORK_DIAG: Diagnostics failed: {e}")
            diagnostics.append(NetworkDiagnostic(
                test_name="diagnostics_execution",
                status="fail",
                message=f"Diagnostics execution failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=0,
                timestamp=datetime.now(timezone.utc),
            ))

        return {
            "summary": summary,
            "diagnostics": [asdict(d) for d in diagnostics],
            "recommendations": self._generate_recommendations(diagnostics, host, port),
            "report_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "hostname": await self._get_hostname(),
                "platform": await self._get_platform_info(),
            },
        }

    async def _run_basic_connectivity_tests(self, host: str, port: int) -> List[NetworkDiagnostic]:
        """Basic connectivity tests"""
        diagnostics = []

        # Test 1: Basic port validation
        start_time = time.time()
        try:
            validation = await self.port_service.validate_port_binding(host, port, validate_connectivity=True)
            execution_time = (time.time() - start_time) * 1000

            if validation.state.value == "listening" and validation.can_connect:
                status = "pass"
                message = f"Port {port} is listening and accepting connections"
            elif validation.state.value == "available":
                status = "warning"
                message = f"Port {port} is available but no service is bound"
            else:
                status = "fail"
                message = f"Port {port} validation failed: {validation.state.value}"

            diagnostics.append(NetworkDiagnostic(
                test_name="basic_port_validation",
                status=status,
                message=message,
                details={
                    "port_state": validation.state.value,
                    "binding_status": validation.binding_status.value,
                    "can_bind": validation.can_bind,
                    "can_connect": validation.can_connect,
                    "response_time_ms": validation.response_time_ms,
                    "error_message": validation.error_message,
                },
                execution_time_ms=execution_time,
                timestamp=datetime.now(timezone.utc),
            ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="basic_port_validation",
                status="fail",
                message=f"Port validation test failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        # Test 2: Host resolution
        start_time = time.time()
        try:
            import socket
            resolved_ip = socket.gethostbyname(host)
            execution_time = (time.time() - start_time) * 1000

            diagnostics.append(NetworkDiagnostic(
                test_name="host_resolution",
                status="pass",
                message=f"Host {host} resolved to {resolved_ip}",
                details={"host": host, "resolved_ip": resolved_ip},
                execution_time_ms=execution_time,
                timestamp=datetime.now(timezone.utc),
            ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="host_resolution",
                status="fail",
                message=f"Failed to resolve host {host}: {e!s}",
                details={"host": host, "exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_port_state_analysis(self, host: str, port: int) -> List[NetworkDiagnostic]:
        """Detailed port state analysis"""
        diagnostics = []

        # Test: Port range scan
        start_time = time.time()
        try:
            port_range_start = max(1, port - 5)
            port_range_end = port + 5

            port_states = {}
            for test_port in range(port_range_start, port_range_end + 1):
                try:
                    validation = await self.port_service.validate_port_binding(host, test_port, validate_connectivity=False)
                    port_states[test_port] = {
                        "state": validation.state.value,
                        "can_bind": validation.can_bind,
                    }
                except Exception as e:
                    port_states[test_port] = {"state": "error", "error": str(e)}

            execution_time = (time.time() - start_time) * 1000

            # Analyze port range
            available_ports = [p for p, s in port_states.items() if s.get("state") == "available"]
            conflicted_ports = [p for p, s in port_states.items() if s.get("state") in ["conflict", "bound", "closed"]]

            if port in available_ports:
                status = "info"
                message = f"Target port {port} is available (found {len(available_ports)} available ports nearby)"
            elif port in conflicted_ports:
                status = "warning"
                message = f"Target port {port} has conflicts (found {len(available_ports)} available alternatives)"
            else:
                status = "info"
                message = "Port range analysis completed"

            diagnostics.append(NetworkDiagnostic(
                test_name="port_range_analysis",
                status=status,
                message=message,
                details={
                    "port_range": f"{port_range_start}-{port_range_end}",
                    "port_states": port_states,
                    "available_ports": available_ports,
                    "conflicted_ports": conflicted_ports,
                },
                execution_time_ms=execution_time,
                timestamp=datetime.now(timezone.utc),
            ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="port_range_analysis",
                status="fail",
                message=f"Port range analysis failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_process_analysis(self, port: int) -> List[NetworkDiagnostic]:
        """Process analysis for port usage"""
        diagnostics = []

        # Test: Process identification
        start_time = time.time()
        try:
            # Use lsof to find processes using the port
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "lsof", "-i", f":{port}", "-P", "-n",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.command_timeout_seconds,
            )

            stdout, stderr = await result.communicate()
            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0 and stdout:
                # Parse lsof output
                lines = stdout.decode().strip().split("\n")
                processes = []

                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 8:
                        processes.append({
                            "command": parts[0],
                            "pid": parts[1],
                            "user": parts[2],
                            "fd": parts[3],
                            "type": parts[4],
                            "device": parts[5],
                            "size_off": parts[6],
                            "node": parts[7],
                            "name": " ".join(parts[8:]) if len(parts) > 8 else "",
                        })

                if processes:
                    status = "info"
                    message = f"Found {len(processes)} process(es) using port {port}"
                else:
                    status = "info"
                    message = f"No processes found using port {port}"

                diagnostics.append(NetworkDiagnostic(
                    test_name="process_identification",
                    status=status,
                    message=message,
                    details={
                        "processes": processes,
                        "lsof_output": stdout.decode(),
                    },
                    execution_time_ms=execution_time,
                    timestamp=datetime.now(timezone.utc),
                ))
            else:
                diagnostics.append(NetworkDiagnostic(
                    test_name="process_identification",
                    status="info",
                    message=f"No processes found using port {port} (lsof returned {result.returncode})",
                    details={
                        "returncode": result.returncode,
                        "stderr": stderr.decode() if stderr else None,
                    },
                    execution_time_ms=execution_time,
                    timestamp=datetime.now(timezone.utc),
                ))

        except asyncio.TimeoutError:
            diagnostics.append(NetworkDiagnostic(
                test_name="process_identification",
                status="warning",
                message=f"Process identification timed out after {self.command_timeout_seconds}s",
                details={"timeout_seconds": self.command_timeout_seconds},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))
        except FileNotFoundError:
            diagnostics.append(NetworkDiagnostic(
                test_name="process_identification",
                status="warning",
                message="lsof command not available",
                details={"note": "Process identification requires lsof"},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))
        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="process_identification",
                status="fail",
                message=f"Process identification failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_system_network_tests(self, host: str, port: int) -> List[NetworkDiagnostic]:
        """System-level network tests"""
        diagnostics = []

        # Test: netstat analysis
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "netstat", "-an",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.command_timeout_seconds,
            )

            stdout, stderr = await result.communicate()
            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0 and stdout:
                netstat_output = stdout.decode()

                # Look for our port in the output
                port_lines = [line for line in netstat_output.split("\n") if f":{port} " in line or f":{port}\t" in line]

                if port_lines:
                    status = "info"
                    message = f"Found {len(port_lines)} netstat entries for port {port}"
                else:
                    status = "info"
                    message = f"No netstat entries found for port {port}"

                diagnostics.append(NetworkDiagnostic(
                    test_name="netstat_analysis",
                    status=status,
                    message=message,
                    details={
                        "port_lines": port_lines,
                        "netstat_sample": netstat_output[:1000] + "..." if len(netstat_output) > 1000 else netstat_output,
                    },
                    execution_time_ms=execution_time,
                    timestamp=datetime.now(timezone.utc),
                ))
            else:
                diagnostics.append(NetworkDiagnostic(
                    test_name="netstat_analysis",
                    status="warning",
                    message=f"netstat command failed (return code: {result.returncode})",
                    details={"returncode": result.returncode},
                    execution_time_ms=execution_time,
                    timestamp=datetime.now(timezone.utc),
                ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="netstat_analysis",
                status="warning",
                message=f"netstat analysis failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_session_management_tests(self, host: str, port: int) -> List[NetworkDiagnostic]:
        """Session management diagnostics"""
        diagnostics = []

        # Test: Session status
        start_time = time.time()
        try:
            session_status = await self.session_manager.get_session_status()
            execution_time = (time.time() - start_time) * 1000

            if session_status["has_current_session"]:
                status = "info"
                message = "Active session found"
            else:
                status = "info"
                message = "No active session"

            diagnostics.append(NetworkDiagnostic(
                test_name="session_management",
                status=status,
                message=message,
                details=session_status,
                execution_time_ms=execution_time,
                timestamp=datetime.now(timezone.utc),
            ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="session_management",
                status="fail",
                message=f"Session management test failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_network_interface_tests(self, host: str) -> List[NetworkDiagnostic]:
        """Network interface tests"""
        diagnostics = []

        # Test: Interface configuration
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "ifconfig",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.command_timeout_seconds,
            )

            stdout, stderr = await result.communicate()
            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0 and stdout:
                ifconfig_output = stdout.decode()

                # Look for relevant interfaces
                active_interfaces = []
                for line in ifconfig_output.split("\n"):
                    if line and not line.startswith(" ") and not line.startswith("\t"):
                        interface_name = line.split(":")[0]
                        if interface_name and interface_name not in ["lo", "lo0"]:
                            active_interfaces.append(interface_name)

                status = "info"
                message = f"Found {len(active_interfaces)} network interfaces"

                diagnostics.append(NetworkDiagnostic(
                    test_name="network_interfaces",
                    status=status,
                    message=message,
                    details={
                        "active_interfaces": active_interfaces,
                        "ifconfig_sample": ifconfig_output[:500] + "..." if len(ifconfig_output) > 500 else ifconfig_output,
                    },
                    execution_time_ms=execution_time,
                    timestamp=datetime.now(timezone.utc),
                ))
            else:
                diagnostics.append(NetworkDiagnostic(
                    test_name="network_interfaces",
                    status="warning",
                    message="Could not retrieve network interface information",
                    details={"returncode": result.returncode},
                    execution_time_ms=execution_time,
                    timestamp=datetime.now(timezone.utc),
                ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="network_interfaces",
                status="warning",
                message=f"Network interface test failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_security_tests(self, host: str, port: int) -> List[NetworkDiagnostic]:
        """Security and firewall tests"""
        diagnostics = []

        # Test: Firewall status (basic check)
        start_time = time.time()
        try:
            # Try to determine if firewall might be blocking
            import socket

            # Test connection from different addresses
            connection_tests = []
            test_addresses = ["127.0.0.1", "localhost"]
            if host not in test_addresses:
                test_addresses.append(host)

            for test_addr in test_addresses:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((test_addr, port))
                    sock.close()

                    connection_tests.append({
                        "address": test_addr,
                        "result": result,
                        "success": result == 0,
                    })
                except Exception as e:
                    connection_tests.append({
                        "address": test_addr,
                        "result": -1,
                        "success": False,
                        "error": str(e),
                    })

            execution_time = (time.time() - start_time) * 1000

            # Analyze results
            successful_connections = [t for t in connection_tests if t["success"]]

            if successful_connections:
                status = "pass"
                message = f"Network connectivity successful from {len(successful_connections)} addresses"
            else:
                status = "warning"
                message = "No successful connections - possible firewall/security restriction"

            diagnostics.append(NetworkDiagnostic(
                test_name="security_connectivity",
                status=status,
                message=message,
                details={"connection_tests": connection_tests},
                execution_time_ms=execution_time,
                timestamp=datetime.now(timezone.utc),
            ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="security_connectivity",
                status="fail",
                message=f"Security test failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    async def _run_performance_tests(self, host: str, port: int) -> List[NetworkDiagnostic]:
        """Performance tests"""
        diagnostics = []

        # Test: Connection timing
        start_time = time.time()
        try:
            timing_tests = []

            for i in range(3):  # Run 3 timing tests
                test_start = time.time()
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)

                    connect_start = time.time()
                    result = sock.connect_ex((host, port))
                    connect_time = (time.time() - connect_start) * 1000

                    if result == 0:
                        sock.close()
                        timing_tests.append({
                            "attempt": i + 1,
                            "success": True,
                            "connect_time_ms": connect_time,
                        })
                    else:
                        timing_tests.append({
                            "attempt": i + 1,
                            "success": False,
                            "connect_time_ms": connect_time,
                            "error_code": result,
                        })

                except Exception as e:
                    timing_tests.append({
                        "attempt": i + 1,
                        "success": False,
                        "error": str(e),
                    })

                # Small delay between tests
                await asyncio.sleep(0.1)

            execution_time = (time.time() - start_time) * 1000

            # Analyze timing results
            successful_tests = [t for t in timing_tests if t.get("success")]

            if successful_tests:
                avg_time = sum(t["connect_time_ms"] for t in successful_tests) / len(successful_tests)

                if avg_time < 10:
                    status = "pass"
                    message = f"Excellent connection performance: {avg_time:.1f}ms average"
                elif avg_time < 50:
                    status = "pass"
                    message = f"Good connection performance: {avg_time:.1f}ms average"
                elif avg_time < 100:
                    status = "warning"
                    message = f"Moderate connection performance: {avg_time:.1f}ms average"
                else:
                    status = "warning"
                    message = f"Slow connection performance: {avg_time:.1f}ms average"
            else:
                status = "fail"
                message = "No successful connection attempts for performance testing"
                avg_time = None

            diagnostics.append(NetworkDiagnostic(
                test_name="connection_performance",
                status=status,
                message=message,
                details={
                    "timing_tests": timing_tests,
                    "average_time_ms": avg_time,
                    "successful_attempts": len(successful_tests),
                    "total_attempts": len(timing_tests),
                },
                execution_time_ms=execution_time,
                timestamp=datetime.now(timezone.utc),
            ))

        except Exception as e:
            diagnostics.append(NetworkDiagnostic(
                test_name="connection_performance",
                status="fail",
                message=f"Performance test failed: {e!s}",
                details={"exception": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
            ))

        return diagnostics

    def _analyze_diagnostic_results(self, diagnostics: List[NetworkDiagnostic]) -> Dict[str, Any]:
        """Analyze diagnostic results and generate summary"""
        total_tests = len(diagnostics)
        passed_tests = len([d for d in diagnostics if d.status == "pass"])
        failed_tests = len([d for d in diagnostics if d.status == "fail"])
        warning_tests = len([d for d in diagnostics if d.status == "warning"])

        # Determine overall status
        if failed_tests > 0:
            overall_status = "critical"
        elif warning_tests > total_tests // 2:  # More than half are warnings
            overall_status = "warning"
        elif passed_tests > total_tests // 2:  # More than half passed
            overall_status = "healthy"
        else:
            overall_status = "degraded"

        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "warning_tests": warning_tests,
            "info_tests": total_tests - passed_tests - failed_tests - warning_tests,
            "overall_status": overall_status,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
        }

    def _generate_recommendations(self, diagnostics: List[NetworkDiagnostic],
                                host: str, port: int) -> List[Dict[str, str]]:
        """Generate recommendations based on diagnostic results"""
        recommendations = []

        # Analyze failed and warning diagnostics
        failed_diagnostics = [d for d in diagnostics if d.status == "fail"]
        warning_diagnostics = [d for d in diagnostics if d.status == "warning"]

        # Port-specific recommendations
        port_issues = [d for d in failed_diagnostics + warning_diagnostics
                      if "port" in d.test_name or "connectivity" in d.test_name]

        if port_issues:
            recommendations.append({
                "category": "port_management",
                "priority": "high",
                "action": f"Investigate port {port} conflicts",
                "description": "Port validation or connectivity issues detected",
            })

        # Process-related recommendations
        process_issues = [d for d in failed_diagnostics + warning_diagnostics
                         if "process" in d.test_name]

        if process_issues:
            recommendations.append({
                "category": "process_management",
                "priority": "medium",
                "action": "Review process status and conflicts",
                "description": "Process identification or management issues detected",
            })

        # Performance recommendations
        performance_issues = [d for d in warning_diagnostics
                            if "performance" in d.test_name]

        if performance_issues:
            recommendations.append({
                "category": "performance",
                "priority": "low",
                "action": "Optimize network performance",
                "description": "Network performance could be improved",
            })

        # Security recommendations
        security_issues = [d for d in failed_diagnostics + warning_diagnostics
                          if "security" in d.test_name or "firewall" in d.test_name]

        if security_issues:
            recommendations.append({
                "category": "security",
                "priority": "medium",
                "action": "Review firewall and security settings",
                "description": "Potential security or firewall restrictions detected",
            })

        # General recommendations based on overall health
        if not recommendations:
            recommendations.append({
                "category": "general",
                "priority": "info",
                "action": "No immediate action required",
                "description": "Network diagnostics completed successfully",
            })

        return recommendations

    async def _get_hostname(self) -> str:
        """Get system hostname"""
        try:
            import socket
            return socket.gethostname()
        except Exception:
            return "unknown"

    async def _get_platform_info(self) -> Dict[str, str]:
        """Get platform information"""
        try:
            import platform
            return {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            }
        except Exception:
            return {"error": "Could not retrieve platform information"}

    async def save_diagnostic_report(self, report: Dict[str, Any],
                                   filename: Optional[str] = None) -> str:
        """Save diagnostic report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_diagnostics_{timestamp}.json"

        filepath = Path("logs") / filename
        filepath.parent.mkdir(exist_ok=True)

        try:
            with open(filepath, "w") as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"NETWORK_DIAG: Report saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"NETWORK_DIAG: Failed to save report: {e}")
            raise
