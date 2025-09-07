import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { ProcessingStatus } from '../../../../frontend/src/components/ProcessingStatus';

// Mock the useProcessingStatus hook
vi.mock('../../../../frontend/src/hooks/useProcessingStatus', () => ({
  useProcessingStatus: vi.fn()
}));

import { useProcessingStatus } from '../../../../frontend/src/hooks/useProcessingStatus';
const mockUseProcessingStatus = vi.mocked(useProcessingStatus);

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

describe('ProcessingStatus Component - Simplified HTTP Version', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProcessingStatus.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Basic Rendering', () => {
    it('should render component with polling-based data', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should display processing statistics
      expect(screen.getByText('Processing Queue Status')).toBeInTheDocument();
      expect(screen.getByText('30')).toBeInTheDocument(); // total_days
      expect(screen.getByText('25')).toBeInTheDocument(); // completed_days
      expect(screen.getByText('3')).toBeInTheDocument();  // pending_days
      expect(screen.getByText('1')).toBeInTheDocument();  // processing_days
      expect(screen.getByText('1')).toBeInTheDocument();  // failed_days
    });

    it('should display loading state correctly', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('Loading processing status...')).toBeInTheDocument();
    });

    it('should display error state correctly', () => {
      const errorMessage = 'Failed to fetch processing status';
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error(errorMessage),
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('Error loading processing status')).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('should display success state with all statistics', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Check all statistical fields are displayed
      expect(screen.getByText('Total Days:')).toBeInTheDocument();
      expect(screen.getByText('Completed:')).toBeInTheDocument();
      expect(screen.getByText('Pending:')).toBeInTheDocument();
      expect(screen.getByText('Processing:')).toBeInTheDocument();
      expect(screen.getByText('Failed:')).toBeInTheDocument();

      // Check values
      expect(screen.getByText('30')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  describe('Polling Health Indicator', () => {
    it('should show green indicator for recent successful poll', () => {
      const recentTime = Date.now() - 2000; // 2 seconds ago
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: recentTime
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should show healthy polling status
      const healthIndicator = screen.getByTestId('polling-health-indicator');
      expect(healthIndicator).toHaveClass('bg-green-500');
    });

    it('should show red indicator for stale poll', () => {
      const staleTime = Date.now() - 30000; // 30 seconds ago
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: staleTime
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should show stale polling status
      const healthIndicator = screen.getByTestId('polling-health-indicator');
      expect(healthIndicator).toHaveClass('bg-red-500');
    });

    it('should show yellow indicator for no poll data', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should show unknown polling status
      const healthIndicator = screen.getByTestId('polling-health-indicator');
      expect(healthIndicator).toHaveClass('bg-yellow-500');
    });

    it('should display last poll time text', () => {
      const pollTime = Date.now() - 5000; // 5 seconds ago
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: pollTime
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
      expect(screen.getByText(/seconds ago/)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('should handle refresh button click', async () => {
      const mockRefetch = vi.fn();
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      fireEvent.click(refreshButton);

      expect(mockRefetch).toHaveBeenCalledTimes(1);
    });

    it('should handle retry button on error', async () => {
      const mockRefetch = vi.fn();
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Network error'),
        refetch: mockRefetch,
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      expect(mockRefetch).toHaveBeenCalledTimes(1);
    });

    it('should handle trigger processing button', async () => {
      // Mock fetch for trigger processing API call
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true })
      });
      global.fetch = mockFetch;

      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      const triggerButton = screen.getByRole('button', { name: /trigger processing/i });
      fireEvent.click(triggerButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/processing/trigger'),
          expect.objectContaining({
            method: 'POST'
          })
        );
      });
    });

    it('should disable buttons during loading', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // All interactive buttons should be disabled during loading
      const buttons = screen.queryAllByRole('button');
      buttons.forEach(button => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('Active Processing State', () => {
    it('should show processing indicator when active', () => {
      const activeStats = { ...mockProcessingStats, active_processing: true };
      mockUseProcessingStatus.mockReturnValue({
        data: activeStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText(/Processing Active/i)).toBeInTheDocument();
      expect(screen.getByTestId('active-processing-indicator')).toBeInTheDocument();
    });

    it('should show idle state when not active', () => {
      const inactiveStats = { ...mockProcessingStats, active_processing: false, processing_days: 0 };
      mockUseProcessingStatus.mockReturnValue({
        data: inactiveStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText(/Idle/i)).toBeInTheDocument();
      expect(screen.queryByTestId('active-processing-indicator')).not.toBeInTheDocument();
    });

    it('should update active state dynamically', () => {
      const { rerender } = render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Initially active
      mockUseProcessingStatus.mockReturnValue({
        data: { ...mockProcessingStats, active_processing: true },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      rerender(<ProcessingStatus />);
      expect(screen.getByText(/Processing Active/i)).toBeInTheDocument();

      // Then becomes idle
      mockUseProcessingStatus.mockReturnValue({
        data: { ...mockProcessingStats, active_processing: false, processing_days: 0 },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      rerender(<ProcessingStatus />);
      expect(screen.getByText(/Idle/i)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should handle HTTP request failures gracefully', async () => {
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('HTTP 500: Internal Server Error'),
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('Error loading processing status')).toBeInTheDocument();
      expect(screen.getByText('HTTP 500: Internal Server Error')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('should handle network connectivity issues', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Network request failed'),
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('Network request failed')).toBeInTheDocument();
    });

    it('should recover from error state when data becomes available', () => {
      const { rerender } = render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Initially error state
      mockUseProcessingStatus.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Service unavailable'),
        refetch: vi.fn(),
        lastSuccessfulPoll: undefined
      });

      rerender(<ProcessingStatus />);
      expect(screen.getByText('Error loading processing status')).toBeInTheDocument();

      // Then successful state
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      rerender(<ProcessingStatus />);
      expect(screen.queryByText('Error loading processing status')).not.toBeInTheDocument();
      expect(screen.getByText('Processing Queue Status')).toBeInTheDocument();
    });
  });

  describe('Data Validation and Edge Cases', () => {
    it('should handle zero values gracefully', () => {
      const zeroStats = {
        total_days: 0,
        completed_days: 0,
        pending_days: 0,
        processing_days: 0,
        failed_days: 0,
        active_processing: false,
        last_updated: "2024-01-15T10:30:00Z"
      };

      mockUseProcessingStatus.mockReturnValue({
        data: zeroStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText(/Idle/i)).toBeInTheDocument();
    });

    it('should handle large numbers correctly', () => {
      const largeStats = {
        total_days: 9999,
        completed_days: 8888,
        pending_days: 777,
        processing_days: 66,
        failed_days: 268,
        active_processing: true,
        last_updated: "2024-01-15T10:30:00Z"
      };

      mockUseProcessingStatus.mockReturnValue({
        data: largeStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('9999')).toBeInTheDocument();
      expect(screen.getByText('8888')).toBeInTheDocument();
      expect(screen.getByText('777')).toBeInTheDocument();
    });

    it('should handle missing data gracefully', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: null as any,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should show some fallback content
      expect(screen.getByText(/No data available/i)).toBeInTheDocument();
    });
  });

  describe('Component Integration', () => {
    it('should use useProcessingStatus hook correctly', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Hook should be called once on mount
      expect(mockUseProcessingStatus).toHaveBeenCalledTimes(1);
    });

    it('should not have any WebSocket dependencies', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should not reference any WebSocket-related elements
      expect(screen.queryByText(/WebSocket/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Connection/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Real-time/i)).not.toBeInTheDocument();
    });

    it('should display polling-based status indicators', () => {
      mockUseProcessingStatus.mockReturnValue({
        data: mockProcessingStats,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        lastSuccessfulPoll: Date.now()
      });

      render(
        <ProcessingStatus />,
        { wrapper: createWrapper() }
      );

      // Should show polling health indicator
      expect(screen.getByTestId('polling-health-indicator')).toBeInTheDocument();
      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    });
  });
});