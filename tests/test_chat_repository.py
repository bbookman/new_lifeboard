"""
Unit tests for ChatRepository implementation

These tests verify that the ChatRepository correctly implements
the IChatRepository interface and maintains backward compatibility
with the original DatabaseService functionality.
"""

import pytest
import tempfile
import os
import asyncio
from datetime import datetime, timezone

from core.repositories.chat_repository import ChatRepository
from core.repositories.interfaces import IChatRepository
from core.database import DatabaseService


@pytest.fixture
def temp_db_path():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def database_service(temp_db_path):
    """Create a test DatabaseService instance"""
    return DatabaseService(temp_db_path)


@pytest.fixture
def repository(database_service):
    """Create a ChatRepository instance for testing"""
    return ChatRepository(database_service)


class TestChatRepositoryInterface:
    """Test that ChatRepository properly implements IChatRepository"""
    
    def test_implements_interface(self, repository):
        """Verify repository implements the interface"""
        assert isinstance(repository, IChatRepository)
    
    def test_has_all_interface_methods(self, repository):
        """Verify all interface methods are implemented"""
        interface_methods = [
            'store_chat_message', 'async_store_chat_message',
            'get_chat_history', 'async_get_chat_history'
        ]
        
        for method_name in interface_methods:
            assert hasattr(repository, method_name), f"Missing method: {method_name}"
            assert callable(getattr(repository, method_name)), f"Method not callable: {method_name}"


class TestChatRepositoryInitialization:
    """Test repository initialization and setup"""
    
    def test_initialization_with_database_service(self, database_service):
        """Test repository initialization with database service"""
        repo = ChatRepository(database_service)
        assert repo.database_service is database_service
        assert hasattr(repo, 'logger')
    
    def test_connection_management(self, repository):
        """Test database connection context managers"""
        # Test sync connection
        with repository._get_connection() as conn:
            assert conn is not None
            # Verify connection works
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1


class TestChatMessageOperations:
    """Test core chat message storage and retrieval operations"""
    
    def test_store_and_retrieve_single_message(self, repository):
        """Test storing and retrieving a single chat message"""
        user_msg = "Hello, assistant!"
        assistant_msg = "Hello! How can I help you today?"
        
        repository.store_chat_message(user_msg, assistant_msg)
        history = repository.get_chat_history(limit=1)
        
        assert len(history) == 1
        message = history[0]
        assert message['user_message'] == user_msg
        assert message['assistant_response'] == assistant_msg
        assert 'id' in message
        assert 'timestamp' in message
    
    def test_store_multiple_messages(self, repository):
        """Test storing multiple chat messages"""
        messages = [
            ("Hi", "Hello!"),
            ("How are you?", "I'm doing well, thank you!"),
            ("What's the weather?", "I'd need more information to check the weather.")
        ]
        
        # Store all messages
        for user_msg, assistant_msg in messages:
            repository.store_chat_message(user_msg, assistant_msg)
        
        # Retrieve all messages
        history = repository.get_chat_history(limit=10)
        
        assert len(history) == 3
        # Check that messages are in chronological order (oldest first)
        for i, (expected_user, expected_assistant) in enumerate(messages):
            assert history[i]['user_message'] == expected_user
            assert history[i]['assistant_response'] == expected_assistant
    
    def test_chat_history_chronological_order(self, repository):
        """Test that chat history is returned in chronological order"""
        # Store messages with a small delay to ensure different timestamps
        import time
        
        repository.store_chat_message("First message", "First response")
        time.sleep(0.01)  # Small delay
        repository.store_chat_message("Second message", "Second response")
        time.sleep(0.01)  # Small delay
        repository.store_chat_message("Third message", "Third response")
        
        history = repository.get_chat_history()
        
        assert len(history) == 3
        assert history[0]['user_message'] == "First message"
        assert history[1]['user_message'] == "Second message"
        assert history[2]['user_message'] == "Third message"
        
        # Verify timestamps are in ascending order
        timestamps = [message['timestamp'] for message in history]
        assert timestamps == sorted(timestamps)
    
    def test_chat_history_limit(self, repository):
        """Test that the limit parameter works correctly"""
        # Store 5 messages
        for i in range(5):
            repository.store_chat_message(f"Message {i+1}", f"Response {i+1}")
        
        # Test different limits
        history_2 = repository.get_chat_history(limit=2)
        assert len(history_2) == 2
        assert history_2[0]['user_message'] == "Message 4"  # Second most recent (chronological order)
        assert history_2[1]['user_message'] == "Message 5"  # Most recent
        
        history_3 = repository.get_chat_history(limit=3)
        assert len(history_3) == 3
        assert history_3[0]['user_message'] == "Message 3"
        assert history_3[1]['user_message'] == "Message 4"
        assert history_3[2]['user_message'] == "Message 5"
        
        # Test limit larger than available messages
        history_10 = repository.get_chat_history(limit=10)
        assert len(history_10) == 5
    
    def test_empty_chat_history(self, repository):
        """Test retrieving chat history when no messages exist"""
        history = repository.get_chat_history()
        assert history == []
    
    def test_store_long_messages(self, repository):
        """Test storing and retrieving long messages"""
        long_user_msg = "This is a very long user message. " * 100
        long_assistant_msg = "This is a very long assistant response. " * 100
        
        repository.store_chat_message(long_user_msg, long_assistant_msg)
        history = repository.get_chat_history(limit=1)
        
        assert len(history) == 1
        assert history[0]['user_message'] == long_user_msg
        assert history[0]['assistant_response'] == long_assistant_msg
    
    def test_store_messages_with_special_characters(self, repository):
        """Test storing messages with special characters"""
        special_user_msg = "Hello! 你好! Здравствуй! مرحبا! 🌟🚀💻"
        special_assistant_msg = "Greetings in many languages! 🌍✨"
        
        repository.store_chat_message(special_user_msg, special_assistant_msg)
        history = repository.get_chat_history(limit=1)
        
        assert len(history) == 1
        assert history[0]['user_message'] == special_user_msg
        assert history[0]['assistant_response'] == special_assistant_msg


@pytest.mark.asyncio
class TestAsyncChatOperations:
    """Test asynchronous chat operations"""
    
    async def test_async_store_and_retrieve_message(self, repository):
        """Test async storing and retrieving chat messages"""
        user_msg = "Async hello!"
        assistant_msg = "Async response!"
        
        await repository.async_store_chat_message(user_msg, assistant_msg)
        history = await repository.async_get_chat_history(limit=1)
        
        assert len(history) == 1
        message = history[0]
        assert message['user_message'] == user_msg
        assert message['assistant_response'] == assistant_msg
        assert 'id' in message
        assert 'timestamp' in message
    
    async def test_async_multiple_messages(self, repository):
        """Test async operations with multiple messages"""
        messages = [
            ("Async message 1", "Async response 1"),
            ("Async message 2", "Async response 2"),
            ("Async message 3", "Async response 3")
        ]
        
        # Store all messages asynchronously
        for user_msg, assistant_msg in messages:
            await repository.async_store_chat_message(user_msg, assistant_msg)
        
        # Retrieve all messages asynchronously
        history = await repository.async_get_chat_history(limit=10)
        
        assert len(history) == 3
        for i, (expected_user, expected_assistant) in enumerate(messages):
            assert history[i]['user_message'] == expected_user
            assert history[i]['assistant_response'] == expected_assistant
    
    async def test_async_chat_history_limit(self, repository):
        """Test async chat history with limit"""
        # Store multiple messages
        for i in range(4):
            await repository.async_store_chat_message(f"Async {i+1}", f"Response {i+1}")
        
        # Test limit
        history = await repository.async_get_chat_history(limit=2)
        assert len(history) == 2
        assert history[0]['user_message'] == "Async 3"  # Second most recent in chronological order
        assert history[1]['user_message'] == "Async 4"  # Most recent
    
    async def test_async_empty_history(self, repository):
        """Test async retrieval of empty chat history"""
        history = await repository.async_get_chat_history()
        assert history == []


class TestMixedSyncAsyncOperations:
    """Test interaction between sync and async operations"""
    
    def test_sync_store_async_retrieve(self, repository):
        """Test storing with sync method and retrieving with async method"""
        user_msg = "Sync stored message"
        assistant_msg = "Sync stored response"
        
        # Store with sync method
        repository.store_chat_message(user_msg, assistant_msg)
        
        # Retrieve with async method
        async def async_get():
            return await repository.async_get_chat_history(limit=1)
        
        history = asyncio.run(async_get())
        assert len(history) == 1
        assert history[0]['user_message'] == user_msg
        assert history[0]['assistant_response'] == assistant_msg
    
    def test_async_store_sync_retrieve(self, repository):
        """Test storing with async method and retrieving with sync method"""
        user_msg = "Async stored message"
        assistant_msg = "Async stored response"
        
        # Store with async method
        async def async_store():
            await repository.async_store_chat_message(user_msg, assistant_msg)
        
        asyncio.run(async_store())
        
        # Retrieve with sync method
        history = repository.get_chat_history(limit=1)
        assert len(history) == 1
        assert history[0]['user_message'] == user_msg
        assert history[0]['assistant_response'] == assistant_msg
    
    def test_mixed_operations_ordering(self, repository):
        """Test that sync and async operations maintain proper ordering"""
        # Store messages using both sync and async methods
        repository.store_chat_message("Sync 1", "Sync Response 1")
        
        async def store_async():
            await repository.async_store_chat_message("Async 1", "Async Response 1")
        asyncio.run(store_async())
        
        repository.store_chat_message("Sync 2", "Sync Response 2")
        
        # Retrieve and verify ordering
        history = repository.get_chat_history()
        assert len(history) == 3
        assert history[0]['user_message'] == "Sync 1"
        assert history[1]['user_message'] == "Async 1"
        assert history[2]['user_message'] == "Sync 2"


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_empty_message_handling(self, repository):
        """Test handling of empty messages"""
        repository.store_chat_message("", "Response to empty message")
        repository.store_chat_message("User message", "")
        repository.store_chat_message("", "")
        
        history = repository.get_chat_history()
        assert len(history) == 3
        assert history[0]['user_message'] == ""
        assert history[0]['assistant_response'] == "Response to empty message"
        assert history[1]['user_message'] == "User message"
        assert history[1]['assistant_response'] == ""
        assert history[2]['user_message'] == ""
        assert history[2]['assistant_response'] == ""
    
    def test_zero_limit(self, repository):
        """Test get_chat_history with zero limit"""
        repository.store_chat_message("Test", "Test response")
        history = repository.get_chat_history(limit=0)
        assert history == []
    
    def test_negative_limit(self, repository):
        """Test get_chat_history with negative limit"""
        repository.store_chat_message("Test", "Test response")
        # SQLite should handle negative limits gracefully
        history = repository.get_chat_history(limit=-1)
        # Behavior may vary, but should not crash
        assert isinstance(history, list)


class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    def test_message_id_auto_increment(self, repository):
        """Test that message IDs are properly auto-incremented"""
        repository.store_chat_message("Message 1", "Response 1")
        repository.store_chat_message("Message 2", "Response 2")
        repository.store_chat_message("Message 3", "Response 3")
        
        history = repository.get_chat_history()
        assert len(history) == 3
        
        # IDs should be sequential and unique
        ids = [message['id'] for message in history]
        assert len(set(ids)) == 3  # All unique
        assert ids == sorted(ids)  # Sequential order
    
    def test_timestamp_consistency(self, repository):
        """Test that timestamps are consistent and properly formatted"""
        import time
        
        start_time = time.time()
        repository.store_chat_message("Time test", "Time response")
        end_time = time.time()
        
        history = repository.get_chat_history(limit=1)
        assert len(history) == 1
        
        timestamp_str = history[0]['timestamp']
        assert isinstance(timestamp_str, str)
        assert len(timestamp_str) > 0
        
        # Timestamp should be within the time window of the test
        # (This is a basic sanity check)
        assert timestamp_str is not None


class TestBackwardCompatibility:
    """Test backward compatibility with original DatabaseService"""
    
    def test_method_signatures_match(self, repository):
        """Verify method signatures match the interface"""
        import inspect
        from core.repositories.interfaces import IChatRepository
        
        # Get all methods from the interface
        interface_methods = inspect.getmembers(IChatRepository, predicate=inspect.isfunction)
        
        for method_name, method in interface_methods:
            if method_name.startswith('_'):
                continue
                
            # Check that repository has the method
            assert hasattr(repository, method_name), f"Repository missing method: {method_name}"
            
            # Check signature compatibility
            interface_sig = inspect.signature(method)
            repo_method = getattr(repository.__class__, method_name)
            repo_sig = inspect.signature(repo_method)
            
            # Parameters should match (excluding 'self')
            interface_params = list(interface_sig.parameters.keys())[1:]  # Skip 'self'
            repo_params = list(repo_sig.parameters.keys())[1:]  # Skip 'self'
            
            assert interface_params == repo_params, f"Parameter mismatch in {method_name}: {interface_params} vs {repo_params}"
    
    def test_output_format_compatibility(self, repository):
        """Test that output format matches original DatabaseService expectations"""
        repository.store_chat_message("Test user message", "Test assistant response")
        history = repository.get_chat_history(limit=1)
        
        assert len(history) == 1
        message = history[0]
        
        # Verify expected keys are present
        expected_keys = {'id', 'user_message', 'assistant_response', 'timestamp'}
        assert set(message.keys()) == expected_keys
        
        # Verify data types
        assert isinstance(message['id'], int)
        assert isinstance(message['user_message'], str)
        assert isinstance(message['assistant_response'], str)
        assert isinstance(message['timestamp'], str)
    
    def test_default_limit_behavior(self, repository):
        """Test that default limit matches original behavior"""
        # Store more than 50 messages to test the default limit of 50
        for i in range(55):
            repository.store_chat_message(f"Message {i+1}", f"Response {i+1}")
        
        # Test default limit (should be 50)
        history_default = repository.get_chat_history()
        assert len(history_default) == 50
        
        # Should get the most recent 50 messages in chronological order
        assert history_default[0]['user_message'] == "Message 6"  # 55 - 50 + 1
        assert history_default[-1]['user_message'] == "Message 55"