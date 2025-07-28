"""
Chat endpoints for Phase 7

This module contains endpoints for the chat interface and
conversation management.
"""

import logging
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.chat_service import ChatService
from core.exception_handling import handle_api_exceptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["chat"])

# Templates will be injected from main server
templates = None


def get_chat_service_dependency() -> ChatService:
    """Get chat service dependency"""
    # Import here to avoid circular imports
    from services.startup import get_startup_service
    from fastapi import HTTPException
    
    startup_service = get_startup_service()
    if not startup_service or not startup_service.chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    
    return startup_service.chat_service


def set_templates(template_instance):
    """Set the templates instance from main server"""
    global templates
    templates = template_instance


@router.get("/chat", response_class=HTMLResponse)
@handle_api_exceptions("Failed to load chat page", 500, include_details=True)
async def chat_page(
    request: Request, 
    chat_service: ChatService = Depends(get_chat_service_dependency)
):
    """Get the chat page with recent history"""
    logger.info("Chat page requested")
    
    # Get recent chat history
    history = chat_service.get_chat_history(limit=10)
    
    logger.info(f"Chat page loaded with {len(history)} history items")
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "history": history
    })


@router.post("/chat", response_class=HTMLResponse)
@handle_api_exceptions("Failed to process chat message", 500, include_details=True)
async def process_chat(
    request: Request, 
    message: str = Form(...),
    chat_service: ChatService = Depends(get_chat_service_dependency)
):
    """Process a chat message and return the response"""
    logger.info(f"Received chat message via API: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    # Process the chat message
    response = await chat_service.process_chat_message(message)
    
    # Get updated chat history
    history = chat_service.get_chat_history(limit=10)
    
    logger.info(f"Chat response sent: {len(response)} characters")
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user_message": message,
        "response": response,
        "history": history
    })