from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import re
from dataclasses import dataclass

from sources.base import DataItem

logger = logging.getLogger(__name__)


@dataclass
class ConversationSegment:
    """A segment of a conversation for improved searchability"""
    content: str
    speaker: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    segment_index: int
    total_segments: int
    metadata: Dict[str, Any]


class BaseProcessor:
    """Base class for content processors"""
    
    def process(self, item: DataItem) -> DataItem:
        """Process a data item"""
        return item
    
    def get_processor_name(self) -> str:
        """Get the processor name for metadata tracking"""
        return self.__class__.__name__


class BasicCleaningProcessor(BaseProcessor):
    """Basic text cleaning and normalization"""
    
    def __init__(self):
        # Patterns for cleaning
        self.whitespace_pattern = re.compile(r'\s+')
        self.control_chars_pattern = re.compile(r'[\x00-\x1f\x7f-\x9f]')
    
    def process(self, item: DataItem) -> DataItem:
        """Clean and normalize text content"""
        if not item.content:
            return item
        
        # Remove control characters
        cleaned_content = self.control_chars_pattern.sub(' ', item.content)
        
        # Normalize whitespace
        cleaned_content = self.whitespace_pattern.sub(' ', cleaned_content)
        
        # Strip leading/trailing whitespace
        cleaned_content = cleaned_content.strip()
        
        # Update item
        item.content = cleaned_content
        
        # Track processing in metadata
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'text_cleaning'
        })
        
        return item


class MetadataEnrichmentProcessor(BaseProcessor):
    """Enrich item metadata with additional computed information"""
    
    def process(self, item: DataItem) -> DataItem:
        """Add enriched metadata"""
        enriched_metadata = self._compute_metadata(item)
        
        # Merge with existing metadata
        item.metadata.update(enriched_metadata)
        
        # Track processing
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'metadata_enrichment'
        })
        
        return item
    
    def _compute_metadata(self, item: DataItem) -> Dict[str, Any]:
        """Compute additional metadata"""
        metadata = {}
        
        # Basic content statistics
        content = item.content or ""
        metadata['content_stats'] = {
            'character_count': len(content),
            'word_count': len(content.split()) if content else 0,
            'line_count': len(content.splitlines()) if content else 0,
            'paragraph_count': len([p for p in content.split('\n\n') if p.strip()]) if content else 0
        }
        
        # Time-based metadata
        if item.created_at and item.updated_at:
            duration = item.updated_at - item.created_at
            metadata['duration_seconds'] = duration.total_seconds()
            metadata['duration_minutes'] = duration.total_seconds() / 60
        
        # Extract original lifelog metadata if available
        original_lifelog = item.metadata.get('original_lifelog', {})
        if original_lifelog:
            metadata['conversation_metadata'] = self._extract_conversation_metadata(original_lifelog, item)
        
        return metadata
    
    def _extract_conversation_metadata(self, lifelog: Dict[str, Any], item: DataItem) -> Dict[str, Any]:
        """Extract conversation-specific metadata"""
        metadata = {}
        
        # Conversation structure
        contents = lifelog.get('contents', [])
        metadata['total_content_nodes'] = len(contents)
        
        # Time analysis
        start_time_str = lifelog.get('startTime')
        end_time_str = lifelog.get('endTime')
        
        if start_time_str and end_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                
                metadata['conversation_duration_minutes'] = (end_time - start_time).total_seconds() / 60
                metadata['time_of_day'] = start_time.hour
                metadata['day_of_week'] = start_time.weekday()  # 0=Monday, 6=Sunday
                metadata['is_business_hours'] = 9 <= start_time.hour <= 17
                metadata['is_weekend'] = start_time.weekday() >= 5
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing conversation times: {e}")
        
        # Speaker analysis
        speakers = item.metadata.get('speakers', [])
        metadata['speaker_count'] = len(speakers)
        metadata['has_user_participation'] = any(
            content.get('speakerIdentifier') == 'user' 
            for content in contents
        )
        
        # Content type analysis
        content_types = item.metadata.get('content_types', [])
        metadata['content_type_diversity'] = len(set(content_types))
        metadata['has_headings'] = any(
            ctype.startswith('heading') for ctype in content_types
        )
        metadata['has_quotes'] = 'blockquote' in content_types
        
        return metadata


class ConversationSegmentProcessor(BaseProcessor):
    """Split long conversations into smaller searchable segments"""
    
    def __init__(self, 
                 max_segment_words: int = 200,
                 min_segment_words: int = 50,
                 split_on_speaker_change: bool = True,
                 split_on_time_gap_minutes: float = 5.0):
        self.max_segment_words = max_segment_words
        self.min_segment_words = min_segment_words
        self.split_on_speaker_change = split_on_speaker_change
        self.split_on_time_gap_minutes = split_on_time_gap_minutes
    
    def process(self, item: DataItem) -> DataItem:
        """Process item and potentially create segments"""
        # Only segment if content is long enough
        word_count = len(item.content.split()) if item.content else 0
        
        if word_count < self.max_segment_words:
            # Add segmentation metadata even for non-segmented items
            item.metadata['segmentation'] = {
                'is_segmented': False,
                'total_segments': 1,
                'segment_index': 0,
                'word_count': word_count
            }
            return item
        
        # Create segments
        segments = self._create_segments(item)
        
        if len(segments) <= 1:
            # Not worth segmenting
            item.metadata['segmentation'] = {
                'is_segmented': False,
                'total_segments': 1,
                'segment_index': 0,
                'word_count': word_count
            }
            return item
        
        # For now, return the original item with segmentation metadata
        # In a more advanced implementation, we might create multiple DataItems
        item.metadata['segmentation'] = {
            'is_segmented': True,
            'total_segments': len(segments),
            'segment_index': 0,  # This is the full conversation
            'segments_available': True,
            'segments': [
                {
                    'content': seg.content,
                    'speaker': seg.speaker,
                    'start_time': seg.start_time.isoformat() if seg.start_time else None,
                    'end_time': seg.end_time.isoformat() if seg.end_time else None,
                    'segment_index': seg.segment_index,
                    'word_count': len(seg.content.split())
                }
                for seg in segments
            ]
        }
        
        # Track processing
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': f'conversation_segmentation_{len(segments)}_segments'
        })
        
        return item
    
    def _create_segments(self, item: DataItem) -> List[ConversationSegment]:
        """Create conversation segments from item"""
        original_lifelog = item.metadata.get('original_lifelog', {})
        contents = original_lifelog.get('contents', [])
        
        if not contents:
            # Fall back to simple text segmentation
            return self._create_text_segments(item)
        
        # Use content nodes for intelligent segmentation
        return self._create_content_node_segments(item, contents)
    
    def _create_text_segments(self, item: DataItem) -> List[ConversationSegment]:
        """Create segments from plain text"""
        if not item.content:
            return []
        
        words = item.content.split()
        segments = []
        current_segment_words = []
        
        for i, word in enumerate(words):
            current_segment_words.append(word)
            
            # Check if we should create a segment
            if (len(current_segment_words) >= self.max_segment_words or 
                i == len(words) - 1):
                
                if len(current_segment_words) >= self.min_segment_words or i == len(words) - 1:
                    segment_content = ' '.join(current_segment_words)
                    
                    segment = ConversationSegment(
                        content=segment_content,
                        speaker=None,
                        start_time=item.created_at,
                        end_time=item.updated_at,
                        segment_index=len(segments),
                        total_segments=0,  # Will be updated later
                        metadata={}
                    )
                    segments.append(segment)
                    current_segment_words = []
        
        # Update total segments count
        for segment in segments:
            segment.total_segments = len(segments)
        
        return segments
    
    def _create_content_node_segments(self, item: DataItem, contents: List[Dict]) -> List[ConversationSegment]:
        """Create segments based on content nodes"""
        segments = []
        current_segment_content = []
        current_speaker = None
        current_start_time = None
        current_end_time = None
        last_time = None
        
        for node in contents:
            node_content = node.get('content', '').strip()
            if not node_content:
                continue
            
            node_speaker = node.get('speakerName')
            node_start_time = self._parse_time(node.get('startTime'))
            node_end_time = self._parse_time(node.get('endTime'))
            
            # Check if we should start a new segment
            should_split = False
            
            # Split on speaker change
            if (self.split_on_speaker_change and 
                current_speaker is not None and 
                node_speaker != current_speaker):
                should_split = True
            
            # Split on time gap
            if (last_time and node_start_time and 
                (node_start_time - last_time).total_seconds() > (self.split_on_time_gap_minutes * 60)):
                should_split = True
            
            # Split on word count
            current_word_count = sum(len(content.split()) for content in current_segment_content)
            node_word_count = len(node_content.split())
            
            if current_word_count + node_word_count > self.max_segment_words and current_segment_content:
                should_split = True
            
            # Create segment if needed
            if should_split and current_segment_content:
                segment = self._create_segment_from_content(
                    current_segment_content,
                    current_speaker,
                    current_start_time,
                    current_end_time,
                    len(segments)
                )
                segments.append(segment)
                current_segment_content = []
                current_start_time = None
            
            # Add current node to segment
            if node_speaker:
                speaker_prefix = f"{node_speaker}: " if node_speaker != current_speaker else ""
                if node.get('speakerIdentifier') == 'user':
                    speaker_prefix = f"{node_speaker} (You): "
                current_segment_content.append(f"{speaker_prefix}{node_content}")
            else:
                current_segment_content.append(node_content)
            
            # Update tracking variables
            current_speaker = node_speaker
            if current_start_time is None:
                current_start_time = node_start_time
            current_end_time = node_end_time
            last_time = node_end_time or node_start_time
        
        # Add final segment
        if current_segment_content:
            segment = self._create_segment_from_content(
                current_segment_content,
                current_speaker,
                current_start_time,
                current_end_time,
                len(segments)
            )
            segments.append(segment)
        
        # Update total segments count
        for segment in segments:
            segment.total_segments = len(segments)
        
        return segments
    
    def _create_segment_from_content(self, 
                                   content_parts: List[str], 
                                   speaker: Optional[str],
                                   start_time: Optional[datetime],
                                   end_time: Optional[datetime],
                                   index: int) -> ConversationSegment:
        """Create a conversation segment from content parts"""
        return ConversationSegment(
            content='\n'.join(content_parts),
            speaker=speaker,
            start_time=start_time,
            end_time=end_time,
            segment_index=index,
            total_segments=0,  # Will be updated later
            metadata={}
        )
    
    def _parse_time(self, time_str: Optional[str]) -> Optional[datetime]:
        """Parse time string to datetime"""
        if not time_str:
            return None
        
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None


class DeduplicationProcessor(BaseProcessor):
    """Remove or mark duplicate content (placeholder for future implementation)"""
    
    def process(self, item: DataItem) -> DataItem:
        """Process item for deduplication"""
        # For now, just add metadata indicating this processor was run
        # In the future, this could:
        # - Generate content hashes
        # - Compare with existing items
        # - Mark duplicates or similar items
        
        item.metadata['deduplication'] = {
            'processed': True,
            'processor_version': '1.0',
            'content_hash': hash(item.content) if item.content else None
        }
        
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'deduplication_analysis'
        })
        
        return item


class LimitlessProcessor:
    """Main processor for Limitless content with configurable pipeline"""
    
    def __init__(self, enable_segmentation: bool = True):
        self.processors: List[BaseProcessor] = []
        
        # Always include basic processors
        self.processors.append(BasicCleaningProcessor())
        self.processors.append(MetadataEnrichmentProcessor())
        
        # Optional processors
        if enable_segmentation:
            self.processors.append(ConversationSegmentProcessor())
        
        # Placeholder for future processors
        self.processors.append(DeduplicationProcessor())
    
    def add_processor(self, processor: BaseProcessor):
        """Add a custom processor to the pipeline"""
        self.processors.append(processor)
    
    def remove_processor(self, processor_class: type):
        """Remove a processor from the pipeline"""
        self.processors = [p for p in self.processors if not isinstance(p, processor_class)]
    
    def process(self, item: DataItem) -> DataItem:
        """Process item through the entire pipeline"""
        processed_item = item
        
        for processor in self.processors:
            try:
                processed_item = processor.process(processed_item)
            except Exception as e:
                logger.error(f"Error in processor {processor.get_processor_name()}: {e}")
                # Continue with other processors
                continue
        
        return processed_item
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about the current processing pipeline"""
        return {
            'processor_count': len(self.processors),
            'processors': [p.get_processor_name() for p in self.processors],
            'pipeline_version': '2.0'
        }