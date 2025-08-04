import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SectionHeader } from './SectionHeader';

interface DayViewProps {
  selectedDate?: string; // Format: YYYY-MM-DD
  onDateChange?: (date: string) => void;
}

export const DayView = ({ selectedDate, onDateChange }: DayViewProps) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Default to today if no date provided
  const currentDate = selectedDate || new Date().toISOString().split('T')[0];
  const today = new Date().toISOString().split('T')[0];
  const isFutureDate = currentDate >= today;
  
  const fetchDayData = async (date: string) => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('[DAY VIEW] Fetching data for date:', date);
      
      const response = await fetch(`http://localhost:8000/calendar/api/day/${date}`, {
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
        console.log('[DAY VIEW] Markdown content length:', data.markdown_content?.length || 0);
        console.log('[DAY VIEW] Markdown content preview:', data.markdown_content?.substring(0, 200) || 'No content');
        
        // Check for headers in the received content
        if (data.markdown_content) {
          const hasHeaders = /^#+\s/m.test(data.markdown_content);
          console.log('[DAY VIEW] Content has headers:', hasHeaders);
          
          if (hasHeaders) {
            const headers = data.markdown_content.match(/^#+\s.+$/gm);
            console.log('[DAY VIEW] Headers found:', headers);
          }
        }
        
        setMarkdownContent(data.markdown_content || '');
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
    fetchDayData(currentDate);
  }, [currentDate]);
  
  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
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
    const newDate = date.toISOString().split('T')[0];
    onDateChange?.(newDate);
  };
  
  const goToToday = () => {
    const today = new Date().toISOString().split('T')[0];
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