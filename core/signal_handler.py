"""
SignalHandler - Extracted from api/server.py for Phase 1.1.2 refactoring

Handles graceful shutdown signals with debug logging integration.
Part of TDD-driven cleanup plan for Lifeboard codebase.
"""

import signal
import threading
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional, Union
from subprocess import Popen

from core.debug_logger import DebugLogger


class SignalHandlerInterface(ABC):
    """Abstract interface for signal handling"""
    
    @abstractmethod
    def register_handlers(self) -> bool:
        """Register signal handlers for graceful shutdown"""
        pass
    
    @abstractmethod
    def graceful_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully"""
        pass
    
    @abstractmethod
    def set_server_instance(self, server_instance: Any) -> None:
        """Set the server instance to control during shutdown"""
        pass
    
    @abstractmethod
    def set_frontend_process(self, frontend_process: Optional[Popen]) -> None:
        """Set the frontend process to cleanup during shutdown"""
        pass
    
    @abstractmethod
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        pass


class SignalHandler(SignalHandlerInterface):
    """
    Handles graceful shutdown signals with comprehensive cleanup.
    
    Features:
    - Signal registration for SIGINT, SIGTERM, and optional signals
    - Graceful shutdown with configurable frontend process cleanup
    - Server instance coordination for uvicorn shutdown
    - Thread-safe shutdown state management
    - Debug logging integration for comprehensive monitoring
    - Comprehensive error handling and recovery
    """
    
    class SignalRegistrationError(Exception):
        """Raised when signal handler registration fails"""
        pass
    
    class ShutdownError(Exception):
        """Raised when shutdown process encounters critical errors"""
        pass
    
    def __init__(self):
        """Initialize SignalHandler with debug logging and thread safety"""
        self.debug = DebugLogger("signal_handler")
        self.refactor_logger = logging.getLogger("refactor")
        
        # Thread-safe shutdown state management
        self._lock = threading.RLock()
        self._shutdown_requested = False
        self._server_instance: Optional[Any] = None
        self._frontend_process: Optional[Popen] = None
        
        # Track registered signal handlers for cleanup
        self._original_handlers = {}
        
        self.debug.log_state("signal_handler_init", {
            'initialized_at': datetime.now(timezone.utc).isoformat(),
            'thread_safe': True,
            'debug_enabled': True,
            'handlers_registered': False
        })
    
    @DebugLogger("signal_handler").trace_function("register_handlers")
    def register_handlers(self) -> bool:
        """
        Register signal handlers for graceful shutdown with enhanced safety checks.
        
        Returns:
            bool: True if all critical handlers registered successfully, False otherwise
        """
        with self._lock:
            self.debug.log_state("signal_registration_start", {
                'target_signals': ['SIGINT', 'SIGTERM'],
                'optional_signals': ['SIGHUP', 'SIGQUIT', 'SIGUSR1', 'SIGUSR2']
            })
            
            registration_success = True
            registered_handlers = []
            failed_handlers = []
            
            # Register critical signal handlers (SIGINT and SIGTERM)
            critical_signals = [
                (signal.SIGINT, 'SIGINT'),
                (signal.SIGTERM, 'SIGTERM')
            ]
            
            for sig, name in critical_signals:
                try:
                    # Store original handler for potential restoration
                    original_handler = signal.signal(sig, self._signal_handler_method)
                    self._original_handlers[sig] = original_handler
                    registered_handlers.append(name)
                    
                    self.debug.log_state("signal_registered", {
                        'signal': name,
                        'signal_number': sig,
                        'handler_method': '_signal_handler_method'
                    })
                    
                    self.refactor_logger.info(f"SIGNAL: Registered graceful shutdown handler for {name}", extra={
                        'component': 'signal_handler',
                        'action': 'register',
                        'signal': name,
                        'signal_number': sig
                    })
                    
                except (OSError, ValueError) as e:
                    self.debug.log_state("signal_registration_failed", {
                        'signal': name,
                        'signal_number': sig,
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
                    failed_handlers.append(name)
                    registration_success = False
                    logging.getLogger("signal_handler").error(f"Failed to register {name} handler: {e}")
            
            # Register optional signal handlers for logging only
            optional_signals = []
            for signal_name in ['SIGHUP', 'SIGQUIT', 'SIGUSR1', 'SIGUSR2']:
                if hasattr(signal, signal_name):
                    sig_value = getattr(signal, signal_name)
                    optional_signals.append((sig_value, signal_name))
                    self.debug.log_state("optional_signal_found", {
                        'signal': signal_name,
                        'signal_number': sig_value
                    })
            
            registered_optional = 0
            for sig_value, signal_name in optional_signals:
                try:
                    original_handler = signal.signal(sig_value, self._log_only_handler)
                    self._original_handlers[sig_value] = original_handler
                    registered_optional += 1
                    
                    self.debug.log_state("optional_signal_registered", {
                        'signal': signal_name,
                        'signal_number': sig_value,
                        'handler_method': '_log_only_handler'
                    })
                    
                except (OSError, ValueError) as e:
                    # Optional signals failing is expected on some platforms
                    self.debug.log_state("optional_signal_failed", {
                        'signal': signal_name,
                        'signal_number': sig_value,
                        'error': str(e),
                        'expected': True
                    })
                except Exception as e:
                    # Unexpected errors should be logged as warnings
                    logging.getLogger("signal_handler").warning(f"Unexpected error registering {signal_name}: {e}")
            
            # Log final registration status
            self.debug.log_state("signal_registration_complete", {
                'success': registration_success,
                'critical_registered': registered_handlers,
                'critical_failed': failed_handlers,
                'optional_registered': registered_optional,
                'total_handlers': len(self._original_handlers)
            })
            
            self.refactor_logger.info("SIGNAL: Signal handler setup completed", extra={
                'component': 'signal_handler',
                'action': 'setup_complete',
                'success': registration_success,
                'critical_handlers': len(registered_handlers),
                'optional_handlers': registered_optional
            })
            
            return registration_success
    
    def _signal_handler_method(self, signum: int, frame: Any) -> None:
        """Internal method that handles signal dispatch with error isolation"""
        try:
            self.graceful_shutdown(signum, frame)
        except Exception as e:
            # Critical error isolation - prevent signal handler from crashing
            logging.getLogger("signal_handler").error(f"Critical error in signal handler: {e}")
            logging.getLogger("signal_handler").exception("Signal handler exception details:")
            
            # Still set shutdown flag even if handler fails
            with self._lock:
                self._shutdown_requested = True
    
    def _log_only_handler(self, signum: int, frame: Any) -> None:
        """Safe logging-only signal handler for optional signals"""
        try:
            # Resolve signal name safely
            signal_name = self._resolve_signal_name(signum)
            
            self.debug.log_state("optional_signal_received", {
                'signal': signal_name,
                'signal_number': signum,
                'action': 'log_only'
            })
            
            logging.getLogger("signal_handler").info(f"SIGNAL: Received {signal_name} ({signum}) - logging only")
            
        except Exception as e:
            # Even logging-only handlers should be robust
            logging.getLogger("signal_handler").debug(f"Error in log-only signal handler: {e}")
    
    @DebugLogger("signal_handler").trace_function("graceful_shutdown")
    def graceful_shutdown(self, signum: int, frame: Any) -> None:
        """
        Handle shutdown signals gracefully with comprehensive cleanup.
        
        Args:
            signum: Signal number received
            frame: Current stack frame (unused but required by signal interface)
        """
        with self._lock:
            # Resolve signal name for logging
            signal_name = self._resolve_signal_name(signum)
            
            self.debug.log_state("graceful_shutdown_start", {
                'signal': signal_name,
                'signal_number': signum,
                'already_requested': self._shutdown_requested,
                'server_available': self._server_instance is not None,
                'frontend_available': self._frontend_process is not None
            })
            
            # Set shutdown flag atomically (idempotent)
            if not self._shutdown_requested:
                self._shutdown_requested = True
                self.debug.log_milestone("shutdown_flag_set", {
                    'signal': signal_name,
                    'first_request': True
                })
            else:
                self.debug.log_state("shutdown_already_requested", {
                    'signal': signal_name,
                    'duplicate_request': True
                })
                return  # Already shutting down, avoid duplicate work
            
            # Handle different signal types
            if signum == signal.SIGINT:
                self._handle_sigint()
            elif signum == signal.SIGTERM:
                self._handle_sigterm()
            else:
                self._handle_other_signal(signal_name, signum)
            
            self.debug.log_milestone("graceful_shutdown_complete", {
                'signal': signal_name,
                'cleanup_completed': True
            })
    
    def _handle_sigint(self) -> None:
        """Handle SIGINT (CTRL-C) with user-friendly messages and comprehensive cleanup"""
        self.debug.log_state("sigint_handling_start", {
            'signal': 'SIGINT',
            'user_friendly_messages': True
        })
        
        try:
            # User-friendly shutdown messages
            print("\\n\\n🛑 Graceful shutdown initiated... Please wait for cleanup to complete.")
            print("⏳ Shutting down services and releasing port bindings...")
        except Exception as print_error:
            self.debug.log_state("sigint_print_error", {
                'error': str(print_error),
                'error_type': type(print_error).__name__
            })
        
        # Cleanup frontend process first
        self._cleanup_frontend_process()
        
        # Trigger server shutdown
        self._cleanup_server_instance(graceful=True)
    
    def _handle_sigterm(self) -> None:
        """Handle SIGTERM with immediate server shutdown"""
        self.debug.log_state("sigterm_handling_start", {
            'signal': 'SIGTERM',
            'immediate_shutdown': True
        })
        
        # For SIGTERM, we don't print user messages, just shutdown cleanly
        self._cleanup_server_instance(graceful=True)
    
    def _handle_other_signal(self, signal_name: str, signum: int) -> None:
        """Handle other signals by just setting shutdown flag"""
        self.debug.log_state("other_signal_handling", {
            'signal': signal_name,
            'signal_number': signum,
            'action': 'shutdown_flag_only'
        })
        
        logging.getLogger("signal_handler").info(f"SIGNAL: Received {signal_name} - setting shutdown flag only")
    
    def _cleanup_frontend_process(self) -> None:
        """Cleanup frontend process with graceful termination and force kill fallback"""
        if self._frontend_process is None:
            self.debug.log_state("frontend_cleanup_skipped", {
                'reason': 'no_frontend_process'
            })
            return
        
        self.debug.log_state("frontend_cleanup_start", {
            'pid': getattr(self._frontend_process, 'pid', 'unknown'),
            'poll_result': self._frontend_process.poll()
        })
        
        try:
            # Check if process is already terminated
            if self._frontend_process.poll() is not None:
                self.debug.log_state("frontend_already_terminated", {
                    'exit_code': self._frontend_process.returncode
                })
                try:
                    print("✅ Frontend server already stopped")
                except:
                    pass  # Ignore print errors
                return
            
            try:
                print("🧹 Stopping frontend server...")
            except:
                pass  # Ignore print errors
            
            # Attempt graceful termination
            self._frontend_process.terminate()
            self.debug.log_state("frontend_terminate_sent", {
                'pid': self._frontend_process.pid
            })
            
            # Wait for graceful termination with timeout
            termination_timeout = 2.0  # seconds
            start_time = time.time()
            
            while (time.time() - start_time) < termination_timeout:
                if self._frontend_process.poll() is not None:
                    self.debug.log_state("frontend_terminated_gracefully", {
                        'pid': self._frontend_process.pid,
                        'duration': time.time() - start_time,
                        'exit_code': self._frontend_process.returncode
                    })
                    try:
                        print("✅ Frontend server stopped")
                    except:
                        pass
                    return
                time.sleep(0.1)
            
            # Graceful termination failed, use force kill
            self.debug.log_state("frontend_force_kill_needed", {
                'pid': self._frontend_process.pid,
                'graceful_timeout': termination_timeout
            })
            
            self._frontend_process.kill()
            
            # Wait briefly for kill to take effect
            kill_timeout = 1.0
            start_time = time.time()
            
            while (time.time() - start_time) < kill_timeout:
                if self._frontend_process.poll() is not None:
                    self.debug.log_state("frontend_force_killed", {
                        'pid': self._frontend_process.pid,
                        'duration': time.time() - start_time,
                        'exit_code': self._frontend_process.returncode
                    })
                    try:
                        print("✅ Frontend server stopped")
                    except:
                        pass
                    return
                time.sleep(0.1)
            
            # Even force kill failed
            self.debug.log_state("frontend_kill_failed", {
                'pid': self._frontend_process.pid,
                'still_running': self._frontend_process.poll() is None
            })
            
            try:
                print("⚠️  Frontend cleanup encountered an issue")
            except:
                pass
            
        except Exception as frontend_error:
            self.debug.log_state("frontend_cleanup_error", {
                'error': str(frontend_error),
                'error_type': type(frontend_error).__name__
            })
            try:
                print("⚠️  Frontend cleanup encountered an issue")
            except:
                pass
    
    def _cleanup_server_instance(self, graceful: bool = True) -> None:
        """Cleanup server instance with proper attribute checking"""
        if self._server_instance is None:
            self.debug.log_state("server_cleanup_skipped", {
                'reason': 'no_server_instance'
            })
            return
        
        self.debug.log_state("server_cleanup_start", {
            'graceful': graceful,
            'has_should_exit': hasattr(self._server_instance, 'should_exit'),
            'has_force_exit': hasattr(self._server_instance, 'force_exit')
        })
        
        try:
            # Set server shutdown flags with proper attribute checking
            if hasattr(self._server_instance, 'should_exit'):
                self._server_instance.should_exit = True
                self.debug.log_state("server_should_exit_set", {
                    'should_exit': True
                })
            else:
                self.debug.log_state("server_missing_should_exit", {
                    'available_attributes': [attr for attr in dir(self._server_instance) 
                                          if not attr.startswith('_')]
                })
            
            if hasattr(self._server_instance, 'force_exit'):
                # For graceful shutdown, don't force exit
                self._server_instance.force_exit = False if graceful else True
                self.debug.log_state("server_force_exit_set", {
                    'force_exit': not graceful,
                    'graceful': graceful
                })
            else:
                self.debug.log_state("server_missing_force_exit", {
                    'graceful': graceful
                })
            
            self.debug.log_milestone("server_shutdown_triggered", {
                'method': 'attribute_setting',
                'graceful': graceful
            })
            
        except AttributeError as attr_error:
            self.debug.log_state("server_attribute_error", {
                'error': str(attr_error),
                'available_attributes': [attr for attr in dir(self._server_instance) 
                                       if not attr.startswith('_')]
            })
            logging.getLogger("signal_handler").error(f"Server instance missing expected attributes: {attr_error}")
            
        except Exception as server_error:
            self.debug.log_state("server_cleanup_error", {
                'error': str(server_error),
                'error_type': type(server_error).__name__
            })
            logging.getLogger("signal_handler").error(f"Error triggering server shutdown: {server_error}")
    
    def _resolve_signal_name(self, signum: int) -> str:
        """Safely resolve signal number to name for logging"""
        try:
            if hasattr(signal, 'Signals') and hasattr(signal.Signals, '__getitem__'):
                return signal.Signals(signum).name
            else:
                return f"signal-{signum}"
        except (ValueError, AttributeError):
            return f"unknown-signal-{signum}"
    
    def set_server_instance(self, server_instance: Any) -> None:
        """
        Set the server instance to control during shutdown.
        
        Args:
            server_instance: Server instance (typically uvicorn server) with should_exit/force_exit attributes
        """
        with self._lock:
            self._server_instance = server_instance
            
            self.debug.log_state("server_instance_set", {
                'server_type': type(server_instance).__name__ if server_instance else None,
                'has_should_exit': hasattr(server_instance, 'should_exit') if server_instance else False,
                'has_force_exit': hasattr(server_instance, 'force_exit') if server_instance else False
            })
    
    def set_frontend_process(self, frontend_process: Optional[Popen]) -> None:
        """
        Set the frontend process to cleanup during shutdown.
        
        Args:
            frontend_process: Subprocess.Popen instance for frontend server, or None
        """
        with self._lock:
            self._frontend_process = frontend_process
            
            self.debug.log_state("frontend_process_set", {
                'process_type': type(frontend_process).__name__ if frontend_process else None,
                'pid': getattr(frontend_process, 'pid', None) if frontend_process else None,
                'is_running': frontend_process.poll() is None if frontend_process else False
            })
    
    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            bool: True if shutdown has been requested, False otherwise
        """
        with self._lock:
            return self._shutdown_requested
    
    def cleanup_handlers(self) -> None:
        """Restore original signal handlers on cleanup"""
        with self._lock:
            restored_count = 0
            for sig, original_handler in self._original_handlers.items():
                try:
                    signal.signal(sig, original_handler)
                    restored_count += 1
                except (OSError, ValueError):
                    pass  # Ignore errors during cleanup
            
            self.debug.log_state("signal_handlers_restored", {
                'total_handlers': len(self._original_handlers),
                'restored_count': restored_count
            })
            
            self._original_handlers.clear()
    
    @classmethod
    def create_handler(cls) -> 'SignalHandler':
        """
        Factory method to create a SignalHandler instance.
        
        Returns:
            SignalHandler: New instance configured with debug logging
        """
        return cls()
    
    def __del__(self):
        """Cleanup signal handlers when SignalHandler is destroyed"""
        try:
            self.cleanup_handlers()
        except:
            # Ignore all errors during destructor cleanup
            pass