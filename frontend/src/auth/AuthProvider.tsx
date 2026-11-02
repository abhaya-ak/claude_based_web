import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient, setAccessToken, setOnAuthFailure, API_BASE_URL } from '../api/client';
import type { User, UserRole, LoginResponse, RefreshResponse } from '../api/schema';
import axios from 'axios';

interface AuthContextValue {
  user: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const clearAuth = useCallback(() => {
    setUser(null);
    setAccessToken(null);
  }, []);

  // Silent session bootstrap on app mount
  const refreshSession = useCallback(async () => {
    try {
      const response = await axios.post<RefreshResponse>(
        `${API_BASE_URL}/auth/refresh/`,
        {},
        {
          withCredentials: true,
          headers: {
            'X-Requested-With': 'scamshield-web',
          },
        }
      );

      const token = response.data.access;
      setAccessToken(token);

      // Verify and load current profile
      const meResponse = await apiClient.get<User>('/auth/me/');
      setUser(meResponse.data);
    } catch {
      clearAuth();
    } finally {
      setIsLoading(false);
    }
  }, [clearAuth]);

  useEffect(() => {
    setOnAuthFailure(clearAuth);
    refreshSession();
  }, [refreshSession, clearAuth]);

  const login = async (email: string, password: string): Promise<User> => {
    setIsLoading(true);
    try {
      const response = await apiClient.post<LoginResponse>('/auth/login/', {
        email,
        password,
      });

      const token = response.data.access;
      const loggedInUser = response.data.user;

      setAccessToken(token);
      setUser(loggedInUser);
      return loggedInUser;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async (): Promise<void> => {
    setIsLoading(true);
    try {
      await apiClient.post(
        '/auth/logout/',
        {},
        {
          headers: {
            'X-Requested-With': 'scamshield-web',
          },
        }
      );
    } catch {
      // Best-effort logout: ignore network failures and proceed with local cleanup
    } finally {
      clearAuth();
      setIsLoading(false);
    }
  };

  const role = user?.role ?? null;
  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        isLoading,
        login,
        logout,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
