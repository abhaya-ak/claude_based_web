import { apiClient, API_BASE_URL } from './client';
import axios from 'axios';
import type { User, LoginResponse, RefreshResponse } from './schema';

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
}

export interface StaffRegisterPayload extends RegisterPayload {
  role: 'ANALYST' | 'EDUCATOR';
  organization: string;
  credential_note: string;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<LoginResponse> => {
    const res = await apiClient.post<LoginResponse>('/auth/login/', payload);
    return res.data;
  },

  register: async (payload: RegisterPayload): Promise<User> => {
    const res = await apiClient.post<User>('/auth/register/', payload);
    return res.data;
  },

  registerStaff: async (payload: StaffRegisterPayload): Promise<User> => {
    const res = await apiClient.post<User>('/auth/register/staff/', payload);
    return res.data;
  },

  refresh: async (): Promise<RefreshResponse> => {
    const res = await axios.post<RefreshResponse>(
      `${API_BASE_URL}/auth/refresh/`,
      {},
      {
        withCredentials: true,
        headers: {
          'X-Requested-With': 'scamshield-web',
        },
      }
    );
    return res.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post(
      '/auth/logout/',
      {},
      {
        headers: {
          'X-Requested-With': 'scamshield-web',
        },
      }
    );
  },

  getMe: async (): Promise<User> => {
    const res = await apiClient.get<User>('/auth/me/');
    return res.data;
  },

  changePassword: async (payload: PasswordChangePayload): Promise<void> => {
    await apiClient.post('/auth/password/change/', payload);
  },
};
