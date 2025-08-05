"""
Base service class providing common functionality for all services

This module provides a base class that standardizes service initialization,
health checking, status tracking, and error handling patterns across all services.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone
from enum import Enum

from .exception_handling import ServiceError, ErrorAccumulator, safe_operation


class ServiceStatus(Enum):
    """Service status enumeration"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


class ServiceHealth(Enum):
    """Service health enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class BaseService(ABC):
    """
    Abstract base class for all services providing common functionality
    
    This class standardizes:
    - Service lifecycle management (initialization, shutdown)
    - Health checking and status reporting
    - Error handling and logging
    - Configuration management
    - Dependency tracking
    """
    
    def __init__(self, service_name: str, config: Optional[Any] = None):
        """
        Initialize base service
        
        Args:
            service_name: Name of the service for logging and identification
            config: Optional configuration object
        """
        self.service_name = service_name
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # Service state tracking
        self._status = ServiceStatus.UNINITIALIZED
        self._health = ServiceHealth.UNKNOWN
        self._initialization_time: Optional[datetime] = None
        self._last_health_check: Optional[datetime] = None
        self._error_count = 0
        self._last_error: Optional[str] = None
        
        # Dependencies and capabilities
        self._dependencies: List[str] = []
        self._capabilities: List[str] = []
        
        # Health check configuration
        self._health_check_interval = 300  # 5 minutes default
        self._max_error_threshold = 5
        
        self.logger.debug(f"Initialized {self.service_name} service")
    
    @property
    def status(self) -> ServiceStatus:
        """Get current service status"""
        return self._status
    
    @property
    def health(self) -> ServiceHealth:
        """Get current service health"""
        return self._health
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized and ready"""
        return self._status == ServiceStatus.READY
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self._health == ServiceHealth.HEALTHY
    
    async def initialize(self) -> bool:
        """
        Initialize the service
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._status != ServiceStatus.UNINITIALIZED:
            self.logger.warning(f"Service {self.service_name} already initialized or in invalid state: {self._status}")
            return self._status == ServiceStatus.READY
        
        self._status = ServiceStatus.INITIALIZING
        self.logger.info(f"Initializing {self.service_name} service...")
        
        try:
            # Run service-specific initialization
            success = await self._initialize_service()
            
            if success:
                self._status = ServiceStatus.READY
                self._health = ServiceHealth.HEALTHY
                self._initialization_time = datetime.now(timezone.utc)
                self.logger.info(f"Successfully initialized {self.service_name} service")
                return True
            else:
                self._status = ServiceStatus.ERROR
                self._health = ServiceHealth.UNHEALTHY
                self.logger.error(f"Failed to initialize {self.service_name} service")
                return False
                
        except Exception as e:
            self._status = ServiceStatus.ERROR
            self._health = ServiceHealth.UNHEALTHY
            self._record_error(f"Initialization failed: {str(e)}")
            self.logger.error(f"Exception during {self.service_name} initialization: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """
        Shutdown the service gracefully
        
        Returns:
            bool: True if shutdown successful, False otherwise
        """
        if self._status == ServiceStatus.SHUTDOWN:
            return True
        
        self._status = ServiceStatus.SHUTTING_DOWN
        self.logger.info(f"Shutting down {self.service_name} service...")
        
        try:
            # Run service-specific shutdown
            success = await self._shutdown_service()
            
            if success:
                self._status = ServiceStatus.SHUTDOWN
                self._health = ServiceHealth.UNKNOWN
                self.logger.info(f"Successfully shutdown {self.service_name} service")
                return True
            else:
                self._record_error(f"Failed to shutdown {self.service_name} service cleanly")
                return False
                
        except Exception as e:
            self._record_error(f"Shutdown failed: {str(e)}")
            self.logger.error(f"Exception during {self.service_name} shutdown: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check
        
        Returns:
            Dict containing health status and details
        """
        self._last_health_check = datetime.now(timezone.utc)
        
        health_data = {
            "service_name": self.service_name,
            "status": self._status.value,
            "health": self._health.value,
            "is_healthy": self.is_healthy,
            "initialization_time": self._initialization_time.isoformat() if self._initialization_time else None,
            "last_health_check": self._last_health_check.isoformat(),
            "error_count": self._error_count,
            "last_error": self._last_error,
            "dependencies": self._dependencies,
            "capabilities": self._capabilities
        }
        
        try:
            # Run service-specific health checks
            service_health = await self._check_service_health()
            health_data.update(service_health)
            
            # Update health status based on checks
            if self._status == ServiceStatus.READY:
                if self._error_count > self._max_error_threshold:
                    self._health = ServiceHealth.DEGRADED
                elif service_health.get("healthy", True):
                    self._health = ServiceHealth.HEALTHY
                else:
                    self._health = ServiceHealth.UNHEALTHY
            
            health_data["health"] = self._health.value
            health_data["is_healthy"] = self.is_healthy
            
        except Exception as e:
            self._record_error(f"Health check failed: {str(e)}")
            self._health = ServiceHealth.UNHEALTHY
            health_data["health_check_error"] = str(e)
            health_data["health"] = self._health.value
            health_data["is_healthy"] = False
        
        return health_data
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of service status
        
        Returns:
            Dict containing basic status information
        """
        return {
            "service_name": self.service_name,
            "status": self._status.value,
            "health": self._health.value,
            "is_initialized": self.is_initialized,
            "is_healthy": self.is_healthy,
            "error_count": self._error_count,
            "initialization_time": self._initialization_time.isoformat() if self._initialization_time else None
        }
    
    def add_dependency(self, dependency_name: str):
        """Add a service dependency"""
        if dependency_name not in self._dependencies:
            self._dependencies.append(dependency_name)
    
    def add_capability(self, capability_name: str):
        """Add a service capability"""
        if capability_name not in self._capabilities:
            self._capabilities.append(capability_name)
    
    def _record_error(self, error_message: str):
        """Record an error for tracking"""
        self._error_count += 1
        self._last_error = error_message
        self.logger.error(f"{self.service_name}: {error_message}")
    
    def reset_error_count(self):
        """Reset error count (useful after recovery)"""
        self._error_count = 0
        self._last_error = None
    
    # Abstract methods that must be implemented by concrete services
    
    @abstractmethod
    async def _initialize_service(self) -> bool:
        """
        Service-specific initialization logic
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    async def _shutdown_service(self) -> bool:
        """
        Service-specific shutdown logic (optional override)
        
        Returns:
            bool: True if shutdown successful, False otherwise
        """
        return True
    
    async def _check_service_health(self) -> Dict[str, Any]:
        """
        Service-specific health check logic (optional override)
        
        Returns:
            Dict containing service-specific health information
        """
        return {"healthy": True}


class AsyncServiceManager:
    """Manager for multiple services with lifecycle coordination"""
    
    def __init__(self):
        self.services: Dict[str, BaseService] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_service(self, service: BaseService):
        """Register a service for management"""
        self.services[service.service_name] = service
        self.logger.debug(f"Registered service: {service.service_name}")
    
    async def initialize_all(self) -> Dict[str, bool]:
        """Initialize all registered services"""
        results = {}
        
        for name, service in self.services.items():
            try:
                self.logger.info(f"Initializing service: {name}")
                success = await service.initialize()
                results[name] = success
                
                if success:
                    self.logger.info(f"Service {name} initialized successfully")
                else:
                    self.logger.error(f"Service {name} failed to initialize")
                    
            except Exception as e:
                self.logger.error(f"Exception initializing service {name}: {e}")
                results[name] = False
        
        return results
    
    async def shutdown_all(self) -> Dict[str, bool]:
        """Shutdown all registered services"""
        results = {}
        
        # Shutdown in reverse order of registration
        for name in reversed(list(self.services.keys())):
            service = self.services[name]
            try:
                self.logger.info(f"Shutting down service: {name}")
                success = await service.shutdown()
                results[name] = success
                
                if success:
                    self.logger.info(f"Service {name} shutdown successfully")
                else:
                    self.logger.error(f"Service {name} failed to shutdown cleanly")
                    
            except Exception as e:
                self.logger.error(f"Exception shutting down service {name}: {e}")
                results[name] = False
        
        return results
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health checks on all services"""
        results = {}
        
        for name, service in self.services.items():
            try:
                health_data = await service.health_check()
                results[name] = health_data
            except Exception as e:
                results[name] = {
                    "service_name": name,
                    "health": "unhealthy",
                    "error": str(e)
                }
        
        return results
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status summary for all services"""
        return {
            name: service.get_status_summary()
            for name, service in self.services.items()
        }