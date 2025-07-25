"""
Tests for the EmbeddingService implementation
"""

import pytest
import numpy as np
import tempfile
import asyncio
from unittest.mock import Mock, patch
from core.embeddings import EmbeddingService
from config.models import EmbeddingConfig


class TestEmbeddingService:
    """Test suite for EmbeddingService"""
    
    @pytest.fixture
    def embedding_config(self):
        """Create test embedding configuration"""
        return EmbeddingConfig(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
            batch_size=8
        )
    
    @pytest.fixture
    def embedding_service(self, embedding_config):
        """Create EmbeddingService instance"""
        return EmbeddingService(embedding_config)
    
    def test_init_embedding_service(self, embedding_service):
        """Test embedding service initialization"""
        assert embedding_service.model_name == "all-MiniLM-L6-v2"
        assert embedding_service.device == "cpu"
        assert embedding_service.batch_size == 8
        assert embedding_service.dimension == 384  # Expected for all-MiniLM-L6-v2
        assert embedding_service.model is None  # Not loaded yet
    
    def test_get_model_dimension(self):
        """Test model dimension mapping"""
        assert EmbeddingService.get_model_dimension("all-MiniLM-L6-v2") == 384
        assert EmbeddingService.get_model_dimension("all-mpnet-base-v2") == 768
        assert EmbeddingService.get_model_dimension("unknown-model") == 384  # Default
    
    def test_get_supported_models(self):
        """Test supported models list"""
        models = EmbeddingService.get_supported_models()
        assert "all-MiniLM-L6-v2" in models
        assert "all-mpnet-base-v2" in models
        assert len(models) > 0
    
    @pytest.mark.asyncio
    async def test_embed_text_without_initialization(self, embedding_service):
        """Test embedding text without explicit initialization"""
        with patch.object(embedding_service, 'initialize') as mock_init:
            with patch('sentence_transformers.SentenceTransformer') as mock_st:
                mock_model = Mock()
                mock_model.encode.return_value = np.array([0.1, 0.2, 0.3] * 128, dtype=np.float32)  # 384 dims
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_st.return_value = mock_model
                
                # This should trigger initialization
                result = await embedding_service.embed_text("test text")
                
                mock_init.assert_called_once()
                assert isinstance(result, np.ndarray)
                assert len(result) == 384
    
    @pytest.mark.asyncio
    async def test_embed_empty_text(self, embedding_service):
        """Test embedding empty or None text"""
        # Mock the model
        embedding_service.model = Mock()
        
        # Test empty string
        result = await embedding_service.embed_text("")
        assert isinstance(result, np.ndarray)
        assert len(result) == 384
        assert np.all(result == 0)  # Should be zeros
        
        # Test None
        result = await embedding_service.embed_text(None)
        assert isinstance(result, np.ndarray)
        assert len(result) == 384
        assert np.all(result == 0)  # Should be zeros
    
    @pytest.mark.asyncio
    async def test_embed_texts_batch(self, embedding_service):
        """Test batch text embedding"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            # Return different embeddings for each text
            mock_model.encode.return_value = np.array([
                [0.1, 0.2] * 192,  # 384 dims for first text
                [0.3, 0.4] * 192   # 384 dims for second text
            ], dtype=np.float32)
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            texts = ["first text", "second text"]
            results = await embedding_service.embed_texts(texts)
            
            assert len(results) == 2
            assert all(isinstance(r, np.ndarray) for r in results)
            assert all(len(r) == 384 for r in results)
            
            # Verify the model was loaded and encode was called
            assert mock_st.called
            assert mock_model.encode.called
    
    @pytest.mark.asyncio
    async def test_embed_texts_with_empty_texts(self, embedding_service):
        """Test batch embedding with some empty texts"""
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            # Only one valid text, so return single embedding
            mock_model.encode.return_value = np.array([[0.5, 0.6] * 192], dtype=np.float32)
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            await embedding_service.initialize()
            
            texts = ["", "valid text", ""]
            results = await embedding_service.embed_texts(texts)
            
            assert len(results) == 3
            # First and last should be zeros
            assert np.all(results[0] == 0)
            assert np.all(results[2] == 0)
            # Middle should have actual values
            assert not np.all(results[1] == 0)
    
    @pytest.mark.asyncio
    async def test_compute_similarity(self, embedding_service):
        """Test similarity computation"""
        with patch.object(embedding_service, 'embed_text') as mock_embed:
            # Return normalized vectors for testing
            mock_embed.side_effect = [
                np.array([1.0, 0.0] * 192, dtype=np.float32),  # [1,0,1,0,...]
                np.array([0.0, 1.0] * 192, dtype=np.float32)   # [0,1,0,1,...]
            ]
            
            similarity = await embedding_service.compute_similarity("text1", "text2")
            
            assert isinstance(similarity, float)
            assert 0.0 <= similarity <= 1.0
            assert mock_embed.call_count == 2
    
    @pytest.mark.asyncio
    async def test_compute_similarity_identical_texts(self, embedding_service):
        """Test similarity of identical texts"""
        with patch.object(embedding_service, 'embed_text') as mock_embed:
            # Return identical vectors
            same_vector = np.array([0.5, 0.5] * 192, dtype=np.float32)
            mock_embed.return_value = same_vector
            
            similarity = await embedding_service.compute_similarity("same text", "same text")
            
            assert abs(similarity - 1.0) < 1e-6  # Should be very close to 1.0
    
    def test_get_model_info_before_loading(self, embedding_service):
        """Test model info before loading model"""
        info = embedding_service.get_model_info()
        
        assert info["model_name"] == "all-MiniLM-L6-v2"
        assert info["dimension"] == 384
        assert info["device"] == "cpu"
        assert info["batch_size"] == 8
        assert info["status"] == "not_loaded"
    
    @pytest.mark.asyncio
    async def test_get_model_info_after_loading(self, embedding_service):
        """Test model info after loading model"""
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.device = "cpu"
            mock_model.max_seq_length = 512
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            await embedding_service.initialize()
            info = embedding_service.get_model_info()
            
            assert info["status"] == "active"
            assert info["torch_device"] == "cpu"
            # The actual implementation uses getattr with fallback, so we check if it exists
            assert "max_seq_length" in info
    
    def test_cleanup(self, embedding_service):
        """Test cleanup method"""
        # Mock a loaded model
        embedding_service.model = Mock()
        
        with patch('torch.cuda.is_available', return_value=False):
            embedding_service.cleanup()
            
        assert embedding_service.model is None
    
    @pytest.mark.asyncio
    async def test_initialization_error_handling(self, embedding_service):
        """Test error handling during initialization"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_st.side_effect = Exception("Model load failed")
            
            # Test that initialization fails when model loading fails
            success = await embedding_service.initialize()
            assert success is False
    
    @pytest.mark.asyncio
    async def test_embedding_error_handling(self, embedding_service):
        """Test error handling during embedding generation"""
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Encoding failed")
        embedding_service.model = mock_model
        
        # Should return zeros on error
        result = await embedding_service.embed_text("test text")
        assert isinstance(result, np.ndarray)
        assert len(result) == 384
        assert np.all(result == 0)


class TestEmbeddingIntegration:
    """Integration tests for embedding service"""
    
    @pytest.mark.asyncio
    async def test_different_model_configs(self):
        """Test different model configurations"""
        configs = [
            {"model_name": "all-MiniLM-L6-v2", "expected_dim": 384},
            {"model_name": "all-mpnet-base-v2", "expected_dim": 768},
        ]
        
        for config in configs:
            embedding_config = EmbeddingConfig(
                model_name=config["model_name"],
                device="cpu",
                batch_size=4
            )
            service = EmbeddingService(embedding_config)
            
            assert service.dimension == config["expected_dim"]
            assert service.model_name == config["model_name"]
    
    @pytest.mark.asyncio  
    async def test_model_validation(self):
        """Test model validation functionality"""
        service = EmbeddingService(EmbeddingConfig())
        
        # Test with a known model (should not raise error in normal circumstances)
        # This is mainly testing the method exists and works
        supported_models = service.get_supported_models()
        assert len(supported_models) > 0
        
        # Test dimension lookup
        for model_name in supported_models:
            dim = service.get_model_dimension(model_name)
            assert dim > 0