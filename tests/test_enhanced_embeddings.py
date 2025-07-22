"""Test cases for enhanced embedding functionality."""

import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from core.enhanced_embeddings import MultiModelEmbeddingService, EmbeddingQualityValidator
from core.config import Config


class TestEmbeddingQualityValidator:
    """Test cases for embedding quality validation."""
    
    def test_validate_empty_embedding(self):
        """Test validation of empty embeddings."""
        result = EmbeddingQualityValidator.validate_embedding(np.array([]))
        assert not result['is_valid']
        assert result['reason'] == 'Empty embedding'
        
        result = EmbeddingQualityValidator.validate_embedding(None)
        assert not result['is_valid']
        assert result['reason'] == 'Empty embedding'
    
    def test_validate_nan_embedding(self):
        """Test validation of embeddings with NaN values."""
        embedding_with_nan = np.array([1.0, 2.0, np.nan, 4.0])
        result = EmbeddingQualityValidator.validate_embedding(embedding_with_nan)
        assert not result['is_valid']
        assert 'NaN' in result['reason']
    
    def test_validate_inf_embedding(self):
        """Test validation of embeddings with infinity values."""
        embedding_with_inf = np.array([1.0, 2.0, np.inf, 4.0])
        result = EmbeddingQualityValidator.validate_embedding(embedding_with_inf)
        assert not result['is_valid']
        assert 'infinity' in result['reason']
    
    def test_validate_good_embedding(self):
        """Test validation of a good quality embedding."""
        good_embedding = np.random.randn(384)
        result = EmbeddingQualityValidator.validate_embedding(good_embedding)
        assert result['is_valid']
        assert 'quality_score' in result
        assert result['quality_score'] > 0
        assert result['dimension'] == 384
    
    def test_validate_sparse_embedding(self):
        """Test validation of sparse embeddings with many zeros."""
        sparse_embedding = np.zeros(100)
        sparse_embedding[:10] = np.random.randn(10)  # Only 10% non-zero
        result = EmbeddingQualityValidator.validate_embedding(sparse_embedding)
        assert result['is_valid']
        assert result['quality_score'] < 1.0  # Should be penalized
        assert result['zero_ratio'] > 0.8
    
    def test_validate_no_variance_embedding(self):
        """Test validation of embeddings with no variance."""
        no_variance_embedding = np.ones(100) * 5.0
        result = EmbeddingQualityValidator.validate_embedding(no_variance_embedding)
        assert result['is_valid']
        assert result['quality_score'] < 1.0  # Should be penalized
        assert result['std'] < 1e-6
    
    def test_similarity_threshold_validation(self):
        """Test similarity threshold validation."""
        assert EmbeddingQualityValidator.validate_similarity_threshold(0.8, 0.5)
        assert not EmbeddingQualityValidator.validate_similarity_threshold(0.3, 0.5)
        assert EmbeddingQualityValidator.validate_similarity_threshold(0.15, 0.1)


class TestMultiModelEmbeddingService:
    """Test cases for multi-model embedding service."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test cache."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=Config)
        config.get = Mock(return_value='all-MiniLM-L6-v2')
        return config
    
    @pytest.fixture
    def embedding_service(self, temp_dir, mock_config):
        """Create embedding service with temp directory."""
        with patch('core.enhanced_embeddings.Config', return_value=mock_config):
            service = MultiModelEmbeddingService(cache_embeddings=True)
            service.cache_dir = Path(temp_dir)
            return service
    
    def test_supported_models(self, embedding_service):
        """Test getting supported models."""
        models = embedding_service.get_supported_models()
        assert isinstance(models, dict)
        assert 'all-MiniLM-L6-v2' in models
        assert 'all-mpnet-base-v2' in models
        assert 'BAAI/bge-base-en-v1.5' in models
        
        # Check model info structure
        for model_name, info in models.items():
            assert 'dimension' in info
            assert 'description' in info
            assert 'pros' in info
            assert 'cons' in info
    
    def test_switch_model_valid(self, embedding_service):
        """Test switching to valid model."""
        result = embedding_service.switch_model('all-mpnet-base-v2')
        assert result is True
        assert embedding_service.model_name == 'all-mpnet-base-v2'
    
    def test_switch_model_invalid(self, embedding_service):
        """Test switching to invalid model."""
        result = embedding_service.switch_model('invalid-model')
        assert result is False
        assert embedding_service.model_name != 'invalid-model'
    
    def test_get_embedding_dimension(self, embedding_service):
        """Test getting embedding dimensions."""
        dim = embedding_service.get_embedding_dimension('all-MiniLM-L6-v2')
        assert dim == 384
        
        dim = embedding_service.get_embedding_dimension('all-mpnet-base-v2')
        assert dim == 768
        
        # Test default model
        dim = embedding_service.get_embedding_dimension()
        assert dim == 384  # Default model dimension
    
    def test_get_model_info(self, embedding_service):
        """Test getting model information."""
        info = embedding_service.get_model_info('all-MiniLM-L6-v2')
        assert info['name'] == 'all-MiniLM-L6-v2'
        assert info['dimension'] == 384
        assert 'description' in info
    
    def test_cache_key_generation(self, embedding_service):
        """Test cache key generation."""
        key1 = embedding_service._get_cache_key("test text", "model1")
        key2 = embedding_service._get_cache_key("test text", "model2")
        key3 = embedding_service._get_cache_key("different text", "model1")
        
        assert key1 != key2  # Different models should produce different keys
        assert key1 != key3  # Different texts should produce different keys
        assert len(key1) == 64  # SHA256 hex digest length
    
    def test_preprocess_text(self, embedding_service):
        """Test text preprocessing."""
        # Test empty text
        result = embedding_service._preprocess_text("")
        assert result == ""
        
        result = embedding_service._preprocess_text("   ")
        assert result == ""
        
        # Test normal text
        result = embedding_service._preprocess_text("  Hello world  ")
        assert result == "Hello world"
        
        # Test long text truncation
        long_text = "a" * 2000  # Very long text
        result = embedding_service._preprocess_text(long_text)
        assert len(result) < len(long_text)
    
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_encode_single_text(self, mock_st_class, embedding_service):
        """Test encoding single text."""
        # Mock the sentence transformer
        mock_model = Mock()
        mock_model.encode.return_value = [np.random.randn(384)]
        mock_st_class.return_value = mock_model
        
        text = "Hello world"
        embeddings, metrics = embedding_service.encode(text)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (384,)
        assert isinstance(metrics, dict)
        assert metrics['is_valid']
    
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_encode_multiple_texts(self, mock_st_class, embedding_service):
        """Test encoding multiple texts."""
        # Mock the sentence transformer
        mock_model = Mock()
        mock_model.encode.return_value = [np.random.randn(384) for _ in range(3)]
        mock_st_class.return_value = mock_model
        
        texts = ["Hello", "world", "test"]
        embeddings, metrics = embedding_service.encode(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 384)
        assert isinstance(metrics, list)
        assert len(metrics) == 3
        assert all(m['is_valid'] for m in metrics)
    
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_encode_with_cache(self, mock_st_class, embedding_service):
        """Test encoding with caching."""
        # Mock the sentence transformer
        mock_model = Mock()
        test_embedding = np.random.randn(384)
        mock_model.encode.return_value = [test_embedding]
        mock_st_class.return_value = mock_model
        
        text = "Test caching"
        
        # First encode - should generate embedding
        embeddings1, metrics1 = embedding_service.encode(text)
        assert mock_model.encode.call_count == 1
        assert not metrics1.get('cached', False)
        
        # Second encode - should use cache
        embeddings2, metrics2 = embedding_service.encode(text)
        assert mock_model.encode.call_count == 1  # Should not call again
        assert metrics2.get('cached', False)
        
        # Embeddings should be similar
        np.testing.assert_array_almost_equal(embeddings1, embeddings2)
    
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_encode_empty_text(self, mock_st_class, embedding_service):
        """Test encoding empty text."""
        mock_model = Mock()
        mock_st_class.return_value = mock_model
        
        embeddings, metrics = embedding_service.encode("")
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (384,)  # Default dimension
        assert not metrics['is_valid']
        assert metrics['reason'] == 'Empty text'
        assert mock_model.encode.call_count == 0  # Should not call model for empty text
    
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_encode_with_fallback(self, mock_st_class, embedding_service):
        """Test encoding with fallback models."""
        # Mock first model to fail, second to succeed
        def side_effect(model_name):
            if model_name == 'failing-model':
                raise Exception("Model failed")
            else:
                mock_model = Mock()
                mock_model.encode.return_value = [np.random.randn(384)]
                return mock_model
        
        mock_st_class.side_effect = side_effect
        
        text = "Test fallback"
        embeddings, metrics = embedding_service.encode_with_fallback(
            text, 
            primary_model='failing-model',
            fallback_models=['all-MiniLM-L6-v2']
        )
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (384,)
        assert metrics['is_valid']
    
    def test_compute_similarities(self, embedding_service):
        """Test computing similarities between embeddings."""
        # Create test embeddings
        embeddings_a = np.random.randn(3, 384)
        embeddings_b = np.random.randn(2, 384)
        
        # Test pairwise similarities within single set
        similarities = embedding_service.compute_similarities(embeddings_a)
        assert similarities.shape == (3, 3)
        
        # Test similarities between two sets
        similarities = embedding_service.compute_similarities(embeddings_a, embeddings_b)
        assert similarities.shape == (3, 2)
        
        # Test with threshold
        similarities = embedding_service.compute_similarities(
            embeddings_a, embeddings_b, threshold=0.5
        )
        assert np.all((similarities >= 0.5) | (similarities == 0.0))
    
    def test_filter_by_similarity(self, embedding_service):
        """Test filtering candidates by similarity threshold."""
        query_embedding = np.random.randn(384)
        candidate_embeddings = np.random.randn(5, 384)
        
        # Make one embedding very similar to query
        candidate_embeddings[2] = query_embedding + 0.01 * np.random.randn(384)
        
        filtered, similarities = embedding_service.filter_by_similarity(
            query_embedding, candidate_embeddings, threshold=0.8
        )
        
        assert filtered.shape[0] <= candidate_embeddings.shape[0]
        assert len(similarities) == filtered.shape[0]
        assert np.all(similarities >= 0.8)
    
    def test_performance_metrics(self, embedding_service):
        """Test performance metrics tracking."""
        initial_metrics = embedding_service.get_performance_metrics()
        assert 'total_embeddings' in initial_metrics
        assert 'cache_hits' in initial_metrics
        assert 'validation_failures' in initial_metrics
        assert 'avg_time_per_embedding' in initial_metrics
        assert 'cache_hit_rate' in initial_metrics
        assert 'failure_rate' in initial_metrics
    
    def test_clear_cache(self, embedding_service):
        """Test clearing cache."""
        # Create some fake cache files
        cache_file1 = embedding_service.cache_dir / "test1.npy"
        cache_file2 = embedding_service.cache_dir / "test2.npy"
        
        np.save(cache_file1, np.random.randn(384))
        np.save(cache_file2, np.random.randn(384))
        
        assert cache_file1.exists()
        assert cache_file2.exists()
        
        removed_count = embedding_service.clear_cache()
        assert removed_count == 2
        assert not cache_file1.exists()
        assert not cache_file2.exists()


class TestEmbeddingIntegration:
    """Integration tests for embedding functionality."""
    
    @pytest.fixture
    def embedding_service(self):
        """Create real embedding service for integration tests."""
        return MultiModelEmbeddingService(
            model_name='all-MiniLM-L6-v2',
            cache_embeddings=False,  # Disable caching for integration tests
            quality_validation=True
        )
    
    @pytest.mark.integration
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_model_switching_integration(self, mock_st_class, embedding_service):
        """Test switching between different models."""
        # Mock different models with different dimensions
        def create_mock_model(dimension):
            mock_model = Mock()
            mock_model.encode.return_value = [np.random.randn(dimension)]
            return mock_model
        
        mock_st_class.side_effect = lambda name: {
            'all-MiniLM-L6-v2': create_mock_model(384),
            'all-mpnet-base-v2': create_mock_model(768),
        }.get(name, create_mock_model(384))
        
        text = "Test model switching"
        
        # Test with first model
        embedding_service.switch_model('all-MiniLM-L6-v2')
        embeddings1, _ = embedding_service.encode(text)
        assert embeddings1.shape == (384,)
        
        # Test with second model
        embedding_service.switch_model('all-mpnet-base-v2')
        embeddings2, _ = embedding_service.encode(text)
        assert embeddings2.shape == (768,)
    
    @pytest.mark.integration
    def test_quality_validation_integration(self, embedding_service):
        """Test quality validation with various inputs."""
        test_cases = [
            ("Normal text", True),
            ("", False),  # Empty text
            ("   ", False),  # Whitespace only
            ("A" * 1000, True),  # Long text (should be truncated)
            ("Special chars: !@#$%^&*()", True),
            ("Numbers: 123 456 789", True),
        ]
        
        with patch('core.enhanced_embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.encode.return_value = [np.random.randn(384)]
            mock_st.return_value = mock_model
            
            for text, should_be_valid in test_cases:
                _, metrics = embedding_service.encode(text)
                if should_be_valid:
                    assert metrics['is_valid'], f"Text '{text[:20]}...' should be valid"
                else:
                    assert not metrics['is_valid'], f"Text '{text[:20]}...' should be invalid"


class TestEmbeddingEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_validator_edge_cases(self):
        """Test embedding validator with edge cases."""
        # Very small embedding
        tiny_embedding = np.array([1e-10])
        result = EmbeddingQualityValidator.validate_embedding(tiny_embedding)
        assert result['is_valid']
        assert result['quality_score'] < 1.0  # Should be penalized for extreme values
        
        # Very large embedding values
        large_embedding = np.array([100.0, 200.0, 300.0])
        result = EmbeddingQualityValidator.validate_embedding(large_embedding)
        assert result['is_valid']
        assert result['quality_score'] < 1.0  # Should be penalized for extreme values
        
        # Single value embedding
        single_value = np.array([5.0])
        result = EmbeddingQualityValidator.validate_embedding(single_value)
        assert result['is_valid']
        assert result['dimension'] == 1
    
    def test_service_initialization_edge_cases(self):
        """Test service initialization with edge cases."""
        with patch('core.enhanced_embeddings.Config') as mock_config_class:
            mock_config = Mock()
            mock_config.get.return_value = 'all-MiniLM-L6-v2'
            mock_config_class.return_value = mock_config
            
            # Test with all default parameters
            service = MultiModelEmbeddingService()
            assert service.model_name == 'all-MiniLM-L6-v2'
            assert service.cache_embeddings is True
            assert service.quality_validation is True
            
            # Test with custom parameters
            service = MultiModelEmbeddingService(
                model_name='custom-model',
                cache_embeddings=False,
                quality_validation=False,
                similarity_threshold=0.5
            )
            assert service.model_name == 'custom-model'
            assert service.cache_embeddings is False
            assert service.quality_validation is False
            assert service.similarity_threshold == 0.5
    
    @patch('core.enhanced_embeddings.SentenceTransformer')
    def test_encoding_failure_handling(self, mock_st_class):
        """Test handling of encoding failures."""
        # Mock model that always fails
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Encoding failed")
        mock_st_class.return_value = mock_model
        
        with patch('core.enhanced_embeddings.Config') as mock_config_class:
            mock_config = Mock()
            mock_config.get.return_value = 'all-MiniLM-L6-v2'
            mock_config_class.return_value = mock_config
            
            service = MultiModelEmbeddingService()
            
            embeddings, metrics = service.encode("test text")
            
            # Should return zero embeddings and mark as invalid
            assert isinstance(embeddings, np.ndarray)
            assert np.all(embeddings == 0)
            assert not metrics['is_valid']
            assert 'Encoding failed' in metrics['reason']
    
    def test_similarity_computation_edge_cases(self):
        """Test similarity computation with edge cases."""
        with patch('core.enhanced_embeddings.Config') as mock_config_class:
            mock_config = Mock()
            mock_config.get.return_value = 'all-MiniLM-L6-v2'
            mock_config_class.return_value = mock_config
            
            service = MultiModelEmbeddingService()
            
            # Test with zero embeddings
            zero_embeddings = np.zeros((2, 384))
            similarities = service.compute_similarities(zero_embeddings)
            # Cosine similarity of zero vectors should be NaN, but sklearn handles this
            assert similarities.shape == (2, 2)
            
            # Test with identical embeddings
            identical_embeddings = np.ones((2, 384))
            similarities = service.compute_similarities(identical_embeddings)
            assert similarities.shape == (2, 2)
            # Diagonal should be 1.0 (self-similarity)
            np.testing.assert_array_almost_equal(np.diag(similarities), [1.0, 1.0])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])