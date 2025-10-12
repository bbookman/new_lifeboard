import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import newsImage from "@/assets/news-placeholder.jpg";
import { ExtendedNewsCard } from "./ExtendedNewsCard";
import { AppleMusicCard } from "./AppleMusicCard";
import { ContentCard, DailySummaryData } from "./ContentCard";
import { DataAvailabilityAlert } from "./DataAvailabilityAlert";
import { useState, useEffect, useCallback } from "react";
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

interface SummarySectionProps {
  selectedDate?: string;
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
 * SummarySection component displays daily summary and news articles for a specific date
 * @param selectedDate - The date to display summary and news for (YYYY-MM-DD format)
 */
export const SummarySection = ({ selectedDate }: SummarySectionProps) => {
  console.log(`[SummarySection] 🔍 COMPONENT INITIALIZED - selectedDate: ${selectedDate}`);
  
  
  // Daily Summary state management
  const [dailySummary, setDailySummary] = useState<DailySummaryData | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [debugInfo, setDebugInfo] = useState<any>(null);
  const [dataAvailabilityMessages, setDataAvailabilityMessages] = useState<string[]>([]);

  const convertToSummaryData = (response: LLMSummaryResponse, date: string): DailySummaryData => {
    const content = response.content || "";
    const highlights: string[] = [];
    const keyThemes: string[] = [];
    
    // Update data availability messages state
    if (response.data_availability?.messages) {
      setDataAvailabilityMessages(response.data_availability.messages);
    } else {
      setDataAvailabilityMessages([]);
    }
    
    const bulletPoints = content.match(/[-*•]\s+([^\n]+)/g);
    if (bulletPoints) {
      highlights.push(...bulletPoints.slice(0, 4).map(bp => bp.replace(/^[-*•]\s+/, '')));
    }
    
    const headers = content.match(/\*\*([^*]+)\*\*/g);
    if (headers) {
      keyThemes.push(...headers.slice(0, 5).map(h => h.replace(/\*\*/g, '')));
    }
    
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






  const loadDailySummary = useCallback(async (date: string) => {
    if (!date) {
      console.log(`[SummarySection] ❌ No date provided, skipping summary load`);
      return;
    }

    console.log(`[SummarySection] 🚀 STARTING summary load workflow for date: ${date}`);
    setSummaryLoading(true);
    
    // Load debug info first
    try {
      console.log(`[SummarySection] 🔍 Fetching debug info to check system status...`);
      const debugResponse = await fetch('/api/debug/summary-status');
      if (debugResponse.ok) {
        const debugData = await debugResponse.json();
        setDebugInfo(debugData);
        console.log(`[SummarySection] 🔍 DEBUG INFO:`, debugData);
        
        if (!debugData.summary_ready) {
          console.warn(`[SummarySection] ⚠️ SUMMARY NOT READY:`, debugData.recommendations);
        }
      } else {
        console.warn(`[SummarySection] ⚠️ Could not fetch debug info: ${debugResponse.status}`);
      }
    } catch (e) {
      console.warn(`[SummarySection] ⚠️ Debug info fetch failed:`, e);
    }

    try {
      console.log(`[SummarySection] 📋 Step 1: Checking for cached summary...`);
      const cachedResponse = await apiClient.getDailySummary(date);

      if (cachedResponse.success && cachedResponse.data?.content) {
        console.log(`[SummarySection] ✅ Step 1 SUCCESS: Found cached summary (${cachedResponse.data.content.length} chars)`);
        const summaryData = convertToSummaryData(cachedResponse.data, date);
        setDailySummary(summaryData);
        setSummaryLoading(false);
        return;
      }

      console.log(`[SummarySection] 📋 Step 1 RESULT: No cached summary, proceeding to generation...`);
      console.log(`[SummarySection] 🔄 Step 2: Generating new summary...`);
      const generateResponse = await apiClient.generateDailySummary(date, false);

      console.log(`[SummarySection] 📋 Step 2 RESPONSE:`, {
        success: generateResponse.success,
        hasData: !!generateResponse.data,
        dataSuccess: generateResponse.data?.success,
        hasContent: !!generateResponse.data?.content,
        contentLength: generateResponse.data?.content?.length || 0,
        error: generateResponse.error,
        errorMessage: generateResponse.data?.error_message
      });

      if (generateResponse.success && generateResponse.data?.success && generateResponse.data?.content) {
        console.log(`[SummarySection] ✅ Step 2 SUCCESS: Generated new summary (${generateResponse.data.content.length} chars)`);
        const summaryData = convertToSummaryData(generateResponse.data, date);
        setDailySummary(summaryData);
      } else {
        const errorMsg = generateResponse.data?.error_message || generateResponse.error || 'Failed to generate summary';
        console.error(`[SummarySection] ❌ Step 2 FAILED: ${errorMsg}`);
        console.error(`[SummarySection] 📋 Full error context:`, generateResponse);
        
        // Check if this is a data availability issue (blocked generation)
        if (generateResponse.success && generateResponse.data?.data_availability?.messages) {
          console.log(`[SummarySection] 📋 Generation blocked due to missing data sources`);
          setDataAvailabilityMessages(generateResponse.data.data_availability.messages);
        } else {
          setDataAvailabilityMessages([]); // Clear messages on other errors
        }
        
        setDailySummary(null);
      }
    } catch (error) {
      console.error('[SummarySection] 💥 CRITICAL ERROR in summary workflow:', error);
      setDailySummary(null);
      setDataAvailabilityMessages([]); // Clear messages on critical error
    } finally {
      setSummaryLoading(false);
      console.log(`[SummarySection] 🏁 Summary load workflow completed`);
    }
  }, []);

  useEffect(() => {
    if (selectedDate) {
      loadDailySummary(selectedDate);
    }
  }, [selectedDate, loadDailySummary]);


  const forceRegenerateSummary = async () => {
    if (!selectedDate) return; 
    
    console.log(`[SummarySection] Force regenerating summary for date: ${selectedDate}`);
    setRegenerating(true);
    
    try {
      const generateResponse = await apiClient.generateDailySummary(selectedDate, true);
      
      if (generateResponse.success && generateResponse.data?.success && generateResponse.data?.content) {
        console.log(`[SummarySection] Successfully force regenerated summary`);
        const summaryData = convertToSummaryData(generateResponse.data, selectedDate);
        setDailySummary(summaryData);
      } else {
        const errorMsg = generateResponse.data?.error_message || generateResponse.error || 'Failed to regenerate summary';
        console.error(`[SummarySection] Failed to regenerate summary:`, errorMsg);
        
        // Check if this is a data availability issue (blocked generation)
        if (generateResponse.success && generateResponse.data?.data_availability?.messages) {
          console.log(`[SummarySection] Force regeneration blocked due to missing data sources`);
          setDataAvailabilityMessages(generateResponse.data.data_availability.messages);
        } else {
          setDataAvailabilityMessages([]); // Clear messages on other errors
        }
        
        setDailySummary(null);
      }
    } catch (error) {
      console.error('[SummarySection] Error force regenerating summary:', error);
      setDailySummary(null);
      setDataAvailabilityMessages([]); // Clear messages on critical error
    } finally {
      setRegenerating(false);
    }
  };


  return (
    <div className="space-y-6">
      <div className="space-y-6">
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

        {selectedDate && (
          <>
            {/* Debug info panel (only show if there's an issue) */}
            {debugInfo && !debugInfo.summary_ready && (
              <div className="card p-4 mb-4 border-l-4 border-l-yellow-500 bg-yellow-50">
                <h4 className="font-semibold text-yellow-800 mb-2">🔧 Summary Debug Info</h4>
                <div className="text-sm text-yellow-700 space-y-1">
                  <div>Status: <span className="font-mono">{debugInfo.summary_ready ? '✅ Ready' : '❌ Not Ready'}</span></div>
                  {debugInfo.recommendations?.map((rec: string, i: number) => (
                    <div key={i}>• {rec}</div>
                  ))}
                  <details className="mt-2">
                    <summary className="cursor-pointer">Technical Details</summary>
                    <pre className="mt-1 text-xs overflow-auto">{JSON.stringify(debugInfo, null, 2)}</pre>
                  </details>
                </div>
              </div>
            )}

            {/* Data Availability Alert */}
            {dataAvailabilityMessages.length > 0 && (
              <DataAvailabilityAlert 
                messages={dataAvailabilityMessages}
                className="mb-4"
              />
            )}

            {summaryLoading ? (
              <div className="card p-6">
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-news-accent"></div>
                  <span className="ml-3 text-newspaper-byline">Generating daily summary...</span>
                </div>
              </div>
            ) : dailySummary ? (
                <div className="relative">
                  <ContentCard data={dailySummary} />
                  <div className="absolute top-4 right-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={forceRegenerateSummary}
                      disabled={regenerating || summaryLoading}
                      className="p-2 bg-white hover:bg-gray-50 border-gray-200"
                      title="Regenerate summary"
                    >
                      <RefreshCw className={`w-4 h-4 text-gray-600 ${regenerating ? 'animate-spin' : ''}`} />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="card p-6 relative">
                  <div className="text-center text-newspaper-byline">
                    {debugInfo?.summary_ready === false 
                      ? "Summary system not ready - check debug info above" 
                      : "No summary available for this date"}
                  </div>
                  {/* Show refresh button when data availability messages are present */}
                  {dataAvailabilityMessages.length > 0 && (
                    <div className="absolute top-4 right-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={forceRegenerateSummary}
                        disabled={regenerating || summaryLoading}
                        className="p-2 bg-white hover:bg-gray-50 border-gray-200"
                        title="Retry summary generation"
                      >
                        <RefreshCw className={`w-4 h-4 text-gray-600 ${regenerating ? 'animate-spin' : ''}`} />
                      </Button>
                    </div>
                  )}
                </div>
              )}
          </>
        )}

        {sampleNews.slice(1).map((article) => (
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

        {/* Apple Music Card */}
        <Card className="overflow-hidden hover:shadow-lg transition-shadow flex flex-col">
          <AppleMusicCard selectedDate={selectedDate} />
        </Card>
      </div>
    </div>
  );
};