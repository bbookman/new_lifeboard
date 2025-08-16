import { useEffect, useCallback, useRef } from 'react';
import { LimitlessDataActions, LimitlessDataState } from './useLimitlessData';

/**
 * Custom hook for managing auto-fetch logic and date changes
 * Separates auto-fetch concerns from the main data fetching logic
 */
export const useAutoFetch = (
  selectedDate: string | undefined,
  limitlessData: LimitlessDataState & LimitlessDataActions
) => {
  const prevSelectedDateRef = useRef<string | undefined>();

  /**
   * Get the target date for fetching
   * Uses selectedDate if provided, otherwise today's date
   */
  const getTargetDate = useCallback((dateInput?: string): string => {
    if (dateInput) {
      console.log(`[useAutoFetch] Using selectedDate: ${dateInput}`);
      return dateInput;
    }
    
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const today = `${year}-${month}-${day}`;
    console.log(`[useAutoFetch] No selectedDate provided, using today: ${today}`);
    return today;
  }, []);

  /**
   * Handle date changes and trigger appropriate fetching
   */
  useEffect(() => {
    // Only run when selectedDate actually changes
    if (prevSelectedDateRef.current === selectedDate) {
      console.log(`[useAutoFetch] selectedDate unchanged (${selectedDate}), skipping`);
      return;
    }

    console.log(`[useAutoFetch] useEffect triggered with selectedDate:`, selectedDate);
    console.log(`[useAutoFetch] useEffect - current state:`, {
      markdownContentLength: limitlessData.markdownContent.length,
      loading: limitlessData.loading,
      fetchAttempted: Array.from(limitlessData.fetchAttempted),
      autoFetching: limitlessData.autoFetching,
      fetchError: limitlessData.fetchError
    });
    
    const targetDate = getTargetDate(selectedDate);
    
    // Reset state when date changes
    if (selectedDate) {
      console.log(`[useAutoFetch] Date changed to: ${selectedDate}, clearing content`);
      limitlessData.clearContent();
    }
    
    // Fetch data for the target date
    console.log(`[useAutoFetch] Fetching data for target date: ${targetDate}`);
    limitlessData.fetchData(targetDate, true);

    // Update the ref to track the current value
    prevSelectedDateRef.current = selectedDate;
  }, [selectedDate]);

  return {
    getTargetDate
  };
};