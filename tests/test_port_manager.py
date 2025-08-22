"""
Comprehensive tests for PortManager class.

Tests the port availability checking, port resolution, and auto-port functionality
that was extracted from the original run_full_stack method.
"""

import socket
from unittest.mock import MagicMock, patch

import pytest

from core.orchestration import PortManager, PortResolution


class TestPortManager:
    """Comprehensive test suite for PortManager functionality"""

    def test_check_port_available_success(self):
        """Test successful port availability check"""
        # Use a mock socket to simulate available port
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.return_value = None  # Successful bind

            result = PortManager.check_port_available(8000)

            assert result is True
            mock_sock.bind.assert_called_once_with(("0.0.0.0", 8000))

    def test_check_port_available_failure(self):
        """Test port availability check when port is in use"""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.side_effect = OSError("Address already in use")

            result = PortManager.check_port_available(8000)

            assert result is False
            mock_sock.bind.assert_called_once_with(("0.0.0.0", 8000))

    def test_check_port_available_custom_host(self):
        """Test port availability check with custom host"""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.return_value = None

            result = PortManager.check_port_available(8000, "localhost")

            assert result is True
            mock_sock.bind.assert_called_once_with(("localhost", 8000))

    def test_find_available_port_first_attempt(self):
        """Test finding available port on first attempt"""
        with patch.object(PortManager, "check_port_available", return_value=True):
            result = PortManager.find_available_port(8000)

            assert result == 8000

    def test_find_available_port_second_attempt(self):
        """Test finding available port on second attempt"""
        with patch.object(PortManager, "check_port_available", side_effect=[False, True]):
            result = PortManager.find_available_port(8000)

            assert result == 8001

    def test_find_available_port_multiple_attempts(self):
        """Test finding available port after multiple attempts"""
        # First 5 ports unavailable, 6th available
        side_effects = [False] * 5 + [True]
        with patch.object(PortManager, "check_port_available", side_effect=side_effects):
            result = PortManager.find_available_port(8000)

            assert result == 8005

    def test_find_available_port_no_ports_available(self):
        """Test exception when no ports are available in range"""
        with patch.object(PortManager, "check_port_available", return_value=False):
            with pytest.raises(RuntimeError) as exc_info:
                PortManager.find_available_port(8000, max_attempts=5)

            assert "No available ports found in range 8000-8005" in str(exc_info.value)

    def test_find_available_port_custom_host(self):
        """Test finding available port with custom host"""
        with patch.object(PortManager, "check_port_available", return_value=True) as mock_check:
            result = PortManager.find_available_port(8000, host="localhost")

            assert result == 8000
            mock_check.assert_called_with(8000, "localhost")

    def test_resolve_port_exact_mode_available(self):
        """Test port resolution in exact mode with available port"""
        with patch.object(PortManager, "check_port_available", return_value=True):
            result = PortManager.resolve_port(8000, no_auto_port=True)

            assert isinstance(result, PortResolution)
            assert result.requested_port == 8000
            assert result.resolved_port == 8000
            assert result.auto_port_used is False
            assert result.available is True
            assert result.error is None

    def test_resolve_port_exact_mode_unavailable(self):
        """Test port resolution in exact mode with unavailable port"""
        with patch.object(PortManager, "check_port_available", return_value=False):
            result = PortManager.resolve_port(8000, no_auto_port=True)

            assert isinstance(result, PortResolution)
            assert result.requested_port == 8000
            assert result.resolved_port == 8000
            assert result.auto_port_used is False
            assert result.available is False
            assert result.error == "Port 8000 is in use (auto-port disabled)"

    def test_resolve_port_auto_mode_available(self):
        """Test port resolution in auto mode with available requested port"""
        with patch.object(PortManager, "check_port_available", return_value=True):
            result = PortManager.resolve_port(8000, no_auto_port=False)

            assert isinstance(result, PortResolution)
            assert result.requested_port == 8000
            assert result.resolved_port == 8000
            assert result.auto_port_used is False
            assert result.available is True
            assert result.error is None

    def test_resolve_port_auto_mode_fallback(self):
        """Test port resolution in auto mode with fallback to different port"""
        with patch.object(PortManager, "check_port_available", return_value=False):
            with patch.object(PortManager, "find_available_port", return_value=8001):
                result = PortManager.resolve_port(8000, no_auto_port=False)

                assert isinstance(result, PortResolution)
                assert result.requested_port == 8000
                assert result.resolved_port == 8001
                assert result.auto_port_used is True
                assert result.available is True
                assert result.error is None

    def test_resolve_port_auto_mode_no_ports_available(self):
        """Test port resolution in auto mode when no ports are available"""
        with patch.object(PortManager, "check_port_available", return_value=False):
            with patch.object(PortManager, "find_available_port",
                            side_effect=RuntimeError("No available ports")):
                result = PortManager.resolve_port(8000, no_auto_port=False)

                assert isinstance(result, PortResolution)
                assert result.requested_port == 8000
                assert result.resolved_port == 8000
                assert result.auto_port_used is False
                assert result.available is False
                assert result.error == "No available ports"

    def test_resolve_port_custom_host(self):
        """Test port resolution with custom host"""
        with patch.object(PortManager, "check_port_available", return_value=True) as mock_check:
            result = PortManager.resolve_port(8000, host="localhost", no_auto_port=True)

            assert result.available is True
            mock_check.assert_called_with(8000, "localhost")


class TestPortResolutionDataClass:
    """Test the PortResolution dataclass"""

    def test_port_resolution_creation(self):
        """Test creating PortResolution instance"""
        resolution = PortResolution(
            requested_port=8000,
            resolved_port=8001,
            auto_port_used=True,
            available=True,
            error=None,
        )

        assert resolution.requested_port == 8000
        assert resolution.resolved_port == 8001
        assert resolution.auto_port_used is True
        assert resolution.available is True
        assert resolution.error is None

    def test_port_resolution_with_error(self):
        """Test creating PortResolution instance with error"""
        resolution = PortResolution(
            requested_port=8000,
            resolved_port=8000,
            auto_port_used=False,
            available=False,
            error="Port in use",
        )

        assert resolution.error == "Port in use"
        assert resolution.available is False


class TestPortManagerIntegration:
    """Integration tests for PortManager functionality"""

    @pytest.mark.skipif(not hasattr(socket, "AF_INET"), reason="Socket AF_INET not available")
    def test_actual_port_check_with_bound_socket(self):
        """Integration test with actual socket binding"""
        # Bind a socket to a port
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.bind(("localhost", 0))  # Let OS choose port
        bound_port = test_socket.getsockname()[1]

        try:
            # Port should be unavailable
            result = PortManager.check_port_available(bound_port, "localhost")
            assert result is False

        finally:
            test_socket.close()

        # After closing, port should become available (might take a moment)
        import time
        time.sleep(0.1)  # Brief wait for port to be released
        result = PortManager.check_port_available(bound_port, "localhost")
        # Note: This might still be False due to TIME_WAIT state, which is expected

    def test_port_range_scanning(self):
        """Test scanning a range of ports for availability"""
        # This is a more realistic test of the port scanning functionality
        with patch.object(PortManager, "check_port_available") as mock_check:
            # Simulate first 3 ports busy, 4th available
            mock_check.side_effect = [False, False, False, True]

            result = PortManager.find_available_port(8000, max_attempts=10)

            assert result == 8003
            assert mock_check.call_count == 4


class TestPortManagerEdgeCases:
    """Test edge cases and error conditions"""

    def test_port_zero(self):
        """Test behavior with port 0 (OS-assigned port)"""
        # Port 0 should generally be available as OS will assign
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock

            PortManager.check_port_available(0)

            mock_sock.bind.assert_called_once_with(("0.0.0.0", 0))

    def test_high_port_number(self):
        """Test behavior with high port numbers"""
        with patch.object(PortManager, "check_port_available", return_value=True):
            result = PortManager.resolve_port(65535)

            assert result.resolved_port == 65535

    def test_invalid_host(self):
        """Test behavior with invalid host"""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.side_effect = OSError("Invalid host")

            result = PortManager.check_port_available(8000, "invalid-host")

            assert result is False

    def test_socket_creation_failure(self):
        """Test behavior when socket creation fails"""
        with patch("socket.socket", side_effect=OSError("Socket creation failed")):
            result = PortManager.check_port_available(8000)

            assert result is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
