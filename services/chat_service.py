"""
Chat service for Phase 7: Minimal Web UI

Provides hybrid data access (vector search + SQL queries) and LLM integration
for the minimal chat interface.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import numpy as np

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from llm.factory import create_llm_provider
from llm.base import LLMResponse, LLMError
from config.models import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """Context data for chat response generation"""
    vector_results: List[Dict[str, Any]]
    sql_results: List[Dict[str, Any]]
    total_results: int


class ChatService:
    """Service for handling chat interactions with hybrid data access"""
    
    def __init__(self, config: AppConfig, database: DatabaseService, 
                 vector_store: VectorStoreService, embeddings: EmbeddingService):
        self.config = config
        self.database = database
        self.vector_store = vector_store
        self.embeddings = embeddings
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
            
    async def process_chat_message(self, user_message: str) -> str:
        """Process a chat message and return assistant response"""
        try:
            logger.info(f"Chat Debug - Processing message: '{user_message}'")
            
            # Log database and data source statistics first
            db_stats = self.database.get_database_stats()
            logger.info(f"Chat Debug - Database stats: {db_stats}")
            
            # Log DATA SOURCES QUERY RESULTS (truncated for brevity)
            logger.info("=== DATA SOURCES QUERY RESULTS (truncated for brevity) ===")
            try:
                with self.database.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT namespace, source_type, metadata, item_count, is_active
                        FROM data_sources
                        ORDER BY item_count DESC
                        LIMIT 10
                    """)
                    
                    data_sources = cursor.fetchall()
                    if data_sources:
                        for i, source in enumerate(data_sources, 1):
                            logger.info(f"Data Source {i}:")
                            logger.info(f"  Namespace: {source['namespace']} | Type: {source['source_type']}")
                            logger.info(f"  Item Count: {source['item_count']} | Active: {source['is_active']}")
                            if source['metadata']:
                                try:
                                    import json
                                    metadata = json.loads(source['metadata'])
                                    logger.debug(f"  Metadata: {metadata}")
                                except:
                                    logger.debug(f"  Raw Metadata: {source['metadata']}")
                            logger.info("  " + "-" * 60)
                    else:
                        logger.warning("No data sources found in database")
            except Exception as e:
                logger.error(f"Failed to query data sources: {e}")
            
            # Log vector store statistics
            if self.vector_store:
                vector_stats = self.vector_store.get_stats()
                logger.info(f"Chat Debug - Vector store stats: {vector_stats}")
            
            # Step 1: Get relevant context data
            context = await self._get_chat_context(user_message)
            
            # Step 2: Generate LLM response with context
            response = await self._generate_response(user_message, context)
            
            # Step 3: Store chat exchange
            self.database.store_chat_message(user_message, response.content)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            error_msg = "I'm sorry, I encountered an error processing your message. Please try again."
            
            # Store error exchange for debugging
            try:
                self.database.store_chat_message(user_message, error_msg)
            except Exception:
                pass  # Don't let storage errors compound the issue
                
            return error_msg
    
    async def _get_chat_context(self, query: str, max_results: int = 10) -> ChatContext:
        """Get relevant context using hybrid approach (vector + SQL)"""
        logger.info(f"Chat Debug - Starting context retrieval for query: '{query}'")
        logger.info(f"Chat Debug - Search parameters: max_results={max_results}, vector_limit={max_results // 2}, sql_limit={max_results // 2}")
        
        vector_results = []
        sql_results = []
        
        try:
            # Vector search for semantic similarity
            if self.vector_store and self.embeddings:
                logger.info("Chat Debug - Performing vector search...")
                vector_results = await self._vector_search(query, max_results // 2)
                logger.info(f"Chat Debug - Vector search returned {len(vector_results)} results")
            else:
                logger.warning("Chat Debug - Vector search skipped: vector_store or embeddings not available")
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
        
        try:
            # SQL search for keyword matching
            logger.info("Chat Debug - Performing SQL search...")
            sql_results = await self._sql_search(query, max_results // 2)
            logger.info(f"Chat Debug - SQL search returned {len(sql_results)} results")
        except Exception as e:
            logger.warning(f"SQL search failed: {e}")
            
        total_results = len(vector_results) + len(sql_results)
        logger.info(f"Chat Debug - Total search results: {total_results} (vector: {len(vector_results)}, sql: {len(sql_results)})")
        
        return ChatContext(
            vector_results=vector_results,
            sql_results=sql_results,
            total_results=total_results
        )
    
    async def _vector_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        try:
            logger.info(f"Chat Debug - Generating embedding for query: '{query}'")
            # Generate embedding for query
            query_embedding = await self.embeddings.embed_text(query)
            logger.info(f"Chat Debug - Query embedding generated, dimension: {len(query_embedding) if query_embedding is not None else 'None'}")
            
            # Log embedding details for debugging
            if query_embedding is not None and len(query_embedding) > 0:
                embedding_stats = {
                    'dimension': len(query_embedding),
                    'norm': float(np.linalg.norm(query_embedding)),
                    'min': float(min(query_embedding)),
                    'max': float(max(query_embedding)),
                    'mean': float(np.mean(query_embedding)),
                    'std': float(np.std(query_embedding))
                }
                logger.debug(f"Chat Debug - Embedding statistics: {embedding_stats}")
            
            # Search vector store
            logger.info(f"Chat Debug - Searching vector store with k={max_results}")
            
            # Log what namespaces are available in vector store
            available_namespaces = set()
            for vector_id in self.vector_store.vectors.keys():
                namespace = vector_id.split(':', 1)[0] if ':' in vector_id else 'unknown'
                available_namespaces.add(namespace)
            logger.info(f"Chat Debug - Available namespaces in vector store: {sorted(available_namespaces)}")
            
            similar_ids = self.vector_store.search(query_embedding, k=max_results)
            logger.info(f"Chat Debug - Vector store returned {len(similar_ids) if similar_ids else 0} similar items")
            
            if similar_ids:
                # Log similarity scores for debugging
                for i, (item_id, score) in enumerate(similar_ids[:3]):
                    logger.debug(f"Chat Debug - Top result {i+1}: ID={item_id}, similarity={score:.4f}")
                
                # Get full data items from database
                ids = [item_id for item_id, _ in similar_ids]
                logger.info(f"Chat Debug - Fetching full data for {len(ids)} IDs: {ids[:3]}...")
                results = self.database.get_data_items_by_ids(ids)
                logger.info(f"Chat Debug - Retrieved {len(results)} full data items from database")
                
                # Detailed analysis of retrieved content
                if results:
                    namespaces = {item.get('namespace') for item in results}
                    content_lengths = [len(item.get('content', '')) for item in results]
                    logger.info(f"Chat Debug - Result analysis: namespaces={sorted(namespaces)}, content_lengths={content_lengths}")
                    
                    # Log detailed VECTOR SEARCH RESULTS (truncated to 10 records for brevity)
                    logger.info("=== VECTOR SEARCH RESULTS (truncated to 10 records for brevity) ===")
                    for i, (item, (vector_id, similarity_score)) in enumerate(zip(results[:10], similar_ids[:10])):
                        content = item.get('content', '')
                        content_preview = content[:150] + '...' if len(content) > 150 else content
                        metadata = item.get('metadata', {})
                        
                        logger.info(f"Vector Result {i+1}:")
                        logger.info(f"  ID: {item.get('id')} (similarity: {similarity_score:.4f})")
                        logger.info(f"  Namespace: {item.get('namespace')} | Source: {item.get('source_id')}")
                        logger.info(f"  Content Length: {len(content)} chars")
                        logger.info(f"  Content Preview: '{content_preview}'")
                        if metadata:
                            logger.debug(f"  Metadata: {metadata}")
                        logger.info(f"  Created: {item.get('created_at')} | Updated: {item.get('updated_at')}")
                        logger.info("  " + "-" * 80)
                    
                    if len(results) > 10:
                        logger.info(f"... and {len(results) - 10} more vector results")
                else:
                    logger.warning("Chat Debug - No data items retrieved despite having vector matches!")
                
                return results
            else:
                logger.info("Chat Debug - No similar items found in vector search")
            
        except Exception as e:
            logger.warning(f"Vector search error: {e}")
            
        return []
    
    async def _sql_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform SQL-based keyword search"""
        try:
            search_pattern = f"%{query}%"
            logger.debug(f"Chat Debug - SQL search pattern: '{search_pattern}', limit: {max_results}")
            
            # Simple keyword search in content
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                    FROM data_items 
                    WHERE content LIKE ? 
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (search_pattern, max_results))
                
                results = []
                for row in cursor.fetchall():
                    item = dict(row)
                    if item['metadata']:
                        try:
                            import json
                            item['metadata'] = json.loads(item['metadata'])
                        except json.JSONDecodeError:
                            item['metadata'] = None
                    results.append(item)
                
                logger.info(f"Chat Debug - SQL search found {len(results)} matching items")
                
                # Analyze SQL results
                if results:
                    sql_namespaces = {item.get('namespace') for item in results}
                    sql_content_lengths = [len(item.get('content', '')) for item in results]
                    logger.info(f"Chat Debug - SQL result analysis: namespaces={sorted(sql_namespaces)}, content_lengths={sql_content_lengths}")
                    
                    # Log detailed SQL SEARCH RESULTS (truncated to 10 records for brevity)
                    logger.info("=== SQL SEARCH RESULTS (truncated to 10 records for brevity) ===")
                    for i, item in enumerate(results[:10]):
                        content = item.get('content', '')
                        content_preview = content[:150] + '...' if len(content) > 150 else content
                        metadata = item.get('metadata', {})
                        
                        logger.info(f"SQL Result {i+1}:")
                        logger.info(f"  ID: {item.get('id')}")
                        logger.info(f"  Namespace: {item.get('namespace')} | Source: {item.get('source_id')}")
                        logger.info(f"  Content Length: {len(content)} chars")
                        logger.info(f"  Content Preview: '{content_preview}'")
                        if metadata:
                            logger.debug(f"  Metadata: {metadata}")
                        logger.info(f"  Created: {item.get('created_at')} | Updated: {item.get('updated_at')}")
                        logger.info("  " + "-" * 80)
                    
                    if len(results) > 10:
                        logger.info(f"... and {len(results) - 10} more SQL results")
                else:
                    logger.info(f"Chat Debug - SQL search with pattern '%{query}%' returned no results")
                
                return results
                
        except Exception as e:
            logger.warning(f"SQL search error: {e}")
            
        return []
    
    async def _generate_response(self, user_message: str, context: ChatContext) -> LLMResponse:
        """Generate LLM response with context"""
        if not self.llm_provider:
            raise LLMError("LLM provider not available", "chat_service")
        
        # Build context string from search results
        context_text = self._build_context_text(context)
        logger.info(f"Chat Debug - Context text length: {len(context_text)} characters")
        logger.info(f"Chat Debug - Context contains {context.total_results} total results (vector: {len(context.vector_results)}, sql: {len(context.sql_results)})")
        
        # Log detailed CONTEXT BUILDING RESULTS
        logger.info("=== CONTEXT BUILDING RESULTS ===")
        
        # Analyze context composition
        if context_text == "No relevant information found in your personal data.":
            logger.warning("Chat Debug - NO RELEVANT INFORMATION FOUND - This is likely the root cause!")
            logger.info("Context Status: EMPTY")
            logger.info(f"Vector Results Available: {len(context.vector_results)}")
            logger.info(f"SQL Results Available: {len(context.sql_results)}")
            logger.info("Reason: No search results to build context from")
        else:
            # Count content sections
            vector_section_count = context_text.count('=== Relevant Information (Semantic Search) ===')
            sql_section_count = context_text.count('=== Additional Relevant Information (Keyword Search) ===')
            
            logger.info(f"Context Status: POPULATED")
            logger.info(f"Total Context Length: {len(context_text)} characters")
            logger.info(f"Vector Section Included: {vector_section_count > 0} (count: {vector_section_count})")
            logger.info(f"SQL Section Included: {sql_section_count > 0} (count: {sql_section_count})")
            
            # Analyze deduplication
            if len(context.vector_results) > 0 and len(context.sql_results) > 0:
                vector_ids = {item.get('id') for item in context.vector_results}
                sql_ids = {item.get('id') for item in context.sql_results}
                overlap_ids = vector_ids.intersection(sql_ids)
                logger.info(f"Result Overlap: {len(overlap_ids)} items appear in both searches")
                if overlap_ids:
                    logger.debug(f"Overlapping IDs: {list(overlap_ids)[:5]}...")
            
            # Context preview
            logger.debug(f"Context Preview (first 300 chars): {context_text[:300]}...")
            
            # Context structure analysis
            lines = context_text.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            logger.info(f"Context Structure: {len(lines)} total lines, {len(non_empty_lines)} non-empty lines")
        
        logger.info("=== END CONTEXT BUILDING RESULTS ===")
        
        # Create prompt with context
        prompt = f"""Based on the provided context from my personal data, please answer my question: {user_message}

If the context doesn't contain relevant information to answer the question, please say so politely."""
        
        logger.info(f"Chat Debug - LLM input - Prompt: '{prompt}'")
        logger.info(f"Chat Debug - LLM parameters: max_tokens=500, temperature=0.7")
        logger.debug(f"Chat Debug - Full context being sent to LLM: {context_text}")
        
        # Generate response
        response = await self.llm_provider.generate_response(
            prompt=prompt,
            context=context_text,
            max_tokens=500,
            temperature=0.7
        )
        
        logger.info(f"Chat Debug - LLM response received, length: {len(response.content) if response.content else 0} characters")
        logger.debug(f"Chat Debug - LLM response content: '{response.content}'")
        
        return response
    
    def _build_context_text(self, context: ChatContext) -> str:
        """Build context text from search results"""
        context_parts = []
        
        logger.debug(f"Context Building - Starting with {len(context.vector_results)} vector results, {len(context.sql_results)} SQL results")
        
        # Add vector search results
        if context.vector_results:
            context_parts.append("=== Relevant Information (Semantic Search) ===")
            logger.debug(f"Context Building - Adding {min(5, len(context.vector_results))} vector results to context")
            for i, item in enumerate(context.vector_results[:5], 1):
                content = item.get('content', '')[:500]  # Limit content length
                context_parts.append(f"{i}. {content}")
                logger.debug(f"Context Building - Added vector item {i}: {len(content)} chars from {item.get('namespace')}:{item.get('source_id')}")
        
        # Add SQL search results (avoiding duplicates)
        vector_ids = {item.get('id') for item in context.vector_results}
        unique_sql_results = [
            item for item in context.sql_results 
            if item.get('id') not in vector_ids
        ]
        
        logger.debug(f"Context Building - After deduplication: {len(unique_sql_results)} unique SQL results (removed {len(context.sql_results) - len(unique_sql_results)} duplicates)")
        
        if unique_sql_results:
            context_parts.append("\n=== Additional Relevant Information (Keyword Search) ===")
            logger.debug(f"Context Building - Adding {min(3, len(unique_sql_results))} SQL results to context")
            for i, item in enumerate(unique_sql_results[:3], 1):
                content = item.get('content', '')[:500]  # Limit content length
                context_parts.append(f"{i}. {content}")
                logger.debug(f"Context Building - Added SQL item {i}: {len(content)} chars from {item.get('namespace')}:{item.get('source_id')}")
        
        if not context_parts:
            logger.warning("Context Building - No context parts generated, returning empty message")
            return "No relevant information found in your personal data."
        
        final_context = "\n\n".join(context_parts)
        logger.debug(f"Context Building - Final context: {len(context_parts)} sections, {len(final_context)} total characters")
        return final_context
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent chat history"""
        return self.database.get_chat_history(limit)
    
    async def close(self):
        """Close resources"""
        if self.llm_provider:
            await self.llm_provider.close()