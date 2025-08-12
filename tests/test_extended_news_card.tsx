import { render, screen, waitFor } from '@testing-library/react';
import { ExtendedNewsCard } from '../frontend/src/components/ExtendedNewsCard';
import '@testing-library/jest-dom';

// Mock fetch responses
global.fetch = jest.fn();

describe('ExtendedNewsCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should render loading state initially', () => {
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => []
    });

    render(<ExtendedNewsCard />);
    expect(screen.getByText('Loading Limitless content...')).toBeInTheDocument();
  });

  it('should render markdown content with proper formatting', async () => {
    const mockMarkdownContent = `# Main Heading
## Subheading
### Third Level

This is a paragraph with **bold** and *italic* text.

- Bullet item 1
- Bullet item 2

1. Numbered item 1
2. Numbered item 2

\`inline code\`

\`\`\`javascript
const test = "code block";
\`\`\`

> This is a blockquote

[Link text](https://example.com)

---
`;

    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => [{
        id: 'test-1',
        namespace: 'limitless',
        days_date: '2025-08-11',
        metadata: {
          cleaned_markdown: mockMarkdownContent
        }
      }]
    });

    render(<ExtendedNewsCard />);

    await waitFor(() => {
      // Check for headings with proper styling
      const h1 = screen.getByRole('heading', { level: 1, name: 'Main Heading' });
      expect(h1).toHaveClass('text-2xl', 'font-bold', 'text-newspaper-headline');

      const h2 = screen.getByRole('heading', { level: 2, name: 'Subheading' });
      expect(h2).toHaveClass('text-xl', 'font-bold', 'text-newspaper-headline');

      const h3 = screen.getByRole('heading', { level: 3, name: 'Third Level' });
      expect(h3).toHaveClass('text-lg', 'font-bold', 'text-newspaper-headline');

      // Check for lists
      expect(screen.getByText('Bullet item 1')).toBeInTheDocument();
      expect(screen.getByText('Numbered item 1')).toBeInTheDocument();

      // Check for code elements
      expect(screen.getByText('inline code')).toHaveClass('bg-gray-100');
      expect(screen.getByText('const test = "code block";')).toBeInTheDocument();

      // Check for blockquote
      expect(screen.getByText('This is a blockquote')).toBeInTheDocument();

      // Check for link
      const link = screen.getByRole('link', { name: 'Link text' });
      expect(link).toHaveAttribute('href', 'https://example.com');
      expect(link).toHaveClass('text-blue-600');
    });
  });

  it('should handle fallback to most recent data when today has no data', async () => {
    // First call returns empty array for today
    (fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => []
      })
      // Second call gets days with data
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          all: ['2025-08-10', '2025-08-09']
        })
      })
      // Third call gets data for most recent date
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{
          id: 'test-1',
          namespace: 'limitless',
          days_date: '2025-08-10',
          metadata: {
            cleaned_markdown: '## Historical Data'
          }
        }]
      });

    render(<ExtendedNewsCard />);

    await waitFor(() => {
      expect(screen.getByText(/Data from/)).toBeInTheDocument();
      expect(screen.getByText('Historical Data')).toBeInTheDocument();
    });
  });

  it('should display no data message when no limitless data exists', async () => {
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => []
    });

    render(<ExtendedNewsCard />);

    await waitFor(() => {
      expect(screen.getByText('No Limitless data available.')).toBeInTheDocument();
    });
  });

  it('should handle fetch errors gracefully', async () => {
    (fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    render(<ExtendedNewsCard />);

    await waitFor(() => {
      expect(screen.getByText('Error loading Limitless data.')).toBeInTheDocument();
    });
  });

  it('should use correct priority for markdown content sources', async () => {
    const testCases = [
      {
        name: 'cleaned_markdown priority',
        data: {
          metadata: {
            cleaned_markdown: 'Cleaned content',
            markdown: 'Regular markdown',
            original_lifelog: { markdown: 'Original markdown' }
          },
          content: 'Plain content'
        },
        expected: 'Cleaned content'
      },
      {
        name: 'markdown fallback',
        data: {
          metadata: {
            markdown: 'Regular markdown',
            original_lifelog: { markdown: 'Original markdown' }
          },
          content: 'Plain content'
        },
        expected: 'Regular markdown'
      },
      {
        name: 'original_lifelog fallback',
        data: {
          metadata: {
            original_lifelog: { markdown: 'Original markdown' }
          },
          content: 'Plain content'
        },
        expected: 'Original markdown'
      },
      {
        name: 'content fallback',
        data: {
          content: 'Plain content'
        },
        expected: 'Plain content'
      }
    ];

    for (const testCase of testCases) {
      jest.clearAllMocks();
      
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [{
          id: 'test-1',
          namespace: 'limitless',
          days_date: '2025-08-11',
          ...testCase.data
        }]
      });

      const { unmount } = render(<ExtendedNewsCard />);

      await waitFor(() => {
        expect(screen.getByText(testCase.expected)).toBeInTheDocument();
      }, { timeout: 3000 });

      unmount();
    }
  });
});