"""Example performance tests demonstrating best practices.

This module provides concrete examples of how to write effective performance tests
and benchmarks for different scenarios.
"""

import pytest
import time
import concurrent.futures
import sqlite3
import tempfile
import json
from typing import List, Dict, Any
from pathlib import Path
import statistics


class TestDatabasePerformanceExamples:
    """Example performance tests for database operations."""
    
    @pytest.fixture
    def temp_database(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Initialize database
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE test_data (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.close()
        
        yield db_path
        
        # Cleanup
        Path(db_path).unlink()
    
    def test_bulk_insert_performance(self, temp_database):
        """Example test for bulk insert performance."""
        conn = sqlite3.connect(temp_database)
        
        # Generate test data
        test_data = [(f'name_{i}', f'data_{i}') for i in range(1000)]
        
        start_time = time.perf_counter()
        
        # Test bulk insert
        conn.executemany(
            'INSERT INTO test_data (name, data) VALUES (?, ?)',
            test_data
        )
        conn.commit()
        
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        conn.close()
        
        # Performance assertions
        assert execution_time < 1.0, f"Bulk insert too slow: {execution_time:.3f}s"
        
        # Calculate throughput
        throughput = len(test_data) / execution_time
        assert throughput > 500, f"Insert throughput too low: {throughput:.1f} records/sec"
    
    def test_query_performance_with_index(self, temp_database):
        """Example test comparing query performance with and without indexes."""
        conn = sqlite3.connect(temp_database)
        
        # Insert test data
        test_data = [(f'name_{i}', f'data_{i}') for i in range(10000)]
        conn.executemany('INSERT INTO test_data (name, data) VALUES (?, ?)', test_data)
        conn.commit()
        
        # Test query without index
        start_time = time.perf_counter()
        cursor = conn.execute('SELECT * FROM test_data WHERE name = ?', ('name_5000',))
        result_no_index = cursor.fetchall()
        time_no_index = time.perf_counter() - start_time
        
        # Create index
        conn.execute('CREATE INDEX idx_name ON test_data(name)')
        
        # Test query with index
        start_time = time.perf_counter()
        cursor = conn.execute('SELECT * FROM test_data WHERE name = ?', ('name_5000',))
        result_with_index = cursor.fetchall()
        time_with_index = time.perf_counter() - start_time
        
        conn.close()
        
        # Verify same results
        assert result_no_index == result_with_index
        
        # Index should improve performance significantly
        improvement_ratio = time_no_index / time_with_index
        assert improvement_ratio > 2.0, f"Index should improve performance by at least 2x, got {improvement_ratio:.1f}x"
    
    def test_concurrent_database_access(self, temp_database):
        """Example test for concurrent database access performance."""
        
        def database_worker(worker_id: int, num_operations: int):
            """Worker function for concurrent database operations."""
            conn = sqlite3.connect(temp_database)
            
            operations_completed = 0
            start_time = time.perf_counter()
            
            for i in range(num_operations):
                # Mix of read and write operations
                if i % 3 == 0:
                    # Insert
                    conn.execute('INSERT INTO test_data (name, data) VALUES (?, ?)', 
                               (f'worker_{worker_id}_item_{i}', f'data_{i}'))
                elif i % 3 == 1:
                    # Update
                    conn.execute('UPDATE test_data SET data = ? WHERE id = ?', 
                               (f'updated_{i}', i % 100 + 1))
                else:
                    # Select
                    cursor = conn.execute('SELECT COUNT(*) FROM test_data')
                    cursor.fetchone()
                
                operations_completed += 1
            
            conn.commit()
            conn.close()
            
            end_time = time.perf_counter()
            return {
                'worker_id': worker_id,
                'operations_completed': operations_completed,
                'execution_time': end_time - start_time
            }
        
        # Run concurrent workers
        num_workers = 5
        operations_per_worker = 100
        
        start_time = time.perf_counter()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(database_worker, worker_id, operations_per_worker)
                for worker_id in range(num_workers)
            ]
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.perf_counter() - start_time
        
        # Verify all workers completed successfully
        assert len(results) == num_workers
        total_operations = sum(r['operations_completed'] for r in results)
        assert total_operations == num_workers * operations_per_worker
        
        # Performance assertions
        assert total_time < 10.0, f"Concurrent operations too slow: {total_time:.3f}s"
        
        # Calculate overall throughput
        throughput = total_operations / total_time
        assert throughput > 50, f"Concurrent throughput too low: {throughput:.1f} ops/sec"


class TestAPIPerformanceExamples:
    """Example performance tests for API endpoints."""
    
    def test_api_response_time_distribution(self):
        """Example test measuring API response time distribution."""
        
        def mock_api_call():
            """Mock API call with realistic timing variation."""
            import random
            # Simulate network latency and processing time
            base_time = 0.1  # 100ms base
            variation = random.uniform(0.05, 0.2)  # 50-200ms variation
            time.sleep(base_time + variation)
            return {'status': 'success', 'data': 'response_data'}
        
        # Collect response times
        response_times = []
        num_requests = 50
        
        for _ in range(num_requests):
            start_time = time.perf_counter()
            result = mock_api_call()
            end_time = time.perf_counter()
            
            assert result['status'] == 'success'  # Verify functionality
            response_times.append(end_time - start_time)
        
        # Analyze distribution
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        p95_time = sorted(response_times)[int(0.95 * len(response_times))]
        p99_time = sorted(response_times)[int(0.99 * len(response_times))]
        
        # Performance assertions
        assert avg_time < 0.5, f"Average response time too high: {avg_time:.3f}s"
        assert median_time < 0.4, f"Median response time too high: {median_time:.3f}s"
        assert p95_time < 0.8, f"95th percentile too high: {p95_time:.3f}s"
        assert p99_time < 1.0, f"99th percentile too high: {p99_time:.3f}s"
        
        # Log performance statistics for monitoring
        print(f"Performance stats - Avg: {avg_time:.3f}s, Median: {median_time:.3f}s, P95: {p95_time:.3f}s")
    
    def test_api_throughput_under_load(self):
        """Example test measuring API throughput under concurrent load."""
        
        def api_worker(num_requests: int):
            """Worker function making API requests."""
            successful_requests = 0
            failed_requests = 0
            total_time = 0
            
            for _ in range(num_requests):
                start_time = time.perf_counter()
                try:
                    # Mock API call
                    time.sleep(0.05)  # 50ms simulated processing
                    successful_requests += 1
                except Exception:
                    failed_requests += 1
                finally:
                    total_time += time.perf_counter() - start_time
            
            return {
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'total_time': total_time
            }
        
        # Test with increasing load levels
        load_levels = [5, 10, 20]  # Number of concurrent workers
        requests_per_worker = 20
        
        for num_workers in load_levels:
            start_time = time.perf_counter()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    executor.submit(api_worker, requests_per_worker)
                    for _ in range(num_workers)
                ]
                
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            total_test_time = time.perf_counter() - start_time
            
            # Aggregate results
            total_successful = sum(r['successful_requests'] for r in results)
            total_failed = sum(r['failed_requests'] for r in results)
            
            # Calculate throughput
            throughput = total_successful / total_test_time
            error_rate = total_failed / (total_successful + total_failed) if (total_successful + total_failed) > 0 else 0
            
            # Performance assertions
            assert error_rate < 0.01, f"Error rate too high at {num_workers} workers: {error_rate:.2%}"
            assert throughput > num_workers * 5, f"Throughput too low at {num_workers} workers: {throughput:.1f} req/sec"
            
            print(f"Load level {num_workers}: Throughput {throughput:.1f} req/sec, Error rate {error_rate:.2%}")


class TestMemoryPerformanceExamples:
    """Example performance tests for memory usage."""
    
    def test_memory_usage_during_batch_processing(self):
        """Example test monitoring memory usage during data processing."""
        import psutil
        import gc
        
        def process_large_batch(batch_size: int):
            """Simulate processing a large batch of data."""
            # Create large data structure
            data_batch = []
            for i in range(batch_size):
                data_batch.append({
                    'id': i,
                    'data': f'item_{i}' * 100,  # Make each item substantial
                    'metadata': {'timestamp': time.time(), 'processed': False}
                })
            
            # Process the batch
            processed_count = 0
            for item in data_batch:
                item['metadata']['processed'] = True
                item['processed_at'] = time.time()
                processed_count += 1
            
            return processed_count
        
        # Measure memory before
        process = psutil.Process()
        gc.collect()  # Clean up before measurement
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process batch
        batch_size = 10000
        start_time = time.perf_counter()
        processed = process_large_batch(batch_size)
        processing_time = time.perf_counter() - start_time
        
        # Measure memory after
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = memory_after - memory_before
        
        # Clean up and measure final memory
        gc.collect()
        memory_final = process.memory_info().rss / 1024 / 1024  # MB
        memory_released = memory_after - memory_final
        
        # Performance assertions
        assert processed == batch_size, "All items should be processed"
        assert processing_time < 5.0, f"Processing too slow: {processing_time:.3f}s"
        assert memory_used < 200, f"Memory usage too high: {memory_used:.1f}MB"
        
        # Memory should be mostly released after cleanup
        memory_retained = memory_final - memory_before
        assert memory_retained < 50, f"Too much memory retained: {memory_retained:.1f}MB"
        
        print(f"Memory usage: {memory_used:.1f}MB peak, {memory_released:.1f}MB released, {memory_retained:.1f}MB retained")
    
    def test_memory_leak_detection(self):
        """Example test for detecting memory leaks."""
        import psutil
        import gc
        
        def potentially_leaky_function():
            """Function that might have memory leaks."""
            # Simulate creating and processing data
            data = [f'item_{i}' * 50 for i in range(1000)]
            processed_data = []
            
            for item in data:
                processed_item = item.upper() + '_PROCESSED'
                processed_data.append(processed_item)
            
            # Intentionally return only a subset (simulating potential leak)
            return processed_data[:10]
        
        process = psutil.Process()
        memory_measurements = []
        
        # Run function multiple times and measure memory
        num_iterations = 10
        for i in range(num_iterations):
            gc.collect()  # Clean up before each measurement
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            result = potentially_leaky_function()
            assert len(result) == 10  # Verify functionality
            
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_measurements.append(memory_after - memory_before)
            
            # Give system time to clean up
            time.sleep(0.1)
        
        # Analyze memory usage trend
        avg_memory_per_call = statistics.mean(memory_measurements)
        memory_trend = statistics.linear_regression(range(num_iterations), memory_measurements).slope
        
        # Performance assertions
        assert avg_memory_per_call < 20, f"Average memory per call too high: {avg_memory_per_call:.1f}MB"
        
        # Memory usage should be relatively stable (no significant upward trend)
        assert memory_trend < 2.0, f"Potential memory leak detected: trend {memory_trend:.2f}MB/call"
        
        print(f"Memory per call: {avg_memory_per_call:.1f}MB avg, trend: {memory_trend:.2f}MB/call")


class TestPerformanceRegressionExamples:
    """Example tests for performance regression detection."""
    
    def test_performance_baseline_comparison(self):
        """Example test that compares current performance against baseline."""
        
        def current_algorithm(data: List[int]) -> int:
            """Current implementation of algorithm."""
            return sum(x * x for x in data)  # O(n)
        
        def baseline_algorithm(data: List[int]) -> int:
            """Baseline implementation for comparison."""
            result = 0
            for x in data:
                result += x * x
            return result  # Also O(n) but potentially different performance characteristics
        
        # Test data
        test_data = list(range(100000))
        
        # Measure current implementation
        start_time = time.perf_counter()
        current_result = current_algorithm(test_data)
        current_time = time.perf_counter() - start_time
        
        # Measure baseline implementation
        start_time = time.perf_counter()
        baseline_result = baseline_algorithm(test_data)
        baseline_time = time.perf_counter() - start_time
        
        # Verify functionality
        assert current_result == baseline_result
        
        # Performance regression check
        performance_ratio = current_time / baseline_time
        assert performance_ratio < 2.0, f"Performance regression detected: {performance_ratio:.2f}x slower than baseline"
        
        # Log performance comparison
        if performance_ratio < 0.8:
            print(f"Performance improvement: {1/performance_ratio:.2f}x faster than baseline")
        elif performance_ratio > 1.2:
            print(f"Performance regression: {performance_ratio:.2f}x slower than baseline")
        else:
            print(f"Performance similar to baseline: {performance_ratio:.2f}x")
    
    def test_scalability_characteristics(self):
        """Example test measuring how performance scales with input size."""
        
        def algorithm_under_test(data: List[int]) -> int:
            """Algorithm whose scalability we want to test."""
            # O(n log n) algorithm
            sorted_data = sorted(data)
            return sum(sorted_data[i] * (i + 1) for i in range(len(sorted_data)))
        
        # Test with different input sizes
        input_sizes = [1000, 2000, 4000, 8000]
        execution_times = []
        
        for size in input_sizes:
            test_data = list(range(size))
            
            start_time = time.perf_counter()
            result = algorithm_under_test(test_data)
            execution_time = time.perf_counter() - start_time
            
            execution_times.append(execution_time)
            
            # Basic functionality check
            assert result > 0  # Should produce meaningful result
        
        # Analyze scaling behavior
        # For O(n log n), doubling input should roughly double time (with log factor)
        for i in range(1, len(input_sizes)):
            size_ratio = input_sizes[i] / input_sizes[i-1]
            time_ratio = execution_times[i] / execution_times[i-1]
            
            # Expected ratio for O(n log n) when doubling input size
            expected_max_ratio = size_ratio * (2.0 * 2.0) / 2.0  # Generous bound
            
            assert time_ratio < expected_max_ratio, \
                f"Algorithm scaling worse than expected: {time_ratio:.2f}x time for {size_ratio:.1f}x input"
        
        print(f"Scaling analysis: {dict(zip(input_sizes, execution_times))}")


class TestPerformanceTestUtilities:
    """Example utilities for performance testing."""
    
    @staticmethod
    def measure_function_performance(func, *args, iterations=5, **kwargs):
        """Utility to measure function performance over multiple iterations."""
        execution_times = []
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_times.append(end_time - start_time)
        
        return {
            'avg_time': statistics.mean(execution_times),
            'min_time': min(execution_times),
            'max_time': max(execution_times),
            'std_dev': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            'result': result
        }
    
    @staticmethod
    def assert_performance_within_bounds(actual_time: float, max_time: float, 
                                       test_name: str = "Performance test"):
        """Utility for performance assertions with clear error messages."""
        if actual_time > max_time:
            raise AssertionError(
                f"{test_name} failed: {actual_time:.3f}s > {max_time:.3f}s "
                f"(exceeded by {((actual_time / max_time) - 1) * 100:.1f}%)"
            )
    
    def test_performance_utilities(self):
        """Test the performance testing utilities."""
        
        def test_function(delay: float):
            time.sleep(delay)
            return "completed"
        
        # Test measurement utility
        results = self.measure_function_performance(test_function, 0.01, iterations=3)
        
        assert 'avg_time' in results
        assert 'result' in results
        assert results['result'] == "completed"
        assert results['avg_time'] > 0.005  # Should be at least half the sleep time
        
        # Test assertion utility
        self.assert_performance_within_bounds(0.1, 0.2, "Test assertion")
        
        # Test assertion failure
        with pytest.raises(AssertionError):
            self.assert_performance_within_bounds(0.3, 0.1, "Test failure")