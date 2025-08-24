"""Service interface definitions for dependency injection."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ServiceInterface(ABC):
    """Base interface for all services in the Lifeboard application.
    
    All services must implement this interface to participate in the 
    dependency injection container and service lifecycle management.
    """
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the service.
        
        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the service.
        
        Returns:
            Dict[str, Any]: Health status information including at minimum
                          a 'status' key with value 'healthy' or 'unhealthy'.
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """Shutdown the service and clean up resources.
        
        Returns:
            bool: True if shutdown was successful, False otherwise.
        """
        pass


class DatabaseServiceInterface(ServiceInterface):
    """Interface for database services."""
    
    @abstractmethod
    def get_connection(self):
        """Get a database connection.
        
        Returns:
            Database connection object.
        """
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a database query.
        
        Args:
            query: SQL query string.
            params: Query parameters (optional).
        
        Returns:
            List[Dict]: Query results as list of dictionaries.
        """
        pass
    
    @abstractmethod
    def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction.
        
        Args:
            queries: List of (query, params) tuples.
        
        Returns:
            bool: True if transaction completed successfully, False otherwise.
        """
        pass


class HTTPClientInterface(ServiceInterface):
    """Interface for HTTP client services."""
    
    @abstractmethod
    def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Perform HTTP GET request.
        
        Args:
            url: Target URL.
            **kwargs: Additional request parameters.
        
        Returns:
            Dict[str, Any]: Response data.
        """
        pass
    
    @abstractmethod
    def post(self, url: str, data: Dict, **kwargs) -> Dict[str, Any]:
        """Perform HTTP POST request.
        
        Args:
            url: Target URL.
            data: Request payload.
            **kwargs: Additional request parameters.
        
        Returns:
            Dict[str, Any]: Response data.
        """
        pass
    
    @abstractmethod
    def put(self, url: str, data: Dict, **kwargs) -> Dict[str, Any]:
        """Perform HTTP PUT request.
        
        Args:
            url: Target URL.
            data: Request payload.
            **kwargs: Additional request parameters.
        
        Returns:
            Dict[str, Any]: Response data.
        """
        pass
    
    @abstractmethod
    def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """Perform HTTP DELETE request.
        
        Args:
            url: Target URL.
            **kwargs: Additional request parameters.
        
        Returns:
            Dict[str, Any]: Response data.
        """
        pass


class EmbeddingServiceInterface(ServiceInterface):
    """Interface for text embedding services."""
    
    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode texts into embedding vectors.
        
        Args:
            texts: List of text strings to encode.
        
        Returns:
            List[List[float]]: List of embedding vectors.
        """
        pass
    
    @abstractmethod
    def encode_single(self, text: str) -> List[float]:
        """Encode a single text into an embedding vector.
        
        Args:
            text: Text string to encode.
        
        Returns:
            List[float]: Embedding vector.
        """
        pass


class VectorStoreInterface(ServiceInterface):
    """Interface for vector store services."""
    
    @abstractmethod
    def add_vectors(self, vectors: List[List[float]], ids: List[str], metadata: List[Dict] = None):
        """Add vectors to the store.
        
        Args:
            vectors: List of embedding vectors.
            ids: Corresponding IDs for the vectors.
            metadata: Optional metadata for each vector.
        """
        pass
    
    @abstractmethod
    def search(self, query_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector.
            k: Number of results to return.
        
        Returns:
            List[Dict[str, Any]]: Search results with IDs, scores, and metadata.
        """
        pass
    
    @abstractmethod
    def delete_vectors(self, ids: List[str]):
        """Delete vectors from the store.
        
        Args:
            ids: List of vector IDs to delete.
        """
        pass


class ChatServiceInterface(ServiceInterface):
    """Interface for chat/LLM services."""
    
    @abstractmethod
    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate a chat response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional generation parameters.
        
        Returns:
            str: Generated response text.
        """
        pass
    
    @abstractmethod
    def generate_embedding_query(self, user_message: str) -> str:
        """Generate a search query from user message for embedding search.
        
        Args:
            user_message: User's chat message.
        
        Returns:
            str: Optimized search query.
        """
        pass


class IngestionServiceInterface(ServiceInterface):
    """Interface for data ingestion services."""
    
    @abstractmethod
    def ingest_data(self, source_name: str, data_items: List[Dict[str, Any]]) -> bool:
        """Ingest data items from a source.
        
        Args:
            source_name: Name of the data source.
            data_items: List of data items to ingest.
        
        Returns:
            bool: True if ingestion was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_source_status(self, source_name: str) -> Dict[str, Any]:
        """Get the status of a data source.
        
        Args:
            source_name: Name of the data source.
        
        Returns:
            Dict[str, Any]: Source status information.
        """
        pass


class SchedulerServiceInterface(ServiceInterface):
    """Interface for task scheduling services."""
    
    @abstractmethod
    def schedule_task(self, task_id: str, cron_expression: str, task_function, **kwargs):
        """Schedule a recurring task.
        
        Args:
            task_id: Unique identifier for the task.
            cron_expression: Cron expression for scheduling.
            task_function: Function to execute.
            **kwargs: Additional task parameters.
        """
        pass
    
    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task.
        
        Args:
            task_id: ID of the task to cancel.
        
        Returns:
            bool: True if task was cancelled, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a scheduled task.
        
        Args:
            task_id: ID of the task.
        
        Returns:
            Dict[str, Any]: Task status information.
        """
        pass