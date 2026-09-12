/**
 * Regression: Calendar handoff phải dùng route task-scoped thật, tải .ics có
 * Bearer token và ghi nhận opened; không được gọi route mock đã bỏ.
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  calendarHandoffBlockReason,
  loadCalendarHandoff,
  recordCalendarHandoffOpened,
} from '../src/lib/calendarHandoffClient.ts';

describe('calendar handoff client', () => {
  it('blocks handoff until the task is confirmed and dated', () => {
    assert.equal(calendarHandoffBlockReason('proposed', '2026-08-14T16:59:00Z', false), 'task_not_confirmed');
    assert.equal(calendarHandoffBlockReason('confirmed', null, false), 'missing_due_at');
    assert.equal(calendarHandoffBlockReason('confirmed', '2026-08-14T16:59:00Z', true), 'request_pending');
    assert.equal(calendarHandoffBlockReason('confirmed', '2026-08-14T16:59:00Z', false), null);
  });

  it('gets the task-scoped handoff and downloads its ICS with auth', async () => {
    const apiCalls: Array<{ path: string; options: unknown }> = [];
    const downloadCalls: Array<{ url: string; init?: RequestInit }> = [];
    const apiRequest = async <T>(path: string, options?: unknown): Promise<T> => {
      apiCalls.push({ path, options });
      return {
        taskId: 42,
        icsUrl: 'https://api.example.test/api/v1/tasks/42/calendar-handoff.ics',
        googleCalendarUrl: 'https://calendar.google.com/calendar/render?action=TEMPLATE',
        opened: false,
        openedAt: null,
      } as T;
    };
    const fetchIcs = async (input: string | URL | Request, init?: RequestInit) => {
      downloadCalls.push({ url: String(input), init });
      return new Response('BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n', {
        status: 200,
        headers: { 'Content-Type': 'text/calendar' },
      });
    };

    const result = await loadCalendarHandoff({
      taskId: 42,
      accessToken: 'access-token',
      apiRequest,
      fetchIcs,
      createObjectUrl: () => 'blob:calendar-handoff',
    });

    assert.equal(apiCalls.length, 1);
    assert.equal(apiCalls[0]?.path, '/api/v1/tasks/42/calendar-handoff');
    assert.deepEqual(apiCalls[0]?.options, { accessToken: 'access-token' });
    assert.equal(downloadCalls[0]?.url, 'https://api.example.test/api/v1/tasks/42/calendar-handoff.ics');
    assert.equal(new Headers(downloadCalls[0]?.init?.headers).get('Authorization'), 'Bearer access-token');
    assert.equal(result.icsUrl, 'blob:calendar-handoff');
    assert.equal(result.filename, 'mondaiy-task-42.ics');
    assert.equal(apiCalls.some(({ path }) => path === '/api/v1/calendar/handoff'), false);
  });

  it('marks the task-scoped handoff as opened', async () => {
    const calls: Array<{ path: string; options: unknown }> = [];
    const apiRequest = async <T>(path: string, options?: unknown): Promise<T> => {
      calls.push({ path, options });
      return {
        taskId: 42,
        icsUrl: 'https://api.example.test/api/v1/tasks/42/calendar-handoff.ics',
        googleCalendarUrl: 'https://calendar.google.com/calendar/render?action=TEMPLATE',
        opened: true,
        openedAt: '2026-08-10T02:00:00Z',
      } as T;
    };

    const result = await recordCalendarHandoffOpened(42, 'access-token', apiRequest);

    assert.deepEqual(calls, [
      {
        path: '/api/v1/tasks/42/calendar-handoff/opened',
        options: { method: 'POST', accessToken: 'access-token' },
      },
    ]);
    assert.equal(result.opened, true);
    assert.equal(result.openedAt, '2026-08-10T02:00:00Z');
  });
});
