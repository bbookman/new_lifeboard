import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SectionHeader } from './SectionHeader';
import { toYYYYMMDD, getTodayYYYYMMDD } from '../lib/utils';

interface DayViewProps {
  selectedDate?: string; // Format: YYYY-MM-DD
  onDateChange?: (date: string) => void;
}

interface WeatherData {
  forecast_days: any[];
}

interface NewsArticle {
  id: number;
  title: string;
  link?: string;
  snippet?: string;
  thumbnail_url?: string;
  published_datetime_utc?: string;
}

interface NewsData {
  articles: NewsArticle[];
  count: number;
  has_data: boolean;
}

export const DayView = ({ selectedDate, onDateChange }: DayViewProps) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null);
  const [newsData, setNewsData] = useState<NewsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [today, setToday] = useState<string>('');
  
  // Get server's today date on component mount
  useEffect(() => {
    const initializeToday = async () => {
      const serverToday = await getTodayYYYYMMDD();
      setToday(serverToday);
    };
    initializeToday();
  }, []);
  
  // Default to today if no date provided
  const currentDate = selectedDate || today;
  const isFutureDate = currentDate >= today;
  
  const fetchDayData = async (date: string) => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('[DAY VIEW] Fetching data for date:', date);
      
      const response = await fetch(`http://localhost:8000/calendar/api/day/${date}/enhanced`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        mode: 'cors',
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('[DAY VIEW] Received data:', data);

        setMarkdownContent(data.limitless?.markdown_content || '');
        setWeatherData(data.weather || null);

        // Normalize news payload defensively to avoid silent rendering issues
        const rawNews = data.news;
        let normalizedNews: NewsData | null = null;

        try {
          if (Array.isArray(rawNews)) {
            // Backend returned a bare array; wrap it
            normalizedNews = {
              articles: rawNews,
              count: rawNews.length,
              has_data: rawNews.length > 0,
            };
          } else if (rawNews && typeof rawNews === 'object') {
            const articles = Array.isArray((rawNews as any).articles)
              ? (rawNews as any).articles
              : [];
            const count = typeof (rawNews as any).count === 'number' ? (rawNews as any).count : articles.length;
            const has_data =
              typeof (rawNews as any).has_data === 'boolean'
                ? (rawNews as any).has_data
                : articles.length > 0;

            normalizedNews = {
              articles,
              count,
              has_data,
            };
          } else if (rawNews == null) {
            normalizedNews = { articles: [], count: 0, has_data: false };
          } else {
            console.error('[DAY VIEW] Unexpected news payload type:', typeof rawNews);
            normalizedNews = { articles: [], count: 0, has_data: false };
          }
        } catch (e) {
          console.error('[DAY VIEW] Error normalizing news payload:', e, rawNews);
          normalizedNews = { articles: [], count: 0, has_data: false };
        }

        console.log('[DAY VIEW] Normalized news:', normalizedNews);
        setNewsData(normalizedNews);

      } else {
        console.error('[DAY VIEW] HTTP Error:', response.status, response.statusText);
        setError(`Failed to load data: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error('[DAY VIEW] Fetch error:', error);
      setError(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    // Only fetch data if we have both currentDate and today initialized
    if (currentDate && today) {
      fetchDayData(currentDate);
    }
  }, [currentDate, today]);
  
  const formatDate = (dateString: string): string => {
    try {
      // Parse the YYYY-MM-DD string and create date in UTC to avoid timezone issues
      const [year, month, day] = dateString.split('-').map(Number);
      const date = new Date(year, month - 1, day); // Month is 0-indexed
      
      return date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch (error) {
      return dateString;
    }
  };
  
  const navigateDate = (direction: 'prev' | 'next') => {
    const date = new Date(currentDate);
    if (direction === 'prev') {
      date.setDate(date.getDate() - 1);
    } else {
      date.setDate(date.getDate() + 1);
    }
    const newDate = toYYYYMMDD(date);
    onDateChange?.(newDate);
  };
  
  const goToToday = () => {
    onDateChange?.(today);
  };
  
  return (
    <div className="day-view">
      <SectionHeader 
        title={formatDate(currentDate)}
        accentColor="border-news-accent"
      />
      
      {/* Date Navigation */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="flex justify-between items-center">
            <button 
              onClick={() => navigateDate('prev')}
              className="button button-outline"
              style={{ padding: '0.5rem 1rem' }}
            >
              ← Previous Day
            </button>
            
            <div className="flex gap-2">
              <button 
                onClick={goToToday}
                className="button button-primary"
                style={{ padding: '0.5rem 1rem' }}
              >
                Today
              </button>
            </div>
            
            <div style={{ visibility: isFutureDate ? 'hidden' : 'visible' }}>
              <button 
                onClick={() => navigateDate('next')}
                className="button button-outline"
                style={{ padding: '0.5rem 1rem' }}
              >
                Next Day →
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 5-Day Weather Forecast */}
      <div className="card mb-6">
        <div className="card-header">
          <h3 className="text-lg font-semibold text-gray-800">5-Day Weather Forecast</h3>
        </div>
        <div className="card-content">
          <div className="flex flex-row gap-4 justify-between">
            {/* Day 1 */}
            <div className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-lg flex-1 min-h-[120px]">
              <div className="font-medium text-sm text-gray-600 mb-2">Today</div>
              <div className="text-3xl mb-2">☀️</div>
              <div className="font-bold text-lg text-gray-800">72°</div>
              <div className="text-sm text-gray-500">58°</div>
              <div className="text-xs text-gray-500 mt-1 text-center">Sunny</div>
            </div>
            
            {/* Day 2 */}
            <div className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-lg flex-1 min-h-[120px]">
              <div className="font-medium text-sm text-gray-600 mb-2">Tomorrow</div>
              <div className="text-3xl mb-2">⛅</div>
              <div className="font-bold text-lg text-gray-800">68°</div>
              <div className="text-sm text-gray-500">54°</div>
              <div className="text-xs text-gray-500 mt-1 text-center">Partly Cloudy</div>
            </div>
            
            {/* Day 3 */}
            <div className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-lg flex-1 min-h-[120px]">
              <div className="font-medium text-sm text-gray-600 mb-2">Wed</div>
              <div className="text-3xl mb-2">🌧️</div>
              <div className="font-bold text-lg text-gray-800">65°</div>
              <div className="text-sm text-gray-500">52°</div>
              <div className="text-xs text-gray-500 mt-1 text-center">Light Rain</div>
            </div>
            
            {/* Day 4 */}
            <div className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-lg flex-1 min-h-[120px]">
              <div className="font-medium text-sm text-gray-600 mb-2">Thu</div>
              <div className="text-3xl mb-2">☁️</div>
              <div className="font-bold text-lg text-gray-800">63°</div>
              <div className="text-sm text-gray-500">49°</div>
              <div className="text-xs text-gray-500 mt-1 text-center">Cloudy</div>
            </div>
            
            {/* Day 5 */}
            <div className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-lg flex-1 min-h-[120px]">
              <div className="font-medium text-sm text-gray-600 mb-2">Fri</div>
              <div className="text-3xl mb-2">🌤️</div>
              <div className="font-bold text-lg text-gray-800">70°</div>
              <div className="text-sm text-gray-500">55°</div>
              <div className="text-xs text-gray-500 mt-1 text-center">Partly Sunny</div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Main content with adaptive layout based on content */}
      <div className={`grid gap-8 ${
        (loading || error || markdownContent)
          ? 'grid-cols-1 lg:grid-cols-[2fr_1fr]'  // 2:1 ratio when reflection shows
          : 'grid-cols-1 lg:grid-cols-[1fr]'      // Full width when no reflection
      }`}>
        {/* Daily Reflection - Show column for content, loading, or error states */}
        {(loading || error || markdownContent) && (
          <div className="border-r border-gray-200 pr-8">
            <div className="space-y-6">
              {/* Daily Reflection header */}
              <div className="border-b-2 border-blue-500 pb-2">
                <h2 className="text-3xl font-bold text-gray-800">Daily Reflection</h2>
              </div>
              
              {/* Daily Reflection content */}
              <div>
                {loading && (
                  <div className="text-center py-8 text-gray-600">
                    Loading day data...
                  </div>
                )}
                
                {error && (
                  <div className="text-center py-8 text-red-600">
                    {error}
                  </div>
                )}
                
                {!loading && !error && !markdownContent && (
                  <div className="text-center py-8 text-gray-600">
                    No reflection data found for {formatDate(currentDate)}
                  </div>
                )}
                
                {!loading && !error && markdownContent && (
                  <div className="prose prose-lg max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {markdownContent}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Breaking News - Adaptive width based on reflection presence */}
        <div className={`space-y-6 ${
          (loading || error || markdownContent)
            ? '' 
            : 'max-w-4xl mx-auto'  // Center and limit width when full-width
        }`}>
            {/* Breaking News header */}  
            <div className="border-b-2 border-red-500 pb-2">
              <h2 className="text-2xl font-bold text-gray-800">Breaking News</h2>
              <p className="text-sm text-gray-600 mt-1">Latest updates from around the world</p>
            </div>
            
            {/* Breaking News content */}
            <div>
              {console.log('[DAY VIEW] Render check. Loading:', loading, 'News data:', newsData)}
              {loading && (
                <div className="text-center py-4 text-gray-600">
                  Loading news...
                </div>
              )}
              
              {!loading && newsData && (newsData.articles?.length ?? 0) > 0 && (
                <div className="space-y-6">
                  {console.log(`[DAY VIEW] Rendering ${newsData.articles.length} news articles.`)}
                  {newsData.articles.map((article, index) => (
                    <div key={article.id || index} className={`overflow-hidden hover:shadow-lg transition-shadow ${index === 0 ? 'border-l-4 border-l-red-500 pl-4' : ''}`}>
                      {article.thumbnail_url && (
                        <div className="mb-3">
                          <img 
                            src={article.thumbnail_url} 
                            alt={article.title}
                            className="w-full h-40 object-cover rounded-lg"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                        </div>
                      )}
                      <h3 className="font-semibold text-base text-gray-800 leading-tight mb-2 hover:text-blue-600">
                        {article.link ? (
                          <a 
                            href={article.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="transition-colors"
                          >
                            {article.title}
                          </a>
                        ) : (
                          article.title
                        )}
                      </h3>
                      {article.snippet && (
                        <p className="text-sm text-gray-600 leading-relaxed mb-3">
                          {article.snippet}
                        </p>
                      )}
                      {article.published_datetime_utc && (
                        <div className="text-xs text-gray-500 border-b border-gray-200 pb-4 mb-4 last:border-b-0 last:pb-0 last:mb-0">
                          {new Date(article.published_datetime_utc).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              
              {!loading && (!newsData || (newsData.articles?.length ?? 0) === 0) && (
                <div className="text-center py-4 text-gray-600">
                  No news available for this date
                </div>
              )}
            </div>
        </div>
      </div>
    </div>
  );
};
