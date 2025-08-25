"""
Chat endpoints for Phase 7

This module contains endpoints for the chat interface and
conversation management.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from services.chat_service import ChatService
from services.startup import StartupService
from core.exception_handling import handle_api_exceptions
from core.dependencies import get_startup_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

def get_chat_service_for_route(startup_service: StartupService = Depends(get_startup_service_dependency)) -> ChatService:
    """Get the chat service instance for route dependency injection"""
    if not startup_service.chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    return startup_service.chat_service


# Pydantic models for JSON API endpoints
class ChatMessageRequest(BaseModel):
    message: str

class ChatMessageResponse(BaseModel):
    response: str
    timestamp: str

class ChatHistoryItem(BaseModel):
    id: int
    user_message: str
    assistant_response: str
    timestamp: str

class ChatHistoryResponse(BaseModel):
    messages: List[ChatHistoryItem]


# JSON API endpoints for React frontend
@router.post("/send")
@handle_api_exceptions("Failed to send chat message", 500, include_details=True)
async def send_chat_message(
    request_data: ChatMessageRequest,
    chat_service: ChatService = Depends(get_chat_service_for_route)
) -> ChatMessageResponse:
    """Send a chat message and get AI response (JSON API)"""
    try:
        # Process the chat message
        response = await chat_service.process_chat_message(request_data.message)
        
        # Return JSON response
        return ChatMessageResponse(
            response=response,
            timestamp=str(datetime.now().isoformat())
        )
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")


@router.get("/history")
@handle_api_exceptions("Failed to get chat history", 500, include_details=True)
async def get_chat_history_api(
    limit: int = 20,
    chat_service: ChatService = Depends(get_chat_service_for_route)
) -> ChatHistoryResponse:
    """Get chat history (JSON API)"""
    try:
        # Get chat history from service
        history = chat_service.get_chat_history(limit=limit)
        
        # Convert to API response format
        messages = []
        for item in history:
            messages.append(ChatHistoryItem(
                id=item.get('id', 0),
                user_message=item.get('user_message', ''),
                assistant_response=item.get('assistant_response', ''),
                timestamp=item.get('timestamp', '')
            ))
        
        return ChatHistoryResponse(messages=messages)
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat history")