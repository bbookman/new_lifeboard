"""
Chat service for Phase 7: Minimal Web UI

Provides hybrid data access (vector search + SQL queries) and LLM integration
for the minimal chat interface.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from core.context_builder import IntelligentContextBuilder, PrioritizedContext
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


@dataclass
class ChatRoundSummary:
    """Summary data for a complete chat processing round"""
    user_query: str
    limitless_search: Dict[str, Any] = field(default_factory=dict)
    vector_search: Dict[str, Any] = field(default_factory=dict)  
    sql_search: Dict[str, Any] = field(default_factory=dict)
    llm_response: str = ""
    total_processing_time: float = 0.0
    start_time: float = field(default_factory=time.time)


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
        self.text_processing_service = None
        self.context_builder = None
        
    async def initialize(self):
        """Initialize LLM provider and embedding service"""
        try:
            logger.info("Starting service initialization...")
            
            # Initialize text processing service
            logger.info("Initializing text processing service...")
            from services.text_processing_service import TextProcessingService
            self.text_processing_service = TextProcessingService(self.config.text_processing)
            logger.info("Text processing service initialized successfully")
            
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
            
            # Initialize intelligent context builder
            logger.info("Initializing intelligent context builder...")
            self.context_builder = IntelligentContextBuilder(
                llm_provider=self.llm_provider,
                embedding_service=self.embeddings
            )
            logger.info("Context builder initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            
    @handle_service_exceptions(
        service_name="ChatService",
        default_return="I'm sorry, I encountered an error processing your message. Please try again."
    )
    async def process_chat_message(self, user_message: str) -> str:
        """Process a chat message and return assistant response"""
        logger.info(f"Processing chat message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
        
        # Initialize summary tracking
        summary = ChatRoundSummary(user_query=user_message)
        
        # Step 1: Get relevant context data
        logger.debug("Getting chat context...")
        context = await self._get_chat_context(user_message, summary=summary)
        logger.info(f"Context retrieved: {context.total_results} total results (vector: {len(context.vector_results)}, sql: {len(context.sql_results)}, limitless: {len(context.limitless_results)})")
        
        # Step 2: Build intelligent prioritized context
        logger.debug("Building intelligent context...")
        if self.context_builder:
            prioritized_context = await self.context_builder.build_prioritized_context(
                limitless_results=context.limitless_results,
                vector_results=context.vector_results,
                sql_results=context.sql_results,
                query=user_message,
                max_context_length=self.config.llm_provider.max_context_length if hasattr(self.config.llm_provider, 'max_context_length') else 4000
            )
            logger.info(f"Intelligent context built: {prioritized_context.total_items} items, "
                       f"{len(prioritized_context.summary)} char summary, "
                       f"{prioritized_context.processing_time:.3f}s")
        else:
            logger.warning("Context builder not available, falling back to basic context")
            prioritized_context = None

        # Step 3: Generate LLM response with intelligent context
        logger.debug("Generating LLM response...")
        response = await self._generate_response(user_message, context, prioritized_context)
        logger.info(f"LLM response generated: {len(response.content)} characters")
        
        # Store response in summary
        summary.llm_response = response.content
        
        # Step 4: Extract entities and topics from context for memory
        entities_mentioned = []
        topics = []
        processing_time_ms = int((time.time() - summary.start_time) * 1000)
        
        if prioritized_context:
            # Extract entities and topics from the intelligent context
            entities_mentioned = self._extract_entities_from_context(prioritized_context)
            topics = self._extract_topics_from_context(prioritized_context)
        
        # Step 5: Store chat exchange with enhanced memory
        logger.debug("Storing chat exchange with conversation memory...")
        session_id = self.database.store_chat_message(
            user_message=user_message,
            assistant_response=response.content,
            context_summary=prioritized_context.summary if prioritized_context else None,
            entities_mentioned=entities_mentioned if entities_mentioned else None,
            topics=topics if topics else None,
            processing_time_ms=processing_time_ms
        )
        logger.info(f"Chat message processed successfully (session: {session_id[:8]}...)")
        
        # Step 4: Log summary if enabled
        try:
            if (self.text_processing_service and 
                hasattr(self.text_processing_service, 'config') and 
                self.text_processing_service.config.enable_chat_round_summary):
                self._log_chat_round_summary(summary)
        except Exception as e:
            logger.warning(f"Failed to log chat round summary: {e}")
        
        return response.content
    
    async def _store_error_message(self, user_message: str, error_details: str):
        """Store error message for debugging (fallback action)"""
        error_msg = "I'm sorry, I encountered an error processing your message. Please try again."
        with safe_operation("store_error_message", log_errors=False):
            self.database.store_chat_message(user_message, error_msg)
    
    async def _get_chat_context(self, query: str, max_results: int = 10, summary: Optional[ChatRoundSummary] = None) -> ChatContext:
        """Get relevant context using 3-way hybrid approach (Limitless API + vector + SQL)"""
        import time
        start_time = time.time()
        
        logger.debug(f"Getting chat context for query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
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
        
        logger.info(f"Search weights: Limitless={limitless_weight:.2f} ({limitless_count} results), "
                   f"Vector={local_weight_each:.2f} ({vector_count} results), "
                   f"SQL={local_weight_each:.2f} ({sql_count} results)")
        
        # Limitless API search (if available and enabled)
        if limitless_count > 0 and self.limitless_source and self.config.limitless.search_enabled:
            try:
                limitless_start = time.time()
                limitless_data_items = await self.limitless_source.search_lifelogs(query, limitless_count)
                # Convert DataItems to dict format for consistency
                limitless_results = [self._dataitem_to_dict(item) for item in limitless_data_items]
                limitless_duration = time.time() - limitless_start
                logger.info(f"Limitless search completed: {len(limitless_results)} results in {limitless_duration:.3f}s")
                
                # Collect summary data
                if summary:
                    summary.limitless_search['content'] = self._extract_content_from_results(limitless_results)
                    summary.limitless_search['count'] = len(limitless_results)
                    summary.limitless_search['duration'] = limitless_duration
                    
            except Exception as e:
                logger.warning(f"Limitless search failed: {str(e)}")
                if summary:
                    summary.limitless_search['error'] = self._format_error_message(e)
        else:
            logger.debug("Limitless search skipped (disabled or not available)")
            if summary:
                summary.limitless_search['content'] = "Skipped (disabled or not available)"
        
        # Vector search for semantic similarity (if enabled)
        if vector_count > 0:
            try:
                if self.vector_store and self.embeddings:
                    vector_start = time.time()
                    vector_results = await self._vector_search(query, vector_count)
                    vector_duration = time.time() - vector_start
                    logger.info(f"Vector search completed: {len(vector_results)} results in {vector_duration:.3f}s")
                    
                    # Collect summary data
                    if summary:
                        summary.vector_search['content'] = self._extract_content_from_results(vector_results)
                        summary.vector_search['count'] = len(vector_results)
                        summary.vector_search['duration'] = vector_duration
                else:
                    logger.debug("Vector search skipped (vector store or embeddings not available)")
                    if summary:
                        summary.vector_search['content'] = "Skipped (vector store or embeddings not available)"
            except Exception as e:
                logger.warning(f"Vector search failed: {str(e)}")
                if summary:
                    summary.vector_search['error'] = self._format_error_message(e)
        else:
            logger.debug("Vector search skipped (count = 0)")
            if summary:
                summary.vector_search['content'] = "Skipped (count = 0)"
        
        # SQL search for keyword matching (if enabled)
        if sql_count > 0:
            try:
                sql_start = time.time()
                sql_results = await self._sql_search(query, sql_count, summary)
                sql_duration = time.time() - sql_start
                logger.info(f"SQL search completed: {len(sql_results)} results in {sql_duration:.3f}s")
                
                # Collect summary data (SQL method will handle its own summary data)
                if summary and 'results' not in summary.sql_search:
                    summary.sql_search['results'] = self._extract_content_from_results(sql_results)
                    
            except Exception as e:
                logger.warning(f"SQL search failed: {str(e)}")
                if summary:
                    summary.sql_search['error'] = self._format_error_message(e)
        else:
            logger.debug("SQL search skipped (count = 0)")
            if summary:
                summary.sql_search['query'] = "Skipped (count = 0)"
                summary.sql_search['results'] = "Not executed"
        
        total_duration = time.time() - start_time
        total_results = len(vector_results) + len(sql_results) + len(limitless_results)
        
        logger.info(f"Context retrieval completed: {total_results} total results "
                   f"(limitless: {len(limitless_results)}, vector: {len(vector_results)}, sql: {len(sql_results)}) "
                   f"in {total_duration:.3f}s")
        
        return ChatContext(
            vector_results=vector_results,
            sql_results=sql_results,
            limitless_results=limitless_results,
            total_results=total_results
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
        import time
        start_time = time.time()
        
        logger.debug(f"Vector search for query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
        # Generate embedding for query
        embed_start = time.time()
        query_embedding = await self.embeddings.embed_text(query)
        embed_duration = time.time() - embed_start
        logger.debug(f"Query embedding generated in {embed_duration:.3f}s")
        
        # Search vector store
        search_start = time.time()
        similar_ids = self.vector_store.search(query_embedding, k=max_results)
        search_duration = time.time() - search_start
        logger.debug(f"Vector store search completed: {len(similar_ids) if similar_ids else 0} similar items found in {search_duration:.3f}s")
        
        # Get full data items from database
        if similar_ids:
            db_start = time.time()
            ids = [item_id for item_id, _ in similar_ids]
            similarities = [score for _, score in similar_ids]
            results = self.database.get_data_items_by_ids(ids)
            db_duration = time.time() - db_start
            
            total_duration = time.time() - start_time
            logger.debug(f"Database lookup completed: {len(results)} items retrieved in {db_duration:.3f}s")
            logger.debug(f"Top 3 similarity scores: {similarities[:3]}")
            logger.info(f"Vector search completed: {len(results)} results in {total_duration:.3f}s")
            
            return results
        
        total_duration = time.time() - start_time
        logger.info(f"Vector search completed: 0 results in {total_duration:.3f}s")
        return []
    
    @handle_service_exceptions(
        service_name="ChatService-SQLSearch",
        default_return=[]
    )
    async def _sql_search(self, query: str, max_results: int, summary: Optional[ChatRoundSummary] = None) -> List[Dict[str, Any]]:
        """Perform SQL-based keyword search with enhanced keyword extraction"""
        import time
        start_time = time.time()
        
        logger.info(f"SQL search query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
        # Extract keywords from query
        if not self.text_processing_service:
            logger.warning("Text processing service not available, falling back to simple search")
            return await self._simple_sql_search(query, max_results, summary)
        
        keywords = self.text_processing_service.extract_keywords(query)
        
        if not keywords:
            logger.info("No keywords extracted from query, returning empty results")
            return []
        
        logger.info(f"Extracted keywords: {keywords}")
        
        # Build dynamic SQL query with keyword scoring
        try:
            with self.database.get_connection() as conn:
                # Create LIKE conditions for each keyword
                like_conditions = []
                score_conditions = []
                params = []
                
                for keyword in keywords:
                    like_pattern = f"%{keyword}%"
                    like_conditions.append("content LIKE ?")
                    score_conditions.append("CASE WHEN content LIKE ? THEN 1 ELSE 0 END")
                    params.extend([like_pattern, like_pattern])
                
                # Determine search logic (AND vs OR)
                search_mode = self.text_processing_service.config.keyword_search_mode
                where_operator = " AND " if search_mode == "AND" else " OR "
                where_clause = f"({where_operator.join(like_conditions)})"
                
                # Build scoring clause
                score_clause = " + ".join(score_conditions)
                
                # Complete SQL query
                sql_query = f"""
                    SELECT id, namespace, source_id, content, metadata, created_at, updated_at,
                           ({score_clause}) as keyword_score
                    FROM data_items 
                    WHERE {where_clause}
                    ORDER BY keyword_score DESC, updated_at DESC
                    LIMIT ?
                """
                
                params.append(max_results)
                
                # Collect summary data (don't truncate SQL query)
                if summary:
                    summary.sql_search['query'] = sql_query.strip()
                
                logger.debug(f"Generated SQL: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}")
                logger.debug(f"SQL parameters: {len(params)} params for {len(keywords)} keywords")
                
                cursor = conn.execute(sql_query, params)
                rows = cursor.fetchall()
                
                # Parse results
                from core.json_utils import DatabaseRowParser
                results = DatabaseRowParser.parse_rows_with_metadata([dict(row) for row in rows])
                
                duration = time.time() - start_time
                logger.info(f"SQL search returned {len(results)} results in {duration:.3f}s")
                
                # Log top results for debugging
                if results:
                    top_scores = [row.get('keyword_score', 0) for row in rows[:3]]
                    logger.debug(f"Top 3 keyword scores: {top_scores}")
                
                return results
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Enhanced SQL search failed: {str(e)} in {duration:.3f}s")
            # Fallback to simple search
            logger.info("Falling back to simple SQL search")
            return await self._simple_sql_search(query, max_results, summary)
    
    async def _simple_sql_search(self, query: str, max_results: int, summary: Optional[ChatRoundSummary] = None) -> List[Dict[str, Any]]:
        """Fallback simple SQL search for when keyword extraction fails"""
        import time
        start_time = time.time()
        
        logger.debug(f"Performing simple SQL search for query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
        with self.database.get_connection() as conn:
            simple_query = """
                SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                FROM data_items 
                WHERE content LIKE ? 
                ORDER BY updated_at DESC
                LIMIT ?
            """
            
            # Collect summary data (don't truncate SQL query)
            if summary:
                summary.sql_search['query'] = f"Simple search: {simple_query.strip()}"
            
            cursor = conn.execute(simple_query, (f"%{query}%", max_results))
            
            from core.json_utils import DatabaseRowParser
            results = DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
            
            duration = time.time() - start_time
            logger.debug(f"Simple SQL search returned {len(results)} results in {duration:.3f}s")
            
            return results
    
    async def _generate_response(self, user_message: str, context: ChatContext, prioritized_context: Optional[PrioritizedContext] = None) -> LLMResponse:
        """Generate LLM response with context"""
        import time
        start_time = time.time()
        
        logger.debug(f"Generating LLM response for message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
        
        if not self.llm_provider:
            raise LLMError("LLM provider not available", "chat_service")
        
        # Use intelligent context if available, otherwise fall back to basic context
        context_start = time.time()
        if prioritized_context and self.context_builder:
            context_text = self.context_builder.format_context_for_llm(prioritized_context)
            logger.info(f"Using intelligent context: {len(context_text)} characters")
        else:
            context_text = self._build_context_text(context)
            logger.info(f"Using basic context: {len(context_text)} characters")
        
        context_duration = time.time() - context_start
        logger.info(f"Context text prepared in {context_duration:.3f}s")
        logger.debug(f"Context preview: {context_text[:200]}{'...' if len(context_text) > 200 else ''}")
        
        # Create enhanced prompt with better instructions
        if prioritized_context:
            prompt = f"""You are a helpful personal AI assistant with access to the user's conversations, activities, and relevant information. 

User's question: {user_message}

Please provide a helpful, practical response based on the context below. Use common sense reasoning to draw logical conclusions from the evidence. When conversations show consistent patterns (like repeatedly calling for "Peach" in pet contexts, or discussing a pet's care), treat that as reliable evidence of ownership or relationships.

Be confident in your conclusions when the evidence clearly supports them. Avoid unnecessary hedging or qualification unless there's genuine ambiguity. If someone is consistently caring for, calling for, and discussing a pet, they effectively have that pet regardless of formal ownership details."""
        else:
            prompt = f"""Based on the provided context from my personal data, please answer my question: {user_message}

If the context doesn't contain relevant information to answer the question, please say so politely."""
        
        logger.debug(f"Generated prompt length: {len(prompt)} characters")
        
        # Generate response
        llm_start = time.time()
        response = await self.llm_provider.generate_response(
            prompt=prompt,
            context=context_text,
            max_tokens=500,
            temperature=0.7
        )
        llm_duration = time.time() - llm_start
        
        total_duration = time.time() - start_time
        logger.info(f"LLM response generated: {len(response.content)} characters in {llm_duration:.3f}s")
        logger.debug(f"Response preview: {response.content[:100]}{'...' if len(response.content) > 100 else ''}")
        logger.info(f"Total response generation time: {total_duration:.3f}s")
        
        return response
    
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
            logger.debug(f"Added {len(context.limitless_results)} Limitless results to context")
        
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
            logger.debug(f"Added {len(unique_vector_results)} vector results to context")
        
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
            logger.debug(f"Added {len(unique_sql_results)} SQL results to context")
        
        if not context_parts:
            logger.debug("No context parts generated, returning default message")
            return "No relevant information found in your personal data."
        
        final_context = "\n\n".join(context_parts)
        logger.debug(f"Final context built: {len(context_parts)} sections, {len(final_context)} total characters")
        
        return final_context
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent chat history"""
        return self.database.get_chat_history(limit)
    
    async def close(self):
        """Close resources"""
        if self.llm_provider:
            await self.llm_provider.close()
    
    def _truncate_text(self, text: str, max_length: int = 100) -> str:
        """Truncate text to specified length with ellipsis if needed"""
        if not text:
            return ""
        text_str = str(text).strip()
        if len(text_str) <= max_length:
            return text_str
        return text_str[:max_length] + "..."
    
    def _extract_content_from_results(self, results: List[Dict[str, Any]], max_items: int = 3) -> str:
        """Extract and concatenate content from search results"""
        if not results:
            return "No results found"
        
        content_pieces = []
        for i, result in enumerate(results[:max_items]):
            content = result.get('content', '')
            if content:
                # Take first 50 chars of each result
                piece = self._truncate_text(content, 50)
                content_pieces.append(piece)
        
        if content_pieces:
            combined = " | ".join(content_pieces)
            return self._truncate_text(combined, 100)
        else:
            return f"{len(results)} results (no content available)"
    
    def _format_error_message(self, error: Exception) -> str:
        """Format error message for summary logging"""
        error_str = str(error)
        return self._truncate_text(f"Error: {error_str}", 100)
    
    def _log_chat_round_summary(self, summary: ChatRoundSummary):
        """Log detailed chat round summary for debugging"""
        if not hasattr(self, 'text_processing_service') or not self.text_processing_service:
            return
        
        # Check if summary logging is enabled
        if not self.text_processing_service.config.enable_chat_round_summary:
            return
        
        # Calculate total time
        summary.total_processing_time = time.time() - summary.start_time
        
        separator = "*" * 39
        summary_text = f"""
{separator}
CHAT ROUND SUMMARY
{separator}
User query: {self._truncate_text(summary.user_query, 100)}

Steps executed:
1. Limitless API search: {summary.limitless_search.get('content', summary.limitless_search.get('error', 'Not executed'))}
2. Vector search: {summary.vector_search.get('content', summary.vector_search.get('error', 'Not executed'))}
3. SQL search query: {summary.sql_search.get('query', 'Not executed')}
4. SQL search results: {summary.sql_search.get('results', summary.sql_search.get('error', 'No results'))}

LLM Response: {self._truncate_text(summary.llm_response, 100)}
Total processing time: {summary.total_processing_time:.3f}s
{separator}
"""
        
        logger.debug(summary_text)
    
    def _extract_entities_from_context(self, context: PrioritizedContext) -> List[str]:
        """Extract entities mentioned in the context for conversation memory"""
        entities = set()
        
        # Simple entity extraction - look for patterns in context items
        for item in context.items[:10]:  # Limit to first 10 items
            content = item.content.lower()
            
            # Extract potential person names (words starting with capital letters)
            import re
            # Simple pattern for names - capital letter followed by lowercase
            name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
            potential_names = re.findall(name_pattern, item.content)
            
            # Filter out common words that aren't names
            common_words = {'The', 'This', 'That', 'Then', 'There', 'They', 'Today', 'Tomorrow', 'Yesterday'}
            names = [name for name in potential_names if name not in common_words and len(name) > 2]
            entities.update(names)
            
            # Extract organizations/companies (words ending in common business suffixes)
            org_pattern = r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*(?:\s+(?:Inc|LLC|Corp|Company|Co|Ltd|Corporation))\b'
            orgs = re.findall(org_pattern, item.content)
            entities.update(orgs)
        
        # Limit to most relevant entities
        return list(entities)[:10]
    
    def _extract_topics_from_context(self, context: PrioritizedContext) -> List[str]:
        """Extract topics from the context for conversation memory"""
        topics = set()
        
        # Extract topics from source attribution and content
        for source, count in context.source_attribution.items():
            if source == 'limitless' and count > 0:
                topics.add('personal_conversations')
            elif source == 'vector' and count > 0:
                topics.add('related_information')
            elif source == 'sql' and count > 0:
                topics.add('keyword_search')
        
        # Extract keywords from context summary
        if context.summary:
            # Simple keyword extraction from summary
            import re
            summary_words = re.findall(r'\b[a-zA-Z]{4,}\b', context.summary.lower())
            
            # Filter out common words
            stop_words = {'this', 'that', 'with', 'from', 'they', 'were', 'been', 'have', 'will', 'would', 'could', 'should'}
            keywords = [word for word in summary_words if word not in stop_words]
            
            # Add most frequent keywords as topics
            from collections import Counter
            word_counts = Counter(keywords)
            top_keywords = [word for word, count in word_counts.most_common(5)]
            topics.update(top_keywords)
        
        return list(topics)[:8]