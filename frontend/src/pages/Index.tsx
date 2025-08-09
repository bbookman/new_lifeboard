import { NewspaperMasthead } from "@/components/NewspaperMasthead";
import { NewsSection } from "@/components/NewsSection";
import { TwitterFeed } from "@/components/TwitterFeed";
import { MusicHistory } from "@/components/MusicHistory";
import { PhotoGallery } from "@/components/PhotoGallery";

const Index = () => {
  return (
    <div className="min-h-screen bg-background font-body">
      <NewspaperMasthead />
      
      <div className="container mx-auto px-4 pb-12">
        {/* Main newspaper grid layout */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Left column - News (main content) */}
          <div className="lg:col-span-3 lg:border-r lg:border-newspaper-divider lg:pr-8">
            <NewsSection />
          </div>
          
          {/* Right column - Social feed only */}
          <div className="lg:col-span-1">
            <TwitterFeed />
          </div>
        </div>
        
        {/* Horizontal divider */}
        <div className="my-12 border-t-2 border-newspaper-divider"></div>
        
        {/* Bottom sections */}
        <div className="space-y-12">
          {/* Music History */}
          <MusicHistory />
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
    </div>
  );
};

export default Index;