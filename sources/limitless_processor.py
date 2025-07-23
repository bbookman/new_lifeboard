from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta, timezone
import logging
import re
from dataclasses import dataclass
import unicodedata

from sources.base import DataItem
from sources.chunking_processor import ChunkingProcessor

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


class AdvancedCleaningProcessor(BaseProcessor):
    """Advanced text cleaning and normalization for better embedding quality"""
    
    def __init__(self):
        """Initialize advanced cleaning patterns and filters"""
        # Basic patterns
        self.whitespace_pattern = re.compile(r'\s+')
        self.control_chars_pattern = re.compile(r'[\x00-\x1f\x7f-\x9f]')
        
        # Advanced normalization patterns
        self.url_pattern = re.compile(r'https?://[^\s]+|www\.[^\s]+')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'(\+?1[-.\s]?)?(\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})')
        self.repetitive_chars = re.compile(r'(.)\1{3,}')  # 4+ repeated chars
        self.excessive_punctuation = re.compile(r'[.!?]{2,}')
        self.unicode_quotes = re.compile(r'[""''`´]')
        self.html_tags = re.compile(r'<[^>]+>')
        self.markdown_links = re.compile(r'\[([^\]]+)\]\([^\)]+\)')
        self.timestamp_patterns = re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}')
        
        # Noise removal patterns
        self.filler_words = {
            'um', 'uh', 'er', 'ah', 'hmm', 'like', 'you know', 'i mean',
            'basically', 'literally', 'actually', 'totally', 'really'
        }
        self.transcription_artifacts = re.compile(r'\[inaudible\]|\[unclear\]|\[crosstalk\]|\[music\]|\[applause\]')
        
    def process(self, item: DataItem) -> DataItem:
        """Apply advanced text cleaning and normalization"""
        if not item.content:
            return item
        
        original_length = len(item.content)
        cleaned_content = item.content
        
        # Track cleaning operations
        cleaning_stats = {
            'unicode_normalized': False,
            'urls_replaced': 0,
            'emails_preserved': 0,
            'html_removed': False,
            'excessive_punct_cleaned': False,
            'repetitive_chars_reduced': False,
            'filler_words_removed': 0,
            'transcription_artifacts_removed': 0
        }
        
        # Unicode normalization for consistent character representation
        cleaned_content = unicodedata.normalize('NFKC', cleaned_content)
        cleaning_stats['unicode_normalized'] = True
        
        # Preserve important structured data while cleaning
        preserved_emails = self.email_pattern.findall(cleaned_content)
        cleaning_stats['emails_preserved'] = len(preserved_emails)
        
        # Replace URLs with placeholder to maintain context
        url_matches = self.url_pattern.findall(cleaned_content)
        if url_matches:
            cleaned_content = self.url_pattern.sub(' [URL] ', cleaned_content)
            cleaning_stats['urls_replaced'] = len(url_matches)
        
        # Remove HTML tags but preserve content
        if self.html_tags.search(cleaned_content):
            cleaned_content = self.html_tags.sub(' ', cleaned_content)
            cleaning_stats['html_removed'] = True
        
        # Clean markdown links, preserve link text
        cleaned_content = self.markdown_links.sub(r'\1', cleaned_content)
        
        # Normalize quotes to standard ASCII
        cleaned_content = self.unicode_quotes.sub('"', cleaned_content)
        
        # Reduce excessive punctuation
        if self.excessive_punctuation.search(cleaned_content):
            cleaned_content = self.excessive_punctuation.sub('.', cleaned_content)
            cleaning_stats['excessive_punct_cleaned'] = True
        
        # Reduce repetitive characters (but preserve intentional emphasis)
        if self.repetitive_chars.search(cleaned_content):
            cleaned_content = self.repetitive_chars.sub(r'\1\1', cleaned_content)
            cleaning_stats['repetitive_chars_reduced'] = True
        
        # Remove transcription artifacts
        transcription_matches = len(self.transcription_artifacts.findall(cleaned_content))
        if transcription_matches > 0:
            cleaned_content = self.transcription_artifacts.sub(' ', cleaned_content)
            cleaning_stats['transcription_artifacts_removed'] = transcription_matches
        
        # Remove excessive filler words (but preserve natural speech)
        words = cleaned_content.split()
        filtered_words = []
        filler_removed = 0
        
        for i, word in enumerate(words):
            word_lower = word.lower().strip('.,!?')
            # Only remove filler words if they appear frequently in context
            if (word_lower in self.filler_words and
                i > 0 and i < len(words) - 1 and
                filler_removed < 3):  # Limit removal to preserve natural flow
                filler_removed += 1
            else:
                filtered_words.append(word)
        
        cleaned_content = ' '.join(filtered_words)
        cleaning_stats['filler_words_removed'] = filler_removed
        
        # Remove control characters
        cleaned_content = self.control_chars_pattern.sub(' ', cleaned_content)
        
        # Normalize whitespace
        cleaned_content = self.whitespace_pattern.sub(' ', cleaned_content)
        
        # Strip leading/trailing whitespace
        cleaned_content = cleaned_content.strip()
        
        # Update item
        item.content = cleaned_content
        
        # Track processing in metadata
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        # Add detailed cleaning statistics
        cleaning_stats.update({
            'original_length': original_length,
            'cleaned_length': len(cleaned_content),
            'reduction_ratio': (original_length - len(cleaned_content)) / original_length if original_length > 0 else 0
        })
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'advanced_text_cleaning',
            'stats': cleaning_stats
        })
        
        # Store preserved structured data
        if preserved_emails:
            item.metadata['extracted_emails'] = preserved_emails
        
        return item


class NamedEntityExtractionProcessor(BaseProcessor):
    """Extract and tag named entities (people, places, organizations, topics)"""
    
    def __init__(self):
        """Initialize entity extraction patterns and databases"""
        # Person name patterns (common first/last name patterns)
        self.person_patterns = [
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]*)*(?:\s+[A-Z][a-z]+))\b'),  # First Last
            re.compile(r'\b(Mr|Mrs|Ms|Dr|Prof)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'),  # Title Name
            re.compile(r'\b([A-Z][a-z]+),\s*([A-Z][a-z]+)\b'),  # Last, First
        ]
        
        # Organization/company patterns
        self.organization_patterns = [
            re.compile(r'\b([A-Z][a-z]*(?:\s+[A-Z][a-z]*)*)\s+(Inc|LLC|Corp|Corporation|Company|Ltd|Limited)\b'),
            re.compile(r'\b(University\s+of\s+[A-Z][a-z]+|[A-Z][a-z]+\s+University)\b'),
            re.compile(r'\b([A-Z][a-z]*(?:\s+[A-Z][a-z]*)*)\s+(Hospital|Medical\s+Center|Clinic)\b'),
            re.compile(r'\b(Department\s+of\s+[A-Z][a-z]+)\b'),
        ]
        
        # Location patterns
        self.location_patterns = [
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+)\b'),  # City, State
            re.compile(r'\b(\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd))\b'),  # Address
            re.compile(r'\b([A-Z][a-z]+\s+(?:Street|Avenue|Road|Drive|Boulevard|Park|Square|Center))\b'),  # Street names
        ]
        
        # Email and contact patterns for person identification
        self.contact_patterns = [
            re.compile(r'\b([a-z]+\.?[a-z]+)@[a-z]+\.[a-z]+\b', re.IGNORECASE),  # Email username
            re.compile(r'\b(\+?1[-.\s]?)?(\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})\b'),  # Phone
        ]
        
        # Topic/keyword patterns
        self.topic_patterns = [
            re.compile(r'\b(AI|artificial\s+intelligence|machine\s+learning|deep\s+learning)\b', re.IGNORECASE),
            re.compile(r'\b(software|programming|development|coding|technology|tech)\b', re.IGNORECASE),
            re.compile(r'\b(business|finance|marketing|sales|strategy)\b', re.IGNORECASE),
            re.compile(r'\b(health|medical|healthcare|wellness|fitness)\b', re.IGNORECASE),
            re.compile(r'\b(education|learning|training|teaching|academic)\b', re.IGNORECASE),
        ]
        
        # Common words to filter out from person names
        self.common_words = {
            'and', 'the', 'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by', 'from',
            'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
            'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
            'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just'
        }
    
    def process(self, item: DataItem) -> DataItem:
        """Extract named entities from content"""
        if not item.content:
            return item
        
        entities = {
            'people': set(),
            'organizations': set(),
            'locations': set(),
            'topics': set(),
            'contacts': set()
        }
        
        content = item.content
        
        # Extract people
        for pattern in self.person_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle patterns with groups
                    name = ' '.join(match).strip()
                else:
                    name = match.strip()
                
                # Filter out common words and validate
                if (len(name.split()) <= 4 and
                    not any(word.lower() in self.common_words for word in name.split()) and
                    len(name) > 2):
                    entities['people'].add(name)
        
        # Extract organizations
        for pattern in self.organization_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    org = ' '.join(match).strip()
                else:
                    org = match.strip()
                entities['organizations'].add(org)
        
        # Extract locations
        for pattern in self.location_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    location = ', '.join(match).strip()
                else:
                    location = match.strip()
                entities['locations'].add(location)
        
        # Extract topics/keywords
        for pattern in self.topic_patterns:
            matches = pattern.findall(content)
            for match in matches:
                entities['topics'].add(match.lower())
        
        # Extract contact information
        for pattern in self.contact_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    contact = ''.join(match).strip()
                else:
                    contact = match.strip()
                if len(contact) > 3:  # Filter very short matches
                    entities['contacts'].add(contact)
        
        # Convert sets to sorted lists for consistent storage
        extracted_entities = {}
        for entity_type, entity_set in entities.items():
            if entity_set:
                extracted_entities[entity_type] = sorted(list(entity_set))
        
        # Store entities in metadata
        if extracted_entities:
            item.metadata['named_entities'] = extracted_entities
        
        # Enhanced speaker detection from conversations
        if 'speakers' in item.metadata:
            speakers = item.metadata.get('speakers', [])
            for speaker in speakers:
                if isinstance(speaker, str) and len(speaker.strip()) > 1:
                    entities['people'].add(speaker.strip())
        
        # Extract from original lifelog if available
        original_lifelog = item.metadata.get('original_lifelog', {})
        if original_lifelog:
            contents = original_lifelog.get('contents', [])
            for content_node in contents:
                speaker_name = content_node.get('speakerName')
                if speaker_name and speaker_name not in ['user', 'system']:
                    entities['people'].add(speaker_name)
        
        # Track processing
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        # Count entities found
        entity_counts = {k: len(v) for k, v in extracted_entities.items()}
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'named_entity_extraction',
            'entities_found': entity_counts
        })
        
        return item


class ContentTypeClassificationProcessor(BaseProcessor):
    """Classify content into types: questions, answers, summaries, facts, etc."""
    
    def __init__(self):
        """Initialize classification patterns"""
        # Question patterns
        self.question_patterns = [
            re.compile(r'^(what|who|where|when|why|how|which|whose|whom)\b', re.IGNORECASE),
            re.compile(r'^(is|are|can|could|would|should|will|did|do|does|have|has)\b.*\?', re.IGNORECASE),
            re.compile(r'\?$'),
            re.compile(r'^(tell me|explain|describe|help me understand)', re.IGNORECASE),
        ]
        
        # Answer patterns
        self.answer_patterns = [
            re.compile(r'^(yes|no|maybe|probably|definitely|certainly)', re.IGNORECASE),
            re.compile(r'^(the answer is|it is|that is|this is)', re.IGNORECASE),
            re.compile(r'^(because|since|due to|as a result)', re.IGNORECASE),
        ]
        
        # Summary patterns
        self.summary_patterns = [
            re.compile(r'^(in summary|to summarize|in conclusion|overall)', re.IGNORECASE),
            re.compile(r'^(the key points|main points|highlights)', re.IGNORECASE),
            re.compile(r'\b(summary|conclusion|recap|overview)\b', re.IGNORECASE),
        ]
        
        # Instruction patterns
        self.instruction_patterns = [
            re.compile(r'^(please|could you|would you|can you)', re.IGNORECASE),
            re.compile(r'^(do|don\'t|make sure|remember to)', re.IGNORECASE),
            re.compile(r'^(step \d+|first|second|third|finally)', re.IGNORECASE),
        ]
        
        # Opinion patterns
        self.opinion_patterns = [
            re.compile(r'\b(i think|i believe|in my opinion|personally)\b', re.IGNORECASE),
            re.compile(r'\b(seems like|appears to|looks like)\b', re.IGNORECASE),
            re.compile(r'\b(good|bad|great|terrible|amazing|awful)\b', re.IGNORECASE),
        ]
        
        # Fact patterns
        self.fact_patterns = [
            re.compile(r'^\d+[\.\)]\s+', re.IGNORECASE),  # Numbered list
            re.compile(r'^[-•*]\s+', re.IGNORECASE),  # Bullet points
            re.compile(r'\b(according to|research shows|studies indicate)\b', re.IGNORECASE),
            re.compile(r'\b(it is a fact|factually|statistically)\b', re.IGNORECASE),
        ]
    
    def process(self, item: DataItem) -> DataItem:
        """Classify content type and add to metadata"""
        if not item.content:
            return item
        
        content = item.content.strip()
        content_types = []
        confidence_scores = {}
        
        # Check for questions
        question_matches = sum(1 for pattern in self.question_patterns if pattern.search(content))
        if question_matches > 0:
            content_types.append('question')
            confidence_scores['question'] = min(question_matches / len(self.question_patterns), 1.0)
        
        # Check for answers
        answer_matches = sum(1 for pattern in self.answer_patterns if pattern.search(content))
        if answer_matches > 0:
            content_types.append('answer')
            confidence_scores['answer'] = min(answer_matches / len(self.answer_patterns), 1.0)
        
        # Check for summaries
        summary_matches = sum(1 for pattern in self.summary_patterns if pattern.search(content))
        if summary_matches > 0:
            content_types.append('summary')
            confidence_scores['summary'] = min(summary_matches / len(self.summary_patterns), 1.0)
        
        # Check for instructions
        instruction_matches = sum(1 for pattern in self.instruction_patterns if pattern.search(content))
        if instruction_matches > 0:
            content_types.append('instruction')
            confidence_scores['instruction'] = min(instruction_matches / len(self.instruction_patterns), 1.0)
        
        # Check for opinions
        opinion_matches = sum(1 for pattern in self.opinion_patterns if pattern.search(content))
        if opinion_matches > 0:
            content_types.append('opinion')
            confidence_scores['opinion'] = min(opinion_matches / len(self.opinion_patterns), 1.0)
        
        # Check for facts
        fact_matches = sum(1 for pattern in self.fact_patterns if pattern.search(content))
        if fact_matches > 0:
            content_types.append('fact')
            confidence_scores['fact'] = min(fact_matches / len(self.fact_patterns), 1.0)
        
        # Default classification based on length and structure
        if not content_types:
            if len(content.split()) < 10:
                content_types.append('brief_statement')
            elif len(content.split()) > 100:
                content_types.append('detailed_content')
            else:
                content_types.append('general_statement')
        
        # Additional classification based on metadata
        if 'speakers' in item.metadata and len(item.metadata.get('speakers', [])) > 1:
            content_types.append('conversation')
        
        # Store classification results
        item.metadata['content_classification'] = {
            'types': content_types,
            'confidence_scores': confidence_scores,
            'primary_type': content_types[0] if content_types else 'unknown'
        }
        
        # Track processing
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'content_type_classification',
            'types_identified': content_types
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


class TemporalContextProcessor(BaseProcessor):
    """Enrich content with temporal context and time-based relationships"""
    
    def __init__(self):
        """Initialize temporal analysis patterns"""
        # Time reference patterns
        self.time_patterns = [
            re.compile(r'\b(yesterday|today|tomorrow|now|currently|recently|lately)\b', re.IGNORECASE),
            re.compile(r'\b(this\s+(?:morning|afternoon|evening|week|month|year))\b', re.IGNORECASE),
            re.compile(r'\b(last\s+(?:week|month|year|night|time))\b', re.IGNORECASE),
            re.compile(r'\b(next\s+(?:week|month|year|time))\b', re.IGNORECASE),
            re.compile(r'\b(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)\b'),
            re.compile(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b'),
        ]
        
        # Activity timing patterns
        self.activity_patterns = [
            re.compile(r'\b(before|after|during|while|when|until|since)\b', re.IGNORECASE),
            re.compile(r'\b(started|finished|completed|began|ended)\b', re.IGNORECASE),
            re.compile(r'\b(meeting|appointment|call|event|session)\b', re.IGNORECASE),
        ]
        
        # Temporal frequency patterns
        self.frequency_patterns = [
            re.compile(r'\b(always|never|often|sometimes|rarely|usually|frequently)\b', re.IGNORECASE),
            re.compile(r'\b(daily|weekly|monthly|yearly|annually)\b', re.IGNORECASE),
            re.compile(r'\b(every\s+(?:day|week|month|year))\b', re.IGNORECASE),
        ]
    
    def process(self, item: DataItem) -> DataItem:
        """Add temporal context enrichment"""
        if not item.content:
            return item
        
        content = item.content
        temporal_context = {
            'time_references': [],
            'activity_timing': [],
            'frequency_indicators': [],
            'temporal_relationships': []
        }
        
        # Extract time references
        for pattern in self.time_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, str) and len(match.strip()) > 1:
                    temporal_context['time_references'].append(match.strip())
        
        # Extract activity timing
        for pattern in self.activity_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, str):
                    temporal_context['activity_timing'].append(match.lower())
        
        # Extract frequency indicators
        for pattern in self.frequency_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, str):
                    temporal_context['frequency_indicators'].append(match.lower())
        
        # Analyze temporal relationships based on item timestamps
        if item.created_at:
            created_time = item.created_at
            current_time = datetime.now(timezone.utc) if created_time.tzinfo else datetime.now()
            
            # Calculate time-based context
            time_diff = current_time - created_time
            
            if time_diff.days == 0:
                temporal_context['recency'] = 'today'
            elif time_diff.days == 1:
                temporal_context['recency'] = 'yesterday'
            elif time_diff.days <= 7:
                temporal_context['recency'] = 'this_week'
            elif time_diff.days <= 30:
                temporal_context['recency'] = 'this_month'
            elif time_diff.days <= 365:
                temporal_context['recency'] = 'this_year'
            else:
                temporal_context['recency'] = 'older'
            
            # Time of day context
            hour = created_time.hour
            if 5 <= hour < 12:
                temporal_context['time_of_day'] = 'morning'
            elif 12 <= hour < 17:
                temporal_context['time_of_day'] = 'afternoon'
            elif 17 <= hour < 21:
                temporal_context['time_of_day'] = 'evening'
            else:
                temporal_context['time_of_day'] = 'night'
            
            # Day of week context
            temporal_context['day_of_week'] = created_time.strftime('%A').lower()
            temporal_context['is_weekend'] = created_time.weekday() >= 5
        
        # Conversation-specific temporal analysis
        original_lifelog = item.metadata.get('original_lifelog', {})
        if original_lifelog:
            start_time_str = original_lifelog.get('startTime')
            end_time_str = original_lifelog.get('endTime')
            
            if start_time_str and end_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    duration_minutes = (end_time - start_time).total_seconds() / 60
                    
                    temporal_context['conversation_duration'] = duration_minutes
                    
                    if duration_minutes < 5:
                        temporal_context['conversation_length'] = 'brief'
                    elif duration_minutes < 30:
                        temporal_context['conversation_length'] = 'standard'
                    elif duration_minutes < 60:
                        temporal_context['conversation_length'] = 'extended'
                    else:
                        temporal_context['conversation_length'] = 'lengthy'
                        
                except (ValueError, TypeError):
                    pass
        
        # Remove duplicates and empty values
        for key, value in temporal_context.items():
            if isinstance(value, list):
                temporal_context[key] = sorted(list(set(value))) if value else []
        
        # Store temporal context
        if any(temporal_context.values()):
            item.metadata['temporal_context'] = temporal_context
        
        # Track processing
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'temporal_context_enrichment',
            'temporal_features': len([v for v in temporal_context.values() if v])
        })
        
        return item


class LimitlessProcessor:
    """Main processor for Limitless content with configurable pipeline"""
    
    def __init__(self,
                 enable_segmentation: bool = True,
                 enable_advanced_processing: bool = True,
                 enable_intelligent_chunking: bool = True,
                 chunking_config: Dict[str, Any] = None):
        self.processors: List[BaseProcessor] = []
        
        if enable_advanced_processing:
            # Advanced processing pipeline
            self.processors.append(AdvancedCleaningProcessor())
            self.processors.append(NamedEntityExtractionProcessor())
            self.processors.append(ContentTypeClassificationProcessor())
            self.processors.append(TemporalContextProcessor())
            self.processors.append(MetadataEnrichmentProcessor())
        else:
            # Basic processing pipeline (backward compatibility)
            self.processors.append(AdvancedCleaningProcessor())
            self.processors.append(MetadataEnrichmentProcessor())
        
        # Optional processors
        if enable_segmentation:
            self.processors.append(ConversationSegmentProcessor())
            
        # Intelligent chunking processor (replaces basic segmentation for embedding)
        if enable_intelligent_chunking:
            chunking_config = chunking_config or {}
            chunking_processor = ChunkingProcessor(
                enable_chunking=True,
                min_chunk_size=chunking_config.get('min_chunk_size', 50),
                max_chunk_size=chunking_config.get('max_chunk_size', 1000),
                target_chunk_size=chunking_config.get('target_chunk_size', 300)
            )
            self.processors.append(chunking_processor)
        
        # Always include deduplication
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