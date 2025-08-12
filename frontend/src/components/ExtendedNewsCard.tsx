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

  useEffect(() => {
    console.log(`[ExtendedNewsCard] useEffect triggered with selectedDate:`, selectedDate);
    /**
     * Fetch cleaned markdown from limitless data_items
     * Gets markdown content from data_items.metadata.cleaned_markdown
     * Only displays data for the requested date - no fallback behavior
     */
    const fetchLimitlessMarkdown = async () => {
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
        
        // First, try to fetch data for the target date
        const apiUrl = `http://localhost:8000/calendar/api/data_items/${targetDate}?namespaces=limitless`;
        console.log(`[ExtendedNewsCard] API URL: ${apiUrl}`);
        
        let response = await fetch(apiUrl);
        console.log(`[ExtendedNewsCard] Response status: ${response.status}`);
        
        if (response.ok) {
          let dataItems: DataItem[] = await response.json();
          console.log(`[ExtendedNewsCard] Received ${dataItems.length} items for ${targetDate}`);
          
          // Log first item for debugging
          if (dataItems.length > 0) {
            console.log(`[ExtendedNewsCard] First item:`, {
              id: dataItems[0].id,
              namespace: dataItems[0].namespace,
              days_date: dataItems[0].days_date,
              has_content: !!dataItems[0].content,
              has_metadata: !!dataItems[0].metadata,
              has_cleaned_markdown: !!dataItems[0].metadata?.cleaned_markdown,
              metadata_keys: dataItems[0].metadata ? Object.keys(dataItems[0].metadata) : []
            });
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
              setMarkdownContent(''); // Set to empty string if no displayable content
            }
          } else {
            console.log(`[ExtendedNewsCard] No data items found for ${targetDate}`);
            setMarkdownContent(''); // Set to empty string if no data items
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
        {loading ? (
          <div className="text-center py-4 text-gray-500 text-sm">
            Loading Limitless content...
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