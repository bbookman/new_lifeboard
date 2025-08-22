"""
Exception handling utilities and decorators

This module provides reusable exception handling patterns to eliminate
duplicate try-catch blocks across the application.
"""

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ServiceError(Exception):
    """Base exception for service-level errors"""

    def __init__(self, message: str, service_name: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.service_name = service_name
        self.error_code = error_code
        self.timestamp = datetime.now(timezone.utc)


class RetryableError(ServiceError):
    """Exception that indicates the operation can be retried"""


class NonRetryableError(ServiceError):
    """Exception that indicates the operation should not be retried"""


def handle_service_exceptions(
    service_name: str,
    default_return: Any = None,
    log_errors: bool = True,
    reraise: bool = False,
    fallback_action: Optional[Callable] = None,
):
    """
    Decorator for handling service-level exceptions consistently
    
    Args:
        service_name: Name of the service for logging/error context
        default_return: Value to return on exception (for sync functions)
        log_errors: Whether to log exceptions
        reraise: Whether to reraise the exception after handling
        fallback_action: Optional callable to execute on exception
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if log_errors:
                        logger.error(f"{service_name} error in {func.__name__}: {e}")

                    if fallback_action:
                        try:
                            await fallback_action(e, *args, **kwargs)
                        except Exception:
                            pass  # Don't let fallback errors compound the issue

                    if reraise:
                        raise

                    return default_return

            return async_wrapper
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"{service_name} error in {func.__name__}: {e}")

                if fallback_action:
                    try:
                        fallback_action(e, *args, **kwargs)
                    except Exception:
                        pass

                if reraise:
                    raise

                return default_return

        return sync_wrapper

    return decorator


def handle_api_exceptions(
    error_message: str = "An error occurred",
    status_code: int = 500,
    include_details: bool = False,
):
    """
    Decorator for handling API endpoint exceptions
    
    Args:
        error_message: Default error message for responses
        status_code: HTTP status code to return on error
        include_details: Whether to include exception details in response
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"API error in {func.__name__}: {e}")

                from fastapi import HTTPException

                detail = error_message
                if include_details:
                    detail = f"{error_message}: {e!s}"

                raise HTTPException(status_code=status_code, detail=detail)

        return wrapper

    return decorator


def safe_operation(
    operation_name: str,
    default_return: Any = None,
    log_errors: bool = True,
    raise_on_error: bool = False,
):
    """
    Context manager for safe execution of operations with consistent error handling
    
    Args:
        operation_name: Name of the operation for logging
        default_return: Value to return on exception
        log_errors: Whether to log exceptions
        raise_on_error: Whether to reraise exceptions
    """
    class SafeOperationContext:
        def __init__(self):
            self.success = False
            self.error = None
            self.result = default_return

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                self.error = exc_val
                if log_errors:
                    logger.error(f"{operation_name} failed: {exc_val}")

                if raise_on_error:
                    return False  # Re-raise the exception

                return True  # Suppress the exception
            self.success = True

            return False

    return SafeOperationContext()


class ErrorAccumulator:
    """Utility for collecting and managing multiple errors"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.errors: list = []
        self.warnings: list = []

    def add_error(self, error: Union[str, Exception], context: Optional[str] = None):
        """Add an error to the collection"""
        error_msg = str(error)
        if context:
            error_msg = f"{context}: {error_msg}"

        self.errors.append(error_msg)
        logger.error(f"{self.operation_name} error: {error_msg}")

    def add_warning(self, warning: Union[str, Exception], context: Optional[str] = None):
        """Add a warning to the collection"""
        warning_msg = str(warning)
        if context:
            warning_msg = f"{context}: {warning_msg}"

        self.warnings.append(warning_msg)
        logger.warning(f"{self.operation_name} warning: {warning_msg}")

    def has_errors(self) -> bool:
        """Check if any errors were recorded"""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were recorded"""
        return len(self.warnings) > 0

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all errors and warnings"""
        return {
            "operation": self.operation_name,
            "success": not self.has_errors(),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


# Import asyncio for the decorator
import asyncio


def with_error_accumulator(operation_name: str):
    """
    Decorator that provides an ErrorAccumulator as the first argument to the decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            accumulator = ErrorAccumulator(operation_name)
            return func(accumulator, *args, **kwargs)

        return wrapper

    return decorator


def log_and_ignore_errors(operation_name: str, default_return: Any = None):
    """
    Decorator that logs exceptions but doesn't reraise them
    Useful for cleanup operations or non-critical functions
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"{operation_name} failed (ignoring): {e}")
                return default_return

        return wrapper

    return decorator


class DatabaseOperationHandler:
    """Specialized error handler for database operations"""

    @staticmethod
    def handle_db_operation(
        operation_name: str,
        default_return: Any = None,
        commit_on_success: bool = True,
    ):
        """
        Context manager for database operations with transaction handling
        """
        class DatabaseOperationContext:
            def __init__(self):
                self.success = False
                self.error = None
                self.result = default_return
                self.connection = None

            def set_connection(self, conn):
                """Set the database connection for transaction management"""
                self.connection = conn
                return self

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    self.error = exc_val
                    logger.error(f"Database {operation_name} failed: {exc_val}")

                    # Rollback transaction if connection is available
                    if self.connection:
                        try:
                            self.connection.rollback()
                        except Exception as rollback_error:
                            logger.error(f"Rollback failed: {rollback_error}")

                    return True  # Suppress the exception
                self.success = True
                # Commit transaction if requested and connection is available
                if commit_on_success and self.connection:
                    try:
                        self.connection.commit()
                    except Exception as commit_error:
                        logger.error(f"Commit failed: {commit_error}")
                        self.success = False
                        self.error = commit_error

                return False

        return DatabaseOperationContext()
