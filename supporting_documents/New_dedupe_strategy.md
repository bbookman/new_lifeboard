# New Semantic Deduplication Strategy

## Executive Summary

This document outlines the implementation of a semantic deduplication system for Lifeboard conversations. The system will identify semantically similar content lines (e.g., "I hate this weather" and "this weather is terrible") and create filtered conversation displays that show only canonical lines while preserving the complete original conversation data.

## Goals and Requirements

### Primary Goals
- **Display Deduplication**: Show filtered conversations in UI cards with semantically redundant lines removed
- **Semantic Understanding**: Identify similar meanings across different phrasings
- **User Experience**: Provide cleaner, more readable conversation summaries
- **Flexibility**: Allow users to toggle between full and condensed views

### Technical Requirements
- **Clean Database Start**: Assume fresh database with no migration constraints
- **Replace Cleaned Markdown**: New structured approach eliminates need for `cleaned_markdown` field
- **Preserve Original Data**: Maintain complete conversation history for reference
- **Performance**: Handle large conversation datasets efficiently
- **Accuracy**: >85% semantic clustering accuracy

## Architecture Overview

### Data Flow Pipeline
```
Limitless API → Raw Conversation Data → Semantic Processing → Clustered Storage → Display Filtering → UI Rendering
```

### Core Components
1. **Semantic Deduplication Engine**: Identifies similar content lines using embeddings and clustering
2. **Display Conversation Generator**: Creates filtered conversation structure for UI
3. **Batch Processing Service**: Handles large-scale semantic analysis
4. **Enhanced Frontend Components**: Render filtered conversations with user controls

## Database Architecture

### New Schema Design

```sql
-- Semantic clusters table
CREATE TABLE semantic_clusters (
    id TEXT PRIMARY KEY,
    theme TEXT NOT NULL,                    -- "weather_complaints", "meeting_prep"
    canonical_line TEXT NOT NULL,          -- Representative line to display
    confidence_score REAL NOT NULL,        -- Clustering confidence (0.0-1.0)
    frequency_count INTEGER NOT NULL,      -- Number of similar lines
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bridge table linking lines to clusters
CREATE TABLE line_cluster_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_item_id TEXT NOT NULL,            -- References data_items.id
    line_content TEXT NOT NULL,            -- Original line text
    cluster_id TEXT NOT NULL,              -- References semantic_clusters.id
    similarity_score REAL NOT NULL,       -- How similar to canonical (0.0-1.0)
    speaker TEXT,                          -- Speaker name
    line_timestamp TEXT,                   -- Original timestamp
    is_canonical BOOLEAN DEFAULT FALSE,   -- Is this the canonical line?
    FOREIGN KEY (data_item_id) REFERENCES data_items(id),
    FOREIGN KEY (cluster_id) REFERENCES semantic_clusters(id)
);

-- Enhanced data_items metadata structure
-- metadata JSON now includes:
{
  "original_lifelog": {...},              // Complete API response
  "display_conversation": [...],          // Filtered conversation for UI
  "semantic_metadata": {
    "processed": true,
    "total_lines_analyzed": 15,
    "clustered_lines": 8,
    "unique_themes": ["weather_complaints", "meeting_prep"],
    "dominant_cluster": "weather_complaints",
    "semantic_density": 0.65              // Ratio of unique to total content
  },
  "processing_history": [...]             // Pipeline tracking
}
```

### Indexes for Performance
```sql
CREATE INDEX idx_clusters_theme ON semantic_clusters(theme);
CREATE INDEX idx_clusters_frequency ON semantic_clusters(frequency_count DESC);
CREATE INDEX idx_line_mapping_item ON line_cluster_mapping(data_item_id);
CREATE INDEX idx_line_mapping_cluster ON line_cluster_mapping(cluster_id);
CREATE INDEX idx_line_mapping_canonical ON line_cluster_mapping(is_canonical);
```

## Data Structure Design

### Enhanced Conversation Format

**Input: Original Limitless Data**
```json
{
  "contents": [
    {
      "content": "wow it is really hot",
      "type": "blockquote",
      "speakerName": "John",
      "startTime": "2024-01-15T10:30:00Z"
    },
    {
      "content": "i hate this heat", 
      "type": "blockquote",
      "speakerName": "John",
      "startTime": "2024-01-15T10:31:00Z"
    },
    {
      "content": "let's go inside",
      "type": "blockquote", 
      "speakerName": "Sarah",
      "startTime": "2024-01-15T10:32:00Z"
    }
  ]
}
```

**Output: Processed Conversation Structure**
```json
{
  "original_conversation": [
    // Complete original data preserved
  ],
  "display_conversation": [
    {
      "content": "wow it is really hot",
      "speaker": "John",
      "timestamp": "2024-01-15T10:30:00Z",
      "type": "blockquote",
      "represents_cluster": "heat_complaints_001",
      "hidden_variations": 1,
      "is_deduplicated": true,
      "canonical_confidence": 0.92
    },
    {
      "content": "let's go inside",
      "speaker": "Sarah", 
      "timestamp": "2024-01-15T10:32:00Z",
      "type": "blockquote",
      "is_unique": true
    }
  ],
  "semantic_clusters": {
    "heat_complaints_001": {
      "theme": "heat_complaints",
      "canonical": "wow it is really hot",
      "variations": [
        {
          "text": "i hate this heat",
          "speaker": "John",
          "similarity": 0.87,
          "timestamp": "2024-01-15T10:31:00Z"
        }
      ],
      "frequency": 2,
      "confidence": 0.89
    }
  }
}
```

## Technical Implementation

### 1. Semantic Deduplication Processor

```python
class SemanticDeduplicationProcessor(BaseProcessor):
    """Identifies and groups semantically similar spoken lines"""
    
    def __init__(self, 
                 similarity_threshold: float = 0.85,
                 min_line_words: int = 3,
                 clustering_method: str = "hierarchical",
                 enable_cross_speaker_clustering: bool = True):
        self.embedding_service = EmbeddingService()
        self.similarity_threshold = similarity_threshold
        self.min_line_words = min_line_words
        self.clustering_method = clustering_method
        self.enable_cross_speaker_clustering = enable_cross_speaker_clustering
        self.similarity_cache = {}
    
    async def process_batch(self, items: List[DataItem]) -> List[DataItem]:
        """Process multiple items for cross-conversation deduplication"""
        # Extract all spoken lines
        all_lines = self._extract_spoken_lines(items)
        
        # Generate embeddings
        line_embeddings = await self._generate_embeddings(all_lines)
        
        # Identify semantic clusters
        clusters = self._identify_clusters(line_embeddings)
        
        # Generate display conversations
        return self._create_display_conversations(items, clusters)
    
    def _extract_spoken_lines(self, items: List[DataItem]) -> List[SpokenLine]:
        """Extract individual spoken lines from conversations"""
        lines = []
        for item in items:
            original_lifelog = item.metadata.get('original_lifelog', {})
            contents = original_lifelog.get('contents', [])
            
            for node in contents:
                content = node.get('content', '').strip()
                if (content and 
                    len(content.split()) >= self.min_line_words and
                    node.get('type') == 'blockquote'):
                    
                    lines.append(SpokenLine(
                        text=content,
                        speaker=node.get('speakerName'),
                        speaker_id=node.get('speakerIdentifier'),
                        timestamp=node.get('startTime'),
                        conversation_id=item.source_id,
                        node_data=node
                    ))
        
        return lines
    
    async def _generate_embeddings(self, lines: List[SpokenLine]) -> Dict[str, np.ndarray]:
        """Generate embeddings for all lines"""
        embeddings = {}
        
        for line in lines:
            # Check cache first
            line_hash = self._get_line_hash(line.text)
            if line_hash in self.similarity_cache:
                embeddings[line.text] = self.similarity_cache[line_hash]
                continue
            
            # Generate new embedding
            embedding = await self.embedding_service.embed_text(line.text)
            embeddings[line.text] = embedding
            self.similarity_cache[line_hash] = embedding
        
        return embeddings
    
    def _identify_clusters(self, line_embeddings: Dict[str, np.ndarray]) -> List[SemanticCluster]:
        """Identify clusters of semantically similar lines"""
        if len(line_embeddings) < 2:
            return []
        
        # Calculate similarity matrix
        texts = list(line_embeddings.keys())
        embeddings = np.array(list(line_embeddings.values()))
        
        # Use cosine similarity
        similarity_matrix = np.dot(embeddings, embeddings.T) / (
            np.linalg.norm(embeddings, axis=1)[:, np.newaxis] * 
            np.linalg.norm(embeddings, axis=1)
        )
        
        # Apply clustering
        if self.clustering_method == "hierarchical":
            clusters = self._hierarchical_clustering(texts, similarity_matrix)
        else:
            clusters = self._dbscan_clustering(texts, similarity_matrix)
        
        return self._filter_quality_clusters(clusters)
    
    def _create_display_conversations(self, items: List[DataItem], 
                                    clusters: List[SemanticCluster]) -> List[DataItem]:
        """Create display conversations with deduplication applied"""
        cluster_lookup = self._build_cluster_lookup(clusters)
        
        for item in items:
            original_lifelog = item.metadata.get('original_lifelog', {})
            contents = original_lifelog.get('contents', [])
            
            display_nodes = []
            cluster_metadata = {}
            
            for node in contents:
                content = node.get('content', '').strip()
                
                # Check if this line is part of a cluster
                cluster_id = cluster_lookup.get(content)
                
                if cluster_id:
                    cluster = clusters[cluster_id]
                    
                    if self._is_canonical_line(content, cluster):
                        # This is the canonical line - include it
                        display_nodes.append({
                            **node,
                            "represents_cluster": cluster_id,
                            "hidden_variations": len(cluster.variations) - 1,
                            "is_deduplicated": True,
                            "canonical_confidence": cluster.confidence_score
                        })
                        
                        # Store cluster metadata
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
                    # Else: skip this line (it's a duplicate)
                else:
                    # Unique line - always include
                    display_nodes.append({
                        **node,
                        "is_unique": True
                    })
            
            # Update item metadata
            item.metadata['display_conversation'] = display_nodes
            item.metadata['semantic_clusters'] = cluster_metadata
            item.metadata['semantic_metadata'] = {
                "processed": True,
                "total_lines_analyzed": len(contents),
                "clustered_lines": len([n for n in display_nodes if n.get('is_deduplicated')]),
                "unique_themes": list(set(c['theme'] for c in cluster_metadata.values())),
                "semantic_density": len(display_nodes) / len(contents) if contents else 1.0
            }
        
        return items

@dataclass
class SpokenLine:
    text: str
    speaker: Optional[str]
    speaker_id: Optional[str]
    timestamp: Optional[str]
    conversation_id: str
    node_data: Dict[str, Any]

@dataclass
class SemanticCluster:
    cluster_id: str
    theme: str
    canonical_line: str
    variations: List['LineVariation']
    confidence_score: float
    frequency_count: int

@dataclass
class LineVariation:
    original_text: str
    speaker: str
    timestamp: str
    conversation_id: str
    similarity_to_canonical: float
```

### 2. Batch Processing Service

```python
class SemanticDeduplicationService:
    """Service for batch semantic deduplication processing"""
    
    def __init__(self, database_service, embedding_service):
        self.database = database_service
        self.embedding_service = embedding_service
        self.processor = SemanticDeduplicationProcessor()
    
    async def process_historical_conversations(self, 
                                             namespace: str = "limitless",
                                             batch_size: int = 50) -> ProcessingResult:
        """Process all historical conversations for semantic deduplication"""
        
        # Fetch all limitless conversations
        items = await self.database.get_data_items_by_namespace(namespace)
        
        # Process in batches for memory efficiency
        results = []
        for batch_start in range(0, len(items), batch_size):
            batch = items[batch_start:batch_start + batch_size]
            
            logger.info(f"Processing batch {batch_start//batch_size + 1}, "
                       f"items {batch_start} to {batch_start + len(batch)}")
            
            # Process batch
            processed_batch = await self.processor.process_batch(batch)
            
            # Store results
            await self._store_semantic_clusters(processed_batch)
            results.extend(processed_batch)
        
        return ProcessingResult(
            total_processed=len(results),
            clusters_created=await self._count_clusters(),
            processing_time=time.time() - start_time
        )
    
    async def _store_semantic_clusters(self, items: List[DataItem]):
        """Store semantic clusters in database"""
        for item in items:
            # Update data_items with new metadata
            await self.database.store_data_item(
                id=f"{item.namespace}:{item.source_id}",
                namespace=item.namespace,
                source_id=item.source_id,
                content=item.content,
                metadata=item.metadata,
                days_date=self._extract_days_date(item)
            )
            
            # Store cluster data
            clusters = item.metadata.get('semantic_clusters', {})
            for cluster_id, cluster_data in clusters.items():
                await self._store_cluster(cluster_id, cluster_data, item)
```

## Frontend Integration

### Enhanced ContentCard Component

```typescript
// Extended data types
export interface LimitlessContentData {
  type: "limitless";
  id: string;
  title?: string;
  timestamp: string;
  displayConversation: ConversationNode[];
  semanticClusters: Record<string, SemanticClusterData>;
  semanticMetadata: {
    totalLines: number;
    clusteredLines: number;
    uniqueThemes: string[];
    semanticDensity: number;
  };
}

interface ConversationNode {
  content: string;
  speaker: string;
  timestamp: string;
  type: string;
  representsCluster?: string;
  hiddenVariations?: number;
  isDeduplicated?: boolean;
  isUnique?: boolean;
  canonicalConfidence?: number;
}

interface SemanticClusterData {
  theme: string;
  canonical: string;
  variations: Array<{
    text: string;
    speaker: string;
    similarity: number;
    timestamp: string;
  }>;
  frequency: number;
  confidence: number;
}

// Enhanced conversation display component
const LimitlessConversationCard = ({ data }: { data: LimitlessContentData }) => {
  const [viewMode, setViewMode] = useState<'condensed' | 'full'>('condensed');
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  
  return (
    <Card className="p-4 hover:shadow-lg transition-shadow">
      <div className="space-y-4">
        {/* Header with title and controls */}
        <div className="flex items-center justify-between">
          <h3 className="font-headline text-lg font-semibold">
            {data.title || "Conversation"}
          </h3>
          <div className="flex items-center space-x-2">
            <Badge variant="secondary" className="text-xs">
              {data.semanticMetadata.clusteredLines} of {data.semanticMetadata.totalLines} lines
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setViewMode(viewMode === 'condensed' ? 'full' : 'condensed')}
            >
              {viewMode === 'condensed' ? 'Show Full' : 'Show Condensed'}
            </Button>
          </div>
        </div>
        
        {/* Semantic density indicator */}
        <div className="w-full bg-muted rounded-full h-2">
          <div 
            className="bg-primary h-2 rounded-full transition-all"
            style={{ width: `${data.semanticMetadata.semanticDensity * 100}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Semantic density: {Math.round(data.semanticMetadata.semanticDensity * 100)}% unique content
        </p>
        
        {/* Conversation content */}
        <div className="space-y-3">
          {data.displayConversation.map((node, index) => (
            <ConversationNode
              key={index}
              node={node}
              clusters={data.semanticClusters}
              expanded={expandedClusters.has(node.representsCluster || '')}
              onToggleExpand={(clusterId) => {
                const newExpanded = new Set(expandedClusters);
                if (newExpanded.has(clusterId)) {
                  newExpanded.delete(clusterId);
                } else {
                  newExpanded.add(clusterId);
                }
                setExpandedClusters(newExpanded);
              }}
            />
          ))}
        </div>
        
        {/* Theme summary */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-muted">
          {data.semanticMetadata.uniqueThemes.map(theme => (
            <Badge key={theme} variant="outline" className="text-xs">
              {theme.replace('_', ' ')}
            </Badge>
          ))}
        </div>
      </div>
    </Card>
  );
};

const ConversationNode = ({ 
  node, 
  clusters, 
  expanded, 
  onToggleExpand 
}: {
  node: ConversationNode;
  clusters: Record<string, SemanticClusterData>;
  expanded: boolean;
  onToggleExpand: (clusterId: string) => void;
}) => {
  const cluster = node.representsCluster ? clusters[node.representsCluster] : null;
  
  return (
    <div className="conversation-node">
      <div className="flex items-start space-x-3">
        <Avatar className="w-8 h-8 flex-shrink-0">
          <div className="w-full h-full bg-primary rounded-full flex items-center justify-center">
            <span className="text-white font-bold text-sm">
              {node.speaker?.charAt(0) || '?'}
            </span>
          </div>
        </Avatar>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-1">
            <span className="font-semibold text-sm">{node.speaker}</span>
            <span className="text-xs text-muted-foreground">{node.timestamp}</span>
            
            {node.isDeduplicated && (
              <Badge variant="secondary" className="text-xs">
                +{node.hiddenVariations} similar
              </Badge>
            )}
          </div>
          
          <p className="text-sm leading-relaxed mb-2">
            {node.content}
          </p>
          
          {/* Cluster expansion */}
          {cluster && node.hiddenVariations && node.hiddenVariations > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-auto p-1"
              onClick={() => onToggleExpand(node.representsCluster!)}
            >
              {expanded ? 'Hide' : 'Show'} {node.hiddenVariations} variations
              <ChevronDown className={`w-3 h-3 ml-1 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </Button>
          )}
          
          {expanded && cluster && (
            <div className="mt-2 pl-4 border-l-2 border-muted space-y-1">
              {cluster.variations.map((variation, index) => (
                <div key={index} className="text-xs text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>"{variation.text}"</span>
                    <span className="text-xs opacity-70">
                      {Math.round(variation.similarity * 100)}% similar
                    </span>
                  </div>
                  <div className="text-xs opacity-60">
                    {variation.speaker} • {variation.timestamp}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
```

## Implementation Phases

### Phase 1: Core Infrastructure (2-3 weeks)
1. **Database Schema Updates**
   - Create semantic_clusters and line_cluster_mapping tables
   - Add migration scripts
   - Set up indexes for performance

2. **Semantic Processing Engine**
   - Implement SemanticDeduplicationProcessor
   - Create clustering algorithms
   - Add quality metrics and validation

3. **Data Structure Enhancement**
   - Update DataItem metadata format
   - Create display_conversation structure
   - Add semantic metadata tracking

### Phase 2: Processing Pipeline (1-2 weeks)
1. **Batch Processing Service**
   - Implement historical data processing
   - Add incremental processing for new data
   - Create performance optimization layers

2. **Integration with Existing Pipeline**
   - Update LimitlessProcessor
   - Replace current deduplication approach
   - Add batch processing capabilities

### Phase 3: Frontend Integration (2-3 weeks)
1. **Enhanced ContentCard**
   - Create LimitlessContentData type
   - Implement conversation display components
   - Add user controls for view modes

2. **User Experience Features**
   - Create semantic cluster indicators
   - Add expandable content sections
   - Implement pattern visualization

### Phase 4: Advanced Features (1-2 weeks)
1. **Real-time Processing**
   - Implement incremental deduplication
   - Add performance monitoring
   - Create user preference systems

2. **Analytics and Insights**
   - Create conversation pattern dashboard
   - Add semantic analysis features
   - Implement usage analytics

## Performance Considerations

### Optimization Strategies
- **Embedding Caching**: Cache embeddings to avoid recomputation
- **Batch Processing**: Process conversations in configurable batches
- **Similarity Matrix Optimization**: Use efficient numpy operations
- **Database Indexing**: Optimize queries with proper indexes

### Memory Management
- **Streaming Processing**: Process large datasets without loading everything into memory
- **Garbage Collection**: Clear embeddings and similarity matrices after processing
- **Connection Pooling**: Efficient database connection management

### Scalability
- **Horizontal Scaling**: Design for distributed processing if needed
- **Incremental Updates**: Only process new/changed conversations
- **Quality Thresholds**: Configurable similarity thresholds for different use cases

## Quality Assurance

### Testing Strategy
- **Unit Tests**: Test individual components and algorithms
- **Integration Tests**: Test end-to-end processing pipeline
- **Performance Tests**: Validate processing speed and memory usage
- **Accuracy Tests**: Validate semantic clustering quality

### Quality Metrics
- **Cluster Coherence**: Internal similarity within clusters (target: >85%)
- **Cluster Separation**: Distance between different clusters
- **Processing Speed**: <30 seconds for 1000 conversations
- **Memory Usage**: <500MB peak memory usage

### Monitoring and Alerting
- **Processing Success Rates**: Track batch processing success
- **Quality Degradation**: Alert on clustering accuracy drops
- **Performance Regression**: Monitor processing speed trends

## Security and Privacy

### Data Protection
- **Local Processing**: All semantic analysis happens locally
- **Anonymization**: Option to anonymize speaker data in clusters
- **Data Retention**: Configurable retention policies for semantic data

### Access Control
- **User Permissions**: Control access to semantic analysis features
- **Audit Logging**: Track semantic processing operations
- **Data Export**: Secure export of semantic analysis results

## Migration Strategy

Since we're assuming a clean database, no migration is required. However, for future deployments:

### Deployment Steps
1. **Schema Creation**: Run migration scripts to create new tables
2. **Batch Processing**: Process existing conversations through new pipeline
3. **Feature Rollout**: Gradually enable semantic features for users
4. **Performance Monitoring**: Monitor system performance during rollout

### Rollback Plan
- **Schema Versioning**: Maintain ability to rollback schema changes
- **Feature Flags**: Control semantic features through configuration
- **Data Backup**: Backup original conversation data before processing

## Success Metrics

### Technical Metrics
- **Processing Accuracy**: >85% semantic clustering accuracy
- **Performance**: <30s processing time for 1000 conversations
- **Memory Efficiency**: <500MB peak memory usage
- **Reliability**: >99% batch processing success rate

### User Experience Metrics
- **Engagement**: >50% of users try condensed view
- **Satisfaction**: >90% user satisfaction with filtered conversations
- **Retention**: Increased session time with semantic features
- **Discovery**: Users discover conversation patterns through interface

### Business Impact
- **Differentiation**: Unique semantic conversation analysis feature
- **User Value**: Improved conversation comprehension and pattern awareness
- **Technical Innovation**: Advanced AI-powered content processing
- **Competitive Advantage**: No other tools offer similar semantic deduplication

## Conclusion

This semantic deduplication strategy transforms Lifeboard from a simple conversation storage system into an intelligent conversation analysis platform. By identifying and filtering semantically similar content, users get cleaner, more meaningful conversation summaries while maintaining access to complete historical data.

The implementation provides immediate value through improved conversation readability while laying the foundation for advanced features like conversation pattern analysis, mood tracking, and AI-powered insights. The system is designed for performance, scalability, and user control, ensuring it can grow with Lifeboard's user base and feature requirements.

The clean database assumption allows for optimal architecture design without migration constraints, while the phased implementation approach ensures steady progress with continuous value delivery to users.