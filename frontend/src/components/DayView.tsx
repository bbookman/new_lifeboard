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

export const DayView = ({ selectedDate, onDateChange }: DayViewProps) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null);
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
      
      {/* Content */}
      <div className="card">
        <div className="card-content">
          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
              Loading day data...
            </div>
          )}
          
          {error && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#d32f2f' }}>
              {error}
            </div>
          )}
          
          {!loading && !error && !markdownContent && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
              No data found for {formatDate(currentDate)}
            </div>
          )}
          
          {!loading && !error && markdownContent && (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {markdownContent}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
