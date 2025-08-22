#!/usr/bin/env python3
"""
Test suite for the database-level duplicate header fix.

This test verifies that the get_markdown_by_date method prevents
duplicate headers across all fallback paths.
"""

import os
import tempfile
import unittest

from core.database import DatabaseService


class TestDatabaseDuplicateHeaderFix(unittest.TestCase):
    """Test cases for database-level duplicate header prevention"""

    def setUp(self):
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_service = DatabaseService(self.temp_db.name)

    def tearDown(self):
        # Clean up the temporary database
        os.unlink(self.temp_db.name)

    def test_fallback_constructed_from_title_content_removes_duplicates(self):
        """Test that the constructed_from_title_content fallback removes duplicate headers"""
        # Store an item that will trigger the fallback path with duplicate headers in content
        test_date = "2024-01-15"
        content_with_duplicate = "# Test Meeting\n\nThis content already has the title as a header.\n\nMore content here."

        self.db_service.store_data_item(
            id="limitless:test_001",
            namespace="limitless",
            source_id="test_001",
            content=content_with_duplicate,
            metadata={
                "title": "Test Meeting",
                "start_time": "2024-01-15T10:00:00Z",
                # Note: No cleaned_markdown, no markdown fields to trigger fallback
            },
            days_date=test_date,
        )

        result = self.db_service.get_markdown_by_date(test_date, namespaces=["limitless"])

        # Should only have ONE instance of the title header
        self.assertEqual(result.count("# Test Meeting"), 1)
        self.assertIn("This content already has the title as a header.", result)
        self.assertIn("More content here.", result)
        self.assertIn("*10:00 AM*", result)

    def test_fallback_metadata_markdown_removes_duplicates(self):
        """Test that the metadata.markdown fallback removes duplicate headers"""
        test_date = "2024-01-15"
        markdown_with_duplicate = "# Important Meeting\n\nFirst section.\n\n# Important Meeting\n\nSecond section."

        self.db_service.store_data_item(
            id="limitless:test_002",
            namespace="limitless",
            source_id="test_002",
            content="some content",
            metadata={
                "title": "Important Meeting",
                "markdown": markdown_with_duplicate,
                # Note: No cleaned_markdown to trigger fallback
            },
            days_date=test_date,
        )

        result = self.db_service.get_markdown_by_date(test_date, namespaces=["limitless"])

        # Should only have ONE instance of the title header
        self.assertEqual(result.count("# Important Meeting"), 1)
        self.assertIn("First section.", result)
        self.assertIn("Second section.", result)

    def test_fallback_original_lifelog_markdown_removes_duplicates(self):
        """Test that the original_lifelog.markdown fallback removes duplicate headers"""
        test_date = "2024-01-15"
        original_markdown = "# Weekly Standup\n\nAgenda items.\n\n# Weekly Standup\n\nDuplicate header content."

        self.db_service.store_data_item(
            id="limitless:test_003",
            namespace="limitless",
            source_id="test_003",
            content="some content",
            metadata={
                "title": "Weekly Standup",
                "original_lifelog": {
                    "markdown": original_markdown,
                    "title": "Weekly Standup",
                },
                # Note: No cleaned_markdown, no direct markdown to trigger this fallback
            },
            days_date=test_date,
        )

        result = self.db_service.get_markdown_by_date(test_date, namespaces=["limitless"])

        # Should only have ONE instance of the title header
        self.assertEqual(result.count("# Weekly Standup"), 1)
        self.assertIn("Agenda items.", result)
        self.assertIn("Duplicate header content.", result)

    def test_cleaned_markdown_preserves_processor_deduplication(self):
        """Test that items with cleaned_markdown (from processor) work correctly"""
        test_date = "2024-01-15"

        # This simulates what the MarkdownProcessor would generate (already deduplicated)
        cleaned_markdown = "# Team Meeting\n\n*02:00 PM*\n\nDiscussion points here."

        self.db_service.store_data_item(
            id="limitless:test_004",
            namespace="limitless",
            source_id="test_004",
            content="some content",
            metadata={
                "title": "Team Meeting",
                "cleaned_markdown": cleaned_markdown,  # This should be used directly
            },
            days_date=test_date,
        )

        result = self.db_service.get_markdown_by_date(test_date, namespaces=["limitless"])

        # Should use the cleaned_markdown as-is
        self.assertEqual(result.count("# Team Meeting"), 1)
        self.assertIn("*02:00 PM*", result)
        self.assertIn("Discussion points here.", result)

    def test_multiple_items_with_mixed_fallback_paths(self):
        """Test multiple items using different fallback paths"""
        test_date = "2024-01-15"

        # Item 1: Uses cleaned_markdown (no duplication expected)
        self.db_service.store_data_item(
            id="limitless:item1",
            namespace="limitless",
            source_id="item1",
            content="content1",
            metadata={
                "title": "Meeting A",
                "cleaned_markdown": "# Meeting A\n\n*09:00 AM*\n\nFirst meeting content.",
            },
            days_date=test_date,
        )

        # Item 2: Uses fallback construction (potential duplication)
        self.db_service.store_data_item(
            id="limitless:item2",
            namespace="limitless",
            source_id="item2",
            content="# Meeting B\n\nDuplicate header in content.",
            metadata={
                "title": "Meeting B",
                "start_time": "2024-01-15T14:00:00Z",
            },
            days_date=test_date,
        )

        result = self.db_service.get_markdown_by_date(test_date, namespaces=["limitless"])

        # Should have one header for each meeting
        self.assertEqual(result.count("# Meeting A"), 1)
        self.assertEqual(result.count("# Meeting B"), 1)
        self.assertIn("First meeting content.", result)
        self.assertIn("Duplicate header in content.", result)
        self.assertIn("---", result)  # Separator between items

    def test_remove_duplicate_headers_helper_method(self):
        """Test the helper method directly"""
        content = "# Sample Header\n\nContent here.\n\n# Sample Header\n\nMore content."
        target_header = "# Sample Header"

        result = self.db_service._remove_duplicate_headers(content, target_header)

        # Should have removed both instances
        self.assertEqual(result.count("# Sample Header"), 0)
        self.assertIn("Content here.", result)
        self.assertIn("More content.", result)


if __name__ == "__main__":
    print("Testing database-level duplicate header fix...")
    unittest.main(verbosity=2)
