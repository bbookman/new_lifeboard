import { useState, useCallback } from 'react';

export interface DataItem {
  id: string;
  namespace: string;
  days_date: string;
  metadata?: {
    processed_response?: {
      cleaned_markdown?: string;
      [key: string]: any;
    };
    original_response?: {
      markdown?: string;
      [key: string]: any;
    };
    cleaned_markdown?: string;
    markdown?: string;
    original_lifelog?: {
      markdown?: string;
    };
    [key: string]: any;
  };
  content?: string;
}

export interface LimitlessDataState {
  markdownContent: string;
  loading: boolean;
  autoFetching: boolean;
  fetchError: string | null;
  fetchAttempted: Set<string>;
}

export interface LimitlessDataActions {
  fetchData: (targetDate: string, allowAutoFetch?: boolean) => Promise<string | null>;
  triggerAutoFetch: (targetDate: string) => Promise<void>;
  resetState: () => void;
  clearContent: () => void;
  resetFetchAttempted: (date?: string) => void;
}

/**
 * Custom hook for managing Limitless data fetching and state
 * Extracts API interaction logic from the component
 */
export const useLimitlessData = (): LimitlessDataState & LimitlessDataActions => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [fetchAttempted, setFetchAttempted] = useState<Set<string>>(new Set());
  const [autoFetching, setAutoFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  /**
   * Extract markdown content from data items in priority order
   */
  const extractMarkdownContent = useCallback((dataItems: DataItem[]): string => {
    const markdownParts: string[] = [];
    
    dataItems.forEach((item, index) => {
      let itemMarkdown = '';
      
      // Priority order: processed_response.cleaned_markdown > original_response.markdown > cleaned_markdown > markdown > content
      if (item.metadata?.processed_response?.cleaned_markdown) {
        itemMarkdown = item.metadata.processed_response.cleaned_markdown;
        console.log(`[useLimitlessData] Item ${index}: Using processed_response.cleaned_markdown (${itemMarkdown.length} chars)`);
      } else if (item.metadata?.original_response?.markdown) {
        itemMarkdown = item.metadata.original_response.markdown;
        console.log(`[useLimitlessData] Item ${index}: Using original_response.markdown (${itemMarkdown.length} chars)`);
      } else if (item.metadata?.cleaned_markdown) {
        itemMarkdown = item.metadata.cleaned_markdown;
        console.log(`[useLimitlessData] Item ${index}: Using cleaned_markdown (${itemMarkdown.length} chars)`);
      } else if (item.metadata?.markdown) {
        itemMarkdown = item.metadata.markdown;
        console.log(`[useLimitlessData] Item ${index}: Using metadata.markdown (${itemMarkdown.length} chars)`);
      } else if (item.metadata?.original_lifelog?.markdown) {
        itemMarkdown = item.metadata.original_lifelog.markdown;
        console.log(`[useLimitlessData] Item ${index}: Using original_lifelog.markdown (${itemMarkdown.length} chars)`);
      } else if (item.content) {
        itemMarkdown = item.content;
        console.log(`[useLimitlessData] Item ${index}: Using content (${itemMarkdown.length} chars)`);
      } else {
        console.log(`[useLimitlessData] Item ${index}: No markdown content found`);
      }
      
      // Validate content - reject API response messages or system messages
      if (itemMarkdown) {
        const lowerContent = itemMarkdown.toLowerCase();
        const isApiResponse = lowerContent.includes('data already exists') || 
                            lowerContent.includes('api response') ||
                            lowerContent.includes('fetch result') ||
                            lowerContent.includes('successfully fetched') ||
                            lowerContent.includes('items_processed');
        
        if (isApiResponse) {
          console.warn(`[useLimitlessData] Item ${index}: Rejecting API response-like content: ${itemMarkdown.substring(0, 100)}...`);
          itemMarkdown = '';
        }
      }
      
      if (itemMarkdown) {
        markdownParts.push(itemMarkdown);
      }
    });
    
    console.log(`[useLimitlessData] Total markdown parts: ${markdownParts.length}, total chars: ${markdownParts.join('').length}`);
    
    // Join all markdown content with separators
    return markdownParts.join('\n\n---\n\n');
  }, []);

  /**
   * Trigger automatic fetch for a specific date when no data exists
   */
  // TEMPORARY: Replace useCallback with direct function to eliminate stale closure
  const triggerAutoFetch = async (targetDate: string): Promise<void> => {
    const uniqueId = `CODE_LOADED_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    console.log(`[useLimitlessData] ===== TRIGGER AUTO FETCH ENTRY POINT ===== ${uniqueId}`);
    console.log(`[useLimitlessData] CODE VERIFICATION: This log confirms new code is loaded at ${new Date().toISOString()}`);
    console.log(`[useLimitlessData] Function called with targetDate: ${targetDate}`);
    console.log(`[useLimitlessData] Current autoFetching state: ${autoFetching}`);
    console.log(`[useLimitlessData] Current fetchAttempted set:`, Array.from(fetchAttempted));
    console.log(`[useLimitlessData] Has targetDate been attempted: ${fetchAttempted.has(targetDate)}`);
    
    try {
      console.log(`[useLimitlessData] Starting automatic fetch for date: ${targetDate}`);
      setAutoFetching(true);
      setFetchError(null);
      
      // Mark this date as attempted
      setFetchAttempted(prev => new Set([...prev, targetDate]));
      
      // Call the on-demand fetch API
      const fetchApiUrl = `/api/calendar/limitless/fetch/${targetDate}`;
      console.log(`[useLimitlessData] Calling automatic fetch API: ${fetchApiUrl}`);
      
      const fetchResponse = await fetch(fetchApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      console.log(`[useLimitlessData] Automatic fetch API response status: ${fetchResponse.status}`);
      
      if (fetchResponse.ok) {
        const fetchResult = await fetchResponse.json();
        console.log(`[useLimitlessData] Automatic fetch result:`, fetchResult);
        
        if (fetchResult.success) {
          console.log(`[useLimitlessData] Automatic fetch successful: ${fetchResult.message}`);
          
          // Wait a moment for data to be processed, then refetch
          setTimeout(async () => {
            console.log(`[useLimitlessData] Refetching data after successful automatic fetch`);
            
            // Fetch data manually without auto-fetch to avoid loops
            try {
              const timestamp = Date.now();
              const apiUrl = `/api/calendar/data_items/${targetDate}?namespaces=limitless&_t=${timestamp}`;
              const response = await fetch(apiUrl, {
                headers: {
                  'Cache-Control': 'no-cache, no-store, must-revalidate',
                  'Pragma': 'no-cache',
                  'Expires': '0'
                }
              });
              
              if (response.ok) {
                const dataItems: DataItem[] = await response.json();
                console.log(`[useLimitlessData] Refetch received: ${dataItems.length} items`);
                
                if (dataItems.length > 0) {
                  const combinedMarkdown = extractMarkdownContent(dataItems);
                  if (combinedMarkdown.trim().length > 0) {
                    setMarkdownContent(combinedMarkdown);
                    console.log(`[useLimitlessData] Refetch set markdown content length: ${combinedMarkdown.length}`);
                  }
                }
              }
            } catch (error) {
              console.error('[useLimitlessData] Error during refetch:', error);
            }
          }, 1000);
          
        } else {
          console.error(`[useLimitlessData] Automatic fetch failed:`, fetchResult.message);
          setFetchError(`Failed to fetch data: ${fetchResult.message}`);
          setMarkdownContent('');
        }
      } else {
        const errorText = await fetchResponse.text();
        console.error(`[useLimitlessData] Automatic fetch API error:`, fetchResponse.status, errorText);
        setFetchError(`Failed to fetch data: ${fetchResponse.status} ${fetchResponse.statusText}`);
        setMarkdownContent('');
      }
      
    } catch (error) {
      console.error(`[useLimitlessData] Error during automatic fetch:`, error);
      setFetchError(`Network error during automatic fetch: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setMarkdownContent('');
    } finally {
      setAutoFetching(false);
      setLoading(false);
    }
  };

  /**
   * Fetch cleaned markdown from limitless data_items
   */
  const fetchData = useCallback(async (targetDate: string, allowAutoFetch: boolean = true): Promise<string | null> => {
    const fetchStartTime = Date.now();
    console.log(`[useLimitlessData] ===== FETCH DATA CALLED at ${new Date().toISOString()} =====`);
    console.log(`[useLimitlessData] Parameters: targetDate=${targetDate}, allowAutoFetch=${allowAutoFetch}`);
    
    // Don't make API call if targetDate is empty or invalid
    if (!targetDate || !targetDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
      console.log(`[useLimitlessData] ABORT: Skipping API call for invalid date: ${targetDate}`);
      return null;
    }

    try {
      console.log(`[useLimitlessData] Step 1: Date validation passed for: ${targetDate}`);
      console.log(`[useLimitlessData] Current state - loading: ${loading}, autoFetching: ${autoFetching}`);
      console.log(`[useLimitlessData] Fetch attempted dates:`, Array.from(fetchAttempted));
      setLoading(true);
      console.log(`[useLimitlessData] Step 2: Setting loading state to true`);
      
      // Fetch data for the target date with cache-busting timestamp
      const timestamp = Date.now();
      const apiUrl = `/api/calendar/data_items/${targetDate}?namespaces=limitless&_t=${timestamp}`;
      console.log(`[useLimitlessData] Step 3: Constructed API URL: ${apiUrl}`);
      console.log(`[useLimitlessData] Cache-busting timestamp: ${timestamp}`);
      
      console.log(`[useLimitlessData] Step 4: Making fetch request to API`);
      const fetchRequestTime = Date.now();
      
      const response = await fetch(apiUrl, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });
      
      const fetchResponseTime = Date.now();
      console.log(`[useLimitlessData] Step 5: Fetch completed in ${fetchResponseTime - fetchRequestTime}ms`);
      console.log(`[useLimitlessData] Response status: ${response.status}`);
      console.log(`[useLimitlessData] Response ok: ${response.ok}`);
      console.log(`[useLimitlessData] Response headers:`, Object.fromEntries(response.headers.entries()));
      
      if (response.ok) {
        console.log(`[useLimitlessData] Step 6: Response successful, parsing JSON`);
        const jsonParseTime = Date.now();
        const dataItems: DataItem[] = await response.json();
        const jsonParsedTime = Date.now();
        
        console.log(`[useLimitlessData] Step 7: JSON parsed in ${jsonParsedTime - jsonParseTime}ms`);
        console.log(`[useLimitlessData] RECEIVED: ${dataItems.length} items for targetDate=${targetDate}`);
        console.log(`[useLimitlessData] Item IDs:`, dataItems.map(item => item.id));
        
        // Verify all items have correct days_date
        const dateMismatchItems = dataItems.filter(item => item.days_date !== targetDate);
        if (dateMismatchItems.length > 0) {
          console.error(`[useLimitlessData] DATE MISMATCH! Found ${dateMismatchItems.length} items with wrong days_date:`, 
            dateMismatchItems.map(item => ({id: item.id, days_date: item.days_date})));
        }
        
        if (dataItems.length > 0) {
          console.log(`[useLimitlessData] Step 8: Processing ${dataItems.length} data items`);
          const extractTime = Date.now();
          const combinedMarkdown = extractMarkdownContent(dataItems);
          const extractedTime = Date.now();
          
          console.log(`[useLimitlessData] Step 9: Markdown extraction completed in ${extractedTime - extractTime}ms`);
          console.log(`[useLimitlessData] Combined markdown length: ${combinedMarkdown.length}`);
          console.log(`[useLimitlessData] Combined markdown trimmed length: ${combinedMarkdown.trim().length}`);
          console.log(`[useLimitlessData] Combined markdown preview: ${combinedMarkdown.substring(0, 200)}...`);
          
          if (combinedMarkdown.trim().length > 0) {
            console.log(`[useLimitlessData] Step 10: Setting markdown content and updating state`);
            setMarkdownContent(combinedMarkdown);
            console.log(`[useLimitlessData] Markdown content set successfully`);
            setLoading(false);
            console.log(`[useLimitlessData] Loading state set to false`);
            const finalTime = Date.now();
            console.log(`[useLimitlessData] ===== FETCH SUCCESS: Returning data after ${finalTime - fetchStartTime}ms =====`);
            return combinedMarkdown;
          } else {
            console.log(`[useLimitlessData] Step 10: No displayable markdown content found for ${targetDate}`);
            console.log(`[useLimitlessData] Auto-fetch evaluation: allowAutoFetch=${allowAutoFetch}, attempted=${fetchAttempted.has(targetDate)}, autoFetching=${autoFetching}`);
            
            // Trigger automatic fetch if no data and not already attempted
            if (allowAutoFetch && !fetchAttempted.has(targetDate) && !autoFetching) {
              console.log(`[useLimitlessData] Triggering automatic fetch for ${targetDate} - no displayable content`);
              await triggerAutoFetch(targetDate);
              setLoading(false);
              const finalTime = Date.now();
              console.log(`[useLimitlessData] ===== FETCH TRIGGERED AUTO-FETCH after ${finalTime - fetchStartTime}ms =====`);
              return markdownContent || null;
            } else {
              console.log(`[useLimitlessData] Not triggering automatic fetch for ${targetDate}: attempted=${fetchAttempted.has(targetDate)}, fetching=${autoFetching}, allowAuto=${allowAutoFetch}`);
              setMarkdownContent('');
              setLoading(false);
              const finalTime = Date.now();
              console.log(`[useLimitlessData] ===== FETCH COMPLETED (no content) after ${finalTime - fetchStartTime}ms =====`);
              return null;
            }
          }
        } else {
          console.log(`[useLimitlessData] Step 8: No data items found for ${targetDate}`);
          console.log(`[useLimitlessData] Auto-fetch evaluation: allowAutoFetch=${allowAutoFetch}, attempted=${fetchAttempted.has(targetDate)}, autoFetching=${autoFetching}`);
          
          // Trigger automatic fetch if no data and not already attempted
          if (allowAutoFetch && !fetchAttempted.has(targetDate) && !autoFetching) {
            console.log(`[useLimitlessData] Triggering automatic fetch for ${targetDate} (no items)`);
            await triggerAutoFetch(targetDate);
            setLoading(false);
            const finalTime = Date.now();
            console.log(`[useLimitlessData] ===== FETCH TRIGGERED AUTO-FETCH (no items) after ${finalTime - fetchStartTime}ms =====`);
            return markdownContent || null;
          } else {
            console.log(`[useLimitlessData] Automatic fetch already attempted or in progress for ${targetDate}, or auto-fetch disabled`);
            setMarkdownContent('');
            setLoading(false);
            const finalTime = Date.now();
            console.log(`[useLimitlessData] ===== FETCH COMPLETED (no items, no auto-fetch) after ${finalTime - fetchStartTime}ms =====`);
            return null;
          }
        }
      } else {
        console.error('[useLimitlessData] Step 6: Failed to fetch limitless data:', response.status);
        console.error('[useLimitlessData] Response not ok, status text:', response.statusText);
        setMarkdownContent('');
        setLoading(false);
        const finalTime = Date.now();
        console.log(`[useLimitlessData] ===== FETCH FAILED after ${finalTime - fetchStartTime}ms =====`);
        return null;
      }
    } catch (error) {
      console.error('[useLimitlessData] ERROR during fetch operation:', error);
      console.error('[useLimitlessData] Error name:', error instanceof Error ? error.name : 'Unknown');
      console.error('[useLimitlessData] Error message:', error instanceof Error ? error.message : 'Unknown error');
      console.error('[useLimitlessData] Error stack:', error instanceof Error ? error.stack : 'No stack trace');
      setMarkdownContent('');
      setLoading(false);
      const finalTime = Date.now();
      console.log(`[useLimitlessData] ===== FETCH ERROR after ${finalTime - fetchStartTime}ms =====`);
      return null;
    }
  }, [extractMarkdownContent, fetchAttempted, autoFetching]);

  /**
   * Reset all state to initial values
   */
  const resetState = useCallback(() => {
    setMarkdownContent('');
    setLoading(true);
    setFetchAttempted(new Set());
    setAutoFetching(false);
    setFetchError(null);
  }, []);

  /**
   * Clear content without resetting other state
   */
  const clearContent = useCallback(() => {
    setMarkdownContent('');
    setFetchError(null);
  }, []);

  /**
   * Reset fetch attempted state for a specific date or all dates
   * @param date - Optional date to reset. If not provided, clears all dates
   */
  const resetFetchAttempted = useCallback((date?: string) => {
    if (date) {
      console.log(`[useLimitlessData] Resetting fetch attempts for date: ${date}`);
      setFetchAttempted(prev => {
        const newSet = new Set(prev);
        newSet.delete(date);
        console.log(`[useLimitlessData] Removed ${date} from fetch attempts. Remaining attempts:`, Array.from(newSet));
        return newSet;
      });
    } else {
      console.log(`[useLimitlessData] Clearing all fetch attempts`);
      setFetchAttempted(new Set());
    }
  }, []);

  return {
    // State
    markdownContent,
    loading,
    autoFetching,
    fetchError,
    fetchAttempted,
    
    // Actions
    fetchData,
    triggerAutoFetch,
    resetState,
    clearContent,
    resetFetchAttempted
  };
};