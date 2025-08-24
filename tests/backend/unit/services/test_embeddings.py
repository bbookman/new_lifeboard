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
        # Import ServiceStatus for proper status setting
        from core.base_service import ServiceStatus
        
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Encoding failed")
        embedding_service.model = mock_model
        embedding_service._status = ServiceStatus.READY  # Prevent real model loading
        
        # Should return zeros on error
        result = await embedding_service.embed_text("test text")
        assert isinstance(result, np.ndarray)
        assert len(result) == 384
        assert np.all(result == 0)


class TestEmbeddingBatchProcessing:
    """Test batch processing capabilities"""
    
    @pytest.mark.asyncio
    async def test_embed_batch_method(self, embedding_config):
        """Test the embed_batch method specifically"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            # Return batch embeddings as numpy arrays
            mock_model.encode.return_value = np.array([
                [0.1, 0.2] * 192,  # 384 dims for first text
                [0.3, 0.4] * 192,  # 384 dims for second text
                [0.5, 0.6] * 192   # 384 dims for third text
            ], dtype=np.float32)
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            texts = ["first text", "second text", "third text"]
            results = await service.embed_batch(texts)
            
            # Should return list of lists (not numpy arrays)
            assert len(results) == 3
            assert all(isinstance(r, list) for r in results)
            assert all(len(r) == 384 for r in results)
            
            # Verify model was called with correct parameters
            mock_model.encode.assert_called_once()
            call_args = mock_model.encode.call_args
            assert call_args[0][0] == texts  # First positional arg should be texts
            assert call_args[1]['batch_size'] == 16  # From fixture config batch_size
            assert call_args[1]['show_progress_bar'] is False
            assert call_args[1]['convert_to_tensor'] is False
    
    @pytest.mark.asyncio
    async def test_batch_size_handling(self, embedding_config):
        """Test that batch processing respects configured batch size"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            # Create larger batch of embeddings
            batch_size = 20
            embeddings = np.random.rand(batch_size, 384).astype(np.float32)
            mock_model.encode.return_value = embeddings
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            # Test with texts larger than batch size
            texts = [f"text {i}" for i in range(batch_size)]
            results = await service.embed_texts(texts)
            
            assert len(results) == batch_size
            # Verify batch_size parameter was used
            call_args = mock_model.encode.call_args
            assert call_args[1]['batch_size'] == 16  # From fixture config batch_size
    
    @pytest.mark.asyncio
    async def test_progress_bar_activation(self, embedding_config):
        """Test that progress bar activates for large batches"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            # Create batch larger than progress bar threshold (50)
            large_batch_size = 60
            embeddings = np.random.rand(large_batch_size, 384).astype(np.float32)
            mock_model.encode.return_value = embeddings
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            texts = [f"text {i}" for i in range(large_batch_size)]
            await service.embed_texts(texts)
            
            # Verify progress bar was enabled for large batch
            call_args = mock_model.encode.call_args
            assert call_args[1]['show_progress_bar'] is True
    
    @pytest.mark.asyncio
    async def test_mixed_empty_and_valid_texts_batch(self, embedding_config):
        """Test batch processing with mix of empty and valid texts"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            # Only 3 valid texts out of 6
            valid_embeddings = np.array([
                [0.1, 0.2] * 192,  # For "text 1"
                [0.3, 0.4] * 192,  # For "text 3" 
                [0.5, 0.6] * 192   # For "text 5"
            ], dtype=np.float32)
            mock_model.encode.return_value = valid_embeddings
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            # Mix of empty and valid texts
            texts = ["", "text 1", "", "text 3", "   ", "text 5"]
            results = await service.embed_texts(texts)
            
            assert len(results) == 6
            # Empty/whitespace texts should return zero vectors
            assert np.all(results[0] == 0)  # Empty string
            assert np.all(results[2] == 0)  # Empty string  
            assert np.all(results[4] == 0)  # Whitespace only
            
            # Valid texts should have non-zero embeddings
            assert not np.all(results[1] == 0)  # "text 1"
            assert not np.all(results[3] == 0)  # "text 3"
            assert not np.all(results[5] == 0)  # "text 5"
            
            # Verify only valid texts were sent to model
            call_args = mock_model.encode.call_args[0][0]  # First positional arg
            assert call_args == ["text 1", "text 3", "text 5"]


class TestEmbeddingServiceIntegration:
    """Integration tests for embedding service with realistic scenarios"""
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, embedding_config):
        """Test complete service lifecycle from init to cleanup"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.encode.return_value = np.array([0.1, 0.2] * 192, dtype=np.float32)
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.device = "cpu"
            mock_model.max_seq_length = 512
            # Mock the _modules attribute to prevent iteration error
            mock_model._modules = {}
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            
            # Initial state
            assert not service.is_model_loaded
            assert not service.is_initialized
            
            # Initialize
            success = await service.initialize()
            assert success is True
            assert service.is_model_loaded
            assert service.is_initialized
            
            # Test functionality
            embedding = await service.embed_text("test text")
            assert isinstance(embedding, np.ndarray)
            assert len(embedding) == 384
            
            # Get info
            info = service.get_model_info()
            assert info["status"] == "active"
            assert info["model_name"] == "all-MiniLM-L6-v2"
            
            # Health check
            health = await service._check_service_health()
            assert health["healthy"] is True
            assert health["model_loaded"] is True
            
            # Cleanup
            cleanup_success = await service._shutdown_service()
            assert cleanup_success is True
            assert service.model is None
    
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
    async def test_concurrent_embedding_requests(self, embedding_config):
        """Test handling concurrent embedding requests"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model._modules = {}
            
            # Mock encode to return different embeddings for different calls
            def encode_side_effect(*args, **kwargs):
                # Handle both single string and list inputs
                texts = args[0] if args else []
                if isinstance(texts, str):
                    return np.random.rand(384).astype(np.float32)
                else:
                    return np.random.rand(len(texts), 384).astype(np.float32)
            
            mock_model.encode.side_effect = encode_side_effect
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            # Create multiple concurrent requests
            import asyncio
            tasks = [
                service.embed_text(f"concurrent text {i}")
                for i in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All requests should complete successfully
            assert len(results) == 10
            assert all(isinstance(r, np.ndarray) for r in results)
            assert all(len(r) == 384 for r in results)
    
    @pytest.mark.asyncio
    async def test_device_configuration(self):
        """Test different device configurations"""
        devices = ["cpu", "cuda"]
        
        for device in devices:
            config = EmbeddingConfig(
                model_name="all-MiniLM-L6-v2",
                device=device,
                batch_size=8
            )
            service = EmbeddingService(config)
            assert service.device == device
    
    @pytest.mark.asyncio
    async def test_model_validation(self):
        """Test model validation functionality"""
        service = EmbeddingService(EmbeddingConfig())
        
        # Test supported models list
        supported_models = service.get_supported_models()
        assert len(supported_models) > 0
        assert "all-MiniLM-L6-v2" in supported_models
        assert "all-mpnet-base-v2" in supported_models
        
        # Test dimension lookup
        for model_name in supported_models:
            dim = service.get_model_dimension(model_name)
            assert dim > 0
    
    @pytest.mark.asyncio
    async def test_model_availability_check(self, embedding_config):
        """Test model availability checking"""
        service = EmbeddingService(embedding_config)
        
        # Test with known model
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_st.return_value = Mock()
            is_available = service.is_model_available("all-MiniLM-L6-v2")
            assert is_available is True
        
        # Test with unknown model (should handle gracefully)
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_st.side_effect = Exception("Model not found")
            is_available = service.is_model_available("nonexistent-model")
            assert is_available is False


class TestEmbeddingServiceErrorScenarios:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_model_loading_failure_recovery(self, embedding_config):
        """Test recovery from model loading failures"""
        service = EmbeddingService(embedding_config)
        
        # First initialization with failure
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_st.side_effect = Exception("Load failed")
            
            success = await service.initialize()
            assert success is False
            assert not service.is_model_loaded
        
        # Second initialization with success (new patch context)
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model._modules = {}
            mock_st.return_value = mock_model
            
            # Reset service status to allow re-initialization
            from core.base_service import ServiceStatus
            service._status = ServiceStatus.UNINITIALIZED
            
            success = await service.initialize()
            assert success is True
            assert service.is_model_loaded
    
    @pytest.mark.asyncio
    async def test_embedding_generation_failure_fallback(self, embedding_config):
        """Test fallback to zero vectors on embedding failure"""
        from core.base_service import ServiceStatus
        
        service = EmbeddingService(embedding_config)
        
        # Set up a mock model that fails during encoding
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Encoding failed")
        service.model = mock_model
        service._status = ServiceStatus.READY  # Prevent re-initialization
        
        # Should return zero vector on failure
        result = await service.embed_text("test text")
        assert isinstance(result, np.ndarray)
        assert len(result) == 384
        assert np.all(result == 0)
    
    @pytest.mark.asyncio
    async def test_batch_processing_partial_failure(self, embedding_config):
        """Test batch processing with partial failures"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.encode.side_effect = Exception("Batch encoding failed")
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model._modules = {}
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            texts = ["text 1", "text 2", "text 3"]
            results = await service.embed_texts(texts)
            
            # Should return zero vectors for all texts on batch failure
            assert len(results) == 3
            assert all(np.all(r == 0) for r in results)
            assert all(len(r) == 384 for r in results)
    
    @pytest.mark.asyncio
    async def test_similarity_computation_edge_cases(self, embedding_config):
        """Test similarity computation edge cases"""
        service = EmbeddingService(embedding_config)
        
        with patch.object(service, 'embed_text') as mock_embed:
            # Test with zero vectors (should handle division by zero gracefully)
            mock_embed.return_value = np.zeros(384, dtype=np.float32)
            similarity = await service.compute_similarity("text1", "text2")
            # Zero vectors result in NaN, which gets clamped to 0.0 in compute_similarity
            assert similarity >= 0.0 and similarity <= 1.0
            
            # Test with identical unit vectors
            unit_vector = np.ones(384, dtype=np.float32) / np.sqrt(384)
            mock_embed.return_value = unit_vector
            similarity = await service.compute_similarity("same", "same")
            assert abs(similarity - 1.0) < 1e-6
            
            # Test with perpendicular vectors
            mock_embed.side_effect = [
                np.array([1.0] + [0.0] * 383, dtype=np.float32),  # [1,0,0,...]
                np.array([0.0, 1.0] + [0.0] * 382, dtype=np.float32)  # [0,1,0,...]
            ]
            similarity = await service.compute_similarity("text1", "text2")
            assert abs(similarity - 0.0) < 1e-6
    
    @pytest.mark.asyncio
    async def test_health_check_failure_scenarios(self, embedding_config):
        """Test health check with various failure scenarios"""
        service = EmbeddingService(embedding_config)
        
        # Test with no model loaded
        health = await service._check_service_health()
        assert health["healthy"] is False
        assert health["model_loaded"] is False
        assert "reason" in health
        
        # Test with model loaded but embedding fails
        mock_model = Mock()
        service.model = mock_model
        
        with patch.object(service, 'embed_text') as mock_embed:
            mock_embed.side_effect = Exception("Health check failed")
            health = await service._check_service_health()
            
            assert health["healthy"] is False
            assert health["model_loaded"] is True
            assert health["test_passed"] is False
            assert "test_error" in health
    
    @pytest.mark.asyncio
    async def test_cleanup_edge_cases(self, embedding_config):
        """Test cleanup method edge cases"""
        service = EmbeddingService(embedding_config)
        
        # Test cleanup without model
        service.model = None
        success = await service._shutdown_service()
        assert success is True
        
        # Test cleanup with model but CUDA unavailable
        mock_model = Mock()
        service.model = mock_model
        service.device = "cuda"
        
        with patch('torch.cuda.is_available', return_value=False):
            success = await service._shutdown_service()
            assert success is True
            assert service.model is None
        
        # Test legacy cleanup method
        service.model = Mock()
        with patch('torch.cuda.is_available', return_value=False):
            service.cleanup()  # Should not raise exception


class TestEmbeddingServicePerformance:
    """Performance tests for embedding service"""
    
    @pytest.mark.asyncio
    async def test_batch_vs_individual_performance(self, embedding_config):
        """Test that batch processing is more efficient than individual calls"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model._modules = {}
            # Track call count
            call_count = {'count': 0}
            
            def mock_encode(*args, **kwargs):
                call_count['count'] += 1
                if isinstance(args[0], str):
                    return np.random.rand(384).astype(np.float32)
                else:
                    return np.random.rand(len(args[0]), 384).astype(np.float32)
            
            mock_model.encode.side_effect = mock_encode
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            texts = [f"performance test {i}" for i in range(10)]
            
            # Test individual calls
            call_count['count'] = 0
            individual_results = []
            for text in texts:
                result = await service.embed_text(text)
                individual_results.append(result)
            individual_calls = call_count['count']
            
            # Test batch call
            call_count['count'] = 0
            batch_results = await service.embed_texts(texts)
            batch_calls = call_count['count']
            
            # Batch should make fewer calls to underlying model
            assert batch_calls < individual_calls
            assert len(batch_results) == len(individual_results)
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_large_batch_processing(self, embedding_config):
        """Test processing large batches efficiently"""
        with patch('core.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model._modules = {}
            
            # Simulate realistic processing time
            def mock_encode(texts, **kwargs):
                if isinstance(texts, str):
                    texts = [texts]
                return np.random.rand(len(texts), 384).astype(np.float32)
            
            mock_model.encode.side_effect = mock_encode
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(embedding_config)
            await service.initialize()
            
            # Test with large batch
            large_texts = [f"large batch text {i}" for i in range(1000)]
            
            import time
            start_time = time.perf_counter()
            results = await service.embed_texts(large_texts)
            end_time = time.perf_counter()
            
            # Should complete within reasonable time
            duration = end_time - start_time
            assert duration < 5.0  # 5 seconds for 1000 embeddings (mocked)
            assert len(results) == 1000
            assert all(len(r) == 384 for r in results)