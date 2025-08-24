"""
Comprehensive tests for system API routes
Tests FastAPI endpoints for system management and search functionality
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.system import router, SystemResponse, SearchRequest, SearchResult
from services.startup import StartupService
from services.chat_service import ChatService


class TestSystemRoutes:
    """Test system API endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI test application"""
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service for testing"""
        service = MagicMock(spec=StartupService)
        service.chat_service = AsyncMock(spec=ChatService)
        return service
    
    @pytest.fixture
    def mock_chat_service(self, mock_startup_service):
        """Mock chat service for testing"""
        return mock_startup_service.chat_service
    
    @pytest.fixture
    def sample_search_results(self):
        """Sample search results for testing"""
        return [
            {
                'id': 'limitless:conv1',
                'content': 'Project planning discussion with team about Q1 milestones and resource allocation',
                'score': 0.95,
                'namespace': 'limitless',
                'days_date': '2024-01-15'
            },
            {
                'id': 'limitless:act1',
                'content': 'Morning walk in Central Park, enjoyed the fresh air and exercise',
                'score': 0.87,
                'namespace': 'limitless',
                'days_date': '2024-01-15'
            },
            {
                'id': 'news:tech1',
                'content': 'Tech industry sees major AI breakthrough with new language models',
                'score': 0.82,
                'namespace': 'news',
                'days_date': '2024-01-15'
            }
        ]
    
    def test_search_data_success(self, client, mock_startup_service, mock_chat_service, sample_search_results):
        """Test successful data search"""
        mock_chat_service.search_data.return_value = sample_search_results
        
        search_payload = {
            "query": "project planning",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response is a list
        assert isinstance(data, list)
        assert len(data) == 3
        
        # Verify first result structure
        first_result = data[0]
        assert "id" in first_result
        assert "content" in first_result
        assert "score" in first_result
        assert "source" in first_result
        assert "date" in first_result
        
        # Verify content
        assert first_result["id"] == "limitless:conv1"
        assert "project planning" in first_result["content"].lower()
        assert first_result["score"] == 0.95
        assert first_result["source"] == "limitless"
        assert first_result["date"] == "2024-01-15"
        
        # Verify service was called correctly
        mock_chat_service.search_data.assert_called_once_with("project planning", limit=20)
    
    def test_search_data_with_custom_limit(self, client, mock_startup_service, mock_chat_service, sample_search_results):
        """Test data search with custom limit"""
        # Return only first 2 results for limit test
        limited_results = sample_search_results[:2]
        mock_chat_service.search_data.return_value = limited_results
        
        search_payload = {
            "query": "planning",
            "limit": 2
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        mock_chat_service.search_data.assert_called_once_with("planning", limit=2)
    
    def test_search_data_empty_query(self, client, mock_startup_service, mock_chat_service):
        """Test search with empty query"""
        mock_chat_service.search_data.return_value = []
        
        search_payload = {
            "query": "",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
        
        mock_chat_service.search_data.assert_called_once_with("", limit=20)
    
    def test_search_data_no_results(self, client, mock_startup_service, mock_chat_service):
        """Test search that returns no results"""
        mock_chat_service.search_data.return_value = []
        
        search_payload = {
            "query": "nonexistent topic",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
    
    def test_search_data_chat_service_unavailable(self, client, mock_startup_service):
        """Test search when chat service is unavailable"""
        mock_startup_service.chat_service = None
        
        search_payload = {
            "query": "test query",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Chat service not available"
    
    def test_search_data_service_error(self, client, mock_startup_service, mock_chat_service):
        """Test search when chat service raises exception"""
        mock_chat_service.search_data.side_effect = Exception("Vector database connection failed")
        
        search_payload = {
            "query": "test query",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 500
        data = response.json()
        assert "Search failed" in data["detail"]
        assert "Vector database connection failed" in data["detail"]
    
    def test_search_data_large_limit(self, client, mock_startup_service, mock_chat_service, sample_search_results):
        """Test search with very large limit"""
        mock_chat_service.search_data.return_value = sample_search_results
        
        search_payload = {
            "query": "test",
            "limit": 1000
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        mock_chat_service.search_data.assert_called_once_with("test", limit=1000)
    
    def test_search_data_missing_fields_in_results(self, client, mock_startup_service, mock_chat_service):
        """Test search with incomplete result data"""
        incomplete_results = [
            {
                'id': 'test:1',
                'content': 'Test content',
                # Missing score, namespace, days_date
            },
            {
                'content': 'Content without ID',
                'score': 0.5,
                'namespace': 'test'
                # Missing id, days_date
            }
        ]
        mock_chat_service.search_data.return_value = incomplete_results
        
        search_payload = {
            "query": "test",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Verify defaults are handled correctly
        first_result = data[0]
        assert first_result["id"] == "test:1"
        assert first_result["content"] == "Test content"
        assert first_result["score"] == 0.0  # Default
        assert first_result["source"] == ""  # Default
        assert first_result["date"] == ""  # Default
        
        second_result = data[1]
        assert second_result["id"] == ""  # Default
        assert second_result["content"] == "Content without ID"
        assert second_result["score"] == 0.5
        assert second_result["source"] == "test"
        assert second_result["date"] == ""  # Default
    
    def test_initialize_system_success(self, client):
        """Test successful system initialization"""
        mock_result = {
            "success": True,
            "message": "All services initialized successfully",
            "details": {
                "database": "connected",
                "services": "started",
                "scheduler": "running"
            }
        }
        
        with patch('api.routes.system.initialize_application', return_value=mock_result) as mock_init:
            with patch('api.routes.system.create_production_config') as mock_config:
                response = client.post("/api/system/startup")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "message" in data
        assert "result" in data
        
        # Verify content
        assert data["success"] is True
        assert data["message"] == "System initialization completed"
        assert data["result"] == mock_result
        
        # Verify services were called
        mock_config.assert_called_once()
        mock_init.assert_called_once()
    
    def test_initialize_system_failure(self, client):
        """Test system initialization failure"""
        mock_result = {
            "success": False,
            "error": "Database connection failed",
            "details": {
                "database": "failed to connect",
                "services": "not started"
            }
        }
        
        with patch('api.routes.system.initialize_application', return_value=mock_result) as mock_init:
            with patch('api.routes.system.create_production_config') as mock_config:
                response = client.post("/api/system/startup")
        
        assert response.status_code == 200  # Route returns 200 even on init failure
        data = response.json()
        
        assert data["success"] is False
        assert data["message"] == "System initialization failed"
        assert data["result"] == mock_result
    
    def test_initialize_system_exception(self, client):
        """Test system initialization when exception is raised"""
        with patch('api.routes.system.initialize_application', side_effect=Exception("Critical startup error")):
            with patch('api.routes.system.create_production_config'):
                response = client.post("/api/system/startup")
        
        assert response.status_code == 500
        data = response.json()
        assert "System initialization failed" in data["detail"]
    
    def test_shutdown_system_success(self, client):
        """Test successful system shutdown"""
        with patch('api.routes.system.shutdown_application', return_value=None) as mock_shutdown:
            response = client.post("/api/system/shutdown")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "message" in data
        
        # Verify content
        assert data["success"] is True
        assert data["message"] == "System shutdown completed"
        
        # Verify shutdown was called
        mock_shutdown.assert_called_once()
    
    def test_shutdown_system_exception(self, client):
        """Test system shutdown when exception is raised"""
        with patch('api.routes.system.shutdown_application', side_effect=Exception("Shutdown error")):
            response = client.post("/api/system/shutdown")
        
        assert response.status_code == 500
        data = response.json()
        assert "System shutdown failed" in data["detail"]
    
    def test_search_request_model_validation(self):
        """Test SearchRequest Pydantic model validation"""
        # Valid request with default limit
        valid_data = {"query": "test search"}
        request = SearchRequest(**valid_data)
        assert request.query == "test search"
        assert request.limit == 20  # Default value
        
        # Valid request with custom limit
        custom_data = {"query": "another search", "limit": 50}
        request = SearchRequest(**custom_data)
        assert request.query == "another search"
        assert request.limit == 50
        
        # Valid request with empty query
        empty_data = {"query": ""}
        request = SearchRequest(**empty_data)
        assert request.query == ""
        assert request.limit == 20
    
    def test_search_result_model_validation(self):
        """Test SearchResult Pydantic model validation"""
        valid_data = {
            "id": "limitless:conv1",
            "content": "Test conversation content",
            "score": 0.95,
            "source": "limitless",
            "date": "2024-01-15"
        }
        result = SearchResult(**valid_data)
        assert result.id == "limitless:conv1"
        assert result.content == "Test conversation content"
        assert result.score == 0.95
        assert result.source == "limitless"
        assert result.date == "2024-01-15"
    
    def test_system_response_model_validation(self):
        """Test SystemResponse Pydantic model validation"""
        # Valid response with result
        valid_data = {
            "success": True,
            "message": "Operation completed",
            "result": {"detail": "success"}
        }
        response = SystemResponse(**valid_data)
        assert response.success is True
        assert response.message == "Operation completed"
        assert response.result == {"detail": "success"}
        
        # Valid response without result
        minimal_data = {
            "success": False,
            "message": "Operation failed"
        }
        response = SystemResponse(**minimal_data)
        assert response.success is False
        assert response.message == "Operation failed"
        assert response.result is None
    
    def test_search_invalid_json_payload(self, client, mock_startup_service, mock_chat_service):
        """Test search endpoint with invalid JSON payload"""
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json={"invalid_field": "test"})
        
        assert response.status_code == 422  # Validation error - missing required 'query' field
    
    def test_search_endpoint_cors_headers(self, client, mock_startup_service, mock_chat_service):
        """Test search endpoint includes proper headers"""
        mock_chat_service.search_data.return_value = []
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json={"query": "test"})
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_search_performance_timing(self, client, mock_startup_service, mock_chat_service):
        """Test search endpoint response timing"""
        mock_chat_service.search_data.return_value = []
        
        import time
        start_time = time.time()
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json={"query": "test"})
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Search should be reasonably fast in test environment
        assert response_time < 0.1
    
    def test_system_startup_performance_timing(self, client):
        """Test system startup endpoint response timing"""
        mock_result = {"success": True}
        
        import time
        start_time = time.time()
        
        with patch('api.routes.system.initialize_application', return_value=mock_result):
            with patch('api.routes.system.create_production_config'):
                response = client.post("/api/system/startup")
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Startup endpoint should respond quickly (actual init happens in background)
        assert response_time < 0.1
    
    def test_search_unicode_query(self, client, mock_startup_service, mock_chat_service):
        """Test search with Unicode characters in query"""
        mock_chat_service.search_data.return_value = []
        
        search_payload = {
            "query": "测试搜索 🔍 émojis and spëcial",
            "limit": 20
        }
        
        with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
            response = client.post("/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
        
        # Verify Unicode query was passed correctly
        mock_chat_service.search_data.assert_called_once_with("测试搜索 🔍 émojis and spëcial", limit=20)
    
    def test_search_concurrent_requests(self, client, mock_startup_service, mock_chat_service):
        """Test search endpoint handles concurrent requests"""
        mock_chat_service.search_data.return_value = []
        
        import threading
        
        responses = []
        errors = []
        
        def make_search_request(query):
            try:
                with patch('api.routes.system.get_startup_service_dependency', return_value=mock_startup_service):
                    response = client.post("/search", json={"query": query})
                    responses.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Start multiple concurrent search requests
        threads = []
        queries = ["query1", "query2", "query3"]
        for query in queries:
            thread = threading.Thread(target=make_search_request, args=[query])
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Verify all requests succeeded
        assert len(errors) == 0
        assert len(responses) == 3
        assert all(status == 200 for status in responses)
        
        # Verify search was called for each request
        assert mock_chat_service.search_data.call_count == 3