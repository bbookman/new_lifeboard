import { Badge } from "@/components/ui/badge";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface LimitlessExpandedViewProps {
  selectedDate?: string;
  onClose: () => void;
  content: string;
}

/**
 * LimitlessExpandedView component - Full screen version of ExtendedNewsCard
 * Displays limitless markdown content consuming the entire screen
 */
export const LimitlessExpandedView = ({ selectedDate, onClose, content }: LimitlessExpandedViewProps) => {

  const formatDisplayDate = (dateString?: string) => {
    if (!dateString) return 'Today';
    
    const date = new Date(dateString + 'T00:00:00');
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    };
    return date.toLocaleDateString('en-US', options);
  };

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col">
      {/* Header with close button */}
      <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-white flex-shrink-0">
        <div className="flex items-center space-x-4">
          <Badge variant="outline" className="text-sm">
            Limitless
          </Badge>
          <h1 className="text-2xl font-bold text-gray-900">
            {formatDisplayDate(selectedDate)}
          </h1>
        </div>
        <button
          onClick={onClose}
          className="flex items-center justify-center w-10 h-10 rounded-full hover:bg-gray-100 transition-colors"
          aria-label="Close expanded view"
        >
          <svg
            className="w-6 h-6 text-gray-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Full screen content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-8 max-w-4xl mx-auto">
          {content ? (
            <div className="prose prose-lg max-w-none">
              <MarkdownRenderer content={content} />
            </div>
          ) : (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <p className="text-gray-500 text-lg">No Limitless content available for this date</p>
                <p className="text-gray-400 mt-2">Try selecting a different date or check back later.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};