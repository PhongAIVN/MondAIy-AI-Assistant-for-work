// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';

import { cancelTask, completeTask } from '../src/lib/tasksApi';

const taskResponse = {
  id: 7,
  clusterKey: 'gmail-7',
  title: 'Submit report',
  detail: 'Send the PDF.',
  dueAt: '2026-08-14T09:00:00+07:00',
  allDay: false,
  ambiguous: false,
  status: 'completed',
  sourceCount: 1,
  signalStrength: 0.9,
  calendarEventId: null,
  createdAt: '2026-08-13T00:00:00Z',
  updatedAt: '2026-08-13T00:00:00Z',
  evidence: [],
};

describe('task lifecycle API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it.each([
    ['complete', completeTask],
    ['cancel', cancelTask],
  ] as const)('posts the %s transition with the signed-in session', async (transition, request) => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...taskResponse, status: transition === 'complete' ? 'completed' : 'cancelled' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await request(7, 'access-token');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith(`/api/v1/tasks/7/${transition}`)).toBe(true);
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer access-token');
    if (transition === 'complete') expect(init.body).toBeUndefined();
  });

  it('sends actualMinutes only when the user supplied it', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(taskResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await completeTask(7, 'access-token', 90);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(JSON.stringify({ actualMinutes: 90 }));
  });
});
