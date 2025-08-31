# Testing Standards for Lifeboard

## Overview

This document establishes comprehensive testing standards for the Lifeboard project, ensuring consistent, maintainable, and effective testing practices across all development activities.

## Testing Philosophy

### Core Principles
- **Test-Driven Development**: Write tests before implementation when possible
- **Evidence-Based Quality**: All quality claims must be verifiable through tests
- **Isolation**: Tests should be independent and not rely on external state
- **Fast Feedback**: Tests should execute quickly to support rapid development
- **Realistic Testing**: Use realistic data and scenarios that mirror production usage

### Quality Gates
- **Minimum Coverage**: 80% overall code coverage
- **Test Pass Rate**: >95% of tests must pass consistently
- **Performance**: Full test suite should complete in <30 seconds
- **Reliability**: No flaky tests - tests must be deterministic

## Test Organization

### Directory Structure
```
tests/
├── unit/                     # Unit tests (60% of test suite)
│   ├── core/                # Core module tests
│   ├── services/            # Service layer tests
│   ├── sources/             # Data source tests
│   ├── llm/                 # LLM integration tests
│   └── config/              # Configuration tests
├── integration/             # Integration tests (30% of test suite)
│   ├── api/                 # API endpoint tests
│   ├── database/            # Database integration tests
│   ├── external_services/   # External API tests
│   └── workflows/           # Multi-service workflow tests
├── e2e/                     # End-to-end tests (10% of test suite)
│   ├── user_journeys/       # Complete user scenarios
│   └── system_tests/        # Full system validation
├── fixtures/                # Shared test fixtures
│   ├── config_fixtures.py   # Configuration builders
│   ├── database_fixtures.py # Database lifecycle management
│   ├── api_fixtures.py      # HTTP client mocking
│   ├── service_fixtures.py  # Service dependency injection
│   └── data_fixtures.py     # Realistic test data
└── utils/                   # Testing utilities
    ├── test_helpers.py      # Common test utilities
    ├── mock_builders.py     # Mock object builders
    └── data_generators.py   # Test data generators
```

### Test Categories

#### Unit Tests
- **Purpose**: Test individual functions/methods in isolation
- **Scope**: Single class or function
- **Dependencies**: Mock all external dependencies
- **Execution Time**: <1ms per test
- **Coverage Target**: 90% of unit-testable code

#### Integration Tests
- **Purpose**: Test component interactions and data flow
- **Scope**: Multiple components working together
- **Dependencies**: Real database, mocked external APIs
- **Execution Time**: <100ms per test
- **Coverage Target**: 70% of integration scenarios

#### End-to-End Tests
- **Purpose**: Validate complete user workflows
- **Scope**: Full application stack
- **Dependencies**: Test database, mocked external services
- **Execution Time**: <5s per test
- **Coverage Target**: 90% of critical user journeys

## Naming Conventions

### Test Files
- **Unit tests**: `test_<module_name>.py`
- **Integration tests**: `test_<component>_integration.py`
- **End-to-end tests**: `test_<workflow>_e2e.py`
- **Performance tests**: `test_<module>_performance.py`

### Test Methods
- **Pattern**: `test_<method_name>_<scenario>_<expected_outcome>`
- **Examples**:
  - `test_store_data_item_with_valid_data_succeeds`
  - `test_fetch_limitless_data_with_invalid_api_key_raises_error`
  - `test_generate_embedding_with_empty_text_returns_none`

### Test Classes
- **Pattern**: `Test<ComponentName>`
- **Examples**:
  - `TestDatabaseService`
  - `TestLimitlessSource`
  - `TestIngestionWorkflow`

## Fixture Usage Standards

### Shared Fixtures
All tests should use the centralized fixtures from `tests/fixtures/`:

```python
# Import shared fixtures
from tests.fixtures.config_fixtures import limitless_config, app_config
from tests.fixtures.database_fixtures import clean_database, sample_data_items  
from tests.fixtures.service_fixtures import mock_database_service
from tests.fixtures.api_fixtures import limitless_client_mock
from tests.fixtures.data_fixtures import sample_limitless_items
```

### Fixture Scopes
- **function**: Default scope, new instance per test (database, mocks)
- **class**: Shared across test class (configuration, test data)
- **module**: Shared across test module (expensive setup)
- **session**: Shared across test session (global configuration)

### Custom Fixtures
When creating custom fixtures:
```python
@pytest.fixture
def custom_scenario():
    """
    Brief description of what this fixture provides.
    
    Returns:
        Type: Description of return value
    """
    # Setup
    yield resource
    # Cleanup
```

## Mock Strategy

### External Services
- **HTTP APIs**: Use `api_fixtures.py` for consistent HTTP mocking
- **Database**: Use `database_fixtures.py` for isolated test databases
- **File System**: Mock file operations to avoid test environment dependencies
- **Time**: Use `freezegun` for time-dependent tests

### Service Dependencies
```python
# Use service fixtures for dependency injection
def test_ingestion_service_with_mocked_dependencies(
    mock_database_service,
    mock_embedding_service,
    mock_vector_store_service
):
    ingestion_service = IngestionService(
        db_service=mock_database_service,
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store_service
    )
    # Test logic here
```

### Mock Configuration
- **Be Explicit**: Configure mock behaviors explicitly for test clarity
- **Realistic Responses**: Use realistic data from `data_fixtures.py`
- **Error Scenarios**: Test both success and failure cases
- **State Verification**: Assert that mocks were called with expected parameters

## Test Data Management

### Realistic Test Data
Use `data_fixtures.py` for generating realistic test data:

```python
def test_limitless_processing_with_realistic_data(sample_limitless_items):
    """Test processing with realistic Limitless data"""
    processor = LimitlessProcessor()
    
    for item in sample_limitless_items:
        result = processor.process(item)
        assert result is not None
        assert result.namespace == "limitless"
```

### Data Consistency
- **Reproducible**: Use fixed seeds for random data generation
- **Varied**: Include edge cases and boundary conditions
- **Realistic**: Mirror production data patterns and volumes
- **Isolated**: Each test should have independent data

### Test Database Management
```python
def test_with_isolated_database(clean_database, sample_data_items):
    """Example of proper test database usage"""
    # Database starts clean
    assert clean_database.count_all_items() == 0
    
    # Insert test data
    for item in sample_data_items:
        clean_database.store_data_item(**item)
    
    # Test operations
    result = clean_database.get_data_items_by_namespace("limitless")
    assert len(result) > 0
    
    # Database cleaned up automatically
```

## Assertion Standards

### Clear Assertions
```python
# Good: Specific and descriptive
assert response.status_code == 200, f"Expected 200, got {response.status_code}"
assert len(results) == 3, f"Expected 3 results, got {len(results)}"
assert "error" not in response.json(), f"Unexpected error in response: {response.json()}"

# Avoid: Generic assertions
assert response.ok
assert results
assert not response.json().get("error")
```

### Error Testing
```python
def test_invalid_input_raises_specific_error():
    """Test that invalid input raises the expected error type"""
    with pytest.raises(ValueError, match="Invalid API key format"):
        LimitlessConfig(api_key="")
```

### Async Testing
```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations properly"""
    result = await async_function()
    assert result is not None
```

## Performance Testing

### Benchmarking
```python
@pytest.mark.performance
def test_database_query_performance(large_dataset_database):
    """Test query performance with large dataset"""
    import time
    
    start_time = time.perf_counter()
    results = database.search_data_items("test query")
    end_time = time.perf_counter()
    
    assert len(results) > 0
    assert (end_time - start_time) < 0.1  # Should complete in <100ms
```

### Memory Testing
```python
def test_memory_usage_within_limits():
    """Test that operations don't exceed memory limits"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Perform memory-intensive operation
    result = process_large_dataset()
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # Should not increase by more than 100MB
    assert memory_increase < 100 * 1024 * 1024
```

## Error Handling Testing

### Exception Testing
```python
def test_error_handling_and_recovery():
    """Test that services handle errors gracefully"""
    mock_service = MagicMock()
    mock_service.fetch_data.side_effect = ConnectionError("Network unavailable")
    
    # Should handle error gracefully
    result = sync_manager.sync_source("test_source", mock_service)
    
    assert result["success"] is False
    assert "Network unavailable" in result["error"]
    assert result["retry_recommended"] is True
```

### Logging Verification
```python
def test_error_logging(caplog):
    """Test that errors are logged appropriately"""
    with caplog.at_level(logging.ERROR):
        service.risky_operation()
    
    assert "Expected error message" in caplog.text
    assert caplog.records[0].levelname == "ERROR"
```

## Continuous Integration Standards

### Test Execution
```bash
# Run all tests with coverage
pytest --cov=. --cov-fail-under=80 --cov-report=html

# Run specific test categories
pytest -m unit                    # Unit tests only
pytest -m integration            # Integration tests only
pytest -m "not slow"             # Skip slow tests

# Run with performance monitoring
pytest --benchmark-only
```

### Quality Gates
- **All tests must pass**: No failing tests allowed in main branch
- **Coverage threshold**: Minimum 80% overall coverage
- **Performance regression**: No tests should become >50% slower
- **Memory leaks**: No significant memory growth during test runs

## Test Documentation

### Test Documentation Standards
```python
def test_complex_business_logic():
    """
    Test complex business logic with multiple scenarios.
    
    This test verifies that:
    1. Valid input produces expected output
    2. Edge cases are handled correctly
    3. Error conditions raise appropriate exceptions
    
    Test scenario:
    - Given: A configured service with valid dependencies
    - When: Processing a complex data item with metadata
    - Then: The output should match expected format and content
    """
```

### README Updates
- Document test execution procedures
- Explain test data requirements
- Describe mock service configurations
- Provide troubleshooting guides for common test failures

## Common Anti-Patterns to Avoid

### Bad Practices
```python
# DON'T: Tests dependent on external state
def test_depends_on_previous_test():
    # Assumes previous test ran and left data
    
# DON'T: Overly complex test logic
def test_with_complex_loops_and_conditions():
    for i in range(100):
        if complex_condition(i):
            # Complex test logic
            
# DON'T: Testing implementation details
def test_private_method_implementation():
    assert service._private_method() == "expected"
    
# DON'T: Shared mutable state
shared_data = {"modified": "by tests"}
```

### Good Practices
```python
# DO: Independent, focused tests
def test_single_responsibility():
    """Test one specific behavior"""
    
# DO: Test public interfaces
def test_public_api_behavior():
    """Test through public methods only"""
    
# DO: Use descriptive test data
def test_with_descriptive_data():
    user = User(name="John Doe", age=30, role="admin")
```

## Debugging Test Failures

### Debug Information
```python
def test_with_debug_info():
    """Include debug information for test failures"""
    result = process_data(input_data)
    
    assert result.success, (
        f"Processing failed. "
        f"Input: {input_data}, "
        f"Result: {result}, "
        f"Errors: {result.errors}"
    )
```

### Logging in Tests
```python
def test_with_logging(caplog):
    """Use caplog for debugging test issues"""
    with caplog.at_level(logging.DEBUG):
        result = complex_operation()
    
    # Debug information available in caplog.text
    if not result.success:
        print(f"Debug logs: {caplog.text}")
```

## Tools and Dependencies

### Required Testing Tools
- **pytest**: Primary testing framework
- **pytest-cov**: Coverage measurement
- **pytest-asyncio**: Async test support
- **pytest-mock**: Enhanced mocking
- **faker**: Realistic test data generation
- **freezegun**: Time mocking
- **responses**: HTTP response mocking

### Optional Tools
- **pytest-benchmark**: Performance testing
- **pytest-xdist**: Parallel test execution
- **mutmut**: Mutation testing
- **hypothesis**: Property-based testing

## Maintenance and Review

### Regular Review Cycle
- **Weekly**: Review failing tests and flaky test reports
- **Monthly**: Analyze test coverage gaps and performance trends
- **Quarterly**: Review and update testing standards and tools

### Test Code Review Standards
- All test code must be reviewed like production code
- Focus on test clarity, maintainability, and effectiveness
- Verify proper use of fixtures and mocking strategies
- Ensure tests are adding value and catching real issues

## Migration Guide

### Updating Existing Tests
When updating existing tests to use new fixture system:

1. **Identify fixture patterns**: Look for repeated setup code
2. **Replace with shared fixtures**: Use appropriate fixtures from `tests/fixtures/`
3. **Update imports**: Import shared fixtures instead of creating local ones
4. **Verify behavior**: Ensure tests still pass with new fixtures
5. **Clean up**: Remove duplicated fixture code

### Example Migration
```python
# Before: Local fixture duplication
@pytest.fixture
def limitless_config():
    return LimitlessConfig(
        api_key="test_key",
        max_retries=2,
        retry_delay=0.1
    )

# After: Use shared fixture
from tests.fixtures.config_fixtures import limitless_config
# Remove local fixture, use shared one
```

This comprehensive testing standard ensures that all Lifeboard tests are consistent, maintainable, and effective at catching issues before they reach production.