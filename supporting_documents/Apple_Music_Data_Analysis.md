# Apple Music Data Structure Analysis

## Overview
Apple Music provides a comprehensive data export with 23 files containing listening history, library information, and user preferences. The data spans from 2015 to 2025 with ~200K total records across CSV and JSON formats.

## File Inventory & Scale

### Large Data Files (Primary Sources)
1. **Apple Music Play Activity.csv** - 122,322 rows
   - Most comprehensive play-by-play activity log
   - 130+ columns with detailed metrics
   - Timestamp precision: milliseconds

2. **Apple Music - Play History Daily Tracks.csv** - 44,792 rows
   - Daily aggregated play history
   - Simplified schema with 13 columns
   - Date format: YYYYMMDD (e.g., 20150701)

3. **Apple Music - Track Play History.csv** - 27,894 rows
   - Track-level play history with timestamps
   - Format: "Artist - Title", Last Played Date (epoch ms), Is User Initiated

### Library Metadata (JSON)
4. **Apple Music Library Tracks.json**
   - Complete track metadata with 30+ fields
   - Track Identifier: numeric ID (e.g., 665642)

5. **Apple Music Library Playlists.json**
   - User playlists with item identifier arrays
   - Links to tracks via "Playlist Item Identifiers"

6. **Apple Music Library Artists.json**
   - Artist metadata with catalog IDs
   - Artist Identifier: string format (e.g., "r.056wvIt")

7. **Apple Music Library Activity.json**
   - Transaction-level library changes
   - addItems, removeItems, updateUser events

8. **Identifier Information.json**
   - Lookup table mapping IDs to titles
   - Format: {"Identifier": "1558596283", "Title": "Skin Of The Master"}

### Aggregate Statistics (CSV)
9. **Apple Music - Container Details.csv** - 1,141 rows
   - Album/playlist statistics with play metrics

10. **Apple Music - Play Statistics.csv** - 288 rows
    - Daily aggregate statistics

11. **Apple Music - Recently Played Tracks.csv** - 201 rows
    - Recent listening activity

12. **Apple Music - Container Origin.csv** - 634 rows
    - Radio station and playlist origins

### Additional Files
- Feature Statistics, Top Content, Favorites, Recent Impressions
- Music Onboarding (Artists, Genres)
- Liked Radio Tracks, Favorite Stations

## Data Relationships & Key Identifiers

### Identifier Ecosystem

#### Track Identifiers (Multiple Types)
1. **Library Track ID** (short numeric)
   - Example: `665642`
   - Used in: Library Tracks JSON, Library Activity JSON
   - Links to: Playlist Item Identifiers

2. **Play History Track ID** (long numeric)
   - Example: `775258899`, `911121225`
   - Used in: Play History Daily Tracks CSV
   - Field: "Track Identifier"

3. **Track Reference** (same as Play History ID)
   - Used for lookups in Play History
   - Can be N/A if not available

4. **Identifier Information ID** (long numeric)
   - Example: `1558596283`
   - Maps to track/album titles
   - Lookup table for human-readable names

#### Container Identifiers
1. **Container ID** (numeric)
   - Example: `1679002688`
   - Links albums, playlists, radio stations

2. **Container Reference** (numeric)
   - Example: `1768728131`
   - Used in Recently Played Containers

3. **Radio Station ID** (alphanumeric)
   - Example: `ra.985486574`
   - Used for radio/station tracking

#### Artist Identifiers
1. **Artist Identifier** (string)
   - Format: `r.056wvIt`
   - Used in Library Artists JSON

2. **Catalog Identifiers - Artist** (numeric)
   - Example: `148662`
   - Apple Music catalog reference

### Database-Like Relationships

```
Identifier Information.json (Lookup Table)
  ├─ Identifier → Title mapping
  └─ Used by: Play History, Container Details

Library Tracks.json (Track Master)
  ├─ Track Identifier (PK)
  ├─ Artist, Album, Genre metadata
  └─ Linked by: Playlist Item Identifiers

Library Playlists.json
  ├─ Container Identifier (PK)
  ├─ Playlist Item Identifiers (FK → Track Identifier)
  └─ Playlist metadata

Library Artists.json
  ├─ Artist Identifier (PK)
  ├─ Catalog Identifiers - Artist
  └─ Artist metadata

Play History Daily Tracks.csv
  ├─ Track Identifier (FK → Identifier Information)
  ├─ Track Reference (FK → Identifier Information)
  ├─ Date Played (YYYYMMDD)
  └─ Play metrics (duration, end reason, source)

Play Activity.csv (Most Detailed)
  ├─ Event ID (unique per play event)
  ├─ Song Name, Album Name, Container Name
  ├─ Timestamps (start, end, received)
  ├─ Device info, location, quality metrics
  └─ 130+ columns of telemetry

Container Details.csv
  ├─ Container Reference (FK)
  ├─ Track Reference (FK)
  ├─ Aggregate play metrics
  └─ Last played timestamps

Library Activity.json (Change Log)
  ├─ Transaction Identifier
  ├─ Transaction Type (addItems, removeItems, updateUser)
  ├─ Tracks array with Track Identifier
  └─ Timestamps
```

## Key Data Fields

### Temporal Fields
- **Date Played**: YYYYMMDD format (20150701)
- **Event Timestamp**: ISO-8601 (2024-07-02T22:34:59.918Z)
- **Last Played Date**: Epoch milliseconds (1750370508136)
- **Hours**: Hour of day (0-23)

### Play Metrics
- **Play Duration Milliseconds**: Actual play time
- **Media Duration Milliseconds**: Track length
- **End Reason Type**:
  - NATURAL_END_OF_TRACK
  - PLAYBACK_MANUALLY_PAUSED
  - MANUALLY_SELECTED_PLAYBACK_OF_A_DIFF_ITEM
  - TRACK_SKIPPED_FORWARDS
  - PLAYBACK_SUSPENDED

### Source/Context
- **Source Type**: IPHONE, ANDROID, UNKNOWN_DEVICE, AMAZON (Alexa)
- **Container Type**: ALBUM, RADIO, PLAYLIST
- **Media Type**: AUDIO (primary)
- **Feature Name**: search, radio, siri, alexa_voice_control

### Track Metadata (from Library Tracks)
- Content Type, Title, Artist, Album
- Genre, Track Year, Track Duration
- Track Play Count, Skip Count
- Is Purchased, Date Added To Library
- Composer, Album Artist

## Data Extraction Strategy for Lifeboard

### Priority 1: Play History (Most Valuable for Timeline)
**Apple Music - Play History Daily Tracks.csv** (44K rows)
- Date format: YYYYMMDD → days_date extraction
- Track Identifier → lookup in Identifier Information
- Duration, source, play/skip counts
- End reason for engagement metrics

**Apple Music Play Activity.csv** (122K rows)
- Most comprehensive but complex
- Event timestamps with device/location context
- Song Name directly available (no lookup needed)
- Rich metadata: shuffle, repeat, audio quality

### Priority 2: Library Context
**Apple Music Library Tracks.json**
- Track metadata for enrichment
- Genre, artist, album information
- Play counts and dates

**Identifier Information.json**
- Lookup table for Track Identifier → Title
- Essential for Daily Tracks CSV

### Priority 3: Aggregate Statistics
- Play Statistics: Daily totals
- Recently Played: Recent activity
- Favorites: User preferences

## Implementation Notes

### DataItem Mapping
```python
DataItem(
    id=f"apple_music:{track_identifier}:{timestamp}",
    namespace="apple_music",
    source_id=f"{track_identifier}:{timestamp}",
    content=f"{artist} - {title}",  # or full track description
    metadata={
        "source_type": "apple_music_play_history",
        "track_identifier": track_identifier,
        "artist": artist,
        "title": title,
        "album": album,
        "play_duration_ms": duration,
        "end_reason": end_reason,
        "device": source_type,
        "genre": genre,
        "is_skipped": skip_count > 0,
        # ... additional fields
    },
    days_date=extract_days_date(date_played)  # YYYYMMDD → YYYY-MM-DD
)
```

### Deduplication Strategy
- **Play History Daily Tracks**: Potential duplicates if same track played multiple times
  - Key: track_identifier + date_played + hours → unique play event

- **Play Activity**: Event ID is unique
  - Can use Event ID as source_id

### File Processing Order
1. Load Identifier Information.json → in-memory lookup dict
2. Load Library Tracks.json → track metadata lookup
3. Process Play History Daily Tracks.csv → primary timeline
4. Process Play Activity.csv → detailed events (optional, if needed)
5. Enrich with Library Artists/Playlists as needed

### Date Extraction Examples
- CSV format: `20150701` → `2015-07-01`
- ISO format: `2024-07-02T22:34:59.918Z` → `2024-07-02`
- Epoch ms: `1750370508136` → convert to date → `2025-06-18`

## Data Quality Notes

### Challenges
1. **Multiple ID Types**: Track IDs vary between files (short vs long)
2. **N/A Values**: Many Track Reference fields are N/A
3. **Encoding**: Track Description field combines "Artist - Title"
4. **Timestamp Formats**: 3 different formats across files

### Strengths
1. **Rich Metadata**: Genre, device, location, quality metrics
2. **Long History**: Data from 2015-2025 (10 years)
3. **Multiple Aggregations**: Daily, track-level, container-level
4. **Context Preservation**: End reason, source type, user initiation

## Recommended Implementation Approach

### Phase 1: Simple Import
- Parse Play History Daily Tracks CSV
- Use Identifier Information for lookups
- Extract: track, date, duration, play/skip counts
- Store in unified data_items table

### Phase 2: Enrichment
- Add Library Tracks metadata
- Include genre, artist, album info
- Add device and source context

### Phase 3: Advanced Features
- Play Activity CSV for detailed timeline
- Container/playlist analysis
- Listening pattern detection
- Genre/artist preferences

### Phase 4: Deduplication
- Cross-reference with Spotify data if available
- Merge duplicate plays across sources
- Semantic deduplication for similar tracks
