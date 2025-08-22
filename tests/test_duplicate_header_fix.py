#!/usr/bin/env python3
"""
Test suite for the duplicate header fix in markdown generation.

This test verifies that the systematic fix for duplicate headers works correctly.
"""

import unittest

from sources.limitless_processor import MarkdownProcessor


class TestDuplicateHeaderFix(unittest.TestCase):
    """Test cases for duplicate header prevention fix"""

    def setUp(self):
        self.processor = MarkdownProcessor()

    def test_remove_duplicate_headers_basic(self):
        """Test basic duplicate header removal"""
        content = "# Sample Meeting\n\nThis is the content.\n\n# Sample Meeting\n\nMore content."
        target_header = "# Sample Meeting"

        result = self.processor._remove_duplicate_headers(content, target_header)

        # Should have removed the duplicate header
        self.assertEqual(result.count("# Sample Meeting"), 0)
        self.assertIn("This is the content.", result)
        self.assertIn("More content.", result)

    def test_remove_duplicate_headers_with_empty_lines(self):
        """Test duplicate header removal with empty lines after headers"""
        content = "# Sample Meeting\n\n\nThis is content.\n\n# Sample Meeting\n\n\nMore content."
        target_header = "# Sample Meeting"

        result = self.processor._remove_duplicate_headers(content, target_header)

        # Should have removed both duplicate headers and their following empty lines
        self.assertEqual(result.count("# Sample Meeting"), 0)
        self.assertIn("This is content.", result)
        self.assertIn("More content.", result)

    def test_remove_duplicate_headers_no_duplicates(self):
        """Test that content without duplicates is unchanged"""
        content = "This is some content without headers.\n\nMore content here."
        target_header = "# Sample Meeting"

        result = self.processor._remove_duplicate_headers(content, target_header)

        # Should be unchanged
        self.assertEqual(result, content)

    def test_generate_cleaned_markdown_prevents_duplication(self):
        """Test that the main method prevents header duplication"""
        # Create a lifelog where the markdown content already contains the title as a header
        lifelog_with_duplicate = {
            "title": "Sample Meeting",
            "start_time": "2024-01-15T10:00:00Z",
            "markdown": "# Sample Meeting\n\nThis content already has the title as a header.",
        }

        result = self.processor._generate_cleaned_markdown(lifelog_with_duplicate)

        # Should only have ONE instance of the title header
        self.assertEqual(result.count("# Sample Meeting"), 1)
        self.assertIn("*10:00 AM*", result)
        self.assertIn("This content already has the title as a header.", result)

    def test_generate_cleaned_markdown_with_different_header(self):
        """Test that non-duplicate headers are preserved"""
        lifelog_with_different_header = {
            "title": "Sample Meeting",
            "start_time": "2024-01-15T10:00:00Z",
            "markdown": "# Different Header\n\nThis content has a different header.",
        }

        result = self.processor._generate_cleaned_markdown(lifelog_with_different_header)

        # Should have both the title header and the different header
        self.assertEqual(result.count("# Sample Meeting"), 1)
        self.assertEqual(result.count("# Different Header"), 1)
        self.assertIn("*10:00 AM*", result)
        self.assertIn("This content has a different header.", result)

    def test_generate_cleaned_markdown_multiple_duplicates(self):
        """Test handling of multiple duplicate headers in content"""
        lifelog_with_multiple_duplicates = {
            "title": "Important Meeting",
            "start_time": "2024-01-15T14:00:00Z",
            "markdown": "# Important Meeting\n\nFirst section.\n\n# Important Meeting\n\nSecond section with duplicate.\n\n# Different Header\n\nThird section.",
        }

        result = self.processor._generate_cleaned_markdown(lifelog_with_multiple_duplicates)

        # Should only have ONE instance of "Important Meeting" header (our added one)
        self.assertEqual(result.count("# Important Meeting"), 1)
        # Should preserve the different header
        self.assertEqual(result.count("# Different Header"), 1)
        self.assertIn("*02:00 PM*", result)
        self.assertIn("First section.", result)
        self.assertIn("Second section with duplicate.", result)
        self.assertIn("Third section.", result)

    def test_edge_case_empty_content(self):
        """Test edge case with empty content"""
        result = self.processor._remove_duplicate_headers("", "# Sample Meeting")
        self.assertEqual(result, "")

    def test_edge_case_empty_header(self):
        """Test edge case with empty header"""
        content = "Some content here."
        result = self.processor._remove_duplicate_headers(content, "")
        self.assertEqual(result, content)


if __name__ == "__main__":
    print("Testing duplicate header fix...")
    unittest.main(verbosity=2)
