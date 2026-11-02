import { apiClient } from './client';
import type { ScamReport, PaginatedResponse, VerifiedIndicator } from './schema';

export interface TriageQueueFilters {
  platform?: string;
  category?: string;
  is_high_priority?: boolean;
  min_risk_score?: number;
  offset?: number;
  limit?: number;
}

export interface VerifyPayload {
  threat_level: 'HIGH' | 'MEDIUM' | 'LOW';
  public_note?: string;
}

export interface RejectPayload {
  rejection_reason: string;
}

export interface EvidenceUrlsResponse {
  evidence_urls: Array<{
    id: string;
    sha256: string;
    download_url: string;
    expires_in_seconds: number;
  }>;
}

export const triageApi = {
  getQueue: async (filters: TriageQueueFilters = {}): Promise<PaginatedResponse<ScamReport>> => {
    const res = await apiClient.get<PaginatedResponse<ScamReport>>('/triage/queue/', {
      params: filters,
    });
    return res.data;
  },

  getReportDetail: async (id: string): Promise<ScamReport> => {
    const res = await apiClient.get<ScamReport>(`/triage/reports/${id}/`);
    return res.data;
  },

  getEvidenceUrls: async (id: string): Promise<EvidenceUrlsResponse> => {
    const res = await apiClient.get<EvidenceUrlsResponse>(`/triage/reports/${id}/evidence/`);
    return res.data;
  },

  verifyReport: async (id: string, payload: VerifyPayload): Promise<{ status: string; verified_count: number }> => {
    const res = await apiClient.post<{ status: string; verified_count: number }>(
      `/triage/reports/${id}/verify/`,
      payload
    );
    return res.data;
  },

  rejectReport: async (id: string, payload: RejectPayload): Promise<{ status: string }> => {
    const res = await apiClient.post<{ status: string }>(`/triage/reports/${id}/reject/`, payload);
    return res.data;
  },

  getIndicators: async (offset = 0, limit = 20): Promise<PaginatedResponse<VerifiedIndicator>> => {
    const res = await apiClient.get<PaginatedResponse<VerifiedIndicator>>('/triage/indicators/', {
      params: { offset, limit },
    });
    return res.data;
  },

  revokeIndicator: async (id: string, reason: string): Promise<{ status: string }> => {
    const res = await apiClient.post<{ status: string }>(`/triage/indicators/${id}/revoke/`, {
      revocation_reason: reason,
    });
    return res.data;
  },
};
