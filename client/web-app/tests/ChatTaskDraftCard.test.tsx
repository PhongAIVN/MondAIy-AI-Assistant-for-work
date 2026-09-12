// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatTaskDraftCard } from '../src/components/briefing/ChatTaskDraftCard';
import { formatTaskDueAt, toLocalDateTimeInputValue } from '../src/lib/taskDateTime';

const mocks = vi.hoisted(() => ({
  cancelTask: vi.fn(),
  syncTaskToCalendar: vi.fn(),
  updateTask: vi.fn(),
}));

vi.mock('../src/lib/tasksApi', () => ({
  cancelTask: mocks.cancelTask,
  syncTaskToCalendar: mocks.syncTaskToCalendar,
  updateTask: mocks.updateTask,
}));

const draft = {
  id: 7,
  title: 'Mentor Duty',
  dueAt: '2026-08-11T20:00:00+07:00',
  allDay: false,
  status: 'proposed' as const,
  calendarWriteReady: true,
  calendarEventId: null,
};

describe('ChatTaskDraftCard', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('preserves the timezone when converting a server ISO due date for the local UI', () => {
    const iso = '2026-08-15T15:31:00Z';
    const localValue = toLocalDateTimeInputValue(iso, 'Asia/Ho_Chi_Minh');

    expect(localValue).toBe('2026-08-15T22:31');
    expect(formatTaskDueAt(iso, 'en-GB', 'Asia/Ho_Chi_Minh')).toContain('22:31');
  });

  it('creates the task without confirmation and exposes only edit/delete actions', async () => {
    mocks.cancelTask.mockResolvedValue({ ...draft, status: 'cancelled' });
    const user = userEvent.setup();
    render(
      <ChatTaskDraftCard
        task={draft}
        accessToken="access-token"
        language="vi"
        onOpenTasks={vi.fn()}
        onReconnectGoogle={vi.fn()}
      />,
    );

    expect(screen.getByText('Task đã tạo')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Xác nhận|Đồng bộ|Calendar|Xem trong Tasks/ })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Xóa task' }));
    await waitFor(() => expect(mocks.cancelTask).toHaveBeenCalledWith(7, 'access-token'));
  });

  it('lets the user edit task details before approval', async () => {
    mocks.updateTask.mockResolvedValue({ ...draft, title: 'Updated duty', detail: 'Bring notes' });
    const user = userEvent.setup();
    render(
      <ChatTaskDraftCard
        task={{ ...draft, detail: 'Original detail' }}
        accessToken="access-token"
        language="en"
        onOpenTasks={vi.fn()}
        onReconnectGoogle={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Edit details' }));
    await user.clear(screen.getByLabelText('Task title'));
    await user.type(screen.getByLabelText('Task title'), 'Updated duty');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mocks.updateTask).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ title: 'Updated duty', detail: 'Original detail' }),
      'access-token',
    ));
    expect(screen.getByText('Updated duty')).toBeTruthy();
  });

  it('removes the card after delete', async () => {
    mocks.cancelTask.mockResolvedValue({ ...draft, status: 'cancelled' });
    const user = userEvent.setup();
    render(
      <ChatTaskDraftCard
        task={draft}
        accessToken="access-token"
        language="vi"
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Xóa task' }));
    await waitFor(() => expect(mocks.cancelTask).toHaveBeenCalledWith(7, 'access-token'));
    await waitFor(() => expect(screen.queryByLabelText('Bản nháp task Mentor Duty')).toBeNull());
  });
});
