import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from '../../auth/AuthProvider';
import { RequireRole } from '../../auth/RequireRole';
import { setAccessToken, getAccessToken } from '../../api/client';
import axios from 'axios';
import { apiClient } from '../../api/client';

// Mock axios and apiClient
vi.mock('axios', async () => {
  const actual = await vi.importActual<any>('axios');
  return {
    ...actual,
    default: {
      ...actual.default,
      post: vi.fn(),
      get: vi.fn(),
      create: vi.fn(() => ({
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
        get: vi.fn(),
        post: vi.fn(),
      })),
    },
  };
});

describe('Phase F2: Authentication & Role Guards (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setAccessToken(null);
  });

  const DummyConsumer = () => {
    const { user, isAuthenticated, isLoading, login, logout } = useAuth();
    if (isLoading) return <div>Loading Auth...</div>;
    return (
      <div>
        <div data-testid="auth-status">{isAuthenticated ? 'LOGGED_IN' : 'LOGGED_OUT'}</div>
        <div data-testid="user-role">{user?.role || 'NONE'}</div>
        <div data-testid="user-name">{user?.full_name || 'ANONYMOUS'}</div>
        <button
          onClick={() =>
            login('citizen@test.com', 'password123').catch(() => {})
          }
        >
          Do Login
        </button>
        <button onClick={() => logout()}>Do Logout</button>
      </div>
    );
  };

  it('boots up with silent refresh check on mount', async () => {
    // Mock silent refresh returning success
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: {
        access: 'mock-jwt-token-123',
        user: {
          id: 'u-1',
          email: 'citizen@test.com',
          full_name: 'Test Citizen',
          role: 'CITIZEN',
          approval_status: 'APPROVED',
          created_at: '2026-01-01',
        },
      },
    });

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        id: 'u-1',
        email: 'citizen@test.com',
        full_name: 'Test Citizen',
        role: 'CITIZEN',
        approval_status: 'APPROVED',
        created_at: '2026-01-01',
      },
    });

    render(
      <AuthProvider>
        <DummyConsumer />
      </AuthProvider>
    );

    expect(screen.getByText('Loading Auth...')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_IN');
      expect(screen.getByTestId('user-role').textContent).toBe('CITIZEN');
      expect(getAccessToken()).toBe('mock-jwt-token-123');
    });
  });

  it('gracefully degrades to anonymous when refresh token cookie is missing', async () => {
    // Mock 401 refresh failure
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 401, data: { detail: 'No token' } },
    });

    render(
      <AuthProvider>
        <DummyConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_OUT');
      expect(getAccessToken()).toBeNull();
    });
  });

  it('enforces RequireRole by redirecting unauthorized roles to /unauthorized', async () => {
    // Setup state where user is CITIZEN
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: {
        access: 'jwt-citizen',
        user: { id: 'u-c', role: 'CITIZEN', approval_status: 'APPROVED', full_name: 'Citizen' },
      },
    });
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: { id: 'u-c', role: 'CITIZEN', approval_status: 'APPROVED', full_name: 'Citizen' },
    });

    render(
      <MemoryRouter initialEntries={['/triage']}>
        <AuthProvider>
          <Routes>
            <Route path="/unauthorized" element={<div>Unauthorized Page Access</div>} />
            <Route
              path="/triage"
              element={
                <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
                  <div>Triage Protected Content</div>
                </RequireRole>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Unauthorized Page Access')).toBeDefined();
      expect(screen.queryByText('Triage Protected Content')).toBeNull();
    });
  });

  it('permits authorized roles through RequireRole', async () => {
    // Setup state where user is ANALYST
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: {
        access: 'jwt-analyst',
        user: { id: 'u-a', role: 'ANALYST', approval_status: 'APPROVED', full_name: 'Analyst S2' },
      },
    });
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: { id: 'u-a', role: 'ANALYST', approval_status: 'APPROVED', full_name: 'Analyst S2' },
    });

    render(
      <MemoryRouter initialEntries={['/triage']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/triage"
              element={
                <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
                  <div>Triage Protected Content</div>
                </RequireRole>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Triage Protected Content')).toBeDefined();
    });
  });

  it('redirects pending staff to /pending-approval', async () => {
    // Setup state where staff user is PENDING
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: {
        access: 'jwt-staff-pending',
        user: { id: 'u-p', role: 'ANALYST', approval_status: 'PENDING', full_name: 'Pending Analyst' },
      },
    });
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: { id: 'u-p', role: 'ANALYST', approval_status: 'PENDING', full_name: 'Pending Analyst' },
    });

    render(
      <MemoryRouter initialEntries={['/triage']}>
        <AuthProvider>
          <Routes>
            <Route path="/pending-approval" element={<div>Staff Application Pending</div>} />
            <Route
              path="/triage"
              element={
                <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
                  <div>Triage Protected Content</div>
                </RequireRole>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Staff Application Pending')).toBeDefined();
    });
  });
});
