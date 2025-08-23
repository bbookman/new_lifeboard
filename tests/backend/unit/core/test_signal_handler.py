"""
Test suite for SignalHandler extraction from api/server.py
Part of TDD-driven cleanup plan for Lifeboard codebase.

Tests follow the pattern described in clean_now.md Phase 1.1.2
"""

import pytest
import signal
import sys
import threading
import time
import unittest.mock as mock
from unittest.mock import Mock, MagicMock, patch

# Now we can directly import the real classes since they exist (TDD Green phase)
from core.signal_handler import SignalHandler, SignalHandlerInterface

def get_signal_handler_classes():
    """Get the SignalHandler classes (now real implementation)"""
    return SignalHandler, SignalHandlerInterface


class TestSignalHandlerInterface:
    """Test the SignalHandler interface contract"""
    
    def test_interface_methods_exist(self):
        """Test that SignalHandlerInterface defines required methods"""
        SignalHandler, SignalHandlerInterface = get_signal_handler_classes()
        
        # Verify abstract methods exist (these will be mocked but we test the interface)
        interface_methods = ['register_handlers', 'graceful_shutdown', 'set_server_instance', 
                           'set_frontend_process', 'is_shutdown_requested']
        
        # In Red phase, we're testing the interface contract
        # The actual implementation doesn't exist yet, so this will fail
        for method in interface_methods:
            assert hasattr(SignalHandlerInterface, method)


class TestSignalHandler:
    """Test SignalHandler implementation"""
    
    @pytest.fixture
    def signal_handler(self):
        """Create a SignalHandler instance for testing"""
        SignalHandler, SignalHandlerInterface = get_signal_handler_classes()
        return SignalHandler()
    
    def test_signal_handler_initialization(self, signal_handler):
        """Test SignalHandler initializes correctly"""
        assert signal_handler is not None
        assert hasattr(signal_handler, 'debug')
        assert signal_handler._shutdown_requested is False
        assert signal_handler._server_instance is None
        assert signal_handler._frontend_process is None
        assert hasattr(signal_handler, '_lock')
    
    def test_register_handlers_success(self, signal_handler):
        """Test signal handlers are registered successfully"""
        with patch('signal.signal') as mock_signal:
            result = signal_handler.register_handlers()
            
            # Should register SIGINT and SIGTERM
            assert mock_signal.call_count >= 2
            mock_signal.assert_any_call(signal.SIGINT, signal_handler._signal_handler_method)
            mock_signal.assert_any_call(signal.SIGTERM, signal_handler._signal_handler_method)
            assert result is True
    
    def test_register_handlers_failure(self, signal_handler):
        """Test graceful handling of signal registration failure"""
        with patch('signal.signal', side_effect=OSError("Signal registration failed")):
            result = signal_handler.register_handlers()
            # Should handle failure gracefully and return False
            assert result is False
    
    def test_set_server_instance(self, signal_handler):
        """Test setting server instance"""
        mock_server = Mock()
        mock_server.should_exit = False
        mock_server.force_exit = False
        
        signal_handler.set_server_instance(mock_server)
        assert signal_handler._server_instance is mock_server
    
    def test_set_frontend_process(self, signal_handler):
        """Test setting frontend process"""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        
        signal_handler.set_frontend_process(mock_process)
        assert signal_handler._frontend_process is mock_process
    
    def test_is_shutdown_requested_initial_state(self, signal_handler):
        """Test initial shutdown state is False"""
        assert signal_handler.is_shutdown_requested() is False
    
    def test_graceful_shutdown_sigint_with_server_and_frontend(self, signal_handler):
        """Test graceful shutdown handling for SIGINT with server and frontend"""
        # Setup mock server
        mock_server = Mock()
        mock_server.should_exit = False
        mock_server.force_exit = False
        signal_handler.set_server_instance(mock_server)
        
        # Setup mock frontend process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        signal_handler.set_frontend_process(mock_process)
        
        # Test SIGINT handling
        with patch('builtins.print') as mock_print:
            signal_handler.graceful_shutdown(signal.SIGINT, None)
            
            # Should set shutdown flag
            assert signal_handler.is_shutdown_requested() is True
            
            # Should set server shutdown flags
            assert mock_server.should_exit is True
            assert mock_server.force_exit is False
            
            # Should terminate frontend process
            mock_process.terminate.assert_called_once()
            
            # Should print shutdown messages
            assert mock_print.called
    
    def test_graceful_shutdown_sigterm(self, signal_handler):
        """Test graceful shutdown handling for SIGTERM"""
        mock_server = Mock()
        mock_server.should_exit = False
        signal_handler.set_server_instance(mock_server)
        
        signal_handler.graceful_shutdown(signal.SIGTERM, None)
        
        # Should set shutdown flag and server exit flag
        assert signal_handler.is_shutdown_requested() is True
        assert mock_server.should_exit is True
    
    def test_graceful_shutdown_unknown_signal(self, signal_handler):
        """Test handling of unknown signals"""
        signal_handler.graceful_shutdown(999, None)  # Unknown signal
        
        # Should only set shutdown flag
        assert signal_handler.is_shutdown_requested() is True
    
    def test_graceful_shutdown_frontend_process_cleanup_force_kill(self, signal_handler):
        """Test frontend process cleanup with force kill when terminate fails"""
        mock_process = Mock()
        mock_process.poll.side_effect = [None, None, 1]  # Running, still running after terminate, then dead
        mock_process.pid = 12345
        signal_handler.set_frontend_process(mock_process)
        
        with patch('time.sleep'):  # Speed up test
            signal_handler.graceful_shutdown(signal.SIGINT, None)
            
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()
    
    def test_graceful_shutdown_frontend_already_dead(self, signal_handler):
        """Test handling when frontend process is already terminated"""
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Process already terminated
        mock_process.pid = 12345
        signal_handler.set_frontend_process(mock_process)
        
        signal_handler.graceful_shutdown(signal.SIGINT, None)
        
        # Should not try to terminate already dead process
        mock_process.terminate.assert_not_called()
    
    def test_graceful_shutdown_server_missing_attributes(self, signal_handler):
        """Test handling when server instance is missing expected attributes"""
        mock_server = Mock()
        # Server missing should_exit attribute
        delattr(mock_server, 'should_exit') if hasattr(mock_server, 'should_exit') else None
        mock_server.spec = []  # Empty spec so hasattr returns False
        
        signal_handler.set_server_instance(mock_server)
        
        # Should handle gracefully without raising exceptions
        signal_handler.graceful_shutdown(signal.SIGINT, None)
        assert signal_handler.is_shutdown_requested() is True
    
    def test_graceful_shutdown_exception_handling(self, signal_handler):
        """Test exception handling during graceful shutdown"""
        mock_server = Mock()
        mock_server.should_exit = False
        # Make setting should_exit raise an exception
        mock_server.__setattr__ = Mock(side_effect=RuntimeError("Server error"))
        signal_handler.set_server_instance(mock_server)
        
        # Should handle exception gracefully and continue
        signal_handler.graceful_shutdown(signal.SIGTERM, None)
        
        # Shutdown flag should still be set despite server error
        assert signal_handler.is_shutdown_requested() is True
    
    def test_thread_safety(self, signal_handler):
        """Test that SignalHandler operations are thread-safe"""
        results = []
        errors = []
        
        def worker():
            try:
                for i in range(100):
                    # Simulate concurrent access
                    signal_handler.is_shutdown_requested()
                    if i % 10 == 0:  # Occasional shutdown request
                        signal_handler.graceful_shutdown(signal.SIGTERM, None)
                    results.append(i)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have any errors from race conditions
        assert len(errors) == 0
        assert len(results) > 0
    
    def test_signal_name_resolution(self, signal_handler):
        """Test signal name resolution for logging"""
        # Test with valid signal
        with patch.object(signal_handler.debug, 'log_state') as mock_log_state:
            signal_handler.graceful_shutdown(signal.SIGINT, None)
            
            # Should log with proper signal name
            mock_log_state.assert_called()
            call_args = mock_log_state.call_args_list
            assert any('SIGINT' in str(call) or 'signal_name' in str(call) for call in call_args)
    
    def test_multiple_shutdown_calls_idempotent(self, signal_handler):
        """Test that multiple shutdown calls are idempotent"""
        mock_server = Mock()
        mock_server.should_exit = False
        signal_handler.set_server_instance(mock_server)
        
        # Call graceful shutdown multiple times
        signal_handler.graceful_shutdown(signal.SIGINT, None)
        first_state = signal_handler.is_shutdown_requested()
        
        signal_handler.graceful_shutdown(signal.SIGINT, None)
        second_state = signal_handler.is_shutdown_requested()
        
        # State should be consistent
        assert first_state is True
        assert second_state is True
        # Server should_exit should only be set once (no side effects)
        assert mock_server.should_exit is True


class TestSignalHandlerIntegration:
    """Integration tests for SignalHandler"""
    
    def test_signal_handler_with_real_signal_registration(self):
        """Test SignalHandler with actual signal registration (careful test)"""
        SignalHandler, SignalHandlerInterface = get_signal_handler_classes()
        signal_handler = SignalHandler()
        
        # Store original handlers to restore later
        original_sigint = signal.signal(signal.SIGINT, signal.default_int_handler)
        original_sigterm = signal.signal(signal.SIGTERM, signal.default_int_handler)
        
        try:
            # Register our handlers
            result = signal_handler.register_handlers()
            assert result is True
            
            # Verify handlers are registered (can't easily test the actual handler function)
            # But we can verify no exceptions were raised during registration
            
        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
    
    def test_signal_handler_factory_method(self):
        """Test factory method for creating SignalHandler instances"""
        SignalHandler, SignalHandlerInterface = get_signal_handler_classes()
        
        handler1 = SignalHandler.create_handler()
        handler2 = SignalHandler.create_handler()
        
        # Should create separate instances
        assert handler1 is not handler2
        # Note: isinstance checks will work with mocks in Red phase