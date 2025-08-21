import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ExtendedNewsCard } from '../ExtendedNewsCard';

// Mock the custom hooks
vi.mock('../hooks/useLimitlessData', () => ({
  useLimitlessData: vi.fn(() => ({
    markdownContent: 'Test markdown content',
    loading: false,
    autoFetching: false,
    fetchError: null,
    fetchAttempted: new Set(),
    fetchData: vi.fn(),
    triggerAutoFetch: vi.fn(),
    resetState: vi.fn(),
    clearContent: vi.fn(),
  })),
}));

vi.mock('../hooks/useAutoFetch', () => ({
  useAutoFetch: vi.fn(),
}));

// Mock the MarkdownRenderer component
vi.mock('../MarkdownRenderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="markdown-renderer">{content}</div>,
}));

describe('ExtendedNewsCard - Optimized Version', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the component header correctly', () => {
    render(<ExtendedNewsCard selectedDate="2024-01-15" />);

    expect(screen.getByText('Limitless')).toBeInTheDocument();
    expect(screen.getByText("Today's Activity")).toBeInTheDocument();
  });

  it('displays markdown content when available', () => {
    render(<ExtendedNewsCard selectedDate="2024-01-15" />);

    expect(screen.getByTestId('markdown-renderer')).toBeInTheDocument();
    expect(screen.getByText('Test markdown content')).toBeInTheDocument();
  });

  it('shows loading state when loading', () => {
    const { useLimitlessData } = require('../hooks/useLimitlessData');
    useLimitlessData.mockReturnValue({
      markdownContent: '',
      loading: true,
      autoFetching: false,
      fetchError: null,
      fetchAttempted: new Set(),
    });

    render(<ExtendedNewsCard selectedDate="2024-01-15" />);

    expect(screen.getByText('Loading Limitless content...')).toBeInTheDocument();
  });

  it('shows auto-fetching state when auto-fetching', () => {
    const { useLimitlessData } = require('../hooks/useLimitlessData');
    useLimitlessData.mockReturnValue({
      markdownContent: '',
      loading: false,
      autoFetching: true,
      fetchError: null,
      fetchAttempted: new Set(),
    });

    render(<ExtendedNewsCard selectedDate="2024-01-15" />);

    expect(screen.getByText('Automatically fetching Limitless data...')).toBeInTheDocument();
  });

  it('shows error state when there is a fetch error', () => {
    const { useLimitlessData } = require('../hooks/useLimitlessData');
    useLimitlessData.mockReturnValue({
      markdownContent: '',
      loading: false,
      autoFetching: false,
      fetchError: 'Failed to fetch data',
      fetchAttempted: new Set(),
    });

    render(<ExtendedNewsCard selectedDate="2024-01-15" />);

    expect(screen.getByText('Failed to fetch data')).toBeInTheDocument();
  });

  it('shows no content message when no markdown content is available', () => {
    const { useLimitlessData } = require('../hooks/useLimitlessData');
    useLimitlessData.mockReturnValue({
      markdownContent: '',
      loading: false,
      autoFetching: false,
      fetchError: null,
      fetchAttempted: new Set(),
    });

    render(<ExtendedNewsCard selectedDate="2024-01-15" />);

    expect(screen.getByText('No Limitless content available')).toBeInTheDocument();
  });

  it('calls useAutoFetch hook with correct parameters', () => {
    const { useAutoFetch } = require('../hooks/useAutoFetch');
    const selectedDate = '2024-01-15';

    render(<ExtendedNewsCard selectedDate={selectedDate} />);

    expect(useAutoFetch).toHaveBeenCalledWith(selectedDate, expect.any(Object));
  });
});
