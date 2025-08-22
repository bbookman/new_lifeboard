"""
Pytest configuration and shared fixtures for orchestration tests.

This file provides project-wide test configuration and fixtures that
are automatically available to all tests.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import fixtures from all fixture modules
from tests.fixtures.api_fixtures import *
from tests.fixtures.config_fixtures import *
from tests.fixtures.data_fixtures import *
from tests.fixtures.database_fixtures import *
from tests.fixtures.orchestration_fixtures import *
from tests.fixtures.service_fixtures import *


# Configure asyncio for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "regression: mark test as regression test")
    config.addinivalue_line("markers", "slow: mark test as slow-running test")
    config.addinivalue_line("markers", "requires_node: mark test as requiring Node.js")

# Collect performance test results
performance_results = []

@pytest.fixture(autouse=True)
def track_performance(request):
    """Automatically track performance for marked tests"""
    if request.node.get_closest_marker("performance"):
        import time
        start_time = time.perf_counter()
        yield
        end_time = time.perf_counter()

        performance_results.append({
            "test": request.node.name,
            "duration": end_time - start_time,
        })
    else:
        yield

def pytest_sessionfinish(session, exitstatus):
    """Print performance summary at end of test session"""
    if performance_results:
        print("\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)

        for result in sorted(performance_results, key=lambda x: x["duration"], reverse=True):
            print(f"{result['test']:<50} {result['duration']:.4f}s")

        avg_time = sum(r["duration"] for r in performance_results) / len(performance_results)
        print(f"\nAverage performance test time: {avg_time:.4f}s")
        print(f"Total performance tests: {len(performance_results)}")

# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file/class names"""
    for item in items:
        # Add markers based on test file names
        if "performance" in item.fspath.basename:
            item.add_marker(pytest.mark.performance)
        elif "e2e" in item.fspath.basename or "integration" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

        # Add slow marker for tests that might be slow
        if any(word in item.name.lower() for word in ["performance", "concurrent", "load"]):
            item.add_marker(pytest.mark.slow)

        # Add requires_node marker for tests that need Node.js
        if any(word in item.name.lower() for word in ["frontend", "node", "npm"]):
            item.add_marker(pytest.mark.requires_node)

# Fixtures for common test scenarios
@pytest.fixture
def temp_frontend_dir(tmp_path):
    """Create a temporary frontend directory structure"""
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    # Create package.json
    package_json = frontend_dir / "package.json"
    package_json.write_text('{"name": "test-frontend", "scripts": {"dev": "echo test"}}')

    # Create node_modules directory
    node_modules = frontend_dir / "node_modules"
    node_modules.mkdir()

    # Create package-lock.json
    package_lock = frontend_dir / "package-lock.json"
    package_lock.write_text('{"lockfileVersion": 1}')

    return frontend_dir

@pytest.fixture
def clean_environment():
    """Provide a clean environment for tests"""
    import os
    original_env = os.environ.copy()

    # Clean up test-specific environment variables
    test_vars = [var for var in os.environ if var.startswith("TEST_")]
    for var in test_vars:
        del os.environ[var]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture(scope="session")
def test_ports():
    """Get available ports for testing"""
    import socket

    def get_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    return {
        "backend": get_free_port(),
        "frontend": get_free_port(),
        "alternative": get_free_port(),
    }

# Async test utilities
@pytest.fixture
def async_timeout():
    """Default timeout for async operations in tests"""
    return 10.0

# Mock management
@pytest.fixture
def mock_registry():
    """Registry for managing mocks across tests"""
    registry = {}
    yield registry

    # Cleanup any registered mocks
    for mock in registry.values():
        if hasattr(mock, "stop"):
            try:
                mock.stop()
            except:
                pass

# Resource tracking
@pytest.fixture(autouse=True)
def resource_tracker():
    """Track resource usage during tests"""
    import gc
    import threading

    # Get initial state
    initial_threads = threading.active_count()
    gc.collect()
    initial_objects = len(gc.get_objects())

    yield

    # Check final state
    final_threads = threading.active_count()
    gc.collect()
    final_objects = len(gc.get_objects())

    # Warn about resource leaks (but don't fail tests)
    thread_growth = final_threads - initial_threads
    object_growth = final_objects - initial_objects

    if thread_growth > 5:  # Allow for some thread growth
        print(f"\nWarning: Thread count increased by {thread_growth} during test")

    if object_growth > 1000:  # Allow for reasonable object growth
        print(f"\nWarning: Object count increased by {object_growth} during test")
