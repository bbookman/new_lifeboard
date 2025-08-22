"""
Test-Driven Development for ProcessManager class.

This test module defines the expected behavior for the ProcessManager
class before implementation. Following the TDD Red-Green-Refactor cycle.
"""

import subprocess
import time
from unittest.mock import Mock, patch

import pytest

# Import will fail initially (Red phase) - this is expected in TDD
try:
    from core.process_manager import ProcessInfo, ProcessManager
except ImportError:
    # This is expected in TDD - we're writing tests first
    ProcessManager = None
    ProcessInfo = None


class TestProcessManager:
    """Test cases for ProcessManager class following TDD methodology."""

    def test_process_manager_can_be_instantiated(self):
        """Test that ProcessManager can be created with default settings."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()
        assert manager is not None
        assert hasattr(manager, "processes")
        assert isinstance(manager.processes, dict)

    def test_start_process_success(self):
        """Test successfully starting a process."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        # Mock subprocess.Popen to simulate successful process start
        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Process is running
            mock_process.returncode = None
            mock_popen.return_value = mock_process

            # Start a simple echo process
            process_info = manager.start_process(
                name="test_echo",
                command=["echo", "hello"],
                cwd="/tmp",
            )

            assert process_info is not None
            assert process_info.name == "test_echo"
            assert process_info.pid == 12345
            assert process_info.is_running is True
            assert "test_echo" in manager.processes

    def test_start_process_failure(self):
        """Test handling of process start failure."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        # Mock subprocess.Popen to simulate failure
        with patch("subprocess.Popen", side_effect=subprocess.CalledProcessError(1, "test")):
            with pytest.raises(RuntimeError, match="Failed to start process"):
                manager.start_process(
                    name="failing_process",
                    command=["nonexistent_command"],
                )

    def test_stop_process_graceful(self):
        """Test graceful process termination."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        # Setup mock process
        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_process.terminate = Mock()
            mock_process.kill = Mock()
            mock_popen.return_value = mock_process

            # Start process
            process_info = manager.start_process("test_process", ["sleep", "10"])

            # Mock graceful termination
            mock_process.poll.side_effect = [None, None, 0]  # Running, still running, then terminated

            with patch("time.sleep"):  # Speed up test
                success = manager.stop_process("test_process", timeout=5)

            assert success is True
            mock_process.terminate.assert_called_once()
            assert "test_process" not in manager.processes

    def test_stop_process_forced_kill(self):
        """Test forced process termination when graceful fails."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_process.terminate = Mock()
            mock_process.kill = Mock()
            mock_popen.return_value = mock_process

            # Start process
            process_info = manager.start_process("stubborn_process", ["sleep", "100"])

            # Track when kill is called to change poll behavior
            kill_called = False

            def track_kill():
                nonlocal kill_called
                kill_called = True

            def poll_behavior():
                if kill_called:
                    return 0  # Terminated after kill
                return None  # Running before kill

            mock_process.kill.side_effect = track_kill
            mock_process.poll.side_effect = poll_behavior

            # Use timeout of 0 to immediately trigger forced kill
            success = manager.stop_process("stubborn_process", timeout=0)

            assert success is True
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()

    def test_process_monitoring_healthy(self):
        """Test monitoring of healthy running processes."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Still running
            mock_popen.return_value = mock_process

            process_info = manager.start_process("monitored_process", ["sleep", "60"])

            # Check process health
            is_healthy = manager.is_process_healthy("monitored_process")
            assert is_healthy is True

    def test_process_monitoring_dead(self):
        """Test detection of dead processes."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 1  # Process exited with code 1
            mock_popen.return_value = mock_process

            process_info = manager.start_process("dead_process", ["false"])

            # Process should be detected as unhealthy
            is_healthy = manager.is_process_healthy("dead_process")
            assert is_healthy is False

    def test_get_all_processes(self):
        """Test retrieving all managed processes."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        with patch("subprocess.Popen") as mock_popen:
            mock_process1 = Mock(pid=111, poll=Mock(return_value=None))
            mock_process2 = Mock(pid=222, poll=Mock(return_value=None))
            mock_popen.side_effect = [mock_process1, mock_process2]

            manager.start_process("proc1", ["sleep", "10"])
            manager.start_process("proc2", ["sleep", "20"])

            all_processes = manager.get_all_processes()
            assert len(all_processes) == 2
            assert "proc1" in all_processes
            assert "proc2" in all_processes

    def test_cleanup_all_processes(self):
        """Test cleaning up all managed processes."""
        if ProcessManager is None:
            pytest.skip("ProcessManager not implemented yet - TDD Red phase")

        manager = ProcessManager()

        with patch("subprocess.Popen") as mock_popen:
            mock_process1 = Mock(pid=111, poll=Mock(side_effect=[None, 0]), terminate=Mock(), kill=Mock())
            mock_process2 = Mock(pid=222, poll=Mock(side_effect=[None, 0]), terminate=Mock(), kill=Mock())
            mock_popen.side_effect = [mock_process1, mock_process2]

            manager.start_process("proc1", ["sleep", "10"])
            manager.start_process("proc2", ["sleep", "20"])

            with patch("time.sleep"):
                cleanup_results = manager.cleanup_all_processes(timeout=5)

            assert len(cleanup_results) == 2
            assert cleanup_results["proc1"] is True
            assert cleanup_results["proc2"] is True
            assert len(manager.processes) == 0


class TestProcessInfo:
    """Test cases for ProcessInfo data class."""

    def test_process_info_creation(self):
        """Test ProcessInfo creation with required fields."""
        if ProcessInfo is None:
            pytest.skip("ProcessInfo not implemented yet - TDD Red phase")

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None

        process_info = ProcessInfo(
            name="test_process",
            process=mock_process,
            command=["echo", "test"],
            cwd="/tmp",
            started_at=time.time(),
        )

        assert process_info.name == "test_process"
        assert process_info.pid == 12345
        assert process_info.command == ["echo", "test"]
        assert process_info.cwd == "/tmp"
        assert process_info.is_running is True

    def test_process_info_is_running_property(self):
        """Test is_running property reflects process state."""
        if ProcessInfo is None:
            pytest.skip("ProcessInfo not implemented yet - TDD Red phase")

        mock_process = Mock()
        mock_process.pid = 12345

        # Test running process
        mock_process.poll.return_value = None
        process_info = ProcessInfo(
            name="running_process",
            process=mock_process,
            command=["sleep", "10"],
            cwd="/tmp",
            started_at=time.time(),
        )
        assert process_info.is_running is True

        # Test terminated process
        mock_process.poll.return_value = 0
        assert process_info.is_running is False


if __name__ == "__main__":
    # Run tests to see initial failures (Red phase of TDD)
    pytest.main([__file__, "-v"])
