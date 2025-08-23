import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from .models import (
    AppConfig, DatabaseConfig, EmbeddingConfig, VectorStoreConfig,
    LimitlessConfig, NewsConfig, WeatherConfig, TwitterConfig, SearchConfig, SchedulerConfig, LoggingConfig,
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
        weather=WeatherConfig(
            api_key="test-rapid-api-key",
            endpoint="easy-weather1.p.rapidapi.com/daily/5",
            latitude="34.0522",
            longitude="-118.2437",
            units="metric",
            enabled=False,  # Disabled for tests by default
            max_retries=2,
            retry_delay=0.1,
            request_timeout=5.0,
            sync_interval_hours=6
        ),
        debug=True
    )


def create_production_config() -> AppConfig:
    """Create production configuration from environment"""
    # Load environment variables from .env file if it exists
    # Use override=True to ensure .env values take precedence over shell environment
    load_dotenv(override=True)
    
    # Debug Twitter configuration loading
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Loading Twitter configuration...")
    logger.info(f"TWITTER_BEARER_TOKEN present: {bool(os.getenv('TWITTER_BEARER_TOKEN'))}")
    logger.info(f"TWITTER_USER_NAME present: {bool(os.getenv('TWITTER_USER_NAME'))}")
    logger.info(f"TWITTER_BEARER_TOKEN: {os.getenv('TWITTER_BEARER_TOKEN')!r}")
    logger.info(f"TWITTER_USER_NAME: {os.getenv('TWITTER_USER_NAME')!r}")
    
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
            api_key=os.getenv("LIMITLESS__API_KEY"),
            base_url=os.getenv("LIMITLESS__BASE_URL", "https://api.limitless.ai"),
            timezone=os.getenv("LIMITLESS__TIMEZONE", os.getenv("TIME_ZONE", "UTC")),
            max_retries=int(os.getenv("LIMITLESS__MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("LIMITLESS__RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("LIMITLESS__REQUEST_TIMEOUT", "30.0")),
            sync_interval_hours=int(os.getenv("LIMITLESS__SYNC_INTERVAL_HOURS", "6")),
            rate_limit_max_delay=int(os.getenv("LIMITLESS__RATE_LIMIT_MAX_DELAY", "300")),
            respect_retry_after=os.getenv("LIMITLESS__RESPECT_RETRY_AFTER", "true").lower() == "true"
        ),
        news=NewsConfig(
            api_key=os.getenv("RAPID_API_KEY"),
            language=os.getenv("USERS_LANGUAGE", "en"),
            country=os.getenv("NEWS_COUNTRY", "US"),
            unique_items_per_day=int(os.getenv("UNIQUE_NEWS_ITEMS_PER_DAY", "5")),
            endpoint=os.getenv("NEWS_ENDPOINT"),
            items_to_retrieve=int(os.getenv("NEWS_ITEMS_TO_RETRIEVE", "20")),
            max_retries=int(os.getenv("NEWS_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("NEWS_RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("NEWS_REQUEST_TIMEOUT", "30.0")),
            sync_interval_hours=int(os.getenv("NEWS_SYNC_INTERVAL_HOURS", "24"))
        ),
        weather=WeatherConfig(
            api_key=os.getenv("RAPID_API_KEY"),
            endpoint=os.getenv("WEATHER_ENDPOINT"),
            latitude=os.getenv("USER_HOME_LATITUDE", "34.0522"),
            longitude=os.getenv("USER_HOME_LONGITUDE", "-118.2437"),
            units=os.getenv("UNITS", "metric"),
            enabled=os.getenv("TURN_ON_WEATHER", "true").lower() == "true",
            max_retries=int(os.getenv("WEATHER_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("WEATHER_RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("WEATHER_REQUEST_TIMEOUT", "30.0")),
            sync_interval_hours=int(os.getenv("WEATHER__SYNC_INTERVAL_HOURS", "6")),
            rate_limit_max_delay=int(os.getenv("WEATHER_RATE_LIMIT_MAX_DELAY", "300")),
            respect_retry_after=os.getenv("WEATHER_RESPECT_RETRY_AFTER", "true").lower() == "true"
        ),
        twitter=TwitterConfig(
            enabled=os.getenv("TWITTER_ENABLED", "true").lower() == "true",
            delete_after_import=os.getenv("DELETE_AFTER_IMPORT", "false").lower() == "true",
            sync_interval_hours=int(os.getenv("TWITTER_SYNC_INTERVAL_HOURS", "24")),
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            username=os.getenv("TWITTER_USER_NAME"),
            max_retries=int(os.getenv("TWITTER_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("TWITTER_RETRY_DELAY", "1.0")),
            request_timeout=float(os.getenv("TWITTER_REQUEST_TIMEOUT", "30.0")),
            rate_limit_max_retries=int(os.getenv("TWITTER_RATE_LIMIT_MAX_RETRIES", "10")),
            other_error_max_retries=int(os.getenv("TWITTER_OTHER_ERROR_MAX_RETRIES", "3")),
            inter_call_delay=float(os.getenv("TWITTER_INTER_CALL_DELAY", "3.0"))
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


def get_config() -> AppConfig:
    """Get configuration for the application (defaults to production config)"""
    return create_production_config()


class ConfigFactory:
    """Factory class for creating application configuration instances"""
    
    @staticmethod
    def create_config() -> AppConfig:
        """Create configuration instance (defaults to production config)"""
        return create_production_config()
    
    @staticmethod
    def create_production_config() -> AppConfig:
        """Create production configuration from environment"""
        return create_production_config()
    
    @staticmethod
    def create_test_config(temp_dir: str = None) -> AppConfig:
        """Create configuration for testing"""
        return create_test_config(temp_dir)