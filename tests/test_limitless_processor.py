"""
Tests for Limitless content processor
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from sources.limitless_processor import (
    LimitlessProcessor,
    BasicCleaningProcessor,
    MetadataEnrichmentProcessor, 
    ConversationSegmentProcessor,
    DeduplicationProcessor,
    ConversationSegment
)
from sources.base import DataItem


@pytest.fixture
def simple_data_item():
    """Simple data item for testing"""
    return DataItem(
        namespace="limitless",
        source_id="test_item",
        content="This is a test conversation with some content.",
        metadata={"title": "Test Item"},
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 15, 10, 5, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def complex_data_item():
    """Complex data item with conversation structure"""
    original_lifelog = {
        "id": "complex_item",
        "title": "Team Meeting",
        "startTime": "2024-01-15T10:00:00Z",
        "endTime": "2024-01-15T10:30:00Z",
        "contents": [
            {
                "type": "heading1",
                "content": "Team Meeting",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:30Z",
                "speakerName": None,
                "speakerIdentifier": None
            },
            {
                "type": "blockquote",
                "content": "Let's start with the project updates.",
                "startTime": "2024-01-15T10:01:00Z",
                "endTime": "2024-01-15T10:01:15Z",
                "speakerName": "Alice",
                "speakerIdentifier": None
            },
            {
                "type": "blockquote", 
                "content": "I've completed the backend API integration. The new endpoints are ready for testing.",
                "startTime": "2024-01-15T10:02:00Z",
                "endTime": "2024-01-15T10:02:30Z",
                "speakerName": "User",
                "speakerIdentifier": "user"
            },
            {
                "type": "blockquote",
                "content": "Great work! What about the frontend components?",
                "startTime": "2024-01-15T10:03:00Z",
                "endTime": "2024-01-15T10:03:10Z",
                "speakerName": "Alice",
                "speakerIdentifier": None
            }
        ]
    }
    
    return DataItem(
        namespace="limitless",
        source_id="complex_item",
        content="Team Meeting\nAlice: Let's start with the project updates.\nUser (You): I've completed the backend API integration. The new endpoints are ready for testing.\nAlice: Great work! What about the frontend components?",
        metadata={
            "title": "Team Meeting",
            "original_lifelog": original_lifelog,
            "speakers": ["Alice", "User"],
            "content_types": ["heading1", "blockquote"]
        },
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def messy_data_item():
    """Data item with messy content for cleaning tests"""
    return DataItem(
        namespace="limitless",
        source_id="messy_item",
        content="  This   has    lots\n\n\nof    whitespace\t\tand\x00control\x1fchars  ",
        metadata={"title": "Messy Item"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestBasicCleaningProcessor:
    """Test basic text cleaning"""
    
    def test_processor_initialization(self):
        """Test processor initialization"""
        processor = BasicCleaningProcessor()
        assert processor.get_processor_name() == "BasicCleaningProcessor"
    
    def test_whitespace_normalization(self, messy_data_item):
        """Test whitespace normalization"""
        processor = BasicCleaningProcessor()
        result = processor.process(messy_data_item)
        
        # Should normalize multiple spaces/tabs/newlines to single spaces
        assert "lots    of" not in result.content
        assert "lots of" in result.content
        assert result.content.startswith("This has")
        assert result.content.endswith("chars")
        assert not result.content.startswith(" ")  # No leading whitespace
        assert not result.content.endswith(" ")   # No trailing whitespace
    
    def test_control_character_removal(self, messy_data_item):
        """Test control character removal"""
        processor = BasicCleaningProcessor()
        result = processor.process(messy_data_item)
        
        # Should remove control characters
        assert '\x00' not in result.content
        assert '\x1f' not in result.content
    
    def test_empty_content_handling(self):
        """Test handling of empty content"""
        item = DataItem(
            namespace="test",
            source_id="empty",
            content="",
            metadata={}
        )
        
        processor = BasicCleaningProcessor()
        result = processor.process(item)
        
        assert result.content == ""
    
    def test_processing_history_tracking(self, simple_data_item):
        """Test that processing history is tracked"""
        processor = BasicCleaningProcessor()
        result = processor.process(simple_data_item)
        
        assert 'processing_history' in result.metadata
        assert len(result.metadata['processing_history']) == 1
        assert result.metadata['processing_history'][0]['processor'] == 'BasicCleaningProcessor'
        assert result.metadata['processing_history'][0]['changes'] == 'text_cleaning'


class TestMetadataEnrichmentProcessor:
    """Test metadata enrichment"""
    
    def test_content_statistics(self, simple_data_item):
        """Test content statistics calculation"""
        processor = MetadataEnrichmentProcessor()
        result = processor.process(simple_data_item)
        
        stats = result.metadata['content_stats']
        assert 'character_count' in stats
        assert 'word_count' in stats
        assert 'line_count' in stats
        assert 'paragraph_count' in stats
        
        assert stats['word_count'] > 0
        assert stats['character_count'] > 0
    
    def test_duration_calculation(self, simple_data_item):
        """Test duration calculation"""
        processor = MetadataEnrichmentProcessor()
        result = processor.process(simple_data_item)
        
        assert 'duration_seconds' in result.metadata
        assert 'duration_minutes' in result.metadata
        assert result.metadata['duration_seconds'] == 300.0  # 5 minutes
        assert result.metadata['duration_minutes'] == 5.0
    
    def test_conversation_metadata_extraction(self, complex_data_item):
        """Test conversation metadata extraction"""
        processor = MetadataEnrichmentProcessor()
        result = processor.process(complex_data_item)
        
        conv_metadata = result.metadata['conversation_metadata']
        
        assert 'total_content_nodes' in conv_metadata
        assert 'conversation_duration_minutes' in conv_metadata
        assert 'time_of_day' in conv_metadata
        assert 'is_business_hours' in conv_metadata
        assert 'speaker_count' in conv_metadata
        assert 'has_user_participation' in conv_metadata
        
        assert conv_metadata['total_content_nodes'] == 4
        assert conv_metadata['conversation_duration_minutes'] == 30.0
        assert conv_metadata['speaker_count'] == 2
        assert conv_metadata['has_user_participation'] is True
        assert conv_metadata['is_business_hours'] is True
    
    def test_time_analysis(self, complex_data_item):
        """Test time-based analysis"""
        processor = MetadataEnrichmentProcessor()
        result = processor.process(complex_data_item)
        
        conv_metadata = result.metadata['conversation_metadata']
        
        assert conv_metadata['time_of_day'] == 10  # 10 AM
        assert conv_metadata['day_of_week'] == 0   # Monday
        assert conv_metadata['is_business_hours'] is True
        assert conv_metadata['is_weekend'] is False
    
    def test_content_type_analysis(self, complex_data_item):
        """Test content type analysis"""
        processor = MetadataEnrichmentProcessor()
        result = processor.process(complex_data_item)
        
        conv_metadata = result.metadata['conversation_metadata']
        
        assert conv_metadata['content_type_diversity'] == 2  # heading1 and blockquote
        assert conv_metadata['has_headings'] is True
        assert conv_metadata['has_quotes'] is True


class TestConversationSegmentProcessor:
    """Test conversation segmentation"""
    
    def test_processor_initialization(self):
        """Test processor initialization"""
        processor = ConversationSegmentProcessor(
            max_segment_words=100,
            min_segment_words=25
        )
        assert processor.max_segment_words == 100
        assert processor.min_segment_words == 25
    
    def test_short_content_no_segmentation(self, simple_data_item):
        """Test that short content is not segmented"""
        processor = ConversationSegmentProcessor(max_segment_words=100)
        result = processor.process(simple_data_item)
        
        segmentation = result.metadata['segmentation']
        assert segmentation['is_segmented'] is False
        assert segmentation['total_segments'] == 1
        assert segmentation['segment_index'] == 0
    
    def test_long_content_segmentation(self):
        """Test that long content gets segmented"""
        # Create a long conversation
        long_content = " ".join(["This is a long conversation."] * 50)  # ~200 words
        
        long_item = DataItem(
            namespace="limitless",
            source_id="long_item",
            content=long_content,
            metadata={"title": "Long Item"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        processor = ConversationSegmentProcessor(max_segment_words=100)
        result = processor.process(long_item)
        
        segmentation = result.metadata['segmentation']
        assert segmentation['is_segmented'] is True
        assert segmentation['total_segments'] > 1
        assert 'segments' in segmentation
    
    def test_content_node_segmentation(self, complex_data_item):
        """Test segmentation based on content nodes"""
        processor = ConversationSegmentProcessor(
            max_segment_words=50,  # Force segmentation
            split_on_speaker_change=True
        )
        result = processor.process(complex_data_item)
        
        segmentation = result.metadata['segmentation']
        
        # Should create segments based on speaker changes
        if segmentation['is_segmented']:
            segments = segmentation['segments']
            assert len(segments) > 1
            
            # Check that segments have proper structure
            for segment in segments:
                assert 'content' in segment
                assert 'speaker' in segment
                assert 'segment_index' in segment
                assert 'word_count' in segment
    
    def test_speaker_change_segmentation(self):
        """Test segmentation on speaker changes"""
        # Create item with speaker changes
        original_lifelog = {
            "contents": [
                {
                    "type": "blockquote",
                    "content": "Hello there, how are you?",
                    "speakerName": "Alice",
                    "startTime": "2024-01-15T10:00:00Z"
                },
                {
                    "type": "blockquote", 
                    "content": "I'm doing well, thanks for asking!",
                    "speakerName": "Bob",
                    "startTime": "2024-01-15T10:00:30Z"
                },
                {
                    "type": "blockquote",
                    "content": "That's great to hear. How's the project going?",
                    "speakerName": "Alice", 
                    "startTime": "2024-01-15T10:01:00Z"
                }
            ]
        }
        
        item = DataItem(
            namespace="limitless",
            source_id="speaker_test",
            content="Speaker conversation",
            metadata={
                "original_lifelog": original_lifelog,
                "speakers": ["Alice", "Bob"]
            }
        )
        
        processor = ConversationSegmentProcessor(
            max_segment_words=200,  # High limit
            split_on_speaker_change=True
        )
        result = processor.process(item)
        
        segmentation = result.metadata['segmentation']
        
        if segmentation['is_segmented']:
            # Should create segments based on speaker changes
            assert len(segmentation['segments']) >= 2
    
    def test_time_gap_segmentation(self):
        """Test segmentation on time gaps"""
        # Create item with time gaps
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        original_lifelog = {
            "contents": [
                {
                    "type": "blockquote",
                    "content": "First part of conversation",
                    "speakerName": "Alice",
                    "startTime": base_time.isoformat(),
                    "endTime": (base_time + timedelta(seconds=30)).isoformat()
                },
                {
                    "type": "blockquote",
                    "content": "Second part after long gap",
                    "speakerName": "Alice",
                    "startTime": (base_time + timedelta(minutes=10)).isoformat(),  # 10 min gap
                    "endTime": (base_time + timedelta(minutes=10, seconds=30)).isoformat()
                }
            ]
        }
        
        item = DataItem(
            namespace="limitless",
            source_id="time_gap_test",
            content="Time gap conversation",
            metadata={
                "original_lifelog": original_lifelog,
                "speakers": ["Alice"]
            }
        )
        
        processor = ConversationSegmentProcessor(
            max_segment_words=200,
            split_on_time_gap_minutes=5.0  # 5 minute threshold
        )
        result = processor.process(item)
        
        segmentation = result.metadata['segmentation']
        
        if segmentation['is_segmented']:
            # Should create segments based on time gap
            assert len(segmentation['segments']) >= 2


class TestDeduplicationProcessor:
    """Test deduplication processor"""
    
    def test_deduplication_metadata(self, simple_data_item):
        """Test that deduplication metadata is added"""
        processor = DeduplicationProcessor()
        result = processor.process(simple_data_item)
        
        dedup_metadata = result.metadata['deduplication']
        assert dedup_metadata['processed'] is True
        assert 'processor_version' in dedup_metadata
        assert 'content_hash' in dedup_metadata
        assert dedup_metadata['content_hash'] is not None
    
    def test_empty_content_hash(self):
        """Test hash handling for empty content"""
        item = DataItem(
            namespace="test",
            source_id="empty",
            content="",
            metadata={}
        )
        
        processor = DeduplicationProcessor()
        result = processor.process(item)
        
        assert result.metadata['deduplication']['content_hash'] is not None


class TestLimitlessProcessor:
    """Test main processor pipeline"""
    
    def test_processor_initialization(self):
        """Test processor initialization"""
        processor = LimitlessProcessor()
        
        # Should have default processors
        pipeline_info = processor.get_pipeline_info()
        assert pipeline_info['processor_count'] > 0
        assert 'BasicCleaningProcessor' in pipeline_info['processors']
        assert 'MetadataEnrichmentProcessor' in pipeline_info['processors']
    
    def test_processor_pipeline(self, simple_data_item):
        """Test full processing pipeline"""
        processor = LimitlessProcessor()
        result = processor.process(simple_data_item)
        
        # Should have metadata from multiple processors
        assert 'content_stats' in result.metadata  # From MetadataEnrichmentProcessor
        assert 'deduplication' in result.metadata  # From DeduplicationProcessor
        assert 'processing_history' in result.metadata  # From all processors
        
        # Processing history should show multiple processors
        history = result.metadata['processing_history']
        assert len(history) > 1
        
        processor_names = [entry['processor'] for entry in history]
        assert 'BasicCleaningProcessor' in processor_names
        assert 'MetadataEnrichmentProcessor' in processor_names
    
    def test_add_custom_processor(self, simple_data_item):
        """Test adding custom processor"""
        processor = LimitlessProcessor()
        
        # Add a custom processor
        custom_processor = BasicCleaningProcessor()  # Using existing one as example
        processor.add_processor(custom_processor)
        
        pipeline_info = processor.get_pipeline_info()
        processor_names = pipeline_info['processors']
        
        # Should have two BasicCleaningProcessor instances
        assert processor_names.count('BasicCleaningProcessor') == 2
    
    def test_remove_processor(self):
        """Test removing processor from pipeline"""
        processor = LimitlessProcessor()
        
        # Remove deduplication processor
        processor.remove_processor(DeduplicationProcessor)
        
        pipeline_info = processor.get_pipeline_info()
        assert 'DeduplicationProcessor' not in pipeline_info['processors']
    
    def test_segmentation_disabled(self, simple_data_item):
        """Test processor with segmentation disabled"""
        processor = LimitlessProcessor(enable_segmentation=False)
        result = processor.process(simple_data_item)
        
        # Should not have segmentation metadata
        assert 'segmentation' not in result.metadata
        
        pipeline_info = processor.get_pipeline_info()
        assert 'ConversationSegmentProcessor' not in pipeline_info['processors']
    
    def test_error_handling(self, simple_data_item):
        """Test error handling in processor pipeline"""
        processor = LimitlessProcessor()
        
        # Create a mock processor that raises an error
        class ErrorProcessor(BasicCleaningProcessor):
            def process(self, item):
                raise Exception("Test error")
        
        processor.add_processor(ErrorProcessor())
        
        # Should handle error gracefully and continue processing
        result = processor.process(simple_data_item)
        
        # Should still have metadata from other processors
        assert 'content_stats' in result.metadata
    
    def test_complex_item_processing(self, complex_data_item):
        """Test processing complex conversation item"""
        processor = LimitlessProcessor(enable_segmentation=True)
        result = processor.process(complex_data_item)
        
        # Should have all expected metadata
        assert 'content_stats' in result.metadata
        assert 'conversation_metadata' in result.metadata
        assert 'segmentation' in result.metadata
        assert 'deduplication' in result.metadata
        assert 'processing_history' in result.metadata
        
        # Conversation metadata should be rich
        conv_metadata = result.metadata['conversation_metadata']
        assert conv_metadata['speaker_count'] == 2
        assert conv_metadata['has_user_participation'] is True
        assert conv_metadata['conversation_duration_minutes'] == 30.0
        
        # Should have proper processing history
        history = result.metadata['processing_history']
        assert len(history) >= 3  # At least 3 processors ran