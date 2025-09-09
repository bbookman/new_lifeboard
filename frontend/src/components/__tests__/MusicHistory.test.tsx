import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MusicHistory } from '../MusicHistory';
import { useSpotifyTracks } from '../../hooks/useSpotifyData';
import { SpotifyTrack } from '../../lib/api';

// Mock the useSpotifyTracks hook
jest.mock('../../hooks/useSpotifyData');
const mockUseSpotifyTracks = useSpotifyTracks as jest.MockedFunction<typeof useSpotifyTracks>;

// Mock the SpotifyPlayer component
jest.mock('../SpotifyPlayer', () => {
  return function MockSpotifyPlayer({ currentTrack, className }: any) {
    return (
      <div data-testid="spotify-player" className={className}>
        <div data-testid="player-track-id">{currentTrack?.id}</div>
        <div data-testid="player-track-name">{currentTrack?.name}</div>
        <button data-testid="play-button">Play</button>
      </div>
    );
  };
});

// Mock the music image import
jest.mock('@/assets/music-placeholder.jpg', () => 'mocked-music-image.jpg');

// Sample Spotify track data for testing
const mockSpotifyTracks: SpotifyTrack[] = [
  {
    id: 'track1',
    name: 'Test Song 1',
    artists: [{ id: 'artist1', name: 'Test Artist 1', external_urls: {} }],
    album: {
      id: 'album1',
      name: 'Test Album 1',
      artists: [{ id: 'artist1', name: 'Test Artist 1', external_urls: {} }],
      images: [],
      external_urls: {},
      release_date: '2024-01-01',
      release_date_precision: 'day',
      total_tracks: 10,
      album_type: 'album'
    },
    duration_ms: 180000, // 3 minutes
    popularity: 80,
    explicit: false,
    preview_url: 'https://example.com/preview1.mp3',
    external_urls: {
      spotify: 'https://open.spotify.com/track/track1'
    },
    external_ids: {},
    available_markets: ['US'],
    disc_number: 1,
    track_number: 1,
    is_local: false,
    played_at: '2024-01-15T10:30:00Z',
    audio_features: {
      danceability: 0.8,
      energy: 0.9,
      key: 5,
      loudness: -5.0,
      mode: 1,
      speechiness: 0.1,
      acousticness: 0.1,
      instrumentalness: 0.0,
      liveness: 0.2,
      valence: 0.7,
      tempo: 120,
      duration_ms: 180000,
      time_signature: 4
    }
  },
  {
    id: 'track2',
    name: 'Test Song 2',
    artists: [{ id: 'artist2', name: 'Test Artist 2', external_urls: {} }],
    album: {
      id: 'album2',
      name: 'Test Album 2',
      artists: [{ id: 'artist2', name: 'Test Artist 2', external_urls: {} }],
      images: [],
      external_urls: {},
      release_date: '2024-01-01',
      release_date_precision: 'day',
      total_tracks: 10,
      album_type: 'album'
    },
    duration_ms: 240000, // 4 minutes
    popularity: 75,
    explicit: false,
    preview_url: null,
    external_urls: {
      spotify: 'https://open.spotify.com/track/track2'
    },
    external_ids: {},
    available_markets: ['US'],
    disc_number: 1,
    track_number: 2,
    is_local: false,
    played_at: '2024-01-15T08:15:00Z',
    audio_features: {
      danceability: 0.3,
      energy: 0.2,
      key: 2,
      loudness: -10.0,
      mode: 0,
      speechiness: 0.05,
      acousticness: 0.8,
      instrumentalness: 0.5,
      liveness: 0.1,
      valence: 0.3,
      tempo: 80,
      duration_ms: 240000,
      time_signature: 4
    }
  },
  {
    id: 'track3',
    name: 'Test Song 3',
    artists: [{ id: 'artist3', name: 'Test Artist 3', external_urls: {} }],
    album: {
      id: 'album3',
      name: 'Test Album 3',
      artists: [{ id: 'artist3', name: 'Test Artist 3', external_urls: {} }],
      images: [],
      external_urls: {},
      release_date: '2024-01-01',
      release_date_precision: 'day',
      total_tracks: 10,
      album_type: 'album'
    },
    duration_ms: 210000, // 3.5 minutes
    popularity: 70,
    explicit: false,
    external_urls: {
      spotify: 'https://open.spotify.com/track/track3'
    },
    external_ids: {},
    available_markets: ['US'],
    disc_number: 1,
    track_number: 3,
    is_local: false,
    played_at: '2024-01-15T06:45:00Z'
    // No audio_features to test fallback
  }
];

// Helper function to create a test wrapper with React Query
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('MusicHistory Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock current time for consistent relative time calculations
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Integration with useSpotifyTracks hook', () => {
    it('should call useSpotifyTracks with selectedDate prop', () => {
      const selectedDate = '2024-01-15';
      mockUseSpotifyTracks.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory selectedDate={selectedDate} />, {
        wrapper: createTestWrapper(),
      });

      expect(mockUseSpotifyTracks).toHaveBeenCalledWith(selectedDate);
    });

    it('should call useSpotifyTracks with undefined when no selectedDate provided', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(mockUseSpotifyTracks).toHaveBeenCalledWith(undefined);
    });

    it('should re-fetch data when selectedDate prop changes', () => {
      const { rerender } = render(<MusicHistory selectedDate="2024-01-15" />, {
        wrapper: createTestWrapper(),
      });

      mockUseSpotifyTracks.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      rerender(<MusicHistory selectedDate="2024-01-16" />);

      expect(mockUseSpotifyTracks).toHaveBeenCalledWith('2024-01-16');
    });
  });

  describe('Loading state', () => {
    it('should display loading spinner and message when data is loading', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory selectedDate="2024-01-15" />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('Loading your music history...')).toBeInTheDocument();
      expect(screen.getByText('Music Journal')).toBeInTheDocument();
      expect(screen.getByText(/Your daily soundtrack and listening history • 2024-01-15/)).toBeInTheDocument();
      
      // Check for loading spinner
      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('should display loading state without selectedDate in subtitle', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('Loading your music history...')).toBeInTheDocument();
      expect(screen.getByText('Your daily soundtrack and listening history')).toBeInTheDocument();
      expect(screen.queryByText(/•/)).not.toBeInTheDocument();
    });
  });

  describe('Error state', () => {
    it('should display error message when data fetching fails', () => {
      const errorMessage = 'Failed to fetch Spotify data';
      mockUseSpotifyTracks.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error(errorMessage),
        isError: true,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory selectedDate="2024-01-15" />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText(`Failed to load music history: ${errorMessage}`)).toBeInTheDocument();
      expect(screen.getByText('⚠️')).toBeInTheDocument();
      expect(screen.getByText('Music Journal')).toBeInTheDocument();
    });

    it('should handle error without message', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: { message: undefined },
        isError: true,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('Failed to load music history: undefined')).toBeInTheDocument();
    });
  });

  describe('Empty state', () => {
    it('should display empty state when no tracks are available', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory selectedDate="2024-01-15" />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('No music history found')).toBeInTheDocument();
      expect(screen.getByText('No tracks were played on 2024-01-15')).toBeInTheDocument();
      expect(screen.getByText('🎵')).toBeInTheDocument();
    });

    it('should display empty state without selectedDate', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('No music history found')).toBeInTheDocument();
      expect(screen.getByText('No recent tracks found')).toBeInTheDocument();
    });

    it('should display empty state when data is null', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('No music history found')).toBeInTheDocument();
    });
  });

  describe('Real data display', () => {
    beforeEach(() => {
      mockUseSpotifyTracks.mockReturnValue({
        data: mockSpotifyTracks,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);
    });

    it('should display track information correctly', () => {
      render(<MusicHistory selectedDate="2024-01-15" />, {
        wrapper: createTestWrapper(),
      });

      // Check that all tracks are displayed
      expect(screen.getByText('Test Song 1')).toBeInTheDocument();
      expect(screen.getByText('Test Artist 1 • Test Album 1')).toBeInTheDocument();
      expect(screen.getByText('Test Song 2')).toBeInTheDocument();
      expect(screen.getByText('Test Artist 2 • Test Album 2')).toBeInTheDocument();
      expect(screen.getByText('Test Song 3')).toBeInTheDocument();
      expect(screen.getByText('Test Artist 3 • Test Album 3')).toBeInTheDocument();
    });

    it('should display formatted duration correctly', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('3:00')).toBeInTheDocument(); // 180000ms = 3:00
      expect(screen.getByText('4:00')).toBeInTheDocument(); // 240000ms = 4:00
      expect(screen.getByText('3:30')).toBeInTheDocument(); // 210000ms = 3:30
    });

    it('should display relative play time correctly', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Based on mocked current time of 12:00:00Z
      expect(screen.getByText('1 hour ago')).toBeInTheDocument(); // 10:30 -> 1.5 hours ago, rounded down
      expect(screen.getByText('3 hours ago')).toBeInTheDocument(); // 08:15 -> 3.75 hours ago, rounded down
      expect(screen.getByText('5 hours ago')).toBeInTheDocument(); // 06:45 -> 5.25 hours ago, rounded down
    });

    it('should display mood badges based on audio features', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Track 1: high valence (0.7) + high energy (0.9) = Energetic
      expect(screen.getByText('Energetic')).toBeInTheDocument();
      
      // Track 2: low valence (0.3) + low energy (0.2) = Chill
      expect(screen.getByText('Chill')).toBeInTheDocument();
      
      // Track 3: no audio features = Unknown
      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    it('should display listening stats correctly', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // 3 tracks, total duration: 180000 + 240000 + 210000 = 630000ms = 10.5 minutes
      expect(screen.getByText('3 tracks • 10 minutes • Mostly energetic vibes')).toBeInTheDocument();
      expect(screen.getByText("Today's Listening Stats")).toBeInTheDocument();
    });

    it('should handle singular track count correctly', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: [mockSpotifyTracks[0]],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('1 track • 3 minutes • Mostly energetic vibes')).toBeInTheDocument();
    });
  });

  describe('SpotifyPlayer integration', () => {
    beforeEach(() => {
      mockUseSpotifyTracks.mockReturnValue({
        data: mockSpotifyTracks,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);
    });

    it('should render SpotifyPlayer component for each track', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      const players = screen.getAllByTestId('spotify-player');
      expect(players).toHaveLength(3);
    });

    it('should pass correct track data to SpotifyPlayer components', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Check that track IDs are passed correctly
      expect(screen.getByTestId('player-track-id')).toHaveTextContent('track1');
      expect(screen.getByTestId('player-track-name')).toHaveTextContent('Test Song 1');
      
      // Check that all play buttons are rendered
      const playButtons = screen.getAllByTestId('play-button');
      expect(playButtons).toHaveLength(3);
    });

    it('should apply correct className to SpotifyPlayer', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      const players = screen.getAllByTestId('spotify-player');
      players.forEach(player => {
        expect(player).toHaveClass('border-t', 'pt-3');
      });
    });

    it('should handle tracks without preview_url', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Track 2 has preview_url: null, should still render player
      const players = screen.getAllByTestId('spotify-player');
      expect(players).toHaveLength(3);
    });
  });

  describe('Mock data removal verification', () => {
    it('should not display any sample/mock track data', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Ensure old mock data is not present
      expect(screen.queryByText('Midnight Reflections')).not.toBeInTheDocument();
      expect(screen.queryByText('The Velvet Underground')).not.toBeInTheDocument();
      expect(screen.queryByText('Electric Dreams')).not.toBeInTheDocument();
      expect(screen.queryByText('Synthwave Collective')).not.toBeInTheDocument();
      expect(screen.queryByText('Ocean Waves')).not.toBeInTheDocument();
      expect(screen.queryByText('Ambient Nature')).not.toBeInTheDocument();
      expect(screen.queryByText('City Lights')).not.toBeInTheDocument();
      expect(screen.queryByText('Jazz Fusion')).not.toBeInTheDocument();
    });

    it('should not display hardcoded stats when using real data', () => {
      mockUseSpotifyTracks.mockReturnValue({
        data: mockSpotifyTracks,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Should not show old hardcoded stats
      expect(screen.queryByText('4 tracks • 19 minutes • Mostly chill vibes')).not.toBeInTheDocument();
    });
  });

  describe('Edge cases and error handling', () => {
    it('should handle tracks with missing audio features gracefully', () => {
      const tracksWithMissingFeatures = [
        {
          ...mockSpotifyTracks[0],
          audio_features: undefined
        }
      ];

      mockUseSpotifyTracks.mockReturnValue({
        data: tracksWithMissingFeatures,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    it('should handle tracks with partial audio features', () => {
      const tracksWithPartialFeatures = [
        {
          ...mockSpotifyTracks[0],
          audio_features: {
            valence: 0.5,
            energy: 0.5,
            danceability: 0.5,
            tempo: 120,
            acousticness: 0.5,
            instrumentalness: 0.5,
            liveness: 0.5,
            speechiness: 0.5
          }
        }
      ];

      mockUseSpotifyTracks.mockReturnValue({
        data: tracksWithPartialFeatures,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Should default to 'Smooth' for middle-range values
      expect(screen.getByText('Smooth')).toBeInTheDocument();
    });

    it('should handle very recent play times', () => {
      const recentTrack = {
        ...mockSpotifyTracks[0],
        played_at: '2024-01-15T11:59:30Z' // 30 seconds ago
      };

      mockUseSpotifyTracks.mockReturnValue({
        data: [recentTrack],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('should handle tracks with zero duration', () => {
      const zeroLengthTrack = {
        ...mockSpotifyTracks[0],
        duration_ms: 0
      };

      mockUseSpotifyTracks.mockReturnValue({
        data: [zeroLengthTrack],
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByText('0:00')).toBeInTheDocument();
    });

    it('should generate unique keys for tracks with same ID but different play times', () => {
      const duplicateIdTracks = [
        {
          ...mockSpotifyTracks[0],
          played_at: '2024-01-15T10:30:00Z'
        },
        {
          ...mockSpotifyTracks[0],
          played_at: '2024-01-15T08:30:00Z'
        }
      ];

      mockUseSpotifyTracks.mockReturnValue({
        data: duplicateIdTracks,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);

      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Should render both tracks without React key warnings
      const trackElements = screen.getAllByText('Test Song 1');
      expect(trackElements).toHaveLength(2);
    });
  });

  describe('Accessibility and UI elements', () => {
    beforeEach(() => {
      mockUseSpotifyTracks.mockReturnValue({
        data: mockSpotifyTracks,
        isLoading: false,
        error: null,
        isError: false,
        refetch: jest.fn(),
      } as any);
    });

    it('should maintain proper heading structure', () => {
      render(<MusicHistory selectedDate="2024-01-15" />, {
        wrapper: createTestWrapper(),
      });

      expect(screen.getByRole('heading', { level: 2, name: 'Music Journal' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: "Today's Listening Stats" })).toBeInTheDocument();
    });

    it('should display music placeholder image with proper alt text', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      const image = screen.getByAltText('Music collage');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', 'mocked-music-image.jpg');
    });

    it('should render "View Full Listening History" button', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      const button = screen.getByRole('button', { name: 'View Full Listening History →' });
      expect(button).toBeInTheDocument();
    });

    it('should apply correct CSS classes for styling', () => {
      render(<MusicHistory />, {
        wrapper: createTestWrapper(),
      });

      // Check for key styling classes
      expect(document.querySelector('.border-music-accent')).toBeInTheDocument();
      expect(document.querySelector('.font-headline')).toBeInTheDocument();
      expect(document.querySelector('.text-newspaper-headline')).toBeInTheDocument();
    });
  });
});