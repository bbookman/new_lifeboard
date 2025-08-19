import pytest
from config.models import TwitterConfig
from pydantic import ValidationError

class TestTwitterConfig:
    """Test TwitterConfig validation and API configuration"""

    def test_default_config(self):
        """Test default TwitterConfig values"""
        config = TwitterConfig()
        
        assert config.enabled is True
        assert config.sync_interval_hours == 24
        assert config.delete_after_import is False
        assert config.bearer_token is None
        assert config.username is None
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.request_timeout == 30.0

    def test_basic_configuration(self):
        """Test basic Twitter configuration without API"""
        config = TwitterConfig(enabled=True)
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_both_present(self):
        """Test API configuration with both token and username"""
        config = TwitterConfig(
            bearer_token="valid_bearer_token_123",
            username="testuser"
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is True

    def test_api_configuration_missing_token(self):
        """Test API configuration with missing token"""
        config = TwitterConfig(
            bearer_token=None,
            username="testuser"
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_missing_username(self):
        """Test API configuration with missing username"""
        config = TwitterConfig(
            bearer_token="valid_bearer_token_123",
            username=None
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_empty_token(self):
        """Test API configuration with empty token"""
        config = TwitterConfig(
            bearer_token="",
            username="testuser"
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_empty_username(self):
        """Test API configuration with empty username"""
        config = TwitterConfig(
            bearer_token="valid_bearer_token_123",
            username=""
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_placeholder_token(self):
        """Test API configuration with placeholder token"""
        config = TwitterConfig(
            bearer_token="your token here",
            username="testuser"
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_placeholder_username(self):
        """Test API configuration with placeholder username"""
        config = TwitterConfig(
            bearer_token="valid_bearer_token_123",
            username="your user name"
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_api_configuration_whitespace_only(self):
        """Test API configuration with whitespace-only values"""
        config = TwitterConfig(
            bearer_token="   ",
            username="   "
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is False

    def test_disabled_configuration(self):
        """Test disabled Twitter configuration"""
        config = TwitterConfig(
            enabled=False,
            bearer_token="valid_bearer_token_123",
            username="testuser"
        )
        
        assert config.is_configured() is False
        assert config.is_api_configured() is True  # API can still be configured even if disabled

    def test_validation_positive_integers(self):
        """Test validation of positive integer fields"""
        # Valid values
        config = TwitterConfig(
            max_retries=5,
            sync_interval_hours=12
        )
        assert config.max_retries == 5
        assert config.sync_interval_hours == 12

        # Invalid values should raise ValidationError
        with pytest.raises(ValidationError):
            TwitterConfig(max_retries=-1)
        
        with pytest.raises(ValidationError):
            TwitterConfig(max_retries=0)
        
        with pytest.raises(ValidationError):
            TwitterConfig(sync_interval_hours=-5)

    def test_validation_positive_floats(self):
        """Test validation of positive float fields"""
        # Valid values
        config = TwitterConfig(
            retry_delay=2.5,
            request_timeout=45.0
        )
        assert config.retry_delay == 2.5
        assert config.request_timeout == 45.0

        # Invalid values should raise ValidationError
        with pytest.raises(ValidationError):
            TwitterConfig(retry_delay=-1.0)
        
        with pytest.raises(ValidationError):
            TwitterConfig(retry_delay=0.0)
        
        with pytest.raises(ValidationError):
            TwitterConfig(request_timeout=-10.0)

    def test_username_validation_empty_string(self):
        """Test username validation with empty string"""
        # Empty string should be allowed and not raise an error
        config = TwitterConfig(username="")
        assert config.username == ""
        assert config.is_api_configured() is False

    def test_comprehensive_valid_config(self):
        """Test comprehensive valid API configuration"""
        config = TwitterConfig(
            enabled=True,
            sync_interval_hours=6,
            delete_after_import=True,
            bearer_token="AAAAAAAAAAAAAAAAAAAAAP%2BhFwEAAAAAIzF4lAntZyU0w6J2kq%2B9Kg3kJWw%3DRb6TrPaTU8M8qg7YGwJWxSMm9YrLq4y5F3P6YfkM2g8WnX",
            username="realuser123",
            max_retries=5,
            retry_delay=2.0,
            request_timeout=60.0
        )
        
        assert config.is_configured() is True
        assert config.is_api_configured() is True
        assert config.enabled is True
        assert config.sync_interval_hours == 6
        assert config.delete_after_import is True
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.request_timeout == 60.0