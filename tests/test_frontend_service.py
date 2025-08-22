"""
Comprehensive tests for FrontendService class.

Tests the frontend server management, environment setup, and process validation
functionality that was extracted from the original run_full_stack method.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from core.orchestration import FrontendService, ProcessInfo


class TestFrontendService:
    """Comprehensive test suite for FrontendService functionality"""

    def setup_method(self):
        """Set up a fresh FrontendService instance for each test"""
        self.service = FrontendService()

    def test_init(self):
        """Test FrontendService initialization"""
        service = FrontendService()

        assert service.process is None
        assert service.port is None

    def test_setup_frontend_environment_basic(self):
        """Test basic frontend environment setup"""
        env = self.service.setup_frontend_environment(8000)

        expected = {
            "REACT_APP_BACKEND_URL": "http://localhost:8000",
            "REACT_APP_BACKEND_PORT": "8000",
            "NODE_ENV": "development",
        }
        assert env == expected

    def test_setup_frontend_environment_different_port(self):
        """Test frontend environment setup with different backend port"""
        env = self.service.setup_frontend_environment(3000)

        expected = {
            "REACT_APP_BACKEND_URL": "http://localhost:3000",
            "REACT_APP_BACKEND_PORT": "3000",
            "NODE_ENV": "development",
        }
        assert env == expected

    def test_check_port_responsiveness_success(self):
        """Test successful port responsiveness check"""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.connect_ex.return_value = 0  # Successful connection

            result = self.service.check_port_responsiveness(5173)

            assert result is True
            mock_sock.settimeout.assert_called_once_with(1)
            mock_sock.connect_ex.assert_called_once_with(("localhost", 5173))

    def test_check_port_responsiveness_failure(self):
        """Test port responsiveness check failure"""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.connect_ex.return_value = 1  # Connection failed

            result = self.service.check_port_responsiveness(5173)

            assert result is False

    def test_check_port_responsiveness_exception(self):
        """Test port responsiveness check with exception"""
        with patch("socket.socket", side_effect=Exception("Socket error")):
            result = self.service.check_port_responsiveness(5173)

            assert result is False

    def test_validate_frontend_startup_process_died(self):
        """Test frontend startup validation when process dies immediately"""
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process exited with error
        self.service.process = mock_process

        with patch("time.sleep"):  # Speed up the test
            result = self.service.validate_frontend_startup(5173, timeout=0.1)

        assert result is False

    def test_validate_frontend_startup_no_process(self):
        """Test frontend startup validation with no process"""
        self.service.process = None

        with patch("time.sleep"):
            result = self.service.validate_frontend_startup(5173, timeout=0.1)

        assert result is False

    def test_validate_frontend_startup_success(self):
        """Test successful frontend startup validation"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process still running
        self.service.process = mock_process

        with patch("time.sleep"):
            with patch.object(self.service, "check_port_responsiveness", return_value=True):
                result = self.service.validate_frontend_startup(5173, timeout=0.1)

        assert result is True

    def test_validate_frontend_startup_port_not_responsive(self):
        """Test frontend startup validation when port is not responsive"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process running
        self.service.process = mock_process

        with patch("time.sleep"):
            with patch.object(self.service, "check_port_responsiveness", return_value=False):
                result = self.service.validate_frontend_startup(5173, timeout=0.1)

        assert result is False

    def test_start_frontend_server_success(self):
        """Test successful frontend server startup"""
        mock_process = Mock()
        mock_process.pid = 12345

        mock_env = {
            "REACT_APP_BACKEND_URL": "http://localhost:8000",
            "REACT_APP_BACKEND_PORT": "8000",
            "NODE_ENV": "development",
        }

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
            with patch("os.environ.copy", return_value={"PATH": "/usr/bin"}):
                with patch.object(self.service, "setup_frontend_environment", return_value=mock_env):
                    with patch.object(self.service, "validate_frontend_startup", return_value=True):
                        result = self.service.start_frontend_server(5173, 8000)

        assert isinstance(result, ProcessInfo)
        assert result.success is True
        assert result.process == mock_process
        assert result.pid == 12345
        assert result.port == 5173
        assert result.error is None

        # Verify Popen was called with correct arguments
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["npm", "run", "dev"]
        assert call_args[1]["cwd"] == "frontend"
        assert "PORT" in call_args[1]["env"]
        assert call_args[1]["env"]["PORT"] == "5173"

    def test_start_frontend_server_validation_failure(self):
        """Test frontend server startup with validation failure"""
        mock_process = Mock()
        mock_process.pid = 12345

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("os.environ.copy", return_value={"PATH": "/usr/bin"}):
                with patch.object(self.service, "setup_frontend_environment", return_value={}):
                    with patch.object(self.service, "validate_frontend_startup", return_value=False):
                        result = self.service.start_frontend_server(5173, 8000)

        assert isinstance(result, ProcessInfo)
        assert result.success is False
        assert result.process == mock_process
        assert result.warning is not None
        assert "responsiveness check failed" in result.warning

    def test_start_frontend_server_subprocess_error(self):
        """Test frontend server startup with subprocess error"""
        with patch("subprocess.Popen", side_effect=Exception("Failed to start process")):
            with patch("os.environ.copy", return_value={"PATH": "/usr/bin"}):
                with patch.object(self.service, "setup_frontend_environment", return_value={}):
                    result = self.service.start_frontend_server(5173, 8000)

        assert isinstance(result, ProcessInfo)
        assert result.success is False
        assert result.process is None
        assert result.pid is None
        assert "Failed to start process" in result.error

    def test_start_frontend_server_environment_setup(self):
        """Test that frontend server startup properly sets up environment"""
        mock_process = Mock()
        expected_env = {
            "REACT_APP_BACKEND_URL": "http://localhost:8000",
            "REACT_APP_BACKEND_PORT": "8000",
            "NODE_ENV": "development",
        }

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
            with patch("os.environ.copy", return_value={"EXISTING": "value"}) as mock_copy:
                with patch.object(self.service, "validate_frontend_startup", return_value=True):
                    self.service.start_frontend_server(5173, 8000)

        # Check that environment was properly merged
        call_args = mock_popen.call_args
        env = call_args[1]["env"]

        # Should contain original environment
        assert env["EXISTING"] == "value"
        # Should contain new environment variables
        assert env["REACT_APP_BACKEND_URL"] == "http://localhost:8000"
        assert env["REACT_APP_BACKEND_PORT"] == "8000"
        assert env["NODE_ENV"] == "development"
        assert env["PORT"] == "5173"

    def test_stop_no_process(self):
        """Test stopping service when no process is running"""
        self.service.process = None

        result = self.service.stop()

        assert result is True

    def test_stop_with_process_success(self):
        """Test successful process stopping"""
        mock_process = Mock()
        self.service.process = mock_process

        with patch("core.orchestration.ProcessTerminator.terminate_process_gracefully",
                   return_value=True) as mock_terminate:
            result = self.service.stop()

        assert result is True
        mock_terminate.assert_called_once_with(mock_process)

    def test_stop_with_process_failure(self):
        """Test process stopping failure"""
        mock_process = Mock()
        self.service.process = mock_process

        with patch("core.orchestration.ProcessTerminator.terminate_process_gracefully",
                   return_value=False) as mock_terminate:
            result = self.service.stop()

        assert result is False
        mock_terminate.assert_called_once_with(mock_process)


class TestFrontendServiceIntegration:
    """Integration tests for FrontendService"""

    def setup_method(self):
        """Set up a fresh FrontendService instance for each test"""
        self.service = FrontendService()

    def test_environment_setup_integration(self):
        """Integration test for environment setup with various backend ports"""
        test_cases = [
            (3000, "http://localhost:3000"),
            (8000, "http://localhost:8000"),
            (8080, "http://localhost:8080"),
            (9999, "http://localhost:9999"),
        ]

        for backend_port, expected_url in test_cases:
            env = self.service.setup_frontend_environment(backend_port)

            assert env["REACT_APP_BACKEND_URL"] == expected_url
            assert env["REACT_APP_BACKEND_PORT"] == str(backend_port)
            assert env["NODE_ENV"] == "development"

    @patch("time.sleep")  # Speed up the test
    def test_startup_validation_integration(self, mock_sleep):
        """Integration test for startup validation flow"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process running
        self.service.process = mock_process

        # Test with responsive port
        with patch.object(self.service, "check_port_responsiveness", return_value=True):
            result = self.service.validate_frontend_startup(5173)
            assert result is True

        # Test with unresponsive port
        with patch.object(self.service, "check_port_responsiveness", return_value=False):
            result = self.service.validate_frontend_startup(5173)
            assert result is False

    def test_full_startup_flow_integration(self):
        """Integration test for complete frontend server startup flow"""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("os.environ.copy", return_value={"PATH": "/usr/bin"}):
                with patch("time.sleep"):  # Speed up validation
                    with patch.object(self.service, "check_port_responsiveness", return_value=True):
                        result = self.service.start_frontend_server(5173, 8000)

        assert result.success is True
        assert result.port == 5173
        assert result.process == mock_process
        assert self.service.process == mock_process
        assert self.service.port == 5173

    def test_error_handling_integration(self):
        """Integration test for error handling throughout the service"""
        # Test subprocess creation failure
        with patch("subprocess.Popen", side_effect=FileNotFoundError("npm not found")):
            with patch("os.environ.copy", return_value={}):
                result = self.service.start_frontend_server(5173, 8000)

                assert result.success is False
                assert "npm not found" in result.error

    def test_port_responsiveness_integration(self):
        """Integration test for port responsiveness checking"""
        # Test with a port that should be available
        result = self.service.check_port_responsiveness(0)  # Port 0 should generally fail
        assert isinstance(result, bool)

        # Test with an obviously unavailable port (high number)
        result = self.service.check_port_responsiveness(65535)
        # Result could be True or False depending on system, just ensure it doesn't crash
        assert isinstance(result, bool)


class TestFrontendServiceEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        self.service = FrontendService()

    def test_start_server_with_invalid_ports(self):
        """Test starting server with invalid port numbers"""
        # Test with negative port
        with patch("subprocess.Popen", side_effect=Exception("Invalid port")):
            with patch("os.environ.copy", return_value={}):
                result = self.service.start_frontend_server(-1, 8000)

                assert result.success is False
                assert result.error is not None

    def test_validate_startup_with_zero_timeout(self):
        """Test startup validation with zero timeout"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        self.service.process = mock_process

        with patch("time.sleep"):
            with patch.object(self.service, "check_port_responsiveness", return_value=True):
                result = self.service.validate_frontend_startup(5173, timeout=0)

        # Should still work, just with no waiting time
        assert isinstance(result, bool)

    def test_environment_setup_with_extreme_ports(self):
        """Test environment setup with edge case port numbers"""
        # Test with minimum port (1)
        env = self.service.setup_frontend_environment(1)
        assert env["REACT_APP_BACKEND_PORT"] == "1"

        # Test with maximum port (65535)
        env = self.service.setup_frontend_environment(65535)
        assert env["REACT_APP_BACKEND_PORT"] == "65535"

    def test_multiple_start_calls(self):
        """Test behavior when start is called multiple times"""
        mock_process1 = Mock()
        mock_process1.pid = 111
        mock_process2 = Mock()
        mock_process2.pid = 222

        with patch("subprocess.Popen", side_effect=[mock_process1, mock_process2]):
            with patch("os.environ.copy", return_value={}):
                with patch.object(self.service, "validate_frontend_startup", return_value=True):

                    result1 = self.service.start_frontend_server(5173, 8000)
                    assert result1.process == mock_process1
                    assert self.service.process == mock_process1

                    result2 = self.service.start_frontend_server(5174, 8000)
                    assert result2.process == mock_process2
                    assert self.service.process == mock_process2  # Should update to new process

    def test_stop_multiple_times(self):
        """Test behavior when stop is called multiple times"""
        mock_process = Mock()
        self.service.process = mock_process

        with patch("core.orchestration.ProcessTerminator.terminate_process_gracefully",
                   return_value=True):

            # First stop should work
            result1 = self.service.stop()
            assert result1 is True

            # Process should still be there for subsequent calls
            result2 = self.service.stop()
            assert result2 is True

    def test_responsiveness_check_with_permission_denied(self):
        """Test port responsiveness check when permission is denied"""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.connect_ex.side_effect = PermissionError("Permission denied")

            result = self.service.check_port_responsiveness(80)  # Privileged port

            assert result is False

    def test_environment_with_missing_os_environ(self):
        """Test environment setup when os.environ operations fail"""
        with patch("os.environ.copy", side_effect=Exception("Environment error")):
            # Should still work, might just not merge environment properly
            try:
                with patch("subprocess.Popen", side_effect=Exception("Expected")):
                    result = self.service.start_frontend_server(5173, 8000)
                    assert result.success is False
            except Exception as e:
                # If it propagates the environment error, that's also acceptable
                assert "error" in str(e).lower()


class TestProcessInfoDataClass:
    """Test the ProcessInfo dataclass used by FrontendService"""

    def test_process_info_creation_success(self):
        """Test creating ProcessInfo for successful startup"""
        mock_process = Mock()
        mock_process.pid = 12345

        info = ProcessInfo(
            process=mock_process,
            pid=12345,
            port=5173,
            success=True,
        )

        assert info.process == mock_process
        assert info.pid == 12345
        assert info.port == 5173
        assert info.success is True
        assert info.error is None
        assert info.warning is None

    def test_process_info_creation_failure(self):
        """Test creating ProcessInfo for failed startup"""
        info = ProcessInfo(
            process=None,
            pid=None,
            port=5173,
            success=False,
            error="Failed to start process",
        )

        assert info.process is None
        assert info.pid is None
        assert info.port == 5173
        assert info.success is False
        assert info.error == "Failed to start process"
        assert info.warning is None

    def test_process_info_with_warning(self):
        """Test creating ProcessInfo with warning"""
        mock_process = Mock()

        info = ProcessInfo(
            process=mock_process,
            pid=12345,
            port=5173,
            success=True,
            warning="Started but port check failed",
        )

        assert info.success is True
        assert info.warning == "Started but port check failed"
        assert info.error is None


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
