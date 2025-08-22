"""
Database service migration utility for seamless transition to connection pooling.

Provides utilities to upgrade existing code from DatabaseService to EnhancedDatabaseService
with minimal code changes and full backward compatibility.
"""

import logging
import warnings
from typing import Optional

from core.database import DatabaseService
from core.enhanced_database import EnhancedDatabaseService
from core.database_pool import PoolConfig

logger = logging.getLogger(__name__)


class DatabaseServiceFactory:
    """Factory for creating database services with migration support."""
    
    @staticmethod
    def create_service(
        db_path: str = "lifeboard.db", 
        use_enhanced: bool = True,
        pool_config: Optional[PoolConfig] = None
    ):
        """Create a database service with optional enhancement.
        
        Args:
            db_path: Path to database file
            use_enhanced: Whether to use enhanced service with connection pooling
            pool_config: Configuration for connection pool (if using enhanced)
            
        Returns:
            DatabaseService or EnhancedDatabaseService instance
        """
        if use_enhanced:
            logger.info("DATABASE_FACTORY: Creating enhanced database service with connection pooling")
            return EnhancedDatabaseService(db_path, pool_config)
        else:
            logger.info("DATABASE_FACTORY: Creating standard database service")
            return DatabaseService(db_path)

    @staticmethod
    def migrate_existing_service(
        existing_service: DatabaseService,
        pool_config: Optional[PoolConfig] = None
    ) -> EnhancedDatabaseService:
        """Migrate an existing DatabaseService to EnhancedDatabaseService.
        
        Args:
            existing_service: Existing DatabaseService instance
            pool_config: Configuration for connection pool
            
        Returns:
            New EnhancedDatabaseService instance with same database
        """
        logger.info(f"DATABASE_FACTORY: Migrating database service from {existing_service.db_path}")
        
        # Create enhanced service with same database path
        enhanced_service = EnhancedDatabaseService(existing_service.db_path, pool_config)
        
        logger.info("DATABASE_FACTORY: Migration completed successfully")
        return enhanced_service


class LegacyDatabaseService(DatabaseService):
    """Legacy database service that warns about upgrade opportunities.
    
    This is a drop-in replacement for DatabaseService that provides
    deprecation warnings and guidance for upgrading to the enhanced version.
    """
    
    def __init__(self, db_path: str = "lifeboard.db"):
        """Initialize legacy database service with upgrade warnings."""
        super().__init__(db_path)
        
        # Issue deprecation warning
        warnings.warn(
            "DatabaseService without connection pooling is deprecated. "
            "Consider upgrading to EnhancedDatabaseService for better performance. "
            "Use DatabaseServiceFactory.create_service(use_enhanced=True) or "
            "migrate with DatabaseServiceFactory.migrate_existing_service()",
            DeprecationWarning,
            stacklevel=2
        )
        
        logger.warning(
            "LEGACY_DB: Using legacy DatabaseService. "
            "Consider upgrading to EnhancedDatabaseService for improved performance and resource management."
        )


def get_recommended_pool_config(environment: str = "development") -> PoolConfig:
    """Get recommended pool configuration for different environments.
    
    Args:
        environment: Environment type ('development', 'production', 'testing')
        
    Returns:
        Recommended PoolConfig for the environment
    """
    if environment == "production":
        return PoolConfig(
            max_connections=20,
            min_connections=5,
            connection_timeout=30.0,
            health_check_interval=60.0,
            enable_health_monitoring=True
        )
    elif environment == "testing":
        return PoolConfig(
            max_connections=5,
            min_connections=1,
            connection_timeout=5.0,
            health_check_interval=30.0,
            enable_health_monitoring=False  # Disable for faster tests
        )
    else:  # development
        return PoolConfig(
            max_connections=10,
            min_connections=2,
            connection_timeout=15.0,
            health_check_interval=45.0,
            enable_health_monitoring=True
        )


def upgrade_database_service_usage(file_content: str) -> str:
    """Automatically upgrade DatabaseService usage in Python code.
    
    Args:
        file_content: Python source code content
        
    Returns:
        Updated source code with enhanced database service usage
        
    Note:
        This is a simple text-based replacement. Manual review is recommended.
    """
    upgrades = [
        # Import statement upgrades
        (
            "from core.database import DatabaseService",
            "from core.database_migration import DatabaseServiceFactory"
        ),
        # Instantiation upgrades
        (
            "DatabaseService(",
            "DatabaseServiceFactory.create_service("
        ),
        (
            "self.database = DatabaseService(",
            "self.database = DatabaseServiceFactory.create_service("
        ),
    ]
    
    updated_content = file_content
    changes_made = []
    
    for old_pattern, new_pattern in upgrades:
        if old_pattern in updated_content:
            updated_content = updated_content.replace(old_pattern, new_pattern)
            changes_made.append(f"'{old_pattern}' -> '{new_pattern}'")
    
    if changes_made:
        logger.info(f"DATABASE_MIGRATION: Made {len(changes_made)} automatic upgrades")
        for change in changes_made:
            logger.debug(f"DATABASE_MIGRATION: {change}")
    
    return updated_content


# Convenience functions for common migration patterns

def create_database_service(
    db_path: str = "lifeboard.db",
    environment: str = "development"
) -> EnhancedDatabaseService:
    """Create database service with environment-appropriate configuration.
    
    Args:
        db_path: Path to database file
        environment: Environment type for configuration
        
    Returns:
        Configured EnhancedDatabaseService
    """
    pool_config = get_recommended_pool_config(environment)
    return DatabaseServiceFactory.create_service(
        db_path=db_path,
        use_enhanced=True,
        pool_config=pool_config
    )


def get_database_service() -> EnhancedDatabaseService:
    """Get singleton database service instance.
    
    Returns:
        Shared EnhancedDatabaseService instance
        
    Note:
        This creates a global singleton. Use carefully in multi-threaded environments.
    """
    if not hasattr(get_database_service, '_instance'):
        get_database_service._instance = create_database_service()
    
    return get_database_service._instance