// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { recordMeaningfulAction, requestProductRating, useProductRating } from '../src/hooks/useProductRating';

const { addToast, authState, submitAppRating } = vi.hoisted(() => ({
  addToast: vi.fn(),
  authState: {
    accessToken: 'token',
    user: { id: 'user-1', role: 'participant' as 'participant' | 'admin' },
  },
  submitAppRating: vi.fn(),
}));

vi.mock('../src/lib/ratingApi', () => ({ submitAppRating }));
vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: typeof authState) => unknown) => selector(authState),
}));
vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: (selector: (state: { addToast: typeof addToast }) => unknown) => selector({ addToast }),
}));

const RatingHarness = () => {
  const { closePrompt, prompt, submit } = useProductRating();
  return (
    <>
      <output>{prompt ? `shown:${prompt.actionCount}` : 'hidden'}</output>
      <button onClick={() => void submit(5, 'Đây là phản hồi đủ dài để gửi đi và mở lượt tiếp theo.')}>rate</button>
      <button onClick={closePrompt}>close</button>
    </>
  );
};

describe('useProductRating', () => {
  afterEach(() => {
    cleanup();
    sessionStorage.clear();
    localStorage.clear();
    authState.user = { id: 'user-1', role: 'participant' };
    vi.clearAllMocks();
  });

  it('does not show on load, then shows after three successful prompt actions and resets after rating', async () => {
    submitAppRating.mockResolvedValue({
      id: 1,
      rating: 5,
      bonusQuestionsAwarded: 5,
      questionsRemaining: 5,
    });
    render(<RatingHarness />);

    expect(screen.getByRole('status').textContent).toBe('hidden');
    for (let count = 0; count < 2; count += 1) recordMeaningfulAction('grounded_answer_completed');
    expect(screen.getByRole('status').textContent).toBe('hidden');

    recordMeaningfulAction('grounded_answer_completed');
    expect(await screen.findByText('shown:3')).toBeTruthy();

    screen.getByRole('button', { name: 'rate' }).click();
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('hidden'));

    for (let count = 0; count < 2; count += 1) recordMeaningfulAction('grounded_answer_completed');
    expect(screen.getByRole('status').textContent).toBe('hidden');
    recordMeaningfulAction('grounded_answer_completed');
    expect(await screen.findByText('shown:3')).toBeTruthy();
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Đã mở thêm 5 câu hỏi',
    }));
  });

  it('opens immediately when the API reports that the daily quota is exhausted', async () => {
    render(<RatingHarness />);
    expect(screen.getByRole('status').textContent).toBe('hidden');

    requestProductRating();

    expect(await screen.findByText('shown:0')).toBeTruthy();
  });

  it('closes the current rating but opens again on the next explicit prompt', async () => {
    render(<RatingHarness />);
    requestProductRating();
    expect(await screen.findByText('shown:0')).toBeTruthy();

    screen.getByRole('button', { name: 'close' }).click();
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('hidden'));
    requestProductRating();

    expect(await screen.findByText('shown:0')).toBeTruthy();
  });

  it('does not automatically prompt an administrator', () => {
    authState.user = { id: 'admin-1', role: 'admin' };
    render(<RatingHarness />);
    for (let count = 0; count < 6; count += 1) recordMeaningfulAction('grounded_answer_completed');

    expect(screen.getByRole('status').textContent).toBe('hidden');
  });

  it('lets an administrator proactively open the feedback prompt', async () => {
    authState.user = { id: 'admin-1', role: 'admin' };
    render(<RatingHarness />);

    requestProductRating();

    expect(await screen.findByText('shown:0')).toBeTruthy();
  });
});
