import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface DataItem {
  id: string;
  namespace: string;
  days_date: string;
  metadata?: {
    cleaned_markdown?: string;
    markdown?: string;
    original_lifelog?: {
      markdown?: string;
    };
    [key: string]: any;
  };
  content?: string;
}

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
 * ExtendedNewsCard component
 * Displays limitless markdown content from data_items.metadata.cleaned_markdown
 * This component is used within a Card wrapper in NewsSection, so no outer Card needed
 */
export const ExtendedNewsCard = ({ selectedDate }: Pick<ExtendedNewsCardProps, 'selectedDate'>) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [fetchAttempted, setFetchAttempted] = useState<Set<string>>(new Set());
  const [autoFetching, setAutoFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    console.log(`[ExtendedNewsCard] useEffect triggered with selectedDate:`, selectedDate);
    console.log(`[ExtendedNewsCard] useEffect - current state:`, {
      markdownContent: markdownContent.length > 0 ? `${markdownContent.length} chars` : 'empty',
      loading,
      fetchAttempted: Array.from(fetchAttempted),
      autoFetching,
      fetchError
    });
    
    // Reset fetch attempted state when date changes
    if (selectedDate) {
      console.log(`[ExtendedNewsCard] Date changed to: ${selectedDate}, resetting fetch state`);
      setFetchError(null);
      setAutoFetching(false);
      // Clear markdown content to force refetch for new date
      setMarkdownContent('');
    }
    
    /**
     * Trigger automatic fetch for a specific date when no data exists
     */
    const triggerAutomaticFetch = async (targetDate: string) => {
      try {
        console.log(`[ExtendedNewsCard] Starting automatic fetch for date: ${targetDate}`);
        setAutoFetching(true);
        setFetchError(null);
        
        // Mark this date as attempted
        setFetchAttempted(prev => new Set([...prev, targetDate]));
        
        // Call the on-demand fetch API
        const fetchApiUrl = `http://localhost:8000/calendar/api/limitless/fetch/${targetDate}`;
        console.log(`[ExtendedNewsCard] Calling automatic fetch API: ${fetchApiUrl}`);
        
        const fetchResponse = await fetch(fetchApiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        
        console.log(`[ExtendedNewsCard] Automatic fetch API response status: ${fetchResponse.status}`);
        
        if (fetchResponse.ok) {
          const fetchResult = await fetchResponse.json();
          console.log(`[ExtendedNewsCard] Automatic fetch result:`, fetchResult);
          
          if (fetchResult.success) {
            console.log(`[ExtendedNewsCard] Automatic fetch successful: ${fetchResult.message}`);
            
            // Wait a moment for data to be processed
            setTimeout(async () => {
              console.log(`[ExtendedNewsCard] Refetching data after successful automatic fetch`);
              // Refetch the data to display it
              await fetchLimitlessMarkdown(false); // Pass false to skip auto-fetch on retry
            }, 1000);
            
          } else {
            console.error(`[ExtendedNewsCard] Automatic fetch failed:`, fetchResult.message);
            setFetchError(`Failed to fetch data: ${fetchResult.message}`);
            setMarkdownContent('');
          }
        } else {
          const errorText = await fetchResponse.text();
          console.error(`[ExtendedNewsCard] Automatic fetch API error:`, fetchResponse.status, errorText);
          setFetchError(`Failed to fetch data: ${fetchResponse.status} ${fetchResponse.statusText}`);
          setMarkdownContent('');
        }
        
      } catch (error) {
        console.error(`[ExtendedNewsCard] Error during automatic fetch:`, error);
        setFetchError(`Network error during automatic fetch: ${error instanceof Error ? error.message : 'Unknown error'}`);
        setMarkdownContent('');
      } finally {
        setAutoFetching(false);
        setLoading(false);
      }
    };

    /**
     * Fetch cleaned markdown from limitless data_items
     * Gets markdown content from data_items.metadata.cleaned_markdown
     * Automatically triggers on-demand fetch if no data exists
     */
    const fetchLimitlessMarkdown = async (allowAutoFetch: boolean = true) => {
      try {
        // Debug selectedDate prop
        console.log(`[ExtendedNewsCard] Component received selectedDate prop:`, selectedDate, typeof selectedDate);
        
        // Use selectedDate if provided, otherwise use today's date
        let targetDate: string;
        if (selectedDate) {
          targetDate = selectedDate;
          console.log(`[ExtendedNewsCard] Using selectedDate: ${targetDate}`);
        } else {
          const now = new Date();
          const year = now.getFullYear();
          const month = String(now.getMonth() + 1).padStart(2, '0');
          const day = String(now.getDate()).padStart(2, '0');
          targetDate = `${year}-${month}-${day}`;
          console.log(`[ExtendedNewsCard] No selectedDate provided, using today: ${targetDate}`);
        }
        
        console.log(`[ExtendedNewsCard] Final targetDate: ${targetDate}`);
        
        // First, try to fetch data for the target date with cache-busting timestamp
        const timestamp = Date.now();
        const apiUrl = `http://localhost:8000/calendar/api/data_items/${targetDate}?namespaces=limitless&_t=${timestamp}`;
        console.log(`[ExtendedNewsCard] API URL: ${apiUrl}`);
        console.log(`[ExtendedNewsCard] FETCH: Making API request at ${new Date().toISOString()}`);
        
        let response = await fetch(apiUrl, {
          // Add cache-busting headers to prevent browser caching
          headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
          }
        });
        console.log(`[ExtendedNewsCard] Response status: ${response.status}`);
        console.log(`[ExtendedNewsCard] Response headers:`, Object.fromEntries(response.headers.entries()));
        
        if (response.ok) {
          let dataItems: DataItem[] = await response.json();
          console.log(`[ExtendedNewsCard] RECEIVED: ${dataItems.length} items for targetDate=${targetDate}`);
          
          // Verify all items have correct days_date
          const dateMismatchItems = dataItems.filter(item => item.days_date !== targetDate);
          if (dateMismatchItems.length > 0) {
            console.error(`[ExtendedNewsCard] DATE MISMATCH! Found ${dateMismatchItems.length} items with wrong days_date:`, 
              dateMismatchItems.map(item => ({id: item.id, days_date: item.days_date})));
          }
          
          // Log first few items for debugging
          if (dataItems.length > 0) {
            console.log(`[ExtendedNewsCard] First 3 items:`, dataItems.slice(0, 3).map(item => ({
              id: item.id,
              namespace: item.namespace,
              days_date: item.days_date,
              has_content: !!item.content,
              has_metadata: !!item.metadata,
              has_cleaned_markdown: !!item.metadata?.cleaned_markdown,
              content_preview: item.content?.substring(0, 50) + '...'
            })));
          }
          
          // No fallback logic - only display data for requested date
          
          if (dataItems.length > 0) {
            // Combine all cleaned markdown content from all items
            const markdownParts: string[] = [];
            
            dataItems.forEach((item, index) => {
              let itemMarkdown = '';
              
              // Priority order: cleaned_markdown > markdown > original_lifelog.markdown > content
              if (item.metadata?.cleaned_markdown) {
                itemMarkdown = item.metadata.cleaned_markdown;
                console.log(`[ExtendedNewsCard] Item ${index}: Using cleaned_markdown (${itemMarkdown.length} chars)`);
              } else if (item.metadata?.markdown) {
                itemMarkdown = item.metadata.markdown;
                console.log(`[ExtendedNewsCard] Item ${index}: Using metadata.markdown (${itemMarkdown.length} chars)`);
              } else if (item.metadata?.original_lifelog?.markdown) {
                itemMarkdown = item.metadata.original_lifelog.markdown;
                console.log(`[ExtendedNewsCard] Item ${index}: Using original_lifelog.markdown (${itemMarkdown.length} chars)`);
              } else if (item.content) {
                itemMarkdown = item.content;
                console.log(`[ExtendedNewsCard] Item ${index}: Using content (${itemMarkdown.length} chars)`);
              } else {
                console.log(`[ExtendedNewsCard] Item ${index}: No markdown content found`);
              }
              
              if (itemMarkdown) {
                markdownParts.push(itemMarkdown);
              }
            });
            
            console.log(`[ExtendedNewsCard] Total markdown parts: ${markdownParts.length}, total chars: ${markdownParts.join('').length}`);
            
            // Join all markdown content with separators
            const combinedMarkdown = markdownParts.join('\n\n---\n\n');
            
            if (combinedMarkdown.trim().length > 0) {
              setMarkdownContent(prevContent => prevContent + combinedMarkdown);
              console.log(`[ExtendedNewsCard] Final markdown content length: ${combinedMarkdown.length}`);
            } else {
              console.log(`[ExtendedNewsCard] No displayable markdown content found for ${targetDate}`);
              
              // Trigger automatic fetch if no data and not already attempted
              if (allowAutoFetch && !fetchAttempted.has(targetDate) && !autoFetching) {
                console.log(`[ExtendedNewsCard] Triggering automatic fetch for ${targetDate}`);
                await triggerAutomaticFetch(targetDate);
              } else {
                console.log(`[ExtendedNewsCard] Automatic fetch already attempted or in progress for ${targetDate}, or auto-fetch disabled`);
                setMarkdownContent(''); // Set to empty string if no displayable content
              }
            }
          } else {
            console.log(`[ExtendedNewsCard] No data items found for ${targetDate}`);
            
            // Trigger automatic fetch if no data and not already attempted
            if (allowAutoFetch && !fetchAttempted.has(targetDate) && !autoFetching) {
              console.log(`[ExtendedNewsCard] Triggering automatic fetch for ${targetDate} (no items)`);
              await triggerAutomaticFetch(targetDate);
            } else {
              console.log(`[ExtendedNewsCard] Automatic fetch already attempted or in progress for ${targetDate}, or auto-fetch disabled`);
              setMarkdownContent(''); // Set to empty string if no data items
            }
          }
        } else {
          console.error('Failed to fetch limitless data:', response.status);
          setMarkdownContent(''); // Don't show error, just empty content
        }
        
        setLoading(false);
      } catch (error) {
        console.error('Error fetching limitless data:', error);
        setMarkdownContent(''); // Don't show error, just empty content
        setLoading(false);
      }
    };

    fetchLimitlessMarkdown();
  }, [selectedDate]); // Re-run when selectedDate changes


  return (
    <>
      {/* Header - Fixed (no outer Card, as parent NewsSection already provides Card) */}
      <div className="p-1 border-b border-gray-200">
        <div className="flex items-center space-x-2 mb-3">
          <Badge variant="outline" className="text-xs">
            Limitless
          </Badge>
          <span className="text-newspaper-byline text-xs">
            Today's Activity
          </span>
        </div>

      </div>

      {/* Scrollable Markdown Content Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 h-[400px]">
        {loading || autoFetching ? (
          <div className="text-center py-4 text-gray-500 text-sm">
            {autoFetching ? 'Automatically fetching Limitless data...' : 'Loading Limitless content...'}
          </div>
        ) : fetchError ? (
          <div className="text-center py-4 text-red-500 text-sm">
            {fetchError}
          </div>
        ) : markdownContent ? (
          <div className="prose prose-sm max-w-none prose-headings:text-newspaper-headline prose-p:text-newspaper-byline prose-hr:border-gray-300">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({children}) => <h1 className="text-2xl font-bold text-newspaper-headline mb-3 mt-4">{children}</h1>,
                h2: ({children}) => <h2 className="text-xl font-bold text-newspaper-headline mb-2 mt-3">{children}</h2>,
                h3: ({children}) => <h3 className="text-lg font-bold text-newspaper-headline mb-2 mt-3">{children}</h3>,
                p: ({children}) => <p className="mb-2 text-newspaper-byline">{children}</p>,
                hr: () => <hr className="my-4 border-gray-300" />,
                // Support for code blocks and inline code
                code: ({children, ...props}: any) => {
                  const className = props.className || '';
                  const isInline = !className.includes('language-');
                  
                  return isInline ? (
                    <code className="bg-gray-100 px-1 py-0.5 rounded text-sm">{children}</code>
                  ) : (
                    <pre className="bg-gray-100 p-3 rounded-md overflow-x-auto">
                      <code className={className}>
                        {children}
                      </code>
                    </pre>
                  );
                },
                // Support for lists - without bullet points
                ul: ({children}) => <ul className="list-none mb-2">{children}</ul>,
                ol: ({children}) => <ol className="list-none mb-2">{children}</ol>,
                li: ({children}) => <li className="mb-1">{children}</li>,
                // Support for blockquotes
                blockquote: ({children}) => (
                  <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2">{children}</blockquote>
                ),
                // Support for links
                a: ({href, children}) => (
                  <a href={href} className="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                )
              }}
            >
              {markdownContent}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="text-center py-4 text-gray-500 text-sm">
            No Limitless content available
          </div>
        )}
      </div>
    </>
  );
};