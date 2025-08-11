from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import hashlib
import numpy as np
from dataclasses import dataclass
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
import asyncio

from sources.base import DataItem
from sources.limitless_processor import BaseProcessor
from core.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SpokenLine:
    """Represents a single spoken line from a conversation"""
    text: str
    speaker: Optional[str]
    speaker_id: Optional[str]  # 'user' or 'other'
    timestamp: Optional[str]
    conversation_id: str
    node_data: Dict[str, Any]
    line_hash: str = None
    
    def __post_init__(self):
        if self.line_hash is None:
            self.line_hash = hashlib.sha256(self.text.encode()).hexdigest()[:16]


@dataclass
class LineVariation:
    """Represents a variation of a canonical line within a cluster"""
    original_text: str
    speaker: str
    timestamp: str
    conversation_id: str
    similarity_to_canonical: float
    line_hash: str


@dataclass
class SemanticCluster:
    """Represents a cluster of semantically similar lines"""
    cluster_id: str
    theme: str
    canonical_line: str
    canonical_hash: str
    variations: List[LineVariation]
    confidence_score: float
    frequency_count: int
    
    def get_canonical_variation(self) -> LineVariation:
        """Get the canonical line as a LineVariation object"""
        for variation in self.variations:
            if variation.original_text == self.canonical_line:
                return variation
        # Fallback - shouldn't happen if data is consistent
        return self.variations[0] if self.variations else None


@dataclass
class ProcessingResult:
    """Result of semantic deduplication processing"""
    total_processed: int
    clusters_created: int
    processing_time: float
    items_modified: int
    errors: List[str]


class SemanticDeduplicationProcessor(BaseProcessor):
    """Processor that identifies and groups semantically similar spoken lines"""
    
    def __init__(self, 
                 similarity_threshold: float = 0.85,
                 min_line_words: int = 3,
                 max_line_words: int = 100,
                 clustering_method: str = "hierarchical",
                 enable_cross_speaker_clustering: bool = True,
                 min_cluster_size: int = 2,
                 embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize semantic deduplication processor
        
        Args:
            similarity_threshold: Minimum similarity for clustering (0.0-1.0)
            min_line_words: Minimum words for a line to be considered
            max_line_words: Maximum words for a line to be processed
            clustering_method: 'hierarchical' or 'dbscan'
            enable_cross_speaker_clustering: Allow clustering across different speakers
            min_cluster_size: Minimum size for a valid cluster
            embedding_service: Service for generating embeddings
        """
        self.similarity_threshold = similarity_threshold
        self.min_line_words = min_line_words
        self.max_line_words = max_line_words
        self.clustering_method = clustering_method
        self.enable_cross_speaker_clustering = enable_cross_speaker_clustering
        self.min_cluster_size = min_cluster_size
        
        # Initialize embedding service
        self.embedding_service = embedding_service
        if not self.embedding_service:
            from config.factory import ConfigFactory
            config = ConfigFactory.create_config()
            self.embedding_service = EmbeddingService(config.embeddings)
        
        # Cache for embeddings and similarities
        self.embedding_cache: Dict[str, np.ndarray] = {}
        self.similarity_cache: Dict[str, float] = {}
        
        logger.info(f"Initialized SemanticDeduplicationProcessor with threshold={similarity_threshold}")
    
    async def process_batch(self, items: List[DataItem]) -> List[DataItem]:
        """
        Process multiple items for cross-conversation semantic deduplication
        
        Args:
            items: List of DataItem objects to process
            
        Returns:
            List of processed DataItem objects with semantic deduplication applied
        """
        logger.info(f"Processing batch of {len(items)} items for semantic deduplication")
        
        try:
            # Extract all spoken lines from conversations
            all_lines = self._extract_spoken_lines(items)
            logger.info(f"Extracted {len(all_lines)} spoken lines for analysis")
            
            if len(all_lines) < 2:
                logger.info("Not enough lines for clustering, skipping semantic deduplication")
                return items
            
            # Generate embeddings for all lines
            line_embeddings = await self._generate_embeddings(all_lines)
            logger.info(f"Generated embeddings for {len(line_embeddings)} lines")
            
            # Identify semantic clusters
            clusters = self._identify_clusters(all_lines, line_embeddings)
            logger.info(f"Identified {len(clusters)} semantic clusters")
            
            # Create display conversations with deduplication applied
            processed_items = self._create_display_conversations(items, clusters)
            logger.info(f"Created display conversations for {len(processed_items)} items")
            
            # Add processing history
            for item in processed_items:
                if 'processing_history' not in item.metadata:
                    item.metadata['processing_history'] = []
                
                item.metadata['processing_history'].append({
                    'processor': self.get_processor_name(),
                    'timestamp': datetime.now().isoformat(),
                    'changes': f'semantic_deduplication_{len(clusters)}_clusters'
                })
            
            return processed_items
            
        except Exception as e:
            logger.error(f"Error in semantic deduplication processing: {e}")
            # Return original items on error to prevent data loss
            return items
    
    def process(self, item: DataItem) -> DataItem:
        """
        Single item processing - delegates to batch processing
        Note: Semantic deduplication is most effective with multiple items
        """
        # For single items, we can't do cross-conversation deduplication
        # But we can still process internal conversation deduplication
        
        try:
            # Check if we're already in a running event loop
            loop = asyncio.get_running_loop()
            # We're in an async context, but this is a sync method
            # We'll skip semantic deduplication for single items in this case
            # and recommend using process_batch() instead
            logger.warning("Semantic deduplication skipped for single item in async context. Use process_batch() for full functionality.")
            return item
        except RuntimeError:
            # No running loop, safe to create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                processed_items = loop.run_until_complete(self.process_batch([item]))
                return processed_items[0] if processed_items else item
            finally:
                loop.close()
    
    def _extract_spoken_lines(self, items: List[DataItem]) -> List[SpokenLine]:
        """Extract individual spoken lines from conversation items"""
        lines = []
        
        for item in items:
            # Handle both old and new metadata structure
            if 'original_response' in item.metadata:
                # New two-key structure
                original_lifelog = item.metadata.get('original_response', {})
            else:
                # Legacy structure
                original_lifelog = item.metadata.get('original_lifelog', {})
            contents = original_lifelog.get('contents', [])
            
            for node in contents:
                content = node.get('content', '').strip()
                word_count = len(content.split()) if content else 0
                
                # Filter lines based on criteria
                if (content and 
                    word_count >= self.min_line_words and
                    word_count <= self.max_line_words and
                    node.get('type') == 'blockquote'):
                    
                    lines.append(SpokenLine(
                        text=content,
                        speaker=node.get('speakerName'),
                        speaker_id=node.get('speakerIdentifier'),
                        timestamp=node.get('startTime'),
                        conversation_id=item.source_id,
                        node_data=node
                    ))
        
        logger.debug(f"Extracted {len(lines)} spoken lines from {len(items)} items")
        return lines
    
    async def _generate_embeddings(self, lines: List[SpokenLine]) -> Dict[str, np.ndarray]:
        """Generate embeddings for all unique lines"""
        embeddings = {}
        lines_to_embed = []
        
        # Check cache first
        for line in lines:
            if line.line_hash in self.embedding_cache:
                embeddings[line.text] = self.embedding_cache[line.line_hash]
            else:
                lines_to_embed.append(line)
        
        # Generate embeddings for uncached lines
        if lines_to_embed:
            logger.info(f"Generating embeddings for {len(lines_to_embed)} new lines")
            
            texts = [line.text for line in lines_to_embed]
            new_embeddings = await self.embedding_service.embed_texts(texts)
            
            # Cache and store results
            for line, embedding in zip(lines_to_embed, new_embeddings):
                self.embedding_cache[line.line_hash] = embedding
                embeddings[line.text] = embedding
        
        return embeddings
    
    def _identify_clusters(self, lines: List[SpokenLine], 
                          line_embeddings: Dict[str, np.ndarray]) -> List[SemanticCluster]:
        """Identify clusters of semantically similar lines"""
        
        if len(line_embeddings) < self.min_cluster_size:
            logger.info(f"Not enough lines ({len(line_embeddings)}) for clustering")
            return []
        
        # Prepare data for clustering
        texts = list(line_embeddings.keys())
        embeddings_matrix = np.array([line_embeddings[text] for text in texts])
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(embeddings_matrix)
        
        # Convert similarity to distance (1 - similarity for clustering)
        distance_matrix = 1 - similarity_matrix
        
        # Apply clustering
        if self.clustering_method == "hierarchical":
            clusters = self._hierarchical_clustering(lines, texts, distance_matrix)
        else:
            # Future: implement DBSCAN clustering
            logger.warning("DBSCAN clustering not yet implemented, using hierarchical")
            clusters = self._hierarchical_clustering(lines, texts, distance_matrix)
        
        # Filter clusters by quality
        quality_clusters = self._filter_quality_clusters(clusters, similarity_matrix, texts)
        
        logger.info(f"Created {len(quality_clusters)} quality clusters from {len(clusters)} raw clusters")
        return quality_clusters
    
    def _hierarchical_clustering(self, lines: List[SpokenLine], texts: List[str], 
                                distance_matrix: np.ndarray) -> List[SemanticCluster]:
        """Perform hierarchical clustering on lines"""
        
        # Use agglomerative clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - self.similarity_threshold,  # Convert similarity to distance
            metric='precomputed',
            linkage='average'
        )
        
        cluster_labels = clustering.fit_predict(distance_matrix)
        
        # Group lines by cluster
        clusters_dict = {}
        for i, label in enumerate(cluster_labels):
            if label not in clusters_dict:
                clusters_dict[label] = []
            
            # Find the corresponding line
            text = texts[i]
            line = next((l for l in lines if l.text == text), None)
            if line:
                clusters_dict[label].append(line)
        
        # Convert to SemanticCluster objects
        clusters = []
        for label, cluster_lines in clusters_dict.items():
            if len(cluster_lines) >= self.min_cluster_size:
                cluster = self._create_semantic_cluster(label, cluster_lines)
                if cluster:
                    clusters.append(cluster)
        
        return clusters
    
    def _create_semantic_cluster(self, label: int, lines: List[SpokenLine]) -> Optional[SemanticCluster]:
        """Create a SemanticCluster from a group of similar lines"""
        
        if not lines:
            return None
        
        # Choose canonical line (first occurrence by timestamp)
        canonical_line = self._choose_canonical_line(lines)
        
        # Create variations
        variations = []
        for line in lines:
            # Calculate similarity to canonical (approximate for now)
            similarity = 0.9 if line.text != canonical_line.text else 1.0
            
            variations.append(LineVariation(
                original_text=line.text,
                speaker=line.speaker or "Unknown",
                timestamp=line.timestamp or "",
                conversation_id=line.conversation_id,
                similarity_to_canonical=similarity,
                line_hash=line.line_hash
            ))
        
        # Generate theme from canonical line (simplified)
        theme = self._generate_theme(canonical_line.text)
        
        # Calculate cluster confidence (simplified)
        confidence = min(0.95, 0.7 + (len(lines) * 0.05))  # Higher confidence with more examples
        
        cluster_id = f"{theme}_{label:03d}"
        
        return SemanticCluster(
            cluster_id=cluster_id,
            theme=theme,
            canonical_line=canonical_line.text,
            canonical_hash=canonical_line.line_hash,
            variations=variations,
            confidence_score=confidence,
            frequency_count=len(lines)
        )
    
    def _choose_canonical_line(self, lines: List[SpokenLine]) -> SpokenLine:
        """Choose the canonical line from a cluster"""
        
        # Strategy 1: Choose first occurrence chronologically
        lines_with_time = [line for line in lines if line.timestamp]
        if lines_with_time:
            try:
                sorted_lines = sorted(lines_with_time, 
                                    key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')))
                return sorted_lines[0]
            except (ValueError, TypeError):
                pass
        
        # Strategy 2: Choose shortest clear version
        return min(lines, key=lambda x: len(x.text.split()))
    
    def _generate_theme(self, text: str) -> str:
        """Generate a theme name from canonical text"""
        
        # Extract key words and create theme
        words = text.lower().split()
        
        # Simple keyword-based theme generation
        if any(word in text.lower() for word in ['weather', 'hot', 'cold', 'rain', 'snow']):
            return 'weather_comments'
        elif any(word in text.lower() for word in ['meeting', 'work', 'project', 'deadline']):
            return 'work_discussion'
        elif any(word in text.lower() for word in ['tired', 'exhausted', 'energy', 'sleep']):
            return 'energy_state'
        elif any(word in text.lower() for word in ['food', 'eat', 'hungry', 'lunch', 'dinner']):
            return 'food_related'
        else:
            # Generic theme based on first significant word
            significant_words = [w for w in words if len(w) > 3 and w not in ['this', 'that', 'with', 'have']]
            if significant_words:
                return f"{significant_words[0]}_topic"
            else:
                return 'general_conversation'
    
    def _filter_quality_clusters(self, clusters: List[SemanticCluster], 
                                similarity_matrix: np.ndarray, texts: List[str]) -> List[SemanticCluster]:
        """Filter clusters based on quality metrics"""
        
        quality_clusters = []
        
        for cluster in clusters:
            # Check minimum cluster size
            if cluster.frequency_count < self.min_cluster_size:
                continue
            
            # Check if cross-speaker clustering is enabled
            if not self.enable_cross_speaker_clustering:
                speakers = set(var.speaker for var in cluster.variations)
                if len(speakers) > 1:
                    continue
            
            # Additional quality checks could be added here
            # - Internal cluster coherence
            # - Cluster separation from other clusters
            # - Semantic meaningfulness
            
            quality_clusters.append(cluster)
        
        return quality_clusters
    
    def _create_display_conversations(self, items: List[DataItem], 
                                    clusters: List[SemanticCluster]) -> List[DataItem]:
        """Create display conversations with semantic deduplication applied"""
        
        # Build lookup for quick cluster identification
        text_to_cluster = {}
        for cluster in clusters:
            for variation in cluster.variations:
                text_to_cluster[variation.original_text] = cluster
        
        processed_items = []
        
        for item in items:
            # Handle both old and new metadata structure
            if 'original_response' in item.metadata:
                # New two-key structure
                original_lifelog = item.metadata.get('original_response', {})
            else:
                # Legacy structure
                original_lifelog = item.metadata.get('original_lifelog', {})
            contents = original_lifelog.get('contents', [])
            
            display_nodes = []
            used_clusters = {}
            
            for node in contents:
                content = node.get('content', '').strip()
                
                # Check if this line is part of a cluster
                cluster = text_to_cluster.get(content)
                
                if cluster:
                    # This line is part of a semantic cluster
                    if cluster.cluster_id not in used_clusters:
                        # First occurrence of this cluster - show canonical line
                        canonical_var = cluster.get_canonical_variation()
                        if canonical_var and canonical_var.original_text == content:
                            # This IS the canonical line - include it
                            display_nodes.append({
                                **node,
                                "represents_cluster": cluster.cluster_id,
                                "hidden_variations": cluster.frequency_count - 1,
                                "is_deduplicated": True,
                                "canonical_confidence": cluster.confidence_score
                            })
                            used_clusters[cluster.cluster_id] = cluster
                        else:
                            # This is NOT the canonical - show canonical instead
                            canonical_node = dict(node)  # Copy original node structure
                            canonical_node.update({
                                "content": cluster.canonical_line,
                                "represents_cluster": cluster.cluster_id,
                                "hidden_variations": cluster.frequency_count - 1,
                                "is_deduplicated": True,
                                "canonical_confidence": cluster.confidence_score,
                                "replaced_original": content  # Track what was replaced
                            })
                            display_nodes.append(canonical_node)
                            used_clusters[cluster.cluster_id] = cluster
                    # Else: Skip this line (already showed canonical for this cluster)
                else:
                    # Unique line - always include
                    display_nodes.append({
                        **node,
                        "is_unique": True
                    })
            
            # Create cluster metadata for frontend
            cluster_metadata = {}
            for cluster_id, cluster in used_clusters.items():
                cluster_metadata[cluster_id] = {
                    "theme": cluster.theme,
                    "canonical": cluster.canonical_line,
                    "variations": [
                        {
                            "text": var.original_text,
                            "speaker": var.speaker,
                            "similarity": var.similarity_to_canonical,
                            "timestamp": var.timestamp
                        }
                        for var in cluster.variations
                        if var.original_text != cluster.canonical_line
                    ],
                    "frequency": cluster.frequency_count,
                    "confidence": cluster.confidence_score
                }
            
            # Update item metadata - handle both old and new structure
            if 'processed_response' in item.metadata:
                # New two-key structure - update processed_response
                processed = item.metadata['processed_response']
                processed['display_conversation'] = display_nodes
                processed['semantic_clusters'] = cluster_metadata
                processed['semantic_metadata'] = {
                    "processed": True,
                    "total_lines_analyzed": len(contents),
                    "clustered_lines": len([n for n in display_nodes if n.get('is_deduplicated')]),
                    "unique_themes": list(set(c['theme'] for c in cluster_metadata.values())),
                    "semantic_density": len(display_nodes) / len(contents) if contents else 1.0,
                    "clusters_found": len(used_clusters)
                }
            else:
                # Legacy structure - update directly
                item.metadata['display_conversation'] = display_nodes
                item.metadata['semantic_clusters'] = cluster_metadata
                item.metadata['semantic_metadata'] = {
                    "processed": True,
                    "total_lines_analyzed": len(contents),
                    "clustered_lines": len([n for n in display_nodes if n.get('is_deduplicated')]),
                    "unique_themes": list(set(c['theme'] for c in cluster_metadata.values())),
                    "semantic_density": len(display_nodes) / len(contents) if contents else 1.0,
                    "clusters_found": len(used_clusters)
                }
            
            processed_items.append(item)
        
        return processed_items
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            "embedding_cache_size": len(self.embedding_cache),
            "similarity_cache_size": len(self.similarity_cache),
            "similarity_threshold": self.similarity_threshold,
            "min_line_words": self.min_line_words,
            "clustering_method": self.clustering_method
        }
    
    def clear_caches(self):
        """Clear processing caches to free memory"""
        self.embedding_cache.clear()
        self.similarity_cache.clear()
        logger.info("Cleared semantic deduplication caches")