# Test Fixup Plan: fixup.md

## Executive Summary

Based on the comprehensive test analysis, this plan addresses the systematic failures in the Lifeboard test suite. The current state shows **88 failed tests out of 138 API tests** (63.8% failure rate) due to outdated dependency injection patterns, non-existent API endpoints, and misaligned service mocks.

## Root Cause Analysis

### Primary Issues
1. **Dependency Injection Inconsistency**: 69 tests use manual `patch` statements instead of FastAPI's dependency override system
2. **Outdated API Endpoints**: Tests reference deprecated endpoints missing `/api/` prefix
3. **Non-existent Service Methods**: Tests mock methods like `get_calendar_month_data` that don't exist in actual services
4. **Inconsistent Test Patterns**: Mix of working dependency override pattern (health tests) vs broken manual patching

### Test Categories Affected
- **API Routes**: Calendar, Chat, Health, Sync, System, WebSocket (154 tests total)
- **Backend Services**: Unit tests for core services and database operations
- **Integration Tests**: Service interaction and full-stack workflows
- **Frontend Tests**: UI components and integration

## Phase 1: Foundation Repair (Priority: Critical)

### 1.1 Standardize Dependency Injection Pattern
**Target**: All API tests use consistent FastAPI dependency override
**Timeline**: 2-3 days
**Files**: All `tests/api/test_*.py` files

**Changes**:
- Update all test class `app` fixtures to use dependency overrides like `tests/api/test_health_simple.py`
- Remove manual `patch('*.get_startup_service_dependency')` calls (69 instances)
- Implement consistent service mocking pattern

**Template Pattern**:
```python
@pytest.fixture
def app(self, mock_startup_service):
    from core.dependencies import get_startup_service_dependency
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
    return app
```

### 1.2 Fix API Endpoint References
**Target**: Update deprecated endpoint URLs
**Timeline**: 1 day
**Files**: All API test files

**Changes**:
- Calendar routes: `/calendar/month` → `/calendar/api/month`
- Calendar routes: `/calendar/day` → `/calendar/api/day`  
- Verify all other route prefixes match actual FastAPI router configurations

### 1.3 Align Service Method Mocks
**Target**: Mock only methods that exist in actual service classes
**Timeline**: 2 days
**Files**: `tests/fixtures/service_fixtures.py` and all test files

**Changes**:
- Remove mocks for `get_calendar_month_data`, `get_calendar_day_data`
- Use actual DatabaseService methods: `get_days_with_data`, `get_data_items_by_date`, `get_markdown_by_date`
- Update ChatService, SyncManagerService, and other service mocks to match implementations

## Phase 2: Service Integration Repair (Priority: High)

### 2.1 Database Service Tests
**Target**: Fix database-dependent tests
**Timeline**: 2 days

**Changes**:
- Update all database service mocks to use methods from `core/database.py`
- Fix calendar tests to use correct database methods
- Ensure in-memory database fixtures work properly

### 2.2 Chat Service Integration
**Target**: Fix chat-related API tests
**Timeline**: 1-2 days

**Changes**:
- Update ChatService mocks to match `services/chat_service.py`
- Fix WebSocket manager tests
- Ensure chat API endpoints work with dependency injection

### 2.3 Sync Manager Tests  
**Target**: Fix synchronization service tests
**Timeline**: 1-2 days

**Changes**:
- Update SyncManagerService mocks
- Fix sync route tests
- Ensure background task integration works

## Phase 3: Test Infrastructure Enhancement (Priority: Medium)

### 3.1 Enhanced Test Fixtures
**Target**: Improve shared test infrastructure
**Timeline**: 2-3 days

**Changes**:
- Enhance `tests/fixtures/service_fixtures.py` with proper service mocks
- Add database fixtures with realistic test data  
- Create API client fixtures with proper authentication
- Add integration test utilities

### 3.2 Test Data Management
**Target**: Consistent test data across test suites
**Timeline**: 1-2 days

**Changes**:
- Create standardized test data in `tests/fixtures/data_fixtures.py`
- Add calendar test data that matches actual API responses
- Create realistic service response fixtures

## Phase 4: Validation and Coverage (Priority: Medium)

### 4.1 Test Execution Validation
**Target**: Ensure all tests pass consistently
**Timeline**: 2-3 days

**Activities**:
- Run full test suite after each phase
- Fix any remaining dependency issues
- Validate test isolation (no cross-test contamination)

### 4.2 Test Coverage Analysis
**Target**: Identify coverage gaps
**Timeline**: 1 day

**Activities**:
- Generate coverage report for all modules
- Identify untested code paths
- Add tests for critical missing coverage

## Phase 5: Performance and Reliability (Priority: Low)

### 5.1 Test Performance Optimization
**Target**: Reduce test execution time
**Timeline**: 1-2 days

**Activities**:
- Profile slow tests (marked as `@pytest.mark.slow`)
- Optimize database fixtures
- Parallelize independent test execution

### 5.2 Continuous Integration Readiness
**Target**: Prepare tests for CI/CD pipeline
**Timeline**: 1 day

**Activities**:
- Ensure tests work in clean environments
- Add proper test dependencies
- Create test execution scripts

## Implementation Strategy

### Execution Order
1. **Week 1**: Phase 1 (Foundation Repair) - Critical fixes
2. **Week 2**: Phase 2 (Service Integration) - High priority fixes  
3. **Week 3**: Phase 3 (Infrastructure) + Phase 4 (Validation)
4. **Week 4**: Phase 5 (Performance) + Documentation

### Success Metrics
- **Phase 1 Complete**: API test failure rate < 20%
- **Phase 2 Complete**: API test failure rate < 10%
- **Phase 3 Complete**: All service integration tests pass
- **Phase 4 Complete**: Test coverage > 80%, all tests pass
- **Phase 5 Complete**: Average test execution time < 30s

### Risk Mitigation
- **Incremental Approach**: Fix tests file by file to avoid breaking working tests
- **Validation Gates**: Run full test suite after each major change
- **Backup Strategy**: Commit working fixes frequently
- **Documentation**: Update test documentation as patterns change

## Expected Outcomes

- **Short Term**: 90%+ of tests passing within 2 weeks
- **Medium Term**: Robust test infrastructure supporting CI/CD
- **Long Term**: Maintainable test suite that prevents regression

## Effort Estimate
- **Total Time**: 2-3 weeks of focused development
- **Complexity**: Medium-High (systematic refactoring required)
- **Risk Level**: Low-Medium (incremental approach reduces risk)

## Status Tracking

### Phase 1 Progress
- [ ] 1.1 Standardize Dependency Injection Pattern
- [ ] 1.2 Fix API Endpoint References  
- [ ] 1.3 Align Service Method Mocks
- [ ] Validation: API test failure rate < 20%

### Phase 2 Progress
- [ ] 2.1 Database Service Tests
- [ ] 2.2 Chat Service Integration
- [ ] 2.3 Sync Manager Tests
- [ ] Validation: API test failure rate < 10%

### Phase 3 Progress
- [ ] 3.1 Enhanced Test Fixtures
- [ ] 3.2 Test Data Management

### Phase 4 Progress
- [ ] 4.1 Test Execution Validation
- [ ] 4.2 Test Coverage Analysis

### Phase 5 Progress
- [ ] 5.1 Test Performance Optimization
- [ ] 5.2 Continuous Integration Readiness

---

*Document created: 2025-01-27*
*Last updated: 2025-01-27*