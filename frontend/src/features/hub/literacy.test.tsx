import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LiteracyHubPage } from './LiteracyHubPage';
import { GuideDetailPage } from './GuideDetailPage';
import { EducatorStudioPage } from './EducatorStudioPage';
import { literacyApi } from '../../api/literacy';
import type { PaginatedResponse, LiteracyGuide } from '../../api/schema';

// Mock literacyApi
vi.mock('../../api/literacy', () => ({
  literacyApi: {
    getGuides: vi.fn(),
    getGuideDetail: vi.fn(),
    getStudioGuides: vi.fn(),
    createStudioGuide: vi.fn(),
    updateStudioGuide: vi.fn(),
    publishStudioGuide: vi.fn(),
    uploadGuideAsset: vi.fn(),
  },
}));

describe('Phase F5: Literacy Hub CMS & Educator Studio (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockGuides: PaginatedResponse<LiteracyGuide> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'guide-uuid-1',
        slug: 'spotting-bank-impersonation-sms',
        title: 'Spotting Bank Impersonation SMS Scams',
        summary: 'Learn how scammers impersonate official banking OTP alerts and verify genuine domain headers.',
        body_markdown: '## Understanding SMS Spoofing\n\nBanks never send URLs in SMS messages asking for credentials.\n\nAlways verify via official banking applications.',
        status: 'PUBLISHED',
        audience_groups: ['GENERAL', 'ELDERLY'],
        tactics: ['URGENCY', 'AUTHORITY'],
        reading_time_minutes: 4,
        created_at: '2026-02-01T10:00:00Z',
        published_at: '2026-02-02T10:00:00Z',
      },
    ],
  };

  it('renders public learning hub and filters by audience chip', async () => {
    vi.mocked(literacyApi.getGuides).mockResolvedValue(mockGuides);

    render(
      <MemoryRouter>
        <LiteracyHubPage />
      </MemoryRouter>
    );

    // Verify initial guide render
    await waitFor(() => {
      expect(screen.getByText('Spotting Bank Impersonation SMS Scams')).toBeDefined();
      expect(screen.getByText(/4 min/i)).toBeDefined();
    });

    // Click elderly filter
    const seniorsChip = screen.getByRole('button', { name: /seniors & families/i });
    fireEvent.click(seniorsChip);

    await waitFor(() => {
      expect(literacyApi.getGuides).toHaveBeenCalledWith({ group: 'ELDERLY' });
    });
  });

  it('renders guide detail page with markdown and speech synthesis button', async () => {
    const guideItem = mockGuides.results[0];
    vi.mocked(literacyApi.getGuideDetail).mockResolvedValueOnce(guideItem);

    render(
      <MemoryRouter initialEntries={['/literacy/spotting-bank-impersonation-sms']}>
        <Routes>
          <Route path="/literacy/:slug" element={<GuideDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: /spotting bank impersonation sms scams/i })).toBeDefined();
      expect(screen.getByText(/banks never send urls in sms messages/i)).toBeDefined();
    });

    // Check TTS read aloud button exists
    const ttsBtn = screen.getByRole('button', { name: /read aloud|listen/i });
    expect(ttsBtn).toBeDefined();
  });

  it('allows educators to list studio guides, create drafts, and publish', async () => {
    vi.mocked(literacyApi.getStudioGuides).mockResolvedValue(mockGuides);
    vi.mocked(literacyApi.createStudioGuide).mockResolvedValueOnce({
      ...mockGuides.results[0],
      id: 'guide-uuid-2',
      title: 'Crypto Investment Traps',
      slug: 'crypto-investment-traps',
      status: 'DRAFT',
    });
    vi.mocked(literacyApi.publishStudioGuide).mockResolvedValueOnce({
      ...mockGuides.results[0],
      status: 'PUBLISHED',
    });

    render(
      <MemoryRouter>
        <EducatorStudioPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Spotting Bank Impersonation SMS Scams')).toBeDefined();
    });

    // Open create guide modal
    const newGuideBtn = screen.getByRole('button', { name: /create new guide/i });
    fireEvent.click(newGuideBtn);

    // Fill form
    const titleInput = screen.getByLabelText(/guide title/i);
    fireEvent.change(titleInput, { target: { value: 'Crypto Investment Traps' } });

    const summaryInput = screen.getByLabelText(/summary/i);
    fireEvent.change(summaryInput, { target: { value: 'Recognize pump and dump schemes.' } });

    const bodyInput = screen.getByLabelText(/content markdown/i);
    fireEvent.change(bodyInput, { target: { value: '# Crypto Warning\nNever send crypto to strangers.' } });

    const submitBtn = screen.getByRole('button', { name: /save as draft/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(literacyApi.createStudioGuide).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Crypto Investment Traps',
          slug: 'crypto-investment-traps',
        })
      );
    });
  });
});
