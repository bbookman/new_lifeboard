"""
Comprehensive tests for ProcessTerminator class.

Tests the process termination, graceful shutdown, and cleanup functionality
that was extracted from the original run_full_stack method.
"""

import pytest
import subprocess
import time
from unittest.mock import Mock, patch, MagicMock
from core.orchestration import ProcessTerminator


class TestProcessTerminator:
    """Comprehensive test suite for ProcessTerminator functionality"""

    def test_terminate_process_gracefully_none_process(self):
        """Test graceful termination with None process"""
        result = ProcessTerminator.terminate_process_gracefully(None)
        
        assert result is True

    def test_terminate_process_gracefully_already_terminated(self):
        """Test graceful termination of already terminated process"""
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Already terminated
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process)
        
        assert result is True
        mock_process.terminate.assert_not_called()
        mock_process.kill.assert_not_called()

    def test_terminate_process_gracefully_success_immediate(self):
        """Test graceful termination that succeeds immediately"""
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 0]  # First None (running), then 0 (terminated)
        mock_process.wait.return_value = 0
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=1)
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=1)
        mock_process.kill.assert_not_called()

    def test_terminate_process_gracefully_requires_force_kill(self):
        """Test graceful termination that requires force kill after timeout"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running
        mock_process.wait.side_effect = [subprocess.TimeoutExpired("test", 1), 0]  # Timeout, then killed
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=1)
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process.wait.call_count == 2

    def test_terminate_process_gracefully_exception_handling(self):
        """Test graceful termination with exception handling"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.terminate.side_effect = Exception("Termination failed")
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process)
        
        assert result is False
        mock_process.terminate.assert_called_once()

    def test_terminate_process_gracefully_kill_exception(self):
        """Test graceful termination when kill also fails"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = [subprocess.TimeoutExpired("test", 1)]
        mock_process.kill.side_effect = Exception("Kill failed")
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=1)
        
        assert result is False
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_terminate_process_gracefully_custom_timeout(self):
        """Test graceful termination with custom timeout"""
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 0]
        mock_process.wait.return_value = 0
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=5)
        
        assert result is True
        mock_process.wait.assert_called_once_with(timeout=5)

    def test_cleanup_processes_empty_list(self):
        """Test cleanup with empty process list"""
        result = ProcessTerminator.cleanup_processes([])
        
        expected = {"terminated": 0, "killed": 0, "failed": 0}
        assert result == expected

    def test_cleanup_processes_single_success(self):
        """Test cleanup with single successful termination"""
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Already terminated
        
        with patch.object(ProcessTerminator, 'terminate_process_gracefully', return_value=True):
            result = ProcessTerminator.cleanup_processes([mock_process])
        
        expected = {"terminated": 1, "killed": 0, "failed": 0}
        assert result == expected

    def test_cleanup_processes_multiple_mixed_results(self):
        """Test cleanup with multiple processes having mixed results"""
        # Create mock processes
        process1 = Mock()  # Will be terminated successfully
        process1.poll.return_value = 0
        
        process2 = Mock()  # Will be killed (force killed)
        process2.poll.return_value = None
        
        process3 = Mock()  # Will fail
        process3.poll.return_value = None
        
        def mock_terminate_side_effect(process):
            if process == process1:
                process.poll.return_value = 0
                return True
            elif process == process2:
                process.poll.return_value = None  # Still None after termination
                return True
            else:  # process3
                return False
        
        with patch.object(ProcessTerminator, 'terminate_process_gracefully', 
                         side_effect=mock_terminate_side_effect):
            result = ProcessTerminator.cleanup_processes([process1, process2, process3])
        
        expected = {"terminated": 1, "killed": 1, "failed": 1}
        assert result == expected

    def test_cleanup_processes_all_failed(self):
        """Test cleanup where all processes fail to terminate"""
        processes = [Mock() for _ in range(3)]
        
        with patch.object(ProcessTerminator, 'terminate_process_gracefully', return_value=False):
            result = ProcessTerminator.cleanup_processes(processes)
        
        expected = {"terminated": 0, "killed": 0, "failed": 3}
        assert result == expected

    def test_cleanup_processes_statistics_accuracy(self):
        """Test that cleanup statistics are accurate for various scenarios"""
        # Create 5 processes with different outcomes
        processes = [Mock() for _ in range(5)]
        
        # Define different poll return values after termination
        poll_values = [0, 0, None, None, 0]  # 3 terminated, 2 killed
        termination_success = [True, True, True, False, True]  # 1 failed
        
        def mock_terminate_side_effect(process):
            index = processes.index(process)
            if termination_success[index]:
                process.poll.return_value = poll_values[index]
                return True
            else:
                return False
        
        with patch.object(ProcessTerminator, 'terminate_process_gracefully', 
                         side_effect=mock_terminate_side_effect):
            result = ProcessTerminator.cleanup_processes(processes)
        
        expected = {"terminated": 3, "killed": 1, "failed": 1}
        assert result == expected


class TestProcessTerminatorIntegration:
    """Integration tests for ProcessTerminator with real processes"""

    def test_terminate_real_process_success(self):
        """Integration test with actual subprocess"""
        # Start a simple long-running process
        process = subprocess.Popen(['python', '-c', 'import time; time.sleep(10)'])
        
        try:
            # Verify process is running
            assert process.poll() is None
            
            # Terminate gracefully
            result = ProcessTerminator.terminate_process_gracefully(process, timeout=2)
            
            assert result is True
            assert process.poll() is not None  # Process should be terminated
            
        except Exception:
            # Ensure cleanup in case of test failure
            try:
                process.kill()
                process.wait()
            except:
                pass
            raise

    def test_terminate_stubborn_process(self):
        """Integration test with process that ignores SIGTERM"""
        # This test simulates a process that doesn't respond to SIGTERM
        # We'll use a Python script that catches SIGTERM
        python_code = '''
import signal
import time

def ignore_sigterm(signum, frame):
    pass

signal.signal(signal.SIGTERM, ignore_sigterm)
time.sleep(10)
'''
        
        process = subprocess.Popen(['python', '-c', python_code])
        
        try:
            # Verify process is running
            assert process.poll() is None
            
            # Attempt graceful termination (should force kill after timeout)
            result = ProcessTerminator.terminate_process_gracefully(process, timeout=1)
            
            assert result is True
            assert process.poll() is not None  # Process should be killed
            
        except Exception:
            # Ensure cleanup
            try:
                process.kill()
                process.wait()
            except:
                pass
            raise

    @pytest.mark.skipif(not hasattr(subprocess, 'Popen'), reason="subprocess.Popen not available")
    def test_cleanup_multiple_real_processes(self):
        """Integration test with multiple real processes"""
        processes = []
        
        try:
            # Start 3 simple processes
            for i in range(3):
                proc = subprocess.Popen(['python', '-c', f'import time; time.sleep(10)'])
                processes.append(proc)
            
            # Verify all processes are running
            for proc in processes:
                assert proc.poll() is None
            
            # Cleanup all processes
            result = ProcessTerminator.cleanup_processes(processes)
            
            # All should be terminated (either gracefully or force killed)
            total_handled = result["terminated"] + result["killed"]
            assert total_handled == 3
            assert result["failed"] == 0
            
            # Verify all processes are actually terminated
            for proc in processes:
                assert proc.poll() is not None
                
        except Exception:
            # Ensure cleanup in case of test failure
            for proc in processes:
                try:
                    proc.kill()
                    proc.wait()
                except:
                    pass
            raise


class TestProcessTerminatorEdgeCases:
    """Test edge cases and error conditions"""

    def test_terminate_process_with_invalid_pid(self):
        """Test termination of process with invalid PID"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.terminate.side_effect = ProcessLookupError("No such process")
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process)
        
        assert result is False

    def test_terminate_process_permission_denied(self):
        """Test termination when permission is denied"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.terminate.side_effect = PermissionError("Permission denied")
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process)
        
        assert result is False

    def test_wait_timeout_exception_handling(self):
        """Test proper handling of timeout exceptions during wait"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        # First wait times out, second wait after kill succeeds
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired("test", 1),
            0
        ]
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=1)
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process.wait.call_count == 2

    def test_zero_timeout(self):
        """Test behavior with zero timeout"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("test", 0)
        
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=0)
        
        assert result is True  # Should still work, immediately force kill
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_negative_timeout(self):
        """Test behavior with negative timeout"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("test", -1)
        
        # Should still work but immediately timeout
        result = ProcessTerminator.terminate_process_gracefully(mock_process, timeout=-1)
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()


class TestProcessTerminatorLogging:
    """Test logging behavior of ProcessTerminator"""

    def test_termination_with_logging(self):
        """Test that process termination includes appropriate logging"""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.terminate.side_effect = Exception("Test exception")
        
        with patch('core.orchestration.logger') as mock_logger:
            result = ProcessTerminator.terminate_process_gracefully(mock_process)
            
            assert result is False
            # Verify that logger.warning was called with process info
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "12345" in call_args
            assert "Test exception" in call_args


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])