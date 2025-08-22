"""
Test that dependency registry is properly initialized during server startup.
"""
import pytest
from unittest.mock import Mock, patch

from core.dependencies import get_dependency_registry


class TestDependencyRegistryInitialization:
    """Test dependency registry initialization during server lifespan."""

    def test_dependency_registry_providers_registered_during_lifespan(self):
        """Test that dependency registry has providers registered after lifespan setup."""
        from api.server import lifespan
        from services.startup import StartupService
        from config.models import AppConfig
        
        # Create mock config and startup service
        mock_config = Mock(spec=AppConfig)
        mock_startup_service = Mock(spec=StartupService)
        mock_startup_service.initialize_application = Mock(return_value={"success": True})
        mock_startup_service.shutdown_application = Mock()
        mock_startup_service.sync_manager = Mock()
        mock_startup_service.chat_service = Mock()
        
        # Mock the global startup service
        with patch('api.server.get_startup_service', return_value=mock_startup_service):
            with patch('api.server.setup_signal_handlers'):
                with patch('api.server._frontend_orchestrator'):
                    with patch('api.server._process_manager'):
                        # Test the lifespan context manager
                        app = Mock()
                        
                        # Get clean registry for this test
                        registry = get_dependency_registry()
                        
                        # Verify providers are not registered initially
                        with pytest.raises(Exception, match="Startup service provider not registered"):
                            registry.get_startup_service()
                        
                        # Run lifespan startup
                        import asyncio
                        
                        async def test_lifespan():
                            async with lifespan(app):
                                # During lifespan, providers should be registered
                                startup_service = registry.get_startup_service()
                                assert startup_service is not None
                                assert startup_service == mock_startup_service
                                
                                # Test sync manager provider
                                sync_manager = registry.get_sync_manager(mock_startup_service)
                                assert sync_manager == mock_startup_service.sync_manager
                                
                                # Test chat service provider  
                                chat_service = registry.get_chat_service(mock_startup_service)
                                assert chat_service == mock_startup_service.chat_service
                        
                        # Run the async test
                        asyncio.run(test_lifespan())

    def test_dependency_providers_accessible_in_routes_during_lifespan(self):
        """Test that dependency providers work correctly for route dependency injection."""
        from api.server import lifespan
        from core.dependencies import get_startup_service_dependency, get_database_service
        from services.startup import StartupService
        from core.database import DatabaseService
        from config.models import AppConfig
        
        # Create mocks
        mock_config = Mock(spec=AppConfig) 
        mock_startup_service = Mock(spec=StartupService)
        mock_startup_service.initialize_application = Mock(return_value={"success": True})
        mock_startup_service.shutdown_application = Mock()
        mock_startup_service.sync_manager = Mock()
        mock_startup_service.chat_service = Mock()
        mock_startup_service.database = Mock(spec=DatabaseService)
        
        # Mock the global startup service
        with patch('api.server.get_startup_service', return_value=mock_startup_service):
            with patch('api.server.setup_signal_handlers'):
                with patch('api.server._frontend_orchestrator'):
                    with patch('api.server._process_manager'):
                        
                        app = Mock()
                        
                        async def test_route_dependencies():
                            async with lifespan(app):
                                # Test that route dependency functions work
                                startup_service = get_startup_service_dependency()
                                assert startup_service == mock_startup_service
                                
                                database_service = get_database_service(startup_service)  
                                assert database_service == mock_startup_service.database
                        
                        import asyncio
                        asyncio.run(test_route_dependencies())