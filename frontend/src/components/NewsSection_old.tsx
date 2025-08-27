import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import newsImage from "@/assets/news-placeholder.jpg";
import { ExtendedNewsCard } from "./ExtendedNewsCard";
import { ContentCard, DailySummaryData } from "./ContentCard";
import { useState, useEffect } from "react";
import { apiClient, LLMSummaryResponse } from "@/lib/api";

interface NewsArticle {
  id: string;
  headline: string;
  summary: string;
  author: string;
  timestamp: string;
  category: string;
  readTime: string;
  breaking?: boolean;
}

interface NewsSectionProps {
  selectedDate?: string;
}

interface DayData {
  summary: {
    has_any_data: boolean;
  };
}

const sampleNews: NewsArticle[] = [
  {
    id: "1",
    headline: "",
    summary: "",
    author: "",
    timestamp: "",
    category: "",
    readTime: "",
    breaking: true
  },
  {
    id: "2",
    headline: "Revolutionary Medical Treatment Shows Promise in Clinical Trials",
    summary: "A groundbreaking new treatment for chronic conditions has shown remarkable results in Phase III trials, offering hope to millions of patients worldwide.",
    author: "Dr. Michael Chen",
    timestamp: "3 hours ago",
    category: "Health",
    readTime: "5 min read"
  }
];

/**
 * NewsSection component displays news articles for a specific date
 * @param selectedDate - The date to display news for (YYYY-MM-DD format)
 */
export const NewsSection = ({ selectedDate }: NewsSectionProps) => {
  console.log(`[NewsSection] Received selectedDate: ${selectedDate}`);
  
  // Daily Summary state management
  const [dailySummary, setDailySummary] = useState<DailySummaryData | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [llmUnavailable, setLlmUnavailable] = useState(false);
  const [hasDataAvailable, setHasDataAvailable] = useState<boolean>(false);
  const [hasPromptConfigured, setHasPromptConfigured] = useState<boolean>(true);

  /**
   * Convert LLM API response to DailySummaryData format for ContentCard
   */
  const convertToSummaryData = (response: LLMSummaryResponse, date: string): DailySummaryData => {
    const content = response.content || "";
    const highlights: string[] = [];
    const keyThemes: string[] = [];
    
    // Simple parsing to extract bullet points as highlights
    const bulletPoints = content.match(/[-*•]\s+([^\n]+)/g);
    if (bulletPoints) {
      highlights.push(...bulletPoints.slice(0, 4).map(bp => bp.replace(/^[-*•]\s+/, '')));
    }
    
    // Extract themes from headers or key sections
    const headers = content.match(/\*\*([^*]+)\*\*/g);
    if (headers) {
      keyThemes.push(...headers.slice(0, 5).map(h => h.replace(/\*\*/g, '')));
    }
    
    // If no structured content found, use fallback
    if (highlights.length === 0) {
      highlights.push("Generated comprehensive daily summary");
      highlights.push("Integrated data from multiple sources");
      highlights.push("Provided insights and key themes");
    }
    
    if (keyThemes.length === 0) {
      keyThemes.push("Technology", "Productivity", "Daily Activities");
    }
    
    return {
      type: "daily-summary",
      date,
      totalItems: 0,
      highlights,
      keyThemes,
      moodScore: 7,
      weatherSummary: "Weather information included in summary",
      generatedContent: content,
      generationTime: response.generation_time,
      modelInfo: response.model_info,
      cached: response.cached
    };
  };

  // Load summary and check data availability when selectedDate changes
  useEffect(() => {
    if (selectedDate) {
      loadDailySummary(selectedDate);
      checkDataAvailability(selectedDate);
      checkPromptConfiguration();
    }
  }, [selectedDate]);

  const checkDataAvailability = async (date: string) => {
    try {
      const response = await fetch(`/calendar/day/${date}/enhanced`);
      if (response.ok) {
        const data: DayData = await response.json();
        setHasDataAvailable(data.summary.has_any_data);
      } else {
        console.error('Failed to check data availability');
        setHasDataAvailable(false);
      }
    } catch (err) {
      console.error('Error checking data availability:', err);
      setHasDataAvailable(false);
    }
  };

  const checkPromptConfiguration = async () => {
    try {
      const response = await fetch('/api/settings/prompt-selection');
      if (response.ok) {
        const data = await response.json();
        setHasPromptConfigured(!!data.prompt_document_id);
      } else {
        console.error('Failed to check prompt configuration');
        setHasPromptConfigured(false);
      }
    } catch (err) {
      console.error('Error checking prompt configuration:', err);
      setHasPromptConfigured(false);
    }
  };

  /**
   * Load daily summary from LLM API
   */
  const loadDailySummary = async (date: string) => {
    if (!date) return;
    
    console.log(`[NewsSection] Loading daily summary for date: ${date}`);
    setSummaryLoading(true);
    setSummaryError(null);
    setLlmUnavailable(false);
    
    try {
      // First check for cached summary
      const cachedResponse = await apiClient.getDailySummary(date);
      
      if (cachedResponse.success && cachedResponse.data?.content) {
        console.log(`[NewsSection] Found cached summary`);
        const summaryData = convertToSummaryData(cachedResponse.data, date);
        setDailySummary(summaryData);
        setSummaryLoading(false);
        return;
      }
      
      // No cached content, generate new summary
      console.log(`[NewsSection] No cached summary found, generating new summary...`);
      const generateResponse = await apiClient.generateDailySummary(date, false);
      
      if (generateResponse.success && generateResponse.data?.success && generateResponse.data?.content) {
        console.log(`[NewsSection] Successfully generated new summary`);
        const summaryData = convertToSummaryData(generateResponse.data, date);
        setDailySummary(summaryData);
      } else {
        // Check if LLM is unavailable
        const isLLMUnavailable = !generateResponse.success || 
                                generateResponse.data?.llm_unavailable || 
                                (generateResponse.data?.error_message?.includes('LLM service not available')) ||
                                (generateResponse.data?.error_message?.includes('No LLM provider'));
        
        if (isLLMUnavailable) {
          console.log(`[NewsSection] LLM service unavailable`);
          setLlmUnavailable(true);
          setDailySummary(null);
        } else {
          const errorMsg = generateResponse.data?.error_message || generateResponse.error || 'Failed to generate summary';
          console.error(`[NewsSection] Failed to generate summary:`, errorMsg);
          setSummaryError(errorMsg);
          setDailySummary(null);
        }
      }
    } catch (error) {
      console.error('[NewsSection] Error loading daily summary:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      if (errorMessage.includes('LLM service not available') || errorMessage.includes('503')) {
        setLlmUnavailable(true);
      } else {
        setSummaryError(errorMessage);
      }
      setDailySummary(null);
    } finally {
      setSummaryLoading(false);
    }
  };

  /**
   * Force regeneration of daily summary
   */
  const forceRegenerateSummary = async () => {
    if (!selectedDate) return;
    
    console.log(`[NewsSection] Force regenerating summary for date: ${selectedDate}`);
    setSummaryLoading(true);
    setSummaryError(null);
    
    try {
      const generateResponse = await apiClient.generateDailySummary(selectedDate, true);
      
      if (generateResponse.success && generateResponse.data?.success && generateResponse.data?.content) {
        console.log(`[NewsSection] Successfully force regenerated summary`);
        const summaryData = convertToSummaryData(generateResponse.data, selectedDate);
        setDailySummary(summaryData);
      } else {
        const errorMsg = generateResponse.data?.error_message || generateResponse.error || 'Failed to regenerate summary';
        console.error(`[NewsSection] Failed to regenerate summary:`, errorMsg);
        setSummaryError(errorMsg);
      }
    } catch (error) {
      console.error('[NewsSection] Error force regenerating summary:', error);
      setSummaryError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setSummaryLoading(false);
    }
  };


  return (
    <div className="space-y-6">
      <div className="space-y-6">
        {/* Main image with AI SUMMARY badge */}
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
        </Card>

        {/* Daily Summary Card - appears below the main image */}
        {selectedDate && (
          <>
            {summaryLoading && (
              <div className="card p-6">
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-news-accent"></div>
                  <span className="ml-3 text-newspaper-byline">Generating daily summary...</span>
                </div>
              </div>
            )}
            
            {llmUnavailable && (
              <div className="card p-6">
                <div className="text-center">
                  <h3 className="font-headline text-lg font-semibold text-newspaper-headline mb-2">
                    Daily Summary
                  </h3>
                  <div className="text-newspaper-byline mb-4">
                    No LLM available to process summary
                  </div>
                  <div className="text-sm text-gray-600">
                    Configure an LLM provider to enable AI-generated daily summaries
                  </div>
                </div>
              </div>
            )}
            
            {summaryError && !llmUnavailable && (
              <div className="card p-6">
                <div className="text-center">
                  <h3 className="font-headline text-lg font-semibold text-newspaper-headline mb-2">
                    Daily Summary
                  </h3>
                  <div className="text-red-600 mb-4">Error: {summaryError}</div>
                  <button 
                    onClick={() => loadDailySummary(selectedDate)}
                    className="button button-outline"
                  >
                    Retry
                  </button>
                </div>
              </div>
            )}
            
            {dailySummary && !summaryLoading && (
              <div className="relative">
                <ContentCard data={dailySummary} />
                {/* Refresh button for regenerating summary */}
                <button
                  onClick={forceRegenerateSummary}
                  className="absolute top-4 right-4 button button-outline button-sm"
                  title="Regenerate summary"
                >
                  ↻
                </button>
              </div>
            )}
          </>
        )}

        {/* Extended News Card */}
        {sampleNews.slice(1).map((article, index) => (
          <ExtendedNewsCard
            key={article.id}
            headline={article.headline}
            summary={article.summary}
            author={article.author}
            timestamp={article.timestamp}
            category={article.category}
            readTime={article.readTime}
            breaking={article.breaking}
            selectedDate={selectedDate}
          />
        ))}
      </div>
    </div>
  );
};