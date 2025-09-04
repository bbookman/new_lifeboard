"""
API endpoint tests for Twitter archive upload functionality.

Tests the /api/settings/upload/twitter endpoint for uploading and processing
Twitter archive files.
"""

import io
import json
import pytest
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from api.routes.settings import get_twitter_source

# We create our own test app with dependency overrides


class TestTwitterUploadAPI:
    """Test the Twitter upload API endpoint."""

    @pytest.fixture
    def mock_startup_service(self):
        """Mock startup service with ingestion service"""
        from services.startup import StartupService
        from services.ingestion import IngestionService
        from unittest.mock import MagicMock
        
        startup_service = MagicMock(spec=StartupService)
        ingestion_service = MagicMock(spec=IngestionService)
        
        # Mock ingestion service with sources dict
        ingestion_service.sources = {}
        startup_service.ingestion_service = ingestion_service
        
        return startup_service

    @pytest.fixture
    def client(self, mock_startup_service):
        """Create test client for API testing."""
        from fastapi import FastAPI
        from core.dependencies import get_startup_service_dependency
        from api.routes.settings import router
        
        app = FastAPI()
        app.include_router(router)
        
        # Override dependency using the same pattern as calendar and documents tests
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
        
        return TestClient(app)

    @pytest.fixture
    def sample_twitter_zip(self):
        """Create a sample Twitter archive ZIP file for testing."""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            # Create sample tweets.js content
            tweets_data = [
                {
                    "tweet": {
                        "id": "1234567890123456789",
                        "created_at": "Mon Jan 15 10:30:00 +0000 2024",
                        "full_text": "This is a test tweet for API testing",
                        "entities": {
                            "hashtags": [],
                            "media": []
                        }
                    }
                },
                {
                    "tweet": {
                        "id": "9876543210987654321", 
                        "created_at": "Tue Jan 16 14:45:00 +0000 2024",
                        "full_text": "Another test tweet",
                        "entities": {
                            "media": [
                                {
                                    "media_url_https": "https://example.com/image.jpg"
                                }
                            ]
                        }
                    }
                }
            ]
            
            # Add tweets.js with proper format
            tweets_content = f"window.YTD.tweets.part0 = {json.dumps(tweets_data)}"
            zip_file.writestr("data/tweets.js", tweets_content)
            
            # Add other typical archive files
            zip_file.writestr("data/account.js", "window.YTD.account.part0 = []")
            zip_file.writestr("data/profile.js", "window.YTD.profile.part0 = []")
        
        zip_buffer.seek(0)
        return zip_buffer

    @pytest.fixture
    def invalid_zip(self):
        """Create an invalid ZIP file for testing."""
        return io.BytesIO(b"This is not a zip file")

    @pytest.fixture
    def empty_zip(self):
        """Create an empty ZIP file for testing."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("empty.txt", "empty file")
        zip_buffer.seek(0)
        return zip_buffer

    def test_upload_twitter_success(self, client, sample_twitter_zip, mock_startup_service):
        """Test successful Twitter archive upload."""
        # Create mock Twitter source
        from sources.twitter import TwitterSource
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": True,
            "imported_count": 2,
            "message": "Twitter archive imported successfully. 2 tweets imported."
        })
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        # Patch the global dependency registry to return our mock startup service
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            # Make the request
            files = {"file": ("twitter-archive.zip", sample_twitter_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "imported successfully" in data["message"].lower()
        
        # Verify import method was called
        mock_twitter_source.import_from_zip.assert_called_once()

    def test_upload_twitter_no_file(self, client, mock_startup_service):
        """Test upload without providing a file."""
        # Even though we're not providing a file, FastAPI still tries to resolve dependencies
        # so we need to add a mock Twitter source and patch the dependency registry
        from sources.twitter import TwitterSource
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            response = client.post("/api/settings/upload/twitter")
        
        assert response.status_code == 422  # Unprocessable Entity
        # FastAPI will return a validation error for missing file

    def test_upload_twitter_non_zip_file(self, client, mock_startup_service):
        """Test upload with non-ZIP file."""
        text_file = io.BytesIO(b"This is a text file, not a zip")
        files = {"file": ("document.txt", text_file, "text/plain")}
        
        # Add mock Twitter source since dependencies are resolved before validation
        from sources.twitter import TwitterSource
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        # Patch the dependency registry for this test
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 400
        data = response.json()
        assert "ZIP archive" in data["detail"]

    def test_upload_twitter_invalid_zip(self, client, invalid_zip, mock_startup_service):
        """Test upload with invalid/corrupted ZIP file."""
        from sources.twitter import TwitterSource
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": False,
            "imported_count": 0,
            "message": "Invalid ZIP file format. Please ensure you're uploading a valid Twitter archive."
        })
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            files = {"file": ("invalid.zip", invalid_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 500
        data = response.json()
        assert "invalid" in data["message"].lower() or "error" in data["message"].lower()

    def test_upload_twitter_empty_zip(self, client, empty_zip, mock_startup_service):
        """Test upload with ZIP that doesn't contain tweets.js."""
        from sources.twitter import TwitterSource
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": False,
            "imported_count": 0,
            "message": "Could not find tweets.js in the archive. Make sure you're using the correct Twitter archive format."
        })
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            files = {"file": ("empty.zip", empty_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 500
        data = response.json()
        assert "tweets.js" in data["message"]

    def test_upload_twitter_source_not_configured(self, client, sample_twitter_zip, mock_startup_service):
        """Test upload when Twitter source is not configured/registered."""
        # Don't add Twitter source to the mock ingestion service (sources dict remains empty)
        # This simulates the source not being registered
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            files = {"file": ("twitter-archive.zip", sample_twitter_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 404
        data = response.json()
        assert "Twitter source not found" in data["detail"]

    def test_upload_twitter_service_unavailable(self, client, sample_twitter_zip):
        """Test upload when application services are not properly initialized."""
        # Mock the dependency registry to return None for startup service
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = None
            
            files = {"file": ("twitter-archive.zip", sample_twitter_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 503
        data = response.json()
        assert "Application not properly initialized" in data["detail"]

    def test_upload_twitter_processing_error(self, client, sample_twitter_zip, mock_startup_service):
        """Test upload when Twitter processing fails with an exception."""
        from sources.twitter import TwitterSource
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.import_from_zip = AsyncMock(side_effect=Exception("Unexpected processing error"))
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            files = {"file": ("twitter-archive.zip", sample_twitter_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 500
        data = response.json()
        assert "unexpected error" in data["message"].lower()

    def test_upload_twitter_file_cleanup(self, client, sample_twitter_zip, mock_startup_service):
        """Test that temporary files are properly cleaned up after upload."""
        import os
        from sources.twitter import TwitterSource
        
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": True,
            "imported_count": 2,
            "message": "Import successful"
        })
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            # Patch os.remove to verify it gets called (file cleanup)
            with patch('os.remove') as mock_remove:
                with patch('os.path.exists', return_value=True):  # File exists for cleanup
                    files = {"file": ("twitter-archive.zip", sample_twitter_zip, "application/zip")}
                    response = client.post("/api/settings/upload/twitter", files=files)
                    
                    # Should attempt to clean up temp file
                    mock_remove.assert_called_once()
        
        assert response.status_code == 200

    def test_upload_twitter_with_real_archive(self, client, mock_startup_service):
        """Test upload using the real Twitter archive from test media."""
        import os
        from sources.twitter import TwitterSource
        
        # Mock successful processing
        mock_twitter_source = MagicMock(spec=TwitterSource) 
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": True,
            "imported_count": 100,
            "message": "Twitter archive imported successfully. 100 tweets imported."
        })
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        # Load the real test archive
        archive_path = "/Users/brucebookman/code/new_lifeboard/tests/media/twitter-x.zip"
        
        if os.path.exists(archive_path):
            with patch('api.routes.settings.get_dependency_registry') as mock_registry:
                mock_registry.return_value.get_startup_service.return_value = mock_startup_service
                
                with open(archive_path, 'rb') as archive_file:
                    files = {"file": ("twitter-x.zip", archive_file, "application/zip")}
                    response = client.post("/api/settings/upload/twitter", files=files)
                
                assert response.status_code == 200
                data = response.json()
                assert "imported successfully" in data["message"].lower()
                
                # Verify the import method was called with the uploaded file
                mock_twitter_source.import_from_zip.assert_called_once()
        else:
            pytest.skip("Real Twitter archive not found for testing")

    def test_upload_twitter_large_file_handling(self, client, mock_startup_service):
        """Test upload handling with large files (within reasonable limits)."""
        # Create a larger test archive with more tweets
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            # Create more tweets (simulate larger archive)
            tweets_data = []
            for i in range(100):  # 100 tweets
                tweets_data.append({
                    "tweet": {
                        "id": f"123456789012345{i:04d}",
                        "created_at": f"Mon Jan {15 + (i % 10)} 10:30:00 +0000 2024",
                        "full_text": f"Test tweet number {i} for large file testing",
                        "entities": {"hashtags": [], "media": []}
                    }
                })
            
            tweets_content = f"window.YTD.tweets.part0 = {json.dumps(tweets_data)}"
            zip_file.writestr("data/tweets.js", tweets_content)
        
        zip_buffer.seek(0)
        
        from sources.twitter import TwitterSource
        
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": True,
            "imported_count": 100,
            "message": "Large archive processed successfully"
        })
        
        # Add Twitter source to the mock ingestion service
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            files = {"file": ("large-twitter-archive.zip", zip_buffer, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "processed successfully" in data["message"].lower()

    def test_get_twitter_source_dependency(self):
        """Test the get_twitter_source dependency function directly."""
        from api.routes.settings import get_twitter_source
        from fastapi import HTTPException
        
        # Test when startup service is not available
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                get_twitter_source()
            assert exc_info.value.status_code == 503

        # Test when ingestion service is not available
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_startup = MagicMock()
            mock_startup.ingestion_service = None
            mock_registry.return_value.get_startup_service.return_value = mock_startup
            
            with pytest.raises(HTTPException) as exc_info:
                get_twitter_source()
            assert exc_info.value.status_code == 503

        # Test when Twitter source is not registered
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_startup = MagicMock()
            mock_ingestion = MagicMock()
            mock_ingestion.sources = {"limitless": "some_source"}  # No twitter source
            mock_startup.ingestion_service = mock_ingestion
            mock_registry.return_value.get_startup_service.return_value = mock_startup
            
            with pytest.raises(HTTPException) as exc_info:
                get_twitter_source()
            assert exc_info.value.status_code == 404
            assert "Twitter source not found" in str(exc_info.value.detail)

        # Test successful case
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            from sources.twitter import TwitterSource
            mock_startup = MagicMock()
            mock_ingestion = MagicMock()
            mock_twitter_source = MagicMock(spec=TwitterSource)
            mock_ingestion.sources = {"twitter": mock_twitter_source}
            mock_startup.ingestion_service = mock_ingestion
            mock_registry.return_value.get_startup_service.return_value = mock_startup
            
            result = get_twitter_source()
            assert result is mock_twitter_source

    def test_twitter_configuration_status_reporting(self, client, mock_startup_service):
        """Test that API endpoints can report Twitter configuration status including user_id."""
        from sources.twitter import TwitterSource
        from config.models import TwitterConfig
        
        # Test with API enabled configuration (with user_id)
        api_enabled_config = TwitterConfig(
            enabled=True,
            bearer_token="valid_token",
            username="testuser",
            user_id="123456789012345678"
        )
        
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.config = api_enabled_config
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            # API should be able to access configuration status
            twitter_source = get_twitter_source()
            
            # Verify configuration reporting
            assert twitter_source.config.is_api_configured() is True
            assert twitter_source.config.user_id == "123456789012345678"
            
        # Test with missing user_id configuration
        api_disabled_config = TwitterConfig(
            enabled=True,
            bearer_token="valid_token",
            username="testuser",
            user_id=None  # Missing user_id
        )
        
        mock_twitter_source.config = api_disabled_config
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            twitter_source = get_twitter_source()
            
            # Should report API as not configured due to missing user_id
            assert twitter_source.config.is_api_configured() is False
            assert twitter_source.config.user_id is None

    def test_upload_twitter_with_invalid_user_id(self, client, sample_twitter_zip, mock_startup_service):
        """Test upload works for archive imports even with invalid user_id."""
        from sources.twitter import TwitterSource
        from config.models import TwitterConfig
        
        # Configuration with invalid user_id (missing)
        config_with_invalid_user_id = TwitterConfig(
            enabled=True,
            bearer_token="valid_token",
            username="testuser",
            user_id=None  # Missing user_id makes API invalid
        )
        
        mock_twitter_source = MagicMock(spec=TwitterSource)
        mock_twitter_source.config = config_with_invalid_user_id
        mock_twitter_source.import_from_zip = AsyncMock(return_value={
            "success": True,
            "imported_count": 2,
            "message": "Twitter archive imported successfully. 2 tweets imported."
        })
        
        mock_startup_service.ingestion_service.sources["twitter"] = mock_twitter_source
        
        with patch('api.routes.settings.get_dependency_registry') as mock_registry:
            mock_registry.return_value.get_startup_service.return_value = mock_startup_service
            
            files = {"file": ("twitter-archive.zip", sample_twitter_zip, "application/zip")}
            response = client.post("/api/settings/upload/twitter", files=files)
        
        # Archive upload should succeed even with invalid user_id
        assert response.status_code == 200
        data = response.json()
        assert "imported successfully" in data["message"].lower()
        
        # Verify API is not considered configured
        assert mock_twitter_source.config.is_api_configured() is False


class TestTwitterUploadIntegration:
    """Integration tests for Twitter upload API with minimal mocking."""

    @pytest.fixture
    def integration_client(self):
        """Client for integration testing with minimal mocking."""
        from fastapi import FastAPI
        from core.dependencies import get_startup_service_dependency
        from api.routes.settings import router
        from services.startup import StartupService
        from services.ingestion import IngestionService
        from unittest.mock import MagicMock
        
        # Create minimal mock startup service
        startup_service = MagicMock(spec=StartupService)
        ingestion_service = MagicMock(spec=IngestionService)
        ingestion_service.sources = {}
        startup_service.ingestion_service = ingestion_service
        
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_startup_service_dependency] = lambda: startup_service
        
        return TestClient(app)

    def test_upload_endpoint_exists(self, integration_client):
        """Test that the upload endpoint exists and is properly configured."""
        # Test with invalid request to see if endpoint exists
        response = integration_client.post("/api/settings/upload/twitter")
        
        # Should return 422 (missing file) or 503 (service not available)
        # but not 404 (endpoint not found)
        assert response.status_code in [422, 503]
        assert response.status_code != 404

    def test_upload_content_type_validation(self, integration_client):
        """Test that the endpoint validates content types appropriately."""
        # Send a text file instead of ZIP
        text_content = io.BytesIO(b"This is not a zip file")
        files = {"file": ("test.txt", text_content, "text/plain")}
        
        response = integration_client.post("/api/settings/upload/twitter", files=files)
        
        # Should validate file type (400) or fail at service level (503)
        # but not crash with unhandled exception (500)
        assert response.status_code in [400, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])