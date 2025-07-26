"""
Chat service for Phase 7: Minimal Web UI

Provides hybrid data access (vector search + SQL queries) and LLM integration
for the minimal chat interface.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from llm.factory import create_llm_provider
from llm.base import LLMResponse, LLMError
from config.models import AppConfig
from core.exception_handling import handle_service_exceptions, safe_operation
from sources.limitless import LimitlessSource

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """Context data for chat response generation"""
    vector_results: List[Dict[str, Any]]
    sql_results: List[Dict[str, Any]]
    limitless_results: List[Dict[str, Any]]
    total_results: int


class ChatService:
    """Service for handling chat interactions with hybrid data access"""
    
    def __init__(self, config: AppConfig, database: DatabaseService, 
                 vector_store: VectorStoreService, embeddings: EmbeddingService,
                 limitless_source: Optional[LimitlessSource] = None):
        self.config = config
        self.database = database
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.limitless_source = limitless_source
        self.llm_provider = None
        
    async def initialize(self):
        """Initialize LLM provider and embedding service"""
        try:
            logger.info("Starting service initialization...")
            
            # Initialize embedding service first
            if self.embeddings:
                logger.info("Initializing embedding service...")
                await self.embeddings.initialize()
                logger.info("Embedding service initialized successfully")
            
            # Create LLM provider factory (synchronous call)
            llm_factory = create_llm_provider(self.config.llm_provider)
            
            # Get the active provider instance (async call)
            self.llm_provider = await llm_factory.get_active_provider()
            
            # Check availability
            if not await self.llm_provider.is_available():
                logger.warning("LLM provider is not available")
            else:
                logger.info("LLM provider initialized and available")
                
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            
    @handle_service_exceptions(
        service_name="ChatService",
        default_return="I'm sorry, I encountered an error processing your message. Please try again."
    )
    async def process_chat_message(self, user_message: str) -> str:
        """Process a chat message and return assistant response"""
        # Step 1: Get relevant context data
        context = await self._get_chat_context(user_message)
        
        # Step 2: Generate LLM response with context
        response = await self._generate_response(user_message, context)
        
        # Step 3: Store chat exchange
        self.database.store_chat_message(user_message, response.content)
        
        return response.content
    
    async def _store_error_message(self, user_message: str, error_details: str):
        """Store error message for debugging (fallback action)"""
        error_msg = "I'm sorry, I encountered an error processing your message. Please try again."
        with safe_operation("store_error_message", log_errors=False):
            self.database.store_chat_message(user_message, error_msg)
    
    async def _get_chat_context(self, query: str, max_results: int = 10) -> ChatContext:
        """Get relevant context using 3-way hybrid approach (Limitless API + vector + SQL)"""
        vector_results = []
        sql_results = []
        limitless_results = []
        
        # Calculate result distribution based on search weights
        limitless_weight = self.config.limitless.search_weight if self.config.limitless.hybrid_search_enabled else 0.0
        remaining_weight = 1.0 - limitless_weight
        local_weight_each = remaining_weight / 2.0
        
        limitless_count = int(max_results * limitless_weight)
        vector_count = int(max_results * local_weight_each)
        sql_count = max_results - limitless_count - vector_count  # Ensure we use all available slots
        
        logger.debug(f"Search distribution: Limitless={limitless_count}, Vector={vector_count}, SQL={sql_count}")
        
        # Limitless API search (if available and enabled)
        if limitless_count > 0 and self.limitless_source and self.config.limitless.search_enabled:
            try:
                limitless_data_items = await self.limitless_source.search_lifelogs(query, limitless_count)
                # Convert DataItems to dict format for consistency
                limitless_results = [self._dataitem_to_dict(item) for item in limitless_data_items]
            except Exception as e:
                logger.warning(f"Limitless search failed: {e}")
        
        # Vector search for semantic similarity (if enabled)
        if vector_count > 0:
            try:
                if self.vector_store and self.embeddings:
                    vector_results = await self._vector_search(query, vector_count)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        # SQL search for keyword matching (if enabled)
        if sql_count > 0:
            try:
                sql_results = await self._sql_search(query, sql_count)
            except Exception as e:
                logger.warning(f"SQL search failed: {e}")
            
        return ChatContext(
            vector_results=vector_results,
            sql_results=sql_results,
            limitless_results=limitless_results,
            total_results=len(vector_results) + len(sql_results) + len(limitless_results)
        )
    
    def _dataitem_to_dict(self, item) -> Dict[str, Any]:
        """Convert DataItem to dictionary format for consistency with database results"""
        return {
            'id': f"{item.namespace}:{item.source_id}",
            'namespace': item.namespace,
            'source_id': item.source_id,
            'content': item.content,
            'metadata': item.metadata,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'updated_at': item.updated_at.isoformat() if item.updated_at else None
        }
    
    @handle_service_exceptions(
        service_name="ChatService-VectorSearch",
        default_return=[]
    )
    async def _vector_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        # Generate embedding for query
        query_embedding = await self.embeddings.embed_text(query)
        
        # Search vector store
        similar_ids = self.vector_store.search(query_embedding, k=max_results)
        
        # Get full data items from database
        if similar_ids:
            ids = [item_id for item_id, _ in similar_ids]
            return self.database.get_data_items_by_ids(ids)
        
        return []
    
    @handle_service_exceptions(
        service_name="ChatService-SQLSearch",
        default_return=[]
    )
    async def _sql_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform SQL-based keyword search"""
        # Simple keyword search in content
        with self.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                FROM data_items 
                WHERE content LIKE ? 
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f"%{query}%", max_results))
            
            from core.json_utils import DatabaseRowParser
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    async def _generate_response(self, user_message: str, context: ChatContext) -> LLMResponse:
        """Generate LLM response with context"""
        if not self.llm_provider:
            raise LLMError("LLM provider not available", "chat_service")
        
        # Build context string from search results
        context_text = self._build_context_text(context)
        
        # Create prompt with context
        prompt = f"""Based on the provided context from my personal data, please answer my question: {user_message}

If the context doesn't contain relevant information to answer the question, please say so politely."""
        
        # Generate response
        return await self.llm_provider.generate_response(
            prompt=prompt,
            context=context_text,
            max_tokens=500,
            temperature=0.7
        )
    
    def _build_context_text(self, context: ChatContext) -> str:
        """Build context text from search results"""
        context_parts = []
        
        # Track all IDs to avoid duplicates across all search types
        all_ids = set()
        
        # Add Limitless search results first (most relevant for real-time data)
        if context.limitless_results:
            context_parts.append("=== Latest Information (Limitless API Search) ===")
            for i, item in enumerate(context.limitless_results[:5], 1):
                content = item.get('content', '')[:500]  # Limit content length
                context_parts.append(f"{i}. {content}")
                all_ids.add(item.get('id'))
        
        # Add vector search results (avoiding duplicates)
        unique_vector_results = [
            item for item in context.vector_results 
            if item.get('id') not in all_ids
        ]
        
        if unique_vector_results:
            context_parts.append("\n=== Relevant Information (Semantic Search) ===")
            for i, item in enumerate(unique_vector_results[:5], 1):
                content = item.get('content', '')[:500]  # Limit content length
                context_parts.append(f"{i}. {content}")
                all_ids.add(item.get('id'))
        
        # Add SQL search results (avoiding duplicates)
        unique_sql_results = [
            item for item in context.sql_results 
            if item.get('id') not in all_ids
        ]
        
        if unique_sql_results:
            context_parts.append("\n=== Additional Relevant Information (Keyword Search) ===")
            for i, item in enumerate(unique_sql_results[:3], 1):
                content = item.get('content', '')[:500]  # Limit content length
                context_parts.append(f"{i}. {content}")
        
        if not context_parts:
            return "No relevant information found in your personal data."
        
        return "\n\n".join(context_parts)
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent chat history"""
        return self.database.get_chat_history(limit)
    
    async def close(self):
        """Close resources"""
        if self.llm_provider:
            await self.llm_provider.close()