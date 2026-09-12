import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { useTranslation } from '../i18n/useTranslation';
import { useAppStore } from '../stores/useAppStore';
import { useConversationStore } from '../stores/useConversationStore';
import { useAuthStore } from '../stores/useAuthStore';
import { getConnections, getGmailSources, getGmailStatus, getIntegrations, isGmailBriefingIntent } from '../lib/gmailApi';
import { createGmailRun, extractGmailDateRange, getRunBrief, streamRunEvents, waitForRun } from '../lib/runApi';
import { isPrimaryGmailSource } from '../lib/sourceListState';
import { Button } from '../components/ui/Button';
import {
  approveProductivityAction,
  rejectProductivityAction,
  streamConversationMessage,
} from '../lib/conversationApi';
import { AgentStreamError, type AgentProgressEvent } from '../lib/agentStream';
import { MarkdownBody } from '../components/marketing/MarkdownBody';
import { FeedbackActions } from '../components/briefing/FeedbackActions';
import { AgentActivity } from '../components/briefing/AgentActivity';
import { ProductivityApprovalCard } from '../components/briefing/ProductivityApprovalCard';
import { ChatTaskDraftCard } from '../components/briefing/ChatTaskDraftCard';
import { ChatTaskSuggestionCard } from '../components/briefing/ChatTaskSuggestionCard';
import { ProgramQuestionEscalation } from '../components/briefing/ProgramQuestionEscalation';
import { VoiceInputTrigger, VoiceListeningBar } from '../components/briefing/VoiceInputControl';
import { useMicLevelMeter } from '../hooks/useMicLevelMeter';
import { recordMeaningfulAction, requestProductRating } from '../hooks/useProductRating';
import { shouldShowMessageQuickActions } from '../lib/briefingActionIntent';
import {
  getSpeechRecognitionConstructor,
  isMobileViewport,
  playLocalAgentCue,
  readMobileAudioCueSetting,
  selectAgentAudioCue,
  writeMobileAudioCueSetting,
  type BrowserSpeechRecognition,
} from '../lib/mobileVoiceAgent';
import {
  Sparkles,
  Send,
  Paperclip,
  CheckCircle2,
  ExternalLink,
  Clock,
  Calendar as CalendarIcon,
  ShieldCheck,
  ChevronRight,
  PanelRightClose,
  FolderPlus,
  Volume2,
  VolumeX,
  CircleAlert,
  ArrowDown,
  Copy,
  Square,
  } from 'lucide-react';
import { resolveBrandIcon } from '../components/ui/BrandIcons';
import { usePipelineRunStore } from '../stores/usePipelineRunStore';
import { ENABLED_PROVIDERS, PROVIDER_LABEL } from '../types/pipeline';
import { listCalendarEvents, listTasks, type CalendarEvent, type Task } from '../lib/tasksApi';
import { type RoutineRun } from '../lib/routinesApi';
import { useRoutineStore } from '../stores/useRoutineStore';
import { extractGoogleSheetsUrl, saveGoogleSheetPrefill } from '../lib/googleSheetsIntent';
import { extractGoogleDocsUrl, saveGoogleDocPrefill } from '../lib/googleDocsIntent';
import { GoogleSheetsConnectCard } from '../components/briefing/GoogleSheetsConnectCard';
import { GoogleDocsConnectCard } from '../components/briefing/GoogleDocsConnectCard';
import { runVisionAction } from '../lib/visionApi';
import { VisionCalendarBatchCard } from '../components/briefing/VisionCalendarBatchCard';
import { TaskImportTool } from '../components/briefing/TaskImportTool';
import { ProjectSuggestionCard } from '../components/briefing/ProjectSuggestionCard';
import { streamRunEvents as streamSyncEvents, triggerChatSync } from '../lib/runsApi';
import { imageFileFromClipboard } from '../lib/imageClipboard';
import { API_BASE_URL } from '../lib/apiClient';
import { shortcutLabel } from '../lib/keyboardShortcuts';
import { readChatHandoff, readChatImageHandoff } from '../lib/chatHandoff';

const AT_A_GLANCE_KEY = 'mondaiy.atAGlanceOpen';
const COLD_START_INVITE_KEY = 'mondaiy.no-data-invite-dismissed.v1';

function coldStartInviteKey(userId: string): string {
  return `${COLD_START_INVITE_KEY}.${userId}`;
}

function readColdStartInviteDismissed(userId: string | undefined): boolean {
  if (!userId) return false;
  try {
    return localStorage.getItem(coldStartInviteKey(userId)) === 'true';
  } catch {
    return false;
  }
}

function writeColdStartInviteDismissed(userId: string | undefined): void {
  if (!userId) return;
  try {
    localStorage.setItem(coldStartInviteKey(userId), 'true');
  } catch {
    // Không chặn thao tác người dùng khi private mode/quota không cho ghi.
  }
}

type ColdStartTimeSlot =
  | 'overnight'
  | 'morning'
  | 'late-morning'
  | 'midday'
  | 'afternoon'
  | 'evening'
  | 'late-night';

function getColdStartTimeSlot(hour: number): ColdStartTimeSlot {
  if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
    throw new RangeError(`Cold-start hour must be an integer from 0 to 23; received ${hour}.`);
  }
  if (hour < 5) return 'overnight';
  if (hour < 9) return 'morning';
  if (hour < 12) return 'late-morning';
  if (hour < 14) return 'midday';
  if (hour < 18) return 'afternoon';
  if (hour < 22) return 'evening';
  return 'late-night';
}

function formatEventWhen(event: CalendarEvent, language: string): string {
  const start = new Date(event.startAt);
  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';
  if (event.allDay) {
    return start.toLocaleDateString(locale, { day: '2-digit', month: 'short' });
  }
  return start.toLocaleString(locale, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function isToday(iso: string, now = new Date()): boolean {
  const date = new Date(iso);
  return date.toDateString() === now.toDateString();
}

function isWithinNextWeek(iso: string | null, now = new Date()): boolean {
  if (!iso) return false;
  const dueAt = new Date(iso).getTime();
  return dueAt >= now.getTime() && dueAt <= now.getTime() + 7 * 24 * 60 * 60 * 1000;
}

function isRetroPlanningIntent(text: string): boolean {
  const normalized = text.toLocaleLowerCase('vi-VN');
  return /(retro|đã làm gì hôm nay|hôm nay.*(đã làm|làm được|hoàn thành)|tổng kết hôm nay|tuần này.*(làm gì|ưu tiên|kế hoạch)|nên làm gì.*tuần)/u.test(normalized);
}

function agentPromptFor(text: string): string {
  if (!isRetroPlanningIntent(text)) return text;
  return `${text}\n\nĐây là yêu cầu Retro và lập kế hoạch tuần. Hãy đọc task thật của người dùng, tóm tắt việc đã hoàn thành hôm nay, chỉ ra việc còn dang dở và đề xuất các việc nên làm trong 7 ngày tới theo thứ tự ưu tiên. Không tự bịa task hoặc trạng thái.`;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

function inlineAgentError(language: string, error?: unknown): string {
  if (error instanceof AgentStreamError && error.status === 429) {
    requestProductRating();
    return error.message;
  }
  return language === 'vi'
    ? 'Tôi chưa thể trả lời ngay lúc này. Vui lòng thử lại; nếu lỗi tiếp diễn, hãy kiểm tra trạng thái các nguồn đã kết nối.'
    : 'I could not answer just now. Please try again; if the problem continues, check your connected sources.';
}

function inlineGmailError(language: string, status?: string): string {
  if (language === 'vi') {
    return status === 'syncing'
      ? 'Gmail đang bận xử lý. Vui lòng thử lại sau ít phút.'
      : 'Để tôi tổng hợp email, bạn hãy kết nối Gmail trong Quản lý nguồn.';
  }
  return status === 'syncing'
    ? 'Gmail is busy processing a request. Please try again in a moment.'
    : 'To summarize your email, connect Gmail in Sources.';
}

function inlineGmailRunError(language: string): string {
  return language === 'vi'
    ? 'Tôi chưa thể tổng hợp Gmail ngay lúc này. Vui lòng thử lại sau.'
    : 'I could not summarize Gmail right now. Please try again later.';
}

function readAtAGlanceOpen(): boolean {
  try {
    const raw = localStorage.getItem(AT_A_GLANCE_KEY);
    if (raw === null) return true;
    return raw !== 'false';
  } catch {
    return true;
  }
}

export const DailyBriefingPage: React.FC = () => {
  const { t, language } = useTranslation();
  const o = t.onboarding;
  const location = useLocation();
  const navigate = useNavigate();
  const { conversationId } = useParams<{ conversationId?: string }>();
  const { openModal, addToast } = useAppStore();
  const { accessToken, user } = useAuthStore();
  const userKey = user?.id ?? user?.email ?? accessToken;
  const ensureRoutinesLoaded = useRoutineStore((state) => state.ensureLoaded);
  const connections = usePipelineRunStore((s) => s.connections);
  const connectionsLoaded = usePipelineRunStore((s) => s.connectionsLoaded);
  const connectionsLoading = usePipelineRunStore((s) => s.connectionsLoading);
  const connectionsError = usePipelineRunStore((s) => s.connectionsError);
  const enabledConnections = ENABLED_PROVIDERS.map((provider) => ({
    provider,
    connected: connections.find((c) => c.provider === provider)?.connected ?? false,
  }));
  const connectedProviderCount = enabledConnections.filter((c) => c.connected).length;

  const {
    conversations,
    getConversation,
    fetchConversationDetail,
    createConversation,
    addMessage,
    updateFeedback,
    replaceLatestAiMessage,
    updateProductivityAction,
    setConversationGenerating,
  } = useConversationStore();

  // Local UI states
  const [query, setQuery] = useState('');
  const consumedChatPromptRef = useRef<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [audioCuesEnabled, setAudioCuesEnabled] = useState(readMobileAudioCueSetting);
  const [voiceCueStatus, setVoiceCueStatus] = useState('');
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [agentProgress, setAgentProgress] = useState<AgentProgressEvent[]>([]);
  const [atAGlanceOpen, setAtAGlanceOpen] = useState(readAtAGlanceOpen);
  const [nextCalendarEvent, setNextCalendarEvent] = useState<CalendarEvent | null>(null);
  const [actionBusy, setActionBusy] = useState<{
    messageId: string;
    decision: 'approve' | 'reject';
  } | null>(null);
  const [pastedImage, setPastedImage] = useState<string | null>(null);
  const [briefingTasks, setBriefingTasks] = useState<Task[]>([]);
  const [briefingTasksStatus, setBriefingTasksStatus] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle');
  const [coldStartInviteDismissed, setColdStartInviteDismissed] = useState(() => readColdStartInviteDismissed(user?.id));
  const [visionBusy, setVisionBusy] = useState(false);
  const [todayRoutineRun, setTodayRoutineRun] = useState<RoutineRun | null>(null);
  const [routineSummaryLoading, setRoutineSummaryLoading] = useState(false);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const consumedChatImageRef = useRef<File | null>(null);
  // Nút copy chỉ đổi màu khi hover thì rê chuột ra là mất luôn dấu hiệu "đã
  // bấm" — đổi hẳn sang icon Check tô đặc một nhịp ngắn để xác nhận rõ ràng.
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const acceptImageFile = (file: File | undefined) => {
    if (!file || !file.type.startsWith('image/')) return;
    if (file.size > 8_000_000) {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Ảnh quá lớn' : 'Image too large',
        message: language === 'vi' ? 'Ảnh phải nhỏ hơn 8 MB.' : 'Use an image smaller than 8 MB.',
      });
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPastedImage(typeof reader.result === 'string' ? reader.result : null);
    reader.readAsDataURL(file);
  };

  const handleImagePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    // Ảnh chụp màn hình macOS thường nằm trong `items`, còn file copy từ
    // Finder lại nằm trong `files`; phải hỗ trợ cả hai dạng clipboard.
    const file = imageFileFromClipboard(event.clipboardData);
    if (file) {
      event.preventDefault();
      acceptImageFile(file);
    }
  };

  const handleImageDrop = (event: React.DragEvent<HTMLTextAreaElement>) => {
    event.preventDefault();
    acceptImageFile(event.dataTransfer.files[0]);
  };

  const trackAgentProgress = (progress: AgentProgressEvent) => {
    setAgentProgress((current) => {
      const previous = current[current.length - 1];
      if (previous?.phase === progress.phase && previous.tool === progress.tool) return current;
      return [...current, progress].slice(-6);
    });
  };

  const setAtAGlanceVisible = (open: boolean) => {
    setAtAGlanceOpen(open);
    try {
      localStorage.setItem(AT_A_GLANCE_KEY, String(open));
    } catch {
      /* bỏ qua quota / private mode */
    }
  };

  useEffect(() => {
    const handleGlanceShortcut = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'g') return;
      const target = event.target as HTMLElement | null;
      if (target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName ?? '')) return;
      event.preventDefault();
      setAtAGlanceVisible(!atAGlanceOpen);
    };
    window.addEventListener('keydown', handleGlanceShortcut);
    return () => window.removeEventListener('keydown', handleGlanceShortcut);
  }, [atAGlanceOpen]);

  // Card "Lịch chương trình" chỉ có dữ liệu thật khi Google đã kết nối —
  // không suy đoán event nào, không có Google thì ẩn hẳn card đó.
  useEffect(() => {
    if (!accessToken || !connections.find((c) => c.provider === 'google' && c.connected)) {
      setNextCalendarEvent(null);
      return;
    }
    let cancelled = false;
    const timeFrom = new Date().toISOString();
    const timeTo = new Date(Date.now() + 14 * 24 * 3600 * 1000).toISOString();
    listCalendarEvents(accessToken, timeFrom, timeTo)
      .then(({ events }) => {
        if (cancelled) return;
        const earliest = [...events].sort(
          (a, b) => new Date(a.startAt).getTime() - new Date(b.startAt).getTime(),
        )[0];
        setNextCalendarEvent(earliest ?? null);
      })
      .catch(() => {
        if (!cancelled) setNextCalendarEvent(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, connections]);

  // Nạp task thật một lần ở màn hình Briefing mới để phân biệt "chưa có task"
  // với trạng thái mặc định chưa tải; lỗi thì không hiện lời mời cold-start.
  useEffect(() => {
    if (!accessToken || conversationId) {
      setBriefingTasksStatus('idle');
      setBriefingTasks([]);
      return;
    }
    let cancelled = false;
    setBriefingTasksStatus('loading');
    void listTasks(accessToken)
      .then(({ tasks }) => {
        if (!cancelled) {
          setBriefingTasks(tasks);
          setBriefingTasksStatus('loaded');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBriefingTasks([]);
          setBriefingTasksStatus('error');
        }
      })
    return () => {
      cancelled = true;
    };
  }, [accessToken, conversationId]);

  const dismissColdStartInvites = () => {
    writeColdStartInviteDismissed(user?.id);
    setColdStartInviteDismissed(true);
  };

  // Hiển thị đúng một summary routine thật trong ngày ở rail bên phải.
  // Không có run hôm nay thì nói thẳng là chưa có, không dựng nội dung mẫu.
  useEffect(() => {
    if (!accessToken || !userKey || conversationId) {
      setTodayRoutineRun(null);
      return;
    }
    let cancelled = false;
    setRoutineSummaryLoading(true);
    void ensureRoutinesLoaded(accessToken, userKey)
      .then(() => {
        if (cancelled) return;
        const runs = useRoutineStore.getState().recentRuns;
        const latestToday = runs
          .filter((run) => isToday(run.startedAt))
          .sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())[0];
        setTodayRoutineRun(latestToday ?? null);
      })
      .catch(() => {
        if (!cancelled) setTodayRoutineRun(null);
      })
      .finally(() => {
        if (!cancelled) setRoutineSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, conversationId, ensureRoutinesLoaded, userKey]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Chỉ một lượt agent chạy tại một thời điểm trên trang này — dùng chung 1
  // controller. Bấm Dừng gọi abort(); fetch ném AbortError, catch bên dưới
  // phân biệt để GIỮ phần văn bản đã stream được thay vì đè bằng thông báo lỗi.
  const abortControllerRef = useRef<AbortController | null>(null);
  const handleStopGenerating = () => {
    abortControllerRef.current?.abort();
  };
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversationRootRef = useRef<HTMLDivElement>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const voiceTranscriptRef = useRef('');
  const voiceResponsePendingRef = useRef(false);
  const queryBeforeVoiceRef = useRef('');
  const voiceCancelledRef = useRef(false);
  const cueAudioRef = useRef<HTMLAudioElement | null>(null);

  const clearVoiceResponsePending = () => {
    voiceResponsePendingRef.current = false;
  };

  const stopAgentCue = () => {
    cueAudioRef.current?.pause();
    if (cueAudioRef.current) cueAudioRef.current.currentTime = 0;
    cueAudioRef.current = null;
    setVoiceCueStatus(language === 'vi' ? 'Đã tắt âm thanh phản hồi.' : 'Agent response audio stopped.');
  };

  const playVoiceResponseCue = (reply: Parameters<typeof selectAgentAudioCue>[0]) => {
    const shouldPlay = voiceResponsePendingRef.current && audioCuesEnabled && isMobileViewport();
    clearVoiceResponsePending();
    if (!shouldPlay) return;

    setVoiceCueStatus(language === 'vi' ? 'Phản hồi của agent đã sẵn sàng.' : 'Agent response is ready.');
    void playLocalAgentCue(selectAgentAudioCue(reply), language === 'vi' ? 'vi' : 'en', (audio) => {
      cueAudioRef.current = audio;
      audio.onended = () => {
        if (cueAudioRef.current === audio) cueAudioRef.current = null;
      };
    });
  };

  const toggleAudioCues = () => {
    const enabled = !audioCuesEnabled;
    setAudioCuesEnabled(enabled);
    writeMobileAudioCueSetting(enabled);
    if (!enabled) stopAgentCue();
    else setVoiceCueStatus(language === 'vi' ? 'Đã bật âm thanh phản hồi trên điện thoại.' : 'Mobile response audio enabled.');
  };

  useEffect(() => () => {
    recognitionRef.current?.abort?.();
    cueAudioRef.current?.pause();
  }, []);

  // Waveform khi đang ghi âm — tách khỏi SpeechRecognition, chỉ để hiển thị.
  const voiceLevels = useMicLevelMeter(isVoiceActive, null);

  const currentConv = conversationId ? getConversation(conversationId) : undefined;
  const latestMessageText = currentConv?.messages.at(-1)?.text;

  // Hội thoại thật nằm ở DB — mở link trực tiếp (reload/gõ URL) trước khi
  // sidebar kịp fetch list thì vẫn phải tự lấy chi tiết, không đọc localStorage.
  useEffect(() => {
    if (!conversationId || !accessToken) return;
    const conv = getConversation(conversationId);
    if (conv?.messagesLoaded) return;
    void fetchConversationDetail(accessToken, conversationId, language);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, accessToken]);

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    if (conversationId && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [
    conversationId,
    currentConv?.messages.length,
    latestMessageText,
    agentProgress.length,
    isGenerating,
  ]);

  // Theo dõi vị trí cuộn của <main> (ancestor cuộn thật, xem AppShell.tsx)
  // để hiện nút "về cuối hội thoại" khi người dùng đã lướt lên xa khỏi đáy.
  useEffect(() => {
    if (!conversationId) return;
    const scrollParent = conversationRootRef.current?.closest('main');
    if (!scrollParent) return;

    const handleScroll = () => {
      const distanceFromBottom =
        scrollParent.scrollHeight - scrollParent.scrollTop - scrollParent.clientHeight;
      setShowScrollToBottom(distanceFromBottom > 200);
    };

    handleScroll();
    scrollParent.addEventListener('scroll', handleScroll, { passive: true });
    return () => scrollParent.removeEventListener('scroll', handleScroll);
  }, [conversationId, currentConv?.messages.length]);

  // Adjust textarea height
  const handleQueryChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuery(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  };

  // Submit initial question in State A
  const handleStartBriefing = async (overrideText?: string) => {
    const questionText = (overrideText || query).trim();
    const agentQuestion = agentPromptFor(questionText);
    if (!questionText && !pastedImage) return;

    if (pastedImage) {
      if (!accessToken) {
        addToast({
          type: 'error',
          title: language === 'vi' ? 'Cần đăng nhập' : 'Sign in required',
          message: language === 'vi' ? 'Vui lòng đăng nhập trước khi gửi ảnh.' : 'Please sign in before sending an image.',
        });
        return;
      }
      const image = pastedImage;
      const imagePrompt = questionText || (language === 'vi' ? 'Đọc ảnh và cho tôi biết cần làm gì.' : 'Read this image and tell me what I should do.');
      setIsGenerating(true);
      setVisionBusy(true);
      try {
        const newId = await createConversation(accessToken, imagePrompt, language);
        setQuery('');
        setPastedImage(null);
        navigate(`/briefing/conversation/${newId}`);
        addMessage(newId, 'user', questionText || '📷 Ảnh đã gửi');
        addMessage(newId, 'ai', '');
        const result = await runVisionAction(API_BASE_URL, accessToken, image, imagePrompt);
        replaceLatestAiMessage(newId, result.response, {
          taskSuggestions: result.taskSuggestions,
          ...(result.calendarSuggestions?.length ? { calendarSuggestions: result.calendarSuggestions } : {}),
        });
        if (result.warnings.length > 0) {
          addToast({
            type: 'info',
            title: language === 'vi' ? 'Lưu ý khi đọc ảnh' : 'Note about this image',
            message: result.warnings.join(' · '),
          });
        }
      } catch (error) {
        addToast({
          type: 'error',
          title: language === 'vi' ? 'Không đọc được ảnh' : 'Could not read image',
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setVisionBusy(false);
        setIsGenerating(false);
      }
      return;
    }

    // Intent gate: chỉ gọi pipeline Gmail thật khi câu hỏi rõ ràng cần đọc/tóm
    // tắt email — còn lại đi qua askAgent (chat chung, không tốn 1 lần fetch
    // Gmail + gọi LLM cho mỗi câu chào hỏi).
    if (!isGmailBriefingIntent(questionText)) {
      if (!accessToken) {
        addToast({
          type: 'error',
          title: language === 'vi' ? 'Cần đăng nhập' : 'Sign in required',
          message: language === 'vi' ? 'Vui lòng đăng nhập trước khi hỏi mondaiy.' : 'Please sign in before asking mondaiy.',
        });
        return;
      }
      setIsGenerating(true);

      // Tạo phiên thật trên backend trước — id trả về là id thật luôn, không
      // còn id giả phía client rồi link sau (nguồn bug "conversation không tồn tại").
      // Giữ nguyên câu hỏi trong ô nhập cho tới khi tạo phiên xong: request này
      // mất 700–900ms thực đo, xoá ô nhập ngay trước đó tạo ra một khoảng trắng
      // im lặng — cảm giác app "nhảy thẳng vào reasoning". Lỗi mạng ở bước này
      // trước đây còn làm mất trắng câu hỏi vì ô nhập đã bị xoá sẵn.
      let newId: string;
      try {
        newId = await createConversation(accessToken, questionText, language);
      } catch (err) {
        clearVoiceResponsePending();
        addToast({
          type: 'error',
          title: language === 'vi' ? 'Không tạo được hội thoại' : 'Could not start conversation',
          message: err instanceof Error ? err.message : String(err),
        });
        setIsGenerating(false);
        return;
      }
      setQuery('');
      navigate(`/briefing/conversation/${newId}`);
      // Hiển thị câu hỏi ngay khi phiên được tạo; trước đây chỉ dựng bubble AI
      // nên câu đầu tiên bị giữ trong request nhưng không xuất hiện trong chat.
      addMessage(newId, 'user', questionText);
      addMessage(newId, 'ai', '');

      // Cờ này sống ở store toàn cục — rời khỏi hội thoại (điều hướng đi chỗ
      // khác) không huỷ request đang chạy (fetch không gắn với vòng đời
      // component), nên sidebar vẫn phải biết hội thoại này đang chạy ngầm để
      // vẽ node đặc; xem renderHistoryRow trong Sidebar.tsx.
      setConversationGenerating(newId, true);

      // Controller phải tồn tại TRƯỚC khi đồng bộ chạy — đồng bộ có thể mất
      // vài phút và nút Dừng đã hiện suốt thời gian đó (isGenerating true từ
      // trên), bấm Dừng lúc này mà ref còn null thì abort() là no-op, người
      // dùng thấy nút Dừng chết cứng tới khi đồng bộ tự xong.
      const controller = new AbortController();
      abortControllerRef.current = controller;
      try {
        // Câu chat ĐẦU TIÊN của phiên đi qua đây, không qua handleSendFollowUp —
        // mà "câu chat đầu tiên trong ngày" gần như luôn là câu này. Bỏ sót chỗ
        // này thì luật đồng bộ theo ngày gần như không bao giờ chạy.
        await runChatSyncIfDue(
          questionText,
          (notice) => {
            replaceLatestAiMessage(newId, notice, {});
          },
          controller.signal,
        );
        setAgentProgress([{ phase: 'thinking' }]);
        let streamedResponse = '';
        await streamConversationMessage(Number(newId), agentQuestion, accessToken, {
          onProgress: trackAgentProgress,
          onToken: (delta) => {
            streamedResponse += delta;
            replaceLatestAiMessage(newId, streamedResponse, {});
          },
          onDone: (reply) => {
            replaceLatestAiMessage(newId, reply.response || streamedResponse, {
              isError: false,
              serverMessageId: reply.messageId,
              productivityAction: reply.productivityAction,
              taskDrafts: reply.taskDrafts,
              ...(reply.taskBacklogCount ? { taskBacklogCount: reply.taskBacklogCount } : {}),
              taskSuggestions: reply.taskSuggestions,
              groundingStatus: reply.groundingStatus,
              programQuestionHandoffEligible: reply.programQuestionHandoffEligible,
              sources: reply.sources || [],
            });
            playVoiceResponseCue(reply);
          },
          signal: controller.signal,
        });
        recordMeaningfulAction('grounded_answer_completed');
      } catch (err) {
        clearVoiceResponsePending();
        if (isAbortError(err)) {
          // Người dùng chủ động bấm Dừng — giữ nguyên phần đã stream được (đã
          // nằm sẵn trong store qua onToken ở trên), không đè bằng thông báo
          // lỗi. Server chưa kịp "done" nên không lưu lượt này — chỉ sống
          // phía client tới khi rời trang, đúng như một câu trả lời bị cắt.
          const lastMessage = getConversation(newId)?.messages.at(-1);
          const partial = lastMessage?.sender === 'ai' ? lastMessage.text : '';
          replaceLatestAiMessage(newId, partial || (language === 'vi' ? 'Đã dừng.' : 'Stopped.'), { isError: false });
        } else {
          replaceLatestAiMessage(newId, inlineAgentError(language, err), { isError: true });
        }
      } finally {
        setAgentProgress([]);
        setIsGenerating(false);
        setConversationGenerating(newId, false);
        abortControllerRef.current = null;
      }
      return;
    }

    if (!accessToken) {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Cần đăng nhập' : 'Sign in required',
        message: language === 'vi'
          ? 'Vui lòng đăng nhập trước khi yêu cầu tổng hợp Gmail.'
          : 'Please sign in before generating a Gmail briefing.',
      });
      return;
    }
    setIsGenerating(true);
    setQuery('');
    setRunStatus(language === 'vi' ? 'Đang kết nối Gmail…' : 'Connecting to Gmail…');

    let newId: string;
    try {
      newId = await createConversation(accessToken, questionText, language);
    } catch (err) {
      clearVoiceResponsePending();
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Không tạo được hội thoại' : 'Could not start conversation',
        message: err instanceof Error ? err.message : String(err),
      });
      setRunStatus(null);
      setIsGenerating(false);
      return;
    }
    navigate(`/briefing/conversation/${newId}`);
    addMessage(newId, 'ai', '');
    const reportGmailUnavailable = (status?: string) => {
      setRunStatus(null);
      replaceLatestAiMessage(newId, inlineGmailError(language, status), { isError: false });
    };
    const reportGmailRunError = () => {
      setRunStatus(null);
      replaceLatestAiMessage(newId, inlineGmailRunError(language), { isError: true });
    };
    try {
      const gmailStatus = await getGmailStatus(accessToken);
      // Có token và mailbox truy cập được là đủ: run Gmail sẽ đọc trực tiếp
      // online khi index chưa có dữ liệu, không bắt user chờ initial sync.
      if (!gmailStatus.oauthValid || !gmailStatus.mailboxAccessible) {
        reportGmailUnavailable(gmailStatus.status);
        return;
      }
      const connections = await getConnections(accessToken);
      const google = connections.find((connection) => connection.provider === 'google' && connection.connected);
      const integrations = await getIntegrations(accessToken);
      const integration = integrations.find((item) => item.provider === 'google');
      if (!google || !integration) {
        reportGmailUnavailable();
        return;
      }
      const gmailSources = await getGmailSources(accessToken, integration.id);
      // Initial briefing is evidence-first: only the approved primary inbox.
      const sourceIds = gmailSources
        .filter((source) => isPrimaryGmailSource(source.id))
        .map((source) => source.id);
      if (!sourceIds.length) {
        reportGmailUnavailable();
        return;
      }
      const run = await createGmailRun(accessToken, integration.id, sourceIds, extractGmailDateRange(questionText));
      setRunStatus(language === 'vi' ? 'Đang đọc và kiểm chứng Gmail…' : 'Gmail is being fetched and grounded…');
      void streamRunEvents(accessToken, run.id, (event) => {
        if (event.node) setRunStatus(`Gmail: ${event.node}${event.count !== undefined ? ` (${event.count})` : ''}`);
      });
      await waitForRun(accessToken, run.id);
      const brief = await getRunBrief(accessToken, run.id);
      recordMeaningfulAction('gmail_summary_completed');
      const evidenceItems = brief.evidence.map((item) => ({
        id: `gmail-${item.messageId}`,
        title: item.importance === 'critical' ? 'Critical Gmail evidence' : 'Gmail evidence',
        summary: item.quote,
        confidence: item.importanceScore >= 60 ? 'certain' as const : 'possible' as const,
        source: { platform: 'Gmail', location: item.sourceUrl, timestamp: new Date().toLocaleString() },
      }));
      replaceLatestAiMessage(newId, language === 'vi' ? 'Đây là bản tổng hợp đã lấy và kiểm chứng từ Gmail.' : 'Here is the grounded summary from Gmail.', {
        isError: false,
        summary: brief.summary,
        confidence: brief.scheduleConflicts.length ? 'ask_mentor' : 'certain',
        source: { platform: 'Gmail', location: 'Approved Gmail labels', timestamp: new Date().toLocaleString() },
        evidenceItems,
        whatChanged: brief.scheduleConflicts.length ? 'Gmail reported conflicting schedule evidence.' : undefined,
        whyItMatters: `Run #${run.id} completed with ${brief.topPriority.length} prioritized item(s).`,
      });
      playVoiceResponseCue({ response: brief.summary, analysis: '', taskDrafts: [], taskSuggestions: [] });
      setRunStatus(null);
      addToast({
        type: 'success',
        title: language === 'vi' ? 'Đã tạo Briefing' : 'Briefing ready',
        message: language === 'vi'
          ? 'Gmail đã được đọc, lọc, kiểm chứng và tổng hợp.'
          : 'Gmail was fetched, filtered, grounded, and summarized.',
      });
    } catch (error) {
      void error;
      clearVoiceResponsePending();
      reportGmailRunError();
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    const imageFile = readChatImageHandoff(location.state);
    if (imageFile && consumedChatImageRef.current !== imageFile) {
      consumedChatImageRef.current = imageFile;
      navigate(location.pathname, { replace: true, state: null });
      acceptImageFile(imageFile);
      return;
    }
    const prompt = readChatHandoff(location.state);
    if (prompt === null || consumedChatPromptRef.current === prompt) return;
    consumedChatPromptRef.current = prompt;
    navigate(location.pathname, { replace: true, state: null });
    void handleStartBriefing(prompt);
    // handleStartBriefing dùng state mới nhất của render hiện tại; route state
    // là trigger one-shot và được xóa trước khi request bắt đầu.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.state, navigate]);

  // Submit follow-up question in State B
  /**
   * Kéo đồng bộ hộ người dùng trước khi trả lời, thay cho nút Sync tay đã ẩn.
   *
   * Server quyết định có chạy hay không (câu chat đầu tiên trong ngày, hoặc câu
   * hỏi về việc trên dữ liệu đã cũ). Ở đây chỉ chờ và hiện tiến trình.
   *
   * Không bao giờ ném lỗi ra ngoài: đồng bộ hỏng thì vẫn phải trả lời được
   * bằng dữ liệu đang có — người dùng hỏi một câu chat, không phải bấm Sync.
   */
  const runChatSyncIfDue = async (
    messageText: string,
    onSyncNotice?: (notice: string) => void,
    signal?: AbortSignal,
  ) => {
    if (!accessToken) return;
    let result;
    try {
      result = await triggerChatSync(accessToken, messageText, language);
    } catch {
      return;
    }
    if (!result.triggered || !result.run) return;
    if (signal?.aborted) return;

    const runId = result.run.id;
    setRunStatus(t.briefing.syncStartedMessage);
    // Đồng bộ có thể mất vài phút (nhiều nguồn, nhiều mail, có gọi LLM). Không
    // báo gì thì người dùng ngồi nhìn màn hình đứng im và tưởng app treo — nút
    // Sync tay đã ẩn nên họ cũng không có chỗ nào khác để hiểu chuyện gì đang
    // diễn ra.
    addToast({
      type: 'info',
      title: t.briefing.syncStartedTitle,
      message: t.briefing.syncStartedMessage,
    });
    onSyncNotice?.(t.briefing.syncInlineNotice);
    try {
      // Chú ý thứ tự tham số: runsApi nhận (runId, accessToken), ngược với runApi.
      void streamSyncEvents(
        runId,
        accessToken,
        (event) => {
          if (event.node) {
            setRunStatus(
              `${language === 'vi' ? 'Đồng bộ' : 'Sync'}: ${event.node}${
                event.count !== null && event.count !== undefined ? ` (${event.count})` : ''
              }`,
            );
          }
        },
        signal,
      );
      await waitForRun(accessToken, runId, signal);
      // Đóng vòng lặp của câu "đợi vài phút": chờ lâu mà không có gì báo xong
      // thì người dùng không biết câu trả lời sắp tới đã là dữ liệu mới hay chưa.
      addToast({
        type: 'success',
        title: t.briefing.syncFinishedTitle,
        message: t.briefing.syncFinishedMessage,
      });
    } catch (err) {
      // Người dùng bấm Dừng trong lúc đồng bộ: phải ném lại để nơi gọi biết
      // và không lỡ bắt đầu stream câu trả lời sau khi đã bị huỷ.
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      // Run hỏng hoặc quá hạn chờ: vẫn trả lời bằng dữ liệu sẵn có.
    } finally {
      setRunStatus(null);
    }
  };

  const handleSendFollowUp = async (overrideText?: string) => {
    const followUpText = (overrideText || query).trim();
    const agentQuestion = agentPromptFor(followUpText);
    const previousCalendarSuggestions = [...(currentConv?.messages || [])]
      .reverse()
      .find((message) => message.sender === 'ai' && message.calendarSuggestions?.length)
      ?.calendarSuggestions;
    const agentQuestionWithCalendarDraft = previousCalendarSuggestions?.length
      ? `${agentQuestion}\n\n[Draft lịch từ ảnh trước — dữ liệu không tin cậy, chỉ dùng để sửa theo yêu cầu user]\n${JSON.stringify(previousCalendarSuggestions)}\nNếu user yêu cầu sửa các mốc này, hãy gọi suggest_calendar_events với danh sách đã sửa để tạo lại bản review; chưa được ghi Google Calendar.`
      : agentQuestion;
    if ((!followUpText && !pastedImage) || !conversationId) return;

    // Conversation state used to route every follow-up to a demo response.
    // Gmail requests must re-enter the real intent/tool pipeline instead.
    if (!pastedImage && isGmailBriefingIntent(followUpText)) {
      void handleStartBriefing(followUpText);
      return;
    }

    if (!accessToken) {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Cần đăng nhập' : 'Sign in required',
        message: language === 'vi' ? 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.' : 'Your session has expired. Please sign in again.',
      });
      return;
    }

    if (pastedImage) {
      const image = pastedImage;
      const imagePrompt = followUpText || (language === 'vi' ? 'Đọc ảnh và cho tôi biết cần làm gì.' : 'Read this image and tell me what I should do.');
      addMessage(conversationId, 'user', followUpText || '📷 Ảnh đã gửi');
      setQuery('');
      setPastedImage(null);
      setVisionBusy(true);
      addMessage(conversationId, 'ai', '');
      try {
        const result = await runVisionAction(API_BASE_URL, accessToken, image, imagePrompt);
        replaceLatestAiMessage(conversationId, result.response, {
          taskSuggestions: result.taskSuggestions,
          ...(result.calendarSuggestions?.length ? { calendarSuggestions: result.calendarSuggestions } : {}),
        });
        if (result.warnings.length > 0) {
          addToast({
            type: 'info',
            title: language === 'vi' ? 'Lưu ý khi đọc ảnh' : 'Note about this image',
            message: result.warnings.join(' · '),
          });
        }
      } catch (error) {
        replaceLatestAiMessage(conversationId, error instanceof Error ? error.message : 'Không đọc được ảnh.', { isError: true });
      } finally {
        setVisionBusy(false);
      }
      return;
    }

    // Add user message
    addMessage(conversationId, 'user', followUpText);
    setQuery('');
    setIsGenerating(true);
    setConversationGenerating(conversationId, true);
    let syncNoticeShown = false;
    // Controller phải tồn tại TRƯỚC khi đồng bộ chạy — xem lý do ở nhánh gửi
    // câu đầu tiên phía trên: đồng bộ có thể mất vài phút và nút Dừng đã hiện
    // suốt lúc đó, bấm Dừng mà ref còn null thì abort() không có tác dụng gì.
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      // Đồng bộ TRƯỚC khi hỏi agent: agent đọc task từ DB, nên dữ liệu phải mới
      // xong thì câu trả lời mới phản ánh việc vừa về.
      // Bọt chat rỗng được dựng trước để chèn câu "đợi vài phút" vào đúng dòng
      // hội thoại; nó bị thay bằng câu trả lời thật ngay sau đó.
      await runChatSyncIfDue(
        followUpText,
        (notice) => {
          syncNoticeShown = true;
          addMessage(conversationId, 'ai', notice);
        },
        controller.signal,
      );

      // conversationId luôn là id thật từ backend (xem createConversation) —
      // không còn conversation local-only cần tạo phiên server lúc follow-up.
      const serverId = Number(conversationId);

      // Đã có bọt "đợi vài phút" thì tái dùng chính nó, không thêm bọt thứ hai.
      if (!syncNoticeShown) addMessage(conversationId, 'ai', '');
      setAgentProgress([{ phase: 'thinking' }]);
      let streamedResponse = '';
      await streamConversationMessage(serverId, agentQuestionWithCalendarDraft, accessToken, {
        onProgress: trackAgentProgress,
        onToken: (delta) => {
          streamedResponse += delta;
          replaceLatestAiMessage(conversationId, streamedResponse, {});
        },
        onDone: (reply) => {
          replaceLatestAiMessage(conversationId, reply.response || streamedResponse, {
            serverMessageId: reply.messageId,
            productivityAction: reply.productivityAction,
            taskDrafts: reply.taskDrafts,
            ...(reply.taskBacklogCount ? { taskBacklogCount: reply.taskBacklogCount } : {}),
            taskSuggestions: reply.taskSuggestions,
            groundingStatus: reply.groundingStatus,
            programQuestionHandoffEligible: reply.programQuestionHandoffEligible,
            sources: reply.sources || [],
          });
          playVoiceResponseCue(reply);
        },
        signal: controller.signal,
      });
      recordMeaningfulAction('grounded_answer_completed');
    } catch (err) {
      clearVoiceResponsePending();
      if (isAbortError(err)) {
        const lastMessage = getConversation(conversationId)?.messages.at(-1);
        const partial = lastMessage?.sender === 'ai' ? lastMessage.text : '';
        replaceLatestAiMessage(conversationId, partial || (language === 'vi' ? 'Đã dừng.' : 'Stopped.'), { isError: false });
      } else {
        replaceLatestAiMessage(conversationId, inlineAgentError(language, err), { isError: true });
      }
    } finally {
      setAgentProgress([]);
      setIsGenerating(false);
      setConversationGenerating(conversationId, false);
      abortControllerRef.current = null;
    }
  };

  const handleProductivityDecision = async (
    messageId: string,
    serverMessageId: number | undefined,
    decision: 'approve' | 'reject',
  ) => {
    if (!conversationId || !accessToken || !serverMessageId) {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Không thể duyệt' : 'Unable to approve',
        message: language === 'vi'
          ? 'Action này chưa được liên kết với phiên trên máy chủ. Hãy gửi lại yêu cầu.'
          : 'This action is not linked to a server message. Please submit it again.',
      });
      return;
    }
    const serverId = Number(conversationId);

    setActionBusy({ messageId, decision });
    try {
      const updated = decision === 'approve'
        ? await approveProductivityAction(serverId, serverMessageId, accessToken)
        : await rejectProductivityAction(serverId, serverMessageId, accessToken);
      updateProductivityAction(conversationId, messageId, updated);
      if (decision === 'approve' && updated.status === 'created' && audioCuesEnabled && isMobileViewport()) {
        setVoiceCueStatus(language === 'vi' ? 'Đã thêm vào lịch cho bạn.' : 'Added to your calendar.');
        void playLocalAgentCue(
          updated.kind === 'calendar_event' ? 'calendar-created' : 'summary-ready',
          language === 'vi' ? 'vi' : 'en',
          (audio) => { cueAudioRef.current = audio; },
        );
      }
      addToast({
        type: decision === 'approve' ? 'success' : 'info',
        title: decision === 'approve'
          ? language === 'vi' ? 'Đã thực hiện' : 'Action completed'
          : language === 'vi' ? 'Đã từ chối' : 'Action rejected',
        message: updated.message,
      });
    } catch (error) {
      void error;
      // error.message là chuỗi kỹ thuật từ backend (vd. "Google Calendar API
      // lỗi 400 khi tạo sự kiện") — không phải thứ nên đưa thẳng lên UI.
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Chưa thực hiện được' : 'Action failed',
        message: language === 'vi'
          ? 'Không thực hiện được thao tác này. Kiểm tra lại thông tin rồi thử lại.'
          : 'Could not complete this action. Check the details and try again.',
      });
    } finally {
      setActionBusy(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (conversationId) {
        handleSendFollowUp();
      } else {
        handleStartBriefing();
      }
    }
  };

  // Web Speech API chỉ được khởi tạo sau cú chạm; không thu/lưu audio trong app.
  const startVoiceCapture = () => {
    if (isVoiceActive) return;
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      addToast({
        type: 'info',
        title: language === 'vi' ? 'Trình duyệt chưa hỗ trợ nhập giọng nói' : 'Voice input is unavailable',
        message: language === 'vi'
          ? 'Bạn vẫn có thể nhập câu hỏi bằng văn bản.'
          : 'You can still type your question.',
      });
      return;
    }

    const recognition = new Recognition();
    recognitionRef.current = recognition;
    recognition.lang = language === 'vi' ? 'vi-VN' : 'en-US';
    recognition.interimResults = true;
    // continuous=true: không tự dừng khi im lặng một nhịp — người dùng chủ
    // động bấm Xong/Hủy trên thanh Đang nghe, nên có thể chờ lâu tuỳ ý.
    recognition.continuous = true;
    voiceTranscriptRef.current = '';
    voiceCancelledRef.current = false;
    queryBeforeVoiceRef.current = query;
    recognition.onresult = (event) => {
      // Duyệt lại từ đầu (không chỉ từ resultIndex) để gộp đủ mọi đoạn đã
      // nhận trong cả phiên — continuous=true có thể phát nhiều đợt kết quả.
      let transcript = '';
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index]?.[0]?.transcript ?? '';
      }
      if (!transcript.trim()) return;
      voiceTranscriptRef.current = transcript.trim();
      setQuery(voiceTranscriptRef.current);
    };
    recognition.onerror = (event) => {
      setIsVoiceActive(false);
      recognitionRef.current = null;
      if (voiceCancelledRef.current) return;
      const denied = event.error === 'not-allowed' || event.error === 'service-not-allowed';
      addToast({
        type: 'info',
        title: language === 'vi' ? 'Không thể nhận giọng nói' : 'Voice input unavailable',
        message: denied
          ? language === 'vi' ? 'Hãy cho phép micro trong trình duyệt hoặc nhập bằng văn bản.' : 'Allow microphone access in your browser or type instead.'
          : language === 'vi' ? 'Không nghe rõ câu nói. Bạn có thể thử lại hoặc nhập bằng văn bản.' : 'I could not hear that. Try again or type instead.',
      });
    };
    recognition.onend = () => {
      const transcript = voiceTranscriptRef.current.trim();
      setIsVoiceActive(false);
      recognitionRef.current = null;
      if (voiceCancelledRef.current) {
        setQuery(queryBeforeVoiceRef.current);
        voiceCancelledRef.current = false;
        return;
      }
      if (!transcript) return;
      voiceResponsePendingRef.current = true;
      if (conversationId) void handleSendFollowUp(transcript);
      else void handleStartBriefing(transcript);
    };
    setIsVoiceActive(true);
    try {
      recognition.start();
    } catch {
      setIsVoiceActive(false);
      recognitionRef.current = null;
    }
  };

  // Kết thúc êm — trigger onend ở trên, tự gửi transcript đã nhận được.
  const confirmVoiceCapture = () => {
    recognitionRef.current?.stop();
  };

  // Hủy hẳn — không gửi gì, khôi phục lại nội dung ô nhập trước khi ghi âm.
  const cancelVoiceCapture = () => {
    voiceCancelledRef.current = true;
    if (recognitionRef.current?.abort) recognitionRef.current.abort();
    else recognitionRef.current?.stop();
  };

  // Format date
  const todayDateStr = new Date().toLocaleDateString(language === 'vi' ? 'vi-VN' : 'en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  // Câu hỏi gợi ý — bấm vào đi thẳng qua handleStartBriefing() thật, không
  // còn kịch bản mock riêng (đã bỏ createConversation() giả cùng 5 hội thoại
  // demo hardcode trong useConversationStore cũ).
  const exampleQuestions = [
    { text: language === 'vi' ? 'Tóm tắt công việc từ Gmail tuần này' : 'Summarize my work from Gmail this week' },
    { text: language === 'vi' ? 'Điều gì cần tôi chú ý?' : 'What needs my attention?' },
    { text: language === 'vi' ? 'Có gì thay đổi từ lần briefing trước?' : 'What changed since my last briefing?' },
    { text: language === 'vi' ? 'Tôi nên làm gì tiếp theo?' : 'What should I do next?' },
    { text: language === 'vi' ? 'Có nguồn thông tin nào đang mâu thuẫn không?' : 'Are any sources conflicting?' },
    { text: language === 'vi' ? 'Sắp tới có hạn chót nào?' : 'What deadlines are coming up?' },
    { text: language === 'vi' ? 'Thông tin nào còn thiếu?' : 'What information is missing?' },
  ];
  const completedToday = briefingTasks.filter((task) => task.status === 'completed' && isToday(task.updatedAt));
  const openThisWeek = briefingTasks.filter(
    (task) => ['proposed', 'confirmed'].includes(task.status) && isWithinNextWeek(task.dueAt),
  );
  const showColdStartInvites =
    !conversationId &&
    !coldStartInviteDismissed &&
    connectionsLoaded &&
    !connectionsLoading &&
    !connectionsError &&
    connectedProviderCount === 0 &&
    briefingTasksStatus === 'loaded' &&
    briefingTasks.length === 0;
  const currentTimeSuggestion = showColdStartInvites
    ? ({
        overnight: { greeting: o.timeOvernightGreeting, routine: o.timeOvernightRoutine },
        morning: { greeting: o.timeMorningGreeting, routine: o.timeMorningRoutine },
        'late-morning': { greeting: o.timeLateMorningGreeting, routine: o.timeLateMorningRoutine },
        midday: { greeting: o.timeMiddayGreeting, routine: o.timeMiddayRoutine },
        afternoon: { greeting: o.timeAfternoonGreeting, routine: o.timeAfternoonRoutine },
        evening: { greeting: o.timeEveningGreeting, routine: o.timeEveningRoutine },
        'late-night': { greeting: o.timeLateNightGreeting, routine: o.timeLateNightRoutine },
      } satisfies Record<ColdStartTimeSlot, { greeting: string; routine: string }>)[
        getColdStartTimeSlot(new Date().getHours())
      ]
    : null;

  // Vào thẳng link /briefing/conversation/{id} (reload, mở tab mới) trước khi
  // fetch xong — currentConv chưa có trong list, không phải hội thoại không tồn tại.
  if (conversationId && !currentConv) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-[var(--color-text-secondary)]">
        {language === 'vi' ? 'Đang tải hội thoại…' : 'Loading conversation…'}
      </div>
    );
  }

  /* =========================================================================
     STATE B: ACTIVE BRIEFING CONVERSATION WORKSPACE
     ========================================================================= */
  if (conversationId && currentConv) {
    return (
      <div ref={conversationRootRef} className="mx-auto flex min-h-[calc(100dvh_-_4rem)] w-full max-w-[1100px] flex-col px-4 sm:px-6 lg:px-8 animate-in fade-in duration-200">
        {/* Gợi ý xếp hội thoại vào dự án — đặt TRÊN dòng tin nhắn để người
            dùng thấy khi vừa đọc xong ngữ cảnh, không phải cuộn xuống đáy. Tự
            ẩn khi chưa đủ lượt chat hoặc server không đủ chắc. */}
        <div className="mb-2">
          <ProjectSuggestionCard
            conversationId={conversationId}
            turnCount={currentConv.messages.length}
          />
        </div>

        {/* Message Stream — pb lớn hơn hẳn chiều cao khối composer+disclaimer
            dính đáy, để tin nhắn cuối cùng luôn cuộn hết lên TRÊN khối đó thay
            vì phải chui/xuyên qua nó. */}
        <div className="space-y-10 py-8 pb-40 sm:space-y-12 sm:py-10 sm:pb-44">
          {currentConv.messages.map((msg, msgIndex) => {
            const isUser = msg.sender === 'user';

            if (isUser) {
              const googleSheetUrl = extractGoogleSheetsUrl(msg.text);
              const googleDocUrl = extractGoogleDocsUrl(msg.text);
              return (
                <div key={msg.id} className="flex flex-col items-end justify-end animate-in fade-in duration-150">
                  {/* Bong bóng người dùng để chìm, không dùng màu nhấn đặc.
                      Câu trả lời mới là thứ cần đọc, không phải câu hỏi. */}
                  <div className="max-w-xl break-words whitespace-pre-wrap bg-[var(--color-accent-soft)] text-[var(--color-text-primary)] rounded-2xl px-4 py-2.5">
                    <p className="text-sm leading-relaxed">{msg.text}</p>
                  </div>
                  {googleSheetUrl && (
                    <GoogleSheetsConnectCard
                      spreadsheetUrl={googleSheetUrl}
                      language={language}
                      onOpenSources={() => {
                        saveGoogleSheetPrefill({ spreadsheetUrl: googleSheetUrl, sheetName: 'Backlog' });
                        navigate(`/sources?connect=google&googleSheetUrl=${encodeURIComponent(googleSheetUrl)}`);
                      }}
                    />
                  )}
                  {googleDocUrl && (
                    <GoogleDocsConnectCard
                      documentUrl={googleDocUrl}
                      language={language}
                      onOpenSources={() => {
                        saveGoogleDocPrefill({ documentUrl: googleDocUrl });
                        navigate(`/sources?connect=google&googleDocsUrl=${encodeURIComponent(googleDocUrl)}`);
                      }}
                    />
                  )}
                </div>
              );
            }

            const showQuickActions = shouldShowMessageQuickActions(
              currentConv.messages,
              msgIndex,
            );
            const previousUserQuestion = [...currentConv.messages.slice(0, msgIndex)]
              .reverse()
              .find((message) => message.sender === 'user')?.text;
            const canEscalateProgramQuestion =
              Boolean(accessToken && previousUserQuestion) &&
              msg.programQuestionHandoffEligible === true;
            const messageSource = msg.source || msg.evidenceItems?.[0]?.source;

            /* Câu trả lời render thành văn xuôi chạy thẳng trong luồng chat.
               Không bọc thẻ, không lồng hộp con. Thông tin về độ chắc chắn và
               nguồn vẫn giữ nguyên, chỉ đổi cách trình bày thành chữ và liên kết. */
            return (
              <div key={msg.id} className="space-y-4 animate-in fade-in duration-200">
                <div className="max-w-4xl space-y-5">
                  {/* Agent thật trả lời vào msg.text, dữ liệu mock thì tách sẵn
                      thành summary và mấy trường kèm theo. Phải render cả hai,
                      thiếu nhánh text là câu trả lời thật hiện ra trống trơn.
                      whitespace-pre-wrap để giữ xuống dòng và gạch đầu dòng. */}
                  {msg.text && msg.isError && (
                    <div
                      role="alert"
                      className="flex max-w-2xl items-start gap-2.5 rounded-xl border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-3.5 py-3 text-[var(--color-text-primary)]"
                    >
                      <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-danger)]" />
                      <p className="text-sm leading-relaxed">{msg.text}</p>
                    </div>
                  )}

                  {msg.text && !msg.isError && (
                    <MarkdownBody
                      source={msg.text}
                      className="space-y-3 text-[15px] leading-[1.7] text-[var(--color-text-primary)]"
                    />
                  )}

                  {canEscalateProgramQuestion && previousUserQuestion && accessToken && (
                    <ProgramQuestionEscalation
                      accessToken={accessToken}
                      initialQuestion={previousUserQuestion}
                      language={language === 'vi' ? 'vi' : 'en'}
                    />
                  )}

                  {msg.productivityAction && (
                    <ProductivityApprovalCard
                      action={msg.productivityAction}
                      language={language === 'vi' ? 'vi' : 'en'}
                      busy={actionBusy?.messageId === msg.id ? actionBusy.decision : null}
                      onApprove={() => void handleProductivityDecision(msg.id, msg.serverMessageId, 'approve')}
                      onReject={() => void handleProductivityDecision(msg.id, msg.serverMessageId, 'reject')}
                      onSubmitClarification={(message) => void handleSendFollowUp(message)}
                    />
                  )}

                  {msg.summary && (
                    <p className="text-[15px] text-[var(--color-text-primary)] leading-[1.7]">
                      {msg.summary}
                    </p>
                  )}

                  {msg.whatChanged && (
                    <p className="text-[15px] text-[var(--color-text-secondary)] leading-[1.7]">
                      <span className="text-[var(--color-text-primary)] font-medium">
                        {t.briefing.whatChanged}.{' '}
                      </span>
                      {msg.whatChanged}
                    </p>
                  )}

                  {msg.whyItMatters && (
                    <p className="text-[15px] text-[var(--color-text-secondary)] leading-[1.7]">
                      <span className="text-[var(--color-text-primary)] font-medium">
                        {t.briefing.whyItMatters}.{' '}
                      </span>
                      {msg.whyItMatters}
                    </p>
                  )}

                  {msg.recommendedNextStep && (
                    <p className="text-[15px] text-[var(--color-text-secondary)] leading-[1.7]">
                      <span className="text-[var(--color-text-primary)] font-medium">
                        {t.briefing.recommendedNextStep}.{' '}
                      </span>
                      {msg.recommendedNextStep}
                    </p>
                  )}

                  {/* Dòng xuất xứ. Độ chắc chắn nói bằng chữ thay vì huy hiệu màu,
                      chỉ tô màu khi mondaiy chưa chắc. */}
                  {(msg.source || msg.confidence) && (
                    <p className="text-xs text-[var(--color-text-muted)] flex items-center gap-2 flex-wrap pt-1">
                      {msg.source && (
                        <button
                          onClick={() =>
                            openModal('source_detail', {
                              id: 'src-ref-1',
                              title: msg.summary || 'Source reference',
                              summary: msg.summary || 'Details',
                              source: msg.source,
                              confidence: msg.confidence || 'certain',
                            })
                          }
                          className="inline-flex items-center gap-1.5 text-[var(--color-primary)] hover:underline"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>{msg.source.platform} · {msg.source.location}</span>
                        </button>
                      )}

                      {msg.source && msg.confidence && (
                        <span className="w-px h-3 bg-[var(--color-border)]" aria-hidden="true" />
                      )}

                      {msg.confidence && (
                        <span
                          className={
                            msg.confidence === 'certain'
                              ? ''
                              : msg.confidence === 'possible'
                              ? 'text-[var(--color-warning)] dark:text-[#D7B270]'
                              : 'text-[var(--color-danger)] dark:text-[#DC9A91]'
                          }
                        >
                          {msg.confidence === 'certain'
                            ? language === 'vi' ? 'Đã đối chiếu nguồn' : 'Verified against sources'
                            : msg.confidence === 'possible'
                            ? language === 'vi' ? 'Chưa chắc chắn' : 'Not fully certain'
                            : language === 'vi' ? 'Cần mentor xác nhận' : 'Needs mentor confirmation'}
                        </span>
                      )}
                    </p>
                  )}

                  {/* Grounded Evidence Items */}
                  {msg.evidenceItems && msg.evidenceItems.length > 0 && (
                    <div className="pt-3 space-y-2">
                      <span className="text-[11px] font-medium text-[var(--color-text-muted)]/70 block">
                        {language === 'vi' ? 'Bằng chứng trích dẫn:' : 'Grounded evidence:'}
                      </span>
                      <div className="space-y-2">
                        {msg.evidenceItems.map((ev) => (
                          <div
                            key={ev.id}
                            className="p-3 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between font-bold text-[var(--color-text-primary)]">
                              <span>{ev.title}</span>
                              <span className="text-[10px] text-[var(--color-text-muted)]">{ev.source.timestamp}</span>
                            </div>
                            <p className="text-[var(--color-text-muted)]">{ev.summary}</p>
                            <button
                              onClick={() =>
                                openModal('source_detail', {
                                  id: ev.id,
                                  title: ev.title,
                                  summary: ev.summary,
                                  source: ev.source,
                                  confidence: ev.confidence,
                                })
                              }
                              className="text-[11px] text-[var(--color-primary)] font-medium hover:underline block pt-0.5"
                            >
                              {ev.source.platform} · {ev.source.location} →
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {msg.sources && msg.sources.length > 0 && (
                    <div className="pt-2 space-y-2" aria-label={language === 'vi' ? 'Nguồn đã dùng' : 'Sources used'}>
                      <span className="text-[11px] font-medium text-[var(--color-text-muted)]/70 block font-heading">
                        {language === 'vi' ? 'Nguồn đã dùng:' : 'Sources used:'}
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {msg.sources.map((source, sourceIndex) => {
                          const label = source.title || source.tool || source.url;
                          return (
                            <a
                              key={`${source.url}-${sourceIndex}`}
                              href={source.url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-accent-soft)] px-2.5 py-1.5 text-xs text-[var(--color-primary)] hover:underline"
                            >
                              <ExternalLink className="h-3 w-3 shrink-0" />
                              <span className="truncate">{label}</span>
                              {source.occurred_at && <span className="shrink-0 text-[10px] text-[var(--color-text-muted)]">{source.occurred_at}</span>}
                            </a>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {msg.taskDrafts?.map((task) => (
                    <ChatTaskDraftCard
                      key={task.id}
                      task={task}
                      accessToken={accessToken}
                      language={language}
                    />
                  ))}

                  {msg.taskBacklogCount && msg.taskBacklogCount > 0 && (
                    <p className="text-sm text-[var(--color-text-muted)]">
                      <button
                        type="button"
                        onClick={() => navigate('/tasks')}
                        className="font-medium text-[var(--color-primary)] hover:underline"
                      >
                        {language === 'vi'
                          ? `Còn ${msg.taskBacklogCount} việc tồn đọng →`
                          : `${msg.taskBacklogCount} tasks still pending →`}
                      </button>
                    </p>
                  )}

                  {msg.taskSuggestions?.map((suggestion, index) => (
                    <ChatTaskSuggestionCard
                      key={`${suggestion.title}-${index}`}
                      suggestion={suggestion}
                      accessToken={accessToken}
                      language={language}
                      onOpenTasks={() => navigate('/tasks')}
                    />
                  ))}

                  {msg.calendarSuggestions && msg.calendarSuggestions.length > 0 && (
                    <VisionCalendarBatchCard
                      suggestions={msg.calendarSuggestions}
                      accessToken={accessToken}
                      language={language}
                    />
                  )}

                  {/* Quick actions chỉ khi user hỏi lên kế hoạch / tóm tắt ngày */}
                  {showQuickActions && (
                    <div className="pt-3 border-t border-[var(--color-border-subtle)] flex items-center gap-2 flex-wrap">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => void handleSendFollowUp(
                          language === 'vi'
                            ? 'Hãy tạo một task draft từ đề xuất ngay trước đó. Chỉ dùng đúng tiêu đề, chi tiết và hạn chót đã có; không tự đoán dữ kiện còn thiếu.'
                            : 'Create a task draft from the immediately preceding recommendation. Use only its known title, details, and deadline; do not guess missing facts.',
                        )}
                        className="text-xs font-semibold shadow-2xs"
                      >
                        {language === 'vi' ? 'Tạo bản nháp nhiệm vụ' : 'Prepare task draft'}
                      </Button>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate('/tasks')}
                        className="text-xs font-semibold"
                      >
                        {language === 'vi' ? 'Xác nhận & đồng bộ lịch' : 'Confirm & sync calendar'}
                      </Button>
                    </div>
                  )}

                  {/* Feedback row — chỉ hiện khi đã CÓ câu trả lời thật. Trước đây
                      render vô điều kiện nên bọt AI rỗng (vừa addMessage(...,'')
                      để chờ stream) đã hiện sẵn nút copy/thumbs, người dùng bấm
                      copy thì chép về chuỗi rỗng — trông như UI hỏng. */}
                  {msg.text && !msg.isError && (
                    <div className="flex items-center gap-2 pt-1 text-xs text-[var(--color-text-muted)]">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => {
                            void navigator.clipboard?.writeText(msg.text);
                            setCopiedMessageId(msg.id);
                            window.setTimeout(() => {
                              setCopiedMessageId((current) => (current === msg.id ? null : current));
                            }, 1600);
                            addToast({
                              type: 'info',
                              title: language === 'vi' ? 'Đã sao chép' : 'Copied',
                              message: language === 'vi' ? 'Đã sao chép câu trả lời.' : 'Response copied.',
                            });
                          }}
                          className={`inline-flex h-9 w-9 items-center justify-center rounded-xl transition-colors ${
                            copiedMessageId === msg.id
                              ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]'
                              : 'bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]'
                          }`}
                          aria-label={language === 'vi' ? 'Sao chép câu trả lời' : 'Copy response'}
                        >
                          {copiedMessageId === msg.id ? (
                            <CheckCircle2 className="h-4 w-4" fill="currentColor" stroke="var(--color-surface)" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </button>
                        <FeedbackActions
                          itemId={msg.id}
                          initialFeedback={msg.feedback}
                          onFeedbackSelect={(fb) => accessToken && void updateFeedback(accessToken, currentConv.id, msg.id, fb)}
                        />
                        {messageSource && (
                          <div className="ml-1 flex items-center gap-1.5 rounded-full bg-[var(--color-surface-hover)] px-2.5 py-1">
                            <span className="text-[11px]">{language === 'vi' ? 'Nguồn' : 'Sources'}</span>
                            <span className="text-[11px] text-[var(--color-text-secondary)]">
                              {messageSource.platform}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

              </div>
            );
          })}

          {isGenerating && (
            <AgentActivity
              events={agentProgress}
              language={language === 'vi' ? 'vi' : 'en'}
              statusText={
                runStatus
                  ? language === 'vi'
                    ? 'Đang tìm dữ liệu của bạn'
                    : 'Looking through your connected data'
                  : undefined
              }
            />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Sticky Active Chat Composer + disclaimer — gộp chung MỘT khối dính
            đáy, nền đặc (tham khảo Claude.ai: thanh chat và dòng "có thể sai
            sót" luôn cố định cùng nhau, nội dung cuộn qua không bao giờ lộ ra
            phía sau). Trước đây disclaimer nằm NGOÀI div sticky, là sibling
            thường — khi composer bị "dính" giữa chừng trang dài, disclaimer
            vẫn nằm đúng vị trí flow gốc của nó (thường đã cuộn khỏi màn hình),
            tách rời khỏi composer trông như biến mất. Dải mờ chỉ nằm ở mép
            TRÊN cùng (trong suốt -> đặc) để chữ tan dần trước khi chạm nền đặc,
            phần còn lại của khối (composer + disclaimer) đặc hoàn toàn.

            `<main>` trong AppShell.tsx có pb-28/lg:pb-12 riêng (chỗ thở cho
            các trang khác không có composer dính đáy) — sticky bottom-0 chỉ
            neo tới MÉP TRONG của vùng padding đó, để hụt lại đúng from
            48-112px trống bên dưới khối này, nơi tin nhắn/task-card cuối vẫn
            lộ ra khi cuộn hết cỡ. Kéo margin âm đúng bằng padding của main
            rồi bù lại pb tương ứng bên trong — nền đặc vẽ tràn hết xuống mép
            thật của viewport, vị trí composer/disclaimer nhìn thấy không đổi. */}
        <div className="sticky bottom-0 z-20 mt-auto">
          <div
            aria-hidden="true"
            className="pointer-events-none h-8 bg-[linear-gradient(to_bottom,transparent_0%,var(--color-app-bg)_100%)]"
          />
          <div className="-mb-28 bg-[var(--color-app-bg)] pb-[7.75rem] pt-1 lg:-mb-12 lg:pb-[3.75rem]">

          {showScrollToBottom && (
            <button
              type="button"
              onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="absolute -top-12 left-1/2 -translate-x-1/2 p-2 rounded-full bg-[var(--color-surface-muted)] border border-[var(--color-border)] shadow-lg text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors"
              aria-label={language === 'vi' ? 'Về tin nhắn mới nhất' : 'Scroll to latest message'}
              title={language === 'vi' ? 'Về tin nhắn mới nhất' : 'Scroll to latest message'}
            >
              <ArrowDown className="w-4 h-4" />
            </button>
          )}

          <div className="relative rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3 shadow-[var(--shadow-sm)] sm:p-4">
          {isVoiceActive ? (
            <VoiceListeningBar
              language={language === 'vi' ? 'vi' : 'en'}
              levels={voiceLevels}
              onCancel={cancelVoiceCapture}
              onConfirm={confirmVoiceCapture}
            />
          ) : (
            <div className="relative flex items-center gap-2">
              {pastedImage && (
                <div className="absolute bottom-full left-0 mb-2 flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-2">
                  <img src={pastedImage} alt="Ảnh chuẩn bị gửi" className="h-12 w-12 rounded-lg object-cover" />
                  <span className="text-xs text-[var(--color-text-muted)]">{language === 'vi' ? 'Ảnh đã sẵn sàng — nhấn Enter để gửi' : 'Image ready — press Enter to send'}</span>
                  <button type="button" className="ml-auto text-xs underline" onClick={() => setPastedImage(null)}>{language === 'vi' ? 'Xóa' : 'Remove'}</button>
                </div>
              )}
              <textarea
                ref={textareaRef}
                value={query}
                onChange={handleQueryChange}
                onKeyDown={handleKeyDown}
                onPaste={handleImagePaste}
                onDrop={handleImageDrop}
                onDragOver={(event) => event.preventDefault()}
                placeholder={language === 'vi' ? 'Hỏi thêm...' : 'Ask a follow-up…'}
                rows={1}
                className="w-full bg-transparent text-sm text-[var(--color-text-primary)] placeholder-[#8B98AB] outline-none focus:outline-none focus-visible:outline-none resize-none leading-relaxed"
              />

              <div className="flex items-center gap-1.5 shrink-0">
                <input
                  ref={imageInputRef}
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  onChange={(event) => {
                    acceptImageFile(event.currentTarget.files?.[0]);
                    event.currentTarget.value = '';
                  }}
                  aria-label={language === 'vi' ? 'Chọn ảnh thời khoá biểu hoặc lịch trình' : 'Choose a timetable or schedule image'}
                />
                <button
                  type="button"
                  onClick={() => imageInputRef.current?.click()}
                  className="p-2 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-primary)]"
                  title={language === 'vi' ? 'Gửi ảnh' : 'Send image'}
                  aria-label={language === 'vi' ? 'Gửi ảnh' : 'Send image'}
                >
                  <Paperclip className="w-4 h-4" />
                </button>
                {accessToken && <TaskImportTool accessToken={accessToken} />}
                <VoiceInputTrigger
                  language={language === 'vi' ? 'vi' : 'en'}
                  onStart={startVoiceCapture}
                />

                <button
                  type="button"
                  onClick={toggleAudioCues}
                  className="p-2 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-hover)]"
                  title={language === 'vi' ? 'Bật hoặc tắt âm thanh phản hồi' : 'Toggle response audio'}
                  aria-label={language === 'vi' ? 'Bật hoặc tắt âm thanh phản hồi' : 'Toggle response audio'}
                  aria-pressed={audioCuesEnabled}
                >
                  {audioCuesEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                </button>

                {isGenerating ? (
                  <button
                    type="button"
                    onClick={handleStopGenerating}
                    className="rounded-full bg-[var(--color-text-primary)] p-2.5 text-[var(--color-surface)] transition-all hover:opacity-90"
                    title={language === 'vi' ? 'Dừng trả lời' : 'Stop generating'}
                    aria-label={language === 'vi' ? 'Dừng trả lời' : 'Stop generating'}
                  >
                    <Square className="w-4 h-4" fill="currentColor" />
                  </button>
                ) : (
                  <button
                    onClick={() => handleSendFollowUp()}
                    disabled={(!query.trim() && !pastedImage) || visionBusy}
                    className="rounded-full bg-[var(--color-primary)] p-2.5 text-[var(--color-on-primary)] transition-all hover:bg-[var(--color-primary-hover)] disabled:opacity-40"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          )}
          <p className="sr-only" aria-live="polite">
            {isVoiceActive
              ? language === 'vi' ? 'Đang lắng nghe. Trình duyệt có thể xử lý giọng nói để nhận dạng.' : 'Listening. Your browser may process speech for recognition.'
              : voiceCueStatus}
          </p>
          </div>

          {/* Disclaimer NẰM TRONG khối đặc — di chuyển cùng composer, không
              còn là sibling rời rạc có thể lạc vị trí khi composer đang dính. */}
          <p className="pt-2 text-center text-[11px] text-[var(--color-text-muted)]">{t.briefing.disclaimer}</p>
          </div>
        </div>
      </div>
    );
  }

  /* =========================================================================
     STATE A: NEW BRIEFING / EMPTY CONVERSATION HOME
     ========================================================================= */
  return (
    <div className="w-full animate-in fade-in duration-200">
      {/* Mở At a glance: full như cũ. Ẩn panel: căn giữa, bề ngang ~cột chính lúc còn panel.
          CSS transition trên max-width từng thử vẫn giật: panel vẫn chiếm chỗ
          suốt lúc fade/slide (transform không đổi kích thước layout) rồi biến
          mất tức thì lúc unmount, làm cột chính "nhảy" đúng frame cuối thay vì
          giãn mượt theo cùng nhịp. mode="popLayout" gỡ phần tử đang exit khỏi
          dòng chảy layout NGAY khi bắt đầu thoát (position: absolute tại chỗ)
          — cột `layout` bên cạnh đo lại và tự nội suy (FLIP) theo đúng frame,
          không cần transition CSS thủ công nữa. */}
      <div className="flex w-full flex-col gap-8 xl:flex-row xl:items-start">
        {/* Central New Briefing Workspace */}
        <motion.div
          layout
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className={`w-full min-w-0 flex-1 space-y-6 ${atAGlanceOpen ? '' : 'mx-auto max-w-[1024px]'}`}
        >

          {/* Lời chào. Serif, không bôi đậm, đây là điểm nhìn đầu tiên của trang
              nên để nó yên tĩnh thay vì nhồi thêm banner phía trên. */}
          <div className="flex items-start justify-between gap-3 pt-6">
            <div className="space-y-1 min-w-0">
              <h1 className="text-3xl sm:text-4xl text-[var(--color-text-primary)]">
                {language === 'vi' ? 'Hôm nay bạn đang làm gì?' : 'What are you working on today?'}
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                {todayDateStr}
              </p>
            </div>
            {!atAGlanceOpen && (
              <button
                type="button"
                onClick={() => setAtAGlanceVisible(true)}
                className="app-control mt-1 inline-flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-[11px] font-semibold text-[var(--color-text-primary)]"
                title={t.briefing.atAGlance.showPanel}
                aria-label={t.briefing.atAGlance.showPanel}
              >
                <Sparkles className="h-3.5 w-3.5 text-[var(--color-primary)]" />
                <span className="hidden sm:inline">{t.briefing.atAGlance.title}</span>
                <kbd className="hidden text-[11px] font-medium text-[var(--color-text-muted)] sm:inline">{shortcutLabel('G')}</kbd>
              </button>
            )}
          </div>

          {new Date().getHours() >= 18 && !conversationId && (
            <section
              data-testid="daily-retro-card"
              className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 shadow-2xs"
              aria-label={language === 'vi' ? 'Retro hôm nay' : 'Today retro'}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-primary)]">
                    {language === 'vi' ? 'Retro hôm nay' : 'Today retro'}
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">
                    {language === 'vi' ? 'Bạn đã làm được gì hôm nay?' : 'What did you accomplish today?'}
                  </h2>
                </div>
                <Clock className="mt-1 h-5 w-5 shrink-0 text-[var(--color-primary)]" />
              </div>

              {briefingTasksStatus === 'loading' ? (
                <p className="mt-3 text-sm text-[var(--color-text-muted)]">{language === 'vi' ? 'Đang xem lại task…' : 'Reviewing tasks…'}</p>
              ) : (
                <>
                  <div className="mt-3 space-y-1.5 text-sm text-[var(--color-text-secondary)]">
                    {completedToday.length > 0 ? completedToday.slice(0, 4).map((task) => (
                      <p key={task.id} className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-success)]" />
                        <span>{task.title}</span>
                      </p>
                    )) : (
                      <p>{language === 'vi' ? 'Chưa có task nào được đánh dấu hoàn thành hôm nay.' : 'No completed tasks recorded today.'}</p>
                    )}
                  </div>
                  <p className="mt-3 text-xs text-[var(--color-text-muted)]">
                    {language === 'vi'
                      ? `${openThisWeek.length} task còn hạn trong 7 ngày tới.`
                      : `${openThisWeek.length} task due in the next 7 days.`}
                  </p>
                  <button
                    type="button"
                    className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--color-primary)] hover:underline"
                    onClick={() => handleStartBriefing(language === 'vi'
                      ? 'Hãy retro hôm nay dựa trên các task của tôi, sau đó gợi ý những việc nên làm trong tuần này theo thứ tự ưu tiên.'
                      : 'Review what I accomplished today from my tasks, then suggest the most important things I should do this week.')}
                    disabled={isGenerating}
                  >
                    {language === 'vi' ? 'Gợi ý kế hoạch tuần' : 'Suggest my week plan'}
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </>
              )}
            </section>
          )}

          {currentTimeSuggestion && (
            <section
              data-testid="cold-start-invites"
              className="space-y-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4"
              aria-label={o.coldStartAria}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-primary)]">
                    {o.timeSuggestionLabel}
                  </p>
                  <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                    {currentTimeSuggestion.greeting}
                  </h2>
                  <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                    {currentTimeSuggestion.routine}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={dismissColdStartInvites}
                  className="shrink-0 text-xs font-semibold text-[var(--color-text-muted)] underline"
                  aria-label={o.dismissColdStartInvites}
                >
                  {o.dismissColdStartInvites}
                </button>
              </div>
              <p className="text-xs text-[var(--color-text-secondary)]">{o.coldStartActionsIntro}</p>
              <div className="grid gap-2 sm:grid-cols-3">
                <button
                  type="button"
                  onClick={() => imageInputRef.current?.click()}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-left text-sm font-semibold text-[var(--color-text-primary)] hover:border-[var(--color-primary)]"
                >
                  {o.tryScheduleAction}
                </button>
                <button
                  type="button"
                  onClick={() => handleStartBriefing(o.tryReminderAction)}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-left text-sm font-semibold text-[var(--color-text-primary)] hover:border-[var(--color-primary)]"
                >
                  {o.tryReminderAction}
                </button>
                <button
                  type="button"
                  onClick={() => handleStartBriefing(o.profileInvitePrompt)}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-left text-sm font-semibold text-[var(--color-text-primary)] hover:border-[var(--color-primary)]"
                >
                  {o.profileInviteAction}
                </button>
              </div>
            </section>
          )}

          {/* AI Input Composer Card — điểm bắt đầu của trang, xem .app-composer-hero
              trong index.css để biết vì sao nó được nâng lên khỏi mặt bằng thẻ. */}
          <div className="app-composer-hero relative border rounded-2xl p-4 sm:p-5 space-y-3">
            {isVoiceActive ? (
              <VoiceListeningBar
                language={language === 'vi' ? 'vi' : 'en'}
                levels={voiceLevels}
                onCancel={cancelVoiceCapture}
                onConfirm={confirmVoiceCapture}
              />
            ) : (
              <>
                {/* Input Textarea Area */}
                <div className="relative">
                  {pastedImage && (
                    <div className="mb-2 flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-2">
                      <img src={pastedImage} alt="Ảnh chuẩn bị gửi" className="h-16 w-16 rounded-lg object-cover" />
                      <span className="text-xs text-[var(--color-text-muted)]">{language === 'vi' ? 'Ảnh đã sẵn sàng — nhấn Enter để gửi' : 'Image ready — press Enter to send'}</span>
                      <button type="button" className="ml-auto text-xs underline" onClick={() => setPastedImage(null)}>{language === 'vi' ? 'Xóa' : 'Remove'}</button>
                    </div>
                  )}
                  <textarea
                    ref={textareaRef}
                    value={query}
                    onChange={handleQueryChange}
                    onKeyDown={handleKeyDown}
                    onPaste={handleImagePaste}
                    onDrop={handleImageDrop}
                    onDragOver={(event) => event.preventDefault()}
                    placeholder={t.briefing.askMondaiy}
                    rows={3}
                    data-tour-id="briefing-compose-input"
                    className="w-full bg-transparent text-sm sm:text-base text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] outline-none focus:outline-none focus-visible:outline-none resize-none leading-relaxed"
                  />
                </div>

                {/* Input Actions Footer Bar */}
                <div
                  className="flex items-center justify-between gap-3 pt-3 border-t border-[var(--color-border-subtle)] flex-wrap"
                  data-tour-id="briefing-toolbar"
                >
                  <div className="flex items-center gap-2">
                    <input
                      ref={imageInputRef}
                      type="file"
                      accept="image/*"
                      className="sr-only"
                      onChange={(event) => {
                        acceptImageFile(event.currentTarget.files?.[0]);
                        event.currentTarget.value = '';
                      }}
                      aria-label={language === 'vi' ? 'Chọn ảnh thời khoá biểu hoặc lịch trình' : 'Choose a timetable or schedule image'}
                    />
                    <button
                      type="button"
                      onClick={() => imageInputRef.current?.click()}
                      className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-surface-hover)] rounded-lg transition-colors"
                      title={language === 'vi' ? 'Gửi ảnh' : 'Send image'}
                      aria-label={language === 'vi' ? 'Gửi ảnh' : 'Send image'}
                    >
                      <Paperclip className="w-4 h-4" />
                    </button>
                    {accessToken && <TaskImportTool accessToken={accessToken} />}
                    <button
                      type="button"
                      onClick={() => openModal('source_library')}
                      className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-accent-soft)] hover:bg-[var(--color-surface-hover)] rounded-lg transition-colors text-xs flex items-center gap-1.5"
                      title="Connect sources"
                    >
                      <Paperclip className="w-4 h-4" />
                      <span className="text-xs font-semibold hidden sm:inline">
                        {language === 'vi' ? 'Thêm nguồn dữ liệu' : 'Add source'}
                      </span>
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => navigate('/projects')}
                      className="p-2 rounded-xl text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-primary)]"
                      title={language === 'vi' ? 'Thêm vào dự án' : 'Add to project'}
                      aria-label={language === 'vi' ? 'Thêm vào dự án' : 'Add to project'}
                    >
                      <FolderPlus className="w-4 h-4" />
                    </button>

                    <VoiceInputTrigger
                      language={language === 'vi' ? 'vi' : 'en'}
                      onStart={startVoiceCapture}
                    />

                    {isGenerating ? (
                      <button
                        type="button"
                        onClick={handleStopGenerating}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-text-primary)] text-[var(--color-surface)] shadow-sm transition-all hover:opacity-90 active:scale-[0.97]"
                        title={language === 'vi' ? 'Dừng trả lời' : 'Stop generating'}
                        aria-label={language === 'vi' ? 'Dừng trả lời' : 'Stop generating'}
                      >
                        <Square className="w-3.5 h-3.5" fill="currentColor" />
                      </button>
                    ) : (
                      <button
                        onClick={() => handleStartBriefing()}
                        disabled={(!query.trim() && !pastedImage) || visionBusy}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-sm transition-all hover:bg-[var(--color-primary-hover)] active:scale-[0.97] disabled:opacity-40"
                        title={language === 'vi' ? 'Gửi' : 'Send'}
                        aria-label={language === 'vi' ? 'Gửi' : 'Send'}
                      >
                        <Send className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </>
            )}
            <p className="text-[11px] text-[var(--color-text-muted)]" aria-live="polite">
              {isVoiceActive
                ? language === 'vi' ? 'Đang lắng nghe — trình duyệt có thể xử lý giọng nói để nhận dạng.' : 'Listening — your browser may process speech for recognition.'
                : voiceCueStatus}
            </p>

            {/* Source Library Mini Bar Below Composer */}
            <div className="pt-2 border-t border-[var(--color-border-subtle)] flex items-center justify-between gap-3 text-xs text-[var(--color-text-muted)] flex-wrap">
              <span className="flex items-center gap-1.5 text-[11px]">
                <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-success)]" />
                {connectedProviderCount > 0
                  ? (language === 'vi'
                      ? `${connectedProviderCount}/${enabledConnections.length} nguồn đã kết nối`
                      : `${connectedProviderCount}/${enabledConnections.length} sources connected`)
                  : (language === 'vi'
                      ? 'Kết nối nguồn để nhận câu trả lời có cơ sở hơn'
                      : 'Connect sources for more grounded answers')}
              </span>

              <div className="flex items-center gap-3">
                {/* Compact source icons — trang thai that tu usePipelineRunStore */}
                <div className="flex items-center gap-1.5">
                  {enabledConnections.map(({ provider, connected }) => (
                    <span
                      key={provider}
                      className={`inline-flex items-center justify-center ${
                        connected ? '' : 'opacity-30 grayscale'
                      }`}
                      title={`${PROVIDER_LABEL[provider]}${
                        connected ? '' : language === 'vi' ? ' (chưa kết nối)' : ' (not connected)'
                      }`}
                    >
                      {resolveBrandIcon(provider, 'w-3 h-3')}
                    </span>
                  ))}
                </div>

                <button
                  onClick={() => openModal('source_library')}
                  className="text-xs font-bold text-[var(--color-primary)] hover:underline"
                >
                  {language === 'vi' ? 'Quản lý nguồn' : 'Manage sources'}
                </button>
              </div>
            </div>
          </div>
          <p className="text-center text-[11px] text-[var(--color-text-muted)]">{t.briefing.disclaimer}</p>

          {/* Gợi ý mở đầu. Chip trôi tự nhiên theo chiều ngang, không phải lưới
              thẻ. Chỉ hiện bốn cái, phần còn lại nằm sau nút mở thêm. */}
          <div className="flex flex-wrap gap-2" data-tour-id="briefing-suggestions">
            {exampleQuestions.slice(0, showAllSuggestions ? undefined : 4).map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleStartBriefing(q.text)}
                disabled={isGenerating}
                className="px-3.5 py-2 bg-[var(--color-surface-muted)] hover:border-[#8B98AB] border border-[var(--color-border)] text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] dark:hover:text-[#E2E8F0] rounded-xl transition-colors text-left"
              >
                {q.text}
              </button>
            ))}

            {!showAllSuggestions && exampleQuestions.length > 4 && (
              <button
                onClick={() => setShowAllSuggestions(true)}
                className="px-3.5 py-2 border border-[var(--color-border)] hover:border-[#8B98AB] text-xs text-[var(--color-text-secondary)] rounded-xl transition-colors inline-flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {language === 'vi' ? 'Thêm gợi ý' : 'More suggestions'}
              </button>
            )}
          </div>

        </motion.div>

        {/* Cột At a glance */}
        <AnimatePresence initial={false} mode="popLayout">
        {atAGlanceOpen && (
          <motion.aside
            initial={{ opacity: 0, x: 18 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 18 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="w-full shrink-0 origin-right xl:w-[340px]"
            data-tour-id="briefing-glance-panel"
          >
            <div className="space-y-3">
              
              {/* Header */}
              <div className="flex items-center justify-between gap-2 px-1 pb-1">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                    <span className="truncate">{t.briefing.atAGlance.title}</span>
                  </h2>
                  <p className="text-xs text-[var(--color-text-muted)]">{todayDateStr}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setAtAGlanceVisible(false)}
                  className="app-icon-button shrink-0 rounded-lg p-1.5"
                  title={t.briefing.atAGlance.hidePanel}
                  aria-label={t.briefing.atAGlance.hidePanel}
                >
                  <PanelRightClose className="h-4 w-4" />
                </button>
              </div>

            {/* Schedule Section — chỉ hiện khi có event lịch thật (Google đã kết nối) */}
            {nextCalendarEvent && (
              <div className="space-y-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
                <span className="text-xs font-bold text-[var(--color-text-primary)] flex items-center gap-1.5">
                  <CalendarIcon className="w-3.5 h-3.5 text-[var(--color-primary)]" />
                  {language === 'vi' ? 'Lịch chương trình' : 'Program Calendar'}
                </span>
                <a
                  href={nextCalendarEvent.deepLink ?? undefined}
                  target={nextCalendarEvent.deepLink ? '_blank' : undefined}
                  rel={nextCalendarEvent.deepLink ? 'noreferrer' : undefined}
                  className="block p-3 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] text-xs space-y-1 hover:border-[#2563A6]/40 transition-colors"
                >
                  <p className="font-semibold text-[var(--color-text-primary)]">{nextCalendarEvent.title}</p>
                  <p className="text-[11px] text-[var(--color-text-muted)]">
                    {formatEventWhen(nextCalendarEvent, language)} · {nextCalendarEvent.calendarName}
                  </p>
                </a>
              </div>
            )}

            {/* Source Health Section */}
            <div className="space-y-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
              <div className="flex items-center justify-between text-xs font-bold text-[var(--color-text-primary)]">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-success)]" />
                  {language === 'vi' ? 'Nguồn đang kết nối' : 'Connected sources'}
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 bg-[var(--color-success-soft)] text-[var(--color-success)] dark:bg-[#2A6B4F]/20 dark:text-[#8CC3A2] rounded-full">
                  {connectedProviderCount}/{enabledConnections.length}
                </span>
              </div>
              <p className="text-xs text-[var(--color-text-muted)]">
                {language === 'vi'
                  ? `${connectedProviderCount} trong số ${enabledConnections.length} nguồn đang hoạt động`
                  : `${connectedProviderCount} of ${enabledConnections.length} sources active`}
              </p>
              {/* Yêu cầu 2026-08-25: bấm "Quản lý nguồn tin" vào thẳng trang
                  thư viện nguồn thay vì mở modal trên briefing. */}
              <button
                onClick={() => navigate('/sources')}
                className="text-xs font-bold text-[var(--color-primary)] hover:underline block pt-1"
              >
                {language === 'vi' ? 'Quản lý nguồn tin →' : 'Manage sources →'}
              </button>
            </div>

            {/* Continue Section — hội thoại gần nhất thật từ DB, list đã sort updated_at desc */}
            {conversations.length > 0 && (
              <div className="space-y-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
                <span className="text-xs font-bold text-[var(--color-text-primary)] block">
                  {language === 'vi' ? 'Tiếp tục cuộc trò chuyện' : 'Continue conversation'}
                </span>
                <div className="p-3 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] text-xs space-y-2">
                  <p className="font-semibold text-[var(--color-text-primary)] truncate">{conversations[0].title}</p>
                  <p className="text-[11px] text-[var(--color-text-muted)]">
                    {language === 'vi' ? 'Cập nhật ' : 'Updated '}
                    {conversations[0].lastUpdated}
                  </p>
                  <button
                    onClick={() => navigate(`/briefing/conversation/${conversations[0].id}`)}
                    className="w-full py-1.5 bg-[#2563A6] hover:bg-[#1E4E85] text-white text-xs font-semibold rounded-lg transition-colors text-center block"
                  >
                    {language === 'vi' ? 'Tiếp tục' : 'Resume'}
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-[var(--color-text-primary)] block">
                  {language === 'vi' ? 'Tóm tắt hôm nay' : "Today's summary"}
                </span>
                <Clock className="h-3.5 w-3.5 text-[var(--color-primary)]" />
              </div>

              {routineSummaryLoading ? (
                <div className="space-y-2" aria-label={language === 'vi' ? 'Đang tải tóm tắt' : 'Loading summary'}>
                  <div className="h-3 w-4/5 animate-pulse rounded bg-[var(--color-surface-muted)]" />
                  <div className="h-3 w-full animate-pulse rounded bg-[var(--color-surface-muted)]" />
                </div>
              ) : todayRoutineRun ? (
                <button
                  type="button"
                  onClick={() => navigate(`/routines/${todayRoutineRun.routineId}`)}
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-accent-soft)] p-3 text-left transition-colors hover:bg-[var(--color-surface-hover)]"
                >
                  <p className="truncate text-xs font-semibold text-[var(--color-text-primary)]">
                    {todayRoutineRun.routineName ?? (language === 'vi' ? 'Routine hôm nay' : "Today's routine")}
                  </p>
                  <div className="mt-1 line-clamp-3 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                    {todayRoutineRun.status === 'error'
                      ? todayRoutineRun.errorMessage
                      : <MarkdownBody source={todayRoutineRun.outputText ?? (language === 'vi' ? 'Đang chờ nội dung tóm tắt.' : 'Summary content is not ready yet.')} />}
                  </div>
                </button>
              ) : (
                <p className="text-xs text-[var(--color-text-muted)]">
                  {language === 'vi' ? 'Chưa có routine nào tạo tóm tắt hôm nay.' : 'No routine summary yet today.'}
                </p>
              )}

              <button
                type="button"
                onClick={() => navigate('/routines')}
                className="text-xs font-bold text-[var(--color-primary)] hover:underline"
              >
                {language === 'vi' ? 'Xem routines →' : 'View routines →'}
              </button>
            </div>

          </div>
        </motion.aside>
        )}
        </AnimatePresence>

      </div>
    </div>
  );
};
