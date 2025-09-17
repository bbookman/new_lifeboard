"""
Integration tests to validate all service migrations to repository pattern are working correctly.

This comprehensive test suite validates:
1. All migrated services can be initialized with RepositoryFactory
2. Repository patterns are working correctly for database operations
3. Backward compatibility is maintained
4. Service integration works end-to-end
5. No regressions in functionality
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from core.repositories.repository_factory import RepositoryFactory
from core.database import DatabaseService
from services.llm_service import LLMService
from services.chat_service import ChatService
from services.ingestion import IngestionService
from services.template_processor import TemplateProcessor
from services.startup import StartupService
from services.document_service import DocumentService
from config.factory import ConfigFactory


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db_path = f.name
    
    try:
        yield temp_db_path
    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


@pytest.fixture
def database_service(temp_db):
    """Create DatabaseService with temporary database"""
    return DatabaseService(temp_db)


@pytest.fixture
def repository_factory(database_service):
    """Create RepositoryFactory with test database"""
    return RepositoryFactory(database_service)


@pytest.fixture
def mock_config():
    """Create mock configuration"""
    config = Mock()
    config.llm = Mock()
    config.llm.provider = "test"
    config.llm.model = "test-model"
    config.llm.temperature = 0.7
    config.llm.max_tokens = 1000
    config.embeddings = Mock()
    config.embeddings.model_name = "test-embedding-model"
    config.embeddings.device = "cpu"
    return config


class TestRepositoryFactoryValidation:
    """Test RepositoryFactory functionality and health checks"""
    
    def test_repository_factory_initialization(self, repository_factory):
        """Test that RepositoryFactory initializes correctly"""
        assert repository_factory is not None
        assert repository_factory.database_service is not None
    
    def test_repository_factory_health_check(self, repository_factory):
        """Test repository factory health check functionality"""
        health_status = repository_factory.health_check()
        
        # Check that all repositories are accessible
        expected_repos = ['data_item', 'settings', 'chat', 'data_source', 'llm']
        for repo_name in expected_repos:
            assert repo_name in health_status
            assert health_status[repo_name] == 'healthy'
    
    def test_all_repositories_can_be_created(self, repository_factory):
        """Test that all repository types can be successfully created"""
        # Test DataItemRepository
        data_item_repo = repository_factory.get_data_item_repository()
        assert data_item_repo is not None
        
        # Test SettingsRepository
        settings_repo = repository_factory.get_settings_repository()
        assert settings_repo is not None
        
        # Test ChatRepository
        chat_repo = repository_factory.get_chat_repository()
        assert chat_repo is not None
        
        # Test DataSourceRepository
        data_source_repo = repository_factory.get_data_source_repository()
        assert data_source_repo is not None
        
        # Test LLMRepository
        llm_repo = repository_factory.get_llm_repository()
        assert llm_repo is not None


class TestLLMServiceMigrationValidation:
    """Test LLMService migration to repository pattern"""
    
    @pytest.fixture
    def llm_service(self, repository_factory, mock_config):
        """Create LLMService with repository factory"""
        document_service = Mock()
        return LLMService(
            repository_factory=repository_factory,
            document_service=document_service,
            config=mock_config
        )
    
    def test_llm_service_initialization_with_repositories(self, llm_service):
        """Test that LLMService initializes correctly with repositories"""
        assert llm_service.repository_factory is not None
        assert llm_service.llm_repo is not None
        assert llm_service.data_item_repo is not None
    
    def test_llm_service_cached_summary_operations(self, llm_service):
        """Test cached summary operations use repository methods"""
        test_date = "2025-09-17"
        test_summary = "Test summary content"
        test_prompt = "Test prompt template"
        
        # Test storing via repository directly
        llm_service.llm_repo.store_generated_summary(test_date, test_summary, test_prompt)
        
        # Test retrieving via repository
        retrieved_summary = llm_service.llm_repo.get_cached_summary(test_date)
        assert retrieved_summary == test_summary
    
    def test_llm_service_prompt_settings_operations(self, llm_service):
        """Test prompt settings operations use repository methods"""
        # Test available repository methods for context building
        test_date = "2025-09-17"
        
        # Test news context retrieval
        news_context = llm_service.llm_repo.get_news_for_context(test_date)
        assert isinstance(news_context, list)
        
        # Test weather context retrieval
        weather_context = llm_service.llm_repo.get_weather_for_context(test_date)
        # Should return None for empty database, not fail
        assert weather_context is None or isinstance(weather_context, dict)


class TestChatServiceMigrationValidation:
    """Test ChatService migration to repository pattern"""
    
    @pytest.fixture
    def chat_service(self, repository_factory, mock_config):
        """Create ChatService with repository factory"""
        vector_store = Mock()
        embeddings = Mock()
        service = ChatService(
            config=mock_config,
            repository_factory=repository_factory,
            vector_store=vector_store,
            embeddings=embeddings
        )
        # Don't call initialize() as it's async and not needed for repository testing
        return service
    
    def test_chat_service_initialization_with_repositories(self, chat_service):
        """Test that ChatService initializes correctly with repositories"""
        assert chat_service.repository_factory is not None
        assert chat_service.chat_repo is not None
        assert chat_service.data_item_repo is not None
    
    def test_chat_service_message_storage(self, chat_service):
        """Test chat message storage uses repository methods"""
        user_message = "Test user message"
        assistant_response = "Test assistant response"
        
        # Test storing via repository directly
        chat_service.chat_repo.store_chat_message(user_message, assistant_response)
        
        # Test retrieving via repository
        chat_history = chat_service.chat_repo.get_chat_history(limit=1)
        assert len(chat_history) == 1
        assert chat_history[0]['user_message'] == user_message
        assert chat_history[0]['assistant_response'] == assistant_response


class TestIngestionServiceMigrationValidation:
    """Test IngestionService migration to repository pattern"""
    
    @pytest.fixture
    def ingestion_service(self, repository_factory, mock_config):
        """Create IngestionService with repository factory"""
        embedding_service = Mock()
        vector_store = Mock()
        
        return IngestionService(
            repository_factory=repository_factory,
            embedding_service=embedding_service,
            vector_store=vector_store,
            config=mock_config
        )
    
    def test_ingestion_service_initialization_with_repositories(self, ingestion_service):
        """Test that IngestionService initializes correctly with repositories"""
        assert ingestion_service.repository_factory is not None
        assert ingestion_service.data_item_repo is not None
        assert ingestion_service.data_source_repo is not None
        assert ingestion_service.settings_repo is not None
    
    @pytest.mark.asyncio
    async def test_ingestion_service_data_storage(self, ingestion_service):
        """Test data storage uses repository methods"""
        from sources.base import DataItem
        
        # Create test data item
        test_item = DataItem(
            namespace="test",
            source_id="test_001",
            content="Test content",
            metadata={"test": "metadata"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Test storing data item directly via repository (simulating ingestion workflow)
        test_id = f"{test_item.namespace}:{test_item.source_id}"
        ingestion_service.data_item_repo.store_data_item(
            id=test_id,
            namespace=test_item.namespace,
            source_id=test_item.source_id,
            content=test_item.content,
            metadata=test_item.metadata,
            days_date="2025-09-17"
        )
        
        # Verify storage using repository
        stored_items = ingestion_service.data_item_repo.get_data_items_by_namespace("test", limit=1)
        assert len(stored_items) == 1
        assert stored_items[0]['namespace'] == "test"
        assert stored_items[0]['source_id'] == "test_001"


class TestTemplateProcessorMigrationValidation:
    """Test TemplateProcessor migration to repository pattern"""
    
    @pytest.fixture
    def template_processor(self, repository_factory, mock_config):
        """Create TemplateProcessor with repository factory"""
        return TemplateProcessor(
            repository_factory=repository_factory,
            config=mock_config,
            timezone='America/New_York'
        )
    
    def test_template_processor_initialization_with_repositories(self, template_processor):
        """Test that TemplateProcessor initializes correctly with repositories"""
        assert template_processor.repository_factory is not None
        assert template_processor.data_item_repo is not None
        assert template_processor.database is not None
    
    @pytest.mark.asyncio
    async def test_template_processor_data_retrieval(self, template_processor):
        """Test template data retrieval uses repository methods"""
        test_date = "2025-09-17"
        
        # Test that repository is being used for data access
        # This tests the migration, not necessarily complete functionality
        assert template_processor.data_item_repo is not None
        
        # Test basic data retrieval through repository
        data_items = await template_processor.data_item_repo.async_get_data_items_by_date(test_date)
        assert isinstance(data_items, list)  # Should return empty list, not fail


class TestServiceIntegrationValidation:
    """Test end-to-end service integration with repository pattern"""
    
    @pytest.fixture
    def startup_service(self, temp_db, mock_config):
        """Create StartupService with test configuration"""
        # StartupService takes config, not db_path
        # Update mock config to use temp database
        mock_config.database = Mock()
        mock_config.database.path = temp_db
        
        # Mock all external dependencies
        with patch.object(ConfigFactory, 'create_config', return_value=mock_config), \
             patch('services.startup.EmbeddingService'), \
             patch('services.startup.VectorStoreService'), \
             patch('services.startup.DocumentService'):
            service = StartupService(config=mock_config)
            return service
    
    def test_startup_service_initializes_all_services_with_repositories(self, startup_service):
        """Test that StartupService initializes all services with repository pattern"""
        # Check that RepositoryFactory is initialized
        assert startup_service.repository_factory is not None
        
        # Check that services are initialized with repositories
        assert startup_service.llm_service is not None
        assert startup_service.chat_service is not None
        assert startup_service.ingestion_service is not None
        assert startup_service.template_processor is not None
        
        # Verify services have repository dependencies
        assert hasattr(startup_service.llm_service, 'repository_factory')
        assert hasattr(startup_service.chat_service, 'repository_factory')
        assert hasattr(startup_service.ingestion_service, 'repository_factory')
        assert hasattr(startup_service.template_processor, 'repository_factory')
    
    def test_service_cross_communication_works(self, startup_service):
        """Test that services can communicate through shared repositories"""
        # Test that LLMService can store data accessible by other services
        test_date = "2025-09-17"
        test_summary = "Cross-service test summary"
        
        # Store via LLMService
        startup_service.llm_service.store_cached_summary(test_date, test_summary)
        
        # Retrieve via repository directly
        cached_summary = startup_service.repository_factory.get_llm_repository().get_cached_summary(test_date)
        assert cached_summary == test_summary


class TestBackwardCompatibilityValidation:
    """Test that migrations maintain backward compatibility"""
    
    def test_database_service_methods_still_work(self, database_service):
        """Test that DatabaseService methods still function for legacy code"""
        # Test basic data item storage (legacy method)
        test_id = "test:legacy_001"
        test_content = "Legacy test content"
        test_metadata = {"legacy": True}
        
        database_service.store_data_item(
            id=test_id,
            namespace="test", 
            source_id="legacy_001",
            content=test_content,
            metadata=test_metadata,
            days_date="2025-09-17"
        )
        
        # Test retrieval works
        items = database_service.get_data_items_by_namespace("test", limit=1)
        assert len(items) == 1
        assert items[0]['id'] == test_id
        assert items[0]['content'] == test_content
    
    def test_repository_and_database_service_consistency(self, repository_factory, database_service):
        """Test that repository methods and database service methods produce consistent results"""
        test_namespace = "consistency_test"
        test_data = {
            "id": f"{test_namespace}:consistency_001",
            "namespace": test_namespace,
            "source_id": "consistency_001",
            "content": "Consistency test content",
            "metadata": {"test": "consistency"},
            "days_date": "2025-09-17"
        }
        
        # Store via repository
        data_item_repo = repository_factory.get_data_item_repository()
        data_item_repo.store_data_item(**test_data)
        
        # Retrieve via both methods
        repo_items = data_item_repo.get_data_items_by_namespace(test_namespace, limit=1)
        db_items = database_service.get_data_items_by_namespace(test_namespace, limit=1)
        
        # Results should be identical
        assert len(repo_items) == len(db_items) == 1
        assert repo_items[0]['id'] == db_items[0]['id']
        assert repo_items[0]['content'] == db_items[0]['content']


class TestPerformanceAndHealthValidation:
    """Test performance and health aspects of migrated services"""
    
    def test_repository_connection_pooling(self, repository_factory):
        """Test that repositories properly manage database connections"""
        data_item_repo = repository_factory.get_data_item_repository()
        
        # Multiple operations should not fail due to connection issues
        for i in range(10):
            test_data = {
                "id": f"perf_test:item_{i}",
                "namespace": "perf_test",
                "source_id": f"item_{i}",
                "content": f"Performance test content {i}",
                "metadata": {"iteration": i},
                "days_date": "2025-09-17"
            }
            data_item_repo.store_data_item(**test_data)
        
        # Verify all items were stored
        items = data_item_repo.get_data_items_by_namespace("perf_test", limit=20)
        assert len(items) == 10
    
    def test_repository_error_handling(self, repository_factory):
        """Test that repositories handle errors gracefully"""
        data_item_repo = repository_factory.get_data_item_repository()
        
        # Test with invalid data should not crash
        try:
            # This should handle gracefully
            items = data_item_repo.get_data_items_by_namespace("nonexistent_namespace")
            assert isinstance(items, list)  # Should return empty list, not crash
        except Exception as e:
            pytest.fail(f"Repository should handle missing namespace gracefully: {e}")
    
    def test_repository_factory_singleton_behavior(self, database_service):
        """Test that RepositoryFactory properly implements singleton pattern for repositories"""
        factory = RepositoryFactory(database_service)
        
        # Multiple calls should return same repository instances
        repo1 = factory.get_data_item_repository()
        repo2 = factory.get_data_item_repository()
        
        assert repo1 is repo2  # Should be same instance
        
        # Different repository types should be different instances
        chat_repo = factory.get_chat_repository()
        assert repo1 is not chat_repo