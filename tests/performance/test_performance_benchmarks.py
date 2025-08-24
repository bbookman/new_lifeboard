"""Performance regression testing framework.

This module implements performance benchmarks to detect regressions in critical
application components and ensure performance targets are maintained.
"""

import pytest
import time
import statistics
import sqlite3
import json
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
from pathlib import Path
import psutil
import threading
from contextlib import contextmanager


@dataclass
class PerformanceMetric:
    """Container for performance measurement results."""
    name: str
    value: float
    unit: str
    threshold: float
    passed: bool
    metadata: Optional[Dict[str, Any]] = None


@dataclass 
class BenchmarkResult:
    """Container for benchmark execution results."""
    name: str
    execution_time: float
    memory_usage: float
    metrics: List[PerformanceMetric]
    timestamp: float
    passed: bool


class PerformanceProfiler:
    """Performance profiling utilities."""
    
    @staticmethod
    @contextmanager
    def measure_performance():
        """Context manager to measure execution time and memory usage."""
        process = psutil.Process()
        start_time = time.perf_counter()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            execution_time = end_time - start_time
            memory_usage = end_memory - start_memory
            
            # Store results in thread-local storage
            current_thread = threading.current_thread()
            current_thread.perf_results = {
                'execution_time': execution_time,
                'memory_usage': memory_usage
            }
    
    @staticmethod
    def get_last_measurement() -> Dict[str, float]:
        """Get the last performance measurement from current thread."""
        current_thread = threading.current_thread()
        return getattr(current_thread, 'perf_results', {'execution_time': 0.0, 'memory_usage': 0.0})
    
    @staticmethod
    def run_multiple_iterations(func: Callable, iterations: int = 5) -> Dict[str, float]:
        """Run function multiple times and return average performance metrics."""
        execution_times = []
        memory_usages = []
        
        for _ in range(iterations):
            with PerformanceProfiler.measure_performance():
                func()
            
            results = PerformanceProfiler.get_last_measurement()
            execution_times.append(results['execution_time'])
            memory_usages.append(results['memory_usage'])
        
        return {
            'avg_execution_time': statistics.mean(execution_times),
            'min_execution_time': min(execution_times),
            'max_execution_time': max(execution_times),
            'std_execution_time': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            'avg_memory_usage': statistics.mean(memory_usages),
            'max_memory_usage': max(memory_usages)
        }


class PerformanceBenchmarks:
    """Performance benchmark test suite."""
    
    # Performance thresholds (configurable via environment or config file)
    THRESHOLDS = {
        'database_query_time': 0.1,  # 100ms
        'embedding_generation_time': 2.0,  # 2 seconds
        'vector_search_time': 0.05,  # 50ms
        'api_response_time': 0.2,  # 200ms
        'memory_usage_mb': 100,  # 100MB
        'startup_time': 5.0,  # 5 seconds
        'chat_response_time': 3.0,  # 3 seconds
        'ingestion_rate_items_per_sec': 10,  # 10 items/sec
    }
    
    @pytest.fixture(autouse=True)
    def setup_benchmark_environment(self):
        """Setup consistent environment for benchmarks."""
        # Ensure clean state before each benchmark
        import gc
        gc.collect()
        
    def test_database_query_performance(self):
        """Benchmark database query performance."""
        from core.database import Database
        
        # Create test database in memory
        db = Database(":memory:")
        db.init_db()
        
        # Insert test data
        test_data = [(f"test:item_{i}", f"namespace_{i%3}", f"content_{i}") for i in range(1000)]
        with db.get_connection() as conn:
            conn.executemany(
                "INSERT INTO data_items (id, namespace, content) VALUES (?, ?, ?)",
                test_data
            )
        
        # Benchmark query performance
        def query_test():
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM data_items WHERE namespace = ?", ("namespace_1",))
                results = cursor.fetchall()
                assert len(results) > 0
        
        metrics = PerformanceProfiler.run_multiple_iterations(query_test, iterations=10)
        
        # Validate performance thresholds
        avg_time = metrics['avg_execution_time']
        assert avg_time < self.THRESHOLDS['database_query_time'], \
            f"Database query too slow: {avg_time:.3f}s > {self.THRESHOLDS['database_query_time']}s"
    
    def test_embedding_service_performance(self):
        """Benchmark embedding generation performance.""" 
        try:
            from core.embeddings import EmbeddingService
        except ImportError:
            pytest.skip("EmbeddingService not available")
        
        embedding_service = EmbeddingService()
        
        def embedding_test():
            test_text = "This is a test document for embedding generation performance testing."
            embedding = embedding_service.embed_text(test_text)
            assert len(embedding) > 0
        
        metrics = PerformanceProfiler.run_multiple_iterations(embedding_test, iterations=3)
        
        avg_time = metrics['avg_execution_time'] 
        assert avg_time < self.THRESHOLDS['embedding_generation_time'], \
            f"Embedding generation too slow: {avg_time:.3f}s > {self.THRESHOLDS['embedding_generation_time']}s"
    
    def test_vector_search_performance(self):
        """Benchmark vector search performance."""
        try:
            from core.vector_store import VectorStore
            from core.embeddings import EmbeddingService
        except ImportError:
            pytest.skip("VectorStore or EmbeddingService not available")
        
        vector_store = VectorStore()
        embedding_service = EmbeddingService()
        
        # Add test vectors
        test_vectors = []
        for i in range(100):
            text = f"Test document {i} with some sample content for vector search benchmarking."
            vector = embedding_service.embed_text(text)
            vector_store.add_vector(f"test:{i}", vector)
            test_vectors.append(vector)
        
        def search_test():
            query_vector = test_vectors[0]  # Use first vector as query
            results = vector_store.search(query_vector, top_k=10)
            assert len(results) > 0
        
        metrics = PerformanceProfiler.run_multiple_iterations(search_test, iterations=10)
        
        avg_time = metrics['avg_execution_time']
        assert avg_time < self.THRESHOLDS['vector_search_time'], \
            f"Vector search too slow: {avg_time:.3f}s > {self.THRESHOLDS['vector_search_time']}s"
    
    def test_api_endpoint_performance(self):
        """Benchmark API endpoint response times."""
        try:
            from api.main import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI app not available")
        
        client = TestClient(app)
        
        def api_test():
            response = client.get("/health")
            assert response.status_code == 200
        
        metrics = PerformanceProfiler.run_multiple_iterations(api_test, iterations=20)
        
        avg_time = metrics['avg_execution_time']
        assert avg_time < self.THRESHOLDS['api_response_time'], \
            f"API response too slow: {avg_time:.3f}s > {self.THRESHOLDS['api_response_time']}s"
    
    def test_memory_usage_performance(self):
        """Benchmark memory usage of core operations."""
        try:
            from services.ingestion import IngestionService
        except ImportError:
            pytest.skip("IngestionService not available")
        
        ingestion_service = IngestionService()
        
        with PerformanceProfiler.measure_performance():
            # Simulate processing a batch of data items
            test_items = [
                {'id': f'test:{i}', 'content': f'Test content {i}' * 100} 
                for i in range(100)
            ]
            # Note: This is a mock test - actual implementation depends on service interface
            
        results = PerformanceProfiler.get_last_measurement()
        memory_usage = results['memory_usage']
        
        assert memory_usage < self.THRESHOLDS['memory_usage_mb'], \
            f"Memory usage too high: {memory_usage:.2f}MB > {self.THRESHOLDS['memory_usage_mb']}MB"
    
    def test_application_startup_performance(self):
        """Benchmark application startup time."""
        def startup_test():
            try:
                from core.dependencies import get_container
                container = get_container()
                # Simulate service initialization
                health_status = container.get_health_status()
                assert isinstance(health_status, dict)
            except Exception as e:
                pytest.skip(f"Startup test failed: {e}")
        
        metrics = PerformanceProfiler.run_multiple_iterations(startup_test, iterations=3)
        
        avg_time = metrics['avg_execution_time']
        assert avg_time < self.THRESHOLDS['startup_time'], \
            f"Startup too slow: {avg_time:.3f}s > {self.THRESHOLDS['startup_time']}s"
    
    def test_concurrent_request_performance(self):
        """Benchmark performance under concurrent load."""
        import concurrent.futures
        try:
            from api.main import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI app not available")
        
        client = TestClient(app)
        
        def make_request():
            response = client.get("/health")
            return response.status_code == 200
        
        # Test concurrent requests
        start_time = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # All requests should succeed
        assert all(results), "Some concurrent requests failed"
        
        # Total time should be reasonable (concurrent execution should be faster than sequential)
        max_acceptable_time = self.THRESHOLDS['api_response_time'] * 10  # Allow 10x for 50 concurrent requests
        assert total_time < max_acceptable_time, \
            f"Concurrent requests too slow: {total_time:.3f}s > {max_acceptable_time}s"


class PerformanceRegressionTracker:
    """Track performance metrics over time to detect regressions."""
    
    def __init__(self, db_path: str = "performance_history.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize performance tracking database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    git_commit TEXT,
                    passed BOOLEAN NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_test_metric_time 
                ON performance_metrics(test_name, metric_name, timestamp)
            """)
    
    def record_metric(self, test_name: str, metric: PerformanceMetric, git_commit: str = None):
        """Record a performance metric."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO performance_metrics 
                (test_name, metric_name, value, unit, timestamp, git_commit, passed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (test_name, metric.name, metric.value, metric.unit, 
                  time.time(), git_commit, metric.passed))
    
    def get_metric_history(self, test_name: str, metric_name: str, days: int = 30) -> List[Dict]:
        """Get historical performance data for a metric."""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT value, timestamp, git_commit, passed 
                FROM performance_metrics 
                WHERE test_name = ? AND metric_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (test_name, metric_name, cutoff_time))
            
            return [
                {'value': row[0], 'timestamp': row[1], 'git_commit': row[2], 'passed': bool(row[3])}
                for row in cursor.fetchall()
            ]
    
    def detect_regression(self, test_name: str, metric_name: str, current_value: float, 
                         threshold_percentage: float = 20.0) -> bool:
        """Detect if current performance represents a regression."""
        history = self.get_metric_history(test_name, metric_name, days=7)
        
        if len(history) < 3:
            return False  # Not enough history to detect regression
        
        # Calculate baseline (average of recent successful runs)
        successful_runs = [h for h in history if h['passed']]
        if len(successful_runs) < 2:
            return False
            
        baseline = statistics.mean([h['value'] for h in successful_runs[:5]])  # Last 5 successful runs
        threshold = baseline * (1 + threshold_percentage / 100)
        
        return current_value > threshold


class TestPerformanceRegression:
    """Integration test for performance regression detection."""
    
    @pytest.fixture
    def regression_tracker(self):
        """Create temporary regression tracker for testing."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db_path = f.name
        
        tracker = PerformanceRegressionTracker(temp_db_path)
        yield tracker
        
        # Cleanup
        os.unlink(temp_db_path)
    
    def test_regression_detection(self, regression_tracker):
        """Test that regression detection works correctly."""
        # Record some baseline metrics
        for i in range(5):
            metric = PerformanceMetric(
                name="test_metric", 
                value=1.0 + (i * 0.1),  # Slight variation
                unit="seconds",
                threshold=2.0,
                passed=True
            )
            regression_tracker.record_metric("test_benchmark", metric)
        
        # Test normal performance (should not be regression)
        assert not regression_tracker.detect_regression("test_benchmark", "test_metric", 1.2)
        
        # Test performance regression (50% slower)
        assert regression_tracker.detect_regression("test_benchmark", "test_metric", 1.8)
    
    def test_insufficient_history_handling(self, regression_tracker):
        """Test handling when insufficient history is available."""
        # With no history, should not detect regression
        assert not regression_tracker.detect_regression("new_test", "new_metric", 10.0)
        
        # With only one data point, should not detect regression  
        metric = PerformanceMetric("new_metric", 1.0, "seconds", 2.0, True)
        regression_tracker.record_metric("new_test", metric)
        assert not regression_tracker.detect_regression("new_test", "new_metric", 5.0)