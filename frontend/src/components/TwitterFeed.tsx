import { ContentCard, ContentItemData, DailySummaryData } from "./ContentCard";

// Sample data with the new structure
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

const sampleTweets: ContentItemData[] = [
  {
    type: "content-item",
    id: "1",
    username: "Tech News Daily",
    handle: "@technewsdaily",
    content: "Breaking: Major AI breakthrough announced by researchers. The implications for machine learning are significant. This could change everything we know about artificial intelligence development.",
    timestamp: "2h",
    likes: 1240,
    retweets: 340,
    verified: true,
    source: "twitter"
  },
  {
    type: "content-item",
    id: "2",
    username: "World Updates",
    handle: "@worldupdates",
    content: "Climate summit reaches historic agreement. World leaders commit to ambitious new targets for carbon reduction. A pivotal moment for environmental policy.",
    timestamp: "4h",
    likes: 890,
    retweets: 560,
    verified: true,
    source: "twitter"
  },
  {
    type: "content-item",
    id: "3",
    username: "Sports Central",
    handle: "@sportscentral",
    content: "Incredible match last night! The championship game delivered everything fans hoped for and more. What a season finale!",
    timestamp: "6h",
    likes: 2340,
    retweets: 890,
    verified: true,
    source: "twitter"
  }
];

export const TwitterFeed = () => {
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-social-accent pb-2">
        <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
          Social Pulse
        </h2>
        <p className="text-newspaper-byline font-body text-sm">
          Trending conversations and updates
        </p>
      </div>
      
      <div className="space-y-4">
        {/* Daily Summary Card (top-most) */}
        <ContentCard data={sampleDailySummary} />
        
        {/* Content Item Cards (below) */}
        {sampleTweets.map((tweet) => (
          <ContentCard key={tweet.id} data={tweet} />
        ))}
      </div>
    </div>
  );
};