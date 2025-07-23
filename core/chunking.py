"""
Intelligent Chunking Strategy for Conversations

Advanced chunking system that creates segment-aware embeddings by:
- Detecting natural conversation boundaries
- Preserving semantic coherence within chunks
- Handling different content types intelligently
- Maintaining speaker context and turn boundaries
- Optimizing chunk size for embedding quality
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import Counter
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class ChunkType(Enum):
    """Types of chunks for different content"""
    CONVERSATION_TURN = "conversation_turn"
    CONVERSATION_SEGMENT = "conversation_segment"
    PARAGRAPH = "paragraph"
    SENTENCE_GROUP = "sentence_group"
    SINGLE_SENTENCE = "single_sentence"
    DOCUMENT_SECTION = "document_section"


@dataclass
class TextChunk:
    """Represents a semantically coherent text chunk"""
    content: str
    chunk_type: ChunkType
    start_position: int
    end_position: int
    metadata: Dict[str, Any]
    quality_score: float = 0.0
    
    def __post_init__(self):
        """Calculate quality score based on chunk properties"""
        self.quality_score = self._calculate_quality_score()
        
    def _calculate_quality_score(self) -> float:
        """Calculate quality score for this chunk"""
        if not self.content or not self.content.strip():
            return 0.0
        
        content = self.content.strip()
        length = len(content)
        
        # Base score from length (optimal range: 100-800 characters)
        if 100 <= length <= 800:
            length_score = 1.0
        elif length < 100:
            length_score = length / 100.0
        else:
            length_score = max(0.3, 800 / length)
        
        # Semantic completeness score
        completeness_score = 1.0
        if not content.endswith(('.', '!', '?', ':', ';')):
            completeness_score *= 0.8
        
        # Content type bonus
        type_bonus = {
            ChunkType.CONVERSATION_TURN: 1.0,
            ChunkType.CONVERSATION_SEGMENT: 0.95,
            ChunkType.PARAGRAPH: 0.9,
            ChunkType.SENTENCE_GROUP: 0.85,
            ChunkType.SINGLE_SENTENCE: 0.7,
            ChunkType.DOCUMENT_SECTION: 1.0
        }.get(self.chunk_type, 0.5)
        
        # Speaker context bonus for conversations
        speaker_bonus = 1.0
        if self.chunk_type in [ChunkType.CONVERSATION_TURN, ChunkType.CONVERSATION_SEGMENT]:
            if self.metadata.get('speaker'):
                speaker_bonus = 1.1
        
        return length_score * completeness_score * type_bonus * speaker_bonus


class ConversationChunker:
    """Intelligent chunker for conversation content"""
    
    def __init__(self, min_chunk_size: int = 50, max_chunk_size: int = 1000, 
                 target_chunk_size: int = 300):
        """
        Initialize conversation chunker
        
        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
            target_chunk_size: Optimal characters per chunk
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.target_chunk_size = target_chunk_size
        
        # Patterns for detecting conversation structure
        self.speaker_patterns = [
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*[:]\s*',  # "John Smith: "
            r'^([A-Z]+)\s*[:]\s*',  # "JOHN: "
            r'^\[([^\]]+)\]\s*[:]\s*',  # "[John]: "
            r'^<([^>]+)>\s*[:]\s*',  # "<John>: "
            r'^(\w+)\s+says?\s*[:]\s*',  # "John says: "
        ]
        
        # Patterns for detecting conversation boundaries
        self.boundary_patterns = [
            r'\n\s*\n',  # Double newlines
            r'\n\s*---+\s*\n',  # Separator lines
            r'\n\s*\*\*\*+\s*\n',  # Asterisk separators
            r'\n\s*#+\s+',  # Markdown headers
            r'\n\s*\d{1,2}:\d{2}\s*(?:AM|PM)?\s*',  # Timestamps
        ]
    
    def chunk_conversation(self, content: str, metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """
        Chunk conversation content intelligently
        
        Args:
            content: The conversation text to chunk
            metadata: Additional metadata about the conversation
            
        Returns:
            List of TextChunk objects
        """
        if not content or not content.strip():
            return []
        
        metadata = metadata or {}
        content = content.strip()
        
        logger.debug(f"Chunking conversation content: {len(content)} characters")
        
        # Try different chunking strategies in order of preference
        chunks = []
        
        # Strategy 1: Detect and chunk by speaker turns
        speaker_chunks = self._chunk_by_speaker_turns(content, metadata)
        if speaker_chunks and self._validate_chunks(speaker_chunks):
            chunks = speaker_chunks
            logger.debug(f"Used speaker turn chunking: {len(chunks)} chunks")
        
        # Strategy 2: Chunk by conversation segments (groups of related turns)
        elif len(content) > self.max_chunk_size:
            segment_chunks = self._chunk_by_conversation_segments(content, metadata)
            if segment_chunks and self._validate_chunks(segment_chunks):
                chunks = segment_chunks
                logger.debug(f"Used conversation segment chunking: {len(chunks)} chunks")
        
        # Strategy 3: Fallback to paragraph-based chunking
        if not chunks:
            chunks = self._chunk_by_paragraphs(content, metadata)
            logger.debug(f"Used paragraph chunking: {len(chunks)} chunks")
        
        # Post-process chunks
        chunks = self._optimize_chunk_sizes(chunks)
        chunks = self._add_chunk_metadata(chunks, metadata)
        
        logger.info(f"Created {len(chunks)} chunks with avg quality: {np.mean([c.quality_score for c in chunks]):.3f}")
        
        return chunks
    
    def _chunk_by_speaker_turns(self, content: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """Chunk content by individual speaker turns"""
        chunks = []
        current_pos = 0
        
        # Find all speaker turn boundaries
        turn_boundaries = []
        
        for pattern in self.speaker_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                speaker = match.group(1)
                start_pos = match.start()
                turn_boundaries.append((start_pos, speaker))
        
        # Sort by position
        turn_boundaries.sort()
        
        if len(turn_boundaries) < 2:
            return []  # Not enough structure for speaker-based chunking
        
        # Create chunks between boundaries
        for i, (start_pos, speaker) in enumerate(turn_boundaries):
            # Find end position (start of next turn or end of content)
            if i < len(turn_boundaries) - 1:
                end_pos = turn_boundaries[i + 1][0]
            else:
                end_pos = len(content)
            
            # Extract turn content
            turn_content = content[start_pos:end_pos].strip()
            
            if len(turn_content) >= self.min_chunk_size:
                # Split long turns if necessary
                if len(turn_content) <= self.max_chunk_size:
                    chunk = TextChunk(
                        content=turn_content,
                        chunk_type=ChunkType.CONVERSATION_TURN,
                        start_position=start_pos,
                        end_position=end_pos,
                        metadata={'speaker': speaker, 'turn_index': i}
                    )
                    chunks.append(chunk)
                else:
                    # Split long turn into smaller chunks
                    sub_chunks = self._split_long_turn(turn_content, start_pos, speaker, i)
                    chunks.extend(sub_chunks)
        
        return chunks
    
    def _chunk_by_conversation_segments(self, content: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """Chunk content by conversation segments (groups of related turns)"""
        chunks = []
        
        # Find natural break points in the conversation
        break_points = [0]  # Start of content
        
        for pattern in self.boundary_patterns:
            for match in re.finditer(pattern, content):
                break_points.append(match.start())
        
        break_points.append(len(content))  # End of content
        break_points = sorted(set(break_points))
        
        # Create segments between break points
        for i in range(len(break_points) - 1):
            start_pos = break_points[i]
            end_pos = break_points[i + 1]
            segment_content = content[start_pos:end_pos].strip()
            
            if len(segment_content) >= self.min_chunk_size:
                if len(segment_content) <= self.max_chunk_size:
                    chunk = TextChunk(
                        content=segment_content,
                        chunk_type=ChunkType.CONVERSATION_SEGMENT,
                        start_position=start_pos,
                        end_position=end_pos,
                        metadata={'segment_index': i}
                    )
                    chunks.append(chunk)
                else:
                    # Split large segments
                    sub_chunks = self._split_large_segment(segment_content, start_pos, i)
                    chunks.extend(sub_chunks)
        
        return chunks
    
    def _chunk_by_paragraphs(self, content: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """Fallback chunking by paragraphs"""
        chunks = []
        paragraphs = re.split(r'\n\s*\n', content)
        current_pos = 0
        
        current_chunk_content = ""
        chunk_start = 0
        
        for para_idx, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                current_pos += len(paragraph) + 2  # Account for newlines
                continue
            
            # Check if adding this paragraph would exceed max size
            if (current_chunk_content and 
                len(current_chunk_content) + len(paragraph) + 1 > self.max_chunk_size):
                
                # Save current chunk if it meets minimum size
                if len(current_chunk_content) >= self.min_chunk_size:
                    chunk = TextChunk(
                        content=current_chunk_content,
                        chunk_type=ChunkType.PARAGRAPH,
                        start_position=chunk_start,
                        end_position=current_pos,
                        metadata={'paragraph_count': current_chunk_content.count('\n\n') + 1}
                    )
                    chunks.append(chunk)
                
                # Start new chunk
                current_chunk_content = paragraph
                chunk_start = current_pos
            else:
                # Add to current chunk
                if current_chunk_content:
                    current_chunk_content += "\n\n" + paragraph
                else:
                    current_chunk_content = paragraph
                    chunk_start = current_pos
            
            current_pos += len(paragraph) + 2
        
        # Add final chunk if it has content
        if current_chunk_content and len(current_chunk_content) >= self.min_chunk_size:
            chunk = TextChunk(
                content=current_chunk_content,
                chunk_type=ChunkType.PARAGRAPH,
                start_position=chunk_start,
                end_position=current_pos,
                metadata={'paragraph_count': current_chunk_content.count('\n\n') + 1}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_long_turn(self, turn_content: str, start_pos: int, speaker: str, turn_index: int) -> List[TextChunk]:
        """Split a long speaker turn into smaller chunks"""
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', turn_content)
        
        current_chunk = ""
        chunk_start = start_pos
        sentence_start = start_pos
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            # Check if adding this sentence would exceed target size
            if current_chunk and len(current_chunk) + len(sentence) + 1 > self.target_chunk_size:
                # Save current chunk
                chunk = TextChunk(
                    content=current_chunk.strip(),
                    chunk_type=ChunkType.CONVERSATION_TURN,
                    start_position=chunk_start,
                    end_position=sentence_start,
                    metadata={
                        'speaker': speaker,
                        'turn_index': turn_index,
                        'is_partial_turn': True
                    }
                )
                chunks.append(chunk)
                
                # Start new chunk
                current_chunk = sentence
                chunk_start = sentence_start
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            
            sentence_start += len(sentence) + 1
        
        # Add final chunk
        if current_chunk.strip():
            chunk = TextChunk(
                content=current_chunk.strip(),
                chunk_type=ChunkType.CONVERSATION_TURN,
                start_position=chunk_start,
                end_position=start_pos + len(turn_content),
                metadata={
                    'speaker': speaker,
                    'turn_index': turn_index,
                    'is_partial_turn': len(chunks) > 0
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_large_segment(self, segment_content: str, start_pos: int, segment_index: int) -> List[TextChunk]:
        """Split a large conversation segment into smaller chunks"""
        chunks = []
        
        # Try to split by speaker turns within the segment
        turn_chunks = self._chunk_by_speaker_turns(segment_content, {})
        
        if turn_chunks:
            # Adjust positions and metadata
            for i, chunk in enumerate(turn_chunks):
                chunk.start_position += start_pos
                chunk.end_position += start_pos
                chunk.metadata['segment_index'] = segment_index
                chunk.metadata['sub_chunk_index'] = i
                chunks.append(chunk)
        else:
            # Fallback to sentence-based splitting
            sentences = re.split(r'(?<=[.!?])\s+', segment_content)
            current_chunk = ""
            chunk_start = start_pos
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                
                if current_chunk and len(current_chunk) + len(sentence) + 1 > self.target_chunk_size:
                    chunk = TextChunk(
                        content=current_chunk.strip(),
                        chunk_type=ChunkType.SENTENCE_GROUP,
                        start_position=chunk_start,
                        end_position=chunk_start + len(current_chunk),
                        metadata={'segment_index': segment_index}
                    )
                    chunks.append(chunk)
                    
                    current_chunk = sentence
                    chunk_start = chunk_start + len(current_chunk) + 1
                else:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
            
            if current_chunk.strip():
                chunk = TextChunk(
                    content=current_chunk.strip(),
                    chunk_type=ChunkType.SENTENCE_GROUP,
                    start_position=chunk_start,
                    end_position=start_pos + len(segment_content),
                    metadata={'segment_index': segment_index}
                )
                chunks.append(chunk)
        
        return chunks
    
    def _validate_chunks(self, chunks: List[TextChunk]) -> bool:
        """Validate that chunks meet quality criteria"""
        if not chunks:
            return False
        
        # Check minimum number of valid chunks
        valid_chunks = [c for c in chunks if c.quality_score > 0.3]
        if len(valid_chunks) < max(1, len(chunks) * 0.5):
            return False
        
        # Check average quality
        avg_quality = np.mean([c.quality_score for c in chunks])
        if avg_quality < 0.5:
            return False
        
        # Check size distribution
        sizes = [len(c.content) for c in chunks]
        if any(size < self.min_chunk_size for size in sizes):
            return False
        
        return True
    
    def _optimize_chunk_sizes(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Optimize chunk sizes by merging small chunks or splitting large ones"""
        if not chunks:
            return chunks
        
        optimized_chunks = []
        i = 0
        
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # If chunk is too small, try to merge with next chunk
            if (len(current_chunk.content) < self.min_chunk_size and 
                i + 1 < len(chunks) and
                len(current_chunk.content) + len(chunks[i + 1].content) <= self.max_chunk_size):
                
                next_chunk = chunks[i + 1]
                
                # Create merged chunk
                merged_content = current_chunk.content + "\n\n" + next_chunk.content
                merged_chunk = TextChunk(
                    content=merged_content,
                    chunk_type=current_chunk.chunk_type,
                    start_position=current_chunk.start_position,
                    end_position=next_chunk.end_position,
                    metadata={
                        **current_chunk.metadata,
                        'merged_from': [current_chunk.metadata, next_chunk.metadata]
                    }
                )
                
                optimized_chunks.append(merged_chunk)
                i += 2  # Skip next chunk since we merged it
            else:
                optimized_chunks.append(current_chunk)
                i += 1
        
        return optimized_chunks
    
    def _add_chunk_metadata(self, chunks: List[TextChunk], base_metadata: Dict[str, Any]) -> List[TextChunk]:
        """Add additional metadata to chunks"""
        for i, chunk in enumerate(chunks):
            # Add base metadata
            chunk.metadata.update({
                'chunk_index': i,
                'total_chunks': len(chunks),
                'created_at': datetime.now().isoformat(),
                **base_metadata
            })
            
            # Add content analysis
            chunk.metadata.update(self._analyze_chunk_content(chunk.content))
        
        return chunks
    
    def _analyze_chunk_content(self, content: str) -> Dict[str, Any]:
        """Analyze chunk content for additional metadata"""
        analysis = {
            'character_count': len(content),
            'word_count': len(content.split()),
            'sentence_count': len(re.findall(r'[.!?]+', content)),
            'has_questions': '?' in content,
            'has_dialogue': ':' in content and any(pattern in content for pattern in ['said', 'says', 'asked']),
            'avg_sentence_length': 0,
            'content_density': 0
        }
        
        # Calculate average sentence length
        sentences = re.split(r'[.!?]+', content)
        sentence_lengths = [len(s.strip().split()) for s in sentences if s.strip()]
        if sentence_lengths:
            analysis['avg_sentence_length'] = np.mean(sentence_lengths)
        
        # Calculate content density (non-whitespace characters / total characters)
        if len(content) > 0:
            analysis['content_density'] = len(content.replace(' ', '').replace('\n', '').replace('\t', '')) / len(content)
        
        return analysis


class DocumentChunker:
    """Intelligent chunker for document content"""
    
    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 1500, 
                 target_chunk_size: int = 500):
        """
        Initialize document chunker
        
        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
            target_chunk_size: Optimal characters per chunk
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.target_chunk_size = target_chunk_size
    
    def chunk_document(self, content: str, metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """
        Chunk document content intelligently
        
        Args:
            content: The document text to chunk
            metadata: Additional metadata about the document
            
        Returns:
            List of TextChunk objects
        """
        if not content or not content.strip():
            return []
        
        metadata = metadata or {}
        content = content.strip()
        
        logger.debug(f"Chunking document content: {len(content)} characters")
        
        # Strategy 1: Try to chunk by sections/headers
        if self._has_section_structure(content):
            chunks = self._chunk_by_sections(content, metadata)
            if chunks:
                logger.debug(f"Used section-based chunking: {len(chunks)} chunks")
                return chunks
        
        # Strategy 2: Chunk by paragraphs
        chunks = self._chunk_by_paragraphs_doc(content, metadata)
        logger.debug(f"Used paragraph chunking: {len(chunks)} chunks")
        
        return chunks
    
    def _has_section_structure(self, content: str) -> bool:
        """Check if content has clear section structure"""
        section_patterns = [
            r'\n\s*#+\s+',  # Markdown headers
            r'\n\s*\d+\.\s+',  # Numbered sections
            r'\n\s*[A-Z][A-Z\s]+\n',  # ALL CAPS headers
            r'\n\s*-{3,}\s*\n',  # Horizontal rules
        ]
        
        section_count = 0
        for pattern in section_patterns:
            section_count += len(re.findall(pattern, content))
        
        return section_count >= 3  # At least 3 sections
    
    def _chunk_by_sections(self, content: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """Chunk content by document sections"""
        chunks = []
        
        # Find section boundaries
        section_pattern = r'\n\s*(#+\s+.*|[A-Z][A-Z\s]+\n|\d+\.\s+.*|-{3,})\s*\n'
        sections = re.split(section_pattern, content)
        
        current_pos = 0
        for i, section in enumerate(sections):
            if not section or not section.strip():
                continue
            
            section = section.strip()
            
            if len(section) >= self.min_chunk_size:
                if len(section) <= self.max_chunk_size:
                    chunk = TextChunk(
                        content=section,
                        chunk_type=ChunkType.DOCUMENT_SECTION,
                        start_position=current_pos,
                        end_position=current_pos + len(section),
                        metadata={'section_index': i}
                    )
                    chunks.append(chunk)
                else:
                    # Split large sections
                    sub_chunks = self._split_large_section(section, current_pos, i)
                    chunks.extend(sub_chunks)
            
            current_pos += len(section)
        
        return chunks
    
    def _chunk_by_paragraphs_doc(self, content: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """Chunk document content by paragraphs"""
        chunks = []
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk = ""
        chunk_start = 0
        current_pos = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if adding this paragraph exceeds max size
            if current_chunk and len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                # Save current chunk
                if len(current_chunk) >= self.min_chunk_size:
                    chunk = TextChunk(
                        content=current_chunk,
                        chunk_type=ChunkType.PARAGRAPH,
                        start_position=chunk_start,
                        end_position=current_pos,
                        metadata={'paragraph_count': current_chunk.count('\n\n') + 1}
                    )
                    chunks.append(chunk)
                
                # Start new chunk
                current_chunk = para
                chunk_start = current_pos
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                    chunk_start = current_pos
            
            current_pos += len(para) + 2
        
        # Add final chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunk = TextChunk(
                content=current_chunk,
                chunk_type=ChunkType.PARAGRAPH,
                start_position=chunk_start,
                end_position=current_pos,
                metadata={'paragraph_count': current_chunk.count('\n\n') + 1}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_large_section(self, section_content: str, start_pos: int, section_index: int) -> List[TextChunk]:
        """Split a large document section into smaller chunks"""
        chunks = []
        
        # Split by paragraphs within the section
        paragraphs = re.split(r'\n\s*\n', section_content)
        current_chunk = ""
        chunk_start = start_pos
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if current_chunk and len(current_chunk) + len(para) + 2 > self.target_chunk_size:
                chunk = TextChunk(
                    content=current_chunk,
                    chunk_type=ChunkType.DOCUMENT_SECTION,
                    start_position=chunk_start,
                    end_position=chunk_start + len(current_chunk),
                    metadata={
                        'section_index': section_index,
                        'is_partial_section': True
                    }
                )
                chunks.append(chunk)
                
                current_chunk = para
                chunk_start = chunk_start + len(current_chunk) + 2
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        if current_chunk:
            chunk = TextChunk(
                content=current_chunk,
                chunk_type=ChunkType.DOCUMENT_SECTION,
                start_position=chunk_start,
                end_position=start_pos + len(section_content),
                metadata={
                    'section_index': section_index,
                    'is_partial_section': len(chunks) > 0
                }
            )
            chunks.append(chunk)
        
        return chunks


class IntelligentChunker:
    """Main chunking service that routes to appropriate specialized chunkers"""
    
    def __init__(self, conversation_chunker: ConversationChunker = None, 
                 document_chunker: DocumentChunker = None):
        """
        Initialize intelligent chunker
        
        Args:
            conversation_chunker: Specialized chunker for conversations
            document_chunker: Specialized chunker for documents
        """
        self.conversation_chunker = conversation_chunker or ConversationChunker()
        self.document_chunker = document_chunker or DocumentChunker()
    
    def chunk_content(self, content: str, content_type: str = None, 
                     metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """
        Intelligently chunk content based on type and structure
        
        Args:
            content: Text content to chunk
            content_type: Hint about content type ('conversation', 'document', etc.)
            metadata: Additional metadata
            
        Returns:
            List of TextChunk objects
        """
        if not content or not content.strip():
            return []
        
        metadata = metadata or {}
        
        # Auto-detect content type if not provided
        if not content_type:
            content_type = self._detect_content_type(content)
        
        logger.info(f"Chunking content type: {content_type}, length: {len(content)} characters")
        
        # Route to appropriate chunker
        if content_type == 'conversation':
            chunks = self.conversation_chunker.chunk_conversation(content, metadata)
        elif content_type == 'document':
            chunks = self.document_chunker.chunk_document(content, metadata)
        else:
            # Default to conversation chunker for mixed content
            chunks = self.conversation_chunker.chunk_conversation(content, metadata)
        
        # Add final metadata
        for chunk in chunks:
            chunk.metadata['detected_content_type'] = content_type
            chunk.metadata['chunking_strategy'] = self.__class__.__name__
        
        logger.info(f"Created {len(chunks)} chunks with avg quality: {np.mean([c.quality_score for c in chunks]):.3f}")
        
        return chunks
    
    def _detect_content_type(self, content: str) -> str:
        """Detect content type from structure and patterns"""
        # Look for conversation indicators
        conversation_indicators = [
            r'[A-Za-z]+\s*:\s*',  # Speaker patterns
            r'\bsaid\b', r'\bsays\b', r'\basked\b',  # Dialogue verbs
            r'\bi\s+told\b', r'\bhe\s+replied\b',  # Reported speech
        ]
        
        conversation_score = sum(len(re.findall(pattern, content, re.IGNORECASE)) 
                               for pattern in conversation_indicators)
        
        # Look for document indicators
        document_indicators = [
            r'\n\s*#+\s+',  # Markdown headers
            r'\n\s*\d+\.\s+',  # Numbered lists
            r'\n\s*[A-Z][A-Z\s]+\n',  # Section headers
            r'\n\s*-{3,}\s*\n',  # Horizontal rules
        ]
        
        document_score = sum(len(re.findall(pattern, content)) 
                           for pattern in document_indicators)
        
        # Determine content type based on scores
        if conversation_score > document_score and conversation_score > 2:
            return 'conversation'
        elif document_score > conversation_score and document_score > 2:
            return 'document'
        else:
            # Default to conversation for mixed or unclear content
            return 'conversation'
    
    def get_chunking_stats(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """Get statistics about a set of chunks"""
        if not chunks:
            return {}
        
        sizes = [len(chunk.content) for chunk in chunks]
        quality_scores = [chunk.quality_score for chunk in chunks]
        chunk_types = [chunk.chunk_type.value for chunk in chunks]
        
        return {
            'total_chunks': len(chunks),
            'total_characters': sum(sizes),
            'avg_chunk_size': np.mean(sizes),
            'median_chunk_size': np.median(sizes),
            'min_chunk_size': min(sizes),
            'max_chunk_size': max(sizes),
            'avg_quality_score': np.mean(quality_scores),
            'chunk_types': dict(Counter(chunk_types)),
            'high_quality_chunks': sum(1 for score in quality_scores if score > 0.8),
            'low_quality_chunks': sum(1 for score in quality_scores if score < 0.5)
        }