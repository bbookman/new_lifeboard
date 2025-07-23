# Data Cleaning Enhancement Plan

## Overview
Implement a comprehensive data cleaning system with three core strategies: Deduplication, Content Normalization, and Entity Standardization. This will maintain original data for UI display while providing optimized data for chat functionality.

## Phase 1: Database Schema Enhancement

### New Cleaning Columns
Add to `data_items` table:
- `content_cleaned` TEXT - Deduplicated, normalized content for chat
- `entities_standardized` TEXT - Standardized entity representations 
- `content_for_search` TEXT - Optimized content for embeddings
- `deduplication_group` TEXT - Group ID for similar items
- `deduplication_score` REAL - Similarity score within group
- `cleaning_status` TEXT DEFAULT 'pending' - Track cleaning progress
- `cleaning_metadata` TEXT - JSON metadata about cleaning operations

## Phase 2: Content Normalization Service

### Create `core/content_normalizer.py`
- Build on existing `AdvancedCleaningProcessor` 
- Enhanced text normalization for chat optimization
- Entity mention standardization (e.g., "dog"/"puppy"/"pup" → "dog")
- Temporal expression normalization
- Quality scoring for content prioritization

### Features:
- Preserve original content structure
- Generate chat-optimized versions
- Maintain traceability of all changes
- Configurable normalization levels

## Phase 3: Deduplication Engine

### Create `core/deduplication_service.py`
- Levenshtein distance calculation for near-duplicates
- Semantic similarity using existing embedding service
- Hybrid scoring (syntactic + semantic similarity)
- Intelligent grouping of similar conversations
- Quality-based selection within duplicate groups

### Algorithm:
1. **Fast Pre-filtering**: Content length, basic fingerprinting
2. **Similarity Calculation**: Levenshtein + embedding cosine similarity  
3. **Grouping**: Cluster similar items (threshold: 0.85 combined score)
4. **Representative Selection**: Choose highest quality item per group

## Phase 4: Entity Standardization Integration

### Enhance `core/ner_service.py`
- Entity resolution and linking
- Canonical entity forms ("Grape (dog)", "Bruce Bookman (person)")
- Cross-reference resolution (same entity, different mentions)
- Confidence scoring for entity relationships

### Standardization Rules:
- Person names: "First Last (person)" format
- Pets: "Name (animal_type)" format  
- Locations: "Place (city/state/country)" format
- Consistent casing and formatting

## Phase 5: Cleaning Pipeline Integration

### Create `sources/cleaning_processor.py`
- Integrate with existing preprocessing pipeline
- Run after `AdvancedCleaningProcessor` and NER analysis
- Populate new cleaning columns during data ingestion
- Batch processing for existing data migration

### Processing Flow:
1. Content normalization → `content_cleaned`
2. Entity standardization → `entities_standardized` 
3. Deduplication analysis → `deduplication_group`, `deduplication_score`
4. Search optimization → `content_for_search`

## Phase 6: Chat Service Integration

### Update `services/chat_service.py`
- Modify `_sql_search()` to prioritize cleaned content
- Use `content_cleaned` + `entities_standardized` for LLM context
- Implement quality-based result filtering
- Fall back to original content when cleaned unavailable

### Search Strategy:
- Primary: Search `content_cleaned` and `entities_standardized`
- Secondary: Search original `content` and `named_entities`
- Deduplication: Filter results by `deduplication_group`
- Quality ranking: Use `content_quality_score` for prioritization

## Phase 7: Configuration & Monitoring

### Environment Variables
- `CLEANING_ENABLED=true`
- `DEDUPLICATION_THRESHOLD=0.85`
- `ENTITY_STANDARDIZATION_ENABLED=true`
- `CLEANING_BATCH_SIZE=100`
- `QUALITY_SCORE_MINIMUM=0.3`

### Monitoring
- Track cleaning performance metrics in logs
- Monitor deduplication effectiveness through code metrics
- Quality score distribution analysis
- Chat accuracy improvements measurement

## Implementation Priority

1. **High Priority**: Database schema + Content normalizer (immediate chat quality improvement)
2. **Medium Priority**: Deduplication engine (reduces redundant context)
3. **Lower Priority**: Enhanced entity standardization (refinement)

## Migration Strategy

- **New Data**: Automatic cleaning during ingestion
- **Existing Data**: Background batch processing with progress tracking
- **Rollback Plan**: Preserve original data, can disable cleaned columns
- **A/B Testing**: Compare chat quality with/without cleaning

## Success Metrics

- **Chat Accuracy**: Improved entity recognition and relationship detection
- **Context Quality**: Reduced redundancy, higher relevance scores
- **Performance**: Faster search through optimized content
- **User Experience**: Maintained authentic UI display with enhanced chat functionality

## Monitoring Details

### In Logs:
- **Processing Statistics**: Log how many items were deduplicated, normalized, entity-standardized
- **Performance Metrics**: Processing time, memory usage, success/failure rates
- **Quality Measurements**: Before/after quality scores, cleaning effectiveness
- **Error Tracking**: Failed cleaning operations, edge cases encountered

Example log entries:
```
INFO - Content cleaning completed: 1000 items processed, 150 deduplicated, avg quality score improved from 0.6 to 0.8
WARN - Entity standardization failed for item limitless:12345: No entities detected
DEBUG - Deduplication found 5 groups, removed 23 duplicates, kept highest quality items
```

### In Code:
- **Metrics Collection**: Code that captures cleaning statistics and stores them
- **Health Checks**: Functions that validate cleaning pipeline is working correctly
- **Performance Counters**: Track processing speed, memory usage, success rates
- **Quality Analyzers**: Measure improvement in chat accuracy, search relevance

Example code patterns:
```python
# Metrics tracking
cleaning_stats = {
    'items_processed': 0,
    'duplicates_removed': 0, 
    'entities_standardized': 0,
    'avg_quality_improvement': 0.0
}

# Performance monitoring
start_time = time.time()
# ... cleaning operations ...
processing_time = time.time() - start_time
logger.info(f"Cleaning completed in {processing_time:.2f}s")
```

### What Gets Monitored:
1. **Deduplication Effectiveness**: How many duplicates found/removed
2. **Content Quality Improvements**: Before/after quality scores
3. **Entity Standardization Success**: Percentage of entities successfully standardized
4. **Chat Accuracy Impact**: Improved entity recognition rates
5. **Processing Performance**: Speed, memory usage, throughput
6. **Error Rates**: Failed operations, edge cases