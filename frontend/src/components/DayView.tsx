import { NewsSection } from "./NewsSection";
import { NewsFeed } from "./NewsFeed";
import { TwitterFeed } from "./TwitterFeed";
import { MusicHistory } from "./MusicHistory";
import { PhotoGallery } from "./PhotoGallery";
import { useEffect, useState } from "react";
import { getTodayYYYYMMDD } from "../lib/utils";

interface DayViewProps {
  selectedDate?: string;
  onDateChange?: (date: string) => void;
}

/**
 * DayView component displays content for a specific date
 * @param selectedDate - The date to display content for (YYYY-MM-DD format)
 * @param onDateChange - Callback when date changes
 */
export const DayView = ({ selectedDate, onDateChange }: DayViewProps) => {
  const [displayDate, setDisplayDate] = useState<string>('');
  
  useEffect(() => {
    const initializeDate = async () => {
      if (selectedDate) {
        setDisplayDate(selectedDate);
      } else {
        const today = await getTodayYYYYMMDD();
        setDisplayDate(today);
      }
    };
    initializeDate();
  }, [selectedDate]);
  
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
          <NewsSection selectedDate={displayDate} />
        </div>
        
        {/* Right column - News feed, Twitter, and Music */}
        <div className="lg:col-span-1 space-y-8">
          <NewsFeed selectedDate={displayDate} />
          <TwitterFeed selectedDate={displayDate} />
          <MusicHistory selectedDate={displayDate} />
        </div>
      </div>
      
      {/* Horizontal divider */}
      <div className="my-12 border-t-2 border-newspaper-divider"></div>
      
      {/* Bottom sections */}
      <div>
        {/* Photo gallery */}
        <PhotoGallery selectedDate={displayDate} />
      </div>
      
      
    </div>
  );
};
