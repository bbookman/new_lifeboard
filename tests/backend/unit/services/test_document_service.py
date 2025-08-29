"""
Unit tests for DocumentService

Tests cover CRUD operations for Folder, Note, Prompt, and Link document types,
including validation, error handling, and edge cases.
"""

import pytest
import pytest_asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from services.document_service import DocumentService, Document
from core.async_database import AsyncDatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from config.models import AppConfig, DocumentsConfig


@pytest.fixture
def mock_database():
    """Mock AsyncDatabaseService"""
    mock_db = AsyncMock(spec=AsyncDatabaseService)
    mock_db.execute_query = AsyncMock()
    mock_db.execute_query_with_params = AsyncMock()
    mock_db.fetch_one = AsyncMock()
    mock_db.fetch_all = AsyncMock()
    return mock_db


@pytest.fixture
def mock_vector_store():
    """Mock VectorStoreService"""
    mock_vs = MagicMock(spec=VectorStoreService)
    mock_vs.add_item = AsyncMock()
    mock_vs.search = AsyncMock()
    mock_vs.update_item = AsyncMock()
    mock_vs.remove_item = AsyncMock()
    return mock_vs


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService"""
    mock_es = MagicMock(spec=EmbeddingService)
    mock_es.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return mock_es


@pytest.fixture
def mock_config():
    """Mock AppConfig"""
    doc_config = DocumentsConfig(
        max_title_length=200,
        max_content_length=10000
    )
    config = MagicMock(spec=AppConfig)
    config.documents = doc_config
    return config


@pytest.fixture
def document_service(mock_database, mock_vector_store, mock_embedding_service, mock_config):
    """Create DocumentService instance with mocked dependencies"""
    return DocumentService(
        database=mock_database,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        config=mock_config
    )


class TestDocumentCreation:
    """Test document creation for all types"""
    
    @pytest.mark.asyncio
    async def test_create_note_document(self, document_service, mock_database):
        """Test creating a note document"""
        # Mock database response
        mock_database.execute_query_with_params.return_value = None
        
        content_delta = {"ops": [{"insert": "Test note content\n"}]}
        
        result = await document_service.create_document(
            title="Test Note",
            document_type="note",
            content_delta=content_delta,
            path="/test/"
        )
        
        assert isinstance(result, Document)
        assert result.title == "Test Note"
        assert result.document_type == "note"
        assert result.content_delta == content_delta
        assert result.path == "/test/"
        assert not result.is_folder
        assert result.url is None
        
        # Verify database call
        mock_database.execute_query_with_params.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_prompt_document(self, document_service, mock_database):
        """Test creating a prompt document"""
        mock_database.execute_query_with_params.return_value = None
        
        content_delta = {"ops": [{"insert": "You are a helpful assistant {{USER_CONTEXT}}\n"}]}
        
        result = await document_service.create_document(
            title="Assistant Prompt",
            document_type="prompt",
            content_delta=content_delta,
            path="/"
        )
        
        assert result.title == "Assistant Prompt"
        assert result.document_type == "prompt"
        assert result.content_delta == content_delta
        assert not result.is_folder

    @pytest.mark.asyncio
    async def test_create_link_document(self, document_service, mock_database):
        """Test creating a link document"""
        mock_database.execute_query_with_params.return_value = None
        
        content_delta = {"ops": [{"insert": "Link description\n"}]}
        
        result = await document_service.create_document(
            title="Useful Link",
            document_type="link",
            content_delta=content_delta,
            path="/",
            url="https://example.com"
        )
        
        assert result.title == "Useful Link"
        assert result.document_type == "link"
        assert result.url == "https://example.com"
        assert not result.is_folder

    @pytest.mark.asyncio
    async def test_create_folder(self, document_service, mock_database):
        """Test creating a folder"""
        mock_database.execute_query_with_params.return_value = None
        
        result = await document_service.create_folder(
            name="Test Folder",
            parent_path="/"
        )
        
        assert result.title == "Test Folder"
        assert result.document_type == "folder"
        assert result.is_folder
        assert result.path == "/Test Folder/"

    @pytest.mark.asyncio
    async def test_create_document_invalid_type(self, document_service):
        """Test creating document with invalid type"""
        with pytest.raises(ValueError, match="Document type must be"):
            await document_service.create_document(
                title="Invalid",
                document_type="invalid_type",
                content_delta={"ops": [{"insert": "\n"}]},
                path="/"
            )

    @pytest.mark.asyncio
    async def test_create_document_title_too_long(self, document_service):
        """Test creating document with title too long"""
        long_title = "x" * 201  # Exceeds max_title_length of 200
        
        with pytest.raises(ValueError, match="Title too long"):
            await document_service.create_document(
                title=long_title,
                document_type="note",
                content_delta={"ops": [{"insert": "\n"}]},
                path="/"
            )

    @pytest.mark.asyncio
    async def test_create_document_content_too_long(self, document_service):
        """Test creating document with content too long"""
        long_content = {"ops": [{"insert": "x" * 10001 + "\n"}]}  # Exceeds max_content_length
        
        with pytest.raises(ValueError, match="Content too long"):
            await document_service.create_document(
                title="Test",
                document_type="note",
                content_delta=long_content,
                path="/"
            )


class TestDocumentRetrieval:
    """Test document retrieval operations"""
    
    @pytest.mark.asyncio
    async def test_get_document_by_id(self, document_service, mock_database):
        """Test getting a document by ID"""
        # Mock database response
        mock_row = {
            'id': 'test-id',
            'title': 'Test Document',
            'document_type': 'note',
            'content_delta': '{"ops":[{"insert":"Test\\n"}]}',
            'content_md': 'Test',
            'path': '/test/',
            'is_folder': 0,
            'url': None,
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z'
        }
        mock_database.fetch_one.return_value = mock_row
        
        result = document_service.get_document("test-id")
        
        assert result is not None
        assert result.id == "test-id"
        assert result.title == "Test Document"
        assert result.document_type == "note"
        assert not result.is_folder

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, document_service, mock_database):
        """Test getting a non-existent document"""
        mock_database.fetch_one.return_value = None
        
        result = document_service.get_document("non-existent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_list_documents_all_types(self, document_service, mock_database):
        """Test listing documents of all types"""
        mock_rows = [
            {
                'id': 'note-1',
                'title': 'Note 1',
                'document_type': 'note',
                'content_delta': '{"ops":[{"insert":"Note content\\n"}]}',
                'content_md': 'Note content',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            },
            {
                'id': 'prompt-1',
                'title': 'Prompt 1',
                'document_type': 'prompt',
                'content_delta': '{"ops":[{"insert":"Prompt content\\n"}]}',
                'content_md': 'Prompt content',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            },
            {
                'id': 'folder-1',
                'title': 'Folder 1',
                'document_type': 'folder',
                'content_delta': '{"ops":[{"insert":"\\n"}]}',
                'content_md': '',
                'path': '/Folder 1/',
                'is_folder': 1,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
        ]
        mock_database.fetch_all.return_value = mock_rows
        
        results = document_service.list_documents(limit=10, offset=0)
        
        assert len(results) == 3
        assert results[0].document_type == "note"
        assert results[1].document_type == "prompt"
        assert results[2].document_type == "folder"
        assert results[2].is_folder

    @pytest.mark.asyncio
    async def test_list_documents_by_type(self, document_service, mock_database):
        """Test listing documents filtered by type"""
        mock_rows = [
            {
                'id': 'note-1',
                'title': 'Note 1',
                'document_type': 'note',
                'content_delta': '{"ops":[{"insert":"Note content\\n"}]}',
                'content_md': 'Note content',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
        ]
        mock_database.fetch_all.return_value = mock_rows
        
        results = document_service.list_documents(document_type="note", limit=10, offset=0)
        
        assert len(results) == 1
        assert results[0].document_type == "note"

    @pytest.mark.asyncio
    async def test_list_folder_contents(self, document_service, mock_database):
        """Test listing folder contents"""
        mock_rows = [
            {
                'id': 'subfolder-1',
                'title': 'Subfolder',
                'document_type': 'folder',
                'content_delta': '{"ops":[{"insert":"\\n"}]}',
                'content_md': '',
                'path': '/test/Subfolder/',
                'is_folder': 1,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            },
            {
                'id': 'note-1',
                'title': 'Note in Folder',
                'document_type': 'note',
                'content_delta': '{"ops":[{"insert":"Note content\\n"}]}',
                'content_md': 'Note content',
                'path': '/test/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
        ]
        mock_database.fetch_all.return_value = mock_rows
        
        results = document_service.list_folder_contents("/test/", include_folders=True)
        
        assert len(results) == 2
        assert results[0].is_folder
        assert not results[1].is_folder


class TestDocumentSearch:
    """Test document search functionality"""
    
    @pytest.mark.asyncio
    async def test_search_documents(self, document_service, mock_database, mock_vector_store):
        """Test searching documents"""
        # Mock vector store search results
        mock_vector_store.search.return_value = [
            ("doc-1", 0.9),
            ("doc-2", 0.8)
        ]
        
        # Mock database fetch for found documents
        mock_documents = [
            {
                'id': 'doc-1',
                'title': 'Matching Document 1',
                'document_type': 'note',
                'content_delta': '{"ops":[{"insert":"Searchable content\\n"}]}',
                'content_md': 'Searchable content',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            },
            {
                'id': 'doc-2',
                'title': 'Matching Document 2',
                'document_type': 'prompt',
                'content_delta': '{"ops":[{"insert":"Another match\\n"}]}',
                'content_md': 'Another match',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
        ]
        mock_database.fetch_all.return_value = mock_documents
        
        results = await document_service.search_documents("search query", limit=10)
        
        assert len(results) == 2
        assert results[0][0].title == "Matching Document 1"
        assert results[0][1] == 0.9  # Score
        assert results[1][0].title == "Matching Document 2"
        assert results[1][1] == 0.8  # Score

    @pytest.mark.asyncio
    async def test_search_documents_by_type(self, document_service, mock_database, mock_vector_store):
        """Test searching documents filtered by type"""
        mock_vector_store.search.return_value = [("doc-1", 0.9)]
        
        mock_documents = [
            {
                'id': 'doc-1',
                'title': 'Matching Prompt',
                'document_type': 'prompt',
                'content_delta': '{"ops":[{"insert":"Prompt content\\n"}]}',
                'content_md': 'Prompt content',
                'path': '/',
                'is_folder': 0,
                'url': None,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
        ]
        mock_database.fetch_all.return_value = mock_documents
        
        results = document_service.search_documents("query", document_type="prompt", limit=10)
        
        assert len(results) == 1
        assert results[0][0].document_type == "prompt"


class TestDocumentUpdate:
    """Test document update operations"""
    
    @pytest.mark.asyncio
    async def test_update_document(self, document_service, mock_database):
        """Test updating a document"""
        # Mock existing document
        existing_doc = {
            'id': 'test-id',
            'title': 'Original Title',
            'document_type': 'note',
            'content_delta': '{"ops":[{"insert":"Original content\\n"}]}',
            'content_md': 'Original content',
            'path': '/',
            'is_folder': 0,
            'url': None,
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z'
        }
        mock_database.fetch_one.return_value = existing_doc
        mock_database.execute_query_with_params.return_value = None
        
        new_content = {"ops": [{"insert": "Updated content\n"}]}
        
        result = await document_service.update_document(
            doc_id="test-id",
            title="Updated Title",
            content_delta=new_content
        )
        
        assert result.title == "Updated Title"
        assert result.content_delta == new_content
        
        # Verify database update call
        mock_database.execute_query_with_params.assert_called()

    @pytest.mark.asyncio
    async def test_update_link_document_url(self, document_service, mock_database):
        """Test updating a link document's URL"""
        existing_doc = {
            'id': 'link-id',
            'title': 'Link Doc',
            'document_type': 'link',
            'content_delta': '{"ops":[{"insert":"Link content\\n"}]}',
            'content_md': 'Link content',
            'path': '/',
            'is_folder': 0,
            'url': 'https://old-url.com',
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z'
        }
        mock_database.fetch_one.return_value = existing_doc
        mock_database.execute_query_with_params.return_value = None
        
        result = await document_service.update_document(
            doc_id="link-id",
            url="https://new-url.com"
        )
        
        assert result.url == "https://new-url.com"


class TestDocumentDeletion:
    """Test document deletion operations"""
    
    @pytest.mark.asyncio
    async def test_delete_document(self, document_service, mock_database):
        """Test deleting a document"""
        mock_database.execute_query_with_params.return_value = MagicMock(rowcount=1)
        
        result = await document_service.delete_document("test-id")
        
        assert result is True
        mock_database.execute_query_with_params.assert_called()

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, document_service, mock_database):
        """Test deleting a non-existent document"""
        mock_database.execute_query_with_params.return_value = MagicMock(rowcount=0)
        
        result = await document_service.delete_document("non-existent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_folder_empty(self, document_service, mock_database):
        """Test deleting an empty folder"""
        # Mock folder check - folder exists and is empty
        mock_database.fetch_one.side_effect = [
            {'count': 1},  # Folder exists
            {'count': 0}   # Folder is empty
        ]
        mock_database.execute_query_with_params.return_value = MagicMock(rowcount=1)
        
        result = await document_service.delete_folder("/test/folder/", recursive=False)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_folder_with_contents_no_recursive(self, document_service, mock_database):
        """Test deleting a folder with contents without recursive flag"""
        # Mock folder check - folder exists and has contents
        mock_database.fetch_one.side_effect = [
            {'count': 1},  # Folder exists
            {'count': 2}   # Folder has contents
        ]
        
        with pytest.raises(ValueError, match="Folder is not empty"):
            await document_service.delete_folder("/test/folder/", recursive=False)

    @pytest.mark.asyncio
    async def test_delete_folder_recursive(self, document_service, mock_database):
        """Test deleting a folder recursively"""
        # Mock folder check - folder exists and has contents
        mock_database.fetch_one.return_value = {'count': 1}  # Folder exists
        mock_database.execute_query_with_params.return_value = MagicMock(rowcount=3)  # 3 items deleted
        
        result = await document_service.delete_folder("/test/folder/", recursive=True)
        
        assert result is True


class TestValidation:
    """Test validation functions"""
    
    def test_title_exists(self, document_service, mock_database):
        """Test title existence validation"""
        mock_database.fetch_one.return_value = {'count': 1}
        
        result = document_service.title_exists("Existing Title", "note")
        
        assert result is True

    def test_title_unique(self, document_service, mock_database):
        """Test unique title validation"""
        mock_database.fetch_one.return_value = {'count': 0}
        
        result = document_service.title_exists("Unique Title", "note")
        
        assert result is False

    def test_title_exists_exclude_id(self, document_service, mock_database):
        """Test title existence with exclusion"""
        mock_database.fetch_one.return_value = {'count': 0}
        
        result = document_service.title_exists("Title", "note", exclude_id="same-doc-id")
        
        assert result is False


class TestMoveOperations:
    """Test document move operations"""
    
    @pytest.mark.asyncio
    async def test_move_document(self, document_service, mock_database):
        """Test moving a document to new folder"""
        # Mock document exists
        mock_database.fetch_one.return_value = {'count': 1}
        mock_database.execute_query_with_params.return_value = MagicMock(rowcount=1)
        
        result = await document_service.move_item("doc-id", "/new/path/")
        
        assert result is True
        mock_database.execute_query_with_params.assert_called()

    @pytest.mark.asyncio
    async def test_move_folder(self, document_service, mock_database):
        """Test moving a folder"""
        # Mock folder exists
        mock_database.fetch_one.return_value = {'count': 1}
        mock_database.execute_query_with_params.return_value = MagicMock(rowcount=1)
        
        result = await document_service.move_item("folder-id", "/new/location/")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_move_item_not_found(self, document_service, mock_database):
        """Test moving non-existent item"""
        mock_database.fetch_one.return_value = {'count': 0}
        
        result = await document_service.move_item("non-existent", "/path/")
        
        assert result is False


class TestCountOperations:
    """Test document counting operations"""
    
    def test_count_documents_all(self, document_service, mock_database):
        """Test counting all documents"""
        mock_database.fetch_one.return_value = {'count': 15}
        
        result = document_service.count_documents()
        
        assert result == 15

    def test_count_documents_by_type(self, document_service, mock_database):
        """Test counting documents by type"""
        mock_database.fetch_one.return_value = {'count': 8}
        
        result = document_service.count_documents(document_type="note")
        
        assert result == 8

    def test_count_documents_in_folder(self, document_service, mock_database):
        """Test counting documents in specific folder"""
        mock_database.fetch_one.return_value = {'count': 3}
        
        result = document_service.count_documents(folder_path="/test/")
        
        assert result == 3


class TestUtilityFunctions:
    """Test utility and helper functions"""
    
    def test_delta_to_markdown_conversion(self, document_service):
        """Test Delta to Markdown conversion"""
        delta = {
            "ops": [
                {"insert": "Hello "},
                {"insert": "World", "attributes": {"bold": True}},
                {"insert": "\n"}
            ]
        }
        
        result = document_service._delta_to_markdown(delta)
        
        # Should contain markdown elements
        assert "Hello" in result
        assert "World" in result

    def test_markdown_to_delta_conversion(self, document_service):
        """Test Markdown to Delta conversion"""
        markdown = "# Heading\n\nSome **bold** text.\n"
        
        result = document_service._markdown_to_delta(markdown)
        
        assert "ops" in result
        assert isinstance(result["ops"], list)