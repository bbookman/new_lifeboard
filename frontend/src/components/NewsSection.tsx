import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import newsImage from "@/assets/news-placeholder.jpg";
import { ExtendedNewsCard } from "./ExtendedNewsCard";
import { useState, useEffect } from "react";


interface NewsSectionProps {
  selectedDate?: string;
  onExpandLimitless?: (markdownContent: string) => void;
}

interface LLMSummary {
  content: string | null;
  days_date: string;
  cached: boolean;
}


/**
 * NewsSection component displays news articles for a specific date
 * @param selectedDate - The date to display news for (YYYY-MM-DD format)
 */
export const NewsSection = ({ selectedDate, onExpandLimitless }: NewsSectionProps) => {
  console.log(`[NewsSection] Received selectedDate: ${selectedDate}`);
  
  const [llmSummary, setLlmSummary] = useState<LLMSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [limitlessContent, setLimitlessContent] = useState<string>('');

  // Fetch LLM summary when selectedDate changes
  useEffect(() => {
    if (selectedDate) {
      fetchLLMSummary(selectedDate);
    }
  }, [selectedDate]);

  const fetchLLMSummary = async (date: string) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/llm/summary/${date}`);
      if (response.ok) {
        const data: LLMSummary = await response.json();
        setLlmSummary(data);
      } else {
        setError('Failed to fetch summary');
      }
    } catch (err) {
      setError('Network error while fetching summary');
      console.error('Error fetching LLM summary:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const generateSummary = async () => {
    if (!selectedDate) return;
    
    setIsGenerating(true);
    setError(null);
    
    try {
      const response = await fetch('/api/llm/generate-summary', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          days_date: selectedDate,
          force_regenerate: true
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setLlmSummary({
            content: data.content,
            days_date: data.days_date,
            cached: false
          });
        } else {
          setError(data.error_message || 'Generation failed');
        }
      } else {
        setError('Failed to generate summary');
      }
    } catch (err) {
      setError('Network error while generating summary');
      console.error('Error generating LLM summary:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const renderLLMContent = () => {
    if (isLoading) {
      return (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-news-accent"></div>
          <span className="ml-3 text-newspaper-byline">Loading summary...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center py-8">
          <p className="text-red-500 mb-4">{error}</p>
          <button
            onClick={generateSummary}
            disabled={isGenerating}
            className="px-4 py-2 bg-news-accent text-white rounded hover:bg-opacity-80 disabled:opacity-50"
          >
            {isGenerating ? 'Generating...' : 'Generate Summary'}
          </button>
        </div>
      );
    }

    if (!llmSummary?.content) {
      return (
        <div className="text-center py-8">
          <p className="text-newspaper-byline mb-4">No summary available for this date.</p>
          <button
            onClick={generateSummary}
            disabled={isGenerating}
            className="px-4 py-2 bg-news-accent text-white rounded hover:bg-opacity-80 disabled:opacity-50"
          >
            {isGenerating ? 'Generating...' : 'Generate Summary'}
          </button>
        </div>
      );
    }

    return (
      <div className="prose prose-sm max-w-none">
        <div className="whitespace-pre-wrap text-newspaper-body leading-relaxed">
          {llmSummary.content}
        </div>
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
          <span className="text-xs text-newspaper-byline">
            {llmSummary.cached ? 'Cached summary' : 'Generated summary'}
          </span>
          <button
            onClick={generateSummary}
            disabled={isGenerating}
            className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded transition-colors disabled:opacity-50"
          >
            {isGenerating ? 'Regenerating...' : 'Regenerate'}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="space-y-6">
        {/* LLM Summary Card */}
        <Card className="overflow-hidden hover:shadow-lg transition-shadow border-l-4 border-l-news-accent">
          <div className="aspect-[16/9] relative overflow-hidden">
            <img
              src={newsImage}
              alt="Daily AI Summary"
              className="w-full h-full object-cover"
            />
            <div className="absolute top-4 left-4">
              <Badge className="bg-news-accent text-white font-bold">
                AI SUMMARY
              </Badge>
            </div>
          </div>
          
          <div className="p-6">
            <div className="flex items-center space-x-2 mb-3">
              <Badge variant="outline" className="text-xs">
                Daily Summary
              </Badge>
              <span className="text-newspaper-byline text-xs">
                Generated by AI
              </span>
            </div>
            {renderLLMContent()}
          </div>
        </Card>

        {/* Limitless Content Card */}
        <Card className="overflow-hidden hover:shadow-lg transition-shadow border-l-4 border-l-blue-500 relative">
          {/* Expand icon in top right */}
          <button
            onClick={() => onExpandLimitless?.(limitlessContent)}
            className="absolute top-4 right-4 z-10 p-2 rounded-full bg-white shadow-md hover:shadow-lg transition-shadow border border-gray-200 hover:bg-gray-50"
            aria-label="Expand Limitless content to full screen"
            title="Expand to full screen"
          >
            <svg
              className="w-5 h-5 text-gray-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
              />
            </svg>
          </button>
          <ExtendedNewsCard selectedDate={selectedDate} onContentLoad={setLimitlessContent} />
        </Card>

      </div>
    </div>
  );
};