import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.base_service import (
    AsyncServiceManager,
    BaseService,
    ServiceHealth,
    ServiceStatus,
)


# A concrete implementation of BaseService for testing
class ConcreteService(BaseService):
    def __init__(self, service_name: str, config: dict = None):
        super().__init__(service_name, config)
        self.init_should_succeed = True
        self.shutdown_should_succeed = True
        self.health_should_be_ok = True

    async def _initialize_service(self) -> bool:
        return self.init_should_succeed

    async def _shutdown_service(self) -> bool:
        return self.shutdown_should_succeed

    async def _check_service_health(self) -> dict:
        return {"healthy": self.health_should_be_ok}

@pytest.fixture
def concrete_service():
    """Provides a fresh instance of ConcreteService for each test."""
    return ConcreteService("test_service")

@pytest.mark.asyncio
async def test_initial_state(concrete_service: ConcreteService):
    """Tests the initial state of a service before initialization."""
    assert concrete_service.status == ServiceStatus.UNINITIALIZED
    assert concrete_service.health == ServiceHealth.UNKNOWN
    assert not concrete_service.is_initialized
    assert not concrete_service.is_healthy

@pytest.mark.asyncio
async def test_successful_initialization(concrete_service: ConcreteService):
    """Tests the state transition after a successful initialization."""
    result = await concrete_service.initialize()
    assert result is True
    assert concrete_service.status == ServiceStatus.READY
    assert concrete_service.health == ServiceHealth.HEALTHY
    assert concrete_service.is_initialized
    assert concrete_service.is_healthy

@pytest.mark.asyncio
async def test_failed_initialization(concrete_service: ConcreteService):
    """Tests the state transition after a failed initialization."""
    concrete_service.init_should_succeed = False
    result = await concrete_service.initialize()
    assert result is False
    assert concrete_service.status == ServiceStatus.ERROR
    assert concrete_service.health == ServiceHealth.UNHEALTHY
    assert not concrete_service.is_initialized
    assert not concrete_service.is_healthy

@pytest.mark.asyncio
async def test_successful_shutdown(concrete_service: ConcreteService):
    """Tests the state transition after a successful shutdown."""
    await concrete_service.initialize()
    result = await concrete_service.shutdown()
    assert result is True
    assert concrete_service.status == ServiceStatus.SHUTDOWN
    assert concrete_service.health == ServiceHealth.UNKNOWN

@pytest.mark.asyncio
async def test_failed_shutdown(concrete_service: ConcreteService):
    """Tests the state transition after a failed shutdown."""
    await concrete_service.initialize()
    concrete_service.shutdown_should_succeed = False
    result = await concrete_service.shutdown()
    assert result is False
    assert concrete_service.status == ServiceStatus.SHUTTING_DOWN # Stays in this state on failure
    assert concrete_service._last_error is not None

@pytest.mark.asyncio
async def test_health_check(concrete_service: ConcreteService):
    """Tests the health check mechanism."""
    await concrete_service.initialize()
    health_data = await concrete_service.health_check()
    assert health_data["service_name"] == "test_service"
    assert health_data["status"] == "ready"
    assert health_data["health"] == "healthy"
    assert health_data["is_healthy"] is True

@pytest.mark.asyncio
async def test_unhealthy_health_check(concrete_service: ConcreteService):
    """Tests the health check when the service-specific check fails."""
    await concrete_service.initialize()
    concrete_service.health_should_be_ok = False
    health_data = await concrete_service.health_check()
    assert health_data["health"] == "unhealthy"
    assert health_data["is_healthy"] is False
    assert concrete_service.health == ServiceHealth.UNHEALTHY

@pytest.mark.asyncio
async def test_error_recording_and_resetting(concrete_service: ConcreteService):
    """Tests the error recording and resetting functionality."""
    assert concrete_service._error_count == 0
    assert concrete_service._last_error is None

    concrete_service._record_error("Test error")
    assert concrete_service._error_count == 1
    assert concrete_service._last_error == "Test error"

    concrete_service.reset_error_count()
    assert concrete_service._error_count == 0
    assert concrete_service._last_error is None

def test_dependency_and_capability_management(concrete_service: ConcreteService):
    """Tests adding dependencies and capabilities."""
    assert not concrete_service._dependencies
    concrete_service.add_dependency("database")
    assert "database" in concrete_service._dependencies

    assert not concrete_service._capabilities
    concrete_service.add_capability("data_sync")
    assert "data_sync" in concrete_service._capabilities

# --- AsyncServiceManager Tests ---

@pytest.fixture
def service_manager():
    """Provides a fresh instance of AsyncServiceManager for each test."""
    return AsyncServiceManager()

@pytest.mark.asyncio
async def test_manager_register_service(service_manager: AsyncServiceManager):
    """Tests registering a service with the manager."""
    service = ConcreteService("service1")
    service_manager.register_service(service)
    assert "service1" in service_manager.services
    assert service_manager.services["service1"] is service

@pytest.mark.asyncio
async def test_manager_initialize_all_success(service_manager: AsyncServiceManager):
    """Tests successful initialization of all registered services."""
    service1 = ConcreteService("service1")
    service2 = ConcreteService("service2")
    service_manager.register_service(service1)
    service_manager.register_service(service2)

    results = await service_manager.initialize_all()
    assert results == {"service1": True, "service2": True}
    assert service1.is_initialized
    assert service2.is_initialized

@pytest.mark.asyncio
async def test_manager_initialize_all_partial_failure(service_manager: AsyncServiceManager):
    """Tests partial failure during initialization of services."""
    service1 = ConcreteService("service1")
    service2 = ConcreteService("service2")
    service2.init_should_succeed = False
    service_manager.register_service(service1)
    service_manager.register_service(service2)

    results = await service_manager.initialize_all()
    assert results == {"service1": True, "service2": False}
    assert service1.is_initialized
    assert not service2.is_initialized

@pytest.mark.asyncio
async def test_manager_shutdown_all(service_manager: AsyncServiceManager):
    """Tests shutting down all registered services."""
    service1 = ConcreteService("service1")
    service2 = ConcreteService("service2")
    service_manager.register_service(service1)
    service_manager.register_service(service2)
    await service_manager.initialize_all()

    results = await service_manager.shutdown_all()
    assert results == {"service1": True, "service2": True}
    assert service1.status == ServiceStatus.SHUTDOWN
    assert service2.status == ServiceStatus.SHUTDOWN

@pytest.mark.asyncio
async def test_manager_health_check_all(service_manager: AsyncServiceManager):
    """Tests performing health checks on all registered services."""
    service1 = ConcreteService("service1")
    service2 = ConcreteService("service2")
    service_manager.register_service(service1)
    service_manager.register_service(service2)
    await service_manager.initialize_all()

    health_results = await service_manager.health_check_all()
    assert "service1" in health_results
    assert "service2" in health_results
    assert health_results["service1"]["health"] == "healthy"
    assert health_results["service2"]["health"] == "healthy"
