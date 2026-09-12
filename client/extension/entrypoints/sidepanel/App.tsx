import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Ban,
  BellRing,
  CalendarDays,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  FileText,
  Flag,
  Lightbulb,
  ListChecks,
  ListOrdered,
  Lock,
  LogOut,
  Mail,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings,
  Sun,
  Target,
  Trash2,
  User,
  Users,
  Wrench,
  X,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { HeaderAvatar } from "@/components/HeaderAvatar";
import { ReminderPopupSetting } from "@/components/ReminderPopupSetting";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Toggle } from "@/components/ui/Toggle";
import { applyWebSession, getSession, getValidAccessToken, loginWithCredentials, logout } from "@/lib/auth";
import {
  confirmTask,
  createTaskFromSuggestion,
  listConfirmedTasks,
  listProposedTasks,
  summarizePageExtraction,
  ApiError,
} from "@/lib/api";
import { applyHighContrast, highContrastItem, initHighContrast } from "@/lib/highContrast";
import { redactSensitive } from "@/lib/pageExtraction";
import type { ExtractedPageData } from "@/lib/pageExtraction";
import { PALETTE_LABEL, PALETTE_NAMES, applyPalette, initPalette, paletteItem } from "@/lib/palette";
import type { PaletteName } from "@/lib/palette";
import { applyTextSize, initTextSize, textSizeItem } from "@/lib/textSize";
import type { TextSize } from "@/lib/textSize";
import { applyTheme, initTheme, themeItem, toggleTheme } from "@/lib/theme";
import type { ThemeMode } from "@/lib/theme";
import { activeReminderBundleItem, authSessionItem, autoOpenReminderPopupItem } from "@/lib/storage";
import type { AuthSession, NotificationBundle, Task } from "@/types";
import type { WebSession } from "@/lib/webSession";

const WEB_APP_URL = import.meta.env.WXT_WEB_APP_URL;

function tasksPageUrl(): string {
  return `${WEB_APP_URL.replace(/\/$/, "")}/tasks`;
}

/**
 * Đọc localStorage của tab web app đang mở (nếu có) — hàm inline, KHÔNG dùng
 * chung `readWebSessionFromPage` vì `chrome.scripting.executeScript({func})`
 * tách hàm khỏi closure gốc, import/hằng số ngoài thân hàm sẽ mất khi Chrome
 * chạy nó trong tab đích.
 *
 * Trả về `undefined` khi không có tab web app nào đang mở (chưa biết trạng
 * thái, giữ nguyên session đã đồng bộ trước đó) — khác với `null` (tab đang
 * mở xác nhận đã đăng xuất, phải xoá session extension theo).
 */
async function probeWebAppSession(): Promise<WebSession | null | undefined> {
  const pattern = `${WEB_APP_URL.replace(/\/$/, "")}/*`;
  const tabs = await chrome.tabs.query({ url: pattern });
  const tab = tabs.find((t) => t.id !== undefined);
  if (!tab?.id) {
    console.error(`[mondaiy] Không tìm thấy tab web app khớp "${pattern}" (${tabs.length} tab query được).`);
    return undefined;
  }

  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const KEY = "nav_session";
      for (const storage of [window.localStorage, window.sessionStorage]) {
        try {
          const raw = storage.getItem(KEY);
          if (!raw) continue;
          const parsed = JSON.parse(raw);
          if (typeof parsed?.accessToken === "string" && typeof parsed?.refreshToken === "string") {
            return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken };
          }
        } catch {
          // thử storage còn lại
        }
      }
      return null;
    },
  });
  return results[0]?.result ?? null;
}

/** Kiểm tra web app đã đăng nhập chưa trước khi tự đòi đăng nhập ở extension. */
async function reconcileWebSession(): Promise<void> {
  try {
    const probed = await probeWebAppSession();
    if (probed !== undefined) await applyWebSession(probed);
  } catch (error) {
    // Tab đặc biệt (chrome://, extension gallery...) không cho executeScript — bỏ qua.
    // Log lại để không phải đoán mù khi việc mượn session thất bại vì lý do khác.
    console.error("[mondaiy] reconcileWebSession thất bại:", error);
  }
}

function formatDue(task: Task): string {
  if (task.ambiguous || !task.dueAt) return "Chưa rõ thời gian";
  const date = new Date(task.dueAt);
  return task.allDay
    ? date.toLocaleDateString("vi-VN", { weekday: "short", day: "numeric", month: "short" })
    : date.toLocaleString("vi-VN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function openOptions(): void {
  chrome.runtime.openOptionsPage();
}

function openWebApp(): void {
  void chrome.tabs.create({ url: tasksPageUrl() });
}

// Màu đại diện mỗi tông trên chấm chọn — Paper dùng nền giấy đặc trưng (chứ
// không phải primary teal của nó, không "đọc" được là Paper); 3 tông còn lại
// dùng primary vì đã đủ nổi bật để nhận ra. Giá trị lấy đúng từ tailwind.css
// (cùng bảng dùng ở entrypoints/options/App.tsx).
const PALETTE_SWATCH: Record<PaletteName, string> = {
  paper: "#fffedd",
  jade: "#2f6b4f",
  plum: "#6b3f73",
  quartz: "#3d4a54",
};

const TEXT_SIZE_OPTIONS: { value: TextSize; label: string }[] = [
  { value: "sm", label: "S" },
  { value: "md", label: "M" },
  { value: "lg", label: "L" },
];

function formatSessionExpiry(expiresAt: number): string {
  const date = new Date(expiresAt);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  return `${hours}:${minutes} ${day}/${month}/${year}`;
}

/** Hàng bật/tắt dạng công tắc — cùng kiểu dáng pill+thumb trượt với
 * ReminderPopupSetting, dùng lại cho "Chế độ tối"/"Độ tương phản cao" để
 * nhất quán một ngôn ngữ hình ảnh cho MỌI công tắc trong trang Cài đặt. */
function SettingsToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-3 cursor-pointer">
      <span className="text-sm text-secondary">{label}</span>
      <Toggle aria-label={label} checked={checked} onChange={onChange} />
    </label>
  );
}

/** Cài đặt — hiện NGAY TRONG side panel thay vì mở options.html ở tab trình
 * duyệt thật (phản hồi người dùng 2026-08-27: "muốn cái đặt không phải là 1
 * tab ở trình duyệt thật sự"). Thay thế toàn bộ nội dung panel khi mở, có nút
 * quay lại ở trên cùng — mọi state (palette/cỡ chữ/tương phản/theme) tự đọc
 * riêng ở đây, KHÔNG chia sẻ với usePreferenceSync() (hàm đó chỉ áp lên DOM,
 * không giữ state để đọc lại) — ghi qua đúng cùng storage item nên
 * usePreferenceSync() ở App() vẫn tự động thấy giá trị mới qua watch().
 *
 * CỐ Ý không có phần "Cấp quyền micro" ở đây — getUserMedia() cần mở trong
 * tab trình duyệt thật để Chrome hiện được hộp thoại xin quyền (xem
 * entrypoints/options/App.tsx), side panel là ngữ cảnh khác chưa kiểm chứng
 * được prompt có hiện đúng hay không — fallback "Cấp quyền micro" trong
 * RecordingPanel vẫn mở options.html như cũ cho đúng luồng đã chứng minh
 * hoạt động, không đổi. */
function SettingsView({ onBack }: { onBack: () => void }) {
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);
  const [pending, setPending] = useState(false);
  const [autoOpenReminder, setAutoOpenReminder] = useState<boolean | undefined>(undefined);
  const [savingReminderSetting, setSavingReminderSetting] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [palette, setPaletteState] = useState<PaletteName>("paper");
  const [textSize, setTextSizeState] = useState<TextSize>("md");
  const [highContrast, setHighContrastState] = useState(false);

  useEffect(() => {
    void getSession().then(setSession);
    void autoOpenReminderPopupItem.getValue().then(setAutoOpenReminder);
    void initTheme().then(setTheme);
    void paletteItem.getValue().then(setPaletteState);
    void textSizeItem.getValue().then(setTextSizeState);
    void highContrastItem.getValue().then(setHighContrastState);
    return autoOpenReminderPopupItem.watch((value) => setAutoOpenReminder(value));
  }, []);

  async function handleToggleTheme() {
    setTheme(await toggleTheme(theme));
  }

  async function handlePaletteChange(name: PaletteName) {
    setPaletteState(name);
    applyPalette(name);
    await paletteItem.setValue(name);
  }

  async function handleTextSizeChange(size: TextSize) {
    setTextSizeState(size);
    applyTextSize(size);
    await textSizeItem.setValue(size);
  }

  async function handleHighContrastChange(enabled: boolean) {
    setHighContrastState(enabled);
    applyHighContrast(enabled);
    await highContrastItem.setValue(enabled);
  }

  async function handleReminderPopupChange(checked: boolean) {
    setSavingReminderSetting(true);
    try {
      await autoOpenReminderPopupItem.setValue(checked);
      setAutoOpenReminder(checked);
    } finally {
      setSavingReminderSetting(false);
    }
  }

  async function handleForget() {
    setPending(true);
    try {
      await logout();
      setSession(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          aria-label="Quay lại"
          className="rounded-lg p-1.5 text-muted transition-colors hover:bg-focus/10 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="font-heading text-base font-semibold text-primary">Cài đặt</h1>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3">
        <section className="app-panel flex flex-col gap-2.5 rounded-xl p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">Tài khoản</span>
            {session && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Đã kết nối
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-focus/15 overflow-hidden">
              {session?.avatarUrl ? (
                <img
                  src={session.avatarUrl}
                  alt="Ảnh đại diện"
                  width={40}
                  height={40}
                  referrerPolicy="no-referrer"
                  className="h-10 w-10 rounded-full object-cover"
                />
              ) : (
                <User className="h-5 w-5 text-primary" aria-hidden />
              )}
            </div>
            <div className="min-w-0 flex-1">
              {session === undefined && <p className="text-xs text-muted">Đang kiểm tra...</p>}
              {session === null && <p className="text-xs text-secondary">Chưa đăng nhập</p>}
              {session && (
                <>
                  <p className="truncate text-xs font-semibold text-primary">
                    {session.email || "Tài khoản mondaiy"}
                  </p>
                  <p className="text-[11px] text-muted">
                    Tự động gia hạn • Hạn: {formatSessionExpiry(session.expiresAt)}
                  </p>
                </>
              )}
            </div>
          </div>

          {session ? (
            <Button
              variant="secondary"
              onClick={() => void handleForget()}
              disabled={pending}
              className="mt-1 w-full justify-center gap-1.5 text-red-600 hover:bg-red-500/10 hover:text-red-700 dark:text-red-400"
            >
              <LogOut className="h-3.5 w-3.5" />
              Đăng xuất khỏi Extension
            </Button>
          ) : (
            <Button onClick={openWebApp} className="mt-1 w-full justify-center gap-1.5">
              Đăng nhập qua web
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          )}
        </section>

        <section className="app-panel flex flex-col gap-4 rounded-xl p-3">
          <h2 className="font-heading text-sm font-semibold text-primary">Hiển thị</h2>

          <SettingsToggleRow label="Chế độ tối" checked={theme === "dark"} onChange={() => void handleToggleTheme()} />

          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Tông màu</p>
            <div className="flex gap-3" role="radiogroup" aria-label="Tông màu">
              {PALETTE_NAMES.map((name) => (
                <button
                  key={name}
                  type="button"
                  role="radio"
                  aria-checked={palette === name}
                  aria-label={PALETTE_LABEL[name]}
                  title={PALETTE_LABEL[name]}
                  onClick={() => void handlePaletteChange(name)}
                  style={{ backgroundColor: PALETTE_SWATCH[name] }}
                  className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${
                    palette === name ? "border-primary shadow-md" : "border-border"
                  }`}
                >
                  {palette === name && (
                    <Check
                      className="h-3.5 w-3.5"
                      style={{ color: name === "paper" ? "#356f83" : "#ffffff" }}
                      aria-hidden
                    />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Cỡ chữ</p>
            <div className="flex rounded-lg border border-border bg-app-bg p-1" role="radiogroup" aria-label="Cỡ chữ">
              {TEXT_SIZE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={textSize === option.value}
                  onClick={() => void handleTextSizeChange(option.value)}
                  className={`flex-1 rounded-md py-1.5 text-sm font-semibold transition-colors ${
                    textSize === option.value ? "bg-surface text-primary shadow-sm" : "text-muted hover:text-secondary"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <SettingsToggleRow
            label="Độ tương phản cao"
            checked={highContrast}
            onChange={(c) => void handleHighContrastChange(c)}
          />
        </section>

        <ReminderPopupSetting
          checked={autoOpenReminder ?? false}
          disabled={autoOpenReminder === undefined || savingReminderSetting}
          onChange={(checked) => void handleReminderPopupChange(checked)}
        />
      </div>
    </div>
  );
}

export interface ParsedTaskBrief {
  cleanDetail: string;
  expectedOutput: string | null;
  acceptanceCriteria: string | null;
  contextInput: string | null;
  constraints: string | null;
  executionSteps: string[] | null;
  executionTool: string | null;
  executionMethod: string | null;
  statedPriority: string | null;
  assignee: string | null;
  stakeholders: string | null;
  deliverTo: string | null;
  sourceText: string | null;
}

export function parseTaskBrief(task: Task): ParsedTaskBrief {
  let cleanDetail = (task.detail || "").trim();
  let expectedOutput = task.expectedOutput || null;
  let acceptanceCriteria = task.acceptanceCriteria || null;
  let contextInput = task.contextInput || null;
  let constraints = task.constraints || null;
  let executionSteps = task.executionSteps && task.executionSteps.length > 0 ? task.executionSteps : null;
  let executionTool = task.executionTool || null;
  let executionMethod = task.executionMethod || null;
  let statedPriority = task.statedPriority || null;
  let assignee = task.assignee || null;
  let stakeholders = task.stakeholders
    ? (Array.isArray(task.stakeholders) ? task.stakeholders.join(", ") : task.stakeholders)
    : null;
  let deliverTo = task.deliverTo || null;
  let sourceText: string | null = null;

  // Trích xuất các trường nếu bị gộp trong detail (hỗ trợ dữ liệu cũ hoặc gộp chuỗi)
  const markerPatterns: { key: keyof ParsedTaskBrief; regex: RegExp }[] = [
    { key: "expectedOutput", regex: /(?:Kết quả mong đợi|Expected output):\s*([^]+?)(?=(?:Ràng buộc|Các bước thực hiện|Công cụ|Cách làm đề xuất|Độ ưu tiên|Người phụ trách|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "constraints", regex: /(?:Ràng buộc|Constraints?):\s*([^]+?)(?=(?:Kết quả mong đợi|Các bước thực hiện|Công cụ|Cách làm đề xuất|Độ ưu tiên|Người phụ trách|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "executionSteps", regex: /(?:Các bước thực hiện|Execution steps):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Công cụ|Cách làm đề xuất|Độ ưu tiên|Người phụ trách|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "executionTool", regex: /(?:Công cụ|Tool):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Các bước thực hiện|Cách làm đề xuất|Độ ưu tiên|Người phụ trách|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "executionMethod", regex: /(?:Cách làm đề xuất|Method):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Các bước thực hiện|Công cụ|Độ ưu tiên|Người phụ trách|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "statedPriority", regex: /(?:Độ ưu tiên|Priority):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Các bước thực hiện|Công cụ|Cách làm đề xuất|Người phụ trách|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "assignee", regex: /(?:Người phụ trách|Assignee):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Các bước thực hiện|Công cụ|Cách làm đề xuất|Độ ưu tiên|Người liên quan|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "stakeholders", regex: /(?:Người liên quan|Stakeholders):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Các bước thực hiện|Công cụ|Cách làm đề xuất|Độ ưu tiên|Người phụ trách|Hoàn thành gửi cho|Nguồn|Hạn:)|$)/i },
    { key: "deliverTo", regex: /(?:Hoàn thành gửi cho|Deliver to):\s*([^]+?)(?=(?:Kết quả mong đợi|Ràng buộc|Các bước thực hiện|Công cụ|Cách làm đề xuất|Độ ưu tiên|Người phụ trách|Người liên quan|Nguồn|Hạn:)|$)/i },
    { key: "sourceText", regex: /(?:Nguồn|Source):\s*([^]+?)$/i },
  ];

  for (const { key, regex } of markerPatterns) {
    const match = regex.exec(cleanDetail);
    if (match && match[1]) {
      const val = match[1].trim();
      if (val) {
        if (key === "expectedOutput" && !expectedOutput) expectedOutput = val;
        else if (key === "constraints" && !constraints) constraints = val;
        else if (key === "executionSteps" && !executionSteps) {
          executionSteps = val.split("\n").map((s) => s.replace(/^[-*\d.]+\s*/, "").trim()).filter(Boolean);
        } else if (key === "executionTool" && !executionTool) executionTool = val;
        else if (key === "executionMethod" && !executionMethod) executionMethod = val;
        else if (key === "statedPriority" && !statedPriority) statedPriority = val;
        else if (key === "assignee" && !assignee) assignee = val;
        else if (key === "stakeholders" && !stakeholders) stakeholders = val;
        else if (key === "deliverTo" && !deliverTo) deliverTo = val;
        else if (key === "sourceText" && !sourceText) sourceText = val;
      }
    }
  }

  const firstMarkerIndex = cleanDetail.search(/(?:Hạn:\s*không rõ|Kết quả mong đợi:|Ràng buộc:|Các bước thực hiện:|Công cụ:|Cách làm đề xuất:|Độ ưu tiên:|Người phụ trách:|Người liên quan:|Hoàn thành gửi cho:|Nguồn:)/i);
  if (firstMarkerIndex > 0) {
    cleanDetail = cleanDetail.substring(0, firstMarkerIndex).trim();
  }

  return {
    cleanDetail,
    expectedOutput,
    acceptanceCriteria,
    contextInput,
    constraints,
    executionSteps,
    executionTool,
    executionMethod,
    statedPriority,
    assignee,
    stakeholders,
    deliverTo,
    sourceText,
  };
}

export function TaskCard({ task }: { task: Task }) {
  const [expanded, setExpanded] = useState(false);
  const brief = parseTaskBrief(task);
  const firstEvidence = task.evidence[0];
  const hasExtras = Boolean(
    brief.expectedOutput ||
      brief.acceptanceCriteria ||
      brief.contextInput ||
      brief.constraints ||
      (brief.executionSteps && brief.executionSteps.length > 0) ||
      brief.executionTool ||
      brief.executionMethod ||
      brief.statedPriority ||
      brief.stakeholders ||
      brief.deliverTo
  );

  return (
    <li
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      className="app-panel group relative flex flex-col gap-2 rounded-xl p-3.5 transition-all duration-200 hover:-translate-y-0.5 hover:border-focus hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Mức ưu tiên theo hạn — đúng thứ tự duyệt của backend */}
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                priorityTone(task)
              }`}
            >
              {priorityLabel(task)}
            </span>
            {brief.statedPriority && (
              <span className="inline-flex items-center gap-1 rounded-full bg-focus/15 px-2 py-0.5 text-[10px] font-semibold text-primary">
                <Flag className="h-3 w-3" aria-hidden />
                {brief.statedPriority}
              </span>
            )}
            <span className="text-[10px] text-muted">{task.sourceCount} nguồn</span>
            {brief.assignee && (
              <span className="inline-flex items-center gap-1 rounded-full bg-focus/15 px-2 py-0.5 text-[10px] font-medium text-primary">
                <User className="h-3 w-3" aria-hidden />
                {brief.assignee}
              </span>
            )}
          </div>
          <h3 className="font-heading text-sm font-semibold leading-snug text-primary transition-colors group-hover:text-focus">
            {task.title}
          </h3>
        </div>
        <span className="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-secondary">
          <Clock className="h-3.5 w-3.5 text-primary" />
          {formatDue(task)}
        </span>
      </div>

      {brief.cleanDetail && brief.cleanDetail.trim() !== "" && brief.cleanDetail !== firstEvidence?.evidenceQuote && (
        <p className="text-xs leading-relaxed text-secondary line-clamp-2 transition-all duration-200 group-hover:line-clamp-none">
          {brief.cleanDetail}
        </p>
      )}

      {/* Khối Chi tiết Phiếu giao việc đầy đủ (Hiện khi hover / expanded) */}
      {hasExtras && (
        <div
          className={`flex flex-col gap-2 rounded-lg border border-border/70 bg-surface/50 p-2.5 text-xs transition-all duration-300 ${
            expanded ? "max-h-[1000px] opacity-100 mt-1" : "max-h-0 opacity-0 overflow-hidden p-0 border-0 m-0"
          }`}
        >
          <div className="flex items-center justify-between border-b border-border/40 pb-1.5 font-heading text-xs font-semibold text-primary">
            <span className="inline-flex items-center gap-1.5">
              <ClipboardList className="h-3.5 w-3.5 text-focus" aria-hidden />
              Chi tiết phiếu giao việc
            </span>
          </div>

          {/* 1. Đầu ra & Tiêu chí nghiệm thu */}
          {(brief.expectedOutput || brief.acceptanceCriteria) && (
            <div className="space-y-1 rounded-md bg-focus/5 p-2">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-primary">
                <Target className="h-3 w-3 text-focus" aria-hidden />
                Đầu ra & Tiêu chí nghiệm thu
              </span>
              {brief.expectedOutput && (
                <p className="pl-4 text-[11px] text-secondary">
                  <span className="font-medium text-muted">Sản phẩm bàn giao:</span> {brief.expectedOutput}
                </p>
              )}
              {brief.acceptanceCriteria && (
                <p className="pl-4 text-[11px] text-secondary">
                  <span className="font-medium text-muted">Tiêu chuẩn nghiệm thu:</span> {brief.acceptanceCriteria}
                </p>
              )}
            </div>
          )}

          {/* 2. Bối cảnh & Đầu vào */}
          {brief.contextInput && (
            <div className="space-y-0.5 rounded-md border border-border/40 bg-surface p-2">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-primary">
                <FileText className="h-3 w-3 text-focus" aria-hidden />
                Bối cảnh & Đầu vào cần có
              </span>
              <p className="pl-4 text-[11px] leading-relaxed text-secondary">{brief.contextInput}</p>
            </div>
          )}

          {/* 3. Ràng buộc & Điều cấm */}
          {brief.constraints && (
            <div className="space-y-0.5 rounded-md border border-danger/20 bg-danger/10 p-2">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-danger">
                <Ban className="h-3 w-3" aria-hidden />
                Ràng buộc & Điều cấm
              </span>
              <p className="pl-4 text-[11px] leading-relaxed text-danger/90">{brief.constraints}</p>
            </div>
          )}

          {/* 4. Thực thi (Các bước, công cụ, cách làm) */}
          {((brief.executionSteps && brief.executionSteps.length > 0) || brief.executionTool || brief.executionMethod) && (
            <div className="space-y-1.5 rounded-md border border-border/40 bg-surface p-2">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-primary">
                <Lightbulb className="h-3 w-3 text-focus" aria-hidden />
                Phương án thực thi
              </span>
              {brief.executionSteps && brief.executionSteps.length > 0 && (
                <div className="space-y-0.5 pl-4">
                  <span className="text-[10px] font-medium text-muted">Các bước:</span>
                  <ol className="list-decimal space-y-0.5 pl-4 text-[11px] text-secondary">
                    {brief.executionSteps.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ol>
                </div>
              )}
              {brief.executionTool && (
                <p className="pl-4 text-[11px] text-secondary">
                  <span className="font-medium text-muted">Công cụ:</span> {brief.executionTool}
                </p>
              )}
              {brief.executionMethod && (
                <p className="pl-4 text-[11px] text-secondary">
                  <span className="font-medium text-muted">Cách làm đề xuất:</span> {brief.executionMethod}
                </p>
              )}
            </div>
          )}

          {/* 5. Con người & Nơi bàn giao */}
          {(brief.deliverTo || brief.stakeholders) && (
            <div className="grid grid-cols-1 gap-1 rounded-md border border-border/40 bg-surface p-2 text-[11px]">
              {brief.deliverTo && (
                <div className="flex items-center gap-1.5">
                  <Send className="h-3 w-3 shrink-0 text-focus" aria-hidden />
                  <span className="font-medium text-muted">Bàn giao cho:</span>
                  <span className="font-semibold text-primary">{brief.deliverTo}</span>
                </div>
              )}
              {brief.stakeholders && (
                <div className="flex items-center gap-1.5">
                  <Users className="h-3 w-3 shrink-0 text-focus" aria-hidden />
                  <span className="font-medium text-muted">Bên liên quan (RACI):</span>
                  <span className="text-secondary">{brief.stakeholders}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Trích dẫn bằng chứng gốc */}
      {(firstEvidence || brief.sourceText) && (
        <a
          href={firstEvidence?.deepLink || (brief.sourceText?.startsWith("http") ? brief.sourceText : undefined)}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col gap-1 rounded-lg border border-border bg-focus/10 p-2.5 text-[11px] text-secondary transition-colors hover:border-focus/40 hover:bg-focus/15 hover:text-primary"
        >
          <div className="flex items-center justify-between text-[10px] text-muted">
            <span className="font-medium">
              {firstEvidence?.provider ? `Nguồn: ${firstEvidence.provider}` : "Trích dẫn nguồn"}
            </span>
            <span className="inline-flex items-center gap-1 font-semibold text-primary group-hover:underline">
              Mở nguồn gốc
              <ExternalLink className="h-3 w-3 shrink-0" />
            </span>
          </div>
          <span className="italic line-clamp-2 transition-all duration-200 group-hover:line-clamp-none">
            &ldquo;{firstEvidence?.evidenceQuote || brief.sourceText}&rdquo;
          </span>
          {task.evidence.length > 1 && (
            <span className="mt-0.5 text-[10px] font-medium text-muted">
              + {task.evidence.length - 1} trích dẫn nguồn khác
            </span>
          )}
        </a>
      )}
    </li>
  );
}

/** Số ngày còn lại tới hạn (âm = quá hạn), so theo ngày lịch local. Nhận kiểu
 * hẹp `{ dueAt }` (không phải nguyên `Task`) để dùng chung được cho cả
 * TaskCard (việc đã xác nhận) lẫn SuggestionCard (gợi ý chưa xác nhận, xem
 * suggestionUrgency() bên dưới) — hai kiểu khác nhau nhưng cùng có dueAt. */
export function daysUntil(item: { dueAt: string | null }): number | null {
  if (!item.dueAt) return null;
  const due = new Date(item.dueAt);
  if (Number.isNaN(due.getTime())) return null;
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  return Math.round((startOfDay(due) - startOfDay(new Date())) / 86_400_000);
}

/** Badge mức khẩn cấp cho SuggestionCard (tab "Lấy dữ liệu", trước khi
 * xác nhận) — 3 mức theo yêu cầu: còn ≤1 ngày (kể cả quá hạn/hôm nay) =
 * "Cảnh báo", trong vòng 3 ngày = "Cần chú ý", chưa rõ hạn (dueAt null hoặc
 * không parse được) = "Cần xem". Còn lại (>3 ngày) không hiện badge — chưa
 * đủ gấp để làm nổi bật. Khác priorityLabel()/priorityTone() (dùng riêng cho
 * TaskCard, đã xác nhận, wording khác: QUÁ HẠN/HÔM NAY/NGÀY MAI/CÒN N NGÀY) —
 * không đổi hàm đó vì tab kia đã hoạt động đúng, không phải phạm vi yêu cầu. */
export function suggestionUrgency(item: { dueAt: string | null }): { label: string; tone: string } | null {
  const days = daysUntil(item);
  if (days === null) return { label: "Cần xem", tone: "bg-muted/30 text-secondary" };
  if (days <= 1) return { label: "Cảnh báo", tone: "bg-danger/15 text-danger" };
  if (days <= 3) return { label: "Cần chú ý", tone: "bg-focus/20 text-primary" };
  return null;
}

export function priorityLabel(task: Task): string {
  if (task.ambiguous) return "CHƯA RÕ";
  const days = daysUntil(task);
  if (days === null) return "KHÔNG HẠN";
  if (days < 0) return "QUÁ HẠN";
  if (days === 0) return "HÔM NAY";
  if (days === 1) return "NGÀY MAI";
  return `CÒN ${days} NGÀY`;
}

function priorityTone(task: Task): string {
  const days = daysUntil(task);
  if (task.ambiguous || days === null) return "bg-muted/30 text-secondary";
  if (days < 0) return "bg-danger/15 text-danger";
  if (days <= 1) return "bg-focus/20 text-primary";
  return "bg-muted/30 text-secondary";
}

/** Thứ tự duyệt giống backend list_tasks: quá hạn trước, rồi hôm nay, ngày
 * mai, các ngày kế tiếp; việc không hạn xuống cuối. */
export function compareTaskPriority(a: Task, b: Task): number {
  const da = daysUntil(a);
  const db = daysUntil(b);
  if (da === null && db === null) return 0;
  if (da === null) return 1;
  if (db === null) return -1;
  return da - db;
}

function ReminderPanel() {
  const [bundle, setBundle] = useState<NotificationBundle | null>(null);

  useEffect(() => {
    void activeReminderBundleItem.getValue().then(setBundle);
    return activeReminderBundleItem.watch((value) => setBundle(value));
  }, []);

  if (!bundle || bundle.tasks.length === 0) return null;

  const firstLink = bundle.tasks.find((task) => task.evidenceDeepLink)?.evidenceDeepLink;

  async function openReminder() {
    await activeReminderBundleItem.setValue(null);
    await chrome.tabs.create({ url: firstLink ?? tasksPageUrl() });
  }

  return (
    <section className="mb-3 rounded-xl border border-focus/40 bg-focus/10 p-3" aria-live="assertive">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-focus/20">
          <BellRing className="h-4 w-4 text-primary" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold text-primary">Việc đến hạn</p>
          <ul className="mt-1 space-y-1">
            {bundle.tasks.map((task, index) => (
              <li key={`${task.taskId ?? "notice"}-${index}`} className="text-xs leading-snug text-secondary">
                {task.title}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => void openReminder()}
            className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
          >
            Xem chi tiết
            <ExternalLink className="h-3 w-3" aria-hidden />
          </button>
        </div>
        <button
          type="button"
          aria-label="Ẩn reminder này"
          onClick={() => void activeReminderBundleItem.setValue(null)}
          className="rounded-md p-1 text-muted transition-colors hover:bg-focus/15 hover:text-primary"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </section>
  );
}


type LoadState = "loading" | "guest" | "error" | "ready";

/** Số việc quá hạn / trong 7 ngày tới (kể cả hôm nay) / tổng — dùng cho dải
 * thống kê đầu tab. Luôn tính trên TOÀN BỘ task đã tải, không phải danh sách
 * đã lọc theo tìm kiếm/bộ lọc, để dải thống kê phản ánh đúng tổng quan. */
export function computeTaskStats(tasks: Task[]): { overdue: number; thisWeek: number; total: number } {
  let overdue = 0;
  let thisWeek = 0;
  for (const task of tasks) {
    if (task.ambiguous) continue;
    const days = daysUntil(task);
    if (days === null) continue;
    if (days < 0) overdue += 1;
    else if (days <= 6) thisWeek += 1;
  }
  return { overdue, thisWeek, total: tasks.length };
}

type TaskFilter = "all" | "overdue" | "thisWeek" | "noDate";

const TASK_FILTER_LABEL: Record<TaskFilter, string> = {
  all: "Tất cả",
  overdue: "Quá hạn",
  thisWeek: "Trong tuần",
  noDate: "Chưa rõ hạn",
};

/** Cùng 2 mốc với computeTaskStats() (quá hạn / trong 7 ngày) — người dùng
 * lọc đúng theo cái đang thấy ở dải thống kê, không phải tiêu chí khác. */
export function matchesTaskFilter(task: Task, filter: TaskFilter): boolean {
  if (filter === "all") return true;
  const days = daysUntil(task);
  const noDate = task.ambiguous || days === null;
  if (filter === "noDate") return noDate;
  if (noDate) return false;
  if (filter === "overdue") return (days as number) < 0;
  return (days as number) >= 0 && (days as number) <= 6;
}

function dateGroupLabel(task: Task): string {
  if (task.ambiguous) return "Chưa rõ hạn";
  const days = daysUntil(task);
  if (days === null) return "Không hạn";
  if (days < 0) return "Quá hạn";
  if (days === 0) return "Hôm nay";
  if (days === 1) return "Ngày mai";
  return new Date(task.dueAt as string).toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/** Nhóm task theo ngày hạn chót cho chế độ xem "Theo ngày" — task đầu vào
 * PHẢI đã sắp theo compareTaskPriority (quá hạn trước, không hạn cuối) để
 * gom đúng nhóm liên tiếp, không cần sắp lại ở đây. */
export function groupTasksByDate(tasks: Task[]): { label: string; tasks: Task[] }[] {
  const groups: { label: string; tasks: Task[] }[] = [];
  for (const task of tasks) {
    const label = dateGroupLabel(task);
    const lastGroup = groups[groups.length - 1];
    if (lastGroup && lastGroup.label === label) lastGroup.tasks.push(task);
    else groups.push({ label, tasks: [task] });
  }
  return groups;
}

function TaskStatsBar({ stats }: { stats: { overdue: number; thisWeek: number; total: number } }) {
  return (
    <div className="app-panel grid grid-cols-3 gap-2 rounded-xl p-3 text-center">
      <div>
        <p className="text-xl font-bold tabular-nums text-danger">{stats.overdue}</p>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Quá hạn</p>
      </div>
      <div className="border-x border-border">
        <p className="text-xl font-bold tabular-nums text-primary">{stats.thisWeek}</p>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Tuần này</p>
      </div>
      <div>
        <p className="text-xl font-bold tabular-nums text-secondary">{stats.total}</p>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Tổng</p>
      </div>
    </div>
  );
}

function TaskSearchBar({
  query,
  onQueryChange,
  filter,
  onFilterChange,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  filter: TaskFilter;
  onFilterChange: (value: TaskFilter) => void;
}) {
  return (
    <div className="flex gap-2">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
        <Input
          aria-label="Tìm kiếm công việc"
          placeholder="Tìm kiếm công việc..."
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          className="pl-8"
        />
      </div>
      <select
        aria-label="Lọc công việc"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value as TaskFilter)}
        className="rounded-lg border border-border bg-surface px-2 text-xs text-secondary shadow-inner focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
      >
        {(Object.keys(TASK_FILTER_LABEL) as TaskFilter[]).map((key) => (
          <option key={key} value={key}>
            {TASK_FILTER_LABEL[key]}
          </option>
        ))}
      </select>
    </div>
  );
}

type TaskViewMode = "list" | "byDate";

function TaskViewModeToggle({ mode, onChange }: { mode: TaskViewMode; onChange: (mode: TaskViewMode) => void }) {
  return (
    <div className="flex rounded-lg border border-border bg-app-bg p-1" role="radiogroup" aria-label="Chế độ xem">
      {(
        [
          { value: "list" as const, label: "Danh sách" },
          { value: "byDate" as const, label: "Theo ngày" },
        ]
      ).map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={mode === option.value}
          onClick={() => onChange(option.value)}
          className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition-colors ${
            mode === option.value ? "bg-surface text-primary shadow-sm" : "text-muted hover:text-secondary"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Form thêm task thủ công gọn — tái dùng thẳng POST /tasks/from-suggestion
 * (createTaskFromSuggestion) vì endpoint đó vốn đã nhận title/detail/dueAt
 * tự do, không cần endpoint riêng cho "thêm tay". */
function QuickAddTaskForm({ onCreated, onCancel }: { onCreated: () => void; onCancel: () => void }) {
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit() {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setErrorMessage("Nhập tiêu đề công việc.");
      return;
    }
    setSaving(true);
    setErrorMessage("");
    try {
      await createTaskFromSuggestion(trimmedTitle, detail.trim(), localInputValueToIso(dueAt));
      onCreated();
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Không thêm được công việc.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="app-panel flex flex-col gap-2 rounded-xl p-3">
      <Input
        aria-label="Tiêu đề công việc mới"
        placeholder="Việc cần làm..."
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        disabled={saving}
        autoFocus
      />
      <textarea
        aria-label="Mô tả (không bắt buộc)"
        placeholder="Mô tả (không bắt buộc)"
        value={detail}
        onChange={(e) => setDetail(e.target.value)}
        disabled={saving}
        rows={2}
        className="w-full resize-y rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-secondary shadow-inner transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
      />
      <label className="flex items-center gap-1.5 text-[11px] font-semibold text-secondary">
        <Clock className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
        Hạn chót
        <input
          aria-label="Hạn chót"
          type="datetime-local"
          value={dueAt}
          onChange={(e) => setDueAt(e.target.value)}
          disabled={saving}
          className="flex-1 rounded-lg border border-border bg-surface px-2 py-1 text-xs text-secondary shadow-inner transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
        />
      </label>
      {errorMessage && <p className="text-[11px] text-danger">{errorMessage}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          Huỷ
        </Button>
        <Button onClick={() => void handleSubmit()} disabled={saving}>
          {saving ? "Đang thêm..." : "Thêm việc"}
        </Button>
      </div>
    </div>
  );
}

function TasksView() {
  const [state, setState] = useState<LoadState>("loading");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [viewMode, setViewMode] = useState<TaskViewMode>("list");
  const [showQuickAdd, setShowQuickAdd] = useState(false);

  // `quiet` = làm mới ngầm (visibilitychange / poll): không chớp về "Đang tải",
  // lỗi mạng thoáng qua thì giữ nguyên danh sách đang hiện, lần sau thử lại.
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setState("loading");
    await reconcileWebSession();
    const session = await getSession();
    if (!session) {
      setState("guest");
      return;
    }
    try {
      // Chính sách 2026-08-25: popup chỉ hiện task ĐÃ duyệt kèm mức ưu tiên;
      // task chờ duyệt chỉ hiện số lượng + link sang web để duyệt.
      const [confirmed, proposed] = await Promise.all([listConfirmedTasks(), listProposedTasks()]);
      setTasks([...confirmed].sort(compareTaskPriority));
      setPendingCount(proposed.length);
      setState("ready");
    } catch (err) {
      if (quiet) return;
      setErrorMessage(err instanceof ApiError ? err.message : "Không tải được danh sách việc cần làm.");
      setState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Panel sống xuyên suốt (không unmount theo tab như popup cũ) nên phải tự làm
  // mới: confirm/done/dismiss một việc bên web app xong quay lại panel thì danh
  // sách phải khớp, không đợi tới lần mount sau. visibilitychange bắt lúc quay
  // lại panel; poll nhẹ bắt thay đổi xảy ra khi panel vẫn mở cạnh tab web.
  useEffect(() => {
    const REFRESH_INTERVAL_MS = 45_000;
    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") void load(true);
    };
    document.addEventListener("visibilitychange", refreshIfVisible);
    const timer = setInterval(refreshIfVisible, REFRESH_INTERVAL_MS);
    return () => {
      document.removeEventListener("visibilitychange", refreshIfVisible);
      clearInterval(timer);
    };
  }, [load]);

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const visibleTasks = tasks
    .filter((task) => matchesTaskFilter(task, filter))
    .filter((task) => !normalizedQuery || task.title.toLowerCase().includes(normalizedQuery));
  const stats = computeTaskStats(tasks);

  return (
    <>
      <ReminderPanel />

      {state === "loading" && <p className="py-8 text-center text-xs text-muted">Đang tải...</p>}

      {state === "guest" && (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <img src="/mondaiy-mascot.png" width={32} height={32} alt="" className="opacity-80" />
          <p className="text-xs text-secondary">
            Đăng nhập ở mondaiy để nhận thông báo việc cần làm ngay tại đây.
          </p>
          <Button onClick={openWebApp}>Mở mondaiy</Button>
        </div>
      )}

      {state === "error" && (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <p className="text-xs text-danger">{errorMessage}</p>
          <Button variant="secondary" onClick={() => void load()}>
            Thử lại
          </Button>
        </div>
      )}

      {state === "ready" && pendingCount > 0 && (
        <div className="app-panel flex items-center justify-between gap-2 rounded-xl p-3">
          <p className="text-xs font-semibold text-secondary">
            {pendingCount} việc đang chờ bạn duyệt
          </p>
          <Button variant="secondary" onClick={openWebApp}>
            Duyệt ngay
          </Button>
        </div>
      )}

      {state === "ready" && (
        <div className="flex flex-col gap-2.5">
          <TaskStatsBar stats={stats} />
          <TaskSearchBar query={searchQuery} onQueryChange={setSearchQuery} filter={filter} onFilterChange={setFilter} />
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <TaskViewModeToggle mode={viewMode} onChange={setViewMode} />
            </div>
            <Button
              variant="secondary"
              onClick={() => setShowQuickAdd((prev) => !prev)}
              aria-label="Thêm việc thủ công"
              className="gap-1"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
              Thêm việc
            </Button>
          </div>

          {showQuickAdd && (
            <QuickAddTaskForm
              onCreated={() => {
                setShowQuickAdd(false);
                void load();
              }}
              onCancel={() => setShowQuickAdd(false)}
            />
          )}

          {tasks.length === 0 && (
            <p className="py-8 text-center text-xs text-secondary">
              {pendingCount > 0 ? "Chưa có việc nào đã duyệt." : "Không có việc nào. 🎉"}
            </p>
          )}

          {tasks.length > 0 && visibleTasks.length === 0 && (
            <p className="py-8 text-center text-xs text-secondary">Không có việc nào khớp tìm kiếm/bộ lọc.</p>
          )}

          {visibleTasks.length > 0 && viewMode === "list" && (
            <ul className="flex flex-col gap-2.5">
              {visibleTasks.map((task) => (
                <TaskCard key={task.id} task={task} />
              ))}
            </ul>
          )}

          {visibleTasks.length > 0 && viewMode === "byDate" && (
            <div className="flex flex-col gap-3">
              {groupTasksByDate(visibleTasks).map((group) => (
                <div key={group.label} className="flex flex-col gap-2">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-muted">
                    <CalendarDays className="h-3 w-3" aria-hidden />
                    {group.label}
                  </div>
                  <ul className="flex flex-col gap-2.5">
                    {group.tasks.map((task) => (
                      <TaskCard key={task.id} task={task} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}

interface ActiveTabInfo {
  id: number;
  title: string | null;
  url: string | null;
}

/** Đọc tab đang active trong cửa sổ hiện tại — permission "tabs" cho phép đọc
 * title/url ngay, không phụ thuộc thời điểm invoke như "activeTab" trước đây. */
async function readActiveTab(): Promise<ActiveTabInfo | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined) return null;
  return { id: tab.id, title: tab.title || null, url: tab.url || null };
}

export function extractPageContentInPage(): {
  title: string;
  url: string;
  text: string;
  sourceContext: string;
} {
  const MAX_CHARS = 20_000;
  const title = document.title;
  const url = location.href;

  try {
    const body = document.body;
    if (!body) return { title, url, text: "", sourceContext: "" };

    // 1. ƯU TIÊN: Nếu người dùng đang bôi đen một đoạn văn bản (selection), lấy đúng đoạn đó
    const selectedText = window.getSelection()?.toString().trim();
    if (selectedText && selectedText.length >= 5) {
      return {
        title,
        url,
        text: selectedText.slice(0, MAX_CHARS),
        sourceContext: "",
      };
    }

    const NOISE_TAG_PATTERN =
      /^(NAV|ASIDE|HEADER|FOOTER|SCRIPT|STYLE|NOSCRIPT|TEMPLATE|SVG|CANVAS|BUTTON|INPUT|SELECT|TEXTAREA|IFRAME|OBJECT|EMBED|AUDIO|VIDEO)$/i;
    const NOISE_ROLE_PATTERN =
      /^(navigation|complementary|banner|contentinfo|search|menu|menubar|toolbar|tablist)$/i;
    const NOISE_KEYWORD_PATTERN =
      /\b(nav(bar)?|sidebar|side-bar|menu|search|breadcrumb|pagination|toolbar|topbar|footer|header|banner|advert|sponsor(ed)?|promo(tion)?|cookie|consent|newsletter|subscribe|comment(s)?|disqus|related|recommend(ed)?|widget|popup|modal|tooltip|dropdown|social-share|conversation-list|chat-list|thread-list)\b/i;
    const ANCESTOR_WALK_DEPTH = 20;

    const preferredRoot = document.querySelector<HTMLElement>('main, [role="main"], article, [role="article"]');
    const trustPreferredRoot = (preferredRoot?.textContent?.trim().length ?? 0) > 40;
    const scanRoot: Element = trustPreferredRoot && preferredRoot ? preferredRoot : body;

    const noiseCache = new WeakMap<Element, boolean>();
    const renderedCache = new WeakMap<Element, boolean>();

    function isNodeNoisy(node: Element): boolean {
      const cached = noiseCache.get(node);
      if (cached !== undefined) return cached;
      const isNoise =
        NOISE_TAG_PATTERN.test(node.tagName) ||
        (() => {
          const role = node.getAttribute("role");
          return role !== null && NOISE_ROLE_PATTERN.test(role);
        })() ||
        node.getAttribute("aria-hidden") === "true" ||
        (typeof node.className === "string" &&
          NOISE_KEYWORD_PATTERN.test(`${node.className} ${node.id}`.replace(/_/g, "-")));
      noiseCache.set(node, isNoise);
      return isNoise;
    }

    function hasNoiseAncestor(start: Element): boolean {
      let node: Element | null = start;
      let depth = 0;
      while (node && depth < ANCESTOR_WALK_DEPTH) {
        if (isNodeNoisy(node)) return true;
        if (node === scanRoot) break;
        node = node.parentElement;
        depth += 1;
      }
      return false;
    }

    function isRendered(el: Element): boolean {
      const cached = renderedCache.get(el);
      if (cached !== undefined) return cached;
      const style = window.getComputedStyle(el);
      const value =
        !(el as HTMLElement).hidden &&
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        style.opacity !== "0";
      renderedCache.set(el, value);
      return value;
    }

    function guessSourceContext(): string {
      const MAX_LEN = 150;
      const normalizedTitle = title.trim();
      const candidates = document.querySelectorAll<HTMLElement>('[role="heading"], h1, h2');
      for (const el of Array.from(candidates)) {
        if (!isRendered(el)) continue;
        const text = el.textContent?.trim();
        if (!text || text.length === 0 || text.length > MAX_LEN) continue;
        if (text === normalizedTitle) continue;
        return text;
      }
      return "";
    }

    function getCleanFallbackText(el: Element): string {
      const clone = el.cloneNode(true) as Element;
      const technicalTags = clone.querySelectorAll(
        "script, style, noscript, template, svg, iframe, canvas, link, meta, nav, header, footer, aside"
      );
      technicalTags.forEach((tag) => tag.remove());
      const rawText = clone.textContent || "";
      const cleanLines = rawText
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => {
          if (!line || line.length < 2) return false;
          if (
            /^(!function|\(function|function\s*\(|window\.|var\s+|const\s+|let\s+|document\.|try\s*\{|\{"authStatus"|\{"props"|\{"pageProps"|eyJ[a-zA-Z0-9_-]{15,})/i.test(
              line
            )
          ) {
            return false;
          }
          let count = 0;
          for (const ch of line) {
            if (/\p{L}/u.test(ch)) {
              count += 1;
              if (count >= 2) break;
            }
          }
          return count >= 2;
        });
      return cleanLines.join("\n").trim();
    }

    const walker = document.createTreeWalker(scanRoot, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || !node.textContent?.trim()) return NodeFilter.FILTER_REJECT;
        if (!isRendered(parent)) return NodeFilter.FILTER_REJECT;
        if (hasNoiseAncestor(parent)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const lines: string[] = [];
    let collected = 0;
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const value = node.textContent?.trim();
      if (!value) continue;
      // Bỏ qua nếu dòng là mã code JS / JSON SSR payload / JWT Token
      if (
        /^(!function|\(function|function\s*\(|window\.|var\s+|const\s+|let\s+|document\.|try\s*\{|\{"authStatus"|\{"props"|\{"pageProps")/i.test(
          value
        ) ||
        /^(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})/i.test(value)
      ) {
        continue;
      }
      let letterCount = 0;
      for (const ch of value) {
        if (/\p{L}/u.test(ch)) {
          letterCount += 1;
          if (letterCount >= 2) break;
        }
      }
      if (letterCount < 2) continue;
      lines.push(value);
      collected += value.length + 1;
      if (collected >= MAX_CHARS) break;
    }

    const filtered = lines.join("\n").trim();
    const text = (filtered.length >= 20 ? filtered : getCleanFallbackText(scanRoot)) || filtered;

    return { title, url, text: text.slice(0, MAX_CHARS), sourceContext: guessSourceContext() };
  } catch (error) {
    const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
    return { title, url, text: `[Lỗi trích xuất nội dung trang: ${message}]`, sourceContext: "" };
  }
}

type ExtractStatus = "idle" | "extracting" | "extracted" | "classifying" | "suggestions" | "error";
type SuggestionSaveState = "idle" | "saving" | "saved" | "error";

interface SuggestionState {
  id: string;
  title: string;
  detail: string;
  // ISO 8601, chỉ có giá trị khi backend parse chắc chắn được thời hạn từ
  // text gốc (BR-05 — không đoán khi mơ hồ, xem resolve_due_at() phía server).
  dueAt: string | null;
  // Nguồn — tách riêng khỏi detail (trước đây bị nhét cứng vào cuối detail,
  // chật/khó đọc trên panel hẹp, phản hồi người dùng 2026-08-26). sourceUrl
  // luôn có giá trị; sourceLabel chỉ có khi backend đoán được nhãn cụ thể
  // hơn url (vd tên nhóm chat — cần cho SPA route tĩnh như Zalo web).
  sourceUrl: string;
  sourceLabel: string;
  // Field mở rộng — thường rỗng (nguồn không nêu), chỉ hiện ô sửa ở
  // SuggestionCard khi có nội dung. executionSteps giữ dạng text nhiều dòng
  // (một bước một dòng) ở tầng UI, chỉ tách mảng lúc gửi API — cùng cách
  // rawExtracted.text tách dòng để hiển thị ở nơi khác trong file này.
  expectedOutput: string;
  constraint: string;
  executionSteps: string;
  executionTool: string;
  executionMethod: string;
  priority: string;
  assignee: string;
  stakeholders: string;
  deliverTo: string;
  // Đóng băng lúc tạo suggestion (từ kết quả extraction gốc) — KHÔNG suy lại
  // từ giá trị đang sửa, để nhóm "Chi tiết thêm" không biến mất giữa chừng
  // nếu người dùng xoá trống một field đang sửa (updateSuggestion() không
  // được phép patch field này — xem handleClassify).
  hasExtras: boolean;
  // Chế độ chọn nhiều (thanh hành động nổi ở đáy) — mặc định chưa chọn.
  selected: boolean;
  saveState: SuggestionSaveState;
  errorMessage: string;
}

/** Gộp field mở rộng (đã sửa nếu có) vào MỘT detail cuối cùng lúc lưu thật —
 * Task DB dùng chung nhiều pipeline khác (Discord/Gmail/Slack/Jira/meeting-
 * notes) không có cột riêng cho các field này, nên chỉ tồn tại ở suggestion
 * (transient, chưa lưu) chứ không phải Task đã lưu. Field rỗng thì bỏ qua
 * hẳn dòng đó, không hiện nhãn suông. */
export function composeFinalDetail(item: {
  detail: string;
  sourceUrl: string;
  sourceLabel: string;
  expectedOutput: string;
  constraint: string;
  executionSteps: string;
  executionTool: string;
  executionMethod: string;
  priority: string;
  assignee: string;
  stakeholders: string;
  deliverTo: string;
}): string {
  const sections = [item.detail.trim()];
  if (item.expectedOutput.trim()) sections.push(`Kết quả mong đợi: ${item.expectedOutput.trim()}`);
  if (item.constraint.trim()) sections.push(`Ràng buộc: ${item.constraint.trim()}`);
  if (item.executionSteps.trim()) sections.push(`Các bước thực hiện:\n${item.executionSteps.trim()}`);
  if (item.executionTool.trim()) sections.push(`Công cụ: ${item.executionTool.trim()}`);
  if (item.executionMethod.trim()) sections.push(`Cách làm đề xuất: ${item.executionMethod.trim()}`);
  if (item.priority.trim()) sections.push(`Độ ưu tiên: ${item.priority.trim()}`);
  if (item.assignee.trim()) sections.push(`Người phụ trách: ${item.assignee.trim()}`);
  if (item.stakeholders.trim()) sections.push(`Người liên quan: ${item.stakeholders.trim()}`);
  if (item.deliverTo.trim()) sections.push(`Hoàn thành gửi cho: ${item.deliverTo.trim()}`);
  // Nguồn luôn ở CUỐI cùng — sourceUrl luôn có giá trị (backend bắt buộc).
  if (item.sourceUrl.trim()) {
    sections.push(
      item.sourceLabel.trim()
        ? `Nguồn: ${item.sourceLabel.trim()} (${item.sourceUrl.trim()})`
        : `Nguồn: ${item.sourceUrl.trim()}`
    );
  }
  return sections.filter((section) => section.length > 0).join("\n\n");
}

/** input[type=datetime-local] cần "YYYY-MM-DDTHH:mm" giờ local, không có
 * timezone — chuyển qua lại với ISO 8601 backend trả về. */
function isoToLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function localInputValueToIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** Đăng nhập mượn từ tab web app trước khi gọi API cần token — dùng lại ở cả
 * bước phân loại lẫn bước lưu, vì cả hai đều cần Authorization Bearer.
 *
 * Cố ý dùng `getValidAccessToken()` chứ không phải `getSession()`: session
 * mới đồng bộ lần đầu luôn có `expiresAt: 0` (lib/auth.ts applyWebSession) nên
 * LUÔN bị coi là hết hạn, buộc `getValidAccessToken()` refresh ngay. `getSession()`
 * chỉ kiểm tra "có object session hay không" — session tồn tại nhưng refresh
 * thất bại (refresh token đã revoke, backend lỗi tạm...) vẫn lọt qua, request
 * thật sự đi ra ngoài không kèm token, và lỗi 401 thô từ backend
 * ("Thiếu Authorization Bearer token.") sẽ lộ thẳng ra UI thay vì thông báo
 * "chưa đăng nhập" dễ hiểu. */
async function ensureLoggedIn(): Promise<boolean> {
  await reconcileWebSession();
  return (await getValidAccessToken()) !== null;
}

/** Một dòng khớp việc-cần-làm, hiện dạng thẻ riêng để confirm/bỏ từng cái —
 * khác form gộp 1 khối text lớn trước đây. */
/** Ô sửa một dòng cho field mở rộng (công cụ/ưu tiên/người phụ trách...) —
 * dùng chung style với Hạn chót để nhất quán, không tạo style riêng. */
/** Icon trước nhãn — cùng ngôn ngữ hình ảnh với hàng "Hạn chót" (icon + nhãn
 * inline) thay vì chỉ chữ suông, giúp quét mắt nhanh biết đây là trường gì
 * khi "Chi tiết thêm" có nhiều hàng liền nhau (phản hồi người dùng
 * 2026-08-27: "cần hiện rõ, cần design thêm"). */
function ExtraFieldLabel({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
      {label}
    </span>
  );
}

function ExtraFieldRow({
  icon,
  label,
  value,
  onChange,
  disabled,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 text-[11px] font-semibold text-secondary">
      <ExtraFieldLabel icon={icon} label={label} />
      <input
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="rounded-lg border border-border bg-surface px-2 py-1 text-xs text-secondary shadow-inner transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
      />
    </label>
  );
}

/** Ô sửa nhiều dòng cho field mở rộng dài hơn (kết quả mong đợi/ràng buộc/
 * các bước/cách làm) — cùng style textarea "Nội dung công việc" bên dưới. */
function ExtraFieldArea({
  icon,
  label,
  value,
  onChange,
  disabled,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 text-[11px] font-semibold text-secondary">
      <ExtraFieldLabel icon={icon} label={label} />
      <textarea
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={2}
        spellCheck={false}
        className="w-full resize-y rounded-lg border border-border bg-surface px-2 py-1 text-xs leading-relaxed text-secondary shadow-inner transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
      />
    </label>
  );
}

/** Chữ hiện cho link nguồn — ưu tiên sourceLabel (vd tên nhóm chat, cụ thể
 * hơn url với SPA route tĩnh như Zalo web). Không có label thì rút gọn về
 * hostname thay vì url đầy đủ, đỡ chiếm chỗ trên panel hẹp. */
function formatSourceLabel(sourceUrl: string, sourceLabel: string): string {
  if (sourceLabel) return sourceLabel;
  try {
    return new URL(sourceUrl).hostname;
  } catch {
    return sourceUrl;
  }
}

function SuggestionCard({
  suggestion,
  onChange,
  onSave,
  onDismiss,
}: {
  suggestion: SuggestionState;
  onChange: (
    patch: Partial<
      Pick<
        SuggestionState,
        | "title"
        | "detail"
        | "dueAt"
        | "expectedOutput"
        | "constraint"
        | "executionSteps"
        | "executionTool"
        | "executionMethod"
        | "priority"
        | "assignee"
        | "stakeholders"
        | "deliverTo"
        | "selected"
      >
    >
  ) => void;
  onSave: () => void;
  onDismiss: () => void;
}) {
  const {
    title,
    detail,
    dueAt,
    sourceUrl,
    sourceLabel,
    hasExtras,
    expectedOutput,
    constraint,
    executionSteps,
    executionTool,
    executionMethod,
    priority,
    assignee,
    stakeholders,
    deliverTo,
    selected,
    saveState,
    errorMessage,
  } = suggestion;
  const locked = saveState === "saving" || saveState === "saved";
  const urgency = suggestionUrgency({ dueAt });

  return (
    <section className="app-panel flex flex-col gap-2 rounded-xl p-3">
      <div className="flex items-start justify-between gap-2">
        {urgency ? (
          <span className={`self-start rounded-full px-2 py-0.5 text-[10px] font-bold ${urgency.tone}`}>
            {urgency.label}
          </span>
        ) : (
          <span />
        )}
        <input
          type="checkbox"
          aria-label="Chọn gợi ý này"
          checked={selected}
          disabled={locked}
          onChange={(e) => onChange({ selected: e.target.checked })}
          className="h-4 w-4 shrink-0 accent-primary"
        />
      </div>
      <Input
        aria-label="Tiêu đề công việc"
        value={title}
        onChange={(e) => onChange({ title: e.target.value })}
        disabled={locked}
      />
      <textarea
        aria-label="Nội dung công việc"
        value={detail}
        onChange={(e) => onChange({ detail: e.target.value })}
        disabled={locked}
        rows={4}
        spellCheck={false}
        className="w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 text-xs leading-relaxed text-secondary shadow-inner transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
      />
      {sourceUrl && (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          title={sourceUrl}
          className="inline-flex max-w-full items-center gap-1 self-start truncate text-[10px] font-medium text-muted hover:text-secondary hover:underline"
        >
          <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
          <span className="truncate">Nguồn: {formatSourceLabel(sourceUrl, sourceLabel)}</span>
        </a>
      )}
      <label className="flex items-center gap-1.5 text-[11px] font-semibold text-secondary">
        <Clock className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
        Hạn chót
        <input
          aria-label="Hạn chót"
          type="datetime-local"
          value={isoToLocalInputValue(dueAt)}
          onChange={(e) => onChange({ dueAt: localInputValueToIso(e.target.value) })}
          disabled={locked}
          className="flex-1 rounded-lg border border-border bg-surface px-2 py-1 text-xs text-secondary shadow-inner transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
        />
      </label>
      {hasExtras && (
        <div className="flex flex-col gap-2.5 rounded-lg border border-border/60 bg-surface/40 p-2.5">
          <span className="flex items-center gap-1.5 font-heading text-sm font-semibold text-primary">
            <ClipboardList className="h-4 w-4 shrink-0" aria-hidden />
            Chi tiết thêm
          </span>
          <ExtraFieldArea
            icon={Target}
            label="Kết quả mong đợi"
            value={expectedOutput}
            onChange={(value) => onChange({ expectedOutput: value })}
            disabled={locked}
          />
          <ExtraFieldArea
            icon={Ban}
            label="Ràng buộc"
            value={constraint}
            onChange={(value) => onChange({ constraint: value })}
            disabled={locked}
          />
          <ExtraFieldArea
            icon={ListOrdered}
            label="Các bước thực hiện"
            value={executionSteps}
            onChange={(value) => onChange({ executionSteps: value })}
            disabled={locked}
          />
          <ExtraFieldRow
            icon={Wrench}
            label="Công cụ"
            value={executionTool}
            onChange={(value) => onChange({ executionTool: value })}
            disabled={locked}
          />
          <ExtraFieldArea
            icon={Lightbulb}
            label="Cách làm đề xuất"
            value={executionMethod}
            onChange={(value) => onChange({ executionMethod: value })}
            disabled={locked}
          />
          <ExtraFieldRow
            icon={Flag}
            label="Độ ưu tiên"
            value={priority}
            onChange={(value) => onChange({ priority: value })}
            disabled={locked}
          />
          <ExtraFieldRow
            icon={User}
            label="Người phụ trách"
            value={assignee}
            onChange={(value) => onChange({ assignee: value })}
            disabled={locked}
          />
          <ExtraFieldRow
            icon={Users}
            label="Người liên quan"
            value={stakeholders}
            onChange={(value) => onChange({ stakeholders: value })}
            disabled={locked}
          />
          <ExtraFieldRow
            icon={Send}
            label="Hoàn thành gửi cho"
            value={deliverTo}
            onChange={(value) => onChange({ deliverTo: value })}
            disabled={locked}
          />
        </div>
      )}
      {saveState === "error" && <p className="text-[11px] text-danger">{errorMessage}</p>}
      {saveState === "saved" ? (
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          Đã lưu vào công việc
        </span>
      ) : (
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onDismiss} disabled={saveState === "saving"}>
            <XCircle className="h-3.5 w-3.5" />
            Bỏ qua
          </Button>
          <Button onClick={onSave} disabled={saveState === "saving"}>
            {saveState === "saving" ? "Đang lưu..." : "Lưu"}
          </Button>
        </div>
      )}
    </section>
  );
}

/**
 * Tab "Lấy dữ liệu": chỉ thao tác với tab đang active tại thời điểm bấm nút —
 * luôn truy vấn lại `chrome.tabs.query({active:true,currentWindow:true})` ngay
 * trước khi inject, không cache tabId cũ, để user chuyển A→B→C thì luôn đọc
 * đúng tab đang xem lúc bấm (yêu cầu #4 trong TASKS.md).
 *
 * Flow 2 bước tách biệt: (1) "Lấy dữ liệu từ tab này" chỉ đọc text thô từ
 * trang (client) + redact số nhạy cảm, hiện list dòng thô để xem trước —
 * CHƯA gọi LLM. (2) "Extract công việc" mới gọi backend (rule engine +
 * LLM cho phần mơ hồ, POST /tasks/summarize-page-extraction — xem
 * src/services/page_extraction.py), trả về MỘT suggestion cho MỖI dòng khớp
 * việc-cần-làm — người dùng confirm/bỏ TỪNG CÁI riêng (SuggestionCard) thay
 * vì sửa một khối text gộp. Lưu thật qua POST /tasks/from-suggestion (đã có
 * sẵn), gọi riêng cho từng suggestion khi bấm "Lưu".
 */
export function ExtractDataView() {
  const [activeTab, setActiveTab] = useState<ActiveTabInfo | null>(null);
  const [status, setStatus] = useState<ExtractStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [rawExtracted, setRawExtracted] = useState<ExtractedPageData | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionState[]>([]);

  useEffect(() => {
    void readActiveTab().then(setActiveTab);

    // Panel tồn tại xuyên suốt lúc đổi tab (không unmount như popup cũ) nên
    // phải tự nghe sự kiện đổi tab để cập nhật, không chỉ đọc một lần lúc mount.
    const onActivated = () => void readActiveTab().then(setActiveTab);
    const onUpdated = (_tabId: number, changeInfo: chrome.tabs.OnUpdatedInfo) => {
      if (changeInfo.status === "complete") void readActiveTab().then(setActiveTab);
    };
    chrome.tabs.onActivated.addListener(onActivated);
    chrome.tabs.onUpdated.addListener(onUpdated);
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated);
      chrome.tabs.onUpdated.removeListener(onUpdated);
    };
  }, []);

  async function handleExtract() {
    setStatus("extracting");
    setErrorMessage("");
    try {
      const tab = await readActiveTab();
      if (!tab) throw new Error("Không xác định được tab đang active.");
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractPageContentInPage,
      });
      const data = results[0]?.result;
      if (!data) throw new Error("Không đọc được nội dung trang này.");
      const redacted: ExtractedPageData = { ...data, text: redactSensitive(data.text) };
      setRawExtracted(redacted);
      setStatus("extracted");
    } catch (err) {
      // host_permissions <all_urls> phủ mọi trang http/https, nên lỗi còn lại
      // ở đây gần như luôn là trang Chrome tự khoá hẳn extension (chrome://,
      // Chrome Web Store, PDF viewer nội bộ...) — không có cách nào xin thêm
      // quyền cho những trang này, chỉ có thể báo và để người dùng đổi tab khác.
      const message = err instanceof Error ? err.message : "Không lấy được dữ liệu từ tab này.";
      const isRestrictedPage = /cannot access|no tab with id/i.test(message);
      setErrorMessage(
        isRestrictedPage
          ? "Chrome không cho phép đọc nội dung trang này (trang hệ thống/nội bộ) — hãy thử ở tab khác."
          : message
      );
      setStatus("error");
    }
  }

  /** Gọi backend phân loại — tách riêng khỏi handleExtract để "Thử lại" không
   * phải chạy lại executeScript (tab có thể đã chuyển hướng/đóng từ lúc lấy
   * dữ liệu), và để người dùng xem trước list thô trước khi tốn lời gọi LLM. */
  async function handleClassify() {
    if (!rawExtracted) return;
    setStatus("classifying");
    setErrorMessage("");
    if (!(await ensureLoggedIn())) {
      setErrorMessage("Chưa đăng nhập mondaiy — mở mondaiy để đăng nhập rồi quay lại.");
      setStatus("error");
      return;
    }
    try {
      const results = await summarizePageExtraction(
        rawExtracted.url,
        rawExtracted.title,
        rawExtracted.text,
        rawExtracted.sourceContext
      );
      setSuggestions(
        results.map((r) => ({
          id: crypto.randomUUID(),
          title: r.title,
          detail: r.detail,
          dueAt: r.dueAt,
          sourceUrl: r.sourceUrl,
          sourceLabel: r.sourceLabel,
          expectedOutput: r.expectedOutput,
          constraint: r.constraint,
          executionSteps: r.executionSteps.join("\n"),
          executionTool: r.executionTool,
          executionMethod: r.executionMethod,
          priority: r.priority,
          assignee: r.assignee,
          stakeholders: r.stakeholders,
          deliverTo: r.deliverTo,
          hasExtras: Boolean(
            r.expectedOutput ||
              r.constraint ||
              r.executionSteps.length > 0 ||
              r.executionTool ||
              r.executionMethod ||
              r.priority ||
              r.assignee ||
              r.stakeholders ||
              r.deliverTo
          ),
          selected: false,
          saveState: "idle",
          errorMessage: "",
        }))
      );
      setStatus("suggestions");
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Không tóm tắt được nội dung trang.");
      setStatus("error");
    }
  }

  function updateSuggestion(id: string, patch: Partial<SuggestionState>) {
    setSuggestions((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function handleDismissSuggestion(id: string) {
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
  }

  async function handleSaveSuggestion(id: string) {
    const item = suggestions.find((s) => s.id === id);
    if (!item) return;
    updateSuggestion(id, { saveState: "saving", errorMessage: "" });
    if (!(await ensureLoggedIn())) {
      updateSuggestion(id, {
        saveState: "error",
        errorMessage: "Chưa đăng nhập mondaiy — mở mondaiy để đăng nhập rồi quay lại lưu.",
      });
      return;
    }
    try {
      const created = await createTaskFromSuggestion(
        item.title.trim() || "Việc từ trang đã lấy dữ liệu",
        item.detail.trim(),
        item.dueAt,
        {
          expectedOutput: item.expectedOutput.trim() || undefined,
          constraints: item.constraint.trim() || undefined,
          executionTool: item.executionTool.trim() || undefined,
          executionMethod: item.executionMethod.trim() || undefined,
          statedPriority: item.priority.trim() || undefined,
          assignee: item.assignee.trim() || undefined,
          stakeholders: item.stakeholders.trim() ? [item.stakeholders.trim()] : undefined,
          deliverTo: item.deliverTo.trim() || undefined,
          source: item.sourceLabel || item.sourceUrl || "suggestion",
        }
      );
      if (created?.id) {
        try {
          await confirmTask(created.id);
        } catch {
          // Bỏ qua lỗi confirm ngầm nếu backend đã lưu task
        }
      }
      updateSuggestion(id, { saveState: "saved" });
    } catch (err) {
      updateSuggestion(id, {
        saveState: "error",
        errorMessage: err instanceof ApiError ? err.message : "Không lưu được vào công việc.",
      });
    }
  }

  function handleReset() {
    setRawExtracted(null);
    setSuggestions([]);
    setStatus("idle");
    setErrorMessage("");
  }

  const selectedIds = suggestions.filter((s) => s.selected).map((s) => s.id);

  /** Lưu/bỏ tất cả mục đang chọn cùng lúc — tái dùng nguyên logic từng-cái
   * (handleSaveSuggestion/handleDismissSuggestion) qua Promise.all thay vì
   * viết lại, để cùng một chỗ xử lý lỗi/trạng thái cho cả hai đường lưu. */
  async function handleBulkSave() {
    await Promise.all(selectedIds.map((id) => handleSaveSuggestion(id)));
  }

  function handleBulkDismiss() {
    setSuggestions((prev) => prev.filter((s) => !s.selected));
  }

  const rawLines = rawExtracted?.text.split("\n").filter((line) => line.trim() !== "") ?? [];
  const showRawPreview = rawExtracted !== null && status !== "suggestions";

  return (
    <div className="flex flex-col gap-3">
      <section className="app-panel rounded-xl p-3">
        <p className="text-[11px] font-semibold text-primary">Tab đang active</p>
        <p className="mt-1 truncate text-xs text-secondary" title={activeTab?.url ?? undefined}>
          {activeTab?.title || activeTab?.url || (activeTab ? `Tab #${activeTab.id}` : "Đang xác định...")}
        </p>
      </section>

      {!rawExtracted && (
        <Button onClick={() => void handleExtract()} disabled={!activeTab || status === "extracting"} className="gap-1.5">
          <Download className="h-3.5 w-3.5" />
          {status === "extracting" ? "Đang lấy dữ liệu..." : "Lấy dữ liệu từ tab này"}
        </Button>
      )}

      {!rawExtracted && status === "error" && <p className="text-[11px] text-danger">{errorMessage}</p>}

      {showRawPreview && (
        <section className="app-panel flex flex-col gap-2 rounded-xl p-3">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-primary">Nội dung thô đã lấy</p>
            <span className="text-[10px] text-muted">{rawLines.length} dòng</span>
          </div>
          <ul className="max-h-56 list-none space-y-1 overflow-y-auto rounded-lg border border-border bg-surface p-2 text-xs leading-relaxed text-secondary shadow-inner">
            {rawLines.length === 0 ? (
              <li className="text-muted">Không đọc được dòng nội dung nào.</li>
            ) : (
              rawLines.map((line, i) => (
                <li key={i} className="border-b border-border/60 pb-1 last:border-none">
                  {line}
                </li>
              ))
            )}
          </ul>

          {status === "error" && <p className="text-[11px] text-danger">{errorMessage}</p>}

          <div className="flex justify-end gap-2 border-t border-border pt-2">
            <Button variant="secondary" onClick={handleReset} disabled={status === "classifying"}>
              Huỷ
            </Button>
            <Button onClick={() => void handleClassify()} disabled={status === "classifying"}>
              {status === "classifying" ? "Đang phân loại..." : status === "error" ? "Thử lại" : "Extract công việc"}
            </Button>
          </div>
        </section>
      )}

      {status === "suggestions" && (
        <>
          <div className="flex items-center justify-between px-1">
            <p className="font-heading text-base font-semibold text-primary">
              {suggestions.length > 0 ? `${suggestions.length} việc được nhận diện` : "Không còn gợi ý nào"}
            </p>
            <button
              type="button"
              onClick={handleReset}
              className="text-xs font-semibold text-primary hover:underline"
            >
              Lấy tiếp
            </button>
          </div>
          {suggestions.map((s) => (
            <SuggestionCard
              key={s.id}
              suggestion={s}
              onChange={(patch) => updateSuggestion(s.id, patch)}
              onSave={() => void handleSaveSuggestion(s.id)}
              onDismiss={() => handleDismissSuggestion(s.id)}
            />
          ))}

          {/* Chừa chỗ cho thanh nổi bên dưới không đè lên card cuối cùng. */}
          {selectedIds.length > 0 && <div className="h-14" aria-hidden />}
        </>
      )}

      {selectedIds.length > 0 && (
        <div className="app-panel sticky bottom-0 flex items-center justify-between gap-2 rounded-xl p-3 shadow-lg">
          <p className="text-xs font-semibold text-secondary">Đã chọn {selectedIds.length} mục</p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleBulkDismiss}>
              Bỏ qua tất cả
            </Button>
            <Button onClick={() => void handleBulkSave()}>Lưu tất cả</Button>
          </div>
        </div>
      )}
    </div>
  );
}

type PanelTab = "tasks" | "extract";

const TAB_ITEMS: { id: PanelTab; label: string }[] = [
  { id: "tasks", label: "Công việc" },
  // "Lấy dữ liệu" nghe như đang thu thập/khai thác dữ liệu người khác — đổi
  // tên hiển thị cho bớt cảm giác đáng ngại (phản hồi người dùng 2026-08-26),
  // id/route giữ nguyên "extract" để không đụng logic/test khác.
  { id: "extract", label: "Quét việc" },
];

type AuthGateState = "checking" | "guest" | "authed";

/**
 * Chốt việc "chưa đăng nhập web thì extension không hoạt động" ở một chỗ
 * DUY NHẤT — App() không mount TasksView/RecordingPanel/ExtractDataView khi
 * chưa có session, thay vì mỗi view tự kiểm tra rời rạc (TasksView trước đây
 * tự chặn tab "Công việc" nhưng RecordingPanel/ExtractDataView vẫn hoạt động
 * một phần khi chưa đăng nhập — vá ở gốc thay vì vá từng nơi).
 *
 * `authSessionItem.watch()` bắt cả trường hợp đăng nhập/đăng xuất diễn ra
 * ngay khi panel đang mở (web-session.content.ts báo qua background ->
 * applyWebSession() ghi storage), không cần đóng mở lại panel.
 */
function useAuthGate(): { status: AuthGateState; session: AuthSession | null } {
  const [status, setStatus] = useState<AuthGateState>("checking");
  const [session, setSession] = useState<AuthSession | null>(null);

  useEffect(() => {
    let cancelled = false;
    void reconcileWebSession()
      .then(() => getSession())
      .then((s) => {
        if (!cancelled) {
          setStatus(s ? "authed" : "guest");
          setSession(s);
        }
      });
    return authSessionItem.watch((s) => {
      setStatus(s ? "authed" : "guest");
      setSession(s);
    });
  }, []);

  return { status, session };
}

function LoginView() {
  const [loginMode, setLoginMode] = useState<"direct" | "web">("direct");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  async function handleDirectLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Vui lòng nhập đầy đủ email và mật khẩu.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await loginWithCredentials(email, password);
      if (res && !res.success) {
        setError(res.error || "Đăng nhập thất bại.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSyncWebSession() {
    setSyncing(true);
    setSyncMessage(null);
    setError(null);
    try {
      await reconcileWebSession();
      const s = await getSession();
      if (!s) {
        setSyncMessage("Chưa tìm thấy phiên đăng nhập trên tab web app. Vui lòng mở tab web và đăng nhập trước.");
      }
    } catch {
      setSyncMessage("Không thể đồng bộ. Vui lòng mở tab mondaiy trên trình duyệt.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col justify-center px-4 py-6 overflow-y-auto">
      <div className="flex flex-col items-center text-center mb-4">
        <img src="/mondaiy-mascot.png" width={42} height={42} alt="mondaiy" className="mb-2 opacity-90 drop-shadow-xs" />
        <h1 className="font-heading text-base font-semibold text-primary">
          Đăng nhập mond<span className="text-focus">ai</span>y
        </h1>
        <p className="text-xs text-secondary mt-1 max-w-[260px]">
          Quản lý công việc và bóc tách phiếu giao việc thông minh ngay trên trình duyệt.
        </p>
      </div>

      <div className="flex rounded-lg border border-border bg-app-bg p-1 mb-4" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={loginMode === "direct"}
          onClick={() => {
            setLoginMode("direct");
            setError(null);
            setSyncMessage(null);
          }}
          className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition-all ${
            loginMode === "direct"
              ? "bg-paper text-primary shadow-xs"
              : "text-muted hover:text-secondary"
          }`}
        >
          Trực tiếp
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={loginMode === "web"}
          onClick={() => {
            setLoginMode("web");
            setError(null);
            setSyncMessage(null);
          }}
          className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition-all ${
            loginMode === "web"
              ? "bg-paper text-primary shadow-xs"
              : "text-muted hover:text-secondary"
          }`}
        >
          Web / Google
        </button>
      </div>

      {loginMode === "direct" ? (
        <form onSubmit={handleDirectLogin} className="flex flex-col gap-3">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-2.5 text-xs text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-secondary">Email</label>
            <div className="relative">
              <Input
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                required
                className="pl-8 text-xs"
              />
              <Mail className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted" aria-hidden />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-secondary">Mật khẩu</label>
            <div className="relative">
              <Input
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
                className="pl-8 pr-8 text-xs"
              />
              <Lock className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted" aria-hidden />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2.5 top-2.5 text-muted hover:text-secondary"
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              >
                {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <Button type="submit" disabled={loading} className="mt-1 w-full justify-center">
            {loading ? "Đang đăng nhập..." : "Đăng nhập ngay"}
          </Button>

          <div className="mt-1 text-center">
            <button
              type="button"
              onClick={openWebApp}
              className="text-[11px] text-muted hover:text-focus transition-colors underline"
            >
              Chưa có tài khoản? Đăng ký trên web
            </button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-3 text-center">
          <div className="rounded-xl border border-border bg-paper p-3 text-xs text-secondary text-left space-y-1.5">
            <p className="font-semibold text-primary">Đăng nhập qua trình duyệt:</p>
            <p className="text-[11px] leading-relaxed">
              1. Bấm nút mở web app bên dưới để đăng nhập bằng <strong>Google</strong> hoặc tài khoản của bạn.
            </p>
            <p className="text-[11px] leading-relaxed">
              2. Sau khi đăng nhập ở web, Extension sẽ tự động nhận diện hoặc bạn bấm <strong>Đồng bộ ngay</strong>.
            </p>
          </div>

          {syncMessage && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300 text-left">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{syncMessage}</span>
            </div>
          )}

          <Button onClick={openWebApp} className="w-full justify-center gap-1.5">
            Mở mondaiy để đăng nhập
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>

          <Button
            variant="secondary"
            onClick={() => void handleSyncWebSession()}
            disabled={syncing}
            className="w-full justify-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Đang kiểm tra..." : "Đã đăng nhập ở web? Đồng bộ ngay"}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Áp theme/tông màu/cỡ chữ/tương phản cao lên <html> của CHÍNH sidepanel lúc
 * mount, và nghe tiếp thay đổi trong lúc panel đang mở. Mỗi trang extension
 * (sidepanel/options) có <html> RIÊNG — đổi ở options KHÔNG tự lan sang
 * sidepanel đang mở cùng lúc, phải tự đọc storage + watch() ở từng nơi. Thiếu
 * bước này là lý do sidepanel vẫn giữ Paper sáng dù đã đổi tông/tối ở options
 * (phản hồi người dùng 2026-08-26). */
function usePreferenceSync(): void {
  useEffect(() => {
    void initTheme();
    void initPalette();
    void initTextSize();
    void initHighContrast();
    const unwatchTheme = themeItem.watch((mode) => applyTheme(mode));
    const unwatchPalette = paletteItem.watch((name) => applyPalette(name));
    const unwatchTextSize = textSizeItem.watch((size) => applyTextSize(size));
    const unwatchHighContrast = highContrastItem.watch((enabled) => applyHighContrast(enabled));
    return () => {
      unwatchTheme();
      unwatchPalette();
      unwatchTextSize();
      unwatchHighContrast();
    };
  }, []);
}

export function App() {
  const [tab, setTab] = useState<PanelTab>("tasks");
  const [showSettings, setShowSettings] = useState(false);
  const { status: authState, session } = useAuthGate();
  usePreferenceSync();

  // Cài đặt thay THẲNG nội dung panel (có nút quay lại riêng ở SettingsView)
  // thay vì mở options.html ở tab trình duyệt thật — phản hồi người dùng
  // 2026-08-27. Trả sớm ở đây vì SettingsView tự lo header/back, không dùng
  // chung header/tab-bar/footer bên dưới.
  if (showSettings) {
    return (
      <div className="app-shell flex h-screen w-full flex-col">
        <SettingsView onBack={() => setShowSettings(false)} />
      </div>
    );
  }

  return (
    <div className="app-shell flex h-screen w-full flex-col">
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <img src="/mondaiy-mascot.png" width={22} height={22} alt="mondaiy" />
          <span className="font-heading text-sm font-semibold text-primary">
            mond<span className="text-focus">ai</span>y
          </span>
        </div>
        <div className="flex items-center gap-2">
          {authState === "authed" && <HeaderAvatar avatarUrl={session?.avatarUrl} />}
          <button
            type="button"
            onClick={() => setShowSettings(true)}
            aria-label="Cài đặt / đăng nhập"
            title="Cài đặt / đăng nhập"
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-focus/10 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </header>

      {authState === "checking" && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-xs text-muted">Đang kiểm tra đăng nhập...</p>
        </div>
      )}

      {authState === "guest" && <LoginView />}

      {authState === "authed" && (
        <>
          <nav className="flex border-b border-border px-2" role="tablist" aria-label="Chức năng mondaiy">
            {TAB_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                onClick={() => setTab(item.id)}
                className={`flex-1 border-b-2 px-2 py-2 text-xs font-semibold transition-colors ${
                  tab === item.id
                    ? "border-primary text-primary"
                    : "border-transparent text-muted hover:text-secondary"
                }`}
              >
                {item.id === "tasks" ? (
                  <span className="inline-flex items-center justify-center gap-1.5">
                    <ListChecks className="h-3.5 w-3.5" aria-hidden />
                    {item.label}
                  </span>
                ) : (
                  <span className="inline-flex items-center justify-center gap-1.5">
                    <Download className="h-3.5 w-3.5" aria-hidden />
                    {item.label}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <main className="flex-1 overflow-y-auto px-4 py-3">
            {tab === "tasks" ? <TasksView /> : <ExtractDataView />}
          </main>

          <footer className="border-t border-border px-4 py-2.5">
            <button
              type="button"
              onClick={openWebApp}
              className="flex w-full items-center justify-center gap-1.5 text-[11px] font-semibold text-primary hover:underline"
            >
              Xem tất cả trong mondaiy
              <ExternalLink className="h-3 w-3" />
            </button>
          </footer>
        </>
      )}
    </div>
  );
}
