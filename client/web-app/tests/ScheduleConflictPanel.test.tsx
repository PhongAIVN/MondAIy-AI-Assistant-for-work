// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ScheduleConflictPanel } from '../src/components/calendar/ScheduleConflictPanel';
import type { ScheduleConflict } from '../src/lib/scheduleConflictsApi';

const mocks = vi.hoisted(() => ({
  detectScheduleConflicts: vi.fn(),
  resolveScheduleConflict: vi.fn(),
}));

vi.mock('../src/lib/scheduleConflictsApi', () => ({
  detectScheduleConflicts: mocks.detectScheduleConflicts,
  resolveScheduleConflict: mocks.resolveScheduleConflict,
}));

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'vi',
    t: {
      scheduleConflicts: {
        title: 'Trùng nhau, cần bạn quyết',
        subtitle: 'Bạn chọn ưu tiên bên nào.',
        rescan: 'Quét lại',
        loading: 'Đang quét tuần này…',
        loadError: 'Không quét được.',
        resolveError: 'Không lưu được quyết định của bạn.',
        empty: 'Tuần này không có gì trùng nhau.',
        typeTimeOverlap: 'Trùng khoảng giờ',
        typeSameItem: 'Có thể là cùng một việc',
        overlapMinutes: 'chồng {count} phút',
        taskSide: 'Task',
        eventSide: 'Sự kiện lịch',
        taskMeta: '{status} · {sources} nguồn',
        eventMeta: 'Lịch: {calendar}',
        timeUnknown: 'Giờ chưa rõ',
        suggestedBadge: 'Gợi ý',
        suggestTask: 'Gợi ý: ưu tiên task.',
        suggestEvent: 'Gợi ý: ưu tiên sự kiện lịch.',
        suggestUndecided: 'Không gợi ý — bằng chứng không nghiêng về bên nào.',
        taskStatus: { proposed: 'Chờ xem lại', confirmed: 'Đã xác nhận' },
        reasons: {
          task_multi_source: 'nhiều nguồn cùng xác nhận hạn chót này',
          evidence_tie: 'chưa đủ căn cứ để nghiêng về bên nào',
        },
        noteLabel: 'Lý do (không bắt buộc)',
        notePlaceholder: 'ví dụ: buổi mentor không dời được.',
        actionPrioritizeTask: 'Ưu tiên task',
        actionPrioritizeEvent: 'Ưu tiên sự kiện',
        actionKeepBoth: 'Giữ cả hai',
        actionTaskIsCanonical: 'Task là bản chính',
        actionEventIsCanonical: 'Sự kiện là bản chính',
        actionNotDuplicate: 'Không phải bản trùng',
        timeOverlapEffectHint: 'Chỉ ghi lại quyết định.',
        sameItemEffectHint: 'Chọn sự kiện thì task trùng chuyển sang đã bỏ qua.',
      },
    },
  }),
}));

const WEEK_START = new Date('2026-08-17T00:00:00Z');
const WEEK_END = new Date('2026-08-24T00:00:00Z');

const overlapConflict: ScheduleConflict = {
  id: 11,
  conflictType: 'time_overlap',
  status: 'open',
  overlapMinutes: 15,
  suggestion: 'prioritize_task',
  suggestionReasons: ['task_multi_source'],
  resolution: null,
  resolutionNote: '',
  resolvedAt: null,
  detectedAt: '2026-08-17T09:00:00Z',
  task: {
    taskId: 5,
    title: 'Nộp báo cáo milestone 2',
    dueAt: '2026-08-18T14:00:00Z',
    allDay: false,
    ambiguous: false,
    status: 'confirmed',
    sourceCount: 2,
    signalStrength: 1,
  },
  event: {
    title: 'Mentor office hours',
    calendarId: 'primary',
    eventId: 'evt-1',
    startsAt: '2026-08-18T14:15:00Z',
    endsAt: '2026-08-18T15:15:00Z',
    allDay: false,
    deepLink: 'https://calendar.google.com/event?eid=abc',
    syncedAt: '2026-08-17T08:00:00Z',
  },
};

const sameItemConflict: ScheduleConflict = {
  ...overlapConflict,
  id: 12,
  conflictType: 'same_item',
  suggestion: 'prioritize_event',
  suggestionReasons: ['evidence_tie'],
  task: { ...overlapConflict.task, status: 'proposed' },
  event: { ...overlapConflict.event, title: 'Nộp báo cáo Milestone 2' },
};

const renderPanel = (onResolved = vi.fn()) =>
  render(
    <ScheduleConflictPanel
      accessToken="access-token"
      timeFrom={WEEK_START}
      timeTo={WEEK_END}
      locale="vi-VN"
      onResolved={onResolved}
    />,
  );

describe('ScheduleConflictPanel', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('scans the visible week and shows both sides with the suggested reason', async () => {
    mocks.detectScheduleConflicts.mockResolvedValue({ conflicts: [overlapConflict], openCount: 1 });

    renderPanel();

    await screen.findByText('Nộp báo cáo milestone 2');
    expect(mocks.detectScheduleConflicts).toHaveBeenCalledWith(
      'access-token',
      WEEK_START.toISOString(),
      WEEK_END.toISOString(),
    );
    expect(screen.getByText('Mentor office hours')).toBeTruthy();
    expect(screen.getByText('Trùng khoảng giờ')).toBeTruthy();
    expect(screen.getByText('chồng 15 phút')).toBeTruthy();
    expect(screen.getByText('Gợi ý: ưu tiên task.')).toBeTruthy();
    expect(screen.getByText('— nhiều nguồn cùng xác nhận hạn chót này')).toBeTruthy();
    // Gợi ý không tự áp dụng: cả ba lựa chọn vẫn phải hiện ra cho người dùng.
    expect(screen.getByRole('button', { name: 'Ưu tiên task' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ưu tiên sự kiện' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Giữ cả hai' })).toBeTruthy();
  });

  it('says plainly when there is no suggestion instead of guessing a side', async () => {
    mocks.detectScheduleConflicts.mockResolvedValue({
      conflicts: [{ ...overlapConflict, suggestion: 'undecided', suggestionReasons: ['evidence_tie'] }],
      openCount: 1,
    });

    renderPanel();

    expect(await screen.findByText('Không gợi ý — bằng chứng không nghiêng về bên nào.')).toBeTruthy();
  });

  it('sends the chosen priority with the note and drops the row', async () => {
    mocks.detectScheduleConflicts.mockResolvedValue({ conflicts: [overlapConflict], openCount: 1 });
    mocks.resolveScheduleConflict.mockResolvedValue({ ...overlapConflict, status: 'resolved' });
    const onResolved = vi.fn();
    const user = userEvent.setup();
    renderPanel(onResolved);

    await screen.findByText('Nộp báo cáo milestone 2');
    await user.type(screen.getByPlaceholderText('ví dụ: buổi mentor không dời được.'), 'Họp không dời được');
    await user.click(screen.getByRole('button', { name: 'Ưu tiên sự kiện' }));

    await waitFor(() =>
      expect(mocks.resolveScheduleConflict).toHaveBeenCalledWith(
        11,
        'prioritize_event',
        'access-token',
        'Họp không dời được',
      ),
    );
    expect(onResolved).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByText('Nộp báo cáo milestone 2')).toBeNull());
  });

  it('uses duplicate wording and the dismissal warning for same_item', async () => {
    mocks.detectScheduleConflicts.mockResolvedValue({ conflicts: [sameItemConflict], openCount: 1 });

    renderPanel();

    await screen.findByText('Có thể là cùng một việc');
    expect(screen.getByRole('button', { name: 'Sự kiện là bản chính' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Không phải bản trùng' })).toBeTruthy();
    expect(screen.getByText('Chọn sự kiện thì task trùng chuyển sang đã bỏ qua.')).toBeTruthy();
    // Kiểu same_item không nói "chồng bao nhiêu phút" — đó là chuyện của trùng giờ.
    expect(screen.queryByText('chồng 15 phút')).toBeNull();
  });

  it('shows the empty state when the week is clean', async () => {
    mocks.detectScheduleConflicts.mockResolvedValue({ conflicts: [], openCount: 0 });

    renderPanel();

    expect(await screen.findByText('Tuần này không có gì trùng nhau.')).toBeTruthy();
  });

  it('surfaces a scan failure instead of pretending the week is clean', async () => {
    mocks.detectScheduleConflicts.mockRejectedValue(new Error('boom'));

    renderPanel();

    expect(await screen.findByText('Không quét được.')).toBeTruthy();
  });

  it('surfaces a resolve failure and keeps the row for another try', async () => {
    mocks.detectScheduleConflicts.mockResolvedValue({ conflicts: [overlapConflict], openCount: 1 });
    mocks.resolveScheduleConflict.mockRejectedValue(new Error('boom'));
    const user = userEvent.setup();
    renderPanel();

    await screen.findByText('Nộp báo cáo milestone 2');
    await user.click(screen.getByRole('button', { name: 'Ưu tiên task' }));

    expect(await screen.findByText('Không lưu được quyết định của bạn.')).toBeTruthy();
    expect(screen.getByText('Nộp báo cáo milestone 2')).toBeTruthy();
  });

  it('renders nothing while signed out', () => {
    const { container } = render(
      <ScheduleConflictPanel accessToken={null} timeFrom={WEEK_START} timeTo={WEEK_END} locale="vi-VN" />,
    );

    expect(container.textContent).toBe('');
    expect(mocks.detectScheduleConflicts).not.toHaveBeenCalled();
  });
  it('rescans after the calendar cache sync completes', async () => {
    mocks.detectScheduleConflicts
      .mockResolvedValueOnce({ conflicts: [], openCount: 0 })
      .mockResolvedValueOnce({ conflicts: [overlapConflict], openCount: 1 });

    const props = {
      accessToken: 'access-token',
      timeFrom: WEEK_START,
      timeTo: WEEK_END,
      locale: 'vi-VN',
    };
    const view = render(<ScheduleConflictPanel {...props} calendarSyncVersion={0} />);

    expect(await screen.findByText('Tuần này không có gì trùng nhau.')).toBeTruthy();
    view.rerender(<ScheduleConflictPanel {...props} calendarSyncVersion={1} />);

    expect(await screen.findByText('Nộp báo cáo milestone 2')).toBeTruthy();
    expect(mocks.detectScheduleConflicts).toHaveBeenCalledTimes(2);
  });
});
