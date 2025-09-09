# Spotify OAuth Integration Technical Specification

## Overview

This document provides the technical specification for implementing popup-based OAuth 2.0 authentication for Spotify integration in the Lifeboard application. The implementation transforms the existing client credentials flow into a user-authorized system that enables access to personal Spotify data.

**Development Approach**: This specification follows Test-Driven Development (TDD) principles, ensuring comprehensive test coverage at all levels before implementation begins.

## Current State Analysis

### Existing Implementation
- ✅ **SpotifyConfig**: Complete configuration model with OAuth fields
- ✅ **OAuth Routes**: `/auth/url` and `/auth/callback` endpoints with mock token exchange
- ✅ **Data Models**: Comprehensive SpotifyTrack, SpotifyArtist, SpotifyAlbum models
- ✅ **Frontend Components**: SpotifyPlayer and MusicHistory components
- ✅ **API Client**: Basic getSpotifyTracks method

### Current Issues
- ❌ **Mock Token Exchange**: `/auth/callback` returns mock tokens
- ❌ **Wrong Auth Flow**: SpotifySource uses client credentials for user data
- ❌ **No Token Storage**: No database storage for user tokens
- ❌ **No Auth State**: Frontend has no awareness of authentication status

## Technical Architecture

### Authentication Flow Architecture
```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌─────────────┐
│   Frontend  │    │   Backend    │    │   Spotify     │    │  Database   │
│             │    │              │    │   OAuth       │    │             │
├─────────────┤    ├──────────────┤    ├───────────────┤    ├─────────────┤
│1. Click     │───▶│2. Generate   │    │               │    │             │
│  Refresh    │    │   auth URL   │    │               │    │             │
│             │    │              │    │               │    │             │
│3. Open      │◀───┤              │    │               │    │             │
│  Popup      │    │              │    │               │    │             │
│             │    │              │    │               │    │             │
│4. Redirect  │───────────────────────▶│5. User        │    │             │
│  to Spotify │    │              │    │   Authorize   │    │             │
│             │    │              │    │               │    │             │
│7. Receive   │◀───────────────────────┤6. Callback    │    │             │
│  auth code  │    │              │    │   with code   │    │             │
│             │    │              │    │               │    │             │
│8. Send code │───▶│9. Exchange   │───▶│10. Return     │    │             │
│  to backend │    │   for tokens │    │    tokens     │    │             │
│             │    │              │    │               │    │             │
│             │    │11. Store     │    │               │───▶│12. Save     │
│             │    │    tokens    │    │               │    │    tokens   │
│             │    │              │    │               │    │             │
│13. Refresh  │◀───┤              │    │               │    │             │
│    UI       │    │              │    │               │    │             │
└─────────────┘    └──────────────┘    └───────────────┘    └─────────────┘
```

### Data Flow Architecture
```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│  User Token │    │   Spotify    │    │   Lifeboard   │
│   Storage   │    │     API      │    │   Database    │
├─────────────┤    ├──────────────┤    ├───────────────┤
│access_token │───▶│/me/player/   │───▶│  data_items   │
│refresh_token│    │recently-     │    │  (spotify     │
│expires_at   │    │played        │    │   namespace)  │
│             │    │              │    │               │
│Auto-refresh │◀───┤Rate Limiting │    │Vector Store   │
│before expiry│    │& Retry Logic │───▶│(FAISS Index) │
└─────────────┘    └──────────────┘    └───────────────┘
```

## Database Schema

### spotify_tokens Table
```sql
CREATE TABLE spotify_tokens (
    id INTEGER PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP NOT NULL,
    scope TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_expiry CHECK (expires_at > created_at),
    CONSTRAINT non_empty_access_token CHECK (length(trim(access_token)) > 0)
);

-- Indexes for performance
CREATE INDEX idx_spotify_tokens_expires_at ON spotify_tokens(expires_at);
CREATE INDEX idx_spotify_tokens_updated_at ON spotify_tokens(updated_at);
```

### Migration Implementation
- **File**: `core/migrations/versions/0015_add_spotify_tokens_table.py`
- **Pattern**: Follow existing migration structure
- **Rollback**: Include DROP TABLE in down migration
- **Testing**: Verify table creation and constraints

## Backend Implementation

### 1. Database Service Extensions

#### Token Management Methods
```python
# In core/database.py or new services/spotify_auth_service.py

class SpotifyTokenService:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def store_tokens(self, access_token: str, refresh_token: str, expires_in: int, scope: str) -> bool:
        """Store OAuth tokens in database"""
        
    async def get_valid_token(self) -> Optional[str]:
        """Get current valid access token, refresh if necessary"""
        
    async def refresh_token_if_needed(self) -> bool:
        """Check expiry and refresh token if within 5 minutes of expiration"""
        
    async def is_authenticated(self) -> bool:
        """Check if user has valid authentication"""
        
    async def revoke_tokens(self) -> bool:
        """Clear stored tokens (logout)"""
```

### 2. Updated Spotify Routes

#### Real Token Exchange Implementation
```python
# In api/routes/spotify.py

async def exchange_code_for_token(code: str, config) -> Dict[str, Any]:
    """Real implementation replacing mock"""
    token_url = "https://accounts.spotify.com/api/token"
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "client_secret": config.client_secret
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=400, detail="Token exchange failed")
```

#### New Auth Status Endpoint
```python
@router.get("/auth/status")
async def get_auth_status(startup_service: StartupService = Depends(...)):
    """Check if user is authenticated with Spotify"""
    token_service = SpotifyTokenService(startup_service.database)
    is_authenticated = await token_service.is_authenticated()
    
    return {
        "authenticated": is_authenticated,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### 3. SpotifySource Authentication Update

#### Token-Based Authentication
```python
# In sources/spotify.py

class SpotifySource(BaseHTTPSource, BaseSource):
    def __init__(self, config: SpotifyConfig, db_service: DatabaseService = None):
        super().__init__(config, "spotify")
        self.token_service = SpotifyTokenService(db_service)
    
    async def _get_access_token(self) -> str:
        """Get user access token instead of client credentials"""
        token = await self.token_service.get_valid_token()
        if not token:
            raise Exception("User not authenticated with Spotify")
        return token
    
    async def is_user_authenticated(self) -> bool:
        """Check if user has valid authentication"""
        return await self.token_service.is_authenticated()
```

### 4. Error Handling and Recovery

#### Authentication Error Responses
```python
# Consistent error responses for unauthenticated requests
{
    "authenticated": false,
    "error": "spotify_auth_required",
    "message": "Please authenticate with Spotify to access your data",
    "auth_url": "/spotify/auth/url"
}
```

## Frontend Implementation

### 1. New API Client Methods

#### Extended API Interface
```typescript
// In frontend/src/lib/api.ts

export interface SpotifyAuthStatus {
  authenticated: boolean;
  timestamp: string;
  error?: string;
}

export interface SpotifyAuthUrl {
  auth_url: string;
}

export const apiClient = {
  // ... existing methods ...
  
  // Spotify OAuth methods
  getSpotifyAuthStatus: (): Promise<ApiResponse<SpotifyAuthStatus>> => {
    return apiFetch<SpotifyAuthStatus>('/spotify/auth/status');
  },
  
  getSpotifyAuthUrl: (): Promise<ApiResponse<SpotifyAuthUrl>> => {
    return apiFetch<SpotifyAuthUrl>('/spotify/auth/url');
  },
  
  exchangeSpotifyCode: (code: string): Promise<ApiResponse<any>> => {
    return apiFetch('/spotify/auth/callback', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  },
};
```

### 2. Auth Status Hook

#### useSpotifyAuth Hook
```typescript
// New file: frontend/src/hooks/useSpotifyAuth.ts

export const useSpotifyAuth = () => {
  const queryClient = useQueryClient();
  
  // Check authentication status
  const { data: authStatus, isLoading } = useQuery({
    queryKey: ['spotify', 'auth', 'status'],
    queryFn: async () => {
      const response = await apiClient.getSpotifyAuthStatus();
      if (!response.success) throw new Error(response.error);
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
  });
  
  // Initiate OAuth flow
  const initiateAuth = useMutation({
    mutationFn: async () => {
      const response = await apiClient.getSpotifyAuthUrl();
      if (!response.success) throw new Error(response.error);
      
      return new Promise((resolve, reject) => {
        const popup = window.open(
          response.data.auth_url,
          'spotify-auth',
          'width=600,height=700,scrollbars=yes,resizable=yes'
        );
        
        const pollForCode = setInterval(() => {
          try {
            if (popup?.closed) {
              clearInterval(pollForCode);
              reject(new Error('User closed popup'));
              return;
            }
            
            const url = popup?.location?.href;
            if (url?.includes('code=')) {
              const code = new URL(url).searchParams.get('code');
              popup.close();
              clearInterval(pollForCode);
              resolve(code);
            }
          } catch (e) {
            // Cross-origin error, continue polling
          }
        }, 1000);
      });
    },
    onSuccess: async (code) => {
      // Exchange code for tokens
      await apiClient.exchangeSpotifyCode(code);
      // Refresh auth status
      queryClient.invalidateQueries({ queryKey: ['spotify', 'auth'] });
      // Refresh Spotify data
      queryClient.invalidateQueries({ queryKey: ['spotify'] });
    },
  });
  
  return {
    isAuthenticated: authStatus?.authenticated || false,
    isLoading,
    initiateAuth: initiateAuth.mutateAsync,
    isAuthenticating: initiateAuth.isPending,
  };
};
```

### 3. SpotifyAuthStatus Component

#### Connection Status Indicator
```typescript
// New file: frontend/src/components/SpotifyAuthStatus.tsx

interface SpotifyAuthStatusProps {
  onAuthClick?: () => void;
  className?: string;
}

export const SpotifyAuthStatus: React.FC<SpotifyAuthStatusProps> = ({ 
  onAuthClick, 
  className = "" 
}) => {
  const { isAuthenticated, isLoading, initiateAuth, isAuthenticating } = useSpotifyAuth();
  
  if (isLoading) {
    return (
      <div className={`flex items-center space-x-2 text-xs ${className}`}>
        <div className="animate-spin rounded-full h-3 w-3 border border-gray-300 border-t-transparent"></div>
        <span className="text-gray-500">Checking connection...</span>
      </div>
    );
  }
  
  if (isAuthenticated) {
    return (
      <div className={`flex items-center space-x-2 text-xs ${className}`}>
        <div className="h-2 w-2 rounded-full bg-green-500"></div>
        <span className="text-green-700">Connected to Spotify</span>
      </div>
    );
  }
  
  return (
    <div className={`flex items-center space-x-2 text-xs ${className}`}>
      <div className="h-2 w-2 rounded-full bg-red-500"></div>
      <button
        onClick={onAuthClick || initiateAuth}
        disabled={isAuthenticating}
        className="text-red-700 hover:text-red-800 underline disabled:opacity-50"
      >
        {isAuthenticating ? 'Connecting...' : 'Connect Spotify'}
      </button>
    </div>
  );
};
```

### 4. Enhanced useSpotifyData Hook

#### Smart Refresh with Auth Handling
```typescript
// Update frontend/src/hooks/useSpotifyData.ts

export const useSpotifyRefresh = (selectedDate?: string) => {
  const queryClient = useQueryClient();
  const { isAuthenticated, initiateAuth } = useSpotifyAuth();
  
  return useMutation({
    mutationFn: async () => {
      // Check authentication first
      if (!isAuthenticated) {
        await initiateAuth();
      }
      
      // Proceed with existing refresh logic
      const syncResponse = await apiClient.triggerSync('spotify');
      // ... rest of existing implementation
    },
    // ... existing onSuccess/onError handlers
  });
};
```

### 5. Updated MusicHistory Component

#### Auth Status Integration
```typescript
// Update frontend/src/components/MusicHistory.tsx

export const MusicHistory = ({ selectedDate }: MusicHistoryProps) => {
  const { data: tracks, isLoading, error } = useSpotifyTracks(selectedDate);
  const refreshMutation = useSpotifyRefresh(selectedDate);
  const { isAuthenticated } = useSpotifyAuth();
  
  // Updated header with auth status
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-music-accent pb-2 relative">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
              Music Journal
            </h2>
            <p className="text-newspaper-byline font-body text-sm">
              Your daily soundtrack and listening history
              {selectedDate && ` • ${selectedDate}`}
            </p>
            <SpotifyAuthStatus className="mt-1" />
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isLoading || refreshMutation.isPending}
            className="h-8 w-8"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading || refreshMutation.isPending ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>
      
      {/* Updated empty state with better auth messaging */}
      {!tracks || tracks.length === 0 ? (
        <Card className="p-6 bg-gradient-to-r from-music-accent/5 to-music-accent/10">
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-4xl mb-4">🎵</div>
              <h3 className="font-headline text-lg font-bold text-newspaper-headline mb-2">
                {isAuthenticated 
                  ? 'No music history found'
                  : 'Connect your Spotify account'
                }
              </h3>
              <p className="text-newspaper-byline mb-4">
                {isAuthenticated
                  ? selectedDate 
                    ? `No tracks were played on ${selectedDate}`
                    : 'No recent tracks found'
                  : 'Connect to Spotify to see your music listening history'
                }
              </p>
              {!isAuthenticated && (
                <SpotifyAuthStatus className="justify-center" />
              )}
            </div>
          </div>
        </Card>
      ) : (
        // ... existing tracks display
      )}
    </div>
  );
};
```

## Security Considerations

### Token Security
- **Storage**: Tokens stored server-side in database, not in browser
- **Transmission**: HTTPS only for all OAuth communications
- **Expiration**: Automatic refresh with 5-minute buffer before expiry
- **Scopes**: Minimal required scopes (`user-read-recently-played`)

### CORS and Popup Security
- **Redirect URI**: Must exactly match registered Spotify app URI
- **Popup Communication**: Use postMessage for secure cross-origin communication
- **CSRF Protection**: Include state parameter in OAuth flow
- **Error Handling**: Graceful fallback for blocked popups

### API Security
- **Rate Limiting**: Respect Spotify API limits with exponential backoff
- **Token Validation**: Verify token validity before each API call
- **Error Responses**: Don't expose sensitive token information
- **Audit Logging**: Log authentication events for security monitoring

## Test-Driven Development Plan

### TDD Implementation Approach

Following the Red-Green-Refactor cycle for all components:

1. **RED**: Write failing tests for the desired functionality
2. **GREEN**: Write minimal implementation to make tests pass
3. **REFACTOR**: Clean up code while maintaining test passes

### Test Coverage Requirements

- **Unit Tests**: ≥90% coverage for all new services and utilities
- **Integration Tests**: ≥85% coverage for API endpoints and database interactions
- **End-to-End Tests**: 100% coverage for critical user paths
- **Component Tests**: ≥90% coverage for React components with user interactions

### Test Categories & Implementation Order

#### Phase 1: Database & Core Services Tests (Write First)

**1.1 Database Migration Tests**
```python
# tests/unit/core/migrations/test_0015_spotify_tokens.py

class TestSpotifyTokensMigration:
    def test_migration_creates_table_with_constraints(self, db_cursor):
        """Test table creation with proper constraints"""
        # RED: Test fails - table doesn't exist
        assert False, "spotify_tokens table not found"
    
    def test_migration_creates_indexes(self, db_cursor):
        """Test index creation for performance"""
        # RED: Test fails - indexes don't exist
        assert False, "Required indexes not found"
    
    def test_migration_rollback_removes_table(self, db_cursor):
        """Test rollback functionality"""
        # RED: Test fails - rollback not implemented
        assert False, "Rollback not properly implemented"
    
    def test_constraint_validation(self, db_cursor):
        """Test database constraints work correctly"""
        # RED: Test fails - constraints not enforced
        assert False, "Database constraints not working"
```

**1.2 SpotifyTokenService Tests**
```python
# tests/unit/services/test_spotify_token_service.py

class TestSpotifyTokenService:
    def test_store_tokens_success(self, mock_db):
        """Test successful token storage"""
        # RED: Service doesn't exist yet
        service = SpotifyTokenService(mock_db)
        result = await service.store_tokens("access", "refresh", 3600, "scope")
        assert result is True
    
    def test_get_valid_token_unexpired(self, mock_db_with_token):
        """Test retrieving valid unexpired token"""
        # RED: Method doesn't exist
        service = SpotifyTokenService(mock_db_with_token)
        token = await service.get_valid_token()
        assert token == "valid_access_token"
    
    def test_get_valid_token_expired_refreshes(self, mock_db_with_expired_token):
        """Test automatic refresh of expired tokens"""
        # RED: Refresh logic not implemented
        service = SpotifyTokenService(mock_db_with_expired_token)
        token = await service.get_valid_token()
        assert token is not None
    
    def test_is_authenticated_with_valid_token(self, mock_db_with_token):
        """Test authentication status check"""
        # RED: Method doesn't exist
        service = SpotifyTokenService(mock_db_with_token)
        result = await service.is_authenticated()
        assert result is True
    
    def test_is_authenticated_without_token(self, mock_empty_db):
        """Test authentication status when no token exists"""
        # RED: Method doesn't exist
        service = SpotifyTokenService(mock_empty_db)
        result = await service.is_authenticated()
        assert result is False
    
    def test_revoke_tokens_clears_storage(self, mock_db_with_token):
        """Test token revocation clears stored tokens"""
        # RED: Method doesn't exist
        service = SpotifyTokenService(mock_db_with_token)
        result = await service.revoke_tokens()
        assert result is True
        # Verify tokens are cleared
        auth_status = await service.is_authenticated()
        assert auth_status is False
```

#### Phase 2: API Routes Tests (Write First)

**2.1 OAuth Routes Tests**
```python
# tests/api/test_spotify_oauth_routes.py

class TestSpotifyOAuthRoutes:
    def test_auth_url_generation(self, test_client, spotify_config):
        """Test OAuth URL generation endpoint"""
        # RED: Real implementation not done
        response = test_client.get("/spotify/auth/url")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "accounts.spotify.com/authorize" in data["auth_url"]
    
    def test_auth_callback_success(self, test_client, mock_spotify_token_exchange):
        """Test successful OAuth callback with code exchange"""
        # RED: Mock token exchange not implemented
        response = test_client.get("/spotify/auth/callback?code=valid_code")
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["expires_in"]
    
    def test_auth_callback_invalid_code(self, test_client):
        """Test OAuth callback with invalid code"""
        # RED: Error handling not implemented
        response = test_client.get("/spotify/auth/callback?code=invalid_code")
        assert response.status_code == 400
        assert "error" in response.json()
    
    def test_auth_status_authenticated(self, test_client, authenticated_user):
        """Test auth status endpoint when user is authenticated"""
        # RED: Status endpoint doesn't exist
        response = test_client.get("/spotify/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert "timestamp" in data
    
    def test_auth_status_not_authenticated(self, test_client):
        """Test auth status endpoint when user is not authenticated"""
        # RED: Status endpoint doesn't exist
        response = test_client.get("/spotify/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
```

**2.2 Token Exchange Tests**
```python
# tests/unit/api/test_token_exchange.py

class TestTokenExchange:
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self, mock_spotify_api):
        """Test successful token exchange with Spotify API"""
        # RED: Real exchange function doesn't exist
        mock_spotify_api.post.return_value.status_code = 200
        mock_spotify_api.post.return_value.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        
        result = await exchange_code_for_token("auth_code", mock_config)
        assert result["access_token"] == "new_access_token"
        assert result["expires_in"] == 3600
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_failure(self, mock_spotify_api):
        """Test token exchange failure handling"""
        # RED: Error handling not implemented
        mock_spotify_api.post.return_value.status_code = 400
        
        with pytest.raises(HTTPException) as exc_info:
            await exchange_code_for_token("invalid_code", mock_config)
        assert exc_info.value.status_code == 400
        assert "Token exchange failed" in str(exc_info.value.detail)
```

#### Phase 3: SpotifySource Update Tests (Write First)

**3.1 SpotifySource Authentication Tests**
```python
# tests/unit/sources/test_spotify_source_oauth.py

class TestSpotifySourceOAuth:
    @pytest.mark.asyncio
    async def test_get_access_token_authenticated_user(self, mock_token_service):
        """Test token retrieval for authenticated user"""
        # RED: OAuth integration not implemented
        mock_token_service.get_valid_token.return_value = "user_access_token"
        
        source = SpotifySource(mock_config, mock_db)
        token = await source._get_access_token()
        assert token == "user_access_token"
    
    @pytest.mark.asyncio
    async def test_get_access_token_unauthenticated_user(self, mock_token_service):
        """Test token retrieval for unauthenticated user"""
        # RED: Error handling not implemented
        mock_token_service.get_valid_token.return_value = None
        
        source = SpotifySource(mock_config, mock_db)
        with pytest.raises(Exception) as exc_info:
            await source._get_access_token()
        assert "User not authenticated" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_is_user_authenticated_true(self, mock_token_service):
        """Test authentication check for authenticated user"""
        # RED: Method doesn't exist
        mock_token_service.is_authenticated.return_value = True
        
        source = SpotifySource(mock_config, mock_db)
        result = await source.is_user_authenticated()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_fetch_items_authenticated_user(self, mock_token_service, mock_spotify_api):
        """Test data fetching with user authentication"""
        # RED: User token integration not implemented
        mock_token_service.get_valid_token.return_value = "user_token"
        mock_spotify_api.get.return_value.json.return_value = {
            "items": [{"track": {"id": "123", "name": "Test Track"}}]
        }
        
        source = SpotifySource(mock_config, mock_db)
        items = [item async for item in source.fetch_items()]
        assert len(items) > 0
        assert items[0].namespace == "spotify"
```

#### Phase 4: Frontend Component Tests (Write First)

**4.1 useSpotifyAuth Hook Tests**
```javascript
// tests/frontend/hooks/test_useSpotifyAuth.test.ts

describe('useSpotifyAuth', () => {
  test('returns authentication status correctly', async () => {
    // RED: Hook doesn't exist yet
    mockApiClient.getSpotifyAuthStatus.mockResolvedValue({
      success: true,
      data: { authenticated: true, timestamp: new Date().toISOString() }
    });
    
    const { result } = renderHook(() => useSpotifyAuth());
    
    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isLoading).toBe(false);
    });
  });
  
  test('initiates OAuth flow correctly', async () => {
    // RED: OAuth flow not implemented
    const mockOpen = jest.spyOn(window, 'open').mockImplementation(() => mockPopup);
    mockApiClient.getSpotifyAuthUrl.mockResolvedValue({
      success: true,
      data: { auth_url: 'https://accounts.spotify.com/authorize?...' }
    });
    
    const { result } = renderHook(() => useSpotifyAuth());
    
    act(() => {
      result.current.initiateAuth();
    });
    
    expect(mockOpen).toHaveBeenCalledWith(
      expect.stringContaining('accounts.spotify.com'),
      'spotify-auth',
      expect.stringContaining('width=600,height=700')
    );
  });
  
  test('handles popup blocked scenario', async () => {
    // RED: Error handling not implemented
    jest.spyOn(window, 'open').mockReturnValue(null);
    
    const { result } = renderHook(() => useSpotifyAuth());
    
    await expect(result.current.initiateAuth()).rejects.toThrow('Popup blocked');
  });
});
```

**4.2 SpotifyAuthStatus Component Tests**
```javascript
// tests/frontend/components/test_SpotifyAuthStatus.test.tsx

describe('SpotifyAuthStatus', () => {
  test('shows loading state initially', () => {
    // RED: Component doesn't exist
    mockUseSpotifyAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      initiateAuth: jest.fn(),
      isAuthenticating: false
    });
    
    render(<SpotifyAuthStatus />);
    
    expect(screen.getByText('Checking connection...')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
  
  test('shows connected state when authenticated', () => {
    // RED: Connected state not implemented
    mockUseSpotifyAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      initiateAuth: jest.fn(),
      isAuthenticating: false
    });
    
    render(<SpotifyAuthStatus />);
    
    expect(screen.getByText('Connected to Spotify')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('bg-green-500');
  });
  
  test('shows connect button when not authenticated', () => {
    // RED: Connect button not implemented
    const mockInitiateAuth = jest.fn();
    mockUseSpotifyAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      initiateAuth: mockInitiateAuth,
      isAuthenticating: false
    });
    
    render(<SpotifyAuthStatus />);
    
    const connectButton = screen.getByRole('button', { name: /connect spotify/i });
    expect(connectButton).toBeInTheDocument();
    
    fireEvent.click(connectButton);
    expect(mockInitiateAuth).toHaveBeenCalled();
  });
  
  test('shows connecting state during authentication', () => {
    // RED: Authenticating state not implemented
    mockUseSpotifyAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      initiateAuth: jest.fn(),
      isAuthenticating: true
    });
    
    render(<SpotifyAuthStatus />);
    
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

#### Phase 5: Integration Tests (Write First)

**5.1 End-to-End OAuth Flow Tests**
```javascript
// tests/e2e/test_spotify_oauth_flow.spec.js

describe('Spotify OAuth Flow E2E', () => {
  test('complete authentication flow works', async () => {
    // RED: Full flow not implemented
    await page.goto('/music-history');
    
    // Should show unauthenticated state
    await expect(page.getByText('Connect your Spotify account')).toBeVisible();
    
    // Click connect button
    await page.getByRole('button', { name: /connect spotify/i }).click();
    
    // Should open popup (mock Spotify OAuth)
    const popup = await page.waitForEvent('popup');
    await popup.goto('http://localhost:8888/api/spotify/auth/callback?code=test_code');
    
    // Should close popup and show authenticated state
    await expect(page.getByText('Connected to Spotify')).toBeVisible();
    
    // Should enable refresh functionality
    const refreshButton = page.getByRole('button', { name: /refresh/i });
    await refreshButton.click();
    
    // Should fetch and display music data
    await expect(page.getByText('Music Journal')).toBeVisible();
  });
  
  test('handles popup blocked scenario gracefully', async () => {
    // RED: Error handling not implemented
    await page.addInitScript(() => {
      window.open = () => null; // Simulate blocked popup
    });
    
    await page.goto('/music-history');
    await page.getByRole('button', { name: /connect spotify/i }).click();
    
    // Should show fallback message
    await expect(page.getByText(/popup blocked/i)).toBeVisible();
  });
  
  test('token refresh works automatically', async () => {
    // RED: Auto-refresh not implemented
    // Setup user with expiring token
    await setupUserWithExpiringToken();
    
    await page.goto('/music-history');
    
    // Wait for token expiry
    await page.waitForTimeout(6000);
    
    // Trigger API call
    await page.getByRole('button', { name: /refresh/i }).click();
    
    // Should automatically refresh token and succeed
    await expect(page.getByText('Connected to Spotify')).toBeVisible();
  });
});
```

### Test Implementation Strategy

#### TDD Development Workflow

**For Each Component/Feature:**

1. **Write Comprehensive Tests First**
   ```bash
   # Example for SpotifyTokenService
   touch tests/unit/services/test_spotify_token_service.py
   # Write all test methods (RED phase)
   pytest tests/unit/services/test_spotify_token_service.py  # All should fail
   ```

2. **Implement Minimal Code to Pass Tests**
   ```bash
   # Create service with minimal implementation
   touch services/spotify_token_service.py
   # Add just enough code to make tests pass (GREEN phase)
   pytest tests/unit/services/test_spotify_token_service.py  # Should pass
   ```

3. **Refactor While Maintaining Test Coverage**
   ```bash
   # Clean up code, add error handling, optimize
   # REFACTOR phase - tests must continue passing
   pytest tests/unit/services/test_spotify_token_service.py  # Still passing
   ```

#### Test Coverage Gates

**Automated Quality Gates:**
```yaml
# In CI/CD pipeline
test_requirements:
  unit_coverage: >=90%
  integration_coverage: >=85%
  e2e_coverage: 100%  # For critical paths
  
quality_gates:
  - all_tests_pass: required
  - no_skipped_tests: required
  - coverage_threshold: required
  - security_scan: required
```

**Pre-Implementation Checklist:**
- [ ] All test files created with failing tests
- [ ] Test coverage plan documented
- [ ] Mock objects and fixtures prepared
- [ ] Integration test environment configured
- [ ] E2E test scenarios defined
- [ ] Performance benchmarks established

### Testing Tools & Frameworks

**Backend Testing Stack:**
- **pytest**: Primary testing framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking capabilities
- **httpx**: HTTP client testing
- **factory-boy**: Test data generation

**Frontend Testing Stack:**
- **Jest**: Unit testing framework
- **React Testing Library**: Component testing
- **MSW**: API mocking
- **Playwright**: E2E browser testing
- **@testing-library/user-event**: User interaction simulation

**Database Testing:**
- **SQLite in-memory**: Fast test database
- **pytest fixtures**: Database state management
- **Transaction rollback**: Test isolation

### Test Data Management

**Test Fixtures:**
```python
# tests/fixtures/spotify_fixtures.py

@pytest.fixture
def mock_spotify_tokens():
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "user-read-recently-played"
    }

@pytest.fixture
def mock_spotify_api_response():
    return {
        "items": [
            {
                "track": {
                    "id": "4iV5W9uYEdYUVa79Axb7Rh",
                    "name": "Clair de Lune",
                    "artists": [{"name": "Claude Debussy"}]
                },
                "played_at": "2024-01-01T12:00:00Z"
            }
        ]
    }
```

### Continuous Testing Strategy

**Development Workflow:**
1. **Pre-commit hooks**: Run relevant tests before commits
2. **CI pipeline**: Full test suite on pull requests
3. **Staging deployment**: Integration tests on staging environment
4. **Production monitoring**: Health checks and error tracking

**Test Execution Timeline:**
- **Unit Tests**: < 30 seconds (run on every save)
- **Integration Tests**: < 2 minutes (run on commit)
- **E2E Tests**: < 5 minutes (run on PR)
- **Performance Tests**: < 10 minutes (run on deploy)

## Error Handling

### Backend Error States
```python
class SpotifyAuthError(Exception):
    """Base class for Spotify authentication errors"""

class TokenExpiredError(SpotifyAuthError):
    """Token has expired and refresh failed"""

class AuthRequiredError(SpotifyAuthError):
    """User authentication required"""

class TokenRefreshError(SpotifyAuthError):
    """Failed to refresh access token"""
```

### Frontend Error States
- **Popup Blocked**: Show manual auth link
- **Network Error**: Retry mechanism with exponential backoff
- **Token Expired**: Automatic re-authentication flow
- **User Cancellation**: Graceful handling without errors

## Performance Considerations

### Database Optimization
- Index on `expires_at` for efficient token queries
- Connection pooling for high-frequency token checks
- Minimal token table schema for fast reads/writes

### Frontend Optimization
- Auth status caching with 5-minute stale time
- Debounced refresh requests
- Lazy loading of auth components
- Efficient re-renders on auth state changes

### API Optimization
- Token refresh only when needed (5-minute buffer)
- Batched API requests where possible
- Intelligent retry logic with backoff
- Connection reuse for multiple API calls

## Deployment Considerations

### Environment Variables
```bash
# Required for OAuth flow
SPOTIFY_CLIENT_ID=your_app_client_id
SPOTIFY_CLIENT_SECRET=your_app_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/api/spotify/auth/callback
```

### Database Migration
1. Run migration to create `spotify_tokens` table
2. Verify table creation and constraints
3. Test token storage functionality
4. Update backup procedures to include new table

### Monitoring
- Track OAuth success/failure rates
- Monitor token refresh frequency
- Alert on authentication errors
- Log API rate limiting events

## Implementation Timeline

### Phase 1: Backend Foundation (2-3 days)
1. Create database migration
2. Implement SpotifyTokenService
3. Update OAuth routes with real token exchange
4. Add auth status endpoint
5. Unit tests for backend components

### Phase 2: Frontend Integration (2-3 days)
1. Create useSpotifyAuth hook
2. Build SpotifyAuthStatus component
3. Update useSpotifyData with auth handling
4. Integrate auth status into MusicHistory
5. Frontend unit tests

### Phase 3: Integration & Testing (1-2 days)
1. End-to-end testing
2. Error handling verification
3. Performance optimization
4. Security audit
5. Documentation updates

### Phase 4: Production Readiness (1 day)
1. Environment configuration
2. Deployment testing
3. Monitoring setup
4. User acceptance testing

## Success Metrics

### Technical Metrics
- OAuth success rate >95%
- Token refresh success rate >99%
- API response time <500ms
- Zero token storage security incidents

### User Experience Metrics
- Auth flow completion rate >90%
- User confusion incidents <5%
- Support requests related to auth <2%
- Overall user satisfaction with music features

## Future Enhancements

### Advanced Features
1. **Multiple Account Support**: Support for family/shared accounts
2. **Offline Mode**: Graceful handling of network unavailability
3. **Enhanced Player**: Full Spotify Web Playback SDK integration
4. **Social Features**: Music sharing and collaborative playlists

### Security Improvements
1. **PKCE Flow**: Implement Proof Key for Code Exchange
2. **Token Rotation**: Periodic token refresh for enhanced security
3. **Audit Trails**: Detailed logging for security compliance
4. **Rate Limiting**: Client-side rate limiting to prevent abuse

This specification provides a comprehensive implementation guide for transforming the current Spotify integration from client credentials to a user-authorized OAuth system with a seamless popup-based authentication experience.