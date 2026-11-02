import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TriagePage } from './TriagePage';
import { IndicatorManagementPage } from './IndicatorManagementPage';
import { triageApi } from '../../api/triage';
import type { PaginatedResponse, ScamReport, VerifiedIndicator } from '../../api/schema';

// Mock triageApi
vi.mock('../../api/triage', () => ({
  triageApi: {
    getQueue: vi.fn(),
    getReportDetail: vi.fn(),
    getEvidenceUrls: vi.fn(),
    verifyReport: vi.fn(),
    rejectReport: vi.fn(),
    getIndicators: vi.fn(),
    revokeIndicator: vi.fn(),
  },
}));

describe('Phase F4: Analyst Triage Workbench & Evidence Vault (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockReports: PaginatedResponse<ScamReport> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'rep-uuid-1',
        reference_code: 'SCM-2026-X8K1N4P2',
        status: 'PENDING',
        category: 'PHISHING',
        platform: 'WHATSAPP',
        message_text: 'Threatening SMS claiming account suspension from Maybank.',
        financial_loss: '1500.00',
        currency: 'MYR',
        payment_method: 'BANK_TRANSFER',
        created_at: '2026-02-01T10:00:00Z',
        is_anonymous: false,
      },
    ],
  };

  const mockIndicators: PaginatedResponse<VerifiedIndicator> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'ind-uuid-1',
        indicator_type: 'PHONE',
        normalized_value: '+60123456789',
        display_value: '+60123456789',
        threat_level: 'HIGH',
        confidence_score: 0.95,
        report_count: 5,
        public_note: 'Impersonation scam syndicate line',
        is_active: true,
        first_confirmed_at: '2026-01-15T08:00:00Z',
        last_confirmed_at: '2026-02-01T10:00:00Z',
      },
    ],
  };

  it('renders triage queue reports and detail split screen', async () => {
    vi.mocked(triageApi.getQueue).mockResolvedValueOnce(mockReports);
    vi.mocked(triageApi.getEvidenceUrls).mockResolvedValueOnce({
      evidence_urls: [
        {
          id: 'ev-1',
          sha256: 'abc123sha256hash',
          download_url: 'https://s3.amazonaws.com/evidence-vault/ev-1.png?X-Amz-Signature=xyz',
          expires_in_seconds: 900,
        },
      ],
    });

    render(
      <MemoryRouter>
        <TriagePage />
      </MemoryRouter>
    );

    // Verify queue displays reference code
    const refs = await screen.findAllByText('SCM-2026-X8K1N4P2');
    expect(refs.length).toBeGreaterThanOrEqual(1);

    // Verify presigned S3 evidence link carries rel="noopener noreferrer"
    const evidenceLink = await screen.findByRole('link', { name: /evidence #1/i });
    expect(evidenceLink.getAttribute('href')).toContain('s3.amazonaws.com');
    expect(evidenceLink.getAttribute('rel')).toBe('noopener noreferrer');
    expect(evidenceLink.getAttribute('target')).toBe('_blank');
  });

  it('submits indicator verification action cleanly', async () => {
    vi.mocked(triageApi.getQueue).mockResolvedValue(mockReports);
    vi.mocked(triageApi.getEvidenceUrls).mockResolvedValue({ evidence_urls: [] });
    vi.mocked(triageApi.verifyReport).mockResolvedValueOnce({
      status: 'VERIFIED',
      verified_count: 1,
    });

    render(
      <MemoryRouter>
        <TriagePage />
      </MemoryRouter>
    );

    const openModalBtn = await screen.findByRole('button', { name: /verify threat \(high\)/i });
    fireEvent.click(openModalBtn);

    const confirmBtn = await screen.findByRole('button', { name: /^confirm verification$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(triageApi.verifyReport).toHaveBeenCalledWith('rep-uuid-1', {
        threat_level: 'HIGH',
        public_note: undefined,
      });
      expect(screen.getByText(/indicators verified at high threat level/i)).toBeDefined();
    });
  });

  it('submits report rejection with rationale', async () => {
    vi.mocked(triageApi.getQueue).mockResolvedValue(mockReports);
    vi.mocked(triageApi.getEvidenceUrls).mockResolvedValue({ evidence_urls: [] });
    vi.mocked(triageApi.rejectReport).mockResolvedValueOnce({ status: 'REJECTED' });

    render(
      <MemoryRouter>
        <TriagePage />
      </MemoryRouter>
    );

    const openRejectModalBtn = await screen.findByRole('button', { name: /reject report/i });
    fireEvent.click(openRejectModalBtn);

    const confirmRejectBtn = await screen.findByRole('button', { name: /confirm rejection/i });
    fireEvent.click(confirmRejectBtn);

    await waitFor(() => {
      expect(triageApi.rejectReport).toHaveBeenCalled();
      expect(screen.getByText(/report rejected/i)).toBeDefined();
    });
  });

  it('loads verified indicators and allows revocation with audit justification', async () => {
    vi.mocked(triageApi.getIndicators).mockResolvedValueOnce(mockIndicators);
    vi.mocked(triageApi.revokeIndicator).mockResolvedValueOnce({ status: 'REVOKED' });

    render(
      <MemoryRouter>
        <IndicatorManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('+60123456789')).toBeDefined();
      expect(screen.getByText('HIGH')).toBeDefined();
      expect(screen.getByText('95%')).toBeDefined();
    });

    const revokeBtn = screen.getByRole('button', { name: /revoke/i });
    fireEvent.click(revokeBtn);

    const reasonInput = screen.getByPlaceholderText(/false positive/i);
    fireEvent.change(reasonInput, { target: { value: 'Number reclaimed by telco' } });

    const confirmBtn = screen.getByRole('button', { name: /confirm revocation/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(triageApi.revokeIndicator).toHaveBeenCalledWith('ind-uuid-1', 'Number reclaimed by telco');
    });
  });
});
