import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, RefreshCw } from "lucide-react";
import { useLimitlessData } from "../hooks/useLimitlessData";
import { useAutoFetch } from "../hooks/useAutoFetch";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface ExtendedNewsCardProps {
  headline: string;
  summary: string;
  author: string;
  timestamp: string;
  category: string;
  readTime: string;
  breaking?: boolean;
  selectedDate?: string;
}

/**
 * ExtendedNewsCard component - Optimized version
 * Displays limitless markdown content using custom hooks for better separation of concerns
 * This component is used within a Card wrapper in SummarySection, so no outer Card needed
 */
export const ExtendedNewsCard = ({ selectedDate }: Pick<ExtendedNewsCardProps, 'selectedDate'>) => {
  // Use custom hooks for data management and auto-fetch logic
  const limitlessData = useLimitlessData();
  useAutoFetch(selectedDate, limitlessData);

  const handleRefresh = async () => {
    // Get today's date as fallback if selectedDate is not provided
    const today = new Date().toISOString().split('T')[0];
    const targetDate = selectedDate || today;
    
    // Reset fetch attempted state for the targeted date only
    limitlessData.resetFetchAttempted(targetDate);
    
    // Trigger a fresh data fetch (loading state will prevent flicker)
    await limitlessData.fetchData(targetDate, true);
  };

  const handleExpandContent = () => {
    if (limitlessData.markdownContent) {
      // Create a simplified data structure for the expanded view
      const expandedData = {
        type: "limitless",
        id: `limitless-${selectedDate || 'current'}`,
        title: "Limitless Content",
        timestamp: selectedDate ? new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        }) : new Date().toLocaleDateString('en-US', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        }),
        markdownContent: limitlessData.markdownContent
      };
      
      // Store data in sessionStorage to avoid URL length limits
      const storageKey = `limitless-expanded-${expandedData.id}`;
      sessionStorage.setItem(storageKey, JSON.stringify(expandedData));
      
      // Open with just the key
      window.open(`/limitless-expanded?key=${storageKey}`, '_blank');
    }
  };

  return (
    <>
      {/* Header - Fixed (no outer Card, as parent SummarySection already provides Card) */}
      <div className="p-1 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="text-xs">
              Limitless
            </Badge>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={limitlessData.loading || limitlessData.autoFetching}
              className="p-2 bg-white hover:bg-gray-50 border-gray-200"
              title="Refresh limitless data"
            >
              <RefreshCw className={`w-4 h-4 text-gray-600 ${limitlessData.loading || limitlessData.autoFetching ? 'animate-spin' : ''}`} />
            </Button>
            {limitlessData.markdownContent && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleExpandContent}
                className="p-2 bg-white hover:bg-gray-50 border-gray-200"
                title="Open in new page"
              >
                <ExternalLink className="w-4 h-4 text-gray-600" />
              </Button>
            )}
          </div>
        </div>

      </div>

      {/* Scrollable Markdown Content Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 h-[400px]">
        {limitlessData.loading || limitlessData.autoFetching ? (
          <div className="text-center py-4 text-gray-500 text-sm">
            {limitlessData.autoFetching ? 'Automatically fetching Limitless data...' : 'Loading Limitless content...'}
          </div>
        ) : limitlessData.fetchError ? (
          <div className="text-center py-4 text-red-500 text-sm">
            {limitlessData.fetchError}
          </div>
        ) : limitlessData.markdownContent ? (
          <MarkdownRenderer content={limitlessData.markdownContent} />
        ) : (
          <div className="text-center py-4 text-gray-500 text-sm">
            No Limitless content available
          </div>
        )}
      </div>
    </>
  );
};
