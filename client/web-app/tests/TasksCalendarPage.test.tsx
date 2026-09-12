// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
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
  syncTaskToCalendar: vi.fn(),
  updateTask: vi.fn(),
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
  syncTaskToCalendar: mocks.syncTaskToCalendar,
  updateTask: mocks.updateTask,
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

const proposedTask = {
  id: 7,
  clusterKey: 'email-7',
  title: 'Submit project report',
  detail: 'Requested in the weekly Gmail digest.',
  dueAt: '2026-08-12T09:30:00+07:00',
  allDay: false,
  ambiguous: false,
  status: 'proposed' as const,
  sourceCount: 1,
  signalStrength: 0.93,
  calendarEventId: null,
  createdAt: '2026-08-11T00:00:00Z',
  updatedAt: '2026-08-11T00:00:00Z',
  evidence: [
    {
      id: 1,
      messageId: 10,
      provider: 'gmail',
      evidenceQuote: 'Please submit the report by Wednesday morning.',
      deepLink: 'https://mail.google.com/mail/u/0/#inbox/abc',
    },
  ],
};

const mondaiyReminderTask = {
  ...proposedTask,
  id: 8,
  clusterKey: 'mondaiy-reminder-8',
  title: 'Prepare questions for mentor',
  detail: 'A reminder requested from mondaiy.',
  evidence: [],
  sourceCount: 0,
};

describe('TasksPage calendar workspace', () => {
  beforeEach(() => {
    vi.setSystemTime(new Date('2026-08-12T12:00:00+07:00'));
    mocks.listTasks.mockResolvedValue({ tasks: [proposedTask] });
    mocks.listCalendarEvents.mockResolvedValue({
      calendars: [{ id: 'primary', name: 'Personal' }],
      events: [
        {
          id: 'event-1',
          title: 'Mentor sync',
          startAt: '2026-08-12T08:00:00+07:00',
          endAt: '2026-08-12T09:00:00+07:00',
          allDay: false,
          status: 'confirmed',
          calendarId: 'primary',
          calendarName: 'Personal',
          deepLink: 'https://calendar.google.com/calendar/event?eid=1',
        },
        {
          id: 'all-day-1',
          title: 'Project deadline',
          startAt: '2026-08-12',
          endAt: '2026-08-13',
          allDay: true,
          status: 'confirmed',
          calendarId: 'primary',
          calendarName: 'Personal',
          deepLink: 'https://calendar.google.com/calendar/event?eid=all-day-1',
        },
      ],
    });
    mocks.confirmTask.mockResolvedValue({ ...proposedTask, status: 'confirmed' });
    mocks.completeTask.mockResolvedValue({ ...proposedTask, status: 'completed' });
    mocks.cancelTask.mockResolvedValue({ ...proposedTask, status: 'cancelled' });
    mocks.syncTaskToCalendar.mockResolvedValue({
      taskId: 7,
      calendarEventId: 'google-event-7',
      calendarUrl: 'https://calendar.google.com/calendar/event?eid=7',
      alreadySynced: false,
    });
    mocks.updateCalendarEvent.mockResolvedValue({
      event: {
        id: 'event-1', title: 'Mentor sync', startAt: '2026-08-12T10:00:00+07:00', endAt: '2026-08-12T11:00:00+07:00', allDay: false,
        status: 'confirmed', calendarId: 'primary', description: '', deepLink: null, syncedAt: '2026-08-12T00:00:00Z',
      }, operationId: 44, undoExpiresAt: new Date(Date.now() + 10_000).toISOString(),
    });
    mocks.deleteCalendarEvent.mockResolvedValue({ event: null, operationId: 45, undoExpiresAt: new Date(Date.now() + 10_000).toISOString() });
    mocks.undoCalendarOperation.mockResolvedValue({ event: {
      id: 'restored-1', title: 'Mentor sync', startAt: '2026-08-12T08:00:00+07:00', endAt: '2026-08-12T09:00:00+07:00', allDay: false,
      status: 'confirmed', calendarId: 'primary', description: '', deepLink: null, syncedAt: '2026-08-12T00:00:00Z',
    }, operationId: 45, undoExpiresAt: new Date(Date.now() + 10_000).toISOString() });
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
    vi.clearAllMocks();
  });

  it('loads the weekly calendar and lets the user confirm then sync an email todo', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);

    expect((await screen.findAllByText('Mentor sync')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Submit project report').length).toBeGreaterThan(0);
    expect(mocks.listCalendarEvents).toHaveBeenCalledWith(
      'access-token',
      expect.any(String),
      expect.any(String),
    );

    await user.click(screen.getByRole('button', { name: 'Xác nhận Submit project report' }));
    await user.click(await screen.findByRole('button', { name: 'Đồng bộ Submit project report vào lịch' }));

    await waitFor(() => {
      expect(mocks.confirmTask).toHaveBeenCalledWith(7, 'access-token');
      expect(mocks.syncTaskToCalendar).toHaveBeenCalledWith(7, 'access-token');
    });
    expect((await screen.findAllByText('Đã đồng bộ')).length).toBeGreaterThan(0);
  });

  it('keeps tasks in the priority rail instead of shrinking them into the timed event grid', async () => {
    render(<TasksPage />);

    const taskRail = await screen.findByTestId('calendar-task-rail');
    const timeGrid = screen.getByTestId('calendar-time-grid');

    expect(within(taskRail).getByText('Submit project report')).toBeTruthy();
    expect(within(timeGrid).queryByText('Submit project report')).toBeNull();
    expect(within(timeGrid).getByText('Mentor sync')).toBeTruthy();
  });

  it('shows each calendar item source, including Mondaiy reminders without evidence', async () => {
    mocks.listTasks.mockResolvedValue({ tasks: [proposedTask, mondaiyReminderTask] });
    render(<TasksPage />);

    const taskRail = await screen.findByTestId('calendar-task-rail');
    expect(within(taskRail).getByRole('img', { name: 'Gmail' })).toBeTruthy();
    expect(within(taskRail).getByRole('img', { name: 'Mondaiy reminder' })).toBeTruthy();
    expect(screen.getAllByRole('img', { name: 'Google Calendar event' }).length).toBeGreaterThanOrEqual(2);
  });

  it('shows source and description inline, then lets a confirmed task become done', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);

    expect(await screen.findByText('Requested in the weekly Gmail digest.')).toBeTruthy();
    expect(screen.getAllByRole('img', { name: 'Gmail' }).length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: 'Xác nhận Submit project report' }));
    expect((await screen.findAllByText('Đang chờ')).length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Đánh dấu Submit project report là đã làm' }));
    await user.click(screen.getByRole('button', { name: 'Bỏ qua' }));

    await waitFor(() => expect(mocks.completeTask).toHaveBeenCalledWith(7, 'access-token', undefined));
    expect((await screen.findAllByText('Đã làm')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Đánh dấu Submit project report là đã làm' })).toBeNull();
  });

  it('lets a pending task be cancelled', async () => {
    mocks.listTasks.mockResolvedValue({ tasks: [{ ...proposedTask, status: 'confirmed' }] });
    const user = userEvent.setup();
    render(<TasksPage />);

    await user.click(await screen.findByRole('button', { name: 'Huỷ Submit project report' }));
    await user.click(screen.getByRole('button', { name: 'Huỷ task' }));

    await waitFor(() => expect(mocks.cancelTask).toHaveBeenCalledWith(7, 'access-token'));
    expect((await screen.findAllByText('Đã huỷ')).length).toBeGreaterThan(0);
  });

  it('loads a new bounded range when moving to the next week', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    await screen.findAllByText('Mentor sync');
    mocks.listCalendarEvents.mockClear();

    await user.click(screen.getByRole('button', { name: 'Tuần sau' }));

    await waitFor(() => expect(mocks.listCalendarEvents).toHaveBeenCalledTimes(1));
  });

  it('marks a calendar rail task done without changing its scheduled date', async () => {
    mocks.listTasks.mockResolvedValue({ tasks: [{ ...proposedTask, status: 'confirmed' }] });
    const user = userEvent.setup();
    render(<TasksPage />);
    await user.click(await screen.findByRole('button', { name: 'Đánh dấu Submit project report là đã làm, từ dải lịch' }));
    await user.click(screen.getByRole('button', { name: 'Bỏ qua' }));
    await waitFor(() => expect(mocks.completeTask).toHaveBeenCalledWith(7, 'access-token', undefined));
    expect(mocks.updateCalendarEvent).not.toHaveBeenCalled();
  });

  it('opens an event context menu, deletes it, then exposes undo', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    const event = await screen.findByRole('button', { name: 'Sửa Mentor sync' });
    await user.pointer({ keys: '[MouseRight]', target: event });
    await user.click(screen.getByRole('menuitem', { name: 'Xoá' }));
    await waitFor(() => expect(mocks.deleteCalendarEvent).toHaveBeenCalledWith('event-1', 'primary', 'access-token'));
    await user.click(screen.getByRole('button', { name: 'Hoàn tác' }));
    await waitFor(() => expect(mocks.undoCalendarOperation).toHaveBeenCalledWith(45, 'access-token'));
  });

  it('explains a read-only calendar without opening edit or enabling drag', async () => {
    mocks.listCalendarEvents.mockResolvedValue({
      calendars: [
        { id: 'primary', name: 'Personal', writable: true },
        { id: 'holiday', name: 'Ngày lễ Việt Nam', writable: false },
      ],
      events: [{
        id: 'holiday-1',
        title: 'Quốc khánh',
        startAt: '2026-08-12T08:00:00+07:00',
        endAt: '2026-08-12T09:00:00+07:00',
        allDay: false,
        status: 'confirmed',
        calendarId: 'holiday',
        calendarName: 'Ngày lễ Việt Nam',
        deepLink: 'https://calendar.google.com/calendar/event?eid=holiday-1',
      }],
    });
    const user = userEvent.setup();
    render(<TasksPage />);

    const event = await screen.findByRole('button', { name: 'Thao tác cho Quốc khánh' });
    expect((event as HTMLButtonElement).draggable).toBe(false);
    await user.click(event);

    expect(screen.getByText(/Lịch này chỉ đọc/)).toBeTruthy();
    expect(screen.queryByRole('menuitem', { name: 'Sửa' })).toBeNull();
    expect(screen.queryByRole('menuitem', { name: 'Xoá' })).toBeNull();
    expect(screen.queryByRole('dialog', { name: 'Sửa sự kiện' })).toBeNull();
  });

  it('only offers writable calendars as an event destination', async () => {
    mocks.listCalendarEvents.mockResolvedValue({
      calendars: [
        { id: 'primary', name: 'Personal', writable: true },
        { id: 'holiday', name: 'Ngày lễ Việt Nam', writable: false },
      ],
      events: [{
        id: 'all-day-1',
        title: 'Project deadline',
        startAt: '2026-08-12',
        endAt: '2026-08-13',
        allDay: true,
        status: 'confirmed',
        calendarId: 'primary',
        calendarName: 'Personal',
        deepLink: 'https://calendar.google.com/calendar/event?eid=all-day-1',
      }],
    });
    const user = userEvent.setup();
    render(<TasksPage />);

    await user.click(await screen.findByRole('button', { name: 'Sửa Project deadline' }));
    const destination = screen.getByRole('combobox', { name: 'Lịch' });
    expect(within(destination).getAllByRole('option').map((option) => option.textContent)).toEqual(['Personal']);
  });

  it('drags an event to another day and opens a confirm dialog instead of writing immediately', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    await screen.findByRole('button', { name: 'Sửa Mentor sync' });
    const target = screen.getByTestId('calendar-day-2026-08-13');
    const transfer = { getData: vi.fn(() => 'event-1'), setData: vi.fn() };
    Object.defineProperty(target, 'getBoundingClientRect', { value: () => ({ top: 0 }) });
    const drop = new MouseEvent('drop', { bubbles: true, clientY: 224 });
    Object.defineProperty(drop, 'dataTransfer', { value: transfer });
    target.dispatchEvent(drop);

    // Thả tay ra chỉ mở dialog xác nhận, chưa ghi gì lên Google Calendar.
    await screen.findByText('Xác nhận thời gian mới');
    expect(mocks.updateCalendarEvent).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() => expect(mocks.updateCalendarEvent).toHaveBeenCalledWith('event-1', expect.objectContaining({
      calendarId: 'primary', startAt: expect.any(String), endAt: expect.any(String), allDay: false,
    }), 'access-token'));
    const [, request] = mocks.updateCalendarEvent.mock.calls[0];
    expect(new Date(request.endAt).getTime() - new Date(request.startAt).getTime()).toBe(60 * 60 * 1000);
  });

  it('lets an all-day event open its edit actions and preserves an explicit Google Calendar link', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    const allDay = await screen.findByRole('button', { name: 'Sửa Project deadline' });
    await user.pointer({ keys: '[MouseRight]', target: allDay });
    expect(screen.getByRole('menuitem', { name: 'Xoá' })).toBeTruthy();
    await user.click(screen.getByRole('menuitem', { name: 'Sửa' }));
    expect(screen.getByRole('button', { name: 'Mở trong Google Calendar' })).toBeTruthy();
  });

  it('saves an all-day edit as an all-day PATCH with its local start and end dates', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    await user.click(await screen.findByRole('button', { name: 'Sửa Project deadline' }));
    await user.click(screen.getByRole('button', { name: 'Lưu' }));
    await waitFor(() => expect(mocks.updateCalendarEvent).toHaveBeenCalledWith('all-day-1', expect.objectContaining({ allDay: true }), 'access-token'));
    const [, request] = mocks.updateCalendarEvent.mock.calls[0];
    expect(request.startAt).toMatch(/^2026-08-12T00:00:00[+-]\d{2}:\d{2}$/);
    expect(request.endAt).toMatch(/^2026-08-13T00:00:00[+-]\d{2}:\d{2}$/);
  });

  it('filters the inbox list through the compact dropdown instead of a row of buttons', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    await screen.findAllByText('Submit project report');

    const filterSelect = screen.getByRole('combobox', { name: 'Hộp việc cần làm' });
    expect(screen.queryByRole('button', { name: 'Đang chờ' })).toBeNull();

    await user.selectOptions(filterSelect, 'Đang chờ');

    const inboxList = document.querySelector('[data-tour-id="tasks-inbox-list"]') as HTMLElement;
    expect(within(inboxList).queryByText('Submit project report')).toBeNull();
    expect(within(inboxList).getByText('Không có việc nào cho bộ lọc này.')).toBeTruthy();
  });

  it('hiện priority và phiếu giao việc nhưng không bịa dữ liệu rỗng', async () => {
    const richTask = {
      ...proposedTask,
      statedPriority: 'high',
      expectedOutput: 'Báo cáo PDF đã gửi cho mentor',
      acceptanceCriteria: 'Mentor xác nhận đã nhận',
      constraints: 'Không dùng dữ liệu production',
      executionTool: 'Google Docs',
      contextInput: 'Brief tuần này',
      executionMethod: 'Đọc brief rồi gửi bản nháp',
      assignee: 'An',
      stakeholders: ['Thái', 'Mentor'],
      deliverTo: 'Nhóm mentor',
      estimateLowMin: 30,
      estimateHighMin: 45,
    };
    const blankTask = {
      ...mondaiyReminderTask,
      statedPriority: null,
      expectedOutput: null,
      acceptanceCriteria: '   ',
      constraints: null,
      executionTool: '',
      contextInput: null,
      executionMethod: null,
      assignee: null,
      stakeholders: [],
      deliverTo: '   ',
      estimateLowMin: null,
      estimateHighMin: null,
    };
    mocks.listTasks.mockResolvedValue({ tasks: [richTask, blankTask] });

    render(<TasksPage />);

    await screen.findByText('Báo cáo PDF đã gửi cho mentor');
    const richCard = document.getElementById('task-inbox-7') as HTMLElement;
    const blankCard = document.getElementById('task-inbox-8') as HTMLElement;
    expect(within(richCard).getByText('Ưu tiên: Cao')).not.toBeNull();
    // Ba trường này đã có sẵn trong DB và API từ lâu nhưng chưa từng hiện ra
    // giao diện — "xong thì gửi cho ai" là thứ Thái hỏi đích danh trong bảng QA.
    expect(within(richCard).getByText('An')).not.toBeNull();
    expect(within(richCard).getByText('Nhóm mentor')).not.toBeNull();
    expect(within(richCard).getByText('30–45 min')).not.toBeNull();
    // Trống thì KHÔNG dựng hàng, tránh biến task sơ sài thành biểu mẫu đầy ô rỗng.
    expect(within(blankCard).queryByText('Xong thì gửi cho')).toBeNull();
    expect(within(blankCard).queryByText('Ước lượng')).toBeNull();
    expect(within(blankCard).queryByText('Người phụ trách')).toBeNull();
    expect(within(richCard).getByText('Báo cáo PDF đã gửi cho mentor')).not.toBeNull();
    expect(within(richCard).getByText('Mentor xác nhận đã nhận')).not.toBeNull();
    expect(within(richCard).getByText('Không dùng dữ liệu production')).not.toBeNull();
    expect(within(richCard).getByText('Google Docs')).not.toBeNull();
    expect(within(richCard).getByText('Brief tuần này')).not.toBeNull();
    expect(within(richCard).getByText('Đọc brief rồi gửi bản nháp')).not.toBeNull();
    expect(within(richCard).getByText('An')).not.toBeNull();
    expect(within(richCard).getByText('Thái, Mentor')).not.toBeNull();
    expect(within(richCard).getByText('Nhóm mentor')).not.toBeNull();
    expect(within(richCard).getByText('30–45 min')).not.toBeNull();
    expect(within(blankCard).queryByText(/Ưu tiên:/)).toBeNull();
    expect(within(blankCard).queryByText('Kết quả mong đợi')).toBeNull();
    expect(within(blankCard).queryByText('Tiêu chí nghiệm thu')).toBeNull();
    expect(within(blankCard).queryByText('Ràng buộc')).toBeNull();
    expect(within(blankCard).queryByText('Công cụ thực hiện')).toBeNull();
    expect(within(blankCard).queryByText('Bên liên quan')).toBeNull();
  });

  it('sửa task từ UI và cập nhật card ngay sau khi lưu', async () => {
    const user = userEvent.setup();
    mocks.updateTask.mockResolvedValue({
      ...proposedTask,
      title: 'Báo cáo đã chỉnh',
      detail: 'Mô tả mới',
    });
    render(<TasksPage />);

    await user.click(await screen.findByRole('button', { name: 'Sửa Submit project report' }));
    await user.clear(screen.getByRole('textbox', { name: 'Tiêu đề' }));
    await user.type(screen.getByRole('textbox', { name: 'Tiêu đề' }), 'Báo cáo đã chỉnh');
    await user.clear(screen.getByRole('textbox', { name: 'Mô tả chi tiết' }));
    await user.type(screen.getByRole('textbox', { name: 'Mô tả chi tiết' }), 'Mô tả mới');
    await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));

    await waitFor(() => expect(mocks.updateTask).toHaveBeenCalledWith(
      7,
      { title: 'Báo cáo đã chỉnh', detail: 'Mô tả mới' },
      'access-token',
    ));
    expect((await screen.findAllByText('Báo cáo đã chỉnh')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Submit project report')).toBeNull();
  });

  it('ưu tiên việc hôm nay, ngày mai và đẩy việc stale hoặc đã đóng xuống dưới', async () => {
    mocks.listTasks.mockResolvedValue({ tasks: [
      { ...proposedTask, id: 21, title: 'Không có deadline', dueAt: null, statedPriority: 'medium' },
      { ...proposedTask, id: 22, title: 'Ngày mai ưu tiên cao', dueAt: '2026-08-13T09:00:00+07:00', statedPriority: 'high' },
      { ...proposedTask, id: 23, title: 'Hôm nay ưu tiên thấp', dueAt: '2026-08-12T17:00:00+07:00', statedPriority: 'low' },
      { ...proposedTask, id: 24, title: 'Hôm nay ưu tiên cao', dueAt: '2026-08-12T18:00:00+07:00', statedPriority: 'urgent' },
      { ...proposedTask, id: 25, title: 'Tương lai ưu tiên cao', dueAt: '2026-08-20T09:00:00+07:00', statedPriority: 'high' },
      { ...proposedTask, id: 26, title: 'Stale ưu tiên cao', dueAt: '2026-08-10T09:00:00+07:00', statedPriority: 'urgent' },
      { ...proposedTask, id: 27, title: 'Đã huỷ hôm nay', dueAt: '2026-08-12T08:00:00+07:00', status: 'cancelled', statedPriority: 'urgent' },
      { ...proposedTask, id: 28, title: 'Deadline lỗi', dueAt: 'not-a-date', statedPriority: null },
    ] });

    render(<TasksPage />);

    const inboxList = document.querySelector('[data-tour-id="tasks-inbox-list"]') as HTMLElement;
    await waitFor(() => expect(within(inboxList).getByText('Hôm nay ưu tiên cao')).not.toBeNull());
    const orderedTitles = [...inboxList.querySelectorAll('article[id^="task-inbox-"] h3')]
      .map((heading) => heading.textContent);
    expect(orderedTitles).toEqual([
      'Hôm nay ưu tiên cao',
      'Hôm nay ưu tiên thấp',
      'Ngày mai ưu tiên cao',
      'Tương lai ưu tiên cao',
      'Không có deadline',
      'Deadline lỗi',
      'Stale ưu tiên cao',
      'Đã huỷ hôm nay',
    ]);
  });

  it('làm mới riêng hộp việc và sắp lại dữ liệu vừa tải', async () => {
    const staleTask = {
      ...proposedTask,
      id: 51,
      title: 'Việc cũ',
      dueAt: '2026-08-01T09:00:00+07:00',
      statedPriority: 'low',
    };
    const todayTask = {
      ...proposedTask,
      id: 52,
      title: 'Việc mới hôm nay',
      dueAt: '2026-08-12T16:00:00+07:00',
      statedPriority: 'high',
    };
    mocks.listTasks
      .mockResolvedValueOnce({ tasks: [staleTask] })
      .mockResolvedValueOnce({ tasks: [staleTask, todayTask] });
    const user = userEvent.setup();
    render(<TasksPage />);

    await screen.findByText('Việc cũ');
    await user.click(screen.getByRole('button', { name: 'Làm mới hộp việc' }));

    await waitFor(() => expect(mocks.listTasks).toHaveBeenCalledTimes(2));
    const inboxList = document.querySelector('[data-tour-id="tasks-inbox-list"]') as HTMLElement;
    const orderedTitles = [...inboxList.querySelectorAll('article[id^="task-inbox-"] h3')]
      .map((heading) => heading.textContent);
    expect(orderedTitles).toEqual(['Việc mới hôm nay', 'Việc cũ']);
    expect(mocks.listCalendarEvents).toHaveBeenCalledTimes(1);
  });

  it('lọc priority độc lập và kết hợp đúng với trạng thái', async () => {
    mocks.listTasks.mockResolvedValue({ tasks: [
      { ...proposedTask, id: 31, title: 'High cần xem', statedPriority: 'high' },
      { ...proposedTask, id: 32, title: 'Low cần xem', statedPriority: 'low' },
      { ...proposedTask, id: 33, title: 'Urgent đã xác nhận', status: 'confirmed', statedPriority: 'urgent' },
      { ...proposedTask, id: 34, title: 'Không priority', statedPriority: null },
    ] });
    const user = userEvent.setup();
    render(<TasksPage />);

    const prioritySelect = await screen.findByRole('combobox', { name: 'Lọc theo ưu tiên' });
    const statusSelect = screen.getByRole('combobox', { name: 'Hộp việc cần làm' });
    await user.selectOptions(prioritySelect, 'Cao');
    const inboxList = document.querySelector('[data-tour-id="tasks-inbox-list"]') as HTMLElement;
    expect(within(inboxList).getByText('High cần xem')).not.toBeNull();
    expect(within(inboxList).getByText('Urgent đã xác nhận')).not.toBeNull();
    expect(within(inboxList).queryByText('Low cần xem')).toBeNull();
    expect(within(inboxList).queryByText('Không priority')).toBeNull();

    await user.selectOptions(statusSelect, 'Đang chờ');
    expect(within(inboxList).queryByText('High cần xem')).toBeNull();
    expect(within(inboxList).getByText('Urgent đã xác nhận')).not.toBeNull();

    await user.selectOptions(statusSelect, 'Đã đóng');
    expect(within(inboxList).getByText('Không có việc nào cho bộ lọc này.')).not.toBeNull();
    expect(screen.queryByTestId('tasks-global-empty-state')).toBeNull();
  });

  it('thống kê từ toàn bộ task và cập nhật ngay sau chuyển trạng thái', async () => {
    const confirmedHigh = { ...proposedTask, id: 41, title: 'High đang xử lý', status: 'confirmed' as const, statedPriority: 'high' };
    mocks.listTasks.mockResolvedValue({ tasks: [
      { ...proposedTask, id: 40, title: 'Đã xong', status: 'completed', statedPriority: 'high', completedAt: '2026-08-12T01:00:00Z' },
      confirmedHigh,
      { ...proposedTask, id: 42, title: 'P1 cần xem', statedPriority: 'p1' },
      { ...proposedTask, id: 43, title: 'High đã bỏ qua', status: 'dismissed', statedPriority: 'high' },
      { ...proposedTask, id: 44, title: 'High đã huỷ', status: 'cancelled', statedPriority: 'high' },
      { ...proposedTask, id: 45, title: 'Low đang xử lý', status: 'confirmed', statedPriority: 'low' },
    ] });
    mocks.completeTask.mockResolvedValue({ ...confirmedHigh, status: 'completed', completedAt: '2026-08-12T05:00:00Z' });
    const user = userEvent.setup();
    render(<TasksPage />);

    expect(within(await screen.findByLabelText('đã làm')).getByText('1')).not.toBeNull();
    expect(within(screen.getByLabelText('đang xử lý')).getByText('2')).not.toBeNull();
    expect(within(screen.getByLabelText('ưu tiên cao cần xử lý')).getByText('2')).not.toBeNull();

    await user.click(screen.getByRole('button', { name: 'Đánh dấu High đang xử lý là đã làm' }));
    await user.click(screen.getByRole('button', { name: 'Bỏ qua' }));

    await waitFor(() => expect(within(screen.getByLabelText('đã làm')).getByText('2')).not.toBeNull());
    expect(within(screen.getByLabelText('đang xử lý')).getByText('1')).not.toBeNull();
    expect(within(screen.getByLabelText('ưu tiên cao cần xử lý')).getByText('1')).not.toBeNull();
  });

  it('chỉ hiện hướng dẫn tạo việc khi danh sách thật sự rỗng', async () => {
    mocks.listTasks.mockResolvedValue({ tasks: [] });
    const user = userEvent.setup();
    render(<TasksPage />);

    expect(await screen.findByText('Bắt đầu lên kế hoạch cho hôm nay')).not.toBeNull();
    expect(screen.getByText(/kết nối nguồn để công việc mới tự xuất hiện/i)).not.toBeNull();
    await user.click(screen.getByRole('button', { name: 'Lên kế hoạch trong chat' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/briefing', {
      state: { chatPrompt: 'lên kế hoạch trong ngày cho tôi' },
    });
    await user.click(screen.getByRole('button', { name: 'Kết nối nguồn' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/sources');
  });

  it('collapses the timeline height while retaining every hourly time slot', async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    await screen.findByRole('button', { name: 'Sửa Mentor sync' });
    const day = screen.getByTestId('calendar-day-2026-08-12');
    expect((day as HTMLElement).style.height).toBe('1008px');
    await user.click(screen.getByRole('button', { name: 'Thu gọn lịch' }));
    expect((day as HTMLElement).style.height).toBe('576px');
    expect(screen.getByRole('button', { name: 'Hiện đủ khung giờ' }).getAttribute('aria-pressed')).toBe('true');
  });
});
