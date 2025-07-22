"""
Real embedding service using sentence transformers for semantic search
"""

import numpy as np
import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)


class EmbeddingService:
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
        self.config = config
        self.model_name = config.model_name
        self.device = config.device
        self.batch_size = config.batch_size
        self.model: Optional[SentenceTransformer] = None
        self.dimension = self._get_model_dimension()
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """Check if the service has been initialized"""
        return self._initialized and self.model is not None
        
    def _get_model_dimension(self) -> int:
        """Get expected dimension for the model"""
        return self.MODEL_DIMENSIONS.get(self.model_name, 384)  # Default to 384
        
    async def initialize(self):
        """Initialize the sentence transformer model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            logger.info(f"Model name from config: {self.config.model_name}")
            logger.info(f"Device: {self.device}")
            
            # Load the model on specified device
            self.model = SentenceTransformer(self.model_name, device=self.device)
            
            logger.info(f"Model loaded: {self.model}")
            logger.info(f"Model modules after loading: {list(self.model._modules.keys())}")
            if hasattr(self.model, '_modules') and '0' in self.model._modules:
                logger.info(f"Model transformer: {self.model._modules['0']}")
            
            # Update dimension from actual model - use multiple approaches to ensure accuracy
            actual_dimension = None
            
            # Method 1: Try get_sentence_embedding_dimension
            if hasattr(self.model, 'get_sentence_embedding_dimension'):
                actual_dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"Got dimension from get_sentence_embedding_dimension(): {actual_dimension}")
            
            # Method 2: If method 1 failed, encode a test sentence and check shape
            if actual_dimension is None:
                try:
                    test_embedding = self.model.encode("test", convert_to_numpy=True)
                    actual_dimension = test_embedding.shape[0]
                    logger.info(f"Got dimension from test encoding: {actual_dimension}")
                except Exception as e:
                    logger.warning(f"Failed to get dimension from test encoding: {e}")
            
            # Update dimension if we got a valid value
            if actual_dimension is not None and actual_dimension > 0:
                self.dimension = actual_dimension
            
            self._initialized = True
            logger.info(f"Embedding model loaded successfully. Final dimension: {self.dimension}")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model {self.model_name}: {e}")
            raise
    
    async def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text to embed
            
        Returns:
            numpy array containing the text embedding
        """
        if self.model is None:
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
        if self.model is None:
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
        if not self.model:
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
    
    def cleanup(self):
        """Clean up resources"""
        if self.model is not None:
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available() and 'cuda' in self.device:
                torch.cuda.empty_cache()
            
            self.model = None
            logger.info("Embedding model resources cleaned up")