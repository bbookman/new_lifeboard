"""
API dependency injection fixtures for testing.

Provides utilities for setting up FastAPI dependency injection in test environments,
ensuring proper mocking and service registration for API route tests.
"""

import logging
from typing import Any, Callable, Dict, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from core.dependencies import DependencyRegistry, get_dependency_registry
from services.chat_service import ChatService
from services.startup import StartupService
from services.sync_manager_service import SyncManagerService

logger = logging.getLogger(__name__)


class TestDependencyRegistry:
    """Test-specific dependency registry with mock services."""
    
    def __init__(self):
        self._registry = DependencyRegistry()
        self._startup_service: Optional[StartupService] = None
        self._chat_service: Optional[ChatService] = None
        self._sync_manager: Optional[SyncManagerService] = None
    
    def setup_with_mocks(self, 
                        startup_service: Optional[StartupService] = None,
                        chat_service: Optional[ChatService] = None, 
                        sync_manager: Optional[SyncManagerService] = None):
        """Set up registry with provided or default mock services."""
        
        # Use provided services or create mocks
        self._startup_service = startup_service or MagicMock(spec=StartupService)
        self._chat_service = chat_service or MagicMock(spec=ChatService)
        self._sync_manager = sync_manager or MagicMock(spec=SyncManagerService)
        
        # Connect services if they have relationships
        if hasattr(self._startup_service, 'chat_service'):
            self._startup_service.chat_service = self._chat_service
        if hasattr(self._startup_service, 'sync_manager'):
            self._startup_service.sync_manager = self._sync_manager
        
        # Register providers
        self._registry.register_startup_service_provider(lambda: self._startup_service)
        self._registry.register_chat_service_provider(lambda startup: self._chat_service)
        self._registry.register_sync_manager_provider(lambda startup: self._sync_manager)
        
        logger.info("TEST_DEPENDENCIES: Test registry configured with mock services")
    
    def get_registry(self) -> DependencyRegistry:
        """Get the test registry instance."""
        return self._registry
    
    def get_startup_service(self) -> StartupService:
        """Get the mock startup service."""
        return self._startup_service
    
    def get_chat_service(self) -> ChatService:
        """Get the mock chat service."""
        return self._chat_service
    
    def get_sync_manager(self) -> SyncManagerService:
        """Get the mock sync manager."""
        return self._sync_manager


def create_test_app_with_dependencies(routers: list, 
                                    registry: Optional[TestDependencyRegistry] = None) -> FastAPI:
    """
    Create a FastAPI test application with proper dependency injection setup.
    
    Args:
        routers: List of routers to include
        registry: Optional test registry (will create one if not provided)
        
    Returns:
        Configured FastAPI application for testing
    """
    app = FastAPI(title="Test API", version="test")
    
    # Setup test registry if not provided
    if registry is None:
        registry = TestDependencyRegistry()
        registry.setup_with_mocks()
    
    # Override global dependency functions to use test registry
    def get_test_startup_service():
        return registry.get_startup_service()
    
    def get_test_chat_service(startup_service: StartupService):
        return registry.get_chat_service()
    
    def get_test_sync_manager(startup_service: StartupService):
        return registry.get_sync_manager()
    
    # Apply dependency overrides
    from core.dependencies import (
        get_startup_service_dependency,
        get_chat_service_dependency, 
        get_sync_manager_dependency
    )
    
    app.dependency_overrides[get_startup_service_dependency] = get_test_startup_service
    app.dependency_overrides[get_chat_service_dependency] = get_test_chat_service
    app.dependency_overrides[get_sync_manager_dependency] = get_test_sync_manager
    
    # Include routers
    for router in routers:
        app.include_router(router, prefix="/api")
    
    logger.info(f"TEST_APP: Created test application with {len(routers)} routers and dependency overrides")
    return app


@pytest.fixture
def test_dependency_registry():
    """Pytest fixture for test dependency registry."""
    registry = TestDependencyRegistry()
    registry.setup_with_mocks()
    return registry


@pytest.fixture
def mock_startup_service():
    """Pytest fixture for mock startup service."""
    return MagicMock(spec=StartupService)


@pytest.fixture
def mock_chat_service():
    """Pytest fixture for mock chat service."""
    return MagicMock(spec=ChatService)


@pytest.fixture
def mock_sync_manager():
    """Pytest fixture for mock sync manager."""
    return MagicMock(spec=SyncManagerService)


@pytest.fixture
def api_test_app(test_dependency_registry):
    """
    Pytest fixture for a complete test API application.
    
    This creates a FastAPI app with all standard routes and proper
    dependency injection setup for testing.
    """
    from api.routes import chat, health, sync, weather, calendar
    
    routers = [health.router, chat.router, sync.router, weather.router, calendar.router]
    return create_test_app_with_dependencies(routers, test_dependency_registry)


@pytest.fixture  
def api_test_client(api_test_app):
    """Pytest fixture for test client with complete API setup."""
    from fastapi.testclient import TestClient
    return TestClient(api_test_app)


class APITestBase:
    """
    Base class for API route tests with dependency injection support.
    
    Provides common setup, utilities, and patterns for testing API routes
    with proper dependency injection and service mocking.
    """
    
    def setup_method(self):
        """Set up test environment for each test method."""
        self.registry = TestDependencyRegistry()
        self.registry.setup_with_mocks()
    
    def create_test_app(self, routers: list) -> FastAPI:
        """Create a test app with specified routers."""
        return create_test_app_with_dependencies(routers, self.registry)
    
    def get_startup_service(self) -> StartupService:
        """Get the mock startup service for this test."""
        return self.registry.get_startup_service()
    
    def get_chat_service(self) -> ChatService:
        """Get the mock chat service for this test."""
        return self.registry.get_chat_service()
    
    def get_sync_manager(self) -> SyncManagerService:
        """Get the mock sync manager for this test."""
        return self.registry.get_sync_manager()
    
    def configure_startup_service(self, **attributes):
        """Configure startup service with specific attributes."""
        startup_service = self.get_startup_service()
        for key, value in attributes.items():
            setattr(startup_service, key, value)
        return startup_service
    
    def configure_chat_service(self, **attributes):
        """Configure chat service with specific attributes."""
        chat_service = self.get_chat_service()
        for key, value in attributes.items():
            setattr(chat_service, key, value)
        return chat_service


def override_dependencies_for_testing(app: FastAPI, **service_overrides):
    """
    Helper function to override specific dependencies in an existing FastAPI app.
    
    Args:
        app: FastAPI application
        **service_overrides: Keyword arguments with dependency names and their overrides
        
    Example:
        override_dependencies_for_testing(
            app,
            startup_service=my_mock_startup_service,
            chat_service=my_mock_chat_service
        )
    """
    from core.dependencies import (
        get_startup_service_dependency,
        get_chat_service_dependency, 
        get_sync_manager_dependency
    )
    
    if 'startup_service' in service_overrides:
        app.dependency_overrides[get_startup_service_dependency] = lambda: service_overrides['startup_service']
    
    if 'chat_service' in service_overrides:
        app.dependency_overrides[get_chat_service_dependency] = lambda startup: service_overrides['chat_service']
    
    if 'sync_manager' in service_overrides:
        app.dependency_overrides[get_sync_manager_dependency] = lambda startup: service_overrides['sync_manager']
    
    logger.info(f"TEST_DEPENDENCIES: Applied {len(service_overrides)} dependency overrides")