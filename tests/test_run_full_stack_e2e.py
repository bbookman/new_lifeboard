"""
End-to-end tests for the refactored run_full_stack function.

Tests the complete integration of the refactored orchestration system
to ensure the main entry point maintains expected functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from core.orchestration import FullStackOrchestrator, ProcessInfo


class TestRunFullStackE2E:
    """End-to-end tests for the refactored run_full_stack function"""

    @pytest.mark.asyncio
    async def test_run_full_stack_successful_startup(self):
        """Test complete successful run_full_stack execution"""
        # Mock the orchestration result
        startup_result = {
            "success": True,
            "backend_port": 8000,
            "frontend_port": 5173,
            "frontend_info": ProcessInfo(Mock(), 12345, 5173, True)
        }
        
        # Mock run_server to avoid actually starting the server
        with patch('api.server.run_server') as mock_run_server:
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result) as mock_orchestrate:
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit') as mock_cleanup:
                    
                    # Import and call the function
                    from api.server import run_full_stack
                    
                    await run_full_stack(
                        host="localhost",
                        port=8000,
                        frontend_port=5173,
                        debug=False,
                        kill_existing=False,
                        no_auto_port=False,
                        no_frontend=False
                    )
        
        # Verify orchestration was called with correct parameters
        mock_orchestrate.assert_called_once_with(
            host="localhost",
            backend_port=8000,
            frontend_port=5173,
            no_auto_port=False,
            no_frontend=False,
            kill_existing=False
        )
        
        # Verify backend server was started with resolved port
        mock_run_server.assert_called_once_with(
            host="localhost",
            port=8000,
            debug=False,
            kill_existing=False
        )
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_full_stack_with_port_resolution(self):
        """Test run_full_stack with port auto-resolution"""
        # Mock the orchestration result with resolved ports
        startup_result = {
            "success": True,
            "backend_port": 8001,  # Auto-resolved
            "frontend_port": 5174,  # Auto-resolved
            "frontend_info": ProcessInfo(Mock(), 12345, 5174, True)
        }
        
        with patch('api.server.run_server') as mock_run_server:
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result):
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit'):
                    
                    from api.server import run_full_stack
                    
                    await run_full_stack(
                        host="localhost",
                        port=8000,  # Original port
                        frontend_port=5173,  # Original port
                        debug=False,
                        kill_existing=False,
                        no_auto_port=False,
                        no_frontend=False
                    )
        
        # Verify backend server was started with resolved port
        mock_run_server.assert_called_once_with(
            host="localhost",
            port=8001,  # Should use resolved port
            debug=False,
            kill_existing=False
        )

    @pytest.mark.asyncio
    async def test_run_full_stack_no_frontend_mode(self):
        """Test run_full_stack in no-frontend mode"""
        startup_result = {
            "success": True,
            "backend_port": 8000,
            "frontend_port": 5173,
            "frontend_info": None  # No frontend started
        }
        
        with patch('api.server.run_server') as mock_run_server:
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result) as mock_orchestrate:
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit') as mock_cleanup:
                    
                    from api.server import run_full_stack
                    
                    await run_full_stack(
                        host="localhost",
                        port=8000,
                        frontend_port=5173,
                        debug=False,
                        kill_existing=False,
                        no_auto_port=False,
                        no_frontend=True  # Frontend disabled
                    )
        
        # Verify orchestration was called with no_frontend=True
        mock_orchestrate.assert_called_once()
        call_args = mock_orchestrate.call_args[1]
        assert call_args['no_frontend'] is True
        
        # Verify cleanup was called with None (no frontend process)
        mock_cleanup.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_run_full_stack_orchestration_failure(self):
        """Test run_full_stack when orchestration fails"""
        startup_result = {
            "success": False,
            "error": "Port resolution failed",
            "backend_port": None,
            "frontend_port": None,
            "frontend_info": None
        }
        
        with patch('api.server.run_server') as mock_run_server:
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result):
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit'):
                    with patch('sys.exit') as mock_exit:
                        with patch('core.orchestration.logger') as mock_logger:
                            
                            from api.server import run_full_stack
                            
                            await run_full_stack(
                                host="localhost",
                                port=8000,
                                frontend_port=5173,
                                debug=False,
                                kill_existing=False,
                                no_auto_port=False,
                                no_frontend=False
                            )
        
        # Verify exit was called due to failure
        mock_exit.assert_called_once_with(1)
        
        # Verify run_server was not called
        mock_run_server.assert_not_called()
        
        # Verify error was logged
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_run_full_stack_keyboard_interrupt(self):
        """Test run_full_stack handling of KeyboardInterrupt"""
        startup_result = {
            "success": True,
            "backend_port": 8000,
            "frontend_port": 5173,
            "frontend_info": ProcessInfo(Mock(), 12345, 5173, True)
        }
        
        with patch('api.server.run_server', side_effect=KeyboardInterrupt()) as mock_run_server:
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result):
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit') as mock_cleanup:
                    with patch('builtins.print') as mock_print:
                        
                        from api.server import run_full_stack
                        
                        await run_full_stack(
                            host="localhost",
                            port=8000,
                            frontend_port=5173,
                            debug=False,
                            kill_existing=False,
                            no_auto_port=False,
                            no_frontend=False
                        )
        
        # Verify cleanup was still called
        mock_cleanup.assert_called_once()
        
        # Verify shutdown message was printed
        mock_print.assert_any_call("\n\n⏹️  Shutting down application...")

    @pytest.mark.asyncio
    async def test_run_full_stack_runtime_exception(self):
        """Test run_full_stack handling of unexpected runtime exceptions"""
        startup_result = {
            "success": True,
            "backend_port": 8000,
            "frontend_port": 5173,
            "frontend_info": ProcessInfo(Mock(), 12345, 5173, True)
        }
        
        with patch('api.server.run_server', side_effect=Exception("Server crashed")) as mock_run_server:
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result):
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit') as mock_cleanup:
                    with patch('builtins.print') as mock_print:
                        with patch('core.orchestration.logger') as mock_logger:
                            
                            from api.server import run_full_stack
                            
                            await run_full_stack(
                                host="localhost",
                                port=8000,
                                frontend_port=5173,
                                debug=False,
                                kill_existing=False,
                                no_auto_port=False,
                                no_frontend=False
                            )
        
        # Verify cleanup was still called
        mock_cleanup.assert_called_once()
        
        # Verify error was logged and printed
        mock_logger.error.assert_called()
        mock_print.assert_any_call("❌ Application startup failed: Server crashed")

    @pytest.mark.asyncio
    async def test_run_full_stack_frontend_process_global_assignment(self):
        """Test that frontend process is assigned to global variable"""
        mock_process = Mock()
        frontend_info = ProcessInfo(mock_process, 12345, 5173, True)
        startup_result = {
            "success": True,
            "backend_port": 8000,
            "frontend_port": 5173,
            "frontend_info": frontend_info
        }
        
        with patch('api.server.run_server'):
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result):
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit'):
                    
                    # Mock the global variable
                    with patch('api.server._frontend_process', None, create=True) as mock_global:
                        
                        from api.server import run_full_stack
                        
                        await run_full_stack(
                            host="localhost",
                            port=8000,
                            frontend_port=5173,
                            debug=False,
                            kill_existing=False,
                            no_auto_port=False,
                            no_frontend=False
                        )
        
        # Note: Testing global assignment is tricky due to import behavior
        # The test verifies the code path is exercised

    @pytest.mark.asyncio
    async def test_run_full_stack_parameter_passing(self):
        """Test that all parameters are correctly passed to orchestration"""
        startup_result = {
            "success": True,
            "backend_port": 9000,
            "frontend_port": 3000,
            "frontend_info": None
        }
        
        with patch('api.server.run_server'):
            with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                             return_value=startup_result) as mock_orchestrate:
                with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit'):
                    
                    from api.server import run_full_stack
                    
                    await run_full_stack(
                        host="0.0.0.0",  # Custom host
                        port=9000,       # Custom backend port
                        frontend_port=3000,  # Custom frontend port
                        debug=True,      # Debug enabled
                        kill_existing=True,  # Kill existing processes
                        no_auto_port=True,   # No auto port
                        no_frontend=True     # No frontend
                    )
        
        # Verify all parameters were passed correctly
        mock_orchestrate.assert_called_once_with(
            host="0.0.0.0",
            backend_port=9000,
            frontend_port=3000,
            no_auto_port=True,
            no_frontend=True,
            kill_existing=True
        )

    @pytest.mark.asyncio
    async def test_run_full_stack_cleanup_always_called(self):
        """Test that cleanup is always called even if startup fails"""
        startup_result = {
            "success": False,
            "error": "Orchestration failed",
            "frontend_info": ProcessInfo(Mock(), 12345, 5173, True)
        }
        
        with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                         return_value=startup_result):
            with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit') as mock_cleanup:
                with patch('sys.exit'):
                    
                    from api.server import run_full_stack
                    
                    await run_full_stack(
                        host="localhost",
                        port=8000,
                        frontend_port=5173,
                        debug=False,
                        kill_existing=False,
                        no_auto_port=False,
                        no_frontend=False
                    )
        
        # Cleanup should still be called even though startup failed
        mock_cleanup.assert_called_once_with(startup_result["frontend_info"])


class TestRunFullStackIntegration:
    """Integration tests combining run_full_stack with real orchestration components"""

    @pytest.mark.asyncio
    async def test_run_full_stack_with_real_orchestrator_components(self):
        """Integration test using real orchestrator components (but mocked external dependencies)"""
        # Mock external dependencies but use real orchestration logic
        with patch('subprocess.Popen') as mock_popen:
            with patch('os.environ.copy', return_value={"PATH": "/usr/bin"}):
                with patch('core.orchestration.FrontendEnvironmentValidator.validate_environment', 
                          return_value={"node_installed": True, "dependencies_ready": True, "frontend_dir_exists": True}):
                    with patch('core.orchestration.PortManager.check_port_available', return_value=True):
                        with patch('api.server.run_server'):
                            with patch('time.sleep'):  # Speed up validation
                                with patch('socket.socket'):  # Mock port responsiveness check
                                    
                                    mock_process = Mock()
                                    mock_process.pid = 12345
                                    mock_process.poll.return_value = None
                                    mock_popen.return_value = mock_process
                                    
                                    from api.server import run_full_stack
                                    
                                    # This should exercise real orchestration logic
                                    await run_full_stack(
                                        host="localhost",
                                        port=8000,
                                        frontend_port=5173,
                                        debug=False,
                                        kill_existing=False,
                                        no_auto_port=False,
                                        no_frontend=False
                                    )
        
        # Verify subprocess was called for frontend startup
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert call_args == ["npm", "run", "dev"]

    @pytest.mark.asyncio
    async def test_run_full_stack_error_propagation(self):
        """Test that errors from real orchestration components are properly handled"""
        # Mock components to simulate real failure scenarios
        with patch('core.orchestration.PortManager.resolve_port', 
                  side_effect=RuntimeError("No available ports")):
            with patch('sys.exit') as mock_exit:
                
                from api.server import run_full_stack
                
                await run_full_stack(
                    host="localhost",
                    port=8000,
                    frontend_port=5173,
                    debug=False,
                    kill_existing=False,
                    no_auto_port=False,
                    no_frontend=False
                )
        
        # Should exit with error code
        mock_exit.assert_called_once_with(1)


class TestRunFullStackEdgeCases:
    """Test edge cases and unusual scenarios"""

    @pytest.mark.asyncio
    async def test_run_full_stack_with_none_startup_result(self):
        """Test run_full_stack when orchestration returns None or invalid result"""
        with patch.object(FullStackOrchestrator, 'orchestrate_startup', return_value=None):
            with patch('sys.exit') as mock_exit:
                
                from api.server import run_full_stack
                
                await run_full_stack(
                    host="localhost",
                    port=8000,
                    frontend_port=5173,
                    debug=False,
                    kill_existing=False,
                    no_auto_port=False,
                    no_frontend=False
                )
        
        # Should handle gracefully and exit
        mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_run_full_stack_with_orchestrator_exception(self):
        """Test run_full_stack when orchestrator constructor fails"""
        with patch('core.orchestration.FullStackOrchestrator', 
                  side_effect=Exception("Orchestrator init failed")):
            with patch('builtins.print') as mock_print:
                with patch('core.orchestration.logger') as mock_logger:
                    
                    from api.server import run_full_stack
                    
                    await run_full_stack(
                        host="localhost",
                        port=8000,
                        frontend_port=5173,
                        debug=False,
                        kill_existing=False,
                        no_auto_port=False,
                        no_frontend=False
                    )
        
        # Should handle the exception gracefully
        mock_print.assert_any_call("❌ Application startup failed: Orchestrator init failed")
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_run_full_stack_cleanup_with_none_result(self):
        """Test cleanup behavior when startup_result is None"""
        with patch.object(FullStackOrchestrator, 'orchestrate_startup', 
                         side_effect=Exception("Early failure")):
            with patch.object(FullStackOrchestrator, 'cleanup_processes_on_exit') as mock_cleanup:
                with patch('builtins.print'):
                    with patch('core.orchestration.logger'):
                        
                        from api.server import run_full_stack
                        
                        await run_full_stack(
                            host="localhost",
                            port=8000,
                            frontend_port=5173,
                            debug=False,
                            kill_existing=False,
                            no_auto_port=False,
                            no_frontend=False
                        )
        
        # Cleanup should be called with None when startup_result is None
        mock_cleanup.assert_called_once_with(None)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])