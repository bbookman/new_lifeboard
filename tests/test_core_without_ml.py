"""
Unit tests for core components without ML dependencies
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.ids import NamespacedIDManager


class TestNamespacedIDManager:
    """Test namespaced ID management"""
    
    def test_create_id_with_source_id(self):
        """Test creating ID with provided source_id"""
        namespace = "test"
        source_id = "123"
        namespaced_id = NamespacedIDManager.create_id(namespace, source_id)
        assert namespaced_id == "test:123"
    
    def test_create_id_without_source_id(self):
        """Test creating ID with generated source_id"""
        namespace = "test"
        namespaced_id = NamespacedIDManager.create_id(namespace)
        assert namespaced_id.startswith("test:")
        assert len(namespaced_id.split(":")) == 2
    
    def test_parse_id(self):
        """Test parsing namespaced ID"""
        namespaced_id = "test:123"
        namespace, source_id = NamespacedIDManager.parse_id(namespaced_id)
        assert namespace == "test"
        assert source_id == "123"
    
    def test_parse_invalid_id(self):
        """Test parsing invalid ID raises error"""
        with pytest.raises(ValueError):
            NamespacedIDManager.parse_id("invalid")
    
    def test_get_namespace(self):
        """Test extracting namespace"""
        namespaced_id = "test:123"
        namespace = NamespacedIDManager.get_namespace(namespaced_id)
        assert namespace == "test"
    
    def test_validate_namespace(self):
        """Test namespace validation"""
        assert NamespacedIDManager.validate_namespace("valid")
        assert not NamespacedIDManager.validate_namespace("invalid:colon")
        assert not NamespacedIDManager.validate_namespace("")
    
    def test_normalize_namespace(self):
        """Test namespace normalization"""
        assert NamespacedIDManager.normalize_namespace("Test Name") == "test_name"
        assert NamespacedIDManager.normalize_namespace("test:colon") == "test_colon"


class TestDatabaseService:
    """Test database operations"""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, db_service: DatabaseService):
        """Test database is properly initialized"""
        stats = db_service.get_database_stats()
        assert stats['total_items'] == 0
        assert 'database_path' in stats
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_item(self, db_service: DatabaseService):
        """Test storing and retrieving data items"""
        namespaced_id = "test:item1"
        content = "Test content"
        metadata = {"key": "value"}
        
        # Store item
        db_service.store_data_item(
            id=namespaced_id,
            namespace="test",
            source_id="item1",
            content=content,
            metadata=metadata
        )
        
        # Retrieve item
        items = db_service.get_data_items_by_ids([namespaced_id])
        assert len(items) == 1
        
        item = items[0]
        assert item['id'] == namespaced_id
        assert item['content'] == content
        assert item['metadata'] == metadata
    
    @pytest.mark.asyncio
    async def test_embedding_status_tracking(self, db_service: DatabaseService):
        """Test embedding status tracking"""
        namespaced_id = "test:item1"
        
        # Store item
        db_service.store_data_item(
            id=namespaced_id,
            namespace="test", 
            source_id="item1",
            content="Test content"
        )
        
        # Check initial status
        pending_items = db_service.get_pending_embeddings()
        assert len(pending_items) == 1
        assert pending_items[0]['id'] == namespaced_id
        
        # Update status
        db_service.update_embedding_status(namespaced_id, 'completed')
        
        # Check no longer pending
        pending_items = db_service.get_pending_embeddings()
        assert len(pending_items) == 0
    
    @pytest.mark.asyncio
    async def test_settings_management(self, db_service: DatabaseService):
        """Test database-backed settings"""
        key = "test_setting"
        value = {"config": "value"}
        
        # Set setting
        db_service.set_setting(key, value)
        
        # Get setting
        retrieved = db_service.get_setting(key)
        assert retrieved == value
        
        # Test default value
        default = db_service.get_setting("nonexistent", "default")
        assert default == "default"


class TestVectorStore:
    """Test vector store operations"""
    
    @pytest.mark.asyncio
    async def test_vector_store_initialization(self, vector_store: VectorStoreService):
        """Test vector store initialization"""
        stats = vector_store.get_stats()
        assert stats['total_vectors'] == 0
        assert stats['dimension'] is None  # No vectors added yet
    
    @pytest.mark.asyncio
    async def test_add_and_search_vectors(self, vector_store: VectorStoreService):
        """Test adding vectors and searching"""
        # Create test vectors
        namespaced_id1 = "test:item1"
        namespaced_id2 = "test:item2"
        vector1 = np.random.rand(384).astype(np.float32)
        vector2 = np.random.rand(384).astype(np.float32)
        
        # Add vectors
        success1 = vector_store.add_vector(namespaced_id1, vector1)
        success2 = vector_store.add_vector(namespaced_id2, vector2)
        assert success1 and success2
        
        # Check stats
        stats = vector_store.get_stats()
        assert stats['total_vectors'] == 2
        assert stats['dimension'] == 384
        
        # Search with first vector (should return itself first)
        results = vector_store.search(vector1, k=2)
        assert len(results) == 2
        assert results[0][0] == namespaced_id1  # Best match is itself
        assert results[0][1] > 0.9  # High similarity score
    
    @pytest.mark.asyncio
    async def test_namespace_filtering(self, vector_store: VectorStoreService):
        """Test namespace-based filtering"""
        # Add vectors from different namespaces
        vector1 = np.random.rand(384).astype(np.float32)
        vector2 = np.random.rand(384).astype(np.float32)
        
        vector_store.add_vector("ns1:item1", vector1)
        vector_store.add_vector("ns2:item1", vector2)
        
        # Search with namespace filter
        results = vector_store.search(vector1, k=5, namespace_filter=["ns1"])
        assert len(results) == 1
        assert results[0][0] == "ns1:item1"
        
        # Search without filter
        results = vector_store.search(vector1, k=5)
        assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_vector_removal(self, vector_store: VectorStoreService):
        """Test removing vectors"""
        namespaced_id = "test:item1"
        vector = np.random.rand(384).astype(np.float32)
        
        # Add vector
        vector_store.add_vector(namespaced_id, vector)
        assert vector_store.get_stats()['total_vectors'] == 1
        
        # Remove vector
        success = vector_store.remove_vector(namespaced_id)
        assert success
        assert vector_store.get_stats()['total_vectors'] == 0


class TestMockEmbeddingService:
    """Test embedding service with mocks"""
    
    @pytest.mark.asyncio
    async def test_mock_embedding_generation(self):
        """Test mock embedding generation"""
        # Create mock embedding service
        mock_service = AsyncMock()
        
        # Configure mock
        test_embedding = np.random.rand(384).astype(np.float32)
        mock_service.embed_text.return_value = test_embedding
        
        # Test
        result = await mock_service.embed_text("test text")
        assert result.shape == (384,)
        mock_service.embed_text.assert_called_once_with("test text")
    
    @pytest.mark.asyncio 
    async def test_mock_batch_embedding(self):
        """Test mock batch embedding"""
        mock_service = AsyncMock()
        
        # Configure mock
        test_embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
        mock_service.embed_texts.return_value = test_embeddings
        
        # Test
        texts = ["text1", "text2", "text3"]
        results = await mock_service.embed_texts(texts)
        
        assert len(results) == 3
        assert all(emb.shape == (384,) for emb in results)
        mock_service.embed_texts.assert_called_once_with(texts)
    
    @pytest.mark.asyncio
    async def test_mock_similarity_computation(self):
        """Test mock similarity computation"""
        mock_service = AsyncMock()
        mock_service.compute_similarity.return_value = 0.75
        
        # Test
        similarity = await mock_service.compute_similarity("text1", "text2")
        assert similarity == 0.75
        mock_service.compute_similarity.assert_called_once_with("text1", "text2")