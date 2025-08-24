"""
Test suite for Feature Flag Infrastructure
Following TDD approach as specified in latest_clean.md
"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict

from core.feature_flags import FeatureFlag, FeatureFlagManager


class TestFeatureFlag:
    """Test Feature Flag enum values"""
    
    def test_feature_flag_enum_values(self):
        """Test that all expected feature flags exist with correct values"""
        assert FeatureFlag.NEW_PROCESS_MANAGER.value == "new_process_manager"
        assert FeatureFlag.NEW_SIGNAL_HANDLER.value == "new_signal_handler"
        assert FeatureFlag.NEW_FRONTEND_ORCHESTRATOR.value == "new_frontend_orchestrator"
        assert FeatureFlag.UNIFIED_HTTP_CLIENT.value == "unified_http_client"
        assert FeatureFlag.DEPENDENCY_INJECTION.value == "dependency_injection"


class TestFeatureFlagManager:
    """Test Feature Flag Manager functionality"""
    
    def test_default_initialization(self):
        """Test that manager initializes with all flags disabled by default"""
        manager = FeatureFlagManager()
        
        for flag in FeatureFlag:
            assert manager.is_enabled(flag) is False
    
    def test_custom_config_initialization(self):
        """Test initialization with custom configuration"""
        custom_config = {
            FeatureFlag.NEW_PROCESS_MANAGER.value: True,
            FeatureFlag.UNIFIED_HTTP_CLIENT.value: True,
        }
        
        manager = FeatureFlagManager(custom_config)
        
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True
        assert manager.is_enabled(FeatureFlag.UNIFIED_HTTP_CLIENT) is True
        assert manager.is_enabled(FeatureFlag.NEW_SIGNAL_HANDLER) is False
    
    def test_enable_flag(self):
        """Test enabling a feature flag"""
        manager = FeatureFlagManager()
        
        # Initially disabled
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is False
        
        # Enable flag
        manager.enable_flag(FeatureFlag.NEW_PROCESS_MANAGER)
        
        # Should now be enabled
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True
    
    def test_disable_flag(self):
        """Test disabling a feature flag"""
        custom_config = {FeatureFlag.NEW_PROCESS_MANAGER.value: True}
        manager = FeatureFlagManager(custom_config)
        
        # Initially enabled
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True
        
        # Disable flag
        manager.disable_flag(FeatureFlag.NEW_PROCESS_MANAGER)
        
        # Should now be disabled
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is False
    
    def test_unknown_flag_returns_false(self):
        """Test that unknown flags return False by default"""
        manager = FeatureFlagManager()
        
        # Mock a flag that doesn't exist in the config
        with patch.object(manager, 'flags', {}):
            fake_flag = MagicMock()
            fake_flag.value = "non_existent_flag"
            
            assert manager.is_enabled(fake_flag) is False
    
    def test_flag_state_persistence(self):
        """Test that flag states persist across multiple operations"""
        manager = FeatureFlagManager()
        
        # Enable multiple flags
        manager.enable_flag(FeatureFlag.NEW_PROCESS_MANAGER)
        manager.enable_flag(FeatureFlag.UNIFIED_HTTP_CLIENT)
        
        # Verify both are enabled
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True
        assert manager.is_enabled(FeatureFlag.UNIFIED_HTTP_CLIENT) is True
        
        # Disable one
        manager.disable_flag(FeatureFlag.NEW_PROCESS_MANAGER)
        
        # Verify states are independent
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is False
        assert manager.is_enabled(FeatureFlag.UNIFIED_HTTP_CLIENT) is True
    
    def test_all_flags_covered_in_defaults(self):
        """Test that all enum flags have default values in manager"""
        manager = FeatureFlagManager()
        
        for flag in FeatureFlag:
            # Should not raise KeyError and should return a boolean
            result = manager.is_enabled(flag)
            assert isinstance(result, bool)


class TestFeatureFlagManagerConfiguration:
    """Test configuration and integration scenarios"""
    
    def test_partial_config_with_defaults(self):
        """Test that partial config uses defaults for unspecified flags"""
        partial_config = {
            FeatureFlag.NEW_PROCESS_MANAGER.value: True,
        }
        
        manager = FeatureFlagManager(partial_config)
        
        # Specified flag should use config value
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True
        
        # Unspecified flags should default to False
        assert manager.is_enabled(FeatureFlag.NEW_SIGNAL_HANDLER) is False
        assert manager.is_enabled(FeatureFlag.UNIFIED_HTTP_CLIENT) is False
    
    def test_config_override_protection(self):
        """Test that runtime changes don't affect original config"""
        original_config = {
            FeatureFlag.NEW_PROCESS_MANAGER.value: False,
        }
        
        manager = FeatureFlagManager(original_config.copy())
        
        # Modify through manager
        manager.enable_flag(FeatureFlag.NEW_PROCESS_MANAGER)
        
        # Original config should be unchanged
        assert original_config[FeatureFlag.NEW_PROCESS_MANAGER.value] is False
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True


class TestFeatureFlagIntegration:
    """Integration tests for feature flag usage patterns"""
    
    def test_gradual_rollout_pattern(self):
        """Test gradual rollout pattern - enabling flags progressively"""
        manager = FeatureFlagManager()
        
        # Phase 1: Enable core infrastructure
        manager.enable_flag(FeatureFlag.NEW_PROCESS_MANAGER)
        assert manager.is_enabled(FeatureFlag.NEW_PROCESS_MANAGER) is True
        assert manager.is_enabled(FeatureFlag.NEW_SIGNAL_HANDLER) is False
        
        # Phase 2: Enable signal handling
        manager.enable_flag(FeatureFlag.NEW_SIGNAL_HANDLER)
        assert manager.is_enabled(FeatureFlag.NEW_SIGNAL_HANDLER) is True
        
        # Phase 3: Enable HTTP client
        manager.enable_flag(FeatureFlag.UNIFIED_HTTP_CLIENT)
        assert manager.is_enabled(FeatureFlag.UNIFIED_HTTP_CLIENT) is True
    
    def test_quick_rollback_pattern(self):
        """Test quick rollback - disabling problematic flags"""
        # Start with all flags enabled
        all_enabled_config = {flag.value: True for flag in FeatureFlag}
        manager = FeatureFlagManager(all_enabled_config)
        
        # Verify all enabled
        for flag in FeatureFlag:
            assert manager.is_enabled(flag) is True
        
        # Quick rollback of problematic feature
        manager.disable_flag(FeatureFlag.NEW_FRONTEND_ORCHESTRATOR)
        
        # Verify rollback
        assert manager.is_enabled(FeatureFlag.NEW_FRONTEND_ORCHESTRATOR) is False
        
        # Verify other flags unaffected
        remaining_flags = [f for f in FeatureFlag if f != FeatureFlag.NEW_FRONTEND_ORCHESTRATOR]
        for flag in remaining_flags:
            assert manager.is_enabled(flag) is True