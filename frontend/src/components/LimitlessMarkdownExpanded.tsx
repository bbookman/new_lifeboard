import { useSearchParams, useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Clock } from "lucide-react";
import { useState, useEffect } from "react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { useLimitlessData } from "../hooks/useLimitlessData";
import { extractDateFromLimitlessId } from "../utils/limitless";

interface LimitlessExpandedData {
  type: "limitless";
  id: string;
  title: string;
  timestamp: string;
  markdownContent: string;
}

export const LimitlessMarkdownExpanded = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState<LimitlessExpandedData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const limitlessData = useLimitlessData();

  useEffect(() => {
    // First try the new key-based approach (sessionStorage)
    const keyParam = searchParams.get('key');
    if (keyParam) {
      try {
        const storedData = sessionStorage.getItem(keyParam);
        if (storedData) {
          const parsedData = JSON.parse(storedData);
          setData(parsedData);
          return;
        }
      } catch (error) {
        console.error('Failed to parse stored content data:', error);
      }
    }
    
    // Fallback to old data parameter approach for backwards compatibility
    const dataParam = searchParams.get('data');
    if (dataParam) {
      try {
        const parsedData = JSON.parse(decodeURIComponent(dataParam));
        setData(parsedData);
      } catch (error) {
        console.error('Failed to parse URL content data:', error);
      }
    }
  }, [searchParams]);

  // Add debugging useEffect to track data state changes
  useEffect(() => {
    if (data) {
      console.log('[LimitlessMarkdownExpanded] DATA STATE CHANGED:', {
        timestamp: data.timestamp,
        markdownLength: data.markdownContent?.length,
        title: data.title,
        id: data.id
      });
    }
  }, [data]);

  const handleRefresh = async () => {
    const startTime = Date.now();
    console.log(`[LimitlessMarkdownExpanded] ===== REFRESH BUTTON CLICKED at ${new Date().toISOString()} =====`);
    
    if (!data) {
      console.log('[LimitlessMarkdownExpanded] ABORT: No data available');
      return;
    }
    
    console.log('[LimitlessMarkdownExpanded] Step 1: Data validation passed');
    console.log('[LimitlessMarkdownExpanded] Data.id:', data.id);
    console.log('[LimitlessMarkdownExpanded] Data.title:', data.title);
    console.log('[LimitlessMarkdownExpanded] Current markdownContent length:', data.markdownContent?.length || 0);
    
    const extractedDate = extractDateFromLimitlessId(data.id);
    console.log('[LimitlessMarkdownExpanded] Step 2: Date extraction result:', extractedDate);
    
    // Add timezone debugging
    const currentDate = new Date().toISOString().split('T')[0];
    const userLocalDate = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD format
    console.log('[LimitlessMarkdownExpanded] TIMEZONE DEBUG:');
    console.log('[LimitlessMarkdownExpanded] - Extracted date from ID:', extractedDate);
    console.log('[LimitlessMarkdownExpanded] - Current UTC date:', currentDate);
    console.log('[LimitlessMarkdownExpanded] - User local date:', userLocalDate);
    console.log('[LimitlessMarkdownExpanded] - User timezone:', Intl.DateTimeFormat().resolvedOptions().timeZone);
    
    if (extractedDate !== currentDate && extractedDate !== userLocalDate) {
      console.warn('[LimitlessMarkdownExpanded] WARNING: Refreshing historical date, not today!');
      console.warn('[LimitlessMarkdownExpanded] This will fetch data for', extractedDate, 'not today\'s data');
    }
    
    if (!extractedDate) {
      console.error('[LimitlessMarkdownExpanded] ABORT: Could not extract date from data ID:', data.id);
      return;
    }

    try {
      console.log('[LimitlessMarkdownExpanded] Step 3: Setting refreshing state to true');
      console.log('[LimitlessMarkdownExpanded] Refreshing state before:', refreshing);
      setRefreshing(true);
      console.log('[LimitlessMarkdownExpanded] Refreshing state set to true');
      
      console.log('[LimitlessMarkdownExpanded] Step 4: Clearing limitless data content');
      limitlessData.clearContent();
      console.log('[LimitlessMarkdownExpanded] Content cleared');
      
      console.log('[LimitlessMarkdownExpanded] Step 5: Resetting fetch attempted state for date:', extractedDate);
      limitlessData.resetFetchAttempted(extractedDate);
      console.log('[LimitlessMarkdownExpanded] Fetch attempted state reset');
      
      console.log('[LimitlessMarkdownExpanded] Step 6: Triggering Limitless API fetch first');
      console.log('[LimitlessMarkdownExpanded] Calling triggerAutoFetch to get fresh data from Limitless API for date:', extractedDate);
      
      // First, trigger a fresh fetch from Limitless API
      const autoFetchStart = Date.now();
      console.log('[LimitlessMarkdownExpanded] About to call triggerAutoFetch...');
      console.log('[LimitlessMarkdownExpanded] limitlessData object:', typeof limitlessData);
      console.log('[LimitlessMarkdownExpanded] triggerAutoFetch function:', typeof limitlessData.triggerAutoFetch);
      console.log('[LimitlessMarkdownExpanded] Function identity check:', limitlessData.triggerAutoFetch.toString().substring(0, 100));
      console.log('[LimitlessMarkdownExpanded] Function name:', limitlessData.triggerAutoFetch.name);
      
      try {
        await limitlessData.triggerAutoFetch(extractedDate);
        console.log('[LimitlessMarkdownExpanded] triggerAutoFetch await completed normally');
      } catch (triggerError) {
        console.error('[LimitlessMarkdownExpanded] triggerAutoFetch threw an error:', triggerError);
        throw triggerError;
      }
      
      const autoFetchEnd = Date.now();
      
      console.log('[LimitlessMarkdownExpanded] Step 7: triggerAutoFetch completed in', autoFetchEnd - autoFetchStart, 'ms');
      console.log('[LimitlessMarkdownExpanded] Waiting additional 2 seconds for backend processing...');
      
      // Wait additional time for backend processing (triggerAutoFetch has internal 1000ms delay)
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      console.log('[LimitlessMarkdownExpanded] Step 8: Now fetching processed data from database');
      console.log('[LimitlessMarkdownExpanded] Calling limitlessData.fetchData with:', { targetDate: extractedDate, allowAutoFetch: false });
      
      const md = await limitlessData.fetchData(extractedDate, false);
      
      console.log('[LimitlessMarkdownExpanded] Step 9: fetchData completed');
      console.log('[LimitlessMarkdownExpanded] fetchData result type:', typeof md);
      console.log('[LimitlessMarkdownExpanded] fetchData result length:', md ? md.length : 'null');
      console.log('[LimitlessMarkdownExpanded] fetchData result preview:', md ? md.substring(0, 100) + '...' : 'null');
      
      if (md) {
        console.log('[LimitlessMarkdownExpanded] Step 10: Processing successful fetchData result');
        
        const newTimestamp = `${new Date().toLocaleDateString('en-US', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        })} (Refreshed at ${new Date().toLocaleTimeString()})`;
        console.log('[LimitlessMarkdownExpanded] Generated new timestamp:', newTimestamp);
        
        // Update the current view with fresh data immediately
        const refreshedData = {
          ...data,
          markdownContent: md,
          timestamp: newTimestamp
        };
        
        console.log('[LimitlessMarkdownExpanded] Created refreshedData object');
        console.log('[LimitlessMarkdownExpanded] New markdownContent length:', refreshedData.markdownContent.length);
        
        setData(refreshedData);
        console.log('[LimitlessMarkdownExpanded] setData called with refreshed data');
        
        // Force a small delay to check if it's a rendering timing issue
        setTimeout(() => {
          console.log('[LimitlessMarkdownExpanded] RENDER CHECK: Current data state after setData:', {
            title: data.title,
            timestamp: data.timestamp,
            markdownLength: data.markdownContent?.length,
            refreshedTitle: refreshedData.title,
            refreshedTimestamp: refreshedData.timestamp,
            refreshedMarkdownLength: refreshedData.markdownContent?.length
          });
        }, 100);
        
        // Update sessionStorage if using key-based storage
        const keyParam = searchParams.get('key');
        console.log('[LimitlessMarkdownExpanded] Step 11: Checking sessionStorage update');
        console.log('[LimitlessMarkdownExpanded] keyParam:', keyParam);
        
        if (keyParam) {
          sessionStorage.setItem(keyParam, JSON.stringify(refreshedData));
          console.log('[LimitlessMarkdownExpanded] SessionStorage updated with key:', keyParam);
        } else {
          console.log('[LimitlessMarkdownExpanded] No keyParam - sessionStorage not updated');
        }
        
        console.log('[LimitlessMarkdownExpanded] SUCCESS: Refresh completed successfully');
        
      } else {
        console.log('[LimitlessMarkdownExpanded] Step 10: No data returned from fetchData');
        console.log('[LimitlessMarkdownExpanded] Navigating back due to no data');
        navigate(-1);
      }
      
    } catch (error) {
      console.error('[LimitlessMarkdownExpanded] ERROR during refresh:', error);
      console.error('[LimitlessMarkdownExpanded] Error name:', error instanceof Error ? error.name : 'Unknown');
      console.error('[LimitlessMarkdownExpanded] Error message:', error instanceof Error ? error.message : 'Unknown error');
      console.error('[LimitlessMarkdownExpanded] Error stack:', error instanceof Error ? error.stack : 'No stack trace');
    } finally {
      console.log('[LimitlessMarkdownExpanded] Step 12: Setting refreshing state to false');
      setRefreshing(false);
      const endTime = Date.now();
      console.log(`[LimitlessMarkdownExpanded] ===== REFRESH COMPLETED in ${endTime - startTime}ms at ${new Date().toISOString()} =====`);
    }
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-5xl mx-auto">
          <div className="text-center">
            <p className="text-xl text-newspaper-byline">Loading content...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 bg-white shadow-sm z-10 p-4 border-b">
        <div className="max-w-5xl mx-auto">
          <div className="relative">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-newspaper-headline">
                {data.title || "Limitless Content"}
              </h1>
              <div className="flex items-center justify-center space-x-2 mt-1">
                <Clock className="w-4 h-4 text-newspaper-byline" />
                <span className="text-sm text-newspaper-byline">{data.timestamp}</span>
              </div>
              <div className="flex items-center justify-center space-x-2 mt-2">
                <Badge variant="secondary">
                  Limitless
                </Badge>
              </div>
            </div>
            
            {/* Refresh button positioned in top right */}
            <div className="absolute top-0 right-0 z-20">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
                className="p-2 bg-white hover:bg-gray-50 border-gray-200 shadow-sm"
                title="Refresh limitless data"
              >
                <RefreshCw className={`w-4 h-4 text-gray-600 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto p-8">
        <Card className="p-8">
          <div className="prose prose-lg max-w-none 
            prose-headings:text-newspaper-headline 
            prose-p:text-newspaper-byline 
            prose-hr:border-gray-300
            prose-h1:text-3xl prose-h1:font-bold prose-h1:mb-4 prose-h1:mt-6
            prose-h2:text-2xl prose-h2:font-bold prose-h2:mb-3 prose-h2:mt-5
            prose-h3:text-xl prose-h3:font-bold prose-h3:mb-2 prose-h3:mt-4
            prose-p:mb-3 prose-p:leading-relaxed prose-p:text-base
            prose-ul:mb-4 prose-li:mb-1
            prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm
            prose-pre:bg-gray-100 prose-pre:p-4 prose-pre:rounded-md prose-pre:overflow-x-auto
            prose-blockquote:border-l-4 prose-blockquote:border-gray-300 prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:my-3
            prose-a:text-blue-600 prose-a:hover:text-blue-800 prose-a:underline">
            <MarkdownRenderer content={data.markdownContent} />
          </div>
        </Card>
      </div>
    </div>
  );
};
