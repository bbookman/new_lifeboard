#!/usr/bin/env python3
"""
Test suite for intelligent chunking system

Tests chunking functionality including:
- Conversation turn detection and chunking
- Document section chunking
- Content type detection
- Chunk quality scoring
- Edge cases and error handling
"""

import unittest
import sys
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.chunking import (
    IntelligentChunker, ConversationChunker, DocumentChunker,
    TextChunk, ChunkType
)


class TestTextChunk(unittest.TestCase):
    """Test cases for TextChunk class"""
    
    def test_chunk_creation(self):
        """Test basic chunk creation"""
        chunk = TextChunk(
            content="This is a test chunk with reasonable length.",
            chunk_type=ChunkType.CONVERSATION_TURN,
            start_position=0,
            end_position=43,
            metadata={'speaker': 'John'}
        )
        
        self.assertEqual(chunk.content, "This is a test chunk with reasonable length.")
        self.assertEqual(chunk.chunk_type, ChunkType.CONVERSATION_TURN)
        self.assertEqual(chunk.start_position, 0)
        self.assertEqual(chunk.end_position, 43)
        self.assertEqual(chunk.metadata['speaker'], 'John')
        self.assertGreater(chunk.quality_score, 0.5)
    
    def test_quality_score_calculation(self):
        """Test quality score calculation for different chunk types"""
        # High quality chunk (optimal length, complete sentence, conversation turn)
        high_quality = TextChunk(
            content="John said this is a well-formed conversation turn with good length and proper punctuation.",
            chunk_type=ChunkType.CONVERSATION_TURN,
            start_position=0,
            end_position=90,
            metadata={'speaker': 'John'}
        )
        self.assertGreater(high_quality.quality_score, 0.8)
        
        # Low quality chunk (too short, no punctuation)
        low_quality = TextChunk(
            content="Short",
            chunk_type=ChunkType.SINGLE_SENTENCE,
            start_position=0,
            end_position=5,
            metadata={}
        )
        self.assertLess(low_quality.quality_score, 0.5)
        
        # Empty chunk
        empty_chunk = TextChunk(
            content="",
            chunk_type=ChunkType.PARAGRAPH,
            start_position=0,
            end_position=0,
            metadata={}
        )
        self.assertEqual(empty_chunk.quality_score, 0.0)
    
    def test_quality_score_length_optimization(self):
        """Test that quality score optimizes for target length"""
        content_base = "This is a sentence. "
        
        # Test different lengths
        test_cases = [
            (content_base * 2, "short"),  # ~40 chars
            (content_base * 5, "optimal"),  # ~100 chars
            (content_base * 15, "good"),  # ~300 chars
            (content_base * 25, "target"),  # ~500 chars
            (content_base * 40, "long"),  # ~800 chars
            (content_base * 100, "very_long"),  # ~2000 chars
        ]
        
        scores = {}
        for content, label in test_cases:
            chunk = TextChunk(
                content=content,
                chunk_type=ChunkType.PARAGRAPH,
                start_position=0,
                end_position=len(content),
                metadata={}
            )
            scores[label] = chunk.quality_score
        
        # Optimal and target should have highest scores
        self.assertGreater(scores["optimal"], scores["short"])
        self.assertGreater(scores["target"], scores["very_long"])


class TestConversationChunker(unittest.TestCase):
    """Test cases for ConversationChunker"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.chunker = ConversationChunker(
            min_chunk_size=20,
            max_chunk_size=200,
            target_chunk_size=100
        )
    
    def test_speaker_turn_detection(self):
        """Test detection of speaker turns in conversation"""
        conversation = """John: Hello there, how are you doing today?
        
Jane: I'm doing well, thank you for asking. How about you?

John: Pretty good, just working on some interesting projects.

Jane: That sounds great! What kind of projects?"""
        
        chunks = self.chunker.chunk_conversation(conversation)
        
        self.assertGreater(len(chunks), 0)
        
        # Should detect speaker turns
        speaker_chunks = [c for c in chunks if c.chunk_type == ChunkType.CONVERSATION_TURN]
        self.assertGreater(len(speaker_chunks), 0)
        
        # Check for speaker metadata
        speakers_found = set()
        for chunk in speaker_chunks:
            if 'speaker' in chunk.metadata:
                speakers_found.add(chunk.metadata['speaker'])
        
        self.assertIn('John', speakers_found)
        self.assertIn('Jane', speakers_found)
    
    def test_conversation_segment_chunking(self):
        """Test chunking by conversation segments"""
        # Long conversation that should be segmented
        long_conversation = """Person A: This is the start of a long conversation that will need to be broken down into multiple segments.

Person B: Yes, I agree that this conversation is getting quite long and detailed.

Person A: We should probably break this up into logical segments based on the natural flow.

---

Person B: Now we're moving to a new topic in the conversation.

Person A: This is a completely different subject matter that deserves its own segment.

Person B: The chunking algorithm should detect this natural boundary."""
        
        chunks = self.chunker.chunk_conversation(long_conversation)
        self.assertGreater(len(chunks), 1)
        
        # Should create reasonable chunk sizes
        for chunk in chunks:
            self.assertGreaterEqual(len(chunk.content), self.chunker.min_chunk_size)
            self.assertLessEqual(len(chunk.content), self.chunker.max_chunk_size)
    
    def test_paragraph_fallback_chunking(self):
        """Test fallback to paragraph-based chunking"""
        # Content without clear speaker structure
        text = """This is a paragraph of text that doesn't have clear speaker indicators or conversation structure.

This is another paragraph that continues the discussion but lacks the typical conversation markers.

Here's a third paragraph that should be chunked appropriately based on paragraph boundaries rather than speaker turns."""
        
        chunks = self.chunker.chunk_conversation(text)
        self.assertGreater(len(chunks), 0)
        
        # Should use paragraph chunking as fallback
        paragraph_chunks = [c for c in chunks if c.chunk_type == ChunkType.PARAGRAPH]
        self.assertGreater(len(paragraph_chunks), 0)
    
    def test_long_turn_splitting(self):
        """Test splitting of very long speaker turns"""
        long_turn = "John: " + "This is a very long speaker turn. " * 20  # ~700 characters
        
        chunks = self.chunker.chunk_conversation(long_turn)
        
        # Should split long turn into multiple chunks
        if len(long_turn) > self.chunker.max_chunk_size:
            self.assertGreater(len(chunks), 1)
        
        # All chunks should have speaker metadata
        for chunk in chunks:
            if chunk.chunk_type == ChunkType.CONVERSATION_TURN:
                self.assertIn('speaker', chunk.metadata)
                self.assertEqual(chunk.metadata['speaker'], 'John')
    
    def test_empty_content_handling(self):
        """Test handling of empty or whitespace-only content"""
        empty_cases = ["", "   ", "\n\n", None]
        
        for content in empty_cases:
            chunks = self.chunker.chunk_conversation(content or "")
            self.assertEqual(len(chunks), 0)
    
    def test_chunk_optimization(self):
        """Test chunk size optimization"""
        # Create content that should trigger optimization
        short_chunks_content = "A: Hi.\n\nB: Hello.\n\nA: How are you?\n\nB: Good."
        
        chunks = self.chunker.chunk_conversation(short_chunks_content)
        
        # Should merge very small chunks
        total_length = sum(len(chunk.content) for chunk in chunks)
        self.assertGreater(total_length, 0)
        
        # All chunks should meet minimum size requirement after optimization
        for chunk in chunks:
            self.assertGreaterEqual(len(chunk.content), self.chunker.min_chunk_size)


class TestDocumentChunker(unittest.TestCase):
    """Test cases for DocumentChunker"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.chunker = DocumentChunker(
            min_chunk_size=50,
            max_chunk_size=300,
            target_chunk_size=150
        )
    
    def test_section_based_chunking(self):
        """Test chunking by document sections"""
        document = """# Introduction

This is the introduction section of the document that explains the main concepts.

## Background

The background section provides important context and historical information about the topic.

## Methodology

This section describes the methods and approaches used in the research.

### Data Collection

Details about how data was collected and processed.

### Analysis

Information about the analysis techniques employed."""
        
        chunks = self.chunker.chunk_document(document)
        self.assertGreater(len(chunks), 0)
        
        # Should detect section structure
        section_chunks = [c for c in chunks if c.chunk_type == ChunkType.DOCUMENT_SECTION]
        self.assertGreater(len(section_chunks), 0)
    
    def test_paragraph_based_chunking(self):
        """Test fallback to paragraph-based chunking"""
        document = """This is the first paragraph of a document that doesn't have clear section headers or structure.

This is the second paragraph that continues the discussion with more detailed information about the topic.

Here's a third paragraph that adds additional context and examples to support the main points being made.

The fourth paragraph concludes the discussion and summarizes the key takeaways."""
        
        chunks = self.chunker.chunk_document(document)
        self.assertGreater(len(chunks), 0)
        
        # Should use paragraph chunking
        paragraph_chunks = [c for c in chunks if c.chunk_type == ChunkType.PARAGRAPH]
        self.assertGreater(len(paragraph_chunks), 0)
    
    def test_large_section_splitting(self):
        """Test splitting of large document sections"""
        large_section = "# Large Section\n\n" + "This is a sentence in a large section. " * 50
        
        chunks = self.chunker.chunk_document(large_section)
        
        # Should split large section if it exceeds max size
        if len(large_section) > self.chunker.max_chunk_size:
            self.assertGreater(len(chunks), 1)
        
        # All chunks should be within size limits
        for chunk in chunks:
            self.assertLessEqual(len(chunk.content), self.chunker.max_chunk_size)


class TestIntelligentChunker(unittest.TestCase):
    """Test cases for IntelligentChunker main class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.chunker = IntelligentChunker()
    
    def test_content_type_detection(self):
        """Test automatic content type detection"""
        # Conversation content
        conversation = "John: Hello there!\nJane: Hi John, how are you?\nJohn: I'm doing well, thanks."
        detected_type = self.chunker._detect_content_type(conversation)
        self.assertEqual(detected_type, 'conversation')
        
        # Document content
        document = "# Introduction\n\nThis is a document with sections.\n\n## Background\n\nMore content here."
        detected_type = self.chunker._detect_content_type(document)
        self.assertEqual(detected_type, 'document')
        
        # Mixed/unclear content - should default to conversation
        mixed = "Some text that doesn't have clear indicators of type."
        detected_type = self.chunker._detect_content_type(mixed)
        self.assertEqual(detected_type, 'conversation')
    
    def test_chunk_content_with_type_hint(self):
        """Test chunking with explicit content type hint"""
        content = "This is some content that could be either conversation or document."
        
        # Test with conversation hint
        conv_chunks = self.chunker.chunk_content(content, content_type='conversation')
        self.assertGreater(len(conv_chunks), 0)
        self.assertEqual(conv_chunks[0].metadata['detected_content_type'], 'conversation')
        
        # Test with document hint
        doc_chunks = self.chunker.chunk_content(content, content_type='document')
        self.assertGreater(len(doc_chunks), 0)
        self.assertEqual(doc_chunks[0].metadata['detected_content_type'], 'document')
    
    def test_chunking_stats(self):
        """Test chunking statistics calculation"""
        content = "John: Hello there!\nJane: Hi John, how are you doing today?\nJohn: I'm doing well, thanks for asking."
        chunks = self.chunker.chunk_content(content)
        
        stats = self.chunker.get_chunking_stats(chunks)
        
        self.assertIn('total_chunks', stats)
        self.assertIn('total_characters', stats)
        self.assertIn('avg_chunk_size', stats)
        self.assertIn('avg_quality_score', stats)
        self.assertIn('chunk_types', stats)
        
        self.assertEqual(stats['total_chunks'], len(chunks))
        self.assertGreater(stats['total_characters'], 0)
        self.assertGreater(stats['avg_quality_score'], 0)
    
    def test_empty_content_handling(self):
        """Test handling of empty content"""
        empty_cases = ["", "   ", "\n\n\n", None]
        
        for content in empty_cases:
            chunks = self.chunker.chunk_content(content or "")
            self.assertEqual(len(chunks), 0)
    
    def test_metadata_propagation(self):
        """Test that metadata is properly propagated to chunks"""
        content = "John: Hello there!\nJane: Hi John!"
        metadata = {
            'source': 'test',
            'timestamp': '2023-01-01T00:00:00Z',
            'custom_field': 'custom_value'
        }
        
        chunks = self.chunker.chunk_content(content, metadata=metadata)
        
        for chunk in chunks:
            # Should have base metadata
            self.assertIn('source', chunk.metadata)
            self.assertIn('timestamp', chunk.metadata)
            self.assertIn('custom_field', chunk.metadata)
            
            # Should have chunking metadata
            self.assertIn('chunk_index', chunk.metadata)
            self.assertIn('total_chunks', chunk.metadata)
            self.assertIn('created_at', chunk.metadata)
            self.assertIn('chunking_strategy', chunk.metadata)
    
    def test_chunk_quality_distribution(self):
        """Test that chunker produces reasonable quality distribution"""
        # Good quality content
        good_content = """John: Hello Jane, how has your day been going?

Jane: It's been quite productive, thank you for asking. I managed to complete several important tasks.

John: That's wonderful to hear. I've been working on some interesting projects myself.

Jane: I'd love to hear about them sometime. Perhaps we could discuss them over coffee?"""
        
        chunks = self.chunker.chunk_content(good_content)
        quality_scores = [chunk.quality_score for chunk in chunks]
        
        # Most chunks should have reasonable quality
        high_quality_count = sum(1 for score in quality_scores if score > 0.6)
        self.assertGreater(high_quality_count, len(chunks) * 0.5)  # At least 50% should be high quality
        
        # Average quality should be reasonable
        avg_quality = sum(quality_scores) / len(quality_scores)
        self.assertGreater(avg_quality, 0.5)


class TestChunkingEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.chunker = IntelligentChunker()
    
    def test_very_long_content(self):
        """Test handling of very long content"""
        long_content = "This is a sentence. " * 1000  # ~20,000 characters
        
        chunks = self.chunker.chunk_content(long_content)
        
        # Should create multiple chunks
        self.assertGreater(len(chunks), 5)
        
        # No chunk should be excessively large
        for chunk in chunks:
            self.assertLess(len(chunk.content), 2000)
    
    def test_special_characters_handling(self):
        """Test handling of special characters and unicode"""
        special_content = """Speaker 1: Hello! How are you? 😊

Speaker 2: I'm doing well, thanks! 👍 What about you?

Speaker 1: Great! I love these emojis: 🎉🎊🎈"""
        
        chunks = self.chunker.chunk_content(special_content)
        
        # Should handle special characters without errors
        self.assertGreater(len(chunks), 0)
        
        # Content should be preserved correctly
        combined_content = " ".join(chunk.content for chunk in chunks)
        self.assertIn("😊", combined_content)
        self.assertIn("👍", combined_content)
    
    def test_malformed_speakers(self):
        """Test handling of malformed speaker patterns"""
        malformed = """John said: This doesn't follow the standard pattern.
        
        SPEAKER_WITHOUT_COLON This line doesn't have proper formatting
        
        : This line starts with a colon
        
        Multiple: Colons: In: One: Line: How does this work?"""
        
        chunks = self.chunker.chunk_content(malformed)
        
        # Should handle malformed input gracefully
        self.assertGreater(len(chunks), 0)
        
        # Should not crash or produce empty chunks
        for chunk in chunks:
            self.assertGreater(len(chunk.content.strip()), 0)
    
    def test_mixed_content_types(self):
        """Test handling of mixed conversation and document content"""
        mixed_content = """# Document Header

This is document-style content with a header.

John: But then we have a conversation mixed in.

Jane: Yes, this is an interesting mix of content types.

## Another Document Section

More document content here.

John: And back to conversation again."""
        
        chunks = self.chunker.chunk_content(mixed_content)
        
        # Should handle mixed content without errors
        self.assertGreater(len(chunks), 0)
        
        # Should maintain reasonable quality
        avg_quality = sum(chunk.quality_score for chunk in chunks) / len(chunks)
        self.assertGreater(avg_quality, 0.4)


if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestTextChunk))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationChunker))
    suite.addTests(loader.loadTestsFromTestCase(TestDocumentChunker))
    suite.addTests(loader.loadTestsFromTestCase(TestIntelligentChunker))
    suite.addTests(loader.loadTestsFromTestCase(TestChunkingEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"CHUNKING TESTS SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)