import { Badge } from '@/components/ui/badge';
import { useLimitlessData } from '../hooks/useLimitlessData';
import { useAutoFetch } from '../hooks/useAutoFetch';
import { MarkdownRenderer } from './MarkdownRenderer';
import { useEffect } from 'react';

interface ExtendedNewsCardProps {
  headline: string;
  summary: string;
  author: string;
  timestamp: string;
  category: string;
  readTime: string;
  breaking?: boolean;
  selectedDate?: string;
  onContentLoad?: (content: string) => void;
}

/**
 * ExtendedNewsCard component - Optimized version
 * Displays limitless markdown content using custom hooks for better separation of concerns
 * This component is used within a Card wrapper in NewsSection, so no outer Card needed
 */
export const ExtendedNewsCard = ({
  selectedDate,
  onContentLoad,
}: Pick<ExtendedNewsCardProps, 'selectedDate' | 'onContentLoad'>) => {
  // Use custom hooks for data management and auto-fetch logic
  const limitlessData = useLimitlessData();
  useAutoFetch(selectedDate, limitlessData);

  // Notify parent when content loads
  useEffect(() => {
    if (limitlessData.markdownContent && onContentLoad) {
      onContentLoad(limitlessData.markdownContent);
    }
  }, [limitlessData.markdownContent, onContentLoad]);

  return (
    <>
      {/* Header - Fixed (no outer Card, as parent NewsSection already provides Card) */}
      <div className="p-1 border-b border-gray-200">
        <div className="flex items-center space-x-2 mb-3">
          <Badge variant="outline" className="text-xs">
            Limitless
          </Badge>
        </div>
      </div>

      {/* Scrollable Markdown Content Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 h-[400px]">
        {limitlessData.loading || limitlessData.autoFetching ? (
          <div className="text-center py-4 text-gray-500 text-sm">
            {limitlessData.autoFetching ? 'Automatically fetching Limitless data...' : 'Loading Limitless content...'}
          </div>
        ) : limitlessData.fetchError ? (
          <div className="text-center py-4 text-red-500 text-sm">{limitlessData.fetchError}</div>
        ) : limitlessData.markdownContent ? (
          <MarkdownRenderer content={limitlessData.markdownContent} />
        ) : (
          <div className="text-center py-4 text-gray-500 text-sm">No Limitless content available</div>
        )}
      </div>
    </>
  );
};
