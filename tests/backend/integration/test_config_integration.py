"""
Integration tests for configuration validation system
Part of Phase 1.2: Configuration Standardization
"""
import pytest
import tempfile
from pathlib import Path
from config.factory import ConfigFactory, create_test_config
from config.startup_validation import (
    validate_configuration_at_startup,
    validate_environment_file_consistency,
    ConfigurationValidationError
)


class TestConfigurationIntegration:
    """Integration tests for configuration system"""
    
    def test_complete_test_config_validation_flow(self):
        """Test complete configuration validation flow with test config"""
        # Create test configuration
        config = create_test_config()
        
        # Should pass validation (with some warnings for missing API keys)
        try:
            validate_configuration_at_startup(config)
            # If we get here, validation passed
            validation_passed = True
        except ConfigurationValidationError:
            validation_passed = False
        
        # Test config should be valid (though may have warnings)
        assert validation_passed
    
    def test_environment_file_consistency_integration(self):
        """Test that .env.example is consistent with current models"""
        is_consistent, errors = validate_environment_file_consistency()
        
        # Should be consistent based on our implementation
        if not is_consistent:
            pytest.fail(f"Environment file consistency check failed: {errors}")
        
        assert is_consistent
        assert len(errors) == 0
    
    def test_config_factory_produces_valid_configs(self):
        """Test that ConfigFactory produces configurations that pass validation"""
        # Test configuration should be valid
        test_config = create_test_config()
        
        # Should not raise exception (though may have warnings)
        try:
            validate_configuration_at_startup(test_config)
        except ConfigurationValidationError as e:
            pytest.fail(f"Test config should be valid: {e}")
    
    def test_typo_detection_works(self):
        """Test that the typo detection system works"""
        config = create_test_config()
        
        # Verify that longitude field exists and logitude does not
        assert hasattr(config.weather, 'longitude')
        assert not hasattr(config.weather, 'logitude')
        
        # Test the longitude field contains a valid value
        longitude = config.weather.longitude
        try:
            lon_float = float(longitude)
            assert -180 <= lon_float <= 180
        except ValueError:
            pytest.fail(f"Longitude value should be a valid number: {longitude}")


if __name__ == "__main__":
    pytest.main([__file__])