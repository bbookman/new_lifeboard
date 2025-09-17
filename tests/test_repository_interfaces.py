"""
Unit tests for repository interface compliance

These tests verify that the repository interfaces are properly defined
with correct method signatures and abstract implementations.
"""

import pytest
import inspect
from abc import ABC
from typing import get_type_hints

from core.repositories.interfaces import (
    IDataItemRepository,
    ISettingsRepository, 
    IChatRepository,
    IDataSourceRepository
)


class TestRepositoryInterfaceDefinitions:
    """Test that repository interfaces are properly defined as abstract base classes"""
    
    def test_data_item_repository_is_abstract(self):
        """Verify IDataItemRepository is an abstract base class"""
        assert issubclass(IDataItemRepository, ABC)
        assert IDataItemRepository.__abstractmethods__
        
        # Verify we cannot instantiate directly
        with pytest.raises(TypeError):
            IDataItemRepository()
    
    def test_settings_repository_is_abstract(self):
        """Verify ISettingsRepository is an abstract base class"""
        assert issubclass(ISettingsRepository, ABC)
        assert ISettingsRepository.__abstractmethods__
        
        with pytest.raises(TypeError):
            ISettingsRepository()
    
    def test_chat_repository_is_abstract(self):
        """Verify IChatRepository is an abstract base class"""
        assert issubclass(IChatRepository, ABC)
        assert IChatRepository.__abstractmethods__
        
        with pytest.raises(TypeError):
            IChatRepository()
    
    def test_data_source_repository_is_abstract(self):
        """Verify IDataSourceRepository is an abstract base class"""
        assert issubclass(IDataSourceRepository, ABC)
        assert IDataSourceRepository.__abstractmethods__
        
        with pytest.raises(TypeError):
            IDataSourceRepository()


class TestDataItemRepositoryInterface:
    """Test IDataItemRepository interface method signatures"""
    
    def test_has_required_sync_methods(self):
        """Verify all required synchronous methods are present"""
        required_methods = [
            'store_data_item',
            'get_data_items_by_ids',
            'get_data_items_by_namespace',
            'get_data_items_by_date_range',
            'get_data_items_by_date',
            'get_available_dates',
            'get_days_with_data',
            'get_all_namespaces',
            'update_embedding_status',
            'update_ingestion_status',
            'get_pending_embeddings'
        ]
        
        interface_methods = [name for name, method in inspect.getmembers(IDataItemRepository, predicate=inspect.isfunction)]
        
        for method_name in required_methods:
            assert method_name in interface_methods, f"Missing required method: {method_name}"
    
    def test_has_required_async_methods(self):
        """Verify all required asynchronous methods are present"""
        required_async_methods = [
            'async_store_data_item',
            'async_get_data_items_by_ids',
            'async_get_data_items_by_namespace',
            'async_get_data_items_by_date_range',
            'async_get_data_items_by_date',
            'async_get_available_dates',
            'async_get_days_with_data',
            'async_get_all_namespaces',
            'async_update_embedding_status',
            'async_update_ingestion_status',
            'async_get_pending_embeddings'
        ]
        
        interface_methods = [name for name, method in inspect.getmembers(IDataItemRepository, predicate=inspect.isfunction)]
        
        for method_name in required_async_methods:
            assert method_name in interface_methods, f"Missing required async method: {method_name}"
    
    def test_store_data_item_signature(self):
        """Verify store_data_item has correct signature"""
        method = getattr(IDataItemRepository, 'store_data_item')
        sig = inspect.signature(method)
        
        # Check parameter names (excluding 'self')
        params = list(sig.parameters.keys())[1:]  # Skip 'self'
        expected_params = ['id', 'namespace', 'source_id', 'content', 'metadata', 'days_date', 'ingestion_status']
        assert params == expected_params
        
        # Check default values
        assert sig.parameters['metadata'].default is None
        assert sig.parameters['days_date'].default is None
        assert sig.parameters['ingestion_status'].default == 'complete'
    
    def test_get_data_items_by_ids_signature(self):
        """Verify get_data_items_by_ids has correct signature"""
        method = getattr(IDataItemRepository, 'get_data_items_by_ids')
        sig = inspect.signature(method)
        
        params = list(sig.parameters.keys())[1:]  # Skip 'self'
        assert params == ['ids']


class TestSettingsRepositoryInterface:
    """Test ISettingsRepository interface method signatures"""
    
    def test_has_required_methods(self):
        """Verify all required methods are present"""
        required_methods = ['get_setting', 'set_setting', 'async_get_setting', 'async_set_setting']
        
        interface_methods = [name for name, method in inspect.getmembers(ISettingsRepository, predicate=inspect.isfunction)]
        
        for method_name in required_methods:
            assert method_name in interface_methods, f"Missing required method: {method_name}"
    
    def test_get_setting_signature(self):
        """Verify get_setting has correct signature"""
        method = getattr(ISettingsRepository, 'get_setting')
        sig = inspect.signature(method)
        
        params = list(sig.parameters.keys())[1:]  # Skip 'self'
        assert params == ['key', 'default']
        assert sig.parameters['default'].default is None


class TestChatRepositoryInterface:
    """Test IChatRepository interface method signatures"""
    
    def test_has_required_methods(self):
        """Verify all required methods are present"""
        required_methods = [
            'store_chat_message', 'get_chat_history',
            'async_store_chat_message', 'async_get_chat_history'
        ]
        
        interface_methods = [name for name, method in inspect.getmembers(IChatRepository, predicate=inspect.isfunction)]
        
        for method_name in required_methods:
            assert method_name in interface_methods, f"Missing required method: {method_name}"
    
    def test_get_chat_history_signature(self):
        """Verify get_chat_history has correct signature"""
        method = getattr(IChatRepository, 'get_chat_history')
        sig = inspect.signature(method)
        
        params = list(sig.parameters.keys())[1:]  # Skip 'self'
        assert params == ['limit']
        assert sig.parameters['limit'].default == 50


class TestDataSourceRepositoryInterface:
    """Test IDataSourceRepository interface method signatures"""
    
    def test_has_required_methods(self):
        """Verify all required methods are present"""
        required_methods = [
            'register_data_source', 'get_active_namespaces', 'update_source_item_count',
            'async_register_data_source', 'async_get_active_namespaces', 'async_update_source_item_count'
        ]
        
        interface_methods = [name for name, method in inspect.getmembers(IDataSourceRepository, predicate=inspect.isfunction)]
        
        for method_name in required_methods:
            assert method_name in interface_methods, f"Missing required method: {method_name}"
    
    def test_register_data_source_signature(self):
        """Verify register_data_source has correct signature"""
        method = getattr(IDataSourceRepository, 'register_data_source')
        sig = inspect.signature(method)
        
        params = list(sig.parameters.keys())[1:]  # Skip 'self'
        assert params == ['namespace', 'source_type', 'metadata']
        assert sig.parameters['metadata'].default is None


class TestInterfaceConsistency:
    """Test consistency between sync and async method signatures"""
    
    def test_data_item_repository_sync_async_consistency(self):
        """Verify sync and async methods have matching signatures"""
        sync_methods = [name for name in dir(IDataItemRepository) 
                       if not name.startswith('async_') and not name.startswith('_')]
        
        for sync_method_name in sync_methods:
            async_method_name = f"async_{sync_method_name}"
            
            if hasattr(IDataItemRepository, async_method_name):
                sync_method = getattr(IDataItemRepository, sync_method_name)
                async_method = getattr(IDataItemRepository, async_method_name)
                
                sync_sig = inspect.signature(sync_method)
                async_sig = inspect.signature(async_method)
                
                # Parameters should be identical
                assert list(sync_sig.parameters.keys()) == list(async_sig.parameters.keys()), \
                    f"Parameter mismatch between {sync_method_name} and {async_method_name}"
    
    def test_settings_repository_sync_async_consistency(self):
        """Verify sync and async methods have matching signatures in settings repository"""
        sync_methods = [name for name in dir(ISettingsRepository) 
                       if not name.startswith('async_') and not name.startswith('_')]
        
        for sync_method_name in sync_methods:
            async_method_name = f"async_{sync_method_name}"
            
            if hasattr(ISettingsRepository, async_method_name):
                sync_method = getattr(ISettingsRepository, sync_method_name)
                async_method = getattr(ISettingsRepository, async_method_name)
                
                sync_sig = inspect.signature(sync_method)
                async_sig = inspect.signature(async_method)
                
                assert list(sync_sig.parameters.keys()) == list(async_sig.parameters.keys()), \
                    f"Parameter mismatch between {sync_method_name} and {async_method_name}"


class TestTypeHints:
    """Test that type hints are properly defined"""
    
    def test_data_item_repository_type_hints(self):
        """Verify IDataItemRepository methods have proper type hints"""
        # Test a few key methods for type hint presence
        store_method = getattr(IDataItemRepository, 'store_data_item')
        get_method = getattr(IDataItemRepository, 'get_data_items_by_ids')
        
        # These should not raise errors and should return type information
        store_hints = get_type_hints(store_method)
        get_hints = get_type_hints(get_method)
        
        # Basic verification that hints exist
        assert len(store_hints) > 0, "store_data_item should have type hints"
        assert len(get_hints) > 0, "get_data_items_by_ids should have type hints"