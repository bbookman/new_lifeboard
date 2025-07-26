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
            
            # Create directory if needed (only if path contains a directory)
            id_map_dir = os.path.dirname(self.config.id_map_path)
            if id_map_dir:  # Only create directory if path is not just a filename
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
                    # Create directory if needed (only if path contains a directory)
                    index_dir = os.path.dirname(self.config.index_path)
                    if index_dir:  # Only create directory if path is not just a filename
                        os.makedirs(index_dir, exist_ok=True)
                    np.save(self.config.index_path, vectors_array)
                    
        except Exception as e:
            logger.error(f"Could not save index: {e}")
    
    def add_vector(self, vector_id: str, vector: np.ndarray) -> bool:
        """Add a vector to the store"""
        try:
            vector = np.array(vector, dtype=np.float32)
            
            # Set dimension on first vector
            if self.dimension is None:
                self.dimension = vector.shape[0]
            elif vector.shape[0] != self.dimension:
                logger.error(f"Vector dimension {vector.shape[0]} doesn't match expected {self.dimension}")
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
            if not self.vectors:
                return []
            
            query_vector = np.array(query_vector, dtype=np.float32)
            
            results = []
            for vector_id, vector in self.vectors.items():
                # Apply namespace filter if provided
                if namespace_filter:
                    namespace = vector_id.split(':', 1)[0] if ':' in vector_id else vector_id
                    if namespace not in namespace_filter:
                        continue
                
                # Calculate cosine similarity
                similarity = np.dot(query_vector, vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(vector)
                )
                results.append((vector_id, float(similarity)))
            
            # Sort by similarity and return top k
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:k]
            
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