import { Card } from "@/components/ui/card";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface Tweet {
  id: string;
  username: string;
  handle: string;
  content: string;
  timestamp: string;
  likes: number;
  retweets: number;
  verified?: boolean;
}

const sampleTweets: Tweet[] = [
  {
    id: "1",
    username: "Tech News Daily",
    handle: "@technewsdaily",
    content: "Breaking: Major AI breakthrough announced by researchers. The implications for machine learning are significant. This could change everything we know about artificial intelligence development.",
    timestamp: "2h",
    likes: 1240,
    retweets: 340,
    verified: true
  },
  {
    id: "2",
    username: "World Updates",
    handle: "@worldupdates",
    content: "Climate summit reaches historic agreement. World leaders commit to ambitious new targets for carbon reduction. A pivotal moment for environmental policy.",
    timestamp: "4h",
    likes: 890,
    retweets: 560,
    verified: true
  },
  {
    id: "3",
    username: "Sports Central",
    handle: "@sportscentral",
    content: "Incredible match last night! The championship game delivered everything fans hoped for and more. What a season finale!",
    timestamp: "6h",
    likes: 2340,
    retweets: 890,
    verified: true
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
        {sampleTweets.map((tweet) => (
          <Card key={tweet.id} className="p-4 hover:shadow-lg transition-shadow">
            <div className="flex space-x-3">
              <Avatar className="w-12 h-12">
                <div className="w-full h-full bg-social-accent rounded-full flex items-center justify-center">
                  <span className="text-white font-bold text-lg">
                    {tweet.username.charAt(0)}
                  </span>
                </div>
              </Avatar>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2 mb-1">
                  <h3 className="font-body font-semibold text-newspaper-headline truncate">
                    {tweet.username}
                  </h3>
                  {tweet.verified && (
                    <Badge variant="secondary" className="bg-social-accent text-white text-xs">
                      ✓
                    </Badge>
                  )}
                  <span className="text-newspaper-byline text-sm">
                    {tweet.handle}
                  </span>
                  <span className="text-newspaper-byline text-sm">•</span>
                  <span className="text-newspaper-byline text-sm">
                    {tweet.timestamp}
                  </span>
                </div>
                
                <p className="font-body text-newspaper-headline leading-relaxed mb-3">
                  {tweet.content}
                </p>
                
                <div className="flex space-x-6 text-newspaper-byline text-sm">
                  <span className="hover:text-social-accent cursor-pointer transition-colors">
                    ♡ {tweet.likes.toLocaleString()}
                  </span>
                  <span className="hover:text-social-accent cursor-pointer transition-colors">
                    ↻ {tweet.retweets.toLocaleString()}
                  </span>
                  <span className="hover:text-social-accent cursor-pointer transition-colors">
                    ⤴ Share
                  </span>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};