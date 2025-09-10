import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { RefreshCw, Play } from "lucide-react";
import musicImage from "@/assets/music-placeholder.jpg";
import { useSpotifyTracks, useSpotifyRefresh, useSpotifyAuth } from "../hooks/useSpotifyData";
import SpotifyPlayer from "./SpotifyPlayer";
import { SpotifyTrack } from "../lib/api";
import { useState } from "react";

interface MusicHistoryProps {
  selectedDate?: string;
}

const getMoodFromAudioFeatures = (audioFeatures?: SpotifyTrack['audio_features']): string => {
  if (!audioFeatures) return 'Unknown';
  
  const { valence, energy, danceability } = audioFeatures;
  
  if (valence > 0.7 && energy > 0.7) return 'Energetic';
  if (valence > 0.6 && danceability > 0.6) return 'Upbeat';
  if (valence < 0.4 && energy < 0.4) return 'Chill';
  if (energy < 0.3) return 'Peaceful';
  if (danceability > 0.7) return 'Danceable';
  if (valence > 0.5) return 'Happy';
  return 'Smooth';
};

const getMoodColor = (mood: string) => {
  switch (mood) {
    case 'Chill': return 'bg-blue-100 text-blue-800';
    case 'Energetic': return 'bg-red-100 text-red-800';
    case 'Peaceful': return 'bg-green-100 text-green-800';
    case 'Smooth': return 'bg-purple-100 text-purple-800';
    case 'Upbeat': return 'bg-orange-100 text-orange-800';
    case 'Danceable': return 'bg-pink-100 text-pink-800';
    case 'Happy': return 'bg-yellow-100 text-yellow-800';
    default: return 'bg-gray-100 text-gray-800';
  }
};

const formatDuration = (durationMs: number): string => {
  const minutes = Math.floor(durationMs / 60000);
  const seconds = Math.floor((durationMs % 60000) / 1000);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const formatPlayTime = (playedAt: string): string => {
  const playedDate = new Date(playedAt);
  const now = new Date();
  const diffMs = now.getTime() - playedDate.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  
  if (diffHours > 0) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  } else if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
  } else {
    return 'Just now';
  }
};

const calculateTotalStats = (tracks: SpotifyTrack[]) => {
  const totalDurationMs = tracks.reduce((sum, track) => sum + track.duration_ms, 0);
  const totalMinutes = Math.floor(totalDurationMs / 60000);
  const trackCount = tracks.length;
  
  // Determine dominant mood
  const moods = tracks.map(track => getMoodFromAudioFeatures(track.audio_features));
  const moodCounts = moods.reduce((acc, mood) => {
    acc[mood] = (acc[mood] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  const dominantMood = Object.entries(moodCounts)
    .sort(([,a], [,b]) => b - a)[0]?.[0] || 'Mixed';
  
  return {
    trackCount,
    totalMinutes,
    dominantMood: dominantMood.toLowerCase()
  };
};

/**
 * MusicHistory component displays music listening history for a specific date
 * @param selectedDate - The date to display music history for (YYYY-MM-DD format)
 */
export const MusicHistory = ({ selectedDate }: MusicHistoryProps) => {
  const { data: tracks, isLoading, error } = useSpotifyTracks(selectedDate);
  const { data: authStatus, isLoading: authLoading } = useSpotifyAuth();
  const refreshMutation = useSpotifyRefresh(selectedDate);
  const [showNoDataModal, setShowNoDataModal] = useState(false);

  const handleRefresh = async () => {
    try {
      const result = await refreshMutation.mutateAsync();
      if (!result || result.length === 0) {
        setShowNoDataModal(true);
      }
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };
  
  // Show loading state only if user is authenticated and tracks are loading
  // Skip loading spinner entirely if user is not authenticated
  if (isLoading && !authLoading && authStatus?.authenticated === true) {
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
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-music-accent"></div>
            <span className="ml-3 text-newspaper-byline">Loading your music history...</span>
          </div>
        </Card>
      </div>
    );
  }
  
  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="border-b-2 border-music-accent pb-2 relative">
          <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
            Music Journal
          </h2>
          <p className="text-newspaper-byline font-body text-sm">
            Your daily soundtrack and listening history
            {selectedDate && ` • ${selectedDate}`}
          </p>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isLoading || refreshMutation.isPending}
            className="absolute top-0 right-0 h-8 w-8"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading || refreshMutation.isPending ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        
        <Card className="p-6 bg-gradient-to-r from-music-accent/5 to-music-accent/10">
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-red-500 mb-2">⚠️</div>
              <p className="text-newspaper-byline mb-4">
                Failed to load music history: {error.message}
              </p>
              <p className="text-newspaper-byline text-xs">
                Click the refresh button above to retry
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }
  
  // Empty state
  if (!tracks || tracks.length === 0) {
    return (
      <div className="space-y-6">
        <div className="border-b-2 border-music-accent pb-2 relative">
          <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
            Music Journal
          </h2>
          <p className="text-newspaper-byline font-body text-sm">
            Your daily soundtrack and listening history
            {selectedDate && ` • ${selectedDate}`}
          </p>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isLoading || refreshMutation.isPending}
            className="absolute top-0 right-0 h-8 w-8"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading || refreshMutation.isPending ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        
        <Card className="p-6 bg-gradient-to-r from-music-accent/5 to-music-accent/10">
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-4xl mb-4">🎵</div>
              <h3 className="font-headline text-lg font-bold text-newspaper-headline mb-2">
                {authStatus?.authenticated === false ? 'Connect Your Spotify Account' : 'No music history found'}
              </h3>
              <p className="text-newspaper-byline mb-4">
                {authStatus?.authenticated === false 
                  ? 'Connect your Spotify account to see your listening history and discover your music patterns'
                  : selectedDate 
                    ? `No tracks were played on ${selectedDate}`
                    : 'No recent tracks found'
                }
              </p>
              <p className="text-newspaper-byline text-xs">
                {authStatus?.authenticated === false 
                  ? 'Click the refresh button above to connect with Spotify'
                  : 'Click the refresh button above to fetch your Spotify data'
                }
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }
  
  // Calculate stats for the tracks
  const stats = calculateTotalStats(tracks);
  
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-music-accent pb-2 relative">
        <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
          Music Journal
        </h2>
        <p className="text-newspaper-byline font-body text-sm">
          Your daily soundtrack and listening history
          {selectedDate && ` • ${selectedDate}`}
        </p>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          disabled={isLoading || refreshMutation.isPending}
          className="absolute top-0 right-0 h-8 w-8"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading || refreshMutation.isPending ? 'animate-spin' : ''}`} />
        </Button>
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
              {stats.trackCount} track{stats.trackCount !== 1 ? 's' : ''} • {stats.totalMinutes} minutes • Mostly {stats.dominantMood} vibes
            </p>
          </div>
        </div>
        
        <div className="space-y-4">
          {tracks.map((track) => {
            const mood = getMoodFromAudioFeatures(track.audio_features);
            const albumArt = track.album?.images?.[0]?.url;
            const releaseYear = track.album?.release_date ? new Date(track.album.release_date).getFullYear() : null;
            const spotifyUrl = track.external_urls?.spotify;
            
            return (
              <div key={`${track.id}-${track.played_at}`} className="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start p-4 space-x-4">
                  {/* Left column: Album art */}
                  <div className="flex-shrink-0">
                    <div className="w-16 h-16 rounded-lg overflow-hidden shadow-sm bg-gray-100">
                      {albumArt ? (
                        <img 
                          src={albumArt} 
                          alt={`${track.album?.name || 'Album'} cover`}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                          🎵
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Right column: Track info and controls */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-body font-semibold text-newspaper-headline truncate">
                          {track.name}
                        </h4>
                        <p className="text-newspaper-byline text-sm truncate">
                          {track.artists?.[0]?.name || 'Unknown Artist'}
                        </p>
                        <p className="text-newspaper-byline text-xs truncate">
                          {track.album?.name || 'Unknown Album'}
                          {releaseYear && ` • ${releaseYear}`}
                        </p>
                        
                        <div className="flex items-center space-x-2 mt-2">
                          <Badge className={`text-xs ${getMoodColor(mood)}`}>
                            {mood}
                          </Badge>
                          <span className="text-newspaper-byline text-xs font-mono">
                            {formatDuration(track.duration_ms)}
                          </span>
                          {track.played_at && (
                            <span className="text-newspaper-byline text-xs">
                              {formatPlayTime(track.played_at)}
                            </span>
                          )}
                        </div>
                      </div>
                      
                      {/* Play button */}
                      {spotifyUrl && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 flex-shrink-0"
                          onClick={() => window.open(spotifyUrl, '_blank')}
                        >
                          <Play className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Spotify Player Integration */}
                <div className="px-4 pb-4">
                  <SpotifyPlayer
                    currentTrack={{
                      id: track.id,
                      name: track.name,
                      artists: track.artists || [{ name: 'Unknown Artist' }],
                      album: {
                        name: track.album?.name || 'Unknown Album',
                        images: track.album?.images || []
                      },
                      preview_url: track.preview_url || null,
                      duration_ms: track.duration_ms
                    }}
                    className="border-t pt-3"
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>
      
      <div className="text-center">
        <button className="font-body text-music-accent hover:text-music-accent/80 transition-colors text-sm font-medium">
          View Full Listening History →
        </button>
      </div>

      {/* No Data Modal */}
      <Dialog open={showNoDataModal} onOpenChange={setShowNoDataModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>No Spotify Data Found</DialogTitle>
            <DialogDescription>
              {authStatus?.authenticated === false ? (
                <>
                  You need to connect your Spotify account to view your music history. 
                  Click the refresh button to start the authentication process.
                </>
              ) : (
                <>
                  No Spotify data found for today. Make sure you've been listening to music on Spotify 
                  and try refreshing again later.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    </div>
  );
};
