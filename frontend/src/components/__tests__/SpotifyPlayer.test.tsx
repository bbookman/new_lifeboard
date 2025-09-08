import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SpotifyPlayer from '../SpotifyPlayer';

// Mock the Spotify Web Playback SDK
const mockPlayer = {
  connect: jest.fn(),
  disconnect: jest.fn(),
  addListener: jest.fn(),
  removeListener: jest.fn(),
  getCurrentState: jest.fn(),
  getVolume: jest.fn(),
  setVolume: jest.fn(),
  pause: jest.fn(),
  resume: jest.fn(),
  togglePlay: jest.fn(),
  seek: jest.fn(),
  previousTrack: jest.fn(),
  nextTrack: jest.fn(),
  activateElement: jest.fn(),
};

const mockSpotify = {
  Player: jest.fn().mockImplementation(() => mockPlayer),
};

// Mock the global Spotify object
Object.defineProperty(window, 'Spotify', {
  value: mockSpotify,
  writable: true,
});

// Mock the onSpotifyWebPlaybackSDKReady callback
Object.defineProperty(window, 'onSpotifyWebPlaybackSDKReady', {
  value: jest.fn(),
  writable: true,
});

// Mock HTML5 Audio for preview mode
const mockAudio = {
  play: jest.fn().mockResolvedValue(undefined),
  pause: jest.fn(),
  load: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  currentTime: 0,
  duration: 30,
  paused: true,
  volume: 1,
  src: '',
};

Object.defineProperty(window, 'Audio', {
  value: jest.fn().mockImplementation(() => mockAudio),
  writable: true,
});

// Mock script loading
const mockScriptElement = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  src: '',
  async: false,
};

const originalCreateElement = document.createElement;
document.createElement = jest.fn().mockImplementation((tagName) => {
  if (tagName === 'script') {
    return mockScriptElement;
  }
  return originalCreateElement.call(document, tagName);
});

const mockAppendChild = jest.fn();
document.head.appendChild = mockAppendChild;

describe('SpotifyPlayer', () => {
  const defaultProps = {
    token: 'mock-access-token',
    trackUris: ['spotify:track:123', 'spotify:track:456'],
    onPlaybackChange: jest.fn(),
  };

  const mockTrack = {
    id: '123',
    name: 'Test Song',
    artists: [{ name: 'Test Artist' }],
    album: { name: 'Test Album', images: [{ url: 'test-image.jpg' }] },
    preview_url: 'https://example.com/preview.mp3',
    duration_ms: 180000,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockPlayer.getCurrentState.mockResolvedValue(null);
    mockPlayer.connect.mockResolvedValue(true);
    mockAudio.paused = true;
    mockAudio.currentTime = 0;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders with default props', () => {
      render(<SpotifyPlayer {...defaultProps} />);
      expect(screen.getByRole('region', { name: /spotify player/i })).toBeInTheDocument();
    });

    it('renders loading state initially', () => {
      render(<SpotifyPlayer {...defaultProps} />);
      expect(screen.getByText(/loading player/i)).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      render(<SpotifyPlayer {...defaultProps} className="custom-player" />);
      const player = screen.getByRole('region', { name: /spotify player/i });
      expect(player).toHaveClass('custom-player');
    });

    it('renders without token (preview mode only)', () => {
      render(<SpotifyPlayer {...defaultProps} token={undefined} />);
      expect(screen.getByText(/preview mode/i)).toBeInTheDocument();
    });

    it('renders with empty track list', () => {
      render(<SpotifyPlayer {...defaultProps} trackUris={[]} />);
      expect(screen.getByText(/no tracks available/i)).toBeInTheDocument();
    });

    it('renders with current track information', async () => {
      const mockState = {
        track_window: {
          current_track: mockTrack,
        },
        paused: false,
        position: 30000,
        duration: 180000,
      };

      mockPlayer.getCurrentState.mockResolvedValue(mockState);

      render(<SpotifyPlayer {...defaultProps} />);

      // Simulate SDK ready
      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      await waitFor(() => {
        expect(screen.getByText('Test Song')).toBeInTheDocument();
        expect(screen.getByText('Test Artist')).toBeInTheDocument();
        expect(screen.getByText('Test Album')).toBeInTheDocument();
      });
    });
  });

  describe('SDK Initialization', () => {
    it('loads Spotify SDK script on mount', () => {
      render(<SpotifyPlayer {...defaultProps} />);

      expect(document.createElement).toHaveBeenCalledWith('script');
      expect(mockScriptElement.src).toBe('https://sdk.scdn.co/spotify-player.js');
      expect(mockScriptElement.async).toBe(true);
      expect(mockAppendChild).toHaveBeenCalledWith(mockScriptElement);
    });

    it('initializes player when SDK is ready', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      await waitFor(() => {
        expect(mockSpotify.Player).toHaveBeenCalledWith({
          name: 'Lifeboard Player',
          getOAuthToken: expect.any(Function),
          volume: 0.5,
        });
      });
    });

    it('handles SDK script load error', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      // Simulate script error
      act(() => {
        const errorHandler = mockScriptElement.addEventListener.mock.calls.find(
          call => call[0] === 'error'
        )?.[1];
        errorHandler?.();
      });

      await waitFor(() => {
        expect(screen.getByText(/failed to load spotify player/i)).toBeInTheDocument();
      });
    });

    it('handles player connection failure', async () => {
      mockPlayer.connect.mockResolvedValue(false);

      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      await waitFor(() => {
        expect(screen.getByText(/failed to connect to spotify/i)).toBeInTheDocument();
      });
    });

    it('sets up player event listeners', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      await waitFor(() => {
        expect(mockPlayer.addListener).toHaveBeenCalledWith('ready', expect.any(Function));
        expect(mockPlayer.addListener).toHaveBeenCalledWith('not_ready', expect.any(Function));
        expect(mockPlayer.addListener).toHaveBeenCalledWith('player_state_changed', expect.any(Function));
        expect(mockPlayer.addListener).toHaveBeenCalledWith('initialization_error', expect.any(Function));
        expect(mockPlayer.addListener).toHaveBeenCalledWith('authentication_error', expect.any(Function));
        expect(mockPlayer.addListener).toHaveBeenCalledWith('account_error', expect.any(Function));
        expect(mockPlayer.addListener).toHaveBeenCalledWith('playback_error', expect.any(Function));
      });
    });
  });

  describe('Loading States', () => {
    it('shows loading state while SDK loads', () => {
      render(<SpotifyPlayer {...defaultProps} />);
      expect(screen.getByText(/loading player/i)).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('shows connecting state during player initialization', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      expect(screen.getByText(/connecting to spotify/i)).toBeInTheDocument();
    });

    it('shows ready state when player is connected', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      // Simulate ready event
      const readyHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'ready'
      )?.[1];

      act(() => {
        readyHandler?.({ device_id: 'test-device-id' });
      });

      await waitFor(() => {
        expect(screen.getByText(/player ready/i)).toBeInTheDocument();
      });
    });
  });

  describe('Play/Pause/Skip Controls', () => {
    beforeEach(async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      // Simulate ready state
      const readyHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'ready'
      )?.[1];

      act(() => {
        readyHandler?.({ device_id: 'test-device-id' });
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      });
    });

    it('renders play button when paused', async () => {
      const mockState = {
        track_window: { current_track: mockTrack },
        paused: true,
      };

      mockPlayer.getCurrentState.mockResolvedValue(mockState);

      const stateHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'player_state_changed'
      )?.[1];

      act(() => {
        stateHandler?.(mockState);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      });
    });

    it('renders pause button when playing', async () => {
      const mockState = {
        track_window: { current_track: mockTrack },
        paused: false,
      };

      mockPlayer.getCurrentState.mockResolvedValue(mockState);

      const stateHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'player_state_changed'
      )?.[1];

      act(() => {
        stateHandler?.(mockState);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
      });
    });

    it('calls togglePlay when play/pause button is clicked', async () => {
      const user = userEvent.setup();
      const playButton = screen.getByRole('button', { name: /play/i });

      await user.click(playButton);

      expect(mockPlayer.togglePlay).toHaveBeenCalled();
    });

    it('calls previousTrack when previous button is clicked', async () => {
      const user = userEvent.setup();
      const prevButton = screen.getByRole('button', { name: /previous/i });

      await user.click(prevButton);

      expect(mockPlayer.previousTrack).toHaveBeenCalled();
    });

    it('calls nextTrack when next button is clicked', async () => {
      const user = userEvent.setup();
      const nextButton = screen.getByRole('button', { name: /next/i });

      await user.click(nextButton);

      expect(mockPlayer.nextTrack).toHaveBeenCalled();
    });

    it('disables controls when no track is loaded', async () => {
      mockPlayer.getCurrentState.mockResolvedValue(null);

      const stateHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'player_state_changed'
      )?.[1];

      act(() => {
        stateHandler?.(null);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeDisabled();
        expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
        expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
      });
    });
  });

  describe('Preview Mode vs Full SDK Mode', () => {
    it('uses preview mode when no token provided', () => {
      render(<SpotifyPlayer {...defaultProps} token={undefined} />);
      expect(screen.getByText(/preview mode/i)).toBeInTheDocument();
      expect(document.createElement).not.toHaveBeenCalledWith('script');
    });

    it('uses full SDK mode when token provided', () => {
      render(<SpotifyPlayer {...defaultProps} />);
      expect(document.createElement).toHaveBeenCalledWith('script');
    });

    it('plays preview audio in preview mode', async () => {
      const user = userEvent.setup();
      const trackWithPreview = {
        ...mockTrack,
        preview_url: 'https://example.com/preview.mp3',
      };

      render(
        <SpotifyPlayer
          {...defaultProps}
          token={undefined}
          currentTrack={trackWithPreview}
        />
      );

      const playButton = screen.getByRole('button', { name: /play preview/i });
      await user.click(playButton);

      expect(window.Audio).toHaveBeenCalledWith('https://example.com/preview.mp3');
      expect(mockAudio.play).toHaveBeenCalled();
    });

    it('shows no preview available when track has no preview_url', () => {
      const trackWithoutPreview = {
        ...mockTrack,
        preview_url: null,
      };

      render(
        <SpotifyPlayer
          {...defaultProps}
          token={undefined}
          currentTrack={trackWithoutPreview}
        />
      );

      expect(screen.getByText(/no preview available/i)).toBeInTheDocument();
    });

    it('handles preview audio play error', async () => {
      const user = userEvent.setup();
      mockAudio.play.mockRejectedValue(new Error('Audio play failed'));

      render(
        <SpotifyPlayer
          {...defaultProps}
          token={undefined}
          currentTrack={mockTrack}
        />
      );

      const playButton = screen.getByRole('button', { name: /play preview/i });
      await user.click(playButton);

      await waitFor(() => {
        expect(screen.getByText(/preview playback failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('handles SDK initialization error', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const errorHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'initialization_error'
      )?.[1];

      act(() => {
        errorHandler?.({ message: 'Initialization failed' });
      });

      await waitFor(() => {
        expect(screen.getByText(/player initialization failed/i)).toBeInTheDocument();
      });
    });

    it('handles authentication error', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const errorHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'authentication_error'
      )?.[1];

      act(() => {
        errorHandler?.({ message: 'Authentication failed' });
      });

      await waitFor(() => {
        expect(screen.getByText(/authentication failed/i)).toBeInTheDocument();
      });
    });

    it('handles account error', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const errorHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'account_error'
      )?.[1];

      act(() => {
        errorHandler?.({ message: 'Account error' });
      });

      await waitFor(() => {
        expect(screen.getByText(/account error/i)).toBeInTheDocument();
      });
    });

    it('handles playback error', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const errorHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'playback_error'
      )?.[1];

      act(() => {
        errorHandler?.({ message: 'Playback error' });
      });

      await waitFor(() => {
        expect(screen.getByText(/playback error/i)).toBeInTheDocument();
      });
    });

    it('retries connection on failure', async () => {
      mockPlayer.connect
        .mockResolvedValueOnce(false)
        .mockResolvedValueOnce(true);

      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      await waitFor(() => {
        expect(mockPlayer.connect).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Token Management', () => {
    it('provides token to player via getOAuthToken callback', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const playerConfig = mockSpotify.Player.mock.calls[0][0];
      const getOAuthToken = playerConfig.getOAuthToken;

      const mockCallback = jest.fn();
      getOAuthToken(mockCallback);

      expect(mockCallback).toHaveBeenCalledWith(defaultProps.token);
    });

    it('handles token expiration', async () => {
      const { rerender } = render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      // Simulate token expiration by changing token
      rerender(<SpotifyPlayer {...defaultProps} token="new-token" />);

      const playerConfig = mockSpotify.Player.mock.calls[0][0];
      const getOAuthToken = playerConfig.getOAuthToken;

      const mockCallback = jest.fn();
      getOAuthToken(mockCallback);

      expect(mockCallback).toHaveBeenCalledWith("new-token");
    });

    it('handles missing token gracefully', async () => {
      render(<SpotifyPlayer {...defaultProps} token={undefined} />);

      // Should not attempt to initialize SDK
      expect(document.createElement).not.toHaveBeenCalledWith('script');
      expect(screen.getByText(/preview mode/i)).toBeInTheDocument();
    });

    it('calls onPlaybackChange when token changes', () => {
      const { rerender } = render(<SpotifyPlayer {...defaultProps} />);

      rerender(<SpotifyPlayer {...defaultProps} token="new-token" />);

      expect(defaultProps.onPlaybackChange).toHaveBeenCalledWith({
        type: 'token_changed',
        token: 'new-token',
      });
    });
  });

  describe('Accessibility and Keyboard Controls', () => {
    beforeEach(async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const readyHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'ready'
      )?.[1];

      act(() => {
        readyHandler?.({ device_id: 'test-device-id' });
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      });
    });

    it('has proper ARIA labels on controls', () => {
      expect(screen.getByRole('button', { name: /play/i })).toHaveAttribute('aria-label');
      expect(screen.getByRole('button', { name: /previous/i })).toHaveAttribute('aria-label');
      expect(screen.getByRole('button', { name: /next/i })).toHaveAttribute('aria-label');
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      const playButton = screen.getByRole('button', { name: /play/i });

      playButton.focus();
      expect(playButton).toHaveFocus();

      await user.keyboard('{Enter}');
      expect(mockPlayer.togglePlay).toHaveBeenCalled();

      await user.keyboard('{Space}');
      expect(mockPlayer.togglePlay).toHaveBeenCalledTimes(2);
    });

    it('supports arrow key navigation between controls', async () => {
      const user = userEvent.setup();
      const playButton = screen.getByRole('button', { name: /play/i });
      const nextButton = screen.getByRole('button', { name: /next/i });
      const prevButton = screen.getByRole('button', { name: /previous/i });

      playButton.focus();
      
      await user.keyboard('{ArrowRight}');
      expect(nextButton).toHaveFocus();

      await user.keyboard('{ArrowLeft}');
      expect(playButton).toHaveFocus();

      await user.keyboard('{ArrowLeft}');
      expect(prevButton).toHaveFocus();
    });

    it('has proper focus management', async () => {
      const user = userEvent.setup();
      const playButton = screen.getByRole('button', { name: /play/i });

      await user.tab();
      expect(playButton).toHaveFocus();
    });

    it('announces state changes to screen readers', async () => {
      const mockState = {
        track_window: { current_track: mockTrack },
        paused: false,
      };

      const stateHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'player_state_changed'
      )?.[1];

      act(() => {
        stateHandler?.(mockState);
      });

      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(/now playing: test song/i);
      });
    });

    it('has proper semantic structure', () => {
      expect(screen.getByRole('region', { name: /spotify player/i })).toBeInTheDocument();
      expect(screen.getByRole('group', { name: /playback controls/i })).toBeInTheDocument();
    });
  });

  describe('Cleanup', () => {
    it('disconnects player on unmount', () => {
      const { unmount } = render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      unmount();

      expect(mockPlayer.disconnect).toHaveBeenCalled();
    });

    it('removes event listeners on unmount', () => {
      const { unmount } = render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      unmount();

      expect(mockPlayer.removeListener).toHaveBeenCalledWith('ready', expect.any(Function));
      expect(mockPlayer.removeListener).toHaveBeenCalledWith('not_ready', expect.any(Function));
      expect(mockPlayer.removeListener).toHaveBeenCalledWith('player_state_changed', expect.any(Function));
    });

    it('pauses preview audio on unmount', () => {
      const { unmount } = render(
        <SpotifyPlayer
          {...defaultProps}
          token={undefined}
          currentTrack={mockTrack}
        />
      );

      unmount();

      expect(mockAudio.pause).toHaveBeenCalled();
    });
  });

  describe('Callback Integration', () => {
    it('calls onPlaybackChange when playback state changes', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const mockState = {
        track_window: { current_track: mockTrack },
        paused: false,
        position: 30000,
        duration: 180000,
      };

      const stateHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'player_state_changed'
      )?.[1];

      act(() => {
        stateHandler?.(mockState);
      });

      expect(defaultProps.onPlaybackChange).toHaveBeenCalledWith({
        type: 'state_changed',
        state: mockState,
      });
    });

    it('calls onPlaybackChange when player is ready', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const readyHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'ready'
      )?.[1];

      act(() => {
        readyHandler?.({ device_id: 'test-device-id' });
      });

      expect(defaultProps.onPlaybackChange).toHaveBeenCalledWith({
        type: 'ready',
        device_id: 'test-device-id',
      });
    });

    it('calls onPlaybackChange on errors', async () => {
      render(<SpotifyPlayer {...defaultProps} />);

      act(() => {
        window.onSpotifyWebPlaybackSDKReady();
      });

      const errorHandler = mockPlayer.addListener.mock.calls.find(
        call => call[0] === 'playback_error'
      )?.[1];

      const error = { message: 'Playback error' };

      act(() => {
        errorHandler?.(error);
      });

      expect(defaultProps.onPlaybackChange).toHaveBeenCalledWith({
        type: 'error',
        error,
      });
    });
  });
});