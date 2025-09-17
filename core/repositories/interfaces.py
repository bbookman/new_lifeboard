"""
Repository interface definitions for database abstraction layer

This module defines abstract interfaces for data access operations, 
implementing the Repository pattern to separate data access concerns
from business logic and enable dependency injection.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class IDataItemRepository(ABC):
    """
    Interface for data_items table operations
    
    Handles all CRUD operations for the main data storage table,
    including content retrieval, embedding status management,
    and date-based filtering.
    """
    
    # Core CRUD operations
    @abstractmethod
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None, days_date: str = None,
                       ingestion_status: str = 'complete') -> None:
        """Store data item with namespaced ID"""
        pass
    
    @abstractmethod
    async def async_store_data_item(self, id: str, namespace: str, source_id: str, 
                                  content: str, metadata: Dict = None, days_date: str = None,
                                  ingestion_status: str = 'complete') -> None:
        """Async version of store_data_item"""
        pass
    
    @abstractmethod
    def get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Batch fetch data items by namespaced IDs"""
        pass
    
    @abstractmethod
    async def async_get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Async version of get_data_items_by_ids"""
        pass
    
    # Namespace operations
    @abstractmethod
    def get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Get data items for a specific namespace"""
        pass
    
    @abstractmethod
    async def async_get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Async version of get_data_items_by_namespace"""
        pass
    
    @abstractmethod
    def get_all_namespaces(self) -> List[str]:
        """Get list of all distinct namespaces in data_items table"""
        pass
    
    @abstractmethod
    async def async_get_all_namespaces(self) -> List[str]:
        """Async version of get_all_namespaces"""
        pass
    
    # Date-based operations
    @abstractmethod
    def get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                   namespaces: Optional[List[str]] = None,
                                   limit: int = 100) -> List[Dict]:
        """Get data items within a date range"""
        pass
    
    @abstractmethod
    async def async_get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                               namespaces: Optional[List[str]] = None,
                                               limit: int = 100) -> List[Dict]:
        """Async version of get_data_items_by_date_range"""
        pass
    
    @abstractmethod
    def get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Get all data items for a specific date"""
        pass
    
    @abstractmethod
    async def async_get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Async version of get_data_items_by_date"""
        pass
    
    @abstractmethod
    def get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of dates that have data available"""
        pass
    
    @abstractmethod
    async def async_get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Async version of get_available_dates"""
        pass
    
    @abstractmethod
    def get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of days that have data (for calendar indicators)"""
        pass
    
    @abstractmethod
    async def async_get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Async version of get_days_with_data"""
        pass
    
    # Embedding and status operations
    @abstractmethod
    def update_embedding_status(self, id: str, status: str) -> None:
        """Update embedding status for a data item"""
        pass
    
    @abstractmethod
    async def async_update_embedding_status(self, id: str, status: str) -> None:
        """Async version of update_embedding_status"""
        pass
    
    @abstractmethod
    def update_ingestion_status(self, item_id: str, status: str) -> None:
        """Update ingestion status for a data item"""
        pass
    
    @abstractmethod
    async def async_update_ingestion_status(self, item_id: str, status: str) -> None:
        """Async version of update_ingestion_status"""
        pass
    
    @abstractmethod
    def get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Get data items that need embedding"""
        pass
    
    @abstractmethod
    async def async_get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Async version of get_pending_embeddings"""
        pass


class ISettingsRepository(ABC):
    """
    Interface for system_settings table operations
    
    Handles application configuration and settings storage
    with JSON serialization support.
    """
    
    @abstractmethod
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get database-backed setting with JSON parsing"""
        pass
    
    @abstractmethod
    async def async_get_setting(self, key: str, default: Any = None) -> Any:
        """Async version of get_setting"""
        pass
    
    @abstractmethod
    def set_setting(self, key: str, value: Any) -> None:
        """Set database-backed setting with JSON serialization"""
        pass
    
    @abstractmethod
    async def async_set_setting(self, key: str, value: Any) -> None:
        """Async version of set_setting"""
        pass


class IChatRepository(ABC):
    """
    Interface for chat_messages table operations
    
    Handles storage and retrieval of chat conversations
    between users and the AI assistant.
    """
    
    @abstractmethod
    def store_chat_message(self, user_message: str, assistant_response: str) -> None:
        """Store a chat message exchange"""
        pass
    
    @abstractmethod
    async def async_store_chat_message(self, user_message: str, assistant_response: str) -> None:
        """Async version of store_chat_message"""
        pass
    
    @abstractmethod
    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent chat history in chronological order"""
        pass
    
    @abstractmethod
    async def async_get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Async version of get_chat_history"""
        pass


class IDataSourceRepository(ABC):
    """
    Interface for data_sources table operations
    
    Handles registration and management of data source metadata,
    tracking active sources and their item counts.
    """
    
    @abstractmethod
    def register_data_source(self, namespace: str, source_type: str, metadata: Dict = None) -> None:
        """Register a new data source"""
        pass
    
    @abstractmethod
    async def async_register_data_source(self, namespace: str, source_type: str, metadata: Dict = None) -> None:
        """Async version of register_data_source"""
        pass
    
    @abstractmethod
    def get_active_namespaces(self) -> List[str]:
        """Get list of active data source namespaces"""
        pass
    
    @abstractmethod
    async def async_get_active_namespaces(self) -> List[str]:
        """Async version of get_active_namespaces"""
        pass
    
    @abstractmethod
    def update_source_item_count(self, namespace: str) -> int:
        """Update item count for a data source, returns new count"""
        pass
    
    @abstractmethod
    async def async_update_source_item_count(self, namespace: str) -> int:
        """Async version of update_source_item_count"""
        pass