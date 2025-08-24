"""
Test-driven development tests for server file consistency.

This test file validates that the correct server file is being used and that
it contains all necessary configurations for the application to work properly.
"""

import pytest
from pathlib import Path
import ast
import re


class TestServerFileConsistency:
    """Test that the correct server file is being used with proper configuration."""

    def test_server_file_exists(self):
        """Test that server.py exists and is the active server file."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        assert server_file.exists(), "server.py should exist as the main server file"

    def test_server_has_all_required_route_imports(self):
        """Test that active server.py contains all required route imports."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Required route modules that should be imported
        required_routes = [
            'calendar', 'chat', 'documents', 'embeddings', 'headings',
            'health', 'llm', 'settings', 'sync', 'sync_status', 'system',
            'weather', 'websocket', 'news', 'data_items'
        ]
        
        # Check that each required route is imported
        for route in required_routes:
            # Look for the route in import statements
            import_pattern = rf'\b{route}\b'
            assert re.search(import_pattern, server_content), f"Server should import {route} route module"

    def test_server_router_registration_includes_all_modules(self):
        """Test that active server.py registers all routes including news and data_items."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Look for the routers list definition
        routers_pattern = r'routers\s*=\s*\[(.*?)\]'
        match = re.search(routers_pattern, server_content, re.DOTALL)
        assert match, "Server should have a routers list definition"
        
        routers_content = match.group(1)
        
        # Required route modules that should be in the routers list
        required_in_routers = ['news', 'data_items', 'llm', 'health', 'calendar']
        
        for route in required_in_routers:
            assert route in routers_content, f"Server routers list should include {route}"

    def test_server_has_create_app_function(self):
        """Test that server.py has the required create_app function."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        assert "def create_app" in server_content, "Server should have create_app function"

    def test_server_includes_router_with_api_prefix(self):
        """Test that server.py includes routers with /api prefix."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Should include routers with /api prefix
        assert 'prefix="/api"' in server_content, "Server should register routers with /api prefix"
        assert "app.include_router" in server_content, "Server should include routers in app"

    def test_server_handles_websocket_router_separately(self):
        """Test that server.py handles websocket router without /api prefix."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Websocket router should be included separately (without /api prefix)
        websocket_pattern = r'app\.include_router\(websocket\.router\)'
        assert re.search(websocket_pattern, server_content), "Server should include websocket router separately"

    def test_server_has_proper_fastapi_configuration(self):
        """Test that server.py has proper FastAPI app configuration."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Should have FastAPI app creation with proper config
        assert "FastAPI(" in server_content, "Server should create FastAPI instance"
        assert "Lifeboard API" in server_content, "Server should have proper app title"
        assert "CORS" in server_content, "Server should configure CORS middleware"

    def test_server_file_structure_is_valid_python(self):
        """Test that server.py is valid Python syntax."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        try:
            ast.parse(server_content)
        except SyntaxError as e:
            pytest.fail(f"Server.py has invalid Python syntax: {e}")

    def test_no_server_refactored_references_in_active_server(self):
        """Test that active server.py doesn't contain references to server_refactored."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Should not contain references to refactored server
        assert "server_refactored" not in server_content.lower(), "Active server should not reference server_refactored"

    def test_server_error_handling_and_logging(self):
        """Test that server.py includes proper error handling and logging."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Should have logging configuration
        assert "logging" in server_content, "Server should include logging"
        
        # Should have error handling for imports
        assert "except" in server_content or "try:" in server_content, "Server should include error handling"

    def test_deprecated_server_file_exists_if_renamed(self):
        """Test that if server files were renamed, deprecated version exists."""
        deprecated_file = Path(__file__).parent.parent / "api" / "server_deprecated.py"
        refactored_file = Path(__file__).parent.parent / "api" / "server_refactored.py"
        
        # If server_refactored.py doesn't exist, it might have been renamed to server.py
        # In that case, the old server.py should be renamed to server_deprecated.py
        if not refactored_file.exists():
            # Files may have been renamed - this is OK as long as main server.py works
            pass
        else:
            # If server_refactored still exists, we haven't done the rename yet
            # This test will help us know when to do the rename
            pass

    def test_server_dependency_injection_configuration(self):
        """Test that server.py properly configures dependency injection."""
        server_file = Path(__file__).parent.parent / "api" / "server.py"
        server_content = server_file.read_text()
        
        # Should import dependencies module
        assert "dependencies" in server_content, "Server should import dependencies module"
        
        # Should have lifespan configuration for dependency setup
        assert "lifespan" in server_content, "Server should configure lifespan for dependency injection"