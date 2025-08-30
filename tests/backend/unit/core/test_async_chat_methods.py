"""
TDD Test for AsyncDatabaseService chat methods implementation

Following TDD methodology:
RED: Write failing test first
GREEN: Implement to make test pass
REFACTOR: Improve implementation
"""

import pytest
from core.async_database import AsyncDatabaseService
from tests.fixtures.async_database_fixtures import async_temp_db_path


class TestAsyncChatMethods:
    """Test suite for chat methods async implementation"""
    
    @pytest.mark.asyncio
    async def test_store_chat_message_basic(self, async_temp_db_path):
        """RED: Test storing a basic chat message"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        await db_service.store_chat_message(
            "Hello, how are you?", 
            "I'm doing well, thank you for asking!"
        )
        
        # Verify message was stored by querying directly
        result = await db_service.fetch_one(
            "SELECT user_message, assistant_response FROM chat_messages ORDER BY timestamp DESC LIMIT 1"
        )
        
        assert result is not None
        assert result['user_message'] == "Hello, how are you?"
        assert result['assistant_response'] == "I'm doing well, thank you for asking!"
    
    @pytest.mark.asyncio
    async def test_get_chat_history_empty(self, async_temp_db_path):
        """RED: Test getting chat history from empty database"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        result = await db_service.get_chat_history()
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_chat_history_single_message(self, async_temp_db_path):
        """RED: Test getting chat history with single message"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store a message
        await db_service.store_chat_message(
            "What is the weather?", 
            "I can't check the weather directly, but I can help you with other questions."
        )
        
        result = await db_service.get_chat_history()
        
        assert len(result) == 1
        assert result[0]['user_message'] == "What is the weather?"
        assert result[0]['assistant_response'] == "I can't check the weather directly, but I can help you with other questions."
        assert 'id' in result[0]
        assert 'timestamp' in result[0]
    
    @pytest.mark.asyncio
    async def test_get_chat_history_multiple_messages(self, async_temp_db_path):
        """RED: Test getting chat history with multiple messages, should be chronological"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store multiple messages
        messages = [
            ("First question", "First answer"),
            ("Second question", "Second answer"),
            ("Third question", "Third answer")
        ]
        
        import asyncio
        for user_msg, assistant_msg in messages:
            await db_service.store_chat_message(user_msg, assistant_msg)
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.01)
        
        result = await db_service.get_chat_history()
        
        assert len(result) == 3
        # Should be in chronological order (oldest first) after reversal
        assert result[0]['user_message'] == "First question"
        assert result[1]['user_message'] == "Second question"
        assert result[2]['user_message'] == "Third question"
    
    @pytest.mark.asyncio
    async def test_get_chat_history_with_limit(self, async_temp_db_path):
        """RED: Test getting chat history with custom limit"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        # Store 5 messages
        for i in range(5):
            await db_service.store_chat_message(
                f"Question {i+1}", 
                f"Answer {i+1}"
            )
        
        # Get only 3 most recent (but return in chronological order)
        result = await db_service.get_chat_history(limit=3)
        
        assert len(result) == 3
        # Should return the 3 most recent messages in chronological order
        assert result[0]['user_message'] == "Question 3"  # Oldest of the recent 3
        assert result[1]['user_message'] == "Question 4"  
        assert result[2]['user_message'] == "Question 5"  # Newest
    
    @pytest.mark.asyncio  
    async def test_store_chat_message_with_special_characters(self, async_temp_db_path):
        """RED: Test storing chat messages with special characters and unicode"""
        db_service = AsyncDatabaseService(async_temp_db_path)
        await db_service.initialize()
        
        user_msg = "Can you help with 'quotes' and \"double quotes\" and émojis 🤖?"
        assistant_msg = "Of course! I can handle 'all' sorts of \"special\" characters including émojis 😊 and symbols: ©™®"
        
        await db_service.store_chat_message(user_msg, assistant_msg)
        
        result = await db_service.get_chat_history()
        assert len(result) == 1
        assert result[0]['user_message'] == user_msg
        assert result[0]['assistant_response'] == assistant_msg