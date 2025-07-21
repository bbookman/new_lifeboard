import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from .models import (
    AppConfig, DatabaseConfig, EmbeddingConfig, VectorStoreConfig,
    LLMConfig, LimitlessConfig, SearchConfig, SchedulerConfig, AutoSyncConfig, LoggingConfig
)


def create_test_config(temp_dir: str = None) -> AppConfig:
    """Create configuration for testing"""
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    
    temp_path = Path(temp_dir)
    
    return AppConfig(
        database=DatabaseConfig(
            path=str(temp_path / "test_lifeboard.db")
        ),
        embeddings=EmbeddingConfig(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
            batch_size=8  # Smaller for tests
        ),
        vector_store=VectorStoreConfig(
            index_path=str(temp_path / "test_vector_index.faiss"),
            id_map_path=str(temp_path / "test_vector_ids.json"),
            dimension=384
        ),
        llm=LLMConfig(
            provider="mock",  # Use mock for tests
            model="mock-model",
            api_key="test-key",
            max_tokens=500,
            temperature=0.0  # Deterministic for tests
        ),
        limitless=LimitlessConfig(
            api_key="test-limitless-key",
            base_url="https://api.limitless.ai",
            timezone="UTC",
            max_retries=2,
            retry_delay=0.1,  # Fast retries for tests
            request_timeout=5.0,
            sync_interval_hours=1
        ),
        search=SearchConfig(
            default_limit=10,
            max_limit=50,
            similarity_threshold=0.5,
            max_top_k=20
        ),
        scheduler=SchedulerConfig(
            check_interval_seconds=60,
            max_concurrent_jobs=2,
            job_timeout_minutes=5
        ),
        auto_sync=AutoSyncConfig(
            enabled=True,
            startup_sync_enabled=False,
            startup_sync_delay_seconds=10,
            auto_register_sources=True
        ),
        logging=LoggingConfig(
            level="DEBUG",
            file_path=str(temp_path / "test_lifeboard.log"),
            max_file_size=1024 * 1024,  # 1MB for tests
            backup_count=2,
            console_logging=True,
            include_correlation_ids=False
        ),
        debug=True
    )


def create_production_config() -> AppConfig:
    """Create production configuration from environment"""
    # Load environment variables from .env file if it exists
    # Use override=True to ensure .env values take precedence over shell environment
    load_dotenv(override=True)
    
    return AppConfig(
        database=DatabaseConfig(
            path=os.getenv("LIFEBOARD_DB_PATH", "lifeboard.db")
        ),
        embeddings=EmbeddingConfig(
            model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            device=os.getenv("EMBEDDING_DEVICE", "cpu"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
        ),
        vector_store=VectorStoreConfig(
            index_path=os.getenv("VECTOR_INDEX_PATH", "vector_index.faiss"),
            id_map_path=os.getenv("VECTOR_ID_MAP_PATH", "vector_ids.json"),
            dimension=int(os.getenv("VECTOR_DIMENSION", "384"))
        ),
        llm=LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            api_key=os.getenv("LLM_API_KEY"),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
        ),
        limitless=LimitlessConfig(
            api_key=os.getenv("LIMITLESS_API_KEY"),
            base_url=os.getenv("LIMITLESS_BASE_URL", "https://api.limitless.ai"),
            timezone=os.getenv("LIMITLESS_TIMEZONE", "UTC"),
            max_retries=int(os.getenv("LIMITLESS_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("LIMITLESS_RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("LIMITLESS_REQUEST_TIMEOUT", "30.0")),
            sync_interval_hours=int(os.getenv("LIMITLESS_SYNC_INTERVAL_HOURS", "6"))
        ),
        search=SearchConfig(
            default_limit=int(os.getenv("SEARCH_DEFAULT_LIMIT", "20")),
            max_limit=int(os.getenv("SEARCH_MAX_LIMIT", "100")),
            similarity_threshold=float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", "0.7")),
            max_top_k=int(os.getenv("SEARCH_MAX_TOP_K", "50"))
        ),
        scheduler=SchedulerConfig(
            check_interval_seconds=int(os.getenv("SCHEDULER_CHECK_INTERVAL", "300")),
            max_concurrent_jobs=int(os.getenv("SCHEDULER_MAX_JOBS", "3")),
            job_timeout_minutes=int(os.getenv("SCHEDULER_JOB_TIMEOUT", "30"))
        ),
        auto_sync=AutoSyncConfig(
            enabled=os.getenv("AUTO_SYNC_ENABLED", "true").lower() == "true",
            startup_sync_enabled=os.getenv("STARTUP_SYNC_ENABLED", "false").lower() == "true",
            startup_sync_delay_seconds=int(os.getenv("STARTUP_SYNC_DELAY_SECONDS", "60")),
            auto_register_sources=os.getenv("AUTO_REGISTER_SOURCES", "true").lower() == "true"
        ),
        logging=LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file_path=os.getenv("LOG_FILE_PATH", "logs/lifeboard.log"),
            max_file_size=int(os.getenv("LOG_MAX_FILE_SIZE", str(10 * 1024 * 1024))),  # 10MB default
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            console_logging=os.getenv("LOG_CONSOLE_ENABLED", "true").lower() == "true",
            include_correlation_ids=os.getenv("LOG_CORRELATION_IDS", "false").lower() == "true",
            log_format=os.getenv("LOG_FORMAT")  # None if not set, will use default
        ),
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )