"""
Repository Factory for centralized repository creation and dependency injection

This factory provides a centralized way to create and manage all repository instances,
implementing dependency injection and ensuring consistent initialization across the application.
"""

import logging
from typing import Optional

from .interfaces import IDataItemRepository, ISettingsRepository, IChatRepository, IDataSourceRepository
from .data_item_repository import DataItemRepository
from .settings_repository import SettingsRepository
from .chat_repository import ChatRepository
from .data_source_repository import DataSourceRepository
from .llm_repository import LLMRepository

logger = logging.getLogger(__name__)


class RepositoryFactory:
    """
    Factory class for creating and managing repository instances
    
    Provides centralized dependency injection and ensures that repositories
    are created with proper database service dependencies. Supports both
    singleton and per-request repository creation patterns.
    """
    
    def __init__(self, database_service):
        """
        Initialize factory with database service dependency
        
        Args:
            database_service: DatabaseService instance for all repositories
        """
        self.database_service = database_service
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # Cache for singleton repository instances
        self._data_item_repository: Optional[IDataItemRepository] = None
        self._settings_repository: Optional[ISettingsRepository] = None
        self._chat_repository: Optional[IChatRepository] = None
        self._data_source_repository: Optional[IDataSourceRepository] = None
        self._llm_repository: Optional[LLMRepository] = None
        
        self.logger.info("RepositoryFactory initialized with database service")
    
    def get_data_item_repository(self) -> IDataItemRepository:
        """
        Get or create DataItemRepository instance
        
        Returns:
            IDataItemRepository instance
        """
        if self._data_item_repository is None:
            self._data_item_repository = DataItemRepository(self.database_service)
            self.logger.debug("Created new DataItemRepository instance")
        return self._data_item_repository
    
    def get_settings_repository(self) -> ISettingsRepository:
        """
        Get or create SettingsRepository instance
        
        Returns:
            ISettingsRepository instance
        """
        if self._settings_repository is None:
            self._settings_repository = SettingsRepository(self.database_service)
            self.logger.debug("Created new SettingsRepository instance")
        return self._settings_repository
    
    def get_chat_repository(self) -> IChatRepository:
        """
        Get or create ChatRepository instance
        
        Returns:
            IChatRepository instance
        """
        if self._chat_repository is None:
            self._chat_repository = ChatRepository(self.database_service)
            self.logger.debug("Created new ChatRepository instance")
        return self._chat_repository
    
    def get_data_source_repository(self) -> IDataSourceRepository:
        """
        Get or create DataSourceRepository instance
        
        Returns:
            IDataSourceRepository instance
        """
        if self._data_source_repository is None:
            self._data_source_repository = DataSourceRepository(self.database_service)
            self.logger.debug("Created new DataSourceRepository instance")
        return self._data_source_repository

    
    def get_llm_repository(self) -> LLMRepository:
        """
        Get or create LLMRepository instance
        
        Returns:
            LLMRepository instance
        """
        if self._llm_repository is None:
            self._llm_repository = LLMRepository(self.database_service)
            self.logger.debug("Created new LLMRepository instance")
        return self._llm_repository
    
    def create_data_item_repository(self) -> IDataItemRepository:
        """
        Create a new DataItemRepository instance (not cached)
        
        Returns:
            New IDataItemRepository instance
        """
        self.logger.debug("Creating new DataItemRepository instance (not cached)")
        return DataItemRepository(self.database_service)
    
    def create_settings_repository(self) -> ISettingsRepository:
        """
        Create a new SettingsRepository instance (not cached)
        
        Returns:
            New ISettingsRepository instance
        """
        self.logger.debug("Creating new SettingsRepository instance (not cached)")
        return SettingsRepository(self.database_service)
    
    def create_chat_repository(self) -> IChatRepository:
        """
        Create a new ChatRepository instance (not cached)
        
        Returns:
            New IChatRepository instance
        """
        self.logger.debug("Creating new ChatRepository instance (not cached)")
        return ChatRepository(self.database_service)
    
    def create_data_source_repository(self) -> IDataSourceRepository:
        """
        Create a new DataSourceRepository instance (not cached)
        
        Returns:
            New IDataSourceRepository instance
        """
        self.logger.debug("Creating new DataSourceRepository instance (not cached)")
        return DataSourceRepository(self.database_service)

    
    def create_llm_repository(self) -> LLMRepository:
        """
        Create a new LLMRepository instance (not cached)
        
        Returns:
            New LLMRepository instance
        """
        self.logger.debug("Creating new LLMRepository instance (not cached)")
        return LLMRepository(self.database_service)
    
    def reset_cache(self) -> None:
        """
        Reset all cached repository instances
        
        This forces new instances to be created on next access.
        Useful for testing or when database service changes.
        """
        self.logger.info("Resetting repository cache")
        self._data_item_repository = None
        self._settings_repository = None
        self._chat_repository = None
        self._data_source_repository = None
        self._llm_repository = None
    
    def get_all_repositories(self) -> dict:
        """
        Get all repository instances (creating them if needed)
        
        Returns:
            Dictionary with all repository instances
        """
        return {
            'data_item': self.get_data_item_repository(),
            'settings': self.get_settings_repository(),
            'chat': self.get_chat_repository(),
            'data_source': self.get_data_source_repository(),
            'llm': self.get_llm_repository()
        }
    
    def health_check(self) -> dict:
        """
        Perform health check on all repositories
        
        Returns:
            Dictionary with health status of each repository
        """
        health_status = {}
        
        try:
            # Test each repository by accessing its database service
            data_item_repo = self.get_data_item_repository()
            with data_item_repo._get_connection() as conn:
                conn.execute("SELECT 1")
            health_status['data_item'] = 'healthy'
        except Exception as e:
            health_status['data_item'] = f'error: {e}'
            self.logger.error(f"DataItemRepository health check failed: {e}")
        
        try:
            settings_repo = self.get_settings_repository()
            with settings_repo._get_connection() as conn:
                conn.execute("SELECT 1")
            health_status['settings'] = 'healthy'
        except Exception as e:
            health_status['settings'] = f'error: {e}'
            self.logger.error(f"SettingsRepository health check failed: {e}")
        
        try:
            chat_repo = self.get_chat_repository()
            with chat_repo._get_connection() as conn:
                conn.execute("SELECT 1")
            health_status['chat'] = 'healthy'
        except Exception as e:
            health_status['chat'] = f'error: {e}'
            self.logger.error(f"ChatRepository health check failed: {e}")
        
        try:
            data_source_repo = self.get_data_source_repository()
            with data_source_repo._get_connection() as conn:
                conn.execute("SELECT 1")
            health_status['data_source'] = 'healthy'
        except Exception as e:
            health_status['data_source'] = f'error: {e}'
            self.logger.error(f"DataSourceRepository health check failed: {e}")
        
        try:
            llm_repo = self.get_llm_repository()
            with llm_repo._get_connection() as conn:
                conn.execute("SELECT 1")
            health_status['llm'] = 'healthy'
        except Exception as e:
            health_status['llm'] = f'error: {e}'
            self.logger.error(f"LLMRepository health check failed: {e}")
        
        return health_status