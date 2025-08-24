# Lifeboard Codebase Cleanup Plan

**DO NOT VIOLATE** 

This document will be updated at the end of completing a task.  Mark as COMPLETE items that are complete

## Tracking
Phase 1: COMPLETE
Phase 2: PENDING
Phase 3: IN PROGRESS

### Phase 1: Critical Architecture Fixes - **COMPLETE**
* Use Test Driven Development.  Write tests first
* Tests are stored in new_lifeboard/tests
- [x] 1.3 Feature Flag Infrastructure (Day 0.5) - **COMPLETE**


### Phase 2: Service Layer Improvements - **IN PROGRESS**
* Use Test Driven Development.  Write tests first
* Tests are stored in new_lifeboard/tests
- [ ] 2.1 Database Connection Management (Days 1-2) - **PENDING**
- [x] 2.2 HTTP Client Unification (Day 3) - **COMPLETE**  
- [x] 2.3 Dependency Injection Container (Days 4-5) - **COMPLETE**

### Phase 3: Test Suite Organization - **IN PROGRESS**
- [x] 3.0 Contract Testing and Performance Regression (Day 0.5) - **COMPLETE**
- [ ] 3.1 Test Reorganization - **PENDING**

### Phase 4: Code Quality Improvements - **PENDING**
* Use Test Driven Development.  Write tests first
* Tests are stored in new_lifeboard/tests
- [ ] 4.0 Quality Metrics Debug Logging (Day 0.5) - **PENDING**
- [ ] 4.1 Service Layer Consolidation - **PENDING**
- [ ] 4.2 Error Handling Standardization - **PENDING**
- [ ] 4.3 Frontend Test Integration - **PENDING**
- [ ] 4.4 Architectural Decision Records and Documentation - **PENDING**

---

## Phase 1: Feature Flag Infrastructure

**Purpose**: Enable gradual rollout and quick rollback of refactored components.

**Implementation**:
```python
# core/feature_flags.py
from typing import Dict, Any
from enum import Enum

class FeatureFlag(Enum):
    NEW_PROCESS_MANAGER = "new_process_manager"
    NEW_SIGNAL_HANDLER = "new_signal_handler"
    NEW_FRONTEND_ORCHESTRATOR = "new_frontend_orchestrator"
    UNIFIED_HTTP_CLIENT = "unified_http_client"
    DEPENDENCY_INJECTION = "dependency_injection"

class FeatureFlagManager:
    def __init__(self, config: Dict[str, bool] = None):
        self.flags = config or {
            FeatureFlag.NEW_PROCESS_MANAGER.value: False,
            FeatureFlag.NEW_SIGNAL_HANDLER.value: False,
            FeatureFlag.NEW_FRONTEND_ORCHESTRATOR.value: False,
            FeatureFlag.UNIFIED_HTTP_CLIENT.value: False,
            FeatureFlag.DEPENDENCY_INJECTION.value: False,
        }
    
    def is_enabled(self, flag: FeatureFlag) -> bool:
        return self.flags.get(flag.value, False)
    
    def enable_flag(self, flag: FeatureFlag):
        self.flags[flag.value] = True
    
    def disable_flag(self, flag: FeatureFlag):
        self.flags[flag.value] = False
```

## Phase 2: Database Connection Management

**Tests First**:
```python
class TestDatabaseConnections:
    def test_connection_pooling(self):
        # Test connection pool behavior
    
    def test_connection_cleanup_on_error(self):
        # Test proper cleanup in exception scenarios
    
    def test_concurrent_database_access(self):
        # Test thread safety
```

**Issues to Address**:
- Potential connection leaks in error scenarios
- No connection pooling  
- Inconsistent cleanup patterns
- Thread-safe connection management

## Phase 2: HTTP Client Unification

**Tests First**:
```python
class TestUnifiedHTTPClient:
    def test_retry_logic(self):
        # Test exponential backoff retry
    
    def test_different_auth_methods(self):
        # Test API key, bearer token auth
    
    def test_error_handling_consistency(self):
        # Test consistent error responses
```

**Implementation Goals**:
- Create unified `HTTPClient` base class
- Standardize retry logic across all API clients
- Consistent error handling and logging
- Support multiple authentication methods

## Phase 2: Dependency Injection Container

**Tests First**:
```python
class TestDependencyContainer:
    def test_service_registration(self):
        # Test service registration and resolution
    
    def test_singleton_behavior(self):
        # Test singleton pattern enforcement
    
    def test_dependency_graph_resolution(self):
        # Test complex dependency chains
```

**Service Interface Design** - **IMPLEMENTED**:
```python
# core/service_interfaces.py - COMPLETE
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class ServiceInterface(ABC):
    """Base interface for all services"""
    
    @abstractmethod
    def initialize(self) -> bool:
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        pass

class DatabaseServiceInterface(ServiceInterface):
    @abstractmethod
    def get_connection(self):
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        pass
    
    @abstractmethod  
    def execute_transaction(self, queries: List[tuple]) -> bool:
        pass

class HTTPClientInterface(ServiceInterface):
    @abstractmethod
    def get(self, url: str, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def post(self, url: str, data: Dict, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def put(self, url: str, data: Dict, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        pass

# Additional interfaces implemented:
# - EmbeddingServiceInterface
# - VectorStoreInterface  
# - ChatServiceInterface
# - IngestionServiceInterface
# - SchedulerServiceInterface
```

**Dependency Injection Container Implementation** - **COMPLETE**:
```python
# core/dependency_container.py - COMPLETE
from enum import Enum
from typing import Any, Dict, Type, TypeVar, Callable, Optional, List, Set
from threading import Lock
from core.service_interfaces import ServiceInterface

class ServiceLifetime(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"

class DependencyContainer:
    """Dependency injection container with constructor injection support"""
    
    def register(self, service_type: Type[T], implementation: Type[T], 
                lifetime: ServiceLifetime = ServiceLifetime.SINGLETON) -> None:
        """Register a service with the container"""
        
    def register_factory(self, service_type: Type[T], factory: Callable[[], T],
                        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON) -> None:
        """Register a service using factory function"""
        
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve service with constructor dependency injection"""
        
    def shutdown(self) -> None:
        """Shutdown all managed services"""
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get aggregated health status from all services"""

# Global container access
def get_container() -> DependencyContainer:
    """Get global dependency container instance"""

# Features implemented:
# ✅ Constructor dependency injection
# ✅ Singleton and transient lifetimes
# ✅ Circular dependency detection
# ✅ Service initialization and shutdown lifecycle
# ✅ Health check aggregation
# ✅ Factory function support
# ✅ Thread-safe operations
# ✅ String annotation support (forward references)
# ✅ Comprehensive test coverage (12 tests, 100% pass)
```

## Phase 3: Test Suite Organization

**Current Issues**:
- 93+ test files with inconsistent naming
- TypeScript test files mixed with Python tests in `/tests/`
- Duplicate test scenarios (calendar: 4 files, news: 5 files, config: 2 files)
- No clear organization structure

**Target Structure**:
```
tests/
├── backend/
│   ├── unit/
│   │   ├── core/
│   │   ├── services/
│   │   ├── api/
│   │   └── sources/
│   ├── integration/
│   │   ├── database/
│   │   ├── api_endpoints/
│   │   └── service_interactions/
│   └── e2e/
│       ├── full_stack/
│       └── user_workflows/
├── frontend/
│   ├── components/
│   ├── integration/
│   └── e2e/
├── fixtures/
└── utilities/
```

## Phase 3.0: Contract Testing and Performance Regression - **COMPLETE**

**Implementation Summary**:

✅ **Contract Testing Infrastructure**:
```
tests/contracts/
├── __init__.py
└── test_service_contracts.py      # Service interface compliance tests
```

- Service interface compliance validation for all services
- Method signature and return type validation  
- Cross-service contract testing
- Health check validation for all services
- Mock service registry for isolated testing

✅ **Performance Regression Framework**:
```
tests/performance/
├── __init__.py  
└── test_performance_benchmarks.py # Performance regression detection
```

- Automated performance benchmarking with configurable thresholds
- Regression detection using statistical analysis
- Historical performance tracking in SQLite database
- Memory usage, execution time, and throughput monitoring
- Performance baselines for critical operations

✅ **Test Examples & Documentation**:
```
tests/examples/
├── __init__.py
├── test_contract_examples.py      # Contract testing best practices
└── test_performance_examples.py   # Performance testing patterns
```

- Comprehensive examples demonstrating testing patterns
- Best practices for contract and performance testing
- Integration examples and utilities

✅ **Enhanced Test Infrastructure**:
- Updated `conftest.py` with new fixtures and pytest markers
- Custom test runner script: `run_contract_and_performance_tests.py`
- New pytest markers: `@pytest.mark.contract`, `@pytest.mark.performance`
- Documentation: `README_CONTRACT_PERFORMANCE.md`

**Services Tested**:
- `ServiceInterface`, `DatabaseServiceInterface`, `HTTPClientInterface`
- `EmbeddingServiceInterface`, `VectorStoreInterface`, `ChatServiceInterface`
- `IngestionServiceInterface`, `SchedulerServiceInterface`

**Performance Benchmarks**:
- Database queries: <100ms threshold
- API responses: <200ms threshold  
- Vector searches: <50ms threshold
- Memory usage: <100MB threshold
- Startup time: <5s threshold

## Phase 4: Service Layer Consolidation

**Service Audit Results** (22+ service files):
```python
# Consolidate related services
class DataProcessingService:
    # Merge: ingestion, semantic_deduplication_service
    
class MonitoringService:
    # Merge: monitor, network_diagnostics, network_recovery
    
class SessionService:
    # Merge: session_lock_manager, port_state_service
```

**Issues to Address**:
- Some services are very specialized (e.g., `port_state_service.py`)
- Overlapping responsibilities between services
- Inconsistent service interfaces

## Phase 4: Error Handling Standardization

**Custom Exception Hierarchy**:
```python
class LifeboardException(Exception):
    """Base exception for Lifeboard application"""

class ConfigurationError(LifeboardException):
    """Configuration-related errors"""

class DatabaseError(LifeboardException):
    """Database operation errors"""

class APIClientError(LifeboardException):
    """External API communication errors"""
```

**Implementation Goals**:
- Replace generic exceptions with specific ones
- Standardize error logging patterns
- Add error recovery mechanisms where appropriate
- Consistent error responses in API endpoints

## Files to Create

### Core Components
- `core/feature_flags.py` - Feature flag management
- `core/http_client.py` - Unified HTTP client
- `core/dependency_container.py` - Dependency injection
- `core/exceptions.py` - Custom exception hierarchy
- `core/service_interfaces.py` - Service contract definitions
- `core/health_checks.py` - Health monitoring endpoints

### Test Infrastructure
- `tests/contracts/test_service_contracts.py` - Interface compliance tests
- `tests/performance/test_performance_benchmarks.py` - Performance regression tests
- `tests/frontend/components/ContentCard.test.tsx` (moved)
- `tests/frontend/components/ExtendedNewsCard.test.tsx` (moved)

### Quality Monitoring
- `tools/quality_monitor.py` - Code quality monitoring
- `tools/error_pattern_analyzer.py` - Error pattern analysis

## Implementation Guidelines

### TDD Workflow
1. **Red**: Write a failing test that defines expected behavior
2. **Green**: Write minimal code to make the test pass
3. **Refactor**: Clean up the code while keeping tests green
4. **Repeat**: Continue with next small increment

### Safety Measures
- Run full test suite before each commit
- Maintain backward compatibility during refactoring
- Create feature branches for each major change
- Deploy incrementally with monitoring
- Keep rollback plan ready for each phase

## Success Metrics

### Quantitative Targets
- **Service files**: Consolidate from 22+ to ~15 focused services
- **Test files**: Organize 93+ files into proper structure
- **Build time**: <2 minutes (from current state)
- **Test suite execution time**: <30 seconds for unit tests

### Qualitative Goals
- Developer satisfaction survey improvement
- Code review feedback improvement
- New developer onboarding experience
- Bug report quality and resolution time

## Required Dependencies
```bash
# Add to requirements.txt
python_json_logger
psutil==5.9.5
coverage==7.3.2
pytest-cov==4.1.0
```