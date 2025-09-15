import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TwitterFetchButton } from '../TwitterFetchButton';

// Mock the useTwitterStatus hook
vi.mock('@/hooks/useTwitterStatus', () => ({
  useTwitterStatus: vi.fn()
}));

const mockUseTwitterStatus = vi.mocked(await import('@/hooks/useTwitterStatus')).useTwitterStatus;

// Mock global fetch
const mockFetch = vi.fn();
Object.defineProperty(global, 'fetch', {
  value: mockFetch,
  writable: true
});

// Mock console methods to avoid noise in tests
const originalConsoleLog = console.log;
const originalConsoleError = console.error;

describe('TwitterFetchButton', () => {
  const defaultProps = {
    selectedDate: '2024-01-15',
    onFetchComplete: vi.fn()
  };

  const defaultTwitterStatus = {
    canFetch: true,
    minutesUntil: 0,
    loading: false,
    error: null,
    lastFetchTime: null,
    checkStatus: vi.fn(),
    resetError: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
    console.log = vi.fn();
    console.error = vi.fn();
    
    // Default mock implementation
    mockUseTwitterStatus.mockReturnValue(defaultTwitterStatus);
    mockFetch.mockClear();
  });

  afterEach(() => {
    console.log = originalConsoleLog;
    console.error = originalConsoleError;
  });

  describe('Button Text Display', () => {
    it('shows "Fetch now" when fetch is available', () => {
      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Fetch now')).toBeInTheDocument();
    });

    it('shows "Fetching..." when fetch is in progress', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Fetched successfully' })
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);
      
      expect(screen.getByText('Fetching...')).toBeInTheDocument();
    });

    it('shows minutes remaining when rate limited', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        canFetch: false,
        minutesUntil: 15
      });

      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Next fetch available in 15 minutes')).toBeInTheDocument();
    });

    it('shows hours and minutes when rate limited for over an hour', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        canFetch: false,
        minutesUntil: 125
      });

      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Next fetch available in 2h 5m')).toBeInTheDocument();
    });

    it('shows "Checking status..." when status is loading', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        loading: true
      });

      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Checking status...')).toBeInTheDocument();
    });
  });

  describe('Button Disabled State', () => {
    it('is enabled when fetch is available', () => {
      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Fetch now')).not.toBeDisabled();
    });

    it('is disabled when rate limited', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        canFetch: false,
        minutesUntil: 15
      });

      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Next fetch available in 15 minutes')).toBeDisabled();
    });

    it('is disabled when status is loading', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        loading: true
      });

      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Checking status...')).toBeDisabled();
    });
  });

  describe('Fetch API Interactions', () => {
    it('calls GET status API on mount', () => {
      render(<TwitterFetchButton {...defaultProps} />);
      expect(mockUseTwitterStatus).toHaveBeenCalledWith('2024-01-15');
    });

    it('calls POST fetch API when button clicked', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Fetched successfully' })
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/calendar/twitter/fetch/2024-01-15',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            }
          }
        );
      });
    });

    it('calls checkStatus and onFetchComplete on successful fetch', async () => {
      const mockCheckStatus = vi.fn();
      const mockOnFetchComplete = vi.fn();
      
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        checkStatus: mockCheckStatus
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Fetched successfully' })
      });

      render(<TwitterFetchButton {...defaultProps} onFetchComplete={mockOnFetchComplete} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(mockCheckStatus).toHaveBeenCalled();
        expect(mockOnFetchComplete).toHaveBeenCalled();
      });
    });
  });

  describe('Error Handling', () => {
    it('shows error message for 404 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Not found'
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Twitter source not available')).toBeInTheDocument();
      });
    });

    it('shows error message for 503 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        text: async () => 'Service unavailable'
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Twitter API not configured')).toBeInTheDocument();
      });
    });

    it('shows error message and calls checkStatus for 429 response', async () => {
      const mockCheckStatus = vi.fn();
      
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        checkStatus: mockCheckStatus
      });

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        statusText: 'Too Many Requests',
        text: async () => 'Rate limited'
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Rate limited - please wait before trying again')).toBeInTheDocument();
        expect(mockCheckStatus).toHaveBeenCalled();
      });
    });

    it('shows error message for 500 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'Internal error'
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Failed to fetch: 500 Internal Server Error')).toBeInTheDocument();
      });
    });

    it('shows network error message for fetch failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Network error: Network error')).toBeInTheDocument();
      });
    });

    it('shows status error from useTwitterStatus hook', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        error: 'Status check failed'
      });

      render(<TwitterFetchButton {...defaultProps} />);
      expect(screen.getByText('Status check failed')).toBeInTheDocument();
    });

    it('handles unsuccessful API response with error message', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: false, message: 'Custom error message' })
      });

      render(<TwitterFetchButton {...defaultProps} />);
      
      const button = screen.getByText('Fetch now');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Custom error message')).toBeInTheDocument();
      });
    });
  });

  describe('Button Variants', () => {
    it('uses default variant when fetch is available', () => {
      render(<TwitterFetchButton {...defaultProps} />);
      const button = screen.getByText('Fetch now');
      expect(button).toHaveClass('bg-primary'); // Assuming default variant has primary background
    });

    it('uses secondary variant when rate limited', () => {
      mockUseTwitterStatus.mockReturnValue({
        ...defaultTwitterStatus,
        canFetch: false,
        minutesUntil: 15
      });

      render(<TwitterFetchButton {...defaultProps} />);
      const button = screen.getByText('Next fetch available in 15 minutes');
      expect(button).toHaveClass('bg-secondary'); // Assuming secondary variant has secondary background
    });
  });
});