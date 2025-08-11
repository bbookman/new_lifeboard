import asyncio
import json
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from services.websocket_manager import WebSocketManager, MessageType
from services.clean_up_crew_service import CleanUpCrewService, ProcessingStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

# Global WebSocket manager instance
websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance"""
    global websocket_manager
    if websocket_manager is None:
        websocket_manager = WebSocketManager(heartbeat_interval=30)
    return websocket_manager


async def get_clean_up_crew_service() -> CleanUpCrewService:
    """Get CleanUpCrewService instance (dependency injection)"""
    # This would be properly injected in a real application
    # For now, we'll import and return a placeholder
    from services.startup import get_service_container
    container = get_service_container()
    return container.get('clean_up_crew_service')


@router.websocket("/processing")
async def websocket_processing_updates(
    websocket: WebSocket,
    client_id: Optional[str] = None,
    manager: WebSocketManager = Depends(get_websocket_manager)
):
    """
    WebSocket endpoint for real-time semantic deduplication processing updates.
    
    Supports:
    - Connection management with heartbeat monitoring
    - Subscription to specific processing topics
    - Real-time status updates for days and queue statistics
    - Error handling and graceful disconnection
    """
    
    try:
        # Connect client
        actual_client_id = await manager.connect_client(websocket, client_id)
        logger.info(f"WebSocket client connected: {actual_client_id}")
        
        # Auto-subscribe to general processing updates
        await manager.subscribe_client(actual_client_id, [
            "processing_updates",
            "queue_stats"
        ])
        
        # Handle client messages
        while True:
            try:
                # Receive message from client
                message_text = await websocket.receive_text()
                message_data = json.loads(message_text)
                
                # Handle the message
                await manager.handle_client_message(actual_client_id, message_data)
                
            except WebSocketDisconnect:
                logger.info(f"Client {actual_client_id} disconnected normally")
                break
                
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from client {actual_client_id}: {e}")
                await manager._send_error_to_client(
                    actual_client_id, 
                    f"Invalid JSON message: {e}"
                )
                
            except Exception as e:
                logger.error(f"Error handling message from client {actual_client_id}: {e}")
                await manager._send_error_to_client(
                    actual_client_id,
                    f"Message processing error: {e}"
                )
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        if 'actual_client_id' in locals():
            await manager.disconnect_client(actual_client_id, f"connection_error: {e}")
        else:
            try:
                await websocket.close(reason=f"connection_error: {e}")
            except Exception:
                pass
    
    finally:
        # Ensure cleanup
        if 'actual_client_id' in locals():
            await manager.disconnect_client(actual_client_id, "connection_closed")


@router.get("/stats")
async def get_websocket_stats(manager: WebSocketManager = Depends(get_websocket_manager)):
    """Get WebSocket connection and subscription statistics"""
    try:
        stats = await manager.get_connection_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get WebSocket statistics: {e}"
        )


@router.post("/broadcast/{topic}")
async def broadcast_message(
    topic: str,
    message_data: Dict[str, Any],
    manager: WebSocketManager = Depends(get_websocket_manager)
):
    """
    Manually broadcast a message to all subscribers of a topic.
    Useful for testing and administrative purposes.
    """
    try:
        from services.websocket_manager import WebSocketMessage
        
        message = WebSocketMessage(
            type=MessageType(message_data.get("type", "processing_status")),
            data=message_data.get("data", {})
        )
        
        await manager.broadcast_to_topic(topic, message)
        
        return JSONResponse(content={
            "success": True,
            "topic": topic,
            "message_sent": True
        })
        
    except Exception as e:
        logger.error(f"Error broadcasting message to topic {topic}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast message: {e}"
        )


@router.post("/trigger-processing/{days_date}")
async def trigger_day_processing_with_updates(
    days_date: str,
    force: bool = False,
    manager: WebSocketManager = Depends(get_websocket_manager),
    crew_service: CleanUpCrewService = Depends(get_clean_up_crew_service)
):
    """
    Trigger processing for a specific day and broadcast real-time updates via WebSocket.
    This demonstrates the integration between CleanUpCrewService and WebSocketManager.
    """
    try:
        # Set up progress callback for real-time updates
        async def progress_callback(day: str, status: ProcessingStatus):
            await manager.send_processing_status(
                days_date=day,
                status=status.value,
                progress={"triggered_manually": True}
            )
        
        # Add callback to crew service
        await crew_service.add_progress_callback(progress_callback)
        
        try:
            # Trigger processing
            result = await crew_service.trigger_day_processing(days_date, force=force)
            
            # Send final result
            await manager.send_processing_status(
                days_date=days_date,
                status=result.status.value,
                progress={
                    "items_processed": result.items_processed,
                    "clusters_created": result.clusters_created,
                    "processing_time": result.processing_time,
                    "completed": True
                }
            )
            
            return JSONResponse(content={
                "success": True,
                "days_date": days_date,
                "result": {
                    "status": result.status.value,
                    "items_processed": result.items_processed,
                    "clusters_created": result.clusters_created,
                    "processing_time": result.processing_time,
                    "error_message": result.error_message
                }
            })
            
        finally:
            # Remove callback
            await crew_service.remove_progress_callback(progress_callback)
    
    except Exception as e:
        logger.error(f"Error triggering processing for {days_date}: {e}")
        
        # Send error update
        await manager.send_processing_status(
            days_date=days_date,
            status="failed",
            progress={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger processing: {e}"
        )


async def setup_websocket_integration(crew_service: CleanUpCrewService, manager: WebSocketManager):
    """
    Set up integration between CleanUpCrewService and WebSocketManager.
    This should be called during application startup.
    """
    
    async def crew_progress_callback(days_date: str, status: ProcessingStatus):
        """Callback to send crew service updates via WebSocket"""
        try:
            await manager.send_processing_status(
                days_date=days_date,
                status=status.value,
                progress={"source": "background_processing"}
            )
        except Exception as e:
            logger.error(f"Error sending WebSocket update for {days_date}: {e}")
    
    # Register the callback
    await crew_service.add_progress_callback(crew_progress_callback)
    logger.info("WebSocket integration with CleanUpCrewService established")


async def start_websocket_manager():
    """Start the global WebSocket manager"""
    global websocket_manager
    if websocket_manager is None:
        websocket_manager = WebSocketManager()
    
    if not websocket_manager.is_running:
        await websocket_manager.start()
        logger.info("WebSocket manager started")


async def stop_websocket_manager():
    """Stop the global WebSocket manager"""
    global websocket_manager
    if websocket_manager and websocket_manager.is_running:
        await websocket_manager.stop()
        logger.info("WebSocket manager stopped")