from pydantic import BaseModel, field_validator, ConfigDict, Field
from typing import Optional, List
import os

from .validation import (
    APIKeyValidator, StringValidator, NumericValidator, PathValidator,
    BaseConfigMixin, ConfigValidationError
)


class DatabaseConfig(BaseModel):
    """Database configuration"""
    path: str = "lifeboard.db"
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("Database path must be a non-empty string")
        return v


class EmbeddingConfig(BaseModel):
    """Embedding service configuration"""
    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    batch_size: int = 32
    
    @field_validator('device')
    @classmethod
    def validate_device(cls, v):
        if v not in ["cpu", "cuda", "mps"]:
            raise ValueError("Device must be one of: cpu, cuda, mps")
        return v
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables"""
        import os
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            device=os.getenv("EMBEDDING_DEVICE", "cpu"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
        )


class VectorStoreConfig(BaseModel):
    """Vector store configuration"""
    index_path: str = "vector_index.faiss"
    id_map_path: str = "vector_ids.json"
    dimension: int = 384  # Matches all-MiniLM-L6-v2
    
    @field_validator('index_path', 'id_map_path')
    @classmethod
    def validate_paths(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("Path must be a non-empty string")
        return v



class LimitlessConfig(BaseModel, BaseConfigMixin):
    """Limitless API configuration"""
    api_key: Optional[str] = None
    base_url: str = "https://api.limitless.ai"
    timezone: str = "UTC"
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    sync_interval_hours: int = 6
    # Rate limiting configuration
    rate_limit_max_delay: int = 300  # Maximum delay for rate limiting (5 minutes)
    respect_retry_after: bool = True
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        return APIKeyValidator.validate_api_key_format(v, "Limitless API key")
    
    @field_validator('max_retries', 'sync_interval_hours', 'rate_limit_max_delay')
    @classmethod
    def validate_positive_ints(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return NumericValidator.validate_positive_int(v, field_name)
    
    @field_validator('retry_delay', 'request_timeout')
    @classmethod
    def validate_positive_floats(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return NumericValidator.validate_positive_float(v, field_name)
    
    def is_api_key_configured(self) -> bool:
        """Check if API key is properly configured"""
        return super().is_api_key_configured(
            self.api_key, 
            additional_placeholders={"your_api_key_here", "limitless_api_key_here"}
        )


class NewsConfig(BaseModel, BaseConfigMixin):
    """News API configuration"""
    api_key: Optional[str] = None
    language: str = "en"
    enabled: bool = True
    country: str = "US"
    unique_items_per_day: int = 5
    endpoint: Optional[str] = None
    items_to_retrieve: int = 20
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    sync_interval_hours: int = 24
    # Rate limiting configuration
    rate_limit_max_delay: int = 300  # Maximum delay for rate limiting (5 minutes)
    respect_retry_after: bool = True
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        return APIKeyValidator.validate_api_key_format(v, "News API key")
    
    @field_validator('language', 'country')
    @classmethod
    def validate_strings(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return StringValidator.validate_non_empty_string(v, field_name)
    
    @field_validator('unique_items_per_day', 'items_to_retrieve', 'max_retries', 'sync_interval_hours', 'rate_limit_max_delay')
    @classmethod
    def validate_positive_ints(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return NumericValidator.validate_positive_int(v, field_name)
    
    @field_validator('retry_delay', 'request_timeout')
    @classmethod
    def validate_positive_floats(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return NumericValidator.validate_positive_float(v, field_name)
    
    def is_api_key_configured(self) -> bool:
        """Check if API key is properly configured"""
        return super().is_api_key_configured(
            self.api_key,
            additional_placeholders={"your-rapid-api-key-here", "rapid_api_key_here"}
        )

    def is_endpoint_configured(self) -> bool:
        """Check if endpoint is properly configured"""
        if not self.endpoint or not isinstance(self.endpoint, str):
            return False
        
        # Check if endpoint is empty or whitespace only
        if not self.endpoint.strip():
            return False
        
        # Check against common placeholder patterns
        endpoint_lower = self.endpoint.lower().strip()
        placeholders = {
            "null", "none", "endpoint_here", "your_endpoint_here", 
            "news_endpoint_here", "example.com", "api.example.com"
        }
        return endpoint_lower not in placeholders

    def is_fully_configured(self) -> bool:
        """Check if both API key and endpoint are properly configured"""
        return self.enabled and self.is_api_key_configured() and self.is_endpoint_configured()


class WeatherConfig(BaseModel, BaseConfigMixin):
    """Weather API configuration"""
    api_key: Optional[str] = Field(None, env="RAPID_API_KEY")
    endpoint: Optional[str] = Field(None, env="WEATHER_ENDPOINT")
    latitude: str = Field("34.0522", env="USER_HOME_LATITUDE")
    longitude: str = Field("-118.2437", env="USER_HOME_LOGITUDE")
    units: str = Field("metric", env="UNITS")
    enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    sync_interval_hours: int = 4 # every 4 hours
    # Rate limiting configuration
    rate_limit_max_delay: int = 300  # Maximum delay for rate limiting (5 minutes)
    respect_retry_after: bool = True

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        return APIKeyValidator.validate_api_key_format(v, "Weather API key")

    @field_validator('units')
    @classmethod
    def validate_units(cls, v):
        return StringValidator.validate_string_choices(v, ["metric", "standard"], "Units")
    
    @field_validator('max_retries', 'sync_interval_hours', 'rate_limit_max_delay')
    @classmethod
    def validate_positive_ints(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return NumericValidator.validate_positive_int(v, field_name)
    
    @field_validator('retry_delay', 'request_timeout')
    @classmethod
    def validate_positive_floats(cls, v, info):
        field_name = info.field_name.replace('_', ' ').title()
        return NumericValidator.validate_positive_float(v, field_name)

    def is_api_key_configured(self) -> bool:
        """Check if API key is properly configured"""
        return super().is_api_key_configured(
            self.api_key,
            additional_placeholders={"your-rapid-api-key-here", "rapid_api_key_here"}
        )

    def is_endpoint_configured(self) -> bool:
        """Check if endpoint is properly configured"""
        if not self.endpoint or not isinstance(self.endpoint, str):
            return False
        
        # Check if endpoint is empty or whitespace only
        if not self.endpoint.strip():
            return False
        
        # Check against common placeholder patterns
        endpoint_lower = self.endpoint.lower().strip()
        placeholders = {
            "null", "none", "endpoint_here", "your_endpoint_here",
            "weather_endpoint_here", "example.com", "api.example.com"
        }
        return endpoint_lower not in placeholders

    def is_fully_configured(self) -> bool:
        """Check if both API key and endpoint are properly configured"""
        return self.enabled and self.is_api_key_configured() and self.is_endpoint_configured()


class SourceConfig(BaseModel):
    """Data source configuration"""
    namespace: str
    enabled: bool = True
    sync_interval_hours: int = 24
    
    @field_validator('namespace')
    @classmethod
    def validate_namespace(cls, v):
        v = StringValidator.validate_non_empty_string(v, "Namespace")
        return StringValidator.validate_no_special_chars(v, "Namespace", {':'})
    
    @field_validator('sync_interval_hours')
    @classmethod
    def validate_sync_interval(cls, v):
        return NumericValidator.validate_positive_int(v, "Sync interval hours")


class SearchConfig(BaseModel):
    """Search configuration"""
    default_limit: int = 20
    max_limit: int = 100
    similarity_threshold: float = 0.7
    max_top_k: int = 50
    
    @field_validator('max_top_k')
    @classmethod
    def validate_max_top_k(cls, v):
        if v <= 0:
            raise ValueError("max_top_k must be positive")
        return v


class SchedulerConfig(BaseModel):
    """Scheduler configuration"""
    check_interval_seconds: int = 300  # 5 minutes
    max_concurrent_jobs: int = 3
    job_timeout_minutes: int = 30



class LoggingConfig(BaseModel):
    """Centralized logging configuration"""
    level: str = "INFO"
    file_path: str = "logs/lifeboard.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_logging: bool = True
    include_correlation_ids: bool = False
    log_format: Optional[str] = None
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator('max_file_size')
    @classmethod
    def validate_max_file_size(cls, v):
        if v <= 0:
            raise ValueError("Max file size must be positive")
        return v
    
    @field_validator('backup_count')
    @classmethod
    def validate_backup_count(cls, v):
        if v < 0:
            raise ValueError("Backup count must be non-negative")
        return v
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("File path must be a non-empty string")
        return v


class ChatConfig(BaseModel):
    """Chat interface configuration"""
    enabled: bool = True
    history_limit: int = 1000
    context_window: int = 4000
    response_timeout: float = 30.0
    
    @field_validator('history_limit')
    @classmethod
    def validate_history_limit(cls, v):
        if v <= 0:
            raise ValueError("History limit must be positive")
        return v
    
    @field_validator('context_window')
    @classmethod
    def validate_context_window(cls, v):
        if v <= 0:
            raise ValueError("Context window must be positive")
        return v


class InsightsConfig(BaseModel):
    """Insights generation configuration"""
    enabled: bool = True
    schedule: str = "daily"  # hourly, daily, weekly, custom
    custom_cron: Optional[str] = None
    max_insights_history: int = 100
    
    @field_validator('schedule')
    @classmethod
    def validate_schedule(cls, v):
        valid_schedules = ["hourly", "daily", "weekly", "custom"]
        if v not in valid_schedules:
            raise ValueError(f"Schedule must be one of: {valid_schedules}")
        return v


class EnhancementConfig(BaseModel):
    """Data enhancement processing configuration"""
    enabled: bool = True
    schedule: str = "nightly"
    batch_size: int = 100
    max_concurrent_jobs: int = 2
    
    @field_validator('batch_size')
    @classmethod
    def validate_batch_size(cls, v):
        if v <= 0:
            raise ValueError("Batch size must be positive")
        return v


class OllamaConfig(BaseModel):
    """Ollama provider configuration"""
    base_url: str = "http://localhost:11434"
    model: str = "llama2"
    timeout: float = 60.0
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        """Check if Ollama is properly configured"""
        return bool(self.base_url and self.model)


class OpenAIConfig(BaseModel):
    """OpenAI provider configuration"""
    api_key: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    base_url: str = "https://api.openai.com/v1"
    timeout: float = 60.0
    max_retries: int = 3
    max_tokens: int = 1000
    temperature: float = 0.7
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("API key must be a string")
        return v
    
    def is_configured(self) -> bool:
        """Check if OpenAI is properly configured"""
        return (self.api_key is not None and 
                self.api_key.strip() != "" and 
                self.api_key != "your_openai_api_key_here")


class LLMProviderConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = "ollama"  # ollama or openai
    ollama: OllamaConfig = OllamaConfig()
    openai: OpenAIConfig = OpenAIConfig()
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        valid_providers = ["ollama", "openai"]
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of: {valid_providers}")
        return v
    
    def get_active_provider_config(self):
        """Get the configuration for the active provider"""
        if self.provider == "ollama":
            return self.ollama
        elif self.provider == "openai":
            return self.openai
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def is_active_provider_configured(self) -> bool:
        """Check if the active provider is properly configured"""
        active_config = self.get_active_provider_config()
        return active_config.is_configured()


class TwitterConfig(BaseModel):
    """Twitter source configuration"""
    enabled: bool = True
    sync_interval_hours: int = 24
    data_path: Optional[str] = None
    delete_after_import: bool = False

    def is_configured(self) -> bool:
        """Check if Twitter source is properly configured"""
        return self.enabled


class AppConfig(BaseModel):
    """Main application configuration"""
    database: DatabaseConfig = DatabaseConfig()
    embeddings: EmbeddingConfig = EmbeddingConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    limitless: LimitlessConfig = LimitlessConfig()
    news: NewsConfig = NewsConfig()
    weather: WeatherConfig = WeatherConfig()
    twitter: TwitterConfig = TwitterConfig()
    search: SearchConfig = SearchConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    logging: LoggingConfig = LoggingConfig()
    
    # Phase 6: LLM and Chat Capabilities
    llm_provider: LLMProviderConfig = LLMProviderConfig()
    chat: ChatConfig = ChatConfig()
    insights: InsightsConfig = InsightsConfig()
    enhancement: EnhancementConfig = EnhancementConfig()
    
    # Global settings
    debug: bool = False
    
    # Backward compatibility - kept for existing code that might use it
    @property
    def log_level(self) -> str:
        """Get log level from logging config for backward compatibility"""
        return self.logging.level
    
    model_config = ConfigDict(
        env_file=".env",
        env_nested_delimiter="__"
    )