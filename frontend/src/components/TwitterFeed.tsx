import { useEffect, useState } from "react";
import { 
  Carousel, 
  CarouselContent, 
  CarouselItem, 
  CarouselApi
} from "@/components/ui/carousel";
import { ContentCard, ContentItemData } from "./ContentCard";
import { fetchTwitterDataItems, DataItem } from "@/lib/api";

interface TwitterFeedProps {
  selectedDate?: string;
}

/**
 * Convert DataItem from database to ContentItemData format for display
 */
const convertDataItemToContentItem = (dataItem: DataItem): ContentItemData => {
  console.log(`🔍 [convertDataItemToContentItem] Processing item ${dataItem.id}`);
  console.log(`📅 Days date: ${dataItem.days_date}`);
  console.log(`📄 Metadata type:`, typeof dataItem.metadata);
  console.log(`📄 Raw metadata:`, dataItem.metadata);
  
  let parsedMetadata: any = {};
  
  // Handle both string and object metadata
  if (typeof dataItem.metadata === 'string') {
    try {
      parsedMetadata = JSON.parse(dataItem.metadata);
      console.log(`✅ [convertDataItemToContentItem] Successfully parsed metadata string for ${dataItem.id}`);
    } catch (error) {
      console.warn(`❌ [convertDataItemToContentItem] Failed to parse metadata string for ${dataItem.id}:`, error);
    }
  } else if (typeof dataItem.metadata === 'object' && dataItem.metadata !== null) {
    parsedMetadata = dataItem.metadata;
    console.log(`✅ [convertDataItemToContentItem] Metadata already parsed for ${dataItem.id}`);
  } else {
    console.warn(`⚠️ [convertDataItemToContentItem] Unexpected metadata type for ${dataItem.id}:`, typeof dataItem.metadata);
  }

  // Media detection with comprehensive logging
  console.log(`🖼️ [convertDataItemToContentItem] Media detection for ${dataItem.id}:`);
  console.log(`   - parsedMetadata.media:`, parsedMetadata.media);
  console.log(`   - parsedMetadata.media?.has_media:`, parsedMetadata.media?.has_media);
  console.log(`   - parsedMetadata.media?.media_urls:`, parsedMetadata.media?.media_urls);
  
  // Try alternative media field locations
  const alternativeMediaFields = {
    'media_urls': parsedMetadata.media_urls, // Top-level media_urls field
    'entities.media': parsedMetadata.entities?.media,
    'extended_entities.media': parsedMetadata.extended_entities?.media,
    'attachments': parsedMetadata.attachments,
    'photo': parsedMetadata.photo,
    'photos': parsedMetadata.photos,
    'images': parsedMetadata.images
  };
  
  console.log(`🔍 [convertDataItemToContentItem] Alternative media fields:`, alternativeMediaFields);
  
  // Media URL determination with fallbacks
  let hasMedia = false;
  let mediaUrl = undefined;
  
  // Primary path: parsedMetadata.media (handle both array and JSON string)
  if (parsedMetadata.media?.has_media) {
    let mediaUrls = parsedMetadata.media?.media_urls;
    
    // If media_urls is a string (JSON encoded), parse it
    if (typeof mediaUrls === 'string') {
      try {
        mediaUrls = JSON.parse(mediaUrls);
        console.log(`🔧 [convertDataItemToContentItem] Parsed media_urls string:`, mediaUrls);
      } catch (error) {
        console.warn(`⚠️ [convertDataItemToContentItem] Failed to parse media_urls string:`, mediaUrls);
      }
    }
    
    if (Array.isArray(mediaUrls) && mediaUrls.length > 0) {
      hasMedia = true;
      mediaUrl = mediaUrls[0];
      console.log(`✅ [convertDataItemToContentItem] Found media via primary path: ${mediaUrl}`);
    }
  }
  // Fallback 1: entities.media (Twitter API format)
  else if (parsedMetadata.entities?.media?.[0]?.media_url_https) {
    hasMedia = true;
    mediaUrl = parsedMetadata.entities.media[0].media_url_https;
    console.log(`✅ [convertDataItemToContentItem] Found media via entities.media: ${mediaUrl}`);
  }
  // Fallback 2: extended_entities.media
  else if (parsedMetadata.extended_entities?.media?.[0]?.media_url_https) {
    hasMedia = true;
    mediaUrl = parsedMetadata.extended_entities.media[0].media_url_https;
    console.log(`✅ [convertDataItemToContentItem] Found media via extended_entities.media: ${mediaUrl}`);
  }
  // Fallback 3: direct photo field
  else if (parsedMetadata.photo) {
    hasMedia = true;
    mediaUrl = parsedMetadata.photo;
    console.log(`✅ [convertDataItemToContentItem] Found media via photo field: ${mediaUrl}`);
  }
  // Fallback 4: photos array
  else if (parsedMetadata.photos?.[0]) {
    hasMedia = true;
    mediaUrl = parsedMetadata.photos[0];
    console.log(`✅ [convertDataItemToContentItem] Found media via photos array: ${mediaUrl}`);
  }
  // Fallback 5: top-level media_urls (handle string or array)
  else if (parsedMetadata.media_urls) {
    let topLevelMediaUrls = parsedMetadata.media_urls;
    
    // If it's a JSON string, parse it
    if (typeof topLevelMediaUrls === 'string') {
      try {
        topLevelMediaUrls = JSON.parse(topLevelMediaUrls);
        console.log(`🔧 [convertDataItemToContentItem] Parsed top-level media_urls string:`, topLevelMediaUrls);
      } catch (error) {
        console.warn(`⚠️ [convertDataItemToContentItem] Failed to parse top-level media_urls string:`, topLevelMediaUrls);
      }
    }
    
    if (Array.isArray(topLevelMediaUrls) && topLevelMediaUrls.length > 0) {
      hasMedia = true;
      mediaUrl = topLevelMediaUrls[0];
      console.log(`✅ [convertDataItemToContentItem] Found media via top-level media_urls: ${mediaUrl}`);
    }
  }
  else {
    console.log(`❌ [convertDataItemToContentItem] No media found for ${dataItem.id}`);
  }

  const result = {
    type: "content-item" as const,
    id: dataItem.id,
    username: parsedMetadata.username || parsedMetadata.author || "Twitter User",
    handle: parsedMetadata.handle || parsedMetadata.screen_name || "@user",
    content: dataItem.content,
    timestamp: parsedMetadata.timestamp || dataItem.created_at,
    verified: parsedMetadata.verified || false,
    source: "twitter" as const,
    likes: parsedMetadata.likes || parsedMetadata.favorite_count,
    retweets: parsedMetadata.retweets || parsedMetadata.retweet_count,
    url: parsedMetadata.url || parsedMetadata.permalink_url,
    hasMedia,
    mediaUrl
  };

  console.log(`📤 [convertDataItemToContentItem] Final result for ${dataItem.id}:`, {
    hasMedia: result.hasMedia,
    mediaUrl: result.mediaUrl,
    username: result.username
  });

  return result;
};

/**
 * TwitterFeed component displays Twitter posts in a carousel format
 * Data comes from data_items table where namespace='twitter'
 * @param selectedDate - The date to display tweets for (YYYY-MM-DD format)
 */
export const TwitterFeed = ({ selectedDate }: TwitterFeedProps) => {
  const [twitterData, setTwitterData] = useState<ContentItemData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [api, setApi] = useState<CarouselApi>();
  const [current, setCurrent] = useState(0);

  console.log(`[TwitterFeed] Received selectedDate: ${selectedDate}`);

  useEffect(() => {
    const fetchTweets = async () => {
      console.log(`[TwitterFeed] useEffect triggered with selectedDate: ${selectedDate}`);
      
      if (!selectedDate) {
        console.log(`[TwitterFeed] No selectedDate provided, setting loading to false`);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        
        console.log(`[TwitterFeed] Fetching Twitter data items for date: ${selectedDate}`);
        const dataItems = await fetchTwitterDataItems(selectedDate);
        console.log(`[TwitterFeed] Fetched ${dataItems.length} Twitter data items for ${selectedDate}:`, dataItems);
        
        // Check if we're looking at the right date with media
        const mediaCount = dataItems.filter(item => {
          try {
            const meta = JSON.parse(item.metadata);
            return meta.media?.has_media === true;
          } catch {
            return false;
          }
        }).length;
        console.log(`[TwitterFeed] Items with media on ${selectedDate}: ${mediaCount}/${dataItems.length}`);
        
        // Convert database items to ContentItemData format
        const contentItems = dataItems.map(convertDataItemToContentItem);
        console.log(`[TwitterFeed] Converted to ${contentItems.length} content items:`, contentItems);
        
        // Log media information for debugging
        const mediaItems = contentItems.filter(item => item.hasMedia);
        console.log(`[TwitterFeed] Items with media: ${mediaItems.length}/${contentItems.length}`, 
          mediaItems.map(item => ({ id: item.id, mediaUrl: item.mediaUrl })));
        
        setTwitterData(contentItems);
      } catch (err) {
        console.error('[TwitterFeed] Error fetching Twitter data items:', err);
        setError('Failed to load tweets');
        setTwitterData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchTweets();
  }, [selectedDate]);

  useEffect(() => {
    if (!api) {
      return;
    }

    setCurrent(api.selectedScrollSnap());

    api.on("select", () => {
      setCurrent(api.selectedScrollSnap());
    });
  }, [api]);

  // Loading state
  if (loading) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
        <div className="flex items-center justify-center p-8 min-h-[200px] border border-newspaper-divider rounded-lg">
          <div className="text-newspaper-byline">Loading tweets...</div>
        </div>
      </div>
    );
  }

  // Error state  
  if (error) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
        <div className="flex items-center justify-center p-8 min-h-[200px] border border-newspaper-divider rounded-lg">
          <div className="text-red-600">Error: {error}</div>
        </div>
      </div>
    );
  }

  // No data state - this is what shows when no twitter data is available in database
  if (twitterData.length === 0) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
        <div className="flex items-center justify-center p-8 min-h-[200px] border border-newspaper-divider rounded-lg">
          <div className="text-newspaper-byline">No tweets available</div>
        </div>
      </div>
    );
  }

  // Render carousel with Twitter data from database
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
      
      {twitterData.length === 1 ? (
        // Single tweet - use same fixed size
        <div className="w-full h-[450px] border border-gray-200 rounded-lg overflow-hidden">
          <div className="h-full overflow-y-auto">
            <ContentCard data={twitterData[0]} />
          </div>
        </div>
      ) : (
        // Multiple tweets - use carousel with fixed size (3x larger)
        <div className="w-full h-[450px] border border-gray-200 rounded-lg overflow-hidden relative">
          <Carousel 
            className="w-full h-full" 
            opts={{ align: "start", loop: true }}
            setApi={setApi}
          >
            <CarouselContent className="h-full">
              {twitterData.map((tweet) => (
                <CarouselItem key={tweet.id} className="basis-full h-full">
                  <div className="h-full overflow-y-auto">
                    <ContentCard data={tweet} />
                  </div>
                </CarouselItem>
              ))}
            </CarouselContent>
          </Carousel>
          
          {/* Dots indicator at bottom - positioned inside fixed container */}
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex space-x-2">
            {twitterData.map((_, index) => (
              <button
                key={index}
                onClick={() => api?.scrollTo(index)}
                className={`w-3 h-3 rounded-full transition-colors ${
                  index === current 
                    ? 'bg-newspaper-byline' 
                    : 'bg-newspaper-divider hover:bg-newspaper-byline/60'
                }`}
                aria-label={`Go to tweet ${index + 1}`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};