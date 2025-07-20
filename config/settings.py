from typing import Any, Dict, Optional
import json
import os
from core.database import DatabaseService
from .models import AppConfig, SourceConfig, LimitlessConfig, LLMConfig


class DatabaseBackedSettings:
    """Database-backed settings manager for runtime configuration"""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self._ensure_default_settings()
    
    def _ensure_default_settings(self):
        """Ensure default settings exist in database"""
        defaults = {
            'embedding_model': 'all-MiniLM-L6-v2',
            'embedding_dimension': 384,
            'vector_store_save_threshold': 100,
            'search_default_top_k': 10,
            'search_similarity_threshold': 0.3,
            'scheduler_embedding_batch_size': 50,
            'scheduler_embedding_interval_seconds': 60,
            'namespace_prediction_enabled': True,
            'sources': []
        }
        
        for key, value in defaults.items():
            if self.db.get_setting(key) is None:
                self.db.set_setting(key, value)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self.db.get_setting(key, default)
    
    def set_setting(self, key: str, value: Any):
        """Set a setting value"""
        self.db.set_setting(key, value)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary"""
        # This would require a method to get all settings from database
        # For now, we'll return the key settings
        return {
            'embedding_model': self.get_setting('embedding_model'),
            'embedding_dimension': self.get_setting('embedding_dimension'),
            'vector_store_save_threshold': self.get_setting('vector_store_save_threshold'),
            'search_default_top_k': self.get_setting('search_default_top_k'),
            'search_similarity_threshold': self.get_setting('search_similarity_threshold'),
            'scheduler_embedding_batch_size': self.get_setting('scheduler_embedding_batch_size'),
            'scheduler_embedding_interval_seconds': self.get_setting('scheduler_embedding_interval_seconds'),
            'namespace_prediction_enabled': self.get_setting('namespace_prediction_enabled'),
            'sources': self.get_setting('sources', [])
        }
    
    def add_source(self, source_config: SourceConfig):
        """Add a new data source configuration"""
        sources = self.get_setting('sources', [])
        
        # Remove existing source with same namespace if it exists
        sources = [s for s in sources if s.get('namespace') != source_config.namespace]
        
        # Add new source
        sources.append(source_config.dict())
        self.set_setting('sources', sources)
        
        # Register in data_sources table
        self.db.register_data_source(
            source_config.namespace,
            source_config.source_type,
            source_config.config
        )
    
    def remove_source(self, namespace: str):
        """Remove a data source configuration"""
        sources = self.get_setting('sources', [])
        sources = [s for s in sources if s.get('namespace') != namespace]
        self.set_setting('sources', sources)
    
    def get_source(self, namespace: str) -> Optional[SourceConfig]:
        """Get source configuration by namespace"""
        sources = self.get_setting('sources', [])
        for source_data in sources:
            if source_data.get('namespace') == namespace:
                return SourceConfig(**source_data)
        return None
    
    def get_enabled_sources(self) -> list[SourceConfig]:
        """Get list of enabled source configurations"""
        sources = self.get_setting('sources', [])
        enabled = []
        for source_data in sources:
            source = SourceConfig(**source_data)
            if source.enabled:
                enabled.append(source)
        return enabled
    
    def update_source_config(self, namespace: str, config_updates: Dict[str, Any]):
        """Update configuration for a specific source"""
        sources = self.get_setting('sources', [])
        for source_data in sources:
            if source_data.get('namespace') == namespace:
                source_data['config'].update(config_updates)
                break
        self.set_setting('sources', sources)
    
    def enable_source(self, namespace: str):
        """Enable a data source"""
        sources = self.get_setting('sources', [])
        for source_data in sources:
            if source_data.get('namespace') == namespace:
                source_data['enabled'] = True
                break
        self.set_setting('sources', sources)
    
    def disable_source(self, namespace: str):
        """Disable a data source"""
        sources = self.get_setting('sources', [])
        for source_data in sources:
            if source_data.get('namespace') == namespace:
                source_data['enabled'] = False
                break
        self.set_setting('sources', sources)
    
    def set_limitless_config(self, config: LimitlessConfig):
        """Set Limitless API configuration"""
        self.set_setting('limitless_config', config.dict())
    
    def get_limitless_config(self) -> Optional[LimitlessConfig]:
        """Get Limitless API configuration"""
        config_data = self.get_setting('limitless_config')
        if config_data:
            return LimitlessConfig(**config_data)
        return None
    
    def set_llm_config(self, config: LLMConfig):
        """Set LLM configuration"""
        self.set_setting('llm_config', config.dict())
    
    def get_llm_config(self) -> Optional[LLMConfig]:
        """Get LLM configuration"""
        config_data = self.get_setting('llm_config')
        if config_data:
            return LLMConfig(**config_data)
        return None
    
    def export_settings(self) -> Dict[str, Any]:
        """Export all settings for backup"""
        return self.get_all_settings()
    
    def import_settings(self, settings: Dict[str, Any]):
        """Import settings from backup"""
        for key, value in settings.items():
            self.set_setting(key, value)


class EnvironmentSettings:
    """Environment-based settings for deployment configuration"""
    
    @staticmethod
    def get_database_path() -> str:
        """Get database path from environment"""
        return os.getenv('LIFEBOARD_DATABASE_PATH', 'lifeboard.db')
    
    @staticmethod
    def get_vector_store_path() -> str:
        """Get vector store path from environment"""
        return os.getenv('LIFEBOARD_VECTOR_STORE_PATH', 'vector_store')
    
    @staticmethod
    def get_api_host() -> str:
        """Get API host from environment"""
        return os.getenv('LIFEBOARD_API_HOST', '0.0.0.0')
    
    @staticmethod
    def get_api_port() -> int:
        """Get API port from environment"""
        return int(os.getenv('LIFEBOARD_API_PORT', '8000'))
    
    @staticmethod
    def get_log_level() -> str:
        """Get log level from environment"""
        return os.getenv('LIFEBOARD_LOG_LEVEL', 'info').lower()
    
    @staticmethod
    def get_openai_api_key() -> Optional[str]:
        """Get OpenAI API key from environment"""
        return os.getenv('OPENAI_API_KEY')
    
    @staticmethod
    def get_anthropic_api_key() -> Optional[str]:
        """Get Anthropic API key from environment"""
        return os.getenv('ANTHROPIC_API_KEY')
    
    @staticmethod
    def get_limitless_api_key() -> Optional[str]:
        """Get Limitless API key from environment"""
        return os.getenv('LIMITLESS_API_KEY')
    
    @staticmethod
    def is_development() -> bool:
        """Check if running in development mode"""
        return os.getenv('LIFEBOARD_ENV', 'production').lower() in ['dev', 'development']
    
    @staticmethod
    def get_embedding_device() -> str:
        """Get embedding computation device"""
        return os.getenv('LIFEBOARD_EMBEDDING_DEVICE', 'cpu')


class SettingsManager:
    """Combined settings manager for both database-backed and environment settings"""
    
    def __init__(self, db_service: DatabaseService):
        self.db_settings = DatabaseBackedSettings(db_service)
        self.env_settings = EnvironmentSettings()
    
    def get_runtime_setting(self, key: str, default: Any = None) -> Any:
        """Get runtime setting from database"""
        return self.db_settings.get_setting(key, default)
    
    def set_runtime_setting(self, key: str, value: Any):
        """Set runtime setting in database"""
        self.db_settings.set_setting(key, value)
    
    def get_deployment_setting(self, setting_type: str) -> Any:
        """Get deployment setting from environment"""
        getters = {
            'database_path': self.env_settings.get_database_path,
            'vector_store_path': self.env_settings.get_vector_store_path,
            'api_host': self.env_settings.get_api_host,
            'api_port': self.env_settings.get_api_port,
            'log_level': self.env_settings.get_log_level,
            'openai_api_key': self.env_settings.get_openai_api_key,
            'anthropic_api_key': self.env_settings.get_anthropic_api_key,
            'limitless_api_key': self.env_settings.get_limitless_api_key,
            'is_development': self.env_settings.is_development,
            'embedding_device': self.env_settings.get_embedding_device
        }
        
        getter = getters.get(setting_type)
        if getter:
            return getter()
        raise ValueError(f"Unknown deployment setting: {setting_type}")
    
    def add_source(self, source_config: SourceConfig):
        """Add data source"""
        self.db_settings.add_source(source_config)
    
    def get_enabled_sources(self) -> list[SourceConfig]:
        """Get enabled data sources"""
        return self.db_settings.get_enabled_sources()
    
    def set_external_service_config(self, service: str, config: Any):
        """Set external service configuration"""
        if service == 'limitless':
            self.db_settings.set_limitless_config(config)
        elif service == 'llm':
            self.db_settings.set_llm_config(config)
        else:
            raise ValueError(f"Unknown service: {service}")
    
    def get_external_service_config(self, service: str) -> Optional[Any]:
        """Get external service configuration"""
        if service == 'limitless':
            return self.db_settings.get_limitless_config()
        elif service == 'llm':
            return self.db_settings.get_llm_config()
        else:
            raise ValueError(f"Unknown service: {service}")