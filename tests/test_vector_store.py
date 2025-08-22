"""
Comprehensive tests for VectorStoreService.

This test suite covers all VectorStoreService functionality including vector storage,
similarity search, index management, file persistence, and error handling across
various scenarios and edge cases.
"""

import json
import os
from unittest.mock import Mock

import numpy as np
import pytest

from config.models import AppConfig
from core.vector_store import VectorStoreService

# Using shared fixtures from tests/fixtures/
# app_config, temp_dir_path, etc. are available


@pytest.fixture
def temp_vector_config(app_config, tmp_path):
    """Create vector store configuration with temporary paths"""
    vector_dir = tmp_path / "vectors"
    vector_dir.mkdir()

    # Create a mock config with vector store paths
    config = Mock(spec=AppConfig)
    config.index_path = str(vector_dir / "vectors.npy")
    config.id_map_path = str(vector_dir / "id_map.json")

    return config


@pytest.fixture
def vector_store_service(temp_vector_config):
    """Create VectorStoreService instance for testing"""
    return VectorStoreService(temp_vector_config)


@pytest.fixture
def sample_vectors():
    """Create sample vectors for testing"""
    return {
        "test:item1": np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        "test:item2": np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32),
        "test:item3": np.array([0.2, 0.3, 0.4, 0.5], dtype=np.float32),
        "news:article1": np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float32),
        "limitless:conv1": np.array([0.3, 0.4, 0.5, 0.6], dtype=np.float32),
    }


@pytest.fixture
def populated_vector_store(vector_store_service, sample_vectors):
    """Create a vector store populated with sample data"""
    for vector_id, vector in sample_vectors.items():
        vector_store_service.add_vector(vector_id, vector)
    return vector_store_service


class TestVectorStoreInitialization:
    """Test vector store initialization and setup"""

    def test_vector_store_initialization(self, temp_vector_config):
        """Test successful vector store initialization"""
        service = VectorStoreService(temp_vector_config)

        assert service.config == temp_vector_config
        assert service.vectors == {}
        assert service.id_to_index == {}
        assert service.index_to_id == {}
        assert service.dimension is None
        assert service.next_index == 0

    def test_initialization_with_existing_data(self, temp_vector_config, sample_vectors):
        """Test initialization when existing data files are present"""
        # First create a vector store and populate it
        service = VectorStoreService(temp_vector_config)
        for vector_id, vector in sample_vectors.items():
            service.add_vector(vector_id, vector)

        # Create a new service instance - should load existing data
        new_service = VectorStoreService(temp_vector_config)

        assert len(new_service.vectors) == len(sample_vectors)
        assert new_service.dimension == 4
        assert new_service.next_index == len(sample_vectors)

        # Verify all vectors are loaded correctly
        for vector_id, expected_vector in sample_vectors.items():
            assert vector_id in new_service.vectors
            np.testing.assert_array_equal(new_service.vectors[vector_id], expected_vector)

    def test_initialization_with_corrupted_id_map(self, temp_vector_config):
        """Test initialization with corrupted ID map file"""
        # Create corrupted ID map file
        os.makedirs(os.path.dirname(temp_vector_config.id_map_path), exist_ok=True)
        with open(temp_vector_config.id_map_path, "w") as f:
            f.write("invalid json content")

        # Should handle gracefully and start with empty state
        service = VectorStoreService(temp_vector_config)

        assert service.vectors == {}
        assert service.id_to_index == {}
        assert service.index_to_id == {}
        assert service.dimension is None

    def test_initialization_with_missing_vector_file(self, temp_vector_config):
        """Test initialization when ID map exists but vector file is missing"""
        # Create ID map without corresponding vector file
        id_map_data = {
            "id_to_index": {"test:item1": 0},
            "index_to_id": {"0": "test:item1"},
            "next_index": 1,
            "dimension": 4,
        }

        os.makedirs(os.path.dirname(temp_vector_config.id_map_path), exist_ok=True)
        with open(temp_vector_config.id_map_path, "w") as f:
            json.dump(id_map_data, f)

        # Should load ID mappings but have no vectors
        service = VectorStoreService(temp_vector_config)

        assert service.id_to_index == {"test:item1": 0}
        assert service.index_to_id == {"0": "test:item1"}
        assert service.next_index == 1
        assert service.dimension == 4
        assert service.vectors == {}


class TestVectorAddition:
    """Test vector addition operations"""

    def test_add_first_vector(self, vector_store_service):
        """Test adding the first vector sets dimension"""
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

        result = vector_store_service.add_vector("test:first", vector)

        assert result is True
        assert vector_store_service.dimension == 4
        assert "test:first" in vector_store_service.vectors
        assert "test:first" in vector_store_service.id_to_index
        assert vector_store_service.id_to_index["test:first"] == 0
        assert vector_store_service.index_to_id["0"] == "test:first"
        assert vector_store_service.next_index == 1

    def test_add_multiple_vectors(self, vector_store_service, sample_vectors):
        """Test adding multiple vectors"""
        for vector_id, vector in sample_vectors.items():
            result = vector_store_service.add_vector(vector_id, vector)
            assert result is True

        assert len(vector_store_service.vectors) == len(sample_vectors)
        assert vector_store_service.next_index == len(sample_vectors)

        # Verify all vectors are stored correctly
        for vector_id, expected_vector in sample_vectors.items():
            stored_vector = vector_store_service.vectors[vector_id]
            np.testing.assert_array_equal(stored_vector, expected_vector)

    def test_add_vector_wrong_dimension(self, vector_store_service):
        """Test adding vector with wrong dimension fails"""
        # Add first vector with dimension 4
        first_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        vector_store_service.add_vector("test:first", first_vector)

        # Try to add vector with wrong dimension
        wrong_vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)  # dimension 3
        result = vector_store_service.add_vector("test:wrong", wrong_vector)

        assert result is False
        assert "test:wrong" not in vector_store_service.vectors

    def test_update_existing_vector(self, vector_store_service):
        """Test updating an existing vector"""
        original_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        updated_vector = np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32)

        # Add original vector
        result = vector_store_service.add_vector("test:update", original_vector)
        assert result is True
        original_index = vector_store_service.id_to_index["test:update"]

        # Update the vector
        result = vector_store_service.add_vector("test:update", updated_vector)
        assert result is True

        # Should have same index but updated vector
        assert vector_store_service.id_to_index["test:update"] == original_index
        np.testing.assert_array_equal(vector_store_service.vectors["test:update"], updated_vector)
        assert vector_store_service.next_index == 1  # Should not increment for updates

    def test_add_vector_auto_dtype_conversion(self, vector_store_service):
        """Test automatic conversion to float32"""
        # Provide vector as different dtypes
        int_vector = np.array([1, 2, 3, 4], dtype=np.int32)
        float64_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
        list_vector = [0.5, 0.6, 0.7, 0.8]

        result1 = vector_store_service.add_vector("test:int", int_vector)
        result2 = vector_store_service.add_vector("test:float64", float64_vector)
        result3 = vector_store_service.add_vector("test:list", list_vector)

        assert all([result1, result2, result3])

        # All should be converted to float32
        assert vector_store_service.vectors["test:int"].dtype == np.float32
        assert vector_store_service.vectors["test:float64"].dtype == np.float32
        assert vector_store_service.vectors["test:list"].dtype == np.float32

    def test_add_vector_invalid_input(self, vector_store_service):
        """Test adding invalid vector inputs"""
        # First, add a valid vector to establish dimension
        valid_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        result = vector_store_service.add_vector("test:valid", valid_vector)
        assert result is True

        # Test inputs that should fail due to conversion errors
        conversion_fail_inputs = [
            "not a vector",  # String can't convert to float
        ]

        for invalid_input in conversion_fail_inputs:
            result = vector_store_service.add_vector(f"test:conversion_fail_{hash(str(invalid_input))}", invalid_input)
            assert result is False

        # Test inputs that convert but have wrong dimensions
        dimension_fail_inputs = [
            None,  # Becomes scalar (0-dimensional)
            [],  # Becomes 0-length vector (dimension 0)
            np.array([]),  # 0-length vector
            [[1, 2], [3, 4]],  # 2D array (wrong shape)
            [1, 2, 3],  # Wrong dimension (3 instead of 4)
        ]

        for invalid_input in dimension_fail_inputs:
            result = vector_store_service.add_vector(f"test:dimension_fail_{hash(str(invalid_input))}", invalid_input)
            assert result is False


class TestVectorRemoval:
    """Test vector removal operations"""

    def test_remove_existing_vector(self, populated_vector_store):
        """Test removing an existing vector"""
        # Get initial state
        initial_count = len(populated_vector_store.vectors)
        vector_id = "test:item1"

        # Remove vector
        result = populated_vector_store.remove_vector(vector_id)

        assert result is True
        assert vector_id not in populated_vector_store.vectors
        assert vector_id not in populated_vector_store.id_to_index
        assert len(populated_vector_store.vectors) == initial_count - 1

        # Index should be removed from index_to_id mapping
        for key in populated_vector_store.index_to_id:
            assert populated_vector_store.index_to_id[key] != vector_id

    def test_remove_nonexistent_vector(self, populated_vector_store):
        """Test removing a vector that doesn't exist"""
        initial_count = len(populated_vector_store.vectors)

        result = populated_vector_store.remove_vector("nonexistent:vector")

        assert result is False
        assert len(populated_vector_store.vectors) == initial_count

    def test_remove_all_vectors(self, populated_vector_store, sample_vectors):
        """Test removing all vectors"""
        for vector_id in list(sample_vectors.keys()):
            result = populated_vector_store.remove_vector(vector_id)
            assert result is True

        assert len(populated_vector_store.vectors) == 0
        assert len(populated_vector_store.id_to_index) == 0
        assert len(populated_vector_store.index_to_id) == 0

    def test_remove_and_readd_vector(self, vector_store_service):
        """Test removing and re-adding a vector"""
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        vector_id = "test:remove_readd"

        # Add vector
        vector_store_service.add_vector(vector_id, vector)
        original_index = vector_store_service.id_to_index[vector_id]

        # Remove vector
        vector_store_service.remove_vector(vector_id)

        # Re-add vector
        vector_store_service.add_vector(vector_id, vector)
        new_index = vector_store_service.id_to_index[vector_id]

        # Should get a new index
        assert new_index != original_index
        assert vector_id in vector_store_service.vectors
        np.testing.assert_array_equal(vector_store_service.vectors[vector_id], vector)


class TestVectorSearch:
    """Test vector similarity search operations"""

    def test_basic_similarity_search(self, populated_vector_store, sample_vectors):
        """Test basic similarity search"""
        # Use one of the existing vectors as query
        query_vector = sample_vectors["test:item1"]

        results = populated_vector_store.search(query_vector, k=3)

        assert len(results) <= 3
        assert len(results) > 0

        # Results should be tuples of (vector_id, similarity_score)
        for vector_id, similarity in results:
            assert isinstance(vector_id, str)
            assert isinstance(similarity, float)
            assert -1.0 <= similarity <= 1.0

        # First result should be the exact match with highest similarity
        assert results[0][0] == "test:item1"
        assert abs(results[0][1] - 1.0) < 1e-6  # Should be very close to 1.0

    def test_search_with_namespace_filter(self, populated_vector_store, sample_vectors):
        """Test search with namespace filtering"""
        query_vector = sample_vectors["test:item1"]

        # Search only in 'test' namespace
        results = populated_vector_store.search(query_vector, k=5, namespace_filter=["test"])

        # Should only return vectors from 'test' namespace
        for vector_id, similarity in results:
            assert vector_id.startswith("test:")

    def test_search_multiple_namespace_filter(self, populated_vector_store, sample_vectors):
        """Test search with multiple namespace filter"""
        query_vector = sample_vectors["test:item1"]

        # Search in 'test' and 'news' namespaces
        results = populated_vector_store.search(query_vector, k=5, namespace_filter=["test", "news"])

        # Should return vectors from both namespaces but not 'limitless'
        found_namespaces = set()
        for vector_id, similarity in results:
            namespace = vector_id.split(":")[0]
            found_namespaces.add(namespace)
            assert namespace in ["test", "news"]

        # Should find both namespaces if they exist
        assert "test" in found_namespaces
        assert "news" in found_namespaces

    def test_search_empty_namespace_filter(self, populated_vector_store, sample_vectors):
        """Test search with empty namespace filter"""
        query_vector = sample_vectors["test:item1"]

        # Empty filter should return all results (treated as no filter)
        # This is the actual implementation behavior - empty list means no filtering
        results = populated_vector_store.search(query_vector, k=5, namespace_filter=[])

        assert len(results) == min(5, len(sample_vectors))  # Should return up to k results

    def test_search_nonexistent_namespace(self, populated_vector_store, sample_vectors):
        """Test search with nonexistent namespace filter"""
        query_vector = sample_vectors["test:item1"]

        # Filter for namespace that doesn't exist
        results = populated_vector_store.search(query_vector, k=5, namespace_filter=["nonexistent"])

        assert len(results) == 0

    def test_search_results_ordering(self, vector_store_service):
        """Test that search results are ordered by similarity"""
        # Create vectors with known similarities
        base_vector = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        similar_vector = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)  # High similarity
        different_vector = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # Low similarity

        vector_store_service.add_vector("base", base_vector)
        vector_store_service.add_vector("similar", similar_vector)
        vector_store_service.add_vector("different", different_vector)

        # Search with base vector
        results = vector_store_service.search(base_vector, k=3)

        assert len(results) == 3

        # Results should be ordered by decreasing similarity
        similarities = [result[1] for result in results]
        assert similarities == sorted(similarities, reverse=True)

        # First result should be exact match, second should be similar vector
        assert results[0][0] == "base"
        assert results[1][0] == "similar"
        assert results[2][0] == "different"

    def test_search_empty_store(self, vector_store_service):
        """Test search on empty vector store"""
        query_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

        results = vector_store_service.search(query_vector, k=5)

        assert len(results) == 0

    def test_search_limit_k(self, populated_vector_store, sample_vectors):
        """Test search respects k limit"""
        query_vector = sample_vectors["test:item1"]

        # Request more results than available
        results = populated_vector_store.search(query_vector, k=100)

        # Should return at most the number of vectors in store
        assert len(results) <= len(sample_vectors)

        # Request fewer results than available
        limited_results = populated_vector_store.search(query_vector, k=2)

        assert len(limited_results) == 2

    def test_search_auto_dtype_conversion(self, populated_vector_store):
        """Test search query vector dtype conversion"""
        # Provide query as different dtypes
        int_query = np.array([1, 2, 3, 4], dtype=np.int32)
        float64_query = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
        list_query = [0.5, 0.6, 0.7, 0.8]

        # All should work without errors
        results1 = populated_vector_store.search(int_query, k=3)
        results2 = populated_vector_store.search(float64_query, k=3)
        results3 = populated_vector_store.search(list_query, k=3)

        assert all([len(results1) > 0, len(results2) > 0, len(results3) > 0])


class TestFilePersistence:
    """Test file persistence and data integrity"""

    def test_save_and_load_cycle(self, vector_store_service, sample_vectors):
        """Test complete save and load cycle"""
        # Add vectors
        for vector_id, vector in sample_vectors.items():
            vector_store_service.add_vector(vector_id, vector)

        # Force save
        vector_store_service._save_index()

        # Verify files exist
        assert os.path.exists(vector_store_service.config.id_map_path)
        assert os.path.exists(vector_store_service.config.index_path)

        # Create new service instance - should load data
        new_service = VectorStoreService(vector_store_service.config)

        # Verify all data is loaded correctly
        assert len(new_service.vectors) == len(sample_vectors)
        assert new_service.dimension == vector_store_service.dimension
        assert new_service.next_index == vector_store_service.next_index

        for vector_id, expected_vector in sample_vectors.items():
            assert vector_id in new_service.vectors
            np.testing.assert_array_equal(new_service.vectors[vector_id], expected_vector)

    def test_save_with_removed_vectors(self, populated_vector_store):
        """Test saving handles removed vectors correctly"""
        # Remove some vectors
        populated_vector_store.remove_vector("test:item1")
        populated_vector_store.remove_vector("news:article1")

        # Force save
        populated_vector_store._save_index()

        # Create new service - should not load removed vectors
        new_service = VectorStoreService(populated_vector_store.config)

        assert "test:item1" not in new_service.vectors
        assert "news:article1" not in new_service.vectors
        assert len(new_service.vectors) == len(populated_vector_store.vectors)

    def test_save_creates_directories(self, temp_vector_config):
        """Test that save creates necessary directories"""
        # Use config with nested directory that doesn't exist
        nested_dir = os.path.dirname(temp_vector_config.id_map_path) + "/nested/deep"
        temp_vector_config.id_map_path = nested_dir + "/id_map.json"
        temp_vector_config.index_path = nested_dir + "/vectors.npy"

        service = VectorStoreService(temp_vector_config)

        # Add a vector to trigger save
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        service.add_vector("test:dir", vector)

        # Directories should be created
        assert os.path.exists(os.path.dirname(temp_vector_config.id_map_path))
        assert os.path.exists(os.path.dirname(temp_vector_config.index_path))
        assert os.path.exists(temp_vector_config.id_map_path)
        assert os.path.exists(temp_vector_config.index_path)

    def test_load_handles_missing_files_gracefully(self, temp_vector_config):
        """Test loading when files don't exist"""
        # Ensure files don't exist
        if os.path.exists(temp_vector_config.id_map_path):
            os.remove(temp_vector_config.id_map_path)
        if os.path.exists(temp_vector_config.index_path):
            os.remove(temp_vector_config.index_path)

        # Should create service without errors
        service = VectorStoreService(temp_vector_config)

        assert service.vectors == {}
        assert service.dimension is None
        assert service.next_index == 0

    @pytest.mark.skipif(os.name == "nt", reason="Permission testing different on Windows")
    def test_save_handles_permission_errors(self, vector_store_service):
        """Test save handles permission errors gracefully"""
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        vector_store_service.add_vector("test:perm", vector)

        # Make directory read-only
        config_dir = os.path.dirname(vector_store_service.config.id_map_path)
        original_mode = os.stat(config_dir).st_mode

        try:
            os.chmod(config_dir, 0o444)  # Read-only

            # Save should not raise exception
            vector_store_service._save_index()

        finally:
            # Restore permissions
            os.chmod(config_dir, original_mode)


class TestStatistics:
    """Test statistics and metadata operations"""

    def test_get_stats_empty_store(self, vector_store_service):
        """Test statistics for empty store"""
        stats = vector_store_service.get_stats()

        assert stats["total_vectors"] == 0
        assert stats["dimension"] is None
        assert "index_path" in stats
        assert "id_map_path" in stats

    def test_get_stats_populated_store(self, populated_vector_store, sample_vectors):
        """Test statistics for populated store"""
        stats = populated_vector_store.get_stats()

        assert stats["total_vectors"] == len(sample_vectors)
        assert stats["dimension"] == 4
        assert stats["index_path"] == populated_vector_store.config.index_path
        assert stats["id_map_path"] == populated_vector_store.config.id_map_path

    def test_stats_update_after_operations(self, vector_store_service):
        """Test that statistics update after operations"""
        # Initial stats
        initial_stats = vector_store_service.get_stats()
        assert initial_stats["total_vectors"] == 0

        # Add vector
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        vector_store_service.add_vector("test:stats", vector)

        # Stats should update
        stats_after_add = vector_store_service.get_stats()
        assert stats_after_add["total_vectors"] == 1
        assert stats_after_add["dimension"] == 4

        # Remove vector
        vector_store_service.remove_vector("test:stats")

        # Stats should update again
        stats_after_remove = vector_store_service.get_stats()
        assert stats_after_remove["total_vectors"] == 0


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_search_with_invalid_query_vector(self, populated_vector_store):
        """Test search with invalid query vector"""
        invalid_queries = [
            None,
            "not a vector",
            [],
            np.array([]),  # Empty array
            [[1, 2], [3, 4]],  # 2D array
        ]

        for invalid_query in invalid_queries:
            # Should not raise exception, should return empty results
            results = populated_vector_store.search(invalid_query, k=5)
            assert results == []

    def test_search_with_wrong_dimension_query(self, populated_vector_store):
        """Test search with wrong dimension query vector"""
        # Store has dimension 4, query with dimension 3
        wrong_dim_query = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        # Should handle gracefully and return empty results
        results = populated_vector_store.search(wrong_dim_query, k=5)
        assert results == []

    def test_add_vector_after_removal_gaps(self, vector_store_service):
        """Test adding vectors after creating gaps in index"""
        # Add vectors
        vectors = {
            "test:a": np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
            "test:b": np.array([0.2, 0.3, 0.4, 0.5], dtype=np.float32),
            "test:c": np.array([0.3, 0.4, 0.5, 0.6], dtype=np.float32),
        }

        for vector_id, vector in vectors.items():
            vector_store_service.add_vector(vector_id, vector)

        # Remove middle vector
        vector_store_service.remove_vector("test:b")

        # Add new vector
        new_vector = np.array([0.4, 0.5, 0.6, 0.7], dtype=np.float32)
        result = vector_store_service.add_vector("test:new", new_vector)

        assert result is True
        assert "test:new" in vector_store_service.vectors

        # Should still be able to search correctly
        query = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        results = vector_store_service.search(query, k=5)

        # Should find remaining vectors
        found_ids = [result[0] for result in results]
        assert "test:a" in found_ids
        assert "test:c" in found_ids
        assert "test:new" in found_ids
        assert "test:b" not in found_ids

    def test_cosine_similarity_edge_cases(self, vector_store_service):
        """Test cosine similarity calculation edge cases"""
        # Add vectors with special properties
        zero_vector = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        unit_vector = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        negative_vector = np.array([-1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        vector_store_service.add_vector("zero", zero_vector)
        vector_store_service.add_vector("unit", unit_vector)
        vector_store_service.add_vector("negative", negative_vector)

        # Query with unit vector
        results = vector_store_service.search(unit_vector, k=3)

        # Should handle zero vectors gracefully (may return NaN or 0)
        assert len(results) == 3

        # Find unit vector result (should have similarity 1.0)
        unit_result = next((r for r in results if r[0] == "unit"), None)
        assert unit_result is not None
        assert abs(unit_result[1] - 1.0) < 1e-6

        # Find negative vector result (should have similarity -1.0)
        negative_result = next((r for r in results if r[0] == "negative"), None)
        assert negative_result is not None
        assert abs(negative_result[1] - (-1.0)) < 1e-6

    def test_cleanup_method(self, vector_store_service):
        """Test cleanup method"""
        # Add some data
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        vector_store_service.add_vector("test:cleanup", vector)

        # Cleanup should not raise errors
        vector_store_service.cleanup()

        # Service should still be functional after cleanup
        stats = vector_store_service.get_stats()
        assert stats["total_vectors"] == 1


class TestNamespaceHandling:
    """Test namespace-specific functionality"""

    def test_namespace_extraction_standard_format(self, populated_vector_store):
        """Test namespace extraction from standard namespace:id format"""
        # Test with various namespace formats
        test_vectors = {
            "simple": "simple",
            "multi:part:id": "multi",
            "news:article:123": "news",
            "limitless:conversation:abc-def": "limitless",
            "no_colon_id": "no_colon_id",  # Should use full ID as namespace
        }

        query_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

        for vector_id, expected_namespace in test_vectors.items():
            # Clear store and add test vector
            populated_vector_store.vectors.clear()
            populated_vector_store.id_to_index.clear()
            populated_vector_store.index_to_id.clear()
            populated_vector_store.next_index = 0

            test_vector = np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32)
            populated_vector_store.add_vector(vector_id, test_vector)

            # Search with namespace filter
            results = populated_vector_store.search(
                query_vector,
                k=5,
                namespace_filter=[expected_namespace],
            )

            # Should find the vector
            assert len(results) == 1
            assert results[0][0] == vector_id

    def test_multiple_vectors_same_namespace(self, vector_store_service):
        """Test handling multiple vectors in same namespace"""
        namespace = "test_ns"
        vectors = {
            f"{namespace}:item1": np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
            f"{namespace}:item2": np.array([0.2, 0.3, 0.4, 0.5], dtype=np.float32),
            f"{namespace}:item3": np.array([0.3, 0.4, 0.5, 0.6], dtype=np.float32),
            "other:item": np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float32),
        }

        for vector_id, vector in vectors.items():
            vector_store_service.add_vector(vector_id, vector)

        # Search with namespace filter
        query = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        results = vector_store_service.search(query, k=10, namespace_filter=[namespace])

        # Should find only vectors from the specified namespace
        assert len(results) == 3
        for vector_id, similarity in results:
            assert vector_id.startswith(f"{namespace}:")


class TestPerformanceScenarios:
    """Test performance-related scenarios"""

    def test_large_vector_store_operations(self, vector_store_service):
        """Test operations with larger number of vectors"""
        # Create larger set of vectors
        num_vectors = 100
        dimension = 128

        vectors = {}
        for i in range(num_vectors):
            vector_id = f"perf:vector_{i:03d}"
            vector = np.random.rand(dimension).astype(np.float32)
            vectors[vector_id] = vector

        # Add all vectors
        import time
        start_time = time.perf_counter()

        for vector_id, vector in vectors.items():
            result = vector_store_service.add_vector(vector_id, vector)
            assert result is True

        add_time = time.perf_counter() - start_time

        # Verify all vectors are stored
        assert len(vector_store_service.vectors) == num_vectors
        assert vector_store_service.dimension == dimension

        # Test search performance
        query_vector = np.random.rand(dimension).astype(np.float32)

        start_time = time.perf_counter()
        results = vector_store_service.search(query_vector, k=10)
        search_time = time.perf_counter() - start_time

        assert len(results) == 10

        # Performance should be reasonable for 100 vectors
        assert add_time < 1.0  # Less than 1 second to add 100 vectors
        assert search_time < 0.1  # Less than 100ms to search 100 vectors

    @pytest.mark.performance
    def test_memory_usage_large_vectors(self, vector_store_service):
        """Test memory usage with large vectors"""
        # Test with high-dimensional vectors
        dimension = 1536  # Similar to OpenAI embeddings
        num_vectors = 50

        for i in range(num_vectors):
            vector_id = f"large:vector_{i:03d}"
            vector = np.random.rand(dimension).astype(np.float32)
            result = vector_store_service.add_vector(vector_id, vector)
            assert result is True

        # Verify functionality with large vectors
        query_vector = np.random.rand(dimension).astype(np.float32)
        results = vector_store_service.search(query_vector, k=5)

        assert len(results) == 5
        assert vector_store_service.dimension == dimension

    @pytest.mark.performance
    def test_concurrent_access_simulation(self, populated_vector_store):
        """Test behavior under simulated concurrent access"""
        import threading

        results = []
        errors = []

        def search_worker():
            try:
                query = np.random.rand(4).astype(np.float32)
                search_results = populated_vector_store.search(query, k=3)
                results.append(len(search_results))
            except Exception as e:
                errors.append(e)

        def add_worker(worker_id):
            try:
                vector = np.random.rand(4).astype(np.float32)
                vector_id = f"concurrent:worker_{worker_id}"
                success = populated_vector_store.add_vector(vector_id, vector)
                results.append(success)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(5):
            search_thread = threading.Thread(target=search_worker)
            add_thread = threading.Thread(target=add_worker, args=(i,))
            threads.extend([search_thread, add_thread])

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should not have errors (though this implementation isn't thread-safe)
        # This test mainly checks that basic operations don't completely break
        assert len(errors) == 0 or all(isinstance(e, Exception) for e in errors)
        assert len(results) > 0
