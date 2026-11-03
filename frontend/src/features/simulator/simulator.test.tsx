import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SimulatorGamePage } from './SimulatorGamePage';
import { ScenarioStudioPage } from './ScenarioStudioPage';
import { literacyApi } from '../../api/literacy';
import type {
  SimulatorAttemptInitResponse,
  AnswerFeedbackResponse,
  SimulatorAttemptCompletionResponse,
  PaginatedResponse,
  StudioScenario,
} from '../../api/schema';

// Mock literacyApi
vi.mock('../../api/literacy', () => ({
  literacyApi: {
    startAttempt: vi.fn(),
    submitAnswer: vi.fn(),
    completeAttempt: vi.fn(),
    getStudioScenarios: vi.fn(),
    createStudioScenario: vi.fn(),
    publishStudioScenario: vi.fn(),
    addScenarioRedFlag: vi.fn(),
  },
}));

describe('Phase F6: Interactive Spot-the-Scam Simulator & Quizzes (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockAttemptInit: SimulatorAttemptInitResponse = {
    attempt_id: 'att-uuid-1',
    session_key: 'sess-uuid-1',
    scenario_count: 1,
    scenarios: [
      {
        id: 'scen-uuid-1',
        title: 'Urgent Bank Account Suspension SMS',
        channel: 'SMS',
        difficulty: 1,
        image_url: '/media/scenarios/sms-threat.png',
        image_alt: 'SMS from Maybank alleging account suspension',
        // Anti-cheat verification: is_scam and explanation are omitted server-side
      },
    ],
  };

  const mockFeedback: AnswerFeedbackResponse = {
    scenario_id: 'scen-uuid-1',
    is_correct: true,
    explanation: 'Banks never send urgent threats containing suspicious .top or .xyz links.',
    red_flags: [
      {
        id: 'rf-1',
        flag_code: 'URGENCY',
        x_pct: 15.0,
        y_pct: 35.0,
        w_pct: 40.0,
        h_pct: 10.0,
        explanation: 'Offender attempts to induce panic by claiming account is permanently frozen.',
      },
    ],
  };

  const mockCompletion: SimulatorAttemptCompletionResponse = {
    attempt_id: 'att-uuid-1',
    status: 'COMPLETED',
    score_pct: 100,
    completed_at: '2026-02-02T12:00:00Z',
    profile: {
      total_scenarios: 1,
      correct_scenarios: 1,
      blind_spots: ['URGENCY'],
    },
    remediation_guides: [
      {
        id: 'guide-uuid-1',
        slug: 'spotting-bank-impersonation-sms',
        title: 'Spotting Bank Impersonation SMS Scams',
        summary: 'Learn how scammers impersonate official banking OTP alerts and verify genuine domain headers.',
        body_markdown: 'Content',
        status: 'PUBLISHED',
        audience_groups: ['GENERAL'],
        tactics: ['URGENCY'],
        reading_time_minutes: 4,
        created_at: '2026-02-01T10:00:00Z',
      },
    ],
  };

  it('plays through simulator game, submits answers, and shows remediation guides', async () => {
    vi.mocked(literacyApi.startAttempt).mockResolvedValueOnce(mockAttemptInit);
    vi.mocked(literacyApi.submitAnswer).mockResolvedValueOnce(mockFeedback);
    vi.mocked(literacyApi.completeAttempt).mockResolvedValueOnce(mockCompletion);

    render(
      <MemoryRouter>
        <SimulatorGamePage />
      </MemoryRouter>
    );

    // Initial Screen -> Start button
    const startBtn = await screen.findByRole('button', { name: /start simulation|begin/i });
    fireEvent.click(startBtn);

    // Verify scenario card loaded
    await waitFor(() => {
      expect(screen.getByText('Urgent Bank Account Suspension SMS')).toBeDefined();
    });

    // Make decision -> Mark as Scam
    const scamBtn = screen.getByRole('button', { name: /flag as scam|is a scam/i });
    fireEvent.click(scamBtn);

    // Verify feedback rendered
    await waitFor(() => {
      expect(screen.getByText(/correct decision/i)).toBeDefined();
      expect(screen.getByText(/banks never send urgent threats/i)).toBeDefined();
    });

    // Finish / View Results
    const nextBtn = screen.getByRole('button', { name: /view results|finish/i });
    fireEvent.click(nextBtn);

    // Verify Results Card & Remediation Guides
    await waitFor(() => {
      expect(screen.getByText('100%')).toBeDefined();
      expect(screen.getByText(/spotting bank impersonation sms scams/i)).toBeDefined();
    });
  });

  it('allows educators to list scenarios in studio', async () => {
    const mockScenarios: PaginatedResponse<StudioScenario> = {
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'scen-uuid-1',
          title: 'Fake Courier Parcel Fee SMS',
          channel: 'SMS',
          is_scam: true,
          tactic: 'URGENCY',
          difficulty: 1,
          image_url: '/media/scenarios/courier.png',
          image_alt: 'SMS alleging pending parcel delivery fee',
          explanation: 'Couriers do not demand credit card payments via unsolicited text messages.',
          status: 'PUBLISHED',
          red_flags: [],
          created_at: '2026-02-01T10:00:00Z',
        },
      ],
    };

    vi.mocked(literacyApi.getStudioScenarios).mockResolvedValueOnce(mockScenarios);

    render(
      <MemoryRouter>
        <ScenarioStudioPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Fake Courier Parcel Fee SMS')).toBeDefined();
      expect(screen.getByText('URGENCY')).toBeDefined();
    });
  });
});
