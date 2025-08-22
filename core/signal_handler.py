"""
SignalHandler - Manages graceful shutdown signals for Lifeboard application.

Extracted from api/server.py as part of TDD-driven architecture cleanup.
Handles SIGINT and SIGTERM signals with configurable shutdown callbacks.
"""

import logging
import signal
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ShutdownCallbacks:
    """Data class for organizing shutdown callbacks."""
    
    frontend_cleanup: Optional[Callable[[], None]] = None
    server_shutdown: Optional[Callable[[], None]] = None
    process_cleanup: Optional[Callable[[], None]] = None
    final_cleanup: Optional[Callable[[], None]] = None
    cleanup: Optional[Callable[[], None]] = None
    
    # Allow additional arbitrary callbacks
    callbacks: Dict[str, Callable[[], None]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Callable[[], None]]:
        """Convert to dictionary format for SignalHandler."""
        result = {}
        
        # Add predefined callbacks
        if self.frontend_cleanup:
            result["frontend_cleanup"] = self.frontend_cleanup
        if self.server_shutdown:
            result["server_shutdown"] = self.server_shutdown
        if self.process_cleanup:
            result["process_cleanup"] = self.process_cleanup
        if self.final_cleanup:
            result["final_cleanup"] = self.final_cleanup
        if self.cleanup:
            result["cleanup"] = self.cleanup
            
        # Add additional callbacks
        result.update(self.callbacks)
        
        return result


class SignalHandler:
    """Handles graceful shutdown signals with configurable callbacks."""
    
    def __init__(self):
        """Initialize SignalHandler with default state."""
        self.shutdown_requested: bool = False
        self.callbacks: Dict[str, Callable[[], None]] = {}
        self._shutdown_executed: bool = False
        logger.info("SIGNAL: SignalHandler initialized")
    
    def setup_handlers(self) -> None:
        """Register signal handlers for SIGINT and SIGTERM."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
            logger.info("SIGNAL: Registered handlers for SIGINT and SIGTERM")
        except Exception as e:
            logger.error(f"SIGNAL: Failed to register signal handlers: {e}")
            raise
    
    def set_callbacks(self, callbacks: Dict[str, Callable[[], None]]) -> None:
        """
        Set shutdown callbacks to be executed on signal.
        
        Args:
            callbacks: Dictionary mapping callback names to functions
        """
        self.callbacks = callbacks.copy()
        logger.info(f"SIGNAL: Registered {len(callbacks)} shutdown callbacks")
    
    def _handle_signal(self, signal_num: int, frame) -> None:
        """
        Handle received signal and execute shutdown callbacks.
        
        Args:
            signal_num: Signal number received
            frame: Current stack frame (unused)
        """
        signal_name = self._get_signal_name(signal_num)
        logger.info(f"SIGNAL: Received {signal_name}")
        
        # Set shutdown flag
        self.shutdown_requested = True
        
        # Execute callbacks only once
        if not self._shutdown_executed:
            self._execute_shutdown_callbacks(signal_name)
            self._shutdown_executed = True
        else:
            logger.info(f"SIGNAL: Shutdown already in progress, ignoring {signal_name}")
    
    def _execute_shutdown_callbacks(self, signal_name: str) -> None:
        """Execute all registered shutdown callbacks."""
        logger.info(f"SIGNAL: Executing shutdown callbacks for {signal_name}")
        
        for callback_name, callback in self.callbacks.items():
            try:
                logger.debug(f"SIGNAL: Executing callback '{callback_name}'")
                callback()
                logger.debug(f"SIGNAL: Callback '{callback_name}' completed")
            except Exception as e:
                logger.error(f"SIGNAL: Error in callback '{callback_name}': {e}")
                # Continue with other callbacks despite individual failures
        
        logger.info("SIGNAL: All shutdown callbacks completed")
    
    def _get_signal_name(self, signal_num: int) -> str:
        """
        Get human-readable signal name for logging.
        
        Args:
            signal_num: Signal number
            
        Returns:
            str: Signal name or description
        """
        try:
            return signal.Signals(signal_num).name
        except ValueError:
            # Handle unknown signals gracefully
            return f"UNKNOWN_SIGNAL_{signal_num}"
    
    def reset(self) -> None:
        """Reset shutdown state for testing purposes."""
        self.shutdown_requested = False
        self._shutdown_executed = False
        logger.debug("SIGNAL: Reset shutdown state")