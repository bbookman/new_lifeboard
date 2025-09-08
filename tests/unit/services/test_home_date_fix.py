"""
Test for home_date bug fix
"""
import pytest
import pytest_asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from services.document_service import DocumentService, Document
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from config.models import AppConfig, DocumentsConfig


@pytest.fixture
def mock_database():
    """Mock DatabaseService"""
    mock_db = MagicMock(spec=DatabaseService)
    mock_db.get_async_connection = MagicMock()
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
    mock_es.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
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


class TestHomeDateFix:
    """Test that home_date is properly stored and retrieved"""

    @pytest.mark.asyncio
    async def test_create_document_with_home_date(self, document_service, mock_database):
        """Test creating a document with a specific home_date"""
        # Mock database response
        mock_database.execute_query_with_params.return_value = None

        # Create a specific home_date
        test_home_date = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Create document with home_date
        doc = await document_service.create_document(
            title="Test Document",
            document_type="note",
            content_delta={"ops": [{"insert": "Test content\n"}]},
            home_date=test_home_date
        )

        # Verify home_date is set correctly
        assert doc.home_date == test_home_date
        assert doc.title == "Test Document"
        assert doc.document_type == "note"

    @pytest.mark.asyncio
    async def test_update_document_home_date(self, document_service, mock_database):
        """Test updating a document's home_date"""
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

        # Update with new home_date
        new_home_date = datetime(2024, 2, 20, 14, 45, 0, tzinfo=timezone.utc)
        updated_doc = await document_service.update_document(
            doc_id="test-id",
            home_date=new_home_date
        )

        # Verify home_date was updated
        assert updated_doc.home_date == new_home_date

    @pytest.mark.asyncio
    async def test_create_document_without_home_date(self, document_service, mock_database):
        """Test creating a document without specifying home_date (should default to now)"""
        # Mock database response
        mock_database.execute_query_with_params.return_value = None

        # Create document without home_date
        doc = await document_service.create_document(
            title="Test Document No Date",
            document_type="note",
            content_delta={"ops": [{"insert": "Test content\n"}]}
        )

        # Verify home_date is set to a reasonable time (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = abs((doc.home_date - now).total_seconds())
        assert time_diff < 60  # Should be within 1 minute

    @pytest.mark.asyncio
    async def test_folder_home_date(self, document_service, mock_database):
        """Test that folders get a reasonable home_date"""
        # Mock database response
        mock_database.execute_query_with_params.return_value = None

        folder = await document_service.create_folder("Test Folder")

        # Verify folder has a home_date
        assert folder.home_date is not None
        assert folder.is_folder is True

        # Verify it's a reasonable time (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = abs((folder.home_date - now).total_seconds())
        assert time_diff < 60  # Should be within 1 minute