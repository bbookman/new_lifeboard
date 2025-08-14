"""
Real embedding service using sentence transformers for semantic search
"""

import numpy as np
import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import torch

from .base_service import BaseService

logger = logging.getLogger(__name__)


class EmbeddingService(BaseService):
    """Real embedding service using sentence transformers"""
    
    # Model dimension mapping for common models
    MODEL_DIMENSIONS = {
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "all-MiniLM-L12-v2": 384,
        "multi-qa-MiniLM-L6-cos-v1": 384,
        "multi-qa-mpnet-base-cos-v1": 768,
        "paraphrase-MiniLM-L6-v2": 384,
        "paraphrase-mpnet-base-v2": 768,
    }
    
    def __init__(self, config):
        """
        Initialize the embedding service
        
        Args:
            config: Configuration object with model_name, device, and batch_size
        """
        super().__init__(service_name="EmbeddingService", config=config)
        self.model_name = config.model_name
        self.device = config.device
        self.batch_size = config.batch_size
        self.model: Optional[SentenceTransformer] = None
        self.dimension = self._get_model_dimension()
        
        # Add service capabilities
        self.add_capability("text_embedding")
        self.add_capability("batch_processing")
        self.add_capability("similarity_computation")
    
    @property
    def is_model_loaded(self) -> bool:
        """Check if the model has been loaded"""
        return self.model is not None
        
    def _get_model_dimension(self) -> int:
        """Get expected dimension for the model"""
        return self.MODEL_DIMENSIONS.get(self.model_name, 384)  # Default to 384
        
    async def _initialize_service(self) -> bool:
        """Initialize the sentence transformer model"""
        try:
            self.logger.info(f"Loading embedding model: {self.model_name}")
            self.logger.info(f"Model name from config: {self.config.model_name}")
            self.logger.info(f"Device: {self.device}")
            
            # Load the model on specified device
            self.model = SentenceTransformer(self.model_name, device=self.device)
            
            self.logger.info(f"Model loaded: {self.model}")
            self.logger.info(f"Model modules after loading: {list(self.model._modules.keys())}")
            if hasattr(self.model, '_modules') and '0' in self.model._modules:
                self.logger.info(f"Model transformer: {self.model._modules['0']}")
            
            # Update dimension from actual model - use multiple approaches to ensure accuracy
            actual_dimension = None
            
            # Method 1: Try get_sentence_embedding_dimension
            if hasattr(self.model, 'get_sentence_embedding_dimension'):
                actual_dimension = self.model.get_sentence_embedding_dimension()
                self.logger.info(f"Got dimension from get_sentence_embedding_dimension(): {actual_dimension}")
            
            # Method 2: If method 1 failed, encode a test sentence and check shape
            if actual_dimension is None:
                try:
                    test_embedding = self.model.encode("test", convert_to_numpy=True)
                    actual_dimension = test_embedding.shape[0]
                    self.logger.info(f"Got dimension from test encoding: {actual_dimension}")
                except Exception as e:
                    self.logger.warning(f"Failed to get dimension from test encoding: {e}")
            
            # Update dimension if we got a valid value
            if actual_dimension is not None and actual_dimension > 0:
                self.dimension = actual_dimension
            
            self.logger.info(f"Embedding model loaded successfully. Final dimension: {self.dimension}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load embedding model {self.model_name}: {e}")
            return False
    
    async def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text to embed
            
        Returns:
            numpy array containing the text embedding
        """
        if not self.is_initialized:
            await self.initialize()
            
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return np.zeros(self.dimension, dtype=np.float32)
            
        try:
            # Generate embedding
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=1
            )
            
            return embedding.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}")
            return np.zeros(self.dimension, dtype=np.float32)
    
    async def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of numpy arrays containing the text embeddings
        """
        if not self.is_initialized:
            await self.initialize()
            
        if not texts:
            return []
            
        try:
            # Filter out empty texts and keep track of indices
            valid_texts = []
            valid_indices = []
            
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_texts.append(text)
                    valid_indices.append(i)
            
            if not valid_texts:
                logger.warning("No valid texts provided for embedding")
                return [np.zeros(self.dimension, dtype=np.float32) for _ in texts]
            
            # Generate embeddings in batches
            embeddings = self.model.encode(
                valid_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=self.batch_size,
                show_progress_bar=len(valid_texts) > 50
            )
            
            # Create result array with zeros for invalid texts
            result = []
            valid_idx = 0
            
            for i, text in enumerate(texts):
                if i in valid_indices:
                    result.append(embeddings[valid_idx].astype(np.float32))
                    valid_idx += 1
                else:
                    result.append(np.zeros(self.dimension, dtype=np.float32))
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating embeddings for texts: {e}")
            return [np.zeros(self.dimension, dtype=np.float32) for _ in texts]
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently, returning lists
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of lists containing the text embeddings
        """
        if not self.is_initialized:
            await self.initialize()
        
        logger.debug(f"Generating embeddings for {len(texts)} texts")
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_tensor=False
            )
            return [embedding.tolist() for embedding in embeddings]
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise
    
    async def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        try:
            emb1 = await self.embed_text(text1)
            emb2 = await self.embed_text(text2)
            
            # Compute cosine similarity
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            
            # Ensure similarity is between 0 and 1
            similarity = max(0.0, min(1.0, float(similarity)))
            
            return similarity
            
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information
        
        Returns:
            Dictionary containing model information
        """
        info = {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "batch_size": self.batch_size,
            "status": "active" if self.model is not None else "not_loaded"
        }
        
        if self.model is not None:
            info["torch_device"] = str(self.model.device)
            info["max_seq_length"] = getattr(self.model, 'max_seq_length', 'unknown')
            
        return info
    
    def is_model_available(self, model_name: str) -> bool:
        """
        Check if a model is available for download/use
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            # Try to load model info (this doesn't download the model)
            from sentence_transformers import SentenceTransformer
            SentenceTransformer(model_name, device='cpu', cache_folder=None)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_supported_models(cls) -> List[str]:
        """
        Get list of commonly supported models
        
        Returns:
            List of supported model names
        """
        return list(cls.MODEL_DIMENSIONS.keys())
    
    @classmethod
    def get_model_dimension(cls, model_name: str) -> int:
        """
        Get dimension for a model without loading it
        
        Args:
            model_name: Name of the model
            
        Returns:
            Expected dimension for the model
        """
        return cls.MODEL_DIMENSIONS.get(model_name, 384)
    
    async def _shutdown_service(self) -> bool:
        """Clean up resources"""
        try:
            if self.model is not None:
                # Clear CUDA cache if using GPU
                if torch.cuda.is_available() and 'cuda' in self.device:
                    torch.cuda.empty_cache()
                
                self.model = None
                self.logger.info("Embedding model resources cleaned up")
            return True
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return False
    
    async def _check_service_health(self) -> Dict[str, Any]:
        """Check service health"""
        health_info = {
            "model_loaded": self.model is not None,
            "model_name": self.model_name,
            "device": self.device,
            "dimension": self.dimension,
            "healthy": True
        }
        
        if self.model is not None:
            try:
                # Quick health check by encoding a test string
                test_embedding = await self.embed_text("health check")
                health_info["test_embedding_shape"] = test_embedding.shape
                health_info["test_passed"] = True
            except Exception as e:
                health_info["test_passed"] = False
                health_info["test_error"] = str(e)
                health_info["healthy"] = False
        else:
            health_info["healthy"] = False
            health_info["reason"] = "Model not loaded"
        
        return health_info
    
    def cleanup(self):
        """Clean up resources (legacy method for backwards compatibility)"""
        import asyncio
        try:
            # Try to create a task if there's a running loop
            asyncio.create_task(self._shutdown_service())
        except RuntimeError:
            # No running event loop, run the shutdown directly
            try:
                asyncio.run(self._shutdown_service())
            except Exception:
                # Fallback to synchronous cleanup
                self._sync_cleanup()
    
    def _sync_cleanup(self):
        """Synchronous cleanup for cases where async is not available"""
        if hasattr(self, 'model') and self.model is not None:
            try:
                del self.model
            except Exception:
                pass
        self.model = None
        self.is_loaded = False