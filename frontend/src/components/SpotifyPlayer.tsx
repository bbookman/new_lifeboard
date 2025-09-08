import React, { useEffect, useState, useRef, useCallback } from 'react';

// TypeScript interfaces for Spotify SDK types
interface SpotifyTrack {
  id: string;
  name: string;
  artists: Array<{ name: string }>;
  album: {
    name: string;
    images: Array<{ url: string }>;
  };
  preview_url: string | null;
  duration_ms: number;
}

interface SpotifyPlayerState {
  track_window: {
    current_track: SpotifyTrack;
  };
  paused: boolean;
  position: number;
  duration: number;
}

interface SpotifyPlayer {
  connect(): Promise<boolean>;
  disconnect(): void;
  addListener(event: string, callback: (data: any) => void): void;
  removeListener(event: string, callback?: (data: any) => void): void;
  getCurrentState(): Promise<SpotifyPlayerState | null>;
  getVolume(): Promise<number>;
  setVolume(volume: number): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  togglePlay(): Promise<void>;
  seek(position: number): Promise<void>;
  previousTrack(): Promise<void>;
  nextTrack(): Promise<void>;
  activateElement(): Promise<void>;
}

interface SpotifySDK {
  Player: new (config: {
    name: string;
    getOAuthToken: (callback: (token: string) => void) => void;
    volume: number;
  }) => SpotifyPlayer;
}

declare global {
  interface Window {
    Spotify?: SpotifySDK;
    onSpotifyWebPlaybackSDKReady?: () => void;
  }
}

// Component props interface
interface SpotifyPlayerProps {
  token?: string;
  trackUris?: string[];
  currentTrack?: SpotifyTrack;
  className?: string;
  onPlaybackChange?: (event: {
    type: 'state_changed' | 'ready' | 'error' | 'token_changed';
    state?: SpotifyPlayerState;
    device_id?: string;
    error?: any;
    token?: string;
  }) => void;
}

// Player state enum
enum PlayerState {
  LOADING = 'loading',
  CONNECTING = 'connecting',
  READY = 'ready',
  ERROR = 'error',
  PREVIEW_MODE = 'preview_mode'
}

const SpotifyPlayer: React.FC<SpotifyPlayerProps> = ({
  token,
  trackUris = [],
  currentTrack,
  className = '',
  onPlaybackChange
}) => {
  // State management
  const [playerState, setPlayerState] = useState<PlayerState>(
    token ? PlayerState.LOADING : PlayerState.PREVIEW_MODE
  );
  const [currentPlayerState, setCurrentPlayerState] = useState<SpotifyPlayerState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isPreviewPlaying, setIsPreviewPlaying] = useState(false);
  const [previewError, setPreviewError] = useState<string>('');

  // Refs
  const playerRef = useRef<SpotifyPlayer | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const retryCountRef = useRef(0);
  const maxRetries = 3;

  // Event handlers refs for cleanup
  const eventHandlersRef = useRef<{
    ready?: (data: any) => void;
    not_ready?: (data: any) => void;
    player_state_changed?: (state: SpotifyPlayerState | null) => void;
    initialization_error?: (error: any) => void;
    authentication_error?: (error: any) => void;
    account_error?: (error: any) => void;
    playback_error?: (error: any) => void;
  }>({});

  // Load Spotify SDK script
  const loadSpotifySDK = useCallback(() => {
    if (document.querySelector('script[src="https://sdk.scdn.co/spotify-player.js"]')) {
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://sdk.scdn.co/spotify-player.js';
    script.async = true;

    script.addEventListener('load', () => {
      // Script loaded successfully
    });

    script.addEventListener('error', () => {
      setPlayerState(PlayerState.ERROR);
      setErrorMessage('Failed to load Spotify player');
      onPlaybackChange?.({
        type: 'error',
        error: { message: 'Failed to load Spotify player' }
      });
    });

    document.head.appendChild(script);
  }, [onPlaybackChange]);

  // Initialize Spotify player
  const initializePlayer = useCallback(async () => {
    if (!window.Spotify || !token) return;

    setPlayerState(PlayerState.CONNECTING);

    try {
      const player = new window.Spotify.Player({
        name: 'Lifeboard Player',
        getOAuthToken: (callback) => {
          callback(token);
        },
        volume: 0.5
      });

      // Set up event handlers
      eventHandlersRef.current.ready = (data: { device_id: string }) => {
        setPlayerState(PlayerState.READY);
        onPlaybackChange?.({
          type: 'ready',
          device_id: data.device_id
        });
      };

      eventHandlersRef.current.not_ready = () => {
        setPlayerState(PlayerState.ERROR);
        setErrorMessage('Player not ready');
      };

      eventHandlersRef.current.player_state_changed = (state: SpotifyPlayerState | null) => {
        setCurrentPlayerState(state);
        onPlaybackChange?.({
          type: 'state_changed',
          state: state || undefined
        });
      };

      eventHandlersRef.current.initialization_error = (error: any) => {
        setPlayerState(PlayerState.ERROR);
        setErrorMessage('Player initialization failed');
        onPlaybackChange?.({
          type: 'error',
          error
        });
      };

      eventHandlersRef.current.authentication_error = (error: any) => {
        setPlayerState(PlayerState.ERROR);
        setErrorMessage('Authentication failed');
        onPlaybackChange?.({
          type: 'error',
          error
        });
      };

      eventHandlersRef.current.account_error = (error: any) => {
        setPlayerState(PlayerState.ERROR);
        setErrorMessage('Account error');
        onPlaybackChange?.({
          type: 'error',
          error
        });
      };

      eventHandlersRef.current.playback_error = (error: any) => {
        setPlayerState(PlayerState.ERROR);
        setErrorMessage('Playback error');
        onPlaybackChange?.({
          type: 'error',
          error
        });
      };

      // Add event listeners
      Object.entries(eventHandlersRef.current).forEach(([event, handler]) => {
        if (handler) {
          player.addListener(event, handler);
        }
      });

      playerRef.current = player;

      // Connect to player
      const connected = await player.connect();
      
      if (!connected) {
        if (retryCountRef.current < maxRetries) {
          retryCountRef.current++;
          setTimeout(() => initializePlayer(), 1000);
        } else {
          setPlayerState(PlayerState.ERROR);
          setErrorMessage('Failed to connect to Spotify');
        }
      }
    } catch (error) {
      setPlayerState(PlayerState.ERROR);
      setErrorMessage('Failed to initialize player');
      onPlaybackChange?.({
        type: 'error',
        error
      });
    }
  }, [token, onPlaybackChange]);

  // Handle token changes
  useEffect(() => {
    if (token) {
      onPlaybackChange?.({
        type: 'token_changed',
        token
      });
    }
  }, [token, onPlaybackChange]);

  // Initialize SDK when component mounts
  useEffect(() => {
    if (!token) {
      setPlayerState(PlayerState.PREVIEW_MODE);
      return;
    }

    setPlayerState(PlayerState.LOADING);

    // Set up global callback
    window.onSpotifyWebPlaybackSDKReady = initializePlayer;

    // Load SDK if not already loaded
    if (window.Spotify) {
      initializePlayer();
    } else {
      loadSpotifySDK();
    }

    return () => {
      // Cleanup
      if (playerRef.current) {
        // Remove event listeners
        Object.entries(eventHandlersRef.current).forEach(([event, handler]) => {
          if (handler && playerRef.current) {
            playerRef.current.removeListener(event, handler);
          }
        });
        
        playerRef.current.disconnect();
        playerRef.current = null;
      }

      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
        previewAudioRef.current = null;
      }
    };
  }, [token, initializePlayer, loadSpotifySDK]);

  // Preview mode handlers
  const handlePreviewPlay = async () => {
    if (!currentTrack?.preview_url) return;

    try {
      setPreviewError('');
      
      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
      }

      const audio = new Audio(currentTrack.preview_url);
      previewAudioRef.current = audio;

      audio.addEventListener('ended', () => {
        setIsPreviewPlaying(false);
      });

      audio.addEventListener('pause', () => {
        setIsPreviewPlaying(false);
      });

      audio.addEventListener('play', () => {
        setIsPreviewPlaying(true);
      });

      await audio.play();
    } catch (error) {
      setPreviewError('Preview playback failed');
      setIsPreviewPlaying(false);
    }
  };

  const handlePreviewPause = () => {
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
    }
    setIsPreviewPlaying(false);
  };

  // Control handlers
  const handleTogglePlay = async () => {
    if (playerRef.current) {
      await playerRef.current.togglePlay();
    }
  };

  const handlePreviousTrack = async () => {
    if (playerRef.current) {
      await playerRef.current.previousTrack();
    }
  };

  const handleNextTrack = async () => {
    if (playerRef.current) {
      await playerRef.current.nextTrack();
    }
  };

  // Keyboard event handlers
  const handleKeyDown = (event: React.KeyboardEvent, action: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  const handleArrowNavigation = (event: React.KeyboardEvent) => {
    const buttons = Array.from(
      event.currentTarget.querySelectorAll('button:not(:disabled)')
    ) as HTMLButtonElement[];
    
    const currentIndex = buttons.findIndex(button => button === event.target);
    
    if (event.key === 'ArrowRight' && currentIndex < buttons.length - 1) {
      event.preventDefault();
      buttons[currentIndex + 1].focus();
    } else if (event.key === 'ArrowLeft' && currentIndex > 0) {
      event.preventDefault();
      buttons[currentIndex - 1].focus();
    }
  };

  // Render helpers
  const renderLoadingState = () => (
    <div className="flex items-center justify-center p-4">
      <div role="progressbar" className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-500"></div>
      <span className="ml-2">Loading player...</span>
    </div>
  );

  const renderConnectingState = () => (
    <div className="flex items-center justify-center p-4">
      <div className="animate-pulse">Connecting to Spotify...</div>
    </div>
  );

  const renderErrorState = () => (
    <div className="flex items-center justify-center p-4 text-red-500">
      <span>{errorMessage}</span>
    </div>
  );

  const renderPreviewMode = () => {
    if (trackUris.length === 0) {
      return (
        <div className="flex items-center justify-center p-4">
          <span>No tracks available</span>
        </div>
      );
    }

    if (!currentTrack) {
      return (
        <div className="flex items-center justify-center p-4">
          <span>Preview mode</span>
        </div>
      );
    }

    if (!currentTrack.preview_url) {
      return (
        <div className="flex items-center justify-center p-4">
          <span>No preview available</span>
        </div>
      );
    }

    return (
      <div className="p-4">
        <div className="text-center mb-4">
          <span className="text-sm text-gray-500">Preview mode</span>
        </div>
        
        {previewError && (
          <div className="text-red-500 text-center mb-2">{previewError}</div>
        )}
        
        <div className="flex items-center justify-center">
          <button
            onClick={isPreviewPlaying ? handlePreviewPause : handlePreviewPlay}
            aria-label={isPreviewPlaying ? 'Pause preview' : 'Play preview'}
            className="bg-green-500 hover:bg-green-600 text-white rounded-full p-3"
          >
            {isPreviewPlaying ? '⏸️' : '▶️'}
          </button>
        </div>
      </div>
    );
  };

  const renderPlayerControls = () => {
    const hasTrack = currentPlayerState?.track_window?.current_track;
    const isPlaying = !currentPlayerState?.paused;

    return (
      <div className="p-4">
        <div className="text-center mb-4">
          <span className="text-sm text-green-500">Player ready</span>
        </div>

        {/* Track info */}
        {hasTrack && (
          <div className="text-center mb-4">
            <div className="font-semibold">{currentPlayerState.track_window.current_track.name}</div>
            <div className="text-sm text-gray-600">
              {currentPlayerState.track_window.current_track.artists[0]?.name}
            </div>
            <div className="text-xs text-gray-500">
              {currentPlayerState.track_window.current_track.album.name}
            </div>
          </div>
        )}

        {/* Controls */}
        <div 
          role="group" 
          aria-label="Playback controls"
          className="flex items-center justify-center space-x-4"
          onKeyDown={handleArrowNavigation}
        >
          <button
            onClick={handlePreviousTrack}
            onKeyDown={(e) => handleKeyDown(e, handlePreviousTrack)}
            disabled={!hasTrack}
            aria-label="Previous track"
            className="bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed rounded-full p-2"
          >
            ⏮️
          </button>

          <button
            onClick={handleTogglePlay}
            onKeyDown={(e) => handleKeyDown(e, handleTogglePlay)}
            disabled={!hasTrack}
            aria-label={isPlaying ? 'Pause' : 'Play'}
            className="bg-green-500 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-full p-3"
          >
            {isPlaying ? '⏸️' : '▶️'}
          </button>

          <button
            onClick={handleNextTrack}
            onKeyDown={(e) => handleKeyDown(e, handleNextTrack)}
            disabled={!hasTrack}
            aria-label="Next track"
            className="bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed rounded-full p-2"
          >
            ⏭️
          </button>
        </div>

        {/* Status announcements for screen readers */}
        {hasTrack && (
          <div role="status" className="sr-only">
            {isPlaying 
              ? `Now playing: ${currentPlayerState.track_window.current_track.name}`
              : `Paused: ${currentPlayerState.track_window.current_track.name}`
            }
          </div>
        )}
      </div>
    );
  };

  const renderContent = () => {
    if (playerState === PlayerState.PREVIEW_MODE) {
      return renderPreviewMode();
    }

    switch (playerState) {
      case PlayerState.LOADING:
        return renderLoadingState();
      case PlayerState.CONNECTING:
        return renderConnectingState();
      case PlayerState.ERROR:
        return renderErrorState();
      case PlayerState.READY:
        return renderPlayerControls();
      default:
        return renderLoadingState();
    }
  };

  return (
    <div 
      role="region" 
      aria-label="Spotify player"
      className={`spotify-player border rounded-lg bg-white shadow-sm ${className}`}
    >
      {renderContent()}
    </div>
  );
};

export default SpotifyPlayer;