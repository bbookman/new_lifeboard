"""
SettingsRepository implementation for system_settings table operations

This repository extracts all settings-related operations from DatabaseService,
implementing the Repository pattern for better separation of concerns and testability.
Maintains full backward compatibility with existing code.
"""

import logging
from typing import Any
from contextlib import contextmanager, asynccontextmanager

from .interfaces import ISettingsRepository
from ..json_utils import JSONMetadataParser

logger = logging.getLogger(__name__)


class SettingsRepository(ISettingsRepository):
    """
    Concrete implementation of ISettingsRepository
    
    Handles all CRUD operations for the system_settings table including:
    - Database-backed setting storage and retrieval
    - JSON serialization/deserialization for complex values
    - Fallback handling for settings with default values
    """
    
    def __init__(self, database_service):
        """
        Initialize repository with database service dependency
        
        Args:
            database_service: DatabaseService instance for connection management
        """
        self.database_service = database_service
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection via DatabaseService"""
        with self.database_service.get_connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def _get_async_connection(self):
        """Get async database connection via DatabaseService"""
        async with self.database_service.get_async_connection() as conn:
            yield conn
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get database-backed setting with JSON parsing"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                # Handle JSON null as Python None
                if row['value'] == "null":
                    return None
                # Try to parse as JSON, fallback to string value
                parsed = JSONMetadataParser.parse_metadata(row['value'])
                return parsed if parsed is not None else row['value']
            return default
    
    async def async_get_setting(self, key: str, default: Any = None) -> Any:
        """Async version of get_setting"""
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute(
                    "SELECT value FROM system_settings WHERE key = ?", (key,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        # Handle JSON null as Python None
                        if row['value'] == "null":
                            return None
                        # Try to parse as JSON, fallback to string value
                        parsed = JSONMetadataParser.parse_metadata(row['value'])
                        return parsed if parsed is not None else row['value']
                    return default
        except Exception as e:
            self.logger.error(f"Error in async_get_setting: {e}")
            raise
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set database-backed setting with JSON serialization"""
        with self._get_connection() as conn:
            # Handle None values by storing as JSON null
            if value is None:
                stored_value = "null"
            else:
                stored_value = JSONMetadataParser.serialize_metadata(value) or str(value)
            
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, stored_value))
            conn.commit()
    
    async def async_set_setting(self, key: str, value: Any) -> None:
        """Async version of set_setting"""
        try:
            # Handle None values by storing as JSON null
            if value is None:
                stored_value = "null"
            else:
                stored_value = JSONMetadataParser.serialize_metadata(value) or str(value)
            
            async with self._get_async_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, stored_value))
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Error in async_set_setting: {e}")
            raise