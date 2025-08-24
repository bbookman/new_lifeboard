"""
Test suite for FrontendOrchestrator extraction from api/server.py
Part of TDD-driven cleanup plan for Lifeboard codebase.

Tests follow the pattern described in clean_now.md Phase 1.1.3
"""

import pytest
import subprocess
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from dataclasses import dataclass

from core.frontend_orchestrator import FrontendOrchestrator, FrontendOrchestratorInterface

def get_frontend_orchestrator_classes():
    """Get the FrontendOrchestrator classes"""
    from core.frontend_orchestrator import FrontendOrchestrator, FrontendOrchestratorInterface
    return FrontendOrchestrator, FrontendOrchestratorInterface


class TestFrontendOrchestratorInterface:
    """Test the FrontendOrchestrator interface contract"""
    
    def test_interface_methods_exist(self):
        """Test that FrontendOrchestratorInterface defines required methods"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        
        # Verify abstract methods exist
        interface_methods = [
            'check_dependencies', 'install_dependencies', 'kill_existing_processes',
            'start_frontend_server', 'stop_frontend_server', 'get_frontend_status',
            'cleanup_all_processes'
        ]
        
        for method in interface_methods:
            assert hasattr(FrontendOrchestratorInterface, method)


class TestFrontendOrchestrator:
    """Test FrontendOrchestrator implementation"""
    
    @pytest.fixture
    def temp_frontend_dir(self):
        """Create a temporary frontend directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            frontend_dir = Path(temp_dir) / "frontend"
            frontend_dir.mkdir()
            
            # Create mock package.json
            package_json = frontend_dir / "package.json"
            package_json.write_text('{"name": "test-frontend", "scripts": {"dev": "vite"}}')
            
            yield frontend_dir
    
    @pytest.fixture
    def frontend_orchestrator(self, temp_frontend_dir):
        """Create a FrontendOrchestrator instance for testing"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        orchestrator = FrontendOrchestrator(frontend_dir=temp_frontend_dir)
        return orchestrator
    
    def test_frontend_orchestrator_initialization(self, frontend_orchestrator):
        """Test FrontendOrchestrator initializes correctly"""
        assert frontend_orchestrator is not None
        assert hasattr(frontend_orchestrator, 'debug')
        assert hasattr(frontend_orchestrator, '_frontend_dir')
        assert hasattr(frontend_orchestrator, '_current_process')
        assert hasattr(frontend_orchestrator, '_lock')
        assert frontend_orchestrator._current_process is None
    
    def test_check_dependencies_success(self, frontend_orchestrator, temp_frontend_dir):
        """Test successful dependency checking"""
        # Create node_modules directory
        node_modules = temp_frontend_dir / "node_modules"
        node_modules.mkdir()
        
        result = frontend_orchestrator.check_dependencies()
        
        assert result is True
    
    def test_check_dependencies_missing_package_json(self, temp_frontend_dir):
        """Test dependency checking with missing package.json"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        
        # Remove package.json
        (temp_frontend_dir / "package.json").unlink()
        
        orchestrator = FrontendOrchestrator(frontend_dir=temp_frontend_dir)
        result = orchestrator.check_dependencies()
        
        assert result is False
    
    def test_check_dependencies_missing_node_modules(self, frontend_orchestrator):
        """Test dependency checking with missing node_modules"""
        # node_modules doesn't exist by default
        result = frontend_orchestrator.check_dependencies()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_install_dependencies_success(self, mock_run, frontend_orchestrator):
        """Test successful dependency installation"""
        mock_run.return_value = Mock(returncode=0, stdout="Dependencies installed", stderr="")
        
        result = frontend_orchestrator.install_dependencies()
        
        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert 'npm' in call_args[0][0]
        assert 'install' in call_args[0][0]
    
    @patch('subprocess.run')
    def test_install_dependencies_failure(self, mock_run, frontend_orchestrator):
        """Test failed dependency installation"""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Installation failed")
        
        result = frontend_orchestrator.install_dependencies()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_install_dependencies_timeout(self, mock_run, frontend_orchestrator):
        """Test dependency installation timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(['npm', 'install'], 180)
        
        result = frontend_orchestrator.install_dependencies()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_kill_existing_processes_success(self, mock_run, frontend_orchestrator):
        """Test killing existing frontend processes"""
        # Mock successful process killing
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        result = frontend_orchestrator.kill_existing_processes()
        
        assert result is True
        # Should call pkill for both vite and npm processes
        assert mock_run.call_count >= 2
    
    @patch('subprocess.run')
    def test_kill_existing_processes_no_processes(self, mock_run, frontend_orchestrator):
        """Test killing processes when none exist"""
        # Mock no processes found
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
        
        result = frontend_orchestrator.kill_existing_processes()
        
        # Should still return True (no processes to kill is success)
        assert result is True
    
    @patch('socket.socket')
    @patch('subprocess.Popen')
    def test_start_frontend_server_success(self, mock_popen, mock_socket, frontend_orchestrator):
        """Test successful frontend server startup"""
        # Mock port availability
        mock_socket.return_value.__enter__.return_value.bind.return_value = None
        
        # Mock successful process start
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        result = frontend_orchestrator.start_frontend_server(port=5173, backend_port=8000)
        
        assert result['success'] is True
        assert result['port'] == 5173
        assert result['process'] is mock_process
        assert frontend_orchestrator._current_process is mock_process
    
    @patch('socket.socket')
    def test_start_frontend_server_port_unavailable(self, mock_socket, frontend_orchestrator):
        """Test frontend server startup with unavailable port"""
        # Mock port unavailable
        mock_socket.return_value.__enter__.return_value.bind.side_effect = OSError("Port in use")
        
        result = frontend_orchestrator.start_frontend_server(port=5173, backend_port=8000)
        
        assert result['success'] is False
        assert 'not available' in result['error'].lower()
    
    @patch('socket.socket')
    @patch('subprocess.Popen')
    def test_start_frontend_server_process_fails(self, mock_popen, mock_socket, frontend_orchestrator):
        """Test frontend server startup with process failure"""
        # Mock port available
        mock_socket.return_value.__enter__.return_value.bind.return_value = None
        
        # Mock process failure
        mock_popen.side_effect = OSError("Failed to start process")
        
        result = frontend_orchestrator.start_frontend_server(port=5173, backend_port=8000)
        
        assert result['success'] is False
        assert 'error starting' in result['error'].lower()
    
    def test_stop_frontend_server_no_process(self, frontend_orchestrator):
        """Test stopping frontend server when no process is running"""
        result = frontend_orchestrator.stop_frontend_server()
        
        assert result is True  # No process to stop is success
    
    def test_stop_frontend_server_already_stopped(self, frontend_orchestrator):
        """Test stopping frontend server when process already terminated"""
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Process already terminated
        frontend_orchestrator._current_process = mock_process
        
        result = frontend_orchestrator.stop_frontend_server()
        
        assert result is True
        mock_process.terminate.assert_not_called()
    
    def test_stop_frontend_server_graceful_termination(self, frontend_orchestrator):
        """Test graceful frontend server termination"""
        mock_process = Mock()
        mock_process.poll.side_effect = [None, None, 1]  # Running, still running, then terminated
        mock_process.pid = 12345
        frontend_orchestrator._current_process = mock_process
        
        with patch('time.sleep'):  # Speed up test
            result = frontend_orchestrator.stop_frontend_server()
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_not_called()  # Should not need force kill
    
    def test_stop_frontend_server_force_kill(self, frontend_orchestrator):
        """Test force killing frontend server when graceful termination fails"""
        mock_process = Mock()
        # Process stays running after terminate, then terminates after kill
        poll_count = 0
        def poll_side_effect():
            nonlocal poll_count
            poll_count += 1
            # Running for terminate phase, then terminates in kill phase  
            return None if poll_count < 12 else 1
            
        mock_process.poll.side_effect = poll_side_effect
        mock_process.pid = 12345
        frontend_orchestrator._current_process = mock_process
        
        # Patch time functions to speed up test but keep timing logic intact
        with patch('time.sleep'):
            with patch('time.time', side_effect=lambda: poll_count * 0.2):  # Simulate time passage
                result = frontend_orchestrator.stop_frontend_server(timeout=1)
        
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
    
    def test_stop_frontend_server_kill_fails(self, frontend_orchestrator):
        """Test handling when even force kill fails"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process never terminates
        mock_process.pid = 12345
        frontend_orchestrator._current_process = mock_process
        
        with patch('time.sleep'):  # Speed up test
            result = frontend_orchestrator.stop_frontend_server(timeout=1)
        
        assert result is False  # Failed to stop process
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
    
    def test_get_frontend_status_no_process(self, frontend_orchestrator):
        """Test getting frontend status when no process is running"""
        status = frontend_orchestrator.get_frontend_status()
        
        assert status['running'] is False
        assert status['process'] is None
        assert status['pid'] is None
        assert status['port'] is None
    
    def test_get_frontend_status_running_process(self, frontend_orchestrator):
        """Test getting frontend status with running process"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        frontend_orchestrator._current_process = mock_process
        frontend_orchestrator._current_port = 5173
        
        status = frontend_orchestrator.get_frontend_status()
        
        assert status['running'] is True
        assert status['process'] is mock_process
        assert status['pid'] == 12345
        assert status['port'] == 5173
    
    def test_get_frontend_status_dead_process(self, frontend_orchestrator):
        """Test getting frontend status with terminated process"""
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process terminated
        mock_process.pid = 12345
        frontend_orchestrator._current_process = mock_process
        
        status = frontend_orchestrator.get_frontend_status()
        
        assert status['running'] is False
        assert status['process'] is mock_process
        assert status['pid'] == 12345
        assert 'exit_code' in status
    
    @patch('subprocess.run')
    def test_cleanup_all_processes(self, mock_run, frontend_orchestrator):
        """Test cleaning up all frontend processes"""
        # Set up a running process
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 1]  # Running, then terminated
        frontend_orchestrator._current_process = mock_process
        
        # Mock subprocess.run for killing processes
        mock_run.return_value = Mock(returncode=0)
        
        result = frontend_orchestrator.cleanup_all_processes()
        
        assert result is True
        mock_process.terminate.assert_called_once()
    
    def test_thread_safety(self, frontend_orchestrator):
        """Test that FrontendOrchestrator operations are thread-safe"""
        import threading
        
        results = []
        errors = []
        
        def worker():
            try:
                for i in range(50):
                    # Simulate concurrent access
                    status = frontend_orchestrator.get_frontend_status()
                    results.append(status)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = [threading.Thread(target=worker) for _ in range(3)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have any errors from race conditions
        assert len(errors) == 0
        assert len(results) > 0
    
    def test_environment_variable_setup(self, frontend_orchestrator):
        """Test that environment variables are properly set for frontend"""
        with patch('subprocess.Popen') as mock_popen:
            mock_popen.return_value = Mock(poll=Mock(return_value=None), pid=12345)
            
            with patch('socket.socket') as mock_socket:
                mock_socket.return_value.__enter__.return_value.bind.return_value = None
                
                frontend_orchestrator.start_frontend_server(port=5173, backend_port=8000)
                
                # Check that Popen was called with correct environment
                call_args = mock_popen.call_args
                env = call_args[1]['env']
                assert 'VITE_API_URL' in env
                assert env['VITE_API_URL'] == 'http://localhost:8000'


class TestFrontendOrchestratorIntegration:
    """Integration tests for FrontendOrchestrator"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory with frontend structure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            frontend_dir = project_dir / "frontend"
            frontend_dir.mkdir()
            
            # Create realistic package.json
            package_json = frontend_dir / "package.json"
            package_json.write_text('''
            {
                "name": "lifeboard-frontend",
                "scripts": {
                    "dev": "vite --port 5173 --host 0.0.0.0",
                    "build": "vite build"
                },
                "dependencies": {
                    "react": "^18.0.0",
                    "vite": "^4.0.0"
                }
            }
            ''')
            
            yield frontend_dir
    
    def test_full_frontend_lifecycle(self, temp_project_dir):
        """Test complete frontend lifecycle from dependency check to cleanup"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        orchestrator = FrontendOrchestrator(frontend_dir=temp_project_dir)
        
        # Initially dependencies should not be available
        assert orchestrator.check_dependencies() is False
        
        # Status should show no running process
        status = orchestrator.get_frontend_status()
        assert status['running'] is False
        
        # Cleanup should succeed even with no processes
        assert orchestrator.cleanup_all_processes() is True
    
    def test_port_conflict_handling(self, temp_project_dir):
        """Test handling of port conflicts"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        orchestrator = FrontendOrchestrator(frontend_dir=temp_project_dir)
        
        # Mock a port conflict scenario
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.__enter__.return_value.bind.side_effect = OSError("Address already in use")
            
            result = orchestrator.start_frontend_server(port=5173, backend_port=8000)
            
            assert result['success'] is False
            assert 'not available' in result['error'].lower()
    
    def test_factory_method(self):
        """Test factory method for creating FrontendOrchestrator instances"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        
        orchestrator1 = FrontendOrchestrator.create_orchestrator()
        orchestrator2 = FrontendOrchestrator.create_orchestrator()
        
        # Should create separate instances
        assert orchestrator1 is not orchestrator2
        assert isinstance(orchestrator1, FrontendOrchestrator)
        assert isinstance(orchestrator2, FrontendOrchestrator)


class TestFrontendOrchestratorErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.fixture
    def frontend_orchestrator(self):
        """Create orchestrator with non-existent frontend directory"""
        FrontendOrchestrator, FrontendOrchestratorInterface = get_frontend_orchestrator_classes()
        return FrontendOrchestrator(frontend_dir=Path("/nonexistent/frontend"))
    
    def test_missing_frontend_directory(self, frontend_orchestrator):
        """Test handling of missing frontend directory"""
        assert frontend_orchestrator.check_dependencies() is False
        
        result = frontend_orchestrator.start_frontend_server(port=5173, backend_port=8000)
        assert result['success'] is False
    
    @patch('subprocess.run')
    def test_install_dependencies_permission_error(self, mock_run, frontend_orchestrator):
        """Test handling of permission errors during installation"""
        mock_run.side_effect = PermissionError("Permission denied")
        
        result = frontend_orchestrator.install_dependencies()
        assert result is False
    
    def test_process_exception_handling(self, frontend_orchestrator):
        """Test exception handling in process operations"""
        # Set up a mock process that raises exceptions
        mock_process = Mock()
        mock_process.poll.side_effect = RuntimeError("Process error")
        frontend_orchestrator._current_process = mock_process
        
        # Should handle exceptions gracefully
        status = frontend_orchestrator.get_frontend_status()
        assert 'error' in status
        
        # Stop should also handle exceptions gracefully
        result = frontend_orchestrator.stop_frontend_server()
        # Should attempt to handle the error gracefully
        assert isinstance(result, bool)