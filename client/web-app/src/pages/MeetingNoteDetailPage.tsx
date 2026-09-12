import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CalendarClock,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  FolderPlus,
  Quote,
  Radio,
  Sparkles,
  User,
  X,
} from 'lucide-react';

import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useAppStore } from '../stores/useAppStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useTranslation } from '../i18n/useTranslation';
import {
  acceptActionItem,
  dismissActionItem,
  endMeetingNote,
  getMeetingNote,
  updateMeetingNote,
  type MeetingActionItem,
  type MeetingNote,
} from '../lib/meetingNotesApi';
import { recordMeaningfulAction } from '../hooks/useProductRating';
import { formatDuration, meetingDurationMs, meetingPhase } from '../lib/meetingDisplay';

type TabId = 'notes' | 'transcript' | 'summary';
type SaveState = 'idle' | 'saving' | 'saved' | 'error';

/**
 * Một dòng transcript sau khi phân tích. `kind: 'speech'` là dòng đọc được đủ
 * mốc giờ, người nói và nội dung; `kind: 'raw'` là dòng không khớp định dạng và
 * vẫn phải hiện nguyên văn vì transcript là bằng chứng, không được nuốt.
 */
type TranscriptTurn = {
  key: string;
  kind: 'speech' | 'raw';
  speaker: string;
  content: string;
  isSelf: boolean;
  raw: string;
  // Mốc giờ quy về giây, dùng để đo khoảng cách khi gộp lượt. Dòng không đọc
  // được mốc giờ mang giá trị null và không bao giờ tham gia gộp.
  offsetSeconds: number | null;
};

/** Khoảng chờ trước khi autosave — đủ dài để không bắn request mỗi phím gõ. */
const AUTOSAVE_DELAY_MS = 900;

/**
 * Nhịp poll khi cuộc họp đang được ghi — backend append transcript dần dần.
 *
 * Extension cắt chunk mỗi 5 giây, nên poll 5 giây làm độ trễ xấu nhất cộng lên
 * gần gấp đôi độ dài chunk và chữ hiện ra thành từng khối rời rạc. 1,5 giây thì
 * chunk vừa được nhận dạng xong là xuất hiện gần như ngay, đổi lại chỉ là một
 * request nhẹ chạy trong lúc người dùng chủ động bật theo dõi.
 */
const LIVE_POLL_INTERVAL_MS = 1500;

/**
 * Hai dòng liền nhau của cùng một người, cách nhau dưới ngưỡng này, được gộp
 * thành một bong bóng. Mỗi chunk 5 giây là một dòng riêng trong transcript, để
 * nguyên thì một mạch nói dài bị xé thành hàng chục bong bóng vụn. Gộp lại cho
 * cảm giác chữ chảy tiếp vào đoạn đang nói thay vì nhảy sang khối mới.
 */
const TURN_MERGE_GAP_SECONDS = 30;

/** Mốc giờ, tên người nói, nội dung: `[00:20] Tôi: mình sẽ deploy...` */
const TRANSCRIPT_LINE_PATTERN = /^\[(\d+):(\d{2})\]\s+([^:]+):\s*(.*)$/;

/**
 * Tên người nói được coi là chính chủ. So sánh sau khi hạ chữ thường vì
 * transcriber có thể trả về "Tôi" hoặc "tôi" tuỳ chunk.
 */
const SELF_SPEAKER_NAMES = new Set(['tôi', 'toi', 'me']);

/**
 * Tách transcript thành danh sách lượt nói. Cắt theo dòng, thử khớp regex; dòng
 * nào khớp thì lấy ra giờ/người nói/nội dung, dòng nào không khớp vẫn được giữ
 * lại nguyên văn dưới dạng `raw`. Chỉ bỏ dòng trắng vì dòng trắng không mang
 * thông tin nào. Trả về mảng theo đúng thứ tự gốc để đọc như một cuộc hội thoại.
 */
const parseTranscript = (raw: string): TranscriptTurn[] =>
  raw
    .split('\n')
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => line.trim().length > 0)
    .map(({ line, index }) => {
      const matched = TRANSCRIPT_LINE_PATTERN.exec(line.trim());
      if (!matched) {
        return {
          key: `raw-${index}`,
          kind: 'raw' as const,
          speaker: '',
          content: '',
          isSelf: false,
          raw: line,
          offsetSeconds: null,
        };
      }
      const [, minutes, seconds, speaker, content] = matched;
      const speakerName = speaker.trim();
      return {
        key: `turn-${index}`,
        kind: 'speech' as const,
        speaker: speakerName,
        content,
        isSelf: SELF_SPEAKER_NAMES.has(speakerName.toLowerCase()),
        raw: line,
        offsetSeconds: Number(minutes) * 60 + Number(seconds),
      };
    });

/**
 * Gộp các dòng liền nhau của cùng một người thành một lượt nói.
 *
 * Backend nối từng chunk vào transcript như một dòng độc lập, nên một người nói
 * liên tục hai phút sinh ra hàng chục dòng. Duyệt một lượt và nối nội dung vào
 * lượt đang mở khi cùng người nói và cách dòng trước dưới `TURN_MERGE_GAP_SECONDS`;
 * khoảng cách đo với dòng liền trước chứ không phải với đầu lượt, để mạch nói dài
 * không bị cắt ngang chỉ vì đã mở lượt lâu. Mốc giờ và key giữ theo dòng đầu để
 * lượt đang lớn dần không nhảy vị trí hay bị React dựng lại từ đầu. Dòng `raw`
 * không đọc được luôn đứng riêng — nó là bằng chứng nguyên văn, gộp vào là sửa.
 */
const mergeAdjacentTurns = (turns: TranscriptTurn[]): TranscriptTurn[] =>
  turns.reduce<TranscriptTurn[]>((merged, turn) => {
    const previous = merged[merged.length - 1];
    const mergeable =
      previous !== undefined &&
      previous.kind === 'speech' &&
      turn.kind === 'speech' &&
      previous.speaker === turn.speaker &&
      previous.offsetSeconds !== null &&
      turn.offsetSeconds !== null &&
      turn.offsetSeconds - previous.offsetSeconds < TURN_MERGE_GAP_SECONDS;

    if (!mergeable) return [...merged, turn];
    merged[merged.length - 1] = {
      ...previous,
      content: `${previous.content} ${turn.content}`.trim(),
      raw: `${previous.raw}\n${turn.raw}`,
      // Dời mốc đo sang dòng vừa nối để dòng kế tiếp so với nó, không so với
      // dòng mở lượt.
      offsetSeconds: turn.offsetSeconds,
    };
    return merged;
  }, []);

export const MeetingNoteDetailPage: React.FC = () => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const { noteId } = useParams<{ noteId: string }>();
  const accessToken = useAuthStore((state) => state.accessToken);
  const { addToast } = useAppStore();

  const [note, setNote] = useState<MeetingNote | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('notes');
  const [isEnding, setIsEnding] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [pendingItemId, setPendingItemId] = useState<number | null>(null);

  // Bật/tắt chế độ theo dõi cuộc họp đang ghi. Mặc định tắt để trang không tự
  // gọi API khi người dùng chỉ mở lại một cuộc họp cũ để đọc.
  const [isLive, setIsLive] = useState(false);
  // Thời điểm lần lấy dữ liệu mới nhất thành công, để người dùng biết nội dung
  // đang xem cũ tới đâu.
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);
  // Lỗi của riêng vòng poll — hiện cạnh nút thay vì toast, vì poll lặp lại nên
  // toast sẽ dồn đống.
  const [liveError, setLiveError] = useState<string | null>(null);

  // Bản nháp giữ trong state để ô nhập không giật khi response autosave về sau
  // vài phím gõ tiếp theo — không bao giờ ghi đè ô đang gõ bằng dữ liệu server.
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [transcript, setTranscript] = useState('');
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSave = useRef<{ title?: string; notes?: string; transcript?: string }>({});

  const numericId = Number(noteId);

  useEffect(() => {
    if (!accessToken || !Number.isFinite(numericId)) return;
    let cancelled = false;
    setIsLoading(true);
    getMeetingNote(numericId, accessToken)
      .then((data) => {
        if (cancelled) return;
        setNote(data);
        setTitle(data.title);
        setNotes(data.notes);
        setTranscript(data.transcript);
        setTab(data.status === 'summarized' ? 'summary' : 'notes');
        // Cuộc họp còn đang thu thì bật theo dõi sẵn: mở trang ra để xem chữ
        // chạy mà phải bấm thêm một nút mới thấy gì là hỏng đúng mục đích.
        // Cuộc họp cũ vẫn im lặng, không sinh request nền.
        setIsLive(meetingPhase(data, Date.now()) === 'recording');
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : t.meetingNotes.loadFailed);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, numericId, t.meetingNotes.loadFailed]);

  /**
   * Hẹn giờ lưu một field vừa đổi. Mỗi lần gõ huỷ lịch cũ và đặt lịch mới, nên
   * chỉ request một lần sau khi người dùng ngừng gõ. Chỉ gửi đúng field đổi để
   * không ghi đè ô còn lại bằng bản nháp cũ hơn.
   */
  const scheduleSave = useCallback(
    (payload: { title?: string; notes?: string; transcript?: string }) => {
      if (!accessToken || !Number.isFinite(numericId)) return;
      // Một timer phục vụ cả ba ô, vì vậy phải gộp phần đang chờ. Nếu chỉ giữ
      // payload mới nhất thì gõ notes rồi chuyển nhanh sang transcript sẽ hủy
      // request notes và làm mất nội dung khi rời trang.
      pendingSave.current = { ...pendingSave.current, ...payload };
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(async () => {
        const fields = pendingSave.current;
        pendingSave.current = {};
        setSaveState('saving');
        try {
          await updateMeetingNote(numericId, accessToken, fields);
          setSaveState('saved');
        } catch {
          // Không rollback ô nhập: nội dung người dùng gõ phải còn nguyên để họ
          // thử lại hoặc tự copy ra ngoài.
          pendingSave.current = { ...fields, ...pendingSave.current };
          setSaveState('error');
        }
      }, AUTOSAVE_DELAY_MS);
    },
    [accessToken, numericId],
  );

  useEffect(() => () => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    pendingSave.current = {};
  }, []);

  /**
   * Vòng poll khi cuộc họp đang được ghi. Cứ mỗi nhịp thì lấy lại note và chép
   * transcript mới xuống. Không ghi đè transcript nếu người dùng còn bản nháp
   * chờ lưu — retry không được làm mất phần họ vừa sửa tay. Cleanup vừa
   * clearInterval vừa bật cờ `cancelled` để response về muộn không setState sau
   * khi component đã unmount.
   */
  useEffect(() => {
    if (!isLive || !accessToken || !Number.isFinite(numericId)) return;
    let cancelled = false;
    const timer = setInterval(() => {
      getMeetingNote(numericId, accessToken)
        .then((fresh) => {
          if (cancelled) return;
          setNote(fresh);
          setLastSyncedAt(new Date());
          setLiveError(null);
          if (pendingSave.current.transcript === undefined) setTranscript(fresh.transcript);
        })
        .catch((error) => {
          if (!cancelled) setLiveError(error instanceof Error ? error.message : t.meetingNotes.liveFailed);
        });
    }, LIVE_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [isLive, accessToken, numericId, t.meetingNotes.liveFailed]);

  const isLocked = note?.status === 'summarized';

  // Cuộc họp đã tổng hợp thì transcript không thể dài thêm — tự tắt poll để
  // không còn request nào chạy nền.
  useEffect(() => {
    if (isLocked && isLive) setIsLive(false);
  }, [isLocked, isLive]);

  // Danh sách lượt nói dựng lại mỗi khi transcript đổi, kể cả khi transcript
  // đến từ vòng poll.
  const transcriptTurns = mergeAdjacentTurns(parseTranscript(transcript));

  /**
   * Kéo theo lượt cuối khi nội dung mới về trong lúc đang theo dõi.
   *
   * Chỉ chạy khi `isLive`: người dùng mở lại cuộc họp cũ để đọc từ đầu mà bị
   * đẩy xuống đáy là mất chỗ đang đọc. `scrollIntoView` được gọi có điều kiện
   * vì jsdom không cài đặt hàm này.
   */
  const lastTurnRef = useRef<HTMLLIElement | null>(null);
  const turnCount = transcriptTurns.length;
  const lastTurnContent = transcriptTurns[turnCount - 1]?.content ?? '';
  useEffect(() => {
    if (!isLive) return;
    lastTurnRef.current?.scrollIntoView?.({ block: 'end', behavior: 'smooth' });
  }, [isLive, turnCount, lastTurnContent]);

  const handleEnd = async () => {
    if (!accessToken || !note || isEnding) return;
    if (!notes.trim() && !transcript.trim()) {
      addToast({ type: 'warning', title: t.meetingNotes.endMeeting, message: t.meetingNotes.endEmpty });
      return;
    }
    // Xả bản nháp đang chờ trước khi tổng hợp, nếu không AI sẽ đọc bản cũ.
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setIsEnding(true);
    try {
      await updateMeetingNote(numericId, accessToken, { title, notes, transcript });
      const summarized = await endMeetingNote(numericId, accessToken);
      setNote(summarized);
      setTab('summary');
      // Bản tổng hợp cuộc họp là một câu trả lời có căn cứ trích dẫn — dùng lại
      // đúng nhãn đó thay vì thêm loại mới vào bộ đếm đánh giá sản phẩm.
      recordMeaningfulAction('grounded_answer_completed');
    } catch (error) {
      addToast({
        type: 'error',
        title: t.meetingNotes.endMeeting,
        message: error instanceof Error ? error.message : t.meetingNotes.endFailed,
      });
    } finally {
      setIsEnding(false);
    }
  };

  const handleAccept = async (item: MeetingActionItem) => {
    if (!accessToken || !note || pendingItemId !== null) return;
    setPendingItemId(item.id);
    try {
      const task = await acceptActionItem(note.id, item.id, accessToken);
      setNote({
        ...note,
        actionItems: note.actionItems.map((row) =>
          row.id === item.id ? { ...row, status: 'accepted', taskId: task.id } : row,
        ),
      });
      // Không đếm ở đây: task mới sinh ra vẫn ở trạng thái "proposed", lượt xác
      // nhận thật nằm ở trang Công việc và đã được đếm tại đó.
      addToast({ type: 'success', title: t.meetingNotes.accepted, message: t.meetingNotes.taskCreated });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.meetingNotes.accept,
        message: error instanceof Error ? error.message : t.meetingNotes.acceptFailed,
      });
    } finally {
      setPendingItemId(null);
    }
  };

  const handleDismiss = async (item: MeetingActionItem) => {
    if (!accessToken || !note || pendingItemId !== null) return;
    setPendingItemId(item.id);
    try {
      const updated = await dismissActionItem(note.id, item.id, accessToken);
      setNote({
        ...note,
        actionItems: note.actionItems.map((row) => (row.id === item.id ? updated : row)),
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.meetingNotes.dismiss,
        message: error instanceof Error ? error.message : t.meetingNotes.dismissFailed,
      });
    } finally {
      setPendingItemId(null);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-[var(--color-text-secondary)]">{t.meetingNotes.loading}</p>;
  }

  if (loadError || !note) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" icon={<ChevronLeft className="w-4 h-4" />} onClick={() => navigate('/meeting-notes')}>
          {t.meetingNotes.backToList}
        </Button>
        <div className="p-4 rounded-xl border border-[var(--color-danger)] text-sm text-[var(--color-danger)]">
          {loadError ?? t.meetingNotes.loadFailed}
        </div>
      </div>
    );
  }

  const decisions = note.decisions.split('\n').filter((line) => line.trim());
  const tabs: Array<{ id: TabId; label: string; icon: React.ReactNode }> = [
    { id: 'notes', label: t.meetingNotes.tabNotes, icon: <FileText className="w-4 h-4" /> },
    { id: 'summary', label: t.meetingNotes.tabSummary, icon: <Sparkles className="w-4 h-4" /> },
    { id: 'transcript', label: t.meetingNotes.tabTranscript, icon: <Quote className="w-4 h-4" /> },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6 animate-in fade-in duration-200">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] pb-4">
        <Button
          variant="ghost"
          size="sm"
          icon={<ArrowLeft className="w-4 h-4" />}
          onClick={() => navigate('/meeting-notes')}
        >
          {t.meetingNotes.backToList}
        </Button>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--color-text-secondary)]">
            {saveState === 'saving' && t.meetingNotes.saving}
            {saveState === 'saved' && t.meetingNotes.saved}
            {saveState === 'error' && (
              <span className="text-[var(--color-danger)]">{t.meetingNotes.saveFailed}</span>
            )}
          </span>
          {!isLocked && (
            <Button onClick={handleEnd} disabled={isEnding} icon={<Sparkles className="w-4 h-4" />}>
              {isEnding ? t.meetingNotes.ending : t.meetingNotes.endMeeting}
            </Button>
          )}
        </div>
      </div>

      <input
        value={title}
        disabled={isLocked}
        placeholder={t.meetingNotes.titlePlaceholder}
        onChange={(event) => {
          setTitle(event.target.value);
          scheduleSave({ title: event.target.value });
        }}
        className="w-full bg-transparent text-3xl font-semibold tracking-tight font-heading text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)] focus:outline-none disabled:opacity-80"
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex items-center p-1 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg transition-colors ${
                tab === item.id
                  ? 'bg-[var(--color-surface-hover)] text-[var(--color-text-primary)]'
                  : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
        <button type="button" aria-label={language === 'vi' ? 'Thêm vào dự án' : 'Add to project'} className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-border)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]">
          <FolderPlus className="h-4 w-4" />
        </button>
        <Badge variant={note.status === 'open' ? 'info' : 'success'}>
          {
            {
              recording: t.meetingNotes.statusOpen,
              stalled: t.meetingNotes.statusStalled,
              recorded: t.meetingNotes.statusRecorded,
              summarized: t.meetingNotes.statusSummarized,
            }[meetingPhase(note, Date.now())]
          }
        </Badge>
        {/* Ngày giờ bắt đầu và thời lượng nằm ngay cạnh trạng thái: mở lại một
            cuộc họp cũ mà chỉ thấy tên thì không biết nó diễn ra lúc nào. */}
        <span className="text-xs text-[var(--color-text-secondary)]">
          {new Date(note.startedAt).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US')}
          {(() => {
            const durationMs = meetingDurationMs(note, meetingPhase(note, Date.now()), Date.now());
            return durationMs === null
              ? ''
              : ` · ${formatDuration(durationMs, {
                  hour: t.meetingNotes.durationHour,
                  minute: t.meetingNotes.durationMinute,
                  lessThanMinute: t.meetingNotes.durationLessThanMinute,
                })}`;
          })()}
        </span>
      </div>

      {isLocked && (
        <p className="text-xs text-[var(--color-text-secondary)]">{t.meetingNotes.lockedAfterEnd}</p>
      )}

      {tab === 'notes' && (
        <textarea
          value={notes}
          disabled={isLocked}
          placeholder={t.meetingNotes.notesPlaceholder}
          onChange={(event) => {
            setNotes(event.target.value);
            scheduleSave({ notes: event.target.value });
          }}
          rows={16}
          className="w-full p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-sm leading-relaxed text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] disabled:opacity-80"
        />
      )}

      {tab === 'transcript' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            {!isLocked && (
              <Button
                size="sm"
                variant={isLive ? 'primary' : 'outline'}
                aria-pressed={isLive}
                onClick={() => setIsLive((current) => !current)}
                icon={<Radio className="w-3.5 h-3.5" />}
              >
                {isLive ? t.meetingNotes.liveStop : t.meetingNotes.liveStart}
              </Button>
            )}
            {lastSyncedAt && (
              <span className="text-xs text-[var(--color-text-secondary)]">
                {t.meetingNotes.liveLastSynced}{' '}
                {lastSyncedAt.toLocaleTimeString(language === 'vi' ? 'vi-VN' : 'en-US')}
              </span>
            )}
            {liveError && <span className="text-xs text-[var(--color-danger)]">{liveError}</span>}
          </div>

          {transcriptTurns.length === 0 ? (
            <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] space-y-1">
              <p className="text-sm text-[var(--color-text-primary)]">{t.meetingNotes.transcriptEmpty}</p>
              <p className="text-xs text-[var(--color-text-secondary)]">{t.meetingNotes.transcriptEmptyHint}</p>
            </div>
          ) : (
            /* Chỉ hai kiểu bong bóng và một nhãn người nói. Mốc giờ bỏ khỏi mặt
               đọc vì với chunk 5 giây thì mỗi lượt kèm một con số làm mắt vấp
               liên tục; ai cần đối chiếu vẫn có nguyên văn trong ô sửa bên dưới. */
            <ol className="space-y-3">
              {transcriptTurns.map((turn, index) =>
                turn.kind === 'raw' ? (
                  <li
                    key={turn.key}
                    ref={index === turnCount - 1 ? lastTurnRef : undefined}
                    className="max-w-[85%] px-4 py-2.5 rounded-2xl border border-dashed border-[var(--color-border-strong)] space-y-1"
                  >
                    {/* Nhãn này chỉ xuất hiện với dòng hỏng — hiếm, nên không
                        làm rối mặt đọc, mà thiếu nó thì bong bóng gạch đứt
                        trông như một lỗi hiển thị. */}
                    <span className="text-[11px] text-[var(--color-text-secondary)]">
                      {t.meetingNotes.transcriptUnparsed}
                    </span>
                    <p className="text-sm whitespace-pre-wrap text-[var(--color-text-primary)]">
                      {turn.raw}
                    </p>
                  </li>
                ) : (
                  <li
                    key={turn.key}
                    ref={index === turnCount - 1 ? lastTurnRef : undefined}
                    className={`flex flex-col gap-1 ${turn.isSelf ? 'items-end' : 'items-start'}`}
                  >
                    <span className="text-xs text-[var(--color-text-secondary)]">{turn.speaker}</span>
                    <p
                      className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                        turn.isSelf
                          ? 'bg-[var(--color-accent-soft)] text-[var(--color-text-primary)]'
                          : 'bg-[var(--color-surface)] text-[var(--color-text-primary)]'
                      }`}
                    >
                      {turn.content}
                    </p>
                  </li>
                ),
              )}
            </ol>
          )}

          {/* Ô nguyên văn thu vào một hàng gấp: nó là công cụ sửa lỗi và dán tay,
              không phải thứ cần nhìn suốt buổi họp — để mở sẵn thì cùng một nội
              dung hiện hai lần trên cùng màn hình. */}
          <details className="group">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
              <ChevronRight className="w-3.5 h-3.5 transition-transform group-open:rotate-90" />
              {t.meetingNotes.transcriptRawToggle}
            </summary>
            <textarea
              value={transcript}
              disabled={isLocked}
              placeholder={t.meetingNotes.transcriptPlaceholder}
              onChange={(event) => {
                setTranscript(event.target.value);
                scheduleSave({ transcript: event.target.value });
              }}
              rows={12}
              className="mt-3 w-full p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-sm leading-relaxed font-mono text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] disabled:opacity-80"
            />
          </details>
        </div>
      )}

      {tab === 'summary' && (
        <div className="space-y-5">
          {note.status === 'open' ? (
            <p className="text-sm text-[var(--color-text-secondary)]">{t.meetingNotes.notEndedYet}</p>
          ) : (
            <>
              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-[var(--color-text-primary)] font-heading">
                  {t.meetingNotes.summaryHeading}
                </h2>
                <p className="text-sm text-[var(--color-text-secondary)] whitespace-pre-wrap">
                  {note.summary || t.meetingNotes.noSummary}
                </p>
              </section>

              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-[var(--color-text-primary)] font-heading">
                  {t.meetingNotes.decisionsHeading}
                </h2>
                {decisions.length === 0 ? (
                  <p className="text-sm text-[var(--color-text-secondary)]">{t.meetingNotes.noDecisions}</p>
                ) : (
                  <ul className="list-disc pl-5 space-y-1 text-sm text-[var(--color-text-secondary)]">
                    {decisions.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-[var(--color-text-primary)] font-heading">
                  {t.meetingNotes.actionsHeading}
                </h2>
                {note.actionItems.length === 0 ? (
                  <p className="text-sm text-[var(--color-text-secondary)]">{t.meetingNotes.noActions}</p>
                ) : (
                  <ul className="space-y-3">
                    {note.actionItems.map((item) => (
                      <li
                        key={item.id}
                        className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] space-y-2"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium text-[var(--color-text-primary)]">{item.title}</p>
                          {item.status === 'accepted' && (
                            <Badge variant="success">{t.meetingNotes.accepted}</Badge>
                          )}
                          {item.status === 'dismissed' && (
                            <Badge variant="neutral">{t.meetingNotes.dismissed}</Badge>
                          )}
                        </div>

                        {item.detail && (
                          <p className="text-xs text-[var(--color-text-secondary)]">{item.detail}</p>
                        )}

                        <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--color-text-secondary)]">
                          <span className="inline-flex items-center gap-1">
                            <User className="w-3.5 h-3.5" />
                            {item.assigneeAmbiguous || !item.assignee
                              ? t.meetingNotes.assigneeUnknown
                              : `${t.meetingNotes.assignee}: ${item.assignee}`}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <CalendarClock className="w-3.5 h-3.5" />
                            {item.dueAt
                              ? new Date(item.dueAt).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US')
                              : item.ambiguous
                                ? `${t.meetingNotes.timeAmbiguous}: “${item.timeExpression}”`
                                : t.meetingNotes.timeUnknown}
                          </span>
                        </div>

                        {item.evidenceQuote && (
                          <blockquote className="pl-3 border-l-2 border-[var(--color-border-strong)] text-xs italic text-[var(--color-text-secondary)]">
                            {t.meetingNotes.evidence}: “{item.evidenceQuote}”
                          </blockquote>
                        )}

                        {item.status === 'suggested' && (
                          <div className="flex items-center gap-2 pt-1">
                            <Button
                              size="sm"
                              disabled={pendingItemId === item.id}
                              onClick={() => handleAccept(item)}
                              icon={<Check className="w-3.5 h-3.5" />}
                            >
                              {t.meetingNotes.accept}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={pendingItemId === item.id}
                              onClick={() => handleDismiss(item)}
                              icon={<X className="w-3.5 h-3.5" />}
                            >
                              {t.meetingNotes.dismiss}
                            </Button>
                          </div>
                        )}

                        {item.status === 'accepted' && (
                          <Button size="sm" variant="ghost" onClick={() => navigate('/tasks')}>
                            {t.meetingNotes.openTask}
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
};
