import os
from typing import Optional, Dict, Any
from .models import (
    AppConfig, DatabaseConfig, EmbeddingConfig, VectorStoreConfig, 
    LLMConfig, SearchConfig, SchedulerConfig, APIConfig, SourceConfig,
    LimitlessConfig
)
from .settings import EnvironmentSettings, SettingsManager
from core.database import DatabaseService


class ConfigurationFactory:
    """Factory for creating application configuration from multiple sources"""
    
    @staticmethod
    def create_config() -> AppConfig:
        """Create complete application configuration"""
        env_settings = EnvironmentSettings()
        
        # Database configuration from environment
        database_config = DatabaseConfig(
            path=env_settings.get_database_path()
        )
        
        # Initialize database service for settings
        db_service = DatabaseService(database_config.path)
        settings_manager = SettingsManager(db_service)
        
        # Embedding configuration
        embedding_config = EmbeddingConfig(
            model_name=settings_manager.get_runtime_setting('embedding_model', 'all-MiniLM-L6-v2'),
            dimension=settings_manager.get_runtime_setting('embedding_dimension', 384),
            device=env_settings.get_embedding_device()
        )
        
        # Vector store configuration  
        vector_store_config = VectorStoreConfig(
            index_path=os.path.join(env_settings.get_vector_store_path(), 'index.faiss'),
            id_map_path=os.path.join(env_settings.get_vector_store_path(), 'id_map.json'),
            save_threshold=settings_manager.get_runtime_setting('vector_store_save_threshold', 100)
        )
        
        # LLM configuration
        llm_config = ConfigurationFactory._create_llm_config(env_settings, settings_manager)
        
        # Search configuration
        search_config = SearchConfig(
            default_top_k=settings_manager.get_runtime_setting('search_default_top_k', 10),
            similarity_threshold=settings_manager.get_runtime_setting('search_similarity_threshold', 0.3),
            namespace_prediction_enabled=settings_manager.get_runtime_setting('namespace_prediction_enabled', True)
        )
        
        # Scheduler configuration
        scheduler_config = SchedulerConfig(
            embedding_batch_size=settings_manager.get_runtime_setting('scheduler_embedding_batch_size', 50),
            embedding_interval_seconds=settings_manager.get_runtime_setting('scheduler_embedding_interval_seconds', 60)
        )
        
        # API configuration
        api_config = APIConfig(
            host=env_settings.get_api_host(),
            port=env_settings.get_api_port(),
            log_level=env_settings.get_log_level(),
            reload=env_settings.is_development()
        )
        
        # Source configurations
        sources = settings_manager.get_enabled_sources()
        
        # Limitless configuration if available
        limitless_config = ConfigurationFactory._create_limitless_config(env_settings, settings_manager)
        
        return AppConfig(
            database=database_config,
            embeddings=embedding_config,
            vector_store=vector_store_config,
            llm=llm_config,
            search=search_config,
            scheduler=scheduler_config,
            api=api_config,
            sources=sources,
            limitless=limitless_config
        )
    
    @staticmethod
    def _create_llm_config(env_settings: EnvironmentSettings, settings_manager: SettingsManager) -> LLMConfig:
        """Create LLM configuration from available API keys"""
        # Check for saved LLM config first
        saved_config = settings_manager.get_external_service_config('llm')
        if saved_config:
            return saved_config
        
        # Try to create from environment
        openai_key = env_settings.get_openai_api_key()
        anthropic_key = env_settings.get_anthropic_api_key()
        
        if openai_key:
            return LLMConfig(
                provider="openai",
                model="gpt-3.5-turbo", 
                api_key=openai_key
            )
        elif anthropic_key:
            return LLMConfig(
                provider="anthropic",
                model="claude-3-haiku-20240307",
                api_key=anthropic_key
            )
        else:
            # Provide a placeholder that will fail validation if used
            return LLMConfig(
                provider="openai",
                model="gpt-3.5-turbo",
                api_key="PLACEHOLDER_API_KEY_NOT_SET"
            )
    
    @staticmethod
    def _create_limitless_config(env_settings: EnvironmentSettings, settings_manager: SettingsManager) -> Optional[LimitlessConfig]:
        """Create Limitless configuration if API key is available"""
        # Check for saved config first
        saved_config = settings_manager.get_external_service_config('limitless')
        if saved_config:
            return saved_config
        
        # Try to create from environment
        api_key = env_settings.get_limitless_api_key()
        if api_key:
            return LimitlessConfig(api_key=api_key)
        
        return None
    
    @staticmethod
    def create_test_config(temp_dir: str = "/tmp") -> AppConfig:
        """Create configuration for testing with temporary files"""
        import tempfile
        
        # Create temporary directory
        test_dir = tempfile.mkdtemp(dir=temp_dir)
        
        return AppConfig(
            database=DatabaseConfig(path=os.path.join(test_dir, "test.db")),
            embeddings=EmbeddingConfig(
                model_name="all-MiniLM-L6-v2",
                dimension=384,
                device="cpu"
            ),
            vector_store=VectorStoreConfig(
                index_path=os.path.join(test_dir, "test_index.faiss"),
                id_map_path=os.path.join(test_dir, "test_id_map.json"),
                save_threshold=10  # Lower threshold for testing
            ),
            llm=LLMConfig(
                provider="openai",
                model="gpt-3.5-turbo",
                api_key="test_key"
            ),
            search=SearchConfig(
                default_top_k=5,
                similarity_threshold=0.1,
                namespace_prediction_enabled=False  # Disable for testing
            ),
            scheduler=SchedulerConfig(
                embedding_batch_size=10,
                embedding_interval_seconds=1
            ),
            api=APIConfig(
                host="127.0.0.1",
                port=8001,  # Different port for testing
                reload=False,
                log_level="debug"
            ),
            sources=[],
            limitless=None
        )
    
    @staticmethod
    def setup_initial_sources(config: AppConfig, settings_manager: SettingsManager):
        """Set up initial data sources based on available configuration"""
        # Add Limitless source if configured
        if config.limitless:
            limitless_source = SourceConfig(
                namespace="limitless",
                source_type="limitless",
                enabled=True,
                config={
                    "api_key": config.limitless.api_key,
                    "base_url": config.limitless.base_url,
                    "timezone": config.limitless.timezone
                }
            )
            settings_manager.add_source(limitless_source)
            config.sources.append(limitless_source)
    
    @staticmethod
    def validate_config(config: AppConfig) -> list[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check LLM configuration
        if config.llm.api_key == "PLACEHOLDER_API_KEY_NOT_SET":
            issues.append("LLM API key not configured - set OPENAI_API_KEY or ANTHROPIC_API_KEY")
        
        # Check database path is writable
        db_dir = os.path.dirname(config.database.path)
        if db_dir and not os.access(db_dir, os.W_OK):
            issues.append(f"Database directory not writable: {db_dir}")
        
        # Check vector store path is writable
        vector_dir = os.path.dirname(config.vector_store.index_path)
        if vector_dir and not os.access(vector_dir, os.W_OK):
            issues.append(f"Vector store directory not writable: {vector_dir}")
        
        # Check if any sources are configured
        if not config.sources and not config.limitless:
            issues.append("No data sources configured - application will have no data to search")
        
        return issues


def create_config() -> AppConfig:
    """Convenience function to create application configuration"""
    return ConfigurationFactory.create_config()


def create_test_config(temp_dir: str = "/tmp") -> AppConfig:
    """Convenience function to create test configuration"""
    return ConfigurationFactory.create_test_config(temp_dir)