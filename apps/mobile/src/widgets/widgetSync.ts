import Constants from 'expo-constants';
import { getTasks, listCalendarEvents, type CalendarEvent, type Task } from '../api/client';
import type { LockScreenWidgetData } from './MondaiyLockScreenWidget';

const isOpenTask = (task: Task) => !['completed', 'dismissed', 'cancelled'].includes(task.status);

const formatTime = (date: string) => new Date(date).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

const formatTaskDetail = (task: Task) => {
  if (task.dueAt) return `Hạn ${new Date(task.dueAt).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`;
  return (task.detail || '').slice(0, 52);
};

const mondayFor = (date: Date) => {
  const monday = new Date(date);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  return monday;
};

export const buildWidgetSnapshot = (tasks: Task[], events: CalendarEvent[], now = new Date()): Partial<LockScreenWidgetData> => {
  const weekStart = mondayFor(now);
  const activeTasks = tasks.filter(isOpenTask);
  const todayEvents = events
    .filter((event) => new Date(event.startAt).toDateString() === now.toDateString())
    .sort((left, right) => left.startAt.localeCompare(right.startAt));
  const next = events
    .filter((event) => new Date(event.endAt || event.startAt).getTime() >= now.getTime())
    .sort((left, right) => left.startAt.localeCompare(right.startAt))[0];

  return {
    openTasks: activeTasks.length,
    tasks: activeTasks.slice(0, 5).map((task) => ({
      title: task.title,
      detail: formatTaskDetail(task),
      suggested: task.status === 'proposed',
    })),
    week: Array.from({ length: 7 }, (_, index) => {
      const day = new Date(weekStart);
      day.setDate(weekStart.getDate() + index);
      return {
        label: index === 6 ? 'CN' : `T${index + 2}`,
        date: String(day.getDate()),
        count: events.filter((event) => new Date(event.startAt).toDateString() === day.toDateString()).length,
        isToday: day.toDateString() === now.toDateString(),
      };
    }),
    schedule: todayEvents.slice(0, 3).map((event) => ({
      time: event.allDay ? 'Cả ngày' : formatTime(event.startAt),
      title: event.title,
    })),
    nextTitle: next?.title || 'Chưa có lịch sắp tới',
    nextTime: next ? (next.allDay ? 'Cả ngày' : formatTime(next.startAt)) : '—',
    updatedAt: now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
  };
};

export const syncLockScreenWidget = async (data: Partial<LockScreenWidgetData>): Promise<boolean> => {
  if (Constants.executionEnvironment === 'storeClient') return false;
  try {
    const { updateLockScreenWidget } = await import('./MondaiyLockScreenWidget');
    updateLockScreenWidget(data);
    return true;
  } catch {
    // WidgetKit chỉ có trong development hoặc production build có extension.
    return false;
  }
};

export const clearWidgetSnapshot = async (): Promise<void> => {
  if (Constants.executionEnvironment === 'storeClient') return;
  try {
    const { clearLockScreenWidget } = await import('./MondaiyLockScreenWidget');
    clearLockScreenWidget();
  } catch {
    // WidgetKit chỉ có trong development hoặc production build có extension.
  }
};

export const syncWidgetFromApi = async (token: string): Promise<boolean> => {
  const now = new Date();
  const from = mondayFor(now);
  const to = new Date(from);
  to.setDate(to.getDate() + 7);
  const [tasks, calendar] = await Promise.all([
    getTasks(token),
    listCalendarEvents(from.toISOString(), to.toISOString(), token),
  ]);
  return syncLockScreenWidget(buildWidgetSnapshot(tasks, calendar.events, now));
};
