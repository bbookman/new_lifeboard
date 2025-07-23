import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from .models import (
    AppConfig, DatabaseConfig, EmbeddingConfig, VectorStoreConfig,
    LimitlessConfig, NewsConfig, SearchConfig, SchedulerConfig, AutoSyncConfig, LoggingConfig,
    LLMProviderConfig, OllamaConfig, OpenAIConfig, ChatConfig, InsightsConfig, EnhancementConfig
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
        news=NewsConfig(
            api_key="test-rapid-api-key",
            language="en",
            enabled=False,  # Disabled for tests by default
            country="US",
            unique_items_per_day=2,
            endpoint="real-time-news-data.p.rapidapi.com",
            items_to_retrieve=5,
            max_retries=2,
            retry_delay=0.1,
            request_timeout=5.0,
            sync_interval_hours=24
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
        limitless=LimitlessConfig(
            api_key=os.getenv("LIMITLESS_API_KEY"),
            base_url=os.getenv("LIMITLESS_BASE_URL", "https://api.limitless.ai"),
            timezone=os.getenv("LIMITLESS_TIMEZONE", "UTC"),
            max_retries=int(os.getenv("LIMITLESS_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("LIMITLESS_RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("LIMITLESS_REQUEST_TIMEOUT", "30.0")),
            sync_interval_hours=int(os.getenv("LIMITLESS_SYNC_INTERVAL_HOURS", "6"))
        ),
        news=NewsConfig(
            api_key=os.getenv("RAPID_API_KEY"),
            language=os.getenv("USERS_LANGUAGE", "en"),
            enabled=os.getenv("TURN_ON_NEWS", "true").lower() == "true",
            country=os.getenv("NEWS_COUNTRY", "US"),
            unique_items_per_day=int(os.getenv("UNIQUE_NEWS_ITEMS_PER_DAY", "5")),
            endpoint=os.getenv("NEWS_ENDPOINT", "real-time-news-data.p.rapidapi.com"),
            items_to_retrieve=int(os.getenv("NEWS_ITEMS_TO_RETRIEVE", "20")),
            max_retries=int(os.getenv("NEWS_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("NEWS_RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("NEWS_REQUEST_TIMEOUT", "30.0")),
            sync_interval_hours=int(os.getenv("NEWS_SYNC_INTERVAL_HOURS", "24"))
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
        
        # Phase 6: LLM and Chat Capabilities
        llm_provider=LLMProviderConfig(
            provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama=OllamaConfig(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "llama2"),
                timeout=float(os.getenv("OLLAMA_TIMEOUT", "60.0")),
                max_retries=int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
            ),
            openai=OpenAIConfig(
                api_key=os.getenv("OPENAI_API_KEY"),
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                timeout=float(os.getenv("OPENAI_TIMEOUT", "60.0")),
                max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "1000")),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
            )
        ),
        chat=ChatConfig(
            enabled=os.getenv("CHAT_ENABLED", "true").lower() == "true",
            history_limit=int(os.getenv("CHAT_HISTORY_LIMIT", "1000")),
            context_window=int(os.getenv("CHAT_CONTEXT_WINDOW", "4000")),
            response_timeout=float(os.getenv("CHAT_RESPONSE_TIMEOUT", "30.0"))
        ),
        insights=InsightsConfig(
            enabled=os.getenv("INSIGHTS_ENABLED", "true").lower() == "true",
            schedule=os.getenv("INSIGHTS_SCHEDULE", "daily"),
            custom_cron=os.getenv("INSIGHTS_CUSTOM_CRON"),
            max_insights_history=int(os.getenv("INSIGHTS_MAX_HISTORY", "100"))
        ),
        enhancement=EnhancementConfig(
            enabled=os.getenv("ENHANCEMENT_ENABLED", "true").lower() == "true",
            schedule=os.getenv("ENHANCEMENT_SCHEDULE", "nightly"),
            batch_size=int(os.getenv("ENHANCEMENT_BATCH_SIZE", "100")),
            max_concurrent_jobs=int(os.getenv("ENHANCEMENT_MAX_CONCURRENT_JOBS", "2"))
        ),
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )