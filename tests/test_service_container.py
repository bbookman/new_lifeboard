"""
Test-driven development tests for ServiceContainer implementation.

This test file ensures the ServiceContainer class works correctly for dependency
management and service registration before implementing the actual functionality.
"""

import pytest
from unittest.mock import Mock


class TestServiceContainer:
    """Test ServiceContainer class functionality."""

    def test_service_container_initialization(self):
        """Test ServiceContainer can be created and initialized."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        assert container is not None
        assert hasattr(container, '_services')
        assert isinstance(container._services, dict)
        assert len(container._services) == 0

    def test_register_service(self):
        """Test registering a service in the container."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        mock_service = Mock()
        
        container.register("test_service", mock_service)
        
        assert "test_service" in container._services
        assert container._services["test_service"] is mock_service

    def test_get_registered_service(self):
        """Test retrieving a registered service."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        mock_service = Mock()
        
        container.register("test_service", mock_service)
        retrieved_service = container.get("test_service")
        
        assert retrieved_service is mock_service

    def test_get_unregistered_service_raises_error(self):
        """Test getting an unregistered service raises KeyError."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        
        with pytest.raises(KeyError, match="Service 'nonexistent' not registered"):
            container.get("nonexistent")

    def test_register_multiple_services(self):
        """Test registering multiple services."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        service1 = Mock()
        service2 = Mock()
        
        container.register("service1", service1)
        container.register("service2", service2)
        
        assert container.get("service1") is service1
        assert container.get("service2") is service2
        assert len(container._services) == 2

    def test_register_overwrites_existing_service(self):
        """Test that registering with same name overwrites previous service."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        old_service = Mock()
        new_service = Mock()
        
        container.register("service", old_service)
        container.register("service", new_service)
        
        assert container.get("service") is new_service
        assert container.get("service") is not old_service


class TestServiceContainerGlobalInstance:
    """Test global service container instance functionality."""

    def test_get_service_container_function_exists(self):
        """Test that get_service_container function exists and returns ServiceContainer."""
        from services.startup import get_service_container, ServiceContainer
        
        container = get_service_container()
        assert isinstance(container, ServiceContainer)

    def test_get_service_container_returns_same_instance(self):
        """Test that get_service_container returns the same instance (singleton)."""
        from services.startup import get_service_container
        
        container1 = get_service_container()
        container2 = get_service_container()
        
        assert container1 is container2

    def test_global_container_persistence(self):
        """Test that global container persists services across calls."""
        from services.startup import get_service_container
        
        container1 = get_service_container()
        mock_service = Mock()
        container1.register("persistent_service", mock_service)
        
        container2 = get_service_container()
        retrieved_service = container2.get("persistent_service")
        
        assert retrieved_service is mock_service


class TestServiceContainerIntegration:
    """Test ServiceContainer integration with existing routes."""

    def test_websocket_route_can_access_service_container(self):
        """Test that WebSocket route can import and use service container."""
        from services.startup import get_service_container
        
        # This should not raise ImportError
        container = get_service_container()
        assert container is not None

    def test_clean_up_crew_route_can_access_service_container(self):
        """Test that clean up crew route can import and use service container."""
        from services.startup import get_service_container
        
        # This should not raise ImportError
        container = get_service_container()
        assert container is not None

    def test_service_container_with_mock_services(self):
        """Test ServiceContainer with mock services like those used in routes."""
        from services.startup import get_service_container
        
        container = get_service_container()
        
        # Mock the services that routes expect
        mock_websocket_manager = Mock()
        mock_clean_up_crew_service = Mock()
        
        container.register("websocket_manager", mock_websocket_manager)
        container.register("clean_up_crew_service", mock_clean_up_crew_service)
        
        # Test retrieval
        assert container.get("websocket_manager") is mock_websocket_manager
        assert container.get("clean_up_crew_service") is mock_clean_up_crew_service


class TestServiceContainerErrorHandling:
    """Test error handling in ServiceContainer."""

    def test_get_service_with_none_name(self):
        """Test getting service with None name raises appropriate error."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        
        with pytest.raises((KeyError, TypeError)):
            container.get(None)

    def test_register_service_with_none_name(self):
        """Test registering service with None name raises appropriate error.""" 
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        mock_service = Mock()
        
        with pytest.raises((KeyError, TypeError)):
            container.register(None, mock_service)

    def test_register_none_service(self):
        """Test registering None as a service (should be allowed)."""
        from services.startup import ServiceContainer
        
        container = ServiceContainer()
        
        # This should be allowed - None can be a valid service value
        container.register("none_service", None)
        assert container.get("none_service") is None