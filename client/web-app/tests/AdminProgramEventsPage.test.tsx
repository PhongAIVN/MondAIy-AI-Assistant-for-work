// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminProgramEventsPage } from '../src/pages/admin/AdminProgramEventsPage';

const mocks = vi.hoisted(() => ({
  listProgramEvents: vi.fn(),
  createProgramEvent: vi.fn(),
  updateProgramEvent: vi.fn(),
  actOnProgramEvent: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) => selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/adminApi', () => ({
  listProgramEvents: mocks.listProgramEvents,
  createProgramEvent: mocks.createProgramEvent,
  updateProgramEvent: mocks.updateProgramEvent,
  actOnProgramEvent: mocks.actOnProgramEvent,
}));

const eventRow = (patch: Partial<Record<string, unknown>> = {}) => ({
  id: 11,
  cohortSlug: 'cohort-III',
  externalId: 'event:8@phoenix',
  eventType: 'custom',
  visibility: 'program',
  title: 'WORKSHOP 08',
  description: '',
  host: 'BTC',
  locationUrl: null,
  startAt: '2026-08-16T13:00:00Z',
  endAt: '2026-08-16T15:00:00Z',
  origin: 'feed',
  status: 'published',
  lockedFields: [],
  sourceConflict: false,
  feedPayload: null,
  updatedBy: null,
  updatedAt: null,
  publishedAt: '2026-08-12T00:00:00Z',
  ...patch,
});

const eventList = (items: unknown[], conflictCount = 0) => ({
  items,
  total: items.length,
  limit: 200,
  offset: 0,
  cohortSlug: 'cohort-III',
  conflictCount,
});

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.listProgramEvents.mockResolvedValue(eventList([eventRow()]));
  mocks.actOnProgramEvent.mockResolvedValue({ event: eventRow(), changedFields: [], notificationCount: 0 });
  mocks.updateProgramEvent.mockResolvedValue({ event: eventRow(), changedFields: ['title'], notificationCount: 0 });
  mocks.createProgramEvent.mockResolvedValue({ event: eventRow({ id: 12, status: 'draft', origin: 'admin' }), changedFields: [], notificationCount: 0 });
});

afterEach(cleanup);

describe('AdminProgramEventsPage', () => {
  it('shows publication, manual locks and source conflict evidence', async () => {
    mocks.listProgramEvents.mockResolvedValue(eventList([
      eventRow({
        title: 'Tên do đội ngũ đặt',
        lockedFields: ['title'],
        sourceConflict: true,
        feedPayload: { title: 'Tên mới từ Phoenix', starts_at: '2026-08-16T14:00:00Z' },
      }),
    ], 1));
    render(<AdminProgramEventsPage />);

    expect(await screen.findByText('Tên do đội ngũ đặt')).toBeTruthy();
    expect(screen.getByText(/giữ tay: title/)).toBeTruthy();
    expect(screen.getByText(/Tên mới từ Phoenix/)).toBeTruthy();
    expect(screen.getAllByText('Đã phát hành').some((element) => element.tagName !== 'BUTTON')).toBe(true);
  });

  it('publishes without notification unless admin explicitly opts in', async () => {
    mocks.listProgramEvents.mockResolvedValue(eventList([eventRow({ status: 'draft' })]));
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');

    await user.click(screen.getByRole('button', { name: 'Phát hành' }));
    expect(screen.getByRole('dialog', { name: 'Xác nhận phát hành lịch' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Xác nhận phát hành' }));

    await waitFor(() => expect(mocks.actOnProgramEvent).toHaveBeenCalledWith(
      'access-token',
      11,
      'publish',
      { notifyUsers: false, changeNote: undefined, expectedUpdatedAt: null },
    ));
  });

  it('does not offer notification on first publish because nobody can have synced the draft', async () => {
    mocks.listProgramEvents.mockResolvedValue(eventList([eventRow({ status: 'draft', updatedAt: '2026-08-16T10:00:00Z' })]));
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');

    await user.click(screen.getByRole('button', { name: 'Phát hành' }));
    expect(screen.queryByRole('checkbox', { name: /Báo cho người đã đồng bộ mốc này/ })).toBeNull();
    expect(screen.getByText(/Lần phát hành đầu chỉ đưa mốc vào nguồn tra cứu/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Xác nhận phát hành' }));

    await waitFor(() => expect(mocks.actOnProgramEvent).toHaveBeenCalledWith(
      'access-token',
      11,
      'publish',
      { notifyUsers: false, changeNote: undefined, expectedUpdatedAt: '2026-08-16T10:00:00Z' },
    ));
  });

  it('creates drafts with event type and never asks to notify users', async () => {
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');

    await user.click(screen.getByRole('button', { name: 'Thêm mốc' }));
    await user.type(screen.getByLabelText('Tiêu đề'), 'Mốc mới');
    await user.selectOptions(screen.getByLabelText('Loại mốc'), 'weekly_deadline');
    await user.type(screen.getByLabelText('Bắt đầu'), '2026-09-01T09:00');
    expect(screen.queryByRole('checkbox', { name: /Báo/ })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Tạo bản nháp' }));

    await waitFor(() => expect(mocks.createProgramEvent).toHaveBeenCalled());
    expect(mocks.createProgramEvent.mock.calls[0][1]).toMatchObject({
      title: 'Mốc mới',
      eventType: 'weekly_deadline',
      notifyUsers: false,
    });
  });

  it('offers official schedule templates when creating a cohort event', async () => {
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');

    await user.click(screen.getByRole('button', { name: 'Thêm mốc' }));
    await user.click(screen.getByRole('button', { name: 'Hạn gate' }));

    expect((screen.getByLabelText('Tiêu đề') as HTMLInputElement).value).toBe('Hạn gate');
    expect((screen.getByLabelText('Loại mốc') as HTMLSelectElement).value).toBe('gate_deadline');
    expect((screen.getByLabelText('Ghi chú') as HTMLTextAreaElement).value).toContain('gate');
  });

  it('blocks an invalid time range before calling the API', async () => {
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');
    await user.click(screen.getByRole('button', { name: 'Thêm mốc' }));
    await user.type(screen.getByLabelText('Tiêu đề'), 'Mốc sai giờ');
    await user.type(screen.getByLabelText('Bắt đầu'), '2026-09-01T10:00');
    await user.type(screen.getByLabelText('Kết thúc'), '2026-09-01T09:00');
    await user.click(screen.getByRole('button', { name: 'Tạo bản nháp' }));

    expect((await screen.findByRole('alert')).textContent).toContain('Thời gian kết thúc phải sau thời gian bắt đầu.');
    expect(mocks.createProgramEvent).not.toHaveBeenCalled();
  });

  it('preserves the edited form when the API rejects the update', async () => {
    mocks.updateProgramEvent.mockRejectedValue(new Error('Dữ liệu vừa được người khác cập nhật.'));
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');
    await user.click(screen.getByRole('button', { name: 'Sửa' }));
    const title = screen.getByLabelText('Tiêu đề');
    await user.clear(title);
    await user.type(title, 'Tên tôi đang sửa');
    await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));

    expect(await screen.findByText('Dữ liệu vừa được người khác cập nhật.')).toBeTruthy();
    expect(screen.getByRole('dialog', { name: 'Sửa mốc chương trình' })).toBeTruthy();
    expect((screen.getByLabelText('Tiêu đề') as HTMLInputElement).value).toBe('Tên tôi đang sửa');
  });

  it('marks the selected filter as pressed and reloads with its value', async () => {
    const user = userEvent.setup();
    render(<AdminProgramEventsPage />);
    await screen.findByText('WORKSHOP 08');
    const draftFilter = screen.getByRole('button', { name: 'Nháp — học viên chưa thấy' });
    await user.click(draftFilter);
    expect(draftFilter.getAttribute('aria-pressed')).toBe('true');
    await waitFor(() => expect(mocks.listProgramEvents).toHaveBeenLastCalledWith('access-token', {
      status: 'draft', conflictsOnly: false, limit: 200,
    }));
  });
});
