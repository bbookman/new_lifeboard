"""
Test-driven development tests for dependency injection system.

This test file validates that the dependency injection system works properly
for new routes, specifically testing the missing get_database_service dependency
and ensuring all route dependencies can be resolved.
"""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi import HTTPException

from core.dependencies import get_dependency_registry
from services.startup import StartupService


class TestDependencyInjection:
    """Test that dependency injection system works for new routes."""

    def test_get_database_service_dependency_function_exists(self):
        """Test that get_database_service dependency function exists in core.dependencies."""
        try:
            from core.dependencies import get_database_service
            assert callable(get_database_service), "get_database_service should be a callable function"
        except ImportError:
            pytest.fail("get_database_service function should exist in core.dependencies module")

    def test_get_database_service_returns_database_from_startup_service(self):
        """Test that get_database_service properly extracts database from startup service."""
        # Import the function we're testing
        from core.dependencies import get_database_service
        
        # Create mock startup service with database
        mock_startup_service = Mock(spec=StartupService)
        mock_database = Mock()
        mock_startup_service.database = mock_database
        
        # Call the dependency function
        result = get_database_service(mock_startup_service)
        
        # Should return the database from the startup service
        assert result == mock_database, "get_database_service should return the database from startup service"

    def test_get_database_service_raises_error_when_database_unavailable(self):
        """Test that get_database_service raises proper error when database is not available."""
        from core.dependencies import get_database_service
        
        # Create mock startup service without database
        mock_startup_service = Mock(spec=StartupService)
        mock_startup_service.database = None
        
        # Should raise HTTPException when database is not available
        with pytest.raises(HTTPException) as exc_info:
            get_database_service(mock_startup_service)
        
        assert exc_info.value.status_code == 503
        assert "Database service not available" in str(exc_info.value.detail)

    def test_news_route_dependencies_can_be_resolved(self):
        """Test that news route can resolve all its dependencies without import errors."""
        try:
            from api.routes.news import get_news_service
            from core.dependencies import get_database_service
            
            # Both dependency functions should be importable and callable
            assert callable(get_news_service), "get_news_service should be callable"
            assert callable(get_database_service), "get_database_service should be callable"
            
        except ImportError as e:
            pytest.fail(f"News route dependencies cannot be imported: {e}")

    def test_data_items_route_dependencies_can_be_resolved(self):
        """Test that data_items route can resolve all its dependencies without import errors."""
        try:
            from api.routes.data_items import router
            from core.dependencies import get_database_service
            
            # Route should be importable and database dependency should exist
            assert router is not None, "data_items router should be importable"
            assert callable(get_database_service), "get_database_service should be callable"
            
        except ImportError as e:
            pytest.fail(f"Data items route dependencies cannot be imported: {e}")

    def test_news_service_can_be_instantiated_with_database_dependency(self):
        """Test that NewsService can be instantiated with database dependency."""
        try:
            from services.news_service import NewsService
            from core.database import DatabaseService
            
            # Create mock database service
            mock_database = Mock(spec=DatabaseService)
            
            # Should be able to create NewsService with database
            news_service = NewsService(mock_database)
            assert news_service is not None, "NewsService should be instantiable with database service"
            
        except Exception as e:
            pytest.fail(f"Failed to create NewsService with database dependency: {e}")

    def test_dependency_registry_has_required_providers(self):
        """Test that dependency registry has all required service providers."""
        registry = get_dependency_registry()
        
        # Registry should have startup service provider
        assert hasattr(registry, '_startup_service_provider'), "Registry should have startup service provider"
        
        # Test that we can get a startup service (even if mocked)
        mock_startup_service = Mock(spec=StartupService)
        mock_startup_service.database = Mock()
        
        # Register a test provider
        registry.register_startup_service_provider(lambda: mock_startup_service)
        
        # Should be able to get startup service
        startup_service = registry.get_startup_service()
        assert startup_service is not None, "Should be able to get startup service from registry"

    def test_database_service_dependency_chain_works_end_to_end(self):
        """Test that the full dependency chain works from startup service to database service."""
        from core.dependencies import get_database_service, get_startup_service_dependency
        
        # Mock the full chain
        mock_database = Mock()
        mock_startup_service = Mock(spec=StartupService)
        mock_startup_service.database = mock_database
        
        # Test that dependency chain works
        database_service = get_database_service(mock_startup_service)
        assert database_service == mock_database, "Dependency chain should work end-to-end"

    def test_route_dependency_injection_patterns_are_consistent(self):
        """Test that all routes use consistent dependency injection patterns."""
        # Test that dependency patterns match existing working routes
        try:
            from api.routes.calendar import get_database_service as calendar_get_db
            from api.routes.news import get_news_service
            from core.dependencies import get_database_service
            
            # All dependency functions should be callable
            assert callable(calendar_get_db), "Calendar route database dependency should be callable"
            assert callable(get_news_service), "News route service dependency should be callable" 
            assert callable(get_database_service), "Core database dependency should be callable"
            
        except ImportError as e:
            pytest.fail(f"Dependency injection patterns are inconsistent: {e}")

    def test_startup_service_dependency_is_available(self):
        """Test that startup service dependency injection works."""
        try:
            from core.dependencies import get_startup_service_dependency
            
            assert callable(get_startup_service_dependency), "get_startup_service_dependency should be callable"
            
        except ImportError:
            pytest.fail("get_startup_service_dependency should be available in core.dependencies")