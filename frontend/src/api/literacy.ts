import { apiClient } from './client';
import type {
  LiteracyGuide,
  PaginatedResponse,
  SimulatorAttemptInitResponse,
  AnswerFeedbackResponse,
  SimulatorAttemptCompletionResponse,
  StudioScenario,
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

export interface SubmitAnswerPayload {
  scenario_id: string;
  answered_is_scam: boolean;
  selected_flag_code?: string;
  session_key?: string;
}

export interface CreateRedFlagPayload {
  flag_code: string;
  x_pct: number;
  y_pct: number;
  w_pct: number;
  h_pct: number;
  explanation: string;
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
  startAttempt: async (): Promise<SimulatorAttemptInitResponse> => {
    const res = await apiClient.post<SimulatorAttemptInitResponse>('/simulator/attempts/');
    return res.data;
  },

  submitAnswer: async (attemptId: string, payload: SubmitAnswerPayload): Promise<AnswerFeedbackResponse> => {
    const res = await apiClient.post<AnswerFeedbackResponse>(
      `/simulator/attempts/${attemptId}/answers/`,
      payload
    );
    return res.data;
  },

  completeAttempt: async (attemptId: string, sessionKey?: string): Promise<SimulatorAttemptCompletionResponse> => {
    const res = await apiClient.post<SimulatorAttemptCompletionResponse>(
      `/simulator/attempts/${attemptId}/complete/`,
      sessionKey ? { session_key: sessionKey } : {}
    );
    return res.data;
  },

  // Scenario Studio (Educators)
  getStudioScenarios: async (offset = 0, limit = 20): Promise<PaginatedResponse<StudioScenario>> => {
    const res = await apiClient.get<PaginatedResponse<StudioScenario>>('/studio/scenarios/', {
      params: { offset, limit },
    });
    return res.data;
  },

  createStudioScenario: async (formData: FormData): Promise<StudioScenario> => {
    const res = await apiClient.post<StudioScenario>('/studio/scenarios/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  publishStudioScenario: async (id: string): Promise<{ status: string }> => {
    const res = await apiClient.post<{ status: string }>(`/studio/scenarios/${id}/publish/`);
    return res.data;
  },

  addScenarioRedFlag: async (scenarioId: string, payload: CreateRedFlagPayload): Promise<void> => {
    await apiClient.post(`/studio/scenarios/${scenarioId}/flags/`, payload);
  },
};
