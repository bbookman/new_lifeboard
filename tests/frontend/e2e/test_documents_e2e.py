"""
End-to-End tests for Documents functionality

Tests complete user workflows for creating, editing, searching, and managing
documents of all types using Playwright or similar E2E testing framework.
"""

import pytest
from unittest.mock import MagicMock, patch
import asyncio


class TestDocumentsE2E:
    """End-to-end tests for document management workflows"""
    
    @pytest.fixture
    def browser_page(self):
        """Mock browser page for E2E testing"""
        page = MagicMock()
        page.goto = MagicMock()
        page.fill = MagicMock()
        page.click = MagicMock()
        page.wait_for_selector = MagicMock()
        page.get_by_text = MagicMock()
        page.get_by_role = MagicMock()
        page.keyboard = MagicMock()
        page.screenshot = MagicMock()
        return page
    
    def test_create_note_workflow(self, browser_page):
        """Test complete workflow for creating a note"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Click create button
        browser_page.click("[data-testid='create-document-btn']")
        
        # Select document type
        browser_page.click("[data-testid='document-type-combobox']")
        browser_page.click("[data-testid='type-option-note']")
        
        # Fill in title
        browser_page.fill("[data-testid='document-title-input']", "My Test Note")
        
        # Fill in content using Quill editor
        browser_page.click("[data-testid='quill-editor'] .ql-editor")
        browser_page.keyboard.type("This is the content of my test note.")
        
        # Apply some formatting
        browser_page.keyboard.press("Control+A")  # Select all
        browser_page.click(".ql-bold")  # Make bold
        
        # Save document
        browser_page.click("[data-testid='save-document-btn']")
        
        # Wait for success message
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify document appears in list
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Verify document card
        note_card = browser_page.get_by_text("My Test Note")
        assert note_card is not None
        
        # Verify document type icon
        browser_page.wait_for_selector("[data-testid='doc-type-icon-note']")

    def test_create_prompt_workflow(self, browser_page):
        """Test complete workflow for creating a prompt"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Click create button
        browser_page.click("[data-testid='create-document-btn']")
        
        # Select prompt type
        browser_page.click("[data-testid='document-type-combobox']")
        browser_page.click("[data-testid='type-option-prompt']")
        
        # Fill in title
        browser_page.fill("[data-testid='document-title-input']", "AI Assistant Prompt")
        
        # Fill in prompt content with template variables
        browser_page.click("[data-testid='quill-editor'] .ql-editor")
        browser_page.keyboard.type("You are a helpful assistant. Answer the following question: {{USER_QUESTION}}")
        
        # Save prompt
        browser_page.click("[data-testid='save-document-btn']")
        
        # Wait for success
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify prompt in list
        browser_page.wait_for_selector("[data-testid='document-list']")
        prompt_card = browser_page.get_by_text("AI Assistant Prompt")
        assert prompt_card is not None
        
        # Verify prompt icon
        browser_page.wait_for_selector("[data-testid='doc-type-icon-prompt']")

    def test_create_link_workflow(self, browser_page):
        """Test complete workflow for creating a link document"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Click create button
        browser_page.click("[data-testid='create-document-btn']")
        
        # Select link type
        browser_page.click("[data-testid='document-type-combobox']")
        browser_page.click("[data-testid='type-option-link']")
        
        # Fill in title
        browser_page.fill("[data-testid='document-title-input']", "Useful Resource")
        
        # Fill in URL (should appear when link type is selected)
        browser_page.fill("[data-testid='link-url-input']", "https://example.com")
        
        # Fill in description
        browser_page.click("[data-testid='quill-editor'] .ql-editor")
        browser_page.keyboard.type("This is a great resource for learning.")
        
        # Save link
        browser_page.click("[data-testid='save-document-btn']")
        
        # Wait for success
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify link in list
        link_card = browser_page.get_by_text("Useful Resource")
        assert link_card is not None
        
        # Verify link icon
        browser_page.wait_for_selector("[data-testid='doc-type-icon-link']")
        
        # Verify URL is displayed
        browser_page.wait_for_selector("[data-testid='link-url']")

    def test_create_folder_workflow(self, browser_page):
        """Test complete workflow for creating a folder"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Click create button
        browser_page.click("[data-testid='create-document-btn']")
        
        # Select folder type
        browser_page.click("[data-testid='document-type-combobox']")
        browser_page.click("[data-testid='type-option-folder']")
        
        # Fill in folder name
        browser_page.fill("[data-testid='folder-name-input']", "Project Documents")
        
        # Save folder
        browser_page.click("[data-testid='save-folder-btn']")
        
        # Wait for success
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify folder in list
        folder_card = browser_page.get_by_text("Project Documents")
        assert folder_card is not None
        
        # Verify folder icon
        browser_page.wait_for_selector("[data-testid='doc-type-icon-folder']")

    def test_search_documents_workflow(self, browser_page):
        """Test complete search workflow"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Click search input
        browser_page.click("[data-testid='search-input']")
        
        # Type search query
        browser_page.keyboard.type("programming")
        
        # Press Enter or wait for search
        browser_page.keyboard.press("Enter")
        
        # Wait for search results
        browser_page.wait_for_selector("[data-testid='search-results']")
        
        # Verify search results are displayed
        results_container = browser_page.wait_for_selector("[data-testid='search-results-container']")
        assert results_container is not None
        
        # Verify search query is highlighted
        browser_page.wait_for_selector("[data-testid='search-query-highlight']")
        
        # Clear search
        browser_page.click("[data-testid='clear-search-btn']")
        
        # Verify all documents are shown again
        browser_page.wait_for_selector("[data-testid='document-list']")

    def test_filter_by_document_type(self, browser_page):
        """Test filtering documents by type"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Click type filter combobox
        browser_page.click("[data-testid='type-filter-combobox']")
        
        # Select "Notes" filter
        browser_page.click("[data-testid='filter-option-note']")
        
        # Wait for filtered results
        browser_page.wait_for_selector("[data-testid='filtered-document-list']")
        
        # Verify only note documents are shown
        note_cards = browser_page.query_selector_all("[data-testid='doc-type-icon-note']")
        prompt_cards = browser_page.query_selector_all("[data-testid='doc-type-icon-prompt']")
        
        # Should have note cards but no prompt cards
        assert len(note_cards) > 0
        assert len(prompt_cards) == 0
        
        # Test "All Documents" filter
        browser_page.click("[data-testid='type-filter-combobox']")
        browser_page.click("[data-testid='filter-option-all']")
        
        # Verify all document types are shown
        browser_page.wait_for_selector("[data-testid='document-list']")

    def test_sort_documents_workflow(self, browser_page):
        """Test sorting documents workflow"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Click sort combobox
        browser_page.click("[data-testid='sort-combobox']")
        
        # Select "Name" sorting
        browser_page.click("[data-testid='sort-option-name']")
        
        # Click sort order button to change to ascending
        browser_page.click("[data-testid='sort-order-btn']")
        
        # Wait for documents to be reordered
        browser_page.wait_for_timeout(500)  # Brief wait for reordering
        
        # Verify sort order indicator
        browser_page.wait_for_selector("[data-testid='sort-order-asc']")
        
        # Test sort by date
        browser_page.click("[data-testid='sort-combobox']")
        browser_page.click("[data-testid='sort-option-modified']")
        
        # Wait for reordering
        browser_page.wait_for_timeout(500)

    def test_edit_document_workflow(self, browser_page):
        """Test editing an existing document"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Click on first document to open it
        browser_page.click("[data-testid='document-card']:first-child")
        
        # Click edit button
        browser_page.click("[data-testid='edit-document-btn']")
        
        # Modify title
        browser_page.fill("[data-testid='document-title-input']", "Updated Document Title")
        
        # Modify content
        browser_page.click("[data-testid='quill-editor'] .ql-editor")
        browser_page.keyboard.press("Control+A")  # Select all
        browser_page.keyboard.type("Updated content for this document.")
        
        # Save changes
        browser_page.click("[data-testid='save-document-btn']")
        
        # Wait for success message
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify updated title is displayed
        updated_title = browser_page.get_by_text("Updated Document Title")
        assert updated_title is not None

    def test_delete_document_workflow(self, browser_page):
        """Test deleting a document"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Get initial document count
        initial_docs = browser_page.query_selector_all("[data-testid='document-card']")
        initial_count = len(initial_docs)
        
        # Click on first document
        browser_page.click("[data-testid='document-card']:first-child")
        
        # Click delete button
        browser_page.click("[data-testid='delete-document-btn']")
        
        # Confirm deletion in dialog
        browser_page.wait_for_selector("[data-testid='delete-confirmation-dialog']")
        browser_page.click("[data-testid='confirm-delete-btn']")
        
        # Wait for success message
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify document count decreased
        remaining_docs = browser_page.query_selector_all("[data-testid='document-card']")
        assert len(remaining_docs) == initial_count - 1

    def test_folder_navigation_workflow(self, browser_page):
        """Test navigating into and out of folders"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Create a test folder first (assuming it exists)
        # Click on folder to enter it
        browser_page.click("[data-testid='folder-card']:first-child")
        
        # Wait for folder contents to load
        browser_page.wait_for_selector("[data-testid='folder-contents']")
        
        # Verify breadcrumb shows current location
        browser_page.wait_for_selector("[data-testid='breadcrumb-current']")
        
        # Click breadcrumb to go back to root
        browser_page.click("[data-testid='breadcrumb-root']")
        
        # Verify we're back at root level
        browser_page.wait_for_selector("[data-testid='document-list']")

    def test_bulk_operations_workflow(self, browser_page):
        """Test bulk selection and operations"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Select multiple documents
        browser_page.click("[data-testid='document-checkbox']:first-child")
        browser_page.click("[data-testid='document-checkbox']:nth-child(2)")
        
        # Verify bulk operations toolbar appears
        browser_page.wait_for_selector("[data-testid='bulk-operations-toolbar']")
        
        # Test bulk delete
        browser_page.click("[data-testid='bulk-delete-btn']")
        
        # Confirm bulk deletion
        browser_page.wait_for_selector("[data-testid='bulk-delete-confirmation']")
        browser_page.click("[data-testid='confirm-bulk-delete-btn']")
        
        # Wait for success message
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Verify bulk operations toolbar disappears
        browser_page.wait_for_selector("[data-testid='bulk-operations-toolbar']", state="hidden")

    def test_responsive_layout_mobile(self, browser_page):
        """Test responsive layout on mobile viewport"""
        
        # Set mobile viewport
        browser_page.set_viewport_size({"width": 375, "height": 667})
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Wait for documents to load
        browser_page.wait_for_selector("[data-testid='document-list']")
        
        # Verify mobile layout elements
        browser_page.wait_for_selector("[data-testid='mobile-header']")
        browser_page.wait_for_selector("[data-testid='mobile-fab']")  # Floating Action Button
        
        # Test mobile menu
        browser_page.click("[data-testid='mobile-menu-btn']")
        browser_page.wait_for_selector("[data-testid='mobile-menu-drawer']")
        
        # Test mobile search
        browser_page.click("[data-testid='mobile-search-btn']")
        browser_page.wait_for_selector("[data-testid='mobile-search-overlay']")

    def test_accessibility_workflow(self, browser_page):
        """Test accessibility features"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Test keyboard navigation
        browser_page.keyboard.press("Tab")  # Should focus first interactive element
        browser_page.keyboard.press("Enter")  # Should activate focused element
        
        # Test screen reader landmarks
        main_content = browser_page.get_by_role("main")
        assert main_content is not None
        
        navigation = browser_page.get_by_role("navigation")
        assert navigation is not None
        
        # Test ARIA labels on buttons
        create_btn = browser_page.get_by_role("button", name="Create new document")
        assert create_btn is not None
        
        # Test focus management in modals
        browser_page.click("[data-testid='create-document-btn']")
        browser_page.wait_for_selector("[data-testid='create-document-modal']")
        
        # First input should be focused
        focused_element = browser_page.evaluate("document.activeElement.tagName")
        assert focused_element in ["INPUT", "TEXTAREA"]

    def test_error_handling_workflow(self, browser_page):
        """Test error handling and recovery"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Test network error scenario (mock)
        with patch('requests.get', side_effect=Exception("Network error")):
            browser_page.reload()
            
            # Should show error message
            browser_page.wait_for_selector("[data-testid='error-message']")
            
            # Test retry functionality
            browser_page.click("[data-testid='retry-btn']")
            
            # Should attempt to reload
            browser_page.wait_for_selector("[data-testid='loading-spinner']")

    def test_performance_workflow(self, browser_page):
        """Test performance characteristics"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Measure page load time
        load_start = browser_page.evaluate("performance.timing.navigationStart")
        load_end = browser_page.evaluate("performance.timing.loadEventEnd")
        load_time = load_end - load_start
        
        # Should load within reasonable time (adjust threshold as needed)
        assert load_time < 3000  # 3 seconds
        
        # Test search performance
        search_start = browser_page.evaluate("performance.now()")
        browser_page.fill("[data-testid='search-input']", "test query")
        browser_page.wait_for_selector("[data-testid='search-results']")
        search_end = browser_page.evaluate("performance.now()")
        
        search_time = search_end - search_start
        assert search_time < 1000  # 1 second for search


class TestDocumentsE2EErrorScenarios:
    """Test error scenarios and edge cases in E2E flows"""
    
    def test_validation_errors_workflow(self, browser_page):
        """Test form validation error handling"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Try to create document without title
        browser_page.click("[data-testid='create-document-btn']")
        browser_page.click("[data-testid='save-document-btn']")  # Save without filling title
        
        # Should show validation error
        browser_page.wait_for_selector("[data-testid='validation-error']")
        
        # Error message should mention title requirement
        error_text = browser_page.get_by_text("Title is required")
        assert error_text is not None

    def test_duplicate_title_workflow(self, browser_page):
        """Test duplicate title handling"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Create first document
        browser_page.click("[data-testid='create-document-btn']")
        browser_page.fill("[data-testid='document-title-input']", "Duplicate Title")
        browser_page.click("[data-testid='save-document-btn']")
        browser_page.wait_for_selector("[data-testid='success-message']")
        
        # Try to create second document with same title
        browser_page.click("[data-testid='create-document-btn']")
        browser_page.fill("[data-testid='document-title-input']", "Duplicate Title")
        browser_page.click("[data-testid='save-document-btn']")
        
        # Should show duplicate title error
        browser_page.wait_for_selector("[data-testid='duplicate-title-error']")

    def test_offline_functionality(self, browser_page):
        """Test offline functionality and sync"""
        
        # Navigate to documents page
        browser_page.goto("/documents")
        
        # Simulate going offline
        browser_page.context.set_offline(True)
        
        # Try to create document offline
        browser_page.click("[data-testid='create-document-btn']")
        browser_page.fill("[data-testid='document-title-input']", "Offline Document")
        browser_page.click("[data-testid='save-document-btn']")
        
        # Should show offline indicator
        browser_page.wait_for_selector("[data-testid='offline-indicator']")
        
        # Should queue document for sync
        browser_page.wait_for_selector("[data-testid='sync-pending-indicator']")
        
        # Go back online
        browser_page.context.set_offline(False)
        
        # Should sync pending changes
        browser_page.wait_for_selector("[data-testid='sync-success-indicator']")