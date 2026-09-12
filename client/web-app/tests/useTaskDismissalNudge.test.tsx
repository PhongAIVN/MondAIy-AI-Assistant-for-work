// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { recordTaskDecision, useTaskDismissalNudge } from '../src/hooks/useTaskDismissalNudge';

const { addToast } = vi.hoisted(() => ({ addToast: vi.fn() }));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: (selector: (state: { addToast: typeof addToast }) => unknown) => selector({ addToast }),
}));

const NudgeHarness = () => {
  useTaskDismissalNudge();
  return null;
};

describe('useTaskDismissalNudge', () => {
  afterEach(() => {
    cleanup();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('shows a sad mascot toast after three dismissals in a row, then resets the streak', () => {
    render(<NudgeHarness />);

    recordTaskDecision('dismissed');
    recordTaskDecision('dismissed');
    expect(addToast).not.toHaveBeenCalled();

    recordTaskDecision('dismissed');
    expect(addToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'mondaiy hơi buồn một chút',
        mascotGif: '/loadinggif1.gif',
      }),
    );

    addToast.mockClear();
    recordTaskDecision('dismissed');
    recordTaskDecision('dismissed');
    expect(addToast).not.toHaveBeenCalled();
  });

  it('breaks the streak when the user confirms a task in between', () => {
    render(<NudgeHarness />);

    recordTaskDecision('dismissed');
    recordTaskDecision('dismissed');
    recordTaskDecision('confirmed');
    recordTaskDecision('dismissed');
    recordTaskDecision('dismissed');

    expect(addToast).not.toHaveBeenCalled();
  });
});
