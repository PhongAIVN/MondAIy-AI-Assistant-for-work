export interface AuthSession {
  accessToken: string;
  expiresAt: number;
  refreshToken: string | null;
  // Chỉ có sau lần đầu tự refresh thật (POST /auth/refresh trả kèm avatarUrl,
  // xem TokenResponse ở src/models/schemas.py) — session đồng bộ ban đầu từ
  // localStorage web app (applyWebSession) chưa có, nên null lúc đó.
  avatarUrl: string | null;
  email?: string | null;
}

export interface ApiErrorBody {
  detail: string;
}

export type TaskStatus = "proposed" | "confirmed" | "dismissed";

export interface TaskEvidence {
  id: number;
  provider: string;
  evidenceQuote: string;
  deepLink: string;
}

export interface Task {
  id: number;
  title: string;
  detail: string;
  dueAt: string | null;
  allDay: boolean;
  ambiguous: boolean;
  assignee: string | null;
  assigneeAmbiguous: boolean;
  status: TaskStatus;
  startedAt: string | null;
  sourceCount: number;
  signalStrength: number;
  evidence: TaskEvidence[];
  // ADR-019 — Phiếu giao việc đầy đủ
  expectedOutput?: string | null;
  acceptanceCriteria?: string | null;
  contextInput?: string | null;
  constraints?: string | null;
  executionSteps?: string[] | null;
  executionTool?: string | null;
  executionMethod?: string | null;
  statedPriority?: string | null;
  stakeholders?: string[] | null;
  deliverTo?: string | null;
  estimateLowMin?: number | null;
  estimateHighMin?: number | null;
}

export interface TaskListResponse {
  tasks: Task[];
}

/** Một việc-cần-làm nhận diện được (LLM một lượt trên toàn đoạn, có đọc
 * user_profile/long_term_memories để điền bối cảnh — xem
 * src/services/page_extraction.py). Kết quả POST
 * /tasks/summarize-page-extraction là MỘT MẢNG suggestion, để người dùng
 * confirm/bỏ TỪNG CÁI trước khi lưu thật qua from-suggestion. dueAt chỉ có
 * khi backend parse chắc chắn được thời hạn (BR-05 — không đoán khi mơ hồ,
 * cụm gốc vẫn giữ trong detail nếu vậy).
 *
 * Field mở rộng (expectedOutput...deliverTo) CHỈ điền khi nguồn nêu rõ —
 * rỗng/[] là bình thường, không phải thiếu sót (rule-based fallback path
 * không có các field này). Trả RIÊNG (không gộp vào detail) để hiện thành ô
 * sửa riêng ở SuggestionCard — lúc lưu thật, composeFinalDetail() gộp lại
 * vào detail vì Task DB dùng chung nhiều pipeline khác không có cột riêng
 * cho các field này (xem App.tsx). */
export interface PageExtractionSuggestion {
  title: string;
  detail: string;
  dueAt: string | null;
  // Nguồn trả RIÊNG khỏi detail (trước đây bị nhét cứng vào cuối detail —
  // chật/khó đọc trên panel hẹp, phản hồi người dùng 2026-08-26). sourceUrl
  // luôn có giá trị; sourceLabel chỉ có khi backend đoán được nhãn cụ thể
  // hơn url (vd tên nhóm chat).
  sourceUrl: string;
  sourceLabel: string;
  expectedOutput: string;
  constraint: string;
  executionSteps: string[];
  executionTool: string;
  executionMethod: string;
  priority: string;
  assignee: string;
  stakeholders: string;
  deliverTo: string;
}

export type ReminderStatus = "scheduled" | "cancelled";

// FR-096: 3 lý do bỏ qua cố định, khớp DismissReason phía backend (src/models/schemas.py).
export type DismissReason = "khong_can_nua" | "da_lam_o_cho_khac" | "han_chot_sai";

export interface Reminder {
  id: number;
  taskId: number;
  milestone: string;
  scheduledAt: string;
  status: ReminderStatus;
  snoozeCount: number;
  dismissReason: string | null;
}

// 6 loai thong bao chung 1 pipe — khop ReminderKind phia backend
// (src/models/schemas.py). conflict_evidence/daily_brief/calendar_changed
// khong gan 1 task cu the nen taskId/dueAt co the null.
export type NotificationKind =
  | "task_due"
  | "task_proposed"
  | "conflict_schedule"
  | "conflict_evidence"
  | "daily_brief"
  | "calendar_changed";

export interface NotificationTask {
  kind: NotificationKind;
  title: string;
  milestone: string;
  taskId: number | null;
  dueAt: string | null;
  evidenceDeepLink: string | null;
  payload: Record<string, unknown>;
}

/** 1 bundle = 1 OS notification, có thể gộp nhiều task cùng khung giờ (FR-095). */
export interface NotificationBundle {
  bundleKey: string;
  scheduledAt: string;
  reminderIds: number[];
  tasks: NotificationTask[];
}

export interface DueNotificationsResponse {
  notifications: NotificationBundle[];
}

// Hai nguồn tiếng tách riêng của một cuộc họp: "mine" là micro của người dùng,
// "theirs" là âm thanh phát ra từ tab (tiếng của người khác). Tách nguồn ngay
// từ lúc ghi để backend gán đúng người nói, không phải đoán lại sau.
export type RecordingSpeaker = "mine" | "theirs";

/** Ghi chú cuộc họp do backend tạo trước khi bắt đầu capture; id dùng cho mọi chunk. */
export interface MeetingNote {
  id: string;
}

// Tên message giữa popup, background và offscreen. Gom thành hằng số để ba nơi
// không lệch chuỗi khi sửa.
export const RECORDING_MESSAGES = {
  start: "mondaiy-recording-start",
  stop: "mondaiy-recording-stop",
  offscreenStart: "mondaiy-offscreen-start",
  offscreenStop: "mondaiy-offscreen-stop",
  // Offscreen xin token từ background thay vì tự đọc storage. Vùng
  // storage.session chứa phiên đăng nhập không đọc được từ offscreen
  // document — driver của wxt ném Error, và lỗi đó nuốt luôn cả lời gọi
  // fetch nên chunk hỏng mà server không hề thấy request nào.
  requestToken: "mondaiy-recording-request-token",
  chunkUploaded: "mondaiy-recording-chunk-uploaded",
  chunkFailed: "mondaiy-recording-chunk-failed",
  // Server trả 429: hết hạn mức ngày. Khác chunkFailed ở chỗ ghi tiếp là vô
  // ích, mọi chunk sau cũng sẽ bị từ chối, nên background phải dừng phiên.
  quotaExhausted: "mondaiy-recording-quota-exhausted",
  // Người dùng trả lời câu hỏi "cuộc họp còn diễn ra không". Có cả trong popup
  // chứ không chỉ ở nút của OS notification: người tắt thông báo hệ thống sẽ
  // không bao giờ thấy câu hỏi, và bị tự dừng sau 1 phút mà không hiểu vì sao.
  stillMeeting: "mondaiy-recording-still-meeting",
  finished: "mondaiy-recording-finished",
  failed: "mondaiy-recording-failed",
} as const;

// Trạng thái phiên ghi nằm ở chrome.storage.local (không phải biến trong bộ
// nhớ) vì service worker MV3 bị Chrome tắt bất cứ lúc nào giữa cuộc họp.
export const RECORDING_SESSION_KEY = "recordingSession";

// Options page ghi true sau khi Chrome cấp quyền micro; popup đọc để biết nên
// hiện nút ghi hay nút xin quyền.
export const MIC_PERMISSION_KEY = "micPermissionGranted";

/** Payload background gửi sang offscreen để dựng stream và bắt đầu cắt chunk. */
export interface OffscreenStartPayload {
  type: typeof RECORDING_MESSAGES.offscreenStart;
  streamId: string;
  noteId: string;
  startedAt: number;
}

/** Hạn mức ghi âm trong ngày do backend cấp; admin có `unlimited` = true. */
export interface RecordingQuota {
  limitMs: number;
  usedMs: number;
  remainingMs: number;
  unlimited: boolean;
}

/** Kết quả xử lý một chunk audio: hạn mức còn lại và có nghe ra chữ nào không. */
export interface AudioChunkResult {
  // null khi server không trả hạn mức (tài khoản không bị giới hạn).
  remainingMs: number | null;
  // true khi STT nghe được chữ và transcript vừa dài thêm. Chunk chỉ có tiếng
  // ồn cho false — đó là tín hiệu để đếm khoảng lặng của cuộc họp.
  heard: boolean;
}

/** Kết quả khép lại phiên ghi: cuộc họp bị xoá vì rỗng, hoặc đã được đặt tên. */
export interface FinalizeRecordingResult {
  deleted: boolean;
  title?: string;
}
