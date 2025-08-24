"""
Chat service for Phase 7: Minimal Web UI

Provides hybrid data access (vector search + SQL queries) and LLM integration
for the minimal chat interface.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.database import DatabaseService
from services.debug_mixin import ServiceDebugMixin
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from llm.factory import create_llm_provider
from llm.base import LLMResponse, LLMError
from config.models import AppConfig
from core.exception_handling import handle_service_exceptions, safe_operation

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """Context data for chat response generation"""
    vector_results: List[Dict[str, Any]]
    sql_results: List[Dict[str, Any]]
    total_results: int


class ChatService(ServiceDebugMixin):
    """Service for handling chat interactions with hybrid data access"""
    
    def __init__(self, config: AppConfig, database: DatabaseService, 
                 vector_store: VectorStoreService, embeddings: EmbeddingService):
        super().__init__("chat_service")
        self.config = config
        self.database = database
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.llm_provider = None
        
        # Log service initialization
        self.log_service_call("__init__", {
            "database_available": database is not None,
            "vector_store_available": vector_store is not None,
            "embeddings_available": embeddings is not None
        })
        
    async def initialize(self):
        """Initialize LLM provider and embedding service"""
        self.log_service_call("initialize")
        
        try:
            logger.info("Starting service initialization...")
            
            # Initialize embedding service first
            if self.embeddings:
                logger.info("Initializing embedding service...")
                embedding_start = time.time()
                await self.embeddings.initialize()
                embedding_duration = (time.time() - embedding_start) * 1000
                self.log_service_performance_metric("embedding_init_time", embedding_duration, "ms")
                logger.info("Embedding service initialized successfully")
            
            # Create LLM provider factory (synchronous call)
            llm_start = time.time()
            llm_factory = create_llm_provider(self.config.llm_provider)
            
            # Get the active provider instance (async call)
            self.llm_provider = await llm_factory.get_active_provider()
            llm_duration = (time.time() - llm_start) * 1000
            self.log_service_performance_metric("llm_init_time", llm_duration, "ms")
            
            # Check availability
            if not await self.llm_provider.is_available():
                logger.warning("LLM provider is not available")
            else:
                logger.info("LLM provider initialized and available")
                
        except Exception as e:
            self.log_service_error("initialize", e, {
                "llm_provider_config": self.config.llm_provider.provider_type.value if self.config.llm_provider else None
            })
            logger.error(f"Failed to initialize services: {e}")
            raise
            
    @handle_service_exceptions(
        service_name="ChatService",
        default_return="I'm sorry, I encountered an error processing your message. Please try again."
    )
    async def process_chat_message(self, user_message: str) -> str:
        """Process a chat message and return assistant response"""
        self.log_service_call("process_chat_message", {
            "message_length": len(user_message),
            "has_llm_provider": self.llm_provider is not None
        })
        
        total_start = time.time()
        
        try:
            # Step 1: Get relevant context data
            context_start = time.time()
            context = await self._get_chat_context(user_message)
            context_duration = (time.time() - context_start) * 1000
            self.log_service_performance_metric("context_retrieval_time", context_duration, "ms")
            
            # Step 2: Generate LLM response with context
            llm_start = time.time()
            response = await self._generate_response(user_message, context)
            llm_duration = (time.time() - llm_start) * 1000
            self.log_service_performance_metric("llm_generation_time", llm_duration, "ms")
            
            # Step 3: Store chat exchange
            db_start = time.time()
            self.database.store_chat_message(user_message, response.content)
            db_duration = (time.time() - db_start) * 1000
            self.log_database_operation("INSERT", "chat_messages", db_duration)
            
            total_duration = (time.time() - total_start) * 1000
            self.log_service_performance_metric("total_chat_processing_time", total_duration, "ms")
            
            return response.content
            
        except Exception as e:
            self.log_service_error("process_chat_message", e, {
                "message_length": len(user_message),
                "has_context": 'context' in locals(),
                "context_results": getattr(locals().get('context'), 'total_results', 0)
            })
            raise
    
    async def _store_error_message(self, user_message: str, error_details: str):
        """Store error message for debugging (fallback action)"""
        error_msg = "I'm sorry, I encountered an error processing your message. Please try again."
        with safe_operation("store_error_message", log_errors=False):
            self.database.store_chat_message(user_message, error_msg)
    
    async def _get_chat_context(self, query: str, max_results: int = 10) -> ChatContext:
        """Get relevant context using hybrid approach (vector + SQL)"""
        self.log_service_call("_get_chat_context", {
            "query_length": len(query),
            "max_results": max_results
        })
        
        vector_results = []
        sql_results = []
        
        try:
            # Vector search for semantic similarity
            if self.vector_store and self.embeddings:
                vector_start = time.time()
                vector_results = await self._vector_search(query, max_results // 2)
                vector_duration = (time.time() - vector_start) * 1000
                self.log_service_performance_metric("vector_search_time", vector_duration, "ms")
        except Exception as e:
            self.log_service_error("_get_chat_context_vector_search", e, {
                "query_length": len(query),
                "max_results": max_results // 2
            })
            logger.warning(f"Vector search failed: {e}")
        
        try:
            # SQL search for keyword matching
            sql_start = time.time()
            sql_results = await self._sql_search(query, max_results // 2)
            sql_duration = (time.time() - sql_start) * 1000
            self.log_service_performance_metric("sql_search_time", sql_duration, "ms")
        except Exception as e:
            self.log_service_error("_get_chat_context_sql_search", e, {
                "query_length": len(query),
                "max_results": max_results // 2
            })
            logger.warning(f"SQL search failed: {e}")
            
        return ChatContext(
            vector_results=vector_results,
            sql_results=sql_results,
            total_results=len(vector_results) + len(sql_results)
        )
    
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
        self.log_service_call("_sql_search", {
            "query_length": len(query),
            "max_results": max_results
        })
        
        # Simple keyword search in content
        db_start = time.time()
        with self.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                FROM data_items 
                WHERE content LIKE ? 
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f"%{query}%", max_results))
            
            results = cursor.fetchall()
            db_duration = (time.time() - db_start) * 1000
            self.log_database_operation("SELECT", "data_items", db_duration)
            
            from core.json_utils import DatabaseRowParser
            parsed_results = DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in results]
            )
            
            self.log_service_performance_metric("sql_search_results_count", len(parsed_results), "count")
            return parsed_results
    
    async def _generate_response(self, user_message: str, context: ChatContext) -> LLMResponse:
        """Generate LLM response with context"""
        self.log_service_call("_generate_response", {
            "message_length": len(user_message),
            "context_results": context.total_results,
            "vector_results": len(context.vector_results),
            "sql_results": len(context.sql_results)
        })
        
        if not self.llm_provider:
            error = LLMError("LLM provider not available", "chat_service")
            self.log_service_error("_generate_response", error, {
                "context_results": context.total_results
            })
            raise error
        
        # Build context string from search results
        context_text = self._build_context_text(context)
        
        # Create prompt with context
        prompt = f"""Based on the provided context from my personal data, please answer my question: {user_message}

If the context doesn't contain relevant information to answer the question, please say so politely."""
        
        # Generate response
        llm_start = time.time()
        response = await self.llm_provider.generate_response(
            prompt=prompt,
            context=context_text,
            max_tokens=500,
            temperature=0.7
        )
        llm_duration = (time.time() - llm_start) * 1000
        
        self.log_external_api_call(
            "llm_provider",
            f"/{self.config.llm_provider.provider_type.value if self.config.llm_provider else 'unknown'}",
            200,  # Assume success if no exception
            llm_duration
        )
        
        self.log_service_performance_metric("llm_response_length", len(response.content), "characters")
        return response
    
    def _build_context_text(self, context: ChatContext) -> str:
        """Build context text from search results"""
        context_parts = []
        
        # Add vector search results
        if context.vector_results:
            context_parts.append("=== Relevant Information (Semantic Search) ===")
            for i, item in enumerate(context.vector_results[:5], 1):
                content = item.get('content', '')[:500]  # Limit content length
                context_parts.append(f"{i}. {content}")
        
        # Add SQL search results (avoiding duplicates)
        vector_ids = {item.get('id') for item in context.vector_results}
        unique_sql_results = [
            item for item in context.sql_results 
            if item.get('id') not in vector_ids
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
        self.log_service_call("get_chat_history", {"limit": limit})
        
        db_start = time.time()
        history = self.database.get_chat_history(limit)
        db_duration = (time.time() - db_start) * 1000
        
        self.log_database_operation("SELECT", "chat_messages", db_duration)
        self.log_service_performance_metric("chat_history_count", len(history), "count")
        
        return history
    
    async def close(self):
        """Close resources"""
        self.log_service_call("close")
        
        try:
            if self.llm_provider:
                close_start = time.time()
                await self.llm_provider.close()
                close_duration = (time.time() - close_start) * 1000
                self.log_service_performance_metric("llm_provider_close_time", close_duration, "ms")
        except Exception as e:
            self.log_service_error("close", e)
            raise