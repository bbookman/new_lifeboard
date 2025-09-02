import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types"""
    PROCESSING_STATUS = "processing_status"
    DAY_UPDATE = "day_update"
    QUEUE_STATS = "queue_stats"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"


@dataclass
class WebSocketMessage:
    """Structured WebSocket message"""
    type: MessageType
    data: Any
    timestamp: str = None
    message_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())


class ConnectionState(Enum):
    """WebSocket client connection states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CONFIRMED = "confirmed"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"


@dataclass
class ClientConnection:
    """Represents a connected WebSocket client with state tracking"""
    websocket: WebSocket
    client_id: str
    connected_at: datetime
    subscriptions: Set[str]
    last_heartbeat: datetime
    state: ConnectionState
    connection_failures: int = 0
    
    def __post_init__(self):
        if not self.subscriptions:
            self.subscriptions = set()
        if not hasattr(self, 'state'):
            self.state = ConnectionState.CONNECTING


class WebSocketManager:
    """
    Manages WebSocket connections for real-time semantic deduplication updates.
    
    Features:
    - Connection management with automatic cleanup
    - Subscription-based message routing
    - Heartbeat monitoring and connection health
    - Broadcast messaging with targeted delivery
    - Error handling and graceful degradation
    """
    
    def __init__(self, heartbeat_interval: int = 30):
        self.connections: Dict[str, ClientConnection] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # topic -> set of client_ids
        self.heartbeat_interval = heartbeat_interval
        self.is_running = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        logger.info("Initialized WebSocketManager")
    
    async def start(self):
        """Start the WebSocket manager and heartbeat monitoring"""
        if self.is_running:
            logger.warning("WebSocketManager already running")
            return
        
        self.is_running = True
        self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        logger.info("WebSocketManager started")
    
    async def stop(self):
        """Stop the WebSocket manager and disconnect all clients"""
        logger.info("Stopping WebSocketManager...")
        self.is_running = False
        
        # Cancel heartbeat monitoring
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        await self._disconnect_all_clients()
        
        self.connections.clear()
        self.subscriptions.clear()
        logger.info("WebSocketManager stopped")
    
    async def connect_client(self, websocket: WebSocket, client_id: str = None) -> str:
        """Connect a new WebSocket client with atomic setup and deferred confirmation"""
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        connection = None
        try:
            # Accept the WebSocket connection (FastAPI handles state validation)
            await websocket.accept()
            
            # Verify WebSocket is now in CONNECTED state
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.error(f"WebSocket accept succeeded but client_state is {websocket.client_state}")
                raise ConnectionError(f"WebSocket accept failed - state: {websocket.client_state}")
            
            # Create connection in CONNECTING state (not CONNECTED yet)
            connection = ClientConnection(
                websocket=websocket,
                client_id=client_id,
                connected_at=datetime.now(timezone.utc),
                subscriptions=set(),
                last_heartbeat=datetime.now(timezone.utc),
                state=ConnectionState.CONNECTING
            )
            
            # Register connection but don't send confirmation yet
            self.connections[client_id] = connection
            connection.state = ConnectionState.CONNECTED
            
            logger.info(f"Client {client_id} connected. Total connections: {len(self.connections)}")
            
            return client_id
            
        except Exception as e:
            logger.error(f"Failed to connect client {client_id}: {e}")
            # Clean up any partial connection state
            if connection and client_id in self.connections:
                del self.connections[client_id]
            raise
    
    async def confirm_client_connection(self, client_id: str) -> bool:
        """Send connection confirmation to a client, marking connection as CONFIRMED"""
        if client_id not in self.connections:
            logger.warning(f"Cannot confirm unknown client: {client_id}")
            return False
        
        connection = self.connections[client_id]
        
        if connection.state != ConnectionState.CONNECTED:
            logger.warning(f"Cannot confirm client {client_id} in state {connection.state}")
            return False
        
        try:
            await self._send_to_client(client_id, WebSocketMessage(
                type=MessageType.HEARTBEAT,
                data={"status": "connected", "client_id": client_id}
            ))
            connection.state = ConnectionState.CONFIRMED
            logger.debug(f"Client {client_id} connection confirmed")
            return True
            
        except Exception as send_error:
            logger.warning(f"Failed to send connection confirmation to {client_id}: {send_error}")
            # Connection confirmation is critical - disconnect immediately
            await self.disconnect_client(client_id, f"confirmation_failed: {send_error}")
            return False
    
    async def disconnect_client(self, client_id: str, reason: str = "normal_closure"):
        """Safely disconnect a WebSocket client with improved state handling"""
        if client_id not in self.connections:
            logger.warning(f"Attempted to disconnect unknown client: {client_id}")
            return

        connection = self.connections[client_id]
        
        # Update connection state to prevent concurrent operations
        connection.state = ConnectionState.DISCONNECTING

        # Remove from all subscriptions
        for topic in list(connection.subscriptions):
            await self._unsubscribe_client_from_topic(client_id, topic)

        # Close WebSocket connection safely
        try:
            # Check multiple conditions for safe close
            websocket_state = connection.websocket.client_state
            if websocket_state in {WebSocketState.CONNECTED, WebSocketState.CONNECTING}:
                await connection.websocket.close(reason=reason)
            elif websocket_state == WebSocketState.DISCONNECTED:
                logger.debug(f"WebSocket for client {client_id} already disconnected")
            else:
                logger.debug(f"WebSocket for client {client_id} in state {websocket_state}, skipping close")
        except Exception as e:
            logger.debug(f"Error closing WebSocket for client {client_id}: {e}")

        # Update state and remove from connections
        connection.state = ConnectionState.DISCONNECTED
        del self.connections[client_id]
        logger.info(f"Client {client_id} disconnected ({reason}). Total connections: {len(self.connections)})")
    
    async def subscribe_client(self, client_id: str, topics: List[str]):
        """Subscribe a client to one or more topics"""
        if client_id not in self.connections:
            logger.warning(f"Cannot subscribe unknown client: {client_id}")
            return
        
        connection = self.connections[client_id]
        
        for topic in topics:
            # Add to client's subscriptions
            connection.subscriptions.add(topic)
            
            # Add to topic subscriptions
            if topic not in self.subscriptions:
                self.subscriptions[topic] = set()
            self.subscriptions[topic].add(client_id)
            
            logger.debug(f"Client {client_id} subscribed to topic: {topic}")
        
        # Confirm subscription
        await self._send_to_client(client_id, WebSocketMessage(
            type=MessageType.SUBSCRIPTION,
            data={"topics": topics, "status": "subscribed"}
        ))
    
    async def unsubscribe_client(self, client_id: str, topics: List[str]):
        """Unsubscribe a client from one or more topics"""
        if client_id not in self.connections:
            logger.warning(f"Cannot unsubscribe unknown client: {client_id}")
            return
        
        for topic in topics:
            await self._unsubscribe_client_from_topic(client_id, topic)
        
        # Confirm unsubscription
        await self._send_to_client(client_id, WebSocketMessage(
            type=MessageType.UNSUBSCRIPTION,
            data={"topics": topics, "status": "unsubscribed"}
        ))
    
    async def broadcast_to_topic(self, topic: str, message: WebSocketMessage):
        """Broadcast a message to all clients subscribed to a topic"""
        if topic not in self.subscriptions:
            logger.debug(f"No subscribers for topic: {topic}")
            return
        
        subscribers = list(self.subscriptions[topic])
        logger.debug(f"Broadcasting to {len(subscribers)} subscribers of topic: {topic}")
        
        # Send to all subscribers concurrently
        tasks = []
        for client_id in subscribers:
            if client_id in self.connections:
                tasks.append(self._send_to_client(client_id, message))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle send failures with improved error handling
            failed_clients = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_client = subscribers[i]
                    logger.warning(f"Failed to send to client {failed_client}: {result}")
                    failed_clients.append(failed_client)
            
            # Handle failed clients with connection failure tracking
            for client_id in failed_clients:
                await self._handle_connection_failure(client_id, "broadcast_send_failure")
    
    async def send_processing_status(self, days_date: str, status: str, progress: Dict[str, Any] = None):
        """Send processing status update for a specific day"""
        message = WebSocketMessage(
            type=MessageType.PROCESSING_STATUS,
            data={
                "days_date": days_date,
                "status": status,
                "progress": progress or {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Broadcast to general processing topic and day-specific topic
        await self.broadcast_to_topic("processing_updates", message)
        await self.broadcast_to_topic(f"day_{days_date}", message)
    
    async def send_queue_stats(self, stats: Dict[str, Any]):
        """Send queue statistics update"""
        message = WebSocketMessage(
            type=MessageType.QUEUE_STATS,
            data=stats
        )
        
        await self.broadcast_to_topic("queue_stats", message)
    
    async def send_day_update(self, days_date: str, update_data: Dict[str, Any]):
        """Send update for a specific day"""
        message = WebSocketMessage(
            type=MessageType.DAY_UPDATE,
            data={
                "days_date": days_date,
                **update_data
            }
        )
        
        await self.broadcast_to_topic(f"day_{days_date}", message)
        await self.broadcast_to_topic("day_updates", message)
    
    async def handle_client_message(self, client_id: str, message_data: Dict[str, Any]):
        """Handle incoming message from client with connection state validation"""
        # Validate client is properly connected before handling any messages
        if client_id not in self.connections:
            logger.warning(f"Received message from unknown client {client_id}, ignoring")
            return
            
        connection = self.connections[client_id]
        
        # Verify WebSocket is still in connected state
        if connection.websocket.client_state != WebSocketState.CONNECTED:
            logger.warning(f"Received message from client {client_id} in state {connection.websocket.client_state}, disconnecting")
            await self.disconnect_client(client_id, "invalid_state")
            return
        
        try:
            message_type = MessageType(message_data.get("type"))
            data = message_data.get("data", {})
            
            if message_type == MessageType.SUBSCRIPTION:
                topics = data.get("topics", [])
                await self.subscribe_client(client_id, topics)
            
            elif message_type == MessageType.UNSUBSCRIPTION:
                topics = data.get("topics", [])
                await self.unsubscribe_client(client_id, topics)
            
            elif message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(client_id)
            
            else:
                logger.warning(f"Unknown message type from client {client_id}: {message_type}")
        
        except Exception as e:
            logger.error(f"Error handling client message from {client_id}: {e}")
            # Only send error response if client is still connected
            if client_id in self.connections:
                await self._send_error_to_client(client_id, f"Message handling error: {e}")
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive connection and subscription statistics"""
        topic_stats = {}
        for topic, subscribers in self.subscriptions.items():
            topic_stats[topic] = len(subscribers)
        
        # Connection state breakdown
        state_stats = {}
        for connection in self.connections.values():
            state = connection.state.value
            state_stats[state] = state_stats.get(state, 0) + 1
        
        # Connection health stats
        healthy_connections = sum(1 for conn in self.connections.values() if conn.connection_failures == 0)
        unhealthy_connections = len(self.connections) - healthy_connections
        
        return {
            "total_connections": len(self.connections),
            "healthy_connections": healthy_connections,
            "unhealthy_connections": unhealthy_connections,
            "connection_states": state_stats,
            "total_topics": len(self.subscriptions),
            "topic_subscribers": topic_stats,
            "heartbeat_interval": self.heartbeat_interval,
            "is_running": self.is_running,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    async def _send_to_client(self, client_id: str, message: WebSocketMessage):
        """Send a message to a specific client with enhanced error handling"""
        if client_id not in self.connections:
            raise ValueError(f"Client {client_id} not connected")

        connection = self.connections[client_id]

        # Check connection state before attempting send
        if connection.state == ConnectionState.DISCONNECTING:
            logger.debug(f"Cannot send to client {client_id}: connection is disconnecting")
            raise ConnectionError(f"Client {client_id} is disconnecting")
        
        if connection.state == ConnectionState.DISCONNECTED:
            logger.debug(f"Cannot send to client {client_id}: connection is disconnected")
            raise ConnectionError(f"Client {client_id} is disconnected")

        # Check if WebSocket connection is still valid
        websocket_state = connection.websocket.client_state
        if websocket_state != WebSocketState.CONNECTED:
            logger.debug(f"Cannot send to client {client_id}: WebSocket is not open (state: {websocket_state})")
            # Don't immediately disconnect - let the calling code handle it
            raise ConnectionError(f"WebSocket for client {client_id} is not open (state: {websocket_state})")

        try:
            message_json = json.dumps({
                "type": message.type.value,
                "data": message.data,
                "timestamp": message.timestamp,
                "message_id": message.message_id
            })

            await connection.websocket.send_text(message_json)
            
            # Reset failure count on successful send
            connection.connection_failures = 0

        except Exception as e:
            # Increment failure count
            connection.connection_failures += 1
            logger.error(f"Error sending message to client {client_id} (failure #{connection.connection_failures}): {e}")
            
            # Don't automatically disconnect - let calling code decide
            # This prevents cascading disconnect errors
            raise ConnectionError(f"Failed to send message to client {client_id}: {e}")
    
    async def _handle_connection_failure(self, client_id: str, reason: str):
        """Handle connection failure with circuit breaker pattern"""
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        connection.connection_failures += 1
        
        # Implement circuit breaker - disconnect after multiple failures
        if connection.connection_failures >= 3:
            logger.warning(f"Client {client_id} has {connection.connection_failures} failures, disconnecting")
            await self.disconnect_client(client_id, f"too_many_failures: {reason}")
        else:
            logger.debug(f"Client {client_id} failure #{connection.connection_failures}: {reason}")
    
    async def _send_error_to_client(self, client_id: str, error_message: str):
        """Send error message to client"""
        try:
            # Check if client still exists before attempting to send
            if client_id not in self.connections:
                logger.debug(f"Cannot send error to client {client_id}: client not connected")
                return
                
            error_msg = WebSocketMessage(
                type=MessageType.ERROR,
                data={"message": error_message}
            )
            await self._send_to_client(client_id, error_msg)
        except Exception as e:
            # Log but don't re-raise to avoid cascading errors
            logger.debug(f"Failed to send error message to client {client_id}: {e}")
    
    async def _unsubscribe_client_from_topic(self, client_id: str, topic: str):
        """Remove client from a specific topic"""
        if client_id in self.connections:
            self.connections[client_id].subscriptions.discard(topic)
        
        if topic in self.subscriptions:
            self.subscriptions[topic].discard(client_id)
            
            # Clean up empty topic subscriptions
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]
        
        logger.debug(f"Client {client_id} unsubscribed from topic: {topic}")
    
    async def _handle_heartbeat(self, client_id: str):
        """Handle heartbeat from client"""
        if client_id in self.connections:
            self.connections[client_id].last_heartbeat = datetime.now(timezone.utc)
            
            # Send heartbeat response
            await self._send_to_client(client_id, WebSocketMessage(
                type=MessageType.HEARTBEAT,
                data={"status": "pong"}
            ))
    
    async def _heartbeat_monitor(self):
        """Monitor client connections and send heartbeats"""
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)
                stale_clients = []
                
                for client_id, connection in list(self.connections.items()):
                    # Check if client hasn't sent heartbeat in 2x interval
                    if (now - connection.last_heartbeat).total_seconds() > self.heartbeat_interval * 2:
                        stale_clients.append(client_id)
                
                # Disconnect stale clients
                for client_id in stale_clients:
                    logger.info(f"Disconnecting stale client: {client_id}")
                    await self.disconnect_client(client_id, "heartbeat_timeout")
                
                # Send heartbeat to remaining clients
                if self.connections:
                    heartbeat_msg = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        data={"status": "ping"}
                    )
                    
                    tasks = []
                    for client_id in list(self.connections.keys()):
                        tasks.append(self._send_to_client(client_id, heartbeat_msg))
                    
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _disconnect_all_clients(self):
        """Disconnect all connected clients"""
        client_ids = list(self.connections.keys())
        tasks = []
        
        for client_id in client_ids:
            tasks.append(self.disconnect_client(client_id, "server_shutdown"))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Global WebSocketManager instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Get the global WebSocketManager instance"""
    return _websocket_manager


def set_websocket_manager(manager: WebSocketManager) -> None:
    """Set the global WebSocketManager instance"""
    global _websocket_manager
    _websocket_manager = manager
    logger.info("Global WebSocketManager instance set")


def clear_websocket_manager() -> None:
    """Clear the global WebSocketManager instance"""
    global _websocket_manager
    _websocket_manager = None
    logger.info("Global WebSocketManager instance cleared")