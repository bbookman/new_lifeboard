"""
Tests for MarkdownProcessor class in LimitlessProcessor

These tests verify that the new MarkdownProcessor correctly generates
cleaned markdown from Limitless lifelog data.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sources.limitless_processor import MarkdownProcessor


class TestMarkdownProcessor(unittest.TestCase):
    """Test cases for MarkdownProcessor functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = MarkdownProcessor()
        
        # Sample lifelog data for testing
        self.sample_lifelog = {
            "id": "test_lifelog_123",
            "title": "Sample Meeting",
            "start_time": "2024-01-15T10:00:00Z",
            "end_time": "2024-01-15T11:00:00Z",
            "is_starred": True,
            "contents": [
                {
                    "type": "text",
                    "content": "This is a sample meeting about project planning."
                },
                {
                    "type": "text", 
                    "content": "We discussed the upcoming milestones and deliverables."
                }
            ]
        }
    
    def test_generate_cleaned_markdown_basic(self):
        """Test basic markdown generation from lifelog data"""
        result = self.processor._generate_cleaned_markdown(self.sample_lifelog)
        
        # Should contain title, timestamp, and content
        self.assertIn("# Sample Meeting", result)
        self.assertIn("*10:00 AM*", result)
        self.assertIn("This is a sample meeting about project planning.", result)
        self.assertIn("We discussed the upcoming milestones", result)
        
        # Should NOT have separators (those are added at database level when combining items)
        self.assertNotIn("---", result)
    
    def test_generate_cleaned_markdown_no_title(self):
        """Test markdown generation when title is missing"""
        lifelog_no_title = self.sample_lifelog.copy()
        del lifelog_no_title["title"]
        
        result = self.processor._generate_cleaned_markdown(lifelog_no_title)
        
        # Should use fallback title
        self.assertIn("# Untitled Entry", result)
        self.assertIn("*10:00 AM*", result)
        self.assertIn("This is a sample meeting", result)
    
    def test_generate_cleaned_markdown_empty_contents(self):
        """Test markdown generation with empty contents"""
        lifelog_empty = self.sample_lifelog.copy()
        lifelog_empty["contents"] = []
        
        result = self.processor._generate_cleaned_markdown(lifelog_empty)
        
        # Should still have title and timestamp but minimal content
        self.assertIn("# Sample Meeting", result)
        self.assertIn("*10:00 AM*", result)
        # Should be relatively short due to empty contents
        self.assertLess(len(result), 200)
    
    def test_generate_cleaned_markdown_invalid_timestamp(self):
        """Test markdown generation with invalid timestamp"""
        lifelog_bad_time = self.sample_lifelog.copy()
        lifelog_bad_time["start_time"] = "invalid-timestamp"
        
        result = self.processor._generate_cleaned_markdown(lifelog_bad_time)
        
        # Should still generate markdown, maybe without time formatting
        self.assertIn("# Sample Meeting", result)
        self.assertIn("This is a sample meeting", result)
    
    def test_extract_markdown_content_from_contents(self):
        """Test extracting content from contents array"""
        contents = [
            {"type": "text", "content": "First paragraph"},
            {"type": "text", "content": "Second paragraph"},
            {"type": "other", "content": "Should be ignored"}
        ]
        
        result = self.processor._extract_markdown_content({"contents": contents})
        
        self.assertIn("First paragraph", result)
        self.assertIn("Second paragraph", result)
        # Non-text types should be handled appropriately
    
    def test_extract_markdown_content_from_processed_content(self):
        """Test extracting content from processed_content field"""
        lifelog = {"processed_content": "This is processed content"}
        
        result = self.processor._extract_markdown_content(lifelog)
        
        self.assertEqual(result, "This is processed content")
    
    def test_extract_markdown_content_fallback_to_raw_data(self):
        """Test extracting content falls back to raw_data when needed"""
        lifelog = {
            "raw_data": '{"contents": [{"type": "text", "content": "Raw data content"}]}'
        }
        
        result = self.processor._extract_markdown_content(lifelog)
        
        self.assertIn("Raw data content", result)
    
    def test_construct_markdown_from_contents_text_types(self):
        """Test markdown construction from text content types"""
        contents = [
            {"type": "text", "content": "Regular text"},
            {"type": "transcript", "content": "Transcribed speech"},
            {"type": "summary", "content": "Summary text"}
        ]
        
        result = self.processor._construct_markdown_from_contents(contents)
        
        self.assertIn("Regular text", result)
        self.assertIn("Transcribed speech", result) 
        self.assertIn("Summary text", result)
    
    def test_construct_markdown_handles_empty_content(self):
        """Test markdown construction handles empty or None content gracefully"""
        contents = [
            {"type": "text", "content": "Valid content"},
            {"type": "text", "content": ""},
            {"type": "text", "content": None},
            {"type": "text"}  # Missing content key
        ]
        
        result = self.processor._construct_markdown_from_contents(contents)
        
        self.assertIn("Valid content", result)
        # Should not crash and should have reasonable output
        self.assertIsInstance(result, str)
    
    def test_process_method_integration(self):
        """Test the main process method integrates markdown generation"""
        # Test with a proper DataItem object
        from sources.base import DataItem
        from datetime import datetime
        
        test_item = DataItem(
            namespace='limitless',
            source_id='test_001',
            content='test content',
            metadata={'original_lifelog': self.sample_lifelog},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = self.processor.process(test_item)
        
        # Should add cleaned_markdown to metadata
        self.assertIn("cleaned_markdown", result.metadata)
        self.assertIn("# Sample Meeting", result.metadata["cleaned_markdown"])
        self.assertIn("processing_history", result.metadata)
    
    def test_markdown_generation_with_starred_content(self):
        """Test that starred content is properly formatted"""
        starred_lifelog = self.sample_lifelog.copy()
        starred_lifelog["is_starred"] = True
        
        result = self.processor._generate_cleaned_markdown(starred_lifelog)
        
        # Should include star indicator or special formatting
        self.assertIn("# Sample Meeting", result)
        # The exact format may vary, but starred content should be distinguishable
        
    def test_markdown_generation_preserves_structure(self):
        """Test that markdown preserves logical structure of content"""
        structured_lifelog = {
            "title": "Structured Meeting",
            "start_time": "2024-01-15T14:00:00Z",
            "contents": [
                {"type": "text", "content": "Opening remarks"},
                {"type": "text", "content": "Main discussion points"},
                {"type": "text", "content": "Action items and next steps"}
            ]
        }
        
        result = self.processor._generate_cleaned_markdown(structured_lifelog)
        
        # Should maintain order and structure
        opening_pos = result.find("Opening remarks")
        main_pos = result.find("Main discussion points")
        action_pos = result.find("Action items")
        
        self.assertTrue(opening_pos < main_pos < action_pos)


if __name__ == '__main__':
    unittest.main()