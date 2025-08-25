"""
Unit tests for TwitterConfig archive-only mode support.

Tests the configuration changes that enable Twitter archive imports 
without requiring API credentials.
"""

import pytest
from config.models import TwitterConfig


class TestTwitterConfigArchiveMode:
    """Test TwitterConfig support for archive-only imports."""

    def test_twitter_config_archive_only_enabled(self):
        """Test that Twitter config allows archive imports without API credentials."""
        config = TwitterConfig(
            enabled=True,
            bearer_token=None,
            username=None,
            sync_interval_hours=24
        )
        
        # Should be configured for archive imports
        assert config.enabled is True
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_twitter_config_disabled_completely(self):
        """Test that disabled Twitter config blocks all operations."""
        config = TwitterConfig(
            enabled=False,  # Completely disabled
            bearer_token="valid_token",
            username="valid_user",
            sync_interval_hours=24
        )
        
        # Should not be configured for any operations
        assert config.enabled is False
        assert config.is_configured() is False
        assert config.is_api_configured() is True  # API creds are valid but service disabled

    def test_twitter_config_api_enabled(self):
        """Test Twitter config with full API credentials."""
        config = TwitterConfig(
            enabled=True,
            bearer_token="valid_bearer_token_123",
            username="testuser",
            sync_interval_hours=24
        )
        
        # Should be configured for both archive and API operations
        assert config.enabled is True
        assert config.is_configured() is True
        assert config.is_api_configured() is True

    def test_twitter_config_invalid_api_credentials(self):
        """Test Twitter config with invalid API credentials."""
        # Test with placeholder bearer token
        config1 = TwitterConfig(
            enabled=True,
            bearer_token="your token here",  # Placeholder
            username="testuser",
            sync_interval_hours=24
        )
        
        assert config1.is_configured() is True  # Archive imports still work
        assert config1.is_api_configured() is False  # API creds invalid

        # Test with placeholder username
        config2 = TwitterConfig(
            enabled=True,
            bearer_token="valid_token",
            username="your user name",  # Placeholder
            sync_interval_hours=24
        )
        
        assert config2.is_configured() is True  # Archive imports still work
        assert config2.is_api_configured() is False  # API creds invalid

        # Test with None values
        config3 = TwitterConfig(
            enabled=True,
            bearer_token=None,
            username=None,
            sync_interval_hours=24
        )
        
        assert config3.is_configured() is True  # Archive imports still work
        assert config3.is_api_configured() is False  # No API creds

    def test_twitter_config_backward_compatibility(self):
        """Test that the config changes maintain backward compatibility."""
        # Old behavior: would require API credentials
        # New behavior: only requires enabled=True for archive imports
        
        # This configuration would have failed before the fix
        config = TwitterConfig(
            enabled=True,
            # No API credentials provided
        )
        
        # Should now work for archive imports
        assert config.is_configured() is True
        
        # But API operations should still fail appropriately
        assert config.is_api_configured() is False

    def test_twitter_config_validation_logic(self):
        """Test the internal validation logic for API credentials."""
        config = TwitterConfig(
            enabled=True,
            bearer_token="AAAAAAAAAAAAAAAAAAAAALTi4wAAAAAAQqg9nPRULQic%2BWNFthrJho5EaXE%3DgVbmsFLT38q1xf439154OYmVbvKntuMrblGg2TCD5CsQWPMry9",
            username="realuser123",
            sync_interval_hours=24
        )
        
        # Test individual validation components
        assert config.enabled is True
        
        # API key validation
        assert config.bearer_token is not None
        assert config.bearer_token.strip() != ""
        assert config.bearer_token not in {"your token here", "your-token-here", "twitter_bearer_token_here"}
        
        # Username validation  
        assert config.username is not None
        assert config.username.strip() != ""
        assert config.username != "your user name"
        
        # Combined API validation
        assert config.is_api_configured() is True

    def test_twitter_config_edge_cases(self):
        """Test edge cases in Twitter configuration."""
        # Empty string bearer token
        config1 = TwitterConfig(
            enabled=True,
            bearer_token="",  # Empty string
            username="validuser",
            sync_interval_hours=24
        )
        assert config1.is_configured() is True
        assert config1.is_api_configured() is False

        # Whitespace-only bearer token
        config2 = TwitterConfig(
            enabled=True,
            bearer_token="   ",  # Whitespace only
            username="validuser", 
            sync_interval_hours=24
        )
        assert config2.is_configured() is True
        assert config2.is_api_configured() is False

        # Empty string username
        config3 = TwitterConfig(
            enabled=True,
            bearer_token="valid_token",
            username="",  # Empty string
            sync_interval_hours=24
        )
        assert config3.is_configured() is True
        assert config3.is_api_configured() is False

    def test_twitter_config_default_values(self):
        """Test that default configuration values work correctly."""
        config = TwitterConfig()  # Use all defaults
        
        # Check defaults
        assert config.enabled is True
        assert config.bearer_token is None
        assert config.username is None
        assert config.sync_interval_hours == 24
        assert config.delete_after_import is False
        
        # Should be configured for archive imports with defaults
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_configuration_change_impact(self):
        """Test that the configuration change achieves the intended impact."""
        # Before: is_configured() required is_api_configured()
        # After: is_configured() only requires enabled=True
        
        # This is the exact scenario that was failing before the fix
        config_from_env = TwitterConfig(
            enabled=True,  # From env: TWITTER_ENABLED=true (default)
            bearer_token=None,  # From env: TWITTER_BEARER_TOKEN not set
            username=None,  # From env: TWITTER_USER_NAME not set
            sync_interval_hours=24,
            delete_after_import=False
        )
        
        # This should now work (was failing before)
        assert config_from_env.is_configured() is True
        
        # API operations should still be blocked appropriately
        assert config_from_env.is_api_configured() is False
        
        # The TwitterSource should be able to register and handle archive imports
        from sources.twitter import TwitterSource
        from unittest.mock import MagicMock
        
        mock_db = MagicMock()
        mock_ingestion = MagicMock()
        
        # This should not raise an exception
        twitter_source = TwitterSource(config_from_env, mock_db, mock_ingestion)
        
        # The source should indicate it's properly configured for archives
        # (We can't test import_from_zip here without mocking extensively,
        # but the config should at least allow the source to be created)
        assert twitter_source.config.is_configured() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])