# Spotify Archive Import - Implementation Plan
**Local Folder Selection | Archive-Only Import | Unified Music Table**

## Executive Summary

Consolidate Apple Music and Spotify archive data into a single "Music" table with:
- **Folder selection** (no upload) - read files directly from user's chosen location
- **Identical fields**: Artist, Album, Song, Play Count
- **Unified table component** displaying both sources together
- **Spotify archive only** - no OAuth/API integration

---

## 1. Architecture Overview

### Data Flow
```
User selects folder → Backend reads StreamingHistory_music_*.json →
Parse JSON → Create DataItems → Store in data_items (namespace="spotify") →
Unified API aggregates apple_music + spotify → MusicTable displays both
```

### Key Components
1. **Backend**: `SpotifyArchiveSource` class (mirrors `AppleMusicSource`)
2. **API**: `/api/music/{date}` (unified endpoint), `/api/music/spotify/import` (import endpoint)
3. **Frontend**: `MusicTable.tsx` (replaces `AppleMusicCard`), `SpotifyArchiveImport.tsx` (Settings component)

---

## 2. Backend Implementation

### 2.1 SpotifyArchiveSource Class
**File**: `sources/spotify_archive.py`

**Key Methods**:

#### `import_from_folder(folder_path: str)`
Main import method:
- Validates folder exists with `os.path.isdir()`
- Finds `StreamingHistory_music_*.json` files using `os.listdir()`
- Reads files with `open(file_path, 'r', encoding='utf-8')`
- Parses JSON with `json.load()`
- Returns `data_items` for ingestion

#### `_parse_streaming_history(tracks: List[Dict])`
Transform JSON format:
- **Input**: `{"endTime": "2025-05-30 02:35", "artistName": "KAROL G", "trackName": "LATINA FOREVA", "msPlayed": 2777}`
- **Output**: `{'artist': 'KAROL G', 'title': 'LATINA FOREVA', 'album': 'Unknown Album', 'days_date': '2025-05-30', ...}`
- Parse timestamp: `datetime.strptime(endTime, '%Y-%m-%d %H:%M')`
- Extract `days_date`: `end_time.strftime('%Y-%m-%d')`
- Create unique `source_id`: `f"{artist}:{title}:{endTime}".replace(' ', '_')`

#### `_transform_tracks_to_items(tracks: List[Dict])`
Create DataItems:
- Creates `DataItem` objects with `namespace="spotify"`
- Metadata structure:
  ```python
  {
      'artist': '...',
      'title': '...',
      'album': 'Unknown Album',  # Not available in archive
      'play_count': 1,  # Each entry = 1 play
      'play_duration_ms': ms_played,
      'days_date': '...',
      'source_origin': 'spotify_archive'
  }
  ```

**Deduplication**:
- Query existing entries: `db_service.async_get_data_items_by_namespace("spotify", limit=100000)`
- Build set of existing `source_id` values
- Filter: `new_tracks = [t for t in parsed if t['source_id'] not in existing_ids]`

### 2.2 Unified Music API
**File**: `api/routes/music.py` (new file)

**Endpoints**:

#### POST `/api/music/spotify/import`
```python
class FolderImportRequest(BaseModel):
    folder_path: str

@router.post("/spotify/import")
async def import_spotify_folder(request: FolderImportRequest, ...):
    # Create SpotifyArchiveSource
    # Call import_from_folder(request.folder_path)
    # Ingest returned data_items
    # Return {"success": true, "imported_count": 123, "message": "..."}
```

#### GET `/api/music/{days_date}`
```python
@router.get("/{days_date}", response_model=List[MusicPlay])
async def get_music_plays(days_date: str, ...):
    # Query: SELECT * FROM data_items
    #        WHERE namespace IN ('apple_music', 'spotify')
    #        AND days_date = ?
    # Aggregate by (source, artist, album, song) → sum play_count
    # Sort by play_count DESC
    # Return list of MusicPlay objects
```

**Data Model**:
```python
class MusicPlay(BaseModel):
    source: str  # "apple_music" or "spotify"
    artist: str
    album: str
    song: str
    play_count: int
```

**Aggregation Logic**:
```python
plays_dict = {}  # Key: (source, artist, album, song), Value: total play_count

for row in cursor.fetchall():
    metadata = json.loads(row['metadata'])
    key = (
        row['namespace'],  # source
        metadata.get('artist', 'Unknown Artist'),
        metadata.get('album', 'Unknown Album'),
        metadata.get('title', 'Unknown Song')
    )
    plays_dict[key] = plays_dict.get(key, 0) + metadata.get('play_count', 1)

# Convert to list and sort
plays = [MusicPlay(source=s, artist=a, album=al, song=so, play_count=c)
         for (s, a, al, so), c in plays_dict.items()]
plays.sort(key=lambda x: x.play_count, reverse=True)
```

---

## 3. Frontend Implementation

### 3.1 Spotify Archive Import Component
**File**: `frontend/src/components/SpotifyArchiveImport.tsx`

**UI Structure**:
```tsx
<Card className="p-6">
  <h3>Import Spotify Archive</h3>
  <p>Select your Spotify export folder containing StreamingHistory_music_*.json files</p>

  <Button onClick={handleFolderSelect}>
    <FolderOpen /> Select Folder
  </Button>

  {result && (
    <ResultDisplay success={result.success} message={result.message} />
  )}
</Card>
```

**Folder Selection Logic**:
```typescript
const handleFolderSelect = async () => {
  try {
    // Browser File System Access API
    // @ts-ignore
    const directoryHandle = await window.showDirectoryPicker();
    const folderPath = directoryHandle.name; // Get absolute path

    setImporting(true);

    const response = await fetch('/api/music/spotify/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath })
    });

    const data = await response.json();
    setResult(data);

    if (data.success) {
      // Refresh page after 2 seconds to show new data
      setTimeout(() => window.location.reload(), 2000);
    }
  } catch (error) {
    if (error.name !== 'AbortError') { // User cancelled
      setResult({ success: false, message: error.message });
    }
  } finally {
    setImporting(false);
  }
};
```

**Location**: Add to Settings page alongside Apple Music import

### 3.2 Unified Music Table
**File**: `frontend/src/components/MusicTable.tsx`

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│ Music                                            🔄  │
├─────────────────────────────────────────────────────┤
│ Source │ Artist │ Album │ Song │ Number of plays    │
├─────────────────────────────────────────────────────┤
│ 🍎     │ The... │ Songs │ Alon │        3           │
│ 🎵     │ KAROL  │ Unkno │ LATI │        1           │
└─────────────────────────────────────────────────────┘
```

**Component Structure**:
```tsx
export const MusicTable = ({ selectedDate }: MusicTableProps) => {
  const { plays, loading, error, refreshPlays } = useMusicData(selectedDate);

  return (
    <>
      {/* Header */}
      <div className="p-1 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-headline text-xl font-bold">Music</h3>

          <Button variant="outline" size="sm" onClick={refreshPlays}>
            <RefreshCw className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto px-6 py-4 h-[400px]">
        <table className="w-full">
          <thead className="sticky top-0 bg-white border-b">
            <tr>
              <th className="text-left py-2 px-3">Source</th>
              <th className="text-left py-2 px-3">Artist</th>
              <th className="text-left py-2 px-3">Album</th>
              <th className="text-left py-2 px-3">Song</th>
              <th className="text-center py-2 px-3">Number of plays</th>
            </tr>
          </thead>
          <tbody>
            {plays.map((play, idx) => (
              <tr key={idx} className="border-b hover:bg-gray-50">
                <td className="py-2 px-3">
                  <Badge variant={play.source === 'spotify' ? 'default' : 'secondary'}>
                    {play.source === 'spotify' ? '🎵' : '🍎'}
                  </Badge>
                </td>
                <td className="py-2 px-3">{play.artist}</td>
                <td className="py-2 px-3 text-gray-600">{play.album}</td>
                <td className="py-2 px-3">{play.song}</td>
                <td className="py-2 px-3 text-center font-semibold">
                  {play.play_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
};
```

**Features**:
- Header with "Music" title and refresh button
- Table with 5 columns: Source (badge), Artist, Album, Song, Play Count
- Source badge: 🍎 for Apple Music (secondary variant), 🎵 for Spotify (default variant)
- Sticky header for scrolling
- Hover effect on rows

### 3.3 Data Hook
**File**: `frontend/src/hooks/useMusicData.ts`

**Interface**:
```typescript
export interface MusicPlay {
  source: 'apple_music' | 'spotify';
  artist: string;
  album: string;
  song: string;
  play_count: number;
}

export interface UseMusicDataResult {
  plays: MusicPlay[];
  loading: boolean;
  error: string | null;
  refreshPlays: () => Promise<void>;
}

export const useMusicData = (selectedDate?: string): UseMusicDataResult => {
  const [plays, setPlays] = useState<MusicPlay[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPlays = useCallback(async (date: string) => {
    if (!date || !date.match(/^\d{4}-\d{2}-\d{2}$/)) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/music/${date}`, {
        headers: { 'Cache-Control': 'no-cache' }
      });

      if (response.ok) {
        const data: MusicPlay[] = await response.json();
        setPlays(data);
      } else {
        setError(`Failed to fetch: ${response.status}`);
        setPlays([]);
      }
    } catch (err) {
      setError(err.message);
      setPlays([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshPlays = useCallback(async () => {
    if (selectedDate) await fetchPlays(selectedDate);
  }, [selectedDate, fetchPlays]);

  useEffect(() => {
    if (selectedDate) fetchPlays(selectedDate);
  }, [selectedDate, fetchPlays]);

  return { plays, loading, error, refreshPlays };
};
```

---

## 4. File Structure

### New Files to Create
```
sources/
  spotify_archive.py          # Spotify archive source class

api/routes/
  music.py                    # Unified music API (new file)

frontend/src/components/
  MusicTable.tsx              # Unified music table (replaces AppleMusicCard)
  SpotifyArchiveImport.tsx    # Spotify folder import component

frontend/src/hooks/
  useMusicData.ts             # Unified music data hook
```

### Files to Modify
```
api/server.py                 # Register music router
frontend/src/components/SummarySection.tsx  # Replace AppleMusicCard with MusicTable
```

### Files to Remove/Deprecate
```
frontend/src/components/AppleMusicCard.tsx       # Remove (replaced by MusicTable)
frontend/src/hooks/useAppleMusicData.ts          # Remove (replaced by useMusicData)
frontend/src/components/MusicHistory.tsx         # Keep but document as unused
```

---

## 5. Implementation Steps

### Phase 1: Backend (3-4 hours)

**Step 1.1: Create SpotifyArchiveSource**
- File: `sources/spotify_archive.py`
- Implement `__init__(config, db_service)`
- Implement `import_from_folder(folder_path)` method:
  - Validate folder with `os.path.isdir()`
  - Find files with `os.listdir()` + filter for `streaminghistory*.json`
  - Read files with `open(file_path, 'r', encoding='utf-8')`
  - Parse with `json.load()`
  - Call `_parse_streaming_history()`
  - Deduplicate against database
  - Call `_transform_tracks_to_items()`
  - Return result dict with `data_items`

**Step 1.2: Create Unified Music API**
- File: `api/routes/music.py`
- Create router: `router = APIRouter(prefix="/music", tags=["music"])`
- Implement POST `/spotify/import`:
  - Request model: `FolderImportRequest(folder_path: str)`
  - Call `SpotifyArchiveSource.import_from_folder()`
  - Ingest returned `data_items`
  - Return result
- Implement GET `/{days_date}`:
  - Query both namespaces
  - Aggregate by (source, artist, album, song)
  - Sort by play_count DESC
  - Return `List[MusicPlay]`

**Step 1.3: Register Router**
- File: `api/server.py`
- Add import: `from api.routes import music`
- Add router: `app.include_router(music.router, prefix="/api")`

### Phase 2: Frontend (3-4 hours)

**Step 2.1: Create Spotify Import Component**
- File: `frontend/src/components/SpotifyArchiveImport.tsx`
- Implement folder picker with `window.showDirectoryPicker()`
- Call `/api/music/spotify/import` endpoint
- Display success/error result
- Reload page on success

**Step 2.2: Create Unified Music Table**
- File: `frontend/src/components/MusicTable.tsx`
- Header with title "Music" and refresh button
- Table with columns: Source, Artist, Album, Song, Play Count
- Source badge rendering (🍎 vs 🎵)
- Loading/error/empty states

**Step 2.3: Create Data Hook**
- File: `frontend/src/hooks/useMusicData.ts`
- Fetch from `/api/music/{date}`
- Auto-refresh on date change
- Return: plays, loading, error, refreshPlays

**Step 2.4: Integration**
- Add `SpotifyArchiveImport` to Settings page
- Replace `AppleMusicCard` with `MusicTable` in `SummarySection.tsx`
- Update imports

### Phase 3: Cleanup & Testing (2-3 hours)

**Step 3.1: Remove Old Components**
- Delete `frontend/src/components/AppleMusicCard.tsx`
- Delete `frontend/src/hooks/useAppleMusicData.ts`
- Add comment to `MusicHistory.tsx`: "// UNUSED - Spotify API integration disabled, archive import only"

**Step 3.2: Testing**
- Test folder selection with sample Spotify export
- Verify JSON parsing (handle multiple files)
- Test deduplication (re-import same folder)
- Test unified table display
- Verify play count aggregation
- Test with both Apple Music and Spotify data
- Test empty states
- Test error handling

---

## 6. Data Structures

### Spotify Archive JSON Format
```json
[
  {
    "endTime": "2025-05-30 02:35",
    "artistName": "KAROL G",
    "trackName": "LATINA FOREVA",
    "msPlayed": 2777
  },
  {
    "endTime": "2025-05-30 02:40",
    "artistName": "Skinny Puppy",
    "trackName": "Jackhammer",
    "msPlayed": 258360
  }
]
```

### DataItem (Spotify)
```json
{
  "id": "spotify:KAROL_G:LATINA_FOREVA:2025-05-30_02:35",
  "namespace": "spotify",
  "source_id": "KAROL_G:LATINA_FOREVA:2025-05-30_02:35",
  "content": "KAROL G - LATINA FOREVA (Album: Unknown Album)",
  "metadata": {
    "artist": "KAROL G",
    "title": "LATINA FOREVA",
    "album": "Unknown Album",
    "play_count": 1,
    "play_duration_ms": 2777,
    "days_date": "2025-05-30",
    "source_origin": "spotify_archive"
  },
  "days_date": "2025-05-30",
  "created_at": "2025-05-30T02:35:00Z"
}
```

### DataItem (Apple Music) - For Comparison
```json
{
  "id": "apple_music:track_id:20250629:10",
  "namespace": "apple_music",
  "source_id": "track_id:20250629:10",
  "content": "The Cure - Alone (Album: Songs of a Lost World)",
  "metadata": {
    "artist": "The Cure",
    "title": "Alone",
    "album": "Songs of a Lost World",
    "play_count": 1,
    "play_duration_ms": 408455,
    "days_date": "2025-06-29",
    "source_origin": "apple_music_archive"
  },
  "days_date": "2025-06-29",
  "created_at": "2025-06-29T10:24:00Z"
}
```

### Unified API Response
```json
GET /api/music/2025-06-29

[
  {
    "source": "apple_music",
    "artist": "The Cure",
    "album": "Songs of a Lost World",
    "song": "Alone",
    "play_count": 3
  },
  {
    "source": "spotify",
    "artist": "KAROL G",
    "album": "Unknown Album",
    "song": "LATINA FOREVA",
    "play_count": 1
  },
  {
    "source": "spotify",
    "artist": "Skinny Puppy",
    "album": "Unknown Album",
    "song": "Jackhammer",
    "play_count": 1
  }
]
```

---

## 7. Key Design Decisions

### ✅ Folder Selection (No Upload)
- **Rationale**: User controls where files are stored, no duplication
- **Implementation**: Use `os.path` to read from absolute path
- **User Experience**: Select folder → system reads directly → files stay in place

### ✅ Album = "Unknown Album" for Spotify
- **Rationale**: Spotify archive doesn't include album information
- **Implementation**: Hardcode `'album': 'Unknown Album'` in metadata
- **Alternative Considered**: Leave blank → Rejected (breaks table consistency)

### ✅ Play Count Aggregation
- **Rationale**: Each JSON entry = 1 play instance, same song played multiple times should aggregate
- **Implementation**: Group by `(source, artist, album, song)`, sum `play_count`
- **Example**: Same song appears 3 times in archive → `play_count: 3`

### ✅ No Source Filtering
- **Rationale**: Keep UI simple, show all music together
- **Implementation**: Always query both namespaces, display in single table
- **User Experience**: See all music at once, source badge provides visual distinction

### ✅ Source Badge Visual Only
- **Rationale**: Distinguish sources without functional complexity
- **Implementation**: Badge with emoji (🍎 vs 🎵) and different variant colors
- **User Experience**: Quick visual identification of data source

---

## 8. Testing Strategy

### Unit Tests

**Backend Tests** (`tests/unit/sources/test_spotify_archive.py`):
```python
def test_parse_streaming_history():
    """Test JSON parsing logic"""
    source = SpotifyArchiveSource(config, db_service)
    tracks = [{"endTime": "2025-05-30 02:35", "artistName": "KAROL G", ...}]
    parsed = source._parse_streaming_history(tracks)

    assert len(parsed) == 1
    assert parsed[0]['artist'] == "KAROL G"
    assert parsed[0]['days_date'] == "2025-05-30"

def test_transform_to_data_items():
    """Test DataItem creation"""
    tracks = [{'source_id': '...', 'artist': '...', ...}]
    items = source._transform_tracks_to_items(tracks)

    assert len(items) == 1
    assert items[0].namespace == "spotify"
    assert items[0].metadata['album'] == "Unknown Album"

def test_deduplication():
    """Test existing track filtering"""
    # Mock database with existing tracks
    # Import same tracks again
    # Verify result.imported_count == 0
```

**API Tests** (`tests/integration/test_music_api.py`):
```python
async def test_unified_music_endpoint():
    """Test /api/music/{date} combines both sources"""
    response = await client.get("/api/music/2025-06-29")

    assert response.status_code == 200
    plays = response.json()

    # Verify structure
    for play in plays:
        assert 'source' in play
        assert 'artist' in play
        assert 'play_count' in play

async def test_aggregation():
    """Test play count aggregation"""
    # Insert 3 plays of same song
    # Query /api/music/{date}
    # Verify play_count == 3
```

### Integration Tests

**Folder Import Test** (`tests/integration/test_spotify_import.py`):
```python
async def test_import_from_folder():
    """Test complete folder import flow"""
    test_folder = "tests/fixtures/spotify_export"
    # Folder contains StreamingHistory_music_0.json with 31 tracks

    result = await spotify_source.import_from_folder(test_folder)

    assert result['success'] == True
    assert result['imported_count'] == 31

    # Verify database entries
    items = await db.async_get_data_items_by_namespace("spotify")
    assert len(items) == 31
```

### E2E Tests

**Frontend Flow** (`tests/frontend/e2e/test_spotify_import.spec.ts`):
```typescript
test('import Spotify archive and view in table', async ({ page }) => {
  // Navigate to settings
  await page.goto('/settings');

  // Click select folder button
  await page.click('button:has-text("Select Folder")');

  // Mock folder selection (browser API)
  // Wait for success message
  await page.waitForSelector('text=Import Successful');

  // Navigate to calendar
  await page.goto('/calendar/2025-05-30');

  // Verify Spotify data appears in Music table
  await page.waitForSelector('text=🎵');
  await page.waitForSelector('text=KAROL G');
});
```

---

## 9. Error Handling

### Backend Errors
| Error Scenario | Handling |
|----------------|----------|
| Folder doesn't exist | Return `{"success": false, "message": "Folder not found: {path}"}` |
| No JSON files found | Return `{"success": false, "message": "No StreamingHistory files found"}` |
| JSON parse error | Log warning, skip file, continue with other files |
| Database error | Raise HTTPException 500 with error details |
| Duplicate import | Return `{"success": true, "imported_count": 0, "message": "All tracks already imported"}` |

### Frontend Errors
| Error Scenario | Handling |
|----------------|----------|
| User cancels folder picker | Silent (AbortError), don't show error message |
| API returns 500 | Display error: "Import failed: {error message}" |
| Network error | Display error: "Network error: {details}" |
| Invalid folder path | Display API error message from backend |

---

## 10. Success Criteria

### Functional Requirements
- ✅ User can select Spotify export folder from anywhere on system
- ✅ System reads `StreamingHistory_music_*.json` files directly (no upload)
- ✅ Spotify tracks imported to `data_items` with `namespace="spotify"`
- ✅ Unified Music table displays both Apple Music and Spotify
- ✅ Play counts aggregate correctly (same song = sum of plays)
- ✅ "Unknown Album" displays for Spotify entries
- ✅ Source badge distinguishes Apple Music (🍎) from Spotify (🎵)

### Non-Functional Requirements
- ✅ Import 1000+ tracks in <30 seconds
- ✅ Table loads <2s for 100 plays
- ✅ Responsive table scrolling (400px height, sticky header)
- ✅ Zero data loss during import
- ✅ Graceful error handling with user-friendly messages

### User Acceptance Criteria
- ✅ User can import Spotify data without uploading files
- ✅ User can view all music (Apple + Spotify) in one table
- ✅ User can identify which source each track came from
- ✅ Play counts match expected values from archive
- ✅ Re-importing same folder doesn't create duplicates
- ✅ Table shows "Music" instead of "Music of the Day"

---

## 11. Timeline Estimate

### Phase 1: Backend (3-4 hours)
- 1.5 hours: `SpotifyArchiveSource` implementation
- 1 hour: Unified Music API (`/api/music/`)
- 0.5-1 hour: Unit tests

### Phase 2: Frontend (3-4 hours)
- 1 hour: `SpotifyArchiveImport.tsx`
- 1.5 hours: `MusicTable.tsx` + `useMusicData.ts`
- 0.5-1 hour: Integration (replace components)

### Phase 3: Testing & Cleanup (2-3 hours)
- 1 hour: Integration testing with sample data
- 0.5 hour: E2E testing
- 0.5-1 hour: Cleanup and documentation

**Total Estimated Time: 8-11 hours**

---

## 12. Migration Checklist

### Backend Tasks
- [ ] Create `sources/spotify_archive.py`
- [ ] Implement `import_from_folder()` method
- [ ] Implement `_parse_streaming_history()` method
- [ ] Implement `_transform_tracks_to_items()` method
- [ ] Create `api/routes/music.py`
- [ ] Implement POST `/api/music/spotify/import` endpoint
- [ ] Implement GET `/api/music/{days_date}` endpoint
- [ ] Register music router in `api/server.py`
- [ ] Write unit tests for SpotifyArchiveSource
- [ ] Write integration tests for music API

### Frontend Tasks
- [ ] Create `frontend/src/components/SpotifyArchiveImport.tsx`
- [ ] Implement folder picker with `showDirectoryPicker()`
- [ ] Create `frontend/src/components/MusicTable.tsx`
- [ ] Create `frontend/src/hooks/useMusicData.ts`
- [ ] Add `SpotifyArchiveImport` to Settings page
- [ ] Replace `AppleMusicCard` with `MusicTable` in `SummarySection.tsx`
- [ ] Update component imports and exports
- [ ] Write E2E tests for import flow

### Cleanup Tasks
- [ ] Remove `frontend/src/components/AppleMusicCard.tsx`
- [ ] Remove `frontend/src/hooks/useAppleMusicData.ts`
- [ ] Add comment to `MusicHistory.tsx`: "UNUSED - Spotify API disabled"
- [ ] Remove unused imports
- [ ] Update documentation

### Testing Tasks
- [ ] Test with sample Spotify export folder
- [ ] Test with multiple `StreamingHistory_music_*.json` files
- [ ] Test deduplication (re-import same folder)
- [ ] Verify play count aggregation
- [ ] Test unified table with both sources
- [ ] Test empty states (no data for date)
- [ ] Test error handling (invalid folder, JSON parse errors)
- [ ] Performance test with 1000+ tracks

---

## 13. Implementation Notes

### Browser Compatibility
- File System Access API (`showDirectoryPicker`) supported in Chrome/Edge 86+
- Safari/Firefox may need alternative approach (file input with `webkitdirectory`)
- Consider fallback or Electron dialog API if desktop app

### Folder Path Handling
- Backend expects absolute path (e.g., `/Users/username/Downloads/spotify_export`)
- Frontend must pass full path from `DirectoryHandle`
- Validate path security (prevent directory traversal)

### Multiple Files Support
- Archive may contain: `StreamingHistory_music_0.json`, `StreamingHistory_music_1.json`, etc.
- Must read ALL matching files and combine tracks
- Log each file processed for debugging

### Performance Considerations
- Large archives (10K+ tracks) may take time to process
- Consider pagination if table becomes too large (>500 rows)
- Database query optimized with index on `(namespace, days_date)`

---

## Appendix: Sample Code Snippets

### A. Folder Reading Logic
```python
# sources/spotify_archive.py
streaming_files = []
for filename in os.listdir(folder_path):
    if 'streaminghistory' in filename.lower() and filename.endswith('.json'):
        file_path = os.path.join(folder_path, filename)
        streaming_files.append((filename, file_path))

all_tracks = []
for filename, file_path in streaming_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        tracks = json.load(f)
        all_tracks.extend(tracks)
```

### B. Aggregation Query
```python
# api/routes/music.py
query = """
    SELECT namespace, metadata
    FROM data_items
    WHERE namespace IN ('apple_music', 'spotify') AND days_date = ?
"""

plays_dict = {}
for row in cursor.fetchall():
    metadata = json.loads(row['metadata'])
    key = (row['namespace'], metadata['artist'], metadata['album'], metadata['title'])
    plays_dict[key] = plays_dict.get(key, 0) + metadata.get('play_count', 1)
```

### C. Table Row Rendering
```tsx
// frontend/src/components/MusicTable.tsx
{plays.map((play, idx) => (
  <tr key={idx}>
    <td>
      <Badge variant={play.source === 'spotify' ? 'default' : 'secondary'}>
        {play.source === 'spotify' ? '🎵' : '🍎'}
      </Badge>
    </td>
    <td>{play.artist}</td>
    <td>{play.album}</td>
    <td>{play.song}</td>
    <td className="text-center font-semibold">{play.play_count}</td>
  </tr>
))}
```

---

**Plan Status**: Ready for implementation. No code has been written yet.
