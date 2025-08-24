"""
Feature Flag Infrastructure for Lifeboard
Enables gradual rollout and quick rollback of refactored components.

As specified in latest_clean.md Phase 1.3
"""
from typing import Dict, Any
from enum import Enum


class FeatureFlag(Enum):
    """Enumeration of all available feature flags in the system"""
    NEW_PROCESS_MANAGER = "new_process_manager"
    NEW_SIGNAL_HANDLER = "new_signal_handler" 
    NEW_FRONTEND_ORCHESTRATOR = "new_frontend_orchestrator"
    UNIFIED_HTTP_CLIENT = "unified_http_client"
    DEPENDENCY_INJECTION = "dependency_injection"


class FeatureFlagManager:
    """
    Manages feature flag state and provides safe access to flag values.
    
    Supports:
    - Default configuration (all flags disabled)
    - Custom configuration override
    - Runtime flag toggling
    - Safe flag checking with fallback to False
    """
    
    def __init__(self, config: Dict[str, bool] = None):
        """
        Initialize feature flag manager with optional custom configuration.
        
        Args:
            config: Optional dictionary mapping flag names to boolean values.
                   If None, all flags default to False.
        """
        if config is None:
            # Default configuration - all flags disabled for safety
            self.flags = {
                FeatureFlag.NEW_PROCESS_MANAGER.value: False,
                FeatureFlag.NEW_SIGNAL_HANDLER.value: False,
                FeatureFlag.NEW_FRONTEND_ORCHESTRATOR.value: False,
                FeatureFlag.UNIFIED_HTTP_CLIENT.value: False,
                FeatureFlag.DEPENDENCY_INJECTION.value: False,
            }
        else:
            # Use provided config, but ensure all flags have defaults
            self.flags = {
                FeatureFlag.NEW_PROCESS_MANAGER.value: config.get(FeatureFlag.NEW_PROCESS_MANAGER.value, False),
                FeatureFlag.NEW_SIGNAL_HANDLER.value: config.get(FeatureFlag.NEW_SIGNAL_HANDLER.value, False),
                FeatureFlag.NEW_FRONTEND_ORCHESTRATOR.value: config.get(FeatureFlag.NEW_FRONTEND_ORCHESTRATOR.value, False),
                FeatureFlag.UNIFIED_HTTP_CLIENT.value: config.get(FeatureFlag.UNIFIED_HTTP_CLIENT.value, False),
                FeatureFlag.DEPENDENCY_INJECTION.value: config.get(FeatureFlag.DEPENDENCY_INJECTION.value, False),
            }
    
    def is_enabled(self, flag: FeatureFlag) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag: The FeatureFlag enum value to check
            
        Returns:
            bool: True if flag is enabled, False otherwise (including for unknown flags)
        """
        return self.flags.get(flag.value, False)
    
    def enable_flag(self, flag: FeatureFlag) -> None:
        """
        Enable a feature flag at runtime.
        
        Args:
            flag: The FeatureFlag enum value to enable
        """
        self.flags[flag.value] = True
    
    def disable_flag(self, flag: FeatureFlag) -> None:
        """
        Disable a feature flag at runtime.
        
        Args:
            flag: The FeatureFlag enum value to disable  
        """
        self.flags[flag.value] = False
    
    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get current state of all feature flags.
        
        Returns:
            Dict mapping flag names to their current boolean values
        """
        return self.flags.copy()
    
    def set_flags(self, flag_config: Dict[str, bool]) -> None:
        """
        Bulk update multiple flags at once.
        
        Args:
            flag_config: Dictionary mapping flag names to boolean values
        """
        for flag_name, enabled in flag_config.items():
            if flag_name in self.flags:
                self.flags[flag_name] = enabled