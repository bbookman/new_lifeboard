"""
Configuration validation module for Phase 1.2: Configuration Standardization
Provides comprehensive validation for application configuration at startup
"""
import logging
import re
from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path
from .models import AppConfig, LimitlessConfig, NewsConfig, WeatherConfig


logger = logging.getLogger(__name__)


class ConfigurationValidationError(Exception):
    """Exception raised when configuration validation fails"""
    
    def __init__(self, message: str, validation_errors: List[str] = None):
        self.message = message
        self.validation_errors = validation_errors or []
        super().__init__(self.format_error_message())
    
    def format_error_message(self) -> str:
        """Format error message with validation details"""
        if not self.validation_errors:
            return self.message
        
        error_list = "\n".join(f"  - {error}" for error in self.validation_errors)
        return f"{self.message}\n\nValidation errors:\n{error_list}"


class ConfigurationValidator:
    """Validates application configuration for consistency and completeness"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Perform comprehensive configuration validation
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        logger.info("Starting comprehensive configuration validation...")
        
        # Reset validation state
        self.validation_errors.clear()
        self.warnings.clear()
        
        # Run all validation checks
        self._validate_api_configurations()
        self._validate_database_configuration()
        self._validate_embedding_configuration()
        self._validate_consistency_checks()
        self._validate_security_requirements()
        
        is_valid = len(self.validation_errors) == 0
        
        if is_valid:
            logger.info("Configuration validation passed successfully")
        else:
            logger.error(f"Configuration validation failed with {len(self.validation_errors)} errors")
        
        if self.warnings:
            logger.warning(f"Configuration validation completed with {len(self.warnings)} warnings")
        
        return is_valid, self.validation_errors.copy(), self.warnings.copy()
    
    def _validate_api_configurations(self) -> None:
        """Validate external API configurations"""
        logger.debug("Validating API configurations...")
        
        # Validate Limitless API configuration
        if not self.config.limitless.is_api_key_configured():
            self.warnings.append("Limitless API key is not configured - Limitless features will be disabled")
        else:
            # Additional Limitless validation
            if self.config.limitless.max_retries < 1:
                self.validation_errors.append("Limitless max_retries must be at least 1")
            
            if self.config.limitless.request_timeout < 5.0:
                self.validation_errors.append("Limitless request_timeout should be at least 5.0 seconds")
        
        # Validate News API configuration
        if self.config.news.enabled:
            if not self.config.news.is_api_key_configured():
                self.validation_errors.append("News API key is required when news is enabled")
            
            if not self.config.news.is_endpoint_configured():
                self.validation_errors.append("News API endpoint is required when news is enabled")
            
            if self.config.news.unique_items_per_day > self.config.news.items_to_retrieve:
                self.validation_errors.append(
                    f"News unique_items_per_day ({self.config.news.unique_items_per_day}) "
                    f"cannot exceed items_to_retrieve ({self.config.news.items_to_retrieve})"
                )
        
        # Validate Weather API configuration  
        if self.config.weather.enabled:
            if not self.config.weather.is_api_key_configured():
                self.validation_errors.append("Weather API key is required when weather is enabled")
            
            # Validate coordinates format (basic validation)
            try:
                lat = float(self.config.weather.latitude)
                lon = float(self.config.weather.longitude)
                
                if not (-90 <= lat <= 90):
                    self.validation_errors.append(f"Invalid latitude: {lat} (must be between -90 and 90)")
                
                if not (-180 <= lon <= 180):
                    self.validation_errors.append(f"Invalid longitude: {lon} (must be between -180 and 180)")
                    
            except ValueError as e:
                self.validation_errors.append(f"Invalid coordinate format: {e}")
    
    def _validate_database_configuration(self) -> None:
        """Validate database configuration"""
        logger.debug("Validating database configuration...")
        
        db_path = Path(self.config.database.path)
        
        # Check if database directory is writable
        try:
            db_dir = db_path.parent
            if not db_dir.exists():
                # Try to create the directory
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            
            # Test write permissions
            test_file = db_dir / ".write_test"
            try:
                test_file.touch()
                test_file.unlink()
            except PermissionError:
                self.validation_errors.append(f"Database directory is not writable: {db_dir}")
                
        except Exception as e:
            self.validation_errors.append(f"Cannot access database directory: {e}")
    
    def _validate_embedding_configuration(self) -> None:
        """Validate embedding configuration"""
        logger.debug("Validating embedding configuration...")
        
        # Validate embedding model configuration
        if self.config.embeddings.batch_size < 1:
            self.validation_errors.append("Embedding batch_size must be positive")
        
        if self.config.embeddings.batch_size > 256:
            self.warnings.append(f"Large embedding batch_size ({self.config.embeddings.batch_size}) may consume excessive memory")
        
        # Validate vector store configuration
        vector_dir = Path(self.config.vector_store.index_path).parent
        if not vector_dir.exists():
            try:
                vector_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created vector store directory: {vector_dir}")
            except Exception as e:
                self.validation_errors.append(f"Cannot create vector store directory: {e}")
    
    def _validate_consistency_checks(self) -> None:
        """Validate configuration consistency"""
        logger.debug("Validating configuration consistency...")
        
        # Check for common configuration typos and inconsistencies
        self._check_for_common_typos()
        
        # Validate timeout and retry consistency
        api_configs = [
            ("Limitless", self.config.limitless),
            ("News", self.config.news), 
            ("Weather", self.config.weather)
        ]
        
        for name, config in api_configs:
            if hasattr(config, 'request_timeout') and hasattr(config, 'retry_delay') and hasattr(config, 'max_retries'):
                total_retry_time = config.retry_delay * config.max_retries
                if total_retry_time > config.request_timeout:
                    self.warnings.append(
                        f"{name} API: Total retry time ({total_retry_time}s) exceeds request timeout ({config.request_timeout}s)"
                    )
    
    def _check_for_common_typos(self) -> None:
        """Check for common configuration typos"""
        logger.debug("Checking for common configuration typos...")
        
        # Check weather configuration for longitude typo
        weather_config = self.config.weather
        if hasattr(weather_config, 'logitude'):  # This should not exist
            self.validation_errors.append("Found 'logitude' field - should be 'longitude'")
        
        # Verify correct field names exist
        required_weather_fields = ['latitude', 'longitude']
        for field in required_weather_fields:
            if not hasattr(weather_config, field):
                self.validation_errors.append(f"Weather configuration missing required field: {field}")
    
    def _validate_security_requirements(self) -> None:
        """Validate security-related configuration"""
        logger.debug("Validating security requirements...")
        
        # Check for placeholder API keys in production
        api_configs = [
            ("Limitless", self.config.limitless.api_key),
            ("News", self.config.news.api_key),
            ("Weather", self.config.weather.api_key)
        ]
        
        placeholder_patterns = [
            r"test[_-]?key",
            r"placeholder",
            r"your[_-]?api[_-]?key",
            r"changeme",
            r"example[_-]?key"
        ]
        
        for name, api_key in api_configs:
            if api_key:
                api_key_lower = api_key.lower()
                for pattern in placeholder_patterns:
                    if re.search(pattern, api_key_lower):
                        self.warnings.append(f"{name} API key appears to be a placeholder value")
                        break
        
        # Validate HTTPS usage
        https_urls = [
            ("Limitless base URL", self.config.limitless.base_url)
        ]
        
        for name, url in https_urls:
            if url and not url.startswith("https://"):
                self.validation_errors.append(f"{name} should use HTTPS: {url}")


def validate_configuration_at_startup(config: AppConfig) -> None:
    """
    Validate configuration at application startup
    
    Args:
        config: Application configuration to validate
        
    Raises:
        ConfigurationValidationError: If validation fails
    """
    logger.info("Performing startup configuration validation...")
    
    validator = ConfigurationValidator(config)
    is_valid, errors, warnings = validator.validate_all()
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"Configuration warning: {warning}")
    
    # Raise exception if validation failed
    if not is_valid:
        logger.error("Configuration validation failed - cannot start application")
        raise ConfigurationValidationError(
            "Configuration validation failed - application cannot start safely",
            validation_errors=errors
        )
    
    logger.info("Configuration validation completed successfully")


def validate_environment_file_consistency() -> Tuple[bool, List[str]]:
    """
    Validate consistency between .env.example and configuration models
    
    Returns:
        Tuple of (is_consistent, inconsistency_errors)
    """
    logger.info("Validating .env.example consistency...")
    
    errors = []
    env_example_path = Path(__file__).parent.parent / ".env.example"
    
    if not env_example_path.exists():
        errors.append(f".env.example file not found at {env_example_path}")
        return False, errors
    
    # Parse .env.example
    env_vars = {}
    try:
        with open(env_example_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
    except Exception as e:
        errors.append(f"Failed to parse .env.example: {e}")
        return False, errors
    
    # Check for required keys
    required_keys = {
        'LIMITLESS__API_KEY', 'RAPID_API_KEY', 'NEWS_ENDPOINT',
        'USER_HOME_LATITUDE', 'USER_HOME_LONGITUDE', 'UNITS',
        'EMBEDDING_MODEL', 'EMBEDDING_DEVICE', 'EMBEDDING_BATCH_SIZE'
    }
    
    missing_keys = required_keys - set(env_vars.keys())
    if missing_keys:
        errors.append(f"Missing required keys in .env.example: {missing_keys}")
    
    # Check for typos
    typo_checks = [
        ('USER_HOME_LOGITUDE', 'USER_HOME_LONGITUDE'),
        ('LATITUTDE', 'LATITUDE'),
        ('LONGITUTDE', 'LONGITUDE')
    ]
    
    for typo, correct in typo_checks:
        if typo in env_vars:
            errors.append(f"Found typo '{typo}' in .env.example - should be '{correct}'")
    
    is_consistent = len(errors) == 0
    
    if is_consistent:
        logger.info(".env.example consistency validation passed")
    else:
        logger.error(f".env.example consistency validation failed with {len(errors)} errors")
    
    return is_consistent, errors