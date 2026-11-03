import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AdminDashboardPage } from './AdminDashboardPage';
import { adminApi, type HeuristicRule, type ScannerConfig } from '../../api/admin';
import type { User, AuditLogItem, PaginatedResponse } from '../../api/schema';

// Mock adminApi
vi.mock('../../api/admin', () => ({
  adminApi: {
    getUsers: vi.fn(),
    approveUser: vi.fn(),
    rejectUser: vi.fn(),
    changeRole: vi.fn(),
    getAuditLogs: vi.fn(),
    getTelemetryMetrics: vi.fn(),
    getRules: vi.fn(),
    getScannerConfig: vi.fn(),
    updateScannerConfig: vi.fn(),
  },
}));

describe('Phase F7: Admin Portal, Telemetry & Audit Log Viewer (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockUsers: PaginatedResponse<User> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'usr-uuid-1',
        email: 'analyst.jane@police.gov.my',
        full_name: 'Inspector Jane Doe',
        role: 'ANALYST',
        approval_status: 'PENDING',
        organization: 'Royal Malaysia Police (PDRM)',
        created_at: '2026-02-01T08:00:00Z',
      },
    ],
  };

  const mockAuditLogs: PaginatedResponse<AuditLogItem> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'aud-uuid-1',
        event_type: 'INDICATOR_VERIFIED',
        severity: 'INFO',
        actor_id: 'usr-uuid-admin',
        actor_email: 'admin@scamshield.gov.my',
        target_type: 'INDICATOR',
        target_id: 'ind-uuid-99',
        metadata: { threat_level: 'HIGH' },
        created_at: '2026-02-01T12:00:00Z',
      },
    ],
  };

  const mockTelemetry = {
    timestamp: '2026-02-01T12:00:00Z',
    metrics: {
      http_requests_total: 12450,
      http_5xx_errors: 0,
      db_latency_ms: 4.2,
      scans_dispatched: 320,
    },
  };

  const mockRules: PaginatedResponse<HeuristicRule> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'rule-uuid-1',
        rule_type: 'KEYWORD',
        pattern: 'account suspended',
        weight: 35,
        is_active: true,
        created_at: '2026-02-01T08:00:00Z',
      },
    ],
  };

  const mockConfig: ScannerConfig = {
    id: 1,
    ruleset_version: 4,
    keyword_cap_points: 60,
    ip_url_points: 40,
    prior_pending_points: 15,
    high_priority_threshold: 65,
    updated_at: '2026-02-01T08:00:00Z',
  };

  it('renders staff approval requests and allows one-click approval', async () => {
    vi.mocked(adminApi.getUsers).mockResolvedValue(mockUsers);
    vi.mocked(adminApi.approveUser).mockResolvedValueOnce({
      ...mockUsers.results[0],
      approval_status: 'APPROVED',
    });

    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Inspector Jane Doe')).toBeDefined();
      expect(screen.getByText('analyst.jane@police.gov.my')).toBeDefined();
      expect(screen.getAllByText('PENDING').length).toBeGreaterThanOrEqual(1);
    });

    const approveBtn = screen.getByRole('button', { name: /^approve$/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(adminApi.approveUser).toHaveBeenCalledWith('usr-uuid-1');
      expect(screen.getByText(/staff account approved/i)).toBeDefined();
    });
  });

  it('switches to audit logs tab and displays tamper-evident events', async () => {
    vi.mocked(adminApi.getUsers).mockResolvedValue(mockUsers);
    vi.mocked(adminApi.getAuditLogs).mockResolvedValue(mockAuditLogs);

    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>
    );

    // Switch to Audit tab
    const auditTabBtn = await screen.findByRole('button', { name: /audit logs/i });
    fireEvent.click(auditTabBtn);

    await waitFor(() => {
      expect(screen.getByText('INDICATOR_VERIFIED')).toBeDefined();
      expect(screen.getByText('admin@scamshield.gov.my')).toBeDefined();
    });
  });

  it('switches to telemetry tab and displays operational metrics', async () => {
    vi.mocked(adminApi.getUsers).mockResolvedValue(mockUsers);
    vi.mocked(adminApi.getTelemetryMetrics).mockResolvedValue(mockTelemetry);

    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>
    );

    // Switch to Telemetry tab
    const telemetryTabBtn = await screen.findByRole('button', { name: /telemetry|metrics/i });
    fireEvent.click(telemetryTabBtn);

    await waitFor(() => {
      expect(screen.getByText('12,450')).toBeDefined();
      expect(screen.getByText('4.2 ms')).toBeDefined();
    });
  });

  it('switches to scanner rules tab and displays heuristic rules', async () => {
    vi.mocked(adminApi.getUsers).mockResolvedValue(mockUsers);
    vi.mocked(adminApi.getRules).mockResolvedValue(mockRules);
    vi.mocked(adminApi.getScannerConfig).mockResolvedValue(mockConfig);

    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>
    );

    // Switch to Rules tab
    const rulesTabBtn = await screen.findByRole('button', { name: /scanner rules|heuristics/i });
    fireEvent.click(rulesTabBtn);

    await waitFor(() => {
      expect(screen.getByText('account suspended')).toBeDefined();
      expect(screen.getByText('Version 4')).toBeDefined();
    });
  });
});
