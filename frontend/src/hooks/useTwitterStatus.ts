import { useState, useCallback, useEffect } from 'react';

/**
 * Twitter rate limit status state
 */
export interface TwitterStatusState {
  canFetch: boolean;
  minutesUntil: number;
  loading: boolean;
  error: string | null;
  lastFetchTime: string | null;
}

/**
 * Twitter rate limit status response
 */
export interface TwitterStatusResponse {
  canFetch: boolean;
  minutesUntil: number;
  lastFetchTime: string | null;
}

/**
 * Twitter rate limit status actions
 */
export interface TwitterStatusActions {
  checkStatus: () => Promise<TwitterStatusResponse>;
  resetError: () => void;
}

/**
 * API response interface for Twitter rate limit status
 */
interface TwitterRateLimitResponse {
  can_fetch_now: boolean;
  minutes_until_next: number;
  last_fetch_time: string | null;
}

/**
 * Custom hook for managing Twitter rate limit status
 * 
 * Provides rate limit checking functionality with automatic polling when rate limited.
 * Designed to be used by components that need to check Twitter API rate limits.
 * 
 * @param selectedDate - The date to check rate limit status for (YYYY-MM-DD format)
 * @returns Combined state and actions for Twitter rate limit status
 * 
 * @example
 * ```tsx
 * const { canFetch, minutesUntil, loading, error, checkStatus } = useTwitterStatus('2024-01-15');
 * 
 * if (loading) return <div>Loading...</div>;
 * if (error) return <div>Error: {error}</div>;
 * if (!canFetch) return <div>Rate limited. Try again in {minutesUntil} minutes</div>;
 * return <button onClick={handleFetch}>Fetch Twitter Data</button>;
 * ```
 */
export function useTwitterStatus(selectedDate: string): TwitterStatusState & TwitterStatusActions {
  const [canFetch, setCanFetch] = useState<boolean>(true);
  const [minutesUntil, setMinutesUntil] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchTime, setLastFetchTime] = useState<string | null>(null);

  /**
   * Checks the current Twitter rate limit status for the selected date
   */
  const checkRateLimit = useCallback(async (abortController?: AbortController) => {
    // Don't make API call if selectedDate is empty or invalid
    if (!selectedDate || !selectedDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
      return { canFetch: true, minutesUntil: 0, lastFetchTime: null };
    }

    try {
      const response = await fetch(`/api/calendar/twitter/status/${selectedDate}`, {
        signal: abortController?.signal
      });

      if (response.ok) {
        const data: TwitterRateLimitResponse = await response.json();
        return {
          canFetch: data.can_fetch_now,
          minutesUntil: data.minutes_until_next,
          lastFetchTime: data.last_fetch_time
        };
      } else if (response.status === 404) {
        // No rate limit data found, assume fetch is allowed
        return { canFetch: true, minutesUntil: 0, lastFetchTime: null };
      }
      throw new Error(`Failed to check rate limit: ${response.status}`);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was aborted, don't update state
        throw err;
      }
      
      console.error('Error checking Twitter rate limit:', err);
      // Fail-safe: assume fetch is allowed on error
      return { canFetch: true, minutesUntil: 0, lastFetchTime: null };
    }
  }, [selectedDate]);

  /**
   * Updates the state with rate limit status
   */
  const updateRateLimitState = useCallback((status: TwitterStatusResponse) => {
    setCanFetch(status.canFetch);
    setMinutesUntil(status.minutesUntil);
    setLastFetchTime(status.lastFetchTime);
  }, []);

  /**
   * Public method to check status (for manual refresh after fetch operations)
   * @returns The updated status values for immediate use by callers
   */
  const checkStatus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const status = await checkRateLimit();
      updateRateLimitState(status);
      return status;
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
      const fallbackStatus = { canFetch: true, minutesUntil: 0, lastFetchTime: null };
      updateRateLimitState(fallbackStatus);
      return fallbackStatus;
    } finally {
      setLoading(false);
    }
  }, [checkRateLimit, updateRateLimitState]);

  /**
   * Resets the error state
   */
  const resetError = useCallback(() => {
    setError(null);
  }, []);

  // Check rate limit status when selectedDate changes
  useEffect(() => {
    const abortController = new AbortController();
    
    async function checkInitialStatus() {
      try {
        const status = await checkRateLimit(abortController);
        if (!abortController.signal.aborted) {
          updateRateLimitState(status);
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          updateRateLimitState({ canFetch: true, minutesUntil: 0, lastFetchTime: null });
        }
      }
    }
    
    checkInitialStatus();
    return () => {
      abortController.abort();
    };
  }, [checkRateLimit, updateRateLimitState]);

  // Poll every 30 seconds when rate limited
  useEffect(() => {
    if (!canFetch && minutesUntil > 0) {
      const abortController = new AbortController();
      
      const intervalId = setInterval(async () => {
        try {
          const status = await checkRateLimit(abortController);
          if (!abortController.signal.aborted) {
            updateRateLimitState(status);
          }
        } catch (err) {
          if (err instanceof Error && err.name !== 'AbortError') {
            updateRateLimitState({ canFetch: true, minutesUntil: 0, lastFetchTime: null });
          }
        }
      }, 30000); // 30 seconds

      return () => {
        clearInterval(intervalId);
        abortController.abort();
      };
    }
  }, [canFetch, minutesUntil, checkRateLimit, updateRateLimitState]);

  return {
    canFetch,
    minutesUntil,
    loading,
    error,
    lastFetchTime,
    checkStatus,
    resetError
  };
}