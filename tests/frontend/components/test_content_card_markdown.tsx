import { render, screen } from '@testing-library/react';
import { ContentCard, LimitlessContentData } from '../frontend/src/components/ContentCard';
import '@testing-library/jest-dom';

describe('ContentCard Markdown Rendering', () => {
  /**
   * Test that markdown bullet points are properly parsed and rendered
   * without showing raw markdown characters
   */
  it('should render markdown content without showing bullet point characters', () => {
    const mockData: LimitlessContentData = {
      type: 'limitless',
      id: 'test-1',
      title: 'Test Conversation',
      timestamp: '2024-01-01T12:00:00Z',
      displayConversation: [
        {
          content: '- First bullet point\n- Second bullet point\n- Third bullet point',
          speaker: 'User',
          timestamp: '2024-01-01T12:00:00Z',
          type: 'message'
        }
      ],
      semanticClusters: {},
      semanticMetadata: {
        totalLines: 3,
        clusteredLines: 0,
        uniqueThemes: [],
        semanticDensity: 0,
        clustersFound: 0
      }
    };

    const { container } = render(<ContentCard data={mockData} />);
    
    // Check that raw markdown characters are not visible in the rendered output
    const contentElement = container.querySelector('.prose');
    expect(contentElement).toBeInTheDocument();
    
    // The raw markdown bullet characters should not be visible
    const textContent = contentElement?.textContent || '';
    expect(textContent).not.toContain('- First bullet point');
    expect(textContent).not.toContain('- Second bullet point');
    
    // But the actual content should be present
    expect(textContent).toContain('First bullet point');
    expect(textContent).toContain('Second bullet point');
    expect(textContent).toContain('Third bullet point');
  });

  /**
   * Test that other markdown syntax is properly rendered
   */
  it('should render other markdown elements correctly', () => {
    const mockData: LimitlessContentData = {
      type: 'limitless',
      id: 'test-2',
      title: 'Test Markdown Parsing',
      timestamp: '2024-01-01T12:00:00Z',
      displayConversation: [
        {
          content: '**Bold text** and *italic text* with a [link](https://example.com)',
          speaker: 'User',
          timestamp: '2024-01-01T12:00:00Z',
          type: 'message'
        }
      ],
      semanticClusters: {},
      semanticMetadata: {
        totalLines: 1,
        clusteredLines: 0,
        uniqueThemes: [],
        semanticDensity: 0,
        clustersFound: 0
      }
    };

    const { container } = render(<ContentCard data={mockData} />);
    
    // Check for bold text (should render as <strong>)
    const strongElement = container.querySelector('strong');
    expect(strongElement).toBeInTheDocument();
    expect(strongElement?.textContent).toBe('Bold text');
    
    // Check for italic text (should render as <em>)
    const emElement = container.querySelector('em');
    expect(emElement).toBeInTheDocument();
    expect(emElement?.textContent).toBe('italic text');
    
    // Check for link (should render as <a>)
    const linkElement = container.querySelector('a');
    expect(linkElement).toBeInTheDocument();
    expect(linkElement?.getAttribute('href')).toBe('https://example.com');
    expect(linkElement?.textContent).toBe('link');
  });

  /**
   * Test edge case with asterisk bullets
   */
  it('should handle asterisk bullet points correctly', () => {
    const mockData: LimitlessContentData = {
      type: 'limitless',
      id: 'test-3',
      title: 'Test Asterisk Bullets',
      timestamp: '2024-01-01T12:00:00Z',
      displayConversation: [
        {
          content: '* Item one\n* Item two\n* Item three',
          speaker: 'User',
          timestamp: '2024-01-01T12:00:00Z',
          type: 'message'
        }
      ],
      semanticClusters: {},
      semanticMetadata: {
        totalLines: 3,
        clusteredLines: 0,
        uniqueThemes: [],
        semanticDensity: 0,
        clustersFound: 0
      }
    };

    const { container } = render(<ContentCard data={mockData} />);
    
    const contentElement = container.querySelector('.prose');
    const textContent = contentElement?.textContent || '';
    
    // Asterisk characters should not be visible
    expect(textContent).not.toContain('* Item one');
    expect(textContent).not.toContain('* Item two');
    
    // Content should be present
    expect(textContent).toContain('Item one');
    expect(textContent).toContain('Item two');
    expect(textContent).toContain('Item three');
  });

  /**
   * Test that replacedOriginal content also uses markdown rendering
   */
  it('should render replacedOriginal content with markdown parsing', () => {
    const mockData: LimitlessContentData = {
      type: 'limitless',
      id: 'test-4',
      title: 'Test Replaced Content',
      timestamp: '2024-01-01T12:00:00Z',
      displayConversation: [
        {
          content: 'Current content',
          speaker: 'User',
          timestamp: '2024-01-01T12:00:00Z',
          type: 'message',
          replacedOriginal: '- Original bullet point'
        }
      ],
      semanticClusters: {},
      semanticMetadata: {
        totalLines: 1,
        clusteredLines: 0,
        uniqueThemes: [],
        semanticDensity: 0,
        clustersFound: 0
      }
    };

    const { container } = render(<ContentCard data={mockData} />);
    
    // Check that replaced original content doesn't show raw markdown
    const replacedContent = container.querySelector('.text-muted-foreground');
    expect(replacedContent).toBeInTheDocument();
    
    const replacedText = replacedContent?.textContent || '';
    expect(replacedText).toContain('Original bullet point');
    expect(replacedText).not.toContain('- Original bullet point');
  });
});