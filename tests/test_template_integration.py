"""
Integration tests for Template Processing with DocumentService and API

Tests the complete template processing pipeline including DocumentService
integration and API endpoints.
"""

from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.documents import router as documents_router
from config.models import AppConfig
from core.database import DatabaseService
from services.document_service import DocumentService


class TestDocumentServiceTemplateIntegration:
    """Test DocumentService template processing integration"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create in-memory database
        self.db_service = DatabaseService(":memory:")

        # Create mock dependencies
        self.mock_config = Mock(spec=AppConfig)
        self.mock_config.documents.max_title_length = 200
        self.mock_config.documents.max_content_length = 50000
        self.mock_config.documents.chunking_enabled = False

        self.mock_vector_store = Mock()
        self.mock_embedding_service = Mock()

        # Initialize document service
        self.document_service = DocumentService(
            database=self.db_service,
            vector_store=self.mock_vector_store,
            embedding_service=self.mock_embedding_service,
            config=self.mock_config,
        )

        # Add test data to database
        self.db_service.store_data_item(
            id="limitless:test1",
            namespace="limitless",
            source_id="test1",
            content="Important meeting with client about project roadmap",
            days_date="2024-01-15",
        )

        self.db_service.store_data_item(
            id="twitter:test1",
            namespace="twitter",
            source_id="test1",
            content="Shared article about new technology trends",
            days_date="2024-01-15",
        )

    def test_process_template_basic_functionality(self):
        """Test basic template processing through DocumentService"""
        content = "Today's activities: {{LIMITLESS_DAY}}"
        target_date = "2024-01-15"

        result = self.document_service.process_template(content, target_date)

        # Should contain resolved data
        assert "Important meeting with client" in result
        assert "{{LIMITLESS_DAY}}" not in result

    def test_process_template_no_variables(self):
        """Test processing content without template variables"""
        content = "This is plain text without any templates."

        result = self.document_service.process_template(content)

        # Should return content unchanged
        assert result == content

    def test_process_template_multiple_variables(self):
        """Test processing content with multiple template variables"""
        content = "Activities: {{LIMITLESS_DAY}} Social: {{TWITTER_DAY}}"
        target_date = "2024-01-15"

        result = self.document_service.process_template(content, target_date)

        # Should resolve both variables
        assert "Important meeting with client" in result
        assert "Shared article about new technology" in result
        assert "{{LIMITLESS_DAY}}" not in result
        assert "{{TWITTER_DAY}}" not in result

    def test_process_template_error_handling(self):
        """Test error handling in template processing"""
        content = "Test: {{LIMITLESS_DAY}}"

        # Mock template processor to raise exception
        with patch("services.template_processor.TemplateProcessor") as mock_tp:
            mock_tp.side_effect = Exception("Template processor error")

            result = self.document_service.process_template(content)

            # Should return original content on error
            assert result == content

    def test_validate_template_valid_content(self):
        """Test template validation with valid content"""
        content = "Hello {{LIMITLESS_DAY}} and {{TWITTER_WEEK}}"

        validation = self.document_service.validate_template(content)

        assert validation["is_valid"] is True
        assert validation["total_variables"] == 2
        assert len(validation["valid_variables"]) == 2
        assert len(validation["invalid_variables"]) == 0

    def test_validate_template_invalid_content(self):
        """Test template validation with invalid content"""
        content = "Hello {{INVALID_SOURCE}} and {{LIMITLESS_BADRANGE}}"

        validation = self.document_service.validate_template(content)

        assert validation["is_valid"] is False
        assert validation["total_variables"] == 0  # No valid variables
        assert len(validation["valid_variables"]) == 0
        assert len(validation["invalid_variables"]) == 0  # Invalid ones filtered out

    def test_validate_template_error_handling(self):
        """Test error handling in template validation"""
        content = "Test content"

        # Mock template processor to raise exception
        with patch("services.template_processor.TemplateProcessor") as mock_tp:
            mock_tp.side_effect = Exception("Validation error")

            validation = self.document_service.validate_template(content)

            assert validation["is_valid"] is False
            assert "error" in validation
            assert validation["total_variables"] == 0


class TestTemplateAPIEndpoints:
    """Test template processing API endpoints"""

    def setup_method(self):
        """Set up API test fixtures"""
        # Create test FastAPI app
        self.app = FastAPI()
        self.app.include_router(documents_router)
        self.client = TestClient(self.app)

        # Create mock document service
        self.mock_document_service = Mock(spec=DocumentService)

        # Patch the dependency to return our mock
        def mock_get_document_service():
            return self.mock_document_service

        self.app.dependency_overrides[documents_router.get_document_service_for_route] = mock_get_document_service

    def test_process_template_endpoint_success(self):
        """Test successful template processing via API"""
        # Mock document service response
        self.mock_document_service.process_template.return_value = "Resolved: Data from today"

        # Make API request
        response = self.client.post("/api/documents/process-template", json={
            "content": "Today: {{LIMITLESS_DAY}}",
            "target_date": "2024-01-15",
        })

        assert response.status_code == 200
        data = response.json()

        assert data["original_content"] == "Today: {{LIMITLESS_DAY}}"
        assert data["resolved_content"] == "Resolved: Data from today"
        assert data["variables_resolved"] == 1
        assert len(data["errors"]) == 0

        # Verify service was called correctly
        self.mock_document_service.process_template.assert_called_once_with(
            content="Today: {{LIMITLESS_DAY}}",
            target_date="2024-01-15",
        )

    def test_process_template_endpoint_no_variables(self):
        """Test processing content without variables"""
        plain_content = "This is plain text"
        self.mock_document_service.process_template.return_value = plain_content

        response = self.client.post("/api/documents/process-template", json={
            "content": plain_content,
        })

        assert response.status_code == 200
        data = response.json()

        assert data["variables_resolved"] == 0
        assert data["resolved_content"] == plain_content

    def test_process_template_endpoint_error(self):
        """Test API error handling"""
        # Mock service to raise exception
        self.mock_document_service.process_template.side_effect = Exception("Service error")

        response = self.client.post("/api/documents/process-template", json={
            "content": "{{LIMITLESS_DAY}}",
        })

        assert response.status_code == 500
        assert "Failed to process template" in response.json()["detail"]

    def test_validate_template_endpoint_success(self):
        """Test template validation via API"""
        # Mock validation response
        self.mock_document_service.validate_template.return_value = {
            "is_valid": True,
            "total_variables": 2,
            "valid_variables": ["{{LIMITLESS_DAY}}", "{{TWITTER_WEEK}}"],
            "invalid_variables": [],
            "supported_sources": ["LIMITLESS", "TWITTER", "NEWS"],
            "supported_time_ranges": ["DAY", "WEEK", "MONTH"],
        }

        response = self.client.post("/api/documents/validate-template", json={
            "content": "{{LIMITLESS_DAY}} {{TWITTER_WEEK}}",
        })

        assert response.status_code == 200
        data = response.json()

        assert data["is_valid"] is True
        assert data["total_variables"] == 2
        assert len(data["valid_variables"]) == 2
        assert len(data["invalid_variables"]) == 0
        assert "LIMITLESS" in data["supported_sources"]

    def test_validate_template_endpoint_invalid(self):
        """Test validation with invalid templates"""
        self.mock_document_service.validate_template.return_value = {
            "is_valid": False,
            "total_variables": 0,
            "valid_variables": [],
            "invalid_variables": [],
            "supported_sources": ["LIMITLESS", "TWITTER", "NEWS"],
            "supported_time_ranges": ["DAY", "WEEK", "MONTH"],
        }

        response = self.client.post("/api/documents/validate-template", json={
            "content": "{{INVALID_FORMAT}}",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False

    def test_process_document_template_endpoint_success(self):
        """Test processing template for specific document"""
        # Mock document retrieval
        mock_document = Mock()
        mock_document.content_md = "Today's work: {{LIMITLESS_DAY}}"
        self.mock_document_service.get_document.return_value = mock_document

        # Mock template processing
        self.mock_document_service.process_template.return_value = "Today's work: Meeting notes"

        response = self.client.post("/api/documents/test-doc-id/process-template")

        assert response.status_code == 200
        data = response.json()

        assert data["original_content"] == "Today's work: {{LIMITLESS_DAY}}"
        assert data["resolved_content"] == "Today's work: Meeting notes"
        assert data["variables_resolved"] == 1

        # Verify service calls
        self.mock_document_service.get_document.assert_called_once_with("test-doc-id")
        self.mock_document_service.process_template.assert_called_once()

    def test_process_document_template_document_not_found(self):
        """Test processing template for non-existent document"""
        self.mock_document_service.get_document.return_value = None

        response = self.client.post("/api/documents/nonexistent/process-template")

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

    def test_process_document_template_with_target_date(self):
        """Test processing document template with specific target date"""
        mock_document = Mock()
        mock_document.content_md = "{{LIMITLESS_DAY}}"
        self.mock_document_service.get_document.return_value = mock_document
        self.mock_document_service.process_template.return_value = "Resolved content"

        response = self.client.post(
            "/api/documents/test-doc-id/process-template?target_date=2024-01-15",
        )

        assert response.status_code == 200

        # Verify target_date was passed correctly
        call_args = self.mock_document_service.process_template.call_args
        assert call_args[1]["target_date"] == "2024-01-15"

    def test_api_request_validation(self):
        """Test API request validation"""
        # Test missing required content field
        response = self.client.post("/api/documents/process-template", json={})

        assert response.status_code == 422  # Validation error

        # Test invalid date format (if we add validation)
        response = self.client.post("/api/documents/process-template", json={
            "content": "{{LIMITLESS_DAY}}",
            "target_date": "invalid-date",
        })

        # Should still process (date validation is in processor, not API)
        # This test documents current behavior


class TestTemplateEndToEndScenarios:
    """End-to-end tests for complete template processing workflows"""

    def setup_method(self):
        """Set up end-to-end test fixtures"""
        # Create real database and services for integration testing
        self.db_service = DatabaseService(":memory:")

        self.mock_config = Mock(spec=AppConfig)
        self.mock_config.documents.max_title_length = 200
        self.mock_config.documents.max_content_length = 50000
        self.mock_config.documents.chunking_enabled = False

        self.mock_vector_store = Mock()
        self.mock_embedding_service = Mock()

        self.document_service = DocumentService(
            database=self.db_service,
            vector_store=self.mock_vector_store,
            embedding_service=self.mock_embedding_service,
            config=self.mock_config,
        )

        # Add realistic test data
        self._add_realistic_test_data()

    def _add_realistic_test_data(self):
        """Add realistic test data for end-to-end scenarios"""
        # Limitless data - meetings and activities
        limitless_data = [
            ("limitless:standup", "standup", "Daily standup - discussed sprint progress, blocked on API review", "2024-01-15"),
            ("limitless:client_call", "client_call", "Client call with Acme Corp - requirements clarification for Q2 features", "2024-01-15"),
            ("limitless:planning", "planning", "Sprint planning session - story point estimation completed", "2024-01-14"),
            ("limitless:review", "review", "Code review session - addressed security feedback", "2024-01-13"),
        ]

        # Twitter data - social media activities
        twitter_data = [
            ("twitter:tech_article", "tech_article", "Shared interesting article about AI developments in healthcare", "2024-01-15"),
            ("twitter:conference", "conference", "Live tweeting from TechConf 2024 - great insights on cloud architecture", "2024-01-14"),
        ]

        # News data - industry news
        news_data = [
            ("news:ai_breakthrough", "ai_breakthrough", "AI Breakthrough: New model achieves 95% accuracy in medical diagnosis", "2024-01-15"),
            ("news:market_update", "market_update", "Tech stocks rally on positive earnings reports", "2024-01-10"),
            ("news:policy_change", "policy_change", "New data privacy regulations announced for 2024", "2024-01-05"),
        ]

        # Add all data to database
        for namespace, data_list in [("limitless", limitless_data), ("twitter", twitter_data), ("news", news_data)]:
            for item_id, source_id, content, days_date in data_list:
                self.db_service.store_data_item(
                    id=f"{namespace}:{source_id}",
                    namespace=namespace,
                    source_id=source_id,
                    content=content,
                    days_date=days_date,
                )

    def test_complete_daily_summary_workflow(self):
        """Test complete workflow for generating a daily summary"""
        # Template for daily summary
        daily_template = """
        # Daily Summary - {{LIMITLESS_DAY}}
        
        ## Today's Meetings and Activities
        {{LIMITLESS_DAY}}
        
        ## Social Media Highlights  
        {{TWITTER_DAY}}
        
        ## Industry News
        {{NEWS_DAY}}
        
        ## This Week's Context
        {{LIMITLESS_WEEK}}
        """

        result = self.document_service.process_template(daily_template, "2024-01-15")

        # Verify all sections are populated
        assert "# Daily Summary - 2024-01-15" in result
        assert "Daily standup - discussed sprint progress" in result
        assert "Client call with Acme Corp" in result
        assert "Shared interesting article about AI" in result
        assert "AI Breakthrough: New model achieves" in result

        # Verify week context includes multiple days
        assert "Sprint planning session" in result  # From 2024-01-14
        assert "Code review session" in result      # From 2024-01-13

    def test_weekly_report_workflow(self):
        """Test workflow for generating weekly report"""
        weekly_template = """
        # Weekly Report
        
        ## Work Summary
        {{LIMITLESS_WEEK}}
        
        ## Social Engagement
        {{TWITTER_WEEK}}
        
        ## Industry Updates (Month-to-Date)
        {{NEWS_MONTH}}
        """

        result = self.document_service.process_template(weekly_template, "2024-01-15")

        # Should include data from multiple days and timeframes
        assert "Daily standup" in result       # Current day
        assert "Sprint planning" in result     # Previous days
        assert "Code review" in result         # Previous days
        assert "Live tweeting from TechConf" in result  # Social from week
        assert "New data privacy regulations" in result  # News from month

    def test_prompt_with_mixed_valid_invalid_variables(self):
        """Test handling of prompts with both valid and invalid template variables"""
        mixed_template = """
        Valid data: {{LIMITLESS_DAY}}
        Invalid data: {{NONEXISTENT_SOURCE}}
        More valid data: {{NEWS_DAY}}
        Bad format: {SINGLE_BRACES}
        Another invalid: {{LIMITLESS_BADRANGE}}
        """

        result = self.document_service.process_template(mixed_template, "2024-01-15")

        # Valid variables should be resolved
        assert "Daily standup - discussed sprint progress" in result
        assert "AI Breakthrough: New model achieves" in result

        # Invalid variables should remain unchanged
        assert "{{NONEXISTENT_SOURCE}}" in result
        assert "{SINGLE_BRACES}" in result
        assert "{{LIMITLESS_BADRANGE}}" in result

        # Template markers should not appear for valid variables
        assert "{{LIMITLESS_DAY}}" not in result
        assert "{{NEWS_DAY}}" not in result

    def test_empty_data_scenarios(self):
        """Test scenarios where template variables have no data"""
        template_future_date = """
        Future activities: {{LIMITLESS_DAY}}
        Future social: {{TWITTER_DAY}}
        """

        # Use future date with no data
        result = self.document_service.process_template(template_future_date, "2024-12-31")

        # Should show "no data" messages
        assert "[No data available for LIMITLESS_DAY]" in result
        assert "[No data available for TWITTER_DAY]" in result

    def test_validation_before_processing(self):
        """Test template validation before processing"""
        template = "Today: {{LIMITLESS_DAY}} Invalid: {{BAD_FORMAT}}"

        # Validate first
        validation = self.document_service.validate_template(template)

        assert validation["is_valid"] is False  # Contains invalid variables
        assert validation["total_variables"] == 1  # Only count valid ones
        assert "{{LIMITLESS_DAY}}" in validation["valid_variables"]

        # Process anyway (should handle invalid gracefully)
        result = self.document_service.process_template(template, "2024-01-15")

        # Valid variable resolved, invalid preserved
        assert "Daily standup" in result
        assert "{{BAD_FORMAT}}" in result
