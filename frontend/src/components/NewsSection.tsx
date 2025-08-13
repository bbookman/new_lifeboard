import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import newsImage from "@/assets/news-placeholder.jpg";
import { ExtendedNewsCard } from "./ExtendedNewsCard";

interface NewsArticle {
  id: string;
  headline: string;
  summary: string;
  author: string;
  timestamp: string;
  category: string;
  readTime: string;
  breaking?: boolean;
}

interface NewsSectionProps {
  selectedDate?: string;
}

const sampleNews: NewsArticle[] = [
  {
    id: "1",
    headline: "Global Markets React to Economic Policy Changes",
    summary: "Stock markets worldwide show mixed reactions following the announcement of new economic policies. Analysts predict continued volatility as markets adjust to the changing landscape.",
    author: "Sarah Johnson",
    timestamp: "1 hour ago",
    category: "Business",
    readTime: "3 min read",
    breaking: true
  },
  {
    id: "2",
    headline: "Revolutionary Medical Treatment Shows Promise in Clinical Trials",
    summary: "A groundbreaking new treatment for chronic conditions has shown remarkable results in Phase III trials, offering hope to millions of patients worldwide.",
    author: "Dr. Michael Chen",
    timestamp: "3 hours ago",
    category: "Health",
    readTime: "5 min read"
  }
];

/**
 * NewsSection component displays news articles for a specific date
 * @param selectedDate - The date to display news for (YYYY-MM-DD format)
 */
export const NewsSection = ({ selectedDate }: NewsSectionProps) => {
  console.log(`[NewsSection] Received selectedDate: ${selectedDate}`);
  
  // TODO: In a real app, fetch news data based on selectedDate
  // For now, we'll display sample data with a note about the selected date
  
  return (
    <div className="space-y-6">
      <div className="space-y-6">
        {sampleNews.map((article, index) => {
          // Use ExtendedNewsCard for the second item (index 1)
          if (index === 1) {
            console.log(`[NewsSection] Passing selectedDate to ExtendedNewsCard: ${selectedDate}`);
            return (
              <ExtendedNewsCard
                key={article.id}
                headline={article.headline}
                summary={article.summary}
                author={article.author}
                timestamp={article.timestamp}
                category={article.category}
                readTime={article.readTime}
                breaking={article.breaking}
                selectedDate={selectedDate}
              />
            );
          }
          
          // Regular card for other items
          return (
            <Card key={article.id} className={`overflow-hidden hover:shadow-lg transition-shadow ${index === 0 ? 'border-l-4 border-l-news-accent' : ''}`}>
              {index === 0 && (
                <div className="aspect-[16/9] relative overflow-hidden">
                  <img
                    src={newsImage}
                    alt="Breaking news"
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute top-4 left-4">
                    <Badge className="bg-news-accent text-white font-bold">
                      BREAKING
                    </Badge>
                  </div>
                </div>
              )}
              
              <div className="p-6">
                <div className="flex items-center space-x-2 mb-3">
                  <Badge variant="outline" className="text-xs">
                    {article.category}
                  </Badge>
                  {article.breaking && index !== 0 && (
                    <Badge className="bg-news-accent text-white text-xs">
                      BREAKING
                    </Badge>
                  )}
                  <span className="text-newspaper-byline text-xs">
                    {article.readTime}
                  </span>
                </div>
                
                <h3 className={`font-headline font-bold text-newspaper-headline mb-3 leading-tight ${index === 0 ? 'text-2xl' : 'text-xl'}`}>
                  {article.headline}
                </h3>
                
                <p className="font-body text-newspaper-byline leading-relaxed mb-4">
                  {article.summary}
                </p>
                
                <div className="flex items-center justify-between text-sm text-newspaper-byline">
                  <span className="font-medium">By {article.author}</span>
                  <span>{article.timestamp}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};