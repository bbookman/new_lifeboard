// React Query provider setup
import { ReactNode, useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '../lib/queryClient';

interface QueryProviderProps {
  children: ReactNode;
}

export const QueryProvider = ({ children }: QueryProviderProps) => {
  useEffect(() => {
    console.log('[QueryProvider] QueryClient initialized:', !!queryClient);
    console.log('[QueryProvider] QueryClient instance:', queryClient);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Uncomment below to add React Query DevTools in development */}
      {/* {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />} */}
    </QueryClientProvider>
  );
};