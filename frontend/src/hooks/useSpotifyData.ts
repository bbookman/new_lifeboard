// Custom hooks for Spotify data operations using React Query
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, queryKeys, SpotifyTrack } from '../lib/api';
import { useSpotifyAuthStatus, useSpotifyOAuth } from './useSpotifyAuth';

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

// Enhanced Spotify refresh hook with authentication checking
export const useSpotifyRefresh = (selectedDate?: string) => {
  const queryClient = useQueryClient();
  const queryKey = selectedDate ? queryKeys.spotify.byDate(selectedDate) : queryKeys.spotify.byDate('all');
  const { startOAuth } = useSpotifyOAuth();

  return useMutation({
    mutationFn: async () => {
      // First check authentication status
      const authResponse = await fetch('/api/spotify/auth/status');
      if (!authResponse.ok) {
        throw new Error('Failed to check authentication status');
      }
      
      const authStatus = await authResponse.json();
      
      // If not authenticated, start OAuth flow
      if (!authStatus.authenticated) {
        console.log('User not authenticated with Spotify, starting OAuth flow...');
        const authSuccess = await startOAuth();
        if (!authSuccess) {
          throw new Error('Authentication was cancelled or failed');
        }
        // Invalidate auth status query after successful OAuth
        queryClient.invalidateQueries({ queryKey: ['spotify', 'auth', 'status'] });
      }

      // Now trigger the Spotify sync (user is authenticated)
      const syncResponse = await apiClient.triggerSync('spotify');
      if (!syncResponse.success) {
        throw new Error(syncResponse.error || 'Failed to trigger Spotify sync');
      }

      // Poll for fresh data with up to 5 attempts every 1 second
      const maxAttempts = 5;
      const pollInterval = 1000;

      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        // Wait before checking
        if (attempt > 0) {
          await new Promise(resolve => setTimeout(resolve, pollInterval));
        }

        // Check if we have fresh data
        const dataResponse = await apiClient.getSpotifyTracks(selectedDate);
        if (dataResponse.success && dataResponse.data && dataResponse.data.length > 0) {
          return dataResponse.data;
        }
      }

      // If we get here, return empty array (timeout)
      return [];
    },
    onSuccess: (data) => {
      // Update the query cache with fresh data
      queryClient.setQueryData(queryKey, data);
      // Invalidate related queries to ensure other dates refresh when relevant
      queryClient.invalidateQueries({ queryKey: ['spotify'], exact: false });
      // Also invalidate auth status to reflect current state
      queryClient.invalidateQueries({ queryKey: ['spotify', 'auth', 'status'] });
    },
    onError: (error) => {
      console.error('Spotify refresh failed:', error);
    },
  });
};

// New hook to get authentication status
export const useSpotifyAuth = () => {
  return useSpotifyAuthStatus();
};
