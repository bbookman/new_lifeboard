import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

export interface AppConfig {
  news: {
    enabled: boolean;
    language: string;
    country: string;
    unique_items_per_day: number;
  };
  weather: {
    enabled: boolean;
    units: string;
  };
  twitter: {
    enabled: boolean;
  };
  spotify: {
    enabled: boolean;
  };
  limitless: {
    timezone: string;
  };
}

export const useConfig = () => {
  return useQuery({
    queryKey: ['config'],
    queryFn: async (): Promise<AppConfig> => {
      const response = await apiClient.getConfig();
      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch configuration');
      }
      return response.data as AppConfig;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
  });
};