import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { useAppleMusicData } from "../hooks/useAppleMusicData";

interface AppleMusicCardProps {
  selectedDate?: string;
}

/**
 * AppleMusicCard component displays Apple Music listening history in a table format
 * Sorted by play count descending (most plays first)
 * This component is used within a Card wrapper in SummarySection, so no outer Card needed
 */
export const AppleMusicCard = ({ selectedDate }: AppleMusicCardProps) => {
  const { plays, loading, error, refreshPlays } = useAppleMusicData(selectedDate);

  const handleRefresh = async () => {
    await refreshPlays();
  };

  return (
    <>
      {/* Header - Fixed */}
      <div className="p-1 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <h3 className="font-headline text-xl font-bold text-newspaper-headline">
              Music of the Day
            </h3>
            
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={loading}
              className="p-2 bg-white hover:bg-gray-50 border-gray-200"
              title="Refresh Apple Music data"
            >
              <RefreshCw className={`w-4 h-4 text-gray-600 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>

      {/* Scrollable Table Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 h-[400px]">
        {loading ? (
          <div className="text-center py-4 text-gray-500 text-sm">
            Loading Apple Music data...
          </div>
        ) : error ? (
          <div className="text-center py-4 text-red-500 text-sm">
            {error}
          </div>
        ) : plays.length > 0 ? (
          <table className="w-full border-collapse">
            <thead className="sticky top-0 bg-white border-b border-gray-200">
              <tr>
                <th className="text-left py-2 px-3 font-body font-semibold text-newspaper-headline text-sm">
                  Artist
                </th>
                <th className="text-left py-2 px-3 font-body font-semibold text-newspaper-headline text-sm">
                  Album
                </th>
                <th className="text-left py-2 px-3 font-body font-semibold text-newspaper-headline text-sm">
                  Song
                </th>
                <th className="text-center py-2 px-3 font-body font-semibold text-newspaper-headline text-sm">
                  Number of plays
                </th>
              </tr>
            </thead>
            <tbody>
              {plays.map((play, index) => (
                <tr
                  key={`${play.artist}-${play.album}-${play.song}-${index}`}
                  className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                >
                  <td className="py-2 px-3 font-body text-newspaper-headline text-sm">
                    {play.artist}
                  </td>
                  <td className="py-2 px-3 font-body text-newspaper-byline text-sm">
                    {play.album}
                  </td>
                  <td className="py-2 px-3 font-body text-newspaper-headline text-sm">
                    {play.song}
                  </td>
                  <td className="py-2 px-3 font-body text-newspaper-headline text-sm text-center font-semibold">
                    {play.play_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-4 text-gray-500 text-sm">
            No Apple Music plays available for this date
          </div>
        )}
      </div>
    </>
  );
};
