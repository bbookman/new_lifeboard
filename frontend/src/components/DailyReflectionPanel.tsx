import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * DailyReflectionPanel.tsx
 *
 * Pure presentation for the Daily Reflection content.
 * No layout or data fetching lives here—only rendering.
 */
export interface DailyReflectionPanelProps {
  markdownContent: string;
  loading: boolean;
  error: string | null;
  dateLabel: string;
}

export const DailyReflectionPanel = ({
  markdownContent,
  loading,
  error,
  dateLabel,
}: DailyReflectionPanelProps) => {
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-blue-500 pb-2">
        <h2 className="text-xl font-bold text-gray-800">Daily Reflection</h2>
      </div>

      <div>
        {loading && <div className="text-center py-8 text-gray-600">Loading day data...</div>}

        {error && <div className="text-center py-8 text-red-600">{error}</div>}

        {!loading && !error && !markdownContent && (
          <div className="text-center py-8 text-gray-600">No reflection data found for {dateLabel}</div>
        )}

        {!loading && !error && markdownContent && (
          <div className="prose prose max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownContent}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

export default DailyReflectionPanel;