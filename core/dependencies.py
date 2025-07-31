"""
Central dependency registry for FastAPI route modules

This module provides a centralized way to manage dependency injection
for FastAPI routes, avoiding the flawed module attribute injection pattern.
"""

import logging
from typing import Optional, Callable, Any
from fastapi import HTTPException

from services.startup import StartupService, get_startup_service
from services.sync_manager_service import SyncManagerService
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


class DependencyRegistry:
    """Registry for managing FastAPI dependencies"""
    
    def __init__(self):
        self._startup_service_provider: Optional[Callable[[], StartupService]] = None
        self._sync_manager_provider: Optional[Callable[[StartupService], SyncManagerService]] = None
        self._chat_service_provider: Optional[Callable[[StartupService], ChatService]] = None
    
    def register_startup_service_provider(self, provider: Callable[[], StartupService]):
        """Register the startup service provider function"""
        self._startup_service_provider = provider
        logger.info("DEPENDENCIES: Startup service provider registered")
    
    def register_sync_manager_provider(self, provider: Callable[[StartupService], SyncManagerService]):
        """Register the sync manager provider function"""
        self._sync_manager_provider = provider
        logger.info("DEPENDENCIES: Sync manager provider registered")
    
    def register_chat_service_provider(self, provider: Callable[[StartupService], ChatService]):
        """Register the chat service provider function"""
        self._chat_service_provider = provider
        logger.info("DEPENDENCIES: Chat service provider registered")
    
    def get_startup_service(self) -> StartupService:
        """Get startup service instance for FastAPI dependency injection"""
        if not self._startup_service_provider:
            logger.error("DEPENDENCIES: Startup service provider not registered")
            raise HTTPException(status_code=503, detail="Application not initialized")
        
        try:
            startup_service = self._startup_service_provider()
            if not startup_service:
                logger.error("DEPENDENCIES: Startup service provider returned None")
                raise HTTPException(status_code=503, detail="Application not initialized")
            return startup_service
        except Exception as e:
            logger.error(f"DEPENDENCIES: Error getting startup service: {e}")
            raise HTTPException(status_code=503, detail="Application not initialized")
    
    def get_sync_manager(self, startup_service: StartupService) -> SyncManagerService:
        """Get sync manager instance for FastAPI dependency injection"""
        if not self._sync_manager_provider:
            logger.error("DEPENDENCIES: Sync manager provider not registered")
            raise HTTPException(status_code=503, detail="Sync manager not available")
        
        try:
            sync_manager = self._sync_manager_provider(startup_service)
            if not sync_manager:
                logger.error("DEPENDENCIES: Sync manager provider returned None")
                raise HTTPException(status_code=503, detail="Sync manager not available")
            return sync_manager
        except Exception as e:
            logger.error(f"DEPENDENCIES: Error getting sync manager: {e}")
            raise HTTPException(status_code=503, detail="Sync manager not available")
    
    def get_chat_service(self, startup_service: StartupService) -> ChatService:
        """Get chat service instance for FastAPI dependency injection"""
        if not self._chat_service_provider:
            logger.error("DEPENDENCIES: Chat service provider not registered")
            raise HTTPException(status_code=503, detail="Chat service not available")
        
        try:
            chat_service = self._chat_service_provider(startup_service)
            if not chat_service:
                logger.error("DEPENDENCIES: Chat service provider returned None")
                raise HTTPException(status_code=503, detail="Chat service not available")
            return chat_service
        except Exception as e:
            logger.error(f"DEPENDENCIES: Error getting chat service: {e}")
            raise HTTPException(status_code=503, detail="Chat service not available")


# Global registry instance
_dependency_registry = DependencyRegistry()


def get_dependency_registry() -> DependencyRegistry:
    """Get the global dependency registry instance"""
    return _dependency_registry


# FastAPI dependency functions for route modules
def get_startup_service_dependency() -> StartupService:
    """FastAPI dependency for startup service"""
    return _dependency_registry.get_startup_service()


def get_sync_manager_dependency(startup_service: StartupService) -> SyncManagerService:
    """FastAPI dependency for sync manager service"""
    return _dependency_registry.get_sync_manager(startup_service)


def get_chat_service_dependency(startup_service: StartupService) -> ChatService:
    """FastAPI dependency for chat service"""
    return _dependency_registry.get_chat_service(startup_service)