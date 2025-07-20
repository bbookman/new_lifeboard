"""
Test configuration and fixtures for Lifeboard tests
"""

import pytest
import pytest_asyncio
import tempfile
import os
import asyncio
from typing import AsyncGenerator, Generator

from config.factory import create_test_config
from config.models import AppConfig, LimitlessConfig, LLMConfig
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from sources.registry import SourceRegistry
from services.namespace_prediction import MockNamespacePredictionService
from services.search import SearchService
from services.ingestion import IngestionService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_config(temp_dir: str) -> AppConfig:
    """Create test configuration with temporary files"""
    return create_test_config(temp_dir)


@pytest_asyncio.fixture
async def db_service(test_config: AppConfig) -> AsyncGenerator[DatabaseService, None]:
    """Create test database service"""
    db = DatabaseService(test_config.database.path)
    yield db
    # Cleanup
    if os.path.exists(test_config.database.path):
        os.remove(test_config.database.path)


@pytest_asyncio.fixture
async def vector_store(test_config: AppConfig) -> AsyncGenerator[VectorStoreService, None]:
    """Create test vector store"""
    vector_store = VectorStoreService(test_config.vector_store)
    yield vector_store
    # Cleanup
    vector_store.cleanup()
    for path in [test_config.vector_store.index_path, test_config.vector_store.id_map_path]:
        if os.path.exists(path):
            os.remove(path)


@pytest_asyncio.fixture
async def embedding_service(test_config: AppConfig) -> AsyncGenerator[EmbeddingService, None]:
    """Create test embedding service"""
    try:
        embeddings = EmbeddingService(test_config.embeddings)
        await embeddings.warmup()
        yield embeddings
        embeddings.cleanup()
    except Exception as e:
        # If real embedding service fails, create a mock one for testing
        from unittest.mock import AsyncMock
        import numpy as np
        
        mock_service = AsyncMock()
        mock_service.embed_text = AsyncMock(return_value=np.random.rand(384).astype(np.float32))
        mock_service.embed_texts = AsyncMock(return_value=[np.random.rand(384).astype(np.float32) for _ in range(3)])
        mock_service.compute_similarity = AsyncMock(return_value=0.7)
        mock_service.get_model_info = lambda: {"status": "mock", "dimension": 384}
        mock_service.cleanup = lambda: None
        
        yield mock_service


@pytest.fixture
def source_registry() -> SourceRegistry:
    """Create test source registry"""
    return SourceRegistry()


@pytest_asyncio.fixture
async def prediction_service(source_registry: SourceRegistry) -> MockNamespacePredictionService:
    """Create mock prediction service for testing"""
    return MockNamespacePredictionService(source_registry.get_namespaces())


@pytest_asyncio.fixture
async def search_service(
    db_service: DatabaseService,
    vector_store: VectorStoreService, 
    embedding_service: EmbeddingService,
    prediction_service: MockNamespacePredictionService,
    test_config: AppConfig
) -> SearchService:
    """Create test search service"""
    return SearchService(
        db_service,
        vector_store,
        embedding_service,
        prediction_service,
        test_config.search
    )


@pytest_asyncio.fixture
async def ingestion_service(
    db_service: DatabaseService,
    vector_store: VectorStoreService,
    embedding_service: EmbeddingService,
    source_registry: SourceRegistry,
    test_config: AppConfig
) -> IngestionService:
    """Create test ingestion service"""
    return IngestionService(
        db_service,
        vector_store,
        embedding_service,
        source_registry,
        test_config.scheduler
    )


@pytest.fixture
def sample_data():
    """Sample data for testing"""
    return [
        {
            "namespace": "test",
            "source_id": "item1",
            "content": "This is a test document about machine learning and artificial intelligence.",
            "metadata": {"topic": "AI", "date": "2024-01-01"}
        },
        {
            "namespace": "test", 
            "source_id": "item2",
            "content": "Python programming tutorial covering data structures and algorithms.",
            "metadata": {"topic": "Programming", "date": "2024-01-02"}
        },
        {
            "namespace": "docs",
            "source_id": "doc1", 
            "content": "Meeting notes from the project planning session on software architecture.",
            "metadata": {"type": "meeting", "date": "2024-01-03"}
        }
    ]


@pytest.fixture
def limitless_config():
    """Test Limitless API configuration"""
    return LimitlessConfig(
        api_key="test_limitless_key",
        base_url="https://api.limitless.ai/v1",
        timezone="UTC"
    )


@pytest.fixture
def llm_config():
    """Test LLM configuration"""
    return LLMConfig(
        provider="openai",
        model="gpt-3.5-turbo",
        api_key="test_openai_key"
    )


@pytest.fixture
def skip_real_api():
    """Skip tests that require real API keys"""
    return pytest.mark.skipif(
        not os.getenv("ENABLE_REAL_API_TESTS"),
        reason="Real API tests disabled (set ENABLE_REAL_API_TESTS=1 to enable)"
    )


@pytest.fixture
def real_limitless_api_key():
    """Get real Limitless API key from environment"""
    api_key = os.getenv("LIMITLESS_API_KEY")
    if not api_key:
        pytest.skip("LIMITLESS_API_KEY not set")
    return api_key


@pytest.fixture
def real_openai_api_key():
    """Get real OpenAI API key from environment"""
    api_key = os.getenv("OPENAI_API_KEY") 
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return api_key


class TestHelpers:
    """Helper functions for tests"""
    
    @staticmethod
    async def populate_test_data(ingestion_service: IngestionService, sample_data: list):
        """Populate test database with sample data"""
        for item in sample_data:
            await ingestion_service.manual_ingest_item(
                namespace=item["namespace"],
                content=item["content"],
                source_id=item["source_id"],
                metadata=item["metadata"]
            )
        
        # Process embeddings
        await ingestion_service.process_pending_embeddings()
    
    @staticmethod
    def assert_search_result_valid(result):
        """Assert that a search result has required fields"""
        assert hasattr(result, 'namespaced_id')
        assert hasattr(result, 'content')
        assert hasattr(result, 'similarity_score')
        assert hasattr(result, 'namespace')
        assert 0 <= result.similarity_score <= 1


@pytest.fixture
def test_helpers():
    """Test helper functions"""
    return TestHelpers