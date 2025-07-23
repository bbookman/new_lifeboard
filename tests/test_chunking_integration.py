"""Integration tests for the chunking system with ingestion service."""

import asyncio
import logging
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from sources.base import DataItem
from sources.chunking_processor import ChunkingEmbeddingIntegrator
from services.ingestion import IngestionService
from core.chunking import TextChunk, IntelligentChunker
from config.models import AppConfig

# Disable logging during tests
logging.disable(logging.CRITICAL)


class TestChunkingIntegration:
    """Test integration between chunking system and ingestion service"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Mock services
        self.mock_database = Mock()
        self.mock_vector_store = Mock()
        self.mock_embedding_service = AsyncMock()
        
        # Mock config
        self.config = Mock(spec=AppConfig)
        self.config.chunking = {
            'enable_intelligent_chunking': True,
            'min_chunk_size': 100,
            'max_chunk_size': 500,
            'overlap_size': 50
        }
        
        # Create ingestion service
        self.ingestion_service = IngestionService(
            database=self.mock_database,
            vector_store=self.mock_vector_store,
            embedding_service=self.mock_embedding_service,
            config=self.config
        )
    
    def test_chunking_integrator_initialization(self):
        """Test that chunking integrator is properly initialized"""
        assert hasattr(self.ingestion_service, 'chunking_integrator')
        assert isinstance(self.ingestion_service.chunking_integrator, ChunkingEmbeddingIntegrator)
    
    def test_processor_chunking_configuration(self):
        """Test that processor is configured with chunking support"""
        processor = self.ingestion_service.processor
        
        # Check that the processor has chunking processors in the pipeline
        processor_names = [p.get_processor_name() for p in processor.processors]
        assert 'ChunkingProcessor' in processor_names
        
        # Verify pipeline info shows chunking capability
        pipeline_info = processor.get_pipeline_info()
        assert 'ChunkingProcessor' in pipeline_info['processors']
        assert pipeline_info['processor_count'] > 0
    
    @pytest.mark.asyncio
    async def test_process_pending_embeddings_with_chunking(self):
        """Test that pending embeddings are processed with chunking support"""
        # Mock pending items
        pending_items = [
            {
                'id': 'limitless:item1',
                'namespace': 'limitless',
                'content': self._create_long_conversation_content(),
                'metadata': {'type': 'conversation'}
            },
            {
                'id': 'limitless:item2',
                'namespace': 'limitless',
                'content': self._create_document_content(),
                'metadata': {'type': 'document'}
            }
        ]
        
        self.mock_database.get_pending_embeddings.return_value = pending_items
        
        # Mock embedding service to return embeddings
        self.mock_embedding_service.embed_texts.return_value = [
            [0.1] * 384,  # Mock embedding 1
            [0.2] * 384,  # Mock embedding 2
            [0.3] * 384,  # Mock embedding 3
        ]
        
        # Mock vector store success
        self.mock_vector_store.add_vector.return_value = True
        
        # Process embeddings
        result = await self.ingestion_service.process_pending_embeddings(batch_size=10)
        
        # Verify chunking stats are included
        assert 'chunking_stats' in result
        assert 'items_chunked' in result['chunking_stats']
        assert 'total_chunks_created' in result['chunking_stats']
        assert 'chunk_embeddings_created' in result['chunking_stats']
        
        # Verify embedding service was called
        assert self.mock_embedding_service.embed_texts.called
        
        # Verify database status updates
        assert self.mock_database.update_embedding_status.called
    
    @pytest.mark.asyncio
    async def test_chunking_embedding_batch_processing(self):
        """Test processing of chunking-aware embedding batches"""
        # Create mock embedding tasks
        embedding_tasks = [
            {
                'id': 'limitless:item1:chunk1',
                'original_id': 'limitless:item1',
                'content': 'This is the first chunk of content',
                'is_chunk': True,
                'chunk_index': 0,
                'metadata': {'chunk_type': 'conversation_turn'}
            },
            {
                'id': 'limitless:item1:chunk2',
                'original_id': 'limitless:item1',
                'content': 'This is the second chunk of content',
                'is_chunk': True,
                'chunk_index': 1,
                'metadata': {'chunk_type': 'conversation_turn'}
            },
            {
                'id': 'limitless:item2',
                'original_id': 'limitless:item2',
                'content': 'This is a complete item without chunking',
                'is_chunk': False,
                'metadata': {'type': 'document'}
            }
        ]
        
        # Mock embedding service
        self.mock_embedding_service.embed_texts.return_value = [
            [0.1] * 384,  # Chunk 1 embedding
            [0.2] * 384,  # Chunk 2 embedding
            [0.3] * 384,  # Complete item embedding
        ]
        
        # Mock vector store success
        self.mock_vector_store.add_vector.return_value = True
        
        # Initialize result dictionary
        result = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "chunking_stats": {
                "items_chunked": 0,
                "total_chunks_created": 0,
                "chunk_embeddings_created": 0
            }
        }
        
        # Process the batch
        await self.ingestion_service._process_chunking_embedding_batch(embedding_tasks, result)
        
        # Verify processing results
        assert result['processed'] == 3
        assert result['successful'] == 3
        assert result['failed'] == 0
        assert len(result['errors']) == 0
        
        # Verify chunking stats
        assert result['chunking_stats']['chunk_embeddings_created'] == 2
        
        # Verify vector store calls
        assert self.mock_vector_store.add_vector.call_count == 3
        
        # Verify database updates
        assert self.mock_database.update_embedding_status.call_count == 3
    
    @pytest.mark.asyncio
    async def test_chunking_error_handling(self):
        """Test error handling in chunking embedding batch processing"""
        # Create mock embedding tasks
        embedding_tasks = [
            {
                'id': 'limitless:item1:chunk1',
                'original_id': 'limitless:item1',
                'content': 'Test chunk content',
                'is_chunk': True
            }
        ]
        
        # Mock embedding service to raise exception
        self.mock_embedding_service.embed_texts.side_effect = Exception("Embedding service error")
        
        # Initialize result dictionary
        result = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "chunking_stats": {
                "items_chunked": 0,
                "total_chunks_created": 0,
                "chunk_embeddings_created": 0
            }
        }
        
        # Process the batch
        await self.ingestion_service._process_chunking_embedding_batch(embedding_tasks, result)
        
        # Verify error handling
        assert result['processed'] == 1
        assert result['successful'] == 0
        assert result['failed'] == 1
        assert len(result['errors']) == 1
        assert "Chunking batch embedding failed" in result['errors'][0]
    
    def test_data_item_conversion_for_chunking(self):
        """Test conversion of database items to DataItems for chunking"""
        # Mock pending items from database
        pending_items = [
            {
                'id': 'limitless:conversation123',
                'namespace': 'limitless',
                'content': 'User: Hello! Assistant: Hi there! How can I help?',
                'metadata': {'type': 'conversation', 'participants': ['User', 'Assistant']}
            }
        ]
        
        self.mock_database.get_pending_embeddings.return_value = pending_items
        
        # Access the chunking integrator
        integrator = self.ingestion_service.chunking_integrator
        
        # Convert to DataItems
        data_items = []
        for item in pending_items:
            data_item = DataItem(
                namespace=item.get('namespace', ''),
                source_id=item.get('id', '').split(':', 1)[-1] if ':' in item.get('id', '') else item.get('id', ''),
                content=item.get('content', ''),
                metadata=item.get('metadata', {}),
                created_at=None,
                updated_at=None
            )
            data_items.append(data_item)
        
        # Test that conversion works correctly
        assert len(data_items) == 1
        assert data_items[0].namespace == 'limitless'
        assert data_items[0].source_id == 'conversation123'
        assert 'User:' in data_items[0].content
        assert data_items[0].metadata['type'] == 'conversation'
    
    @pytest.mark.asyncio
    async def test_no_pending_embeddings(self):
        """Test handling when there are no pending embeddings"""
        # Mock empty pending items
        self.mock_database.get_pending_embeddings.return_value = []
        
        # Process embeddings
        result = await self.ingestion_service.process_pending_embeddings()
        
        # Verify result
        assert result['processed'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
        assert len(result['errors']) == 0
        assert 'chunking_stats' in result
        
        # Verify no embedding service calls
        assert not self.mock_embedding_service.embed_texts.called
    
    @pytest.mark.asyncio
    async def test_empty_content_filtering(self):
        """Test that items with empty content are filtered out"""
        # Mock embedding tasks with empty content
        embedding_tasks = [
            {
                'id': 'limitless:empty1',
                'original_id': 'limitless:empty1',
                'content': '',  # Empty content
                'is_chunk': False
            },
            {
                'id': 'limitless:valid1',
                'original_id': 'limitless:valid1',
                'content': 'Valid content here',
                'is_chunk': False
            },
            {
                'id': 'limitless:none1',
                'original_id': 'limitless:none1',
                'content': None,  # None content
                'is_chunk': False
            }
        ]
        
        # Mock embedding service for valid content only
        self.mock_embedding_service.embed_texts.return_value = [
            [0.1] * 384  # Only one embedding for valid content
        ]
        
        self.mock_vector_store.add_vector.return_value = True
        
        # Initialize result dictionary
        result = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "chunking_stats": {
                "items_chunked": 0,
                "total_chunks_created": 0,
                "chunk_embeddings_created": 0
            }
        }
        
        # Process the batch
        await self.ingestion_service._process_chunking_embedding_batch(embedding_tasks, result)
        
        # Verify only valid content was processed
        assert result['processed'] == 1  # Only the valid content item
        assert result['successful'] == 1
        assert self.mock_embedding_service.embed_texts.call_count == 1
        
        # Verify embedding service was called with only valid content
        call_args = self.mock_embedding_service.embed_texts.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] == 'Valid content here'
    
    def _create_long_conversation_content(self) -> str:
        """Create a long conversation content for testing chunking"""
        return """
        User: I've been thinking about starting a new project, but I'm not sure where to begin.
        
        Assistant: That's exciting! Starting a new project can feel overwhelming, but breaking it down into manageable steps helps. What kind of project are you considering?
        
        User: It's a web application for tracking personal finances. I want to help people manage their budgets better.
        
        Assistant: That's a great idea! Personal finance management is always in demand. Here are some key steps to get started:
        
        1. Define your target audience - who specifically do you want to help?
        2. Research existing solutions to understand the competitive landscape
        3. Identify unique features that will set your app apart
        4. Create wireframes and user flow diagrams
        5. Choose your technology stack
        
        Would you like to dive deeper into any of these areas?
        
        User: I'm particularly interested in the technology stack. I have experience with Python and JavaScript, but I'm not sure about the database choice.
        
        Assistant: Great! With Python and JavaScript experience, you have solid options. For a finance app, here's what I'd recommend:
        
        Backend: Python with Django or FastAPI
        Frontend: React or Vue.js
        Database: PostgreSQL for structured financial data
        
        PostgreSQL is excellent for financial applications because it provides ACID compliance, strong data integrity, and excellent support for complex queries you'll need for financial analysis.
        """
    
    def _create_document_content(self) -> str:
        """Create a document content for testing chunking"""
        return """
        # Financial Planning Guide
        
        ## Introduction
        Financial planning is the process of setting and achieving your financial goals through proper management of your finances.
        
        ## Key Principles
        1. Set clear financial goals
        2. Create a budget and stick to it
        3. Build an emergency fund
        4. Invest for the long term
        5. Regularly review and adjust your plan
        
        ## Getting Started
        The first step in financial planning is understanding your current financial situation. This includes calculating your net worth, analyzing your cash flow, and identifying your financial goals.
        
        ## Conclusion
        Remember that financial planning is a marathon, not a sprint. Consistency and patience are key to long-term success.
        """


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])