"""
API tests for Documents routes

Tests cover REST API endpoints for creating, reading, updating, deleting,
and searching documents of all types (Note, Prompt, Folder, Link).
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from api.routes.documents import router
from services.document_service import DocumentService, Document
from services.startup import StartupService
from datetime import datetime, timezone


@pytest.fixture
def mock_document_service():
    """Mock DocumentService for API testing"""
    service = MagicMock(spec=DocumentService)
    
    # Mock service methods as async
    service.create_document = AsyncMock()
    service.create_folder = AsyncMock()
    service.get_document = AsyncMock()
    service.list_documents = MagicMock()
    service.list_folder_contents = MagicMock()
    service.search_documents = AsyncMock()
    service.update_document = AsyncMock()
    service.delete_document = AsyncMock()
    service.delete_folder = AsyncMock()
    service.move_item = AsyncMock()
    service.count_documents = MagicMock()
    service.title_exists = MagicMock()
    service.process_template = MagicMock()
    service.validate_template = MagicMock()
    service._check_service_health = AsyncMock()
    
    return service


@pytest.fixture
def mock_startup_service(mock_document_service):
    """Mock StartupService with document service"""
    startup_service = MagicMock(spec=StartupService)
    startup_service.document_service = mock_document_service
    return startup_service


@pytest.fixture
def app(mock_startup_service):
    """Create FastAPI test application with dependency overrides"""
    from fastapi import FastAPI
    from core.dependencies import get_startup_service_dependency
    
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


def create_sample_document(doc_type="note", title="Test Document", doc_id="test-123"):
    """Helper to create sample Document objects"""
    return Document(
        id=doc_id,
        title=title,
        document_type=doc_type,
        content_delta={"ops": [{"insert": "Sample content\n"}]},
        content_md="Sample content",
        path="/",
        is_folder=(doc_type == "folder"),
        url="https://example.com" if doc_type == "link" else None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestCreateDocument:
    """Test document creation endpoints"""
    
    def test_create_note_document(self, client, mock_document_service):
        """Test creating a note document"""
        # Setup mock
        expected_doc = create_sample_document("note", "My Note")
        mock_document_service.create_document.return_value = expected_doc
        
        # Make request
        payload = {
            "title": "My Note",
            "document_type": "note",
            "content_delta": {"ops": [{"insert": "Note content\n"}]},
            "path": "/"
        }
        
        response = client.post("/api/documents", json=payload)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "My Note"
        assert data["document_type"] == "note"
        assert data["is_folder"] is False
        assert data["url"] is None
        
        # Verify service was called correctly
        mock_document_service.create_document.assert_called_once_with(
            title="My Note",
            document_type="note",
            content_delta={"ops": [{"insert": "Note content\n"}]},
            path="/",
            url=None
        )

    def test_create_prompt_document(self, client, mock_document_service):
        """Test creating a prompt document"""
        expected_doc = create_sample_document("prompt", "Assistant Prompt")
        mock_document_service.create_document.return_value = expected_doc
        
        payload = {
            "title": "Assistant Prompt",
            "document_type": "prompt",
            "content_delta": {"ops": [{"insert": "You are a helpful {{USER_CONTEXT}}\n"}]},
            "path": "/prompts/"
        }
        
        response = client.post("/api/documents", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_type"] == "prompt"
        assert data["title"] == "Assistant Prompt"

    def test_create_link_document(self, client, mock_document_service):
        """Test creating a link document"""
        expected_doc = create_sample_document("link", "Useful Resource")
        mock_document_service.create_document.return_value = expected_doc
        
        payload = {
            "title": "Useful Resource",
            "document_type": "link",
            "content_delta": {"ops": [{"insert": "Great resource for learning\n"}]},
            "path": "/links/",
            "url": "https://example.com"
        }
        
        response = client.post("/api/documents", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_type"] == "link"
        assert data["url"] == "https://example.com"

    def test_create_folder_via_document_endpoint(self, client, mock_document_service):
        """Test creating a folder via the main document endpoint"""
        expected_folder = create_sample_document("folder", "Project Folder")
        mock_document_service.create_folder.return_value = expected_folder
        
        payload = {
            "title": "Project Folder",
            "document_type": "folder",
            "path": "/"
        }
        
        response = client.post("/api/documents", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_type"] == "folder"
        assert data["is_folder"] is True
        
        # Should call create_folder, not create_document
        mock_document_service.create_folder.assert_called_once()

    def test_create_document_invalid_type(self, client, mock_document_service):
        """Test creating document with invalid type"""
        payload = {
            "title": "Invalid",
            "document_type": "invalid_type",
            "content_delta": {"ops": [{"insert": "\n"}]},
            "path": "/"
        }
        
        response = client.post("/api/documents", json=payload)
        
        assert response.status_code == 422  # Validation error
        
    def test_create_document_empty_title(self, client, mock_document_service):
        """Test creating document with empty title"""
        payload = {
            "title": "",
            "document_type": "note",
            "content_delta": {"ops": [{"insert": "\n"}]},
            "path": "/"
        }
        
        response = client.post("/api/documents", json=payload)
        
        assert response.status_code == 422  # Validation error

    def test_create_document_service_error(self, client, mock_document_service):
        """Test handling service errors during creation"""
        mock_document_service.create_document.side_effect = ValueError("Title too long")
        
        payload = {
            "title": "Valid Title",
            "document_type": "note",
            "content_delta": {"ops": [{"insert": "\n"}]},
            "path": "/"
        }
        
        response = client.post("/api/documents", json=payload)
        
        assert response.status_code == 400
        assert "Title too long" in response.json()["detail"]


class TestCreateFolder:
    """Test folder creation endpoint"""
    
    def test_create_folder(self, client, mock_document_service):
        """Test creating a folder via dedicated endpoint"""
        expected_folder = create_sample_document("folder", "New Folder")
        mock_document_service.create_folder.return_value = expected_folder
        
        payload = {
            "name": "New Folder",
            "parent_path": "/"
        }
        
        response = client.post("/api/documents/folders", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Folder"
        assert data["is_folder"] is True
        
        mock_document_service.create_folder.assert_called_once_with(
            name="New Folder",
            parent_path="/"
        )

    def test_create_folder_with_slash_in_name(self, client, mock_document_service):
        """Test creating folder with invalid characters"""
        payload = {
            "name": "Invalid/Folder",
            "parent_path": "/"
        }
        
        response = client.post("/api/documents/folders", json=payload)
        
        assert response.status_code == 422  # Validation error


class TestRetrieveDocument:
    """Test document retrieval endpoints"""
    
    def test_get_document_by_id(self, client, mock_document_service):
        """Test getting a document by ID"""
        expected_doc = create_sample_document("note", "Retrieved Note", "test-123")
        mock_document_service.get_document.return_value = expected_doc
        
        response = client.get("/api/documents/test-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-123"
        assert data["title"] == "Retrieved Note"
        
        mock_document_service.get_document.assert_called_once_with("test-123")

    def test_get_document_not_found(self, client, mock_document_service):
        """Test getting non-existent document"""
        mock_document_service.get_document.return_value = None
        
        response = client.get("/api/documents/non-existent")
        
        assert response.status_code == 404

    def test_list_documents_all(self, client, mock_document_service):
        """Test listing all documents"""
        docs = [
            create_sample_document("note", "Note 1", "note-1"),
            create_sample_document("prompt", "Prompt 1", "prompt-1"),
            create_sample_document("folder", "Folder 1", "folder-1"),
            create_sample_document("link", "Link 1", "link-1")
        ]
        mock_document_service.list_documents.return_value = docs
        
        response = client.get("/api/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 4
        assert data["total"] == 4
        
        # Check all document types are present
        types = [doc["document_type"] for doc in data["documents"]]
        assert "note" in types
        assert "prompt" in types
        assert "folder" in types
        assert "link" in types

    def test_list_documents_by_type(self, client, mock_document_service):
        """Test listing documents filtered by type"""
        notes = [
            create_sample_document("note", "Note 1", "note-1"),
            create_sample_document("note", "Note 2", "note-2")
        ]
        mock_document_service.list_documents.return_value = notes
        
        response = client.get("/api/documents?document_type=note")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2
        assert all(doc["document_type"] == "note" for doc in data["documents"])

    def test_list_folder_contents(self, client, mock_document_service):
        """Test listing folder contents"""
        contents = [
            create_sample_document("folder", "Subfolder", "sub-1"),
            create_sample_document("note", "Note in Folder", "note-1")
        ]
        mock_document_service.list_folder_contents.return_value = contents
        
        response = client.get("/api/documents/folders/contents?folder_path=/test/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2
        
        mock_document_service.list_folder_contents.assert_called_once_with(
            folder_path="/test/",
            include_folders=True
        )

    def test_count_documents(self, client, mock_document_service):
        """Test document count endpoint"""
        mock_document_service.count_documents.return_value = 25
        
        response = client.get("/api/documents/count")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 25

    def test_count_documents_by_type(self, client, mock_document_service):
        """Test counting documents by type"""
        mock_document_service.count_documents.return_value = 12
        
        response = client.get("/api/documents/count?document_type=prompt")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 12
        
        mock_document_service.count_documents.assert_called_once_with(
            document_type="prompt",
            folder_path=None
        )


class TestSearchDocuments:
    """Test document search functionality"""
    
    def test_search_documents_all_types(self, client, mock_document_service):
        """Test searching across all document types"""
        # Mock search results with scores
        search_results = [
            (create_sample_document("note", "Matching Note", "note-1"), 0.9),
            (create_sample_document("prompt", "Matching Prompt", "prompt-1"), 0.8),
            (create_sample_document("link", "Matching Link", "link-1"), 0.7)
        ]
        mock_document_service.search_documents.return_value = search_results
        
        response = client.get("/api/documents/search?q=matching")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3
        assert data["query"] == "matching"
        
        # Check scores are included
        assert data["results"][0]["score"] == 0.9
        assert data["results"][1]["score"] == 0.8
        assert data["results"][2]["score"] == 0.7
        
        # Check document types
        types = [result["document"]["document_type"] for result in data["results"]]
        assert "note" in types
        assert "prompt" in types
        assert "link" in types

    def test_search_documents_by_type(self, client, mock_document_service):
        """Test searching documents filtered by type"""
        search_results = [
            (create_sample_document("prompt", "AI Assistant", "prompt-1"), 0.95)
        ]
        mock_document_service.search_documents.return_value = search_results
        
        response = client.get("/api/documents/search?q=assistant&document_type=prompt")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["document"]["document_type"] == "prompt"
        
        mock_document_service.search_documents.assert_called_once_with(
            query="assistant",
            document_type="prompt",
            limit=20
        )

    def test_search_documents_empty_query(self, client, mock_document_service):
        """Test search with empty query"""
        response = client.get("/api/documents/search?q=")
        
        assert response.status_code == 422  # Validation error

    def test_search_documents_with_limit(self, client, mock_document_service):
        """Test search with custom limit"""
        search_results = []
        mock_document_service.search_documents.return_value = search_results
        
        response = client.get("/api/documents/search?q=test&limit=5")
        
        assert response.status_code == 200
        mock_document_service.search_documents.assert_called_once_with(
            query="test",
            document_type=None,
            limit=5
        )


class TestUpdateDocument:
    """Test document update operations"""
    
    def test_update_document_title(self, client, mock_document_service):
        """Test updating document title"""
        updated_doc = create_sample_document("note", "Updated Title", "test-123")
        mock_document_service.update_document.return_value = updated_doc
        
        payload = {
            "title": "Updated Title"
        }
        
        response = client.put("/api/documents/test-123", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        
        mock_document_service.update_document.assert_called_once_with(
            doc_id="test-123",
            title="Updated Title",
            document_type=None,
            content_delta=None,
            url=None
        )

    def test_update_document_content(self, client, mock_document_service):
        """Test updating document content"""
        updated_doc = create_sample_document("note", "Test Document", "test-123")
        mock_document_service.update_document.return_value = updated_doc
        
        new_content = {"ops": [{"insert": "New content\n"}]}
        payload = {
            "content_delta": new_content
        }
        
        response = client.put("/api/documents/test-123", json=payload)
        
        assert response.status_code == 200
        mock_document_service.update_document.assert_called_once_with(
            doc_id="test-123",
            title=None,
            document_type=None,
            content_delta=new_content,
            url=None
        )

    def test_update_link_document_url(self, client, mock_document_service):
        """Test updating link document URL"""
        updated_doc = create_sample_document("link", "Test Link", "link-123")
        updated_doc.url = "https://new-url.com"
        mock_document_service.update_document.return_value = updated_doc
        
        payload = {
            "url": "https://new-url.com"
        }
        
        response = client.put("/api/documents/link-123", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://new-url.com"

    def test_update_document_type(self, client, mock_document_service):
        """Test updating document type"""
        updated_doc = create_sample_document("prompt", "Converted Document", "test-123")
        mock_document_service.update_document.return_value = updated_doc
        
        payload = {
            "document_type": "prompt"
        }
        
        response = client.put("/api/documents/test-123", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_type"] == "prompt"

    def test_update_document_validation_error(self, client, mock_document_service):
        """Test update with validation error"""
        mock_document_service.update_document.side_effect = ValueError("Invalid update")
        
        payload = {
            "title": "Test"
        }
        
        response = client.put("/api/documents/test-123", json=payload)
        
        assert response.status_code == 400
        assert "Invalid update" in response.json()["detail"]


class TestDeleteDocument:
    """Test document deletion operations"""
    
    def test_delete_document_success(self, client, mock_document_service):
        """Test successful document deletion"""
        mock_document_service.delete_document.return_value = True
        
        response = client.delete("/api/documents/test-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Document deleted successfully"
        
        mock_document_service.delete_document.assert_called_once_with("test-123")

    def test_delete_document_not_found(self, client, mock_document_service):
        """Test deleting non-existent document"""
        mock_document_service.delete_document.return_value = False
        
        response = client.delete("/api/documents/non-existent")
        
        assert response.status_code == 404

    def test_delete_folder_empty(self, client, mock_document_service):
        """Test deleting empty folder"""
        mock_document_service.delete_folder.return_value = True
        
        response = client.delete("/api/documents/folders?folder_path=/test/&recursive=false")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Folder deleted successfully"
        
        mock_document_service.delete_folder.assert_called_once_with(
            folder_path="/test/",
            recursive=False
        )

    def test_delete_folder_recursive(self, client, mock_document_service):
        """Test deleting folder recursively"""
        mock_document_service.delete_folder.return_value = True
        
        response = client.delete("/api/documents/folders?folder_path=/test/&recursive=true")
        
        assert response.status_code == 200
        mock_document_service.delete_folder.assert_called_once_with(
            folder_path="/test/",
            recursive=True
        )


class TestMoveOperations:
    """Test move operations"""
    
    def test_move_document(self, client, mock_document_service):
        """Test moving a document"""
        mock_document_service.move_item.return_value = True
        
        payload = {
            "new_parent_path": "/new/location/"
        }
        
        response = client.put("/api/documents/test-123/move", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Item moved successfully"
        
        mock_document_service.move_item.assert_called_once_with(
            item_id="test-123",
            new_parent_path="/new/location/"
        )

    def test_move_item_not_found(self, client, mock_document_service):
        """Test moving non-existent item"""
        mock_document_service.move_item.return_value = False
        
        payload = {
            "new_parent_path": "/new/location/"
        }
        
        response = client.put("/api/documents/non-existent/move", json=payload)
        
        assert response.status_code == 404


class TestValidation:
    """Test validation endpoints"""
    
    def test_validate_title_unique(self, client, mock_document_service):
        """Test title uniqueness validation"""
        mock_document_service.title_exists.return_value = False
        
        response = client.get("/api/documents/validate-title?title=Unique Title&document_type=note")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_unique"] is True
        
        mock_document_service.title_exists.assert_called_once_with(
            "Unique Title", "note", None
        )

    def test_validate_title_exists(self, client, mock_document_service):
        """Test title exists validation"""
        mock_document_service.title_exists.return_value = True
        
        response = client.get("/api/documents/validate-title?title=Existing Title&document_type=note")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_unique"] is False

    def test_validate_title_with_exclusion(self, client, mock_document_service):
        """Test title validation excluding specific document"""
        mock_document_service.title_exists.return_value = False
        
        response = client.get("/api/documents/validate-title?title=Title&document_type=note&exclude_id=same-doc")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_unique"] is True
        
        mock_document_service.title_exists.assert_called_once_with(
            "Title", "note", "same-doc"
        )


class TestTemplateProcessing:
    """Test template processing endpoints"""
    
    def test_process_template_content(self, client, mock_document_service):
        """Test processing template variables in content"""
        mock_document_service.process_template.return_value = "Hello John, today is Monday"
        
        payload = {
            "content": "Hello {{USER_NAME}}, today is {{DAY_OF_WEEK}}",
            "target_date": "2023-01-01"
        }
        
        response = client.post("/api/documents/process-template", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["original_content"] == "Hello {{USER_NAME}}, today is {{DAY_OF_WEEK}}"
        assert data["resolved_content"] == "Hello John, today is Monday"
        assert data["variables_resolved"] == 2

    def test_validate_template_content(self, client, mock_document_service):
        """Test validating template variables"""
        validation_result = {
            "is_valid": True,
            "total_variables": 2,
            "valid_variables": ["USER_NAME", "DAY_OF_WEEK"],
            "invalid_variables": [],
            "supported_sources": ["user", "calendar"],
            "supported_time_ranges": ["today", "yesterday", "last_week"]
        }
        mock_document_service.validate_template.return_value = validation_result
        
        payload = {
            "content": "Hello {{USER_NAME}}, today is {{DAY_OF_WEEK}}"
        }
        
        response = client.post("/api/documents/validate-template", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["total_variables"] == 2
        assert len(data["valid_variables"]) == 2
        assert len(data["invalid_variables"]) == 0

    def test_process_document_template(self, client, mock_document_service):
        """Test processing template in specific document"""
        # Mock getting the document
        doc_with_template = create_sample_document("prompt", "Template Prompt", "template-123")
        doc_with_template.content_md = "Hello {{USER_NAME}}"
        mock_document_service.get_document.return_value = doc_with_template
        mock_document_service.process_template.return_value = "Hello John"
        
        response = client.post("/api/documents/template-123/process-template")
        
        assert response.status_code == 200
        data = response.json()
        assert data["original_content"] == "Hello {{USER_NAME}}"
        assert data["resolved_content"] == "Hello John"

    def test_process_document_template_not_found(self, client, mock_document_service):
        """Test processing template for non-existent document"""
        mock_document_service.get_document.return_value = None
        
        response = client.post("/api/documents/non-existent/process-template")
        
        assert response.status_code == 404


class TestHealthEndpoint:
    """Test service health endpoint"""
    
    def test_get_service_health(self, client, mock_document_service):
        """Test getting service health status"""
        health_info = {
            "status": "healthy",
            "database_connected": True,
            "vector_store_connected": True,
            "document_count": 150
        }
        mock_document_service._check_service_health.return_value = health_info
        
        response = client.get("/api/documents/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database_connected"] is True
        assert data["document_count"] == 150


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_service_unavailable(self):
        """Test handling when document service is unavailable"""
        # Create a fresh app without dependency overrides for this test
        from fastapi import FastAPI
        from core.dependencies import get_startup_service_dependency
        
        # Override dependency to return startup service without document service
        mock_startup = MagicMock(spec=StartupService)
        mock_startup.document_service = None
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup
        
        with TestClient(app) as test_client:
            response = test_client.get("/api/documents")
            
            assert response.status_code == 503
            assert "Document service not available" in response.json()["detail"]

    def test_unexpected_service_error(self, client, mock_document_service):
        """Test handling unexpected service errors"""
        mock_document_service.list_documents.side_effect = Exception("Database connection lost")
        
        response = client.get("/api/documents")
        
        assert response.status_code == 500
        assert "Failed to list documents" in response.json()["detail"]