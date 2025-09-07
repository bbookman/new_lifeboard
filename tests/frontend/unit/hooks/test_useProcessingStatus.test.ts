import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { useProcessingStatus } from '../../../../frontend/src/hooks/useProcessingStatus';

// Mock the API client
vi.mock('../../../../frontend/src/lib/api', () => ({
  getProcessingQueue: vi.fn(),
  queryKeys: {
    processing: {
      queue: ['processing', 'queue'] as const
    }
  }
}));

import { getProcessingQueue } from '../../../../frontend/src/lib/api';

const mockGetProcessingQueue = vi.mocked(getProcessingQueue);

// Sample processing stats data
const mockProcessingStats = {
  total_days: 30,
  completed_days: 25,
  pending_days: 3,
  processing_days: 1,
  failed_days: 1,
  active_processing: true,
  last_updated: "2024-01-15T10:30:00Z"
};

// Create wrapper for React Query
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('useProcessingStatus Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetProcessingQueue.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Basic Functionality', () => {
    it('should fetch processing statistics successfully', async () => {
      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      // Initially should be loading
      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();

      // Wait for data to load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify data structure
      expect(result.current.data).toEqual(mockProcessingStats);
      expect(result.current.error).toBeNull();
      expect(mockGetProcessingQueue).toHaveBeenCalledTimes(1);
    });

    it('should return correct data structure', async () => {
      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const data = result.current.data;
      
      // Verify all required fields are present
      expect(data).toHaveProperty('total_days');
      expect(data).toHaveProperty('completed_days');
      expect(data).toHaveProperty('pending_days');
      expect(data).toHaveProperty('processing_days');
      expect(data).toHaveProperty('failed_days');
      expect(data).toHaveProperty('active_processing');
      expect(data).toHaveProperty('last_updated');

      // Verify data types
      expect(typeof data?.total_days).toBe('number');
      expect(typeof data?.completed_days).toBe('number');
      expect(typeof data?.pending_days).toBe('number');
      expect(typeof data?.processing_days).toBe('number');
      expect(typeof data?.failed_days).toBe('number');
      expect(typeof data?.active_processing).toBe('boolean');
      expect(typeof data?.last_updated).toBe('string');
    });

    it('should handle loading states correctly', async () => {
      // Create a pending promise to simulate loading
      let resolvePromise: (value: any) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      
      mockGetProcessingQueue.mockReturnValue(pendingPromise);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      // Should be loading initially
      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
      expect(result.current.error).toBeNull();

      // Resolve the promise
      resolvePromise!(mockProcessingStats);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockProcessingStats);
    });

    it('should handle error states correctly', async () => {
      const errorMessage = 'Failed to fetch processing status';
      mockGetProcessingQueue.mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeUndefined();
      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('Polling Behavior', () => {
    it('should poll data every 5 seconds', async () => {
      vi.useFakeTimers();
      
      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockGetProcessingQueue).toHaveBeenCalledTimes(1);

      // Fast-forward 5 seconds
      vi.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockGetProcessingQueue).toHaveBeenCalledTimes(2);
      });

      // Fast-forward another 5 seconds
      vi.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockGetProcessingQueue).toHaveBeenCalledTimes(3);
      });

      vi.useRealTimers();
    });

    it('should provide last successful poll timestamp', async () => {
      const currentTime = Date.now();
      vi.setSystemTime(currentTime);

      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should have a recent timestamp for last successful poll
      expect(result.current.lastSuccessfulPoll).toBeDefined();
      const timeDiff = Date.now() - (result.current.lastSuccessfulPoll || 0);
      expect(timeDiff).toBeLessThan(1000); // Within 1 second

      vi.useRealTimers();
    });

    it('should not update last successful poll timestamp on error', async () => {
      vi.useFakeTimers();
      const currentTime = Date.now();
      vi.setSystemTime(currentTime);

      // First successful call
      mockGetProcessingQueue.mockResolvedValueOnce(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const firstSuccessTimestamp = result.current.lastSuccessfulPoll;
      expect(firstSuccessTimestamp).toBeDefined();

      // Second call fails
      mockGetProcessingQueue.mockRejectedValueOnce(new Error('API Error'));

      // Fast-forward 5 seconds to trigger refetch
      vi.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockGetProcessingQueue).toHaveBeenCalledTimes(2);
      });

      // Last successful poll timestamp should remain unchanged
      expect(result.current.lastSuccessfulPoll).toBe(firstSuccessTimestamp);

      vi.useRealTimers();
    });

    it('should continue polling after errors', async () => {
      vi.useFakeTimers();

      // First call fails, second succeeds
      mockGetProcessingQueue
        .mockRejectedValueOnce(new Error('Temporary error'))
        .mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      // Wait for initial (failed) fetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(mockGetProcessingQueue).toHaveBeenCalledTimes(1);

      // Fast-forward 5 seconds
      vi.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockGetProcessingQueue).toHaveBeenCalledTimes(2);
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockProcessingStats);
        expect(result.current.error).toBeNull();
      });

      vi.useRealTimers();
    });
  });

  describe('Retry Logic', () => {
    it('should provide retry functionality', async () => {
      mockGetProcessingQueue.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(mockGetProcessingQueue).toHaveBeenCalledTimes(1);

      // Mock successful retry
      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      // Trigger retry
      result.current.refetch();

      await waitFor(() => {
        expect(result.current.data).toEqual(mockProcessingStats);
        expect(result.current.error).toBeNull();
      });

      expect(mockGetProcessingQueue).toHaveBeenCalledTimes(2);
    });

    it('should handle retry failures gracefully', async () => {
      const errorMessage = 'Persistent error';
      mockGetProcessingQueue.mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();

      // Retry also fails
      result.current.refetch();

      await waitFor(() => {
        expect(result.current.error?.message).toBe(errorMessage);
      });

      expect(mockGetProcessingQueue).toHaveBeenCalledTimes(2);
    });
  });

  describe('Data Updates', () => {
    it('should reflect real-time data changes through polling', async () => {
      vi.useFakeTimers();

      const initialStats = { ...mockProcessingStats, completed_days: 25 };
      const updatedStats = { ...mockProcessingStats, completed_days: 26 };

      mockGetProcessingQueue
        .mockResolvedValueOnce(initialStats)
        .mockResolvedValue(updatedStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      // Wait for initial data
      await waitFor(() => {
        expect(result.current.data?.completed_days).toBe(25);
      });

      // Fast-forward to trigger next poll
      vi.advanceTimersByTime(5000);

      // Wait for updated data
      await waitFor(() => {
        expect(result.current.data?.completed_days).toBe(26);
      });

      vi.useRealTimers();
    });

    it('should handle active processing state changes', async () => {
      vi.useFakeTimers();

      const activeStats = { ...mockProcessingStats, active_processing: true, processing_days: 1 };
      const inactiveStats = { ...mockProcessingStats, active_processing: false, processing_days: 0 };

      mockGetProcessingQueue
        .mockResolvedValueOnce(activeStats)
        .mockResolvedValue(inactiveStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      // Initially active
      await waitFor(() => {
        expect(result.current.data?.active_processing).toBe(true);
      });

      // Fast-forward to next poll
      vi.advanceTimersByTime(5000);

      // Now inactive
      await waitFor(() => {
        expect(result.current.data?.active_processing).toBe(false);
        expect(result.current.data?.processing_days).toBe(0);
      });

      vi.useRealTimers();
    });
  });

  describe('Performance and Efficiency', () => {
    it('should not cause excessive re-renders', async () => {
      let renderCount = 0;
      
      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => {
        renderCount++;
        return useProcessingStatus();
      }, {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should have reasonable number of renders (initial + success)
      expect(renderCount).toBeLessThan(5);
    });

    it('should use correct React Query configuration', async () => {
      mockGetProcessingQueue.mockResolvedValue(mockProcessingStats);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify the hook maintains the expected interface
      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('refetch');
      expect(result.current).toHaveProperty('lastSuccessfulPoll');
    });
  });

  describe('Error Scenarios', () => {
    it('should handle API timeout errors', async () => {
      const timeoutError = new Error('Request timeout');
      timeoutError.name = 'TimeoutError';
      
      mockGetProcessingQueue.mockRejectedValue(timeoutError);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.name).toBe('TimeoutError');
    });

    it('should handle network connectivity issues', async () => {
      const networkError = new Error('Network unavailable');
      networkError.name = 'NetworkError';
      
      mockGetProcessingQueue.mockRejectedValue(networkError);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.data).toBeUndefined();
    });

    it('should handle malformed API responses gracefully', async () => {
      // Return invalid data structure
      const invalidData = { invalid: 'data' };
      mockGetProcessingQueue.mockResolvedValue(invalidData as any);

      const { result } = renderHook(() => useProcessingStatus(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should still return the data even if malformed
      expect(result.current.data).toEqual(invalidData);
      expect(result.current.error).toBeNull();
    });
  });
});