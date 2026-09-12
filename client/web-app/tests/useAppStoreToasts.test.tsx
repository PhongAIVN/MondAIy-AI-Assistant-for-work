// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';

import { useAppStore } from '../src/stores/useAppStore';

describe('useAppStore toasts', () => {
  afterEach(() => {
    useAppStore.setState({ toasts: [] });
    vi.useRealTimers();
  });

  it('does not stack a toast with the same type, title, and message', () => {
    const { addToast } = useAppStore.getState();

    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to English.' });
    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to English.' });
    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to English.' });

    expect(useAppStore.getState().toasts).toHaveLength(1);
  });

  it('still shows a new toast once the message text actually differs', () => {
    const { addToast } = useAppStore.getState();

    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to English.' });
    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to Tiếng Việt.' });

    expect(useAppStore.getState().toasts).toHaveLength(2);
  });

  it('allows the same toast again once the previous one has expired', () => {
    vi.useFakeTimers();
    const { addToast } = useAppStore.getState();

    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to English.' });
    expect(useAppStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(4001);
    expect(useAppStore.getState().toasts).toHaveLength(0);

    addToast({ type: 'info', title: 'Language Updated', message: 'Switched to English.' });
    expect(useAppStore.getState().toasts).toHaveLength(1);
  });
});
