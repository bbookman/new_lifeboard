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


@dataclass
class ClientConnection:
    """Represents a connected WebSocket client"""
    websocket: WebSocket
    client_id: str
    connected_at: datetime
    subscriptions: Set[str]
    last_heartbeat: datetime
    
    def __post_init__(self):
        if not self.subscriptions:
            self.subscriptions = set()


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
        """Connect a new WebSocket client"""
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        await websocket.accept()
        
        connection = ClientConnection(
            websocket=websocket,
            client_id=client_id,
            connected_at=datetime.now(timezone.utc),
            subscriptions=set(),
            last_heartbeat=datetime.now(timezone.utc)
        )
        
        self.connections[client_id] = connection
        logger.info(f"Client {client_id} connected. Total connections: {len(self.connections)}")
        
        # Send connection confirmation
        await self._send_to_client(client_id, WebSocketMessage(
            type=MessageType.HEARTBEAT,
            data={"status": "connected", "client_id": client_id}
        ))
        
        return client_id
    
    async def disconnect_client(self, client_id: str, reason: str = "normal_closure"):
        """Disconnect a WebSocket client"""
        if client_id not in self.connections:
            logger.warning(f"Attempted to disconnect unknown client: {client_id}")
            return
        
        connection = self.connections[client_id]
        
        # Remove from all subscriptions
        for topic in list(connection.subscriptions):
            await self._unsubscribe_client_from_topic(client_id, topic)
        
        # Close WebSocket connection
        try:
            await connection.websocket.close(reason=reason)
        except Exception as e:
            logger.debug(f"Error closing WebSocket for client {client_id}: {e}")
        
        # Remove from connections
        del self.connections[client_id]
        logger.info(f"Client {client_id} disconnected ({reason}). Total connections: {len(self.connections)}")
    
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
            
            # Handle send failures
            failed_clients = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_client = subscribers[i]
                    logger.warning(f"Failed to send to client {failed_client}: {result}")
                    failed_clients.append(failed_client)
            
            # Disconnect failed clients
            for client_id in failed_clients:
                await self.disconnect_client(client_id, "send_failure")
    
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
        """Handle incoming message from client"""
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
            await self._send_error_to_client(client_id, f"Message handling error: {e}")
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection and subscription statistics"""
        topic_stats = {}
        for topic, subscribers in self.subscriptions.items():
            topic_stats[topic] = len(subscribers)
        
        return {
            "total_connections": len(self.connections),
            "total_topics": len(self.subscriptions),
            "topic_subscribers": topic_stats,
            "heartbeat_interval": self.heartbeat_interval,
            "is_running": self.is_running,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    async def _send_to_client(self, client_id: str, message: WebSocketMessage):
        """Send a message to a specific client"""
        if client_id not in self.connections:
            raise ValueError(f"Client {client_id} not connected")
        
        connection = self.connections[client_id]
        
        # Check if WebSocket connection is still valid
        if connection.websocket.client_state == WebSocketState.DISCONNECTED:
            logger.debug(f"Cannot send to client {client_id}: WebSocket is disconnected")
            # Remove the closed connection
            await self.disconnect_client(client_id, "websocket_disconnected")
            raise ConnectionError(f"WebSocket for client {client_id} is disconnected")
        
        try:
            message_json = json.dumps({
                "type": message.type.value,
                "data": message.data,
                "timestamp": message.timestamp,
                "message_id": message.message_id
            })
            
            await connection.websocket.send_text(message_json)
            
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
            # If send fails, likely the connection is dead - disconnect client
            await self.disconnect_client(client_id, f"send_error: {e}")
            raise
    
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