import numpy as np
import json
import os
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Simple vector store service using numpy and JSON for storage"""
    
    def __init__(self, config):
        self.config = config
        self.vectors = {}  # id -> vector mapping
        self.id_to_index = {}  # id -> index mapping  
        self.index_to_id = {}  # index -> id mapping
        self.dimension = None
        self.next_index = 0
        
        # Load existing data if available
        self._load_index()
    
    def _load_index(self):
        """Load existing vector index"""
        try:
            if os.path.exists(self.config.id_map_path):
                with open(self.config.id_map_path, 'r') as f:
                    data = json.load(f)
                    self.id_to_index = data.get('id_to_index', {})
                    self.index_to_id = data.get('index_to_id', {})
                    self.next_index = data.get('next_index', 0)
                    self.dimension = data.get('dimension')
            
            # Load vectors if they exist
            if os.path.exists(self.config.index_path):
                vectors_array = np.load(self.config.index_path)
                for i, vector in enumerate(vectors_array):
                    if str(i) in self.index_to_id:
                        vector_id = self.index_to_id[str(i)]
                        self.vectors[vector_id] = vector
                        
        except Exception as e:
            logger.warning(f"Could not load existing index: {e}")
    
    def _save_index(self):
        """Save vector index to disk"""
        try:
            # Save ID mappings
            data = {
                'id_to_index': self.id_to_index,
                'index_to_id': self.index_to_id,
                'next_index': self.next_index,
                'dimension': self.dimension
            }
            
            # Create directory if needed
            id_map_dir = os.path.dirname(self.config.id_map_path)
            if id_map_dir:  # Only create if there's actually a directory path
                os.makedirs(id_map_dir, exist_ok=True)
            
            with open(self.config.id_map_path, 'w') as f:
                json.dump(data, f)
            
            # Save vectors as numpy array
            if self.vectors:
                vectors_list = []
                for i in range(self.next_index):
                    if str(i) in self.index_to_id:
                        vector_id = self.index_to_id[str(i)]
                        if vector_id in self.vectors:
                            vectors_list.append(self.vectors[vector_id])
                        else:
                            # Placeholder for deleted vectors
                            vectors_list.append(np.zeros(self.dimension, dtype=np.float32))
                    else:
                        vectors_list.append(np.zeros(self.dimension, dtype=np.float32))
                
                if vectors_list:
                    vectors_array = np.array(vectors_list)
                    
                    # Create directory if needed
                    index_dir = os.path.dirname(self.config.index_path)
                    if index_dir:  # Only create if there's actually a directory path
                        os.makedirs(index_dir, exist_ok=True)
                    
                    np.save(self.config.index_path, vectors_array)
                    
        except Exception as e:
            logger.error(f"Could not save index: {e}")
    
    def _should_rebuild_for_new_dimension(self, new_dimension: int) -> bool:
        """Determine if vector store should be rebuilt for new dimension"""
        # Always allow rebuild if configured dimension matches
        if hasattr(self.config, 'dimension') and new_dimension == self.config.dimension:
            logger.info(f"Dimension {new_dimension} matches config - allowing rebuild")
            return True
        
        # Allow rebuild if store is empty or has very few vectors
        if len(self.vectors) <= 5:
            logger.info(f"Vector store has {len(self.vectors)} vectors - allowing rebuild")
            return True
            
        # Check if auto-migration is enabled
        if hasattr(self.config, 'allow_dimension_migration') and self.config.allow_dimension_migration:
            logger.info("Auto-migration enabled in config - allowing rebuild")
            return True
            
        logger.warning("Dimension rebuild not allowed - store has data and migration disabled")
        return False
    
    def _rebuild_for_new_dimension(self, new_dimension: int):
        """Rebuild vector store for new embedding dimension"""
        logger.info(f"Starting vector store rebuild: {self.dimension}D → {new_dimension}D")
        
        # Backup existing files if they exist
        if os.path.exists(self.config.index_path):
            backup_path = f"{self.config.index_path}.backup"
            try:
                os.rename(self.config.index_path, backup_path)
                logger.info(f"Backed up vector index to {backup_path}")
            except Exception as e:
                logger.warning(f"Could not backup vector index: {e}")
        
        if os.path.exists(self.config.id_map_path):
            backup_path = f"{self.config.id_map_path}.backup"
            try:
                os.rename(self.config.id_map_path, backup_path)
                logger.info(f"Backed up ID map to {backup_path}")
            except Exception as e:
                logger.warning(f"Could not backup ID map: {e}")
        
        # Clear current state
        old_count = len(self.vectors)
        self.vectors.clear()
        self.id_to_index.clear()
        self.index_to_id.clear()
        self.next_index = 0
        self.dimension = new_dimension
        
        logger.info(f"Vector store rebuilt - cleared {old_count} vectors, ready for {new_dimension}D embeddings")
    
    def add_vector(self, vector_id: str, vector: np.ndarray) -> bool:
        """Add a vector to the store"""
        try:
            vector = np.array(vector, dtype=np.float32)
            
            # Set dimension on first vector
            if self.dimension is None:
                self.dimension = vector.shape[0]
                logger.info(f"Vector store initialized with dimension {self.dimension}")
            elif vector.shape[0] != self.dimension:
                logger.warning(f"Vector dimension mismatch: {vector.shape[0]} vs expected {self.dimension}")
                
                # Check if we should rebuild for new dimension
                if self._should_rebuild_for_new_dimension(vector.shape[0]):
                    logger.info(f"Auto-rebuilding vector store for new dimension {vector.shape[0]}")
                    self._rebuild_for_new_dimension(vector.shape[0])
                else:
                    logger.error(f"Cannot add vector - dimension mismatch not allowed")
                    return False
            
            # Add or update vector
            if vector_id not in self.id_to_index:
                # New vector
                index = self.next_index
                self.id_to_index[vector_id] = index
                self.index_to_id[str(index)] = vector_id
                self.next_index += 1
            
            self.vectors[vector_id] = vector
            self._save_index()
            return True
            
        except Exception as e:
            logger.error(f"Error adding vector {vector_id}: {e}")
            return False
    
    def remove_vector(self, vector_id: str) -> bool:
        """Remove a vector from the store"""
        try:
            if vector_id in self.vectors:
                index = self.id_to_index[vector_id]
                del self.vectors[vector_id]
                del self.id_to_index[vector_id]
                del self.index_to_id[str(index)]
                self._save_index()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing vector {vector_id}: {e}")
            return False
    
    def search(self, query_vector: np.ndarray, k: int = 10, 
               namespace_filter: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Search for similar vectors"""
        try:
            logger.debug(f"Vector Debug - Starting search with k={k}, namespace_filter={namespace_filter}")
            logger.debug(f"Vector Debug - Total vectors in store: {len(self.vectors)}")
            
            if not self.vectors:
                logger.info("Vector Debug - No vectors in store, returning empty results")
                return []
            
            query_vector = np.array(query_vector, dtype=np.float32)
            logger.debug(f"Vector Debug - Query vector dimension: {query_vector.shape[0]}")
            
            results = []
            filtered_count = 0
            for vector_id, vector in self.vectors.items():
                # Apply namespace filter if provided
                if namespace_filter:
                    namespace = vector_id.split(':', 1)[0] if ':' in vector_id else vector_id
                    if namespace not in namespace_filter:
                        filtered_count += 1
                        continue
                
                # Calculate cosine similarity
                similarity = np.dot(query_vector, vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(vector)
                )
                results.append((vector_id, float(similarity)))
            
            logger.debug(f"Vector Debug - Considered {len(results)} vectors (filtered out {filtered_count})")
            
            # Sort by similarity and return top k
            results.sort(key=lambda x: x[1], reverse=True)
            top_results = results[:k]
            
            logger.info(f"Vector Debug - Returning {len(top_results)} results out of {len(results)} candidates")
            
            # Log top results for debugging
            for i, (vector_id, score) in enumerate(top_results[:3]):
                logger.debug(f"Vector Debug - Result {i+1}: {vector_id} (similarity: {score:.4f})")
            
            return top_results
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            'total_vectors': len(self.vectors),
            'dimension': self.dimension,
            'index_path': self.config.index_path,
            'id_map_path': self.config.id_map_path
        }
    
    def cleanup(self):
        """Clean up resources"""
        pass