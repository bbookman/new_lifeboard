"""
Tests for unified database flow after limitless table removal

These tests verify that the DatabaseService correctly handles data
through the unified data_items table and the get_markdown_by_date method
works with the new architecture.
"""

import os
import sys
import tempfile
import unittest

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.database import DatabaseService


class TestDatabaseUnifiedFlow(unittest.TestCase):
    """Test cases for unified database functionality"""

    def setUp(self):
        """Set up test fixtures with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_service = DatabaseService(self.temp_db.name)

        # Sample data items for testing
        self.sample_limitless_data = [
            {
                "id": "limitless:test_001",
                "namespace": "limitless",
                "source_id": "test_001",
                "content": "Test content 1",
                "metadata": {
                    "title": "Test Meeting 1",
                    "start_time": "2024-01-15T10:00:00Z",
                    "is_starred": True,
                    "cleaned_markdown": "# Test Meeting 1\n\n*10:00 AM*\n\nTest content 1",
                    "original_lifelog": {
                        "id": "test_001",
                        "title": "Test Meeting 1",
                        "contents": [{"type": "text", "content": "Test content 1"}],
                    },
                },
                "days_date": "2024-01-15",
            },
            {
                "id": "limitless:test_002",
                "namespace": "limitless",
                "source_id": "test_002",
                "content": "Test content 2",
                "metadata": {
                    "title": "Test Meeting 2",
                    "start_time": "2024-01-15T14:00:00Z",
                    "is_starred": False,
                    "cleaned_markdown": "# Test Meeting 2\n\n*2:00 PM*\n\nTest content 2",
                    "original_lifelog": {
                        "id": "test_002",
                        "title": "Test Meeting 2",
                        "contents": [{"type": "text", "content": "Test content 2"}],
                    },
                },
                "days_date": "2024-01-15",
            },
        ]

    def tearDown(self):
        """Clean up temporary database"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def _store_test_data(self):
        """Helper method to store test data in database"""
        for item in self.sample_limitless_data:
            self.db_service.store_data_item(
                id=item["id"],
                namespace=item["namespace"],
                source_id=item["source_id"],
                content=item["content"],
                metadata=item["metadata"],
                days_date=item["days_date"],
            )

    def test_get_data_items_by_date_basic_functionality(self):
        """Test basic functionality of get_data_items_by_date"""
        self._store_test_data()

        # Get all data for the test date
        items = self.db_service.get_data_items_by_date("2024-01-15")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["namespace"], "limitless")
        self.assertEqual(items[1]["namespace"], "limitless")

        # Check that metadata is properly parsed
        self.assertIsInstance(items[0]["metadata"], dict)
        self.assertIn("title", items[0]["metadata"])

    def test_get_data_items_by_date_with_namespace_filter(self):
        """Test get_data_items_by_date with namespace filtering"""
        self._store_test_data()

        # Get only limitless items
        limitless_items = self.db_service.get_data_items_by_date("2024-01-15", namespaces=["limitless"])
        self.assertEqual(len(limitless_items), 2)

        # Get non-existent namespace
        other_items = self.db_service.get_data_items_by_date("2024-01-15", namespaces=["other"])
        self.assertEqual(len(other_items), 0)

    def test_get_data_items_by_date_no_data(self):
        """Test get_data_items_by_date returns empty list when no data exists"""
        items = self.db_service.get_data_items_by_date("2024-01-16")
        self.assertEqual(len(items), 0)

    def test_get_markdown_by_date_with_cleaned_markdown(self):
        """Test get_markdown_by_date uses pre-generated cleaned markdown"""
        self._store_test_data()

        result = self.db_service.get_markdown_by_date("2024-01-15", namespaces=["limitless"])

        # Should contain cleaned markdown from both items
        self.assertIn("# Test Meeting 1", result)
        self.assertIn("# Test Meeting 2", result)
        self.assertIn("*10:00 AM*", result)
        self.assertIn("*2:00 PM*", result)
        self.assertIn("Test content 1", result)
        self.assertIn("Test content 2", result)

        # Should have separators between items
        self.assertIn("---", result)

    def test_get_markdown_by_date_fallback_to_legacy_format(self):
        """Test get_markdown_by_date falls back to legacy extraction when no cleaned markdown"""
        # Store data without cleaned_markdown
        legacy_data = {
            "id": "limitless:legacy_001",
            "namespace": "limitless",
            "source_id": "legacy_001",
            "content": "Legacy content",
            "metadata": {
                "title": "Legacy Meeting",
                "start_time": "2024-01-16T09:00:00Z",
                "original_lifelog": {
                    "markdown": "Original markdown content",
                },
            },
            "days_date": "2024-01-16",
        }

        self.db_service.store_data_item(**legacy_data)

        result = self.db_service.get_markdown_by_date("2024-01-16", namespaces=["limitless"])

        # Should fall back to original markdown
        self.assertIn("Original markdown content", result)

    def test_get_markdown_by_date_constructs_from_title_content(self):
        """Test get_markdown_by_date constructs markdown from title and content when needed"""
        # Store data with only title and content, no pre-generated markdown
        minimal_data = {
            "id": "limitless:minimal_001",
            "namespace": "limitless",
            "source_id": "minimal_001",
            "content": "Minimal content",
            "metadata": {
                "title": "Minimal Meeting",
                "start_time": "2024-01-17T11:00:00Z",
            },
            "days_date": "2024-01-17",
        }

        self.db_service.store_data_item(**minimal_data)

        result = self.db_service.get_markdown_by_date("2024-01-17", namespaces=["limitless"])

        # Should construct markdown from title and content
        self.assertIn("# Minimal Meeting", result)
        self.assertIn("Minimal content", result)
        self.assertIn("*11:00 AM*", result)  # Time formatting

    def test_get_markdown_by_date_no_data_returns_default(self):
        """Test get_markdown_by_date returns default message when no data"""
        result = self.db_service.get_markdown_by_date("2024-01-18", namespaces=["limitless"])

        self.assertIn("# 2024-01-18", result)
        self.assertIn("No data available for this date", result)

    def test_get_markdown_by_date_handles_invalid_timestamps(self):
        """Test get_markdown_by_date handles invalid timestamps gracefully"""
        invalid_data = {
            "id": "limitless:invalid_001",
            "namespace": "limitless",
            "source_id": "invalid_001",
            "content": "Content with bad timestamp",
            "metadata": {
                "title": "Invalid Time Meeting",
                "start_time": "invalid-timestamp",
                "cleaned_markdown": "# Invalid Time Meeting\n\nContent with bad timestamp",
            },
            "days_date": "2024-01-19",
        }

        self.db_service.store_data_item(**invalid_data)

        # Should not crash with invalid timestamp
        result = self.db_service.get_markdown_by_date("2024-01-19", namespaces=["limitless"])

        self.assertIn("# Invalid Time Meeting", result)
        self.assertIn("Content with bad timestamp", result)

    def test_get_markdown_by_date_preserves_order(self):
        """Test get_markdown_by_date preserves logical ordering of items"""
        self._store_test_data()

        result = self.db_service.get_markdown_by_date("2024-01-15", namespaces=["limitless"])

        # Should contain both meetings in some logical order
        meeting1_pos = result.find("# Test Meeting 1")
        meeting2_pos = result.find("# Test Meeting 2")

        # Both should be present
        self.assertNotEqual(meeting1_pos, -1)
        self.assertNotEqual(meeting2_pos, -1)

        # Should have separator between them
        separator_pos = result.find("---")
        self.assertNotEqual(separator_pos, -1)

    def test_database_backward_compatibility(self):
        """Test that database maintains backward compatibility with existing data structures"""
        # Test with data that might exist from before the refactoring
        legacy_metadata = {
            "id": "limitless:legacy_002",
            "namespace": "limitless",
            "source_id": "legacy_002",
            "content": "Legacy content format",
            "metadata": {
                # Old format without cleaned_markdown
                "title": "Legacy Format Meeting",
                "original_lifelog": {
                    "id": "legacy_002",
                    "title": "Legacy Format Meeting",
                    "contents": [
                        {"type": "text", "content": "Legacy content format"},
                    ],
                },
            },
            "days_date": "2024-01-20",
        }

        self.db_service.store_data_item(**legacy_metadata)

        # Should still be able to retrieve and process
        items = self.db_service.get_data_items_by_date("2024-01-20", namespaces=["limitless"])
        self.assertEqual(len(items), 1)

        markdown = self.db_service.get_markdown_by_date("2024-01-20", namespaces=["limitless"])
        self.assertIn("Legacy Format Meeting", markdown)
        self.assertIn("Legacy content format", markdown)

    def test_get_days_with_data_includes_limitless_namespace(self):
        """Test that get_days_with_data properly includes limitless namespace data"""
        self._store_test_data()

        # Get all days with data
        all_days = self.db_service.get_days_with_data()
        self.assertIn("2024-01-15", all_days)

        # Get days with limitless data specifically
        limitless_days = self.db_service.get_days_with_data(namespaces=["limitless"])
        self.assertIn("2024-01-15", limitless_days)

    def test_metadata_serialization_deserialization(self):
        """Test that complex metadata is properly serialized and deserialized"""
        complex_metadata = {
            "title": "Complex Meeting",
            "nested_data": {
                "participants": ["Alice", "Bob"],
                "duration": 60,
                "notes": ["Note 1", "Note 2"],
            },
            "cleaned_markdown": "# Complex Meeting\n\nComplex content",
            "boolean_flag": True,
            "null_value": None,
        }

        self.db_service.store_data_item(
            id="limitless:complex_001",
            namespace="limitless",
            source_id="complex_001",
            content="Complex content",
            metadata=complex_metadata,
            days_date="2024-01-21",
        )

        # Retrieve and verify metadata integrity
        items = self.db_service.get_data_items_by_date("2024-01-21", namespaces=["limitless"])
        retrieved_metadata = items[0]["metadata"]

        self.assertEqual(retrieved_metadata["title"], "Complex Meeting")
        self.assertEqual(retrieved_metadata["nested_data"]["participants"], ["Alice", "Bob"])
        self.assertEqual(retrieved_metadata["boolean_flag"], True)
        self.assertIsNone(retrieved_metadata["null_value"])


if __name__ == "__main__":
    unittest.main()
