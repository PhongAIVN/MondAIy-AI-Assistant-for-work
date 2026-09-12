/**
 * Thùng rác task: hạn còn lại phải nói đúng sự thật của backend.
 *
 * Backend (PR#86) chỉ xoá vĩnh viễn task có `status === 'cancelled'` VÀ
 * `cancelled_at` khác NULL, sau 7 ngày. Hai loại KHÔNG bao giờ bị đụng tới:
 * task `dismissed`, và task huỷ từ trước khi có cột `cancelled_at`.
 *
 * Hiện đếm ngược cho hai loại đó là nói với người dùng một hạn xoá không tồn
 * tại — và ngược lại, không hiện gì cho task sắp bị xoá thật thì họ mất việc mà
 * không được báo. Đây là chỗ dễ sai nhất trong cả tính năng.
 */

import { describe, expect, it } from 'vitest';

import { TRASH_RETENTION_DAYS, trashLabel, trashState } from '../src/lib/taskTrash';
import type { Task } from '../src/lib/tasksApi';

const NOW = new Date('2026-08-27T12:00:00Z');

function task(overrides: Partial<Task>): Task {
  return {
    id: 1,
    clusterKey: 'k',
    title: 'Task',
    detail: '',
    dueAt: null,
    allDay: false,
    ambiguous: false,
    status: 'cancelled',
    sourceCount: 1,
    signalStrength: 1,
    calendarEventId: null,
    createdAt: NOW.toISOString(),
    completedAt: null,
    cancelledAt: null,
    actualMinutes: null,
    updatedAt: NOW.toISOString(),
    evidence: [],
    ...overrides,
  } as Task;
}

function daysAgo(days: number): string {
  return new Date(NOW.getTime() - days * 86_400_000).toISOString();
}

describe('trashState', () => {
  it('task không phải cancelled thì không nằm trong thùng rác', () => {
    expect(trashState(task({ status: 'confirmed' }), NOW)).toEqual({ kind: 'not_in_trash' });
  });

  it('dismissed KHÔNG nằm trong thùng rác — backend không bao giờ xoá nó', () => {
    expect(trashState(task({ status: 'dismissed', cancelledAt: daysAgo(30) }), NOW)).toEqual({
      kind: 'not_in_trash',
    });
  });

  it('cancelled mà thiếu mốc huỷ thì giữ lại vô thời hạn, KHÔNG bịa hạn', () => {
    expect(trashState(task({ cancelledAt: null }), NOW)).toEqual({ kind: 'kept_indefinitely' });
  });

  it('mốc huỷ không đọc được cũng không được đoán một con số', () => {
    expect(trashState(task({ cancelledAt: 'không-phải-ngày' }), NOW)).toEqual({
      kind: 'kept_indefinitely',
    });
  });

  it('vừa huỷ thì còn đúng số ngày lưu giữ', () => {
    expect(trashState(task({ cancelledAt: daysAgo(0) }), NOW)).toEqual({
      kind: 'expiring',
      daysLeft: TRASH_RETENTION_DAYS,
    });
  });

  it('làm tròn LÊN — còn nửa ngày vẫn là "còn 1 ngày", không phải 0', () => {
    expect(trashState(task({ cancelledAt: daysAgo(6.5) }), NOW)).toEqual({
      kind: 'expiring',
      daysLeft: 1,
    });
  });

  it('quá hạn thì báo sắp bị xoá', () => {
    expect(trashState(task({ cancelledAt: daysAgo(8) }), NOW)).toEqual({ kind: 'due_for_purge' });
  });

  it('đúng mốc 7 ngày là đã quá hạn — khớp điều kiện < cutoff ở backend', () => {
    expect(trashState(task({ cancelledAt: daysAgo(TRASH_RETENTION_DAYS) }), NOW)).toEqual({
      kind: 'due_for_purge',
    });
  });
});

describe('trashLabel', () => {
  it('không nằm trong rác thì không hiện gì', () => {
    expect(trashLabel({ kind: 'not_in_trash' }, 'vi')).toBeNull();
  });

  it('giữ vô thời hạn thì KHÔNG nhắc tới ngày nào', () => {
    const label = trashLabel({ kind: 'kept_indefinitely' }, 'vi');
    expect(label).not.toBeNull();
    expect(label).not.toMatch(/\d/);
  });

  it('còn hạn thì nêu đúng số ngày, cả vi lẫn en', () => {
    expect(trashLabel({ kind: 'expiring', daysLeft: 3 }, 'vi')).toContain('3');
    expect(trashLabel({ kind: 'expiring', daysLeft: 3 }, 'en')).toContain('3');
  });
});
