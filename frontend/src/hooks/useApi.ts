// Custom hooks for API operations using React Query
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, queryKeys, ChatMessage, HealthCheck, CalendarData } from '../lib/api';

// Health check hook
export const useHealth = () => {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: async () => {
      const response = await apiClient.getHealth();
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch health status');
      }
      return response.data!;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });
};

// Chat hooks
export const useChatHistory = () => {
  return useQuery({
    queryKey: queryKeys.chat.history,
    queryFn: async () => {
      const response = await apiClient.getChatHistory();
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch chat history');
      }
      return response.data || [];
    },
  });
};

export const useSendMessage = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (message: string) => {
      const response = await apiClient.sendChatMessage(message);
      if (!response.success) {
        throw new Error(response.error || 'Failed to send message');
      }
      return response.data!;
    },
    onSuccess: () => {
      // Invalidate chat history to refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.chat.history });
    },
  });
};

// Calendar hooks
export const useCalendarData = (date?: string) => {
  return useQuery({
    queryKey: date ? queryKeys.calendar.byDate(date) : queryKeys.calendar.all,
    queryFn: async () => {
      const response = await apiClient.getCalendarData(date);
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch calendar data');
      }
      return response.data || [];
    },
  });
};

// Search hook
export const useSearch = (query: string, enabled = true) => {
  return useQuery({
    queryKey: queryKeys.search(query),
    queryFn: async () => {
      if (!query.trim()) return [];
      
      const response = await apiClient.searchData(query);
      if (!response.success) {
        throw new Error(response.error || 'Failed to search data');
      }
      return response.data || [];
    },
    enabled: enabled && query.trim().length > 0,
  });
};

// Sync hooks
export const useSyncStatus = () => {
  return useQuery({
    queryKey: queryKeys.sync.status,
    queryFn: async () => {
      const response = await apiClient.getSyncStatus();
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch sync status');
      }
      return response.data!;
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  });
};

export const useTriggerSync = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (source?: string) => {
      const response = await apiClient.triggerSync(source);
      if (!response.success) {
        throw new Error(response.error || 'Failed to trigger sync');
      }
      return response.data!;
    },
    onSuccess: () => {
      // Invalidate sync status to refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.sync.status });
    },
  });
};

// Settings hooks
export const useSettings = () => {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: async () => {
      const response = await apiClient.getSettings();
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch settings');
      }
      return response.data || {};
    },
  });
};

export const useUpdateSettings = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (settings: Record<string, any>) => {
      const response = await apiClient.updateSettings(settings);
      if (!response.success) {
        throw new Error(response.error || 'Failed to update settings');
      }
      return response.data!;
    },
    onSuccess: () => {
      // Invalidate settings to refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.settings });
    },
  });
};