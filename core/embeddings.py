import numpy as np
from typing import List, Union, Optional
import asyncio
import logging
from sentence_transformers import SentenceTransformer
import torch
from config.models import EmbeddingConfig


logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using sentence transformers"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model: Optional[SentenceTransformer] = None
        self._model_lock = asyncio.Lock()
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the sentence transformer model"""
        try:
            logger.info(f"Loading embedding model: {self.config.model_name}")
            self.model = SentenceTransformer(self.config.model_name, device=self.config.device)
            
            # Verify model dimension matches config
            test_embedding = self.model.encode("test", convert_to_numpy=True)
            actual_dimension = test_embedding.shape[0]
            
            if actual_dimension != self.config.dimension:
                logger.warning(
                    f"Model dimension ({actual_dimension}) doesn't match config ({self.config.dimension}). "
                    f"Updating config to match model."
                )
                self.config.dimension = actual_dimension
            
            logger.info(f"Embedding model loaded successfully. Dimension: {self.config.dimension}")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(f"Could not initialize embedding model: {e}")
    
    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(self.config.dimension, dtype=np.float32)
        
        async with self._model_lock:
            try:
                # Run embedding generation in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    None, 
                    self._encode_single, 
                    text.strip()
                )
                return embedding
                
            except Exception as e:
                logger.error(f"Error generating embedding for text: {e}")
                # Return zero vector on error
                return np.zeros(self.config.dimension, dtype=np.float32)
    
    async def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts in batch"""
        if not texts:
            return []
        
        # Filter out empty texts and keep track of original indices
        non_empty_texts = []
        text_indices = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts.append(text.strip())
                text_indices.append(i)
        
        # Generate embeddings for non-empty texts
        embeddings = [np.zeros(self.config.dimension, dtype=np.float32)] * len(texts)
        
        if non_empty_texts:
            async with self._model_lock:
                try:
                    # Process in batches to manage memory
                    batch_embeddings = []
                    
                    for i in range(0, len(non_empty_texts), self.config.batch_size):
                        batch = non_empty_texts[i:i + self.config.batch_size]
                        
                        # Run batch embedding in thread pool
                        loop = asyncio.get_event_loop()
                        batch_result = await loop.run_in_executor(
                            None, 
                            self._encode_batch, 
                            batch
                        )
                        batch_embeddings.extend(batch_result)
                    
                    # Place embeddings in correct positions
                    for embedding, original_index in zip(batch_embeddings, text_indices):
                        embeddings[original_index] = embedding
                        
                except Exception as e:
                    logger.error(f"Error generating batch embeddings: {e}")
                    # Return zero vectors for all texts on error
        
        return embeddings
    
    def _encode_single(self, text: str) -> np.ndarray:
        """Encode single text (synchronous)"""
        return self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    
    def _encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Encode batch of texts (synchronous)"""
        embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [embedding for embedding in embeddings]
    
    async def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts"""
        embedding1 = await self.embed_text(text1)
        embedding2 = await self.embed_text(text2)
        
        # Compute cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    async def find_most_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[tuple[str, float]]:
        """Find most similar texts to query from candidates"""
        if not candidates:
            return []
        
        query_embedding = await self.embed_text(query)
        candidate_embeddings = await self.embed_texts(candidates)
        
        similarities = []
        for i, candidate_embedding in enumerate(candidate_embeddings):
            # Compute cosine similarity
            dot_product = np.dot(query_embedding, candidate_embedding)
            norm_query = np.linalg.norm(query_embedding)
            norm_candidate = np.linalg.norm(candidate_embedding)
            
            if norm_query == 0 or norm_candidate == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (norm_query * norm_candidate)
            
            similarities.append((candidates[i], float(similarity)))
        
        # Sort by similarity (descending) and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        if not self.model:
            return {"status": "not_loaded"}
        
        return {
            "status": "loaded",
            "model_name": self.config.model_name,
            "dimension": self.config.dimension,
            "device": self.config.device,
            "batch_size": self.config.batch_size,
            "max_sequence_length": getattr(self.model, 'max_seq_length', 'unknown')
        }
    
    async def warmup(self):
        """Warm up the model with a sample embedding"""
        logger.info("Warming up embedding model...")
        await self.embed_text("This is a warmup text to initialize the model.")
        logger.info("Embedding model warmed up successfully")
    
    def cleanup(self):
        """Clean up model resources"""
        if self.model:
            # Clear CUDA cache if using GPU
            if self.config.device.startswith('cuda'):
                torch.cuda.empty_cache()
            self.model = None
            logger.info("Embedding model cleaned up")


class EmbeddingBatch:
    """Helper class for managing embedding batches"""
    
    def __init__(self, embedding_service: EmbeddingService):
        self.service = embedding_service
        self.texts: List[str] = []
        self.ids: List[str] = []
    
    def add(self, text: str, id: str):
        """Add text and ID to batch"""
        self.texts.append(text)
        self.ids.append(id)
    
    async def process(self) -> List[tuple[str, np.ndarray]]:
        """Process all texts in batch and return (id, embedding) pairs"""
        if not self.texts:
            return []
        
        embeddings = await self.service.embed_texts(self.texts)
        return list(zip(self.ids, embeddings))
    
    def clear(self):
        """Clear the batch"""
        self.texts.clear()
        self.ids.clear()
    
    def size(self) -> int:
        """Get number of items in batch"""
        return len(self.texts)
    
    def is_empty(self) -> bool:
        """Check if batch is empty"""
        return len(self.texts) == 0