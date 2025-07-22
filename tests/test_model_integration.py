"""
Integration tests for different embedding models
"""

import pytest
import os
import asyncio
from config.models import EmbeddingConfig
from core.embeddings import EmbeddingService


@pytest.mark.integration
class TestModelIntegration:
    """Integration tests for different embedding models"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_name,expected_dim", [
        ("all-MiniLM-L6-v2", 384),
        ("all-mpnet-base-v2", 768),
        ("multi-qa-MiniLM-L6-cos-v1", 384),
    ])
    async def test_different_models(self, model_name, expected_dim):
        """Test that different models work correctly"""
        config = EmbeddingConfig(
            model_name=model_name,
            device="cpu",
            batch_size=4
        )
        
        service = EmbeddingService(config)
        
        # Test basic embedding generation - this will initialize the model
        test_text = "This is a test sentence for embedding generation."
        embedding = await service.embed_text(test_text)
        
        # Check dimension after model is loaded
        assert service.dimension == expected_dim
        
        assert embedding.shape == (expected_dim,)
        assert embedding.dtype.name == 'float32'
        # Embeddings should be normalized (sentence-transformers normalize by default)
        assert abs(1.0 - float((embedding ** 2).sum() ** 0.5)) < 1e-5
        
        service.cleanup()
    
    @pytest.mark.asyncio
    async def test_model_switching(self):
        """Test switching between different models"""
        # Test with small model first
        config1 = EmbeddingConfig(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
            batch_size=4
        )
        
        service1 = EmbeddingService(config1)
        embedding1 = await service1.embed_text("test text")
        assert embedding1.shape == (384,)
        assert service1.dimension == 384
        service1.cleanup()
        
        # Test with larger model
        config2 = EmbeddingConfig(
            model_name="all-mpnet-base-v2",
            device="cpu",
            batch_size=4
        )
        
        service2 = EmbeddingService(config2)
        embedding2 = await service2.embed_text("test text")
        assert embedding2.shape == (768,)
        assert service2.dimension == 768
        service2.cleanup()
        
        # Embeddings should be different due to different models
        # (can't compare directly due to different dimensions)
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing with real model"""
        config = EmbeddingConfig(
            model_name="all-MiniLM-L6-v2",
            device="cpu", 
            batch_size=2
        )
        
        service = EmbeddingService(config)
        
        texts = [
            "This is the first test sentence.",
            "This is the second test sentence.", 
            "This is the third test sentence.",
            "This is the fourth test sentence."
        ]
        
        embeddings = await service.embed_texts(texts)
        
        assert len(embeddings) == 4
        for embedding in embeddings:
            assert embedding.shape == (384,)
            assert embedding.dtype.name == 'float32'
        
        service.cleanup()
    
    @pytest.mark.asyncio
    async def test_similarity_computation(self):
        """Test similarity computation with real embeddings"""
        config = EmbeddingConfig(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
            batch_size=4
        )
        
        service = EmbeddingService(config)
        
        # Similar texts should have high similarity
        text1 = "The cat is sleeping on the mat."
        text2 = "A cat is resting on the carpet."
        similarity_high = await service.compute_similarity(text1, text2)
        
        # Dissimilar texts should have lower similarity
        text3 = "Python is a programming language."
        similarity_low = await service.compute_similarity(text1, text3)
        
        # Identical texts should have similarity close to 1
        similarity_identical = await service.compute_similarity(text1, text1)
        
        assert 0.0 <= similarity_high <= 1.0
        assert 0.0 <= similarity_low <= 1.0
        assert 0.0 <= similarity_identical <= 1.0
        
        # Similar texts should have higher similarity than dissimilar ones
        assert similarity_high > similarity_low
        # Identical texts should have highest similarity
        assert similarity_identical >= similarity_high
        # Identical should be very close to 1.0
        assert similarity_identical > 0.95
        
        service.cleanup()
    
    @pytest.mark.asyncio
    async def test_environment_configuration(self):
        """Test that environment variables work correctly"""
        # Save original values
        original_model = os.environ.get('EMBEDDING_MODEL')
        original_device = os.environ.get('EMBEDDING_DEVICE')
        original_batch = os.environ.get('EMBEDDING_BATCH_SIZE')
        
        try:
            # Set test environment variables
            os.environ['EMBEDDING_MODEL'] = 'all-MiniLM-L6-v2'
            os.environ['EMBEDDING_DEVICE'] = 'cpu'
            os.environ['EMBEDDING_BATCH_SIZE'] = '8'
            
            config = EmbeddingConfig.from_env()
            assert config.model_name == 'all-MiniLM-L6-v2'
            assert config.device == 'cpu'
            assert config.batch_size == 8
            
            service = EmbeddingService(config)
            assert service.model_name == 'all-MiniLM-L6-v2'
            assert service.device == 'cpu'
            assert service.batch_size == 8
            
        finally:
            # Restore original values
            if original_model is not None:
                os.environ['EMBEDDING_MODEL'] = original_model
            elif 'EMBEDDING_MODEL' in os.environ:
                del os.environ['EMBEDDING_MODEL']
                
            if original_device is not None:
                os.environ['EMBEDDING_DEVICE'] = original_device
            elif 'EMBEDDING_DEVICE' in os.environ:
                del os.environ['EMBEDDING_DEVICE']
                
            if original_batch is not None:
                os.environ['EMBEDDING_BATCH_SIZE'] = original_batch
            elif 'EMBEDDING_BATCH_SIZE' in os.environ:
                del os.environ['EMBEDDING_BATCH_SIZE']