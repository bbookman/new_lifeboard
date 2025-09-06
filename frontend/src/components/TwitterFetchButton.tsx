import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { useTwitterStatus } from '@/hooks/useTwitterStatus';

interface TwitterFetchButtonProps {
  selectedDate: string;
  onFetchComplete?: () => void;
}


/**
 * TwitterFetchButton component provides manual Twitter data fetching functionality
 * with configurable rate limiting support. Works with any rate limiting interval
 * configured by the user via TWITTER_RATE_LIMIT_IN_MINUTES environment variable.
 */
const TwitterFetchButton: React.FC<TwitterFetchButtonProps> = ({
  selectedDate,
  onFetchComplete
}) => {
  const [fetchLoading, setFetchLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { canFetch, minutesUntil, loading: statusLoading, error: statusError, checkStatus } = useTwitterStatus(selectedDate);


  /**
   * Handle fetch button click
   */
  const handleFetch = async () => {
    if (!canFetch || fetchLoading) {
      return;
    }

    try {
      setFetchLoading(true);
      setError(null);

      console.log(`[TwitterFetchButton] Starting manual fetch for date: ${selectedDate}`);

      // Call the existing Twitter fetch API endpoint
      const response = await fetch(`/api/calendar/twitter/fetch/${selectedDate}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json();
        console.log(`[TwitterFetchButton] Fetch result:`, result);
        
        if (result.success) {
          console.log(`[TwitterFetchButton] Fetch successful: ${result.message}`);
          
          // Refresh rate limit status after successful fetch
          await checkStatus();
          
          // Notify parent component if callback provided
          if (onFetchComplete) {
            onFetchComplete();
          }
        } else {
          console.error(`[TwitterFetchButton] Fetch failed:`, result.message);
          setError(result.message || 'Failed to fetch Twitter data');
        }
      } else {
        const errorText = await response.text();
        console.error(`[TwitterFetchButton] Fetch API error:`, response.status, errorText);
        
        // Handle specific error cases
        if (response.status === 503) {
          setError('Twitter API not configured');
        } else if (response.status === 404) {
          setError('Twitter source not available');
        } else if (response.status === 429) {
          setError('Rate limited - please wait before trying again');
          await checkStatus(); // Refresh rate limit status on 429 error
        } else {
          setError(`Failed to fetch: ${response.status} ${response.statusText}`);
        }
      }
    } catch (error) {
      console.error(`[TwitterFetchButton] Network error:`, error);
      setError(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setFetchLoading(false);
    }
  };


  // Determine button state and content
  const getButtonContent = () => {
    if (fetchLoading) {
      return (
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
          <span>Fetching...</span>
        </div>
      );
    }
    
    if (!canFetch && minutesUntil > 0) {
      // Adapt display for different time intervals
      if (minutesUntil >= 60) {
        const hours = Math.floor(minutesUntil / 60);
        const remainingMinutes = minutesUntil % 60;
        if (remainingMinutes > 0) {
          return `Next fetch available in ${hours}h ${remainingMinutes}m`;
        } else {
          return `Next fetch available in ${hours} hour${hours > 1 ? 's' : ''}`;
        }
      } else {
        return `Next fetch available in ${minutesUntil} minute${minutesUntil !== 1 ? 's' : ''}`;
      }
    }
    
    return 'Fetch now';
  };

  const getButtonVariant = () => {
    if (fetchLoading || (!canFetch && minutesUntil > 0)) {
      return 'secondary';
    }
    return 'default';
  };

  const isButtonDisabled = () => {
    return fetchLoading || statusLoading || (!canFetch && minutesUntil > 0);
  };

  return (
    <div className="space-y-2">
      <Button
        onClick={handleFetch}
        disabled={isButtonDisabled()}
        variant={getButtonVariant()}
        size="sm"
        className="w-full"
      >
        {statusLoading ? 'Checking status...' : getButtonContent()}
      </Button>
      
      {(error || statusError) && (
        <div className="text-red-600 text-sm">
          {error || statusError}
        </div>
      )}
    </div>
  );
};

export { TwitterFetchButton };