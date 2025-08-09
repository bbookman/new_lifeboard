import { NewsSection } from "./NewsSection";
import { TwitterFeed } from "./TwitterFeed";
import { MusicHistory } from "./MusicHistory";
import { PhotoGallery } from "./PhotoGallery";

interface DayViewProps {
  selectedDate?: string;
  onDateChange?: (date: string) => void;
}

export const DayView = ({ selectedDate, onDateChange }: DayViewProps) => {
  return (
    <div>
      {/* Main newspaper grid layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column - News (main content) */}
        <div className="lg:col-span-2 lg:border-r lg:border-newspaper-divider lg:pr-8">
          <NewsSection />
        </div>
        
        {/* Right column - Social feed and Music */}
        <div className="lg:col-span-1 space-y-8">
          <TwitterFeed />
          <MusicHistory />
        </div>
      </div>
      
      {/* Horizontal divider */}
      <div className="my-12 border-t-2 border-newspaper-divider"></div>
      
      {/* Bottom sections */}
      <div>
        {/* Photo gallery */}
        <PhotoGallery />
      </div>
      
      {/* Footer */}
      <footer className="mt-12 pt-8 border-t border-newspaper-divider">
        <div className="text-center">
          <p className="font-body text-newspaper-byline text-sm">
            The Daily Digest • Your Personalized News Experience
          </p>
          <p className="font-body text-newspaper-byline text-xs mt-1">
            Curated from your social feeds, music history, and daily moments
          </p>
        </div>
      </footer>
    </div>
  );
};
