import assert from 'node:assert/strict';
import test from 'node:test';
import { BRIEFING_ROUTINE_NAME, findBriefingRoutine } from '../src/briefingSchedule.ts';
import type { Routine } from '../src/api/client.ts';

const routine = (id: number, name: string): Routine => ({
  id,
  name,
  instructions: 'Tạo brief',
  frequency: 'daily',
  intervalDays: 2,
  hour: 8,
  minute: 0,
  dayOfWeek: null,
  dayOfMonth: null,
  timezone: 'Asia/Ho_Chi_Minh',
  enabled: true,
  notifyPush: true,
  notifyEmail: false,
  lastRunDate: null,
});

test('briefing settings select the named briefing routine, not the newest unrelated one', () => {
  const selected = findBriefingRoutine([
    routine(10, 'Theo dõi email khách hàng'),
    routine(4, BRIEFING_ROUTINE_NAME),
  ]);

  assert.equal(selected?.id, 4);
});
