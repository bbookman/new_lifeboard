import { useEffect, useState, useRef, memo, useCallback } from "react";
import { 
  Carousel, 
  CarouselContent, 
  CarouselItem, 
  CarouselApi
} from "@/components/ui/carousel";
import { ContentCard, ContentItemData } from "./ContentCard";
import { fetchTwitterDataItems, DataItem } from "@/lib/api";
import { TwitterFetchButton } from "./TwitterFetchButton";

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

  // Handle different data source formats (API vs Archive)
  const isArchiveData = parsedMetadata.source_type === 'twitter_archive';
  
  console.log(`🔍 [convertDataItemToContentItem] Data source type: ${parsedMetadata.source_type || 'unknown'}`);
  console.log(`🔍 [convertDataItemToContentItem] Is archive data: ${isArchiveData}`);
  
  let username, handle, timestamp, likes, retweets, url, verified;
  
  if (isArchiveData) {
    // Twitter Archive format - extract from different locations
    username = "Twitter User"; // Archive doesn't typically include username
    handle = "@user"; // Archive doesn't typically include handle
    timestamp = parsedMetadata.original_created_at || dataItem.created_at;
    likes = 0; // Archive doesn't include engagement metrics
    retweets = 0; // Archive doesn't include engagement metrics
    url = null; // Archive doesn't include URL
    verified = false; // Archive doesn't include verification status
    
    console.log(`🔍 [convertDataItemToContentItem] Archive format - using defaults for missing fields`);
  } else {
    // API format - use original field mappings
    username = parsedMetadata.username || parsedMetadata.author || "Twitter User";
    handle = parsedMetadata.handle || parsedMetadata.screen_name || "@user";
    timestamp = parsedMetadata.timestamp || dataItem.created_at;
    likes = parsedMetadata.likes || parsedMetadata.favorite_count;
    retweets = parsedMetadata.retweets || parsedMetadata.retweet_count;
    url = parsedMetadata.url || parsedMetadata.permalink_url;
    verified = parsedMetadata.verified || false;
    
    console.log(`🔍 [convertDataItemToContentItem] API format - using extracted fields`);
  }

  const result = {
    type: "content-item" as const,
    id: dataItem.id,
    username,
    handle,
    content: dataItem.content,
    timestamp,
    verified,
    source: "twitter" as const,
    likes,
    retweets,
    url,
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
const TwitterFeedComponent = ({ selectedDate }: TwitterFeedProps) => {
  const [twitterData, setTwitterData] = useState<ContentItemData[]>([]);
  const [api, setApi] = useState<CarouselApi>();
  const [current, setCurrent] = useState(0);
  
  // Fetch tweets function
  const fetchTweets = useCallback(async () => {
    console.log(`[TwitterFeed DEBUG] === FETCH START ===`);
    console.log(`[TwitterFeed DEBUG] useEffect triggered with selectedDate: ${selectedDate}`);
    
    if (!selectedDate) {
      console.log(`[TwitterFeed DEBUG] No selectedDate provided, setting loading to false`);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Fetch the data directly without auto-fetching
      console.log(`[TwitterFeed] Calling fetchTwitterDataItems for date: ${selectedDate}`);
      console.log(`[TwitterFeed] API URL will be: /calendar/data_items/${selectedDate}?namespaces=twitter`);
      
      const dataItems = await fetchTwitterDataItems(selectedDate);
      
      console.log(`[TwitterFeed DEBUG] === API RESPONSE ANALYSIS ===`);
      console.log(`[TwitterFeed DEBUG] Raw API response:`, dataItems);
      console.log(`[TwitterFeed DEBUG] Response type:`, typeof dataItems);
      console.log(`[TwitterFeed DEBUG] Is array:`, Array.isArray(dataItems));
      console.log(`[TwitterFeed DEBUG] Length:`, dataItems?.length || 0);
      
      if (!dataItems) {
        console.error(`[TwitterFeed DEBUG] API returned null/undefined`);
        setTwitterData([]);
        return;
      }

      if (!Array.isArray(dataItems)) {
        console.error(`[TwitterFeed DEBUG] API returned non-array:`, dataItems);
        setTwitterData([]);
        return;
      }
      
      console.log(`[TwitterFeed DEBUG] Successfully fetched ${dataItems.length} Twitter data items for ${selectedDate}`);
      
      // Analyze each raw data item
      if (dataItems.length > 0) {
        console.log(`[TwitterFeed DEBUG] === RAW DATA ANALYSIS ===`);
        dataItems.slice(0, 3).forEach((item, index) => {
          console.log(`[TwitterFeed DEBUG] Raw Item ${index + 1}:`, {
            id: item.id,
            namespace: item.namespace,
            source_id: item.source_id,
            content: item.content?.substring(0, 50) + (item.content?.length > 50 ? '...' : ''),
            contentLength: item.content?.length || 0,
            days_date: item.days_date,
            metadataType: typeof item.metadata,
            metadataKeys: typeof item.metadata === 'object' && item.metadata ? Object.keys(item.metadata) : 'n/a'
          });
        });
      }
      
      // Check if we're looking at the right date with media
      console.log(`[TwitterFeed DEBUG] === MEDIA ANALYSIS ===`);
      const mediaCount = dataItems.filter(item => {
        try {
          let meta = item.metadata;
          if (typeof meta === 'string') {
            meta = JSON.parse(meta);
          }
          const hasMedia = meta.media?.has_media === true;
          console.log(`[TwitterFeed DEBUG] Item ${item.id} has media:`, hasMedia, 'media obj:', meta.media);
          return hasMedia;
        } catch (e) {
          console.warn(`[TwitterFeed DEBUG] Error parsing metadata for ${item.id}:`, e);
          return false;
        }
      }).length;
      console.log(`[TwitterFeed DEBUG] Items with media on ${selectedDate}: ${mediaCount}/${dataItems.length}`);
      
      // Convert database items to ContentItemData format
      console.log(`[TwitterFeed DEBUG] === CONVERSION PROCESS ===`);
      console.log(`[TwitterFeed DEBUG] Starting conversion of ${dataItems.length} items...`);
      
      const contentItems = dataItems.map((item, index) => {
        console.log(`[TwitterFeed DEBUG] Converting item ${index + 1}/${dataItems.length}: ${item.id}`);
        const converted = convertDataItemToContentItem(item);
        console.log(`[TwitterFeed DEBUG] Converted result:`, {
          id: converted.id,
          username: converted.username,
          content: converted.content?.substring(0, 50) + (converted.content?.length > 50 ? '...' : ''),
          hasMedia: converted.hasMedia,
          mediaUrl: converted.mediaUrl,
          timestamp: converted.timestamp
        });
        return converted;
      });
      
      console.log(`[TwitterFeed DEBUG] === CONVERSION RESULTS ===`);
      console.log(`[TwitterFeed DEBUG] Converted to ${contentItems.length} content items`);
      
      // Log media information for debugging
      const mediaItems = contentItems.filter(item => item.hasMedia);
      console.log(`[TwitterFeed DEBUG] Final items with media: ${mediaItems.length}/${contentItems.length}`);
      mediaItems.forEach(item => {
        console.log(`[TwitterFeed DEBUG] Media item:`, {
          id: item.id,
          username: item.username,
          mediaUrl: item.mediaUrl,
          hasMedia: item.hasMedia
        });
      });
      
      console.log(`[TwitterFeed DEBUG] === SETTING STATE ===`);
      console.log(`[TwitterFeed DEBUG] About to set twitterData with ${contentItems.length} items`);
      setTwitterData(contentItems);
      console.log(`[TwitterFeed DEBUG] State set successfully`);
      
    } catch (err) {
      console.error('[TwitterFeed DEBUG] === ERROR IN FETCH ===');
      console.error('[TwitterFeed DEBUG] Error fetching Twitter data items:', err);
      console.error('[TwitterFeed DEBUG] Error details:', {
        name: err?.name,
        message: err?.message,
        stack: err?.stack?.split('\n').slice(0, 5)
      });
      setError('Failed to load tweets');
      setTwitterData([]);
    } finally {
      console.log(`[TwitterFeed DEBUG] === FETCH COMPLETE ===`);
      console.log(`[TwitterFeed DEBUG] Setting loading to false`);
      setLoading(false);
    }
  }, [selectedDate]);

  // Callback for handling fetch completion
  const handleFetchComplete = () => {
    // Refresh data after successful fetch
    fetchTweets();
  };
  
  // Local loading state for data fetching
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Auto-advance state
  const [isAutoAdvanceEnabled, setIsAutoAdvanceEnabled] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(5000);
  const currentIndexRef = useRef(0);
  const isAutoAdvancingRef = useRef(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const timeRemainingRef = useRef(5000);

  // Only log when selectedDate actually changes
  const prevSelectedDateRef = useRef<string>();
  if (prevSelectedDateRef.current !== selectedDate) {
    console.log(`[TwitterFeed] Selected date changed: ${prevSelectedDateRef.current} → ${selectedDate}`);
    prevSelectedDateRef.current = selectedDate;
  }

  // Stable timer functions
  const startAutoAdvance = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    
    if (!api || !isAutoAdvanceEnabled || isPaused || twitterData.length <= 1) {
      return;
    }

    const intervalId = Date.now();
    console.log(`[TwitterFeed] Starting stable auto-advance timer ${intervalId}`);
    
    timerRef.current = setInterval(() => {
      timeRemainingRef.current -= 100;
      setTimeRemaining(timeRemainingRef.current);
      
      // Only log every second to reduce console noise
      if (timeRemainingRef.current % 1000 === 0) {
        console.log(`[TwitterFeed] Stable timer: ${timeRemainingRef.current}ms remaining`);
      }
      
      if (timeRemainingRef.current <= 0) {
        // Time to advance
        const currentIndex = currentIndexRef.current;
        const nextIndex = (currentIndex + 1) % twitterData.length;
        console.log(`[TwitterFeed] Stable timer: Auto-advancing from ${currentIndex} to ${nextIndex}`);
        
        isAutoAdvancingRef.current = true;
        currentIndexRef.current = nextIndex;
        api.scrollTo(nextIndex);
        
        // Reset timer
        timeRemainingRef.current = 5000;
        setTimeRemaining(5000);
      }
    }, 100);
  };

  const stopAutoAdvance = () => {
    if (timerRef.current) {
      console.log(`[TwitterFeed] Stopping stable auto-advance timer`);
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    fetchTweets();
  }, [fetchTweets]);

  useEffect(() => {
    if (!api) {
      return;
    }

    const updateCurrent = () => {
      const newCurrent = api.selectedScrollSnap();
      setCurrent(newCurrent);
      
      // Only update ref and reset timer if this isn't from auto-advance
      if (!isAutoAdvancingRef.current) {
        currentIndexRef.current = newCurrent;
        // Reset timer when user manually navigates
        timeRemainingRef.current = 5000;
        setTimeRemaining(5000);
        console.log(`[TwitterFeed] Manual navigation to ${newCurrent}, timer reset`);
      } else {
        // Auto-advance just completed, clear the flag
        isAutoAdvancingRef.current = false;
        console.log(`[TwitterFeed] Auto-advance to ${newCurrent} completed`);
      }
    };

    updateCurrent(); // Set initial value
    api.on("select", updateCurrent);

    return () => {
      api.off("select", updateCurrent);
    };
  }, [api]);

  // Auto-advance state management
  useEffect(() => {
    if (isAutoAdvanceEnabled && !isPaused && api && twitterData.length > 1) {
      startAutoAdvance();
    } else {
      stopAutoAdvance();
    }
    
    return stopAutoAdvance;
  }, [api, isAutoAdvanceEnabled, isPaused, twitterData.length]);

  // Debug logging for render state
  console.log(`[TwitterFeed] Render: date=${selectedDate}, loading=${loading}, error=${error}, items=${twitterData.length}`);

  // Loading state
  if (loading) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
          <TwitterFetchButton selectedDate={selectedDate || ''} onFetchComplete={handleFetchComplete} />
        </div>
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
        <div>
          <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
          <TwitterFetchButton selectedDate={selectedDate || ''} onFetchComplete={handleFetchComplete} />
        </div>
        <div className="flex items-center justify-center p-8 min-h-[200px] border border-newspaper-divider rounded-lg">
          <div className="text-red-600">Error: {error}</div>
        </div>
      </div>
    );
  }

  // No data state
  if (twitterData.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
          <TwitterFetchButton selectedDate={selectedDate || ''} onFetchComplete={handleFetchComplete} />
        </div>
      </div>
    );
  }

  console.log(`[TwitterFeed] Rendering carousel with ${twitterData.length} tweets`);

  // Render carousel with Twitter data from database
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-newspaper-headline">Twitter</h3>
        <TwitterFetchButton selectedDate={selectedDate || ''} onFetchComplete={handleFetchComplete} />
      </div>
      
      {twitterData.length === 1 ? (
        // Single tweet - use same fixed size
        <div className="w-full h-[450px] border border-gray-200 rounded-lg overflow-hidden">
          <div className="h-full overflow-y-auto">
            <ContentCard data={twitterData[0]} />
          </div>
        </div>
      ) : (
        // Multiple tweets - use carousel with fixed size (3x larger)
        <div 
          className="w-full h-[450px] border border-gray-200 rounded-lg overflow-hidden relative"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
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
          
          {/* Auto-advance controls at bottom - replaces dots */}
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex items-center space-x-3">
            <button
              onClick={() => setIsAutoAdvanceEnabled(!isAutoAdvanceEnabled)}
              className={`px-3 py-2 text-sm rounded-lg transition-colors flex items-center space-x-2 ${
                isAutoAdvanceEnabled 
                  ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              aria-label={isAutoAdvanceEnabled ? 'Disable auto-advance' : 'Enable auto-advance'}
            >
              <span>{isAutoAdvanceEnabled ? '⏸️' : '▶️'}</span>
              <span>Auto</span>
            </button>
            
            {isAutoAdvanceEnabled && !isPaused && twitterData.length > 1 && (
              <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-100 ease-linear rounded-full"
                  style={{ width: `${((5000 - timeRemaining) / 5000) * 100}%` }}
                />
              </div>
            )}
            
            {/* Current slide indicator */}
            <div className="text-xs text-gray-500 bg-white px-3 py-1 rounded whitespace-nowrap">
              {current + 1} of {twitterData.length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Memoized export to prevent unnecessary re-renders
export const TwitterFeed = memo(TwitterFeedComponent);