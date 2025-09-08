// Custom hooks for Spotify data operations using React Query
import { useQuery } from '@tanstack/react-query';
import { apiClient, queryKeys, SpotifyTrack } from '../lib/api';

// Spotify tracks hook
export const useSpotifyTracks = (selectedDate?: string) => {
  return useQuery({
    queryKey: selectedDate ? queryKeys.spotify.byDate(selectedDate) : queryKeys.spotify.byDate('all'),
    queryFn: async () => {
      const response = await apiClient.getSpotifyTracks(selectedDate);
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch Spotify tracks');
      }
      return response.data || [];
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
  });
};