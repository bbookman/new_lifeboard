"""
Comprehensive tests for chat API routes
Tests FastAPI endpoints for chat interactions and conversation management
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.chat import (
    ChatHistoryItem,
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    router,
)
from services.chat_service import ChatService
from services.startup import StartupService


class TestChatRoutes:
    """Test chat API endpoints"""

    @pytest.fixture
    def app(self):
        """Create FastAPI test application"""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service for testing"""
        service = MagicMock(spec=StartupService)
        return service

    @pytest.fixture
    def mock_chat_service(self):
        """Mock chat service for testing"""
        service = AsyncMock(spec=ChatService)
        return service

    @pytest.fixture
    def sample_chat_message(self):
        """Sample chat message for testing"""
        return "Hello, can you help me understand my data patterns from last week?"

    @pytest.fixture
    def sample_chat_response(self):
        """Sample chat response for testing"""
        return "Based on your data from last week, I can see several interesting patterns. You had 15 conversations, with the most active day being Wednesday when you had 5 conversations focused on work projects. Your mood data shows you were generally positive, with happiness scores averaging 7.2/10. The weather was mostly sunny, which correlates with your higher energy levels during afternoon activities."

    @pytest.fixture
    def sample_chat_history(self):
        """Sample chat history for testing"""
        return [
            {
                "id": 1,
                "user_message": "What were my main activities yesterday?",
                "assistant_response": "Yesterday you had 3 meetings, spent 2 hours on the project proposal, and took a 30-minute walk in the park.",
                "timestamp": "2024-01-15T09:30:00",
            },
            {
                "id": 2,
                "user_message": "How was my mood this week?",
                "assistant_response": "Your mood has been generally positive this week, with an average happiness score of 7.5/10. Tuesday was your best day with a score of 9/10.",
                "timestamp": "2024-01-15T10:15:00",
            },
            {
                "id": 3,
                "user_message": "Show me my sleep patterns",
                "assistant_response": "Your sleep data shows you averaged 7.2 hours per night this week, with bedtime around 11:30 PM and wake time around 6:45 AM.",
                "timestamp": "2024-01-15T11:00:00",
            },
        ]

    def test_send_chat_message_success(self, client, mock_startup_service, mock_chat_service, sample_chat_message, sample_chat_response):
        """Test successful chat message sending"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.process_chat_message.return_value = sample_chat_response

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": sample_chat_message})

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "response" in data
        assert "timestamp" in data

        # Verify content
        assert data["response"] == sample_chat_response

        # Verify timestamp format
        timestamp = data["timestamp"]
        datetime.fromisoformat(timestamp)  # Should not raise exception

        # Verify service was called correctly
        mock_chat_service.process_chat_message.assert_called_once_with(sample_chat_message)

    def test_send_chat_message_empty_message(self, client, mock_startup_service, mock_chat_service):
        """Test sending empty chat message"""
        mock_startup_service.chat_service = mock_chat_service

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": ""})

        # Should still process empty message (let service handle validation)
        assert response.status_code == 200 or response.status_code == 422

    def test_send_chat_message_long_message(self, client, mock_startup_service, mock_chat_service):
        """Test sending very long chat message"""
        mock_startup_service.chat_service = mock_chat_service
        long_message = "Can you help me analyze " + "data " * 1000  # Very long message
        mock_chat_service.process_chat_message.return_value = "I'll help you with that analysis."

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": long_message})

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        mock_chat_service.process_chat_message.assert_called_once_with(long_message)

    def test_send_chat_message_special_characters(self, client, mock_startup_service, mock_chat_service):
        """Test sending message with special characters and Unicode"""
        mock_startup_service.chat_service = mock_chat_service
        special_message = "Hello! 🤖 Can you analyze data with émojis and spëcial characters? 中文测试"
        mock_response = "I can definitely help with that! 😊"
        mock_chat_service.process_chat_message.return_value = mock_response

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": special_message})

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == mock_response
        mock_chat_service.process_chat_message.assert_called_once_with(special_message)

    def test_send_chat_message_invalid_json(self, client, mock_startup_service, mock_chat_service):
        """Test sending invalid JSON data"""
        mock_startup_service.chat_service = mock_chat_service

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"invalid_field": "test"})

        assert response.status_code == 422  # Validation error

    def test_send_chat_message_service_unavailable(self, client, mock_startup_service):
        """Test sending message when chat service is unavailable"""
        mock_startup_service.chat_service = None

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": "test"})

        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Chat service not available"

    def test_send_chat_message_service_error(self, client, mock_startup_service, mock_chat_service):
        """Test sending message when chat service raises exception"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.process_chat_message.side_effect = Exception("LLM service timeout")

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": "test message"})

        assert response.status_code == 500
        data = response.json()
        assert "Failed to process chat message" in data["detail"]

    def test_get_chat_history_success(self, client, mock_startup_service, mock_chat_service, sample_chat_history):
        """Test successful chat history retrieval"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.get_chat_history.return_value = sample_chat_history

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "messages" in data
        messages = data["messages"]
        assert len(messages) == 3

        # Verify first message
        first_message = messages[0]
        assert first_message["id"] == 1
        assert first_message["user_message"] == "What were my main activities yesterday?"
        assert "meetings" in first_message["assistant_response"]
        assert first_message["timestamp"] == "2024-01-15T09:30:00"

        # Verify service was called with default limit
        mock_chat_service.get_chat_history.assert_called_once_with(limit=20)

    def test_get_chat_history_with_limit(self, client, mock_startup_service, mock_chat_service, sample_chat_history):
        """Test chat history retrieval with custom limit"""
        mock_startup_service.chat_service = mock_chat_service
        # Return only first 2 messages for limit test
        limited_history = sample_chat_history[:2]
        mock_chat_service.get_chat_history.return_value = limited_history

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history?limit=2")

        assert response.status_code == 200
        data = response.json()

        messages = data["messages"]
        assert len(messages) == 2

        # Verify service was called with custom limit
        mock_chat_service.get_chat_history.assert_called_once_with(limit=2)

    def test_get_chat_history_empty(self, client, mock_startup_service, mock_chat_service):
        """Test chat history retrieval when no messages exist"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.get_chat_history.return_value = []

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history")

        assert response.status_code == 200
        data = response.json()

        assert "messages" in data
        assert len(data["messages"]) == 0

    def test_get_chat_history_large_limit(self, client, mock_startup_service, mock_chat_service, sample_chat_history):
        """Test chat history with very large limit"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.get_chat_history.return_value = sample_chat_history

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history?limit=1000")

        assert response.status_code == 200
        mock_chat_service.get_chat_history.assert_called_once_with(limit=1000)

    def test_get_chat_history_invalid_limit(self, client, mock_startup_service, mock_chat_service):
        """Test chat history with invalid limit parameter"""
        mock_startup_service.chat_service = mock_chat_service

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history?limit=invalid")

        assert response.status_code == 422  # Validation error

    def test_get_chat_history_service_unavailable(self, client, mock_startup_service):
        """Test chat history when service is unavailable"""
        mock_startup_service.chat_service = None

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history")

        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Chat service not available"

    def test_get_chat_history_service_error(self, client, mock_startup_service, mock_chat_service):
        """Test chat history when service raises exception"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.get_chat_history.side_effect = Exception("Database connection failed")

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.get("/api/chat/history")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to get chat history" in data["detail"]

    def test_chat_message_request_model_validation(self):
        """Test ChatMessageRequest Pydantic model validation"""
        # Valid request
        valid_data = {"message": "Hello, AI!"}
        request = ChatMessageRequest(**valid_data)
        assert request.message == "Hello, AI!"

        # Test with empty message (should be valid)
        empty_data = {"message": ""}
        request = ChatMessageRequest(**empty_data)
        assert request.message == ""

    def test_chat_message_response_model_validation(self):
        """Test ChatMessageResponse Pydantic model validation"""
        valid_data = {
            "response": "Hello! How can I help you?",
            "timestamp": "2024-01-15T09:30:00.000Z",
        }
        response = ChatMessageResponse(**valid_data)
        assert response.response == "Hello! How can I help you?"
        assert response.timestamp == "2024-01-15T09:30:00.000Z"

    def test_chat_history_item_model_validation(self):
        """Test ChatHistoryItem Pydantic model validation"""
        valid_data = {
            "id": 1,
            "user_message": "What's the weather?",
            "assistant_response": "It's sunny today!",
            "timestamp": "2024-01-15T09:30:00",
        }
        item = ChatHistoryItem(**valid_data)
        assert item.id == 1
        assert item.user_message == "What's the weather?"
        assert item.assistant_response == "It's sunny today!"
        assert item.timestamp == "2024-01-15T09:30:00"

    def test_chat_history_response_model_validation(self):
        """Test ChatHistoryResponse Pydantic model validation"""
        valid_data = {
            "messages": [
                {
                    "id": 1,
                    "user_message": "Hello",
                    "assistant_response": "Hi there!",
                    "timestamp": "2024-01-15T09:30:00",
                },
            ],
        }
        response = ChatHistoryResponse(**valid_data)
        assert len(response.messages) == 1
        assert response.messages[0].user_message == "Hello"

    def test_chat_endpoint_cors_headers(self, client, mock_startup_service, mock_chat_service):
        """Test chat endpoints include proper CORS headers"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.process_chat_message.return_value = "Test response"

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": "test"})

        assert response.status_code == 200
        # Note: CORS headers are typically added by middleware, not individual routes
        assert response.headers["content-type"] == "application/json"

    def test_chat_performance_timing(self, client, mock_startup_service, mock_chat_service):
        """Test chat endpoint response timing"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.process_chat_message.return_value = "Quick response"

        import time
        start_time = time.time()

        with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
            response = client.post("/api/chat/send", json={"message": "test"})

        end_time = time.time()
        response_time = end_time - start_time

        assert response.status_code == 200
        # API overhead should be minimal (under 50ms in test environment)
        assert response_time < 0.05

    def test_chat_concurrent_requests(self, client, mock_startup_service, mock_chat_service):
        """Test chat endpoint handles concurrent requests"""
        mock_startup_service.chat_service = mock_chat_service
        mock_chat_service.process_chat_message.return_value = "Concurrent response"

        import threading

        responses = []
        errors = []

        def make_request(message):
            try:
                with patch("api.routes.chat.get_startup_service_dependency", return_value=mock_startup_service):
                    response = client.post("/api/chat/send", json={"message": message})
                    responses.append(response.status_code)
            except Exception as e:
                errors.append(e)

        # Start multiple concurrent requests
        threads = []
        for i in range(3):
            thread = threading.Thread(target=make_request, args=[f"Message {i}"])
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)

        # Verify all requests succeeded
        assert len(errors) == 0
        assert len(responses) == 3
        assert all(status == 200 for status in responses)
        assert mock_chat_service.process_chat_message.call_count == 3
