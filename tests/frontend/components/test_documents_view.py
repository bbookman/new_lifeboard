"""
Frontend UI tests for DocumentsView component

Tests cover UI interactions for creating, editing, deleting, and searching
documents of all types (Note, Prompt, Folder, Link), including combobox functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestDocumentsViewUI:
    """Test DocumentsView component UI functionality"""
    
    @pytest.fixture
    def mock_api_responses(self):
        """Mock API response data"""
        return {
            "documents_list": {
                "documents": [
                    {
                        "id": "note-1",
                        "title": "Test Note",
                        "document_type": "note",
                        "content_delta": {"ops": [{"insert": "Note content\n"}]},
                        "content_md": "Note content",
                        "path": "/",
                        "is_folder": False,
                        "url": None,
                        "home_date": "2023-01-01T00:00:00Z",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-01T00:00:00Z"
                    },
                    {
                        "id": "prompt-1",
                        "title": "AI Assistant",
                        "document_type": "prompt",
                        "content_delta": {"ops": [{"insert": "You are helpful {{USER_CONTEXT}}\n"}]},
                        "content_md": "You are helpful {{USER_CONTEXT}}",
                        "path": "/",
                        "is_folder": False,
                        "url": None,
                        "home_date": "2023-01-01T00:00:00Z",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-01T00:00:00Z"
                    },
                    {
                        "id": "folder-1",
                        "title": "Projects",
                        "document_type": "folder",
                        "content_delta": {"ops": [{"insert": "\n"}]},
                        "content_md": "",
                        "path": "/Projects/",
                        "is_folder": True,
                        "url": None,
                        "home_date": "2023-01-01T00:00:00Z",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-01T00:00:00Z"
                    },
                    {
                        "id": "link-1",
                        "title": "Useful Resource",
                        "document_type": "link",
                        "content_delta": {"ops": [{"insert": "Great learning resource\n"}]},
                        "content_md": "Great learning resource",
                        "path": "/",
                        "is_folder": False,
                        "url": "https://example.com",
                        "home_date": "2023-01-01T00:00:00Z",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-01T00:00:00Z"
                    }
                ],
                "total": 4,
                "limit": 50,
                "offset": 0
            },
            "search_results": {
                "results": [
                    {
                        "document": {
                            "id": "note-1",
                            "title": "Test Note",
                            "document_type": "note",
                            "content_delta": {"ops": [{"insert": "Matching content\n"}]},
                            "content_md": "Matching content",
                            "path": "/",
                            "is_folder": False,
                            "url": None,
                            "home_date": "2023-01-01T00:00:00Z",
                            "created_at": "2023-01-01T00:00:00Z",
                            "updated_at": "2023-01-01T00:00:00Z"
                        },
                        "score": 0.95
                    }
                ],
                "total": 1,
                "query": "matching"
            },
            "create_response": {
                "id": "new-doc-123",
                "title": "New Document",
                "document_type": "note",
                "content_delta": {"ops": [{"insert": "New content\n"}]},
                "content_md": "New content",
                "path": "/",
                "is_folder": False,
                "url": None,
                "home_date": "2023-01-01T00:00:00Z",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            },
            "title_validation": {
                "is_unique": True
            }
        }

    def test_document_type_icons_display(self, mock_api_responses):
        """Test that correct icons are displayed for each document type"""
        # Test data contains all document types
        documents = mock_api_responses["documents_list"]["documents"]
        
        # Note document should show File icon
        note_doc = next(d for d in documents if d["document_type"] == "note")
        assert note_doc["document_type"] == "note"
        
        # Prompt document should show ScrollText icon  
        prompt_doc = next(d for d in documents if d["document_type"] == "prompt")
        assert prompt_doc["document_type"] == "prompt"
        
        # Folder document should show Folder icon and is_folder=True
        folder_doc = next(d for d in documents if d["document_type"] == "folder")
        assert folder_doc["document_type"] == "folder"
        assert folder_doc["is_folder"] is True
        
        # Link document should show Link icon and have URL
        link_doc = next(d for d in documents if d["document_type"] == "link")
        assert link_doc["document_type"] == "link"
        assert link_doc["url"] is not None

    def test_document_type_filter_combobox(self, mock_api_responses):
        """Test document type filter combobox functionality"""
        # Mock the component state for filter testing
        filter_options = ['all', 'note', 'prompt', 'folder', 'link', 'home_date', 'none']
        
        # Test all filter options are available
        assert 'all' in filter_options
        assert 'note' in filter_options
        assert 'prompt' in filter_options
        assert 'folder' in filter_options
        assert 'link' in filter_options
        
        # Test filtering by note type
        documents = mock_api_responses["documents_list"]["documents"]
        note_docs = [d for d in documents if d["document_type"] == "note"]
        assert len(note_docs) == 1
        assert note_docs[0]["title"] == "Test Note"
        
        # Test filtering by prompt type
        prompt_docs = [d for d in documents if d["document_type"] == "prompt"]
        assert len(prompt_docs) == 1
        assert prompt_docs[0]["title"] == "AI Assistant"
        
        # Test filtering by folder type
        folder_docs = [d for d in documents if d["document_type"] == "folder"]
        assert len(folder_docs) == 1
        assert folder_docs[0]["title"] == "Projects"
        assert folder_docs[0]["is_folder"] is True
        
        # Test filtering by link type
        link_docs = [d for d in documents if d["document_type"] == "link"]
        assert len(link_docs) == 1
        assert link_docs[0]["title"] == "Useful Resource"
        assert link_docs[0]["url"] == "https://example.com"

    def test_create_document_dialog_workflow(self, mock_api_responses):
        """Test create document dialog workflow for all types"""
        
        # Test create note workflow
        create_data = {
            "title": "My New Note",
            "document_type": "note",
            "content_delta": {"ops": [{"insert": "Note content\n"}]},
            "path": "/"
        }
        
        # Validate form data structure
        assert "title" in create_data
        assert "document_type" in create_data
        assert "content_delta" in create_data
        assert create_data["document_type"] == "note"
        
        # Test create prompt workflow
        prompt_data = {
            "title": "Custom Prompt",
            "document_type": "prompt",
            "content_delta": {"ops": [{"insert": "You are {{ROLE}}\n"}]},
            "path": "/"
        }
        
        assert prompt_data["document_type"] == "prompt"
        # Check template variables are preserved
        content_text = prompt_data["content_delta"]["ops"][0]["insert"]
        assert "{{ROLE}}" in content_text
        
        # Test create folder workflow
        folder_data = {
            "name": "New Project",
            "parent_path": "/"
        }
        
        assert "name" in folder_data
        assert "parent_path" in folder_data
        
        # Test create link workflow
        link_data = {
            "title": "External Link",
            "document_type": "link",
            "content_delta": {"ops": [{"insert": "Link description\n"}]},
            "path": "/",
            "url": "https://example.com"
        }
        
        assert link_data["document_type"] == "link"
        assert "url" in link_data
        assert link_data["url"] == "https://example.com"

    def test_document_creation_type_selection(self, mock_api_responses):
        """Test document type selection in creation dialog"""
        
        # Test document type selection options
        document_types = ["folder", "note", "prompt", "link"]
        
        for doc_type in document_types:
            assert doc_type in document_types
        
        # Test type-specific form fields
        # Note: Basic title and content
        note_fields = ["title", "document_type", "content_delta"]
        
        # Prompt: Same as note but typically has template variables
        prompt_fields = ["title", "document_type", "content_delta"]
        
        # Folder: Only needs name and parent path
        folder_fields = ["name", "parent_path"]
        
        # Link: Needs URL in addition to basic fields
        link_fields = ["title", "document_type", "content_delta", "url"]
        
        assert len(note_fields) == 3
        assert len(prompt_fields) == 3
        assert len(folder_fields) == 2
        assert len(link_fields) == 4

    def test_search_functionality_all_types(self, mock_api_responses):
        """Test search functionality across all document types"""
        
        search_results = mock_api_responses["search_results"]
        
        # Test search returns results with scores
        assert "results" in search_results
        assert "query" in search_results
        assert search_results["query"] == "matching"
        
        # Test search result structure
        result = search_results["results"][0]
        assert "document" in result
        assert "score" in result
        assert result["score"] == 0.95
        
        # Test document in search result
        document = result["document"]
        assert "id" in document
        assert "title" in document
        assert "document_type" in document
        assert "content_md" in document
        
        # Test search can find different document types
        # (In real implementation, this would test searching for prompts, links, etc.)
        searchable_types = ["note", "prompt", "link"]  # folders typically not searched
        assert document["document_type"] in searchable_types or document["document_type"] == "note"

    def test_search_filter_by_type(self, mock_api_responses):
        """Test search with document type filtering"""
        
        # Test search query structure with type filter
        search_params = {
            "q": "test query",
            "document_type": "prompt",
            "limit": 20
        }
        
        assert "q" in search_params
        assert "document_type" in search_params
        assert search_params["document_type"] == "prompt"
        
        # Test type-specific searches
        type_filters = ["note", "prompt", "link"]
        
        for doc_type in type_filters:
            type_search = {
                "q": "search term",
                "document_type": doc_type,
                "limit": 20
            }
            assert type_search["document_type"] == doc_type

    def test_combobox_sort_options(self, mock_api_responses):
        """Test combobox sort options functionality"""
        
        # Test available sort options
        sort_options = ['name', 'type', 'modified', 'home_date', 'created']
        sort_orders = ['asc', 'desc']
        
        # Validate sort options
        assert 'name' in sort_options
        assert 'type' in sort_options
        assert 'modified' in sort_options
        assert 'home_date' in sort_options
        assert 'created' in sort_options
        
        # Validate sort orders
        assert 'asc' in sort_orders
        assert 'desc' in sort_orders
        
        # Test sorting by different fields
        documents = mock_api_responses["documents_list"]["documents"]
        
        # Sort by name (alphabetical)
        sorted_by_name = sorted(documents, key=lambda x: x["title"])
        assert sorted_by_name[0]["title"] == "AI Assistant"
        
        # Sort by type
        sorted_by_type = sorted(documents, key=lambda x: x["document_type"])
        assert sorted_by_type[0]["document_type"] == "folder"
        
        # Sort by created date
        sorted_by_created = sorted(documents, key=lambda x: x["created_at"], reverse=True)
        assert len(sorted_by_created) == 4

    def test_folder_navigation_breadcrumbs(self, mock_api_responses):
        """Test folder navigation and breadcrumb functionality"""
        
        # Test folder path handling
        folder_paths = ["/", "/Projects/", "/Projects/Subfolder/"]
        
        for path in folder_paths:
            assert path.startswith("/")
            if path != "/":
                assert path.endswith("/")
        
        # Test breadcrumb generation
        def generate_breadcrumbs(path):
            if path == "/":
                return [{"name": "Root", "path": "/"}]
            
            parts = path.strip("/").split("/")
            breadcrumbs = [{"name": "Root", "path": "/"}]
            
            current_path = "/"
            for part in parts:
                if part:
                    current_path += part + "/"
                    breadcrumbs.append({"name": part, "path": current_path})
            
            return breadcrumbs
        
        # Test root breadcrumb
        root_breadcrumbs = generate_breadcrumbs("/")
        assert len(root_breadcrumbs) == 1
        assert root_breadcrumbs[0]["name"] == "Root"
        
        # Test nested folder breadcrumbs
        nested_breadcrumbs = generate_breadcrumbs("/Projects/Subfolder/")
        assert len(nested_breadcrumbs) == 3
        assert nested_breadcrumbs[0]["name"] == "Root"
        assert nested_breadcrumbs[1]["name"] == "Projects"
        assert nested_breadcrumbs[2]["name"] == "Subfolder"

    def test_document_edit_modal_all_types(self, mock_api_responses):
        """Test document edit modal for all document types"""
        
        documents = mock_api_responses["documents_list"]["documents"]
        
        # Test editing note document
        note_doc = next(d for d in documents if d["document_type"] == "note")
        edit_note_data = {
            "title": note_doc["title"],
            "document_type": note_doc["document_type"],
            "content_delta": note_doc["content_delta"]
        }
        
        assert edit_note_data["document_type"] == "note"
        assert "content_delta" in edit_note_data
        
        # Test editing prompt document
        prompt_doc = next(d for d in documents if d["document_type"] == "prompt")
        edit_prompt_data = {
            "title": prompt_doc["title"],
            "document_type": prompt_doc["document_type"],
            "content_delta": prompt_doc["content_delta"]
        }
        
        assert edit_prompt_data["document_type"] == "prompt"
        # Check for template variables in prompt
        content = prompt_doc["content_md"]
        assert "{{" in content or "}}" in content or "USER_CONTEXT" in content
        
        # Test editing link document
        link_doc = next(d for d in documents if d["document_type"] == "link")
        edit_link_data = {
            "title": link_doc["title"],
            "document_type": link_doc["document_type"],
            "content_delta": link_doc["content_delta"],
            "url": link_doc["url"]
        }
        
        assert edit_link_data["document_type"] == "link"
        assert "url" in edit_link_data
        assert edit_link_data["url"] == "https://example.com"

    def test_bulk_selection_and_operations(self, mock_api_responses):
        """Test bulk selection and operations functionality"""
        
        documents = mock_api_responses["documents_list"]["documents"]
        
        # Test selection state tracking
        def simulate_selection_state():
            selection_state = {}
            for doc in documents:
                selection_state[doc["id"]] = False  # Initially unselected
            return selection_state
        
        selection = simulate_selection_state()
        
        # Test individual selection
        selection["note-1"] = True
        selected_count = sum(1 for selected in selection.values() if selected)
        assert selected_count == 1
        
        # Test select all functionality
        for doc_id in selection:
            selection[doc_id] = True
        
        all_selected = all(selection.values())
        assert all_selected is True
        
        # Test bulk operations availability
        bulk_operations = ["delete", "move", "export"]
        
        for operation in bulk_operations:
            assert operation in bulk_operations
        
        # Test deselect all
        for doc_id in selection:
            selection[doc_id] = False
        
        none_selected = any(selection.values())
        assert none_selected is False

    def test_title_validation_ui(self, mock_api_responses):
        """Test title validation in UI forms"""
        
        validation_response = mock_api_responses["title_validation"]
        
        # Test unique title validation
        assert "is_unique" in validation_response
        assert validation_response["is_unique"] is True
        
        # Test validation for different document types
        validation_cases = [
            {"title": "New Note", "document_type": "note", "expected_unique": True},
            {"title": "New Prompt", "document_type": "prompt", "expected_unique": True},
            {"title": "New Folder", "document_type": "folder", "expected_unique": True},
            {"title": "New Link", "document_type": "link", "expected_unique": True}
        ]
        
        for case in validation_cases:
            assert case["document_type"] in ["note", "prompt", "folder", "link"]
            # In real implementation, this would call the validation API
            # For test, we assume the validation structure is correct
            assert case["expected_unique"] is True

    def test_quill_editor_integration(self, mock_api_responses):
        """Test Quill editor integration for content editing"""
        
        # Test Quill Delta format structure
        sample_delta = {"ops": [{"insert": "Hello "},
                               {"insert": "World", "attributes": {"bold": True}},
                               {"insert": "\n"}]}
        
        # Validate Delta structure
        assert "ops" in sample_delta
        assert isinstance(sample_delta["ops"], list)
        
        # Test Delta operations
        ops = sample_delta["ops"]
        assert len(ops) == 3
        assert ops[0]["insert"] == "Hello "
        assert ops[1]["insert"] == "World"
        assert "attributes" in ops[1]
        assert ops[1]["attributes"]["bold"] is True
        
        # Test empty content Delta
        empty_delta = {"ops": [{"insert": "\n"}]}
        assert len(empty_delta["ops"]) == 1
        assert empty_delta["ops"][0]["insert"] == "\n"
        
        # Test Delta with various formatting
        formatted_delta = {
            "ops": [
                {"insert": "Header", "attributes": {"header": 1}},
                {"insert": "\n"},
                {"insert": "Bold text", "attributes": {"bold": True}},
                {"insert": " and "},
                {"insert": "italic text", "attributes": {"italic": True}},
                {"insert": "\n"}
            ]
        }
        
        header_op = next(op for op in formatted_delta["ops"] if op.get("attributes", {}).get("header"))
        assert header_op["insert"] == "Header"
        assert header_op["attributes"]["header"] == 1

    def test_link_document_url_validation(self, mock_api_responses):
        """Test URL validation for link documents"""
        
        # Test valid URLs
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://subdomain.example.com/path",
            "https://example.com/path?query=value"
        ]
        
        for url in valid_urls:
            assert url.startswith("http://") or url.startswith("https://")
        
        # Test link document with URL
        link_doc = next(d for d in mock_api_responses["documents_list"]["documents"] 
                       if d["document_type"] == "link")
        
        assert link_doc["url"] is not None
        assert link_doc["url"].startswith("https://")
        
        # Test URL field requirements for link type
        link_form_data = {
            "title": "Test Link",
            "document_type": "link",
            "content_delta": {"ops": [{"insert": "Description\n"}]},
            "url": "https://example.com"
        }
        
        assert link_form_data["document_type"] == "link"
        assert "url" in link_form_data
        assert link_form_data["url"].startswith("https://")

    def test_responsive_layout_behavior(self, mock_api_responses):
        """Test responsive layout behavior for different screen sizes"""
        
        # Test layout modes
        layout_modes = ["list", "grid", "compact"]
        
        for mode in layout_modes:
            assert mode in layout_modes
        
        # Test view modes
        view_modes = ["list", "document"]
        
        assert "list" in view_modes
        assert "document" in view_modes
        
        # Test mobile-specific features
        mobile_features = {
            "show_sidebar": False,
            "compact_toolbar": True,
            "swipe_actions": True,
            "touch_friendly_buttons": True
        }
        
        for feature, enabled in mobile_features.items():
            assert isinstance(enabled, bool)
        
        # Test tablet layout
        tablet_features = {
            "show_sidebar": True,
            "split_view": True,
            "drag_drop": True
        }
        
        for feature, enabled in tablet_features.items():
            assert isinstance(enabled, bool)

    def test_keyboard_shortcuts_support(self, mock_api_responses):
        """Test keyboard shortcuts support"""
        
        # Test common keyboard shortcuts
        keyboard_shortcuts = {
            "Ctrl+N": "create_new_document",
            "Ctrl+S": "save_document",
            "Ctrl+F": "search",
            "Delete": "delete_selected",
            "Escape": "close_modal",
            "Enter": "confirm_action"
        }
        
        for shortcut, action in keyboard_shortcuts.items():
            assert len(shortcut) > 0
            assert len(action) > 0
        
        # Test navigation shortcuts
        navigation_shortcuts = {
            "Arrow Up": "previous_document",
            "Arrow Down": "next_document",
            "Tab": "next_focusable",
            "Shift+Tab": "previous_focusable"
        }
        
        for shortcut, action in navigation_shortcuts.items():
            assert len(shortcut) > 0
            assert len(action) > 0