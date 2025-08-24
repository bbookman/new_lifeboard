# Contract Testing and Performance Regression Implementation

This document describes the implementation of contract testing and performance regression testing infrastructure as specified in Phase 3.0 of the cleanup plan.

## Overview

The implementation provides:

1. **Contract Testing Infrastructure** - Validates service interface compliance
2. **Performance Regression Testing** - Detects performance regressions and tracks metrics
3. **Test Examples** - Demonstrates best practices for both testing approaches
4. **Integration Support** - Works with existing test suite and fixtures

## Files Implemented

### Core Testing Infrastructure

```
tests/
├── contracts/
│   ├── __init__.py
│   └── test_service_contracts.py      # Service interface compliance tests
├── performance/  
│   ├── __init__.py
│   └── test_performance_benchmarks.py # Performance regression framework
├── examples/
│   ├── __init__.py
│   ├── test_contract_examples.py      # Contract testing examples
│   └── test_performance_examples.py   # Performance testing examples
├── conftest.py                        # Enhanced with new fixtures
└── run_contract_and_performance_tests.py # Test runner script
```

## Contract Testing

### Purpose
Validates that all service implementations comply with their defined interfaces from `core.service_interfaces`.

### Key Features
- **Interface Compliance**: Checks all services implement required methods
- **Method Signature Validation**: Verifies parameter names and types
- **Cross-Service Contracts**: Tests integration between services
- **Health Check Validation**: Ensures all services have working health checks

### Example Usage
```python
# Run contract tests
pytest -m contract tests/contracts/

# Check specific service compliance
pytest tests/contracts/test_service_contracts.py::TestServiceContracts::test_database_service_contract
```

### Service Interfaces Tested
- `ServiceInterface` (base interface)
- `DatabaseServiceInterface`
- `HTTPClientInterface`
- `EmbeddingServiceInterface`
- `VectorStoreInterface`
- `ChatServiceInterface`
- `IngestionServiceInterface`
- `SchedulerServiceInterface`

## Performance Regression Testing

### Purpose
Detects performance regressions and maintains performance benchmarks for critical operations.

### Key Features
- **Automated Benchmarking**: Measures execution time and memory usage
- **Regression Detection**: Compares current performance against historical baselines
- **Multiple Metrics**: Tracks execution time, memory usage, throughput
- **Statistical Analysis**: Uses statistical methods for reliable regression detection

### Performance Thresholds
```python
THRESHOLDS = {
    'database_query_time': 0.1,      # 100ms
    'embedding_generation_time': 2.0, # 2 seconds  
    'vector_search_time': 0.05,      # 50ms
    'api_response_time': 0.2,        # 200ms
    'memory_usage_mb': 100,          # 100MB
    'startup_time': 5.0,             # 5 seconds
}
```

### Example Usage
```python
# Run performance tests
pytest -m performance tests/performance/

# Run only benchmark tests
pytest -m benchmark tests/performance/

# Run with performance tracking
pytest --durations=10 tests/performance/
```

### Benchmarked Operations
- Database query performance
- Embedding generation speed
- Vector search efficiency
- API endpoint response times
- Memory usage patterns
- Application startup time
- Concurrent request handling

## Test Examples

### Contract Testing Examples
The `test_contract_examples.py` file demonstrates:
- Writing interface compliance tests
- Validating error handling contracts
- Testing cross-service integration
- Using validation helper utilities

### Performance Testing Examples  
The `test_performance_examples.py` file demonstrates:
- Database performance testing
- API throughput measurement
- Memory usage monitoring
- Regression detection
- Scalability testing

## Integration with Existing Test Suite

### Enhanced conftest.py
- Added contract and performance testing fixtures
- New pytest markers: `@pytest.mark.contract`, `@pytest.mark.performance`
- Mock service registry for contract testing
- Performance tracking and profiling fixtures

### Test Markers
```python
@pytest.mark.contract      # Contract compliance test
@pytest.mark.performance   # Performance regression test
@pytest.mark.benchmark     # Performance benchmark test
@pytest.mark.slow         # Slow-running test
```

### Running Tests

```bash
# Use the custom test runner
./tests/run_contract_and_performance_tests.py --type all

# Run specific test types
./tests/run_contract_and_performance_tests.py --type contract
./tests/run_contract_and_performance_tests.py --type performance

# Check dependencies
./tests/run_contract_and_performance_tests.py --check-deps

# Generate test report
./tests/run_contract_and_performance_tests.py --report
```

## Performance Regression Tracking

### Database Storage
Performance metrics are stored in SQLite database for historical analysis:

```sql
CREATE TABLE performance_metrics (
    test_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    timestamp REAL NOT NULL,
    git_commit TEXT,
    passed BOOLEAN NOT NULL
);
```

### Regression Algorithm
- Calculates baseline from recent successful runs
- Uses configurable threshold percentage (default: 20%)
- Requires minimum history for reliable detection
- Accounts for natural performance variation

## Dependencies

### Required Packages
- `pytest` - Test framework
- `psutil` - System resource monitoring
- `sqlite3` - Performance metrics storage (built-in)
- `statistics` - Statistical analysis (built-in)

### Optional Packages
- `fastapi` - For API endpoint testing
- `sentence-transformers` - For embedding performance tests

## Usage Guidelines

### Contract Tests
1. **Write contract tests for new services**: Implement interface compliance tests
2. **Validate error handling**: Test exception scenarios and error responses
3. **Check cross-service compatibility**: Test service interactions
4. **Update when interfaces change**: Maintain tests with interface evolution

### Performance Tests
1. **Set realistic thresholds**: Based on actual performance requirements
2. **Run regularly**: Include in CI/CD pipeline for regression detection
3. **Track over time**: Use historical data for trend analysis
4. **Test representative scenarios**: Use realistic data sizes and conditions

## Future Enhancements

### Potential Improvements
1. **CI/CD Integration**: Automated performance tracking in build pipeline
2. **Performance Dashboards**: Visual tracking of performance trends
3. **More Metrics**: CPU usage, network I/O, disk I/O tracking
4. **Load Testing**: Higher concurrent user simulation
5. **Contract Generation**: Automatic contract test generation from interfaces

### Configuration
Both testing frameworks support configuration through fixtures and environment variables, allowing customization for different environments and requirements.

## Implementation Status

✅ **COMPLETE** - Contract Testing and Performance Regression (Phase 3.0)

This implementation addresses the requirements from `latest_clean.md` Phase 3.0:
- ✅ Contract testing infrastructure for service interface compliance
- ✅ Performance regression detection and benchmarking
- ✅ Integration with existing test suite
- ✅ Example tests demonstrating best practices
- ✅ Test runner and documentation