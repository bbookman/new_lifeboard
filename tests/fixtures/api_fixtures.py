"""
API testing fixtures for HTTP client mocking and response simulation.

This module provides comprehensive HTTP client mocking utilities,
eliminating duplication across test files and ensuring consistent API testing.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class MockHTTPResponse:
    """Mock HTTP response object with realistic interface"""

    def __init__(self, status_code: int = 200, json_data: Dict = None,
                 text_data: str = None, headers: Dict = None,
                 raise_for_status: bool = False):
        self.status_code = status_code
        self._json_data = json_data or {}
        self._text_data = text_data or ""
        self.headers = headers or {}
        self._raise_for_status = raise_for_status

    def json(self):
        """Return JSON data"""
        return self._json_data

    @property
    def text(self):
        """Return text data"""
        return self._text_data

    def raise_for_status(self):
        """Raise HTTPStatusError if configured to do so"""
        if self._raise_for_status:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self,
            )


class MockAsyncHTTPClient:
    """Mock async HTTP client with configurable responses"""

    def __init__(self):
        self.get_responses = {}
        self.post_responses = {}
        self.put_responses = {}
        self.delete_responses = {}
        self.default_response = MockHTTPResponse()
        self.call_history = []

    def configure_get(self, url_pattern: str, response: MockHTTPResponse):
        """Configure response for GET requests matching URL pattern"""
        self.get_responses[url_pattern] = response

    def configure_post(self, url_pattern: str, response: MockHTTPResponse):
        """Configure response for POST requests matching URL pattern"""
        self.post_responses[url_pattern] = response

    def configure_put(self, url_pattern: str, response: MockHTTPResponse):
        """Configure response for PUT requests matching URL pattern"""
        self.put_responses[url_pattern] = response

    def configure_delete(self, url_pattern: str, response: MockHTTPResponse):
        """Configure response for DELETE requests matching URL pattern"""
        self.delete_responses[url_pattern] = response

    def _find_response(self, method: str, url: str) -> MockHTTPResponse:
        """Find configured response for method and URL"""
        response_map = {
            "GET": self.get_responses,
            "POST": self.post_responses,
            "PUT": self.put_responses,
            "DELETE": self.delete_responses,
        }

        responses = response_map.get(method, {})

        # Try exact match first
        if url in responses:
            return responses[url]

        # Try pattern matching
        for pattern, response in responses.items():
            if pattern in url or url.endswith(pattern):
                return response

        return self.default_response

    async def get(self, url: str, **kwargs):
        """Mock GET request"""
        self.call_history.append(("GET", url, kwargs))
        return self._find_response("GET", url)

    async def post(self, url: str, **kwargs):
        """Mock POST request"""
        self.call_history.append(("POST", url, kwargs))
        return self._find_response("POST", url)

    async def put(self, url: str, **kwargs):
        """Mock PUT request"""
        self.call_history.append(("PUT", url, kwargs))
        return self._find_response("PUT", url)

    async def delete(self, url: str, **kwargs):
        """Mock DELETE request"""
        self.call_history.append(("DELETE", url, kwargs))
        return self._find_response("DELETE", url)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Standard API Response Fixtures

@pytest.fixture
def mock_http_response():
    """Factory for creating mock HTTP responses"""
    return MockHTTPResponse


@pytest.fixture
def mock_async_client():
    """Factory for creating mock async HTTP clients"""
    return MockAsyncHTTPClient


@pytest.fixture
def success_response():
    """Standard success response"""
    return MockHTTPResponse(
        status_code=200,
        json_data={"status": "success", "data": {}},
    )


@pytest.fixture
def error_response():
    """Standard error response"""
    return MockHTTPResponse(
        status_code=400,
        json_data={"error": "Bad Request", "message": "Invalid request"},
    )


@pytest.fixture
def server_error_response():
    """Standard server error response"""
    return MockHTTPResponse(
        status_code=500,
        json_data={"error": "Internal Server Error", "message": "Server error"},
    )


@pytest.fixture
def unauthorized_response():
    """Standard unauthorized response"""
    return MockHTTPResponse(
        status_code=401,
        json_data={"error": "Unauthorized", "message": "Invalid API key"},
    )


@pytest.fixture
def rate_limit_response():
    """Standard rate limit response"""
    return MockHTTPResponse(
        status_code=429,
        json_data={"error": "Rate Limit Exceeded", "message": "Too many requests"},
        headers={"Retry-After": "60"},
    )


# Service-Specific API Fixtures

@pytest.fixture
def limitless_api_responses():
    """Standard Limitless API responses"""
    return {
        "success": MockHTTPResponse(
            status_code=200,
            json_data={
                "data": [{
                    "id": "test_lifelog_001",
                    "title": "Test Meeting",
                    "startTime": "2024-01-15T14:30:00Z",
                    "endTime": "2024-01-15T14:45:00Z",
                    "isStarred": False,
                    "updatedAtApi": "2024-01-15T15:00:00Z",
                    "content": {
                        "type": "doc",
                        "content": [{
                            "type": "blockquote",
                            "content": "Sample meeting discussion",
                            "startTime": "2024-01-15T14:30:00Z",
                            "endTime": "2024-01-15T14:30:05Z",
                            "speakerName": "User",
                            "speakerIdentifier": "user",
                        }],
                    },
                }],
            },
        ),
        "empty": MockHTTPResponse(
            status_code=200,
            json_data={"data": []},
        ),
        "error": MockHTTPResponse(
            status_code=400,
            json_data={"error": "Invalid date range"},
        ),
    }


@pytest.fixture
def news_api_responses():
    """Standard News API responses"""
    return {
        "success": MockHTTPResponse(
            status_code=200,
            json_data={
                "status": "success",
                "data": [{
                    "title": "Breaking Tech News",
                    "link": "https://example.com/news/1",
                    "snippet": "Important technology development announced today",
                    "published_datetime_utc": "2025-01-15T12:00:00Z",
                    "thumbnail": "https://example.com/thumb1.jpg",
                }],
            },
        ),
        "empty": MockHTTPResponse(
            status_code=200,
            json_data={"status": "success", "data": []},
        ),
        "error": MockHTTPResponse(
            status_code=400,
            json_data={"status": "error", "message": "Invalid parameters"},
        ),
    }


@pytest.fixture
def weather_api_responses():
    """Standard Weather API responses"""
    return {
        "success": MockHTTPResponse(
            status_code=200,
            json_data={
                "reportedTime": "2025-01-15T16:00:00Z",
                "readTime": "2025-01-15T17:13:14Z",
                "days": [{
                    "datetime": "2025-01-16",
                    "tempmax": 75.2,
                    "tempmin": 58.1,
                    "humidity": 65.3,
                    "conditions": "Sunny",
                    "description": "Clear skies throughout the day",
                }],
            },
        ),
        "error": MockHTTPResponse(
            status_code=400,
            json_data={"error": "Invalid location"},
        ),
    }


# HTTP Client Mocking Context Managers

class HTTPClientMocker:
    """Context manager for comprehensive HTTP client mocking"""

    def __init__(self, client_responses: Dict[str, Any] = None):
        self.client_responses = client_responses or {}
        self.mock_client = MockAsyncHTTPClient()
        self.patches = []

    def configure_responses(self, responses: Dict[str, Any]):
        """Configure multiple responses at once"""
        for url_pattern, response_config in responses.items():
            method = response_config.get("method", "GET").upper()
            response = response_config.get("response", MockHTTPResponse())

            if method == "GET":
                self.mock_client.configure_get(url_pattern, response)
            elif method == "POST":
                self.mock_client.configure_post(url_pattern, response)
            elif method == "PUT":
                self.mock_client.configure_put(url_pattern, response)
            elif method == "DELETE":
                self.mock_client.configure_delete(url_pattern, response)

    def __enter__(self):
        # Configure responses if provided
        if self.client_responses:
            self.configure_responses(self.client_responses)

        # Patch httpx.AsyncClient
        client_patch = patch("httpx.AsyncClient", return_value=self.mock_client)
        self.patches.append(client_patch)
        client_patch.start()

        return self.mock_client

    def __exit__(self, exc_type, exc_val, exc_tb):
        for patch_obj in reversed(self.patches):
            patch_obj.stop()


@pytest.fixture
def http_client_mocker():
    """Fixture providing HTTP client mocker"""
    return HTTPClientMocker


@pytest.fixture
def limitless_client_mock(limitless_api_responses):
    """Pre-configured HTTP client mock for Limitless API"""
    mocker = HTTPClientMocker({
        "/v1/lifelogs": {
            "method": "GET",
            "response": limitless_api_responses["success"],
        },
        "/v1/auth/test": {
            "method": "GET",
            "response": MockHTTPResponse(status_code=200, json_data={"valid": True}),
        },
    })
    return mocker


@pytest.fixture
def news_client_mock(news_api_responses):
    """Pre-configured HTTP client mock for News API"""
    mocker = HTTPClientMocker({
        "/search": {
            "method": "GET",
            "response": news_api_responses["success"],
        },
    })
    return mocker


@pytest.fixture
def weather_client_mock(weather_api_responses):
    """Pre-configured HTTP client mock for Weather API"""
    mocker = HTTPClientMocker({
        "/daily/5": {
            "method": "GET",
            "response": weather_api_responses["success"],
        },
    })
    return mocker


# Network Condition Simulation

@pytest.fixture
def network_timeout_mock():
    """Mock that simulates network timeouts"""
    mocker = HTTPClientMocker()

    def timeout_side_effect(*args, **kwargs):
        raise httpx.TimeoutException("Request timed out")

    mocker.mock_client.get = AsyncMock(side_effect=timeout_side_effect)
    mocker.mock_client.post = AsyncMock(side_effect=timeout_side_effect)

    return mocker


@pytest.fixture
def network_error_mock():
    """Mock that simulates network connection errors"""
    mocker = HTTPClientMocker()

    def connection_error_side_effect(*args, **kwargs):
        raise httpx.ConnectError("Connection failed")

    mocker.mock_client.get = AsyncMock(side_effect=connection_error_side_effect)
    mocker.mock_client.post = AsyncMock(side_effect=connection_error_side_effect)

    return mocker


# FastAPI Testing Utilities

@pytest.fixture
def api_test_client():
    """Factory for creating FastAPI test clients"""
    from fastapi.testclient import TestClient
    return TestClient


@pytest.fixture
def mock_dependency_override():
    """Utility for overriding FastAPI dependencies in tests"""

    class DependencyOverride:
        def __init__(self, app):
            self.app = app
            self.overrides = {}

        def override(self, dependency, override_with):
            """Override a dependency"""
            self.app.dependency_overrides[dependency] = override_with
            self.overrides[dependency] = override_with

        def clear(self):
            """Clear all overrides"""
            for dependency in self.overrides:
                if dependency in self.app.dependency_overrides:
                    del self.app.dependency_overrides[dependency]
            self.overrides.clear()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.clear()

    return DependencyOverride


# Request/Response Validation Utilities

class APITestHelper:
    """Helper utilities for API testing"""

    @staticmethod
    def assert_successful_response(response, expected_status=200):
        """Assert that a response indicates success"""
        assert response.status_code == expected_status
        if hasattr(response, "json"):
            data = response.json()
            if isinstance(data, dict):
                assert data.get("status") != "error"

    @staticmethod
    def assert_error_response(response, expected_status=400):
        """Assert that a response indicates an error"""
        assert response.status_code == expected_status
        if hasattr(response, "json"):
            data = response.json()
            if isinstance(data, dict):
                assert "error" in data or data.get("status") == "error"

    @staticmethod
    def extract_response_data(response):
        """Extract data from API response"""
        if hasattr(response, "json"):
            json_data = response.json()
            if isinstance(json_data, dict):
                return json_data.get("data", json_data)
        return None

    @staticmethod
    def validate_api_key_header(call_history, expected_key):
        """Validate that API key was sent in request headers"""
        for method, url, kwargs in call_history:
            headers = kwargs.get("headers", {})
            api_key = headers.get("X-API-Key") or headers.get("X-RapidAPI-Key")
            if api_key:
                assert api_key == expected_key
                return True
        return False


@pytest.fixture
def api_test_helper():
    """Fixture providing API testing helper utilities"""
    return APITestHelper


# Export all commonly used fixtures
__all__ = [
    "APITestHelper",
    "HTTPClientMocker",
    "MockAsyncHTTPClient",
    "MockHTTPResponse",
    "api_test_client",
    "api_test_helper",
    "error_response",
    "http_client_mocker",
    "limitless_api_responses",
    "limitless_client_mock",
    "mock_async_client",
    "mock_dependency_override",
    "mock_http_response",
    "network_error_mock",
    "network_timeout_mock",
    "news_api_responses",
    "news_client_mock",
    "rate_limit_response",
    "server_error_response",
    "success_response",
    "unauthorized_response",
    "weather_api_responses",
    "weather_client_mock",
]
