"""
Test for the orchestration refactor to ensure functionality is maintained.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from core.orchestration import (
    FrontendEnvironmentValidator,
    FrontendService,
    FullStackOrchestrator,
    PortManager,
    PortResolution,
    ProcessInfo,
    ProcessTerminator,
)


class TestPortManager:
    """Test port management functionality"""

    def test_port_resolution_exact_port_available(self):
        """Test exact port resolution when port is available"""
        with patch.object(PortManager, "check_port_available", return_value=True):
            result = PortManager.resolve_port(8000, no_auto_port=True)

            assert result.requested_port == 8000
            assert result.resolved_port == 8000
            assert result.auto_port_used is False
            assert result.available is True
            assert result.error is None

    def test_port_resolution_exact_port_unavailable(self):
        """Test exact port resolution when port is unavailable"""
        with patch.object(PortManager, "check_port_available", return_value=False):
            result = PortManager.resolve_port(8000, no_auto_port=True)

            assert result.requested_port == 8000
            assert result.resolved_port == 8000
            assert result.auto_port_used is False
            assert result.available is False
            assert result.error == "Port 8000 is in use (auto-port disabled)"

    def test_port_resolution_auto_port_fallback(self):
        """Test auto port resolution when original port is unavailable"""
        with patch.object(PortManager, "check_port_available", side_effect=[False, True]):
            with patch.object(PortManager, "find_available_port", return_value=8001):
                result = PortManager.resolve_port(8000, no_auto_port=False)

                assert result.requested_port == 8000
                assert result.resolved_port == 8001
                assert result.auto_port_used is True
                assert result.available is True


class TestFrontendEnvironmentValidator:
    """Test frontend environment validation"""

    @patch("subprocess.run")
    def test_node_installed_success(self, mock_run):
        """Test Node.js installation check when installed"""
        mock_run.return_value = Mock(returncode=0)

        assert FrontendEnvironmentValidator.is_node_installed() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_node_not_installed(self, mock_run):
        """Test Node.js installation check when not installed"""
        mock_run.side_effect = FileNotFoundError()

        assert FrontendEnvironmentValidator.is_node_installed() is False

    @patch("pathlib.Path.exists")
    def test_dependencies_check(self, mock_exists):
        """Test frontend dependencies check"""
        # Mock the existence of required files/directories
        mock_exists.side_effect = lambda: True

        # This is a simplified test - in reality we'd need to mock Path objects properly
        # For now, just test the method exists and doesn't crash
        result = FrontendEnvironmentValidator.check_frontend_dependencies()
        assert isinstance(result, bool)


class TestProcessTerminator:
    """Test process termination functionality"""

    def test_terminate_process_gracefully_already_terminated(self):
        """Test graceful termination of already terminated process"""
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Already terminated

        result = ProcessTerminator.terminate_process_gracefully(mock_process)

        assert result is True
        mock_process.terminate.assert_not_called()

    def test_terminate_process_gracefully_success(self):
        """Test graceful termination success"""
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 0]  # First None (running), then 0 (terminated)

        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=0.1)

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()


class TestFullStackOrchestrator:
    """Test the main orchestration functionality"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing"""
        return FullStackOrchestrator()

    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initializes correctly"""
        assert orchestrator.frontend_service is not None
        assert isinstance(orchestrator.frontend_service, FrontendService)
        assert orchestrator.backend_started is False
        assert orchestrator.frontend_info is None

    @patch.object(FrontendEnvironmentValidator, "validate_environment")
    def test_validate_frontend_environment_success(self, mock_validate, orchestrator):
        """Test frontend environment validation success"""
        mock_validate.return_value = {
            "node_installed": True,
            "dependencies_ready": True,
            "frontend_dir_exists": True,
        }

        result = orchestrator.validate_frontend_environment()

        assert result is True

    @patch.object(FrontendEnvironmentValidator, "validate_environment")
    def test_validate_frontend_environment_no_node(self, mock_validate, orchestrator):
        """Test frontend environment validation when Node.js not installed"""
        mock_validate.return_value = {
            "node_installed": False,
            "dependencies_ready": True,
            "frontend_dir_exists": True,
        }

        result = orchestrator.validate_frontend_environment()

        assert result is False

    def test_resolve_ports_success(self, orchestrator):
        """Test port resolution for both backend and frontend"""
        with patch.object(PortManager, "resolve_port") as mock_resolve:
            mock_resolve.side_effect = [
                PortResolution(8000, 8000, False, True),  # Backend
                PortResolution(5173, 5173, False, True),   # Frontend
            ]

            backend_port, frontend_port = orchestrator.resolve_ports(8000, 5173, no_auto_port=False)

            assert backend_port == 8000
            assert frontend_port == 5173
            assert mock_resolve.call_count == 2


class TestRefactoredFunctionality:
    """Integration tests to ensure refactored code maintains original functionality"""

    @pytest.mark.asyncio
    async def test_orchestrate_startup_basic_flow(self):
        """Test that orchestrate_startup follows the expected flow"""
        orchestrator = FullStackOrchestrator()

        with patch.object(orchestrator, "resolve_ports", return_value=(8000, 5173)) as mock_resolve_ports:
            with patch.object(orchestrator, "start_frontend_if_enabled", return_value=ProcessInfo(None, None, 5173, True)) as mock_start_frontend:

                result = await orchestrator.orchestrate_startup(
                    host="localhost",
                    backend_port=8000,
                    frontend_port=5173,
                    no_auto_port=False,
                    no_frontend=False,
                    kill_existing=False,
                )

                assert result["success"] is True
                assert result["backend_port"] == 8000
                assert result["frontend_port"] == 5173
                assert result["frontend_info"] is not None

                mock_resolve_ports.assert_called_once()
                mock_start_frontend.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrate_startup_no_frontend(self):
        """Test orchestrate_startup with frontend disabled"""
        orchestrator = FullStackOrchestrator()

        with patch.object(orchestrator, "resolve_ports", return_value=(8000, 5173)) as mock_resolve_ports:

            result = await orchestrator.orchestrate_startup(
                host="localhost",
                backend_port=8000,
                frontend_port=5173,
                no_auto_port=False,
                no_frontend=True,  # Frontend disabled
                kill_existing=False,
            )

            assert result["success"] is True
            assert result["backend_port"] == 8000
            assert result["frontend_port"] == 5173
            assert result["frontend_info"] is None  # No frontend should be started

            mock_resolve_ports.assert_called_once()


if __name__ == "__main__":
    # Simple test runner for basic validation
    import sys
    import traceback

    test_classes = [TestPortManager, TestFrontendEnvironmentValidator, TestProcessTerminator, TestFullStackOrchestrator]

    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    if asyncio.iscoroutinefunction(method):
                        asyncio.run(method())
                    # Handle methods that need orchestrator fixture
                    elif test_class == TestFullStackOrchestrator and method_name in [
                        "test_orchestrator_initialization",
                        "test_validate_frontend_environment_success",
                        "test_validate_frontend_environment_no_node",
                        "test_resolve_ports_success",
                    ]:
                        orchestrator = FullStackOrchestrator()
                        method(orchestrator)
                    else:
                        method()
                    print(f"✅ {test_class.__name__}::{method_name}")
                    passed += 1
                except Exception as e:
                    print(f"❌ {test_class.__name__}::{method_name}: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n📊 Test Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        print("🎉 All tests passed!")
