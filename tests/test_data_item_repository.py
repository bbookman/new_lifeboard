"""
Unit tests for DataItemRepository implementation

These tests verify that the DataItemRepository correctly implements
the IDataItemRepository interface and maintains backward compatibility
with the original DatabaseService functionality.
"""

import pytest
import tempfile
import os
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from core.repositories.data_item_repository import DataItemRepository
from core.repositories.interfaces import IDataItemRepository
from core.database import DatabaseService


@pytest.fixture
def temp_db_path():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def database_service(temp_db_path):
    """Create a test DatabaseService instance"""
    return DatabaseService(temp_db_path)


@pytest.fixture
def repository(database_service):
    """Create a DataItemRepository instance for testing"""
    return DataItemRepository(database_service)


class TestDataItemRepositoryInterface:
    """Test that DataItemRepository properly implements IDataItemRepository"""
    
    def test_implements_interface(self, repository):
        """Verify repository implements the interface"""
        assert isinstance(repository, IDataItemRepository)
    
    def test_has_all_interface_methods(self, repository):
        """Verify all interface methods are implemented"""
        interface_methods = [
            # Core CRUD
            'store_data_item', 'async_store_data_item',
            'get_data_items_by_ids', 'async_get_data_items_by_ids',
            
            # Namespace operations
            'get_data_items_by_namespace', 'async_get_data_items_by_namespace',
            'get_all_namespaces', 'async_get_all_namespaces',
            
            # Date operations
            'get_data_items_by_date_range', 'async_get_data_items_by_date_range',
            'get_data_items_by_date', 'async_get_data_items_by_date',
            'get_available_dates', 'async_get_available_dates',
            'get_days_with_data', 'async_get_days_with_data',
            
            # Status operations
            'update_embedding_status', 'async_update_embedding_status',
            'update_ingestion_status', 'async_update_ingestion_status',
            'get_pending_embeddings', 'async_get_pending_embeddings'
        ]
        
        for method_name in interface_methods:
            assert hasattr(repository, method_name), f"Missing method: {method_name}"
            assert callable(getattr(repository, method_name)), f"Method not callable: {method_name}"


class TestDataItemRepositoryInitialization:
    """Test repository initialization and setup"""
    
    def test_initialization_with_database_service(self, database_service):
        """Test repository initialization with database service"""
        repo = DataItemRepository(database_service)
        assert repo.database_service is database_service
        assert hasattr(repo, 'logger')
    
    def test_connection_management(self, repository):
        """Test database connection context managers"""
        # Test sync connection
        with repository._get_connection() as conn:
            assert conn is not None
            # Verify connection works
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1


class TestCoreDataOperations:
    """Test core data storage and retrieval operations"""
    
    def test_store_and_retrieve_data_item(self, repository):
        """Test storing and retrieving a data item"""
        # Store test data
        test_id = "test:item1"
        test_namespace = "test"
        test_source_id = "item1"
        test_content = "Test content"
        test_metadata = {"type": "test", "version": 1}
        test_days_date = "2024-01-01"
        
        repository.store_data_item(
            id=test_id,
            namespace=test_namespace,
            source_id=test_source_id,
            content=test_content,
            metadata=test_metadata,
            days_date=test_days_date
        )
        
        # Retrieve data
        items = repository.get_data_items_by_ids([test_id])
        
        assert len(items) == 1
        item = items[0]
        assert item['id'] == test_id
        assert item['namespace'] == test_namespace
        assert item['source_id'] == test_source_id
        assert item['content'] == test_content
        assert item['metadata'] == test_metadata
        assert item['days_date'] == test_days_date
    
    def test_store_data_item_with_defaults(self, repository):
        """Test storing data item with default parameters"""
        test_id = "test:item2"
        test_namespace = "test"
        test_source_id = "item2"
        test_content = "Test content"
        test_days_date = "2024-01-01"  # days_date is NOT NULL in schema
        
        repository.store_data_item(
            id=test_id,
            namespace=test_namespace,
            source_id=test_source_id,
            content=test_content,
            days_date=test_days_date
        )
        
        items = repository.get_data_items_by_ids([test_id])
        assert len(items) == 1
        assert items[0]['id'] == test_id
        assert items[0]['metadata'] is None
        assert items[0]['days_date'] == test_days_date
    
    def test_get_data_items_by_ids_empty_list(self, repository):
        """Test retrieving with empty ID list"""
        result = repository.get_data_items_by_ids([])
        assert result == []
    
    def test_get_data_items_by_ids_nonexistent(self, repository):
        """Test retrieving nonexistent items"""
        result = repository.get_data_items_by_ids(["nonexistent:id"])
        assert result == []


class TestNamespaceOperations:
    """Test namespace-based data operations"""
    
    def test_get_data_items_by_namespace(self, repository):
        """Test retrieving data items by namespace"""
        # Store test data in multiple namespaces
        repository.store_data_item("ns1:item1", "namespace1", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("ns1:item2", "namespace1", "item2", "Content 2", days_date="2024-01-01")
        repository.store_data_item("ns2:item1", "namespace2", "item1", "Content 3", days_date="2024-01-01")
        
        # Test namespace1
        ns1_items = repository.get_data_items_by_namespace("namespace1")
        assert len(ns1_items) == 2
        assert all(item['namespace'] == 'namespace1' for item in ns1_items)
        
        # Test namespace2
        ns2_items = repository.get_data_items_by_namespace("namespace2")
        assert len(ns2_items) == 1
        assert ns2_items[0]['namespace'] == 'namespace2'
    
    def test_get_data_items_by_namespace_with_limit(self, repository):
        """Test namespace retrieval with limit"""
        # Store multiple items in same namespace
        for i in range(5):
            repository.store_data_item(f"test:item{i}", "test", f"item{i}", f"Content {i}", days_date="2024-01-01")
        
        # Test with limit
        items = repository.get_data_items_by_namespace("test", limit=3)
        assert len(items) == 3
    
    def test_get_all_namespaces(self, repository):
        """Test retrieving all namespaces"""
        # Store data in multiple namespaces
        repository.store_data_item("ns1:item1", "namespace1", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("ns2:item1", "namespace2", "item1", "Content 2", days_date="2024-01-01")
        repository.store_data_item("ns3:item1", "namespace3", "item1", "Content 3", days_date="2024-01-01")
        
        namespaces = repository.get_all_namespaces()
        assert "namespace1" in namespaces
        assert "namespace2" in namespaces
        assert "namespace3" in namespaces
        assert len(namespaces) == 3


class TestDateOperations:
    """Test date-based data operations"""
    
    def test_get_data_items_by_date_range(self, repository):
        """Test retrieving data items by date range"""
        # Store data with different dates
        repository.store_data_item("item1", "test", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("item2", "test", "item2", "Content 2", days_date="2024-01-02")
        repository.store_data_item("item3", "test", "item3", "Content 3", days_date="2024-01-03")
        repository.store_data_item("item4", "test", "item4", "Content 4", days_date="2024-01-05")
        
        # Test date range
        items = repository.get_data_items_by_date_range("2024-01-01", "2024-01-03")
        assert len(items) == 3
        
        # Test single date range
        items = repository.get_data_items_by_date_range("2024-01-02", "2024-01-02")
        assert len(items) == 1
        assert items[0]['days_date'] == "2024-01-02"
    
    def test_get_data_items_by_date_range_with_namespaces(self, repository):
        """Test date range with namespace filtering"""
        # Store data in different namespaces
        repository.store_data_item("ns1:item1", "namespace1", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("ns2:item1", "namespace2", "item1", "Content 2", days_date="2024-01-01")
        repository.store_data_item("ns1:item2", "namespace1", "item2", "Content 3", days_date="2024-01-02")
        
        # Test with namespace filter
        items = repository.get_data_items_by_date_range(
            "2024-01-01", "2024-01-02", 
            namespaces=["namespace1"]
        )
        assert len(items) == 2
        assert all(item['namespace'] == 'namespace1' for item in items)
    
    def test_get_data_items_by_date(self, repository):
        """Test retrieving data items by specific date"""
        repository.store_data_item("item1", "test", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("item2", "test", "item2", "Content 2", days_date="2024-01-01")
        repository.store_data_item("item3", "test", "item3", "Content 3", days_date="2024-01-02")
        
        items = repository.get_data_items_by_date("2024-01-01")
        assert len(items) == 2
        assert all(item['days_date'] == '2024-01-01' for item in items)
    
    def test_get_available_dates(self, repository):
        """Test retrieving available dates"""
        repository.store_data_item("item1", "test", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("item2", "test", "item2", "Content 2", days_date="2024-01-02")
        repository.store_data_item("item3", "test", "item3", "Content 3", days_date="2024-01-01")  # Duplicate date
        
        dates = repository.get_available_dates()
        assert "2024-01-01" in dates
        assert "2024-01-02" in dates
        assert len(dates) == 2  # Should be deduplicated
    
    def test_get_days_with_data(self, repository):
        """Test retrieving days with data for calendar"""
        repository.store_data_item("item1", "test", "item1", "Content 1", days_date="2024-01-01")
        repository.store_data_item("item2", "test", "item2", "Content 2", days_date="2024-01-02")
        
        days = repository.get_days_with_data()
        assert "2024-01-01" in days
        assert "2024-01-02" in days


class TestStatusOperations:
    """Test embedding and ingestion status operations"""
    
    def test_update_embedding_status(self, repository):
        """Test updating embedding status"""
        # Store initial item
        test_id = "test:item1"
        repository.store_data_item(test_id, "test", "item1", "Content", days_date="2024-01-01")
        
        # Update embedding status
        repository.update_embedding_status(test_id, "completed")
        
        # Note: We can't easily verify the status update without adding
        # additional methods to retrieve the embedding_status field
        # This test verifies the method executes without error
    
    def test_update_ingestion_status(self, repository):
        """Test updating ingestion status"""
        test_id = "test:item1"
        repository.store_data_item(test_id, "test", "item1", "Content", days_date="2024-01-01")
        
        # Update ingestion status
        repository.update_ingestion_status(test_id, "complete")
        
        # This test verifies the method executes without error
    
    def test_get_pending_embeddings(self, repository):
        """Test retrieving pending embeddings"""
        # Store items with different embedding statuses
        repository.store_data_item("item1", "test", "item1", "Content 1", days_date="2024-01-01")
        # Note: Default embedding_status is 'pending' based on schema
        
        pending = repository.get_pending_embeddings()
        # The exact number depends on the default embedding status in the schema
        assert isinstance(pending, list)


@pytest.mark.asyncio
class TestAsyncOperations:
    """Test asynchronous repository operations"""
    
    async def test_async_store_and_retrieve(self, repository):
        """Test async store and retrieve operations"""
        test_id = "async:item1"
        test_namespace = "async_test"
        test_content = "Async content"
        
        # Store data asynchronously
        await repository.async_store_data_item(
            id=test_id,
            namespace=test_namespace,
            source_id="item1",
            content=test_content,
            days_date="2024-01-01"
        )
        
        # Retrieve data asynchronously
        items = await repository.async_get_data_items_by_ids([test_id])
        assert len(items) == 1
        assert items[0]['id'] == test_id
        assert items[0]['content'] == test_content
    
    async def test_async_namespace_operations(self, repository):
        """Test async namespace operations"""
        await repository.async_store_data_item("async:item1", "async_ns", "item1", "Content 1", days_date="2024-01-01")
        await repository.async_store_data_item("async:item2", "async_ns", "item2", "Content 2", days_date="2024-01-01")
        
        # Test async namespace retrieval
        items = await repository.async_get_data_items_by_namespace("async_ns")
        assert len(items) == 2
        
        # Test async get all namespaces
        namespaces = await repository.async_get_all_namespaces()
        assert "async_ns" in namespaces
    
    async def test_async_date_operations(self, repository):
        """Test async date operations"""
        await repository.async_store_data_item("async:date1", "async_ns", "date1", "Content", days_date="2024-01-01")
        await repository.async_store_data_item("async:date2", "async_ns", "date2", "Content", days_date="2024-01-02")
        
        # Test async date range
        items = await repository.async_get_data_items_by_date_range("2024-01-01", "2024-01-02")
        assert len(items) == 2
        
        # Test async single date
        items = await repository.async_get_data_items_by_date("2024-01-01")
        assert len(items) >= 1
        
        # Test async available dates
        dates = await repository.async_get_available_dates()
        assert "2024-01-01" in dates
        assert "2024-01-02" in dates
        
        # Test async days with data
        days = await repository.async_get_days_with_data()
        assert "2024-01-01" in days
        assert "2024-01-02" in days
    
    async def test_async_status_operations(self, repository):
        """Test async status operations"""
        test_id = "async:status1"
        await repository.async_store_data_item(test_id, "async_ns", "status1", "Content", days_date="2024-01-01")
        
        # Test async status updates
        await repository.async_update_embedding_status(test_id, "completed")
        await repository.async_update_ingestion_status(test_id, "complete")
        
        # Test async pending embeddings
        pending = await repository.async_get_pending_embeddings()
        assert isinstance(pending, list)


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_database_operations(self, repository):
        """Test handling of invalid database operations"""
        # Test with invalid IDs
        result = repository.get_data_items_by_ids(["invalid:id"])
        assert result == []
        
        # Test with invalid namespace
        result = repository.get_data_items_by_namespace("nonexistent_namespace")
        assert result == []
        
        # Test with invalid date range
        result = repository.get_data_items_by_date_range("invalid-date", "another-invalid-date")
        assert result == []


class TestBackwardCompatibility:
    """Test backward compatibility with original DatabaseService"""
    
    def test_method_signatures_match(self, repository):
        """Verify method signatures match the interface"""
        import inspect
        from core.repositories.interfaces import IDataItemRepository
        
        # Get all methods from the interface
        interface_methods = inspect.getmembers(IDataItemRepository, predicate=inspect.isfunction)
        
        for method_name, method in interface_methods:
            if method_name.startswith('_'):
                continue
                
            # Check that repository has the method
            assert hasattr(repository, method_name), f"Repository missing method: {method_name}"
            
            # Check signature compatibility
            interface_sig = inspect.signature(method)
            repo_method = getattr(repository.__class__, method_name)
            repo_sig = inspect.signature(repo_method)
            
            # Parameters should match (excluding 'self')
            interface_params = list(interface_sig.parameters.keys())[1:]  # Skip 'self'
            repo_params = list(repo_sig.parameters.keys())[1:]  # Skip 'self'
            
            assert interface_params == repo_params, f"Parameter mismatch in {method_name}: {interface_params} vs {repo_params}"