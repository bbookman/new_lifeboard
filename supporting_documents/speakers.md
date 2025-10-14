# Design: Speaker Labeling Improvement Feature

## Executive Summary
Create an automatic speaker labeling workflow that processes transcripts through the "SPEAKER LABELING" prompt. Processing runs automatically, tracks status via `speaker_label_status` column in `data_items`, and provides a manual regeneration option. Processes lifelogs one-by-one starting from yesterday.

---

## Architecture Analysis

### Current Data Storage

```
data_items table:
├─ id (PRIMARY KEY)
├─ namespace TEXT
├─ source_id TEXT
├─ content TEXT
├─ metadata TEXT
├─ embedding_status TEXT DEFAULT 'pending' ← Tracking pattern to replicate
├─ days_date TEXT
└─ ... (other columns)

limitless table:
├─ id (PRIMARY KEY)
├─ lifelog_id (UNIQUE)
├─ processed_content TEXT ← Source for extraction
├─ raw_data TEXT
└─ days_date TEXT
```

### Proposed Storage Strategy

**Status Tracking**: Add `speaker_label_status` column to `data_items` table (similar to `embedding_status`)

**Improved Content**: Add `speaker_labeled_content` column to `limitless` table

**Rationale**:
- ✅ Consistent with existing embedding_status pattern
- ✅ Enables efficient querying for pending items
- ✅ Tracks processing state per data item
- ✅ Allows filtering and batch processing
- ✅ Preserves original data integrity

---

## Detailed Design

### 1. Database Schema Updates

**File**: `core/unified_database.py`

**Modification 1**: Update `data_items` table in `_create_complete_schema()`

```python
# Main data storage table with all columns
conn.execute("""
    CREATE TABLE IF NOT EXISTS data_items (
        id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        source_id TEXT NOT NULL,
        content TEXT,
        metadata TEXT,
        embedding_status TEXT DEFAULT 'pending',
        speaker_label_status TEXT DEFAULT 'pending',  -- NEW: Track speaker labeling
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        days_date TEXT NOT NULL,
        semantic_status TEXT DEFAULT 'pending' CHECK (semantic_status IN ('pending', 'processing', 'completed', 'failed')),
        semantic_processed_at TIMESTAMP,
        processing_priority INTEGER DEFAULT 1,
        ingestion_status TEXT DEFAULT 'complete' CHECK (ingestion_status IN ('partial', 'complete', 'failed'))
    )
""")
```

**Modification 2**: Update `limitless` table in `_create_complete_schema()`

```python
# Limitless lifelog data for specialized processing
conn.execute("""
    CREATE TABLE IF NOT EXISTS limitless (
        id TEXT PRIMARY KEY,
        lifelog_id TEXT NOT NULL UNIQUE,
        title TEXT,
        start_time TEXT,
        end_time TEXT,
        is_starred BOOLEAN DEFAULT FALSE,
        updated_at_api TEXT,
        processed_content TEXT,
        speaker_labeled_content TEXT,           -- NEW: Improved speaker labels
        raw_data TEXT,
        days_date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
```

**Index Additions**: In `_create_all_indexes()`

```python
# Data items indexes
conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_speaker_status ON data_items(speaker_label_status)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace_speaker_status ON data_items(namespace, speaker_label_status)")

# Limitless indexes
conn.execute("CREATE INDEX IF NOT EXISTS idx_limitless_speaker_labeled ON limitless(lifelog_id) WHERE speaker_labeled_content IS NOT NULL")
```

**Status Values**:
- `pending`: Not yet processed
- `processing`: Currently being processed
- `completed`: Successfully labeled
- `skipped`: No speaker lines found, no processing needed
- `failed`: Error during processing

---

### 2. Speaker Labeling Service

**File**: `services/speaker_labeling_service.py`

**Class**: `SpeakerLabelingService(BaseService)`

**Core Methods**:

```python
async def process_pending_speaker_labeling(
    batch_size: int = 10,
    force_reprocess: bool = False
) -> Dict[str, Any]:
    """
    Automatically process pending speaker labeling items
    Called on startup or scheduled basis

    Args:
        batch_size: Number of items to process in this run
        force_reprocess: Reprocess even if already completed

    Returns:
        {
            "items_processed": int,
            "items_completed": int,
            "items_skipped": int,
            "items_failed": int,
            "errors": List[str]
        }
    """

async def regenerate_speaker_labeling_for_date(
    days_date: str
) -> Dict[str, Any]:
    """
    Manually regenerate speaker labeling for a specific date
    Triggered by UI button

    Returns:
        {
            "success": bool,
            "days_date": str,
            "items_reprocessed": int,
            "items_improved": int,
            "errors": List[str]
        }
    """

async def get_pending_items(
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get data items that need speaker labeling

    Query:
        SELECT * FROM data_items
        WHERE namespace = 'limitless'
        AND speaker_label_status = 'pending'
        ORDER BY days_date DESC, created_at ASC
        LIMIT ?
    """

async def process_single_item(
    data_item_id: str
) -> Dict[str, Any]:
    """
    Process a single data item through speaker labeling

    Steps:
    1. Get data_item from data_items table
    2. Get corresponding limitless record via source_id
    3. Extract speaker lines from limitless.processed_content
    4. If no speakers, mark as 'skipped' and return
    5. Apply LLM prompt to speaker lines
    6. Reconstruct markdown with improved labels
    7. Store in limitless.speaker_labeled_content
    8. Update data_items.speaker_label_status = 'completed'

    Returns:
        {
            "success": bool,
            "data_item_id": str,
            "status": "completed|skipped|failed",
            "error": Optional[str]
        }
    """

async def _extract_speaker_lines(
    processed_content: str
) -> Tuple[List[str], Dict[int, Dict[str, Any]]]:
    """
    Extract blockquote lines from processed_content

    Returns:
        - List of speaker lines (format: "Speaker (date time): text")
        - Mapping dict for reconstruction
    """

async def _apply_speaker_prompt(
    speaker_lines: List[str]
) -> str:
    """
    Send speaker lines to LLM with SPEAKER LABELING prompt

    Returns:
        - Labeled transcript as plain text
    """

async def _reconstruct_markdown(
    original_markdown: str,
    improved_lines: str,
    line_mapping: Dict[int, Dict[str, Any]]
) -> str:
    """
    Replace speaker lines in original markdown with improved versions
    """

def update_speaker_label_status(
    data_item_id: str,
    status: str
):
    """
    Update speaker_label_status for a data item

    Status values: 'pending', 'processing', 'completed', 'skipped', 'failed'
    """
```

---

### 3. Automatic Processing Workflow

**Integration Point**: `services/startup.py`

**Addition to startup sequence**:

```python
# In initialize_application():
# After step 2.7 (Initialize LLM service)
# Add step 2.8: Initialize speaker labeling processing

async def _start_speaker_labeling_processing(self, startup_result: Dict[str, Any]):
    """Start automatic speaker labeling processing"""
    try:
        logger.info("Starting automatic speaker labeling processing...")

        # Create background task
        asyncio.create_task(self._speaker_labeling_worker())

        startup_result["speaker_labeling_started"] = True
        logger.info("Speaker labeling processing started successfully")

    except Exception as e:
        error_msg = f"Failed to start speaker labeling: {str(e)}"
        logger.error(error_msg)
        startup_result["errors"].append(error_msg)

async def _speaker_labeling_worker(self):
    """Background worker for speaker labeling"""
    # Wait for services to be ready
    await asyncio.sleep(10)

    # Import speaker labeling service
    from services.speaker_labeling_service import SpeakerLabelingService

    speaker_service = SpeakerLabelingService(
        database=self.database,
        config=self.config
    )

    # Process pending items
    result = await speaker_service.process_pending_speaker_labeling(
        batch_size=20,
        force_reprocess=False
    )

    logger.info(f"Speaker labeling completed: {result['items_completed']} items processed")
```

**Processing Logic**:
```
1. On application startup, start background worker
   ↓
2. Worker gets pending items from data_items:
   - WHERE namespace = 'limitless'
   - AND speaker_label_status = 'pending'
   - ORDER BY days_date DESC (yesterday first)
   ↓
3. For each data_item:
   ├─ Set status = 'processing'
   ├─ Get limitless record via source_id (lifelog_id)
   ├─ Extract speaker lines from processed_content
   ├─ If no speakers: Set status = 'skipped', continue
   ├─ Call LLM with SPEAKER LABELING prompt
   ├─ Reconstruct markdown with improved labels
   ├─ Store in limitless.speaker_labeled_content
   └─ Set status = 'completed'
   ↓
4. Continue until batch_size reached or no more pending
```

---

### 4. Manual Regeneration

**API Endpoint**: `POST /api/speaker-labeling/regenerate`

**Request**:
```json
{
  "days_date": "2025-10-13"
}
```

**Response**:
```json
{
  "success": true,
  "days_date": "2025-10-13",
  "items_reprocessed": 15,
  "items_improved": 12,
  "items_skipped": 3,
  "duration_seconds": 23.5
}
```

**Processing Logic**:
```python
async def regenerate_speaker_labeling_for_date(days_date: str):
    # Get all limitless data_items for this date
    items = await self._get_items_for_date(days_date)

    # Reset their status to pending
    for item in items:
        self.update_speaker_label_status(item['id'], 'pending')

    # Process them
    results = []
    for item in items:
        result = await self.process_single_item(item['id'])
        results.append(result)

    return {
        "items_reprocessed": len(items),
        "items_improved": sum(1 for r in results if r['status'] == 'completed'),
        "items_skipped": sum(1 for r in results if r['status'] == 'skipped')
    }
```

---

### 5. Frontend Integration

**File**: `frontend/src/components/calendar/LimitlessCard.tsx`

**Button Addition**:
```tsx
// Add "Regenerate Speakers" button next to refresh
<Button
  onClick={handleRegenerateSpeakers}
  disabled={isRegenerating}
  variant="outline"
  size="sm"
>
  {isRegenerating ? (
    <>
      <Spinner size="sm" />
      Regenerating...
    </>
  ) : (
    <>
      <RefreshIcon />
      Regenerate Speakers
    </>
  )}
</Button>
```

**Handler**:
```tsx
const handleRegenerateSpeakers = async () => {
  try {
    setIsRegenerating(true);

    const response = await fetch('/api/speaker-labeling/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days_date: selectedDate })
    });

    const data = await response.json();

    if (data.success) {
      toast.success(`Regenerated ${data.items_improved} speaker labels`);
      // Refresh the limitless data display
      refetchLimitlessData();
    }
  } catch (error) {
    toast.error('Failed to regenerate speaker labels');
  } finally {
    setIsRegenerating(false);
  }
};
```

---

### 6. Status Tracking Queries

**Get Pending Items**:
```sql
SELECT id, namespace, source_id, days_date
FROM data_items
WHERE namespace = 'limitless'
  AND speaker_label_status = 'pending'
ORDER BY days_date DESC, created_at ASC
LIMIT ?
```

**Get Statistics**:
```sql
SELECT
    speaker_label_status,
    COUNT(*) as count
FROM data_items
WHERE namespace = 'limitless'
GROUP BY speaker_label_status
```

**Update Status**:
```sql
UPDATE data_items
SET speaker_label_status = ?,
    updated_at = CURRENT_TIMESTAMP
WHERE id = ?
```

---

### 7. LLM Integration

**Prompt Retrieval** (cached):
```python
cursor = conn.execute("""
    SELECT d.content_md
    FROM prompt_settings ps
    JOIN user_documents d ON d.id = ps.prompt_document_id
    WHERE ps.setting_key = 'speaker_labeling_prompt_default'
    AND ps.is_active = TRUE
""")
prompt_content = cursor.fetchone()['content_md']
```

**LLM Call** (per data item):
```python
messages = [
    {"role": "system", "content": prompt_content},
    {"role": "user", "content": "\n".join(speaker_lines)}
]

response = await llm_provider.chat(messages)
improved_transcript = response.content
```

---

## Implementation Phases

### Phase 1: Schema & Foundation (Days 1-2)
- Update `core/unified_database.py` with new columns and indexes
- Create `SpeakerLabelingService` skeleton
- Implement status tracking methods
- Write unit tests for extraction

### Phase 2: Core Processing (Days 3-4)
- Implement speaker line extraction
- Implement LLM prompt integration
- Implement markdown reconstruction
- Add error handling and logging
- Write integration tests

### Phase 3: Automatic Processing (Days 5-6)
- Integrate into startup.py
- Implement background worker
- Add batch processing logic
- Test automatic processing flow

### Phase 4: Manual Regeneration (Day 7)
- Create regeneration API endpoint
- Add frontend button
- Implement regeneration workflow
- User testing

---

## Processing Order

**Automatic Processing**:
1. Get items WHERE `speaker_label_status = 'pending'`
2. Order by `days_date DESC` (yesterday first, then day before, etc.)
3. Process one-by-one up to batch_size
4. Run on startup, can be re-triggered manually

**Manual Regeneration**:
1. User selects a specific date
2. Reset all items for that date to 'pending'
3. Process all items for that date
4. Return results

---

## Risk Mitigation

**Data Safety**:
- Original data never modified
- Status column allows reprocessing
- Failed items don't block others

**Performance**:
- Batch size limits processing load
- Async background processing
- Status column enables efficient querying

**Quality Control**:
- Track status per item
- Log all operations
- Skip items without speakers
- Regeneration option for improvements

---

## Success Metrics

- **Coverage**: All limitless items processed
- **Accuracy**: >90% correct speaker identification
- **Performance**: Process 20 items in <30 seconds
- **Reliability**: <5% failure rate

---

## Files to Create/Modify

**Modified Files**:
1. `core/unified_database.py` - Add `speaker_label_status` to data_items, `speaker_labeled_content` to limitless
2. `services/startup.py` - Add automatic speaker labeling worker

**New Files**:
1. `services/speaker_labeling_service.py`
2. `api/routes/speaker_labeling.py`
3. `frontend/src/components/calendar/RegenerateSpeakersButton.tsx` (or modify existing)
4. `tests/backend/unit/services/test_speaker_labeling_service.py`
5. `tests/backend/integration/test_speaker_labeling_integration.py`
