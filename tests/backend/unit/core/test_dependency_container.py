"""Tests for the dependency injection container."""

import pytest
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch
from abc import ABC, abstractmethod

from core.dependency_container import DependencyContainer, ServiceLifetime
from core.service_interfaces import ServiceInterface, DatabaseServiceInterface, HTTPClientInterface


class MockService(ServiceInterface):
    """Mock service for testing."""
    
    def __init__(self):
        self.name = "mock"
        self.initialized = False
        self.shutdown_called = False
    
    def initialize(self) -> bool:
        self.initialized = True
        return True
    
    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "name": self.name}
    
    def shutdown(self) -> bool:
        self.shutdown_called = True
        return True


class MockDatabaseService(DatabaseServiceInterface):
    """Mock database service for testing."""
    
    def __init__(self):
        self.initialized = False
        self.shutdown_called = False
    
    def initialize(self) -> bool:
        self.initialized = True
        return True
    
    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "service": "database"}
    
    def shutdown(self) -> bool:
        self.shutdown_called = True
        return True
    
    def get_connection(self):
        return Mock()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        return [{"result": "mock"}]
    
    def execute_transaction(self, queries: List[tuple]) -> bool:
        return True


class MockHTTPClient(HTTPClientInterface):
    """Mock HTTP client for testing."""
    
    def __init__(self):
        self.initialized = False
        self.shutdown_called = False
    
    def initialize(self) -> bool:
        self.initialized = True
        return True
    
    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "service": "http_client"}
    
    def shutdown(self) -> bool:
        self.shutdown_called = True
        return True
    
    def get(self, url: str, **kwargs) -> Dict[str, Any]:
        return {"status": "success", "url": url}
    
    def post(self, url: str, data: Dict, **kwargs) -> Dict[str, Any]:
        return {"status": "success", "url": url, "data": data}
    
    def put(self, url: str, data: Dict, **kwargs) -> Dict[str, Any]:
        return {"status": "success", "url": url, "data": data}
    
    def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        return {"status": "success", "url": url}


class ServiceWithDependency(ServiceInterface):
    """Service that depends on another service."""
    
    def __init__(self, database_service: DatabaseServiceInterface):
        self.database_service = database_service
        self.initialized = False
        self.shutdown_called = False
    
    def initialize(self) -> bool:
        self.initialized = True
        return True
    
    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "dependency": self.database_service.health_check()}
    
    def shutdown(self) -> bool:
        self.shutdown_called = True
        return True


class TestDependencyContainer:
    """Test cases for dependency injection container."""
    
    def test_service_registration_and_resolution(self):
        """Test basic service registration and resolution."""
        container = DependencyContainer()
        
        # Register a service
        container.register(ServiceInterface, MockService)
        
        # Resolve the service
        service = container.resolve(ServiceInterface)
        
        assert isinstance(service, MockService)
        assert service.initialized is True
    
    def test_singleton_behavior(self):
        """Test that singleton services return the same instance."""
        container = DependencyContainer()
        
        # Register as singleton (default behavior)
        container.register(ServiceInterface, MockService)
        
        # Resolve multiple times
        service1 = container.resolve(ServiceInterface)
        service2 = container.resolve(ServiceInterface)
        
        assert service1 is service2
        assert id(service1) == id(service2)
    
    def test_transient_behavior(self):
        """Test that transient services return new instances."""
        container = DependencyContainer()
        
        # Register as transient
        container.register(ServiceInterface, MockService, lifetime=ServiceLifetime.TRANSIENT)
        
        # Resolve multiple times
        service1 = container.resolve(ServiceInterface)
        service2 = container.resolve(ServiceInterface)
        
        assert service1 is not service2
        assert id(service1) != id(service2)
        assert isinstance(service1, MockService)
        assert isinstance(service2, MockService)
    
    def test_dependency_graph_resolution(self):
        """Test complex dependency chain resolution."""
        container = DependencyContainer()
        
        # Register dependencies
        container.register(DatabaseServiceInterface, MockDatabaseService)
        container.register(ServiceWithDependency, ServiceWithDependency)
        
        # Resolve service with dependencies
        service = container.resolve(ServiceWithDependency)
        
        assert isinstance(service, ServiceWithDependency)
        assert isinstance(service.database_service, MockDatabaseService)
        assert service.initialized is True
        assert service.database_service.initialized is True
    
    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        container = DependencyContainer()
        
        class ServiceA(ServiceInterface):
            def __init__(self, service_b: 'ServiceB'):
                self.service_b = service_b
            
            def initialize(self) -> bool:
                return True
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy"}
            
            def shutdown(self) -> bool:
                return True
        
        class ServiceB(ServiceInterface):
            def __init__(self, service_a: ServiceA):
                self.service_a = service_a
            
            def initialize(self) -> bool:
                return True
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy"}
            
            def shutdown(self) -> bool:
                return True
        
        container.register(ServiceA, ServiceA)
        container.register(ServiceB, ServiceB)
        
        # Should raise an exception for circular dependency
        with pytest.raises(ValueError, match="Circular dependency detected"):
            container.resolve(ServiceA)
    
    def test_unregistered_service_raises_error(self):
        """Test that resolving unregistered service raises error."""
        container = DependencyContainer()
        
        with pytest.raises(KeyError, match="Service.*not registered"):
            container.resolve(ServiceInterface)
    
    def test_service_initialization_failure_handling(self):
        """Test handling of service initialization failures."""
        container = DependencyContainer()
        
        class FailingService(ServiceInterface):
            def __init__(self):
                pass
            
            def initialize(self) -> bool:
                return False
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "unhealthy"}
            
            def shutdown(self) -> bool:
                return True
        
        container.register(ServiceInterface, FailingService)
        
        with pytest.raises(RuntimeError, match="Failed to initialize service"):
            container.resolve(ServiceInterface)
    
    def test_constructor_parameter_injection(self):
        """Test that constructor parameters are properly injected."""
        container = DependencyContainer()
        
        # Register services
        container.register(DatabaseServiceInterface, MockDatabaseService)
        container.register(HTTPClientInterface, MockHTTPClient)
        
        class MultiDependencyService(ServiceInterface):
            def __init__(self, db: DatabaseServiceInterface, http: HTTPClientInterface):
                self.db = db
                self.http = http
                self.initialized = False
            
            def initialize(self) -> bool:
                self.initialized = True
                return True
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy"}
            
            def shutdown(self) -> bool:
                return True
        
        container.register(MultiDependencyService, MultiDependencyService)
        
        # Resolve service
        service = container.resolve(MultiDependencyService)
        
        assert isinstance(service.db, MockDatabaseService)
        assert isinstance(service.http, MockHTTPClient)
        assert service.initialized is True
        assert service.db.initialized is True
        assert service.http.initialized is True
    
    def test_container_shutdown(self):
        """Test that container properly shuts down all services."""
        container = DependencyContainer()
        
        # Register multiple services
        container.register(ServiceInterface, MockService)
        container.register(DatabaseServiceInterface, MockDatabaseService)
        
        # Resolve services to create instances
        service1 = container.resolve(ServiceInterface)
        service2 = container.resolve(DatabaseServiceInterface)
        
        # Shutdown container
        container.shutdown()
        
        assert service1.shutdown_called is True
        assert service2.shutdown_called is True
    
    def test_health_check_aggregation(self):
        """Test that container can aggregate health checks from all services."""
        container = DependencyContainer()
        
        # Register services
        container.register(ServiceInterface, MockService)
        container.register(DatabaseServiceInterface, MockDatabaseService)
        
        # Resolve services
        container.resolve(ServiceInterface)
        container.resolve(DatabaseServiceInterface)
        
        # Get health check
        health = container.get_health_status()
        
        assert "services" in health
        assert len(health["services"]) == 2
        assert all(service["status"] == "healthy" for service in health["services"])
    
    def test_service_registration_with_factory_function(self):
        """Test service registration using factory functions."""
        container = DependencyContainer()
        
        def mock_service_factory() -> ServiceInterface:
            service = MockService()
            service.name = "factory_created"
            return service
        
        # Register with factory function
        container.register_factory(ServiceInterface, mock_service_factory)
        
        # Resolve service
        service = container.resolve(ServiceInterface)
        
        assert isinstance(service, MockService)
        assert service.name == "factory_created"
        assert service.initialized is True
    
    def test_service_replacement(self):
        """Test that services can be replaced in the container."""
        container = DependencyContainer()
        
        # Register initial service
        container.register(ServiceInterface, MockService)
        service1 = container.resolve(ServiceInterface)
        
        # Replace with new service using factory
        def replaced_service_factory():
            service = MockService()
            service.name = "replaced"
            return service
        
        container.register_factory(ServiceInterface, replaced_service_factory)
        service2 = container.resolve(ServiceInterface)
        
        # Should be different instances due to re-registration
        assert service1.name == "mock"
        assert service2.name == "replaced"