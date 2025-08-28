import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useTwitterData } from '../useTwitterData';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('useTwitterData Hook - Auto-Fetch Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('API Endpoint URL Correctness', () => {
    it('should use correct URL for data checking', async () => {
      const targetDate = '2025-08-24';
      const expectedDataUrl = `http://localhost:8000/calendar/data_items/${targetDate}?namespaces=twitter&_t=`;

      // Mock successful response (no data exists)
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useTwitterData());

      // Trigger the check
      await result.current.checkAndFetchData(targetDate);

      // Verify the data check URL was called
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(new RegExp(`^${expectedDataUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
          })
        })
      );
    });

    it('should use correct URL for auto-fetch API', async () => {
      const targetDate = '2025-08-24';
      const expectedFetchUrl = `http://localhost:8000/calendar/twitter/fetch/${targetDate}`;

      // Mock data check response (no data exists)
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      } as Response);

      // Mock auto-fetch response (successful)
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Successfully fetched Twitter data',
          items_processed: 2,
          items_stored: 2
        })
      } as Response);

      const { result } = renderHook(() => useTwitterData());

      // Trigger the check and auto-fetch
      await result.current.checkAndFetchData(targetDate);

      // Wait for auto-fetch to complete
      await waitFor(() => {
        expect(result.current.autoFetching).toBe(false);
      });

      // Verify the auto-fetch URL was called
      expect(mockFetch).toHaveBeenCalledWith(
        expectedFetchUrl,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      );
    });
  });

  describe('Auto-Fetch State Management', () => {
    it('should not trigger auto-fetch if data already attempted', async () => {
      const targetDate = '2025-08-24';

      // Mock data check response (no data exists)
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useTwitterData());

      // First call should trigger auto-fetch
      await result.current.checkAndFetchData(targetDate);
      
      // Wait for first auto-fetch to complete
      await waitFor(() => {
        expect(result.current.autoFetching).toBe(false);
      });

      const firstCallCount = mockFetch.mock.calls.length;
      
      // Reset mock to track second call
      mockFetch.mockClear();
      
      // Second call should not trigger auto-fetch (already attempted)
      await result.current.checkAndFetchData(targetDate);

      // Should only make the data check call, not the auto-fetch call
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/calendar/data_items/'),
        expect.any(Object)
      );
    });

    it('should handle auto-fetch errors gracefully', async () => {
      const targetDate = '2025-08-24';

      // Mock data check response (no data exists)
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      } as Response);

      // Mock auto-fetch response (Twitter API not configured)
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        text: async () => 'Twitter API not configured'
      } as Response);

      const { result } = renderHook(() => useTwitterData());

      // Trigger the check and auto-fetch
      await result.current.checkAndFetchData(targetDate);

      // Wait for auto-fetch to complete with error
      await waitFor(() => {
        expect(result.current.autoFetching).toBe(false);
        expect(result.current.fetchError).toBe('Twitter API not configured');
      });
    });
  });

  describe('State Reset Functionality', () => {
    it('should reset all state when resetState is called', () => {
      const { result } = renderHook(() => useTwitterData());

      // Trigger some state changes first
      result.current.resetState();

      expect(result.current.loading).toBe(false);
      expect(result.current.autoFetching).toBe(false);
      expect(result.current.fetchError).toBe(null);
      expect(result.current.fetchAttempted.size).toBe(0);
    });
  });
});