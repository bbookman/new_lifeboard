"""
Integration tests for search functionality
"""

import pytest
from services.search import SearchService
from services.ingestion import IngestionService


class TestSearchIntegration:
    """Integration tests for the complete search pipeline"""
    
    @pytest.mark.asyncio
    async def test_search_pipeline_empty_database(self, search_service: SearchService):
        """Test search with empty database"""
        response = await search_service.search("test query")
        
        assert response.query == "test query"
        assert response.total_results == 0
        assert len(response.results) == 0
        assert response.search_duration_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_search_with_data(
        self, 
        search_service: SearchService,
        ingestion_service: IngestionService,
        sample_data: list,
        test_helpers
    ):
        """Test search with populated data"""
        # Populate test data
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Perform search
        response = await search_service.search("machine learning")
        
        assert response.total_results > 0
        assert len(response.results) > 0
        
        # Check result structure
        for result in response.results:
            test_helpers.assert_search_result_valid(result)
        
        # Results should be sorted by similarity (descending)
        if len(response.results) > 1:
            similarities = [r.similarity_score for r in response.results]
            assert similarities == sorted(similarities, reverse=True)
    
    @pytest.mark.asyncio
    async def test_search_with_namespace_filter(
        self,
        search_service: SearchService, 
        ingestion_service: IngestionService,
        sample_data: list,
        test_helpers
    ):
        """Test search with namespace filtering"""
        # Populate test data
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Search with namespace filter
        response = await search_service.search(
            "document",
            namespace_filter=["test"]
        )
        
        # All results should be from 'test' namespace
        for result in response.results:
            assert result.namespace == "test"
    
    @pytest.mark.asyncio
    async def test_search_similarity_threshold(
        self,
        search_service: SearchService,
        ingestion_service: IngestionService, 
        sample_data: list,
        test_helpers
    ):
        """Test search with similarity threshold"""
        # Populate test data  
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Search with high similarity threshold
        response = await search_service.search(
            "completely unrelated query about zebras",
            similarity_threshold=0.8
        )
        
        # Should have fewer or no results due to high threshold
        for result in response.results:
            assert result.similarity_score >= 0.8
    
    @pytest.mark.asyncio
    async def test_search_by_namespace(
        self,
        search_service: SearchService,
        ingestion_service: IngestionService,
        sample_data: list, 
        test_helpers
    ):
        """Test searching within specific namespace"""
        # Populate test data
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Search within specific namespace
        results = await search_service.search_by_namespace("test", "programming")
        
        # All results should be from 'test' namespace
        for result in results:
            assert result.namespace == "test"
    
    @pytest.mark.asyncio
    async def test_similar_content_search(
        self,
        search_service: SearchService,
        ingestion_service: IngestionService,
        sample_data: list,
        test_helpers
    ):
        """Test finding similar content"""
        # Populate test data
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Find content similar to first item
        content = sample_data[0]["content"]
        namespaced_id = f"{sample_data[0]['namespace']}:{sample_data[0]['source_id']}"
        
        similar_results = await search_service.search_similar_content(
            content=content,
            exclude_namespaced_id=namespaced_id,
            top_k=5
        )
        
        # Should not include the original item
        for result in similar_results:
            assert result.namespaced_id != namespaced_id
    
    @pytest.mark.asyncio
    async def test_search_stats(self, search_service: SearchService):
        """Test getting search service statistics"""
        stats = search_service.get_search_stats()
        
        assert 'vector_store' in stats
        assert 'embeddings' in stats
        assert 'namespace_prediction' in stats
        assert 'search_config' in stats
    
    @pytest.mark.asyncio
    async def test_search_pipeline_test(self, search_service: SearchService):
        """Test the search pipeline testing functionality"""
        test_result = await search_service.test_search_pipeline()
        
        assert 'success' in test_result
        assert 'component_tests' in test_result
        assert 'total_duration_seconds' in test_result
        
        # Check individual component tests
        components = test_result['component_tests']
        assert 'embedding' in components
        assert 'namespace_prediction' in components
        assert 'vector_search' in components
        assert 'full_search' in components


class TestSearchPerformance:
    """Performance tests for search functionality"""
    
    @pytest.mark.asyncio
    async def test_search_response_time(
        self,
        search_service: SearchService,
        ingestion_service: IngestionService,
        sample_data: list,
        test_helpers
    ):
        """Test search response time is reasonable"""
        # Populate test data
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Perform search
        response = await search_service.search("test query")
        
        # Response should be reasonably fast (< 2 seconds for small dataset)
        assert response.search_duration_seconds < 2.0
    
    @pytest.mark.asyncio
    async def test_batch_search_performance(
        self,
        search_service: SearchService,
        ingestion_service: IngestionService,
        sample_data: list,
        test_helpers
    ):
        """Test performance with multiple searches"""
        # Populate test data
        await test_helpers.populate_test_data(ingestion_service, sample_data)
        
        # Perform multiple searches
        queries = [
            "machine learning",
            "programming tutorial", 
            "meeting notes",
            "artificial intelligence",
            "data structures"
        ]
        
        total_time = 0
        for query in queries:
            response = await search_service.search(query)
            total_time += response.search_duration_seconds
        
        # Average search time should be reasonable
        avg_time = total_time / len(queries)
        assert avg_time < 1.0  # Less than 1 second per search on average


class TestSearchEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_search_very_long_query(self, search_service: SearchService):
        """Test search with very long query"""
        long_query = "test " * 1000  # 4000+ character query
        response = await search_service.search(long_query)
        
        # Should handle gracefully
        assert response.query == long_query
        assert response.search_duration_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, search_service: SearchService):
        """Test search with empty query"""
        response = await search_service.search("")
        
        # Should handle gracefully
        assert response.query == ""
        assert response.total_results == 0
    
    @pytest.mark.asyncio
    async def test_search_special_characters(self, search_service: SearchService):
        """Test search with special characters"""
        queries = [
            "query with @#$% special chars",
            "unicode: café résumé naïve",
            "emoji: 🚀 🔍 ✨",
        ]
        
        for query in queries:
            response = await search_service.search(query)
            # Should not crash
            assert response.query == query
    
    @pytest.mark.asyncio
    async def test_search_invalid_parameters(self, search_service: SearchService):
        """Test search with invalid parameters"""
        # These should be handled gracefully by the service
        response = await search_service.search(
            "test query",
            top_k=0,  # Invalid
            similarity_threshold=1.5  # Invalid
        )
        
        # Service should use valid defaults
        assert response.search_config['top_k'] > 0
        assert response.search_config['similarity_threshold'] <= 1.0