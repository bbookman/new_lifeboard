"""
Example service demonstrating integration with Enhanced Debug Logging.

This service shows how to integrate both ServiceDebugMixin for service-level
logging and DebugDatabaseConnection for database monitoring.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from services.debug_mixin import ServiceDebugMixin
from core.database_debug import DebugDatabaseConnection


class ExampleDebugService(ServiceDebugMixin):
    """
    Example service with comprehensive debug logging integration.
    
    Demonstrates:
    - ServiceDebugMixin integration for service call logging
    - DebugDatabaseConnection usage for database monitoring
    - External API call logging
    - Performance metric tracking
    - Error handling with debug context
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the example service with debug capabilities.
        
        Args:
            db_path: Path to the SQLite database
        """
        # Initialize debug mixin
        super().__init__("example_service")
        
        # Set up database with debug monitoring
        self.debug_db = DebugDatabaseConnection(db_path)
        
        # Initialize service state
        self.cache = {}
        self.request_count = 0
        
        # Log service initialization
        self.log_service_call("__init__", {"db_path": db_path})
        
    def get_user_data(self, user_id: int, include_history: bool = False) -> Dict[str, Any]:
        """
        Get user data with optional history, demonstrating debug integration.
        
        Args:
            user_id: User ID to fetch data for
            include_history: Whether to include user history
            
        Returns:
            Dictionary containing user data and metadata
        """
        # Log service method call with parameters
        self.log_service_call("get_user_data", {
            "user_id": user_id,
            "include_history": include_history
        })
        
        try:
            # Check cache first
            cache_key = f"user_{user_id}"
            if cache_key in self.cache:
                self.log_service_performance_metric("cache_hit_rate", 1.0, "ratio")
                return self.cache[cache_key]
            
            # Database operation with timing
            start_time = time.time()
            
            with self.debug_db.get_connection() as conn:
                # Basic user query
                cursor = conn.execute(
                    "SELECT id, name, email, created_at FROM users WHERE id = ?",
                    (user_id,)
                )
                user_row = cursor.fetchone()
                
                if not user_row:
                    return {"error": "User not found", "user_id": user_id}
                    
                user_data = {
                    "id": user_row["id"],
                    "name": user_row["name"],
                    "email": user_row["email"],
                    "created_at": user_row["created_at"]
                }
                
                # Optional history query
                if include_history:
                    cursor = conn.execute(
                        "SELECT action, timestamp FROM user_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
                        (user_id,)
                    )
                    user_data["history"] = [dict(row) for row in cursor.fetchall()]
            
            # Log database operation timing
            db_duration = (time.time() - start_time) * 1000
            self.log_database_operation("SELECT", "users", db_duration)
            
            # Cache the result
            self.cache[cache_key] = user_data
            self.log_service_performance_metric("cache_miss_rate", 1.0, "ratio")
            
            return user_data
            
        except Exception as e:
            # Log service errors with context
            self.log_service_error("get_user_data", e, {
                "user_id": user_id,
                "include_history": include_history,
                "cache_size": len(self.cache)
            })
            raise
            
    def create_user(self, name: str, email: str) -> Dict[str, Any]:
        """
        Create a new user demonstrating transaction logging.
        
        Args:
            name: User's name
            email: User's email address
            
        Returns:
            Dictionary containing created user information
        """
        self.log_service_call("create_user", {
            "name": name,
            "email": email
        })
        
        try:
            start_time = time.time()
            
            with self.debug_db.get_connection() as conn:
                # Use transaction for data integrity
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO users (name, email) VALUES (?, ?) RETURNING id, created_at",
                        (name, email)
                    )
                    new_user = cursor.fetchone()
                    
                    # Log initial user activity
                    conn.execute(
                        "INSERT INTO user_history (user_id, action, timestamp) VALUES (?, 'created', datetime('now'))",
                        (new_user["id"],)
                    )
            
            # Log database operation
            db_duration = (time.time() - start_time) * 1000
            self.log_database_operation("INSERT", "users", db_duration)
            
            result = {
                "id": new_user["id"],
                "name": name,
                "email": email,
                "created_at": new_user["created_at"]
            }
            
            # Clear relevant cache entries
            self.cache.clear()
            
            return result
            
        except Exception as e:
            self.log_service_error("create_user", e, {
                "name": name,
                "email": email
            })
            raise
            
    def fetch_external_data(self, api_endpoint: str) -> Dict[str, Any]:
        """
        Fetch data from external API demonstrating API call logging.
        
        Args:
            api_endpoint: External API endpoint to call
            
        Returns:
            Dictionary containing API response data
        """
        self.log_service_call("fetch_external_data", {
            "api_endpoint": api_endpoint
        })
        
        try:
            # Simulate external API call
            start_time = time.time()
            
            # Mock API response (in real implementation would use httpx/requests)
            time.sleep(0.1)  # Simulate network delay
            
            # Mock different response scenarios
            if "error" in api_endpoint:
                status_code = 500
                response_data = {"error": "Internal server error"}
            elif "timeout" in api_endpoint:
                status_code = 408
                response_data = {"error": "Request timeout"}
            else:
                status_code = 200
                response_data = {"data": "Mock API response", "endpoint": api_endpoint}
                
            api_duration = (time.time() - start_time) * 1000
            
            # Log external API call
            self.log_external_api_call("mock_api", api_endpoint, status_code, api_duration)
            
            # Log performance metrics
            self.log_service_performance_metric("api_response_time", api_duration, "ms")
            
            return response_data
            
        except Exception as e:
            self.log_service_error("fetch_external_data", e, {
                "api_endpoint": api_endpoint
            })
            raise
            
    def get_service_health(self) -> Dict[str, Any]:
        """
        Get comprehensive service health information.
        
        Returns:
            Dictionary containing service health metrics
        """
        self.log_service_call("get_service_health")
        
        try:
            # Get basic health metrics from mixin
            health_metrics = self.get_service_health_metrics()
            
            # Add service-specific metrics
            health_metrics.update({
                "cache_size": len(self.cache),
                "request_count": self.request_count,
                "service_name": self.service_name
            })
            
            # Get database connection health
            db_health = self.debug_db.log_connection_health()
            health_metrics["database"] = db_health
            
            return health_metrics
            
        except Exception as e:
            self.log_service_error("get_service_health", e)
            return {
                "status": "error",
                "error": str(e),
                "service_name": self.service_name
            }
            
    def clear_cache(self) -> Dict[str, Any]:
        """Clear service cache and return statistics."""
        self.log_service_call("clear_cache")
        
        cache_size = len(self.cache)
        self.cache.clear()
        
        result = {
            "cache_entries_cleared": cache_size,
            "timestamp": time.time()
        }
        
        self.log_service_performance_metric("cache_clear_count", 1, "count")
        
        return result
        
    def simulate_batch_operations(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Simulate batch operations for demonstrating performance monitoring.
        
        Args:
            batch_size: Number of operations to simulate
            
        Returns:
            Dictionary containing batch operation results
        """
        self.log_service_call("simulate_batch_operations", {
            "batch_size": batch_size
        })
        
        try:
            start_time = time.time()
            processed_count = 0
            
            with self.debug_db.get_connection() as conn:
                for i in range(batch_size):
                    # Simulate batch processing
                    cursor = conn.execute("SELECT COUNT(*) as count FROM users")
                    result = cursor.fetchone()
                    processed_count += 1
                    
            total_duration = (time.time() - start_time) * 1000
            avg_duration_per_operation = total_duration / batch_size if batch_size > 0 else 0
            
            # Log batch database operation
            self.log_database_operation("BATCH_SELECT", "users", total_duration)
            
            # Log performance metrics
            self.log_service_performance_metric("batch_operation_time", total_duration, "ms")
            self.log_service_performance_metric("avg_operation_time", avg_duration_per_operation, "ms")
            
            return {
                "batch_size": batch_size,
                "processed_count": processed_count,
                "total_duration_ms": round(total_duration, 2),
                "avg_duration_per_operation_ms": round(avg_duration_per_operation, 2)
            }
            
        except Exception as e:
            self.log_service_error("simulate_batch_operations", e, {
                "batch_size": batch_size,
                "processed_count": processed_count
            })
            raise


# Example of creating a service with debug capabilities using the factory function
from services.debug_mixin import create_debug_enabled_service


class RegularService:
    """A regular service without debug capabilities."""
    
    def __init__(self, name: str):
        self.name = name
        
    def do_work(self):
        return f"Work done by {self.name}"


def create_example_services():
    """Example of creating services with debug capabilities."""
    
    # Create regular service with debug capabilities added
    debug_service = create_debug_enabled_service(
        RegularService, 
        "regular_service_with_debug",
        "Enhanced Service"
    )
    
    # Now the service has debug capabilities
    debug_service.log_service_call("do_work")
    result = debug_service.do_work()
    
    return result


# Usage example
if __name__ == "__main__":
    # Example usage of the debug-enabled service
    service = ExampleDebugService("example.db")
    
    # Demonstrate various debug logging features
    print("Service Health:", service.get_service_health())
    
    try:
        # This would require actual database tables
        # user_data = service.get_user_data(123, include_history=True)
        pass
    except Exception:
        print("Database operations require proper setup")
        
    # Demonstrate API logging
    api_data = service.fetch_external_data("/api/test")
    print("API Response:", api_data)
    
    # Demonstrate batch operations
    batch_result = service.simulate_batch_operations(5)
    print("Batch Results:", batch_result)