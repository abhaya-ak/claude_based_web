import { apiClient } from './client';
import type { ThreatAdvisory, PaginatedResponse } from './schema';

export interface VolumeDataPoint {
  date: string;
  count: number;
}

export interface LossesByCurrency {
  currency: string;
  total_loss: string;
  report_count: number;
}

export interface TacticBreakdown {
  tactic: string;
  count: number;
  percentage: number;
}

export interface SpikeAlert {
  category: string;
  current_count: number;
  baseline_count: number;
  percentage_increase: number;
  is_spike: boolean;
}

export interface CreateAdvisoryPayload {
  title: string;
  summary: string;
  content: string;
  audience_group: 'GENERAL' | 'ELDERLY' | 'TEENAGER' | 'NON_TECH' | 'ALL';
  primary_category: string;
}

export const analyticsApi = {
  getVolumeTrends: async (days = 30): Promise<{ points: VolumeDataPoint[] }> => {
    const res = await apiClient.get<{ points: VolumeDataPoint[] }>('/analytics/volume/', {
      params: { days },
    });
    return res.data;
  },

  getLosses: async (): Promise<{ losses: LossesByCurrency[] }> => {
    const res = await apiClient.get<{ losses: LossesByCurrency[] }>('/analytics/losses/');
    return res.data;
  },

  getTactics: async (): Promise<{ tactics: TacticBreakdown[] }> => {
    const res = await apiClient.get<{ tactics: TacticBreakdown[] }>('/analytics/tactics/');
    return res.data;
  },

  getSpikes: async (): Promise<{ spikes: SpikeAlert[] }> => {
    const res = await apiClient.get<{ spikes: SpikeAlert[] }>('/analytics/spikes/');
    return res.data;
  },

  // Threat Advisories (Analyst broadcast)
  getAdvisories: async (offset = 0, limit = 20): Promise<PaginatedResponse<ThreatAdvisory>> => {
    const res = await apiClient.get<PaginatedResponse<ThreatAdvisory>>('/advisories/', {
      params: { offset, limit },
    });
    return res.data;
  },

  createAdvisory: async (payload: CreateAdvisoryPayload): Promise<ThreatAdvisory> => {
    const res = await apiClient.post<ThreatAdvisory>('/advisories/', payload);
    return res.data;
  },

  publishAdvisory: async (id: string): Promise<ThreatAdvisory> => {
    const res = await apiClient.post<ThreatAdvisory>(`/advisories/${id}/publish/`);
    return res.data;
  },
};
