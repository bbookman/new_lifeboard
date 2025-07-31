"""
Settings endpoints for Lifeboard

This module contains endpoints for application settings and configuration management.
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["settings"])

# Templates will be set by the main server
templates = None


def set_templates(template_instance):
    """Set the templates instance from main server"""
    global templates
    templates = template_instance


@router.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request):
    """Serve the main settings page"""
    return templates.TemplateResponse("settings.html", {"request": request})