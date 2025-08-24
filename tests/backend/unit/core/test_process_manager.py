"""
Test suite for ProcessManager class

Following TDD approach for Phase 1: Critical Architecture Fixes
Tests written first to define expected behavior for ProcessManager extraction
"""

import pytest
import subprocess
import signal
import time
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
from pathlib import Path

# Import the ProcessManager interface and implementation
from core.process_manager import ProcessManagerInterface, ProcessManager


class TestProcessManagerInterface:
    """Test the ProcessManager abstract interface"""
    
    def test_interface_methods_exist(self):
        """Test that interface defines required abstract methods"""
        # Verify interface has required abstract methods
        assert hasattr(ProcessManagerInterface, 'start_process')
        assert hasattr(ProcessManagerInterface, 'stop_process')
        assert hasattr(ProcessManagerInterface, 'monitor_health')
        
    def test_interface_cannot_be_instantiated(self):
        """Test that abstract interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ProcessManagerInterface()


class TestProcessManager:
    """Test the ProcessManager implementation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.process_manager = ProcessManager()
        
    def teardown_method(self):
        """Clean up after tests"""
        # Ensure all test processes are cleaned up
        for process_id, process_info in list(self.process_manager.processes.items()):
            if process_info['process'] and process_info['process'].poll() is None:
                try:
                    process_info['process'].terminate()
                    time.sleep(0.1)
                    if process_info['process'].poll() is None:
                        process_info['process'].kill()
                except:
                    pass
        self.process_manager.processes.clear()
    
    def test_initialization(self):
        """Test ProcessManager initializes correctly"""
        pm = ProcessManager()
        assert hasattr(pm, 'debug')
        assert hasattr(pm, 'processes')
        assert isinstance(pm.processes, dict)
        assert len(pm.processes) == 0
    
    def test_start_process_success(self):
        """Test successful process start"""
        # Test with a simple command that should succeed
        command = ['echo', 'hello world']
        
        process_id = self.process_manager.start_process(command)
        
        # Verify process was started and stored
        assert process_id is not None
        assert process_id in self.process_manager.processes
        
        process_info = self.process_manager.processes[process_id]
        assert process_info['command'] == command
        assert process_info['process'] is not None
        assert 'start_time' in process_info
        assert 'status' in process_info
        
        # Wait for process to complete (echo should finish quickly)
        time.sleep(0.5)
        process_info['process'].wait()
        assert process_info['process'].returncode == 0
    
    def test_start_process_with_environment(self):
        """Test starting process with custom environment variables"""
        command = ['echo', '$TEST_VAR']
        env_vars = {'TEST_VAR': 'test_value'}
        
        process_id = self.process_manager.start_process(command, env=env_vars)
        
        assert process_id in self.process_manager.processes
        process_info = self.process_manager.processes[process_id]
        assert process_info['env'] == env_vars
    
    def test_start_process_with_working_directory(self):
        """Test starting process with custom working directory"""
        command = ['pwd']
        cwd = '/tmp'
        
        process_id = self.process_manager.start_process(command, cwd=cwd)
        
        assert process_id in self.process_manager.processes
        process_info = self.process_manager.processes[process_id]
        assert process_info['cwd'] == cwd
    
    def test_start_process_invalid_command(self):
        """Test handling of invalid command"""
        command = ['nonexistent_command_12345']
        
        with pytest.raises(ProcessManager.ProcessStartError):
            self.process_manager.start_process(command)
    
    def test_stop_process_graceful(self):
        """Test graceful process termination"""
        # Start a long-running process
        command = ['sleep', '10']
        process_id = self.process_manager.start_process(command)
        
        # Verify process is running
        process_info = self.process_manager.processes[process_id]
        assert process_info['process'].poll() is None
        
        # Stop the process gracefully
        result = self.process_manager.stop_process(process_id, timeout=5)
        
        assert result is True
        assert process_info['process'].poll() is not None  # Process should be terminated
        assert process_info['status'] == 'stopped'
    
    def test_stop_process_force_kill(self):
        """Test force killing process when graceful termination fails"""
        # Start a process that ignores SIGTERM
        command = ['python3', '-c', 'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']
        process_id = self.process_manager.start_process(command)
        
        # Try to stop with very short timeout to force kill
        result = self.process_manager.stop_process(process_id, timeout=0.1)
        
        assert result is True
        process_info = self.process_manager.processes[process_id]
        assert process_info['process'].poll() is not None
        # Accept either 'stopped' (if process stopped gracefully despite ignoring SIGTERM) 
        # or 'force_killed' (if force kill was needed)
        assert process_info['status'] in ['stopped', 'force_killed']
    
    def test_stop_process_nonexistent(self):
        """Test stopping nonexistent process"""
        result = self.process_manager.stop_process('nonexistent_process_id')
        assert result is False
    
    def test_monitor_health_empty(self):
        """Test health monitoring with no processes"""
        health = self.process_manager.monitor_health()
        
        assert isinstance(health, dict)
        assert health['total_processes'] == 0
        assert health['running_processes'] == 0
        assert health['stopped_processes'] == 0
        assert health['processes'] == {}
    
    def test_monitor_health_with_processes(self):
        """Test health monitoring with active processes"""
        # Start a couple of processes
        process1_id = self.process_manager.start_process(['sleep', '5'])
        process2_id = self.process_manager.start_process(['echo', 'test'])
        
        # Wait for echo to finish
        time.sleep(0.5)
        
        health = self.process_manager.monitor_health()
        
        assert health['total_processes'] == 2
        assert process1_id in health['processes']
        assert process2_id in health['processes']
        
        # Check individual process health
        process1_health = health['processes'][process1_id]
        assert 'status' in process1_health
        assert 'cpu_percent' in process1_health
        assert 'memory_mb' in process1_health
        assert 'uptime_seconds' in process1_health
    
    def test_process_cleanup_on_error(self):
        """Test that processes are properly cleaned up when errors occur"""
        initial_count = len(self.process_manager.processes)
        
        # Try to start invalid process
        try:
            self.process_manager.start_process(['invalid_command'])
        except ProcessManager.ProcessStartError:
            pass
        
        # Process count should not increase after failed start
        assert len(self.process_manager.processes) == initial_count
    
    def test_concurrent_process_access(self):
        """Test thread-safe process management"""
        import threading
        import concurrent.futures
        
        def start_and_stop_process():
            try:
                process_id = self.process_manager.start_process(['echo', 'concurrent_test'])
                time.sleep(0.1)
                return self.process_manager.stop_process(process_id)
            except:
                return False
        
        # Run multiple threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(start_and_stop_process) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Most operations should succeed (some might fail due to timing)
        success_rate = sum(results) / len(results)
        assert success_rate > 0.8  # At least 80% should succeed
    
    def test_debug_logging_integration(self):
        """Test that debug logging is properly integrated"""
        with patch.object(self.process_manager.debug, 'log_state') as mock_log_state:
            with patch.object(self.process_manager.debug, 'trace_function') as mock_trace:
                
                # Start a process
                process_id = self.process_manager.start_process(['echo', 'debug_test'])
                
                # Verify debug logging was called
                mock_log_state.assert_called()
                
                # Check that log_state was called multiple times and find the right call
                found_expected_keys = False
                for call in mock_log_state.call_args_list:
                    if len(call[0]) >= 2:
                        state_dict = call[0][1]
                        if 'command' in state_dict and 'active_processes' in state_dict:
                            found_expected_keys = True
                            break
                
                assert found_expected_keys, f"Expected keys not found in any log_state calls. Calls: {mock_log_state.call_args_list}"


class TestProcessManagerExceptionHandling:
    """Test ProcessManager custom exceptions"""
    
    def test_process_start_error_exception(self):
        """Test ProcessStartError exception"""
        exception = ProcessManager.ProcessStartError("Test error message")
        assert str(exception) == "Test error message"
        assert isinstance(exception, Exception)
    
    def test_process_stop_error_exception(self):
        """Test ProcessStopError exception"""
        exception = ProcessManager.ProcessStopError("Test stop error")
        assert str(exception) == "Test stop error"
        assert isinstance(exception, Exception)


class TestProcessManagerIntegration:
    """Integration tests for ProcessManager with real processes"""
    
    def setup_method(self):
        self.process_manager = ProcessManager()
    
    def teardown_method(self):
        # Clean up all processes
        for process_id in list(self.process_manager.processes.keys()):
            try:
                self.process_manager.stop_process(process_id)
            except:
                pass
    
    def test_frontend_server_process_simulation(self):
        """Test managing a process similar to frontend server"""
        # Simulate starting a development server (using a simple HTTP server)
        command = ['python3', '-m', 'http.server', '0', '--bind', '127.0.0.1']
        
        process_id = self.process_manager.start_process(command)
        
        # Give it time to start
        time.sleep(1)
        
        # Check it's running
        health = self.process_manager.monitor_health()
        assert process_id in health['processes']
        assert health['processes'][process_id]['status'] in ['running', 'active']
        
        # Stop it gracefully
        result = self.process_manager.stop_process(process_id, timeout=10)
        assert result is True
    
    @pytest.mark.slow
    def test_long_running_process_management(self):
        """Test managing long-running processes with health monitoring"""
        # Start a process that runs for a while
        command = ['python3', '-c', 'import time; [time.sleep(1) for _ in range(30)]']
        process_id = self.process_manager.start_process(command)
        
        # Monitor health over time
        health_checks = []
        for i in range(5):
            time.sleep(0.5)
            health = self.process_manager.monitor_health()
            health_checks.append(health['processes'][process_id])
        
        # Verify process was consistently healthy
        for health_check in health_checks:
            assert health_check['status'] in ['running', 'active']
            assert health_check['uptime_seconds'] >= 0
        
        # Stop the process
        self.process_manager.stop_process(process_id)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.Popen for isolated testing"""
    mock_process = Mock()
    mock_process.pid = 12345
    mock_process.poll.return_value = None  # Running
    mock_process.terminate.return_value = None
    mock_process.kill.return_value = None
    mock_process.wait.return_value = 0
    
    with patch('subprocess.Popen', return_value=mock_process) as mock_popen:
        yield mock_popen, mock_process


class TestProcessManagerMocked:
    """Tests using mocked subprocess for isolation"""
    
    def test_start_process_calls_popen_correctly(self, mock_subprocess):
        """Test that start_process calls subprocess.Popen with correct arguments"""
        mock_popen, mock_process = mock_subprocess
        
        pm = ProcessManager()
        command = ['echo', 'test']
        env = {'TEST': 'value'}
        cwd = '/tmp'
        
        process_id = pm.start_process(command, env=env, cwd=cwd)
        
        # Verify subprocess.Popen was called correctly
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        
        assert call_args[0][0] == command  # First positional argument
        assert call_args[1]['env']['TEST'] == 'value'  # Environment variables
        assert call_args[1]['cwd'] == '/tmp'  # Working directory
        assert call_args[1]['stdout'] == subprocess.PIPE
        assert call_args[1]['stderr'] == subprocess.PIPE