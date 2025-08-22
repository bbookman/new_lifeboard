"""
Centralized configuration fixtures for testing.

This module provides shared configuration builders for all services,
eliminating duplication across test files and ensuring consistency.
"""


import pytest

from config.models import (
    AppConfig,
    DatabaseConfig,
    EmbeddingConfig,
    LimitlessConfig,
    LLMProviderConfig,
    NewsConfig,
    OllamaConfig,
    OpenAIConfig,
    WeatherConfig,
)

# Base test configuration values
BASE_TEST_CONFIG = {
    "max_retries": 2,
    "retry_delay": 0.1,  # Fast retries for testing
    "request_timeout": 5.0,
    "sync_interval_hours": 24,
}


@pytest.fixture
def base_test_config():
    """Base test configuration with common test values"""
    return BASE_TEST_CONFIG.copy()


@pytest.fixture
def test_api_keys():
    """Standard test API keys"""
    return {
        "limitless": "test_limitless_api_key",
        "news": "test_rapid_api_key",
        "weather": "test_weather_api_key",
        "openai": "test_openai_api_key",
    }


# Configuration Builders

@pytest.fixture
def limitless_config(base_test_config, test_api_keys):
    """Test Limitless configuration with standard test values"""
    return LimitlessConfig(
        api_key=test_api_keys["limitless"],
        base_url="https://api.limitless.ai",
        timezone="America/Los_Angeles",
        max_retries=base_test_config["max_retries"],
        retry_delay=base_test_config["retry_delay"],
        request_timeout=base_test_config["request_timeout"],
    )


@pytest.fixture
def news_config(base_test_config, test_api_keys):
    """Test News configuration with standard test values"""
    return NewsConfig(
        api_key=test_api_keys["news"],
        language="en",
        enabled=True,
        country="US",
        unique_items_per_day=5,
        endpoint="real-time-news-data.p.rapidapi.com",
        items_to_retrieve=20,
        max_retries=base_test_config["max_retries"],
        retry_delay=base_test_config["retry_delay"],
        request_timeout=base_test_config["request_timeout"],
        sync_interval_hours=base_test_config["sync_interval_hours"],
    )


@pytest.fixture
def weather_config(base_test_config, test_api_keys):
    """Test Weather configuration with standard test values"""
    return WeatherConfig(
        api_key=test_api_keys["weather"],
        location="San Francisco, CA",
        enabled=True,
        endpoint="easy-weather1.p.rapidapi.com/daily/5",
        max_retries=base_test_config["max_retries"],
        retry_delay=base_test_config["retry_delay"],
        request_timeout=base_test_config["request_timeout"],
        sync_interval_hours=base_test_config["sync_interval_hours"],
    )


@pytest.fixture
def database_config():
    """Test Database configuration"""
    return DatabaseConfig(
        database_path=":memory:",  # In-memory database for tests
        enable_wal_mode=False,  # Disable WAL for test simplicity
        connection_pool_size=1,  # Single connection for tests
        query_timeout=5.0,
        pragma_settings={
            "journal_mode": "MEMORY",
            "synchronous": "OFF",  # Faster for tests
            "temp_store": "MEMORY",
        },
    )


@pytest.fixture
def embedding_config():
    """Test Embedding configuration"""
    return EmbeddingConfig(
        model_name="all-MiniLM-L6-v2",  # Lightweight model for tests
        device="cpu",  # Force CPU for consistent test environment
        batch_size=16,
        max_sequence_length=256,  # Shorter for faster tests
        vector_dimension=384,
        cache_embeddings=False,  # Disable caching for tests
        embedding_service_timeout=10.0,
    )


@pytest.fixture
def llm_provider_config(test_api_keys):
    """Test LLM Provider configuration"""
    return LLMProviderConfig(
        openai=OpenAIConfig(
            api_key=test_api_keys["openai"],
            model="gpt-3.5-turbo",
            temperature=0.1,
            max_tokens=500,
            timeout=10.0,
        ),
        ollama=OllamaConfig(
            base_url="http://localhost:11434",
            model="llama2",
            timeout=10.0,
        ),
        provider="openai",
    )


@pytest.fixture
def app_config(
    limitless_config,
    news_config,
    weather_config,
    database_config,
    embedding_config,
    llm_provider_config,
):
    """Complete test application configuration"""
    return AppConfig(
        limitless=limitless_config,
        news=news_config,
        weather=weather_config,
        database=database_config,
        embedding=embedding_config,
        llm=llm_provider_config,
        debug=True,  # Enable debug mode for tests
        log_level="DEBUG",
        data_directory="test_data",
    )


# Configuration Variant Builders

class ConfigBuilder:
    """Builder class for creating configuration variants"""

    @staticmethod
    def limitless_config_with(**overrides) -> LimitlessConfig:
        """Create Limitless config with custom overrides"""
        defaults = {
            "api_key": "test_limitless_api_key",
            "base_url": "https://api.limitless.ai",
            "timezone": "America/Los_Angeles",
            "max_retries": 2,
            "retry_delay": 0.1,
            "request_timeout": 5.0,
        }
        defaults.update(overrides)
        return LimitlessConfig(**defaults)

    @staticmethod
    def news_config_with(**overrides) -> NewsConfig:
        """Create News config with custom overrides"""
        defaults = {
            "api_key": "test_rapid_api_key",
            "language": "en",
            "enabled": True,
            "country": "US",
            "unique_items_per_day": 5,
            "endpoint": "real-time-news-data.p.rapidapi.com",
            "items_to_retrieve": 20,
            "max_retries": 2,
            "retry_delay": 0.1,
            "request_timeout": 5.0,
            "sync_interval_hours": 24,
        }
        defaults.update(overrides)
        return NewsConfig(**defaults)

    @staticmethod
    def weather_config_with(**overrides) -> WeatherConfig:
        """Create Weather config with custom overrides"""
        defaults = {
            "api_key": "test_weather_api_key",
            "location": "San Francisco, CA",
            "enabled": True,
            "endpoint": "easy-weather1.p.rapidapi.com/daily/5",
            "max_retries": 2,
            "retry_delay": 0.1,
            "request_timeout": 5.0,
            "sync_interval_hours": 24,
        }
        defaults.update(overrides)
        return WeatherConfig(**defaults)

    @staticmethod
    def database_config_with(**overrides) -> DatabaseConfig:
        """Create Database config with custom overrides"""
        defaults = {
            "database_path": ":memory:",
            "enable_wal_mode": False,
            "connection_pool_size": 1,
            "query_timeout": 5.0,
            "pragma_settings": {
                "journal_mode": "MEMORY",
                "synchronous": "OFF",
                "temp_store": "MEMORY",
            },
        }
        defaults.update(overrides)
        return DatabaseConfig(**defaults)

    @staticmethod
    def embedding_config_with(**overrides) -> EmbeddingConfig:
        """Create Embedding config with custom overrides"""
        defaults = {
            "model_name": "all-MiniLM-L6-v2",
            "device": "cpu",
            "batch_size": 16,
            "max_sequence_length": 256,
            "vector_dimension": 384,
            "cache_embeddings": False,
            "embedding_service_timeout": 10.0,
        }
        defaults.update(overrides)
        return EmbeddingConfig(**defaults)

    @staticmethod
    def llm_provider_config_with(**overrides) -> LLMProviderConfig:
        """Create LLM Provider config with custom overrides"""
        defaults = {
            "openai": OpenAIConfig(
                api_key="test_openai_api_key",
                model="gpt-3.5-turbo",
                temperature=0.1,
                max_tokens=500,
                timeout=10.0,
            ),
            "ollama": OllamaConfig(
                base_url="http://localhost:11434",
                model="llama2",
                timeout=10.0,
            ),
            "provider": "openai",
        }
        defaults.update(overrides)
        return LLMProviderConfig(**defaults)


@pytest.fixture
def config_builder():
    """Fixture providing the ConfigBuilder class"""
    return ConfigBuilder


# Specialized Configuration Scenarios

@pytest.fixture
def disabled_limitless_config(limitless_config):
    """Limitless config with API disabled (for error testing)"""
    return ConfigBuilder.limitless_config_with(
        api_key="",  # Empty API key
        max_retries=0,  # No retries
    )


@pytest.fixture
def slow_network_config(base_test_config):
    """Configuration simulating slow network conditions"""
    return {
        **base_test_config,
        "request_timeout": 0.1,  # Very short timeout
        "retry_delay": 0.01,  # Minimal retry delay
        "max_retries": 1,  # Single retry only
    }


@pytest.fixture
def high_throughput_config(base_test_config):
    """Configuration for high throughput testing"""
    return {
        **base_test_config,
        "request_timeout": 30.0,  # Longer timeout
        "max_retries": 5,  # More retries
        "retry_delay": 0.5,  # Longer delay between retries
        "sync_interval_hours": 1,  # More frequent syncing
    }


@pytest.fixture
def minimal_config():
    """Minimal configuration for basic functionality tests"""
    return AppConfig(
        limitless=ConfigBuilder.limitless_config_with(),
        news=ConfigBuilder.news_config_with(enabled=False),
        weather=ConfigBuilder.weather_config_with(enabled=False),
        database=ConfigBuilder.database_config_with(),
        embedding=ConfigBuilder.embedding_config_with(),
        llm=ConfigBuilder.llm_config_with(),
        debug=True,
        log_level="ERROR",  # Minimal logging
        data_directory="test_data",
        max_concurrent_syncs=1,
        api_port=8000,
        enable_cors=False,
        session_timeout_minutes=5,
    )


# Export all commonly used fixtures
__all__ = [
    "ConfigBuilder",
    "app_config",
    "base_test_config",
    "config_builder",
    "database_config",
    "disabled_limitless_config",
    "embedding_config",
    "high_throughput_config",
    "limitless_config",
    "llm_provider_config",
    "minimal_config",
    "news_config",
    "slow_network_config",
    "test_api_keys",
    "weather_config",
]
