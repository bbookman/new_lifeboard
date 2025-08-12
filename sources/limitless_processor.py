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
        
        # Track processing in metadata (handle both old and new structure)
        if 'processed_response' in item.metadata:
            # New two-key structure
            processed = item.metadata['processed_response']
            if 'processing_history' not in processed:
                processed['processing_history'] = []
            processed['processing_history'].append({
                'processor': self.get_processor_name(),
                'timestamp': datetime.now().isoformat(),
                'changes': 'text_cleaning'
            })
        else:
            # Legacy structure fallback
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
        
        # Handle both old and new metadata structure
        if 'processed_response' in item.metadata:
            # New two-key structure - merge into processed_response
            processed = item.metadata['processed_response']
            processed.update(enriched_metadata)
            
            # Track processing
            if 'processing_history' not in processed:
                processed['processing_history'] = []
            processed['processing_history'].append({
                'processor': self.get_processor_name(),
                'timestamp': datetime.now().isoformat(),
                'changes': 'metadata_enrichment'
            })
        else:
            # Legacy structure fallback
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
        
        # Extract original lifelog metadata if available (handle both structures)
        if 'processed_response' in item.metadata:
            # New two-key structure
            original_lifelog = item.metadata.get('original_response', {})
        else:
            # Legacy structure
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
            segmentation_data = {
                'is_segmented': False,
                'total_segments': 1,
                'segment_index': 0,
                'word_count': word_count
            }
            
            if 'processed_response' in item.metadata:
                # New two-key structure
                item.metadata['processed_response']['segmentation'] = segmentation_data
            else:
                # Legacy structure
                item.metadata['segmentation'] = segmentation_data
            return item
        
        # Create segments
        segments = self._create_segments(item)
        
        if len(segments) <= 1:
            # Not worth segmenting
            segmentation_data = {
                'is_segmented': False,
                'total_segments': 1,
                'segment_index': 0,
                'word_count': word_count
            }
            
            if 'processed_response' in item.metadata:
                # New two-key structure
                item.metadata['processed_response']['segmentation'] = segmentation_data
            else:
                # Legacy structure
                item.metadata['segmentation'] = segmentation_data
            return item
        
        # For now, return the original item with segmentation metadata
        # In a more advanced implementation, we might create multiple DataItems
        segmentation_data = {
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
        
        if 'processed_response' in item.metadata:
            # New two-key structure
            item.metadata['processed_response']['segmentation'] = segmentation_data
        else:
            # Legacy structure
            item.metadata['segmentation'] = segmentation_data
        
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


class MarkdownProcessor(BaseProcessor):
    """Generate cleaned markdown from original lifelog data for display purposes"""
    
    def process(self, item) -> DataItem:
        """Process item to generate cleaned markdown"""
        # Handle both DataItem objects and raw dictionaries for testing
        if hasattr(item, 'metadata'):
            # DataItem object
            cleaned_markdown = self._generate_cleaned_markdown(item)
            
            if cleaned_markdown:
                # Handle both old and new metadata structure
                if 'processed_response' in item.metadata:
                    # New two-key structure
                    processed = item.metadata['processed_response']
                    processed['cleaned_markdown'] = cleaned_markdown
                    
                    # Track processing
                    if 'processing_history' not in processed:
                        processed['processing_history'] = []
                    processed['processing_history'].append({
                        'processor': self.get_processor_name(),
                        'timestamp': datetime.now().isoformat(),
                        'changes': 'cleaned_markdown_generation'
                    })
                else:
                    # Legacy structure
                    item.metadata['cleaned_markdown'] = cleaned_markdown
                    
                    # Track processing
                    if 'processing_history' not in item.metadata:
                        item.metadata['processing_history'] = []
                    item.metadata['processing_history'].append({
                        'processor': self.get_processor_name(),
                        'timestamp': datetime.now().isoformat(),
                        'changes': 'cleaned_markdown_generation'
                    })
            
            return item
        else:
            # For testing with raw dictionaries - create a mock DataItem-like object
            from sources.base import DataItem
            mock_item = DataItem(
                namespace='test',
                source_id='test',
                content='',
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={'original_lifelog': item}
            )
            processed_item = self.process(mock_item)
            # Return the result in a format the test expects
            return processed_item
    
    def _generate_cleaned_markdown(self, item) -> Optional[str]:
        """Generate cleaned markdown from original lifelog data, using deduplicated content when available"""
        # Handle both DataItem objects and raw dictionaries for backward compatibility
        processed_response = None
        if hasattr(item, 'metadata'):
            # DataItem object - handle both old and new structure
            if 'processed_response' in item.metadata:
                # New two-key structure
                original_lifelog = item.metadata.get('original_response', {})
                processed_response = item.metadata.get('processed_response', {})
            else:
                # Legacy structure
                original_lifelog = item.metadata.get('original_lifelog', {})
                # Check for legacy semantic processing results
                if item.metadata.get('display_conversation'):
                    processed_response = {
                        'display_conversation': item.metadata.get('display_conversation'),
                        'semantic_metadata': item.metadata.get('semantic_metadata', {})
                    }
        else:
            # Raw dictionary - treat as lifelog data directly
            original_lifelog = item
        
        if not original_lifelog:
            return None
        
        markdown_parts = []
        
        # Extract and format content first, using deduplicated data when available
        markdown_content = self._extract_markdown_content(original_lifelog, processed_response)
        
        # Add title if available, with fallback - but avoid duplication
        title = original_lifelog.get('title')
        title_header = None
        if title:
            title_header = f"# {title}"
        elif not title and original_lifelog.get('contents'):
            # Only add fallback title if there's content
            title_header = "# Untitled Entry"
        
        # Check if the extracted content already contains the same title header
        if title_header and markdown_content:
            markdown_content = self._remove_duplicate_headers(markdown_content, title_header)
        
        # Add the title header if we have one
        if title_header:
            markdown_parts.append(title_header)
        
        # Add the deduplicated content
        if markdown_content:
            markdown_parts.append(markdown_content)
        
        # Add timestamp if available - check both startTime and start_time fields
        start_time = original_lifelog.get('startTime') or original_lifelog.get('start_time')
        if start_time and markdown_parts:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                timestamp_info = f"*{dt.strftime('%I:%M %p')}*"
                # Insert timestamp after the title (first element) if it exists
                if len(markdown_parts) > 0:
                    # Check if first part is a title (starts with #)
                    if markdown_parts[0].startswith('#'):
                        # Insert timestamp after title
                        markdown_parts.insert(1, timestamp_info)
                    else:
                        # Insert timestamp at the beginning
                        markdown_parts.insert(0, timestamp_info)
                else:
                    markdown_parts.append(timestamp_info)
            except (ValueError, TypeError):
                pass
        
        return "\n\n".join(markdown_parts) if markdown_parts else None
    
    def _remove_duplicate_headers(self, content: str, target_header: str) -> str:
        """Remove duplicate instances of a header from content"""
        if not content or not target_header:
            return content
        
        lines = content.split('\n')
        filtered_lines = []
        target_header_clean = target_header.strip()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # If we find a matching header
            if line == target_header_clean:
                # Skip this line and any immediately following empty lines
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                continue
            else:
                filtered_lines.append(lines[i])
                i += 1
        
        return '\n'.join(filtered_lines)
    
    def _extract_markdown_content(self, lifelog: Dict[str, Any], processed_response: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Extract markdown content from lifelog data, preferring deduplicated content when available"""
        
        # First priority: Use deduplicated content if available and semantic processing is completed
        if processed_response:
            semantic_metadata = processed_response.get('semantic_metadata', {})
            if semantic_metadata.get('processed') and processed_response.get('display_conversation'):
                logger.debug("Using deduplicated content from semantic processing for markdown generation")
                return self._construct_markdown_from_contents(processed_response['display_conversation'])
        
        # Second priority: Try to get markdown directly from lifelog
        if lifelog.get('markdown'):
            return lifelog['markdown']
        
        # Third priority: Try processed_content field
        if lifelog.get('processed_content'):
            return lifelog['processed_content']
        
        # Fourth priority: Construct from original structured content nodes
        contents = lifelog.get('contents', [])
        if contents:
            logger.debug("Using original content (non-deduplicated) for markdown generation")
            return self._construct_markdown_from_contents(contents)
        
        # Final fallback: Try raw_data if available
        raw_data = lifelog.get('raw_data')
        if raw_data:
            try:
                import json
                parsed_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                contents = parsed_data.get('contents', [])
                if contents:
                    return self._construct_markdown_from_contents(contents)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return None
    
    def _construct_markdown_from_contents(self, contents: List[Dict[str, Any]]) -> str:
        """Construct markdown from content nodes, handling both original and deduplicated content"""
        markdown_parts = []
        
        for node in contents:
            node_content = node.get('content', '') or ''
            node_content = node_content.strip()
            if not node_content:
                continue
            
            # Handle different content types
            node_type = node.get('type', '')
            speaker_name = node.get('speakerName')
            speaker_id = node.get('speakerIdentifier')
            
            # Check if this is a deduplicated node (from semantic processing)
            is_deduplicated = node.get('is_deduplicated', False)
            hidden_variations = node.get('hidden_variations', 0)
            
            if node_type == 'blockquote' and speaker_name:
                # Format as quoted speech
                speaker_label = f"{speaker_name} (You)" if speaker_id == 'user' else speaker_name
                formatted_content = f"> **{speaker_label}:** {node_content}"
                
                # Add deduplication indicator if this represents multiple similar lines
                if is_deduplicated and hidden_variations > 0:
                    formatted_content += f" *(represents {hidden_variations + 1} similar statements)*"
                
                markdown_parts.append(formatted_content)
                
            elif node_type.startswith('heading'):
                # Format as appropriate heading level
                level = int(node_type.replace('heading', '') or '2')
                heading_prefix = '#' * min(level, 6)
                markdown_parts.append(f"{heading_prefix} {node_content}")
                
            else:
                # Regular paragraph content
                if speaker_name and node_type != 'paragraph':
                    speaker_label = f"{speaker_name} (You)" if speaker_id == 'user' else speaker_name
                    formatted_content = f"**{speaker_label}:** {node_content}"
                    
                    # Add deduplication indicator if applicable
                    if is_deduplicated and hidden_variations > 0:
                        formatted_content += f" *(represents {hidden_variations + 1} similar statements)*"
                    
                    markdown_parts.append(formatted_content)
                else:
                    markdown_parts.append(node_content)
        
        return '\n\n'.join(markdown_parts) if markdown_parts else ''


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
    """
    Main processor for Limitless content with two-key metadata architecture
    
    Generates clean separation between original API response and processed data:
    - original_response: Complete unmodified Limitless API response
    - processed_response: All processing results including semantic deduplication
    """
    
    def __init__(self, 
                 enable_segmentation: bool = True, 
                 enable_markdown_generation: bool = True,  # Enable for basic markdown in processed_response
                 enable_semantic_deduplication: bool = True,
                 embedding_service = None):
        self.processors: List[BaseProcessor] = []
        self.enable_semantic_deduplication = enable_semantic_deduplication
        
        # Always include basic processors for processed_response
        self.processors.append(BasicCleaningProcessor())
        self.processors.append(MetadataEnrichmentProcessor())
        
        # Optional processors for processed_response
        if enable_segmentation:
            self.processors.append(ConversationSegmentProcessor())
        
        # Markdown processor for basic cleaned markdown in processed_response
        if enable_markdown_generation:
            self.processors.append(MarkdownProcessor())
        
        # Semantic deduplication processor (for cross-conversation analysis)
        if enable_semantic_deduplication:
            from sources.semantic_deduplication_processor import SemanticDeduplicationProcessor
            self.semantic_processor = SemanticDeduplicationProcessor(embedding_service=embedding_service)
        else:
            # Fallback to basic deduplication
            self.processors.append(DeduplicationProcessor())
    
    def add_processor(self, processor: BaseProcessor):
        """Add a custom processor to the pipeline"""
        self.processors.append(processor)
    
    def remove_processor(self, processor_class: type):
        """Remove a processor from the pipeline"""
        self.processors = [p for p in self.processors if not isinstance(p, processor_class)]
    
    def process(self, item: DataItem) -> DataItem:
        """Process item with two-key metadata architecture"""
        # Extract original Limitless API response
        original_lifelog = item.metadata.get('original_lifelog', {})
        
        # Create clean two-key metadata structure
        item.metadata = {
            "original_response": original_lifelog,
            "processed_response": {
                "processing_history": [],
                "semantic_metadata": {"processed": False},
                "display_conversation": [],
                "semantic_clusters": {}
            }
        }
        
        # Apply basic processing to processed_response
        self._apply_basic_processing(item)
        
        # Process through standard processors (they will update processed_response)
        for processor in self.processors:
            try:
                processed_item = processor.process(item)
                item = processed_item  # Update reference
            except Exception as e:
                logger.error(f"Error in processor {processor.get_processor_name()}: {e}")
                # Continue with other processors
                continue
        
        # Note: Semantic deduplication requires batch processing for full effectiveness
        # Single items will be processed without cross-conversation deduplication
        # For optimal semantic deduplication, use process_batch() instead
        if self.enable_semantic_deduplication:
            try:
                processed_item = self.semantic_processor.process(item)
                item = processed_item  # Update reference
            except Exception as e:
                logger.debug(f"Semantic deduplication skipped for single item: {e}")
                # Continue without semantic deduplication for single items
        
        return item
    
    async def process_batch(self, items: List[DataItem]) -> List[DataItem]:
        """
        Process multiple items through the pipeline, enabling cross-item analysis
        This is the preferred method for semantic deduplication
        """
        processed_items = []
        
        # Process each item through standard processors first
        for item in items:
            processed_item = item
            for processor in self.processors:
                try:
                    processed_item = processor.process(processed_item)
                except Exception as e:
                    logger.error(f"Error in processor {processor.get_processor_name()}: {e}")
                    continue
            processed_items.append(processed_item)
        
        # Apply semantic deduplication across all items
        if self.enable_semantic_deduplication and processed_items:
            try:
                processed_items = await self.semantic_processor.process_batch(processed_items)
            except Exception as e:
                logger.error(f"Error in batch semantic deduplication: {e}")
                # Return items without semantic deduplication on error
        
        return processed_items
    
    def _apply_basic_processing(self, item: DataItem):
        """Apply basic processing like metadata extraction to processed_response"""
        processed = item.metadata['processed_response']
        original = item.metadata['original_response']
        
        # Extract basic metadata from original response
        processed['title'] = original.get('title', 'Untitled')
        processed['start_time'] = original.get('startTime')
        processed['end_time'] = original.get('endTime')
        processed['is_starred'] = original.get('isStarred', False)
        processed['updated_at'] = original.get('updatedAt')
        
        # Extract speakers from content nodes
        processed['speakers'] = self._extract_speakers(original)
        processed['content_types'] = self._extract_content_types(original)
        processed['has_markdown'] = bool(original.get('markdown'))
        processed['node_count'] = len(original.get('contents', []))
        
        # Track processing
        processed['processing_history'].append({
            'processor': 'TwoKeyMetadataProcessor',
            'timestamp': datetime.now().isoformat(),
            'changes': 'two_key_structure_creation'
        })
    
    def _extract_speakers(self, original_lifelog: Dict[str, Any]) -> List[str]:
        """Extract unique speakers from conversation content"""
        speakers = set()
        contents = original_lifelog.get('contents', [])
        
        for node in contents:
            speaker_name = node.get('speakerName')
            if speaker_name:
                speakers.add(speaker_name)
        
        return sorted(list(speakers))
    
    def _extract_content_types(self, original_lifelog: Dict[str, Any]) -> List[str]:
        """Extract content types from conversation nodes"""
        content_types = set()
        contents = original_lifelog.get('contents', [])
        
        for node in contents:
            node_type = node.get('type')
            if node_type:
                content_types.add(node_type)
        
        return sorted(list(content_types))
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about the current processing pipeline"""
        processors_list = [p.get_processor_name() for p in self.processors]
        if self.enable_semantic_deduplication:
            processors_list.append('SemanticDeduplicationProcessor')
        
        return {
            'processor_count': len(processors_list),
            'processors': processors_list,
            'pipeline_version': '3.0',  # Updated for semantic deduplication
            'semantic_deduplication_enabled': self.enable_semantic_deduplication,
            'supports_batch_processing': True
        }