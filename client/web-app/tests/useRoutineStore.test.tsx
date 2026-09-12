// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { resetRoutineStore, useRoutineStore } from '../src/stores/useRoutineStore';

const api = vi.hoisted(() => ({
  listRoutines: vi.fn(),
  listRecentRoutineRuns: vi.fn(),
}));

vi.mock('../src/lib/routinesApi', () => ({
  listRoutines: api.listRoutines,
  listRecentRoutineRuns: api.listRecentRoutineRuns,
}));

const ROUTINE = {
  id: 1,
  name: 'Daily digest',
  instructions: 'Summarize my day.',
  frequency: 'daily' as const,
  hour: 7,
  dayOfWeek: null,
  dayOfMonth: null,
  timezone: 'Asia/Ho_Chi_Minh',
  enabled: true,
  notifyPush: true,
  notifyEmail: false,
  lastRunDate: null,
};

beforeEach(() => {
  api.listRoutines.mockReset().mockResolvedValue([ROUTINE]);
  api.listRecentRoutineRuns.mockReset().mockResolvedValue([]);
  resetRoutineStore();
});

afterEach(resetRoutineStore);

describe('useRoutineStore', () => {
  it('loads once per user and serves the same cache to later pages', async () => {
    await useRoutineStore.getState().ensureLoaded('token', 'user-1');
    await useRoutineStore.getState().ensureLoaded('token', 'user-1');

    expect(api.listRoutines).toHaveBeenCalledTimes(1);
    expect(api.listRecentRoutineRuns).toHaveBeenCalledTimes(1);
    expect(useRoutineStore.getState().routines).toEqual([ROUTINE]);
  });

  it('does not expose the previous user cache after the user changes', async () => {
    api.listRoutines.mockResolvedValueOnce([ROUTINE]).mockResolvedValueOnce([]);

    await useRoutineStore.getState().ensureLoaded('token-a', 'user-a');
    await useRoutineStore.getState().ensureLoaded('token-b', 'user-b');

    expect(useRoutineStore.getState().userKey).toBe('user-b');
    expect(useRoutineStore.getState().routines).toEqual([]);
  });

  it('keeps briefing runs in the shared cache when a routine result arrives', () => {
    const run = {
      id: 9,
      routineId: 1,
      routineName: 'Daily digest',
      status: 'done' as const,
      outputText: 'Done',
      outputJson: null,
      errorMessage: null,
      startedAt: '2026-08-24T01:00:00Z',
      finishedAt: '2026-08-24T01:01:00Z',
    };

    useRoutineStore.getState().prependRecentRun(run);

    expect(useRoutineStore.getState().recentRuns[0]).toEqual(run);
  });
});
