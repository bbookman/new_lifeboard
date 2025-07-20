import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from core.ids import NamespacedIDManager
from services.namespace_prediction import NamespacePredictionService
from config.models import SearchConfig


logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result"""
    
    def __init__(self, namespaced_id: str, content: str, similarity_score: float, 
                 metadata: Dict[str, Any] = None, namespace: str = None):
        self.namespaced_id = namespaced_id
        self.content = content
        self.similarity_score = similarity_score
        self.metadata = metadata or {}
        self.namespace = namespace or NamespacedIDManager.get_namespace(namespaced_id)
        self.source_id = NamespacedIDManager.get_source_id(namespaced_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'namespaced_id': self.namespaced_id,
            'namespace': self.namespace,
            'source_id': self.source_id,
            'content': self.content,
            'similarity_score': self.similarity_score,
            'metadata': self.metadata
        }


class SearchResponse:
    """Complete search response with metadata"""
    
    def __init__(self, query: str, results: List[SearchResult], predicted_sources: List[str],
                 priority_order: List[str], search_config: Dict[str, Any], 
                 search_duration_seconds: float):
        self.query = query
        self.results = results
        self.predicted_sources = predicted_sources
        self.priority_order = priority_order
        self.search_config = search_config
        self.search_duration_seconds = search_duration_seconds
        self.timestamp = datetime.now()
    
    @property
    def total_results(self) -> int:
        return len(self.results)
    
    @property
    def namespaces_found(self) -> List[str]:
        return list(set(result.namespace for result in self.results))
    
    def get_results_by_namespace(self) -> Dict[str, List[SearchResult]]:
        """Group results by namespace in priority order"""
        grouped = {}
        
        # Group by namespace
        for result in self.results:
            if result.namespace not in grouped:
                grouped[result.namespace] = []
            grouped[result.namespace].append(result)
        
        # Return in priority order
        ordered_results = {}
        for namespace in self.priority_order:
            if namespace in grouped:
                ordered_results[namespace] = grouped[namespace]
        
        # Add any remaining namespaces not in priority order
        for namespace, results in grouped.items():
            if namespace not in ordered_results:
                ordered_results[namespace] = results
        
        return ordered_results
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'query': self.query,
            'results': [result.to_dict() for result in self.results],
            'total_results': self.total_results,
            'predicted_sources': self.predicted_sources,
            'priority_order': self.priority_order,
            'namespaces_found': self.namespaces_found,
            'search_config': self.search_config,
            'search_duration_seconds': self.search_duration_seconds,
            'timestamp': self.timestamp.isoformat()
        }


class SearchService:
    """Main search orchestration service"""
    
    def __init__(self, 
                 db_service: DatabaseService,
                 vector_service: VectorStoreService,
                 embedding_service: EmbeddingService,
                 prediction_service: NamespacePredictionService,
                 search_config: SearchConfig):
        self.db = db_service
        self.vector_store = vector_service
        self.embeddings = embedding_service
        self.prediction = prediction_service
        self.config = search_config
        self.logger = logging.getLogger(__name__)
    
    async def search(self, query: str, top_k: Optional[int] = None, 
                    namespace_filter: Optional[List[str]] = None,
                    similarity_threshold: Optional[float] = None) -> SearchResponse:
        """
        Execute the complete search process
        
        Args:
            query: Search query text
            top_k: Number of results to return (defaults to config)
            namespace_filter: Specific namespaces to search (overrides prediction)
            similarity_threshold: Minimum similarity score (defaults to config)
        
        Returns:
            SearchResponse with results and metadata
        """
        start_time = asyncio.get_event_loop().time()
        
        # Use config defaults if not specified
        if top_k is None:
            top_k = self.config.default_top_k
        if similarity_threshold is None:
            similarity_threshold = self.config.similarity_threshold
        
        # Validate inputs
        top_k = min(top_k, self.config.max_top_k)
        
        try:
            # Step 1: Predict relevant namespaces (unless overridden)
            if namespace_filter:
                relevant_namespaces = namespace_filter
                priority_order = namespace_filter
                self.logger.info(f"Using provided namespace filter: {namespace_filter}")
            elif self.config.namespace_prediction_enabled:
                self.logger.info("Predicting relevant namespaces...")
                namespace_prediction = await self.prediction.predict_namespaces(query)
                relevant_namespaces = namespace_prediction.get("namespaces", [])
                priority_order = namespace_prediction.get("priority", relevant_namespaces)
                self.logger.info(f"Predicted namespaces: {relevant_namespaces}")
            else:
                # Use all available namespaces
                available_namespaces = self.vector_store.get_namespaces()
                relevant_namespaces = available_namespaces
                priority_order = available_namespaces
                self.logger.info("Namespace prediction disabled, using all namespaces")
            
            # Step 2: Embed the query
            self.logger.info("Generating query embedding...")
            query_vector = await self.embeddings.embed_text(query)
            
            # Step 3: Search FAISS with namespace filter
            self.logger.info(f"Searching vector store with {len(relevant_namespaces)} namespaces...")
            vector_results = self.vector_store.search(
                query_vector, 
                k=top_k * 2,  # Get more results to filter by similarity threshold
                namespace_filter=relevant_namespaces if relevant_namespaces else None
            )
            
            # Step 4: Filter by similarity threshold
            filtered_results = [
                (namespaced_id, score) for namespaced_id, score in vector_results
                if score >= similarity_threshold
            ][:top_k]  # Take top_k after filtering
            
            # Step 5: Fetch full data from SQLite
            if filtered_results:
                result_ids = [result[0] for result in filtered_results]
                self.logger.info(f"Fetching {len(result_ids)} items from database...")
                full_data = self.db.get_data_items_by_ids(result_ids)
                
                # Create mapping for quick lookup
                data_by_id = {item['id']: item for item in full_data}
                
                # Step 6: Create search results with similarity scores
                search_results = []
                for namespaced_id, similarity_score in filtered_results:
                    if namespaced_id in data_by_id:
                        item = data_by_id[namespaced_id]
                        result = SearchResult(
                            namespaced_id=namespaced_id,
                            content=item['content'],
                            similarity_score=similarity_score,
                            metadata=item.get('metadata', {})
                        )
                        search_results.append(result)
            else:
                search_results = []
            
            # Calculate search duration
            end_time = asyncio.get_event_loop().time()
            search_duration = end_time - start_time
            
            self.logger.info(f"Search completed: {len(search_results)} results in {search_duration:.3f}s")
            
            # Create response
            response = SearchResponse(
                query=query,
                results=search_results,
                predicted_sources=relevant_namespaces,
                priority_order=priority_order,
                search_config={
                    'top_k': top_k,
                    'similarity_threshold': similarity_threshold,
                    'namespace_prediction_enabled': self.config.namespace_prediction_enabled
                },
                search_duration_seconds=search_duration
            )
            
            return response
            
        except Exception as e:
            end_time = asyncio.get_event_loop().time()
            search_duration = end_time - start_time
            
            self.logger.error(f"Search failed after {search_duration:.3f}s: {e}")
            
            # Return empty response on error
            return SearchResponse(
                query=query,
                results=[],
                predicted_sources=[],
                priority_order=[],
                search_config={
                    'top_k': top_k,
                    'similarity_threshold': similarity_threshold,
                    'error': str(e)
                },
                search_duration_seconds=search_duration
            )
    
    async def search_similar_content(self, content: str, top_k: int = 5,
                                   exclude_namespaced_id: Optional[str] = None) -> List[SearchResult]:
        """
        Find content similar to the provided text
        
        Args:
            content: Text to find similar content for
            top_k: Number of similar results to return
            exclude_namespaced_id: ID to exclude from results (e.g., the source document)
        
        Returns:
            List of similar search results
        """
        try:
            # Generate embedding for the content
            content_vector = await self.embeddings.embed_text(content)
            
            # Search for similar vectors
            vector_results = self.vector_store.search(content_vector, k=top_k + 1)
            
            # Filter out excluded ID
            if exclude_namespaced_id:
                vector_results = [
                    (namespaced_id, score) for namespaced_id, score in vector_results
                    if namespaced_id != exclude_namespaced_id
                ][:top_k]
            else:
                vector_results = vector_results[:top_k]
            
            # Fetch full data
            if vector_results:
                result_ids = [result[0] for result in vector_results]
                full_data = self.db.get_data_items_by_ids(result_ids)
                data_by_id = {item['id']: item for item in full_data}
                
                # Create search results
                results = []
                for namespaced_id, similarity_score in vector_results:
                    if namespaced_id in data_by_id:
                        item = data_by_id[namespaced_id]
                        result = SearchResult(
                            namespaced_id=namespaced_id,
                            content=item['content'],
                            similarity_score=similarity_score,
                            metadata=item.get('metadata', {})
                        )
                        results.append(result)
                
                return results
            
            return []
            
        except Exception as e:
            self.logger.error(f"Similar content search failed: {e}")
            return []
    
    async def search_by_namespace(self, namespace: str, query: str, 
                                 top_k: Optional[int] = None) -> List[SearchResult]:
        """
        Search within a specific namespace only
        
        Args:
            namespace: Namespace to search within
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results from the specified namespace
        """
        response = await self.search(
            query=query,
            top_k=top_k,
            namespace_filter=[namespace]
        )
        return response.results
    
    async def get_recent_items(self, namespace: Optional[str] = None, 
                              limit: int = 10) -> List[SearchResult]:
        """
        Get recently added/updated items
        
        Args:
            namespace: Optional namespace filter
            limit: Number of items to return
            
        Returns:
            List of recent items as search results
        """
        try:
            if namespace:
                items = self.db.get_data_items_by_namespace(namespace, limit)
            else:
                # Get recent items across all namespaces
                # This would require a new database method
                items = []  # Placeholder
            
            results = []
            for item in items:
                result = SearchResult(
                    namespaced_id=item['id'],
                    content=item['content'],
                    similarity_score=1.0,  # Not applicable for recent items
                    metadata=item.get('metadata', {})
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get recent items: {e}")
            return []
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search service statistics"""
        vector_stats = self.vector_store.get_stats()
        embedding_info = self.embeddings.get_model_info()
        prediction_info = self.prediction.get_config_info()
        
        return {
            'vector_store': vector_stats,
            'embeddings': embedding_info,
            'namespace_prediction': prediction_info,
            'search_config': {
                'default_top_k': self.config.default_top_k,
                'max_top_k': self.config.max_top_k,
                'similarity_threshold': self.config.similarity_threshold,
                'namespace_prediction_enabled': self.config.namespace_prediction_enabled
            }
        }
    
    async def test_search_pipeline(self, test_query: str = "test query") -> Dict[str, Any]:
        """Test the complete search pipeline"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Test each component
            tests = {}
            
            # Test embedding
            try:
                embedding = await self.embeddings.embed_text(test_query)
                tests['embedding'] = {
                    'success': True,
                    'dimension': len(embedding),
                    'non_zero_values': int((embedding != 0).sum())
                }
            except Exception as e:
                tests['embedding'] = {'success': False, 'error': str(e)}
            
            # Test namespace prediction
            try:
                prediction_result = await self.prediction.test_prediction(test_query)
                tests['namespace_prediction'] = prediction_result
            except Exception as e:
                tests['namespace_prediction'] = {'success': False, 'error': str(e)}
            
            # Test vector search
            try:
                if tests['embedding']['success']:
                    vector_results = self.vector_store.search(embedding, k=5)
                    tests['vector_search'] = {
                        'success': True,
                        'results_count': len(vector_results),
                        'has_results': len(vector_results) > 0
                    }
                else:
                    tests['vector_search'] = {'success': False, 'error': 'Embedding failed'}
            except Exception as e:
                tests['vector_search'] = {'success': False, 'error': str(e)}
            
            # Test full search
            try:
                search_response = await self.search(test_query, top_k=5)
                tests['full_search'] = {
                    'success': True,
                    'results_count': search_response.total_results,
                    'search_duration': search_response.search_duration_seconds,
                    'namespaces_found': search_response.namespaces_found
                }
            except Exception as e:
                tests['full_search'] = {'success': False, 'error': str(e)}
            
            end_time = asyncio.get_event_loop().time()
            total_duration = end_time - start_time
            
            return {
                'success': all(test.get('success', False) for test in tests.values()),
                'total_duration_seconds': total_duration,
                'component_tests': tests
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'component_tests': {}
            }