import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock('../src/lib/apiClient', () => ({ apiRequest: mocks.apiRequest }));

import { updateProgramEvent } from '../src/lib/adminApi';

const eventRow = () => ({
  id: 11,
  cohortSlug: 'cohort-III',
  externalId: 'event-11',
  eventType: 'custom',
  visibility: 'program',
  title: 'Workshop',
  description: '',
  host: null,
  locationUrl: null,
  startAt: '2026-08-16T13:00:00Z',
  endAt: null,
  origin: 'admin',
  status: 'published',
  lockedFields: [],
  sourceConflict: false,
  feedPayload: null,
  updatedBy: '1',
  updatedAt: '2026-08-16T12:00:00Z',
  publishedAt: '2026-08-16T11:00:00Z',
});

beforeEach(() => mocks.apiRequest.mockReset());

describe('program event mutation contract', () => {
  it('keeps inline notification metadata returned by the backend row', async () => {
    mocks.apiRequest.mockResolvedValue({
      ...eventRow(),
      changedFields: ['startAt'],
      notificationCount: 12,
    });

    const result = await updateProgramEvent('access-token', 11, { title: 'Workshop mới' });

    expect(result.changedFields).toEqual(['startAt']);
    expect(result.notificationCount).toBe(12);
    expect(result.event.id).toBe(11);
  });
});
