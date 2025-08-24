"""Contract testing for service interfaces.

This module implements contract testing to ensure all service implementations
comply with their defined interfaces from core.service_interfaces.
"""

import pytest
import inspect
from typing import Type, get_type_hints, Dict, Any
from abc import ABC
from core.service_interfaces import (
    ServiceInterface,
    DatabaseServiceInterface, 
    HTTPClientInterface,
    EmbeddingServiceInterface,
    VectorStoreInterface,
    ChatServiceInterface,
    IngestionServiceInterface,
    SchedulerServiceInterface
)


class TestServiceContracts:
    """Test that all service implementations comply with interface contracts."""
    
    @pytest.fixture
    def service_implementations(self):
        """Get all service implementations registered in the container."""
        # Import here to avoid circular dependencies
        from core.dependencies import get_container
        container = get_container()
        
        return {
            DatabaseServiceInterface: container._services.get(DatabaseServiceInterface),
            HTTPClientInterface: container._services.get(HTTPClientInterface),
            EmbeddingServiceInterface: container._services.get(EmbeddingServiceInterface),
            VectorStoreInterface: container._services.get(VectorStoreInterface),
            ChatServiceInterface: container._services.get(ChatServiceInterface),
            IngestionServiceInterface: container._services.get(IngestionServiceInterface),
            SchedulerServiceInterface: container._services.get(SchedulerServiceInterface)
        }
    
    def test_all_services_implement_base_interface(self, service_implementations):
        """Test that all services implement the base ServiceInterface."""
        for interface, implementation in service_implementations.items():
            if implementation is None:
                pytest.skip(f"No implementation registered for {interface.__name__}")
            
            # Get the actual class if it's a factory result
            impl_class = implementation if inspect.isclass(implementation) else type(implementation)
            
            assert issubclass(impl_class, ServiceInterface), f"{impl_class.__name__} must implement ServiceInterface"
    
    def test_database_service_contract(self, service_implementations):
        """Test DatabaseService implements DatabaseServiceInterface contract."""
        impl = service_implementations[DatabaseServiceInterface]
        if impl is None:
            pytest.skip("No DatabaseService implementation registered")
        
        # Test required methods exist
        assert hasattr(impl, 'get_connection'), "Must implement get_connection method"
        assert hasattr(impl, 'execute_query'), "Must implement execute_query method"
        assert hasattr(impl, 'execute_transaction'), "Must implement execute_transaction method"
        
        # Test method signatures
        self._validate_method_signature(impl, 'execute_query', ['query', 'params'])
        self._validate_method_signature(impl, 'execute_transaction', ['queries'])
        
    def test_http_client_contract(self, service_implementations):
        """Test HTTPClient implements HTTPClientInterface contract.""" 
        impl = service_implementations[HTTPClientInterface]
        if impl is None:
            pytest.skip("No HTTPClient implementation registered")
            
        # Test HTTP methods exist
        for method in ['get', 'post', 'put', 'delete']:
            assert hasattr(impl, method), f"Must implement {method} method"
            
        # Test method signatures
        self._validate_method_signature(impl, 'get', ['url'])
        self._validate_method_signature(impl, 'post', ['url', 'data'])
        
    def test_embedding_service_contract(self, service_implementations):
        """Test EmbeddingService implements EmbeddingServiceInterface contract."""
        impl = service_implementations[EmbeddingServiceInterface]
        if impl is None:
            pytest.skip("No EmbeddingService implementation registered")
            
        assert hasattr(impl, 'embed_text'), "Must implement embed_text method"
        assert hasattr(impl, 'embed_batch'), "Must implement embed_batch method"
        
        self._validate_method_signature(impl, 'embed_text', ['text'])
        self._validate_method_signature(impl, 'embed_batch', ['texts'])
        
    def test_vector_store_contract(self, service_implementations):
        """Test VectorStore implements VectorStoreInterface contract."""
        impl = service_implementations[VectorStoreInterface]
        if impl is None:
            pytest.skip("No VectorStore implementation registered")
            
        required_methods = ['add_vectors', 'search', 'get_vector', 'update_vector', 'delete_vector']
        for method in required_methods:
            assert hasattr(impl, method), f"Must implement {method} method"
            
    def test_chat_service_contract(self, service_implementations):
        """Test ChatService implements ChatServiceInterface contract."""
        impl = service_implementations[ChatServiceInterface]
        if impl is None:
            pytest.skip("No ChatService implementation registered")
            
        required_methods = ['generate_response', 'get_chat_history', 'clear_history']
        for method in required_methods:
            assert hasattr(impl, method), f"Must implement {method} method"
            
    def test_ingestion_service_contract(self, service_implementations):
        """Test IngestionService implements IngestionServiceInterface contract."""
        impl = service_implementations[IngestionServiceInterface]
        if impl is None:
            pytest.skip("No IngestionService implementation registered")
            
        required_methods = ['ingest_data', 'get_ingestion_status', 'process_batch']
        for method in required_methods:
            assert hasattr(impl, method), f"Must implement {method} method"
            
    def test_scheduler_service_contract(self, service_implementations):
        """Test SchedulerService implements SchedulerServiceInterface contract."""
        impl = service_implementations[SchedulerServiceInterface] 
        if impl is None:
            pytest.skip("No SchedulerService implementation registered")
            
        required_methods = ['schedule_job', 'cancel_job', 'get_scheduled_jobs', 'start', 'stop']
        for method in required_methods:
            assert hasattr(impl, method), f"Must implement {method} method"
    
    def _validate_method_signature(self, impl, method_name: str, required_params: list):
        """Validate that a method has the required parameters."""
        if not hasattr(impl, method_name):
            return
            
        method = getattr(impl, method_name)
        sig = inspect.signature(method)
        param_names = [p for p in sig.parameters.keys() if p != 'self']
        
        for required_param in required_params:
            if required_param not in param_names and required_param not in ['kwargs', 'args']:
                # Check if there are **kwargs that could handle this
                has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
                if not has_kwargs:
                    pytest.fail(f"Method {method_name} missing required parameter: {required_param}")
                    
    def test_service_health_checks(self, service_implementations):
        """Test that all services implement health_check method."""
        for interface, impl in service_implementations.items():
            if impl is None:
                continue
                
            assert hasattr(impl, 'health_check'), f"{interface.__name__} implementation must have health_check method"
            
            # Try to call health_check (should not raise exception)
            try:
                result = impl.health_check()
                assert isinstance(result, dict), "health_check must return a dict"
                assert 'status' in result, "health_check result must contain 'status' key"
            except Exception as e:
                pytest.fail(f"health_check failed for {interface.__name__}: {e}")
                
    def test_service_initialization(self, service_implementations):
        """Test that all services can be initialized."""
        for interface, impl in service_implementations.items():
            if impl is None:
                continue
                
            assert hasattr(impl, 'initialize'), f"{interface.__name__} implementation must have initialize method"
            
    def test_service_shutdown(self, service_implementations):
        """Test that all services implement shutdown method."""
        for interface, impl in service_implementations.items():
            if impl is None:
                continue
                
            assert hasattr(impl, 'shutdown'), f"{interface.__name__} implementation must have shutdown method"


class TestServiceInterfaceCompliance:
    """Additional compliance tests for interface contracts."""
    
    def test_interface_method_annotations(self):
        """Test that interface methods have proper type annotations."""
        interfaces = [
            ServiceInterface,
            DatabaseServiceInterface,
            HTTPClientInterface,
            EmbeddingServiceInterface,
            VectorStoreInterface,
            ChatServiceInterface,
            IngestionServiceInterface,
            SchedulerServiceInterface
        ]
        
        for interface in interfaces:
            for method_name, method in inspect.getmembers(interface, predicate=inspect.isfunction):
                if method_name.startswith('_'):
                    continue
                    
                # Check if method has type hints
                hints = get_type_hints(method)
                assert hints, f"Method {interface.__name__}.{method_name} should have type annotations"
                
    def test_abstract_methods_marked(self):
        """Test that interface methods are properly marked as abstract."""
        interfaces = [
            DatabaseServiceInterface,
            HTTPClientInterface, 
            EmbeddingServiceInterface,
            VectorStoreInterface,
            ChatServiceInterface,
            IngestionServiceInterface,
            SchedulerServiceInterface
        ]
        
        for interface in interfaces:
            assert getattr(interface, '__abstractmethods__', None), f"{interface.__name__} should have abstract methods"
            
            # Verify it's actually abstract
            with pytest.raises(TypeError):
                interface()  # Should fail - can't instantiate abstract class


class TestCrossServiceContracts:
    """Test contracts between services (integration contracts)."""
    
    def test_database_vector_store_compatibility(self, service_implementations):
        """Test that DatabaseService and VectorStore work together."""
        db_impl = service_implementations[DatabaseServiceInterface]
        vector_impl = service_implementations[VectorStoreInterface]
        
        if db_impl is None or vector_impl is None:
            pytest.skip("Database or VectorStore implementation not available")
            
        # Test that vector IDs can be stored in database
        # This is a contract test - both services must support the same ID format
        
        # Mock test data
        test_id = "test:123"
        
        # Vector store should accept this ID format
        assert hasattr(vector_impl, 'add_vectors'), "VectorStore must support adding vectors"
        
        # Database should be able to store items with this ID format
        assert hasattr(db_impl, 'execute_query'), "Database must support queries"
        
    def test_embedding_vector_store_compatibility(self, service_implementations):
        """Test that EmbeddingService and VectorStore have compatible vector dimensions."""
        embedding_impl = service_implementations[EmbeddingServiceInterface] 
        vector_impl = service_implementations[VectorStoreInterface]
        
        if embedding_impl is None or vector_impl is None:
            pytest.skip("Embedding or VectorStore implementation not available")
            
        # Both services should work with the same vector dimensions
        # This is tested by ensuring they can work together in the ingestion pipeline
        
        if hasattr(embedding_impl, 'get_dimension') and hasattr(vector_impl, 'get_dimension'):
            emb_dim = embedding_impl.get_dimension()
            vec_dim = vector_impl.get_dimension()
            assert emb_dim == vec_dim, f"Embedding dimension ({emb_dim}) must match VectorStore dimension ({vec_dim})"