import { useState, useCallback } from 'react';
import { DataItem } from '@/lib/api';

export interface TwitterDataState {
  loading: boolean;
  autoFetching: boolean;
  fetchError: string | null;
  fetchAttempted: Set<string>;
}

export interface TwitterDataActions {
  checkAndFetchData: (targetDate: string) => Promise<void>;
  triggerAutoFetch: (targetDate: string) => Promise<void>;
  resetState: () => void;
}

/**
 * Custom hook for managing Twitter data fetching and state
 * Similar to useLimitlessData but for Twitter API data
 */
export const useTwitterData = (): TwitterDataState & TwitterDataActions => {
  const [loading, setLoading] = useState(false);
  const [fetchAttempted, setFetchAttempted] = useState<Set<string>>(new Set());
  const [autoFetching, setAutoFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  /**
   * Trigger automatic fetch for a specific date when no data exists
   */
  const triggerAutoFetch = useCallback(async (targetDate: string): Promise<void> => {
    try {
      console.log(`[useTwitterData] Starting automatic fetch for date: ${targetDate}`);
      setAutoFetching(true);
      setFetchError(null);
      
      // Mark this date as attempted
      setFetchAttempted(prev => new Set([...prev, targetDate]));
      
      // Call the on-demand fetch API
      const fetchApiUrl = `http://localhost:8000/calendar/twitter/fetch/${targetDate}`;
      console.log(`[useTwitterData] Calling automatic fetch API: ${fetchApiUrl}`);
      
      const fetchResponse = await fetch(fetchApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      console.log(`[useTwitterData] Automatic fetch API response status: ${fetchResponse.status}`);
      
      if (fetchResponse.ok) {
        const fetchResult = await fetchResponse.json();
        console.log(`[useTwitterData] Automatic fetch result:`, fetchResult);
        
        if (fetchResult.success) {
          console.log(`[useTwitterData] Automatic fetch successful: ${fetchResult.message}`);
        } else {
          console.error(`[useTwitterData] Automatic fetch failed:`, fetchResult.message);
          setFetchError(`Failed to fetch Twitter data: ${fetchResult.message}`);
        }
      } else {
        const errorText = await fetchResponse.text();
        console.error(`[useTwitterData] Automatic fetch API error:`, fetchResponse.status, errorText);
        
        // Handle specific error cases
        if (fetchResponse.status === 503) {
          setFetchError('Twitter API not configured');
        } else if (fetchResponse.status === 404) {
          setFetchError('Twitter source not available');
        } else {
          setFetchError(`Failed to fetch Twitter data: ${fetchResponse.status} ${fetchResponse.statusText}`);
        }
      }
      
    } catch (error) {
      console.error(`[useTwitterData] Error during automatic fetch:`, error);
      setFetchError(`Network error during Twitter data fetch: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setAutoFetching(false);
      setLoading(false);
    }
  }, []);

  /**
   * Check if Twitter data exists for a date and trigger fetch if needed
   */
  const checkAndFetchData = useCallback(async (targetDate: string): Promise<void> => {
    try {
      setLoading(true);
      setFetchError(null);
      console.log(`[useTwitterData] Checking Twitter data for targetDate: ${targetDate}`);
      
      // Fetch existing data for the target date
      const timestamp = Date.now();
      const apiUrl = `http://localhost:8000/calendar/data_items/${targetDate}?namespaces=twitter&_t=${timestamp}`;
      console.log(`[useTwitterData] API URL: ${apiUrl}`);
      
      const response = await fetch(apiUrl, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });
      
      console.log(`[useTwitterData] Response status: ${response.status}`);
      
      if (response.ok) {
        const dataItems: DataItem[] = await response.json();
        console.log(`[useTwitterData] RECEIVED: ${dataItems.length} Twitter items for targetDate=${targetDate}`);
        
        // Verify all items have correct days_date
        const dateMismatchItems = dataItems.filter(item => item.days_date !== targetDate);
        if (dateMismatchItems.length > 0) {
          console.error(`[useTwitterData] DATE MISMATCH! Found ${dateMismatchItems.length} items with wrong days_date:`, 
            dateMismatchItems.map(item => ({id: item.id, days_date: item.days_date})));
        }
        
        if (dataItems.length === 0) {
          console.log(`[useTwitterData] No Twitter data items found for ${targetDate}`);
          
          // Trigger automatic fetch if no data and not already attempted
          if (!fetchAttempted.has(targetDate) && !autoFetching) {
            console.log(`[useTwitterData] Triggering automatic fetch for ${targetDate} (no items)`);
            await triggerAutoFetch(targetDate);
          } else {
            console.log(`[useTwitterData] Automatic fetch already attempted or in progress for ${targetDate}`);
          }
        } else {
          console.log(`[useTwitterData] Found ${dataItems.length} Twitter items for ${targetDate}`);
        }
      } else {
        console.error('[useTwitterData] Failed to fetch Twitter data:', response.status);
        setFetchError(`Failed to check Twitter data: ${response.status}`);
      }
      
    } catch (error) {
      console.error('[useTwitterData] Error checking Twitter data:', error);
      setFetchError(`Error checking Twitter data: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      if (!autoFetching) {
        setLoading(false);
      }
    }
  }, [fetchAttempted, autoFetching, triggerAutoFetch]);

  /**
   * Reset all state to initial values
   */
  const resetState = useCallback(() => {
    setLoading(false);
    setFetchAttempted(new Set());
    setAutoFetching(false);
    setFetchError(null);
  }, []);

  return {
    // State
    loading,
    autoFetching,
    fetchError,
    fetchAttempted,
    
    // Actions
    checkAndFetchData,
    triggerAutoFetch,
    resetState
  };
};