"""
Test cases for weather endpoint validation fix.

This test validates that when WEATHER_ENDPOINT is commented out or not provided,
the weather service correctly identifies the configuration as invalid and skips API calls.
"""
from unittest.mock import Mock

import pytest

from config.models import WeatherConfig
from core.database import DatabaseService
from sources.weather import WeatherSource


class TestWeatherEndpointValidation:
    """Test weather endpoint validation functionality"""

    def test_default_endpoint_not_considered_configured(self):
        """Test that default fallback endpoint is not considered as configured"""
        # Create config with default endpoint (what happens when WEATHER_ENDPOINT is commented out)
        config = WeatherConfig(
            api_key="test-api-key",
            endpoint="easy-weather1.p.rapidapi.com/daily/5",  # Default fallback value
            latitude="34.0522",
            longitude="-118.2437",
            units="metric",
            enabled=True,
        )

        # The endpoint should not be considered configured since it's the default
        assert not config.is_endpoint_configured()
        assert not config.is_fully_configured()

    def test_custom_endpoint_is_considered_configured(self):
        """Test that a custom endpoint is properly considered as configured"""
        config = WeatherConfig(
            api_key="test-api-key",
            endpoint="custom-weather-api.example.com/v1/forecast",  # Custom endpoint
            latitude="34.0522",
            longitude="-118.2437",
            units="metric",
            enabled=True,
        )

        # Custom endpoint should be considered configured
        assert config.is_endpoint_configured()
        assert config.is_fully_configured()

    def test_placeholder_endpoints_not_configured(self):
        """Test that placeholder endpoints are not considered configured"""
        placeholders = [
            "null",
            "none",
            "endpoint_here",
            "your_endpoint_here",
            "weather_endpoint_here",
            "example.com",
            "api.example.com",
            "easy-weather1.p.rapidapi.com/daily/5",  # Default fallback
        ]

        for placeholder in placeholders:
            config = WeatherConfig(
                api_key="test-api-key",
                endpoint=placeholder,
                latitude="34.0522",
                longitude="-118.2437",
                units="metric",
                enabled=True,
            )

            assert not config.is_endpoint_configured(), f"Placeholder '{placeholder}' should not be considered configured"
            assert not config.is_fully_configured(), f"Config with placeholder '{placeholder}' should not be fully configured"

    def test_empty_endpoint_not_configured(self):
        """Test that empty or whitespace endpoints are not considered configured"""
        empty_values = ["", "   ", "\t", "\n", None]

        for empty_value in empty_values:
            config = WeatherConfig(
                api_key="test-api-key",
                endpoint=empty_value,
                latitude="34.0522",
                longitude="-118.2437",
                units="metric",
                enabled=True,
            )

            assert not config.is_endpoint_configured(), f"Empty value '{empty_value}' should not be considered configured"
            assert not config.is_fully_configured(), f"Config with empty endpoint '{empty_value}' should not be fully configured"

    def test_missing_api_key_not_fully_configured(self):
        """Test that missing API key prevents full configuration"""
        config = WeatherConfig(
            api_key=None,  # Missing API key
            endpoint="custom-weather-api.example.com/v1/forecast",
            latitude="34.0522",
            longitude="-118.2437",
            units="metric",
            enabled=True,
        )

        # Endpoint is configured but API key is missing
        assert config.is_endpoint_configured()
        assert not config.is_fully_configured()

    @pytest.mark.asyncio
    async def test_weather_source_skips_fetch_with_default_endpoint(self):
        """Test that WeatherSource skips fetch when using default endpoint"""
        # Mock database service
        db_service = Mock(spec=DatabaseService)

        # Create config with default endpoint (simulates commented WEATHER_ENDPOINT)
        config = WeatherConfig(
            api_key="test-api-key",
            endpoint="easy-weather1.p.rapidapi.com/daily/5",  # Default fallback
            latitude="34.0522",
            longitude="-118.2437",
            units="metric",
            enabled=True,
        )

        # Create weather source
        weather_source = WeatherSource(config, db_service)

        # Collect items from fetch_items
        items = []
        async for item in weather_source.fetch_items():
            items.append(item)

        # Should return no items since endpoint is not properly configured
        assert len(items) == 0, "Weather source should not fetch items when endpoint is default fallback"

    @pytest.mark.asyncio
    async def test_weather_source_proceeds_with_custom_endpoint(self):
        """Test that WeatherSource would proceed with a custom endpoint (but still check API key)"""
        # Mock database service
        db_service = Mock(spec=DatabaseService)

        # Create config with custom endpoint
        config = WeatherConfig(
            api_key="test-api-key",
            endpoint="custom-weather-api.example.com/v1/forecast",  # Custom endpoint
            latitude="34.0522",
            longitude="-118.2437",
            units="metric",
            enabled=True,
        )

        # Create weather source
        weather_source = WeatherSource(config, db_service)

        # The source should pass endpoint validation but may still fail on other checks
        # This test just verifies that endpoint validation allows custom endpoints
        assert config.is_endpoint_configured()
        assert config.is_fully_configured()
