import { getValidAccessToken, refreshSession } from "@/lib/auth";
import type {
  ApiErrorBody,
  AudioChunkResult,
  DismissReason,
  DueNotificationsResponse,
  MeetingNote,
  FinalizeRecordingResult,
  NotificationBundle,
  PageExtractionSuggestion,
  RecordingQuota,
  RecordingSpeaker,
  Reminder,
  Task,
  TaskListResponse,
} from "@/types";

const API_BASE = import.meta.env.WXT_API_BASE_URL;
const DEFAULT_TIMEOUT_MS = 10_000;
// Chunk audio 20 giây nặng hơn payload JSON nhiều lần, mạng chậm mà cắt ở 10s
// thì chunk nào cũng hỏng. Retry ở phía gọi vẫn còn, đây chỉ là ngưỡng cuối.
const UPLOAD_TIMEOUT_MS = 60_000;
// Tóm tắt trang gọi rule+LLM hybrid cho TỪNG dòng "ambiguous" (xem
// src/services/page_extraction.py), tuần tự theo lô 5 dòng/lần — trang chat
// (Zalo, Messenger...) có thể có hàng chục dòng, dễ vượt 10s mặc định dù
// backend vẫn đang xử lý bình thường, không phải lỗi thật.
const SUMMARIZE_TIMEOUT_MS = 45_000;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function authorizedFetch(
  path: string,
  init: RequestInit,
  timeoutMs: number,
  // Token truyền sẵn từ ngoài, dùng cho ngữ cảnh không đọc được storage
  // (offscreen document). Bỏ trống thì tự lấy như cũ.
  explicitToken?: string | null
): Promise<Response> {
  // `null` truyền tường minh có nghĩa là caller đã tự xử lý việc lấy token
  // nhưng hiện không có token. Không được dùng `??` ở đây: nó sẽ rơi ngược về
  // getValidAccessToken() trong offscreen document, nơi storage.session không
  // truy cập được.
  const usesExplicitToken = explicitToken !== undefined;
  const token = usesExplicitToken ? explicitToken : await getValidAccessToken();
  const headers = new Headers({ "Content-Type": "application/json", ...init.headers });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const url = `${API_BASE}${path}`;
  let response = await fetchWithTimeout(url, { ...init, headers }, timeoutMs);

  // Caller truyền token (offscreen) sẽ xin lại token từ background ở vòng retry.
  // Refresh ngay tại đây lại chạm storage.session trong sai execution context.
  if (response.status === 401 && !usesExplicitToken) {
    const refreshed = await refreshSession();
    if (refreshed) {
      headers.set("Authorization", `Bearer ${refreshed.accessToken}`);
      response = await fetchWithTimeout(url, { ...init, headers }, timeoutMs);
    }
  }

  return response;
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const response = await authorizedFetch(path, init, timeoutMs);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiError(response.status, body?.detail ?? `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Task đang chờ duyệt (status=proposed) — nguồn của badge nền + banner đếm
 * trong popup; danh sách chính của popup giờ là task ĐÃ duyệt. */
export async function listProposedTasks(): Promise<Task[]> {
  const body = await requestJson<TaskListResponse>("/api/v1/tasks?status=proposed");
  return body.tasks;
}

/** Task đã duyệt (status=confirmed) — danh sách chính hiển thị trong popup
 * kèm mức ưu tiên (yêu cầu 2026-08-25). */
export async function listConfirmedTasks(): Promise<Task[]> {
  const body = await requestJson<TaskListResponse>("/api/v1/tasks?status=confirmed");
  return body.tasks;
}

export async function confirmTask(taskId: number): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}/confirm`, { method: "POST" });
}

export async function dismissTask(taskId: number): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}/dismiss`, { method: "POST" });
}

export async function startTask(taskId: number): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}/start`, { method: "POST" });
}

export async function completeTask(taskId: number, actualMinutes?: number): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}/complete`, {
    method: "POST",
    ...(actualMinutes === undefined
      ? {}
      : { body: JSON.stringify({ actualMinutes }) }),
  });
}

/** Tạo task "proposed" thủ công — dùng chung endpoint với thẻ gợi ý trên web
 * app (src/api/tasks.py: POST /tasks/from-suggestion), tái sử dụng đúng cơ chế
 * Task hiện có thay vì tạo hệ thống lưu trữ riêng cho dữ liệu lấy từ tab.
 * dueAt bỏ trống khi backend không parse chắc chắn được thời hạn (BR-05). */
export interface CreateTaskFromSuggestionExtras {
  expectedOutput?: string;
  acceptanceCriteria?: string;
  contextInput?: string;
  constraints?: string;
  executionTool?: string;
  executionMethod?: string;
  statedPriority?: string;
  stakeholders?: string[];
  deliverTo?: string;
  assignee?: string;
  source?: string;
}

export async function createTaskFromSuggestion(
  title: string,
  detail: string,
  dueAt?: string | null,
  extras?: CreateTaskFromSuggestionExtras
): Promise<Task> {
  const body: Record<string, unknown> = { title, detail };
  if (dueAt) body.dueAt = dueAt;
  if (extras) {
    if (extras.expectedOutput) body.expectedOutput = extras.expectedOutput;
    if (extras.acceptanceCriteria) body.acceptanceCriteria = extras.acceptanceCriteria;
    if (extras.contextInput) body.contextInput = extras.contextInput;
    if (extras.constraints) body.constraints = extras.constraints;
    if (extras.executionTool) body.executionTool = extras.executionTool;
    if (extras.executionMethod) body.executionMethod = extras.executionMethod;
    if (extras.statedPriority) body.statedPriority = extras.statedPriority;
    if (extras.stakeholders && extras.stakeholders.length > 0) body.stakeholders = extras.stakeholders;
    if (extras.deliverTo) body.deliverTo = extras.deliverTo;
    if (extras.assignee) body.assignee = extras.assignee;
    if (extras.source) body.source = extras.source;
  }
  return requestJson<Task>("/api/v1/tasks/from-suggestion", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Tab "Lấy dữ liệu": gửi nội dung tab đang active (đã redact ở client) lên
 * backend để LLM một lượt trên toàn đoạn phân loại (có đọc user_profile/
 * long_term_memories để điền bối cảnh) — trả MỘT suggestion cho MỖI việc
 * nhận diện được, đã gộp sẵn dòng liên quan — KHÔNG tạo task, chỉ trả gợi ý
 * để người dùng confirm/bỏ từng cái trước khi lưu thật (createTaskFromSuggestion). */
export async function summarizePageExtraction(
  url: string,
  pageTitle: string,
  text: string,
  sourceContext = ""
): Promise<PageExtractionSuggestion[]> {
  const body = await requestJson<{ suggestions: PageExtractionSuggestion[] }>(
    "/api/v1/tasks/summarize-page-extraction",
    { method: "POST", body: JSON.stringify({ url, pageTitle, text, sourceContext }) },
    SUMMARIZE_TIMEOUT_MS
  );
  return body.suggestions;
}

/** Đọc nhẹ lịch nhắc đã gộp/chặn bão thông báo phía server (ADR-007 mục 8-9). */
export async function getDueReminders(): Promise<NotificationBundle[]> {
  const body = await requestJson<DueNotificationsResponse>("/api/v1/reminders/due");
  return body.notifications;
}

/** Gọi ngay sau khi thật sự tạo được OS notification — chống giao trùng khi
 * service worker khởi động lại giữa chừng (FR-091). */
export async function recordReminderDeliveries(reminderIds: number[]): Promise<void> {
  await requestJson("/api/v1/reminders/deliveries", {
    method: "POST",
    body: JSON.stringify({ reminderIds }),
  });
}

export async function snoozeReminder(reminderId: number, minutes?: number): Promise<Reminder> {
  return requestJson<Reminder>(`/api/v1/reminders/${reminderId}/snooze`, {
    method: "POST",
    body: JSON.stringify(minutes ? { minutes } : {}),
  });
}

export async function dismissReminder(reminderId: number, reason: DismissReason): Promise<Reminder> {
  return requestJson<Reminder>(`/api/v1/reminders/${reminderId}/dismiss`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

/**
 * Tạo ghi chú cuộc họp rỗng trước khi bật micro. Phải có id ngay từ đầu vì mỗi
 * chunk upload ngay khi cắt xong, không chờ hết cuộc họp mới biết gửi vào đâu.
 * id được ép về string để chỗ gọi khỏi quan tâm backend trả số hay chuỗi.
 */
export async function createMeetingNote(): Promise<MeetingNote> {
  const body = await requestJson<{ id: string | number }>("/api/v1/meeting-notes", {
    method: "POST",
    body: JSON.stringify({}),
  });
  return { id: String(body.id) };
}

/**
 * Gửi một chunk webm hoàn chỉnh kèm vị trí của nó trên trục thời gian.
 *
 * Body multipart được ráp tay thay vì dùng FormData: `authorizedFetch` luôn gắn
 * sẵn `Content-Type: application/json`, mà FormData thì cần trình duyệt tự sinh
 * boundary — hai thứ này xung khắc. Tự đặt boundary rồi ghi đè header là cách
 * dùng lại được `authorizedFetch` (token + tự refresh 401) mà không phải sửa nó.
 */
export async function uploadAudioChunk(
  noteId: string,
  blob: Blob,
  speaker: RecordingSpeaker,
  offsetMs: number,
  token: string | null
): Promise<AudioChunkResult> {
  const boundary = `----mondaiy${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  const field = (name: string, value: string): string =>
    `--${boundary}\r\nContent-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`;

  const body = new Blob([
    field("speaker", speaker),
    field("offset_ms", String(offsetMs)),
    `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="chunk-${offsetMs}.webm"\r\n` +
      `Content-Type: audio/webm\r\n\r\n`,
    blob,
    `\r\n--${boundary}--\r\n`,
  ]);

  const response = await authorizedFetch(
    `/api/v1/meeting-notes/${noteId}/audio-chunk`,
    {
      method: "POST",
      headers: { "Content-Type": `multipart/form-data; boundary=${boundary}` },
      body,
    },
    UPLOAD_TIMEOUT_MS,
    token
  );

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiError(response.status, errorBody?.detail ?? `HTTP ${response.status}`);
  }

  // Server trả kèm hạn mức còn lại sau mỗi chunk để popup đếm ngược mà không
  // phải gọi thêm endpoint giữa lúc đang ghi, và cờ `appended` cho biết chunk
  // này có nghe ra chữ nào không — căn cứ duy nhất để phát hiện phòng họp đã
  // trống mà máy vẫn đang ghi.
  const result = (await response.json().catch(() => null)) as
    | { remainingMs?: number; appended?: boolean }
    | null;
  return { remainingMs: result?.remainingMs ?? null, heard: result?.appended === true };
}

/**
 * Hạn mức ghi âm còn lại trong ngày. Gọi trước khi bắt đầu ghi: còn 1 phút mà
 * mở máy ghi cả cuộc họp thì phần lớn nội dung mất trắng, biết trước thì người
 * dùng chọn được cách khác.
 */
export async function getRecordingQuota(): Promise<RecordingQuota> {
  return requestJson<RecordingQuota>("/api/v1/meeting-notes/recording-quota");
}

/**
 * Khép lại phiên ghi: server xoá cuộc họp nếu không thu được chữ nào, ngược lại
 * tự đặt tên theo nội dung. Trả về `deleted` để chỗ gọi biết có nên mở trang
 * ghi chú hay không — mở trang của một note vừa bị xoá sẽ ra 404.
 */
export async function finalizeRecording(noteId: string): Promise<FinalizeRecordingResult> {
  return requestJson<FinalizeRecordingResult>(
    `/api/v1/meeting-notes/${noteId}/finalize-recording`,
    { method: "POST" }
  );
}
