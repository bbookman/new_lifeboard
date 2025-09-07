import { useQuery } from '@tanstack/react-query';
import type { QueryObserverResult } from '@tanstack/react-query';
import { getProcessingQueue, queryKeys, ProcessingStats } from '../lib/api';

export interface UseProcessingStatusResult {
  data: ProcessingStats | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<QueryObserverResult<ProcessingStats, Error>>;
  lastSuccessfulPoll: number | undefined;
}

export function useProcessingStatus(): UseProcessingStatusResult {
  const {
    data,
    isLoading,
    error,
    refetch,
    dataUpdatedAt
  } = useQuery({
    queryKey: queryKeys.processing.queue,
    queryFn: getProcessingQueue,
    refetchInterval: 5000, // Poll every 5 seconds
    refetchIntervalInBackground: true,
    staleTime: 0, // Always consider data stale to ensure fresh polling
    retry: (failureCount, error) => {
      // Retry up to 3 times, then keep polling but don't retry immediately
      return failureCount < 3;
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000), // Exponential backoff up to 10s
  });

  return {
    data,
    isLoading,
    error: error as Error | null,
    refetch,
    lastSuccessfulPoll: data ? dataUpdatedAt : undefined,
  };
}