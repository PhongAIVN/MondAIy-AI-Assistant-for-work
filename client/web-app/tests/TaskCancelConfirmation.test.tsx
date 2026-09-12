// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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

vi.mock('react-router-dom', () => ({ useNavigate: () => mocks.navigate }));
vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) => selector({ accessToken: 'access-token' }),
}));
vi.mock('../src/stores/useAppStore', () => ({ useAppStore: () => ({ addToast: mocks.addToast }) }));
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
vi.mock('../src/lib/connectionsApi', () => ({ createConnectIntent: vi.fn() }));
vi.mock('../src/hooks/useProductRating', () => ({ recordMeaningfulAction: vi.fn() }));

const confirmedTask = {
  id: 42,
  clusterKey: 'jira-42',
  title: 'Gửi báo cáo tuần',
  detail: '',
  dueAt: null,
  allDay: false,
  ambiguous: false,
  status: 'confirmed' as const,
  sourceCount: 1,
  signalStrength: 0.5,
  calendarEventId: null,
  createdAt: '2026-08-20T02:00:00Z',
  completedAt: null,
  cancelledAt: null,
  actualMinutes: null,
  updatedAt: '2026-08-25T02:00:00Z',
  evidence: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listTasks.mockResolvedValue({ tasks: [confirmedTask] });
  mocks.listCalendarEvents.mockResolvedValue({ calendars: [{ id: 'primary', name: 'Personal' }], events: [] });
  mocks.cancelTask.mockResolvedValue({ ...confirmedTask, status: 'cancelled', cancelledAt: '2026-08-28T02:00:00Z' });
});

afterEach(() => cleanup());

async function openCancellationDialog() {
  const user = userEvent.setup();
  render(<TasksPage />);
  await user.click(await screen.findByRole('button', { name: 'Huỷ Gửi báo cáo tuần' }));
  return user;
}

describe('Xác nhận huỷ task', () => {
  it('mở hộp thoại trước khi huỷ và chưa gọi API', async () => {
    await openCancellationDialog();

    expect(screen.getByRole('dialog')).not.toBeNull();
    expect(mocks.cancelTask).not.toHaveBeenCalled();
  });

  it('nêu tên task, thời hạn thùng rác và nhãn cho trình đọc màn hình', async () => {
    await openCancellationDialog();

    const dialog = screen.getByRole('dialog', { name: 'Huỷ Gửi báo cáo tuần?' });
    expect(dialog).not.toBeNull();
    expect(within(dialog).getByText('Gửi báo cáo tuần')).not.toBeNull();
    expect(within(dialog).getByText(/thùng rác.*7 ngày/i)).not.toBeNull();
  });

  it('chỉ gọi cancelTask với đúng id sau khi xác nhận', async () => {
    const user = await openCancellationDialog();
    await user.click(screen.getByRole('button', { name: 'Huỷ task' }));

    await waitFor(() => expect(mocks.cancelTask).toHaveBeenCalledWith(42, 'access-token'));
  });

  it('đóng bằng nút giữ lại thì không gọi API', async () => {
    const user = await openCancellationDialog();
    await user.click(screen.getByRole('button', { name: 'Giữ lại task' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(mocks.cancelTask).not.toHaveBeenCalled();
  });

  it('đóng bằng Esc thì không gọi API', async () => {
    await openCancellationDialog();
    fireEvent.keyDown(window, { key: 'Escape' });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(mocks.cancelTask).not.toHaveBeenCalled();
  });

  it('nhấn Enter không xác nhận huỷ', async () => {
    const user = await openCancellationDialog();
    await user.keyboard('{Enter}');

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(mocks.cancelTask).not.toHaveBeenCalled();
  });

  it('đóng khi bấm ngoài hộp thoại thì không gọi API', async () => {
    await openCancellationDialog();
    fireEvent.mouseDown(screen.getByRole('dialog').parentElement as HTMLElement);

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(mocks.cancelTask).not.toHaveBeenCalled();
  });
});
