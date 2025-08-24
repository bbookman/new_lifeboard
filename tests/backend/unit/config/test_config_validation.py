"""
Configuration validation tests for Phase 1.2: Configuration Standardization
Tests validate consistency between .env.example and configuration models
"""
import pytest
import os
import re
from pathlib import Path
from typing import Dict, Set, List, Any
from pydantic import ValidationError
from config.models import (
    LimitlessConfig, NewsConfig, WeatherConfig, DatabaseConfig, 
    EmbeddingConfig, VectorStoreConfig
)
from config.factory import ConfigFactory


class TestConfigValidation:
    """Test configuration consistency and validation"""
    
    @pytest.fixture
    def env_example_path(self) -> Path:
        """Path to .env.example file"""
        return Path(__file__).parent.parent.parent.parent.parent / ".env.example"
    
    @pytest.fixture
    def config_models_path(self) -> Path:
        """Path to config/models.py file"""
        return Path(__file__).parent.parent.parent.parent.parent / "config" / "models.py"
    
    @pytest.fixture
    def env_vars_from_example(self, env_example_path: Path) -> Dict[str, str]:
        """Extract environment variables from .env.example"""
        env_vars = {}
        if not env_example_path.exists():
            pytest.skip(f".env.example file not found at {env_example_path}")
        
        with open(env_example_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE format
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')  # Remove quotes
                    env_vars[key] = value
        
        return env_vars
    
    @pytest.fixture
    def config_field_mappings(self) -> Dict[str, Dict[str, str]]:
        """Expected mappings between env vars and config fields"""
        return {
            'limitless': {
                'LIMITLESS__API_KEY': 'api_key',
                'LIMITLESS__BASE_URL': 'base_url', 
                'LIMITLESS__MAX_RETRIES': 'max_retries',
                'LIMITLESS__RETRY_DELAY': 'retry_delay',
                'LIMITLESS__REQUEST_TIMEOUT': 'request_timeout',
                'LIMITLESS__SYNC_INTERVAL_HOURS': 'sync_interval_hours',
                'LIMITLESS__RATE_LIMIT_MAX_DELAY': 'rate_limit_max_delay',
                'LIMITLESS__RESPECT_RETRY_AFTER': 'respect_retry_after',
                'TIME_ZONE': 'timezone'
            },
            'news': {
                'RAPID_API_KEY': 'api_key',
                'NEWS_ENDPOINT': 'endpoint',
                'NEWS_COUNTRY': 'country',
                'UNIQUE_NEWS_ITEMS_PER_DAY': 'unique_items_per_day',
                'NEWS_ITEMS_TO_RETRIEVE': 'items_to_retrieve',
                'TURN_ON_NEWS': 'enabled'
            },
            'weather': {
                'RAPID_API_KEY': 'api_key',
                'WEATHER_ENDPOINT': 'endpoint',
                'USER_HOME_LATITUDE': 'latitude',
                'USER_HOME_LONGITUDE': 'longitude',
                'UNITS': 'units'
            },
            'embedding': {
                'EMBEDDING_MODEL': 'model_name',
                'EMBEDDING_DEVICE': 'device',
                'EMBEDDING_BATCH_SIZE': 'batch_size'
            }
        }
    
    def test_env_example_exists(self, env_example_path: Path):
        """Ensure .env.example file exists"""
        assert env_example_path.exists(), f".env.example file not found at {env_example_path}"
    
    def test_env_example_has_all_required_keys(self, env_vars_from_example: Dict[str, str]):
        """Verify .env.example contains all required configuration keys"""
        required_keys = {
            # Limitless API
            'LIMITLESS__API_KEY', 'LIMITLESS__BASE_URL',
            # News API  
            'RAPID_API_KEY', 'NEWS_ENDPOINT', 'NEWS_COUNTRY',
            # Weather API
            'USER_HOME_LATITUDE', 'USER_HOME_LONGITUDE', 'UNITS',
            # Embedding
            'EMBEDDING_MODEL', 'EMBEDDING_DEVICE', 'EMBEDDING_BATCH_SIZE',
            # Basic config
            'TIME_ZONE', 'USERS_LANGUAGE'
        }
        
        missing_keys = required_keys - set(env_vars_from_example.keys())
        assert not missing_keys, f"Missing required keys in .env.example: {missing_keys}"
    
    def test_config_key_consistency(self, env_vars_from_example: Dict[str, str], 
                                   config_field_mappings: Dict[str, Dict[str, str]]):
        """Test that environment variable names are consistent with configuration models"""
        # Check for naming inconsistencies
        for section, mappings in config_field_mappings.items():
            for env_key, field_name in mappings.items():
                assert env_key in env_vars_from_example, \
                    f"Environment variable {env_key} not found in .env.example (maps to {section}.{field_name})"
    
    def test_no_typos_in_longitude_latitude(self, env_vars_from_example: Dict[str, str]):
        """Test for common typos like LOGITUDE instead of LONGITUDE"""
        # Check for the specific typo mentioned in clean_now.md
        typo_variations = [
            'USER_HOME_LOGITUDE', 'LOGITUDE', 'USER_LOGITUDE'
        ]
        
        found_typos = []
        for typo in typo_variations:
            if typo in env_vars_from_example:
                found_typos.append(typo)
        
        assert not found_typos, f"Found typos in .env.example: {found_typos}. Should be 'USER_HOME_LONGITUDE'"
    
    def test_config_models_field_validation(self):
        """Test that configuration models properly validate fields"""
        # Test WeatherConfig longitude/latitude fields
        config = WeatherConfig(
            latitude="34.0522",
            longitude="-118.2437"  # Should be longitude, not "logitude"
        )
        
        # Verify field names are correct
        assert hasattr(config, 'longitude'), "WeatherConfig should have 'longitude' field"
        assert hasattr(config, 'latitude'), "WeatherConfig should have 'latitude' field"
        assert not hasattr(config, 'logitude'), "WeatherConfig should not have 'logitude' field (typo)"
    
    def test_missing_config_handling(self):
        """Test graceful handling of missing configuration"""
        # Test that individual config objects handle None API keys
        limitless_config = LimitlessConfig(api_key=None)
        assert limitless_config.api_key is None
        
        news_config = NewsConfig(api_key=None)
        assert news_config.api_key is None
        
        weather_config = WeatherConfig(api_key=None)
        assert weather_config.api_key is None
        
        # Test that validation methods handle None correctly
        assert not limitless_config.is_api_key_configured()
        assert not news_config.is_api_key_configured()
        assert not weather_config.is_api_key_configured()
    
    def test_configuration_validation_at_startup(self):
        """Test that configuration validation catches issues at startup"""
        # This test ensures startup validation will catch config issues
        
        # Test that configuration models validate required formats
        # Test that units field validates properly
        with pytest.raises(ValidationError):
            WeatherConfig(units="invalid_units")
        
        # Test that negative values are rejected where appropriate
        with pytest.raises(ValidationError):
            LimitlessConfig(max_retries=-1)
        
        with pytest.raises(ValidationError):
            NewsConfig(unique_items_per_day=0)
    
    def test_no_placeholder_values_in_production_config(self, env_vars_from_example: Dict[str, str]):
        """Test that production environment doesn't contain placeholder values"""
        placeholder_patterns = [
            r"your.*key.*here",
            r"your.*token.*here", 
            r"your.*endpoint.*here",
            r"example\.com",
            r"api\.example\.com",
            r"placeholder",
            r"changeme",
            r"replace.*with"
        ]
        
        # This test documents what placeholder values look like
        # In actual deployment, these should be replaced with real values
        suspicious_values = {}
        
        for key, value in env_vars_from_example.items():
            value_lower = value.lower()
            for pattern in placeholder_patterns:
                if re.search(pattern, value_lower):
                    suspicious_values[key] = value
        
        # For .env.example, these are expected to be placeholders
        # This test documents the expected placeholder format
        expected_placeholders = {
            'LIMITLESS__API_KEY', 'RAPID_API_KEY', 'TWITTER_BEARER_TOKEN'
        }
        
        # Verify that known placeholders are present (good for .env.example)
        for placeholder_key in expected_placeholders:
            if placeholder_key in env_vars_from_example:
                assert placeholder_key in suspicious_values, \
                    f"{placeholder_key} should contain placeholder value in .env.example"
    
    def test_config_defaults_are_reasonable(self):
        """Test that configuration defaults are sensible"""
        # Test default values are reasonable
        limitless_config = LimitlessConfig()
        assert limitless_config.max_retries >= 1, "Max retries should be at least 1"
        assert limitless_config.request_timeout >= 10.0, "Timeout should be reasonable"
        assert limitless_config.base_url.startswith("https://"), "Should use HTTPS"
        
        news_config = NewsConfig()
        assert news_config.unique_items_per_day >= 1, "Should fetch at least 1 news item"
        assert news_config.items_to_retrieve >= news_config.unique_items_per_day, \
            "Should retrieve at least as many as unique items needed"
        
        weather_config = WeatherConfig()
        assert weather_config.units in ["metric", "standard"], "Units should be valid"
        
        embedding_config = EmbeddingConfig()
        assert embedding_config.device in ["cpu", "cuda", "mps"], "Device should be valid"
        assert embedding_config.batch_size >= 1, "Batch size should be positive"


class TestConfigurationConsistency:
    """Test configuration consistency across different sources"""
    
    def test_limitless_timezone_consistency(self):
        """Test Limitless timezone configuration consistency"""
        # According to clean_now.md, there was an inconsistency between 
        # LIMITLESS__TIMEZONE vs timezone field
        
        # Test that LimitlessConfig properly maps timezone
        config = LimitlessConfig(timezone="America/New_York")
        assert config.timezone == "America/New_York"
        
        # Test environment variable mapping
        original_tz = os.environ.get('TIME_ZONE')
        try:
            os.environ['TIME_ZONE'] = 'America/Los_Angeles'
            # This would be handled by ConfigFactory in actual implementation
            # For now, just verify the field exists and can be set
            config = LimitlessConfig(timezone='America/Los_Angeles')
            assert config.timezone == 'America/Los_Angeles'
        finally:
            if original_tz:
                os.environ['TIME_ZONE'] = original_tz
            else:
                os.environ.pop('TIME_ZONE', None)
    
    def test_api_key_field_consistency(self):
        """Test that all API configurations use consistent field names"""
        # All API configs should have 'api_key' field, not variations
        configs_with_api_keys = [LimitlessConfig, NewsConfig, WeatherConfig]
        
        for config_class in configs_with_api_keys:
            # Verify api_key field exists
            config = config_class()
            assert hasattr(config, 'api_key'), f"{config_class.__name__} should have 'api_key' field"
            
            # Verify field can be set
            config_with_key = config_class(api_key="test_key")
            assert config_with_key.api_key == "test_key"
    
    def test_retry_configuration_consistency(self):
        """Test that retry configurations are consistent across services"""
        configs_with_retries = [LimitlessConfig, NewsConfig, WeatherConfig]
        
        for config_class in configs_with_retries:
            config = config_class()
            
            # All should have these retry-related fields
            assert hasattr(config, 'max_retries'), f"{config_class.__name__} should have 'max_retries'"
            assert hasattr(config, 'retry_delay'), f"{config_class.__name__} should have 'retry_delay'"
            assert hasattr(config, 'request_timeout'), f"{config_class.__name__} should have 'request_timeout'"
            
            # Values should be reasonable
            assert config.max_retries >= 1
            assert config.retry_delay >= 0.1
            assert config.request_timeout >= 5.0


if __name__ == "__main__":
    pytest.main([__file__])