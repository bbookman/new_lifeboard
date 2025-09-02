"""
Tests for WebSocket connection stability improvements.

This test suite verifies the fixes for race conditions and cascading errors
in WebSocket connection management.
"""

import asyncio
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from services.websocket_manager import (
    WebSocketManager, 
    ConnectionState, 
    ClientConnection,
    WebSocketMessage, 
    MessageType
)


class MockWebSocket:
    """Mock WebSocket for testing"""
    
    def __init__(self, client_state=WebSocketState.CONNECTING):
        self.client_state = client_state
        self.accept_called = False
        self.close_called = False
        self.close_reason = None
        self.sent_messages = []
        self.should_fail_send = False
        self.should_fail_accept = False
    
    async def accept(self):
        if self.should_fail_accept:
            raise Exception("Accept failed")
        self.accept_called = True
        self.client_state = WebSocketState.CONNECTED
    
    async def close(self, reason=None):
        self.close_called = True
        self.close_reason = reason
        self.client_state = WebSocketState.DISCONNECTED
    
    async def send_text(self, message):
        if self.should_fail_send:
            raise Exception("Send failed")
        self.sent_messages.append(message)


@pytest.fixture
def websocket_manager():
    """Create WebSocketManager for testing"""
    manager = WebSocketManager(heartbeat_interval=5)
    return manager


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for testing"""
    return MockWebSocket()


@pytest.mark.asyncio
class TestConnectionLifecycle:
    """Test connection lifecycle improvements"""
    
    async def test_connect_client_atomic_setup(self, websocket_manager, mock_websocket):
        """Test that connection setup is atomic"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        
        # Verify connection is registered
        assert client_id in websocket_manager.connections
        connection = websocket_manager.connections[client_id]
        
        # Verify initial state
        assert connection.state == ConnectionState.CONNECTED
        assert mock_websocket.accept_called
        
        # Verify no confirmation sent yet (deferred)
        assert len(mock_websocket.sent_messages) == 0
    
    async def test_connection_confirmation_separate(self, websocket_manager, mock_websocket):
        """Test that connection confirmation is handled separately"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        
        # Confirm connection
        result = await websocket_manager.confirm_client_connection(client_id)
        
        assert result is True
        connection = websocket_manager.connections[client_id]
        assert connection.state == ConnectionState.CONFIRMED
        assert len(mock_websocket.sent_messages) == 1
        
        # Verify confirmation message
        sent_message = json.loads(mock_websocket.sent_messages[0])
        assert sent_message["type"] == "heartbeat"
        assert sent_message["data"]["status"] == "connected"
    
    async def test_connection_confirmation_failure_recovery(self, websocket_manager, mock_websocket):
        """Test recovery when connection confirmation fails"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        
        # Make send fail
        mock_websocket.should_fail_send = True
        
        # Attempt confirmation
        result = await websocket_manager.confirm_client_connection(client_id)
        
        assert result is False
        # Client should be disconnected due to confirmation failure
        assert client_id not in websocket_manager.connections
    
    async def test_connection_state_transitions(self, websocket_manager, mock_websocket):
        """Test proper connection state transitions"""
        # Initial connection
        client_id = await websocket_manager.connect_client(mock_websocket)
        connection = websocket_manager.connections[client_id]
        assert connection.state == ConnectionState.CONNECTED
        
        # Confirmation
        await websocket_manager.confirm_client_connection(client_id)
        assert connection.state == ConnectionState.CONFIRMED
        
        # Disconnection
        await websocket_manager.disconnect_client(client_id)
        # Connection should be removed from manager
        assert client_id not in websocket_manager.connections


@pytest.mark.asyncio  
class TestErrorHandling:
    """Test improved error handling"""
    
    async def test_send_failure_no_cascading_disconnect(self, websocket_manager, mock_websocket):
        """Test that send failures don't cause cascading disconnects"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        await websocket_manager.confirm_client_connection(client_id)
        
        connection = websocket_manager.connections[client_id]
        initial_failures = connection.connection_failures
        
        # Make send fail
        mock_websocket.should_fail_send = True
        
        # Try to send message - should raise but not auto-disconnect
        with pytest.raises(ConnectionError):
            await websocket_manager._send_to_client(
                client_id, 
                WebSocketMessage(type=MessageType.HEARTBEAT, data={})
            )
        
        # Connection should still exist with incremented failure count
        assert client_id in websocket_manager.connections
        assert connection.connection_failures == initial_failures + 1
        assert not mock_websocket.close_called
    
    async def test_circuit_breaker_pattern(self, websocket_manager, mock_websocket):
        """Test circuit breaker disconnects after multiple failures"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        await websocket_manager.confirm_client_connection(client_id)
        
        # Trigger multiple failures through connection failure handler
        await websocket_manager._handle_connection_failure(client_id, "test_failure_1")
        assert client_id in websocket_manager.connections  # Still connected
        
        await websocket_manager._handle_connection_failure(client_id, "test_failure_2")
        assert client_id in websocket_manager.connections  # Still connected
        
        await websocket_manager._handle_connection_failure(client_id, "test_failure_3")
        assert client_id not in websocket_manager.connections  # Now disconnected
        assert mock_websocket.close_called
    
    async def test_safe_disconnect_multiple_states(self, websocket_manager):
        """Test safe disconnection handles various WebSocket states"""
        # Test with already disconnected WebSocket
        disconnected_ws = MockWebSocket(WebSocketState.DISCONNECTED)
        client_id1 = await websocket_manager.connect_client(disconnected_ws)
        disconnected_ws.client_state = WebSocketState.DISCONNECTED
        
        # Should not attempt to close already disconnected WebSocket
        await websocket_manager.disconnect_client(client_id1)
        assert not disconnected_ws.close_called
        
        # Test with connected WebSocket
        connected_ws = MockWebSocket(WebSocketState.CONNECTED)
        client_id2 = await websocket_manager.connect_client(connected_ws)
        
        # Should close connected WebSocket
        await websocket_manager.disconnect_client(client_id2)
        assert connected_ws.close_called
    
    async def test_broadcast_failure_handling(self, websocket_manager):
        """Test broadcast handles individual client failures gracefully"""
        # Create multiple clients
        clients = []
        for i in range(3):
            ws = MockWebSocket()
            client_id = await websocket_manager.connect_client(ws)
            await websocket_manager.confirm_client_connection(client_id)
            await websocket_manager.subscribe_client(client_id, ["test_topic"])
            clients.append((client_id, ws))
        
        # Make one client fail sends
        failing_client_id, failing_ws = clients[1]
        failing_ws.should_fail_send = True
        
        # Broadcast message
        message = WebSocketMessage(type=MessageType.HEARTBEAT, data={"test": True})
        await websocket_manager.broadcast_to_topic("test_topic", message)
        
        # Verify successful clients received message
        successful_clients = [clients[0], clients[2]]
        for client_id, ws in successful_clients:
            assert len(ws.sent_messages) >= 1  # At least confirmation + broadcast
        
        # Failing client should have failure tracked
        if failing_client_id in websocket_manager.connections:
            connection = websocket_manager.connections[failing_client_id]
            assert connection.connection_failures > 0


@pytest.mark.asyncio
class TestConnectionHealth:
    """Test connection health monitoring"""
    
    async def test_connection_stats_include_health(self, websocket_manager):
        """Test that connection stats include health information"""
        # Create healthy connection
        healthy_ws = MockWebSocket()
        healthy_id = await websocket_manager.connect_client(healthy_ws)
        await websocket_manager.confirm_client_connection(healthy_id)
        
        # Create unhealthy connection
        unhealthy_ws = MockWebSocket()
        unhealthy_id = await websocket_manager.connect_client(unhealthy_ws)
        await websocket_manager.confirm_client_connection(unhealthy_id)
        
        # Make unhealthy connection fail
        await websocket_manager._handle_connection_failure(unhealthy_id, "test_failure")
        
        # Get stats
        stats = await websocket_manager.get_connection_stats()
        
        assert stats["total_connections"] == 2
        assert stats["healthy_connections"] == 1
        assert stats["unhealthy_connections"] == 1
        assert "connection_states" in stats
        assert stats["connection_states"]["confirmed"] == 2
    
    async def test_state_tracking_in_stats(self, websocket_manager, mock_websocket):
        """Test that connection states are properly tracked in stats"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        
        # Check initial state
        stats = await websocket_manager.get_connection_stats()
        assert stats["connection_states"]["connected"] == 1
        
        # Confirm connection
        await websocket_manager.confirm_client_connection(client_id)
        
        # Check confirmed state
        stats = await websocket_manager.get_connection_stats()
        assert stats["connection_states"]["confirmed"] == 1
        assert "connected" not in stats["connection_states"]


@pytest.mark.asyncio
class TestRaceConditions:
    """Test fixes for race conditions"""
    
    async def test_concurrent_connection_operations(self, websocket_manager):
        """Test handling of concurrent connection operations"""
        websockets = [MockWebSocket() for _ in range(5)]
        
        # Connect multiple clients concurrently
        tasks = [
            websocket_manager.connect_client(ws) 
            for ws in websockets
        ]
        client_ids = await asyncio.gather(*tasks)
        
        # Verify all connections successful
        assert len(client_ids) == 5
        assert len(websocket_manager.connections) == 5
        
        # Confirm all connections concurrently
        confirm_tasks = [
            websocket_manager.confirm_client_connection(client_id)
            for client_id in client_ids
        ]
        results = await asyncio.gather(*confirm_tasks)
        
        # All confirmations should succeed
        assert all(results)
        
        # Verify all connections in CONFIRMED state
        for client_id in client_ids:
            connection = websocket_manager.connections[client_id]
            assert connection.state == ConnectionState.CONFIRMED
    
    async def test_connection_cleanup_race(self, websocket_manager, mock_websocket):
        """Test that connection cleanup doesn't race with other operations"""
        client_id = await websocket_manager.connect_client(mock_websocket)
        await websocket_manager.confirm_client_connection(client_id)
        
        # Start disconnect and send operations concurrently
        disconnect_task = asyncio.create_task(
            websocket_manager.disconnect_client(client_id)
        )
        
        # Give disconnect a head start
        await asyncio.sleep(0.01)
        
        # Try to send message - should fail gracefully
        with pytest.raises((ConnectionError, ValueError)):
            await websocket_manager._send_to_client(
                client_id,
                WebSocketMessage(type=MessageType.HEARTBEAT, data={})
            )
        
        await disconnect_task
        
        # Connection should be fully cleaned up
        assert client_id not in websocket_manager.connections


if __name__ == "__main__":
    pytest.main([__file__])