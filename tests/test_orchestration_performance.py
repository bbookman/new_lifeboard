"""
Performance and regression tests for the orchestration refactoring.

Tests to ensure the refactoring maintains performance characteristics
and doesn't introduce regressions compared to the original implementation.
"""

import pytest
import time
import asyncio
import statistics
from unittest.mock import Mock, patch, MagicMock
from core.orchestration import (
    PortManager, 
    ProcessTerminator, 
    FrontendEnvironmentValidator,
    FrontendService,
    FullStackOrchestrator,
    ProcessInfo
)


class TestPerformanceBenchmarks:
    """Performance benchmarks for orchestration components"""

    def test_port_manager_performance(self):
        """Test PortManager performance for port resolution"""
        iterations = 100
        times = []
        
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.return_value = None
            
            for _ in range(iterations):
                start_time = time.perf_counter()
                
                # Test port availability check
                PortManager.check_port_available(8000)
                
                end_time = time.perf_counter()
                times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.01, f"Average port check time {avg_time:.4f}s too slow"
        assert max_time < 0.05, f"Max port check time {max_time:.4f}s too slow"
        
        print(f"PortManager.check_port_available: avg={avg_time:.4f}s, max={max_time:.4f}s")

    def test_port_resolution_performance(self):
        """Test port resolution performance"""
        iterations = 50
        times = []
        
        with patch.object(PortManager, 'check_port_available', return_value=True):
            for _ in range(iterations):
                start_time = time.perf_counter()
                
                result = PortManager.resolve_port(8000, no_auto_port=True)
                
                end_time = time.perf_counter()
                times.append(end_time - start_time)
                
                assert result.available is True
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.005, f"Average port resolution time {avg_time:.4f}s too slow"
        assert max_time < 0.02, f"Max port resolution time {max_time:.4f}s too slow"
        
        print(f"PortManager.resolve_port: avg={avg_time:.4f}s, max={max_time:.4f}s")

    def test_process_terminator_performance(self):
        """Test ProcessTerminator performance"""
        iterations = 20
        times = []
        
        for _ in range(iterations):
            mock_process = Mock()
            mock_process.poll.return_value = 0  # Already terminated
            
            start_time = time.perf_counter()
            
            result = ProcessTerminator.terminate_process_gracefully(mock_process)
            
            end_time = time.perf_counter()
            times.append(end_time - start_time)
            
            assert result is True
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.001, f"Average process termination time {avg_time:.4f}s too slow"
        assert max_time < 0.01, f"Max process termination time {max_time:.4f}s too slow"
        
        print(f"ProcessTerminator.terminate_process_gracefully: avg={avg_time:.4f}s, max={max_time:.4f}s")

    def test_frontend_environment_validation_performance(self):
        """Test frontend environment validation performance"""
        iterations = 30
        times = []
        
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            for _ in range(iterations):
                start_time = time.perf_counter()
                
                result = FrontendEnvironmentValidator.is_node_installed()
                
                end_time = time.perf_counter()
                times.append(end_time - start_time)
                
                assert result is True
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions (more lenient due to subprocess mocking)
        assert avg_time < 0.01, f"Average node validation time {avg_time:.4f}s too slow"
        assert max_time < 0.05, f"Max node validation time {max_time:.4f}s too slow"
        
        print(f"FrontendEnvironmentValidator.is_node_installed: avg={avg_time:.4f}s, max={max_time:.4f}s")

    @pytest.mark.asyncio
    async def test_orchestrator_startup_performance(self):
        """Test FullStackOrchestrator startup performance"""
        iterations = 10
        times = []
        
        for _ in range(iterations):
            orchestrator = FullStackOrchestrator()
            
            # Mock all dependencies for fast execution
            with patch.object(orchestrator, 'resolve_ports', return_value=(8000, 5173)):
                with patch.object(orchestrator, 'start_frontend_if_enabled', 
                                 return_value=ProcessInfo(Mock(), 12345, 5173, True)):
                    
                    start_time = time.perf_counter()
                    
                    result = await orchestrator.orchestrate_startup(
                        host="localhost",
                        backend_port=8000,
                        frontend_port=5173,
                        no_auto_port=False,
                        no_frontend=False,
                        kill_existing=False
                    )
                    
                    end_time = time.perf_counter()
                    times.append(end_time - start_time)
                    
                    assert result["success"] is True
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.01, f"Average orchestration time {avg_time:.4f}s too slow"
        assert max_time < 0.05, f"Max orchestration time {max_time:.4f}s too slow"
        
        print(f"FullStackOrchestrator.orchestrate_startup: avg={avg_time:.4f}s, max={max_time:.4f}s")


class TestMemoryUsage:
    """Test memory usage characteristics"""

    def test_orchestrator_memory_efficiency(self):
        """Test that orchestrator doesn't leak memory with multiple instances"""
        import gc
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Create and use multiple orchestrator instances
        for _ in range(50):
            orchestrator = FullStackOrchestrator()
            # Simulate basic usage
            env = orchestrator.frontend_service.setup_frontend_environment(8000)
            assert env["NODE_ENV"] == "development"
            del orchestrator
        
        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Allow for some growth but not excessive
        object_growth = final_objects - initial_objects
        assert object_growth < 100, f"Excessive object growth: {object_growth}"
        
        print(f"Memory test: {object_growth} objects growth (acceptable)")

    def test_port_manager_static_methods_efficiency(self):
        """Test that static methods don't accumulate state"""
        # Static methods should not create persistent state
        for _ in range(100):
            with patch('socket.socket'):
                PortManager.check_port_available(8000)
                result = PortManager.resolve_port(8000, no_auto_port=True)
                assert result.requested_port == 8000


class TestRegressionPrevention:
    """Tests to prevent regression from the original implementation"""

    @pytest.mark.asyncio
    async def test_run_full_stack_interface_compatibility(self):
        """Test that run_full_stack maintains the same interface as original"""
        from api.server import run_full_stack
        import inspect
        
        # Get the function signature
        sig = inspect.signature(run_full_stack)
        
        # Verify expected parameters exist
        expected_params = {
            'host', 'port', 'frontend_port', 'debug', 
            'kill_existing', 'no_auto_port', 'no_frontend'
        }
        
        actual_params = set(sig.parameters.keys())
        assert expected_params == actual_params, f"Interface changed: expected {expected_params}, got {actual_params}"
        
        # Verify it's still async
        assert inspect.iscoroutinefunction(run_full_stack), "Function is no longer async"

    def test_port_resolution_behavior_consistency(self):
        """Test that port resolution behavior matches expected patterns"""
        # Test exact port mode
        with patch.object(PortManager, 'check_port_available', return_value=True):
            result = PortManager.resolve_port(8000, no_auto_port=True)
            assert result.requested_port == 8000
            assert result.resolved_port == 8000
            assert result.auto_port_used is False
        
        # Test auto port mode
        with patch.object(PortManager, 'check_port_available', return_value=False):
            with patch.object(PortManager, 'find_available_port', return_value=8001):
                result = PortManager.resolve_port(8000, no_auto_port=False)
                assert result.requested_port == 8000
                assert result.resolved_port == 8001
                assert result.auto_port_used is True

    def test_error_handling_consistency(self):
        """Test that error handling behaves consistently with expectations"""
        # Test graceful handling of None process
        result = ProcessTerminator.terminate_process_gracefully(None)
        assert result is True
        
        # Test graceful handling of missing Node.js
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = FrontendEnvironmentValidator.is_node_installed()
            assert result is False

    @pytest.mark.asyncio
    async def test_orchestration_flow_consistency(self):
        """Test that orchestration follows expected flow patterns"""
        orchestrator = FullStackOrchestrator()
        
        # Test that validation is called before startup
        with patch.object(orchestrator, 'validate_frontend_environment', return_value=False) as mock_validate:
            with pytest.raises(RuntimeError):
                orchestrator.start_frontend_if_enabled(5173, 8000)
            mock_validate.assert_called_once()
        
        # Test that cleanup can be called safely multiple times
        frontend_info = ProcessInfo(Mock(), 12345, 5173, True)
        with patch('core.orchestration.ProcessTerminator.terminate_process_gracefully', return_value=True):
            orchestrator.cleanup_processes_on_exit(frontend_info)
            orchestrator.cleanup_processes_on_exit(frontend_info)  # Should not crash


class TestScalabilityCharacteristics:
    """Test scalability and resource usage under load"""

    def test_concurrent_port_checking(self):
        """Test performance of concurrent port checking"""
        import concurrent.futures
        import threading
        
        num_threads = 10
        checks_per_thread = 20
        
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.return_value = None
            
            def check_ports():
                results = []
                for i in range(checks_per_thread):
                    port = 8000 + i
                    start_time = time.perf_counter()
                    result = PortManager.check_port_available(port)
                    end_time = time.perf_counter()
                    results.append((result, end_time - start_time))
                return results
            
            start_total = time.perf_counter()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(check_ports) for _ in range(num_threads)]
                all_results = []
                for future in concurrent.futures.as_completed(futures):
                    all_results.extend(future.result())
            
            end_total = time.perf_counter()
            total_time = end_total - start_total
            
            # Verify all checks succeeded
            assert all(result[0] for result in all_results)
            
            # Performance assertion
            avg_time_per_check = total_time / len(all_results)
            assert avg_time_per_check < 0.01, f"Concurrent port checking too slow: {avg_time_per_check:.4f}s per check"
            
            print(f"Concurrent port checking: {len(all_results)} checks in {total_time:.4f}s")

    def test_multiple_orchestrator_instances(self):
        """Test performance with multiple orchestrator instances"""
        num_instances = 20
        times = []
        
        for _ in range(num_instances):
            start_time = time.perf_counter()
            
            orchestrator = FullStackOrchestrator()
            # Simulate basic operations
            env = orchestrator.frontend_service.setup_frontend_environment(8000)
            assert env["NODE_ENV"] == "development"
            
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.001, f"Orchestrator creation too slow: avg={avg_time:.4f}s"
        assert max_time < 0.01, f"Orchestrator creation max time too slow: {max_time:.4f}s"
        
        print(f"Multiple orchestrator instances: avg={avg_time:.4f}s, max={max_time:.4f}s")


class TestResourceCleanup:
    """Test proper resource cleanup and no resource leaks"""

    def test_process_cleanup_reliability(self):
        """Test that process cleanup is reliable and complete"""
        mock_processes = []
        cleanup_results = []
        
        # Create multiple mock processes
        for i in range(10):
            mock_process = Mock()
            mock_process.pid = 1000 + i
            mock_process.poll.return_value = 0 if i % 2 == 0 else None
            mock_processes.append(mock_process)
        
        with patch('core.orchestration.ProcessTerminator.terminate_process_gracefully') as mock_terminate:
            mock_terminate.return_value = True
            
            # Test cleanup of multiple processes
            result = ProcessTerminator.cleanup_processes(mock_processes)
            
            # Verify all processes were handled
            assert mock_terminate.call_count == len(mock_processes)
            
            # Verify statistics are reasonable
            total_handled = result["terminated"] + result["killed"] + result["failed"]
            assert total_handled == len(mock_processes)

    def test_frontend_service_cleanup(self):
        """Test frontend service cleanup"""
        service = FrontendService()
        
        # Set up a mock process
        mock_process = Mock()
        service.process = mock_process
        service.port = 5173
        
        with patch('core.orchestration.ProcessTerminator.terminate_process_gracefully', return_value=True) as mock_terminate:
            result = service.stop()
            
            assert result is True
            mock_terminate.assert_called_once_with(mock_process)

    def test_orchestrator_cleanup_edge_cases(self):
        """Test orchestrator cleanup handles edge cases"""
        orchestrator = FullStackOrchestrator()
        
        # Test cleanup with None
        orchestrator.cleanup_processes_on_exit(None)  # Should not crash
        
        # Test cleanup with invalid ProcessInfo
        invalid_info = ProcessInfo(None, None, 0, False)
        orchestrator.cleanup_processes_on_exit(invalid_info)  # Should not crash
        
        # Test cleanup with exception
        mock_process = Mock()
        frontend_info = ProcessInfo(mock_process, 12345, 5173, True)
        
        with patch('core.orchestration.ProcessTerminator.terminate_process_gracefully', 
                  side_effect=Exception("Cleanup failed")):
            # Should handle exception gracefully
            orchestrator.cleanup_processes_on_exit(frontend_info)


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])  # -s to see print output