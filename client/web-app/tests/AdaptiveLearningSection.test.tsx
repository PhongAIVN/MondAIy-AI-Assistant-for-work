// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AdaptiveLearningSection } from '../src/components/privacy/AdaptiveLearningSection';
import { ApiError } from '../src/lib/apiClient';

const mocks = vi.hoisted(() => ({
  getLearningConsent: vi.fn(),
  updateLearningConsent: vi.fn(),
  listLearningCandidates: vi.fn(),
  rejectLearningCandidate: vi.fn(),
  resetLearning: vi.fn(),
  listLearningAudit: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/adaptiveLearningApi', () => ({
  getLearningConsent: mocks.getLearningConsent,
  updateLearningConsent: mocks.updateLearningConsent,
  listLearningCandidates: mocks.listLearningCandidates,
  rejectLearningCandidate: mocks.rejectLearningCandidate,
  resetLearning: mocks.resetLearning,
  listLearningAudit: mocks.listLearningAudit,
}));

const allOff = {
  consents: [
    { capability: 'chat_learning', enabled: false, policyVersion: null, consentedAt: null, revokedAt: null },
    { capability: 'adaptive_style', enabled: false, policyVersion: null, consentedAt: null, revokedAt: null },
    { capability: 'learned_skills', enabled: false, policyVersion: null, consentedAt: null, revokedAt: null },
    { capability: 'routine_learning', enabled: false, policyVersion: null, consentedAt: null, revokedAt: null },
  ],
};

const chatOn = {
  consents: [
    { capability: 'chat_learning', enabled: true, policyVersion: 'v1', consentedAt: '2026-08-22T00:00:00Z', revokedAt: null },
    ...allOff.consents.slice(1),
  ],
};

const candidate = {
  id: 7,
  candidateKey: 'style-verbosity',
  version: 1,
  candidateType: 'style_preference' as const,
  status: 'pending_review',
  payload: { dimension: 'verbosity', value: 'concise', rationale: 'Thường yêu cầu đi thẳng vào kết luận' },
  confidence: 0.82,
  expiresAt: '2026-09-21T00:00:00Z',
  createdAt: '2026-08-22T00:00:00Z',
};

function mockHappyPath(consents = allOff, candidates: typeof candidate[] = []) {
  mocks.getLearningConsent.mockResolvedValue(consents);
  mocks.listLearningCandidates.mockResolvedValue({ candidates });
  mocks.listLearningAudit.mockResolvedValue({
    events: [
      { id: 1, actor: 'user', action: 'consent_enabled', targetType: 'capability', targetRef: 'chat_learning', reasonCodes: ['policy:v1'], createdAt: '2026-08-22T01:00:00Z' },
    ],
  });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('AdaptiveLearningSection', () => {
  it('renders four consent switches off and an empty inbox by default', async () => {
    mockHappyPath();

    render(<AdaptiveLearningSection />);

    expect(await screen.findByText(/mondaiy đã học gì/i)).toBeTruthy();
    const switches = screen.getAllByRole('switch');
    expect(switches).toHaveLength(4);
    for (const sw of switches) expect(sw.getAttribute('aria-checked')).toBe('false');
    expect(screen.getByText(/chưa có gì cần xem xét/i)).toBeTruthy();
    expect(screen.getByText(/bật quyền học/i)).toBeTruthy();
  });

  it('enables a capability through the API and refetches state', async () => {
    const user = userEvent.setup();
    mockHappyPath();
    mocks.updateLearningConsent.mockResolvedValue(chatOn);

    render(<AdaptiveLearningSection />);
    await screen.findByText(/mondaiy đã học gì/i);

    await user.click(screen.getByRole('switch', { name: /chat_learning/ }));

    await waitFor(() =>
      expect(mocks.updateLearningConsent).toHaveBeenCalledWith('chat_learning', true, 'access-token'),
    );
    await waitFor(() => expect(mocks.getLearningConsent).toHaveBeenCalledTimes(2));
  });

  it('locks the switches and explains when the server rejects with 403', async () => {
    const user = userEvent.setup();
    mockHappyPath();
    const forbidden = new ApiError(403, 'Năng lực học thích ứng chưa được mở.');
    mocks.updateLearningConsent.mockRejectedValueOnce(forbidden);

    render(<AdaptiveLearningSection />);
    await screen.findByText(/mondaiy đã học gì/i);

    await user.click(screen.getByRole('switch', { name: /chat_learning/ }));

    const notice = await screen.findByRole('status');
    expect(notice.textContent).toMatch(/chưa được mở/i);
    await waitFor(() => {
      for (const sw of screen.getAllByRole('switch')) {
        expect((sw as HTMLButtonElement).disabled).toBe(true);
      }
    });
  });

  it('rejects a candidate through the API and clears it from the inbox', async () => {
    const user = userEvent.setup();
    mockHappyPath(allOff, [candidate]);
    mocks.rejectLearningCandidate.mockResolvedValue({ ...candidate, status: 'rejected' });
    mocks.listLearningCandidates.mockResolvedValueOnce({ candidates: [candidate] }).mockResolvedValue({ candidates: [] });

    render(<AdaptiveLearningSection />);
    await screen.findByText(/verbosity: concise/i);

    await user.click(screen.getByRole('button', { name: /đừng gợi ý lại/i }));

    await waitFor(() => expect(mocks.rejectLearningCandidate).toHaveBeenCalledWith(7, ['user_rejected'], 'access-token'));
    await waitFor(() => expect(screen.getByText(/chưa có gì cần xem xét/i)).toBeTruthy());
  });

  it('resets learning only after the user confirms', async () => {
    const user = userEvent.setup();
    mockHappyPath(allOff, [candidate]);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    mocks.resetLearning.mockResolvedValue({ scope: 'all', forgotten: 1 });

    render(<AdaptiveLearningSection />);
    await screen.findByText(/đừng gợi ý lại/i);

    await user.click(screen.getByRole('button', { name: /đặt lại$/i }));
    expect(mocks.resetLearning).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    await user.click(screen.getByRole('button', { name: /đặt lại$/i }));

    await waitFor(() => expect(mocks.resetLearning).toHaveBeenCalledWith('all', 'access-token'));
  });
});
