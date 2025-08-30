"""
Test suite for dependency registration and AsyncDatabaseService initialization.

This test specifically covers the bug scenario where AsyncDatabaseService was missing
the _init_database method, causing dependency registration to fail during startup.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from core.async_database import AsyncDatabaseService
from core.dependencies import DependencyRegistry, get_dependency_registry
from services.startup import StartupService
from config.factory import create_production_config


class TestDependencyRegistration:
    """Test suite for dependency registration functionality"""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path for testing"""
        with tempfile.NamedTemporaryFile(suffix='_test.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    @pytest.fixture
    def clean_registry(self):
        """Provide a clean dependency registry for testing"""
        registry = DependencyRegistry()
        return registry

    @pytest.mark.asyncio
    async def test_async_database_service_initialization_success(self, temp_db_path):
        """Test that AsyncDatabaseService can be initialized without missing method errors"""
        # This test verifies the fix for the missing _init_database method
        db_service = AsyncDatabaseService(temp_db_path)

        # Should not raise AttributeError about missing _init_database method
        await db_service.initialize()

        # Verify database file was created
        assert os.path.exists(temp_db_path)

        # Verify the service has the required attributes
        assert hasattr(db_service, '_init_database')
        assert callable(db_service._init_database)

        # Clean up
        await db_service.close()

    @pytest.mark.asyncio
    async def test_async_database_service_init_database_method_exists(self, temp_db_path):
        """Test that the _init_database method exists and is callable"""
        db_service = AsyncDatabaseService(temp_db_path)

        # Verify the method exists
        assert hasattr(db_service, '_init_database')
        assert callable(getattr(db_service, '_init_database'))

        # Verify it can be called without errors
        await db_service.initialize()

        # Verify database tables were created by checking if we can query them
        async with db_service.get_connection() as conn:
            # Check if data_items table exists
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='data_items'")
            table_exists = await cursor.fetchone()
            assert table_exists is not None
            assert table_exists['name'] == 'data_items'

        await db_service.close()

    @pytest.mark.asyncio
    async def test_dependency_registry_startup_service_registration(self, temp_db_path, clean_registry):
        """Test that dependency registry can register startup service provider"""
        # Create a mock startup service that uses our database service
        config = create_production_config()
        startup_service = StartupService(config)

        # Initialize the database service first
        db_service = AsyncDatabaseService(temp_db_path)
        await db_service.initialize()

        # Set the database service in startup service
        startup_service.database = db_service

        # Register the startup service provider
        def startup_provider():
            return startup_service

        # This should not raise any errors
        clean_registry.register_startup_service_provider(startup_provider)

        # Verify the provider was registered
        assert clean_registry._startup_service_provider is not None
        assert callable(clean_registry._startup_service_provider)

        # Test that we can get the startup service
        retrieved_service = clean_registry.get_startup_service()
        assert retrieved_service is not None
        assert retrieved_service is startup_service

        # Clean up
        await db_service.close()

    @pytest.mark.asyncio
    async def test_dependency_registry_database_service_registration(self, temp_db_path, clean_registry):
        """Test that dependency registry can register database service provider"""
        # Create a mock startup service
        config = create_production_config()
        startup_service = StartupService(config)

        # Initialize the database service
        db_service = AsyncDatabaseService(temp_db_path)
        await db_service.initialize()
        startup_service.database = db_service

        # Register the database service provider
        def database_provider(startup_svc):
            return startup_svc.database

        # This should not raise any errors
        clean_registry.register_database_service_provider(database_provider)

        # Verify the provider was registered
        assert clean_registry._database_service_provider is not None
        assert callable(clean_registry._database_service_provider)

        # Test that we can get the database service
        retrieved_db = clean_registry.get_database_service(startup_service)
        assert retrieved_db is not None
        assert retrieved_db is db_service

        # Clean up
        await db_service.close()

    @pytest.mark.asyncio
    async def test_full_dependency_registration_workflow(self, temp_db_path, clean_registry):
        """Test the complete dependency registration workflow that was failing"""
        # This test simulates the exact scenario that was failing before the fix

        # Step 1: Create and initialize database service (this was failing before)
        db_service = AsyncDatabaseService(temp_db_path)
        await db_service.initialize()  # This would fail with AttributeError before the fix

        # Step 2: Create startup service and set database
        config = create_production_config()
        startup_service = StartupService(config)
        startup_service.database = db_service

        # Step 3: Register all providers (this was failing because step 1 failed)
        clean_registry.register_startup_service_provider(lambda: startup_service)
        clean_registry.register_database_service_provider(lambda s: s.database)
        clean_registry.register_sync_manager_provider(lambda s: s.sync_manager)
        clean_registry.register_chat_service_provider(lambda s: s.chat_service)

        # Step 4: Verify all providers work
        retrieved_startup = clean_registry.get_startup_service()
        assert retrieved_startup is startup_service

        retrieved_db = clean_registry.get_database_service(startup_service)
        assert retrieved_db is db_service

        # Step 5: Test that FastAPI dependency functions work
        from core.dependencies import get_startup_service_dependency

        # This should work without raising HTTPException
        dep_startup = get_startup_service_dependency()
        assert dep_startup is startup_service

        # Clean up
        await db_service.close()

    @pytest.mark.asyncio
    async def test_database_initialization_error_handling(self, temp_db_path):
        """Test error handling during database initialization"""
        # Test with invalid path to ensure proper error handling
        invalid_path = "/nonexistent/directory/that/does/not/exist/database.db"
        db_service = AsyncDatabaseService(invalid_path)

        # Should raise an exception for invalid path
        with pytest.raises(Exception):
            await db_service.initialize()

    @pytest.mark.asyncio
    async def test_database_service_reinitialization(self, temp_db_path):
        """Test that database service can be reinitialized safely"""
        db_service = AsyncDatabaseService(temp_db_path)

        # Initialize twice
        await db_service.initialize()
        await db_service.initialize()  # Should not fail

        # Verify database still works
        async with db_service.get_connection() as conn:
            cursor = await conn.execute("SELECT 1")
            result = await cursor.fetchone()
            assert result is not None

        await db_service.close()

    @pytest.mark.asyncio
    async def test_dependency_registry_provider_override(self, temp_db_path, clean_registry):
        """Test that dependency providers can be overridden"""
        # Register initial provider
        config = create_production_config()
        startup_service1 = StartupService(config)
        clean_registry.register_startup_service_provider(lambda: startup_service1)

        # Override with new provider
        startup_service2 = StartupService(config)
        clean_registry.register_startup_service_provider(lambda: startup_service2)

        # Should return the new provider
        retrieved = clean_registry.get_startup_service()
        assert retrieved is startup_service2
        assert retrieved is not startup_service1


class TestStartupServiceIntegration:
    """Test integration between StartupService and dependency registration"""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path for testing"""
        with tempfile.NamedTemporaryFile(suffix='_integration.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    @pytest.mark.asyncio
    async def test_startup_service_with_dependency_registry(self, temp_db_path):
        """Test that StartupService works correctly with dependency registry after fix"""
        # This test verifies the end-to-end scenario that was broken

        # Create startup service
        config = create_production_config()
        startup_service = StartupService(config)

        # Initialize database service (this was the failing point)
        db_service = AsyncDatabaseService(temp_db_path)
        await db_service.initialize()
        startup_service.database = db_service

        # Get dependency registry
        registry = get_dependency_registry()

        # Register providers (this would fail before the fix)
        registry.register_startup_service_provider(lambda: startup_service)
        registry.register_database_service_provider(lambda s: s.database)

        # Verify dependency injection works
        injected_startup = registry.get_startup_service()
        injected_db = registry.get_database_service(injected_startup)

        assert injected_startup is startup_service
        assert injected_db is db_service

        # Clean up
        await db_service.close()

    @pytest.mark.asyncio
    async def test_database_service_method_completeness(self, temp_db_path):
        """Test that all expected methods exist on AsyncDatabaseService after fix"""
        db_service = AsyncDatabaseService(temp_db_path)
        await db_service.initialize()

        # Verify all core methods exist and are callable
        required_methods = [
            '_init_database',
            'initialize',
            'close',
            'get_connection',
            'store_data_item',
            'fetch_one',
            'execute_query'
        ]

        for method_name in required_methods:
            assert hasattr(db_service, method_name), f"Missing method: {method_name}"
            assert callable(getattr(db_service, method_name)), f"Method not callable: {method_name}"

        await db_service.close()