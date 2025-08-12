import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";

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
}

/**
 * ExtendedNewsCard component
 * Displays limitless markdown content from data_items.metadata.cleaned_markdown
 * This component is used within a Card wrapper in NewsSection, so no outer Card needed
 */
export const ExtendedNewsCard = ({
  headline,
  summary,
  author,
  timestamp,
  category,
  readTime,
  breaking
}: ExtendedNewsCardProps) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    /**
     * Fetch cleaned markdown from limitless data_items
     * Gets markdown content from data_items.metadata.cleaned_markdown
     * Falls back to most recent available data if today has no data
     */
    const fetchLimitlessMarkdown = async () => {
      try {
        // Get today's date in local timezone (not UTC)
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const today = `${year}-${month}-${day}`;
        
        console.log(`Fetching data for local date: ${today}`);
        
        // First, try to fetch data for today
        let response = await fetch(`http://localhost:8000/calendar/api/data_items/${today}?namespaces=limitless`);
        
        if (response.ok) {
          let dataItems: DataItem[] = await response.json();
          
          // If no data for today, fetch the most recent available data
          if (dataItems.length === 0) {
            console.log(`No data for today (${today}), fetching most recent available data...`);
            
            // Get list of days with data
            const daysResponse = await fetch('http://localhost:8000/calendar/api/days-with-data');
            if (daysResponse.ok) {
              const daysData = await daysResponse.json();
              const allDays = daysData.all || [];
              
              // Find the most recent date with data
              if (allDays.length > 0) {
                const mostRecentDate = allDays[0]; // Days are returned in descending order
                console.log(`Fetching data for most recent date: ${mostRecentDate}`);
                
                // Fetch data for the most recent date
                response = await fetch(`http://localhost:8000/calendar/api/data_items/${mostRecentDate}?namespaces=limitless`);
                if (response.ok) {
                  dataItems = await response.json();
                  
                  // Add a note about the date
                  if (dataItems.length > 0) {
                    const dateObj = new Date(mostRecentDate + 'T00:00:00');
                    const formattedDate = dateObj.toLocaleDateString('en-US', {
                      weekday: 'long',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    });
                    setMarkdownContent(`# Data from ${formattedDate}\n\n`);
                  }
                }
              }
            }
          }
          
          if (dataItems.length > 0) {
            // Combine all cleaned markdown content from all items
            const markdownParts: string[] = [];
            
            dataItems.forEach(item => {
              let itemMarkdown = '';
              
              // Priority order: cleaned_markdown > markdown > original_lifelog.markdown > content
              if (item.metadata?.cleaned_markdown) {
                itemMarkdown = item.metadata.cleaned_markdown;
              } else if (item.metadata?.markdown) {
                itemMarkdown = item.metadata.markdown;
              } else if (item.metadata?.original_lifelog?.markdown) {
                itemMarkdown = item.metadata.original_lifelog.markdown;
              } else if (item.content) {
                itemMarkdown = item.content;
              }
              
              if (itemMarkdown) {
                markdownParts.push(itemMarkdown);
              }
            });
            
            // Join all markdown content with separators
            const combinedMarkdown = markdownParts.join('\n\n---\n\n');
            setMarkdownContent(prevContent => prevContent + combinedMarkdown);
          } else {
            setMarkdownContent('No Limitless data available.');
          }
        } else {
          console.error('Failed to fetch limitless data:', response.status);
          setMarkdownContent('Failed to load Limitless data.');
        }
        
        setLoading(false);
      } catch (error) {
        console.error('Error fetching limitless data:', error);
        setMarkdownContent('Error loading Limitless data.');
        setLoading(false);
      }
    };

    fetchLimitlessMarkdown();
  }, []);

  // Simple markdown rendering function (basic)
  const renderMarkdown = (markdown: string) => {
    if (!markdown) return '';
    
    // Basic markdown parsing - you could use a proper markdown library here
    return markdown
      .split('\n')
      .map(line => {
        if (line.startsWith('# ')) {
          return `<h1 class="text-2xl font-bold text-newspaper-headline mb-3 mt-4">${line.substring(2)}</h1>`;
        } else if (line.startsWith('## ')) {
          return `<h2 class="text-xl font-bold text-newspaper-headline mb-2 mt-3">${line.substring(3)}</h2>`;
        } else if (line.startsWith('### ')) {
          return `<h3 class="text-lg font-bold text-newspaper-headline mb-2 mt-3">${line.substring(4)}</h3>`;
        } else if (line.trim() === '---') {
          return `<hr class="my-4 border-gray-300" />`;
        } else if (line.trim() === '') {
          return '<br />';
        } else {
          return `<p class="mb-2 text-newspaper-byline">${line}</p>`;
        }
      })
      .join('');
  };

  return (
    <>
      {/* Header - Fixed (no outer Card, as parent NewsSection already provides Card) */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center space-x-2 mb-3">
          <Badge variant="outline" className="text-xs">
            Limitless
          </Badge>
          <span className="text-newspaper-byline text-xs">
            Today's Activity
          </span>
        </div>
        
        <h3 className="font-headline font-bold text-xl text-newspaper-headline mb-3 leading-tight">
          Limitless
        </h3>
        
        <p className="font-body text-newspaper-byline leading-relaxed mb-4">
          Your cleaned markdown content from today's activity
        </p>
      </div>

      {/* Scrollable Markdown Content Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 h-[400px]">
        {loading ? (
          <div className="text-center py-4 text-gray-500 text-sm">
            Loading Limitless content...
          </div>
        ) : markdownContent ? (
          <div 
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(markdownContent) }}
          />
        ) : (
          <div className="text-center py-4 text-gray-500 text-sm">
            No Limitless content available
          </div>
        )}
      </div>
    </>
  );
};