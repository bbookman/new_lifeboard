"""
Test fixtures and utilities for orchestration testing.

Provides reusable fixtures, mocks, and utilities for testing the
refactored orchestration components.
"""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from core.orchestration import (
    FrontendEnvironmentValidator,
    FrontendService,
    FullStackOrchestrator,
    PortManager,
    PortResolution,
    ProcessInfo,
)


class MockProcess:
    """Mock process for testing process management"""

    def __init__(self, pid: int = 12345, returncode: Optional[int] = None, should_terminate_gracefully: bool = True):
        self.pid = pid
        self.returncode = returncode
        self._poll_return_values = [None, returncode] if returncode is not None else [None]
        self._poll_index = 0
        self.should_terminate_gracefully = should_terminate_gracefully

        # Mock method calls tracking
        self.terminate_called = False
        self.kill_called = False
        self.wait_called = False

    def poll(self):
        """Mock poll method that can simulate process state changes"""
        if self._poll_index < len(self._poll_return_values):
            value = self._poll_return_values[self._poll_index]
            self._poll_index += 1
            return value
        return self._poll_return_values[-1]

    def terminate(self):
        """Mock terminate method"""
        self.terminate_called = True
        if self.should_terminate_gracefully:
            # Simulate successful termination
            self._poll_return_values = [0]
            self._poll_index = 0

    def kill(self):
        """Mock kill method"""
        self.kill_called = True
        self._poll_return_values = [0]
        self._poll_index = 0

    def wait(self, timeout=None):
        """Mock wait method"""
        self.wait_called = True
        if not self.should_terminate_gracefully and not self.kill_called:
            import subprocess
            raise subprocess.TimeoutExpired("mock_process", timeout)
        return 0


class MockSocket:
    """Mock socket for testing port operations"""

    def __init__(self, should_bind_succeed: bool = True):
        self.should_bind_succeed = should_bind_succeed
        self.bound_addresses = []
        self.connect_results = {}  # port -> success (True/False)

    def bind(self, address):
        """Mock bind method"""
        host, port = address
        self.bound_addresses.append(address)
        if not self.should_bind_succeed:
            raise OSError("Address already in use")

    def connect_ex(self, address):
        """Mock connect_ex method for responsiveness testing"""
        host, port = address
        return self.connect_results.get(port, 0)  # 0 = success

    def settimeout(self, timeout):
        """Mock settimeout method"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockSubprocessResult:
    """Mock subprocess result"""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def mock_process():
    """Fixture providing a mock process"""
    return MockProcess()


@pytest.fixture
def mock_failed_process():
    """Fixture providing a mock process that fails to terminate gracefully"""
    return MockProcess(should_terminate_gracefully=False)


@pytest.fixture
def mock_socket_success():
    """Fixture providing a mock socket that succeeds operations"""
    return MockSocket(should_bind_succeed=True)


@pytest.fixture
def mock_socket_failure():
    """Fixture providing a mock socket that fails bind operations"""
    return MockSocket(should_bind_succeed=False)


@pytest.fixture
def orchestrator():
    """Fixture providing a FullStackOrchestrator instance"""
    return FullStackOrchestrator()


@pytest.fixture
def frontend_service():
    """Fixture providing a FrontendService instance"""
    return FrontendService()


@pytest.fixture
def successful_process_info():
    """Fixture providing a successful ProcessInfo"""
    return ProcessInfo(
        process=MockProcess(),
        pid=12345,
        port=5173,
        success=True,
    )


@pytest.fixture
def failed_process_info():
    """Fixture providing a failed ProcessInfo"""
    return ProcessInfo(
        process=None,
        pid=None,
        port=5173,
        success=False,
        error="Process failed to start",
    )


@pytest.fixture
def successful_port_resolution():
    """Fixture providing a successful port resolution"""
    return PortResolution(
        requested_port=8000,
        resolved_port=8000,
        auto_port_used=False,
        available=True,
    )


@pytest.fixture
def auto_resolved_port_resolution():
    """Fixture providing an auto-resolved port resolution"""
    return PortResolution(
        requested_port=8000,
        resolved_port=8001,
        auto_port_used=True,
        available=True,
    )


@pytest.fixture
def failed_port_resolution():
    """Fixture providing a failed port resolution"""
    return PortResolution(
        requested_port=8000,
        resolved_port=8000,
        auto_port_used=False,
        available=False,
        error="Port in use",
    )


class OrchestrationMockContext:
    """Context manager for comprehensive orchestration mocking"""

    def __init__(self,
                 node_installed: bool = True,
                 dependencies_ready: bool = True,
                 frontend_dir_exists: bool = True,
                 ports_available: bool = True,
                 frontend_startup_success: bool = True,
                 port_responsive: bool = True):
        self.node_installed = node_installed
        self.dependencies_ready = dependencies_ready
        self.frontend_dir_exists = frontend_dir_exists
        self.ports_available = ports_available
        self.frontend_startup_success = frontend_startup_success
        self.port_responsive = port_responsive
        self.patches = []

    def __enter__(self):
        # Mock environment validation
        validation_result = {
            "node_installed": self.node_installed,
            "dependencies_ready": self.dependencies_ready,
            "frontend_dir_exists": self.frontend_dir_exists,
        }

        env_patch = patch.object(
            FrontendEnvironmentValidator,
            "validate_environment",
            return_value=validation_result,
        )
        self.patches.append(env_patch)
        env_patch.start()

        # Mock dependency installation
        install_patch = patch.object(
            FrontendEnvironmentValidator,
            "install_frontend_dependencies",
            return_value=True,
        )
        self.patches.append(install_patch)
        install_patch.start()

        # Mock port availability
        port_patch = patch.object(
            PortManager,
            "check_port_available",
            return_value=self.ports_available,
        )
        self.patches.append(port_patch)
        port_patch.start()

        # Mock socket operations
        mock_socket = MockSocket(should_bind_succeed=self.ports_available)
        mock_socket.connect_results = {5173: 0 if self.port_responsive else 1}
        socket_patch = patch("socket.socket", return_value=mock_socket)
        self.patches.append(socket_patch)
        socket_patch.start()

        # Mock subprocess for frontend startup
        if self.frontend_startup_success:
            mock_process = MockProcess()
        else:
            mock_process = None

        subprocess_patch = patch("subprocess.Popen", return_value=mock_process)
        self.patches.append(subprocess_patch)
        subprocess_patch.start()

        # Mock os.environ.copy
        environ_patch = patch("os.environ.copy", return_value={"PATH": "/usr/bin"})
        self.patches.append(environ_patch)
        environ_patch.start()

        # Mock time.sleep to speed up tests
        sleep_patch = patch("time.sleep")
        self.patches.append(sleep_patch)
        sleep_patch.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for patch_obj in reversed(self.patches):
            patch_obj.stop()


@pytest.fixture
def orchestration_success_mocks():
    """Fixture providing comprehensive success mocks"""
    return OrchestrationMockContext()


@pytest.fixture
def orchestration_failure_mocks():
    """Fixture providing comprehensive failure mocks"""
    return OrchestrationMockContext(
        node_installed=False,
        dependencies_ready=False,
        ports_available=False,
        frontend_startup_success=False,
        port_responsive=False,
    )


class TestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_startup_result(success: bool = True, **kwargs) -> Dict[str, Any]:
        """Create a startup result dictionary"""
        base_result = {
            "success": success,
            "backend_port": kwargs.get("backend_port", 8000),
            "frontend_port": kwargs.get("frontend_port", 5173),
            "frontend_info": kwargs.get("frontend_info"),
        }

        if not success:
            base_result["error"] = kwargs.get("error", "Startup failed")

        return base_result

    @staticmethod
    def create_process_list(count: int, mixed_states: bool = False) -> List[MockProcess]:
        """Create a list of mock processes"""
        processes = []
        for i in range(count):
            if mixed_states:
                # Mix of running and terminated processes
                returncode = 0 if i % 2 == 0 else None
                should_terminate = i % 3 != 0
            else:
                returncode = None
                should_terminate = True

            process = MockProcess(
                pid=10000 + i,
                returncode=returncode,
                should_terminate_gracefully=should_terminate,
            )
            processes.append(process)

        return processes

    @staticmethod
    def create_environment_scenarios() -> List[Dict[str, Any]]:
        """Create various environment validation scenarios"""
        return [
            # All good
            {"node_installed": True, "dependencies_ready": True, "frontend_dir_exists": True},
            # Node missing
            {"node_installed": False, "dependencies_ready": True, "frontend_dir_exists": True},
            # Dependencies missing
            {"node_installed": True, "dependencies_ready": False, "frontend_dir_exists": True},
            # Frontend dir missing
            {"node_installed": True, "dependencies_ready": True, "frontend_dir_exists": False},
            # Everything missing
            {"node_installed": False, "dependencies_ready": False, "frontend_dir_exists": False},
        ]


def assert_process_info_valid(process_info: ProcessInfo, should_succeed: bool = True):
    """Utility function to validate ProcessInfo objects"""
    assert isinstance(process_info, ProcessInfo)
    assert isinstance(process_info.port, int)
    assert isinstance(process_info.success, bool)

    if should_succeed:
        assert process_info.success is True
        assert process_info.error is None
        # Process and PID might be None in some valid scenarios
    else:
        assert process_info.success is False
        assert process_info.error is not None


def assert_port_resolution_valid(port_resolution: PortResolution, expected_available: bool = True):
    """Utility function to validate PortResolution objects"""
    assert isinstance(port_resolution, PortResolution)
    assert isinstance(port_resolution.requested_port, int)
    assert isinstance(port_resolution.resolved_port, int)
    assert isinstance(port_resolution.auto_port_used, bool)
    assert isinstance(port_resolution.available, bool)

    if expected_available:
        assert port_resolution.available is True
        assert port_resolution.error is None
    else:
        assert port_resolution.available is False
        assert port_resolution.error is not None


def assert_startup_result_valid(startup_result: Dict[str, Any], should_succeed: bool = True):
    """Utility function to validate startup result dictionaries"""
    assert isinstance(startup_result, dict)
    assert "success" in startup_result
    assert isinstance(startup_result["success"], bool)

    if should_succeed:
        assert startup_result["success"] is True
        assert "backend_port" in startup_result
        assert "frontend_port" in startup_result
        assert isinstance(startup_result["backend_port"], int)
        assert isinstance(startup_result["frontend_port"], int)
    else:
        assert startup_result["success"] is False
        assert "error" in startup_result
        assert startup_result["error"] is not None


async def async_test_helper(coro, timeout: float = 5.0):
    """Helper for running async tests with timeout"""
    return await asyncio.wait_for(coro, timeout=timeout)


class PerformanceTimer:
    """Utility for measuring performance in tests"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start timing"""
        import time
        self.start_time = time.perf_counter()

    def stop(self):
        """Stop timing"""
        import time
        self.end_time = time.perf_counter()

    def elapsed(self) -> float:
        """Get elapsed time in seconds"""
        if self.start_time is None or self.end_time is None:
            raise ValueError("Timer not properly started/stopped")
        return self.end_time - self.start_time

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def skip_if_no_node():
    """Decorator to skip tests if Node.js is not available"""
    import subprocess

    try:
        result = subprocess.run(["node", "--version"], check=False, capture_output=True, timeout=5)
        has_node = result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        has_node = False

    return pytest.mark.skipif(not has_node, reason="Node.js not available")


def parametrize_port_ranges():
    """Decorator for parametrizing tests with various port ranges"""
    port_ranges = [
        (8000, 8099),
        (5000, 5099),
        (3000, 3099),
        (9000, 9099),
    ]
    return pytest.mark.parametrize("start_port,end_port", port_ranges)


# Custom pytest markers for test organization
pytest_markers = {
    "unit": "Mark test as unit test",
    "integration": "Mark test as integration test",
    "performance": "Mark test as performance test",
    "regression": "Mark test as regression test",
    "slow": "Mark test as slow-running",
}

# Test configuration constants
TEST_CONFIG = {
    "DEFAULT_TIMEOUT": 30.0,
    "PERFORMANCE_TIMEOUT": 60.0,
    "MAX_PORT_ATTEMPTS": 50,
    "DEFAULT_BACKEND_PORT": 8000,
    "DEFAULT_FRONTEND_PORT": 5173,
    "TEST_HOST": "localhost",
}


def get_available_test_port(start_port: int = 9000) -> int:
    """Get an available port for testing"""
    import socket

    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue

    raise RuntimeError(f"No available ports found starting from {start_port}")


def cleanup_test_processes(process_list: List[MockProcess]):
    """Clean up test processes"""
    for process in process_list:
        if hasattr(process, "terminate"):
            try:
                process.terminate()
            except:
                pass


# Export commonly used fixtures and utilities
__all__ = [
    "TEST_CONFIG",
    "MockProcess",
    "MockSocket",
    "MockSubprocessResult",
    "OrchestrationMockContext",
    "PerformanceTimer",
    "TestDataFactory",
    "assert_port_resolution_valid",
    "assert_process_info_valid",
    "assert_startup_result_valid",
    "async_test_helper",
    "cleanup_test_processes",
    "get_available_test_port",
    "parametrize_port_ranges",
    "skip_if_no_node",
]
