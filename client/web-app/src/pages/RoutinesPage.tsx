import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  CalendarClock,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  ListChecks,
  LoaderCircle,
  Mail,
  MessageSquare,
  Pause,
  Play,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';

import { Button } from '../components/ui/Button';
import { Toggle } from '../components/ui/Toggle';
import {
  createRoutine,
  deleteRoutine,
  updateRoutine,
  type Routine,
  type RoutineFrequency,
} from '../lib/routinesApi';
import { useAuthStore } from '../stores/useAuthStore';
import { useAppStore } from '../stores/useAppStore';
import { useRoutineStore } from '../stores/useRoutineStore';
import { useTranslation } from '../i18n/useTranslation';

const WEEKDAYS_VI = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật'];
const WEEKDAYS_EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);
const formatHour = (hour: number): string => `${String(hour).padStart(2, '0')}:00`;

type TemplateCategory = 'suggested' | 'calendar' | 'inbox' | 'jira' | 'discord';

type RoutineTemplate = {
  id: string;
  category: TemplateCategory;
  icon: React.ComponentType<{ className?: string }>;
  name: string;
  description: string;
  frequency: RoutineFrequency;
  hour: number;
  dayOfWeek?: number;
  instructions: string;
};

/**
 * Mẫu routine tĩnh, thích nghi đúng nguồn mondaiy thật sự có (Gmail, Calendar,
 * Jira, Discord) — KHÔNG copy nguyên mẫu Littlebird vì mẫu gốc ngụ ý tự ghi ra
 * ứng dụng ngoài (vd tự tạo Gmail draft), vi phạm BR-13. Mọi instructions ở
 * đây đều nói rõ "để tôi duyệt" / "không tự gửi" khi liên quan tới soạn nội dung.
 */
function getTemplates(language: 'vi' | 'en'): RoutineTemplate[] {
  if (language === 'vi') {
    return [
      {
        id: 'daily-digest',
        category: 'suggested',
        icon: Clock3,
        name: 'Tóm tắt việc hôm nay',
        description: 'Tổng hợp việc cần xử lý và việc đang chờ xác nhận mỗi sáng.',
        frequency: 'daily',
        hour: 7,
        instructions: 'Tóm tắt việc cần xử lý và việc đang chờ xác nhận hôm nay, dựa trên task đã có trong tài khoản của tôi.',
      },
      {
        id: 'dont-drop-ball',
        category: 'suggested',
        icon: AlertTriangle,
        name: 'Không bỏ sót việc',
        description: 'Lưới an toàn hằng ngày: việc gì quá hạn, ai đang chờ tôi phản hồi.',
        frequency: 'daily',
        hour: 8,
        instructions: 'Kiểm tra việc quá hạn hoặc đang chờ tôi trả lời/xử lý trong 24 giờ qua. Chỉ nêu việc tôi thực sự là người phải xử lý, bỏ qua việc chỉ liên quan gián tiếp.',
      },
      {
        id: 'inbox-drafts',
        category: 'inbox',
        icon: Mail,
        name: 'Soạn sẵn trả lời email quan trọng',
        description: 'Đọc email hôm nay, soạn sẵn nội dung trả lời để tôi duyệt — không tự gửi.',
        frequency: 'daily',
        hour: 17,
        instructions: 'Đọc email hôm nay, liệt kê email tôi thực sự cần trả lời (bỏ qua email chỉ CC hoặc thông báo tự động), và soạn sẵn nội dung trả lời cho từng email để tôi xem lại trong mondaiy. Không tự gửi.',
      },
      {
        id: 'weekly-focus',
        category: 'calendar',
        icon: CalendarClock,
        name: 'Lên lịch tuần làm việc',
        description: 'Xem lịch tuần tới, đề xuất khung giờ tập trung còn trống.',
        frequency: 'weekly',
        hour: 18,
        dayOfWeek: 6,
        instructions: 'Xem lịch của tôi tuần tới, tìm khung giờ còn trống mỗi ngày và đề xuất 1 khung giờ tập trung 60 phút cho từng ngày.',
      },
      {
        id: 'jira-standup',
        category: 'jira',
        icon: ListChecks,
        name: 'Chuẩn bị standup',
        description: 'Tóm tắt issue Jira của tôi trước standup mỗi sáng.',
        frequency: 'daily',
        hour: 8,
        instructions: 'Xem issue Jira đang gán cho tôi, tóm tắt cái nào đang làm, cái nào bị chặn, cái nào sắp tới hạn — để tôi đọc trước standup.',
      },
      {
        id: 'discord-catchup',
        category: 'discord',
        icon: MessageSquare,
        name: 'Bắt kịp Discord chương trình',
        description: 'Tóm tắt thông báo và tin nhắn quan trọng tôi có thể đã bỏ lỡ.',
        frequency: 'daily',
        hour: 9,
        instructions: 'Xem thông báo chính thức và tin nhắn có nhắc tới tôi trên Discord chương trình từ hôm qua tới giờ, tóm tắt cái nào tôi cần biết hoặc cần trả lời.',
      },
    ];
  }
  return [
    {
      id: 'daily-digest',
      category: 'suggested',
      icon: Clock3,
      name: 'Daily digest',
      description: 'A daily summary of work needing attention and pending confirmations.',
      frequency: 'daily',
      hour: 7,
      instructions: 'Summarize the work that needs attention and tasks pending confirmation today, using what is already in my account.',
    },
    {
      id: 'dont-drop-ball',
      category: 'suggested',
      icon: AlertTriangle,
      name: "Don't let me drop the ball",
      description: 'A daily safety net that checks what is overdue or waiting on me.',
      frequency: 'daily',
      hour: 8,
      instructions: 'Check what is overdue or waiting on my response in the last 24 hours. Only flag items where I am clearly the one who owes an action, skip anything only tangentially about me.',
    },
    {
      id: 'inbox-drafts',
      category: 'inbox',
      icon: Mail,
      name: 'Draft replies to important emails',
      description: "Reads today's emails and drafts replies for me to review — never sends on its own.",
      frequency: 'daily',
      hour: 17,
      instructions: "Read today's emails, list the ones I actually need to reply to (skip CC-only or automated notices), and draft a reply for each so I can review it inside mondaiy. Never send on your own.",
    },
    {
      id: 'weekly-focus',
      category: 'calendar',
      icon: CalendarClock,
      name: 'Weekly focus block scheduler',
      description: 'Scans the upcoming week and suggests a focus block where there is room.',
      frequency: 'weekly',
      hour: 18,
      dayOfWeek: 6,
      instructions: 'Look at my calendar for the upcoming week, find open time each day, and suggest one 60-minute focus block per day where there is room.',
    },
    {
      id: 'jira-standup',
      category: 'jira',
      icon: ListChecks,
      name: 'Standup prep',
      description: 'Summarizes my Jira issues before standup each morning.',
      frequency: 'daily',
      hour: 8,
      instructions: 'Look at Jira issues assigned to me, summarize what is in progress, what is blocked, and what is due soon — for me to read before standup.',
    },
    {
      id: 'discord-catchup',
      category: 'discord',
      icon: MessageSquare,
      name: 'Catch up on program Discord',
      description: 'Summarizes announcements and messages I may have missed.',
      frequency: 'daily',
      hour: 9,
      instructions: 'Look at official announcements and messages that mention me on the program Discord since yesterday, and summarize what I need to know or reply to.',
    },
  ];
}

type ModalStep = 'closed' | 'picker' | 'configure';

/**
 * Routine = automation user tự đặt, chạy agent thật theo lịch
 * (`src/services/routines.py`), đọc nguồn đã kết nối, chỉ tạo bản nháp/tóm
 * tắt để đọc trong mondaiy — không tự ghi ra ứng dụng bên ngoài (BR-13).
 * Luồng UI theo 2 bước: chọn "tạo từ đầu" hoặc mẫu có sẵn (picker), rồi
 * chỉnh chi tiết + lưu (configure) — giữ đúng màu/token hiện có của mondaiy.
 */
export const RoutinesPage: React.FC = () => {
  const navigate = useNavigate();
  // Trả về từng primitive riêng để React/Zustand giữ snapshot ổn định. Selector
  // object tạo object mới sau mỗi render và có thể gây React error #185
  // (maximum update depth exceeded) trên route Routines.
  const accessToken = useAuthStore((state) => state.accessToken);
  const userKey = useAuthStore((state) => state.user?.id ?? state.user?.email ?? state.accessToken);
  const { addToast } = useAppStore();
  const { routines, ensureLoaded, upsertRoutine, removeRoutine: removeCachedRoutine } = useRoutineStore();
  const { language } = useTranslation();
  const weekdayNames = language === 'vi' ? WEEKDAYS_VI : WEEKDAYS_EN;
  const templates = useMemo(() => getTemplates(language), [language]);

  const copy = language === 'vi'
    ? {
        title: 'Routines', newRoutine: 'Routine mới', yourRoutines: 'Routine của bạn',
        heroTitle: 'Đặt lịch cho AI của bạn', heroSubtitle: 'Mô tả việc bạn muốn thu thập, chọn lịch chạy — mondaiy gửi kết quả tới đây khi xong.',
        libraryTitle: 'Xem thư viện', setUp: 'Thiết lập',
        startFromScratch: 'Tạo từ đầu', startFromScratchHint: 'Tự xây routine của bạn — mô tả việc cần làm và khi nào chạy.',
        orStartTemplate: 'Hoặc bắt đầu từ mẫu', createPickerTitle: 'Tạo routine mới', createPickerHint: 'Routine chạy theo lịch và gửi kết quả để bạn xem lại.',
        configureTitle: 'Cấu hình routine', configureHint: 'Chỉnh chi tiết rồi tạo routine.',
        customRoutine: 'Routine tùy chỉnh', changeTemplate: 'Đổi mẫu',
        nameLabel: 'Tên', namePlaceholder: 'Vd: Tóm tắt email quan trọng',
        instructionsLabel: 'Hướng dẫn', instructionsHint: 'Mô tả việc bạn muốn mondaiy thu thập, phân tích hoặc tóm tắt.',
        instructionsPlaceholder: 'Vd: Đọc email hôm nay, liệt kê việc cần trả lời và soạn sẵn nội dung trả lời.',
        scheduleLabel: 'Lịch chạy', frequencyDaily: 'Hằng ngày', frequencyWeekly: 'Hằng tuần', frequencyMonthly: 'Hằng tháng',
        dayOfWeekLabel: 'Vào ngày', dayOfMonthLabel: 'Vào ngày (trong tháng)',
        notificationsLabel: 'Thông báo', notificationsHint: 'Báo khi có kết quả mới.',
        emailLabel: 'Email', emailHint: 'Gửi email khi có kết quả mới.',
        create: 'Tạo routine', cancel: 'Hủy', noRoutinesYet: 'Chưa có routine nào.',
        runNow: 'Chạy thử ngay', active: 'Đang bật', paused: 'Đã tạm dừng',
        pause: 'Tạm dừng', resume: 'Bật lại', deleteRoutine: 'Xoá routine', at: 'lúc', timezone: 'theo múi giờ',
        safetyNote: 'Chỉ tạo bản nháp/tóm tắt trong mondaiy — không tự gửi email hay ghi vào ứng dụng khác.',
        loadError: 'Không tải được routine. Hãy thử lại.', saveError: 'Không lưu được routine. Hãy thử lại.',
        categories: { suggested: 'Đề xuất', calendar: 'Lịch', inbox: 'Hộp thư', jira: 'Jira', discord: 'Discord' },
        searchPlaceholder: 'Tìm routine...', filterAll: 'Tất cả', sortLabel: 'Sắp xếp', sortRecent: 'Mới cập nhật', sortName: 'Tên A–Z', routineCount: 'routine', lastRun: 'Lần chạy gần nhất', neverRun: 'Chưa chạy', noMatches: 'Không tìm thấy routine phù hợp', noMatchesHint: 'Thử đổi từ khóa hoặc bộ lọc.',
      }
    : {
        title: 'Routines', newRoutine: 'New routine', yourRoutines: 'Your routines',
        heroTitle: 'Set your AI on a schedule', heroSubtitle: "Describe what you want to gather, pick a schedule, and mondaiy delivers a note when it's ready.",
        libraryTitle: 'Browse the library', setUp: 'Set up',
        startFromScratch: 'Start from scratch', startFromScratchHint: 'Build your own routine — describe what to gather and when',
        orStartTemplate: 'Or start with a template', createPickerTitle: 'Create a new routine', createPickerHint: 'Routines run on a schedule and deliver a note you can review later.',
        configureTitle: 'Configure routine', configureHint: 'Adjust the details, then create the routine.',
        customRoutine: 'Custom routine', changeTemplate: 'Change template',
        nameLabel: 'Name', namePlaceholder: 'e.g. Summarize important emails',
        instructionsLabel: 'Instructions', instructionsHint: "Describe what you'd like mondaiy to gather, analyze, or summarize.",
        instructionsPlaceholder: "e.g. Read today's emails, list the ones I should reply to, and draft a reply for each.",
        scheduleLabel: 'Schedule', frequencyDaily: 'Daily', frequencyWeekly: 'Weekly', frequencyMonthly: 'Monthly',
        dayOfWeekLabel: 'On day', dayOfMonthLabel: 'On day of month',
        notificationsLabel: 'Notifications', notificationsHint: 'Push when a new report is ready.',
        emailLabel: 'Email', emailHint: 'Email me when a new report is ready.',
        create: 'Create routine', cancel: 'Cancel', noRoutinesYet: 'No routines yet.',
        runNow: 'Run now', active: 'Active', paused: 'Paused',
        pause: 'Pause', resume: 'Resume', deleteRoutine: 'Delete routine', at: 'at', timezone: 'in',
        safetyNote: 'Only drafts or summarizes inside mondaiy — never sends email or writes to other apps on its own.',
        loadError: 'Could not load routines. Please retry.', saveError: 'Could not save the routine. Please retry.',
        categories: { suggested: 'Suggested', calendar: 'Calendar', inbox: 'Inbox', jira: 'Jira', discord: 'Discord' },
        searchPlaceholder: 'Search routines...', filterAll: 'All', sortLabel: 'Sort', sortRecent: 'Recently updated', sortName: 'Name A–Z', routineCount: 'routines', lastRun: 'Last run', neverRun: 'Not run yet', noMatches: 'No routines match', noMatchesHint: 'Try another search or filter.',
      };

  const [routinesLoading, setRoutinesLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [modalStep, setModalStep] = useState<ModalStep>('closed');
  const [libraryTab, setLibraryTab] = useState<TemplateCategory>('suggested');
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formName, setFormName] = useState('');
  const [formInstructions, setFormInstructions] = useState('');
  const [formFrequency, setFormFrequency] = useState<RoutineFrequency>('daily');
  const [formHour, setFormHour] = useState(8);
  const [formDayOfWeek, setFormDayOfWeek] = useState(0);
  const [formDayOfMonth, setFormDayOfMonth] = useState(1);
  const [formNotifyPush, setFormNotifyPush] = useState(true);
  const [formNotifyEmail, setFormNotifyEmail] = useState(false);
  const [hourPickerOpen, setHourPickerOpen] = useState(false);
  const hourPickerRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [frequencyFilter, setFrequencyFilter] = useState<'all' | RoutineFrequency>('all');
  const [sortMode, setSortMode] = useState<'recent' | 'name'>('recent');

  // Đóng popover giờ khi bấm ra ngoài — <select> gốc để trình duyệt tự vẽ
  // danh sách 24 mục, tràn hết màn hình và không theo được theme; thay bằng
  // popover tự vẽ nên cần tự lo việc đóng khi bấm ra ngoài.
  useEffect(() => {
    if (!hourPickerOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!hourPickerRef.current?.contains(event.target as Node)) setHourPickerOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [hourPickerOpen]);

  const reload = async (force = false) => {
    if (!accessToken || !userKey) return;
    setRoutinesLoading(true);
    setLoadError(null);
    try {
      await ensureLoaded(accessToken, userKey, force);
    } catch {
      setLoadError(copy.loadError);
    } finally {
      setRoutinesLoading(false);
    }
  };

  useEffect(() => { void reload(); }, [accessToken, userKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const resetForm = () => {
    setFormName('');
    setFormInstructions('');
    setFormFrequency('daily');
    setFormHour(8);
    setFormDayOfWeek(0);
    setFormDayOfMonth(1);
    setFormNotifyPush(true);
    setFormNotifyEmail(false);
  };

  const openPicker = () => {
    setActiveTemplateId(null);
    setModalStep('picker');
  };

  const closeModal = () => setModalStep('closed');

  const openScratch = () => {
    resetForm();
    setActiveTemplateId(null);
    setModalStep('configure');
  };

  const openFromTemplate = (template: RoutineTemplate) => {
    setFormName(template.name);
    setFormInstructions(template.instructions);
    setFormFrequency(template.frequency);
    setFormHour(template.hour);
    setFormDayOfWeek(template.dayOfWeek ?? 0);
    setFormDayOfMonth(1);
    setFormNotifyPush(true);
    setFormNotifyEmail(false);
    setActiveTemplateId(template.id);
    setModalStep('configure');
  };

  const activeTemplate = templates.find((template) => template.id === activeTemplateId) ?? null;

  const submitCreate = async () => {
    if (!accessToken || !formName.trim() || !formInstructions.trim()) return;
    setSaving(true);
    try {
      const created = await createRoutine(accessToken, {
        name: formName.trim(),
        instructions: formInstructions.trim(),
        frequency: formFrequency,
        hour: formHour,
        dayOfWeek: formFrequency === 'weekly' ? formDayOfWeek : undefined,
        dayOfMonth: formFrequency === 'monthly' ? formDayOfMonth : undefined,
        notifyPush: formNotifyPush,
        notifyEmail: formNotifyEmail,
      });
      upsertRoutine(created);
      closeModal();
    } catch {
      addToast({ type: 'error', title: copy.title, message: copy.saveError });
    } finally {
      setSaving(false);
    }
  };

  const toggleRoutineEnabled = async (routine: Routine) => {
    if (!accessToken) return;
    const updated = await updateRoutine(accessToken, routine.id, { enabled: !routine.enabled });
    upsertRoutine(updated);
  };

  const removeRoutine = async (routine: Routine) => {
    if (!accessToken) return;
    await deleteRoutine(accessToken, routine.id);
    removeCachedRoutine(routine.id);
  };

  const runNow = (routine: Routine) => {
    // Trang chi tiết tự chạy đúng một lần; chạy trước ở đây rồi điều hướng sẽ
    // tạo hai RoutineRun cho cùng một lần bấm.
    navigate(`/routines/${routine.id}`);
  };

  const describeSchedule = (routine: Routine): string => {
    const at = `${copy.at} ${formatHour(routine.hour)} ${copy.timezone} ${routine.timezone}`;
    if (routine.frequency === 'weekly' && routine.dayOfWeek !== null) {
      return `${copy.frequencyWeekly} · ${weekdayNames[routine.dayOfWeek]} · ${at}`;
    }
    if (routine.frequency === 'monthly' && routine.dayOfMonth !== null) {
      return `${copy.frequencyMonthly} · ${copy.dayOfMonthLabel} ${routine.dayOfMonth} · ${at}`;
    }
    return `${copy.frequencyDaily} · ${at}`;
  };

  const categoryOrder: TemplateCategory[] = ['suggested', 'calendar', 'inbox', 'jira', 'discord'];
  const visibleTemplates = templates.filter((template) => template.category === libraryTab);
  const filteredRoutines = useMemo(() => routines
    .filter((routine) => frequencyFilter === 'all' || routine.frequency === frequencyFilter)
    .filter((routine) => `${routine.name} ${routine.instructions}`.toLowerCase().includes(searchQuery.trim().toLowerCase()))
    .sort((a, b) => {
      if (sortMode === 'name') return a.name.localeCompare(b.name, language === 'vi' ? 'vi' : 'en');
      return (b.lastRunDate ?? '').localeCompare(a.lastRunDate ?? '') || b.id - a.id;
    }), [frequencyFilter, language, routines, searchQuery, sortMode]);

  const frequencyLabel = (frequency: RoutineFrequency): string => frequency === 'daily' ? copy.frequencyDaily : frequency === 'weekly' ? copy.frequencyWeekly : copy.frequencyMonthly;

  const TemplateCard: React.FC<{ template: RoutineTemplate }> = ({ template }) => {
    const Icon = template.icon;
    return (
      <div data-testid={`template-${template.id}`} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{template.name}</h3>
            <p className="mt-1 line-clamp-2 text-xs text-[var(--color-text-secondary)]">{template.description}</p>
          </div>
        </div>
        <div className="mt-3 flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--color-accent-soft)] text-[var(--color-primary)]">
          <Icon className="h-4 w-4" />
        </div>
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-[var(--color-border)] pt-3">
          <p className="flex items-center gap-1 text-[11px] text-[var(--color-text-muted)]">
            <Clock3 className="h-3 w-3" />
            {template.frequency === 'weekly'
              ? `${copy.frequencyWeekly} ${formatHour(template.hour)}`
              : `${copy.frequencyDaily} ${formatHour(template.hour)}`}
          </p>
          <Button size="xs" variant="outline" icon={<Plus className="h-3 w-3" />} onClick={() => openFromTemplate(template)}>
            {copy.setUp}
          </Button>
        </div>
      </div>
    );
  };

  const Library: React.FC = () => (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">{copy.libraryTitle}</h2>
      <div className="mt-3 flex flex-wrap gap-1 border-b border-[var(--color-border)]">
        {categoryOrder.map((category) => (
          <button
            key={category}
            type="button"
            className={`px-3 py-2 text-sm font-medium ${
              libraryTab === category
                ? 'border-b-2 border-[var(--color-primary)] text-[var(--color-text-primary)]'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
            }`}
            onClick={() => setLibraryTab(category)}
          >
            {copy.categories[category]}
          </button>
        ))}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {visibleTemplates.map((template) => <TemplateCard key={template.id} template={template} />)}
      </div>
    </section>
  );

  return (
    <div className="mx-auto w-full max-w-6xl">
      <header data-tour-id="routines-header" className="mb-8 flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]"><CalendarDays className="h-3.5 w-3.5" /> {copy.title}</p>
          <h1 className="font-display text-4xl leading-none tracking-tight text-[var(--color-text-primary)] sm:text-5xl">{copy.heroTitle}</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--color-text-secondary)]">{copy.heroSubtitle}</p>
        </div>
        <Button
          size="lg"
          icon={<Plus className="h-4 w-4" />}
          onClick={openPicker}
          disabled={routinesLoading}
          data-tour-id="routines-new-button"
        >
          {copy.newRoutine}
        </Button>
      </header>

      <nav aria-label="Kế hoạch" className="mb-6 flex w-fit rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-1 text-sm font-semibold">
        <button type="button" onClick={() => navigate('/planner')} className="rounded-lg px-3 py-2 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]">Hôm nay & tuần này</button>
        <button type="button" aria-current="page" className="rounded-lg bg-[var(--color-surface)] px-3 py-2 text-[var(--color-primary)] shadow-[var(--shadow-sm)]">Nhịp lặp lại</button>
      </nav>

      {loadError && (
        <div role="alert" className="mb-6 rounded-xl border border-[var(--color-danger)]/35 bg-[var(--color-danger)]/10 p-4 text-sm text-[var(--color-text-primary)]">
          {loadError} <Button size="xs" variant="outline" className="ml-2" onClick={() => void reload()}>{language === 'vi' ? 'Thử lại' : 'Retry'}</Button>
        </div>
      )}

      {routinesLoading ? (
        <section aria-label={copy.yourRoutines} className="mb-10 grid gap-3 md:grid-cols-2">
          {[1, 2, 3].map((item) => <div key={item} className="h-40 animate-pulse rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)]" />)}
        </section>
      ) : routines.length === 0 ? (
        <div className="mb-10 rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-10 text-center">
          <div className="mx-auto flex w-fit items-center gap-2 rounded-xl bg-[var(--color-accent-soft)] p-3 text-[var(--color-primary)]"><Clock3 className="h-5 w-5" /><Sparkles className="h-5 w-5" /><ListChecks className="h-5 w-5" /></div>
          <h2 className="mt-4 font-display text-xl text-[var(--color-text-primary)]">{copy.heroTitle}</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-[var(--color-text-secondary)]">{copy.heroSubtitle}</p>
        </div>
      ) : (
        <section className="mb-10">
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div><h2 className="text-lg font-semibold text-[var(--color-text-primary)]">{copy.yourRoutines}</h2><p className="mt-1 text-xs text-[var(--color-text-muted)]">{filteredRoutines.length} {copy.routineCount}</p></div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="flex min-w-60 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm focus-within:border-[var(--color-primary)]">
                <Search className="h-4 w-4 text-[var(--color-text-muted)]" /><span className="sr-only">{copy.searchPlaceholder}</span><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder={copy.searchPlaceholder} className="min-w-0 flex-1 bg-transparent text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]" />
              </label>
              <div className="flex items-center gap-1 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1">
                {(['all', 'daily', 'weekly', 'monthly'] as const).map((option) => <button key={option} type="button" onClick={() => setFrequencyFilter(option)} className={`whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors ${frequencyFilter === option ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'}`}>{option === 'all' ? copy.filterAll : frequencyLabel(option)}</button>)}
              </div>
              <label className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-secondary)]"><SlidersHorizontal className="h-3.5 w-3.5" /><span className="sr-only">{copy.sortLabel}</span><select value={sortMode} onChange={(event) => setSortMode(event.target.value as 'recent' | 'name')} className="bg-transparent text-[var(--color-text-primary)] outline-none"><option value="recent">{copy.sortRecent}</option><option value="name">{copy.sortName}</option></select></label>
            </div>
          </div>
          {filteredRoutines.length === 0 ? <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-10 text-center"><Search className="mx-auto h-6 w-6 text-[var(--color-text-muted)]" /><p className="mt-3 text-sm font-semibold text-[var(--color-text-primary)]">{copy.noMatches}</p><p className="mt-1 text-xs text-[var(--color-text-secondary)]">{copy.noMatchesHint}</p></div> : <div className="grid gap-3 md:grid-cols-2">
            {filteredRoutines.map((routine) => {
              return (
                <div
                  key={routine.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/routines/${routine.id}`)}
                  onKeyDown={(event) => { if (event.key === 'Enter') navigate(`/routines/${routine.id}`); }}
                  className="group flex min-h-40 cursor-pointer flex-col justify-between gap-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)] transition-[transform,background-color,box-shadow] duration-300 hover:-translate-y-0.5 hover:bg-[var(--color-surface-hover)] hover:shadow-[var(--shadow-md)]"
                >
                  <div className="flex min-w-0 gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent-soft)] text-[var(--color-primary)]"><Sparkles className="h-5 w-5" /></div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-[var(--color-text-primary)]">{routine.name}</h3>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${routine.enabled ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' : 'bg-[var(--color-accent-soft)] text-[var(--color-text-secondary)]'}`}>
                          {routine.enabled ? copy.active : copy.paused}
                        </span>
                      </div>
                      <p className="mt-1 truncate text-sm text-[var(--color-text-secondary)]">{routine.instructions}</p>
                      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--color-text-muted)]"><Clock3 className="h-3.5 w-3.5" />{describeSchedule(routine)}<span className="text-[var(--color-border-strong)]">·</span><span>{routine.lastRunDate ? `${copy.lastRun} ${new Date(routine.lastRunDate).toLocaleDateString(language === 'vi' ? 'vi-VN' : 'en-GB')}` : copy.neverRun}</span></p>
                    </div>
                  </div>
                  {/* stopPropagation: bấm hành động không được kéo theo điều hướng sang trang chi tiết. */}
                  <div className="flex shrink-0 items-center justify-between gap-1.5 border-t border-[var(--color-border-subtle)] pt-3" onClick={(event) => event.stopPropagation()}>
                    <span className="text-xs font-medium text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)]">{copy.runNow} <span aria-hidden>→</span></span>
                    <Button size="xs" variant="outline" onClick={() => runNow(routine)}>
                      {copy.runNow}
                    </Button>
                    <button type="button" className="app-icon-button p-1.5 rounded-lg" aria-label={routine.enabled ? copy.pause : copy.resume} title={routine.enabled ? copy.pause : copy.resume} onClick={() => void toggleRoutineEnabled(routine)}>
                      {routine.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </button>
                    <button type="button" className="app-icon-button p-1.5 rounded-lg" aria-label={copy.deleteRoutine} title={copy.deleteRoutine} onClick={() => void removeRoutine(routine)}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>}
        </section>
      )}

      {!routinesLoading && <Library />}

      {modalStep === 'picker' && (
        <div
          className="app-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label={copy.createPickerTitle}
          data-tour-id="routines-create-modal"
        >
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-2xl text-[var(--color-text-primary)]">{copy.createPickerTitle}</h2>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{copy.createPickerHint}</p>
              </div>
              <button
                className="app-icon-button p-1.5 rounded-lg"
                aria-label={copy.cancel}
                onClick={closeModal}
                data-tour-id="routines-modal-close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <button
              type="button"
              onClick={openScratch}
              className="mt-6 flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] p-4 text-left hover:bg-[var(--color-surface-hover)]"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-accent-soft)] text-[var(--color-primary)]"><Plus className="h-4 w-4" /></div>
                <div>
                  <p className="font-semibold text-[var(--color-text-primary)]">{copy.startFromScratch}</p>
                  <p className="text-xs text-[var(--color-text-secondary)]">{copy.startFromScratchHint}</p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
            </button>

            <p className="mt-6 text-sm font-medium text-[var(--color-text-secondary)]">{copy.orStartTemplate}</p>
            <div className="mt-3 flex flex-wrap gap-1 border-b border-[var(--color-border)]">
              {categoryOrder.map((category) => (
                <button
                  key={category}
                  type="button"
                  className={`px-3 py-2 text-sm font-medium ${
                    libraryTab === category
                      ? 'border-b-2 border-[var(--color-primary)] text-[var(--color-text-primary)]'
                      : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
                  }`}
                  onClick={() => setLibraryTab(category)}
                >
                  {copy.categories[category]}
                </button>
              ))}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {visibleTemplates.map((template) => <TemplateCard key={template.id} template={template} />)}
            </div>
          </div>
        </div>
      )}

      {modalStep === 'configure' && (
        <div className="app-overlay fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={copy.configureTitle}>
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-2xl text-[var(--color-text-primary)]">{copy.configureTitle}</h2>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{copy.configureHint}</p>
              </div>
              <button className="app-icon-button p-1.5 rounded-lg" aria-label={copy.cancel} onClick={closeModal}><X className="h-4 w-4" /></button>
            </div>

            <div className="mt-6 flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] p-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-accent-soft)] text-[var(--color-primary)]">
                  {activeTemplate ? <activeTemplate.icon className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                </div>
                <div>
                  <p className="font-semibold text-[var(--color-text-primary)]">{activeTemplate?.name ?? copy.customRoutine}</p>
                  <p className="text-xs text-[var(--color-text-secondary)]">
                    {formFrequency === 'weekly' ? copy.frequencyWeekly : formFrequency === 'monthly' ? copy.frequencyMonthly : copy.frequencyDaily} · {formatHour(formHour)}
                  </p>
                </div>
              </div>
              <button type="button" className="flex shrink-0 items-center gap-1 text-xs font-semibold text-[var(--color-primary)] hover:underline" onClick={() => setModalStep('picker')}>
                <ChevronRight className="h-3.5 w-3.5 rotate-180" />{copy.changeTemplate}
              </button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-primary)]">
                  {copy.nameLabel}
                  <input
                    className="mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-app-bg)] px-3 py-2 text-sm"
                    value={formName}
                    placeholder={copy.namePlaceholder}
                    onChange={(event) => setFormName(event.target.value)}
                  />
                </label>

                <p className="mt-5 text-sm font-medium text-[var(--color-text-primary)]">{copy.scheduleLabel}</p>
                <div className="mt-1.5 inline-flex rounded-lg border border-[var(--color-border)] p-1">
                  {(['daily', 'weekly', 'monthly'] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                        formFrequency === option ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)]'
                      }`}
                      onClick={() => setFormFrequency(option)}
                    >
                      {option === 'daily' ? copy.frequencyDaily : option === 'weekly' ? copy.frequencyWeekly : copy.frequencyMonthly}
                    </button>
                  ))}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <div className="relative" ref={hourPickerRef}>
                    <button
                      type="button"
                      aria-haspopup="listbox"
                      aria-expanded={hourPickerOpen}
                      onClick={() => setHourPickerOpen((open) => !open)}
                      className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-app-bg)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
                    >
                      <Clock3 className="h-4 w-4 text-[var(--color-text-muted)]" />
                      {formatHour(formHour)}
                      <ChevronDown className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
                    </button>
                    {hourPickerOpen && (
                      <div role="listbox" aria-label={copy.scheduleLabel} className="absolute left-0 top-full z-10 mt-1 max-h-56 w-28 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg">
                        {HOURS.map((value) => (
                          <button
                            key={value}
                            type="button"
                            role="option"
                            aria-selected={value === formHour}
                            onClick={() => { setFormHour(value); setHourPickerOpen(false); }}
                            className={`block w-full px-3 py-1.5 text-left text-sm ${
                              value === formHour
                                ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]'
                                : 'text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]'
                            }`}
                          >
                            {formatHour(value)}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {formFrequency === 'weekly' && (
                    <label className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                      {copy.dayOfWeekLabel}
                      <select
                        aria-label={copy.dayOfWeekLabel}
                        className="bg-transparent"
                        value={formDayOfWeek}
                        onChange={(event) => setFormDayOfWeek(Number(event.target.value))}
                      >
                        {weekdayNames.map((label, index) => <option key={label} value={index}>{label}</option>)}
                      </select>
                    </label>
                  )}

                  {formFrequency === 'monthly' && (
                    <label className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                      {copy.dayOfMonthLabel}
                      <input
                        type="number"
                        min={1}
                        max={31}
                        aria-label={copy.dayOfMonthLabel}
                        className="w-14 bg-transparent"
                        value={formDayOfMonth}
                        onChange={(event) => setFormDayOfMonth(Number(event.target.value))}
                      />
                    </label>
                  )}
                </div>

                <div className="mt-5 flex items-center justify-between gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">{copy.notificationsLabel}</p>
                    <p className="text-xs text-[var(--color-text-secondary)]">{copy.notificationsHint}</p>
                  </div>
                  <Toggle checked={formNotifyPush} onChange={setFormNotifyPush} aria-label={copy.notificationsLabel} />
                </div>
                <div className="mt-2 flex items-center justify-between gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">{copy.emailLabel}</p>
                    <p className="text-xs text-[var(--color-text-secondary)]">{language === 'vi' ? 'Email chưa khả dụng; kết quả chỉ gửi qua thông báo trong ứng dụng.' : 'Email delivery is not available yet; results are delivered in-app only.'}</p>
                  </div>
                  <Toggle checked={false} onChange={() => undefined} aria-label={copy.emailLabel} disabled />
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-[var(--color-text-primary)]">{copy.instructionsLabel}</p>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{copy.instructionsHint}</p>
                <label className="sr-only" htmlFor="routine-instructions">{copy.instructionsLabel}</label>
                <textarea
                  id="routine-instructions"
                  className="mt-1.5 h-56 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-app-bg)] px-3 py-2 text-sm"
                  value={formInstructions}
                  placeholder={copy.instructionsPlaceholder}
                  onChange={(event) => setFormInstructions(event.target.value)}
                />
              </div>
            </div>

            <p className="mt-4 text-xs text-[var(--color-text-muted)]">{copy.safetyNote}</p>

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="ghost" onClick={closeModal} disabled={saving}>{copy.cancel}</Button>
              <Button
                icon={saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                onClick={() => void submitCreate()}
                disabled={saving || !formName.trim() || !formInstructions.trim()}
              >
                {copy.create}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
