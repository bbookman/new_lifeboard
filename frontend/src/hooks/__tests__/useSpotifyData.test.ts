import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSpotifyTracks } from '../useSpotifyData';
import * as apiClient from '../../lib/api';

// Mock the API client
jest.mock('../../lib/api');
const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

// Mock Spotify track data
const mockSpotifyTrack = {
  id: 'track123',
  title: 'Test Song',
  artist: 'Test Artist',
  album: 'Test Album',
  duration_ms: 180000,
  played_at: '2024-01-15T10:30:00Z',
  preview_url: 'https://example.com/preview.mp3',
  external_urls: {
    spotify: 'https://open.spotify.com/track/track123'
  },
  audio_features: {
    danceability: 0.8,
    energy: 0.7,
    valence: 0.6
  }
};

const mockSpotifyTracks = [
  mockSpotifyTrack,
  {
    ...mockSpotifyTrack,
    id: 'track456',
    title: 'Another Song',
    played_at: '2024-01-15T11:00:00Z'
  }
];

// Test wrapper with QueryClient
const createWrapper = () => {
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

describe('useSpotifyTracks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('data fetching', () => {
    it('should fetch Spotify tracks for a given date', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockSpotifyTracks);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('2024-01-15');
    });

    it('should fetch tracks without date parameter', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks(),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith(undefined);
    });

    it('should handle undefined selectedDate', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks(undefined),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith(undefined);
    });
  });

  describe('loading states', () => {
    it('should show loading state initially', () => {
      mockedApiClient.getSpotifyTracks.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
      expect(result.current.isSuccess).toBe(false);
      expect(result.current.isError).toBe(false);
      expect(result.current.data).toBeUndefined();
    });

    it('should transition from loading to success', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(mockSpotifyTracks);
    });
  });

  describe('error handling', () => {
    it('should handle API errors', async () => {
      const errorMessage = 'Failed to fetch Spotify tracks';
      mockedApiClient.getSpotifyTracks.mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
      expect(result.current.data).toBeUndefined();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.isSuccess).toBe(false);
    });

    it('should handle network errors', async () => {
      mockedApiClient.getSpotifyTracks.mockRejectedValue(new Error('Network Error'));

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe('Network Error');
    });

    it('should handle 404 errors gracefully', async () => {
      mockedApiClient.getSpotifyTracks.mockRejectedValue(new Error('Not Found'));

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe('Not Found');
    });
  });

  describe('cache behavior and invalidation', () => {
    it('should cache results for the same date', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const wrapper = createWrapper();

      // First render
      const { result: result1 } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result1.current.isSuccess).toBe(true);
      });

      // Second render with same date should use cache
      const { result: result2 } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper }
      );

      expect(result2.current.data).toEqual(mockSpotifyTracks);
      expect(result2.current.isLoading).toBe(false);
      
      // API should only be called once due to caching
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledTimes(1);
    });

    it('should make separate requests for different dates', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const wrapper = createWrapper();

      // First render with date1
      const { result: result1 } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result1.current.isSuccess).toBe(true);
      });

      // Second render with different date
      const { result: result2 } = renderHook(
        () => useSpotifyTracks('2024-01-16'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result2.current.isSuccess).toBe(true);
      });

      // API should be called twice for different dates
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledTimes(2);
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('2024-01-15');
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('2024-01-16');
    });

    it('should have correct cache keys for different dates', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result, rerender } = renderHook(
        ({ date }) => useSpotifyTracks(date),
        {
          wrapper: createWrapper(),
          initialProps: { date: '2024-01-15' }
        }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Change date should trigger new request
      rerender({ date: '2024-01-16' });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledTimes(2);
    });
  });

  describe('date format edge cases', () => {
    it('should handle ISO date strings', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15T00:00:00Z'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('2024-01-15T00:00:00Z');
    });

    it('should handle different date formats', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const testDates = [
        '2024-01-15',
        '2024/01/15',
        '01-15-2024',
        '15/01/2024'
      ];

      for (const date of testDates) {
        const { result } = renderHook(
          () => useSpotifyTracks(date),
          { wrapper: createWrapper() }
        );

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith(date);
      }
    });

    it('should handle empty string date', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks(''),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('');
    });

    it('should handle null date', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks(null as any),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith(null);
    });
  });

  describe('no data scenarios', () => {
    it('should handle empty array response', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue([]);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([]);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should handle null response', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(null as any);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toBeNull();
    });

    it('should handle undefined response', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(undefined as any);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('React Query integration', () => {
    it('should provide correct query key structure', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // The hook should expose query metadata
      expect(result.current.dataUpdatedAt).toBeGreaterThan(0);
      expect(result.current.isFetching).toBe(false);
      expect(result.current.isStale).toBe(false);
    });

    it('should support refetch functionality', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Refetch should be available
      expect(typeof result.current.refetch).toBe('function');

      // Call refetch
      await result.current.refetch();

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledTimes(2);
    });

    it('should handle stale data correctly', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.isStale).toBe(false);
      expect(result.current.data).toEqual(mockSpotifyTracks);
    });

    it('should handle background refetching', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result } = renderHook(
        () => useSpotifyTracks('2024-01-15'),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.isRefetching).toBe(false);
    });
  });

  describe('hook parameter changes', () => {
    it('should refetch when selectedDate changes', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result, rerender } = renderHook(
        ({ date }) => useSpotifyTracks(date),
        {
          wrapper: createWrapper(),
          initialProps: { date: '2024-01-15' }
        }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('2024-01-15');

      // Change the date
      rerender({ date: '2024-01-16' });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledWith('2024-01-16');
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledTimes(2);
    });

    it('should not refetch when selectedDate stays the same', async () => {
      mockedApiClient.getSpotifyTracks.mockResolvedValue(mockSpotifyTracks);

      const { result, rerender } = renderHook(
        ({ date }) => useSpotifyTracks(date),
        {
          wrapper: createWrapper(),
          initialProps: { date: '2024-01-15' }
        }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Rerender with same date
      rerender({ date: '2024-01-15' });

      // Should not trigger additional API call
      expect(mockedApiClient.getSpotifyTracks).toHaveBeenCalledTimes(1);
    });
  });
});