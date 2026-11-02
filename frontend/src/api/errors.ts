import axios, { AxiosError } from 'axios';
import type { ApiErrorEnvelope, ApiErrorDetail } from './schema';

export interface ParsedApiError {
  code: string;
  message: string;
  details: ApiErrorDetail;
  requestId: string | null;
  status: number;
}

/**
 * Standard Application API Error Class
 */
export class AppApiError extends Error {
  public readonly code: string;
  public readonly details: ApiErrorDetail;
  public readonly requestId: string | null;
  public readonly status: number;

  constructor(parsed: ParsedApiError) {
    super(parsed.message);
    this.name = 'AppApiError';
    this.code = parsed.code;
    this.details = parsed.details;
    this.requestId = parsed.requestId;
    this.status = parsed.status;
  }
}

/**
 * Parses any raw unknown error into our standard error envelope format
 */
export function parseApiError(error: unknown): ParsedApiError {
  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<ApiErrorEnvelope>;
    const status = axiosErr.response?.status ?? 0;
    const data = axiosErr.response?.data;

    // Standard DRF Custom Error Envelope
    if (data && typeof data === 'object' && 'error' in data) {
      const envelope = data.error;
      return {
        code: envelope.code || 'unknown_error',
        message: envelope.message || axiosErr.message || 'An unexpected error occurred.',
        details: envelope.details || {},
        requestId: envelope.request_id || (axiosErr.response?.headers['x-request-id'] as string) || null,
        status,
      };
    }

    // Network / Gateway fallback
    if (!axiosErr.response) {
      return {
        code: 'network_unavailable',
        message: 'Unable to reach the server. Please check your network connection.',
        details: {},
        requestId: null,
        status: 0,
      };
    }

    return {
      code: `http_${status}`,
      message: axiosErr.message || 'Server returned an error response.',
      details: {},
      requestId: (axiosErr.response?.headers['x-request-id'] as string) || null,
      status,
    };
  }

  if (error instanceof Error) {
    return {
      code: 'client_runtime_error',
      message: error.message,
      details: {},
      requestId: null,
      status: 0,
    };
  }

  return {
    code: 'unknown_error',
    message: 'An unknown error occurred.',
    details: {},
    requestId: null,
    status: 0,
  };
}

/**
 * Formats details dictionary into single readable string
 */
export function formatFieldErrors(details: ApiErrorDetail): string[] {
  const messages: string[] = [];
  for (const [field, error] of Object.entries(details)) {
    if (Array.isArray(error)) {
      messages.push(`${field}: ${error.join(', ')}`);
    } else if (typeof error === 'string') {
      messages.push(`${field}: ${error}`);
    } else if (typeof error === 'object' && error !== null) {
      messages.push(`${field}: ${JSON.stringify(error)}`);
    }
  }
  return messages;
}
