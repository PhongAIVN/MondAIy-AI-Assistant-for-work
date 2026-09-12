/**
 * Thùng rác hiện ra được trên màn hình Task, không chỉ đúng ở tầng hàm thuần.
 *
 * Bản đầu của tính năng này tôi chèn nhánh thùng rác vào BÊN TRONG khối
 * `task.status === 'confirmed'`. Nó không bao giờ chạy, và toàn bộ test hàm
 * thuần vẫn xanh — chỉ `npm run build` bắt được (TS2367). Test render này là
 * lớp bắt trực tiếp loại lỗi đó.
 */

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TasksPage } from '../src/pages/TasksPage';

const mocks = vi.hoisted(() => ({
  listTasks: vi.fn(),
  listCalendarEvents: vi.fn(),
  confirmTask: vi.fn(),
  dismissTask: vi.fn(),
  completeTask: vi.fn(),
  cancelTask: vi.fn(),
  restoreTask: vi.fn(),
  syncTaskToCalendar: vi.fn(),
  createCalendarEvent: vi.fn(),
  updateCalendarEvent: vi.fn(),
  deleteCalendarEvent: vi.fn(),
  undoCalendarOperation: vi.fn(),
  addToast: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ addToast: mocks.addToast }),
}));

vi.mock('../src/lib/tasksApi', () => ({
  listTasks: mocks.listTasks,
  listCalendarEvents: mocks.listCalendarEvents,
  confirmTask: mocks.confirmTask,
  dismissTask: mocks.dismissTask,
  completeTask: mocks.completeTask,
  cancelTask: mocks.cancelTask,
  restoreTask: mocks.restoreTask,
  syncTaskToCalendar: mocks.syncTaskToCalendar,
}));

vi.mock('../src/lib/calendarApi', () => ({
  createCalendarEvent: mocks.createCalendarEvent,
  updateCalendarEvent: mocks.updateCalendarEvent,
  deleteCalendarEvent: mocks.deleteCalendarEvent,
  undoCalendarOperation: mocks.undoCalendarOperation,
}));

vi.mock('../src/lib/connectionsApi', () => ({
  createConnectIntent: vi.fn(),
}));

vi.mock('../src/hooks/useProductRating', () => ({ recordMeaningfulAction: vi.fn() }));

const cancelledTask = {
  id: 42,
  clusterKey: 'jira-42',
  title: 'Việc đã huỷ',
  detail: '',
  dueAt: null,
  allDay: false,
  ambiguous: false,
  status: 'cancelled' as const,
  sourceCount: 1,
  signalStrength: 0.5,
  calendarEventId: null,
  createdAt: '2026-08-20T02:00:00Z',
  completedAt: null,
  cancelledAt: '2026-08-25T02:00:00Z',
  actualMinutes: null,
  updatedAt: '2026-08-25T02:00:00Z',
  evidence: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listTasks.mockResolvedValue({ tasks: [cancelledTask] });
  mocks.listCalendarEvents.mockResolvedValue({ calendars: [{ id: 'primary', name: 'Personal' }], events: [] });
});

afterEach(() => {
  // Repo KHÔNG bật auto-cleanup của Testing Library.
  cleanup();
});

describe('Thùng rác task', () => {
  it('có mục lọc Thùng rác, và task đã huỷ hiện hạn còn lại kèm nút khôi phục', async () => {
    render(<TasksPage />);

    const trashFilter = await screen.findByRole('option', { name: 'Thùng rác' });
    expect(trashFilter).not.toBeNull();

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /hộp việc|todo/i }),
      'trash',
    );

    expect(await screen.findByTestId('trash-countdown-42')).not.toBeNull();
    expect(
      screen.getByRole('button', { name: 'Khôi phục Việc đã huỷ khỏi thùng rác' }),
    ).not.toBeNull();
  });

  it('bấm khôi phục thì gọi đúng API restoreTask', async () => {
    mocks.restoreTask.mockResolvedValue({ ...cancelledTask, status: 'proposed', cancelledAt: null });
    render(<TasksPage />);

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: /hộp việc|todo/i }),
      'trash',
    );
    const button = await screen.findByRole('button', {
      name: 'Khôi phục Việc đã huỷ khỏi thùng rác',
    });
    await userEvent.click(button);

    await waitFor(() => expect(mocks.restoreTask).toHaveBeenCalledWith(42, expect.anything()));
  });
});
