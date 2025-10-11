# Spotify Integration Plan

## Overview

This document outlines the plan to integrate Spotify recently played data into the Lifeboard application, allowing users to view their music listening history within the calendar day view and potentially interact with an embedded Spotify player.

## Requirements Summary

- **Data Source**: Spotify Web API "Recently Played Tracks" endpoint
- **Historical Data**: As far back as the API allows (limited to 50 most recent tracks)
- **Sync Strategy**: User-configurable scheduled sync via .env configuration
- **Display Integration**: Calendar day view shows played songs for each day
- **Player Integration**: Embedded Spotify player in day view (progressive enhancement)
- **Audio Features**: Always included (tempo, energy, valence, etc.)

## Technical Architecture

### Data Flow
```
Spotify Web API → Recently Played (50 tracks) → DataItem objects → 
Unified data_items table → Embedding generation → FAISS vector store
```

### Database Schema

#### Primary Storage (Unified Pattern)
All Spotify data follows the existing unified DataItem pattern:
- **Table**: `data_items`
- **Namespace**: `"spotify"`
- **Source ID**: `"{track_id}_{played_at_timestamp}"`
- **Content**: `"Artist - Track Name (Album)"`
- **Metadata**: JSON containing track details and audio features

#### Optional Spotify-Specific Table
```sql
CREATE TABLE spotify_tracks (
    id TEXT PRIMARY KEY,
    track_id TEXT NOT NULL,
    played_at TEXT NOT NULL,
    artist TEXT,
    track_name TEXT,
    album TEXT,
    duration_ms INTEGER,
    audio_features TEXT, -- JSON: tempo, energy, valence, etc.
    external_urls TEXT,   -- JSON: spotify, preview_url, etc.
    days_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Configuration Architecture

### Environment Variables (.env)
```bash
# Spotify API Configuration
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
SPOTIFY_ENABLED=true
SPOTIFY_SYNC_INTERVAL_HOURS=1  # User configurable sync frequency
```

### Configuration Model (config/models.py)
```python
class SpotifyConfig(BaseModel, BaseConfigMixin):
    """Spotify API configuration"""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  
    redirect_uri: str = "http://localhost:8888/callback"
    enabled: bool = True
    sync_interval_hours: int = 1  # User configurable
    recently_played_limit: int = 50  # Max allowed by API
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: float = 30.0
    rate_limit_max_delay: int = 300
    respect_retry_after: bool = True
    
    # OAuth scopes needed
    required_scopes: List[str] = [
        "user-read-recently-played",
        "user-read-playback-state"  # For player integration
    ]
```

## Implementation Components

### 1. Spotify Source Class (sources/spotify.py)
```python
class SpotifySource(BaseSource):
    """Spotify recently played tracks data source"""
    
    def __init__(self, namespace: str = "spotify"):
        super().__init__(namespace)
        self.client_id = config.spotify.client_id
        self.client_secret = config.spotify.client_secret
        
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 50) -> AsyncIterator[DataItem]:
        """Fetch recently played tracks from Spotify API"""
        # Implementation yields DataItem objects
        
    def get_source_type(self) -> str:
        return "spotify_recently_played"
        
    async def test_connection(self) -> bool:
        """Test Spotify API connectivity"""
```

### 2. OAuth Authentication Handler
- Handle Spotify OAuth2 flow
- Token refresh management
- Secure token storage

### 3. Audio Features Integration
- Automatic fetch of audio features for each track
- Store in DataItem metadata: tempo, energy, valence, danceability, etc.
- Enable music-based insights and correlations

### 4. Scheduler Integration
- Add Spotify sync job to existing scheduler
- Respect user-configured `SPOTIFY_SYNC_INTERVAL_HOURS`
- Handle rate limiting and error recovery

## Calendar Day View Integration

### Display Strategy: Timeline Integration
- Mix Spotify tracks chronologically with other daily activities
- Format: `🎵 [time] Artist - Track Name (Album)`
- Click to expand for full track details and album art
- Show listening duration and audio features on hover

### Data Presentation
```
🎵 9:23 AM - Taylor Swift - Anti-Hero (Midnights)
   ↳ Duration: 3:21 | Energy: 0.65 | Valence: 0.33
```

## Player Integration (Progressive Enhancement)

### Phase 1: Basic Integration
- Display track information with "Open in Spotify" links
- Show album art and basic metadata
- No Premium requirement

### Phase 2: Preview Player
- 30-second track previews using Spotify's preview URLs
- Basic play/pause controls
- Works for all users (no Premium required)

### Phase 3: Full Web Playback SDK (Future)
- Complete Spotify player integration
- Full playback control within Lifeboard
- Requires Spotify Premium subscription
- Additional OAuth scopes needed

## API Limitations & Considerations

### Historical Data Limitations
- **Spotify API Constraint**: Only provides last 50 tracks
- **Solution**: Continuous collection starting from implementation date
- **User Communication**: Clearly explain that historical data is limited to sync start date

### Rate Limiting
- Follow Spotify API rate limits
- Implement exponential backoff
- Respect `Retry-After` headers

### Data Quality
- Handle missing preview URLs gracefully
- Audio features may not be available for all tracks
- Manage offline periods and sync gaps

## Development Phases

### Phase 1: Core Integration
1. Create SpotifyConfig and add to AppConfig
2. Implement SpotifySource class
3. Add OAuth2 authentication flow
4. Create basic scheduler job
5. Update .env.example with Spotify configuration

### Phase 2: UI Integration
1. Add Spotify data to calendar day view
2. Implement timeline display format
3. Add track detail expansion
4. Show audio features in metadata

### Phase 3: Enhanced Features
1. Implement preview player
2. Add music-based insights to AI assistant
3. Correlate music with mood/activity data
4. Advanced player controls (if Premium available)

## Testing Strategy

### Unit Tests
- SpotifySource class methods
- OAuth token handling
- Data transformation to DataItem format
- Audio features processing

### Integration Tests
- End-to-end sync process
- Calendar view display
- Error handling and recovery
- Rate limit compliance

### Manual Testing
- OAuth flow with real Spotify account
- Player functionality across browsers
- Data accuracy and completeness
- Performance with large music libraries

## Security Considerations

- Secure storage of OAuth tokens
- Token refresh handling
- API key protection in environment variables
- User consent for data access
- Compliance with Spotify's Terms of Service

## Success Metrics

- Successful OAuth authentication flow
- Consistent data sync without gaps
- Accurate track metadata and audio features
- Smooth calendar integration
- Positive user experience with player controls
- No API rate limit violations

## Future Enhancements

- **Playlist Integration**: Show user's playlists and recently saved tracks
- **Music Recommendations**: AI-powered music discovery based on listening patterns
- **Social Features**: Share favorite tracks or music insights
- **Advanced Analytics**: Listening habit analysis and trends
- **Smart Insights**: Correlate music choices with productivity, mood, or activities