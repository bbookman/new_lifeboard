"""
Chunking-aware processor for LimitlessProcessor

Integrates intelligent chunking system with the existing preprocessing pipeline
to create segment-aware embeddings that improve search quality and context relevance.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from sources.base import DataItem
from core.chunking import IntelligentChunker, TextChunk, ChunkType

logger = logging.getLogger(__name__)


@dataclass
class ChunkedDataItem:
    """Represents a data item with its associated chunks"""
    original_item: DataItem
    chunks: List[TextChunk]
    chunking_metadata: Dict[str, Any]


class ChunkingProcessor:
    """
    Processor that applies intelligent chunking to content
    
    Creates multiple semantically coherent chunks from long content while
    preserving metadata and context for better embedding generation.
    """
    
    def __init__(self,
                 enable_chunking: bool = True,
                 min_chunk_size: int = 50,
                 max_chunk_size: int = 1000,
                 target_chunk_size: int = 300):
        """
        Initialize chunking processor
        
        Args:
            enable_chunking: Whether to enable intelligent chunking
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
            target_chunk_size: Optimal characters per chunk
        """
        self.enable_chunking = enable_chunking
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.target_chunk_size = target_chunk_size
        
        if self.enable_chunking:
            from core.chunking import ConversationChunker, DocumentChunker
            
            # Create specialized chunkers with custom parameters
            conversation_chunker = ConversationChunker(
                min_chunk_size=min_chunk_size,
                max_chunk_size=max_chunk_size,
                target_chunk_size=target_chunk_size
            )
            
            document_chunker = DocumentChunker(
                min_chunk_size=min_chunk_size,
                max_chunk_size=max_chunk_size,
                target_chunk_size=target_chunk_size
            )
            
            self.chunker = IntelligentChunker(conversation_chunker, document_chunker)
        else:
            self.chunker = None

    def get_processor_name(self) -> str:
        """Get the processor name for metadata tracking"""
        return self.__class__.__name__
    
    def process(self, item: DataItem) -> DataItem:
        """
        Process item with intelligent chunking
        
        Args:
            item: DataItem to process
            
        Returns:
            DataItem with chunking metadata added
        """
        if not self.enable_chunking or not self.chunker or not item.content:
            return self._add_no_chunking_metadata(item)
        
        try:
            # Detect content type from existing metadata or content
            content_type = self._detect_content_type(item)
            
            # Create chunks using intelligent chunker
            chunks = self.chunker.chunk_content(
                content=item.content,
                content_type=content_type,
                metadata=item.metadata
            )
            
            if not chunks:
                return self._add_no_chunking_metadata(item)
            
            # Add chunking metadata to original item
            chunking_stats = self.chunker.get_chunking_stats(chunks)
            
            # Store chunk information in metadata
            item.metadata['intelligent_chunking'] = {
                'enabled': True,
                'total_chunks': len(chunks),
                'content_type': content_type,
                'chunking_stats': chunking_stats,
                'chunks': [
                    {
                        'content': chunk.content,
                        'chunk_type': chunk.chunk_type.value,
                        'start_position': chunk.start_position,
                        'end_position': chunk.end_position,
                        'quality_score': chunk.quality_score,
                        'metadata': chunk.metadata
                    }
                    for chunk in chunks
                ]
            }
            
            # Track processing
            self._add_processing_history(item, chunks, chunking_stats)
            
            logger.info(f"Chunked item {item.source_id}: {len(chunks)} chunks, "
                       f"avg quality: {chunking_stats.get('avg_quality_score', 0):.3f}")
            
            return item
            
        except Exception as e:
            logger.error(f"Error in chunking processor for item {item.source_id}: {e}")
            return self._add_error_metadata(item, str(e))
    
    def _detect_content_type(self, item: DataItem) -> str:
        """Detect content type from item metadata and content"""
        # Check existing classification
        content_classification = item.metadata.get('content_classification', {})
        content_types = content_classification.get('types', [])
        
        # Look for conversation indicators
        if 'conversation' in content_types:
            return 'conversation'
        
        # Check for document-like structure
        if any(t in content_types for t in ['summary', 'fact', 'detailed_content']):
            return 'document'
        
        # Check metadata for conversation indicators
        if item.metadata.get('speakers') or item.metadata.get('original_lifelog'):
            return 'conversation'
        
        # Check for named entities that might indicate conversation
        named_entities = item.metadata.get('named_entities', {})
        if named_entities.get('people'):
            return 'conversation'
        
        # Default to letting the chunker auto-detect
        return None
    
    def _add_no_chunking_metadata(self, item: DataItem) -> DataItem:
        """Add metadata when chunking is disabled or not applicable"""
        item.metadata['intelligent_chunking'] = {
            'enabled': False,
            'total_chunks': 1,
            'reason': 'chunking_disabled' if not self.enable_chunking else 'no_content'
        }
        
        self._add_processing_history(item, [], {})
        return item
    
    def _add_error_metadata(self, item: DataItem, error_message: str) -> DataItem:
        """Add metadata when chunking fails"""
        item.metadata['intelligent_chunking'] = {
            'enabled': False,
            'total_chunks': 1,
            'error': error_message,
            'reason': 'chunking_failed'
        }
        
        self._add_processing_history(item, [], {})
        return item
    
    def _add_processing_history(self, item: DataItem, chunks: List[TextChunk], 
                              stats: Dict[str, Any]):
        """Add processing history entry"""
        if 'processing_history' not in item.metadata:
            item.metadata['processing_history'] = []
        
        item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'intelligent_chunking',
            'chunks_created': len(chunks),
            'chunking_stats': stats
        })
    
    def get_chunks_for_embedding(self, item: DataItem) -> List[Dict[str, Any]]:
        """
        Extract chunks that should be embedded separately
        
        Args:
            item: Processed DataItem
            
        Returns:
            List of chunk data suitable for embedding
        """
        chunking_data = item.metadata.get('intelligent_chunking')
        if not chunking_data or not chunking_data.get('enabled'):
            # Return original content as single chunk
            return [{
                'content': item.content,
                'chunk_id': f"{item.source_id}_full",
                'chunk_type': 'full_content',
                'quality_score': 1.0,
                'metadata': {
                    'is_full_content': True,
                    'original_item_id': item.source_id,
                    'namespace': item.namespace
                }
            }]
        
        # Return individual chunks
        chunks_data = []
        chunks = chunking_data.get('chunks', [])
        
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'content': chunk['content'],
                'chunk_id': f"{item.source_id}_chunk_{i}",
                'chunk_type': chunk['chunk_type'],
                'quality_score': chunk['quality_score'],
                'metadata': {
                    'is_chunk': True,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'original_item_id': item.source_id,
                    'namespace': item.namespace,
                    'start_position': chunk['start_position'],
                    'end_position': chunk['end_position'],
                    **chunk['metadata']
                }
            }
            chunks_data.append(chunk_data)
        
        return chunks_data
    
    def should_embed_chunks_separately(self, item: DataItem) -> bool:
        """
        Determine if chunks should be embedded separately
        
        Args:
            item: Processed DataItem
            
        Returns:
            True if chunks should be embedded separately
        """
        chunking_data = item.metadata.get('intelligent_chunking')
        if not chunking_data or not chunking_data.get('enabled'):
            return False
        
        # Check if chunking created high-quality chunks
        stats = chunking_data.get('chunking_stats', {})
        total_chunks = stats.get('total_chunks', 1)
        avg_quality = stats.get('avg_quality_score', 0)
        
        # Embed separately if we have multiple high-quality chunks
        return total_chunks > 1 and avg_quality > 0.6
    
    def get_processor_config(self) -> Dict[str, Any]:
        """Get processor configuration"""
        return {
            'enable_chunking': self.enable_chunking,
            'min_chunk_size': self.min_chunk_size,
            'max_chunk_size': self.max_chunk_size,
            'target_chunk_size': self.target_chunk_size,
            'chunker_available': self.chunker is not None
        }


class ChunkingEmbeddingIntegrator:
    """
    Service to integrate chunking with embedding generation
    
    Handles the creation of separate embeddings for chunks while maintaining
    relationships to the original content.
    """
    
    def __init__(self):
        """Initialize the integrator"""
        pass
    
    def prepare_items_for_embedding(self, processed_items: List[DataItem]) -> List[Dict[str, Any]]:
        """
        Prepare processed items for embedding generation
        
        Args:
            processed_items: List of items processed by ChunkingProcessor
            
        Returns:
            List of embedding tasks (original items + chunks)
        """
        embedding_tasks = []
        
        for item in processed_items:
            # Check if item has chunking processor metadata
            chunking_processor = None
            for processor_entry in item.metadata.get('processing_history', []):
                if processor_entry.get('processor') == 'ChunkingProcessor':
                    chunking_processor = ChunkingProcessor()
                    break
            
            if not chunking_processor:
                # No chunking processor found, treat as single item
                embedding_tasks.append({
                    'type': 'original_item',
                    'item': item,
                    'content': item.content,
                    'item_id': f"{item.namespace}:{item.source_id}",
                    'metadata': item.metadata
                })
                continue
            
            # Check if we should embed chunks separately
            if chunking_processor.should_embed_chunks_separately(item):
                # Add chunks as separate embedding tasks
                chunks_data = chunking_processor.get_chunks_for_embedding(item)
                
                for chunk_data in chunks_data:
                    embedding_tasks.append({
                        'type': 'chunk',
                        'item': item,
                        'content': chunk_data['content'],
                        'item_id': f"{item.namespace}:{chunk_data['chunk_id']}",
                        'chunk_metadata': chunk_data,
                        'metadata': {
                            **item.metadata,
                            'chunk_info': chunk_data['metadata']
                        }
                    })
                
                # Also add original item with chunking context
                embedding_tasks.append({
                    'type': 'original_with_chunks',
                    'item': item,
                    'content': item.content,
                    'item_id': f"{item.namespace}:{item.source_id}",
                    'metadata': {
                        **item.metadata,
                        'has_chunks': True,
                        'chunk_count': len(chunks_data)
                    }
                })
            else:
                # Embed as single item
                embedding_tasks.append({
                    'type': 'original_item',
                    'item': item,
                    'content': item.content,
                    'item_id': f"{item.namespace}:{item.source_id}",
                    'metadata': item.metadata
                })
        
        logger.info(f"Prepared {len(embedding_tasks)} embedding tasks from {len(processed_items)} items")
        return embedding_tasks
    
    def create_vector_id(self, task: Dict[str, Any]) -> str:
        """
        Create vector store ID for an embedding task
        
        Args:
            task: Embedding task
            
        Returns:
            Unique vector ID
        """
        return task['item_id']
    
    def get_embedding_stats(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics about embedding tasks
        
        Args:
            tasks: List of embedding tasks
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_tasks': len(tasks),
            'original_items': 0,
            'chunks': 0,
            'original_with_chunks': 0
        }
        
        for task in tasks:
            task_type = task.get('type', 'unknown')
            if task_type in stats:
                stats[task_type] += 1
            else:
                stats['unknown'] = stats.get('unknown', 0) + 1
        
        # Calculate chunking efficiency
        if stats['chunks'] > 0 and stats['original_items'] > 0:
            stats['avg_chunks_per_item'] = stats['chunks'] / stats['original_items']
        
        return stats