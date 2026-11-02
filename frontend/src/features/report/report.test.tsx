import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LookupPage } from '../lookup/LookupPage';
import { ReportSuccessPage } from './ReportSuccessPage';
import { reportsApi } from '../../api/reports';
import type { CreateReportResponse, LookupResponse } from '../../api/schema';

// Mock reportsApi
vi.mock('../../api/reports', () => ({
  reportsApi: {
    lookup: vi.fn(),
    createReport: vi.fn(),
    getOptions: vi.fn(),
    trackReport: vi.fn(),
    getMyReports: vi.fn(),
  },
}));

describe('Phase F3: Citizen Threat Lookup & Scam Reporting Portal (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders lookup widget and displays RED confirmed threat verdict', async () => {
    const mockVerdict: LookupResponse = {
      input: '+60123456789',
      detected_type: 'PHONE',
      verdict: 'RED',
      verdict_title: 'Confirmed Scam / High Risk',
      verdict_description: 'This indicator is linked to confirmed scam operations.',
      matches: [
        {
          indicator_type: 'PHONE',
          display_value: '+60123456789',
          threat_level: 'HIGH',
          report_count: 8,
          public_note: 'Impersonating Maybank customer support.',
        },
      ],
    };

    vi.mocked(reportsApi.lookup).mockResolvedValueOnce(mockVerdict);

    render(
      <MemoryRouter>
        <LookupPage />
      </MemoryRouter>
    );

    const input = screen.getByRole('textbox', { name: /enter phone/i });
    fireEvent.change(input, { target: { value: '+60123456789' } });

    const submitBtn = screen.getByRole('button', { name: /verify now/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Verdict: RED/i)).toBeDefined();
      expect(screen.getByText(/Confirmed Scam \/ High Risk/i)).toBeDefined();
    });
  });

  it('enforces mandatory Access Key acknowledgment on anonymous submission success', async () => {
    const mockSuccess: CreateReportResponse = {
      reference_code: 'SCM-2026-T9K2M4P1',
      status: 'PENDING',
      access_key: 'acc_sec_128bit_mock_key_xyz',
      playbook: {
        title: 'Emergency Action Playbook',
        steps: [
          { title: 'Contact Bank Hotline', detail: 'Call bank emergency freeze line immediately.' },
        ],
        hotlines: [{ name: 'National Scam Response Centre (NSRC)', number: '997' }],
      },
    };

    render(
      <MemoryRouter>
        <ReportSuccessPage reportData={mockSuccess} />
      </MemoryRouter>
    );

    // Verify Reference code and Access key are displayed
    expect(screen.getByText('SCM-2026-T9K2M4P1')).toBeDefined();
    expect(screen.getByText('acc_sec_128bit_mock_key_xyz')).toBeDefined();

    // Verify "Continue to Home" button is disabled until user checks acknowledgment
    const continueBtn = screen.getByRole('button', { name: /continue to home/i });
    expect(continueBtn.hasAttribute('disabled')).toBe(true);

    // Check acknowledgment checkbox
    const ackCheckbox = screen.getByRole('checkbox', {
      name: /i have securely saved my access key/i,
    });
    fireEvent.click(ackCheckbox);

    // Button should now be enabled
    expect(continueBtn.hasAttribute('disabled')).toBe(false);

    // CRITICAL SECURITY RULE: Access Key is NEVER stored in localStorage
    expect(localStorage.getItem('access_key')).toBeNull();
    expect(localStorage.getItem('SCM-2026-T9K2M4P1')).toBeNull();
  });
});
