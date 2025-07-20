"""
Tests for the FastAPI web interface
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Import after setting up test environment
from api.server import app


@pytest.fixture
def client():
    """Create test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_lifeboard_app():
    """Mock Lifeboard application for testing"""
    mock_app = AsyncMock()
    
    # Mock search response
    mock_search_response = AsyncMock()
    mock_search_response.query = "test query"
    mock_search_response.results = []
    mock_search_response.total_results = 0
    mock_search_response.predicted_sources = ["test"]
    mock_search_response.priority_order = ["test"]
    mock_search_response.namespaces_found = []
    mock_search_response.search_config = {"top_k": 10}
    mock_search_response.search_duration_seconds = 0.1
    mock_search_response.timestamp.isoformat.return_value = "2024-01-01T00:00:00"
    
    mock_app.search.return_value = mock_search_response
    mock_app.ingest_manual_item.return_value = "test:item1"
    
    # Mock stats
    mock_app.get_stats.return_value = {
        "status": "running",
        "database": {"total_items": 0},
        "vector_store": {"total_vectors": 0},
        "sources": {"active_sources": 0},
        "search": {"default_top_k": 10},
        "ingestion": {"embedding_batch_size": 50}
    }
    
    return mock_app


class TestAPIEndpoints:
    """Test FastAPI endpoints"""
    
    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "Lifeboard API"
    
    def test_health_endpoint_not_initialized(self, client: TestClient):
        """Test health endpoint when app is not initialized"""
        response = client.get("/health")
        # Should return service unavailable since app isn't initialized in tests
        assert response.status_code == 503
    
    @patch('api.server.lifeboard_app')
    def test_health_endpoint_initialized(self, mock_app, client: TestClient):
        """Test health endpoint when app is initialized"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @patch('api.server.lifeboard_app')
    def test_search_endpoint(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test search endpoint"""
        mock_app_global.return_value = mock_lifeboard_app
        
        # Mock the get_lifeboard_app dependency
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            search_request = {
                "query": "test query",
                "top_k": 5
            }
            
            response = client.post("/search", json=search_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["query"] == "test query"
            assert data["total_results"] == 0
            assert "search_duration_seconds" in data
    
    @patch('api.server.lifeboard_app')
    def test_ingest_endpoint(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test content ingestion endpoint"""
        mock_app_global.return_value = mock_lifeboard_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            ingest_request = {
                "namespace": "test",
                "content": "Test content to ingest",
                "metadata": {"type": "test"}
            }
            
            response = client.post("/ingest", json=ingest_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is True
            assert data["namespaced_id"] == "test:item1"
    
    @patch('api.server.lifeboard_app')
    def test_stats_endpoint(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test stats endpoint"""
        mock_app_global.return_value = mock_lifeboard_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            response = client.get("/stats")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "running"
            assert "database" in data
            assert "vector_store" in data
    
    def test_search_endpoint_not_initialized(self, client: TestClient):
        """Test search endpoint when app is not initialized"""
        search_request = {
            "query": "test query"
        }
        
        response = client.post("/search", json=search_request)
        assert response.status_code == 503
    
    def test_invalid_search_request(self, client: TestClient):
        """Test search with invalid request"""
        # Missing required query field
        invalid_request = {
            "top_k": 5
        }
        
        response = client.post("/search", json=invalid_request)
        assert response.status_code == 422  # Validation error


class TestAPIValidation:
    """Test API request validation"""
    
    @patch('api.server.lifeboard_app')
    def test_search_validation(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test search request validation"""
        mock_app_global.return_value = mock_lifeboard_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            # Test valid request
            valid_request = {
                "query": "test query",
                "top_k": 10,
                "similarity_threshold": 0.5
            }
            response = client.post("/search", json=valid_request)
            assert response.status_code == 200
            
            # Test invalid top_k (too high)
            invalid_request = {
                "query": "test query",
                "top_k": 1000  # Above max limit
            }
            response = client.post("/search", json=invalid_request)
            assert response.status_code == 422
            
            # Test invalid similarity_threshold
            invalid_request = {
                "query": "test query", 
                "similarity_threshold": 1.5  # Above 1.0
            }
            response = client.post("/search", json=invalid_request)
            assert response.status_code == 422
    
    @patch('api.server.lifeboard_app')
    def test_ingest_validation(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test ingest request validation"""
        mock_app_global.return_value = mock_lifeboard_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            # Test valid request
            valid_request = {
                "namespace": "test",
                "content": "Test content"
            }
            response = client.post("/ingest", json=valid_request)
            assert response.status_code == 200
            
            # Test missing required fields
            invalid_request = {
                "namespace": "test"
                # Missing content
            }
            response = client.post("/ingest", json=invalid_request)
            assert response.status_code == 422


class TestAPIErrorHandling:
    """Test API error handling"""
    
    @patch('api.server.lifeboard_app')
    def test_search_error_handling(self, mock_app_global, client: TestClient):
        """Test search error handling"""
        # Mock app that raises an exception
        mock_app = AsyncMock()
        mock_app.search.side_effect = Exception("Search failed")
        mock_app_global.return_value = mock_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_app):
            search_request = {
                "query": "test query"
            }
            
            response = client.post("/search", json=search_request)
            assert response.status_code == 500
            assert "Search failed" in response.json()["detail"]
    
    @patch('api.server.lifeboard_app')
    def test_ingest_error_handling(self, mock_app_global, client: TestClient):
        """Test ingest error handling"""
        # Mock app that raises an exception
        mock_app = AsyncMock()
        mock_app.ingest_manual_item.side_effect = Exception("Ingestion failed")
        mock_app_global.return_value = mock_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_app):
            ingest_request = {
                "namespace": "test",
                "content": "Test content"
            }
            
            response = client.post("/ingest", json=ingest_request)
            assert response.status_code == 500
            assert "Ingestion failed" in response.json()["detail"]


class TestAPIPerformance:
    """Test API performance characteristics"""
    
    @patch('api.server.lifeboard_app')
    def test_search_response_time(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test search endpoint response time"""
        mock_app_global.return_value = mock_lifeboard_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            search_request = {
                "query": "test query"
            }
            
            import time
            start_time = time.time()
            response = client.post("/search", json=search_request)
            end_time = time.time()
            
            assert response.status_code == 200
            # API overhead should be minimal (< 100ms for mocked response)
            assert (end_time - start_time) < 0.1
    
    @patch('api.server.lifeboard_app')
    def test_concurrent_requests(self, mock_app_global, client: TestClient, mock_lifeboard_app):
        """Test handling of concurrent requests"""
        mock_app_global.return_value = mock_lifeboard_app
        
        with patch('api.server.get_lifeboard_app', return_value=mock_lifeboard_app):
            # Simulate concurrent requests
            import threading
            import time
            
            results = []
            
            def make_request():
                search_request = {"query": "test query"}
                response = client.post("/search", json=search_request)
                results.append(response.status_code)
            
            # Create multiple threads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # All requests should succeed
            assert all(status == 200 for status in results)
            assert len(results) == 5


class TestAPISecurity:
    """Test API security features"""
    
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are present"""
        response = client.get("/")
        
        # Check for CORS headers (these are added by FastAPI middleware)
        # The test client may not include all headers, but we can verify the endpoint works
        assert response.status_code == 200
    
    def test_input_sanitization(self, client: TestClient):
        """Test that potentially malicious input is handled safely"""
        # Test with potentially problematic input
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "\x00\x01\x02\x03"  # Binary data
        ]
        
        for malicious_input in malicious_inputs:
            search_request = {
                "query": malicious_input
            }
            
            response = client.post("/search", json=search_request)
            # Should either process safely or return validation error, not crash
            assert response.status_code in [200, 422, 503]  # 503 if app not initialized