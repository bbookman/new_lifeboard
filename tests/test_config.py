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
    LimitlessConfig, SearchConfig, SchedulerConfig, LoggingConfig,
    LLMProviderConfig, OllamaConfig, OpenAIConfig, ChatConfig,
    InsightsConfig, EnhancementConfig
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
        assert isinstance(config.limitless, LimitlessConfig)
        assert isinstance(config.search, SearchConfig)
        assert isinstance(config.scheduler, SchedulerConfig)
        
        # Check global settings
        assert config.debug is False
        assert config.log_level == "INFO"
    
    def test_log_level_validation(self):
        """Test log level validation through logging config"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in valid_levels:
            config = AppConfig(logging=LoggingConfig(level=level))
            assert config.log_level == level
        
        with pytest.raises(ValidationError):
            AppConfig(logging=LoggingConfig(level="INVALID"))


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
        """Test production configuration loads successfully"""
        config = create_production_config()
        
        # Check that configuration loads and has expected structure
        assert isinstance(config, AppConfig)
        assert config.database.path is not None
        assert config.embeddings.model_name is not None
        assert config.debug is False
        # Note: limitless.api_key and log_level may be set from .env file
    
    def test_create_production_config_with_env_vars(self):
        """Test production configuration respects environment variables"""
        # Test specific environment variables that aren't in .env
        original_db_path = os.environ.get("LIFEBOARD_DB_PATH")
        original_embedding_model = os.environ.get("EMBEDDING_MODEL")
        
        try:
            # Set test values
            os.environ["LIFEBOARD_DB_PATH"] = "/custom/db.sqlite"
            os.environ["EMBEDDING_MODEL"] = "custom-model"
            
            config = create_production_config()
            
            # Check that environment variables override defaults
            assert config.database.path == "/custom/db.sqlite"
            assert config.embeddings.model_name == "custom-model"
            
        finally:
            # Restore original environment
            if original_db_path is not None:
                os.environ["LIFEBOARD_DB_PATH"] = original_db_path
            elif "LIFEBOARD_DB_PATH" in os.environ:
                del os.environ["LIFEBOARD_DB_PATH"]
                
            if original_embedding_model is not None:
                os.environ["EMBEDDING_MODEL"] = original_embedding_model
            elif "EMBEDDING_MODEL" in os.environ:
                del os.environ["EMBEDDING_MODEL"]


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


class TestOllamaConfig:
    """Test Ollama configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = OllamaConfig()
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama2"
        assert config.timeout == 60.0
        assert config.max_retries == 3
    
    def test_custom_values(self):
        """Test custom configuration values"""
        config = OllamaConfig(
            base_url="http://custom:8080",
            model="custom-model",
            timeout=30.0,
            max_retries=5
        )
        assert config.base_url == "http://custom:8080"
        assert config.model == "custom-model"
        assert config.timeout == 30.0
        assert config.max_retries == 5
    
    def test_is_configured_valid(self):
        """Test is_configured with valid config"""
        config = OllamaConfig(
            base_url="http://localhost:11434",
            model="llama2"
        )
        assert config.is_configured() is True
    
    def test_is_configured_invalid(self):
        """Test is_configured with invalid config"""
        config = OllamaConfig(base_url="", model="llama2")
        assert config.is_configured() is False
        
        config = OllamaConfig(base_url="http://localhost:11434", model="")
        assert config.is_configured() is False


class TestOpenAIConfig:
    """Test OpenAI configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = OpenAIConfig()
        assert config.api_key is None
        assert config.model == "gpt-3.5-turbo"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.timeout == 60.0
        assert config.max_retries == 3
        assert config.max_tokens == 1000
        assert config.temperature == 0.7
    
    def test_custom_values(self):
        """Test custom configuration values"""
        config = OpenAIConfig(
            api_key="sk-test-key",
            model="gpt-4",
            base_url="https://custom.openai.com/v1",
            timeout=30.0,
            max_retries=5,
            max_tokens=2000,
            temperature=0.5
        )
        assert config.api_key == "sk-test-key"
        assert config.model == "gpt-4"
        assert config.base_url == "https://custom.openai.com/v1"
        assert config.timeout == 30.0
        assert config.max_retries == 5
        assert config.max_tokens == 2000
        assert config.temperature == 0.5
    
    def test_is_configured_valid(self):
        """Test is_configured with valid config"""
        config = OpenAIConfig(api_key="sk-valid-key")
        assert config.is_configured() is True
    
    def test_is_configured_invalid(self):
        """Test is_configured with invalid config"""
        config = OpenAIConfig(api_key=None)
        assert config.is_configured() is False
        
        config = OpenAIConfig(api_key="")
        assert config.is_configured() is False
        
        config = OpenAIConfig(api_key="your_openai_api_key_here")
        assert config.is_configured() is False
    
    def test_api_key_validation(self):
        """Test API key validation"""
        config = OpenAIConfig(api_key="valid-key")
        assert config.api_key == "valid-key"
        
        config = OpenAIConfig(api_key=None)
        assert config.api_key is None
        
        with pytest.raises(ValidationError):
            OpenAIConfig(api_key=123)


class TestLLMProviderConfig:
    """Test LLM provider configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = LLMProviderConfig()
        assert config.provider == "ollama"
        assert isinstance(config.ollama, OllamaConfig)
        assert isinstance(config.openai, OpenAIConfig)
    
    def test_custom_values(self):
        """Test custom configuration values"""
        ollama_config = OllamaConfig(model="custom-llama")
        openai_config = OpenAIConfig(api_key="sk-test")
        
        config = LLMProviderConfig(
            provider="openai",
            ollama=ollama_config,
            openai=openai_config
        )
        
        assert config.provider == "openai"
        assert config.ollama is ollama_config
        assert config.openai is openai_config
    
    def test_provider_validation(self):
        """Test provider validation"""
        config = LLMProviderConfig(provider="ollama")
        assert config.provider == "ollama"
        
        config = LLMProviderConfig(provider="openai")
        assert config.provider == "openai"
        
        with pytest.raises(ValidationError):
            LLMProviderConfig(provider="invalid")
    
    def test_get_active_provider_config(self):
        """Test getting active provider configuration"""
        config = LLMProviderConfig(provider="ollama")
        active_config = config.get_active_provider_config()
        assert active_config is config.ollama
        
        config = LLMProviderConfig(provider="openai")
        active_config = config.get_active_provider_config()
        assert active_config is config.openai
        
        config.provider = "invalid"
        with pytest.raises(ValueError):
            config.get_active_provider_config()
    
    def test_is_active_provider_configured(self):
        """Test checking if active provider is configured"""
        # Ollama with valid config
        config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(base_url="http://localhost:11434", model="llama2")
        )
        assert config.is_active_provider_configured() is True
        
        # Ollama with invalid config
        config = LLMProviderConfig(
            provider="ollama",
            ollama=OllamaConfig(base_url="", model="llama2")
        )
        assert config.is_active_provider_configured() is False
        
        # OpenAI with valid config
        config = LLMProviderConfig(
            provider="openai",
            openai=OpenAIConfig(api_key="sk-valid-key")
        )
        assert config.is_active_provider_configured() is True
        
        # OpenAI with invalid config
        config = LLMProviderConfig(
            provider="openai",
            openai=OpenAIConfig(api_key=None)
        )
        assert config.is_active_provider_configured() is False


class TestChatConfig:
    """Test chat configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = ChatConfig()
        assert config.enabled is True
        assert config.history_limit == 1000
        assert config.context_window == 4000
        assert config.response_timeout == 30.0
    
    def test_custom_values(self):
        """Test custom configuration values"""
        config = ChatConfig(
            enabled=False,
            history_limit=500,
            context_window=2000,
            response_timeout=60.0
        )
        assert config.enabled is False
        assert config.history_limit == 500
        assert config.context_window == 2000
        assert config.response_timeout == 60.0
    
    def test_validation(self):
        """Test configuration validation"""
        with pytest.raises(ValidationError):
            ChatConfig(history_limit=0)
        
        with pytest.raises(ValidationError):
            ChatConfig(context_window=0)


class TestInsightsConfig:
    """Test insights configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = InsightsConfig()
        assert config.enabled is True
        assert config.schedule == "daily"
        assert config.custom_cron is None
        assert config.max_insights_history == 100
    
    def test_custom_values(self):
        """Test custom configuration values"""
        config = InsightsConfig(
            enabled=False,
            schedule="custom",
            custom_cron="0 8 * * *",
            max_insights_history=50
        )
        assert config.enabled is False
        assert config.schedule == "custom"
        assert config.custom_cron == "0 8 * * *"
        assert config.max_insights_history == 50
    
    def test_schedule_validation(self):
        """Test schedule validation"""
        valid_schedules = ["hourly", "daily", "weekly", "custom"]
        
        for schedule in valid_schedules:
            config = InsightsConfig(schedule=schedule)
            assert config.schedule == schedule
        
        with pytest.raises(ValidationError):
            InsightsConfig(schedule="invalid")


class TestEnhancementConfig:
    """Test enhancement configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = EnhancementConfig()
        assert config.enabled is True
        assert config.schedule == "nightly"
        assert config.batch_size == 100
        assert config.max_concurrent_jobs == 2
    
    def test_custom_values(self):
        """Test custom configuration values"""
        config = EnhancementConfig(
            enabled=False,
            schedule="hourly",
            batch_size=50,
            max_concurrent_jobs=1
        )
        assert config.enabled is False
        assert config.schedule == "hourly"
        assert config.batch_size == 50
        assert config.max_concurrent_jobs == 1
    
    def test_batch_size_validation(self):
        """Test batch size validation"""
        config = EnhancementConfig(batch_size=10)
        assert config.batch_size == 10
        
        with pytest.raises(ValidationError):
            EnhancementConfig(batch_size=0)
        
        with pytest.raises(ValidationError):
            EnhancementConfig(batch_size=-1)


class TestAppConfigPhase6:
    """Test app configuration with Phase 6 components"""
    
    def test_default_phase6_values(self):
        """Test default Phase 6 configuration"""
        config = AppConfig()
        
        # Check Phase 6 configs are properly initialized
        assert isinstance(config.llm_provider, LLMProviderConfig)
        assert isinstance(config.chat, ChatConfig)
        assert isinstance(config.insights, InsightsConfig)
        assert isinstance(config.enhancement, EnhancementConfig)
        
        # Check defaults
        assert config.llm_provider.provider == "ollama"
        assert config.chat.enabled is True
        assert config.insights.enabled is True
        assert config.enhancement.enabled is True
    
    def test_custom_phase6_values(self):
        """Test custom Phase 6 configuration"""
        config = AppConfig(
            llm_provider=LLMProviderConfig(
                provider="openai",
                openai=OpenAIConfig(api_key="sk-test")
            ),
            chat=ChatConfig(enabled=False),
            insights=InsightsConfig(schedule="weekly"),
            enhancement=EnhancementConfig(batch_size=50)
        )
        
        assert config.llm_provider.provider == "openai"
        assert config.llm_provider.openai.api_key == "sk-test"
        assert config.chat.enabled is False
        assert config.insights.schedule == "weekly"
        assert config.enhancement.batch_size == 50