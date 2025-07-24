"""
Provides hybrid data access (vector search + SQL queries) and LLM integration
for the minimal chat interface.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import numpy as np

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from core.ner_service import NERService
from core.emotional_concepts import EmotionalConceptEngine
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
    search_mode: str = "hybrid"  # hybrid, sql_only, sql_favored
    embedding_count: int = 0


class ChatService:
    """Service for handling chat interactions with hybrid data access"""
    
    def __init__(self, config: AppConfig, database: DatabaseService, 
                 vector_store: VectorStoreService, embeddings: EmbeddingService):
        self.config = config
        self.database = database
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.ner_service = NERService()
        self.emotional_engine = EmotionalConceptEngine(use_spacy_fallback=True)
        self.llm_provider = None
        
    async def initialize(self):
        """Initialize LLM provider, embedding service, and NER service"""
        try:
            logger.info("Starting service initialization...")
            
            # DIAGNOSTIC: Log LLM configuration details
            logger.info("=== LLM CONFIGURATION DIAGNOSTIC ===")
            logger.info(f"LLM Provider: {self.config.llm_provider.provider}")
            logger.info(f"Ollama Base URL: {self.config.llm_provider.ollama.base_url}")
            logger.info(f"Ollama Model: {self.config.llm_provider.ollama.model}")
            logger.info(f"Ollama Timeout: {self.config.llm_provider.ollama.timeout}")
            logger.info(f"Ollama Max Retries: {self.config.llm_provider.ollama.max_retries}")
            logger.info(f"Ollama Is Configured: {self.config.llm_provider.ollama.is_configured()}")
            logger.info(f"Active Provider Configured: {self.config.llm_provider.is_active_provider_configured()}")
            logger.info("=== END LLM CONFIGURATION DIAGNOSTIC ===")
            
            # Initialize embedding service first
            if self.embeddings:
                logger.info("Initializing embedding service...")
                await self.embeddings.initialize()
                logger.info("Embedding service initialized successfully")
            
            # Initialize NER service
            logger.info("Initializing NER service...")
            await self.ner_service.initialize()
            logger.info("NER service initialized successfully")
            
            # Create LLM provider factory (synchronous call)
            logger.info("Creating LLM provider factory...")
            llm_factory = create_llm_provider(self.config.llm_provider)
            logger.info(f"LLM factory created for provider: {self.config.llm_provider.provider}")
            
            # Get the active provider instance (async call)
            logger.info("Getting active LLM provider instance...")
            self.llm_provider = await llm_factory.get_active_provider()
            logger.info(f"Active LLM provider obtained: {self.llm_provider.provider_name if self.llm_provider else 'None'}")
            
            # DIAGNOSTIC: Test Ollama connectivity before availability check
            if self.llm_provider and self.llm_provider.provider_name == "ollama":
                logger.info("=== OLLAMA CONNECTIVITY DIAGNOSTIC ===")
                try:
                    import httpx
                    client = httpx.AsyncClient(timeout=10.0)
                    logger.info(f"Testing direct connection to: {self.config.llm_provider.ollama.base_url}/api/tags")
                    response = await client.get(f"{self.config.llm_provider.ollama.base_url}/api/tags")
                    logger.info(f"Direct connectivity test - Status: {response.status_code}")
                    if response.status_code == 200:
                        data = response.json()
                        models = [model.get("name", "") for model in data.get("models", [])]
                        logger.info(f"Available models: {models}")
                        target_model = self.config.llm_provider.ollama.model
                        model_available = target_model in models
                        logger.info(f"Target model '{target_model}' available: {model_available}")
                    else:
                        logger.warning(f"Ollama API returned status {response.status_code}: {response.text}")
                    await client.aclose()
                except Exception as conn_e:
                    logger.error(f"Direct Ollama connectivity test failed: {conn_e}")
                logger.info("=== END OLLAMA CONNECTIVITY DIAGNOSTIC ===")
            
            # Check availability using the provider's method
            logger.info("Checking LLM provider availability...")
            if not await self.llm_provider.is_available():
                logger.error("LLM provider availability check FAILED")
                
                # Additional diagnostic for Ollama
                if self.llm_provider.provider_name == "ollama":
                    logger.error("=== OLLAMA AVAILABILITY FAILURE DETAILS ===")
                    logger.error(f"Provider name: {self.llm_provider.provider_name}")
                    logger.error(f"Config base_url: {self.llm_provider.config.base_url}")
                    logger.error(f"Config model: {self.llm_provider.config.model}")
                    logger.error(f"Config is_configured(): {self.llm_provider.config.is_configured()}")
                    logger.error("=== END OLLAMA AVAILABILITY FAILURE DETAILS ===")
            else:
                logger.info("LLM provider initialized and available")
                
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
    async def process_chat_message(self, user_message: str) -> str:
        """Process a chat message and return assistant response"""
        try:
            logger.info(f"🎯 CHAT START: Processing message: '{user_message}'")
            logger.info(f"🔧 CHAT INIT: Services initialized - Vector: {self.vector_store is not None}, Embeddings: {self.embeddings is not None}, LLM: {self.llm_provider is not None}, Database: {self.database is not None}")
            
            # Test our enhanced methods are available
            if hasattr(self, '_extract_search_keywords'):
                logger.info(f"✅ ENHANCED METHODS: _extract_search_keywords available")
            else:
                logger.error(f"❌ ENHANCED METHODS: _extract_search_keywords NOT available")
            
            if hasattr(self, '_build_execution_sequence_summary'):
                logger.info(f"✅ ENHANCED METHODS: _build_execution_sequence_summary available")
            else:
                logger.error(f"❌ ENHANCED METHODS: _build_execution_sequence_summary NOT available")
                
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
                                    #logger.debug(f"  Metadata: {metadata}")
                                except:
                                    logger.debug(f"  Raw Metadata: {source['metadata'][:100]}")
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
            
            # Final logging of complete chat transaction
            logger.info("🏁 CHAT TRANSACTION COMPLETED:")
            logger.info(f"   Query: '{user_message[:100]}'")
            logger.info(f"   Response length: {len(response.content)} characters")
            final_preview = response.content[:150] + "..." if len(response.content) > 150 else response.content
            logger.info(f"   Response preview: '{final_preview}'")
            
            return response.content
            
        except Exception as e:
            # Enhanced error logging for debugging
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ CHAT ERROR: Failed to process message: '{user_message}'")
            logger.error(f"❌ CHAT ERROR: Exception type: {type(e).__name__}")
            logger.error(f"❌ CHAT ERROR: Exception message: {str(e)}")
            logger.error(f"❌ CHAT ERROR: Full traceback:\n{error_details}")
            
            # Check service states for debugging
            logger.error(f"🔍 DEBUG STATE: Vector store available: {self.vector_store is not None}")
            logger.error(f"🔍 DEBUG STATE: Embeddings available: {self.embeddings is not None}")
            logger.error(f"🔍 DEBUG STATE: Database available: {self.database is not None}")
            logger.error(f"🔍 DEBUG STATE: LLM provider available: {self.llm_provider is not None}")
            logger.error(f"🔍 DEBUG STATE: NER service available: {hasattr(self, 'ner_service') and self.ner_service is not None}")
            
            error_msg = "I'm sorry, I encountered an error processing your message. Please try again."
            
            # Store error exchange for debugging
            try:
                self.database.store_chat_message(user_message, error_msg)
            except Exception as storage_e:
                logger.error(f"❌ STORAGE ERROR: Could not store error message: {storage_e}")
                
            return error_msg
    
    async def _get_chat_context(self, query: str, max_results: int = 10) -> ChatContext:
        """Get relevant context using hybrid approach with intelligent fallback"""
        logger.info(f"=== CONTEXT RETRIEVAL START ===")
        logger.info(f"Query: '{query}[:100]'")
        logger.info(f"Max results requested: {max_results}")
        
        vector_results = []
        sql_results = []
        search_mode = "hybrid"  # hybrid, vector_only, sql_only
        
        # Check if vector search is available and has any embeddings
        vector_available = False
        embedding_count = 0
        total_vectors_in_store = 0
        
        if self.vector_store and self.embeddings:
            try:
                # Use the official get_stats method for more reliable count
                vector_stats = self.vector_store.get_stats()
                total_vectors_in_store = vector_stats.get('total_vectors', 0)
                embedding_count = total_vectors_in_store
                vector_available = embedding_count > 0
                
                logger.info(f"📊 VECTOR STORE STATS: {vector_stats}")
                logger.info(f"📊 TOTAL VECTORS AVAILABLE: {total_vectors_in_store}")
                logger.info(f"📊 Vector store service available: {self.vector_store is not None}")
                logger.info(f"📊 Embedding service available: {self.embeddings is not None}")
                logger.info(f"📊 Vector search enabled: {vector_available}")
                
                # Additional debugging: check database embedding status
                db_stats = self.database.get_database_stats()
                embedding_status = db_stats.get('embedding_status', {})
                logger.info(f"📊 DATABASE EMBEDDING STATUS: {embedding_status}")
                
            except Exception as e:
                logger.warning(f"❌ Error checking vector store: {e}")
                logger.info(f"📊 TOTAL VECTORS AVAILABLE: 0 (error accessing vector store)")
                
                # Try to get database stats even if vector store fails
                try:
                    db_stats = self.database.get_database_stats()
                    embedding_status = db_stats.get('embedding_status', {})
                    logger.info(f"📊 DATABASE EMBEDDING STATUS (fallback): {embedding_status}")
                except Exception as db_e:
                    logger.warning(f"❌ Error checking database stats: {db_e}")
        else:
            logger.info(f"📊 TOTAL VECTORS AVAILABLE: 0 (services not initialized)")
            logger.info(f"📊 Vector store service available: {self.vector_store is not None}")
            logger.info(f"📊 Embedding service available: {self.embeddings is not None}")
        
        # Determine search strategy based on available vectors
        if not vector_available:
            # No embeddings available - use SQL search only with more results
            search_mode = "sql_only"
            logger.info(f"🔄 SEARCH STRATEGY: SQL-only (no vectors available)")
            sql_limit = max_results
            vector_limit = 0
        elif embedding_count < 100:
            # Limited embeddings - favor SQL search but still try vector
            search_mode = "sql_favored"
            logger.info(f"🔄 SEARCH STRATEGY: SQL-favored ({embedding_count} vectors available, below 100 threshold)")
            sql_limit = int(max_results * 0.7)
            vector_limit = max_results - sql_limit
        else:
            # Full embeddings available - balanced approach
            search_mode = "hybrid"
            logger.info(f"🔄 SEARCH STRATEGY: Balanced hybrid ({embedding_count} vectors available)")
            sql_limit = max_results // 2
            vector_limit = max_results // 2
        
        logger.info(f"📋 Search allocation: vector_limit={vector_limit}, sql_limit={sql_limit}")
        
        # Perform vector search if available
        vector_search_attempted = False
        vector_search_successful = False
        if vector_limit > 0:
            try:
                vector_search_attempted = True
                logger.info(f"🔍 VECTOR SEARCH: Starting (requesting {vector_limit} results)...")
                vector_results = await self._vector_search(query, vector_limit)
                vector_search_successful = True
                logger.info(f"✅ VECTOR SEARCH: Completed successfully - {len(vector_results)} results returned")
            except Exception as e:
                logger.warning(f"❌ VECTOR SEARCH: Failed with error: {e}")
                vector_results = []
        else:
            logger.info(f"⏭️  VECTOR SEARCH: Skipped (vector_limit=0)")
        
        # Always perform SQL search (fallback or primary)
        sql_search_attempted = False
        sql_search_successful = False
        try:
            sql_search_attempted = True
            logger.info(f"🔍 SQL SEARCH: Starting (requesting {sql_limit} results)...")
            sql_results = await self._sql_search(query, sql_limit)
            sql_search_successful = True
            logger.info(f"✅ SQL SEARCH: Completed successfully - {len(sql_results)} results returned")
        except Exception as e:
            logger.warning(f"❌ SQL SEARCH: Failed with error: {e}")
            sql_results = []
            
        # Final result summary
        total_results = len(vector_results) + len(sql_results)
        vector_contribution = len(vector_results)
        sql_contribution = len(sql_results)
        
        logger.info(f"📊 VECTORS IDENTIFIED FOR THIS CHAT QUERY: {vector_contribution}")
        logger.info(f"📊 SQL RESULTS FOR THIS CHAT QUERY: {sql_contribution}")
        logger.info(f"📊 TOTAL CONTEXT ITEMS: {total_results}")
        logger.info(f"=== CONTEXT RETRIEVAL COMPLETE ===")
        
        return ChatContext(
            vector_results=vector_results,
            sql_results=sql_results,
            total_results=total_results,
            search_mode=search_mode,
            embedding_count=embedding_count
        )
    
    async def _vector_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        try:
            logger.info(f"🔗 VECTOR SEARCH DETAIL: Generating embedding for query: '{query}'")
            
            # Generate embedding for query
            query_embedding = await self.embeddings.embed_text(query)
            embedding_dimension = len(query_embedding) if query_embedding is not None else 0
            logger.info(f"✅ VECTOR SEARCH DETAIL: Query embedding generated - dimension: {embedding_dimension}")
            
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
                logger.debug(f"📊 VECTOR SEARCH DETAIL: Embedding statistics: {embedding_stats}")
            
            # Analyze vector store contents
            total_vectors_in_store = len(self.vector_store.vectors)
            logger.info(f"📦 VECTOR STORE STATUS: Total vectors in store: {total_vectors_in_store}")
            logger.info(f"🎯 VECTOR SEARCH REQUEST: Searching for top {max_results} similar vectors")
            
            # Log what namespaces are available in vector store
            available_namespaces = set()
            namespace_counts = {}
            for vector_id in self.vector_store.vectors.keys():
                namespace = vector_id.split(':', 1)[0] if ':' in vector_id else 'unknown'
                available_namespaces.add(namespace)
                namespace_counts[namespace] = namespace_counts.get(namespace, 0) + 1
            
            logger.info(f"📂 VECTOR NAMESPACES: Available namespaces: {sorted(available_namespaces)}")
            logger.info(f"📊 VECTOR DISTRIBUTION: {dict(sorted(namespace_counts.items()))}")
            
            # Perform the actual vector search
            similar_ids = self.vector_store.search(query_embedding, k=max_results)
            found_count = len(similar_ids) if similar_ids else 0
            logger.info(f"🎯 VECTOR SEARCH RESULT: Found {found_count} similar vectors out of {total_vectors_in_store} total")
            
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
    
    def _expand_emotional_keywords(self, keywords: List[str]) -> List[str]:
        """Expand keywords with emotional concept relationships using ConceptNet5 and ontology"""
        try:
            # Use the new EmotionalConceptEngine for sophisticated concept expansion
            expanded_concepts = self.emotional_engine.expand_emotional_concepts(
                concepts=keywords,
                max_expansions=15,
                similarity_threshold=0.6
            )
            
            # Combine original keywords with expanded concepts
            all_keywords = list(set(keywords + expanded_concepts))
            
            logger.info(f"🧠 EMOTIONAL EXPANSION (Library-based): {keywords} → {expanded_concepts}")
            return all_keywords
            
        except Exception as e:
            logger.warning(f"EmotionalConceptEngine failed, using original keywords: {e}")
            return keywords

    def _extract_search_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from user query for SQL search with emotional intelligence"""
        try:
            logger.info(f"🔍 KEYWORD EXTRACTION: Processing query: '{query}'")
            
            # Use NER service to extract entities if available
            ner_keywords = []
            if hasattr(self, 'ner_service') and self.ner_service:
                ner_result = self.ner_service.extract_entities(query)
                
                # Add person names
                ner_keywords.extend(ner_result.person_names)
                
                # Add pet names  
                ner_keywords.extend(ner_result.pet_names)
                
                # Add other significant entities
                for entity in ner_result.entities:
                    if entity.label in ['PERSON', 'PET', 'ANIMAL', 'ORG', 'GPE', 'PRODUCT']:
                        ner_keywords.append(entity.text)
            
            # Enhanced keyword extraction with emotional and psychological concept recognition
            import re
            
            # Extended stop words including question words and common emotional query terms
            stop_words = {'do', 'i', 'have', 'a', 'an', 'the', 'is', 'are', 'was', 'were', 
                         'can', 'could', 'would', 'should', 'what', 'when', 'where', 'who', 
                         'how', 'why', 'my', 'me', 'you', 'your', 'his', 'her', 'their', 'our',
                         'in', 'at', 'on', 'for', 'with', 'by', 'from', 'to', 'of', 'and', 'or',
                         'last', 'this', 'that', 'these', 'those', 'were', 'been', 'being'}
            
            # Psychological and emotional priority terms that should always be included
            priority_psychological_terms = {
                'fear', 'fears', 'anxiety', 'anxious', 'worry', 'worried', 'concern', 'concerned',
                'stress', 'stressed', 'nervous', 'panic', 'scared', 'afraid', 'frightened',
                'health', 'medical', 'doctor', 'symptoms', 'pain', 'sick', 'illness',
                'sleep', 'tired', 'exhausted', 'fatigue', 'sleepiness',
                'social', 'meeting', 'party', 'gathering', 'people', 'friends', 'family',
                'work', 'professional', 'job', 'career', 'business',
                'age', 'aging', 'old', 'young', 'time', 'future', 'uncertainty'
            }
            
            # Extract all words from query
            words = re.findall(r'\b\w+\b', query.lower())
            
            # Categorize keywords
            extracted_keywords = []
            
            # 1. Always include priority psychological terms
            for word in words:
                if word in priority_psychological_terms:
                    extracted_keywords.append(word)
            
            # 2. Include meaningful non-stop words
            for word in words:
                if (word not in stop_words and 
                    len(word) > 2 and 
                    word not in extracted_keywords):
                    extracted_keywords.append(word)
            
            # 3. Add NER-extracted keywords
            for keyword in ner_keywords:
                if keyword.lower() not in [k.lower() for k in extracted_keywords]:
                    extracted_keywords.append(keyword)
            
            # 4. Apply emotional keyword expansion
            if extracted_keywords:
                expanded_keywords = self._expand_emotional_keywords(extracted_keywords)
                logger.info(f"🔍 EMOTIONAL EXPANSION: Original keywords: {extracted_keywords}")
                logger.info(f"🔍 EMOTIONAL EXPANSION: Expanded to: {expanded_keywords}")
                extracted_keywords = expanded_keywords
            
            # Fallback strategies if no good keywords found
            if not extracted_keywords:
                # Try to find any capitalized words (potential names)
                capitalized = re.findall(r'\b[A-Z][a-z]+\b', query)
                if capitalized:
                    logger.info(f"🔍 FALLBACK: Using capitalized words: {capitalized}")
                    return capitalized
                
                # Last resort: use original query
                logger.info(f"🔍 FALLBACK: Using original query as single keyword")
                return [query.strip()]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = []
            for keyword in extracted_keywords:
                if keyword.lower() not in seen:
                    unique_keywords.append(keyword)
                    seen.add(keyword.lower())
            
            logger.info(f"🔍 FINAL KEYWORDS: {unique_keywords}")
            return unique_keywords
            
        except Exception as e:
            logger.debug(f"Error extracting keywords: {e}")
            return [query.strip()]

    async def _find_similar_terms_in_data(self, query_embedding: np.ndarray, original_keywords: List[str], 
                                        similarity_threshold: float = 0.6, max_similar_terms: int = 10) -> List[str]:
        """Find semantically similar terms in existing data to expand keyword search"""
        try:
            if query_embedding is None:
                logger.debug("No query embedding available for semantic expansion")
                return []
            
            logger.info(f"🔍 SEMANTIC EXPANSION: Finding similar terms for keywords: {original_keywords}")
            
            # Get a sample of content from database to find similar terms
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT content, summary_content, named_entities, content_classification
                    FROM data_items 
                    WHERE content IS NOT NULL 
                    ORDER BY updated_at DESC
                    LIMIT 100
                """)
                
                # Extract unique terms from existing content
                all_terms = set()
                for row in cursor.fetchall():
                    for field in [row['content'], row['summary_content'], row['named_entities'], row['content_classification']]:
                        if field:
                            # Extract meaningful terms (words 3+ characters, not in original keywords)
                            import re
                            terms = re.findall(r'\b[a-zA-Z]{3,}\b', field.lower())
                            all_terms.update(term for term in terms if term not in [k.lower() for k in original_keywords])
                
                # Limit to reasonable number for performance
                sample_terms = list(all_terms)[:200] if len(all_terms) > 200 else list(all_terms)
                
                if not sample_terms:
                    logger.debug("No terms found for semantic expansion")
                    return []
                
                logger.info(f"🔍 SEMANTIC EXPANSION: Evaluating {len(sample_terms)} candidate terms")
                
                # Generate embeddings for candidate terms and compare with query
                similar_terms = []
                batch_size = min(20, len(sample_terms))  # Process in smaller batches for performance
                
                for i in range(0, len(sample_terms), batch_size):
                    batch_terms = sample_terms[i:i + batch_size]
                    try:
                        # Generate embeddings for batch
                        batch_embeddings = await self.embeddings.embed_texts(batch_terms)
                        
                        if batch_embeddings and len(batch_embeddings) > 0:
                            # Calculate similarities
                            import numpy as np
                            query_embedding_2d = query_embedding.reshape(1, -1)
                            batch_embeddings_2d = np.array(batch_embeddings)
                            
                            # Calculate cosine similarity
                            from sklearn.metrics.pairwise import cosine_similarity
                            similarities = cosine_similarity(query_embedding_2d, batch_embeddings_2d)[0]
                            
                            # Find terms above threshold
                            for j, similarity in enumerate(similarities):
                                if similarity >= similarity_threshold:
                                    similar_terms.append((batch_terms[j], similarity))
                                    
                    except Exception as e:
                        logger.debug(f"Error processing batch {i}: {e}")
                        continue
                
                # Sort by similarity and take top results
                similar_terms.sort(key=lambda x: x[1], reverse=True)
                top_similar_terms = [term for term, score in similar_terms[:max_similar_terms]]
                
                logger.info(f"🔍 SEMANTIC EXPANSION: Found {len(top_similar_terms)} similar terms: {top_similar_terms}")
                return top_similar_terms
                
        except Exception as e:
            logger.warning(f"Error in semantic term expansion: {e}")
            return []

    async def _sql_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform SQL-based keyword search with semantic expansion across content and enhanced preprocessing fields"""
        try:
            # MARKER: Enhanced SQL search with semantic keyword expansion
            logger.info(f"🔍 ENHANCED SQL SEARCH: Starting semantic-enhanced keyword search for query: '{query}'")
            
            # Extract meaningful keywords from the query instead of using exact phrase
            original_keywords = self._extract_search_keywords(query)
            logger.info(f"🔍 SQL SEARCH DETAIL: Keyword extraction from query '{query}'")
            logger.info(f"🔍 SQL SEARCH DETAIL: Extracted keywords: {original_keywords}")
            
            # If no good keywords found, fall back to original query
            if not original_keywords:
                original_keywords = [query]
                logger.info(f"🔍 SQL SEARCH DETAIL: No keywords extracted, using original query as fallback")
            
            # Attempt semantic expansion of keywords (if enabled)
            expanded_keywords = []
            semantic_expansion_enabled = os.getenv("SQL_SEARCH_SEMANTIC_EXPANSION", "true").lower() == "true"
            
            if semantic_expansion_enabled:
                try:
                    # Generate embedding for the query
                    query_embedding = await self.embeddings.embed_text(query)
                    if query_embedding is not None:
                        # Find semantically similar terms in the data
                        similarity_threshold = float(os.getenv("SQL_SEARCH_SIMILARITY_THRESHOLD", "0.6"))
                        max_similar_terms = int(os.getenv("SQL_SEARCH_MAX_SIMILAR_TERMS", "8"))
                        
                        expanded_keywords = await self._find_similar_terms_in_data(
                            query_embedding, 
                            original_keywords,
                            similarity_threshold=similarity_threshold,
                            max_similar_terms=max_similar_terms
                        )
                        
                except Exception as e:
                    logger.debug(f"Semantic expansion failed, proceeding with original keywords: {e}")
            else:
                logger.debug("Semantic expansion disabled in configuration")
            # Combine original and expanded keywords
            all_keywords = original_keywords + expanded_keywords
            keywords = all_keywords  # Use expanded set for search
            
            logger.info(f"🔍 SEMANTIC EXPANSION RESULT: Using {len(keywords)} total keywords: {keywords}")
            
            # Try FTS search first (much faster for text search) if enabled
            use_fts = os.getenv("SQL_SEARCH_USE_FTS", "true").lower() == "true"
            if use_fts:
                try:
                    fts_results = self.database.fts_search(keywords, max_results)
                    if fts_results is not None:
                        logger.info(f"🚀 FTS SEARCH: Successfully used Full-Text Search with {len(fts_results)} results")
                        return fts_results
                    else:
                        logger.debug("🔍 FTS SEARCH: FTS not available, falling back to LIKE search")
                except Exception as e:
                    logger.debug(f"🔍 FTS SEARCH: FTS search failed, falling back to LIKE search: {e}")
            else:
                logger.debug("🔍 FTS SEARCH: FTS disabled in configuration")
            
            # Fallback to LIKE-based search
            logger.info("🔍 LIKE SEARCH: Using traditional LIKE-based search")
            
            # Build OR conditions for multiple keywords
            search_conditions = []
            search_params = []
            
            for keyword in keywords:
                search_pattern = f"%{keyword}%"
                search_conditions.append("""
                    (content LIKE ? 
                     OR summary_content LIKE ?
                     OR named_entities LIKE ?
                     OR content_classification LIKE ?)
                """)
                search_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            
            # Combine conditions with OR
            where_clause = " OR ".join(search_conditions)
            
            logger.debug(f"Chat Debug - SQL search with {len(keywords)} keywords, {len(search_params)} parameters")
            
            # Enhanced search across content, summary_content, and named_entities
            with self.database.get_connection() as conn:
                sql_query = f"""
                    SELECT id, namespace, source_id, content, metadata, 
                           summary_content, named_entities, content_classification,
                           created_at, updated_at
                    FROM data_items 
                    WHERE {where_clause}
                    ORDER BY 
                        CASE 
                            WHEN named_entities LIKE ? THEN 1
                            WHEN summary_content LIKE ? THEN 2  
                            WHEN content_classification LIKE ? THEN 3
                            ELSE 4
                        END,
                        updated_at DESC
                    LIMIT ?
                """
                
                # Add priority search pattern (use first keyword for ordering)
                priority_pattern = f"%{keywords[0]}%"
                all_params = search_params + [priority_pattern, priority_pattern, priority_pattern, max_results]
                
                cursor = conn.execute(sql_query, all_params)
                
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
                
                logger.info(f"Chat Debug - Enhanced SQL search found {len(results)} matching items")
                
                # Analyze SQL results with field match analysis
                if results:
                    sql_namespaces = {item.get('namespace') for item in results}
                    sql_content_lengths = [len(item.get('content', '')) for item in results]
                    
                    # Analyze which fields had matches for debugging
                    field_matches = {'content': 0, 'summary_content': 0, 'named_entities': 0, 'content_classification': 0}
                    for item in results:
                        for keyword in keywords:
                            keyword_lower = keyword.lower()
                            if keyword_lower in (item.get('content', '') or '').lower():
                                field_matches['content'] += 1
                            if keyword_lower in (item.get('summary_content', '') or '').lower():
                                field_matches['summary_content'] += 1
                            if keyword_lower in (item.get('named_entities', '') or '').lower():
                                field_matches['named_entities'] += 1
                            if keyword_lower in (item.get('content_classification', '') or '').lower():
                                field_matches['content_classification'] += 1
                    
                    logger.info(f"Chat Debug - SQL result analysis: namespaces={sorted(sql_namespaces)}, content_lengths={sql_content_lengths}")
                    logger.info(f"Chat Debug - Field matches: {field_matches}")
                    
                    # Log detailed SQL SEARCH RESULTS (truncated to 10 records for brevity)
                    logger.info("=== ENHANCED SQL SEARCH RESULTS (truncated to 10 records for brevity) ===")
                    for i, item in enumerate(results[:10]):
                        content = item.get('content', '')
                        content_preview = content[:150] + '...' if len(content) > 150 else content
                        metadata = item.get('metadata', {})
                        summary_content = item.get('summary_content', '')
                        named_entities = item.get('named_entities', '')
                        
                        # Determine which field(s) matched
                        matched_fields = []
                        for keyword in keywords:
                            keyword_lower = keyword.lower()
                            if keyword_lower in content.lower():
                                matched_fields.append(f'content({keyword})')
                            if keyword_lower in (summary_content or '').lower():
                                matched_fields.append(f'summary_content({keyword})')
                            if keyword_lower in (named_entities or '').lower():
                                matched_fields.append(f'named_entities({keyword})')
                        
                        logger.info(f"SQL Result {i+1}:")
                        logger.info(f"  ID: {item.get('id')}")
                        logger.info(f"  Namespace: {item.get('namespace')} | Source: {item.get('source_id')}")
                        logger.info(f"  Matched Fields: {', '.join(matched_fields) if matched_fields else 'Unknown'}")
                        logger.info(f"  Content Length: {len(content)} chars")
                        logger.info(f"  Content Preview: '{content_preview}'")
                        if summary_content:
                            summary_preview = summary_content[:100] + '...' if len(summary_content) > 100 else summary_content
                            logger.info(f"  Summary Content: '{summary_preview}'")
                        if named_entities:
                            entities_preview = named_entities[:100] + '...' if len(named_entities) > 100 else named_entities
                            logger.info(f"  Named Entities: '{entities_preview}'")
                        if metadata:
                            logger.debug(f"  Metadata: {metadata}")
                        logger.info(f"  Created: {item.get('created_at')} | Updated: {item.get('updated_at')}")
                        logger.info("  " + "-" * 80)
                    
                    if len(results) > 10:
                        logger.info(f"... and {len(results) - 10} more SQL results")
                else:
                    logger.info(f"Chat Debug - Enhanced SQL search with keywords {keywords} returned no results")
                
                return results
                
        except Exception as e:
            logger.warning(f"SQL search error: {e}")
            
        return []
    
    async def _generate_response(self, user_message: str, context: ChatContext) -> LLMResponse:
        """Generate LLM response with context"""
        
        # Generate execution sequence summary before calling LLM
        execution_sequence = self._build_execution_sequence_summary(context)
        logger.info("🔄 EXECUTION SEQUENCE SUMMARY:")
        for step in execution_sequence:
            logger.info(f"   {step}")
        
        # DIAGNOSTIC: Log LLM provider state at response generation time
        logger.info("=== LLM RESPONSE GENERATION DIAGNOSTIC ===")
        logger.info(f"LLM Provider Object: {self.llm_provider}")
        logger.info(f"LLM Provider Type: {type(self.llm_provider)}")
        if self.llm_provider:
            logger.info(f"Provider Name: {self.llm_provider.provider_name}")
            logger.info(f"Provider Config: {self.llm_provider.config}")
            # Test availability at response time
            try:
                is_available = await self.llm_provider.is_available()
                logger.info(f"Provider Available at Response Time: {is_available}")
            except Exception as avail_e:
                logger.error(f"Availability check failed at response time: {avail_e}")
        else:
            logger.error("LLM Provider is None - this is the root cause!")
        logger.info("=== END LLM RESPONSE GENERATION DIAGNOSTIC ===")
        
        if not self.llm_provider:
            raise LLMError("LLM provider not available", "chat_service")
        
        # Build context string from search results
        context_text = self._build_context_text(context)
        logger.info(f"Chat Debug - Context text length: {len(context_text)} characters")
        logger.info(f"Chat Debug - Context contains {context.total_results} total results (vector: {len(context.vector_results)}, sql: {len(context.sql_results)})")
        logger.info(f"Chat Debug - Search mode: {context.search_mode}, embedding count: {context.embedding_count}")
        
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
        
        # Create comprehensive AI assistant prompt with emotional intelligence and contextual understanding
        prompt = f"""You are an advanced AI assistant with deep emotional intelligence and contextual understanding, designed to provide comprehensive, empathetic responses by fully leveraging all available personal data. Your enhanced operational principles:

COMPREHENSIVE DATA UTILIZATION: Always access and incorporate every relevant fact, emotional indicator, behavioral pattern, and contextual clue from the knowledge base. Never ignore subtle emotional signals, relationship dynamics, or psychological patterns embedded in the data.

EMOTIONAL INTELLIGENCE APPLICATION: Recognize that emotions, fears, concerns, and psychological states are expressed through indirect language, contextual situations, and behavioral patterns. When analyzing emotional queries:
- Look for anxiety indicators: mentions of health concerns, sleep issues, stress signals, avoidance behaviors
- Identify fear patterns: discussions of future uncertainties, medical appointments, relationship concerns, professional challenges
- Recognize emotional expressions: worry about outcomes, seeking reassurance, discussing difficult situations
- Understand emotional context: social situations that cause discomfort, recurring themes of concern, temporal patterns of stress

CONTEXTUAL AND TEMPORAL PATTERN RECOGNITION: Analyze data across time periods to identify emotional trajectories, recurring concerns, and evolving psychological states. Connect seemingly unrelated events that may share emotional undertones or represent manifestations of underlying concerns.

PSYCHOLOGICAL INSIGHT SYNTHESIS: For emotional and psychological queries, synthesize patterns from:
- Health-related discussions and medical concerns
- Sleep patterns and physical symptoms that may indicate stress
- Social interactions and relationship dynamics
- Professional or personal challenges mentioned
- Recurring themes or topics that may reveal underlying worries
- Temporal clustering of concerns (e.g., "in the last week")

EMPATHETIC INFERENCE: When analyzing emotional states like fears, anxieties, or concerns:
- Recognize that fears are often expressed indirectly through discussions of challenging situations
- Understand that health anxieties may manifest through symptom discussions or medical appointments
- Identify social fears through mentions of gatherings, meetings, or interpersonal situations
- Detect professional fears through work-related stress indicators or challenging conversations

INTELLIGENT EMOTIONAL EXTRAPOLATION: Use contextual clues to identify emotional patterns even when not explicitly stated. Connect behavioral indicators, situational stressors, and expressed concerns to provide insightful analysis of emotional states.

QUESTION: {user_message}

ENHANCED RESPONSE GUIDELINES:
- For emotional queries (fears, concerns, worries), analyze indirect emotional indicators rather than seeking literal mentions
- Identify patterns of stress, anxiety, or concern through situational context and behavioral clues
- Synthesize emotional insights from health discussions, sleep patterns, social interactions, and professional challenges
- Provide emotionally intelligent responses that acknowledge the complexity of human psychology
- When analyzing fears or concerns, look for underlying themes and emotional patterns across different life areas
- Connect temporal patterns (e.g., "last week") with specific events, discussions, or situations that may have contributed to emotional states
- Demonstrate understanding that psychological states manifest through various topics and discussions, not just direct emotional expressions

Analyze the provided personal data with enhanced emotional intelligence and provide a response that demonstrates deep psychological insight and empathetic understanding of the human experience reflected in the data."""
        
        logger.info(f"Chat Debug - LLM input - Prompt: '{prompt}'")
        logger.info(f"Chat Debug - LLM parameters: max_tokens=800, temperature=0.7")
        logger.debug(f"Chat Debug - Full context being sent to LLM: {context_text}")
        
        # Generate response with increased token limit for comprehensive answers
        response = await self.llm_provider.generate_response(
            prompt=prompt,
            context=context_text,
            max_tokens=800,
            temperature=0.7
        )
        
        # Log final execution sequence completion and response details
        logger.info("🎯 FINAL EXECUTION SEQUENCE COMPLETED:")
        logger.info("   8️⃣  LLM response generation completed successfully")
        
        response_length = len(response.content) if response.content else 0
        logger.info(f"📄 LLM RESPONSE METRICS:")
        logger.info(f"   Response length: {response_length} characters")
        logger.info(f"   Response available: {response.content is not None}")
        logger.info(f"   Response non-empty: {response_length > 0}")
        
        # Preview the response content (first 200 chars)
        if response.content:
            preview = response.content[:200] + "..." if len(response.content) > 200 else response.content
            logger.info(f"📝 LLM response preview: '{preview}'")
        else:
            logger.warning("⚠️  LLM response is empty!")
            
        logger.debug(f"🔍 LLM response content (full): '{response.content}'")
        
        # Add search mode notification to response if not using full vector search
        if context.search_mode == "sql_only":
            total_items = context.total_results + context.embedding_count  # Approximate total items
            if context.embedding_count == 0:
                response.content += f"\n\n---\n**🔄 SYSTEM STATUS:** Currently using keyword search only. Semantic search is being prepared in the background to enable AI-powered understanding of your content. Your data is being processed and will enable more intelligent responses soon.\n---"
            else:
                response.content += f"\n\n---\n**🔄 SYSTEM STATUS:** Using keyword search. {context.embedding_count} items ready for semantic search, more being processed in background for enhanced AI understanding.\n---"
        elif context.search_mode == "sql_favored":
            response.content += f"\n\n---\n**🔄 SYSTEM STATUS:** Using enhanced hybrid search ({context.embedding_count} items available for semantic search). Full AI-powered search capabilities improving as background processing continues.\n---"
        
        return response
    
    def _build_execution_sequence_summary(self, context: ChatContext) -> List[str]:
        """Build a step-by-step summary of the execution sequence"""
        sequence = []
        
        # Step 1: Query analysis
        sequence.append("1️⃣  Query received and analyzed")
        
        # Step 2: Vector store assessment  
        if context.embedding_count > 0:
            sequence.append(f"2️⃣  Vector store assessed: {context.embedding_count} embeddings available")
        else:
            sequence.append("2️⃣  Vector store assessed: NO embeddings available")
        
        # Step 3: Search strategy determination
        if context.search_mode == "sql_only":
            sequence.append("3️⃣  Search strategy: SQL-ONLY (no vectors → fallback mode)")
        elif context.search_mode == "sql_favored": 
            sequence.append(f"3️⃣  Search strategy: SQL-FAVORED (limited vectors: {context.embedding_count} < 100)")
        elif context.search_mode == "hybrid":
            sequence.append(f"3️⃣  Search strategy: BALANCED HYBRID (sufficient vectors: {context.embedding_count} ≥ 100)")
        else:
            sequence.append(f"3️⃣  Search strategy: {context.search_mode.upper()}")
        
        # Step 4: Vector search execution
        vector_count = len(context.vector_results)
        if vector_count > 0:
            sequence.append(f"4️⃣  Vector search executed: {vector_count} semantic matches found")
        elif context.search_mode == "sql_only":
            sequence.append("4️⃣  Vector search skipped: not available")
        else:
            sequence.append("4️⃣  Vector search executed: 0 semantic matches found")
        
        # Step 5: SQL search execution
        sql_count = len(context.sql_results)
        if sql_count > 0:
            sequence.append(f"5️⃣  SQL search executed: {sql_count} keyword matches found")
        else:
            sequence.append("5️⃣  SQL search executed: 0 keyword matches found")
        
        # Step 6: Context building
        total_context = context.total_results
        if total_context > 0:
            sequence.append(f"6️⃣  Context built: {total_context} total items combined")
        else:
            sequence.append("6️⃣  Context built: NO relevant information found")
        
        # Step 7: Fallback indicator if applicable
        if context.search_mode == "sql_only" and context.embedding_count == 0:
            sequence.append("⚠️  FALLBACK: Using SQL search only due to no embeddings")
        elif context.search_mode == "sql_favored":
            sequence.append("⚠️  FALLBACK: Favoring SQL search due to limited embeddings")
        
        # Step 8: LLM generation
        sequence.append("7️⃣  LLM response generation initiated")
        
        return sequence
    
    def _extract_emotional_patterns(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract emotional patterns and psychological indicators from search results"""
        emotional_analysis = {
            'anxiety_indicators': [],
            'health_concerns': [],
            'social_stressors': [],
            'work_pressures': [],
            'temporal_emotional_patterns': {},
            'emotional_intensity_markers': [],
            'recurring_themes': []
        }
        
        # Get emotional concepts using the new engine for each category
        try:
            anxiety_concepts = self.emotional_engine.expand_emotional_concepts(['fear', 'anxiety', 'worry'], max_expansions=10)
            health_concepts = self.emotional_engine.expand_emotional_concepts(['health', 'medical', 'symptoms'], max_expansions=10)
            social_concepts = self.emotional_engine.expand_emotional_concepts(['social', 'meeting', 'people'], max_expansions=10)
            work_concepts = self.emotional_engine.expand_emotional_concepts(['work', 'professional', 'job'], max_expansions=10)
            
            # Create a comprehensive emotional concept mapping
            emotional_concepts = {
                'anxiety_indicators': set(anxiety_concepts),
                'health_concerns': set(health_concepts),
                'social_stressors': set(social_concepts),
                'work_pressures': set(work_concepts)
            }
        except Exception as e:
            logger.warning(f"EmotionalConceptEngine failed for pattern extraction, using basic fallback: {e}")
            # Basic fallback
            emotional_concepts = {
                'anxiety_indicators': {'fear', 'anxiety', 'worry', 'concern', 'stress', 'nervous'},
                'health_concerns': {'health', 'medical', 'doctor', 'symptoms', 'pain', 'illness'},
                'social_stressors': {'social', 'meeting', 'party', 'people', 'gathering'},
                'work_pressures': {'work', 'professional', 'job', 'career', 'business'}
            }
        
        for item in results:
            content = item.get('content', '') or ''
            content_lower = content.lower()
            
            # Extract timestamp for temporal analysis
            timestamp = item.get('created_at', '') or item.get('updated_at', '')
            
            # Analyze content for emotional indicators using the new structure
            for category, concept_set in emotional_concepts.items():
                matched_concepts = []
                for concept in concept_set:
                    if concept.lower() in content_lower:
                        matched_concepts.append(concept)
                
                if matched_concepts:
                    # Create analysis entry based on category
                    analysis_entry = {
                        'content_snippet': content[:200] + '...' if len(content) > 200 else content,
                        'matched_concepts': matched_concepts,
                        'timestamp': timestamp,
                        'item_id': item.get('id', '')
                    }
                    
                    if category == 'anxiety_indicators':
                        analysis_entry['concept'] = matched_concepts[0]  # Primary concept
                        emotional_analysis['anxiety_indicators'].append(analysis_entry)
                    elif category == 'health_concerns':
                        analysis_entry['concern_type'] = matched_concepts[0]
                        emotional_analysis['health_concerns'].append(analysis_entry)
                    elif category == 'social_stressors':
                        analysis_entry['social_context'] = matched_concepts[0]
                        emotional_analysis['social_stressors'].append(analysis_entry)
                    elif category == 'work_pressures':
                        analysis_entry['work_context'] = matched_concepts[0]
                        emotional_analysis['work_pressures'].append(analysis_entry)
            
            # Look for emotional intensity markers
            intensity_words = ['very', 'extremely', 'really', 'quite', 'pretty', 'somewhat', 'a bit', 'little']
            emotional_words = ['worried', 'scared', 'anxious', 'concerned', 'stressed', 'tired', 'exhausted']
            
            for intensity in intensity_words:
                for emotion in emotional_words:
                    if f"{intensity} {emotion}" in content_lower:
                        emotional_analysis['emotional_intensity_markers'].append({
                            'intensity': intensity,
                            'emotion': emotion,
                            'context': content[:300] + '...' if len(content) > 300 else content,
                            'timestamp': timestamp
                        })
        
        # Analyze temporal patterns in emotional content
        if emotional_analysis['anxiety_indicators']:
            # Group by time periods (simplified - could be enhanced with actual date parsing)
            for indicator in emotional_analysis['anxiety_indicators']:
                if indicator['timestamp']:
                    # Extract day/time info from timestamp for pattern analysis
                    time_key = indicator['timestamp'][:10] if len(indicator['timestamp']) >= 10 else 'unknown'
                    if time_key not in emotional_analysis['temporal_emotional_patterns']:
                        emotional_analysis['temporal_emotional_patterns'][time_key] = []
                    emotional_analysis['temporal_emotional_patterns'][time_key].append(indicator['concept'])
        
        return emotional_analysis

    def _build_context_text(self, context: ChatContext) -> str:
        """
        Build comprehensive context text from search results with enhanced entity relationships,
        structured facts, and comprehensive data utilization for advanced AI assistant behavior
        """
        context_parts = []
        all_items = []
        
        logger.debug(f"Context Building - Starting with {len(context.vector_results)} vector results, {len(context.sql_results)} SQL results")
        
        # Combine all results for comprehensive analysis - increased limits
        all_items.extend(context.vector_results[:15])  # Increased from 10 to 15
        
        # Add unique SQL results
        vector_ids = {item.get('id') for item in context.vector_results}
        unique_sql_results = [
            item for item in context.sql_results[:15]  # Increased from 10 to 15
            if item.get('id') not in vector_ids
        ]
        all_items.extend(unique_sql_results)
        
        if not all_items:
            logger.warning("Context Building - No context items available")
            return "No relevant information found in your personal data."
        
        # Build comprehensive structured context for advanced AI analysis
        context_parts.append("=== COMPREHENSIVE PERSONAL DATA ANALYSIS ===")
        
        # Extract and organize information with enhanced categorization
        entities_found = set()
        entity_attributes = {}
        conversations = []
        activities = []
        relationships = []
        facts = []
        temporal_patterns = []
        behavioral_indicators = []
        
        # Extract emotional patterns for enhanced psychological analysis
        emotional_patterns = self._extract_emotional_patterns(all_items)
        logger.info(f"🧠 EMOTIONAL ANALYSIS: Extracted {len(emotional_patterns['anxiety_indicators'])} anxiety indicators, {len(emotional_patterns['health_concerns'])} health concerns, {len(emotional_patterns['social_stressors'])} social stressors")
        
        for item in all_items:
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            timestamp = item.get('created_at', 'Unknown time')
            namespace = item.get('namespace', 'Unknown')
            source_id = item.get('source_id', 'Unknown')
            
            # Enhanced preprocessing data extraction
            summary_content = item.get('summary_content', '')
            named_entities = item.get('named_entities', '')
            content_classification = item.get('content_classification', '')
            
            # Use full content for comprehensive analysis - increased limit
            full_content = content[:2000]  # Increased from 1500 to 2000 characters
            
            # Combine content with enhanced preprocessing data for richer analysis
            analysis_text = content
            if summary_content:
                analysis_text += f" [SUMMARY: {summary_content}]"
            if named_entities:
                analysis_text += f" [ENTITIES: {named_entities}]"
            if content_classification:
                analysis_text += f" [CLASSIFICATION: {content_classification}]"
            
            # Categorize by content type and source
            content_lower = content.lower()
            analysis_text_lower = analysis_text.lower()  # Use enhanced text for analysis
            
            # Use NER service for intelligent entity extraction and relationship mapping
            if self.ner_service.is_available():
                try:
                    ner_analysis = self.ner_service.analyze_content_for_context(analysis_text)
                    
                    # Merge NER results with our tracking structures
                    if ner_analysis:
                        entities_found.update(ner_analysis.get('entities_found', set()))
                        
                        # Merge entity attributes
                        for key, attrs in ner_analysis.get('entity_attributes', {}).items():
                            if key not in entity_attributes:
                                entity_attributes[key] = {'mentions': [], 'contexts': [], 'attributes': []}
                            entity_attributes[key]['mentions'].extend(attrs.get('mentions', []))
                            entity_attributes[key]['contexts'].append(namespace)
                            entity_attributes[key]['attributes'].extend(attrs.get('attributes', []))
                        
                        # Add relationships
                        for rel in ner_analysis.get('relationships', []):
                            relationships.append(rel)
                        
                        # Add behavioral indicators
                        behavioral_indicators.extend(ner_analysis.get('behavioral_indicators', []))
                        
                        logger.debug(f"NER analysis found {len(ner_analysis.get('entities_found', set()))} entity types in item {item.get('id', 'unknown')}")
                    
                except Exception as e:
                    logger.warning(f"NER analysis failed for item {item.get('id', 'unknown')}: {e}")
            
            # Additional temporal pattern detection (simple keyword-based)
            import re
            time_indicators = ['today', 'yesterday', 'tomorrow', 'morning', 'afternoon', 'evening', 'night', 'weekend']
            time_matches = [word for word in time_indicators if word in analysis_text_lower]
            if time_matches:
                temporal_patterns.append(f'{timestamp}: {", ".join(time_matches)}')
            
            # Email detection (supplementary to NER)
            email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
            emails = re.findall(email_pattern, analysis_text)
            for email in emails:
                # Check if email belongs to any detected person
                for person_name in [name for name in entity_attributes.keys() if not name.startswith('pet_name_')]:
                    if any(part in email.lower() for part in person_name.split('_')):
                        if person_name not in entity_attributes:
                            entity_attributes[person_name] = {'mentions': [], 'contexts': [], 'attributes': []}
                        entity_attributes[person_name]['attributes'].append(f'email: {email}')
                        entities_found.add(f'{person_name}_email_found')
                
            # Enhanced content categorization with metadata integration - use enhanced analysis text
            if (metadata and 'speaker' in metadata) or 'conversation' in analysis_text_lower or 'said' in analysis_text_lower:
                conversations.append({
                    'content': full_content,
                    'enhanced_content': analysis_text[:500],  # Include enhanced data preview
                    'timestamp': timestamp,
                    'metadata': metadata,
                    'namespace': namespace,
                    'source_id': source_id,
                    'speakers': metadata.get('speaker', 'Unknown'),
                    'named_entities': named_entities,
                    'summary_content': summary_content
                })
            elif any(activity_word in analysis_text_lower for activity_word in ['went', 'visited', 'did', 'activity', 'meeting', 'traveled', 'walked']):
                activities.append({
                    'content': full_content,
                    'enhanced_content': analysis_text[:500],
                    'timestamp': timestamp,
                    'metadata': metadata,
                    'namespace': namespace,
                    'source_id': source_id,
                    'named_entities': named_entities,
                    'summary_content': summary_content
                })
            else:
                facts.append({
                    'content': full_content,
                    'enhanced_content': analysis_text[:500],
                    'timestamp': timestamp,
                    'metadata': metadata,
                    'namespace': namespace,
                    'source_id': source_id,
                    'named_entities': named_entities,
                    'summary_content': summary_content
                })
        
        # Build comprehensive structured sections for advanced AI analysis
        if conversations:
            context_parts.append("\n=== CONVERSATION DATA ===")
            for i, conv in enumerate(conversations[:7], 1):  # Increased from 5 to 7
                speaker_info = f" [Speaker: {conv['speakers']}]" if conv['speakers'] != 'Unknown' else ""
                source_info = f" [Source: {conv['namespace']}]"
                entities_info = f" [Entities: {conv['named_entities']}]" if conv.get('named_entities') else ""
                summary_info = f" [Summary: {conv['summary_content'][:100]}...]" if conv.get('summary_content') else ""
                context_parts.append(f"{i}. {conv['content']}{speaker_info}{source_info}{entities_info}{summary_info}")
                
        if activities:
            context_parts.append("\n=== ACTIVITY DATA ===")
            for i, activity in enumerate(activities[:5], 1):  # Increased from 3 to 5
                source_info = f" [Source: {activity['namespace']}]"
                entities_info = f" [Entities: {activity['named_entities']}]" if activity.get('named_entities') else ""
                summary_info = f" [Summary: {activity['summary_content'][:100]}...]" if activity.get('summary_content') else ""
                context_parts.append(f"{i}. {activity['content']}{source_info}{entities_info}{summary_info}")
                
        if facts:
            context_parts.append("\n=== FACTUAL DATA ===")
            for i, fact in enumerate(facts[:5], 1):  # Increased from 3 to 5
                source_info = f" [Source: {fact['namespace']}]"
                entities_info = f" [Entities: {fact['named_entities']}]" if fact.get('named_entities') else ""
                summary_info = f" [Summary: {fact['summary_content'][:100]}...]" if fact.get('summary_content') else ""
                context_parts.append(f"{i}. {fact['content']}{source_info}{entities_info}{summary_info}")
        
        # Comprehensive entity relationship mapping for advanced AI inference
        if entities_found:
            context_parts.append("\n=== ENTITY ANALYSIS & RELATIONSHIP MAP ===")
            entity_insights = []
            
            # Pet relationship analysis using NER results
            if 'pets_mentioned' in entities_found:
                pet_names = [e for e in entities_found if e.startswith('pet_name_')]
                if pet_names:
                    pet_details = []
                    for pet_key in pet_names:
                        name = pet_key.replace('pet_name_', '').title()
                        if pet_key in entity_attributes:
                            contexts = set(entity_attributes[pet_key]['contexts'])
                            attributes = entity_attributes[pet_key].get('attributes', [])
                            detail = f"{name} (contexts: {', '.join(contexts)}"
                            if attributes:
                                detail += f", {', '.join(attributes)}"
                            detail += ")"
                            pet_details.append(detail)
                        else:
                            pet_details.append(name)
                    entity_insights.append(f"• PETS IDENTIFIED: {', '.join(pet_details)}")
                else:
                    entity_insights.append("• PET REFERENCES: Unnamed pets/dogs mentioned")
            
            # Person analysis using NER results - generalized for any detected people
            people_entities = [e for e in entities_found if e.endswith('_mentioned') and e not in ['pets_mentioned']]
            for person_entity in people_entities:
                person_name = person_entity.replace('_mentioned', '')
                if person_name in entity_attributes:
                    person_profile = [f"{person_name.title()} (detected person)"]
                    contexts = set(entity_attributes[person_name]['contexts'])
                    person_profile.append(f"mentioned across {len(contexts)} data sources: {', '.join(contexts)}")
                    
                    attributes = entity_attributes[person_name].get('attributes', [])
                    if attributes:
                        person_profile.append(f"attributes: {', '.join(attributes)}")
                    
                    entity_insights.append(f"• PERSON: {' | '.join(person_profile)}")
            
            # Relationship analysis using NER detected relationships
            if relationships:
                context_parts.append("\n=== DETECTED RELATIONSHIPS ===")
                for i, rel in enumerate(relationships[:5], 1):
                    if isinstance(rel, dict):
                        rel_type = rel.get('type', 'unknown')
                        if rel_type == 'pet_ownership':
                            owner = rel.get('owner', 'Unknown')
                            pet = rel.get('pet', 'Unknown')
                            confidence = rel.get('confidence', 0.0)
                            context_parts.append(f"• Relationship {i}: {owner} owns pet {pet} (confidence: {confidence:.2f})")
                    else:
                        # Handle Relationship dataclass objects
                        context_parts.append(f"• Relationship {i}: {rel.subject.text} {rel.predicate} {rel.object.text} (confidence: {rel.confidence:.2f})")
            
            # Location and organization analysis
            location_entities = [e for e in entities_found if e == 'location_mentioned']
            if location_entities:
                entity_insights.append("• LOCATIONS: Geographic references detected")
            
            org_entities = [e for e in entities_found if e == 'organization_mentioned']  
            if org_entities:
                entity_insights.append("• ORGANIZATIONS: Business/organization references detected")
            
            # Emotional and psychological pattern analysis
            if any(emotional_patterns.values()):
                context_parts.append("\n=== EMOTIONAL & PSYCHOLOGICAL PATTERN ANALYSIS ===")
                
                if emotional_patterns['anxiety_indicators']:
                    context_parts.append("• ANXIETY/FEAR INDICATORS:")
                    for indicator in emotional_patterns['anxiety_indicators'][:3]:
                        context_parts.append(f"  - {indicator['concept'].upper()}: {indicator['content_snippet']} [{indicator['timestamp'][:10] if indicator['timestamp'] else 'unknown date'}]")
                
                if emotional_patterns['health_concerns']:
                    context_parts.append("• HEALTH-RELATED CONCERNS:")
                    for concern in emotional_patterns['health_concerns'][:3]:
                        context_parts.append(f"  - {concern['concern_type'].upper()}: {concern['content_snippet']} [{concern['timestamp'][:10] if concern['timestamp'] else 'unknown date'}]")
                
                if emotional_patterns['social_stressors']:
                    context_parts.append("• SOCIAL INTERACTION PATTERNS:")
                    for stressor in emotional_patterns['social_stressors'][:3]:
                        context_parts.append(f"  - {stressor['social_context'].upper()}: {stressor['content_snippet']} [{stressor['timestamp'][:10] if stressor['timestamp'] else 'unknown date'}]")
                
                if emotional_patterns['work_pressures']:
                    context_parts.append("• PROFESSIONAL/WORK RELATED CONCERNS:")
                    for pressure in emotional_patterns['work_pressures'][:3]:
                        context_parts.append(f"  - {pressure['work_context'].upper()}: {pressure['content_snippet']} [{pressure['timestamp'][:10] if pressure['timestamp'] else 'unknown date'}]")
                
                if emotional_patterns['emotional_intensity_markers']:
                    context_parts.append("• EMOTIONAL INTENSITY MARKERS:")
                    for marker in emotional_patterns['emotional_intensity_markers'][:3]:
                        context_parts.append(f"  - {marker['intensity'].upper()} {marker['emotion'].upper()}: {marker['context']} [{marker['timestamp'][:10] if marker['timestamp'] else 'unknown date'}]")
                
                if emotional_patterns['temporal_emotional_patterns']:
                    context_parts.append("• TEMPORAL EMOTIONAL PATTERNS:")
                    for date, concepts in emotional_patterns['temporal_emotional_patterns'].items():
                        concept_counts = {}
                        for concept in concepts:
                            concept_counts[concept] = concept_counts.get(concept, 0) + 1
                        pattern_summary = ", ".join([f"{concept}({count})" for concept, count in concept_counts.items()])
                        context_parts.append(f"  - {date}: {pattern_summary}")
            
            # Behavioral pattern analysis
            if behavioral_indicators:
                context_parts.append("\n=== BEHAVIORAL PATTERN ANALYSIS ===")
                context_parts.extend([f"• {indicator}" for indicator in behavioral_indicators[:10]])
            
            # Temporal pattern analysis
            if temporal_patterns:
                context_parts.append("\n=== TEMPORAL PATTERN ANALYSIS ===")
                context_parts.extend([f"• {pattern}" for pattern in temporal_patterns[:5]])
            
            context_parts.extend(entity_insights)
        
        # Data source summary for comprehensive understanding
        namespaces = set(item.get('namespace', 'Unknown') for item in all_items)
        context_parts.append(f"\n=== DATA SOURCE SUMMARY ===")
        context_parts.append(f"• Total data items analyzed: {len(all_items)}")
        context_parts.append(f"• Data sources: {', '.join(sorted(namespaces))}")
        context_parts.append(f"• Entity types detected: {len(entities_found)}")
        context_parts.append(f"• Behavioral indicators found: {len(behavioral_indicators)}")
        
        final_context = "\n".join(context_parts)
        logger.debug(f"Context Building - Comprehensive context: {len(context_parts)} sections, {len(final_context)} total characters, {len(entities_found)} entities detected")
        return final_context
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent chat history"""
        return self.database.get_chat_history(limit)
    
    async def close(self):
        """Close resources"""
        if self.llm_provider:
            await self.llm_provider.close()