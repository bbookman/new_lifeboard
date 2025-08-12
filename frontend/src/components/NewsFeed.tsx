import { ContentCard, ContentItemData, DailySummaryData } from "./ContentCard";
import { useEffect, useState } from "react";
import { fetchNewsForDate, NewsArticle as ApiNewsArticle } from "@/lib/api";

interface NewsFeedProps {
  selectedDate?: string;
}

// Sample data with the new structure - keeping the daily summary for now
const sampleDailySummary: DailySummaryData = {
  type: "daily-summary",
  date: new Date().toISOString().split('T')[0],
  totalItems: 47,
  highlights: [
    "Had a productive morning meeting with the team",
    "Discovered an interesting article about AI developments",
    "Enjoyed a great lunch conversation about sustainability",
    "Made significant progress on the quarterly project"
  ],
  keyThemes: ["Productivity", "Technology", "Sustainability", "Teamwork", "Innovation"],
  moodScore: 8,
  weatherSummary: "Pleasant day with partly cloudy skies, perfect for outdoor activities"
};

/**
 * Convert API news article to ContentItemData format
 */
const convertNewsToContentItem = (apiArticle: ApiNewsArticle, index: number): ContentItemData => {
  // Extract news source from link domain or use fallback
  const getNewsSource = (link?: string): string => {
    if (!link) return "News Source";
    try {
      const url = new URL(link);
      const domain = url.hostname.replace('www.', '');
      // Capitalize first letter
      return domain.charAt(0).toUpperCase() + domain.slice(1);
    } catch {
      return "News Source";
    }
  };

  // Format timestamp
  const formatTimestamp = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    
    if (diffHours < 1) {
      return "Just now";
    } else if (diffHours < 24) {
      return `${diffHours}h`;
    } else {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d`;
    }
  };

  const newsSource = getNewsSource(apiArticle.link);
  
  return {
    type: "content-item",
    id: `news-${index}`,
    username: newsSource,
    handle: `@${newsSource.toLowerCase().replace(/\s+/g, '')}`,
    content: `${apiArticle.title}\n\n${apiArticle.snippet || apiArticle.content.substring(0, 200)}...`,
    timestamp: formatTimestamp(apiArticle.created_at || apiArticle.published_datetime_utc || new Date().toISOString()),
    verified: true,
    source: "news",
    url: apiArticle.link
  };
};

/**
 * NewsFeed component displays news content cards for a specific date
 * @param selectedDate - The date to display news for (YYYY-MM-DD format)
 */
export const NewsFeed = ({ selectedDate }: NewsFeedProps) => {
  const [newsItems, setNewsItems] = useState<ContentItemData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  console.log(`[NewsFeed] Received selectedDate: ${selectedDate}`);

  useEffect(() => {
    const fetchNews = async () => {
      console.log(`[NewsFeed] useEffect triggered with selectedDate: ${selectedDate}`);
      
      if (!selectedDate) {
        console.log(`[NewsFeed] No selectedDate provided, setting loading to false`);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        
        console.log(`[NewsFeed] Fetching news for date: ${selectedDate}`);
        const apiArticles = await fetchNewsForDate(selectedDate);
        console.log(`[NewsFeed] Fetched ${apiArticles.length} articles:`, apiArticles);
        
        // Convert API articles to ContentItemData format
        const contentItems = apiArticles.map((article, index) => {
          const converted = convertNewsToContentItem(article, index);
          console.log(`[NewsFeed] Converted article ${index}:`, converted);
          return converted;
        });
        
        console.log(`[NewsFeed] Setting ${contentItems.length} content items`);
        setNewsItems(contentItems);
      } catch (err) {
        console.error('[NewsFeed] Error fetching news:', err);
        setError('Failed to load news articles');
        setNewsItems([]);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
  }, [selectedDate]);

  // Update the daily summary date to match the selected date
  const dailySummary: DailySummaryData = {
    ...sampleDailySummary,
    date: selectedDate || new Date().toISOString().split('T')[0]
  };
  
  return (
    <div className="space-y-6">
      <div className="space-y-4">
        {/* Daily Summary Card (top-most) */}
        <ContentCard data={dailySummary} />
        
        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center p-8">
            <div className="text-newspaper-byline">Loading news articles...</div>
          </div>
        )}
        
        {/* Error state */}
        {error && (
          <div className="flex items-center justify-center p-8">
            <div className="text-red-600">Error: {error}</div>
          </div>
        )}
        
        {/* No data state */}
        {!loading && !error && newsItems.length === 0 && (
          <div className="flex items-center justify-center p-8">
            <div className="text-newspaper-byline">No news articles available for {selectedDate}</div>
          </div>
        )}
        
        {/* News Content Cards */}
        {!loading && !error && newsItems.map((newsItem) => (
          <ContentCard key={newsItem.id} data={newsItem} />
        ))}
      </div>
    </div>
  );
};