import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Inbox,
  Link2,
  Paperclip,
  RefreshCw,
  Sparkles,
  X,
  RotateCcw,} from 'lucide-react';

import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useAppStore } from '../stores/useAppStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useTranslation } from '../i18n/useTranslation';
import {
  buildTaskBreakdown,
  confirmTask,
  completeTask,
  cancelTask,
  restoreTask,
  dismissTask,
  listCalendarEvents,
  listTasks,
  syncTaskToCalendar,
  updateTask,
  type CalendarInfo,
  type CalendarEvent,
  type Task,
  type TaskBreakdown,
} from '../lib/tasksApi';
import { trashLabel, trashState } from '../lib/taskTrash';
import { ScheduleConflictPanel } from '../components/calendar/ScheduleConflictPanel';
import { TaskBreakdownPanel } from '../components/tasks/TaskBreakdownPanel';
import { createConnectIntent } from '../lib/connectionsApi';
import { ApiError } from '../lib/apiClient';
import { recordMeaningfulAction } from '../hooks/useProductRating';
import { recordTaskDecision, useTaskDismissalNudge } from '../hooks/useTaskDismissalNudge';
import { GoogleCalendarIcon, resolveBrandIcon } from '../components/ui/BrandIcons';
import { Dialog } from '../components/ui/Dialog';
import {
  createCalendarEvent,
  deleteCalendarEvent,
  undoCalendarOperation,
  updateCalendarEvent,
} from '../lib/calendarApi';
import { createChatHandoff } from '../lib/chatHandoff';

type FilterId = 'all' | 'proposed' | 'confirmed' | 'completed' | 'closed' | 'trash';
type PriorityBand = 'high' | 'medium' | 'low' | 'other' | 'absent';

const ALL_PRIORITIES = '__all_priorities__';
const HIGH_PRIORITIES = new Set(['high', 'urgent', 'p1']);
const MEDIUM_PRIORITIES = new Set(['medium', 'normal', 'p2']);
const LOW_PRIORITIES = new Set(['low', 'p3']);

function normalizeStatedPriority(value: string | null | undefined): string | null {
  const normalized = value?.trim().toLocaleLowerCase('en-US');
  return normalized || null;
}

function priorityBandOf(value: string | null | undefined): PriorityBand {
  const normalized = normalizeStatedPriority(value);
  if (normalized === null) return 'absent';
  if (HIGH_PRIORITIES.has(normalized)) return 'high';
  if (MEDIUM_PRIORITIES.has(normalized)) return 'medium';
  if (LOW_PRIORITIES.has(normalized)) return 'low';
  return 'other';
}

function prioritySortRank(value: string | null | undefined): number {
  return { high: 0, medium: 1, low: 2, other: 3, absent: 4 }[priorityBandOf(value)];
}

function priorityFilterKey(value: string | null | undefined): string | null {
  const normalized = normalizeStatedPriority(value);
  if (normalized === null) return null;
  const band = priorityBandOf(normalized);
  return band === 'other' ? `other:${normalized}` : `band:${band}`;
}

function inboxActionabilityRank(task: Task, today: Date): number {
  if (task.status === 'dismissed' || task.status === 'cancelled') return 4;
  const due = taskDate(task);
  if (!due) return 2;
  const dueDay = startOfDay(due).getTime();
  const todayStart = startOfDay(today);
  if (dueDay === todayStart.getTime()) return 0;
  if (dueDay === addDays(todayStart, 1).getTime()) return 1;
  return dueDay < todayStart.getTime() ? 3 : 2;
}

function compareInboxTasks(left: Task, right: Task, today: Date): number {
  // Hộp việc là hàng đợi hành động: hôm nay rồi ngày mai; việc stale và đã
  // đóng nằm dưới. Priority chỉ phân hạng các việc trong cùng một nhóm ngày.
  const actionabilityDifference = inboxActionabilityRank(left, today) - inboxActionabilityRank(right, today);
  if (actionabilityDifference !== 0) return actionabilityDifference;
  const priorityDifference = prioritySortRank(left.statedPriority) - prioritySortRank(right.statedPriority);
  if (priorityDifference !== 0) return priorityDifference;
  const leftDue = taskDate(left)?.getTime() ?? null;
  const rightDue = taskDate(right)?.getTime() ?? null;
  if (leftDue !== null && rightDue !== null && leftDue !== rightDue) return leftDue - rightDue;
  if (leftDue === null && rightDue !== null) return 1;
  if (leftDue !== null && rightDue === null) return -1;
  if (left.signalStrength !== right.signalStrength) return right.signalStrength - left.signalStrength;
  return left.id - right.id;
}

function isOpenTask(task: Task): boolean {
  return task.status === 'proposed' || task.status === 'confirmed';
}

function nonBlank(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized || null;
}

function nonBlankList(values: string[] | null | undefined): string | null {
  const normalized = values?.map((value) => value.trim()).filter(Boolean) ?? [];
  return normalized.length > 0 ? normalized.join(', ') : null;
}

const GRID_START_HOUR = 6;
const GRID_END_HOUR = 24;
const HOUR_HEIGHT = 56;
const HOUR_MARKS = Array.from(
  { length: GRID_END_HOUR - GRID_START_HOUR + 1 },
  (_, index) => GRID_START_HOUR + index,
);

// Kéo co dãn cột Hộp việc — cùng cơ chế với Sidebar (drag handle, clamp
// min-max, lưu localStorage), chỉ là kéo trục ngang bên phải thay vì trái.
const INBOX_WIDTH = { min: 280, default: 340, max: 560 } as const;
const INBOX_WIDTH_KEY = 'mondaiy.tasksInboxWidth';

function clampInboxWidth(width: number): number {
  return Math.min(INBOX_WIDTH.max, Math.max(INBOX_WIDTH.min, Math.round(width)));
}

function readStoredInboxWidth(): number {
  try {
    const raw = localStorage.getItem(INBOX_WIDTH_KEY);
    if (!raw) return INBOX_WIDTH.default;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return INBOX_WIDTH.default;
    return clampInboxWidth(parsed);
  } catch {
    return INBOX_WIDTH.default;
  }
}

function startOfWeek(value: Date): Date {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  const day = date.getDay();
  date.setDate(date.getDate() + (day === 0 ? -6 : 1 - day));
  return date;
}

function addDays(value: Date, amount: number): Date {
  const date = new Date(value);
  date.setDate(date.getDate() + amount);
  return date;
}

function startOfDay(value: Date): Date {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
}

function addMonths(value: Date, amount: number): Date {
  const date = new Date(value);
  date.setDate(1);
  date.setMonth(date.getMonth() + amount);
  return date;
}

/** Lưới tháng luôn đủ tuần trọn (Thứ 2 → Chủ nhật), không cắt ngang tuần đầu/cuối. */
function monthGridWeeks(value: Date): Date[][] {
  const monthStart = new Date(value.getFullYear(), value.getMonth(), 1);
  const monthEnd = new Date(value.getFullYear(), value.getMonth() + 1, 0);
  const gridStart = startOfWeek(monthStart);
  const gridEnd = addDays(startOfWeek(monthEnd), 7);
  const totalDays = Math.round((gridEnd.getTime() - gridStart.getTime()) / 86_400_000);
  const days = Array.from({ length: totalDays }, (_, index) => addDays(gridStart, index));
  const weeks: Date[][] = [];
  for (let index = 0; index < days.length; index += 7) weeks.push(days.slice(index, index + 7));
  return weeks;
}

function localDateKey(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function eventDate(value: string, allDay: boolean): Date {
  return allDay && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value);
}

function minutesFromMidnight(value: Date): number {
  return value.getHours() * 60 + value.getMinutes();
}

function normalizedSource(provider: string): { key: string; label: string } {
  const normalized = provider.trim().toLowerCase();
  if (normalized === 'google' || normalized.includes('gmail') || normalized === 'email') {
    return { key: 'gmail', label: 'Gmail' };
  }
  if (normalized.includes('discord')) return { key: 'discord', label: 'Discord' };
  if (normalized.includes('calendar')) return { key: 'google calendar', label: 'Google Calendar' };
  if (normalized.includes('jira')) return { key: 'jira', label: 'Jira' };
  if (normalized.includes('outlook')) return { key: 'outlook', label: 'Outlook' };
  if (normalized.includes('vlearn') || normalized.includes('lms')) {
    return { key: 'vlearn', label: 'VLearn' };
  }
  return { key: normalized || 'mondaiy', label: provider.trim() || 'Mondaiy' };
}

function taskSources(task: Task): Array<{ key: string; label: string; deepLink?: string }> {
  const sources = new Map<string, { key: string; label: string; deepLink?: string }>();
  task.evidence.forEach((evidence) => {
    const source = normalizedSource(evidence.provider);
    if (!sources.has(source.key)) sources.set(source.key, { ...source, deepLink: evidence.deepLink });
  });
  return sources.size > 0 ? [...sources.values()] : [{ key: 'mondaiy', label: 'Mondaiy' }];
}

function taskDate(task: Task): Date | null {
  if (!task.dueAt) return null;
  const parsed = new Date(task.dueAt);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

type TimedItemBase = {
  key: string;
  title: string;
  start: Date;
  end: Date;
  startMinute: number;
  endMinute: number;
  kind: 'event';
  event: CalendarEvent;
};

type TimedItem = TimedItemBase & { lane: number; lanes: number };

type EventDraft = {
  event?: CalendarEvent;
  calendarId: string;
  title: string;
  startAt: string;
  endAt: string;
  allDay: boolean;
};

type CompletionPrompt = {
  task: Task;
  customMinutes: string;
  showCustomInput: boolean;
};

type CalendarViewMode = 'day' | 'week' | 'month';

/** Bản nháp kéo-thả chờ xác nhận — chưa ghi gì lên Google Calendar / task cho
 * tới khi người dùng bấm Xác nhận trong dialog. `toStart`/`toEnd` là null cho
 * kiểu 'task' khi kéo ở lưới tháng (chỉ đổi NGÀY, không có khung giờ). */
type RescheduleDraft =
  | { kind: 'event'; event: CalendarEvent; fromStart: Date; fromEnd: Date; toStart: Date; toEnd: Date }
  | { kind: 'task'; task: Task; fromDue: Date; toDue: Date };

function toDateTimeLocal(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

/** Giữ nguyên ngày theo lịch địa phương khi backend sẽ chuyển nó thành all-day date. */
function toOffsetIso(value: string): string {
  const date = new Date(value);
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absolute = Math.abs(offsetMinutes);
  const offset = `${sign}${String(Math.floor(absolute / 60)).padStart(2, '0')}:${String(absolute % 60).padStart(2, '0')}`;
  return `${toDateTimeLocal(date)}:00${offset}`;
}

export const TasksPage: React.FC = () => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const { addToast } = useAppStore();
  const accessToken = useAuthStore((state) => state.accessToken);
  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';
  useTaskDismissalNudge();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [calendars, setCalendars] = useState<CalendarInfo[]>([]);
  // Lịch chưa biết thì coi như ghi được: thà để backend trả 409 kèm lời giải
  // thích còn hơn chặn nhầm lịch chính của người dùng khi danh sách chưa về.
  const isCalendarWritable = (calendarId: string) =>
    calendars.find((calendar) => calendar.id === calendarId)?.writable !== false;
  // Ô "tạo sự kiện vào lịch nào" chỉ nên liệt kê lịch ghi được.
  const writableCalendars = calendars.filter((calendar) => calendar.writable !== false);
  const [view, setView] = useState<CalendarViewMode>('week');
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [statusFilter, setStatusFilter] = useState<FilterId>('all');
  const [priorityFilter, setPriorityFilter] = useState(ALL_PRIORITIES);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [calendarLoading, setCalendarLoading] = useState(true);
  const [calendarSyncVersion, setCalendarSyncVersion] = useState(0);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [eventDraft, setEventDraft] = useState<EventDraft | null>(null);
  const [completionPrompt, setCompletionPrompt] = useState<CompletionPrompt | null>(null);
  const [cancellationPrompt, setCancellationPrompt] = useState<Task | null>(null);
  const [dueDraft, setDueDraft] = useState<{ task: Task; value: string; allDay: boolean } | null>(null);
  const [taskDraft, setTaskDraft] = useState<{ task: Task; title: string; detail: string } | null>(null);
  const [savingTask, setSavingTask] = useState(false);
  const [savingDue, setSavingDue] = useState(false);
  const [contextEvent, setContextEvent] = useState<CalendarEvent | null>(null);
  const [writingEvent, setWritingEvent] = useState(false);
  const [undoOperation, setUndoOperation] = useState<{ id: number; expiresAt: number } | null>(null);
  const [rescheduleDraft, setRescheduleDraft] = useState<RescheduleDraft | null>(null);
  const [savingReschedule, setSavingReschedule] = useState(false);
  const [compactTimeline, setCompactTimeline] = useState(false);
  const [inboxWidth, setInboxWidth] = useState(readStoredInboxWidth);
  const [isResizingInbox, setIsResizingInbox] = useState(false);
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [breakdown, setBreakdown] = useState<TaskBreakdown | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(false);
  const [breakdownError, setBreakdownError] = useState<string | null>(null);
  const inboxColumnRef = useRef<HTMLDivElement>(null);

  const weekStart = useMemo(() => startOfWeek(focusDate), [focusDate]);
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart],
  );
  const weekEnd = useMemo(() => addDays(weekStart, 7), [weekStart]);
  const dayStart = useMemo(() => startOfDay(focusDate), [focusDate]);
  const dayEnd = useMemo(() => addDays(dayStart, 1), [dayStart]);
  const monthWeeks = useMemo(() => monthGridWeeks(focusDate), [focusDate]);
  const monthStart = monthWeeks[0][0];
  const monthEnd = useMemo(() => addDays(monthWeeks[monthWeeks.length - 1][6], 1), [monthWeeks]);
  // Cửa sổ dữ liệu thật sự cần tải, theo đúng view đang chọn — lưới tháng tối
  // đa 6 tuần (42 ngày), vừa khít trần _MAX_CALENDAR_WINDOW của backend. Bọc
  // useMemo vì loadCalendar (useCallback) phụ thuộc identity của hai mốc này —
  // không nhớ lại thì mỗi render sinh Date mới, useEffect tải lịch chạy vô hạn.
  const rangeStart = useMemo(
    () => (view === 'day' ? dayStart : view === 'month' ? monthStart : weekStart),
    [view, dayStart, monthStart, weekStart],
  );
  const rangeEnd = useMemo(
    () => (view === 'day' ? dayEnd : view === 'month' ? monthEnd : weekEnd),
    [view, dayEnd, monthEnd, weekEnd],
  );
  const viewDays = view === 'day' ? [dayStart] : view === 'month' ? monthWeeks.flat() : weekDays;
  const hourHeight = compactTimeline ? 32 : HOUR_HEIGHT;
  const gridHeight = (GRID_END_HOUR - GRID_START_HOUR) * hourHeight;

  const loadTasks = useCallback(async () => {
    if (!accessToken) {
      setTasksLoading(false);
      return;
    }
    setTasksLoading(true);
    setTasksError(null);
    try {
      const result = await listTasks(accessToken);
      setTasks(result.tasks);
    } catch (error) {
      setTasksError(error instanceof ApiError ? error.message : t.tasksPage.loadError);
    } finally {
      setTasksLoading(false);
    }
  }, [accessToken, t.tasksPage.loadError]);

  const loadCalendar = useCallback(async () => {
    if (!accessToken) {
      setCalendarLoading(false);
      return;
    }
    setCalendarLoading(true);
    setCalendarError(null);
    try {
      const result = await listCalendarEvents(
        accessToken,
        rangeStart.toISOString(),
        rangeEnd.toISOString(),
      );
      setEvents(result.events);
      // Phản hồi đọc từ đệm không kèm danh sách lịch. Ghi đè bằng mảng rỗng là
      // quên mất lịch nào chỉ đọc, và nút Xoá lại hiện trên lịch ngày lễ.
      if (result.calendars.length > 0) {
        setCalendars(result.calendars);
      }
    } catch (error) {
      setEvents([]);
      setCalendars([]);
      // Luôn hiện thông báo thân thiện — error.message của ApiError là chuỗi
      // kỹ thuật từ backend (vd "Google Calendar API lỗi 403 tại
      // /users/me/calendarList"), không phải thứ nên đưa thẳng lên UI.
      void error;
      setCalendarError(t.tasksPage.calendarLoadError);
    } finally {
      setCalendarLoading(false);
      // ScheduleConflictPanel đọc cùng cache với request này. Đánh thức nó
      // sau mỗi lần tải xong để không mất conflict vì race lúc mount/đổi tuần.
      setCalendarSyncVersion((version) => version + 1);
    }
  }, [accessToken, t.tasksPage.calendarLoadError, rangeEnd, rangeStart]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  const runBreakdown = useCallback(async () => {
    if (!accessToken) return;
    setBreakdownOpen(true);
    setBreakdownLoading(true);
    setBreakdownError(null);
    try {
      const result = await buildTaskBreakdown(accessToken);
      setBreakdown(result);
    } catch (error) {
      setBreakdown(null);
      setBreakdownError(error instanceof ApiError ? error.message : t.tasksPage.breakdownLoadError);
    } finally {
      setBreakdownLoading(false);
    }
  }, [accessToken, t.tasksPage.breakdownLoadError]);

  const closeBreakdown = useCallback(() => {
    setBreakdownOpen(false);
    setBreakdown(null);
    setBreakdownError(null);
  }, []);

  const handleInboxWidthChange = useCallback((width: number) => {
    const next = clampInboxWidth(width);
    setInboxWidth(next);
    try {
      localStorage.setItem(INBOX_WIDTH_KEY, String(next));
    } catch {
      // localStorage có thể bị chặn ở private mode — độ rộng chỉ sống trong phiên này.
    }
  }, []);

  useEffect(() => {
    if (!isResizingInbox) return undefined;

    const onPointerMove = (e: PointerEvent) => {
      const rect = inboxColumnRef.current?.getBoundingClientRect();
      if (!rect) return;
      // Tay kéo nằm ở cạnh TRÁI cột (cột nằm bên phải màn hình) — độ rộng là
      // khoảng cách từ con trỏ tới cạnh PHẢI cột, ngược hướng so với Sidebar.
      handleInboxWidthChange(rect.right - e.clientX);
    };
    const onPointerUp = () => setIsResizingInbox(false);

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    return () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
  }, [isResizingInbox, handleInboxWidthChange]);

  useEffect(() => {
    void loadCalendar();
  }, [loadCalendar]);

  useEffect(() => {
    if (!undoOperation) return undefined;
    const delay = Math.max(0, undoOperation.expiresAt - Date.now());
    const timer = window.setTimeout(() => setUndoOperation(null), delay);
    return () => window.clearTimeout(timer);
  }, [undoOperation]);

  const matchesPriorityFilter = useCallback((task: Task) => (
    priorityFilter === ALL_PRIORITIES
      || priorityFilterKey(task.statedPriority) === priorityFilter
  ), [priorityFilter]);
  const filteredTasks = useMemo(() => {
    const today = startOfDay(new Date());
    return tasks.filter((task) => {
      const matchesStatus = statusFilter === 'all'
        ? task.status !== 'completed'
        : statusFilter === 'closed'
          ? task.status === 'dismissed' || task.status === 'cancelled'
          // 'trash' CHỈ gồm 'cancelled'. Job dọn ở backend chỉ xoá status
          // 'cancelled'; 'dismissed' không bao giờ bị đụng tới. Gộp chung rồi
          // hiện đếm ngược cho cả hai là nói với người dùng một hạn xoá không
          // tồn tại.
          : statusFilter === 'trash'
            ? task.status === 'cancelled'
            : task.status === statusFilter;
      return matchesStatus && matchesPriorityFilter(task);
    })
      .sort((left, right) => compareInboxTasks(left, right, today));
  }, [matchesPriorityFilter, statusFilter, tasks]);
  const completedTasks = useMemo(
    () => tasks
      .filter((task) => task.status === 'completed')
      .sort((left, right) => new Date(right.completedAt ?? right.updatedAt).getTime() - new Date(left.completedAt ?? left.updatedAt).getTime()),
    [tasks],
  );
  const filteredCompletedTasks = useMemo(
    () => completedTasks.filter(matchesPriorityFilter),
    [completedTasks, matchesPriorityFilter],
  );
  const tasksToRender = statusFilter === 'completed' ? filteredCompletedTasks : filteredTasks;
  const showCompletedArchive = statusFilter === 'all' && filteredCompletedTasks.length > 0;
  const priorityOptions = useMemo(() => {
    const values = new Map<string, string>();
    tasks.forEach((task) => {
      const filterKey = priorityFilterKey(task.statedPriority);
      const displayValue = nonBlank(task.statedPriority);
      if (filterKey && displayValue && !values.has(filterKey)) values.set(filterKey, displayValue);
    });
    return [...values.entries()].sort(([leftKey], [rightKey]) => {
      const leftDisplay = values.get(leftKey);
      const rightDisplay = values.get(rightKey);
      const bandDifference = prioritySortRank(leftDisplay) - prioritySortRank(rightDisplay);
      return bandDifference || leftKey.localeCompare(rightKey);
    });
  }, [tasks]);
  const taskStats = useMemo(() => ({
    completed: tasks.filter((task) => task.status === 'completed').length,
    inProgress: tasks.filter((task) => task.status === 'confirmed').length,
    highPriorityOpen: tasks.filter((task) => isOpenTask(task) && priorityBandOf(task.statedPriority) === 'high').length,
  }), [tasks]);
  const visibleCalendarTasks = useMemo(
    () => tasks.filter((task) => !['dismissed', 'completed', 'cancelled'].includes(task.status) && task.dueAt),
    [tasks],
  );

  const formatTime = (value: Date): string =>
    `${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`;

  const formatDue = (task: Task): string =>
    new Date(task.dueAt!).toLocaleString(locale, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      ...(task.allDay ? {} : { hour: '2-digit', minute: '2-digit' }),
    });

  const transitionTask = async (task: Task, action: 'confirm' | 'dismiss') => {
    if (!accessToken) return;
    setPendingId(task.id);
    try {
      const updated =
        action === 'confirm'
          ? await confirmTask(task.id, accessToken)
          : await dismissTask(task.id, accessToken);
      setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      recordMeaningfulAction(action === 'confirm' ? 'task_confirmed' : 'task_dismissed');
      recordTaskDecision(action === 'confirm' ? 'confirmed' : 'dismissed');
      addToast({
        type: 'success',
        title: action === 'confirm' ? t.tasksPage.confirmedToast : t.tasksPage.dismissedToast,
        message: (action === 'confirm' ? t.tasksPage.confirmedMsg : t.tasksPage.dismissedMsg).replace(
          '{title}',
          task.title,
        ),
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.updateFailTitle,
        message: error instanceof ApiError ? error.message : t.tasksPage.unknownError,
      });
    } finally {
      setPendingId(null);
    }
  };

  const handleRestore = async (task: Task) => {
    if (!accessToken) return;
    setPendingId(task.id);
    try {
      const updated = await restoreTask(task.id, accessToken);
      setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      addToast({
        type: 'success',
        title: t.tasksPage.restoreTask,
        message: task.title,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.restoreTask,
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setPendingId(null);
    }
  };

  const resolveTask = async (task: Task, action: 'complete' | 'cancel', actualMinutes?: number) => {
    if (!accessToken) return;
    setPendingId(task.id);
    try {
      const updated = action === 'complete'
        ? await completeTask(task.id, accessToken, actualMinutes)
        : await cancelTask(task.id, accessToken);
      setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      addToast({
        type: 'success',
        title: action === 'complete' ? t.tasksPage.completedToast : t.tasksPage.cancelledToast,
        message: (action === 'complete' ? t.tasksPage.completedMsg : t.tasksPage.cancelledMsg).replace(
          '{title}',
          task.title,
        ),
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.updateFailTitle,
        message: error instanceof ApiError ? error.message : t.tasksPage.unknownError,
      });
    } finally {
      setPendingId(null);
    }
  };

  const openCompletionPrompt = (task: Task) => {
    setCompletionPrompt({ task, customMinutes: '', showCustomInput: false });
  };

  const completeFromPrompt = async (actualMinutes?: number) => {
    if (completionPrompt === null) return;
    const { task } = completionPrompt;
    setCompletionPrompt(null);
    await resolveTask(task, 'complete', actualMinutes);
  };

  const cancelFromPrompt = async () => {
    if (cancellationPrompt === null) return;
    const task = cancellationPrompt;
    setCancellationPrompt(null);
    await resolveTask(task, 'cancel');
  };

  const openDueEditor = (task: Task) => {
    setDueDraft({ task, value: task.dueAt ? task.dueAt.slice(0, 16) : '', allDay: task.allDay });
  };

  const openTaskEditor = (task: Task) => setTaskDraft({ task, title: task.title, detail: task.detail });

  const saveTaskDraft = async () => {
    if (!accessToken || taskDraft === null || !taskDraft.title.trim()) return;
    setSavingTask(true);
    try {
      const updated = await updateTask(taskDraft.task.id, {
        title: taskDraft.title.trim(),
        detail: taskDraft.detail,
      }, accessToken);
      setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setTaskDraft(null);
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.updateFailTitle,
        message: error instanceof ApiError ? error.message : t.tasksPage.unknownError,
      });
    } finally {
      setSavingTask(false);
    }
  };

  const saveDueDraft = async () => {
    if (!accessToken || dueDraft === null || !dueDraft.value) return;
    setSavingDue(true);
    try {
      const wasSynced = Boolean(dueDraft.task.calendarEventId);
      const dueAt = dueDraft.allDay ? dueDraft.value.slice(0, 10) : new Date(dueDraft.value).toISOString();
      const updated = await updateTask(dueDraft.task.id, { dueAt, allDay: dueDraft.allDay }, accessToken);
      setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setDueDraft(null);
      if (wasSynced) {
        addToast({
          type: 'info',
          title: t.tasksPage.dueChangedSyncedTitle,
          message: t.tasksPage.dueChangedSyncedMsg,
        });
      }
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.updateFailTitle,
        message: error instanceof ApiError ? error.message : t.tasksPage.unknownError,
      });
    } finally {
      setSavingDue(false);
    }
  };

  const syncTask = async (task: Task) => {
    if (!accessToken) return;
    setSyncingId(task.id);
    try {
      const result = await syncTaskToCalendar(task.id, accessToken);
      setTasks((current) =>
        current.map((row) =>
          row.id === task.id ? { ...row, calendarEventId: result.calendarEventId } : row,
        ),
      );
      addToast({
        type: 'success',
        title: t.tasksPage.syncSuccessTitle,
        message: t.tasksPage.syncSuccessMsg.replace('{title}', task.title),
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.syncFailTitle,
        message: error instanceof ApiError ? error.message : t.tasksPage.unknownError,
      });
    } finally {
      setSyncingId(null);
    }
  };

  const connectGoogle = async () => {
    if (!accessToken) return;
    setConnecting(true);
    try {
      const redirectUri = `${window.location.origin}/tasks`;
      const { authorizeUrl } = await createConnectIntent('google', redirectUri, accessToken);
      window.location.assign(authorizeUrl);
    } catch (error) {
      addToast({
        type: 'error',
        title: t.tasksPage.connectFailTitle,
        message: error instanceof ApiError ? error.message : t.tasksPage.unknownError,
      });
      setConnecting(false);
    }
  };

  const showUndo = (operationId: number, undoExpiresAt: string) => {
    const expiresAt = new Date(undoExpiresAt).getTime();
    setUndoOperation(Number.isFinite(expiresAt) && expiresAt > Date.now() ? { id: operationId, expiresAt } : null);
  };

  const replaceEvent = (event: CalendarEvent) => {
    setEvents((current) => current.map((row) => (row.id === event.id ? event : row)));
  };

  const openCreateEvent = (day: Date, minute: number) => {
    const start = new Date(day);
    start.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
    const end = new Date(start);
    end.setMinutes(end.getMinutes() + 30);
    setEventDraft({
      calendarId: writableCalendars[0]?.id ?? 'primary',
      title: '', startAt: toDateTimeLocal(start), endAt: toDateTimeLocal(end), allDay: false,
    });
  };

  const openEditEvent = (event: CalendarEvent) => {
    const start = eventDate(event.startAt, event.allDay);
    const end = event.endAt ? eventDate(event.endAt, event.allDay) : new Date(start.getTime() + 30 * 60_000);
    setContextEvent(null);
    setEventDraft({ event, calendarId: event.calendarId, title: event.title, startAt: toDateTimeLocal(start), endAt: toDateTimeLocal(end), allDay: event.allDay });
  };

  const saveEvent = async () => {
    if (!accessToken || !eventDraft) return;
    setWritingEvent(true);
    try {
      const result = eventDraft.event
        ? await updateCalendarEvent(eventDraft.event.id, {
          calendarId: eventDraft.calendarId, title: eventDraft.title,
          startAt: eventDraft.allDay ? toOffsetIso(eventDraft.startAt) : new Date(eventDraft.startAt).toISOString(),
          endAt: eventDraft.allDay ? toOffsetIso(eventDraft.endAt) : new Date(eventDraft.endAt).toISOString(), allDay: eventDraft.allDay,
        }, accessToken)
        : await createCalendarEvent({
          calendarId: eventDraft.calendarId, title: eventDraft.title,
          startAt: new Date(eventDraft.startAt).toISOString(), endAt: new Date(eventDraft.endAt).toISOString(), allDay: false,
        }, accessToken);
      if (result.event) {
        const event = { ...result.event, calendarName: eventDraft.event?.calendarName ?? calendars.find((calendar) => calendar.id === result.event?.calendarId)?.name ?? 'Google Calendar' };
        setEvents((current) => eventDraft.event ? current.map((row) => row.id === event.id ? event : row) : [...current, event]);
      }
      setEventDraft(null);
      showUndo(result.operationId, result.undoExpiresAt);
      addToast({ type: 'success', title: eventDraft.event ? 'Event updated' : 'Event created', message: 'You can undo this change for 10 seconds.' });
    } catch (error) {
      addToast({ type: 'error', title: t.tasksPage.updateFailTitle, message: error instanceof ApiError ? error.message : t.tasksPage.unknownError });
    } finally {
      setWritingEvent(false);
    }
  };

  const removeEvent = async (event: CalendarEvent) => {
    if (!accessToken) return;
    setWritingEvent(true);
    try {
      const result = await deleteCalendarEvent(event.id, event.calendarId, accessToken);
      setEvents((current) => current.filter((row) => row.id !== event.id));
      setContextEvent(null);
      showUndo(result.operationId, result.undoExpiresAt);
      addToast({ type: 'success', title: 'Event deleted', message: 'You can undo this change for 10 seconds.' });
    } catch (error) {
      addToast({ type: 'error', title: t.tasksPage.updateFailTitle, message: error instanceof ApiError ? error.message : t.tasksPage.unknownError });
    } finally {
      setWritingEvent(false);
    }
  };

  const undoLastOperation = async () => {
    if (!accessToken || !undoOperation || undoOperation.expiresAt <= Date.now()) {
      setUndoOperation(null);
      return;
    }
    try {
      const result = await undoCalendarOperation(undoOperation.id, accessToken);
      setUndoOperation(null);
      if (result.event) {
        const event = { ...result.event, calendarName: calendars.find((calendar) => calendar.id === result.event?.calendarId)?.name ?? 'Google Calendar' };
        setEvents((current) => {
          const withoutSame = current.filter((row) => row.id !== event.id);
          return [...withoutSame, event];
        });
      } else {
        await loadCalendar();
      }
      addToast({ type: 'success', title: 'Change undone', message: 'Your calendar is restored.' });
    } catch (error) {
      addToast({ type: 'error', title: t.tasksPage.updateFailTitle, message: error instanceof ApiError ? error.message : t.tasksPage.unknownError });
    }
  };

  // Kéo-thả không ghi ngay — chỉ mở bản nháp chờ người dùng bấm Xác nhận
  // trong dialog (confirmReschedule). Ba hàm request* dưới đây chỉ TÍNH toán
  // giờ/ngày đích, không gọi API nào cả.
  const requestEventReschedule = (event: CalendarEvent, day: Date, minute: number) => {
    if (event.allDay) return;
    const fromStart = eventDate(event.startAt, false);
    const fromEnd = event.endAt ? eventDate(event.endAt, false) : new Date(fromStart.getTime() + 30 * 60_000);
    const duration = Math.max(15 * 60_000, fromEnd.getTime() - fromStart.getTime());
    const toStart = new Date(day);
    toStart.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
    const toEnd = new Date(toStart.getTime() + duration);
    setRescheduleDraft({ kind: 'event', event, fromStart, fromEnd, toStart, toEnd });
  };

  /** Kéo ở lưới tháng: chỉ đổi NGÀY, giữ nguyên giờ/phút và thời lượng gốc. */
  const requestEventDayMove = (event: CalendarEvent, day: Date) => {
    if (event.allDay) return;
    const fromStart = eventDate(event.startAt, false);
    const fromEnd = event.endAt ? eventDate(event.endAt, false) : new Date(fromStart.getTime() + 30 * 60_000);
    const duration = fromEnd.getTime() - fromStart.getTime();
    const toStart = new Date(day);
    toStart.setHours(fromStart.getHours(), fromStart.getMinutes(), 0, 0);
    const toEnd = new Date(toStart.getTime() + duration);
    setRescheduleDraft({ kind: 'event', event, fromStart, fromEnd, toStart, toEnd });
  };

  /** Kéo task sang ngày khác (dải task hoặc lưới tháng) — chỉ đổi NGÀY của
   * due_at, giữ nguyên giờ/phút nếu task không phải cả ngày. */
  const requestTaskDayMove = (task: Task, day: Date) => {
    const fromDue = taskDate(task);
    if (!fromDue) return;
    const toDue = new Date(day);
    if (!task.allDay) toDue.setHours(fromDue.getHours(), fromDue.getMinutes(), 0, 0);
    setRescheduleDraft({ kind: 'task', task, fromDue, toDue });
  };

  const confirmReschedule = async () => {
    if (!accessToken || rescheduleDraft === null) return;
    setSavingReschedule(true);
    try {
      if (rescheduleDraft.kind === 'event') {
        const { event, toStart, toEnd } = rescheduleDraft;
        const result = await updateCalendarEvent(
          event.id,
          { calendarId: event.calendarId, startAt: toStart.toISOString(), endAt: toEnd.toISOString(), allDay: false },
          accessToken,
        );
        if (result.event) replaceEvent({ ...result.event, calendarName: event.calendarName });
      } else {
        const { task, toDue } = rescheduleDraft;
        const dueAt = task.allDay ? localDateKey(toDue) : toDue.toISOString();
        const updated = await updateTask(task.id, { dueAt, allDay: task.allDay }, accessToken);
        setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      }
      setRescheduleDraft(null);
      addToast({ type: 'success', title: t.tasksPage.rescheduleSuccessTitle, message: t.tasksPage.rescheduleSuccessMsg });
    } catch (error) {
      addToast({ type: 'error', title: t.tasksPage.updateFailTitle, message: error instanceof ApiError ? error.message : t.tasksPage.unknownError });
    } finally {
      setSavingReschedule(false);
    }
  };

  const calendarEventsForDay = (day: Date, allDay: boolean): CalendarEvent[] => {
    const key = localDateKey(day);
    return events.filter(
      (event) => event.allDay === allDay && localDateKey(eventDate(event.startAt, event.allDay)) === key,
    );
  };

  const tasksForDay = (day: Date, allDay: boolean): Task[] => {
    const key = localDateKey(day);
    return visibleCalendarTasks.filter((task) => {
      const due = taskDate(task);
      return due && task.allDay === allDay && localDateKey(due) === key;
    });
  };

  const calendarTasksForDay = (day: Date): Task[] => {
    const key = localDateKey(day);
    return visibleCalendarTasks
      .filter((task) => {
        const due = taskDate(task);
        return due && localDateKey(due) === key;
      })
      .sort((left, right) => (taskDate(left)?.getTime() ?? 0) - (taskDate(right)?.getTime() ?? 0));
  };

  const timedItemsForDay = (day: Date): TimedItem[] => {
    const dayKey = localDateKey(day);
    const dayEndMinute = GRID_END_HOUR * 60;
    const baseItems: TimedItemBase[] = [
      ...calendarEventsForDay(day, false).map((event) => {
        const start = eventDate(event.startAt, false);
        const parsedEnd = event.endAt ? eventDate(event.endAt, false) : addDays(start, 0);
        if (!event.endAt) parsedEnd.setMinutes(parsedEnd.getMinutes() + 30);
        const rawEndMinute = localDateKey(parsedEnd) !== dayKey ? dayEndMinute : minutesFromMidnight(parsedEnd);
        const startMinute = Math.max(GRID_START_HOUR * 60, minutesFromMidnight(start));
        return {
          key: `event-${event.id}`,
          kind: 'event' as const,
          title: event.title,
          start,
          end: parsedEnd,
          startMinute,
          endMinute: Math.min(dayEndMinute, Math.max(startMinute + 15, rawEndMinute)),
          event,
        };
      }),
    ]
      .filter((item) => item.startMinute < dayEndMinute && item.endMinute > GRID_START_HOUR * 60)
      .sort((left, right) => left.startMinute - right.startMinute || left.endMinute - right.endMinute);

    const laidOut: TimedItem[] = [];
    let cluster: TimedItemBase[] = [];
    let clusterEnd = -1;
    const flushCluster = () => {
      if (cluster.length === 0) return;
      const laneEnds: number[] = [];
      const withLanes = cluster.map((item) => {
        let lane = laneEnds.findIndex((endMinute) => endMinute <= item.startMinute);
        if (lane === -1) lane = laneEnds.length;
        laneEnds[lane] = item.endMinute;
        return { ...item, lane };
      });
      const lanes = laneEnds.length;
      laidOut.push(...withLanes.map((item) => ({ ...item, lanes }) as TimedItem));
      cluster = [];
      clusterEnd = -1;
    };

    for (const item of baseItems) {
      if (cluster.length > 0 && item.startMinute >= clusterEnd) flushCluster();
      cluster.push(item);
      clusterEnd = Math.max(clusterEnd, item.endMinute);
    }
    flushCluster();
    return laidOut;
  };

  const mobileItemsForDay = (day: Date) => {
    const calendarItems = [...calendarEventsForDay(day, true), ...calendarEventsForDay(day, false)].map(
      (event) => ({
        key: `event-${event.id}`,
        title: event.title,
        date: eventDate(event.startAt, event.allDay),
        allDay: event.allDay,
        kind: 'event' as const,
        event,
      }),
    );
    const todoItems = [...tasksForDay(day, true), ...tasksForDay(day, false)].map((task) => ({
      key: `task-${task.id}`,
      title: task.title,
      date: taskDate(task) as Date,
      allDay: task.allDay,
      kind: 'task' as const,
      task,
    }));
    return [...todoItems, ...calendarItems].sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === 'task' ? -1 : 1;
      return left.date.getTime() - right.date.getTime();
    });
  };

  const filters: Array<{ id: FilterId; label: string }> = [
    { id: 'all', label: t.tasksPage.filterAll },
    { id: 'proposed', label: t.tasksPage.filterProposed },
    { id: 'confirmed', label: t.tasksPage.filterConfirmed },
    { id: 'completed', label: t.tasksPage.filterCompleted },
    { id: 'closed', label: t.tasksPage.filterClosed },
    { id: 'trash', label: t.tasksPage.filterTrash },
  ];

  const priorityDisplayName = (value: string): string => {
    const band = priorityBandOf(value);
    if (band === 'high') return t.tasksPage.priorityHigh;
    if (band === 'medium') return t.tasksPage.priorityMedium;
    if (band === 'low') return t.tasksPage.priorityLow;
    return value;
  };

  const assignmentDetails = (task: Task) => [
    { label: t.tasksPage.expectedOutputLabel, value: nonBlank(task.expectedOutput) },
    { label: t.tasksPage.acceptanceCriteriaLabel, value: nonBlank(task.acceptanceCriteria) },
    { label: t.tasksPage.contextInputLabel, value: nonBlank(task.contextInput) },
    { label: t.tasksPage.constraintsLabel, value: nonBlank(task.constraints) },
    { label: t.tasksPage.executionMethodLabel, value: nonBlank(task.executionMethod) },
    { label: t.tasksPage.executionToolLabel, value: nonBlank(task.executionTool) },
    { label: t.tasksPage.assigneeLabel, value: nonBlank(task.assignee) },
    { label: t.tasksPage.stakeholdersLabel, value: nonBlankList(task.stakeholders) },
    { label: t.tasksPage.deliverToLabel, value: nonBlank(task.deliverTo) },
    {
      label: t.tasksPage.estimateLabel,
      value: task.estimateLowMin !== null && task.estimateHighMin !== null
        ? `${task.estimateLowMin}–${task.estimateHighMin} min`
        : null,
    },
  ].filter((field): field is { label: string; value: string } => field.value !== null);

  const renderPriorityBadge = (task: Task) => {
    const priority = nonBlank(task.statedPriority);
    if (priority === null) return <Badge variant="neutral">Chưa xếp ưu tiên</Badge>;
    const band = priorityBandOf(priority);
    const variant = band === 'high' ? 'danger' : band === 'medium' ? 'warning' : 'neutral';
    return (
      <Badge variant={variant}>
        {t.tasksPage.priorityBadge.replace('{priority}', priorityDisplayName(priority))}
      </Badge>
    );
  };

  const renderAssignmentDetails = (task: Task) => {
    const details = assignmentDetails(task);
    if (details.length === 0) return null;
    return <details className="group mt-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)]/55 p-3 text-xs"><summary className="cursor-pointer list-none font-semibold text-[var(--color-primary)] marker:content-none">Xem brief công việc · mục tiêu, tiêu chí và bối cảnh</summary><dl className="mt-3 grid gap-3 border-t border-[var(--color-border)] pt-3 sm:grid-cols-2">{details.map((field) => <div key={field.label}><dt className="font-semibold text-[var(--color-text-muted)]">{field.label}</dt><dd className="mt-0.5 whitespace-pre-wrap break-words leading-relaxed text-[var(--color-text-secondary)]">{field.value}</dd></div>)}</dl></details>;
  };

  const weekLabel = `${weekStart.toLocaleDateString(locale, {
    day: 'numeric',
    month: 'short',
  })} — ${addDays(weekStart, 6).toLocaleDateString(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })}`;
  const dayLabel = dayStart.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const monthLabel = focusDate.toLocaleDateString(locale, { month: 'long', year: 'numeric' });
  const rangeLabel = view === 'day' ? dayLabel : view === 'month' ? monthLabel : weekLabel;

  // Prev/Next/Today đổi field theo đúng đơn vị của view đang chọn — lùi 1
  // tuần khi ở view tuần vẫn phải lùi cả tuần dù đang neo vào giữa tuần đó.
  const goToPrevious = () => setFocusDate((current) => (view === 'day' ? addDays(current, -1) : view === 'month' ? addMonths(current, -1) : addDays(current, -7)));
  const goToNext = () => setFocusDate((current) => (view === 'day' ? addDays(current, 1) : view === 'month' ? addMonths(current, 1) : addDays(current, 7)));
  const goToToday = () => setFocusDate(new Date());

  const todayKey = localDateKey(new Date());
  return (
    <div className="mx-auto max-w-[1680px] space-y-5 animate-in fade-in duration-300">
      <header className="flex flex-col gap-5 2xl:flex-row 2xl:items-end 2xl:justify-between">
        <div className="max-w-3xl">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-[0.08em] text-[var(--color-primary)]">
            <CalendarDays className="h-4 w-4" /> {t.tasksPage.eyebrow}
          </div>
          <h1 className="font-heading text-3xl font-semibold tracking-[-0.035em] text-[var(--color-text-primary)] sm:text-4xl">
            {t.tasksPage.title}
          </h1>
          <p className="mt-2 max-w-[64ch] text-sm text-[var(--color-text-secondary)]">
            {t.tasksPage.subtitle}
          </p>
        </div>

        <div className="grid min-w-0 grid-cols-3 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-sm)]">
          <div className="min-w-0 px-2 py-3 sm:px-4" aria-label={t.tasksPage.statsCompleted}>
            <span className="block text-xl font-semibold tabular-nums text-[var(--color-text-primary)]">{taskStats.completed}</span>
            <span className="block break-words text-[11px] leading-tight text-[var(--color-text-muted)]">{t.tasksPage.statsCompleted}</span>
          </div>
          <div className="min-w-0 border-x border-[var(--color-border)] px-2 py-3 sm:px-4" aria-label={t.tasksPage.statsInProgress}>
            <span className="block text-xl font-semibold tabular-nums text-[var(--color-text-primary)]">{taskStats.inProgress}</span>
            <span className="block break-words text-[11px] leading-tight text-[var(--color-text-muted)]">{t.tasksPage.statsInProgress}</span>
          </div>
          <div className="min-w-0 px-2 py-3 sm:px-4" aria-label={t.tasksPage.statsHighPriorityOpen}>
            <span className="block text-xl font-semibold tabular-nums text-[var(--color-danger)]">{taskStats.highPriorityOpen}</span>
            <span className="block break-words text-[11px] leading-tight text-[var(--color-text-muted)]">{t.tasksPage.statsHighPriorityOpen}</span>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-5 xl:flex xl:flex-row xl:items-start">
      <div className="min-w-0 space-y-5 xl:flex-1">
      <section className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-md)]">
        {/* flex-wrap ở chính hàng này (không chỉ bên trong từng cụm) — thiếu
            nó thì 3 cụm (điều hướng / chuyển view / legend+nút) xuống dòng
            độc lập với nhau khi hẹp đi (phóng chữ, đóng/mở panel task), làm
            nút vỡ dòng lộn xộn thay vì cả cụm cùng trôi xuống dòng mới. */}
        <div className="flex flex-col flex-wrap gap-3 border-b border-[var(--color-border)] p-3 sm:flex-row sm:items-center">
          <div className="flex shrink-0 flex-wrap items-center gap-x-1.5 gap-y-1" data-tour-id="tasks-week-nav">
            <Button
              variant="outline"
              size="sm"
              className="px-2"
              aria-label={t.tasksPage.previousWeek}
              onClick={goToPrevious}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="px-2"
              aria-label={t.tasksPage.nextWeek}
              onClick={goToNext}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <span className="min-w-0 px-2 text-sm font-semibold tabular-nums text-[var(--color-text-primary)] sm:min-w-[13rem]">
              {rangeLabel}
            </span>
            <Button variant="ghost" size="sm" onClick={goToToday}>
              {t.tasksPage.today}
            </Button>
          </div>

          <div className="inline-flex shrink-0 items-center gap-0.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-0.5" role="tablist" aria-label={t.tasksPage.viewSwitcherAria}>
            {(['day', 'week', 'month'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                role="tab"
                aria-selected={view === mode}
                onClick={() => setView(mode)}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] ${
                  view === mode
                    ? 'bg-[var(--color-surface)] text-[var(--color-primary)] shadow-[var(--shadow-sm)]'
                    : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
                }`}
              >
                {mode === 'day' ? t.tasksPage.viewDay : mode === 'week' ? t.tasksPage.viewWeek : t.tasksPage.viewMonth}
              </button>
            ))}
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3 sm:ml-auto">
            <span className="inline-flex items-center gap-1.5 text-[11px] text-[var(--color-text-secondary)]">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--color-primary)]" />
              {t.tasksPage.calendarLegend}
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-[var(--color-text-secondary)]">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--color-warning)]" />
              {t.tasksPage.todoLegend}
            </span>
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={`h-3.5 w-3.5 ${calendarLoading ? 'animate-spin' : ''}`} />}
              onClick={() => void loadCalendar()}
              disabled={calendarLoading}
            >
              {t.tasksPage.refresh}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setCompactTimeline((current) => !current)} aria-pressed={compactTimeline}>
              {compactTimeline ? 'Hiện đủ khung giờ' : 'Thu gọn lịch'}
            </Button>
          </div>
        </div>

        {calendarError && (
          <div className="flex flex-col gap-3 border-b border-[var(--color-border)] bg-[var(--color-warning-soft)] px-4 py-3 text-sm text-[var(--color-text-primary)] sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Link2 className="h-4 w-4 shrink-0 text-[var(--color-warning)]" />
              <span className="truncate">{calendarError}</span>
            </div>
            <Button variant="outline" size="sm" onClick={() => void connectGoogle()} disabled={connecting}>
              {connecting ? t.tasksPage.connecting : t.tasksPage.connectCalendar}
            </Button>
          </div>
        )}

        {/* Lưới tuần 7 cột không đọc nổi ở khổ điện thoại nên vẫn ẩn dưới md:,
            dùng danh sách phẳng bên dưới thay thế. Ngày/Tháng thì khác: view
            ngày chỉ 1 cột (vừa mọi khổ máy), view tháng đã tự đổi sang ô chấm
            tròn gọn ở mobile (không còn chữ dài) — cả hai không có lý do gì
            phải ẩn, trước đây bị ẩn oan theo cùng class với tuần. */}
        <div className={view === 'week' ? 'hidden md:block' : ''} data-tour-id="tasks-calendar-grid">
          {view === 'month' ? (
            <div key="month" className="animate-in fade-in duration-200 p-2 sm:p-3">
              <div className="grid grid-cols-7 gap-1.5 pb-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                {weekDays.map((day) => (
                  <div key={localDateKey(day)}>{day.toLocaleDateString(locale, { weekday: 'short' })}</div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1.5">
                {monthWeeks.flat().map((day) => {
                  const key = localDateKey(day);
                  const inMonth = day.getMonth() === focusDate.getMonth();
                  const dayTasks = calendarTasksForDay(day);
                  const dayEvents = [...calendarEventsForDay(day, true), ...calendarEventsForDay(day, false)];
                  const totalChips = dayTasks.length + dayEvents.length;
                  const visibleTasks = dayTasks.slice(0, 3);
                  const visibleEvents = dayEvents.slice(0, Math.max(0, 3 - visibleTasks.length));
                  const overflow = totalChips - visibleTasks.length - visibleEvents.length;
                  return (
                    <div
                      key={key}
                      className={`min-h-[3.25rem] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1.5 text-left transition-colors sm:min-h-[6.5rem] ${
                        inMonth ? '' : 'opacity-45'
                      } ${key === todayKey ? 'ring-2 ring-inset ring-[var(--color-primary)]' : ''}`}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => {
                        event.preventDefault();
                        const taskId = event.dataTransfer.getData('text/task-id');
                        if (taskId) {
                          const task = tasks.find((row) => String(row.id) === taskId);
                          if (task) requestTaskDayMove(task, day);
                          return;
                        }
                        const eventId = event.dataTransfer.getData('text/calendar-event-id');
                        const moved = events.find((row) => row.id === eventId);
                        if (moved) requestEventDayMove(moved, day);
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => { setFocusDate(day); setView('day'); }}
                        aria-label={t.tasksPage.openDayViewA11y.replace('{date}', day.toLocaleDateString(locale, { day: 'numeric', month: 'short' }))}
                        className={`rounded px-1 text-xs font-semibold tabular-nums hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] ${
                          key === todayKey ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-primary)]'
                        }`}
                      >
                        {day.getDate()}
                      </button>
                      {/* Điện thoại: ô ~50px/cột không đủ chỗ cho chữ, kéo-thả
                          native HTML5 cũng không hoạt động qua chạm — chỉ hiện
                          chấm chỉ báo, bấm số ngày để nhảy sang view Ngày xem
                          chi tiết. Từ sm: trở lên vẫn chip chữ + kéo-thả như cũ. */}
                      {totalChips > 0 && (
                        <div className="mt-1 flex flex-wrap items-center gap-0.5 sm:hidden">
                          {visibleTasks.map((task) => (
                            <span key={`dot-task-${task.id}`} className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-warning)]" title={task.title} />
                          ))}
                          {visibleEvents.map((event) => (
                            <span key={`dot-event-${event.id}`} className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-primary)]" title={event.title} />
                          ))}
                          {overflow > 0 && <span className="text-[8px] leading-none text-[var(--color-text-muted)]">+{overflow}</span>}
                        </div>
                      )}
                      <div className="mt-1 hidden space-y-0.5 sm:block">
                        {visibleTasks.map((task) => (
                          <div
                            key={`task-${task.id}`}
                            draggable
                            onDragStart={(event) => event.dataTransfer.setData('text/task-id', String(task.id))}
                            onClick={() => document.getElementById(`task-inbox-${task.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
                            className="flex cursor-grab items-center gap-1 truncate rounded border border-[var(--color-warning)]/35 bg-[var(--color-warning-soft)]/60 px-1 py-0.5 text-[10px] font-medium text-[var(--color-text-primary)]"
                            title={task.title}
                          >
                            <span className="truncate">{task.title}</span>
                          </div>
                        ))}
                        {visibleEvents.map((event) => (
                          <button
                            key={`event-${event.id}`}
                            type="button"
                            draggable={isCalendarWritable(event.calendarId)}
                            onDragStart={(dragEvent) => {
                              if (isCalendarWritable(event.calendarId)) {
                                dragEvent.dataTransfer.setData('text/calendar-event-id', event.id);
                              }
                            }}
                            onClick={() => {
                              if (isCalendarWritable(event.calendarId)) openEditEvent(event);
                              else setContextEvent(event);
                            }}
                            onContextMenu={(clickEvent) => { clickEvent.preventDefault(); setContextEvent(event); }}
                            aria-label={(isCalendarWritable(event.calendarId) ? t.tasksPage.editEventAria : t.tasksPage.eventContextMenuAria).replace('{title}', event.title)}
                            className="flex w-full cursor-grab items-center gap-1 truncate rounded bg-[var(--color-primary)] px-1 py-0.5 text-left text-[10px] font-medium text-[var(--color-on-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                            title={event.title}
                          >
                            <span className="truncate">{event.title}</span>
                          </button>
                        ))}
                        {overflow > 0 && (
                          <span className="block px-1 text-[10px] text-[var(--color-text-muted)]">
                            {t.tasksPage.moreItems.replace('{count}', String(overflow))}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
          <div key={view} className="animate-in fade-in duration-200 max-h-[72vh] overflow-auto">
            <div className={view === 'day' ? '' : 'min-w-[840px]'}>
              <div className={`sticky top-0 z-30 grid ${view === 'day' ? 'grid-cols-[3.75rem_repeat(1,minmax(0,1fr))]' : 'grid-cols-[3.75rem_repeat(7,minmax(0,1fr))]'} border-b border-[var(--color-border)] bg-[var(--color-surface)]`}>
                <div aria-hidden />
                {viewDays.map((day) => {
                  const key = localDateKey(day);
                  const count =
                    calendarEventsForDay(day, true).length +
                    calendarEventsForDay(day, false).length +
                    calendarTasksForDay(day).length;
                  return (
                    <div
                      key={key}
                      className={`min-w-0 cursor-default border-l border-[var(--color-border)] py-2 text-center transition-colors hover:bg-[var(--color-surface-hover)] ${
                        key === todayKey ? 'bg-[var(--color-accent-soft)]/45' : ''
                      }`}
                    >
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
                        {day.toLocaleDateString(locale, { weekday: 'short' })}
                      </span>
                      <span className={`text-xl font-semibold tabular-nums ${key === todayKey ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-primary)]'}`}>
                        {day.getDate()}
                      </span>
                      {count > 0 && (
                        <span className="ml-1.5 rounded-md bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-secondary)]">
                          {count}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              <div
                className={`grid ${view === 'day' ? 'grid-cols-[3.75rem_repeat(1,minmax(0,1fr))]' : 'grid-cols-[3.75rem_repeat(7,minmax(0,1fr))]'} border-b border-[var(--color-border)] bg-[var(--color-warning-soft)]/35`}
                data-testid="calendar-task-rail"
              >
                <div className="py-2 pr-2 text-right text-[10px] font-semibold text-[var(--color-warning)]">
                  {t.tasksPage.tasksRail}
                </div>
                {viewDays.map((day) => (
                  <div
                    key={localDateKey(day)}
                    className="min-h-10 min-w-0 space-y-1 overflow-hidden border-l border-[var(--color-border)] p-1"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      const taskId = event.dataTransfer.getData('text/task-id');
                      if (!taskId) return;
                      const task = tasks.find((row) => String(row.id) === taskId);
                      if (task) requestTaskDayMove(task, day);
                    }}
                  >
                    {calendarTasksForDay(day).map((task) => {
                      const source = taskSources(task)[0];
                      return (
                        <div
                          key={task.id}
                          draggable
                          onDragStart={(event) => event.dataTransfer.setData('text/task-id', String(task.id))}
                          className="flex w-full cursor-grab items-center gap-1 rounded-md border border-[var(--color-warning)]/35 bg-[var(--color-surface)] px-1.5 py-1 text-left text-[10px] font-semibold text-[var(--color-text-primary)] shadow-[var(--shadow-sm)]"
                        >
                          <a href={`#task-inbox-${task.id}`} className="flex min-w-0 flex-1 items-center gap-1.5 rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]">
                            {resolveBrandIcon(source.key, 'h-3.5 w-3.5') ?? <Inbox className="h-3.5 w-3.5 shrink-0 text-[var(--color-warning)]" />}
                            <span className="truncate">{task.title}</span>
                          </a>
                          {task.status === 'confirmed' && (
                            <button type="button" className="shrink-0 rounded p-0.5 text-[var(--color-text-muted)] hover:bg-[var(--color-success-soft)] hover:text-[var(--color-success)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]" onClick={() => openCompletionPrompt(task)} disabled={pendingId === task.id} title={t.tasksPage.completeTaskInCalendarA11y.replace('{title}', task.title)} aria-label={t.tasksPage.completeTaskInCalendarA11y.replace('{title}', task.title)}>
                              <CheckCircle2 className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>

              <div className={`grid ${view === 'day' ? 'grid-cols-[3.75rem_repeat(1,minmax(0,1fr))]' : 'grid-cols-[3.75rem_repeat(7,minmax(0,1fr))]'} border-b border-[var(--color-border)] bg-[var(--color-surface-muted)]/55`}>
                <div className="py-2 pr-2 text-right text-[10px] text-[var(--color-text-muted)]">{t.tasksPage.allDay}</div>
                {viewDays.map((day) => (
                  <div key={localDateKey(day)} className="min-h-10 min-w-0 space-y-1 overflow-hidden border-l border-[var(--color-border)] p-1">
                    {calendarEventsForDay(day, true).map((event) => (
                      <button
                        key={event.id}
                        type="button"
                        onClick={() => {
                          if (isCalendarWritable(event.calendarId)) openEditEvent(event);
                          else setContextEvent(event);
                        }}
                        onContextMenu={(clickEvent) => { clickEvent.preventDefault(); setContextEvent(event); }}
                        onKeyDown={(keyEvent) => {
                          if (keyEvent.key === 'ContextMenu' || (keyEvent.shiftKey && keyEvent.key === 'F10')) {
                            keyEvent.preventDefault(); setContextEvent(event);
                          }
                        }}
                        aria-label={(isCalendarWritable(event.calendarId) ? t.tasksPage.editEventAria : t.tasksPage.eventContextMenuAria).replace('{title}', event.title)}
                        className="flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-1.5 py-1 text-[10px] font-medium text-[var(--color-on-primary)] transition-opacity hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                      >
                        <GoogleCalendarIcon className="h-3 w-3 shrink-0" title="Google Calendar event" />
                        <span className="truncate">{event.title}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>

              <div
                className={`grid ${view === 'day' ? 'grid-cols-[3.75rem_repeat(1,minmax(0,1fr))]' : 'grid-cols-[3.75rem_repeat(7,minmax(0,1fr))]'}`}
                data-testid="calendar-time-grid"
              >
                <div className="relative" style={{ height: gridHeight }}>
                  {HOUR_MARKS.map((hour) => (
                    <span
                      key={hour}
                      className="absolute right-2 -translate-y-1/2 text-[10px] tabular-nums text-[var(--color-text-muted)]"
                      style={{ top: (hour - GRID_START_HOUR) * hourHeight }}
                    >
                      {String(hour).padStart(2, '0')}:00
                    </span>
                  ))}
                </div>

                {viewDays.map((day) => {
                  const key = localDateKey(day);
                  return (
                    <div
                      key={key}
                      className={`relative min-w-0 overflow-hidden border-l border-[var(--color-border)] ${key === todayKey ? 'bg-[var(--color-accent-soft)]/20' : ''}`}
                      style={{ height: gridHeight }}
                      data-testid={`calendar-day-${key}`}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => {
                        event.preventDefault();
                        const eventId = event.dataTransfer.getData('text/calendar-event-id');
                        const moved = events.find((row) => row.id === eventId);
                        if (!moved) return;
                        const rect = event.currentTarget.getBoundingClientRect();
                        const minute = Math.min(GRID_END_HOUR * 60 - 15, Math.max(GRID_START_HOUR * 60, Math.round((GRID_START_HOUR * 60 + ((event.clientY - rect.top) / hourHeight) * 60) / 15) * 15));
                        requestEventReschedule(moved, day, minute);
                      }}
                    >
                      {/* Mỗi Ô GIỜ hover riêng — trước đây hover phủ NGUYÊN
                          CỘT vì cả cột chỉ là 1 div hover chung, đường kẻ giờ
                          chỉ là span trang trí cao ~0 nên click cũng luôn rơi
                          vào div cha. Giờ mỗi ô có chiều cao thật (hourHeight),
                          tự bắt hover + click tạo sự kiện đúng ô đó. */}
                      {HOUR_MARKS.map((hour) => (
                        <div
                          key={hour}
                          className="absolute inset-x-0 cursor-pointer border-t border-[var(--color-border-subtle)] transition-colors hover:bg-[var(--color-surface-hover)]"
                          style={{ top: (hour - GRID_START_HOUR) * hourHeight, height: hourHeight }}
                          onClick={(event) => {
                            const rect = event.currentTarget.getBoundingClientRect();
                            const minuteWithinHour = Math.round(((event.clientY - rect.top) / hourHeight) * 60 / 15) * 15;
                            const minute = Math.min(GRID_END_HOUR * 60 - 30, Math.max(GRID_START_HOUR * 60, hour * 60 + minuteWithinHour));
                            openCreateEvent(day, minute);
                          }}
                        />
                      ))}

                      {timedItemsForDay(day).map((item) => {
                        const style: React.CSSProperties = {
                          top: ((item.startMinute - GRID_START_HOUR * 60) / 60) * hourHeight,
                          height: Math.max(28, ((item.endMinute - item.startMinute) / 60) * hourHeight),
                          left: `calc(${(item.lane / item.lanes) * 100}% + 3px)`,
                          width: `calc(${100 / item.lanes}% - 6px)`,
                        };
                        return (
                          <button
                            key={item.key}
                            type="button"
                            draggable={isCalendarWritable(item.event.calendarId)}
                            onDragStart={(event) => {
                              if (isCalendarWritable(item.event.calendarId)) {
                                event.dataTransfer.setData('text/calendar-event-id', item.event.id);
                              }
                            }}
                            onClick={() => {
                              if (isCalendarWritable(item.event.calendarId)) openEditEvent(item.event);
                              else setContextEvent(item.event);
                            }}
                            onContextMenu={(event) => { event.preventDefault(); setContextEvent(item.event); }}
                            onKeyDown={(event) => {
                              if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
                                event.preventDefault(); setContextEvent(item.event);
                              }
                            }}
                            aria-label={(isCalendarWritable(item.event.calendarId) ? t.tasksPage.editEventAria : t.tasksPage.eventContextMenuAria).replace('{title}', item.title)}
                            className="absolute z-10 overflow-hidden rounded-lg border border-[var(--color-primary)]/35 bg-[var(--color-accent-soft)] px-2 py-1 text-left text-[11px] leading-tight text-[var(--color-text-primary)] shadow-[var(--shadow-sm)] transition-[transform,box-shadow] hover:-translate-y-px hover:shadow-[var(--shadow-md)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                            style={style}
                            title={`${item.title} · ${item.event.calendarName}`}
                          >
                            <span className="flex items-center gap-1 truncate text-[10px] text-[var(--color-primary)]">
                              <GoogleCalendarIcon className="h-3 w-3" title="Google Calendar event" />
                              <span className="truncate">{item.event.calendarName}</span>
                            </span>
                            <span className="block truncate text-[10px] tabular-nums text-[var(--color-primary)]">
                              {formatTime(item.start)}–{formatTime(item.end)}
                            </span>
                            <span className="mt-0.5 block truncate font-semibold">{item.title}</span>
                            <span className="mt-0.5 block truncate text-[10px] text-[var(--color-text-secondary)]">
                              {item.event.calendarName}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
          )}
        </div>

        {/* Danh sách phẳng dự phòng chỉ còn dùng cho Tuần ở mobile — Ngày và
            Tháng giờ đã có lưới thật riêng ngay phía trên, không cần trùng lặp. */}
        <div className={`space-y-5 p-3 md:hidden ${view === 'week' ? '' : 'hidden'}`}>
          {viewDays.map((day) => {
            const items = mobileItemsForDay(day);
            return items.length > 0 ? (
              <section key={localDateKey(day)} className="space-y-2">
                <h2 className="flex items-baseline gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
                  {day.toLocaleDateString(locale, { weekday: 'long' })}
                  <span className="text-xs tabular-nums text-[var(--color-text-muted)]">
                    {day.toLocaleDateString(locale, { day: '2-digit', month: '2-digit' })}
                  </span>
                </h2>
                {items.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => {
                      if (item.kind === 'event' && item.event.deepLink) {
                        window.open(item.event.deepLink, '_blank', 'noopener,noreferrer');
                      } else if (item.kind === 'task') {
                        document.getElementById(`task-inbox-${item.task.id}`)?.scrollIntoView({
                          behavior: 'smooth',
                          block: 'center',
                        });
                      }
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] ${
                      item.kind === 'event'
                        ? 'border-[var(--color-primary)]/35 bg-[var(--color-accent-soft)]'
                        : 'border-[var(--color-warning)]/35 bg-[var(--color-warning-soft)]'
                    }`}
                  >
                    {item.kind === 'event'
                      ? <GoogleCalendarIcon className="h-4 w-4" title="Google Calendar event" />
                      : resolveBrandIcon(taskSources(item.task)[0].key, 'h-4 w-4') ?? <Inbox className="h-4 w-4" />}
                    <span className="w-14 shrink-0 text-[11px] tabular-nums text-[var(--color-text-secondary)]">
                      {item.allDay ? t.tasksPage.allDay : formatTime(item.date)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</span>
                  </button>
                ))}
              </section>
            ) : null;
          })}
          {!calendarLoading && events.length === 0 && visibleCalendarTasks.length === 0 && (
            <p className="py-12 text-center text-sm text-[var(--color-text-muted)]">{t.tasksPage.calendarEmpty}</p>
          )}
        </div>
      </section>

      {/* Panel nằm ngay dưới lưới lịch: người dùng vừa thấy hai bên chồng nhau
          trên lưới thì đọc được luôn cần quyết gì, không phải đi tìm ở trang khác. */}
      <ScheduleConflictPanel
        accessToken={accessToken}
        timeFrom={rangeStart}
        timeTo={rangeEnd}
        locale={locale}
        calendarSyncVersion={calendarSyncVersion}
        onResolved={() => void loadTasks()}
      />
      </div>

      {/* Cột hộp việc — hẹp, nằm song song lịch để dễ đối chiếu, không phải cuộn xuống.
          Kéo co dãn được (cạnh trái) — cùng cơ chế Sidebar, clamp 280–560px. */}
      <div
        ref={inboxColumnRef}
        className="relative w-full shrink-0 xl:w-[var(--tasks-inbox-width)]"
        style={{ '--tasks-inbox-width': `${inboxWidth}px` } as React.CSSProperties}
      >
        {/* Thanh kéo resize — chỉ desktop */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={t.tasksPage.todoInbox}
          aria-valuemin={INBOX_WIDTH.min}
          aria-valuemax={INBOX_WIDTH.max}
          aria-valuenow={inboxWidth}
          tabIndex={0}
          onPointerDown={(e) => {
            e.preventDefault();
            setIsResizingInbox(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') {
              e.preventDefault();
              handleInboxWidthChange(inboxWidth + 8);
            } else if (e.key === 'ArrowRight') {
              e.preventDefault();
              handleInboxWidthChange(inboxWidth - 8);
            }
          }}
          className="absolute inset-y-0 left-0 z-10 hidden w-1.5 -translate-x-1/2 cursor-col-resize touch-none xl:block group"
        >
          <span
            className={`pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors ${
              isResizingInbox ? 'bg-[var(--color-primary)]' : 'bg-transparent group-hover:bg-[var(--color-primary)]'
            }`}
          />
        </div>
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
          <div className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-3">
            <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1.5">
              <h2 className="flex min-w-0 items-center gap-1.5 truncate font-heading text-base font-semibold tracking-[-0.02em] text-[var(--color-text-primary)]">
                <Inbox className="h-4 w-4 shrink-0 text-[var(--color-primary)]" /> {t.tasksPage.todoInbox}
              </h2>
              <div className="flex flex-wrap items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  aria-label={t.tasksPage.refreshTasks}
                  title={t.tasksPage.refreshTasks}
                  icon={<RefreshCw className={`h-3.5 w-3.5 ${tasksLoading ? 'animate-spin' : ''}`} />}
                  onClick={() => void loadTasks()}
                  disabled={tasksLoading}
                >
                  {t.tasksPage.refresh}
                </Button>
                <button
                  type="button"
                  onClick={() => void runBreakdown()}
                  disabled={breakdownLoading}
                  data-tour-id="tasks-breakdown-trigger"
                  aria-label={t.tasksPage.breakdownButton}
                  className="inline-flex items-center gap-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1 text-[11px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] disabled:opacity-60"
                >
                  <Sparkles className="h-3.5 w-3.5 text-[var(--color-primary)]" />
                  {breakdownLoading ? t.tasksPage.breakdownLoading : t.tasksPage.breakdownButton}
                </button>
                <select
                  aria-label={t.tasksPage.todoInbox}
                  data-tour-id="tasks-inbox-filters"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as FilterId)}
                  className="shrink-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1 text-[11px] font-semibold text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                >
                  {filters.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={t.tasksPage.priorityFilterLabel}
                  value={priorityFilter}
                  onChange={(event) => setPriorityFilter(event.target.value)}
                  className="shrink-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1 text-[11px] font-semibold text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                >
                  <option value={ALL_PRIORITIES}>{t.tasksPage.priorityFilterAll}</option>
                  {priorityOptions.map(([value, displayValue]) => (
                    <option key={value} value={value}>
                      {priorityDisplayName(displayValue)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-[var(--color-text-secondary)]">{t.tasksPage.todoInboxHint}</p>
          </div>

          {breakdownOpen && (
            <TaskBreakdownPanel
              breakdown={breakdown ?? { generatedAt: '', summary: '', items: [] }}
              loading={breakdownLoading}
              error={breakdownError}
              onClose={closeBreakdown}
              onRetry={() => void runBreakdown()}
            />
          )}

          {tasksError && <p className="mt-4 rounded-lg bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{tasksError}</p>}
          <div className="mt-3 max-h-[72vh] overflow-y-auto pr-1" data-tour-id="tasks-inbox-list">
          {tasksLoading ? (
            <div className="space-y-2 pt-4" aria-label={t.tasksPage.loading}>
              {[0, 1, 2].map((item) => (
                <div key={item} className="h-20 animate-pulse rounded-xl bg-[var(--color-surface-muted)]" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <div className="flex flex-col items-center px-4 py-10 text-center" data-testid="tasks-global-empty-state">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--color-accent-soft)] text-[var(--color-primary)]">
                <Sparkles className="h-5 w-5" />
              </span>
              <h3 className="mt-4 text-sm font-semibold text-[var(--color-text-primary)]">{t.tasksPage.emptyTitle}</h3>
              <p className="mt-1 max-w-sm text-xs leading-relaxed text-[var(--color-text-secondary)]">{t.tasksPage.emptyDescription}</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Button
                  size="sm"
                  onClick={() => navigate('/briefing', { state: createChatHandoff(t.tasksPage.emptyPlanPrompt) })}
                >
                  {t.tasksPage.emptyPlanAction}
                </Button>
                <Button size="sm" variant="outline" onClick={() => navigate('/sources')}>
                  {t.tasksPage.emptyConnectAction}
                </Button>
              </div>
            </div>
          ) : tasksToRender.length === 0 && !showCompletedArchive ? (
            <p className="py-12 text-center text-sm text-[var(--color-text-muted)]">{t.tasksPage.empty}</p>
          ) : (
            <div className="space-y-3">
              {tasksToRender.map((task) => {
                const sources = taskSources(task);
                const primarySource = sources[0];
                const primaryDeepLink = task.evidence[0]?.deepLink || primarySource.deepLink;
                const dueTime = taskDate(task)?.getTime() ?? null;
                const hoursToDue = dueTime === null ? null : (dueTime - Date.now()) / 3_600_000;
                const dueTone = hoursToDue !== null && hoursToDue < 0
                  ? 'border-[var(--color-danger)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]'
                  : hoursToDue !== null && hoursToDue <= 48
                    ? 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-text-primary)]'
                    : 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-primary)]';
                const statusLabel = {
                  proposed: t.tasksPage.filterProposed,
                  confirmed: t.tasksPage.statusConfirmed,
                  dismissed: t.tasksPage.filterDismissed,
                  completed: t.tasksPage.filterCompleted,
                  cancelled: t.tasksPage.filterCancelled,
                }[task.status];
                const description = task.detail || task.evidence[0]?.evidenceQuote || t.tasksPage.noDescription;
                return (
                  <article
                    key={task.id}
                    id={`task-inbox-${task.id}`}
                    className={`rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5 shadow-[var(--shadow-sm)] transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-[var(--color-primary)] hover:shadow-[var(--shadow-md)] target:bg-[var(--color-accent-soft)]/35 ${
                      task.status === 'dismissed' || task.status === 'cancelled' ? 'opacity-60' : ''
                    }`}
                  >
                    {/* flex-wrap — cột hộp việc kéo hẹp được xuống 280px (xem
                        comment ở inboxColumnRef); không wrap thì badge hạn
                        chót (shrink-0) bị ép sát/đè lên tiêu đề dài thay vì
                        tự xuống dòng riêng. */}
                    <div className="flex flex-wrap items-start gap-3">
                      <div
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-surface-muted)]"
                        aria-label={primarySource.label}
                      >
                        {resolveBrandIcon(primarySource.key, 'h-5 w-5') ?? <Inbox className="h-5 w-5 text-[var(--color-text-muted)]" />}
                      </div>

                      {/* min-w-[9rem] chứ không phải min-w-0 — 0 cho phép co vô hạn
                          nên flexbox coi hàng là "vẫn vừa" và không bao giờ đẩy
                          badge hạn chót xuống dòng riêng, tiêu đề bị ép còn vài
                          px và rớt chữ theo từng ký tự thay vì wrap câu bình
                          thường. Đặt sàn hợp lý thì hàng buộc phải wrap khi hẹp. */}
                      <div className="min-w-[9rem] flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Badge
                            variant={
                              task.status === 'confirmed' || task.status === 'completed'
                                ? 'success'
                                : task.status === 'proposed'
                                  ? 'warning'
                                  : 'neutral'
                            }
                          >
                            {statusLabel}
                          </Badge>
                          {renderPriorityBadge(task)}
                          {task.calendarEventId && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--color-success)]">
                              <Check className="h-3 w-3" /> {t.tasksPage.synced}
                            </span>
                          )}
                          {task.evidence.some((item) => item.hasAttachment) && (
                            <span
                              className="inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--color-text-secondary)]"
                              title={t.tasksPage.hasAttachment}
                            >
                              <Paperclip className="h-3 w-3" /> {t.tasksPage.hasAttachment}
                            </span>
                          )}
                        </div>
                        <h3 className="mt-1.5 break-words text-sm font-semibold leading-snug text-[var(--color-text-primary)]">{task.title}</h3>
                      </div>

                      <div className={`shrink-0 rounded-xl border px-2.5 py-2 text-right ${dueTone}`}>
                        <p className="text-[10px] font-bold uppercase tracking-wide opacity-75">
                          {t.tasksPage.dueLabel}
                        </p>
                        {task.status === 'confirmed' ? (
                          <button
                            type="button"
                            onClick={() => openDueEditor(task)}
                            title={t.tasksPage.setDueButton}
                            className={`mt-0.5 flex items-center justify-end gap-1 text-[11px] font-bold tabular-nums underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] ${
                              task.dueAt ? '' : 'text-[var(--color-warning)]'
                            }`}
                          >
                            <Clock3 className={`h-3 w-3 shrink-0 ${task.dueAt ? 'text-[var(--color-primary)]' : ''}`} />
                            {task.dueAt ? formatDue(task) : t.tasksPage.setDueButton}
                          </button>
                        ) : task.dueAt ? (
                          <p className="mt-0.5 flex items-center justify-end gap-1 text-[11px] font-bold tabular-nums">
                            <Clock3 className="h-3 w-3 shrink-0" />
                            {formatDue(task)}
                          </p>
                        ) : (
                          <p className="mt-0.5 flex items-center justify-end gap-1 text-[11px] font-medium text-[var(--color-warning)]">
                            <Clock3 className="h-3 w-3 shrink-0" />
                            {t.tasksPage.dueUnknown}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="mt-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">{t.tasksPage.summaryLabel}</p>
                      <div className="mt-1 line-clamp-3 rounded-xl bg-[var(--color-surface-muted)] px-3 py-2.5 text-xs leading-relaxed text-[var(--color-text-secondary)]" title={description}>
                        {description}
                      </div>
                    </div>
                    {renderAssignmentDetails(task)}

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      {primaryDeepLink ? (
                        <a
                          href={primaryDeepLink}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                        >
                          <Link2 className="h-3.5 w-3.5" /> {t.tasksPage.accessSource}
                        </a>
                      ) : (
                        <span />
                      )}

                      <div className="flex flex-wrap items-center gap-1.5">
                        {task.status === 'proposed' && (
                          <>
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() => openTaskEditor(task)}
                              aria-label={t.tasksPage.editTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.editEventAction}
                            </Button>
                            <Button
                              variant="ghost"
                              size="xs"
                              icon={<X className="h-3.5 w-3.5" />}
                              onClick={() => void transitionTask(task, 'dismiss')}
                              disabled={pendingId === task.id}
                              aria-label={t.tasksPage.dismissTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.dismiss}
                            </Button>
                            <Button
                              variant="primary"
                              size="xs"
                              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                              onClick={() => void transitionTask(task, 'confirm')}
                              disabled={pendingId === task.id}
                              aria-label={t.tasksPage.confirmTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.confirm}
                            </Button>
                          </>
                        )}
                        {/* Task trong thùng rác. Nhánh RIÊNG, ngang hàng với
                            'confirmed' — đặt lồng bên trong sẽ không bao giờ chạy
                            vì hai status loại trừ nhau, và TypeScript bắt được
                            đúng điều đó (TS2367). */}
                        {task.status === 'cancelled' && (
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--color-text-muted)]"
                              data-testid={`trash-countdown-${task.id}`}
                            >
                              <Clock3 className="h-3 w-3" />
                              {trashLabel(trashState(task), language === 'vi' ? 'vi' : 'en')}
                            </span>
                            <Button
                              variant="ghost"
                              size="xs"
                              icon={<RotateCcw className="h-3.5 w-3.5" />}
                              onClick={() => void handleRestore(task)}
                              disabled={pendingId === task.id}
                              aria-label={t.tasksPage.restoreTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.restoreTask}
                            </Button>
                          </div>
                        )}
                        {task.status === 'confirmed' && (
                          <>
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() => openTaskEditor(task)}
                              aria-label={t.tasksPage.editTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.editEventAction}
                            </Button>
                            {!task.calendarEventId && task.dueAt && (
                              <Button
                                variant="outline"
                                size="xs"
                                icon={<CalendarDays className="h-3.5 w-3.5" />}
                                onClick={() => void syncTask(task)}
                                disabled={syncingId === task.id}
                                aria-label={t.tasksPage.syncTaskA11y.replace('{title}', task.title)}
                              >
                                {syncingId === task.id ? t.tasksPage.syncing : t.tasksPage.sync}
                              </Button>
                            )}
                            {!task.calendarEventId && !task.dueAt && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--color-text-muted)]" title={t.tasksPage.ambiguousDue}>
                                <Clock3 className="h-3 w-3" /> {t.tasksPage.ambiguousDue}
                              </span>
                            )}
                            <Button
                              variant="ghost"
                              size="xs"
                              icon={<X className="h-3.5 w-3.5" />}
                              onClick={() => setCancellationPrompt(task)}
                              disabled={pendingId === task.id}
                              aria-label={t.tasksPage.cancelTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.cancel}
                            </Button>
                            <Button
                              variant="primary"
                              size="xs"
                              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                              onClick={() => openCompletionPrompt(task)}
                              disabled={pendingId === task.id}
                              aria-label={t.tasksPage.completeTaskA11y.replace('{title}', task.title)}
                            >
                              {t.tasksPage.complete}
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
              {showCompletedArchive && (
                <section className="mt-6 border-t border-[var(--color-border)] pt-4" aria-label={t.tasksPage.completedArchiveTitle}>
                  <div className="mb-3">
                    <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{t.tasksPage.completedArchiveTitle}</h3>
                    <p className="mt-1 text-[11px] text-[var(--color-text-secondary)]">{t.tasksPage.completedArchiveHint}</p>
                  </div>
                  <div className="space-y-3">
                    {filteredCompletedTasks.map((task) => {
                      const sources = taskSources(task);
                      const primarySource = sources[0];
                      const description = task.detail || task.evidence[0]?.evidenceQuote || t.tasksPage.noDescription;
                      return (
                        <article key={task.id} id={`task-inbox-${task.id}`} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)]/45 p-3.5 opacity-75">
                          <div className="flex items-start gap-3">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]" aria-label={primarySource.label}>
                              {resolveBrandIcon(primarySource.key, 'h-5 w-5') ?? <Inbox className="h-5 w-5 text-[var(--color-text-muted)]" />}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-1.5">
                                <Badge variant="success">{t.tasksPage.filterCompleted}</Badge>
                                {renderPriorityBadge(task)}
                              </div>
                              <h3 className="mt-1.5 break-words text-sm font-semibold leading-snug text-[var(--color-text-primary)]">{task.title}</h3>
                              <p className="mt-2 rounded-xl bg-[var(--color-surface)] px-3 py-2.5 text-xs leading-relaxed text-[var(--color-text-secondary)]">{description}</p>
                              {renderAssignmentDetails(task)}
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </section>
              )}
            </div>
          )}
          </div>
        </div>
      </div>
      </div>

      {contextEvent && (
        <div role="menu" tabIndex={-1} aria-label={t.tasksPage.eventContextMenuAria.replace('{title}', contextEvent.title)} onKeyDown={(event) => { if (event.key === 'Escape') setContextEvent(null); }} className="fixed bottom-5 right-5 z-40 flex gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-2 shadow-[var(--shadow-lg)]">
          {isCalendarWritable(contextEvent.calendarId) ? (
            <>
              <Button role="menuitem" size="sm" variant="outline" onClick={() => openEditEvent(contextEvent)}>{t.tasksPage.editEventAction}</Button>
              <Button role="menuitem" size="sm" variant="danger" onClick={() => void removeEvent(contextEvent)} disabled={writingEvent}>{t.tasksPage.deleteEventAction}</Button>
            </>
          ) : (
            <p className="max-w-[16rem] self-center px-2 text-xs text-[var(--color-text-secondary)]">{t.tasksPage.readOnlyCalendarHint}</p>
          )}
          <Button role="menuitem" size="sm" variant="ghost" onClick={() => setContextEvent(null)}>{t.tasksPage.closeAction}</Button>
        </div>
      )}

      {undoOperation !== null && undoOperation.expiresAt > Date.now() && (
        <div role="status" className="fixed bottom-5 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-xl bg-[var(--color-text-primary)] px-4 py-3 text-sm text-[var(--color-on-primary)] shadow-[var(--shadow-lg)]">
          <span>{t.tasksPage.calendarUpdatedToast}</span>
          <button type="button" onClick={() => void undoLastOperation()} className="rounded px-2 py-1 font-semibold underline focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]">{t.tasksPage.undoAction}</button>
        </div>
      )}

      <Dialog
        isOpen={taskDraft !== null}
        onClose={() => setTaskDraft(null)}
        title={t.tasksPage.editTaskTitle}
        footer={
          <>
            <Button variant="ghost" onClick={() => setTaskDraft(null)}>{t.tasksPage.cancel}</Button>
            <Button onClick={() => void saveTaskDraft()} disabled={savingTask || !taskDraft?.title.trim()}>
              {t.tasksPage.saveTask}
            </Button>
          </>
        }
      >
        <label className="block text-sm font-medium">
          {t.tasksPage.taskTitleLabel}
          <input
            aria-label={t.tasksPage.taskTitleLabel}
            value={taskDraft?.title ?? ''}
            onChange={(event) => setTaskDraft((current) => (current ? { ...current, title: event.target.value } : current))}
            className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          {t.tasksPage.taskDetailLabel}
          <textarea
            aria-label={t.tasksPage.taskDetailLabel}
            value={taskDraft?.detail ?? ''}
            onChange={(event) => setTaskDraft((current) => (current ? { ...current, detail: event.target.value } : current))}
            rows={4}
            className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
          />
        </label>
      </Dialog>

      <Dialog
        isOpen={eventDraft !== null}
        onClose={() => setEventDraft(null)}
        title={eventDraft?.event ? t.tasksPage.editEventTitle : t.tasksPage.newEventTitle}
        description={t.tasksPage.eventDialogDesc}
        footer={<>{eventDraft?.event?.deepLink && <Button variant="outline" onClick={() => window.open(eventDraft.event?.deepLink ?? '', '_blank', 'noopener,noreferrer')}>{t.calendarWeek.openInGoogle}</Button>}<Button variant="ghost" onClick={() => setEventDraft(null)}>{t.tasksPage.cancel}</Button><Button onClick={() => void saveEvent()} disabled={writingEvent || !eventDraft?.title.trim()}>{t.tasksPage.saveEvent}</Button></>}
      >
        <label className="block text-sm font-medium">{t.tasksPage.calendarDestinationLabel}<select aria-label={t.tasksPage.calendarDestinationLabel} value={eventDraft?.calendarId ?? 'primary'} onChange={(event) => setEventDraft((current) => current ? { ...current, calendarId: event.target.value } : current)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">{writableCalendars.length > 0 ? writableCalendars.map((calendar) => <option key={calendar.id} value={calendar.id}>{calendar.name}</option>) : <option value="primary">{t.tasksPage.primaryCalendarOption}</option>}</select></label>
        <label className="block text-sm font-medium">{t.tasksPage.eventTitleLabel}<input aria-label={t.tasksPage.eventTitleLabel} value={eventDraft?.title ?? ''} onChange={(event) => setEventDraft((current) => current ? { ...current, title: event.target.value } : current)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" /></label>
        <label className="block text-sm font-medium">{t.tasksPage.eventStartLabel}<input aria-label={t.tasksPage.eventStartLabel} type="datetime-local" value={eventDraft?.startAt ?? ''} onChange={(event) => setEventDraft((current) => current ? { ...current, startAt: event.target.value } : current)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" /></label>
        <label className="block text-sm font-medium">{t.tasksPage.eventEndLabel}<input aria-label={t.tasksPage.eventEndLabel} type="datetime-local" value={eventDraft?.endAt ?? ''} onChange={(event) => setEventDraft((current) => current ? { ...current, endAt: event.target.value } : current)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" /></label>
      </Dialog>

      <Dialog
        isOpen={completionPrompt !== null}
        onClose={() => setCompletionPrompt(null)}
        title={t.tasksPage.actualMinutesQuestion}
        footer={<Button variant="ghost" onClick={() => void completeFromPrompt()}>{t.tasksPage.actualMinutesSkip}</Button>}
      >
        <div className="grid grid-cols-2 gap-2">
          {[
            [15, t.tasksPage.actualMinutes15],
            [30, t.tasksPage.actualMinutes30],
            [60, t.tasksPage.actualMinutes60],
            [120, t.tasksPage.actualMinutes120],
          ].map(([minutes, label]) => (
            <Button key={minutes} variant="outline" onClick={() => void completeFromPrompt(minutes as number)}>{label}</Button>
          ))}
          <Button variant="outline" onClick={() => setCompletionPrompt((current) => current ? { ...current, showCustomInput: true } : current)}>{t.tasksPage.actualMinutesMore}</Button>
        </div>
        {completionPrompt?.showCustomInput && (
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="actual-minutes">{t.tasksPage.actualMinutesInputLabel}</label>
            <input
              id="actual-minutes"
              type="number"
              min="1"
              max="1440"
              value={completionPrompt.customMinutes}
              onChange={(event) => setCompletionPrompt((current) => current ? { ...current, customMinutes: event.target.value } : current)}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
            />
            <Button
              onClick={() => void completeFromPrompt(Number(completionPrompt.customMinutes))}
              disabled={!Number.isInteger(Number(completionPrompt.customMinutes)) || Number(completionPrompt.customMinutes) < 1 || Number(completionPrompt.customMinutes) > 1440}
            >
              {t.tasksPage.actualMinutesSubmit}
            </Button>
          </div>
        )}
      </Dialog>

      <Dialog
        isOpen={cancellationPrompt !== null}
        onClose={() => setCancellationPrompt(null)}
        title={cancellationPrompt === null ? undefined : t.tasksPage.cancelConfirmTitle.replace('{title}', cancellationPrompt.title)}
        footer={
          <>
            <Button variant="ghost" data-autofocus onClick={() => setCancellationPrompt(null)}>
              {t.tasksPage.cancelConfirmKeep}
            </Button>
            <Button variant="danger" onClick={() => void cancelFromPrompt()}>
              {t.tasksPage.cancelConfirmAction}
            </Button>
          </>
        }
      >
        <p><strong>{cancellationPrompt?.title}</strong></p>
        <p>{t.tasksPage.cancelConfirmConsequences}</p>
      </Dialog>

      <Dialog
        isOpen={dueDraft !== null}
        onClose={() => setDueDraft(null)}
        title={t.tasksPage.dueDraftTitle}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDueDraft(null)}>{t.tasksPage.cancel}</Button>
            <Button onClick={() => void saveDueDraft()} disabled={savingDue || !dueDraft?.value}>
              {t.tasksPage.saveDue}
            </Button>
          </>
        }
      >
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={dueDraft?.allDay ?? false}
            onChange={(event) => setDueDraft((current) => (current ? { ...current, allDay: event.target.checked, value: current.value.slice(0, 10) } : current))}
          />
          {t.tasksPage.allDay}
        </label>
        <label className="block text-sm font-medium">
          {t.tasksPage.dueDraftLabel}
          <input
            aria-label={t.tasksPage.dueDraftLabel}
            type={dueDraft?.allDay ? 'date' : 'datetime-local'}
            value={dueDraft?.value ?? ''}
            onChange={(event) => setDueDraft((current) => (current ? { ...current, value: event.target.value } : current))}
            className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
          />
        </label>
      </Dialog>

      <Dialog
        isOpen={rescheduleDraft !== null}
        onClose={() => setRescheduleDraft(null)}
        title={t.tasksPage.rescheduleConfirmTitle}
        description={
          rescheduleDraft?.kind === 'event'
            ? rescheduleDraft.event.title
            : rescheduleDraft?.kind === 'task'
              ? rescheduleDraft.task.title
              : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setRescheduleDraft(null)}>{t.tasksPage.cancel}</Button>
            <Button onClick={() => void confirmReschedule()} disabled={savingReschedule}>
              {savingReschedule ? t.tasksPage.rescheduleSaving : t.tasksPage.rescheduleConfirmAction}
            </Button>
          </>
        }
      >
        {rescheduleDraft && (
          <div className="flex items-center justify-between gap-3 rounded-xl bg-[var(--color-surface-muted)] px-3.5 py-3 text-sm">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">{t.tasksPage.rescheduleFrom}</p>
              <p className="mt-0.5 font-medium tabular-nums text-[var(--color-text-secondary)] line-through decoration-[var(--color-danger)]">
                {(rescheduleDraft.kind === 'event' ? rescheduleDraft.fromStart : rescheduleDraft.fromDue).toLocaleString(locale, {
                  weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                })}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
            <div className="text-right">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">{t.tasksPage.rescheduleTo}</p>
              <p className="mt-0.5 font-medium tabular-nums text-[var(--color-primary)]">
                {(rescheduleDraft.kind === 'event' ? rescheduleDraft.toStart : rescheduleDraft.toDue).toLocaleString(locale, {
                  weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                })}
              </p>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
};
