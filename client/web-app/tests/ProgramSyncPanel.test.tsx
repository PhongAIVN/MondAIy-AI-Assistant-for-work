// @vitest-environment jsdom

/**
 * Luồng đồng bộ lịch chương trình phía học viên (ADR-009).
 *
 * Điều đáng test không phải chuỗi hiển thị mà là ba ràng buộc: xem trước không
 * ghi, chỉ ghi mốc được tick, và mốc đã khớp thì không tick được.
 */

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProgramSyncPanel } from '../src/components/calendar/ProgramSyncPanel';
import { ApiError } from '../src/lib/apiClient';

const mocks = vi.hoisted(() => ({
  previewProgramSync: vi.fn(),
  applyProgramSync: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/programCalendarApi', () => ({
  previewProgramSync: mocks.previewProgramSync,
  applyProgramSync: mocks.applyProgramSync,
}));

const KE_HOACH = {
  cohortSlug: 'cohort-III',
  items: [
    {
      programEventId: 1,
      eventType: 'custom' as const,
      title: 'WORKSHOP 08',
      startAt: '2026-08-16T13:00:00Z',
      endAt: '2026-08-16T15:00:00Z',
      action: 'create' as const,
      reason: 'Chưa có trong lịch của bạn.',
    },
    {
      programEventId: 2,
      eventType: 'gate_deadline' as const,
      title: 'Hạn nộp MVP',
      startAt: '2026-08-16T16:59:00Z',
      endAt: null,
      action: 'update' as const,
      reason: 'Ban tổ chức đã đổi mốc này sau lần bạn duyệt.',
    },
    {
      programEventId: 3,
      eventType: 'custom' as const,
      title: 'OFFICE HOUR 08',
      startAt: '2026-08-14T13:00:00Z',
      endAt: null,
      action: 'unchanged' as const,
      reason: 'Đã đồng bộ và khớp nguồn.',
    },
  ],
};

beforeEach(() => {
  mocks.previewProgramSync.mockReset();
  mocks.applyProgramSync.mockReset();
  mocks.previewProgramSync.mockResolvedValue(KE_HOACH);
  mocks.applyProgramSync.mockResolvedValue({ created: 1, updated: 1, skipped: [] });
});

afterEach(cleanup);

const moPanel = async () => {
  const user = userEvent.setup();
  render(<ProgramSyncPanel />);
  await user.click(screen.getByRole('button', { name: /Xem danh sách|Review list/i }));
  await screen.findByText('WORKSHOP 08');
  return user;
};

describe('ProgramSyncPanel', () => {
  it('chưa bấm gì thì không gọi cả preview lẫn apply', () => {
    render(<ProgramSyncPanel />);
    expect(mocks.previewProgramSync).not.toHaveBeenCalled();
    expect(mocks.applyProgramSync).not.toHaveBeenCalled();
  });

  it('xem trước không ghi gì lên lịch', async () => {
    await moPanel();
    expect(mocks.previewProgramSync).toHaveBeenCalledTimes(1);
    expect(mocks.applyProgramSync).not.toHaveBeenCalled();
  });

  it('tick sẵn mốc cần tạo và cần cập nhật, không tick mốc đã khớp', async () => {
    await moPanel();

    const workshop = screen.getByRole('checkbox', { name: 'WORKSHOP 08' });
    const gate = screen.getByRole('checkbox', { name: 'Hạn nộp MVP' });
    const daKhop = screen.getByRole('checkbox', { name: 'OFFICE HOUR 08' });

    expect((workshop as HTMLInputElement).checked).toBe(true);
    expect((gate as HTMLInputElement).checked).toBe(true);
    expect((daKhop as HTMLInputElement).checked).toBe(false);
    // Mốc đã khớp không cho tick: ghi lại nó là gọi Google thừa cho không việc gì.
    expect((daKhop as HTMLInputElement).disabled).toBe(true);
  });

  it('chỉ gửi đi những mốc còn được tick', async () => {
    const user = await moPanel();

    await user.click(screen.getByRole('checkbox', { name: 'Hạn nộp MVP' }));
    await user.click(screen.getByRole('button', { name: /Đồng bộ 1 mốc|Sync 1 item/i }));

    await waitFor(() => expect(mocks.applyProgramSync).toHaveBeenCalledTimes(1));
    expect(mocks.applyProgramSync).toHaveBeenCalledWith('access-token', { programEventIds: [1] });
  });

  it('bỏ tick hết thì nút đồng bộ tắt', async () => {
    const user = await moPanel();

    await user.click(screen.getByRole('checkbox', { name: 'WORKSHOP 08' }));
    await user.click(screen.getByRole('checkbox', { name: 'Hạn nộp MVP' }));

    const nut = screen.getByRole('button', { name: /Đồng bộ 0 mốc|Sync 0 item/i });
    expect((nut as HTMLButtonElement).disabled).toBe(true);
  });

  it('mốc ghi hỏng được nêu tên, không nuốt im lặng', async () => {
    mocks.applyProgramSync.mockResolvedValue({
      created: 1,
      updated: 0,
      skipped: ['Hạn nộp MVP: không còn trong lịch Google, cần duyệt lại'],
    });
    const user = await moPanel();

    await user.click(screen.getByRole('button', { name: /Đồng bộ 2 mốc|Sync 2 item/i }));

    expect(await screen.findByText(/không còn trong lịch Google, cần duyệt lại/)).toBeTruthy();
  });

  it('tài khoản chưa khớp danh tính chương trình nhận đúng lý do từ máy chủ', async () => {
    mocks.previewProgramSync.mockRejectedValue(
      new ApiError(403, 'Tài khoản này chưa khớp danh tính chương trình nên chưa đồng bộ được lịch khóa học.'),
    );
    const user = userEvent.setup();
    render(<ProgramSyncPanel />);

    await user.click(screen.getByRole('button', { name: /Xem danh sách|Review list/i }));

    const canhBao = await screen.findByRole('alert');
    expect(canhBao.textContent).toMatch(/chưa khớp danh tính chương trình/);
  });

  it('kèm hạn daily thì nạp lại danh sách với đúng bộ loại mốc', async () => {
    const user = await moPanel();

    await user.click(screen.getByRole('checkbox', { name: /hạn nộp daily|daily submission/i }));

    await waitFor(() => expect(mocks.previewProgramSync).toHaveBeenCalledTimes(2));
    expect(mocks.previewProgramSync).toHaveBeenLastCalledWith('access-token', {
      eventTypes: ['custom', 'gate_deadline', 'weekly_deadline', 'daily_deadline'],
    });
  });
});
