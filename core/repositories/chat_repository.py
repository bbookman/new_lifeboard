"""
ChatRepository implementation for chat_messages table operations

This repository extracts all chat-related operations from DatabaseService,
implementing the Repository pattern for better separation of concerns and testability.
Maintains full backward compatibility with existing code.
"""

import logging
from typing import List, Dict, Any
from contextlib import contextmanager, asynccontextmanager

from .interfaces import IChatRepository

logger = logging.getLogger(__name__)


class ChatRepository(IChatRepository):
    """
    Concrete implementation of IChatRepository
    
    Handles all CRUD operations for the chat_messages table including:
    - Chat message storage and retrieval
    - Chat history management with chronological ordering
    - Both sync and async operations for all functionality
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
    
    def store_chat_message(self, user_message: str, assistant_response: str) -> None:
        """Store a chat message exchange"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chat_messages (user_message, assistant_response)
                VALUES (?, ?)
            """, (user_message, assistant_response))
            conn.commit()
    
    async def async_store_chat_message(self, user_message: str, assistant_response: str) -> None:
        """Async version of store_chat_message"""
        try:
            async with self._get_async_connection() as conn:
                await conn.execute("""
                    INSERT INTO chat_messages (user_message, assistant_response)
                    VALUES (?, ?)
                """, (user_message, assistant_response))
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Error in async_store_chat_message: {e}")
            raise
    
    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent chat history in chronological order"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, user_message, assistant_response, timestamp
                FROM chat_messages
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row['id'],
                    'user_message': row['user_message'],
                    'assistant_response': row['assistant_response'],
                    'timestamp': row['timestamp']
                })
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))
    
    async def async_get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Async version of get_chat_history"""
        try:
            async with self._get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, user_message, assistant_response, timestamp
                    FROM chat_messages
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    messages = []
                    for row in rows:
                        messages.append({
                            'id': row['id'],
                            'user_message': row['user_message'],
                            'assistant_response': row['assistant_response'],
                            'timestamp': row['timestamp']
                        })
                    
                    # Return in chronological order (oldest first)
                    return list(reversed(messages))
        except Exception as e:
            self.logger.error(f"Error in async_get_chat_history: {e}")
            raise