"""
Service fixtures for dependency injection and service testing.

This module provides mock services and dependency injection utilities,
enabling isolated testing of services and their interactions.
"""

import pytest
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime, timezone

# Core Services
from core.database import DatabaseService
from core.embeddings import EmbeddingService
from core.vector_store import VectorStoreService
from core.base_service import BaseService, ServiceStatus, ServiceHealth

# Business Services
from services.ingestion import IngestionService, IngestionResult
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.chat_service import ChatService
from services.scheduler import AsyncScheduler
from services.startup import StartupService
from services.sync_manager_service import SyncManagerService
from services.websocket_manager import WebSocketManager

# Sources and Processors
from sources.base import DataItem, BaseSource
from sources.limitless_processor import LimitlessProcessor, BaseProcessor
from sources.sync_manager import SyncManager

# Configuration
from config.models import AppConfig


# Mock Service Base Classes

class MockBaseService:
    """Mock base service with standard service interface"""
    
    def __init__(self, service_name: str = "mock_service"):
        self.service_name = service_name
        self._status = ServiceStatus.READY
        self._health = ServiceHealth.HEALTHY
        self.is_initialized = True
        self.initialization_error = None
        self.health_check_result = True
        
        # Track method calls
        self.initialize_called = False
        self.shutdown_called = False
        self.health_check_called = False
    
    async def initialize(self):
        """Mock initialization"""
        self.initialize_called = True
        if self.initialization_error:
            raise self.initialization_error
        self._status = ServiceStatus.READY
    
    async def shutdown(self):
        """Mock shutdown"""
        self.shutdown_called = True
        self._status = ServiceStatus.SHUTDOWN
    
    async def health_check(self) -> bool:
        """Mock health check"""
        self.health_check_called = True
        return self.health_check_result
    
    @property
    def status(self) -> ServiceStatus:
        return self._status
    
    @property
    def health(self) -> ServiceHealth:
        return self._health


# Core Service Fixtures

@pytest.fixture
def mock_database_service():
    """Mock DatabaseService with common operations"""
    mock_db = MagicMock(spec=DatabaseService)
    
    # Configure default behaviors
    mock_db.store_data_item.return_value = None
    mock_db.get_data_items_by_namespace.return_value = []
    mock_db.get_markdown_by_date.return_value = "# No data found"
    mock_db.get_all_data_items.return_value = []
    mock_db.delete_data_item.return_value = True
    mock_db.update_embedding_status.return_value = None
    mock_db.get_data_items_pending_embedding.return_value = []
    
    # Configure context manager
    mock_connection = MagicMock()
    mock_db.get_connection.return_value.__enter__.return_value = mock_connection
    mock_db.get_connection.return_value.__exit__.return_value = None
    
    return mock_db


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService with standard behaviors"""
    mock_embedding = AsyncMock(spec=EmbeddingService)
    
    # Configure default behaviors
    mock_embedding.generate_embedding.return_value = [0.1] * 384  # Standard vector size
    mock_embedding.batch_generate_embeddings.return_value = [[0.1] * 384, [0.2] * 384]
    mock_embedding.is_initialized = True
    mock_embedding.model_name = "test-model"
    mock_embedding.vector_dimension = 384
    
    # Service status
    mock_embedding.status = ServiceStatus.READY
    mock_embedding.health = ServiceHealth.HEALTHY
    
    return mock_embedding


@pytest.fixture
def mock_vector_store_service():
    """Mock VectorStoreService with search capabilities"""
    mock_vector_store = AsyncMock(spec=VectorStoreService)
    
    # Configure default behaviors
    mock_vector_store.add_vector.return_value = None
    mock_vector_store.search_similar.return_value = [
        ("item_1", 0.95),
        ("item_2", 0.85),
        ("item_3", 0.75)
    ]
    mock_vector_store.delete_vector.return_value = True
    mock_vector_store.get_vector_count.return_value = 100
    
    # Service status
    mock_vector_store.is_initialized = True
    mock_vector_store.status = ServiceStatus.READY
    
    return mock_vector_store


# Business Service Fixtures

@pytest.fixture
def mock_ingestion_service():
    """Mock IngestionService with ingestion operations"""
    mock_ingestion = AsyncMock(spec=IngestionService)
    
    # Create mock ingestion result
    mock_result = IngestionResult()
    mock_result.items_processed = 5
    mock_result.items_stored = 5
    mock_result.items_skipped = 0
    mock_result.embeddings_generated = 5
    mock_result.errors = []
    
    # Configure behaviors
    mock_ingestion.ingest_data_item.return_value = mock_result
    mock_ingestion.process_pending_embeddings.return_value = 5
    mock_ingestion.get_ingestion_stats.return_value = {
        "total_items": 100,
        "pending_embeddings": 5,
        "failed_items": 0
    }
    
    # Service status
    mock_ingestion.status = ServiceStatus.READY
    mock_ingestion.is_initialized = True
    
    return mock_ingestion


@pytest.fixture
def mock_weather_service():
    """Mock WeatherService with weather data operations"""
    mock_weather = MagicMock(spec=WeatherService)
    
    # Sample weather data
    sample_weather = {
        "reportedTime": "2025-01-15T16:00:00Z",
        "days": [{
            "datetime": "2025-01-16",
            "tempmax": 75.2,
            "tempmin": 58.1,
            "humidity": 65.3,
            "conditions": "Sunny"
        }]
    }
    
    # Configure behaviors
    mock_weather.get_latest_weather.return_value = sample_weather
    mock_weather.get_weather_by_date.return_value = sample_weather
    mock_weather.parse_weather_data.return_value = sample_weather
    
    return mock_weather


@pytest.fixture
def mock_news_service():
    """Mock NewsService with news operations"""
    mock_news = MagicMock(spec=NewsService)
    
    # Sample news data
    sample_news = [{
        "title": "Tech Breakthrough",
        "link": "https://example.com/news/1",
        "snippet": "Important development in AI",
        "published_datetime_utc": "2025-01-15T12:00:00Z"
    }]
    
    # Configure behaviors
    mock_news.get_latest_news.return_value = sample_news
    mock_news.get_news_by_date.return_value = sample_news
    
    return mock_news


@pytest.fixture
def mock_chat_service():
    """Mock ChatService with conversation operations"""
    mock_chat = AsyncMock(spec=ChatService)
    
    # Configure behaviors
    mock_chat.process_message.return_value = {
        "response": "Mock AI response",
        "sources_used": ["limitless:001", "news:001"],
        "confidence": 0.85
    }
    mock_chat.get_chat_history.return_value = []
    mock_chat.clear_history.return_value = None
    
    return mock_chat


@pytest.fixture
def mock_scheduler_service():
    """Mock AsyncScheduler with job scheduling"""
    mock_scheduler = AsyncMock(spec=AsyncScheduler)
    
    # Configure behaviors
    mock_scheduler.schedule_job.return_value = "job_123"
    mock_scheduler.cancel_job.return_value = True
    mock_scheduler.get_job_status.return_value = "running"
    mock_scheduler.list_jobs.return_value = []
    mock_scheduler.is_running = True
    
    return mock_scheduler


@pytest.fixture
def mock_startup_service():
    """Mock StartupService with initialization operations"""
    mock_startup = AsyncMock(spec=StartupService)
    
    # Configure behaviors
    mock_startup.initialize_all_services.return_value = True
    mock_startup.health_check_all_services.return_value = {
        "database": True,
        "embeddings": True,
        "vector_store": True
    }
    mock_startup.shutdown_all_services.return_value = None
    
    return mock_startup


@pytest.fixture
def mock_sync_manager_service():
    """Mock SyncManagerService with sync operations"""
    mock_sync = AsyncMock(spec=SyncManagerService)
    
    # Configure behaviors
    mock_sync.sync_all_sources.return_value = {
        "limitless": {"success": True, "items": 10},
        "news": {"success": True, "items": 5},
        "weather": {"success": True, "items": 1}
    }
    mock_sync.sync_source.return_value = {"success": True, "items": 5}
    mock_sync.get_sync_status.return_value = "idle"
    
    return mock_sync


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocketManager with WebSocket operations"""
    mock_ws = AsyncMock(spec=WebSocketManager)
    
    # Configure behaviors
    mock_ws.broadcast.return_value = None
    mock_ws.send_to_client.return_value = None
    mock_ws.get_active_connections.return_value = 2
    mock_ws.disconnect_client.return_value = None
    
    return mock_ws


# Source and Processor Fixtures

@pytest.fixture
def mock_base_source():
    """Mock BaseSource for testing source interactions"""
    mock_source = AsyncMock(spec=BaseSource)
    
    # Sample data items
    sample_items = [
        DataItem(
            id="test:001",
            namespace="test",
            source_id="001",
            content="Test content 1",
            metadata={"title": "Test 1"},
            days_date="2025-01-15"
        )
    ]
    
    # Configure behaviors
    mock_source.fetch_data.return_value = sample_items
    mock_source.test_connection.return_value = True
    mock_source.get_config.return_value = {"api_key": "test_key"}
    
    return mock_source


@pytest.fixture
def mock_limitless_processor():
    """Mock LimitlessProcessor for testing data processing"""
    mock_processor = MagicMock(spec=LimitlessProcessor)
    
    # Configure behaviors
    mock_processor.process.return_value = [
        DataItem(
            id="limitless:processed_001",
            namespace="limitless",
            source_id="processed_001",
            content="Processed limitless content",
            metadata={"title": "Processed Meeting"},
            days_date="2025-01-15"
        )
    ]
    mock_processor.should_process.return_value = True
    
    return mock_processor


@pytest.fixture
def mock_sync_manager():
    """Mock SyncManager for testing sync operations"""
    mock_sync_mgr = AsyncMock(spec=SyncManager)
    
    # Configure behaviors
    mock_sync_mgr.sync_source.return_value = {
        "success": True,
        "items_fetched": 10,
        "items_processed": 10,
        "errors": []
    }
    mock_sync_mgr.get_last_sync_time.return_value = datetime.now(timezone.utc)
    
    return mock_sync_mgr


# Service Factory and Dependency Injection

class MockServiceFactory:
    """Factory for creating mock services with dependencies"""
    
    def __init__(self):
        self.services = {}
        self.dependencies = {}
    
    def register_service(self, service_name: str, service_instance):
        """Register a service instance"""
        self.services[service_name] = service_instance
    
    def register_dependency(self, service_name: str, dependency_name: str, dependency):
        """Register a dependency for a service"""
        if service_name not in self.dependencies:
            self.dependencies[service_name] = {}
        self.dependencies[service_name][dependency_name] = dependency
    
    def get_service(self, service_name: str):
        """Get a service with its dependencies injected"""
        if service_name in self.services:
            service = self.services[service_name]
            
            # Inject dependencies if any
            if service_name in self.dependencies:
                for dep_name, dep_instance in self.dependencies[service_name].items():
                    setattr(service, dep_name, dep_instance)
            
            return service
        
        raise ValueError(f"Service {service_name} not registered")
    
    def create_with_dependencies(self, service_class, **dependencies):
        """Create a service instance with specific dependencies"""
        return service_class(**dependencies)


@pytest.fixture
def mock_service_factory():
    """Factory for creating mock services with dependency injection"""
    return MockServiceFactory()


@pytest.fixture
def fully_mocked_services(
    mock_database_service,
    mock_embedding_service,
    mock_vector_store_service,
    mock_ingestion_service,
    mock_weather_service,
    mock_news_service,
    mock_chat_service,
    mock_scheduler_service,
    mock_startup_service,
    mock_sync_manager_service,
    mock_websocket_manager
):
    """Complete set of mocked services for integration testing"""
    return {
        "database": mock_database_service,
        "embedding": mock_embedding_service,
        "vector_store": mock_vector_store_service,
        "ingestion": mock_ingestion_service,
        "weather": mock_weather_service,
        "news": mock_news_service,
        "chat": mock_chat_service,
        "scheduler": mock_scheduler_service,
        "startup": mock_startup_service,
        "sync_manager": mock_sync_manager_service,
        "websocket": mock_websocket_manager
    }


# Service Testing Utilities

class ServiceTestHelper:
    """Helper utilities for service testing"""
    
    @staticmethod
    def configure_service_success(mock_service):
        """Configure a mock service for successful operations"""
        mock_service.status = ServiceStatus.READY
        mock_service.health = ServiceHealth.HEALTHY
        mock_service.is_initialized = True
        
        if hasattr(mock_service, 'health_check'):
            mock_service.health_check.return_value = True
    
    @staticmethod
    def configure_service_failure(mock_service, error_message="Service error"):
        """Configure a mock service for failure scenarios"""
        mock_service.status = ServiceStatus.ERROR
        mock_service.health = ServiceHealth.UNHEALTHY
        mock_service.is_initialized = False
        
        if hasattr(mock_service, 'health_check'):
            mock_service.health_check.return_value = False
            
        # Configure methods to raise exceptions
        error = Exception(error_message)
        for method_name in ['initialize', 'process', 'fetch_data']:
            if hasattr(mock_service, method_name):
                method = getattr(mock_service, method_name)
                if hasattr(method, 'side_effect'):
                    method.side_effect = error
    
    @staticmethod
    def assert_service_called(mock_service, method_name, times=1):
        """Assert that a service method was called a specific number of times"""
        if hasattr(mock_service, method_name):
            method = getattr(mock_service, method_name)
            assert method.call_count == times, f"{method_name} was called {method.call_count} times, expected {times}"
    
    @staticmethod
    def get_service_call_args(mock_service, method_name, call_index=0):
        """Get the arguments from a specific service method call"""
        if hasattr(mock_service, method_name):
            method = getattr(mock_service, method_name)
            if method.call_args_list and len(method.call_args_list) > call_index:
                return method.call_args_list[call_index]
        return None
    
    @staticmethod
    async def wait_for_async_service(mock_service, method_name, timeout=5.0):
        """Wait for an async service method to complete"""
        if hasattr(mock_service, method_name):
            method = getattr(mock_service, method_name)
            if asyncio.iscoroutinefunction(method):
                try:
                    return await asyncio.wait_for(method(), timeout=timeout)
                except asyncio.TimeoutError:
                    raise AssertionError(f"Async method {method_name} timed out after {timeout} seconds")
        return None


@pytest.fixture
def service_test_helper():
    """Fixture providing service testing helper utilities"""
    return ServiceTestHelper


# Specialized Service Scenarios

@pytest.fixture
def degraded_services_scenario(fully_mocked_services):
    """Scenario with some services in degraded state"""
    services = fully_mocked_services
    
    # Configure some services as degraded
    services["embedding"].health = ServiceHealth.DEGRADED
    services["vector_store"].health = ServiceHealth.DEGRADED
    
    return services


@pytest.fixture
def failed_services_scenario(fully_mocked_services):
    """Scenario with multiple service failures"""
    services = fully_mocked_services
    
    # Configure some services as failed
    ServiceTestHelper.configure_service_failure(services["embedding"], "Embedding model not loaded")
    ServiceTestHelper.configure_service_failure(services["vector_store"], "Vector store unavailable")
    
    return services


# Export all commonly used fixtures
__all__ = [
    "MockBaseService",
    "MockServiceFactory",
    "ServiceTestHelper",
    "mock_database_service",
    "mock_embedding_service",
    "mock_vector_store_service",
    "mock_ingestion_service",
    "mock_weather_service",
    "mock_news_service",
    "mock_chat_service",
    "mock_scheduler_service",
    "mock_startup_service",
    "mock_sync_manager_service",
    "mock_websocket_manager",
    "mock_base_source",
    "mock_limitless_processor",
    "mock_sync_manager",
    "mock_service_factory",
    "fully_mocked_services",
    "service_test_helper",
    "degraded_services_scenario",
    "failed_services_scenario"
]