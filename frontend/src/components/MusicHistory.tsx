import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import musicImage from "@/assets/music-placeholder.jpg";

interface MusicTrack {
  id: string;
  title: string;
  artist: string;
  album: string;
  playTime: string;
  duration: string;
  mood?: string;
}

interface MusicHistoryProps {
  selectedDate?: string;
}

const sampleTracks: MusicTrack[] = [
  {
    id: "1",
    title: "Midnight Reflections",
    artist: "The Velvet Underground",
    album: "Late Night Sessions",
    playTime: "2 hours ago",
    duration: "4:23",
    mood: "Chill"
  },
  {
    id: "2",
    title: "Electric Dreams",
    artist: "Synthwave Collective",
    album: "Neon Nights",
    playTime: "4 hours ago",
    duration: "3:45",
    mood: "Energetic"
  },
  {
    id: "3",
    title: "Ocean Waves",
    artist: "Ambient Nature",
    album: "Peaceful Moments",
    playTime: "6 hours ago",
    duration: "5:12",
    mood: "Peaceful"
  },
  {
    id: "4",
    title: "City Lights",
    artist: "Jazz Fusion",
    album: "Urban Stories",
    playTime: "8 hours ago",
    duration: "6:01",
    mood: "Smooth"
  }
];

const getMoodColor = (mood: string) => {
  switch (mood) {
    case 'Chill': return 'bg-blue-100 text-blue-800';
    case 'Energetic': return 'bg-red-100 text-red-800';
    case 'Peaceful': return 'bg-green-100 text-green-800';
    case 'Smooth': return 'bg-purple-100 text-purple-800';
    default: return 'bg-gray-100 text-gray-800';
  }
};

/**
 * MusicHistory component displays music listening history for a specific date
 * @param selectedDate - The date to display music history for (YYYY-MM-DD format)
 */
export const MusicHistory = ({ selectedDate }: MusicHistoryProps) => {
  // TODO: In a real app, fetch music data based on selectedDate
  
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-music-accent pb-2">
        <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
          Music Journal
        </h2>
        <p className="text-newspaper-byline font-body text-sm">
          Your daily soundtrack and listening history
          {selectedDate && ` • ${selectedDate}`}
        </p>
      </div>
      
      <Card className="p-6 bg-gradient-to-r from-music-accent/5 to-music-accent/10">
        <div className="flex items-center space-x-4 mb-6">
          <div className="w-20 h-20 rounded-lg overflow-hidden shadow-lg">
            <img 
              src={musicImage} 
              alt="Music collage"
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <h3 className="font-headline text-xl font-bold text-newspaper-headline">
              Today's Listening Stats
            </h3>
            <p className="text-newspaper-byline font-body">
              4 tracks • 19 minutes • Mostly chill vibes
            </p>
          </div>
        </div>
        
        <div className="space-y-4">
          {sampleTracks.map((track) => (
            <div key={track.id} className="flex items-center justify-between p-4 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow">
              <div className="flex-1">
                <h4 className="font-body font-semibold text-newspaper-headline">
                  {track.title}
                </h4>
                <p className="text-newspaper-byline text-sm">
                  {track.artist} • {track.album}
                </p>
              </div>
              
              <div className="flex items-center space-x-3">
                {track.mood && (
                  <Badge className={`text-xs ${getMoodColor(track.mood)}`}>
                    {track.mood}
                  </Badge>
                )}
                <span className="text-newspaper-byline text-sm font-mono">
                  {track.duration}
                </span>
                <span className="text-newspaper-byline text-xs">
                  {track.playTime}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
      
      <div className="text-center">
        <button className="font-body text-music-accent hover:text-music-accent/80 transition-colors text-sm font-medium">
          View Full Listening History →
        </button>
      </div>
    </div>
  );
};