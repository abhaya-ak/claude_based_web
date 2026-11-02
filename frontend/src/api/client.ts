import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { parseApiError, AppApiError } from './errors';
import type { RefreshResponse } from './schema';

// In-memory token storage (NEVER in localStorage per security rule 30)
let memoryAccessToken: string | null = null;
let onAuthFailureCallback: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  memoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return memoryAccessToken;
}

export function setOnAuthFailure(callback: () => void): void {
  onAuthFailureCallback = callback;
}

// Compute API base URL with /v1 namespace
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api';
export const API_BASE_URL = rawBaseUrl.endsWith('/v1') ? rawBaseUrl : `${rawBaseUrl.replace(/\/+$/, '')}/v1`;

// Create core Axios instance
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Single-flight refresh state
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else if (token) {
      promise.resolve(token);
    }
  });
  failedQueue = [];
}

// Request Interceptor: Attach Authorization Bearer token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (memoryAccessToken && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${memoryAccessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Catch 401s and execute single-flight silent refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Pass through if not a 401 or request has already been retried
    if (!error.response || error.response.status !== 401 || !originalRequest) {
      return Promise.reject(new AppApiError(parseApiError(error)));
    }

    // Do not attempt refresh on auth endpoints (login, refresh, logout, register)
    const requestUrl = originalRequest.url || '';
    if (
      requestUrl.includes('/auth/login/') ||
      requestUrl.includes('/auth/refresh/') ||
      requestUrl.includes('/auth/logout/') ||
      requestUrl.includes('/auth/register/')
    ) {
      return Promise.reject(new AppApiError(parseApiError(error)));
    }

    if (originalRequest._retry) {
      return Promise.reject(new AppApiError(parseApiError(error)));
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        })
        .catch((err) => Promise.reject(err));
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      // Call silent refresh endpoint with mandatory CSRF mitigation header
      const refreshResponse = await axios.post<RefreshResponse>(
        `${API_BASE_URL}/auth/refresh/`,
        {},
        {
          withCredentials: true,
          headers: {
            'X-Requested-With': 'scamshield-web',
          },
        }
      );

      const newAccessToken = refreshResponse.data.access;
      setAccessToken(newAccessToken);
      processQueue(null, newAccessToken);

      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return apiClient(originalRequest);
    } catch (refreshErr) {
      processQueue(refreshErr, null);
      setAccessToken(null);
      if (onAuthFailureCallback) {
        onAuthFailureCallback();
      }
      return Promise.reject(new AppApiError(parseApiError(refreshErr)));
    } finally {
      isRefreshing = false;
    }
  }
);
