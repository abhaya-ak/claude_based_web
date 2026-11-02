import { apiClient } from './client';
import type { User, PaginatedResponse, AuditLogItem } from './schema';

export interface AdminUserFilters {
  status?: string;
  role?: string;
  offset?: number;
  limit?: number;
}

export interface HeuristicRule {
  id: string;
  rule_type: 'KEYWORD' | 'TLD' | 'SHORTENER';
  pattern: string;
  weight: number;
  is_active: boolean;
  created_at: string;
}

export interface ScannerConfig {
  id: number;
  ruleset_version: number;
  keyword_cap_points: number;
  ip_url_points: number;
  prior_pending_points: number;
  high_priority_threshold: number;
  updated_at: string;
}


export interface TelemetryMetrics {
  timestamp: string;
  metrics: Record<string, number>;
}

export const adminApi = {
  getUsers: async (filters: AdminUserFilters = {}): Promise<PaginatedResponse<User>> => {
    const res = await apiClient.get<PaginatedResponse<User>>('/admin-portal/users/', {
      params: filters,
    });
    return res.data;
  },

  approveUser: async (id: string): Promise<User> => {
    const res = await apiClient.post<User>(`/admin-portal/users/${id}/approve/`);
    return res.data;
  },

  rejectUser: async (id: string, reason: string): Promise<User> => {
    const res = await apiClient.post<User>(`/admin-portal/users/${id}/reject/`, {
      rejection_reason: reason,
    });
    return res.data;
  },

  changeRole: async (id: string, newRole: string): Promise<User> => {
    const res = await apiClient.post<User>(`/admin-portal/users/${id}/change-role/`, {
      role: newRole,
    });
    return res.data;
  },

  getRules: async (ruleType?: string): Promise<PaginatedResponse<HeuristicRule>> => {
    const res = await apiClient.get<PaginatedResponse<HeuristicRule>>('/admin-portal/rules/', {
      params: { rule_type: ruleType },
    });
    return res.data;
  },

  getScannerConfig: async (): Promise<ScannerConfig> => {
    const res = await apiClient.get<ScannerConfig>('/admin-portal/scanner-config/');
    return res.data;
  },

  updateScannerConfig: async (payload: Partial<ScannerConfig>): Promise<ScannerConfig> => {
    const res = await apiClient.patch<ScannerConfig>('/admin-portal/scanner-config/', payload);
    return res.data;
  },

  getAuditLogs: async (params: { severity?: string; event_type?: string; offset?: number; limit?: number } = {}): Promise<PaginatedResponse<AuditLogItem>> => {
    const res = await apiClient.get<PaginatedResponse<AuditLogItem>>('/admin-portal/audit-logs/', {
      params,
    });
    return res.data;
  },

  getTelemetryMetrics: async (rangeMinutes = 60): Promise<TelemetryMetrics> => {
    const res = await apiClient.get<TelemetryMetrics>('/admin-portal/telemetry/metrics/', {
      params: { range_minutes: rangeMinutes },
    });
    return res.data;
  },
};
