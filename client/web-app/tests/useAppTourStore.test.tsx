// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest';
import { useAppTourStore } from '../src/stores/useAppTourStore';

describe('useAppTourStore', () => {
  afterEach(() => {
    useAppTourStore.setState({ pending: false });
  });

  it('starts with no pending request', () => {
    expect(useAppTourStore.getState().pending).toBe(false);
  });

  it('flips pending on request, clears it after AppShell consumes it', () => {
    useAppTourStore.getState().requestAppTour();
    expect(useAppTourStore.getState().pending).toBe(true);

    useAppTourStore.getState().clearAppTourRequest();
    expect(useAppTourStore.getState().pending).toBe(false);
  });
});
