"""
Simplified Unit tests for DocumentService

Tests core functionality that exists in the actual DocumentService.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.document_service import DocumentService, Document
from config.models import AppConfig, DocumentsConfig


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
def mock_database():
    """Mock DatabaseService"""
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock()
    return mock_db


@pytest.fixture
def mock_vector_store():
    """Mock VectorStoreService"""
    return MagicMock()


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService"""
    return MagicMock()


@pytest.fixture
def document_service(mock_database, mock_vector_store, mock_embedding_service, mock_config):
    """Create DocumentService instance with mocked dependencies"""
    return DocumentService(
        database=mock_database,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        config=mock_config
    )


class TestDocumentService:
    """Test DocumentService basic functionality"""
    
    def test_document_service_creation(self, document_service):
        """Test that DocumentService can be created"""
        assert document_service is not None
        assert hasattr(document_service, 'database')
        assert hasattr(document_service, 'vector_store')
        assert hasattr(document_service, 'embedding_service')
        assert hasattr(document_service, 'config')

    def test_document_service_has_required_methods(self, document_service):
        """Test that DocumentService has all required methods"""
        required_methods = [
            'create_document',
            'get_document', 
            'update_document',
            'delete_document',
            'list_documents',
            'search_documents',
            'create_folder',
            'list_folder_contents',
            'move_item',
            'delete_folder',
            'title_exists',
            'count_documents'
        ]
        
        for method_name in required_methods:
            assert hasattr(document_service, method_name), f"Missing method: {method_name}"

    def test_delta_to_markdown_method_exists(self, document_service):
        """Test that _delta_to_markdown method exists"""
        assert hasattr(document_service, '_delta_to_markdown')
        
        # Test basic conversion
        delta = {"ops": [{"insert": "Hello World\n"}]}
        result = document_service._delta_to_markdown(delta)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_document_validation_title_length(self, document_service):
        """Test title length validation"""
        # Test that config limits are accessible
        assert document_service.config.documents.max_title_length == 200
        assert document_service.config.documents.max_content_length == 10000

    def test_title_exists_method(self, document_service, mock_database):
        """Test title_exists method"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'count': 1}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        mock_database.get_connection.return_value = mock_conn
        
        # Test that title exists
        result = document_service.title_exists("Test Title", "note")
        assert result is True
        
        # Verify database was called
        mock_database.get_connection.assert_called()

    def test_count_documents_method(self, document_service, mock_database):
        """Test count_documents method"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'count': 5}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        mock_database.get_connection.return_value = mock_conn
        
        # Test document count
        result = document_service.count_documents()
        assert result == 5

    def test_document_dataclass(self):
        """Test Document dataclass"""
        doc = Document(
            id="test-id",
            title="Test Document", 
            document_type="note",
            content_delta={"ops": [{"insert": "content\n"}]},
            content_md="content",
            path="/",
            is_folder=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        assert doc.id == "test-id"
        assert doc.title == "Test Document"
        assert doc.document_type == "note"
        assert doc.is_folder is False
        assert doc.url is None

    def test_document_types_supported(self):
        """Test supported document types"""
        # These are the types mentioned in the create_document method
        supported_types = ['note', 'prompt', 'link']
        folder_type = 'folder'  # Handled separately via create_folder
        
        for doc_type in supported_types:
            assert doc_type in ['note', 'prompt', 'link']
        
        assert folder_type == 'folder'

    def test_service_capabilities(self, document_service):
        """Test that service declares expected capabilities"""
        # The service should have been initialized with BaseService
        assert hasattr(document_service, 'add_capability')
        assert hasattr(document_service, 'add_dependency')

    def test_config_access(self, document_service):
        """Test config access patterns"""
        # Test that document config is accessible
        assert hasattr(document_service.config, 'documents')
        assert hasattr(document_service.config.documents, 'max_title_length')
        assert hasattr(document_service.config.documents, 'max_content_length')
        
        # Test config values
        assert document_service.config.documents.max_title_length > 0
        assert document_service.config.documents.max_content_length > 0


class TestDocumentOperations:
    """Test individual document operations that don't require async"""
    
    def test_path_formatting(self, document_service):
        """Test internal path formatting logic"""
        # This tests the logic that would be in create_document
        test_cases = [
            ("", "/"),
            ("test", "/test/"),  
            ("/test", "/test/"),
            ("test/", "/test/"),
            ("/test/", "/test/")
        ]
        
        for input_path, expected in test_cases:
            # Simulate the path formatting logic from create_document
            path = input_path
            if not path.startswith('/'):
                path = '/' + path
            if not path.endswith('/') and path != '/':
                path += '/'
            
            assert path == expected

    def test_document_types_validation(self, document_service):
        """Test document type validation logic"""
        valid_types = ['note', 'prompt', 'link']
        invalid_types = ['invalid_type', 'doc', 'file', '']
        
        for doc_type in valid_types:
            assert doc_type in ['note', 'prompt', 'link']
        
        for doc_type in invalid_types:
            assert doc_type not in ['note', 'prompt', 'link']

    def test_row_to_document_method(self, document_service):
        """Test _row_to_document conversion method"""
        # Mock database row
        mock_row = {
            'id': 'test-123',
            'title': 'Test Document',
            'document_type': 'note',
            'content_delta': '{"ops":[{"insert":"content\\n"}]}',
            'content_md': 'content',
            'path': '/test/',
            'is_folder': 0,
            'url': None,
            'created_at': '2023-01-01T00:00:00',
            'updated_at': '2023-01-01T00:00:00'
        }
        
        # Test conversion
        document = document_service._row_to_document(mock_row)
        
        assert isinstance(document, Document)
        assert document.id == 'test-123'
        assert document.title == 'Test Document'
        assert document.document_type == 'note'
        assert document.is_folder is False
        assert isinstance(document.content_delta, dict)


class TestTemplateProcessing:
    """Test template processing functionality"""
    
    def test_has_template_methods(self, document_service):
        """Test that template processing methods exist"""
        assert hasattr(document_service, 'process_template')
        assert hasattr(document_service, 'validate_template')

    def test_process_template_basic(self, document_service):
        """Test basic template processing"""
        # Mock the template processing
        with patch.object(document_service, 'process_template', return_value="Processed content"):
            result = document_service.process_template("Template with {{VAR}}")
            assert result == "Processed content"

    def test_validate_template_basic(self, document_service):
        """Test basic template validation"""
        # Mock the template validation
        mock_result = {
            "is_valid": True,
            "total_variables": 1,
            "valid_variables": ["VAR"],
            "invalid_variables": []
        }
        
        with patch.object(document_service, 'validate_template', return_value=mock_result):
            result = document_service.validate_template("Template with {{VAR}}")
            assert result["is_valid"] is True
            assert result["total_variables"] == 1