"""
Intelligent Context Builder for Enhanced Chat Experience

Transforms raw search results from multiple sources (Limitless API, Vector, SQL)
into intelligent, prioritized, and summarized context for LLM response generation.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

from llm.base import LLMResponse, LLMError
from core.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """Represents a single context item with metadata"""
    id: str
    content: str
    source: str  # 'limitless', 'vector', 'sql'
    relevance_score: float
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None


@dataclass
class PrioritizedContext:
    """Prioritized and processed context ready for LLM"""
    items: List[ContextItem]
    summary: str
    source_attribution: Dict[str, int]  # source -> count
    total_items: int
    processing_time: float


class IntelligentContextBuilder:
    """Builds intelligent, prioritized context from multiple search sources"""
    
    def __init__(self, llm_provider, embedding_service: Optional[EmbeddingService] = None):
        self.llm_provider = llm_provider
        self.embedding_service = embedding_service
        
        # Source priority weights (higher = more important)
        self.source_weights = {
            'limitless': 1.0,  # Personal conversations - highest priority
            'vector': 0.7,    # Semantic relevance - medium priority  
            'sql': 0.5        # Keyword matches - lower priority
        }
        
        # Deduplication similarity threshold
        self.similarity_threshold = 0.85
        
    async def build_prioritized_context(self, 
                                      limitless_results: List[Dict[str, Any]],
                                      vector_results: List[Dict[str, Any]], 
                                      sql_results: List[Dict[str, Any]],
                                      query: str,
                                      max_context_length: int = 4000) -> PrioritizedContext:
        """Build intelligent, prioritized context from multiple sources"""
        start_time = time.time()
        
        logger.info(f"Building prioritized context: {len(limitless_results)} limitless, "
                   f"{len(vector_results)} vector, {len(sql_results)} sql results")
        
        # Step 1: Convert all results to ContextItems
        all_items = []
        all_items.extend(self._convert_to_context_items(limitless_results, 'limitless'))
        all_items.extend(self._convert_to_context_items(vector_results, 'vector'))
        all_items.extend(self._convert_to_context_items(sql_results, 'sql'))
        
        logger.debug(f"Converted {len(all_items)} total items to ContextItems")
        
        # Step 2: Remove semantic duplicates
        if self.embedding_service and len(all_items) > 1:
            deduplicated_items = await self._remove_semantic_duplicates(all_items)
            logger.info(f"Deduplication: {len(all_items)} -> {len(deduplicated_items)} items")
        else:
            deduplicated_items = all_items
            logger.debug("Skipping deduplication (no embedding service or insufficient items)")
        
        # Step 3: Calculate relevance scores and sort by priority
        scored_items = self._calculate_relevance_scores(deduplicated_items, query)
        prioritized_items = sorted(scored_items, key=lambda x: x.relevance_score, reverse=True)
        
        logger.debug(f"Top 3 relevance scores: {[item.relevance_score for item in prioritized_items[:3]]}")
        
        # Step 4: Select top items within context length limit
        selected_items = self._select_items_within_limit(prioritized_items, max_context_length)
        
        logger.info(f"Selected {len(selected_items)} items for context (within {max_context_length} char limit)")
        
        # Step 5: Generate intelligent summary
        context_summary = await self._generate_context_summary(selected_items, query)
        
        # Step 6: Build source attribution
        source_attribution = self._build_source_attribution(selected_items)
        
        processing_time = time.time() - start_time
        
        result = PrioritizedContext(
            items=selected_items,
            summary=context_summary,
            source_attribution=source_attribution,
            total_items=len(selected_items),
            processing_time=processing_time
        )
        
        logger.info(f"Context building completed in {processing_time:.3f}s: "
                   f"{result.total_items} items, {len(result.summary)} char summary")
        
        return result
    
    def _convert_to_context_items(self, results: List[Dict[str, Any]], source: str) -> List[ContextItem]:
        """Convert search results to ContextItems"""
        items = []
        
        for result in results:
            # Extract timestamp if available
            timestamp = None
            if 'created_at' in result and result['created_at']:
                try:
                    if isinstance(result['created_at'], str):
                        timestamp = datetime.fromisoformat(result['created_at'].replace('Z', '+00:00'))
                    elif isinstance(result['created_at'], datetime):
                        timestamp = result['created_at']
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp {result['created_at']}: {e}")
            
            item = ContextItem(
                id=result.get('id', f"{source}_{len(items)}"),
                content=result.get('content', ''),
                source=source,
                relevance_score=0.0,  # Will be calculated later
                timestamp=timestamp,
                metadata=result.get('metadata', {})
            )
            
            items.append(item)
        
        return items
    
    async def _remove_semantic_duplicates(self, items: List[ContextItem]) -> List[ContextItem]:
        """Remove semantically similar items using embeddings"""
        if not items or not self.embedding_service:
            return items
        
        logger.debug(f"Checking {len(items)} items for semantic duplicates")
        
        try:
            # Generate embeddings for all content
            contents = [item.content for item in items]
            embeddings = await self.embedding_service.embed_texts(contents)
            
            if not embeddings or len(embeddings) != len(items):
                logger.warning("Failed to generate embeddings for deduplication")
                return items
            
            # Find duplicates using cosine similarity
            unique_items = []
            used_indices = set()
            
            for i, item in enumerate(items):
                if i in used_indices:
                    continue
                
                # Check similarity with all subsequent items
                for j in range(i + 1, len(items)):
                    if j in used_indices:
                        continue
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(embeddings[i], embeddings[j])
                    
                    if similarity > self.similarity_threshold:
                        # Mark the lower priority item as duplicate
                        if self.source_weights[items[i].source] >= self.source_weights[items[j].source]:
                            used_indices.add(j)
                            logger.debug(f"Marked item {j} as duplicate of {i} (similarity: {similarity:.3f})")
                        else:
                            used_indices.add(i)
                            logger.debug(f"Marked item {i} as duplicate of {j} (similarity: {similarity:.3f})")
                            break
                
                if i not in used_indices:
                    unique_items.append(item)
            
            logger.info(f"Semantic deduplication: {len(items)} -> {len(unique_items)} items")
            return unique_items
            
        except Exception as e:
            logger.warning(f"Semantic deduplication failed: {e}")
            return items
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            import math
            
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            
            # Calculate magnitudes
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception as e:
            logger.debug(f"Cosine similarity calculation failed: {e}")
            return 0.0
    
    def _calculate_relevance_scores(self, items: List[ContextItem], query: str) -> List[ContextItem]:
        """Calculate relevance scores for context items"""
        current_time = datetime.now(timezone.utc)
        
        for item in items:
            # Base score from source priority
            base_score = self.source_weights[item.source]
            
            # Temporal relevance boost (more recent = higher score)
            temporal_boost = 0.0
            if item.timestamp:
                age_hours = (current_time - item.timestamp).total_seconds() / 3600
                # Boost recent items (within last 24 hours)
                if age_hours < 24:
                    temporal_boost = 0.3 * (1.0 - age_hours / 24)
            
            # Content length penalty (very short or very long content gets penalized)
            content_length = len(item.content)
            length_score = 1.0
            if content_length < 50:
                length_score = 0.7  # Too short
            elif content_length > 2000:
                length_score = 0.8  # Too long
            
            # Simple keyword relevance (basic implementation)
            keyword_boost = 0.0
            query_words = query.lower().split()
            content_lower = item.content.lower()
            matching_words = sum(1 for word in query_words if word in content_lower)
            if query_words:
                keyword_boost = 0.2 * (matching_words / len(query_words))
            
            # Calculate final score
            item.relevance_score = (base_score + temporal_boost + keyword_boost) * length_score
        
        return items
    
    def _select_items_within_limit(self, items: List[ContextItem], max_length: int) -> List[ContextItem]:
        """Select items that fit within the context length limit"""
        selected = []
        current_length = 0
        
        for item in items:
            item_length = len(item.content) + 50  # Add some overhead for formatting
            
            if current_length + item_length <= max_length:
                selected.append(item)
                current_length += item_length
            else:
                # Try to fit a truncated version
                remaining_space = max_length - current_length - 50
                if remaining_space > 100:  # Only if we have reasonable space left
                    truncated_content = item.content[:remaining_space] + "..."
                    truncated_item = ContextItem(
                        id=item.id,
                        content=truncated_content,
                        source=item.source,
                        relevance_score=item.relevance_score,
                        timestamp=item.timestamp,
                        metadata=item.metadata
                    )
                    selected.append(truncated_item)
                break
        
        return selected
    
    async def _generate_context_summary(self, items: List[ContextItem], query: str) -> str:
        """Generate an intelligent summary of the context"""
        if not items:
            return "No relevant information found in your personal data."
        
        if not self.llm_provider:
            return self._generate_simple_summary(items)
        
        try:
            # Extract query keywords for smart content preservation
            query_words = set(word.lower() for word in query.split() if len(word) > 2)
            
            # Prepare content for summarization with smarter truncation
            content_pieces = []
            for i, item in enumerate(items[:5], 1):  # Limit to top 5 for summarization
                source_label = {
                    'limitless': 'Recent conversation',
                    'vector': 'Related information', 
                    'sql': 'Relevant data'
                }.get(item.source, item.source)
                
                # Smart content extraction that preserves query-relevant parts
                smart_content = self._extract_relevant_content(item.content, query_words, 500)
                content_pieces.append(f"{i}. [{source_label}] {smart_content}")
            
            summary_prompt = f"""Based on the user's question "{query}", analyze the following information sources and provide a practical summary. Pay special attention to any specific names, entities, or details mentioned in the question:

{chr(10).join(content_pieces)}

Important: Draw logical conclusions from patterns in the data. If someone consistently calls for "Peach" in pet contexts, discusses her care, or mentions her alongside other pets, conclude that Peach is their pet. Use common sense reasoning - repeated pet-related interactions indicate ownership or primary care responsibility. Be direct and confident in your summary when evidence clearly supports a conclusion."""
            
            response = await self.llm_provider.generate_response(
                prompt=summary_prompt,
                context="",
                max_tokens=200,
                temperature=0.1  # Lower temperature for more factual responses
            )
            
            if response and response.content:
                return response.content.strip()
            else:
                return self._generate_simple_summary(items)
                
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            return self._generate_simple_summary(items)
    
    def _extract_relevant_content(self, content: str, query_words: set, max_length: int) -> str:
        """Extract relevant content that preserves query-relevant information"""
        if len(content) <= max_length:
            return content
        
        # Split content into sentences for smarter truncation
        import re
        sentences = re.split(r'[.!?]+', content)
        
        # Score sentences by relevance to query
        scored_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            score = 0
            sentence_lower = sentence.lower()
            
            # High score for sentences containing query words
            for word in query_words:
                if word in sentence_lower:
                    score += 10
            
            # Boost for sentences with proper nouns (likely names/entities)
            proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', sentence)
            score += len(proper_nouns) * 2
            
            scored_sentences.append((score, sentence))
        
        # Sort by relevance and build content within length limit
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        result_parts = []
        current_length = 0
        
        for score, sentence in scored_sentences:
            if current_length + len(sentence) + 2 <= max_length:  # +2 for ". "
                result_parts.append(sentence)
                current_length += len(sentence) + 2
            elif not result_parts:  # Ensure we include at least something
                result_parts.append(sentence[:max_length-3] + "...")
                break
        
        if result_parts:
            return ". ".join(result_parts) + "."
        else:
            # Fallback to simple truncation
            return content[:max_length-3] + "..."
    
    def _generate_simple_summary(self, items: List[ContextItem]) -> str:
        """Generate a simple summary without LLM"""
        if not items:
            return "No relevant information found."
        
        source_counts = self._build_source_attribution(items)
        
        summary_parts = []
        if source_counts.get('limitless', 0) > 0:
            summary_parts.append(f"{source_counts['limitless']} recent conversations")
        if source_counts.get('vector', 0) > 0:
            summary_parts.append(f"{source_counts['vector']} related topics")
        if source_counts.get('sql', 0) > 0:
            summary_parts.append(f"{source_counts['sql']} keyword matches")
        
        if summary_parts:
            return f"Found relevant information from: {', '.join(summary_parts)}"
        else:
            return f"Found {len(items)} relevant items in your personal data"
    
    def _build_source_attribution(self, items: List[ContextItem]) -> Dict[str, int]:
        """Build source attribution counts"""
        attribution = {}
        for item in items:
            attribution[item.source] = attribution.get(item.source, 0) + 1
        return attribution
    
    def format_context_for_llm(self, context: PrioritizedContext) -> str:
        """Format the prioritized context for LLM consumption"""
        if not context.items:
            return "No relevant information found in your personal data."
        
        context_parts = []
        
        # Add summary at the top
        context_parts.append(f"=== Context Summary ===")
        context_parts.append(context.summary)
        context_parts.append("")
        
        # Group items by source and add them with clear attribution
        source_groups = {}
        for item in context.items:
            if item.source not in source_groups:
                source_groups[item.source] = []
            source_groups[item.source].append(item)
        
        # Add each source group with proper headers
        source_headers = {
            'limitless': '=== From Your Recent Conversations ===',
            'vector': '=== Related Information (Semantic Search) ===',
            'sql': '=== Additional Relevant Information ===',
        }
        
        for source in ['limitless', 'vector', 'sql']:  # Maintain priority order
            if source in source_groups:
                context_parts.append(source_headers[source])
                for i, item in enumerate(source_groups[source], 1):
                    # Add timestamp if available
                    time_info = ""
                    if item.timestamp:
                        time_info = f" ({item.timestamp.strftime('%Y-%m-%d %H:%M')})"
                    
                    context_parts.append(f"{i}. {item.content}{time_info}")
                context_parts.append("")
        
        return "\n".join(context_parts)