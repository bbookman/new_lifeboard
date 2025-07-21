from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
import os


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


class LLMConfig(BaseModel):
    """LLM service configuration"""
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    api_key: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        if v not in ["openai", "anthropic", "mock"]:
            raise ValueError("Provider must be one of: openai, anthropic, mock")
        return v
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("API key must be a string")
        return v


class LimitlessConfig(BaseModel):
    """Limitless API configuration"""
    api_key: Optional[str] = None
    base_url: str = "https://api.limitless.ai"
    timezone: str = "UTC"
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    sync_interval_hours: int = 6
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("API key must be a string")
        return v


class SourceConfig(BaseModel):
    """Data source configuration"""
    namespace: str
    enabled: bool = True
    sync_interval_hours: int = 24
    
    @field_validator('namespace')
    @classmethod
    def validate_namespace(cls, v):
        if not v or not isinstance(v, str) or ':' in v:
            raise ValueError("Namespace must be a non-empty string without colons")
        return v


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


class AutoSyncConfig(BaseModel):
    """Auto-sync configuration"""
    enabled: bool = True
    startup_sync_enabled: bool = False
    startup_sync_delay_seconds: int = 60
    auto_register_sources: bool = True
    
    @field_validator('startup_sync_delay_seconds')
    @classmethod
    def validate_startup_delay(cls, v):
        if v < 0:
            raise ValueError("Startup sync delay must be non-negative")
        return v


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


class AppConfig(BaseModel):
    """Main application configuration"""
    database: DatabaseConfig = DatabaseConfig()
    embeddings: EmbeddingConfig = EmbeddingConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    llm: LLMConfig = LLMConfig()
    limitless: LimitlessConfig = LimitlessConfig()
    search: SearchConfig = SearchConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    auto_sync: AutoSyncConfig = AutoSyncConfig()
    logging: LoggingConfig = LoggingConfig()
    
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