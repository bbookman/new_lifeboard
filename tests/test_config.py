"""
Tests for configuration models and factory
"""

import pytest
import tempfile
from pathlib import Path
import os
from pydantic import ValidationError

from config.models import (
    AppConfig, DatabaseConfig, EmbeddingConfig, VectorStoreConfig,
    LLMConfig, LimitlessConfig, SearchConfig, SchedulerConfig
)
from config.factory import create_test_config, create_production_config


class TestDatabaseConfig:
    """Test database configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = DatabaseConfig()
        assert config.path == "lifeboard.db"
    
    def test_custom_path(self):
        """Test custom database path"""
        config = DatabaseConfig(path="/custom/path/db.sqlite")
        assert config.path == "/custom/path/db.sqlite"
    
    def test_invalid_path(self):
        """Test validation with invalid path"""
        with pytest.raises(ValidationError):
            DatabaseConfig(path="")
        
        with pytest.raises(ValidationError):
            DatabaseConfig(path=None)


class TestEmbeddingConfig:
    """Test embedding configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = EmbeddingConfig()
        assert config.model_name == "all-MiniLM-L6-v2"
        assert config.device == "cpu"
        assert config.batch_size == 32
    
    def test_valid_devices(self):
        """Test valid device configurations"""
        for device in ["cpu", "cuda", "mps"]:
            config = EmbeddingConfig(device=device)
            assert config.device == device
    
    def test_invalid_device(self):
        """Test invalid device validation"""
        with pytest.raises(ValidationError):
            EmbeddingConfig(device="invalid")


class TestVectorStoreConfig:
    """Test vector store configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = VectorStoreConfig()
        assert config.index_path == "vector_index.faiss"
        assert config.id_map_path == "vector_ids.json"
        assert config.dimension == 384
    
    def test_invalid_paths(self):
        """Test validation with invalid paths"""
        with pytest.raises(ValidationError):
            VectorStoreConfig(index_path="")
        
        with pytest.raises(ValidationError):
            VectorStoreConfig(id_map_path=None)


class TestLLMConfig:
    """Test LLM configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-3.5-turbo"
        assert config.api_key is None
        assert config.max_tokens == 1000
        assert config.temperature == 0.7
    
    def test_valid_providers(self):
        """Test valid provider configurations"""
        for provider in ["openai", "anthropic", "mock"]:
            config = LLMConfig(provider=provider)
            assert config.provider == provider
    
    def test_invalid_provider(self):
        """Test invalid provider validation"""
        with pytest.raises(ValidationError):
            LLMConfig(provider="invalid")
    
    def test_api_key_validation(self):
        """Test API key validation"""
        config = LLMConfig(api_key="valid-key")
        assert config.api_key == "valid-key"
        
        config = LLMConfig(api_key=None)
        assert config.api_key is None
        
        with pytest.raises(ValidationError):
            LLMConfig(api_key=123)


class TestLimitlessConfig:
    """Test Limitless configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = LimitlessConfig()
        assert config.api_key is None
        assert config.base_url == "https://api.limitless.ai"
        assert config.timezone == "UTC"
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.request_timeout == 30.0
        assert config.sync_interval_hours == 6
    
    def test_custom_values(self):
        """Test custom configuration values"""
        config = LimitlessConfig(
            api_key="test-key",
            base_url="https://custom.api.com",
            timezone="America/New_York",
            max_retries=5,
            retry_delay=2.0,
            request_timeout=60.0,
            sync_interval_hours=12
        )
        assert config.api_key == "test-key"
        assert config.base_url == "https://custom.api.com"
        assert config.timezone == "America/New_York"
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.request_timeout == 60.0
        assert config.sync_interval_hours == 12
    
    def test_api_key_validation(self):
        """Test API key validation"""
        config = LimitlessConfig(api_key="valid-key")
        assert config.api_key == "valid-key"
        
        config = LimitlessConfig(api_key=None)
        assert config.api_key is None
        
        with pytest.raises(ValidationError):
            LimitlessConfig(api_key=123)


class TestSearchConfig:
    """Test search configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = SearchConfig()
        assert config.default_limit == 20
        assert config.max_limit == 100
        assert config.similarity_threshold == 0.7
        assert config.max_top_k == 50
    
    def test_max_top_k_validation(self):
        """Test max_top_k validation"""
        config = SearchConfig(max_top_k=10)
        assert config.max_top_k == 10
        
        with pytest.raises(ValidationError):
            SearchConfig(max_top_k=0)
        
        with pytest.raises(ValidationError):
            SearchConfig(max_top_k=-1)


class TestAppConfig:
    """Test main app configuration"""
    
    def test_default_values(self):
        """Test default configuration composition"""
        config = AppConfig()
        
        # Check nested configs are properly initialized
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.embeddings, EmbeddingConfig)
        assert isinstance(config.vector_store, VectorStoreConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.limitless, LimitlessConfig)
        assert isinstance(config.search, SearchConfig)
        assert isinstance(config.scheduler, SchedulerConfig)
        
        # Check global settings
        assert config.debug is False
        assert config.log_level == "INFO"
    
    def test_log_level_validation(self):
        """Test log level validation"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in valid_levels:
            config = AppConfig(log_level=level)
            assert config.log_level == level
        
        with pytest.raises(ValidationError):
            AppConfig(log_level="INVALID")


class TestConfigFactory:
    """Test configuration factory functions"""
    
    def test_create_test_config(self):
        """Test test configuration creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = create_test_config(temp_dir)
            
            # Verify it's an AppConfig instance
            assert isinstance(config, AppConfig)
            
            # Check test-specific values
            assert config.debug is True
            assert config.log_level == "DEBUG"
            assert config.llm.provider == "mock"
            assert config.limitless.api_key == "test-limitless-key"
            assert config.limitless.retry_delay == 0.1  # Fast for tests
            
            # Check paths are in temp directory
            assert temp_dir in config.database.path
            assert temp_dir in config.vector_store.index_path
    
    def test_create_test_config_default_temp_dir(self):
        """Test test configuration with default temp directory"""
        config = create_test_config()
        assert isinstance(config, AppConfig)
        assert config.debug is True
    
    def test_create_production_config_defaults(self):
        """Test production configuration with default environment"""
        # Clear any existing environment variables
        env_vars = [
            "LIFEBOARD_DB_PATH", "EMBEDDING_MODEL", "LLM_PROVIDER",
            "LIMITLESS_API_KEY", "DEBUG", "LOG_LEVEL"
        ]
        
        original_values = {}
        for var in env_vars:
            original_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]
        
        try:
            config = create_production_config()
            
            # Check default values are used
            assert config.database.path == "lifeboard.db"
            assert config.embeddings.model_name == "all-MiniLM-L6-v2"
            assert config.llm.provider == "openai"
            assert config.limitless.api_key is None
            assert config.debug is False
            assert config.log_level == "INFO"
            
        finally:
            # Restore original environment
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value
    
    def test_create_production_config_with_env_vars(self):
        """Test production configuration with environment variables"""
        env_vars = {
            "LIFEBOARD_DB_PATH": "/custom/db.sqlite",
            "EMBEDDING_MODEL": "custom-model",
            "LLM_PROVIDER": "anthropic",
            "LIMITLESS_API_KEY": "real-key",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG"
        }
        
        # Set environment variables
        original_values = {}
        for var, value in env_vars.items():
            original_values[var] = os.environ.get(var)
            os.environ[var] = value
        
        try:
            config = create_production_config()
            
            # Check environment values are used
            assert config.database.path == "/custom/db.sqlite"
            assert config.embeddings.model_name == "custom-model"
            assert config.llm.provider == "anthropic"
            assert config.limitless.api_key == "real-key"
            assert config.debug is True
            assert config.log_level == "DEBUG"
            
        finally:
            # Restore original environment
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]


class TestConfigIntegration:
    """Test configuration integration scenarios"""
    
    def test_limitless_config_in_app_config(self):
        """Test Limitless config integration in app config"""
        app_config = AppConfig(
            limitless=LimitlessConfig(
                api_key="integration-test-key",
                timezone="America/Los_Angeles",
                sync_interval_hours=2
            )
        )
        
        assert app_config.limitless.api_key == "integration-test-key"
        assert app_config.limitless.timezone == "America/Los_Angeles"
        assert app_config.limitless.sync_interval_hours == 2
    
    def test_config_serialization(self):
        """Test configuration can be serialized/deserialized"""
        original_config = AppConfig(
            limitless=LimitlessConfig(api_key="test-key", timezone="UTC"),
            debug=True
        )
        
        # Convert to dict and back
        config_dict = original_config.model_dump()
        restored_config = AppConfig(**config_dict)
        
        assert restored_config.limitless.api_key == "test-key"
        assert restored_config.limitless.timezone == "UTC"
        assert restored_config.debug is True