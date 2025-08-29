"""
Integration tests for document search functionality

Tests the complete search flow from API endpoints through service layer
to vector store and database integration for all document types.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from services.document_service import DocumentService, Document
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from api.routes.documents import router
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def sample_documents():
    """Create sample documents for testing"""
    return [
        Document(
            id="note-1",
            title="Python Programming Guide",
            document_type="note",
            content_delta={"ops": [{"insert": "Complete guide to Python programming with examples\n"}]},
            content_md="Complete guide to Python programming with examples",
            path="/programming/",
            is_folder=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Document(
            id="prompt-1", 
            title="Code Review Assistant",
            document_type="prompt",
            content_delta={"ops": [{"insert": "You are a code reviewer. Analyze {{CODE_SNIPPET}} for quality\n"}]},
            content_md="You are a code reviewer. Analyze {{CODE_SNIPPET}} for quality",
            path="/prompts/",
            is_folder=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Document(
            id="link-1",
            title="Python Documentation",
            document_type="link",
            content_delta={"ops": [{"insert": "Official Python language documentation\n"}]},
            content_md="Official Python language documentation",
            path="/resources/",
            is_folder=False,
            url="https://docs.python.org",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Document(
            id="note-2",
            title="JavaScript Fundamentals",
            document_type="note",
            content_delta={"ops": [{"insert": "Learn JavaScript basics and advanced concepts\n"}]},
            content_md="Learn JavaScript basics and advanced concepts",
            path="/programming/",
            is_folder=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Document(
            id="prompt-2",
            title="Writing Assistant",
            document_type="prompt", 
            content_delta={"ops": [{"insert": "Help improve writing style and grammar for {{TEXT_INPUT}}\n"}]},
            content_md="Help improve writing style and grammar for {{TEXT_INPUT}}",
            path="/prompts/",
            is_folder=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        Document(
            id="link-2",
            title="MDN Web Docs",
            document_type="link",
            content_delta={"ops": [{"insert": "Mozilla Developer Network documentation\n"}]},
            content_md="Mozilla Developer Network documentation",
            path="/resources/",
            is_folder=False,
            url="https://developer.mozilla.org",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    ]


@pytest.fixture
def mock_vector_search_results():
    """Mock vector store search results with scores"""
    return [
        ("note-1", 0.95),    # High relevance Python guide
        ("prompt-1", 0.88),  # Medium relevance code review
        ("link-1", 0.82),    # Medium relevance Python docs
        ("note-2", 0.45),    # Low relevance JavaScript
    ]


class TestDocumentSearchIntegration:
    """Test complete document search integration"""
    
    async def test_search_all_document_types(self, sample_documents, mock_vector_search_results):
        """Test search across all document types returns scored results"""
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup vector store mock
        mock_vector_store.search = AsyncMock(return_value=mock_vector_search_results)
        
        # Setup embedding service mock
        mock_embedding_service.generate_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3, 0.4, 0.5]
        )
        
        # Setup database mock to return documents by IDs
        def mock_fetch_all(query, params):
            doc_ids = [result[0] for result in mock_vector_search_results]
            return [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'content_delta': json.dumps(doc.content_delta),
                    'content_md': doc.content_md,
                    'path': doc.path,
                    'is_folder': 1 if doc.is_folder else 0,
                    'url': getattr(doc, 'url', None),
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat()
                }
                for doc in sample_documents
                if doc.id in doc_ids
            ]
        
        mock_db.fetch_all = MagicMock(side_effect=mock_fetch_all)
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Execute search
        results = await service.search_documents("Python programming", limit=10)
        
        # Verify results
        assert len(results) == 4  # All matching documents
        
        # Check results are sorted by score (highest first)
        scores = [result[1] for result in results]
        assert scores == sorted(scores, reverse=True)
        
        # Check document types are included
        doc_types = [result[0].document_type for result in results]
        assert "note" in doc_types
        assert "prompt" in doc_types  
        assert "link" in doc_types
        
        # Check highest scoring result
        top_result = results[0]
        assert top_result[0].title == "Python Programming Guide"
        assert top_result[1] == 0.95
        
        # Verify vector store was called with query embedding
        mock_embedding_service.generate_embedding.assert_called_once_with("Python programming")
        mock_vector_store.search.assert_called_once()

    async def test_search_filtered_by_document_type(self, sample_documents, mock_vector_search_results):
        """Test search filtered by specific document type"""
        
        # Mock dependencies  
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks
        mock_vector_store.search = AsyncMock(return_value=mock_vector_search_results)
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        
        # Mock database to return only prompt documents
        def mock_fetch_all_prompts(query, params):
            doc_ids = [result[0] for result in mock_vector_search_results]
            return [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'content_delta': json.dumps(doc.content_delta),
                    'content_md': doc.content_md,
                    'path': doc.path,
                    'is_folder': 1 if doc.is_folder else 0,
                    'url': getattr(doc, 'url', None),
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat()
                }
                for doc in sample_documents
                if doc.id in doc_ids and doc.document_type == "prompt"
            ]
        
        mock_db.fetch_all = MagicMock(side_effect=mock_fetch_all_prompts)
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Execute search with type filter
        results = await service.search_documents("code review", document_type="prompt", limit=10)
        
        # Verify only prompt documents returned
        assert len(results) == 1  # Only prompt documents
        assert all(result[0].document_type == "prompt" for result in results)
        
        # Check the prompt document
        prompt_result = results[0]
        assert "review" in prompt_result[0].title.lower() or "review" in prompt_result[0].content_md.lower()

    async def test_search_empty_results(self, sample_documents):
        """Test search with no matching results"""
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)  
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks for no results
        mock_vector_store.search = AsyncMock(return_value=[])
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_db.fetch_all = MagicMock(return_value=[])
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store, 
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Execute search
        results = await service.search_documents("nonexistent topic", limit=10)
        
        # Verify empty results
        assert len(results) == 0
        
        # Verify embedding was still generated
        mock_embedding_service.generate_embedding.assert_called_once_with("nonexistent topic")

    async def test_search_with_score_threshold(self, sample_documents, mock_vector_search_results):
        """Test search applies score threshold filtering"""
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks
        mock_vector_store.search = AsyncMock(return_value=mock_vector_search_results)
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        
        # Mock database to return documents above threshold
        def mock_fetch_all_filtered(query, params):
            threshold = 0.5  # Filter out low scores
            high_score_ids = [result[0] for result in mock_vector_search_results if result[1] >= threshold]
            return [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'content_delta': json.dumps(doc.content_delta),
                    'content_md': doc.content_md,
                    'path': doc.path,
                    'is_folder': 1 if doc.is_folder else 0,
                    'url': getattr(doc, 'url', None),
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat()
                }
                for doc in sample_documents
                if doc.id in high_score_ids
            ]
        
        mock_db.fetch_all = MagicMock(side_effect=mock_fetch_all_filtered)
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Execute search
        results = await service.search_documents("Python", limit=10)
        
        # Verify only high-scoring results returned
        assert len(results) == 3  # Only results with score >= 0.5
        assert all(result[1] >= 0.5 for result in results)

    async def test_search_handles_special_characters(self, sample_documents):
        """Test search handles special characters and edge cases"""
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks
        mock_vector_store.search = AsyncMock(return_value=[])
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_db.fetch_all = MagicMock(return_value=[])
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Test special character queries
        special_queries = [
            "C++",
            "F#",
            "Node.js",
            "React.js",
            "{{TEMPLATE_VAR}}",
            "SQL SELECT * FROM",
            "UTF-8 encoding"
        ]
        
        for query in special_queries:
            results = await service.search_documents(query, limit=10)
            
            # Should handle gracefully without errors
            assert isinstance(results, list)
            
            # Verify embedding service was called with the query
            mock_embedding_service.generate_embedding.assert_called_with(query)

    async def test_search_respects_limit_parameter(self, sample_documents, mock_vector_search_results):
        """Test search respects the limit parameter"""
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks
        mock_vector_store.search = AsyncMock(return_value=mock_vector_search_results)
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        
        # Mock database to return all documents
        def mock_fetch_all_limited(query, params):
            doc_ids = [result[0] for result in mock_vector_search_results]
            return [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'content_delta': json.dumps(doc.content_delta),
                    'content_md': doc.content_md,
                    'path': doc.path,
                    'is_folder': 1 if doc.is_folder else 0,
                    'url': getattr(doc, 'url', None),
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat()
                }
                for doc in sample_documents
                if doc.id in doc_ids
            ]
        
        mock_db.fetch_all = MagicMock(side_effect=mock_fetch_all_limited)
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Test different limits
        test_limits = [1, 2, 3, 10]
        
        for limit in test_limits:
            results = await service.search_documents("test query", limit=limit)
            
            # Should respect limit (or return fewer if not enough results)
            expected_count = min(limit, len(mock_vector_search_results))
            assert len(results) == expected_count


class TestSearchAPIIntegration:
    """Test search API endpoint integration"""
    
    @pytest.fixture
    def app_with_search(self):
        """Create FastAPI app with document routes for testing"""
        app = FastAPI()
        app.include_router(router)
        return app
    
    def test_search_api_endpoint_all_types(self, app_with_search, sample_documents, mock_vector_search_results):
        """Test search API endpoint returns properly formatted results"""
        
        # Mock the document service
        mock_service = MagicMock(spec=DocumentService)
        
        # Setup search results
        search_results = [
            (sample_documents[0], 0.95),  # Note document
            (sample_documents[1], 0.88),  # Prompt document  
            (sample_documents[2], 0.82),  # Link document
        ]
        mock_service.search_documents = MagicMock(return_value=search_results)
        
        # Mock startup service
        mock_startup = MagicMock()
        mock_startup.document_service = mock_service
        
        with patch('api.routes.documents.get_startup_service_dependency', return_value=mock_startup):
            with TestClient(app_with_search) as client:
                response = client.get("/api/documents/search?q=programming&limit=10")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "results" in data
        assert "total" in data
        assert "query" in data
        assert data["query"] == "programming"
        assert data["total"] == 3
        
        # Check search results
        results = data["results"]
        assert len(results) == 3
        
        # Verify first result structure
        first_result = results[0]
        assert "document" in first_result
        assert "score" in first_result
        assert first_result["score"] == 0.95
        
        # Verify document structure
        document = first_result["document"]
        assert "id" in document
        assert "title" in document
        assert "document_type" in document
        assert "content_md" in document
        assert document["document_type"] in ["note", "prompt", "link"]

    def test_search_api_with_type_filter(self, app_with_search, sample_documents):
        """Test search API with document type filtering"""
        
        # Mock the document service
        mock_service = MagicMock(spec=DocumentService)
        
        # Setup filtered search results (only prompts)
        prompt_results = [
            (sample_documents[1], 0.88),  # Code Review Assistant prompt
            (sample_documents[4], 0.75),  # Writing Assistant prompt
        ]
        mock_service.search_documents = MagicMock(return_value=prompt_results)
        
        # Mock startup service
        mock_startup = MagicMock()
        mock_startup.document_service = mock_service
        
        with patch('api.routes.documents.get_startup_service_dependency', return_value=mock_startup):
            with TestClient(app_with_search) as client:
                response = client.get("/api/documents/search?q=assistant&document_type=prompt&limit=5")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check filtering worked
        assert len(data["results"]) == 2
        assert all(result["document"]["document_type"] == "prompt" 
                  for result in data["results"])
        
        # Verify service was called with correct parameters
        mock_service.search_documents.assert_called_once_with(
            query="assistant",
            document_type="prompt",
            limit=5
        )

    def test_search_api_error_handling(self, app_with_search):
        """Test search API error handling"""
        
        # Mock service that raises an exception
        mock_service = MagicMock(spec=DocumentService)
        mock_service.search_documents = MagicMock(side_effect=Exception("Search failed"))
        
        mock_startup = MagicMock()
        mock_startup.document_service = mock_service
        
        with patch('api.routes.documents.get_startup_service_dependency', return_value=mock_startup):
            with TestClient(app_with_search) as client:
                response = client.get("/api/documents/search?q=test")
        
        # Should return 500 error
        assert response.status_code == 500
        assert "Failed to search documents" in response.json()["detail"]

    def test_search_api_validation(self, app_with_search):
        """Test search API parameter validation"""
        
        mock_service = MagicMock(spec=DocumentService)
        mock_startup = MagicMock()
        mock_startup.document_service = mock_service
        
        with patch('api.routes.documents.get_startup_service_dependency', return_value=mock_startup):
            with TestClient(app_with_search) as client:
                
                # Test missing query parameter
                response = client.get("/api/documents/search")
                assert response.status_code == 422
                
                # Test empty query
                response = client.get("/api/documents/search?q=")
                assert response.status_code == 422
                
                # Test invalid document type
                response = client.get("/api/documents/search?q=test&document_type=invalid")
                assert response.status_code == 422
                
                # Test invalid limit
                response = client.get("/api/documents/search?q=test&limit=0")
                assert response.status_code == 422
                
                response = client.get("/api/documents/search?q=test&limit=51")  # Over max limit
                assert response.status_code == 422


class TestSearchPerformance:
    """Test search performance characteristics"""
    
    async def test_search_performance_with_large_dataset(self, sample_documents):
        """Test search performance with large number of results"""
        
        # Create large dataset simulation
        large_vector_results = [(f"doc-{i}", 0.9 - (i * 0.01)) for i in range(100)]
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks
        mock_vector_store.search = AsyncMock(return_value=large_vector_results)
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1] * 100)
        
        # Mock database with large dataset
        mock_db.fetch_all = MagicMock(return_value=[
            {
                'id': f'doc-{i}',
                'title': f'Document {i}',
                'document_type': 'note',
                'content_delta': '{"ops":[{"insert":"Content\\n"}]}',
                'content_md': 'Content',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
            for i in range(100)
        ])
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Measure search performance
        import time
        start_time = time.time()
        
        results = await service.search_documents("test query", limit=20)
        
        end_time = time.time()
        search_time = end_time - start_time
        
        # Verify results
        assert len(results) == 20  # Respects limit
        assert search_time < 1.0  # Should complete quickly (adjust threshold as needed)
        
        # Verify results are properly sorted by score
        scores = [result[1] for result in results]
        assert scores == sorted(scores, reverse=True)

    async def test_concurrent_search_requests(self, sample_documents, mock_vector_search_results):
        """Test handling concurrent search requests"""
        
        # Mock dependencies
        mock_db = MagicMock(spec=DatabaseService)
        mock_vector_store = MagicMock(spec=VectorStoreService)
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_config = MagicMock()
        mock_config.documents.max_title_length = 200
        mock_config.documents.max_content_length = 10000
        
        # Setup mocks with slight delay to simulate real conditions
        async def mock_search_with_delay(*args, **kwargs):
            await asyncio.sleep(0.01)  # Small delay
            return mock_vector_search_results
        
        mock_vector_store.search = AsyncMock(side_effect=mock_search_with_delay)
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        
        # Mock database
        mock_db.fetch_all = MagicMock(return_value=[
            {
                'id': doc.id,
                'title': doc.title,
                'document_type': doc.document_type,
                'content_delta': json.dumps(doc.content_delta),
                'content_md': doc.content_md,
                'path': doc.path,
                'is_folder': 1 if doc.is_folder else 0,
                'url': getattr(doc, 'url', None),
                'created_at': doc.created_at.isoformat(),
                'updated_at': doc.updated_at.isoformat()
            }
            for doc in sample_documents[:4]
        ])
        
        # Create service
        service = DocumentService(
            database=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=mock_config
        )
        
        # Execute concurrent searches
        search_queries = ["Python", "JavaScript", "documentation", "programming"]
        
        tasks = [
            service.search_documents(query, limit=10)
            for query in search_queries
        ]
        
        # Wait for all searches to complete
        results_list = await asyncio.gather(*tasks)
        
        # Verify all searches completed successfully
        assert len(results_list) == 4
        for results in results_list:
            assert isinstance(results, list)
            assert len(results) <= 10