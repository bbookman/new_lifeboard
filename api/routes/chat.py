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


def get_chat_service_dependency():
    """This will be set by the main server module"""
    raise NotImplementedError("Chat service dependency not configured")


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
    # Get recent chat history
    history = chat_service.get_chat_history(limit=10)
    
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
    # Process the chat message
    response = await chat_service.process_chat_message(message)
    
    # Get updated chat history
    history = chat_service.get_chat_history(limit=10)
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user_message": message,
        "response": response,
        "history": history
    })