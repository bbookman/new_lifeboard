import { NewsSection } from "./NewsSection";
import { NewsFeed } from "./NewsFeed";
import { TwitterFeed } from "./TwitterFeed";
import { MusicHistory } from "./MusicHistory";
import { PhotoGallery } from "./PhotoGallery";
import { useEffect, useState, useCallback } from "react";
import { getTodayYYYYMMDD } from "../lib/utils";
import { useWebSocket, DayUpdateData } from "../hooks/useWebSocket";

interface DayViewProps {
  selectedDate?: string;
  onDateChange?: (date: string) => void;
  setFormattedDate: (date: string) => void;
}

/**
 * DayView component displays content for a specific date
 * @param selectedDate - The date to display content for (YYYY-MM-DD format)
 * @param onDateChange - Callback when date changes
 */
export const DayView = ({ selectedDate, onDateChange, setFormattedDate }: DayViewProps) => {
  const [displayDate, setDisplayDate] = useState<string>('');
  const [dataRefreshTrigger, setDataRefreshTrigger] = useState<number>(0);
  
  // Use selectedDate directly when available, otherwise use state
  const effectiveDate = selectedDate || displayDate;
  
  useEffect(() => {
    const initializeDate = async () => {
      console.log('[DayView] Initializing date, selectedDate:', selectedDate);
      if (selectedDate) {
        console.log('[DayView] Using selectedDate:', selectedDate);
        setDisplayDate(selectedDate);
      } else {
        const today = await getTodayYYYYMMDD();
        console.log('[DayView] Using today:', today);
        setDisplayDate(today);
      }
    };
    initializeDate();
  }, [selectedDate]);

  useEffect(() => {
    const formatted = formatDisplayDate(effectiveDate);
    console.log('[DayView] Setting formatted date:', { effectiveDate, formatted });
    setFormattedDate(formatted);
  }, [effectiveDate, setFormattedDate]);

  // Handle WebSocket day update notifications
  const handleDayUpdate = useCallback((data: DayUpdateData) => {
    console.log('[DayView] Received day update:', data);
    
    // Check if the update is for the currently displayed date
    if (data.days_date === effectiveDate && data.status === 'complete') {
      console.log(`[DayView] Complete data available for ${effectiveDate}, triggering refresh`);
      
      // Trigger a re-render to fetch updated data
      setDataRefreshTrigger(prev => prev + 1);
    }
  }, [effectiveDate]);

  // Initialize WebSocket connection
  const { isConnected } = useWebSocket({
    autoConnect: true,
    onDayUpdate: handleDayUpdate,
    onConnect: () => {
      console.log('[DayView] WebSocket connected');
    },
    onDisconnect: () => {
      console.log('[DayView] WebSocket disconnected');
    },
    onError: (error) => {
      console.error('[DayView] WebSocket error:', error);
    }
  });
  
  /**
   * Format date for display
   */
  const formatDisplayDate = (dateString: string) => {
    if (!dateString) return 'Loading...';
    
    const date = new Date(dateString + 'T00:00:00');
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    };
    return date.toLocaleDateString('en-US', options);
  };
  
  return (
    <div>
      
      
      {/* Main newspaper grid layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column - News (main content) */}
        <div className="lg:col-span-2 lg:border-r lg:border-newspaper-divider lg:pr-8">
          <NewsSection selectedDate={effectiveDate} key={`news-${effectiveDate}-${dataRefreshTrigger}`} />
        </div>
        
        {/* Right column - News feed, Twitter, and Music */}
        <div className="lg:col-span-1 space-y-8">
          <NewsFeed selectedDate={effectiveDate} key={`newsfeed-${effectiveDate}-${dataRefreshTrigger}`} />
          <TwitterFeed selectedDate={effectiveDate} key={`twitter-${effectiveDate}-${dataRefreshTrigger}`} />
          <MusicHistory selectedDate={effectiveDate} key={`music-${effectiveDate}-${dataRefreshTrigger}`} />
        </div>
      </div>
      
      {/* Horizontal divider */}
      <div className="my-12 border-t-2 border-newspaper-divider"></div>
      
      {/* Bottom sections */}
      <div>
        {/* Photo gallery */}
        <PhotoGallery selectedDate={effectiveDate} key={`gallery-${effectiveDate}-${dataRefreshTrigger}`} />
      </div>
      
      
    </div>
  );
};
