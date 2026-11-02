import { describe, it, expect } from 'vitest';
import { parseApiError, formatFieldErrors, AppApiError } from './errors';
import axios from 'axios';

describe('API Errors Parser', () => {
  it('parses standard backend error envelope correctly', () => {
    const rawError = {
      isAxiosError: true,
      response: {
        status: 400,
        headers: { 'x-request-id': 'req-abc-123' },
        data: {
          error: {
            code: 'validation_error',
            message: 'Invalid submission data.',
            details: {
              email: ['Enter a valid email address.'],
            },
            request_id: 'req-abc-123',
          },
        },
      },
    };

    // Mock axios.isAxiosError with a valid type predicate
    const originalIsAxiosError = axios.isAxiosError;
    axios.isAxiosError = ((_payload: unknown): _payload is any => true) as any;

    const parsed = parseApiError(rawError);

    expect(parsed.code).toBe('validation_error');
    expect(parsed.message).toBe('Invalid submission data.');
    expect(parsed.requestId).toBe('req-abc-123');
    expect(parsed.status).toBe(400);
    expect(parsed.details).toEqual({
      email: ['Enter a valid email address.'],
    });

    const formatted = formatFieldErrors(parsed.details);
    expect(formatted).toEqual(['email: Enter a valid email address.']);

    axios.isAxiosError = originalIsAxiosError;
  });

  it('handles standard Javascript Error instance', () => {
    const err = new Error('Network timeout');
    const parsed = parseApiError(err);

    expect(parsed.code).toBe('client_runtime_error');
    expect(parsed.message).toBe('Network timeout');
    expect(parsed.status).toBe(0);
  });

  it('handles unknown error types safely', () => {
    const parsed = parseApiError('something random broke');

    expect(parsed.code).toBe('unknown_error');
    expect(parsed.message).toBe('An unknown error occurred.');
    expect(parsed.status).toBe(0);
  });

  it('constructs AppApiError properly', () => {
    const appError = new AppApiError({
      code: 'unauthorized',
      message: 'Token expired',
      details: {},
      requestId: 'req-xyz',
      status: 401,
    });

    expect(appError.name).toBe('AppApiError');
    expect(appError.code).toBe('unauthorized');
    expect(appError.message).toBe('Token expired');
    expect(appError.status).toBe(401);
  });
});
