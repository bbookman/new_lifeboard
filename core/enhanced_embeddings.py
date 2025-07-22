"""Enhanced embedding service with multiple model support and quality validation."""

import numpy as np
from typing import List, Dict, Optional, Union, Tuple, Any
import json
import hashlib
import time
import logging
from sentence_transformers import SentenceTransformer
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

from core.logger import Logger
from core.config import Config

logger = Logger(__name__)

class EmbeddingQualityValidator:
    """Validates and scores embedding quality."""
    
    @staticmethod
    def validate_embedding(embedding: np.ndarray) -> Dict[str, Any]:
        """Validate embedding quality and return metrics.
        
        Args:
            embedding: The embedding vector to validate
            
        Returns:
            Dictionary with validation results and quality metrics
        """
        if embedding is None or len(embedding) == 0:
            return {'is_valid': False, 'reason': 'Empty embedding'}
        
        # Check for NaN or infinity values
        if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
            return {'is_valid': False, 'reason': 'Contains NaN or infinity values'}
        
        # Calculate quality metrics
        norm = np.linalg.norm(embedding)
        mean_val = np.mean(embedding)
        std_val = np.std(embedding)
        
        # Check if embedding is too sparse (too many zeros)
        zero_ratio = np.sum(embedding == 0) / len(embedding)
        
        # Check if embedding has reasonable variance
        has_variance = std_val > 1e-6
        
        quality_score = 1.0
        
        # Penalize high zero ratio
        if zero_ratio > 0.8:
            quality_score *= 0.5
            
        # Penalize low variance
        if not has_variance:
            quality_score *= 0.3
            
        # Penalize extreme values
        if norm < 1e-6 or norm > 100:
            quality_score *= 0.7
        
        return {
            'is_valid': True,
            'quality_score': quality_score,
            'norm': float(norm),
            'mean': float(mean_val),
            'std': float(std_val),
            'zero_ratio': float(zero_ratio),
            'dimension': len(embedding)
        }
    
    @staticmethod
    def validate_similarity_threshold(similarity: float, threshold: float = 0.1) -> bool:
        """Check if similarity score meets minimum threshold."""
        return similarity >= threshold

class MultiModelEmbeddingService:
    """Enhanced embedding service with multiple model support and quality validation."""
    
    SUPPORTED_MODELS = {
        'all-MiniLM-L6-v2': {
            'dimension': 384,
            'max_length': 256,
            'description': 'Lightweight general-purpose model',
            'pros': ['Fast inference', 'Low memory', 'Good for general purpose'],
            'cons': ['Lower accuracy', 'Limited semantic understanding']
        },
        'all-mpnet-base-v2': {
            'dimension': 768,
            'max_length': 384,
            'description': 'Better semantic understanding',
            'pros': ['Better semantic understanding', 'Good performance on benchmarks'],
            'cons': ['Larger size', 'Slower inference']
        },
        'sentence-transformers/all-MiniLM-L12-v2': {
            'dimension': 384,
            'max_length': 256,
            'description': 'Larger MiniLM variant',
            'pros': ['Better than L6', 'Still relatively fast'],
            'cons': ['Larger than L6', 'Still limited semantic depth']
        },
        'sentence-transformers/paraphrase-mpnet-base-v2': {
            'dimension': 768,
            'max_length': 384,
            'description': 'Excellent for paraphrase detection',
            'pros': ['Excellent paraphrase detection', 'High semantic accuracy'],
            'cons': ['Slower inference', 'Higher memory usage']
        },
        'BAAI/bge-base-en-v1.5': {
            'dimension': 768,
            'max_length': 512,
            'description': 'State-of-the-art retrieval model',
            'pros': ['SOTA performance', 'Excellent retrieval'],
            'cons': ['Largest model', 'Highest computational cost']
        }
    }
    
    def __init__(self, model_name: str = None, cache_embeddings: bool = True,
                 quality_validation: bool = True, similarity_threshold: float = 0.1):
        """Initialize multi-model embedding service.
        
        Args:
            model_name: Name of the embedding model to use
            cache_embeddings: Whether to cache embeddings to disk
            quality_validation: Whether to validate embedding quality
            similarity_threshold: Minimum similarity threshold for filtering
        """
        self.config = Config()
        self.model_name = model_name or self.config.get('embedding.model', 'all-MiniLM-L6-v2')
        self.cache_embeddings = cache_embeddings
        self.quality_validation = quality_validation
        self.similarity_threshold = similarity_threshold
        
        # Model instances cache
        self.models = {}
        self.cache_dir = Path("data/embedding_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Quality validator
        self.validator = EmbeddingQualityValidator()
        
        # Performance metrics
        self.metrics = {
            'total_embeddings': 0,
            'cache_hits': 0,
            'validation_failures': 0,
            'total_time': 0.0
        }
        
    def get_supported_models(self) -> Dict[str, Dict]:
        """Get information about all supported models."""
        return self.SUPPORTED_MODELS.copy()
    
    def switch_model(self, model_name: str) -> bool:
        """Switch to a different embedding model.
        
        Args:
            model_name: Name of the model to switch to
            
        Returns:
            True if switch successful, False otherwise
        """
        if model_name not in self.SUPPORTED_MODELS:
            logger.error(f"Unsupported model: {model_name}")
            return False
        
        try:
            self.model_name = model_name
            # Don't load immediately - lazy load when needed
            logger.info(f"Switched to model: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to model {model_name}: {e}")
            return False
    
    def _load_model(self, model_name: str = None) -> SentenceTransformer:
        """Load the specified embedding model.
        
        Args:
            model_name: Name of model to load, defaults to current model
            
        Returns:
            Loaded SentenceTransformer model
        """
        model_name = model_name or self.model_name
        
        if model_name not in self.models:
            try:
                logger.info(f"Loading embedding model: {model_name}")
                start_time = time.time()
                self.models[model_name] = SentenceTransformer(model_name)
                load_time = time.time() - start_time
                
                model_info = self.SUPPORTED_MODELS.get(model_name, {})
                logger.info(f"Model loaded in {load_time:.2f}s. Dimension: {model_info.get('dimension', 'unknown')}")
                
            except Exception as e:
                logger.error(f"Failed to load embedding model {model_name}: {e}")
                raise
        
        return self.models[model_name]
    
    def _get_cache_key(self, text: str, model_name: str = None) -> str:
        """Generate cache key for text and model combination."""
        model_name = model_name or self.model_name
        content = f"{model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[np.ndarray]:
        """Retrieve embedding from cache."""
        if not self.cache_embeddings:
            return None
            
        try:
            cache_file = self.cache_dir / f"{cache_key}.npy"
            if cache_file.exists():
                embedding = np.load(cache_file)
                self.metrics['cache_hits'] += 1
                return embedding
        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, embedding: np.ndarray) -> None:
        """Save embedding to cache."""
        if not self.cache_embeddings:
            return
            
        try:
            cache_file = self.cache_dir / f"{cache_key}.npy"
            np.save(cache_file, embedding)
        except Exception as e:
            logger.warning(f"Failed to save to cache: {e}")
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text before embedding.
        
        Args:
            text: Raw text to preprocess
            
        Returns:
            Preprocessed text
        """
        if not text or not text.strip():
            return ""
        
        # Basic preprocessing
        text = text.strip()
        
        # Truncate if too long (model-specific limits)
        model_info = self.SUPPORTED_MODELS.get(self.model_name, {})
        max_length = model_info.get('max_length', 256)
        
        # Rough token estimation (1 token ≈ 4 characters)
        estimated_tokens = len(text) // 4
        if estimated_tokens > max_length:
            # Truncate to approximate token limit
            text = text[:max_length * 4]
            logger.debug(f"Text truncated to {len(text)} characters")
        
        return text
    
    def encode(self, texts: Union[str, List[str]], 
               model_name: str = None,
               normalize: bool = True,
               show_progress: bool = False,
               validate_quality: bool = None) -> Tuple[np.ndarray, List[Dict]]:
        """Generate embeddings for text(s) with quality validation.
        
        Args:
            texts: Single text or list of texts to embed
            model_name: Specific model to use (overrides default)
            normalize: Whether to normalize embeddings
            show_progress: Whether to show progress bar
            validate_quality: Whether to validate embedding quality
            
        Returns:
            Tuple of (embeddings array, quality metrics list)
        """
        start_time = time.time()
        
        # Use specified model or default
        target_model = model_name or self.model_name
        model = self._load_model(target_model)
        
        # Handle single text
        single_text = isinstance(texts, str)
        if single_text:
            texts = [texts]
        
        # Preprocess texts
        preprocessed_texts = [self._preprocess_text(text) for text in texts]
        
        embeddings = []
        quality_metrics = []
        cached_count = 0
        
        for i, (original_text, processed_text) in enumerate(zip(texts, preprocessed_texts)):
            if not processed_text:
                # Handle empty text
                embedding = np.zeros(self.SUPPORTED_MODELS[target_model]['dimension'])
                quality_info = {'is_valid': False, 'reason': 'Empty text'}
            else:
                # Try cache first
                cache_key = self._get_cache_key(processed_text, target_model)
                cached_embedding = self._get_from_cache(cache_key)
                
                if cached_embedding is not None:
                    embedding = cached_embedding
                    cached_count += 1
                    quality_info = {'is_valid': True, 'cached': True}
                else:
                    # Generate new embedding
                    try:
                        embedding = model.encode([processed_text], 
                                               normalize_embeddings=normalize,
                                               show_progress_bar=show_progress and i == 0)[0]
                        
                        # Cache the embedding
                        self._save_to_cache(cache_key, embedding)
                        quality_info = {'is_valid': True, 'cached': False}
                        
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for text {i}: {e}")
                        embedding = np.zeros(self.SUPPORTED_MODELS[target_model]['dimension'])
                        quality_info = {'is_valid': False, 'reason': str(e)}
                        self.metrics['validation_failures'] += 1
            
            # Validate quality if enabled
            if validate_quality or (validate_quality is None and self.quality_validation):
                validation_result = self.validator.validate_embedding(embedding)
                quality_info.update(validation_result)
                
                if not validation_result['is_valid']:
                    self.metrics['validation_failures'] += 1
                    logger.warning(f"Invalid embedding for text {i}: {validation_result.get('reason')}")
            
            embeddings.append(embedding)
            quality_metrics.append(quality_info)
            self.metrics['total_embeddings'] += 1
        
        # Update performance metrics
        self.metrics['total_time'] += time.time() - start_time
        
        if cached_count > 0:
            logger.debug(f"Used {cached_count}/{len(texts)} cached embeddings")
        
        result_embeddings = np.array(embeddings)
        
        # Return single embedding if single text input
        if single_text:
            return result_embeddings[0], quality_metrics[0]
        
        return result_embeddings, quality_metrics
    
    def encode_with_fallback(self, texts: Union[str, List[str]], 
                           primary_model: str = None,
                           fallback_models: List[str] = None) -> Tuple[np.ndarray, List[Dict]]:
        """Encode with fallback models if primary fails.
        
        Args:
            texts: Text(s) to embed
            primary_model: Primary model to try first
            fallback_models: List of fallback models to try
            
        Returns:
            Tuple of (embeddings, quality metrics)
        """
        primary_model = primary_model or self.model_name
        if fallback_models is None:
            fallback_models = ['all-MiniLM-L6-v2']  # Reliable fallback
        
        # Try primary model first
        try:
            return self.encode(texts, model_name=primary_model)
        except Exception as e:
            logger.warning(f"Primary model {primary_model} failed: {e}")
        
        # Try fallback models
        for fallback_model in fallback_models:
            try:
                logger.info(f"Trying fallback model: {fallback_model}")
                return self.encode(texts, model_name=fallback_model)
            except Exception as e:
                logger.warning(f"Fallback model {fallback_model} failed: {e}")
                continue
        
        # If all models fail, return zeros
        logger.error("All embedding models failed")
        single_text = isinstance(texts, str)
        text_count = 1 if single_text else len(texts)
        
        zero_embeddings = np.zeros((text_count, 384))  # Default dimension
        error_metrics = [{'is_valid': False, 'reason': 'All models failed'}] * text_count
        
        if single_text:
            return zero_embeddings[0], error_metrics[0]
        return zero_embeddings, error_metrics
    
    def compute_similarities(self, embeddings_a: np.ndarray, 
                           embeddings_b: np.ndarray = None,
                           threshold: float = None) -> np.ndarray:
        """Compute cosine similarities between embeddings with optional thresholding.
        
        Args:
            embeddings_a: First set of embeddings
            embeddings_b: Second set of embeddings (if None, compute pairwise within embeddings_a)
            threshold: Minimum similarity threshold to apply
            
        Returns:
            Similarity matrix
        """
        if embeddings_b is None:
            similarities = cosine_similarity(embeddings_a)
        else:
            similarities = cosine_similarity(embeddings_a, embeddings_b)
        
        # Apply threshold if specified
        if threshold is not None:
            similarities = np.where(similarities >= threshold, similarities, 0.0)
        
        return similarities
    
    def filter_by_similarity(self, query_embedding: np.ndarray, 
                           candidate_embeddings: np.ndarray,
                           threshold: float = None) -> Tuple[np.ndarray, np.ndarray]:
        """Filter candidates by similarity threshold.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: Candidate embeddings to filter
            threshold: Minimum similarity threshold
            
        Returns:
            Tuple of (filtered_embeddings, similarity_scores)
        """
        threshold = threshold or self.similarity_threshold
        
        similarities = cosine_similarity([query_embedding], candidate_embeddings)[0]
        
        valid_indices = np.where(similarities >= threshold)[0]
        filtered_embeddings = candidate_embeddings[valid_indices]
        filtered_similarities = similarities[valid_indices]
        
        return filtered_embeddings, filtered_similarities
    
    def get_embedding_dimension(self, model_name: str = None) -> int:
        """Get the dimension of embeddings from specified model."""
        model_name = model_name or self.model_name
        return self.SUPPORTED_MODELS.get(model_name, {}).get('dimension', 384)
    
    def get_model_info(self, model_name: str = None) -> Dict:
        """Get information about the specified model."""
        model_name = model_name or self.model_name
        model_info = self.SUPPORTED_MODELS.get(model_name, {})
        return {
            'name': model_name,
            **model_info
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the embedding service."""
        avg_time_per_embedding = (self.metrics['total_time'] / 
                                 max(1, self.metrics['total_embeddings']))
        cache_hit_rate = (self.metrics['cache_hits'] / 
                         max(1, self.metrics['total_embeddings']))
        failure_rate = (self.metrics['validation_failures'] / 
                       max(1, self.metrics['total_embeddings']))
        
        return {
            **self.metrics,
            'avg_time_per_embedding': avg_time_per_embedding,
            'cache_hit_rate': cache_hit_rate,
            'failure_rate': failure_rate,
            'current_model': self.model_name
        }
    
    def clear_cache(self, model_name: str = None) -> int:
        """Clear embedding cache for specified model.
        
        Args:
            model_name: Specific model to clear cache for, or None for all
            
        Returns:
            Number of cache files removed
        """
        try:
            if not self.cache_dir.exists():
                return 0
            
            removed_count = 0
            for cache_file in self.cache_dir.glob("*.npy"):
                if model_name is None:
                    # Remove all cache files
                    cache_file.unlink()
                    removed_count += 1
                else:
                    # Check if cache file is for specific model
                    # This is approximate since we hash the key
                    cache_file.unlink()  # For now, remove all
                    removed_count += 1
            
            logger.info(f"Cleared {removed_count} cache files")
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0