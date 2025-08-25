import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useLimitlessData } from '../useLimitlessData';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('useLimitlessData Hook - URL Endpoint Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('API Endpoint URL Correctness', () => {
    it('should use correct URL for data fetching', async () => {
      const targetDate = '2025-08-24';
      const expectedUrl = `http://localhost:8000/calendar/data_items/${targetDate}?namespaces=limitless&_t=`;

      // Mock successful response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useLimitlessData());

      // Trigger fetch
      await result.current.fetchData(targetDate);

      // Verify correct URL was called
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(`http://localhost:8000/calendar/data_items/${targetDate}?namespaces=limitless&_t=`),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
          })
        })
      );

      // Verify URL does NOT contain the incorrect patterns
      const calledUrl = mockFetch.mock.calls[0][0];
      expect(calledUrl).not.toContain('/calendar/api/data_items');
      expect(calledUrl).toContain('/calendar/data_items');
    });

    it('should use correct URL for automatic fetch', async () => {
      const targetDate = '2025-08-24';
      const expectedFetchUrl = `http://localhost:8000/calendar/limitless/fetch/${targetDate}`;

      // Mock failed data fetch to trigger auto fetch
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [] // Empty data triggers auto-fetch
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true, message: 'Fetched successfully' })
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [
            {
              id: 'test-id',
              metadata: {
                cleaned_markdown: 'Test markdown content'
              }
            }
          ]
        } as Response);

      const { result } = renderHook(() => useLimitlessData());

      // Trigger auto-fetch
      await result.current.triggerAutoFetch(targetDate);

      // Wait for all async operations
      await waitFor(() => {
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

      // Verify URL does NOT contain the incorrect patterns
      const fetchCalls = mockFetch.mock.calls;
      const autoFetchCall = fetchCalls.find(call => call[0].includes('/limitless/fetch/'));
      expect(autoFetchCall).toBeDefined();
      expect(autoFetchCall![0]).not.toContain('/calendar/api/limitless/fetch');
      expect(autoFetchCall![0]).toContain('/calendar/limitless/fetch');
    });

    it('should use correct URL in refetch after successful auto-fetch', async () => {
      const targetDate = '2025-08-24';
      
      // Mock auto-fetch success, then refetch
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [{ id: 'test', metadata: { cleaned_markdown: 'test' } }]
        } as Response);

      const { result } = renderHook(() => useLimitlessData());

      await result.current.triggerAutoFetch(targetDate);

      // Wait for the delayed refetch
      await new Promise(resolve => setTimeout(resolve, 1100));

      await waitFor(() => {
        const refetchCall = mockFetch.mock.calls.find(call => 
          call[0].includes('/calendar/data_items') && 
          call[0].includes('namespaces=limitless')
        );
        expect(refetchCall).toBeDefined();
        expect(refetchCall![0]).not.toContain('/calendar/api/data_items');
        expect(refetchCall![0]).toContain('/calendar/data_items');
      });
    });
  });

  describe('URL Pattern Anti-Regression Tests', () => {
    it('should never use /calendar/api/data_items pattern', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useLimitlessData());
      await result.current.fetchData(targetDate);

      // Check all fetch calls for the incorrect pattern
      mockFetch.mock.calls.forEach(call => {
        expect(call[0]).not.toContain('/calendar/api/data_items');
      });
    });

    it('should never use /calendar/api/limitless/fetch pattern', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      } as Response);

      const { result } = renderHook(() => useLimitlessData());
      await result.current.triggerAutoFetch(targetDate);

      // Check all fetch calls for the incorrect pattern
      mockFetch.mock.calls.forEach(call => {
        expect(call[0]).not.toContain('/calendar/api/limitless/fetch');
      });
    });

    it('should always use correct base URL format', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useLimitlessData());
      
      // Test both methods
      await result.current.fetchData(targetDate);
      await result.current.triggerAutoFetch(targetDate);

      // Verify all URLs start with correct base
      mockFetch.mock.calls.forEach(call => {
        expect(call[0]).toMatch(/^http:\/\/localhost:8000\//);
      });
    });
  });

  describe('Error Handling with Correct URLs', () => {
    it('should handle 404 errors with correct URL format', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404
      } as Response);

      const { result } = renderHook(() => useLimitlessData());
      await result.current.fetchData(targetDate);

      // Verify it used the correct URL even for failed requests
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/calendar/data_items/'),
        expect.any(Object)
      );
      expect(mockFetch).not.toHaveBeenCalledWith(
        expect.stringContaining('/calendar/api/data_items/'),
        expect.any(Object)
      );
    });

    it('should handle network errors with correct URL format', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useLimitlessData());
      await result.current.fetchData(targetDate);

      // Verify it attempted the correct URL even for network errors
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/calendar/data_items/'),
        expect.any(Object)
      );
    });
  });

  describe('Cache Busting Parameter Validation', () => {
    it('should include cache-busting timestamp parameter', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useLimitlessData());
      await result.current.fetchData(targetDate);

      const calledUrl = mockFetch.mock.calls[0][0];
      expect(calledUrl).toMatch(/&_t=\d+$/);
    });

    it('should use different timestamps for multiple calls', async () => {
      const targetDate = '2025-08-24';
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => []
      } as Response);

      const { result } = renderHook(() => useLimitlessData());
      
      await result.current.fetchData(targetDate);
      await new Promise(resolve => setTimeout(resolve, 10)); // Small delay
      await result.current.fetchData(targetDate);

      expect(mockFetch).toHaveBeenCalledTimes(2);
      
      const firstUrl = mockFetch.mock.calls[0][0];
      const secondUrl = mockFetch.mock.calls[1][0];
      
      const firstTimestamp = firstUrl.match(/_t=(\d+)$/)?.[1];
      const secondTimestamp = secondUrl.match(/_t=(\d+)$/)?.[1];
      
      expect(firstTimestamp).toBeDefined();
      expect(secondTimestamp).toBeDefined();
      expect(firstTimestamp).not.toEqual(secondTimestamp);
    });
  });
});