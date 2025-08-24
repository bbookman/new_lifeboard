"""Dependency injection container implementation."""

import inspect
import logging
from enum import Enum
from typing import Any, Dict, Type, TypeVar, Callable, Optional, List, Set
from threading import Lock

from core.service_interfaces import ServiceInterface

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifetime(Enum):
    """Service lifetime management options."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"


class ServiceRegistration:
    """Represents a service registration in the container."""
    
    def __init__(self, 
                 service_type: Type,
                 implementation: Type,
                 lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
                 factory: Optional[Callable] = None):
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.factory = factory
        self.instance: Optional[Any] = None


class DependencyContainer:
    """Dependency injection container for service management.
    
    Provides service registration, resolution, and lifecycle management
    with support for constructor injection and circular dependency detection.
    """
    
    def __init__(self):
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._instances: Dict[Type, Any] = {}
        self._lock = Lock()
        self._resolution_stack: Set[Type] = set()
        
    def register(self, 
                 service_type: Type[T], 
                 implementation: Type[T],
                 lifetime: ServiceLifetime = ServiceLifetime.SINGLETON) -> None:
        """Register a service with the container.
        
        Args:
            service_type: The interface or base class type.
            implementation: The concrete implementation class.
            lifetime: Service lifetime management (singleton or transient).
        """
        with self._lock:
            if not issubclass(implementation, service_type):
                raise ValueError(f"Implementation {implementation.__name__} must inherit from {service_type.__name__}")
            
            self._registrations[service_type] = ServiceRegistration(
                service_type=service_type,
                implementation=implementation,
                lifetime=lifetime
            )
            
            # Clear any existing instance if re-registering
            if service_type in self._instances:
                del self._instances[service_type]
                
            logger.debug(f"Registered {service_type.__name__} -> {implementation.__name__} ({lifetime.value})")
    
    def register_factory(self,
                        service_type: Type[T],
                        factory: Callable[[], T],
                        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON) -> None:
        """Register a service using a factory function.
        
        Args:
            service_type: The interface or base class type.
            factory: Factory function that creates the service instance.
            lifetime: Service lifetime management (singleton or transient).
        """
        with self._lock:
            self._registrations[service_type] = ServiceRegistration(
                service_type=service_type,
                implementation=None,  # Not used for factories
                lifetime=lifetime,
                factory=factory
            )
            
            # Clear any existing instance if re-registering
            if service_type in self._instances:
                del self._instances[service_type]
                
            logger.debug(f"Registered factory for {service_type.__name__} ({lifetime.value})")
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance from the container.
        
        Args:
            service_type: The service type to resolve.
            
        Returns:
            The service instance.
            
        Raises:
            KeyError: If the service is not registered.
            ValueError: If a circular dependency is detected.
            RuntimeError: If service initialization fails.
        """
        if service_type not in self._registrations:
            type_name = getattr(service_type, '__name__', str(service_type))
            raise KeyError(f"Service {type_name} is not registered in the container")
        
        registration = self._registrations[service_type]
        
        # Check for singleton instance
        if (registration.lifetime == ServiceLifetime.SINGLETON and 
            service_type in self._instances):
            return self._instances[service_type]
        
        # Check for circular dependencies
        if service_type in self._resolution_stack:
            stack_names = [t.__name__ for t in self._resolution_stack]
            raise ValueError(f"Circular dependency detected: {' -> '.join(stack_names)} -> {service_type.__name__}")
        
        try:
            self._resolution_stack.add(service_type)
            instance = self._create_instance(registration)
            
            # Initialize the service
            if isinstance(instance, ServiceInterface):
                if not instance.initialize():
                    raise RuntimeError(f"Failed to initialize service {service_type.__name__}")
            
            # Store singleton instances
            if registration.lifetime == ServiceLifetime.SINGLETON:
                self._instances[service_type] = instance
            
            logger.debug(f"Resolved {service_type.__name__}")
            return instance
            
        finally:
            self._resolution_stack.discard(service_type)
    
    def _create_instance(self, registration: ServiceRegistration) -> Any:
        """Create a service instance using constructor injection.
        
        Args:
            registration: The service registration.
            
        Returns:
            The created service instance.
        """
        if registration.factory:
            return registration.factory()
        
        implementation = registration.implementation
        
        # Get constructor signature
        sig = inspect.signature(implementation.__init__)
        
        # Resolve constructor dependencies
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            if param.annotation == inspect.Parameter.empty:
                raise ValueError(f"Parameter {param_name} in {implementation.__name__} must have type annotation")
            
            # Handle string annotations (forward references)
            annotation = param.annotation
            if isinstance(annotation, str):
                # For string annotations, we need to look up the type in the registry
                # This is a simplified approach - in a more complex system you'd want
                # to resolve the string to an actual type
                matching_types = [t for t in self._registrations.keys() if t.__name__ == annotation]
                if matching_types:
                    annotation = matching_types[0]
                else:
                    raise KeyError(f"Cannot resolve string annotation '{annotation}' for parameter {param_name}")
            
            # Resolve dependency
            dependency = self.resolve(annotation)
            kwargs[param_name] = dependency
        
        # Create instance with injected dependencies
        return implementation(**kwargs)
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered.
        
        Args:
            service_type: The service type to check.
            
        Returns:
            True if the service is registered, False otherwise.
        """
        return service_type in self._registrations
    
    def get_registered_services(self) -> List[Type]:
        """Get a list of all registered service types.
        
        Returns:
            List of registered service types.
        """
        return list(self._registrations.keys())
    
    def shutdown(self) -> None:
        """Shutdown all managed services and clean up resources."""
        with self._lock:
            shutdown_errors = []
            
            for service_type, instance in self._instances.items():
                try:
                    if isinstance(instance, ServiceInterface):
                        if not instance.shutdown():
                            logger.warning(f"Service {service_type.__name__} reported shutdown failure")
                    logger.debug(f"Shutdown {service_type.__name__}")
                except Exception as e:
                    logger.error(f"Error shutting down {service_type.__name__}: {e}")
                    shutdown_errors.append((service_type, e))
            
            # Clear all instances
            self._instances.clear()
            
            if shutdown_errors:
                error_summary = ", ".join([f"{t.__name__}: {str(e)}" for t, e in shutdown_errors])
                logger.error(f"Shutdown completed with errors: {error_summary}")
            else:
                logger.info("All services shutdown successfully")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get aggregated health status from all resolved services.
        
        Returns:
            Dictionary containing overall health status and individual service health.
        """
        services_health = []
        overall_healthy = True
        
        for service_type, instance in self._instances.items():
            if isinstance(instance, ServiceInterface):
                try:
                    health = instance.health_check()
                    health['service_type'] = service_type.__name__
                    services_health.append(health)
                    
                    if health.get('status') != 'healthy':
                        overall_healthy = False
                        
                except Exception as e:
                    logger.error(f"Health check failed for {service_type.__name__}: {e}")
                    services_health.append({
                        'service_type': service_type.__name__,
                        'status': 'unhealthy',
                        'error': str(e)
                    })
                    overall_healthy = False
        
        return {
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'services': services_health,
            'total_services': len(self._instances)
        }
    
    def clear(self) -> None:
        """Clear all registrations and instances (for testing purposes)."""
        with self._lock:
            self._registrations.clear()
            self._instances.clear()
            self._resolution_stack.clear()
            logger.debug("Container cleared")


# Global container instance
_container: Optional[DependencyContainer] = None
_container_lock = Lock()


def get_container() -> DependencyContainer:
    """Get the global dependency container instance.
    
    Returns:
        The global DependencyContainer instance.
    """
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = DependencyContainer()
    return _container


def reset_container() -> None:
    """Reset the global container (primarily for testing)."""
    global _container
    with _container_lock:
        if _container:
            _container.shutdown()
        _container = None