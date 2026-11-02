import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { AccessibilityProvider } from './a11y/AccessibilityProvider';
import { router } from './router';

// Initialize React Query Client with safe defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      retry: (failureCount, error: any) => {
        // Do not retry 401 or 403 authorization failures
        if (error?.status === 401 || error?.status === 403) {
          return false;
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AccessibilityProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </AccessibilityProvider>
    </QueryClientProvider>
  );
};

export default App;
