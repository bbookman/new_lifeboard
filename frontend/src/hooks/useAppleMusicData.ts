import { useState, useCallback, useEffect } from 'react';

export interface AppleMusicPlay {
  artist: string;
  album: string;
  song: string;
  play_count: number;
}

export interface AppleMusicDataState {
  plays: AppleMusicPlay[];
  loading: boolean;
  error: string | null;
}

export interface AppleMusicDataActions {
  fetchPlays: (date: string) => Promise<void>;
  refreshPlays: () => Promise<void>;
}

/**
 * Custom hook for managing Apple Music play data fetching and state
 */
export const useAppleMusicData = (selectedDate?: string): AppleMusicDataState & AppleMusicDataActions => {
  const [plays, setPlays] = useState<AppleMusicPlay[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentDate, setCurrentDate] = useState<string | undefined>(selectedDate);

  /**
   * Fetch Apple Music plays for a specific date
   */
  const fetchPlays = useCallback(async (date: string): Promise<void> => {
    // Don't make API call if date is empty or invalid
    if (!date || !date.match(/^\d{4}-\d{2}-\d{2}$/)) {
      console.log(`[useAppleMusicData] Skipping API call for invalid date: ${date}`);
      return;
    }

    try {
      console.log(`[useAppleMusicData] Fetching Apple Music plays for date: ${date}`);
      setLoading(true);
      setError(null);
      setCurrentDate(date);

      const timestamp = Date.now();
      const apiUrl = `/api/apple-music/${date}?_t=${timestamp}`;
      console.log(`[useAppleMusicData] API URL: ${apiUrl}`);

      const response = await fetch(apiUrl, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });

      console.log(`[useAppleMusicData] Response status: ${response.status}`);

      if (response.ok) {
        const data: AppleMusicPlay[] = await response.json();
        console.log(`[useAppleMusicData] Received ${data.length} Apple Music plays`);
        setPlays(data);
      } else {
        const errorText = await response.text();
        console.error(`[useAppleMusicData] API error: ${response.status} ${errorText}`);
        setError(`Failed to fetch Apple Music data: ${response.status} ${response.statusText}`);
        setPlays([]);
      }
    } catch (err) {
      console.error('[useAppleMusicData] Error fetching Apple Music plays:', err);
      setError(`Network error: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setPlays([]);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Refresh plays for the current date
   */
  const refreshPlays = useCallback(async (): Promise<void> => {
    if (currentDate) {
      await fetchPlays(currentDate);
    }
  }, [currentDate, fetchPlays]);

  // Auto-fetch when selectedDate changes
  useEffect(() => {
    if (selectedDate) {
      fetchPlays(selectedDate);
    }
  }, [selectedDate, fetchPlays]);

  return {
    // State
    plays,
    loading,
    error,

    // Actions
    fetchPlays,
    refreshPlays
  };
};
