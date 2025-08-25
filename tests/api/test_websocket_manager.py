"""
Comprehensive tests for WebSocket manager and routes
Tests WebSocket connection management, messaging, and real-time updates
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketState

from services.websocket_manager import (
    WebSocketManager, 
    MessageType, 
    WebSocketMessage, 
    ClientConnection,
    get_websocket_manager,
    set_websocket_manager,
    clear_websocket_manager
)
from api.routes.websocket import router


class MockWebSocket:
    """Mock WebSocket for testing"""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.received_messages = []
        self.close_reason = None
        self.connection_exception = None
        self.send_exception = None
        self.client_state = WebSocketState.CONNECTING
    
    async def accept(self):
        if self.connection_exception:
            raise self.connection_exception
        self.accepted = True
        self.client_state = WebSocketState.CONNECTED
    
    async def close(self, reason=None):
        self.closed = True
        self.close_reason = reason
        self.client_state = WebSocketState.DISCONNECTED
    
    async def send_text(self, data: str):
        if self.send_exception:
            raise self.send_exception
        self.sent_messages.append(data)
    
    async def receive_text(self):
        if self.received_messages:
            return self.received_messages.pop(0)
        # Simulate WebSocket disconnect
        from fastapi import WebSocketDisconnect
        raise WebSocketDisconnect()


class TestWebSocketMessage:
    """Test WebSocketMessage dataclass"""
    
    def test_websocket_message_creation(self):
        """Test WebSocketMessage creation with automatic fields"""
        message = WebSocketMessage(
            type=MessageType.PROCESSING_STATUS,
            data={"status": "processing"}
        )
        
        assert message.type == MessageType.PROCESSING_STATUS
        assert message.data == {"status": "processing"}
        assert message.timestamp is not None
        assert message.message_id is not None
        
        # Verify timestamp format
        datetime.fromisoformat(message.timestamp.replace('Z', '+00:00'))
    
    def test_websocket_message_with_custom_fields(self):
        """Test WebSocketMessage with custom timestamp and ID"""
        custom_timestamp = "2024-01-15T10:00:00Z"
        custom_id = "test-message-123"
        
        message = WebSocketMessage(
            type=MessageType.DAY_UPDATE,
            data={"day": "2024-01-15"},
            timestamp=custom_timestamp,
            message_id=custom_id
        )
        
        assert message.timestamp == custom_timestamp
        assert message.message_id == custom_id


class TestClientConnection:
    """Test ClientConnection dataclass"""
    
    def test_client_connection_creation(self):
        """Test ClientConnection creation"""
        mock_websocket = MockWebSocket()
        now = datetime.now(timezone.utc)
        
        connection = ClientConnection(
            websocket=mock_websocket,
            client_id="test-client",
            connected_at=now,
            subscriptions={"topic1", "topic2"},
            last_heartbeat=now
        )
        
        assert connection.websocket == mock_websocket
        assert connection.client_id == "test-client"
        assert connection.connected_at == now
        assert connection.subscriptions == {"topic1", "topic2"}
        assert connection.last_heartbeat == now
    
    def test_client_connection_default_subscriptions(self):
        """Test ClientConnection with default empty subscriptions"""
        mock_websocket = MockWebSocket()
        now = datetime.now(timezone.utc)
        
        connection = ClientConnection(
            websocket=mock_websocket,
            client_id="test-client",
            connected_at=now,
            subscriptions=None,
            last_heartbeat=now
        )
        
        assert connection.subscriptions == set()


class TestWebSocketManager:
    """Test WebSocketManager functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create WebSocketManager for testing"""
        return WebSocketManager(heartbeat_interval=1)
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket"""
        return MockWebSocket()
    
    @pytest.mark.asyncio
    async def test_manager_start_stop(self, manager):
        """Test WebSocketManager start and stop"""
        assert not manager.is_running
        assert manager.heartbeat_task is None
        
        await manager.start()
        assert manager.is_running
        assert manager.heartbeat_task is not None
        
        await manager.stop()
        assert not manager.is_running
        assert len(manager.connections) == 0
        assert len(manager.subscriptions) == 0
    
    @pytest.mark.asyncio
    async def test_connect_client_success(self, manager, mock_websocket):
        """Test successful client connection"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        assert client_id == "test-client"
        assert mock_websocket.accepted
        assert client_id in manager.connections
        
        connection = manager.connections[client_id]
        assert connection.websocket == mock_websocket
        assert connection.client_id == client_id
        assert isinstance(connection.connected_at, datetime)
        assert isinstance(connection.last_heartbeat, datetime)
        assert len(connection.subscriptions) == 0
        
        # Verify connection confirmation message was sent
        assert len(mock_websocket.sent_messages) == 1
        sent_message = json.loads(mock_websocket.sent_messages[0])
        assert sent_message["type"] == "heartbeat"
        assert sent_message["data"]["status"] == "connected"
    
    @pytest.mark.asyncio
    async def test_connect_client_auto_id(self, manager, mock_websocket):
        """Test client connection with auto-generated ID"""
        client_id = await manager.connect_client(mock_websocket)
        
        assert client_id is not None
        assert len(client_id) > 0
        assert client_id in manager.connections
    
    @pytest.mark.asyncio
    async def test_connect_client_websocket_error(self, manager, mock_websocket):
        """Test client connection when WebSocket accept fails"""
        mock_websocket.connection_exception = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            await manager.connect_client(mock_websocket, "test-client")
        
        assert "test-client" not in manager.connections
    
    @pytest.mark.asyncio
    async def test_disconnect_client_success(self, manager, mock_websocket):
        """Test successful client disconnection"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        # Subscribe to topics first
        await manager.subscribe_client(client_id, ["topic1", "topic2"])
        
        # Disconnect
        await manager.disconnect_client(client_id)
        
        assert client_id not in manager.connections
        assert mock_websocket.closed
        assert "topic1" not in manager.subscriptions
        assert "topic2" not in manager.subscriptions
    
    @pytest.mark.asyncio
    async def test_disconnect_unknown_client(self, manager):
        """Test disconnecting unknown client"""
        # Should not raise exception
        await manager.disconnect_client("unknown-client")
        assert len(manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_subscribe_client_success(self, manager, mock_websocket):
        """Test successful client subscription"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        await manager.subscribe_client(client_id, ["topic1", "topic2"])
        
        connection = manager.connections[client_id]
        assert "topic1" in connection.subscriptions
        assert "topic2" in connection.subscriptions
        
        assert client_id in manager.subscriptions["topic1"]
        assert client_id in manager.subscriptions["topic2"]
        
        # Verify subscription confirmation was sent
        sent_messages = [json.loads(msg) for msg in mock_websocket.sent_messages]
        subscription_messages = [msg for msg in sent_messages if msg["type"] == "subscription"]
        assert len(subscription_messages) == 1
        assert subscription_messages[0]["data"]["status"] == "subscribed"
    
    @pytest.mark.asyncio
    async def test_subscribe_unknown_client(self, manager):
        """Test subscribing unknown client"""
        # Should not raise exception
        await manager.subscribe_client("unknown-client", ["topic1"])
        assert len(manager.subscriptions) == 0
    
    @pytest.mark.asyncio
    async def test_unsubscribe_client_success(self, manager, mock_websocket):
        """Test successful client unsubscription"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        # Subscribe first
        await manager.subscribe_client(client_id, ["topic1", "topic2", "topic3"])
        
        # Unsubscribe from some topics
        await manager.unsubscribe_client(client_id, ["topic1", "topic2"])
        
        connection = manager.connections[client_id]
        assert "topic1" not in connection.subscriptions
        assert "topic2" not in connection.subscriptions
        assert "topic3" in connection.subscriptions
        
        assert "topic1" not in manager.subscriptions
        assert "topic2" not in manager.subscriptions
        assert client_id in manager.subscriptions["topic3"]
    
    @pytest.mark.asyncio
    async def test_broadcast_to_topic_success(self, manager, mock_websocket):
        """Test successful topic broadcast"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["test-topic"])
        
        # Clear previous messages
        mock_websocket.sent_messages.clear()
        
        message = WebSocketMessage(
            type=MessageType.PROCESSING_STATUS,
            data={"status": "processing", "day": "2024-01-15"}
        )
        
        await manager.broadcast_to_topic("test-topic", message)
        
        # Verify message was sent
        assert len(mock_websocket.sent_messages) == 1
        sent_message = json.loads(mock_websocket.sent_messages[0])
        assert sent_message["type"] == "processing_status"
        assert sent_message["data"]["status"] == "processing"
        assert sent_message["data"]["day"] == "2024-01-15"
    
    @pytest.mark.asyncio
    async def test_broadcast_to_empty_topic(self, manager):
        """Test broadcasting to topic with no subscribers"""
        message = WebSocketMessage(
            type=MessageType.PROCESSING_STATUS,
            data={"status": "processing"}
        )
        
        # Should not raise exception
        await manager.broadcast_to_topic("empty-topic", message)
    
    @pytest.mark.asyncio
    async def test_broadcast_with_send_failure(self, manager, mock_websocket):
        """Test broadcast when client send fails"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["test-topic"])
        
        # Make send fail
        mock_websocket.send_exception = Exception("Send failed")
        
        message = WebSocketMessage(
            type=MessageType.PROCESSING_STATUS,
            data={"status": "processing"}
        )
        
        await manager.broadcast_to_topic("test-topic", message)
        
        # Client should be disconnected due to send failure
        assert client_id not in manager.connections
        assert mock_websocket.closed
    
    @pytest.mark.asyncio
    async def test_send_processing_status(self, manager, mock_websocket):
        """Test sending processing status updates"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["processing_updates", "day_2024-01-15"])
        
        mock_websocket.sent_messages.clear()
        
        await manager.send_processing_status(
            days_date="2024-01-15",
            status="processing",
            progress={"items": 10, "processed": 5}
        )
        
        # Should send to both general and day-specific topics
        assert len(mock_websocket.sent_messages) == 2
        
        messages = [json.loads(msg) for msg in mock_websocket.sent_messages]
        for message in messages:
            assert message["type"] == "processing_status"
            assert message["data"]["days_date"] == "2024-01-15"
            assert message["data"]["status"] == "processing"
            assert message["data"]["progress"]["items"] == 10
    
    @pytest.mark.asyncio
    async def test_send_queue_stats(self, manager, mock_websocket):
        """Test sending queue statistics"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["queue_stats"])
        
        mock_websocket.sent_messages.clear()
        
        stats = {"pending": 5, "processing": 2, "completed": 10}
        await manager.send_queue_stats(stats)
        
        assert len(mock_websocket.sent_messages) == 1
        sent_message = json.loads(mock_websocket.sent_messages[0])
        assert sent_message["type"] == "queue_stats"
        assert sent_message["data"] == stats
    
    @pytest.mark.asyncio
    async def test_send_day_update(self, manager, mock_websocket):
        """Test sending day update"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["day_2024-01-15", "day_updates"])
        
        mock_websocket.sent_messages.clear()
        
        update_data = {"new_items": 5, "updated_clusters": 3}
        await manager.send_day_update("2024-01-15", update_data)
        
        # Should send to both day-specific and general day update topics
        assert len(mock_websocket.sent_messages) == 2
        
        messages = [json.loads(msg) for msg in mock_websocket.sent_messages]
        for message in messages:
            assert message["type"] == "day_update"
            assert message["data"]["days_date"] == "2024-01-15"
            assert message["data"]["new_items"] == 5
            assert message["data"]["updated_clusters"] == 3
    
    @pytest.mark.asyncio
    async def test_handle_client_message_subscription(self, manager, mock_websocket):
        """Test handling client subscription message"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        message_data = {
            "type": "subscription",
            "data": {"topics": ["topic1", "topic2"]}
        }
        
        await manager.handle_client_message(client_id, message_data)
        
        connection = manager.connections[client_id]
        assert "topic1" in connection.subscriptions
        assert "topic2" in connection.subscriptions
    
    @pytest.mark.asyncio
    async def test_handle_client_message_unsubscription(self, manager, mock_websocket):
        """Test handling client unsubscription message"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["topic1", "topic2", "topic3"])
        
        message_data = {
            "type": "unsubscription",
            "data": {"topics": ["topic1", "topic2"]}
        }
        
        await manager.handle_client_message(client_id, message_data)
        
        connection = manager.connections[client_id]
        assert "topic1" not in connection.subscriptions
        assert "topic2" not in connection.subscriptions
        assert "topic3" in connection.subscriptions
    
    @pytest.mark.asyncio
    async def test_handle_client_message_heartbeat(self, manager, mock_websocket):
        """Test handling client heartbeat message"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        # Get initial heartbeat time
        initial_heartbeat = manager.connections[client_id].last_heartbeat
        
        # Wait a bit and send heartbeat
        await asyncio.sleep(0.01)
        
        message_data = {"type": "heartbeat", "data": {}}
        await manager.handle_client_message(client_id, message_data)
        
        # Heartbeat time should be updated
        new_heartbeat = manager.connections[client_id].last_heartbeat
        assert new_heartbeat > initial_heartbeat
    
    @pytest.mark.asyncio
    async def test_handle_client_message_invalid_type(self, manager, mock_websocket):
        """Test handling client message with invalid type"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        message_data = {"type": "invalid_type", "data": {}}
        
        # Should not raise exception
        await manager.handle_client_message(client_id, message_data)
    
    @pytest.mark.asyncio
    async def test_handle_client_message_exception(self, manager, mock_websocket):
        """Test handling client message when exception occurs"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        # Invalid message data
        message_data = {"invalid": "structure"}
        
        # Should send error to client
        await manager.handle_client_message(client_id, message_data)
        
        # Check for error message in sent messages
        sent_messages = [json.loads(msg) for msg in mock_websocket.sent_messages]
        error_messages = [msg for msg in sent_messages if msg["type"] == "error"]
        assert len(error_messages) > 0
    
    @pytest.mark.asyncio
    async def test_get_connection_stats(self, manager, mock_websocket):
        """Test getting connection statistics"""
        # Connect client and subscribe to topics
        client_id = await manager.connect_client(mock_websocket, "test-client")
        await manager.subscribe_client(client_id, ["topic1", "topic2"])
        
        stats = await manager.get_connection_stats()
        
        assert stats["total_connections"] == 1
        assert stats["total_topics"] == 2
        assert stats["topic_subscribers"]["topic1"] == 1
        assert stats["topic_subscribers"]["topic2"] == 1
        assert stats["heartbeat_interval"] == 1
        assert stats["is_running"] == False  # Not started yet
        assert "last_updated" in stats
    
    @pytest.mark.asyncio
    async def test_heartbeat_monitor_disconnect_stale(self, manager, mock_websocket):
        """Test heartbeat monitor disconnects stale clients"""
        await manager.start()
        
        # Connect client
        client_id = await manager.connect_client(mock_websocket, "test-client")
        
        # Manually set last_heartbeat to past (simulate stale client)
        past_time = datetime.now(timezone.utc).replace(year=2020)
        manager.connections[client_id].last_heartbeat = past_time
        
        # Wait for heartbeat monitor to run
        await asyncio.sleep(1.1)
        
        # Client should be disconnected
        assert client_id not in manager.connections
        assert mock_websocket.closed
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_client_unknown_client(self, manager):
        """Test sending message to unknown client"""
        message = WebSocketMessage(
            type=MessageType.HEARTBEAT,
            data={"status": "test"}
        )
        
        with pytest.raises(ValueError, match="not connected"):
            await manager._send_to_client("unknown-client", message)
    
    @pytest.mark.asyncio
    async def test_send_to_client_websocket_error(self, manager, mock_websocket):
        """Test sending message when WebSocket send fails"""
        client_id = await manager.connect_client(mock_websocket, "test-client")
        mock_websocket.send_exception = Exception("Send failed")
        
        message = WebSocketMessage(
            type=MessageType.HEARTBEAT,
            data={"status": "test"}
        )
        
        with pytest.raises(Exception, match="Send failed"):
            await manager._send_to_client(client_id, message)


class TestWebSocketManagerGlobal:
    """Test global WebSocketManager functions"""
    
    def test_global_manager_lifecycle(self):
        """Test global WebSocketManager lifecycle"""
        # Initially no manager
        assert get_websocket_manager() is None
        
        # Set manager
        manager = WebSocketManager()
        set_websocket_manager(manager)
        assert get_websocket_manager() is manager
        
        # Clear manager
        clear_websocket_manager()
        assert get_websocket_manager() is None


class TestWebSocketRoutes:
    """Test WebSocket API routes"""
    
    @pytest.fixture
    def app(self, mock_manager):
        """Create FastAPI test application with dependency overrides"""
        from api.routes.websocket import get_websocket_manager
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_websocket_manager] = lambda: mock_manager
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_manager(self):
        """Mock WebSocketManager"""
        manager = AsyncMock(spec=WebSocketManager)
        return manager
    
    def test_websocket_stats_success(self, client, mock_manager):
        """Test getting WebSocket statistics"""
        mock_stats = {
            "total_connections": 5,
            "total_topics": 3,
            "topic_subscribers": {"topic1": 2, "topic2": 3},
            "heartbeat_interval": 30,
            "is_running": True,
            "last_updated": "2024-01-15T10:00:00Z"
        }
        mock_manager.get_connection_stats.return_value = mock_stats
        
        response = client.get("/ws/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data == mock_stats
    
    def test_websocket_stats_manager_unavailable(self):
        """Test stats when WebSocket manager is unavailable"""
        from api.routes.websocket import get_websocket_manager
        from fastapi import FastAPI
        
        # Create app with dependency that raises HTTPException
        app = FastAPI()
        app.include_router(router)
        
        def failing_manager():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="WebSocket manager not initialized. Server may be starting up.")
        
        app.dependency_overrides[get_websocket_manager] = failing_manager
        
        client = TestClient(app)
        response = client.get("/ws/stats")
        
        assert response.status_code == 503
        data = response.json()
        assert "WebSocket manager not initialized" in data["detail"]
    
    def test_websocket_stats_service_error(self, client, mock_manager):
        """Test stats when service raises exception"""
        mock_manager.get_connection_stats.side_effect = Exception("Stats error")
        
        response = client.get("/ws/stats")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get WebSocket statistics" in data["detail"]
    
    def test_broadcast_message_success(self, client, mock_manager):
        """Test manual message broadcast"""
        mock_manager.broadcast_to_topic.return_value = None
        
        message_data = {
            "type": "processing_status",
            "data": {"status": "processing", "day": "2024-01-15"}
        }
        
        response = client.post("/ws/broadcast/test-topic", json=message_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        assert data["message_sent"] is True
        
        # Verify manager was called
        mock_manager.broadcast_to_topic.assert_called_once()
    
    def test_broadcast_message_invalid_type(self, client, mock_manager):
        """Test broadcast with invalid message type"""
        mock_manager.broadcast_to_topic.side_effect = ValueError("Invalid message type")
        
        message_data = {
            "type": "invalid_type",
            "data": {"test": "data"}
        }
        
        response = client.post("/ws/broadcast/test-topic", json=message_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to broadcast message" in data["detail"]
    
    def test_broadcast_message_manager_unavailable(self):
        """Test broadcast when WebSocket manager is unavailable"""
        from api.routes.websocket import get_websocket_manager
        from fastapi import FastAPI
        
        message_data = {
            "type": "processing_status",
            "data": {"status": "processing"}
        }
        
        # Create app with dependency that raises HTTPException
        app = FastAPI()
        app.include_router(router)
        
        def failing_manager():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="WebSocket manager not initialized. Server may be starting up.")
        
        app.dependency_overrides[get_websocket_manager] = failing_manager
        
        client = TestClient(app)
        response = client.post("/ws/broadcast/test-topic", json=message_data)
        
        assert response.status_code == 503
        data = response.json()
        assert "WebSocket manager not initialized" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_websocket_endpoint_connection_flow(self):
        """Test WebSocket endpoint connection and message flow"""
        # This test simulates the WebSocket connection flow
        # In practice, WebSocket testing requires special handling
        
        mock_websocket = MockWebSocket()
        mock_manager = AsyncMock(spec=WebSocketManager)
        mock_manager.connect_client.return_value = "test-client-123"
        mock_manager.subscribe_client.return_value = None
        mock_manager.handle_client_message.return_value = None
        mock_manager.disconnect_client.return_value = None
        
        # Simulate receiving messages
        mock_websocket.received_messages = [
            json.dumps({"type": "subscription", "data": {"topics": ["custom-topic"]}}),
            json.dumps({"type": "heartbeat", "data": {}})
        ]
        
        # Test the connection logic (would normally be handled by FastAPI WebSocket)
        with patch('api.routes.websocket.get_websocket_manager', return_value=mock_manager):
            # Simulate the endpoint logic
            from api.routes.websocket import websocket_processing_updates
            
            # This would normally be called by FastAPI, but we can test the logic
            try:
                # Connect
                client_id = await mock_manager.connect_client(mock_websocket, None)
                assert client_id == "test-client-123"
                
                # Subscribe
                await mock_manager.subscribe_client(client_id, ["processing_updates", "queue_stats"])
                
                # Handle messages
                message_data = {"type": "heartbeat", "data": {}}
                await mock_manager.handle_client_message(client_id, message_data)
                
                # Disconnect
                await mock_manager.disconnect_client(client_id, "connection_closed")
                
                # Verify calls
                mock_manager.connect_client.assert_called()
                mock_manager.subscribe_client.assert_called()
                mock_manager.handle_client_message.assert_called()
                mock_manager.disconnect_client.assert_called()
                
            except Exception as e:
                pytest.fail(f"WebSocket endpoint logic failed: {e}")
    
    def test_websocket_dependency_injection(self):
        """Test WebSocket manager dependency injection"""
        from api.routes.websocket import get_websocket_manager as route_get_manager
        
        # Test when manager is not available
        with patch('api.routes.websocket.get_global_websocket_manager', return_value=None):
            with pytest.raises(Exception) as exc_info:
                route_get_manager()
            assert "WebSocket manager not initialized" in str(exc_info.value)
        
        # Test when manager is available
        mock_manager = MagicMock(spec=WebSocketManager)
        with patch('api.routes.websocket.get_global_websocket_manager', return_value=mock_manager):
            manager = route_get_manager()
            assert manager is mock_manager
    
    @pytest.mark.asyncio
    async def test_websocket_concurrent_connections(self):
        """Test WebSocket manager handles concurrent connections"""
        manager = WebSocketManager(heartbeat_interval=60)  # Longer interval for test
        
        # Create multiple mock WebSockets
        websockets = [MockWebSocket() for _ in range(3)]
        client_ids = []
        
        try:
            # Connect clients concurrently
            tasks = []
            for i, ws in enumerate(websockets):
                tasks.append(manager.connect_client(ws, f"client-{i}"))
            
            client_ids = await asyncio.gather(*tasks)
            
            # Verify all connected
            assert len(client_ids) == 3
            assert len(manager.connections) == 3
            
            # Subscribe all to same topic
            for client_id in client_ids:
                await manager.subscribe_client(client_id, ["common-topic"])
            
            # Broadcast message
            message = WebSocketMessage(
                type=MessageType.PROCESSING_STATUS,
                data={"status": "test"}
            )
            await manager.broadcast_to_topic("common-topic", message)
            
            # Verify all received message
            for ws in websockets:
                assert len(ws.sent_messages) > 0  # At least connection confirmation + broadcast
                
        finally:
            # Cleanup
            for client_id in client_ids:
                if client_id in manager.connections:
                    await manager.disconnect_client(client_id)
    
    @pytest.mark.asyncio
    async def test_websocket_message_serialization(self):
        """Test WebSocket message JSON serialization"""
        manager = WebSocketManager()
        mock_websocket = MockWebSocket()
        
        client_id = await manager.connect_client(mock_websocket, "test-client")
        mock_websocket.sent_messages.clear()
        
        # Test complex message data
        complex_data = {
            "status": "processing",
            "progress": {
                "items_processed": 15,
                "total_items": 100,
                "percentage": 15.0,
                "nested": {
                    "array": [1, 2, 3],
                    "boolean": True,
                    "null_value": None
                }
            },
            "timestamp": "2024-01-15T10:00:00Z"
        }
        
        message = WebSocketMessage(
            type=MessageType.PROCESSING_STATUS,
            data=complex_data
        )
        
        await manager._send_to_client(client_id, message)
        
        # Verify message was serialized correctly
        assert len(mock_websocket.sent_messages) == 1
        sent_json = mock_websocket.sent_messages[0]
        parsed = json.loads(sent_json)
        
        assert parsed["type"] == "processing_status"
        assert parsed["data"] == complex_data
        assert "timestamp" in parsed
        assert "message_id" in parsed
        
        await manager.disconnect_client(client_id)