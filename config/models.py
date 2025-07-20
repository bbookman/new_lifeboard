from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import os


class DatabaseConfig(BaseModel):
    """Database configuration"""
    path: str = Field(default="lifeboard.db", description="SQLite database file path")
    
    @validator('path')
    def validate_path(cls, v):
        # Ensure directory exists
        dir_path = os.path.dirname(v)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        return v


class EmbeddingConfig(BaseModel):
    """Embedding service configuration"""
    model_name: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer model name")
    dimension: int = Field(default=384, description="Embedding vector dimension")
    batch_size: int = Field(default=32, description="Batch size for embedding generation")
    device: str = Field(default="cpu", description="Device for embedding computation (cpu/cuda)")
    
    @validator('device')
    def validate_device(cls, v):
        if v not in ['cpu', 'cuda', 'mps']:
            raise ValueError("Device must be 'cpu', 'cuda', or 'mps'")
        return v


class VectorStoreConfig(BaseModel):
    """Vector store configuration"""
    index_path: str = Field(default="vector_store/index.faiss", description="FAISS index file path")
    id_map_path: str = Field(default="vector_store/id_map.json", description="ID mapping file path")
    save_threshold: int = Field(default=100, description="Auto-save after N operations")
    
    @validator('index_path', 'id_map_path')
    def validate_paths(cls, v):
        # Ensure directory exists
        dir_path = os.path.dirname(v)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        return v


class LLMConfig(BaseModel):
    """LLM service configuration"""
    provider: str = Field(default="openai", description="LLM provider (openai, anthropic)")
    model: str = Field(default="gpt-3.5-turbo", description="Model name")
    api_key: str = Field(description="API key for LLM service")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=200, ge=1, description="Maximum tokens in response")
    timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    
    @validator('provider')
    def validate_provider(cls, v):
        if v not in ['openai', 'anthropic']:
            raise ValueError("Provider must be 'openai' or 'anthropic'")
        return v
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("API key cannot be empty")
        return v.strip()


class LimitlessConfig(BaseModel):
    """Limitless API configuration"""
    api_key: str = Field(description="Limitless API key")
    base_url: str = Field(default="https://api.limitless.ai/v1", description="Limitless API base URL")
    timezone: str = Field(default="UTC", description="Default timezone for queries")
    include_markdown: bool = Field(default=True, description="Include markdown in responses")
    include_headings: bool = Field(default=True, description="Include headings in responses")
    page_limit: int = Field(default=10, ge=1, le=10, description="Items per page (max 10)")
    timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Limitless API key cannot be empty")
        return v.strip()


class SourceConfig(BaseModel):
    """Data source configuration"""
    namespace: str = Field(description="Unique namespace for this source")
    source_type: str = Field(description="Type of source (limitless, file, api)")
    enabled: bool = Field(default=True, description="Whether this source is active")
    config: Dict[str, Any] = Field(default_factory=dict, description="Source-specific configuration")
    sync_interval_hours: int = Field(default=24, ge=1, description="Hours between sync operations")
    
    @validator('namespace')
    def validate_namespace(cls, v):
        from core.ids import NamespacedIDManager
        if not NamespacedIDManager.validate_namespace(v):
            raise ValueError(f"Invalid namespace: {v}")
        return NamespacedIDManager.normalize_namespace(v)


class SearchConfig(BaseModel):
    """Search service configuration"""
    default_top_k: int = Field(default=10, ge=1, description="Default number of results")
    max_top_k: int = Field(default=100, ge=1, description="Maximum allowed results")
    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum similarity score")
    namespace_prediction_enabled: bool = Field(default=True, description="Enable namespace prediction")
    max_prediction_retries: int = Field(default=3, ge=1, description="Max retries for namespace prediction")
    
    @validator('max_top_k')
    def validate_max_top_k(cls, v, values):
        if 'default_top_k' in values and v < values['default_top_k']:
            raise ValueError("max_top_k must be >= default_top_k")
        return v


class SchedulerConfig(BaseModel):
    """Background scheduler configuration"""
    embedding_batch_size: int = Field(default=50, ge=1, description="Batch size for embedding processing")
    embedding_interval_seconds: int = Field(default=60, ge=1, description="Seconds between embedding checks")
    cleanup_interval_hours: int = Field(default=24, ge=1, description="Hours between cleanup operations")
    max_embedding_retries: int = Field(default=3, ge=1, description="Max retries for failed embeddings")


class APIConfig(BaseModel):
    """API server configuration"""
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    reload: bool = Field(default=False, description="Enable auto-reload in development")
    log_level: str = Field(default="info", description="Logging level")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['critical', 'error', 'warning', 'info', 'debug']
        if v.lower() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.lower()


class AppConfig(BaseModel):
    """Main application configuration"""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    llm: LLMConfig = Field(description="LLM configuration for namespace prediction")
    search: SearchConfig = Field(default_factory=SearchConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    sources: List[SourceConfig] = Field(default_factory=list, description="Configured data sources")
    
    # Optional external service configurations
    limitless: Optional[LimitlessConfig] = Field(default=None, description="Limitless API configuration")
    
    class Config:
        env_prefix = "LIFEBOARD_"
        case_sensitive = False
        
    def get_source_by_namespace(self, namespace: str) -> Optional[SourceConfig]:
        """Get source configuration by namespace"""
        for source in self.sources:
            if source.namespace == namespace:
                return source
        return None
    
    def get_enabled_sources(self) -> List[SourceConfig]:
        """Get list of enabled sources"""
        return [source for source in self.sources if source.enabled]
    
    def get_namespaces(self) -> List[str]:
        """Get list of all configured namespaces"""
        return [source.namespace for source in self.sources]