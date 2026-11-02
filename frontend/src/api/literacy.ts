import { apiClient } from './client';
import type {
  LiteracyGuide,
  PaginatedResponse,
  SimulatorAttempt,
  AttemptAnswer,
  CompletionResult,
  GuideAsset,
} from './schema';

export interface GuideFilters {
  group?: string;
  language?: string;
  tactic?: string;
  offset?: number;
  limit?: number;
}

export interface CreateGuidePayload {
  title: string;
  slug: string;
  summary: string;
  body_markdown: string;
  audience_groups: string[];
  tactics: string[];
  reading_time_minutes: number;
}

export const literacyApi = {
  getGuides: async (filters: GuideFilters = {}): Promise<PaginatedResponse<LiteracyGuide>> => {
    const res = await apiClient.get<PaginatedResponse<LiteracyGuide>>('/guides/', {
      params: filters,
    });
    return res.data;
  },

  getGuideDetail: async (slug: string): Promise<LiteracyGuide> => {
    const res = await apiClient.get<LiteracyGuide>(`/guides/${slug}/`);
    return res.data;
  },

  // Studio Guides CRUD (Educators)
  getStudioGuides: async (offset = 0, limit = 20): Promise<PaginatedResponse<LiteracyGuide>> => {
    const res = await apiClient.get<PaginatedResponse<LiteracyGuide>>('/studio/guides/', {
      params: { offset, limit },
    });
    return res.data;
  },

  createStudioGuide: async (payload: CreateGuidePayload): Promise<LiteracyGuide> => {
    const res = await apiClient.post<LiteracyGuide>('/studio/guides/', payload);
    return res.data;
  },

  updateStudioGuide: async (id: string, payload: Partial<CreateGuidePayload>): Promise<LiteracyGuide> => {
    const res = await apiClient.patch<LiteracyGuide>(`/studio/guides/${id}/`, payload);
    return res.data;
  },

  publishStudioGuide: async (id: string): Promise<LiteracyGuide> => {
    const res = await apiClient.post<LiteracyGuide>(`/studio/guides/${id}/publish/`);
    return res.data;
  },

  uploadGuideAsset: async (guideId: string, formData: FormData): Promise<GuideAsset> => {
    const res = await apiClient.post<GuideAsset>(`/studio/guides/${guideId}/assets/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  // Spot-the-Scam Simulator
  startAttempt: async (): Promise<SimulatorAttempt> => {
    const res = await apiClient.post<SimulatorAttempt>('/simulator/attempts/');
    return res.data;
  },

  submitAnswer: async (attemptId: string, answer: AttemptAnswer): Promise<{ status: string }> => {
    const res = await apiClient.post<{ status: string }>(
      `/simulator/attempts/${attemptId}/answers/`,
      answer
    );
    return res.data;
  },

  completeAttempt: async (attemptId: string): Promise<CompletionResult> => {
    const res = await apiClient.post<CompletionResult>(
      `/simulator/attempts/${attemptId}/complete/`
    );
    return res.data;
  },
};
