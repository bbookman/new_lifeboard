import faiss
import numpy as np
import json
import os
import threading
import logging
from typing import List, Tuple, Dict, Optional
from config.models import VectorStoreConfig


logger = logging.getLogger(__name__)


class VectorStoreService:
    """FAISS-based vector store for similarity search with namespaced ID management"""
    
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.index: Optional[faiss.Index] = None
        self.id_to_vector_id: Dict[str, int] = {}  # namespaced_id -> vector_id
        self.vector_id_to_id: Dict[int, str] = {}  # vector_id -> namespaced_id
        self.next_vector_id = 0
        self.operation_count = 0
        self.lock = threading.Lock()
        self.dimension: Optional[int] = None
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create new one"""
        try:
            if os.path.exists(self.config.index_path) and os.path.exists(self.config.id_map_path):
                self._load_index()
                logger.info(f"Loaded existing vector store with {len(self.id_to_vector_id)} vectors")
            else:
                logger.info("Creating new vector store")
                # Will create index when first vector is added
                
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            logger.info("Creating new vector store")
            self.index = None
    
    def _load_index(self):
        """Load FAISS index and ID mappings from disk"""
        # Load FAISS index
        self.index = faiss.read_index(self.config.index_path)
        self.dimension = self.index.d
        
        # Load ID mappings
        with open(self.config.id_map_path, 'r') as f:
            data = json.load(f)
            
        # Convert string keys back to integers for vector_id_to_id
        self.id_to_vector_id = data['id_to_vector_id']
        self.vector_id_to_id = {int(k): v for k, v in data['vector_id_to_id'].items()}
        self.next_vector_id = data['next_vector_id']
        
        logger.info(f"Loaded vector store: {self.index.ntotal} vectors, dimension {self.dimension}")
    
    def _create_index(self, dimension: int):
        """Create a new FAISS index"""
        self.dimension = dimension
        
        # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(dimension)
        
        logger.info(f"Created new FAISS index with dimension {dimension}")
    
    def add_vector(self, namespaced_id: str, vector: np.ndarray) -> bool:
        """Add vector with namespaced ID"""
        if vector.ndim != 1:
            raise ValueError("Vector must be 1-dimensional")
        
        # Normalize vector for cosine similarity
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        with self.lock:
            try:
                # Create index if it doesn't exist
                if self.index is None:
                    self._create_index(len(vector))
                elif len(vector) != self.dimension:
                    raise ValueError(f"Vector dimension {len(vector)} doesn't match index dimension {self.dimension}")
                
                # Check if ID already exists
                if namespaced_id in self.id_to_vector_id:
                    logger.warning(f"Updating existing vector for ID: {namespaced_id}")
                    return self.update_vector(namespaced_id, vector)
                
                # Add to FAISS index
                vector_id = self.next_vector_id
                self.index.add(vector.reshape(1, -1).astype(np.float32))
                
                # Update mappings
                self.id_to_vector_id[namespaced_id] = vector_id
                self.vector_id_to_id[vector_id] = namespaced_id
                self.next_vector_id += 1
                self.operation_count += 1
                
                # Auto-save based on activity
                if self.operation_count >= self.config.save_threshold:
                    self.save_index()
                    self.operation_count = 0
                
                return True
                
            except Exception as e:
                logger.error(f"Error adding vector for {namespaced_id}: {e}")
                return False
    
    def update_vector(self, namespaced_id: str, vector: np.ndarray) -> bool:
        """Update existing vector (removes old, adds new)"""
        with self.lock:
            try:
                if namespaced_id not in self.id_to_vector_id:
                    logger.warning(f"Vector {namespaced_id} not found for update, adding as new")
                    return self.add_vector(namespaced_id, vector)
                
                # For simplicity, we'll rebuild the index
                # In production, you might want a more sophisticated approach
                old_vector_id = self.id_to_vector_id[namespaced_id]
                
                # Remove from mappings
                del self.id_to_vector_id[namespaced_id]
                del self.vector_id_to_id[old_vector_id]
                
                # Rebuild index without the old vector
                self._rebuild_index_excluding(old_vector_id)
                
                # Add new vector
                return self.add_vector(namespaced_id, vector)
                
            except Exception as e:
                logger.error(f"Error updating vector for {namespaced_id}: {e}")
                return False
    
    def _rebuild_index_excluding(self, exclude_vector_id: int):
        """Rebuild index excluding a specific vector ID"""
        if self.index is None or self.index.ntotal == 0:
            return
        
        # Get all vectors except the excluded one
        all_vectors = []
        valid_mappings = {}
        new_vector_id = 0
        
        for old_vector_id, namespaced_id in self.vector_id_to_id.items():
            if old_vector_id != exclude_vector_id:
                # Reconstruct vector from index (this is approximate for some index types)
                vector = self.index.reconstruct(old_vector_id)
                all_vectors.append(vector)
                valid_mappings[namespaced_id] = new_vector_id
                new_vector_id += 1
        
        # Create new index
        if all_vectors:
            vectors_array = np.vstack(all_vectors)
            self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(vectors_array.astype(np.float32))
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
        
        # Update mappings
        self.id_to_vector_id = valid_mappings
        self.vector_id_to_id = {v: k for k, v in valid_mappings.items()}
        self.next_vector_id = new_vector_id
    
    def remove_vector(self, namespaced_id: str) -> bool:
        """Remove vector by namespaced ID"""
        with self.lock:
            try:
                if namespaced_id not in self.id_to_vector_id:
                    logger.warning(f"Vector {namespaced_id} not found for removal")
                    return False
                
                vector_id = self.id_to_vector_id[namespaced_id]
                
                # Remove from mappings
                del self.id_to_vector_id[namespaced_id]
                del self.vector_id_to_id[vector_id]
                
                # Rebuild index without this vector
                self._rebuild_index_excluding(vector_id)
                
                self.operation_count += 1
                
                # Auto-save
                if self.operation_count >= self.config.save_threshold:
                    self.save_index()
                    self.operation_count = 0
                
                return True
                
            except Exception as e:
                logger.error(f"Error removing vector {namespaced_id}: {e}")
                return False
    
    def search(self, query_vector: np.ndarray, k: int = 10, 
               namespace_filter: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Search vectors and return namespaced IDs with similarity scores"""
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Normalize query vector
        norm = np.linalg.norm(query_vector)
        if norm > 0:
            query_vector = query_vector / norm
        
        with self.lock:
            try:
                # Search with larger k if we need to filter by namespace
                search_k = k * 3 if namespace_filter else k
                search_k = min(search_k, self.index.ntotal)
                
                distances, indices = self.index.search(
                    query_vector.reshape(1, -1).astype(np.float32), 
                    search_k
                )
                
                results = []
                for i, (score, vector_id) in enumerate(zip(distances[0], indices[0])):
                    if vector_id == -1:  # No more results
                        break
                    
                    namespaced_id = self.vector_id_to_id.get(vector_id)
                    if namespaced_id:
                        # Apply namespace filter if specified
                        if namespace_filter:
                            namespace = namespaced_id.split(':', 1)[0]
                            if namespace not in namespace_filter:
                                continue
                        
                        # Convert inner product back to similarity score (0-1 range)
                        similarity = max(0.0, float(score))  # Ensure non-negative
                        results.append((namespaced_id, similarity))
                        
                        if len(results) >= k:
                            break
                
                return results
                
            except Exception as e:
                logger.error(f"Error during vector search: {e}")
                return []
    
    def get_vector(self, namespaced_id: str) -> Optional[np.ndarray]:
        """Retrieve vector by namespaced ID"""
        with self.lock:
            try:
                if namespaced_id not in self.id_to_vector_id:
                    return None
                
                vector_id = self.id_to_vector_id[namespaced_id]
                vector = self.index.reconstruct(vector_id)
                return vector
                
            except Exception as e:
                logger.error(f"Error retrieving vector {namespaced_id}: {e}")
                return None
    
    def save_index(self):
        """Save FAISS index and ID mappings to disk"""
        try:
            # Ensure directories exist
            os.makedirs(os.path.dirname(self.config.index_path), exist_ok=True)
            os.makedirs(os.path.dirname(self.config.id_map_path), exist_ok=True)
            
            # Save FAISS index
            if self.index is not None:
                faiss.write_index(self.index, self.config.index_path)
            
            # Save ID mappings
            with open(self.config.id_map_path, 'w') as f:
                json.dump({
                    'id_to_vector_id': self.id_to_vector_id,
                    'vector_id_to_id': {str(k): v for k, v in self.vector_id_to_id.items()},
                    'next_vector_id': self.next_vector_id
                }, f, indent=2)
            
            logger.info(f"Saved vector store with {len(self.id_to_vector_id)} vectors")
            
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")
            raise
    
    def get_stats(self) -> Dict[str, any]:
        """Get vector store statistics"""
        with self.lock:
            return {
                'total_vectors': len(self.id_to_vector_id),
                'dimension': self.dimension,
                'next_vector_id': self.next_vector_id,
                'operation_count': self.operation_count,
                'index_path': self.config.index_path,
                'id_map_path': self.config.id_map_path,
                'save_threshold': self.config.save_threshold
            }
    
    def get_namespaces(self) -> List[str]:
        """Get list of unique namespaces in the vector store"""
        namespaces = set()
        for namespaced_id in self.id_to_vector_id.keys():
            namespace = namespaced_id.split(':', 1)[0]
            namespaces.add(namespace)
        return sorted(list(namespaces))
    
    def get_namespace_count(self, namespace: str) -> int:
        """Get count of vectors for a specific namespace"""
        count = 0
        for namespaced_id in self.id_to_vector_id.keys():
            if namespaced_id.startswith(f"{namespace}:"):
                count += 1
        return count
    
    def clear_namespace(self, namespace: str) -> int:
        """Remove all vectors from a specific namespace"""
        removed_count = 0
        ids_to_remove = []
        
        for namespaced_id in self.id_to_vector_id.keys():
            if namespaced_id.startswith(f"{namespace}:"):
                ids_to_remove.append(namespaced_id)
        
        for namespaced_id in ids_to_remove:
            if self.remove_vector(namespaced_id):
                removed_count += 1
        
        return removed_count
    
    def cleanup(self):
        """Clean up resources and save index"""
        try:
            if self.operation_count > 0:
                self.save_index()
            logger.info("Vector store cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during vector store cleanup: {e}")


class VectorBatch:
    """Helper class for batch vector operations"""
    
    def __init__(self, vector_store: VectorStoreService):
        self.vector_store = vector_store
        self.vectors: List[Tuple[str, np.ndarray]] = []
    
    def add(self, namespaced_id: str, vector: np.ndarray):
        """Add vector to batch"""
        self.vectors.append((namespaced_id, vector))
    
    def commit(self) -> List[bool]:
        """Commit all vectors in batch"""
        results = []
        for namespaced_id, vector in self.vectors:
            success = self.vector_store.add_vector(namespaced_id, vector)
            results.append(success)
        return results
    
    def clear(self):
        """Clear the batch"""
        self.vectors.clear()
    
    def size(self) -> int:
        """Get number of vectors in batch"""
        return len(self.vectors)