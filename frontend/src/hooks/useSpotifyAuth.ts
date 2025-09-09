// Custom hooks for Spotify OAuth authentication
import { useQuery, useMutation } from '@tanstack/react-query';

// Types for Spotify OAuth
interface TokenInfo {
  has_token: boolean;
  is_expired: boolean;
  scope?: string;
  expires_at?: string;
  created_at?: string;
}

interface AuthStatusResponse {
  authenticated: boolean;
  token_info: TokenInfo;
}

interface AuthUrlResponse {
  auth_url: string;
}

// API base URL
const API_BASE_URL = '/api';

// Check Spotify authentication status
export const useSpotifyAuthStatus = () => {
  return useQuery({
    queryKey: ['spotify', 'auth', 'status'],
    queryFn: async (): Promise<AuthStatusResponse> => {
      const response = await fetch(`${API_BASE_URL}/spotify/auth/status`);
      if (!response.ok) {
        throw new Error(`Failed to check auth status: ${response.status}`);
      }
      return response.json();
    },
    staleTime: 30 * 1000, // 30 seconds - check frequently for auth state changes
    cacheTime: 60 * 1000, // 1 minute
  });
};

// Get Spotify OAuth URL
export const useSpotifyAuthUrl = () => {
  return useMutation({
    mutationFn: async (): Promise<string> => {
      const response = await fetch(`${API_BASE_URL}/spotify/auth/url`);
      if (!response.ok) {
        throw new Error(`Failed to get auth URL: ${response.status}`);
      }
      const data: AuthUrlResponse = await response.json();
      return data.auth_url;
    },
  });
};

// OAuth popup handler
export const useSpotifyOAuth = () => {
  const getAuthUrl = useSpotifyAuthUrl();

  const startOAuthFlow = useMutation({
    mutationFn: async (): Promise<boolean> => {
      try {
        // Get the auth URL
        const authUrl = await getAuthUrl.mutateAsync();
        
        // Open OAuth popup
        const popup = window.open(
          authUrl,
          'spotify-oauth',
          'width=600,height=700,left=' + 
          (window.screen.width / 2 - 300) + 
          ',top=' + 
          (window.screen.height / 2 - 350)
        );

        if (!popup) {
          throw new Error('Failed to open OAuth popup. Please allow popups for this site.');
        }

        // Wait for OAuth completion
        return new Promise((resolve, reject) => {
          const checkClosed = setInterval(() => {
            if (popup.closed) {
              clearInterval(checkClosed);
              // Check if auth was successful by querying auth status
              fetch(`${API_BASE_URL}/spotify/auth/status`)
                .then(response => response.json())
                .then((status: AuthStatusResponse) => {
                  if (status.authenticated) {
                    resolve(true);
                  } else {
                    reject(new Error('OAuth was cancelled or failed'));
                  }
                })
                .catch(() => {
                  reject(new Error('Failed to verify authentication status'));
                });
            }
          }, 1000);

          // Timeout after 5 minutes
          setTimeout(() => {
            clearInterval(checkClosed);
            if (!popup.closed) {
              popup.close();
            }
            reject(new Error('OAuth timeout - please try again'));
          }, 5 * 60 * 1000);
        });
      } catch (error) {
        throw error;
      }
    },
  });

  return {
    startOAuth: startOAuthFlow.mutateAsync,
    isLoading: startOAuthFlow.isPending,
    error: startOAuthFlow.error,
  };
};