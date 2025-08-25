"""
Test-driven development tests for server route registration.

This test file validates that all route modules are properly imported 
and registered in the FastAPI application, specifically focusing on 
the missing news and data_items routes.
"""

import pytest
import importlib
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from api.server import app


class TestServerRouteRegistration:
    """Test that all route modules are properly imported and registered."""

    def test_news_route_module_can_be_imported(self):
        """Test that news route module can be imported without errors."""
        try:
            from api.routes import news
            assert hasattr(news, 'router'), "News module should have a router attribute"
        except ImportError as e:
            pytest.fail(f"Failed to import news route module: {e}")

    def test_data_items_route_module_can_be_imported(self):
        """Test that data_items route module can be imported without errors."""
        try:
            from api.routes import data_items
            assert hasattr(data_items, 'router'), "Data items module should have a router attribute"
        except ImportError as e:
            pytest.fail(f"Failed to import data_items route module: {e}")

    def test_server_imports_all_required_route_modules(self):
        """Test that server.py imports all required route modules including news and data_items."""
        # Read the server.py file to check imports
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Check that news and data_items are imported
        assert "news," in server_content or "news\n" in server_content, "Server should import news route module"
        assert "data_items," in server_content or "data_items\n" in server_content, "Server should import data_items route module"

    def test_server_registers_all_route_modules_in_router_list(self):
        """Test that server.py includes all route modules in the routers list."""
        # Read the server.py file to check router registration
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Look for the routers list and verify it includes news and data_items
        assert "news" in server_content, "Server routers list should include news"
        assert "data_items" in server_content, "Server routers list should include data_items"

    def test_app_creation_succeeds_with_all_routes(self):
        """Test that FastAPI app can be created successfully with all routes."""
        try:
            # Use the existing app instance
            assert app is not None, "App creation should succeed"
            assert app.title == "Lifeboard API", "App should have correct title"
        except ImportError as e:
            pytest.fail(f"App creation failed due to import error: {e}")
        except Exception as e:
            pytest.fail(f"App creation failed: {e}")

    def test_all_expected_routes_are_registered_in_app(self):
        """Test that all expected routes are actually registered in the FastAPI app."""
        # Use the existing app instance
        
        # Get all registered routes
        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # Check for expected API routes (these should exist after proper registration)
        expected_prefixes = [
            "/api/news",      # from news route module
            "/api/data_items", # from data_items route module  
            "/api/llm",       # from llm route module
            "/api/health",    # from health route module
            "/api/calendar",  # from calendar route module
        ]
        
        for prefix in expected_prefixes:
            # Check if any route starts with this prefix
            matching_routes = [path for path in route_paths if path.startswith(prefix)]
            assert len(matching_routes) > 0, f"No routes found with prefix {prefix}. Available routes: {route_paths}"

    def test_no_import_errors_during_server_startup(self):
        """Test that server startup doesn't fail with ImportError from route modules."""
        # This test specifically checks the import chain doesn't break
        try:
            # Import server module - this should not raise ImportError
            import api.server
            
            # Check the existing app - this validates all route imports
            app_instance = api.server.app
            
            # If we get here, no import errors occurred
            assert True, "Server startup completed without import errors"
            
        except ImportError as e:
            pytest.fail(f"Server startup failed with ImportError: {e}")

    def test_route_modules_have_required_attributes(self):
        """Test that route modules have the required router attribute."""
        route_modules = ['news', 'data_items', 'llm', 'health', 'calendar']
        
        for module_name in route_modules:
            try:
                module = importlib.import_module(f"api.routes.{module_name}")
                assert hasattr(module, 'router'), f"Route module {module_name} should have a router attribute"
                assert module.router is not None, f"Route module {module_name} router should not be None"
            except ImportError as e:
                pytest.fail(f"Failed to import route module {module_name}: {e}")

    def test_server_file_has_correct_structure(self):
        """Test that the active server.py file has the expected structure."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        assert server_file.exists(), "server.py should exist"
        
        server_content = server_file.read_text()
        
        # Check for key structural elements
        assert "app = FastAPI" in server_content, "server.py should create FastAPI app instance"
        assert "app.include_router" in server_content, "server.py should register routers"
        assert "FastAPI(" in server_content, "server.py should create FastAPI instance"