import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError

from config.models import SpotifyConfig


class TestSpotifyConfig:
    """Test suite for SpotifyConfig class"""

    def test_default_values(self):
        """Test that SpotifyConfig has correct default values"""
        config = SpotifyConfig()
        
        assert config.client_id is None
        assert config.client_secret is None
        assert config.redirect_uri == "http://localhost:8888/callback"
        assert config.enabled is True
        assert config.sync_interval_hours == 1
        assert config.recently_played_limit == 50
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.request_timeout == 30.0
        assert config.rate_limit_max_delay == 60
        assert config.respect_retry_after is True
        assert config.required_scopes == ["user-read-recently-played", "user-read-playback-state"]

    def test_valid_configuration(self):
        """Test creating SpotifyConfig with valid values"""
        config = SpotifyConfig(
            client_id="valid_client_id",
            client_secret="valid_client_secret",
            redirect_uri="http://localhost:3000/callback",
            enabled=True,
            sync_interval_hours=2,
            recently_played_limit=25,
            max_retries=5,
            retry_delay=2.0,
            request_timeout=45.0,
            rate_limit_max_delay=120,
            respect_retry_after=False,
            required_scopes=["user-read-recently-played"]
        )
        
        assert config.client_id == "valid_client_id"
        assert config.client_secret == "valid_client_secret"
        assert config.redirect_uri == "http://localhost:3000/callback"
        assert config.enabled is True
        assert config.sync_interval_hours == 2
        assert config.recently_played_limit == 25
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.request_timeout == 45.0
        assert config.rate_limit_max_delay == 120
        assert config.respect_retry_after is False
        assert config.required_scopes == ["user-read-recently-played"]

    def test_client_id_validation(self):
        """Test client_id field validation"""
        # Valid client_id
        config = SpotifyConfig(client_id="valid_client_id")
        assert config.client_id == "valid_client_id"
        
        # None is allowed
        config = SpotifyConfig(client_id=None)
        assert config.client_id is None
        
        # Empty string should raise error
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(client_id="")
        assert "Client Id must be a non-empty string if provided" in str(exc_info.value)
        
        # Whitespace-only string should raise error
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(client_id="   ")
        assert "Client Id must be a non-empty string if provided" in str(exc_info.value)
        
        # Non-string should raise error
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(client_id=123)
        assert "Client Id must be a non-empty string if provided" in str(exc_info.value)

    def test_client_secret_validation(self):
        """Test client_secret field validation"""
        # Valid client_secret
        config = SpotifyConfig(client_secret="valid_client_secret")
        assert config.client_secret == "valid_client_secret"
        
        # None is allowed
        config = SpotifyConfig(client_secret=None)
        assert config.client_secret is None
        
        # Empty string should raise error
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(client_secret="")
        assert "Client Secret must be a non-empty string if provided" in str(exc_info.value)
        
        # Whitespace-only string should raise error
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(client_secret="   ")
        assert "Client Secret must be a non-empty string if provided" in str(exc_info.value)
        
        # Non-string should raise error
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(client_secret=123)
        assert "Client Secret must be a non-empty string if provided" in str(exc_info.value)

    def test_sync_interval_hours_validation(self):
        """Test sync_interval_hours field validation"""
        # Valid values
        for hours in [1, 12, 24]:
            config = SpotifyConfig(sync_interval_hours=hours)
            assert config.sync_interval_hours == hours
        
        # Invalid values - too low
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(sync_interval_hours=0)
        assert "sync_interval_hours must be between 1 and 24" in str(exc_info.value)
        
        # Invalid values - too high
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(sync_interval_hours=25)
        assert "sync_interval_hours must be between 1 and 24" in str(exc_info.value)
        
        # Invalid type
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(sync_interval_hours="invalid")
        assert "sync_interval_hours must be between 1 and 24" in str(exc_info.value)

    def test_recently_played_limit_validation(self):
        """Test recently_played_limit field validation"""
        # Valid values
        for limit in [1, 25, 50]:
            config = SpotifyConfig(recently_played_limit=limit)
            assert config.recently_played_limit == limit
        
        # Invalid values - too low
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(recently_played_limit=0)
        assert "recently_played_limit must be between 1 and 50" in str(exc_info.value)
        
        # Invalid values - too high
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(recently_played_limit=51)
        assert "recently_played_limit must be between 1 and 50" in str(exc_info.value)
        
        # Invalid type
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(recently_played_limit="invalid")
        assert "recently_played_limit must be between 1 and 50" in str(exc_info.value)

    def test_request_timeout_validation(self):
        """Test request_timeout field validation"""
        # Valid values
        for timeout in [1.0, 30.0, 60.5]:
            config = SpotifyConfig(request_timeout=timeout)
            assert config.request_timeout == timeout
        
        # Valid integer
        config = SpotifyConfig(request_timeout=30)
        assert config.request_timeout == 30
        
        # Invalid values - zero
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(request_timeout=0)
        assert "request_timeout must be positive" in str(exc_info.value)
        
        # Invalid values - negative
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(request_timeout=-1.0)
        assert "request_timeout must be positive" in str(exc_info.value)
        
        # Invalid type
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(request_timeout="invalid")
        assert "request_timeout must be positive" in str(exc_info.value)

    def test_max_retries_validation(self):
        """Test max_retries field validation using NumericValidator"""
        # Valid values
        for retries in [1, 3, 10]:
            config = SpotifyConfig(max_retries=retries)
            assert config.max_retries == retries
        
        # Invalid values - zero
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(max_retries=0)
        assert "Max Retries must be a positive integer" in str(exc_info.value)
        
        # Invalid values - negative
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(max_retries=-1)
        assert "Max Retries must be a positive integer" in str(exc_info.value)

    def test_rate_limit_max_delay_validation(self):
        """Test rate_limit_max_delay field validation using NumericValidator"""
        # Valid values
        for delay in [30, 60, 300]:
            config = SpotifyConfig(rate_limit_max_delay=delay)
            assert config.rate_limit_max_delay == delay
        
        # Invalid values - zero
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(rate_limit_max_delay=0)
        assert "Rate Limit Max Delay must be a positive integer" in str(exc_info.value)
        
        # Invalid values - negative
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(rate_limit_max_delay=-1)
        assert "Rate Limit Max Delay must be a positive integer" in str(exc_info.value)

    def test_retry_delay_validation(self):
        """Test retry_delay field validation using NumericValidator"""
        # Valid values
        for delay in [0.5, 1.0, 2.5]:
            config = SpotifyConfig(retry_delay=delay)
            assert config.retry_delay == delay
        
        # Invalid values - zero
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(retry_delay=0)
        assert "Retry Delay must be a positive number" in str(exc_info.value)
        
        # Invalid values - negative
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(retry_delay=-1.0)
        assert "Retry Delay must be a positive number" in str(exc_info.value)

    def test_is_api_configured_method(self):
        """Test is_api_configured method"""
        # Both client_id and client_secret provided
        config = SpotifyConfig(
            client_id="valid_client_id",
            client_secret="valid_client_secret"
        )
        assert config.is_api_configured() is True
        
        # Only client_id provided
        config = SpotifyConfig(client_id="valid_client_id")
        assert config.is_api_configured() is False
        
        # Only client_secret provided
        config = SpotifyConfig(client_secret="valid_client_secret")
        assert config.is_api_configured() is False
        
        # Neither provided (None values)
        config = SpotifyConfig()
        assert config.is_api_configured() is False
        
        # Empty strings (should be caught by validation, but test the method)
        config = SpotifyConfig()
        config.client_id = ""
        config.client_secret = "valid_secret"
        assert config.is_api_configured() is False
        
        config.client_id = "valid_id"
        config.client_secret = ""
        assert config.is_api_configured() is False

    def test_is_fully_configured_method(self):
        """Test is_fully_configured method"""
        # Enabled and API configured
        config = SpotifyConfig(
            enabled=True,
            client_id="valid_client_id",
            client_secret="valid_client_secret"
        )
        assert config.is_fully_configured() is True
        
        # Disabled but API configured
        config = SpotifyConfig(
            enabled=False,
            client_id="valid_client_id",
            client_secret="valid_client_secret"
        )
        assert config.is_fully_configured() is False
        
        # Enabled but API not configured
        config = SpotifyConfig(enabled=True)
        assert config.is_fully_configured() is False
        
        # Disabled and API not configured
        config = SpotifyConfig(enabled=False)
        assert config.is_fully_configured() is False

    def test_oauth_scope_validation(self):
        """Test OAuth scope requirements"""
        # Default scopes
        config = SpotifyConfig()
        assert "user-read-recently-played" in config.required_scopes
        assert "user-read-playback-state" in config.required_scopes
        
        # Custom scopes
        custom_scopes = ["user-read-recently-played", "user-modify-playback-state"]
        config = SpotifyConfig(required_scopes=custom_scopes)
        assert config.required_scopes == custom_scopes
        
        # Empty scopes list
        config = SpotifyConfig(required_scopes=[])
        assert config.required_scopes == []

    @patch.dict(os.environ, {
        "SPOTIFY_CLIENT_ID": "env_client_id",
        "SPOTIFY_CLIENT_SECRET": "env_client_secret",
        "SPOTIFY_REDIRECT_URI": "http://localhost:9000/callback",
        "SPOTIFY_ENABLED": "false",
        "SPOTIFY_SYNC_INTERVAL_HOURS": "6",
        "SPOTIFY_RECENTLY_PLAYED_LIMIT": "30",
        "SPOTIFY_MAX_RETRIES": "5",
        "SPOTIFY_RETRY_DELAY": "2.5",
        "SPOTIFY_REQUEST_TIMEOUT": "45.0",
        "SPOTIFY_RATE_LIMIT_MAX_DELAY": "120",
        "SPOTIFY_RESPECT_RETRY_AFTER": "false"
    })
    def test_environment_variable_loading(self):
        """Test that SpotifyConfig loads values from environment variables"""
        # Note: This test assumes the config uses pydantic's env loading
        # Since SpotifyConfig doesn't explicitly define env vars, this tests the pattern
        config = SpotifyConfig()
        
        # Test that default values are used when env vars don't match field names
        assert config.client_id is None  # No env var matching
        assert config.client_secret is None  # No env var matching
        assert config.redirect_uri == "http://localhost:8888/callback"  # Default
        assert config.enabled is True  # Default
        assert config.sync_interval_hours == 1  # Default

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Minimum valid sync_interval_hours
        config = SpotifyConfig(sync_interval_hours=1)
        assert config.sync_interval_hours == 1
        
        # Maximum valid sync_interval_hours
        config = SpotifyConfig(sync_interval_hours=24)
        assert config.sync_interval_hours == 24
        
        # Minimum valid recently_played_limit
        config = SpotifyConfig(recently_played_limit=1)
        assert config.recently_played_limit == 1
        
        # Maximum valid recently_played_limit
        config = SpotifyConfig(recently_played_limit=50)
        assert config.recently_played_limit == 50
        
        # Very small positive timeout
        config = SpotifyConfig(request_timeout=0.1)
        assert config.request_timeout == 0.1

    def test_string_trimming(self):
        """Test that string fields are properly trimmed"""
        config = SpotifyConfig(
            client_id="  trimmed_id  ",
            client_secret="  trimmed_secret  "
        )
        assert config.client_id == "trimmed_id"
        assert config.client_secret == "trimmed_secret"

    def test_configuration_scenarios(self):
        """Test various real-world configuration scenarios"""
        # Development configuration
        dev_config = SpotifyConfig(
            client_id="dev_client_id",
            client_secret="dev_client_secret",
            redirect_uri="http://localhost:3000/callback",
            sync_interval_hours=1,
            recently_played_limit=20
        )
        assert dev_config.is_fully_configured() is True
        
        # Production configuration
        prod_config = SpotifyConfig(
            client_id="prod_client_id",
            client_secret="prod_client_secret",
            redirect_uri="https://myapp.com/spotify/callback",
            sync_interval_hours=6,
            recently_played_limit=50,
            max_retries=5,
            request_timeout=60.0
        )
        assert prod_config.is_fully_configured() is True
        
        # Disabled configuration
        disabled_config = SpotifyConfig(enabled=False)
        assert disabled_config.is_fully_configured() is False
        
        # Partially configured (missing secret)
        partial_config = SpotifyConfig(client_id="only_id")
        assert partial_config.is_api_configured() is False
        assert partial_config.is_fully_configured() is False

    def test_invalid_combinations(self):
        """Test invalid field combinations"""
        # Test multiple validation errors at once
        with pytest.raises(ValidationError) as exc_info:
            SpotifyConfig(
                client_id="",  # Empty string
                sync_interval_hours=0,  # Too low
                recently_played_limit=100,  # Too high
                request_timeout=-1  # Negative
            )
        
        # Should have multiple validation errors
        errors = exc_info.value.errors()
        assert len(errors) >= 4  # At least 4 validation errors
        
        # Check that all expected error types are present
        error_messages = [error['msg'] for error in errors]
        assert any("Client Id must be a non-empty string" in msg for msg in error_messages)
        assert any("sync_interval_hours must be between 1 and 24" in msg for msg in error_messages)
        assert any("recently_played_limit must be between 1 and 50" in msg for msg in error_messages)
        assert any("request_timeout must be positive" in msg for msg in error_messages)