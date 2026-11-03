import { apiClient } from './client';
import type {
  LookupResponse,
  CreateReportResponse,
  TrackReportResponse,
  ScamReport,
  PaginatedResponse,
} from './schema';

export interface LookupPayload {
  input: string;
}

export interface TrackPayload {
  reference_code: string;
  access_key: string;
}

export interface ReportOptions {
  categories: Array<{ value: string; label: string }>;
  platforms: Array<{ value: string; label: string }>;
  payment_methods: Array<{ value: string; label: string }>;
  admin_areas: Record<string, string[]>;
}

export const reportsApi = {
  lookup: async (payload: LookupPayload): Promise<LookupResponse> => {
    const res = await apiClient.post<LookupResponse>('/lookups/', payload);
    return res.data;
  },

  getOptions: async (): Promise<ReportOptions> => {
    const res = await apiClient.get<ReportOptions>('/reports/options/');
    return res.data;
  },

  createReport: async (
    formData: FormData,
    idempotencyKey?: string
  ): Promise<CreateReportResponse> => {
    const headers: Record<string, string> = {
      'Content-Type': 'multipart/form-data',
    };
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }

    const res = await apiClient.post<CreateReportResponse>('/reports/', formData, {
      headers,
    });
    return res.data;
  },

  trackReport: async (payload: TrackPayload): Promise<TrackReportResponse> => {
    const res = await apiClient.post<TrackReportResponse>('/reports/track/', payload);
    return res.data;
  },

  getMyReports: async (offset = 0, limit = 20): Promise<PaginatedResponse<ScamReport>> => {
    const res = await apiClient.get<PaginatedResponse<ScamReport>>('/reports/mine/', {
      params: { offset, limit },
    });
    return res.data;
  },
};
