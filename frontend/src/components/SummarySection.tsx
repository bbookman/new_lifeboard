import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import newsImage from "@/assets/news-placeholder.jpg";
import { ExtendedNewsCard } from "./ExtendedNewsCard";
import { ContentCard, DailySummaryData } from "./ContentCard";
import { useState, useEffect, useCallback } from "react";
import { apiClient, LLMSummaryResponse } from "@/lib/api";
import { useNavigate } from 'react-router-dom';

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
  console.log(`[SummarySection] Received selectedDate: ${selectedDate}`);
  
  const navigate = useNavigate();
  
  // Daily Summary state management
  const [dailySummary, setDailySummary] = useState<DailySummaryData | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryPromptExists, setSummaryPromptExists] = useState<boolean | null>(null);
  const [summaryPromptDefined, setSummaryPromptDefined] = useState<boolean | null>(null);
  const [llmDefined, setLlmDefined] = useState<boolean | null>(null);

  const convertToSummaryData = (response: LLMSummaryResponse, date: string): DailySummaryData => {
    const content = response.content || "";
    const highlights: string[] = [];
    const keyThemes: string[] = [];
    
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

  const checkLlmDefined = useCallback(async () => {
    try {
      // Check if LLM is configured by checking system settings
      // This is more reliable than health endpoints that might have dependency issues
      const response = await fetch('/api/settings/');
      
      if (response.ok) {
        const settings = await response.json();
        console.log(`[SummarySection] System settings response:`, settings);
        
        // Look for LLM_PROVIDER in settings or check if any LLM-related config exists
        const llmProvider = settings.LLM_PROVIDER || settings.llm_provider;
        const isDefined = llmProvider && llmProvider !== 'none' && llmProvider.trim() !== '';
        
        setLlmDefined(isDefined);
        console.log(`[SummarySection] LLM defined: ${isDefined} (provider: ${llmProvider})`);
        return isDefined;
      } else {
        // Fallback: assume LLM is configured if we can't check settings
        // This prevents the UI from showing setup steps when the backend might be working
        console.warn(`[SummarySection] Could not check system settings (${response.status}), assuming LLM is configured`);
        setLlmDefined(true);
        return true;
      }
    } catch (error) {
      console.error('[SummarySection] Error checking LLM configuration:', error);
      // Fallback: assume LLM is configured to avoid false negatives
      setLlmDefined(true);
      return true;
    }
  }, []);

  const checkSummaryPrompt = useCallback(async () => {
    try {
      const response = await fetch('/api/documents?document_type=prompt&limit=1');
      if (!response.ok) {
        throw new Error('Failed to check for summary prompts');
      }
      
      const data = await response.json();
      const hasPrompt = data.documents && data.documents.length > 0;
      setSummaryPromptExists(hasPrompt);
      
      console.log(`[SummarySection] Summary prompt exists: ${hasPrompt}`);
      return hasPrompt;
    } catch (error) {
      console.error('[SummarySection] Error checking summary prompt:', error);
      setSummaryPromptExists(false);
      return false;
    }
  }, []);

  const checkSummaryPromptDefined = useCallback(async () => {
    try {
      // Check if there's a setting for which summary prompt is chosen/defined
      const response = await fetch('/api/settings/prompt-selection');
      if (!response.ok) {
        throw new Error('Failed to check if summary prompt is defined');
      }
      
      const data = await response.json();
      const isDefined = data.prompt_document_id && data.prompt_document_id.trim() !== '' && data.is_active;
      setSummaryPromptDefined(isDefined);
      
      console.log(`[SummarySection] Summary prompt defined: ${isDefined} (ID: ${data.prompt_document_id}, Active: ${data.is_active})`);
      return isDefined;
    } catch (error) {
      console.error('[SummarySection] Error checking if summary prompt is defined:', error);
      setSummaryPromptDefined(false);
      return false;
    }
  }, []);

  const handleCreatePromptClick = () => {
    console.log('[SummarySection] Navigating to documents to create prompt');
    navigate('/documents');
  };

  const handleChoosePromptClick = () => {
    console.log('[SummarySection] Navigating to settings to choose prompt');
    navigate('/settings');
  };

  const getStepStatuses = useCallback(() => {
    return [
      {
        text: "Please edit .env to get an AI generated summary",
        completed: llmDefined === true,
        clickable: false,
        onClick: null
      },
      {
        text: "Create a summary prompt if you have not",
        completed: summaryPromptExists === true,
        clickable: summaryPromptExists !== true,
        onClick: handleCreatePromptClick
      },
      {
        text: "Choose your prompt in Settings",
        completed: summaryPromptDefined === true,
        clickable: summaryPromptDefined !== true,
        onClick: handleChoosePromptClick
      }
    ];
  }, [llmDefined, summaryPromptExists, summaryPromptDefined, handleCreatePromptClick, handleChoosePromptClick]);

  const loadDailySummary = useCallback(async (date: string) => {
    if (!date) return; 
    
    console.log(`[SummarySection] Loading daily summary for date: ${date}`);
    setSummaryLoading(true);
    
    try {
      // Check if LLM is defined/running first
      const llmAvailable = await checkLlmDefined();
      
      if (!llmAvailable) {
        console.log(`[SummarySection] LLM not running, skipping summary generation`);
        setDailySummary(null);
        setSummaryLoading(false);
        return;
      }

      // Check if summary prompt exists
      const promptExists = await checkSummaryPrompt();
      
      if (!promptExists) {
        console.log(`[SummarySection] No summary prompt exists, skipping summary generation`);
        setDailySummary(null);
        setSummaryLoading(false);
        return;
      }

      // Check if a summary prompt is defined/chosen
      const promptDefined = await checkSummaryPromptDefined();
      
      if (!promptDefined) {
        console.log(`[SummarySection] Summary prompt exists but not defined/chosen, skipping summary generation`);
        setDailySummary(null);
        setSummaryLoading(false);
        return;
      }

      const cachedResponse = await apiClient.getDailySummary(date);
      
      if (cachedResponse.success && cachedResponse.data?.content) {
        console.log(`[SummarySection] Found cached summary`);
        const summaryData = convertToSummaryData(cachedResponse.data, date);
        setDailySummary(summaryData);
        setSummaryLoading(false);
        return;
      }
      
      console.log(`[SummarySection] No cached summary found, generating new summary...`);
      const generateResponse = await apiClient.generateDailySummary(date, false);
      
      if (generateResponse.success && generateResponse.data?.success && generateResponse.data?.content) {
        console.log(`[SummarySection] Successfully generated new summary`);
        const summaryData = convertToSummaryData(generateResponse.data, date);
        setDailySummary(summaryData);
      } else {
        const errorMsg = generateResponse.data?.error_message || generateResponse.error || 'Failed to generate summary';
        console.error(`[SummarySection] Failed to generate summary:`, errorMsg);
        setDailySummary(null);
      }
    } catch (error) {
      console.error('[SummarySection] Error loading daily summary:', error);
      setDailySummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [checkLlmDefined, checkSummaryPrompt, checkSummaryPromptDefined]);

  useEffect(() => {
    if (selectedDate) {
      loadDailySummary(selectedDate);
    }
  }, [selectedDate, loadDailySummary]);

  // Initial check for LLM status and summary prompts when component mounts
  useEffect(() => {
    checkLlmDefined();
    checkSummaryPrompt();
    checkSummaryPromptDefined();
  }, [checkLlmDefined, checkSummaryPrompt, checkSummaryPromptDefined]);

  const forceRegenerateSummary = async () => {
    if (!selectedDate) return; 
    
    console.log(`[SummarySection] Force regenerating summary for date: ${selectedDate}`);
    setSummaryLoading(true);
    
    try {
      const generateResponse = await apiClient.generateDailySummary(selectedDate, true);
      
      if (generateResponse.success && generateResponse.data?.success && generateResponse.data?.content) {
        console.log(`[SummarySection] Successfully force regenerated summary`);
        const summaryData = convertToSummaryData(generateResponse.data, selectedDate);
        setDailySummary(summaryData);
      } else {
        const errorMsg = generateResponse.data?.error_message || generateResponse.error || 'Failed to regenerate summary';
        console.error(`[SummarySection] Failed to regenerate summary:`, errorMsg);
      }
    } catch (error) {
      console.error('[SummarySection] Error force regenerating summary:', error);
    } finally {
      setSummaryLoading(false);
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
            {summaryLoading ? (
              <div className="card p-6">
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-news-accent"></div>
                  <span className="ml-3 text-newspaper-byline">Generating daily summary...</span>
                </div>
              </div>
            ) : (() => {
              const steps = getStepStatuses();
              const allStepsCompleted = steps.every(step => step.completed);
              
              return !allStepsCompleted ? (
                <div className="card p-6">
                  <div className="text-newspaper-byline text-left">
                    <h3>Summary section</h3>
                    <div className="mt-2">Setup steps:</div>
                    <ol className="list-decimal list-inside ml-4 mt-2 space-y-1">
                      {steps.map((step, index) => (
                        <li key={index}>
                          {step.completed ? (
                            <span className="inline-flex items-center">
                              <span className="text-green-600 mr-2">✅</span>
                              <span className="line-through text-gray-500">
                                {step.text.includes('.env') ? (
                                  <>Please edit <b>.env</b> to get an AI generated summary</>
                                ) : (
                                  step.text
                                )}
                              </span>
                            </span>
                          ) : step.clickable ? (
                            <button
                              onClick={step.onClick}
                              className="text-blue-600 hover:text-blue-800 underline font-medium"
                            >
                              {step.text.includes('.env') ? (
                                <>Please edit <b>.env</b> to get an AI generated summary</>
                              ) : (
                                step.text
                              )}
                            </button>
                          ) : (
                            <span>
                              {step.text.includes('.env') ? (
                                <>Please edit <b>.env</b> to get an AI generated summary</>
                              ) : (
                                step.text
                              )}
                            </span>
                          )}
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              ) : dailySummary ? (
                <div className="relative">
                  <ContentCard data={dailySummary} />
                  <button
                    onClick={forceRegenerateSummary}
                    className="absolute top-4 right-4 button button-outline button-sm"
                    title="Regenerate summary"
                  >
                    ↻
                  </button>
                </div>
              ) : (
                <div className="card p-6">
                  <div className="text-newspaper-byline text-left">
                    Loading summary... Check that either local LLM is running or remote LLM is accessible (see logs)
                  </div>
                </div>
              );
            })()}
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
      </div>
    </div>
  );
};