import type { RecordingSpeaker } from "@/types";

/**
 * State machine thuần của luồng ghi âm cuộc họp — cố ý KHÔNG chạm MediaRecorder,
 * getUserMedia hay chrome.* để test được bằng vitest trong môi trường node.
 * Phần thật sự đụng Web API nằm ở entrypoints/offscreen/main.ts.
 */

// Các trạng thái hiển thị được của phiên ghi âm; popup render theo đúng danh sách này.
export type RecordingState =
  | "idle"
  | "requesting"
  | "recording"
  | "finalizing"
  | "done"
  | "error"
  // Hết hạn mức ghi trong ngày. Tách khỏi "error" vì đây không phải sự cố:
  // phần đã ghi vẫn hợp lệ, chỉ là không ghi thêm được cho tới ngày mai.
  | "quotaExhausted"
  // Dừng mà không thu được chữ nào nên cuộc họp đã bị xoá. Cũng không phải
  // lỗi: người dùng cần biết là KHÔNG có gì được lưu, thay vì mở ra trang trống.
  | "emptyDiscarded";

// Độ dài mỗi chunk, cũng chính là độ trễ tối thiểu trước khi một câu nói hiện
// ra trong transcript: chunk chỉ rời khỏi máy khi recorder stop. 5 giây là chỗ
// đứng giữa — đủ ngắn để người xem thấy chữ chảy gần như liên tục, còn đủ dài
// để mỗi lần cắt không xé quá nhiều từ ở mép và không bắn quá dày request STT.
// Phải khớp `recording_chunk_duration_ms` trong src/config.py, vì server lấy
// đúng số đó làm bước lưới quy chuẩn offset khi trừ hạn mức.
export const CHUNK_DURATION_MS = 5_000;

// Backoff giữa các lần thử lại khi upload chunk hỏng. Hết danh sách là bỏ chunk
// đó, tuyệt đối không dừng ghi âm vì một chunk lỗi.
export const UPLOAD_RETRY_DELAYS_MS: readonly number[] = [1_000, 3_000];

// Im lặng bao lâu thì hỏi người dùng cuộc họp còn không. 10 phút đủ dài để
// không cắt ngang một đoạn suy nghĩ hay giờ nghỉ giữa buổi, nhưng đủ ngắn để
// một cuộc họp đã tan không ăn thêm cả tiếng hạn mức ghi âm.
export const IDLE_PROMPT_AFTER_MS = 10 * 60_000;

// Hỏi rồi mà không ai trả lời trong ngần này thì tự dừng. Không trả lời gần như
// chắc chắn là người dùng đã rời máy — dừng vẫn giữ nguyên phần đã ghi, còn ghi
// tiếp thì đốt hạn mức vào phòng họp trống.
export const IDLE_AUTO_STOP_AFTER_MS = 60_000;

/**
 * Điều phối vòng stop -> dataavailable -> stop-event -> start của MediaRecorder.
 *
 * `MediaRecorder.stop()` hoàn tất bất đồng bộ. Gọi `start()` ngay sau `stop()`
 * có thể ném InvalidStateError vì recorder vẫn đang ở pha stopping. State
 * machine nhỏ này buộc chỗ gọi chỉ restart sau sự kiện `stop`, đồng thời ngăn
 * lệnh dừng cuối phiên gọi `stop()` lần hai khi một vòng rotate đang chờ.
 */
export class RecorderRotationState {
  private phase: "recording" | "stopping" | "inactive" = "recording";
  private finalizing = false;

  /** true nghĩa là caller phải gọi recorder.stop() đúng một lần. */
  requestRotation(): boolean {
    if (this.finalizing || this.phase !== "recording") return false;
    this.phase = "stopping";
    return true;
  }

  /**
   * Dừng phiên. Nếu rotate đã gọi stop rồi thì chỉ đánh dấu finalizing và chờ
   * chính stop-event đang bay, không phát thêm một lệnh stop trùng.
   */
  requestFinalStop(): boolean {
    this.finalizing = true;
    if (this.phase !== "recording") return false;
    this.phase = "stopping";
    return true;
  }

  /** true nghĩa là caller được phép recorder.start() sau stop-event này. */
  recorderStopped(): boolean {
    if (this.phase !== "stopping") return false;
    if (this.finalizing) {
      this.phase = "inactive";
      return false;
    }
    this.phase = "recording";
    return true;
  }
}

/** Toàn bộ trạng thái một phiên ghi âm, đủ để popup vẽ UI mà không cần hỏi thêm. */
export interface RecordingSession {
  state: RecordingState;
  // id ghi chú cuộc họp do backend cấp trước khi bắt đầu capture.
  noteId: string | null;
  // Mốc thời gian bắt đầu ghi (epoch ms), dùng để tính đồng hồ mm:ss và offsetMs.
  startedAt: number | null;
  // Số chunk đã upload thành công, hiển thị trong popup.
  uploadedChunks: number;
  // Số chunk bỏ lỡ sau khi hết lượt retry — user cần biết ghi chú có thể thiếu.
  failedChunks: number;
  // Hạn mức còn lại trong ngày (ms), cập nhật sau mỗi chunk. null khi chưa
  // biết hoặc tài khoản không bị giới hạn.
  remainingMs: number | null;
  // Tiêu đề server tự đặt sau khi khép sổ; null khi chưa khép hoặc bị xoá.
  title: string | null;
  // Lần cuối server nghe được chữ nào (epoch ms). Chunk im lặng KHÔNG tính là
  // tín hiệu — đó chính là thứ cần phát hiện. null khi chưa ghi.
  lastSignalAt: number | null;
  // Thời điểm đã hỏi "cuộc họp còn không"; null khi chưa hỏi hoặc vừa được trả
  // lời. Đồng hồ 1 phút trước khi tự dừng đếm từ mốc này.
  idleAskedAt: number | null;
  // Lỗi của chunk hỏng gần nhất. Khác errorMessage: cái này không dừng phiên,
  // chỉ để người dùng và người sửa lỗi biết chunk hỏng vì cái gì.
  lastChunkError: string | null;
  errorMessage: string | null;
}

/** Phiên rỗng lúc chưa ghi gì — dùng làm giá trị khởi tạo ở background lẫn popup. */
export function createRecordingSession(): RecordingSession {
  return {
    state: "idle",
    noteId: null,
    startedAt: null,
    uploadedChunks: 0,
    failedChunks: 0,
    remainingMs: null,
    title: null,
    lastSignalAt: null,
    idleAskedAt: null,
    lastChunkError: null,
    errorMessage: null,
  };
}

/**
 * Bù các field được thêm sau khi extension đã có người dùng.
 *
 * Chrome giữ `storage.local` qua mỗi lần Reload/Update, nên một phiên đang ghi
 * từ bản cũ có thể thiếu field mà type hiện tại coi là bắt buộc. Với phiên
 * recording cũ, lấy `startedAt` làm mốc tín hiệu cuối để vẫn hỏi đúng sau 10
 * phút; tuyệt đối không lấy `Date.now()` vì reload không được kéo dài im lặng.
 */
export function hydrateRecordingSession(stored: unknown): RecordingSession {
  const empty = createRecordingSession();
  if (!stored || typeof stored !== "object" || Array.isArray(stored)) return empty;

  const partial = stored as Partial<RecordingSession>;
  const state = partial.state ?? empty.state;
  const startedAt = partial.startedAt ?? empty.startedAt;

  return {
    state,
    noteId: partial.noteId ?? empty.noteId,
    startedAt,
    uploadedChunks: partial.uploadedChunks ?? empty.uploadedChunks,
    failedChunks: partial.failedChunks ?? empty.failedChunks,
    remainingMs: partial.remainingMs ?? empty.remainingMs,
    title: partial.title ?? empty.title,
    lastSignalAt:
      partial.lastSignalAt ?? (state === "recording" ? startedAt : empty.lastSignalAt),
    idleAskedAt: partial.idleAskedAt ?? empty.idleAskedAt,
    lastChunkError: partial.lastChunkError ?? empty.lastChunkError,
    errorMessage: partial.errorMessage ?? empty.errorMessage,
  };
}

/** Storage chỉ cần ghi lại khi đây là object từ schema cũ còn thiếu field. */
export function recordingSessionNeedsMigration(stored: unknown): boolean {
  if (stored === undefined) return false;
  if (!stored || typeof stored !== "object" || Array.isArray(stored)) return true;

  return Object.keys(createRecordingSession()).some((field) =>
    !Object.prototype.hasOwnProperty.call(stored, field)
  );
}

/**
 * Đánh dấu đang xin quyền + tạo note. Reset bộ đếm vì đây là phiên mới hoàn
 * toàn, số chunk của phiên trước không được cộng dồn sang.
 */
export function startRequesting(session: RecordingSession): RecordingSession {
  return { ...createRecordingSession(), state: "requesting" };
}

/**
 * Chuyển sang đang ghi khi offscreen đã dựng xong stream. Ghi lại noteId và mốc
 * bắt đầu ở đây vì mọi offsetMs sau này đều tính từ mốc này.
 */
export function markRecording(
  session: RecordingSession,
  noteId: string,
  startedAt: number
): RecordingSession {
  // Coi mốc bắt đầu là tín hiệu đầu tiên: chưa nói gì trong 10 phút đầu cũng là
  // im lặng đáng hỏi, nhưng đồng hồ phải đếm từ lúc bắt đầu chứ không từ 0.
  return { ...session, state: "recording", noteId, startedAt, lastSignalAt: startedAt, idleAskedAt: null };
}

/**
 * Server vừa nghe được chữ: dời mốc tín hiệu và huỷ luôn câu hỏi đang treo.
 * Có người nói tức là cuộc họp còn diễn ra, không cần chờ họ bấm trả lời.
 */
export function markSignal(session: RecordingSession, at: number): RecordingSession {
  return { ...session, lastSignalAt: at, idleAskedAt: null };
}

/** Đã hỏi người dùng cuộc họp còn không — bắt đầu đếm 1 phút chờ trả lời. */
export function markIdleAsked(session: RecordingSession, at: number): RecordingSession {
  return { ...session, idleAskedAt: at };
}

/** Người dùng trả lời "vẫn đang họp": dời mốc tín hiệu để không hỏi lại ngay. */
export function markStillMeeting(session: RecordingSession, at: number): RecordingSession {
  return markSignal(session, at);
}

/**
 * Ba nước đi khi kiểm tra khoảng lặng, tính thuần từ hai mốc thời gian:
 * "none" là chưa tới lúc, "ask" là hỏi cuộc họp còn không, "stop" là hỏi rồi mà
 * không ai trả lời nên dừng hẳn.
 */
export type IdleDecision = "none" | "ask" | "stop";

export function decideIdleAction(session: RecordingSession, now: number): IdleDecision {
  // Chỉ xét lúc đang thu thật. Đang xin quyền hay đang tải chunk cuối mà chen
  // vào hỏi thì vừa vô nghĩa vừa đá nhau với luồng dừng.
  if (session.state !== "recording") return "none";
  if (session.idleAskedAt !== null) {
    return now - session.idleAskedAt >= IDLE_AUTO_STOP_AFTER_MS ? "stop" : "none";
  }
  if (session.lastSignalAt === null) return "none";
  return now - session.lastSignalAt >= IDLE_PROMPT_AFTER_MS ? "ask" : "none";
}

/**
 * Cộng một chunk upload thành công và cập nhật hạn mức còn lại nếu server có
 * trả. Không đổi `state` vì việc ghi vẫn đang chạy.
 */
export function markChunkUploaded(
  session: RecordingSession,
  remainingMs: number | null = null
): RecordingSession {
  return {
    ...session,
    uploadedChunks: session.uploadedChunks + 1,
    remainingMs: remainingMs ?? session.remainingMs,
  };
}

/**
 * Hết hạn mức ngày: dừng phiên chứ không retry. Mọi chunk sau cũng sẽ bị từ
 * chối nên ghi tiếp chỉ tốn pin và làm người dùng tưởng vẫn đang được ghi.
 * Giữ nguyên bộ đếm chunk để phần đã ghi được vẫn hiện đúng.
 */
export function markQuotaExhausted(session: RecordingSession): RecordingSession {
  return { ...session, state: "quotaExhausted", remainingMs: 0 };
}

/**
 * Cộng một chunk hỏng. Cố ý giữ nguyên `state`: upload lỗi là sự cố mạng cục
 * bộ, không phải lý do để cắt ngang cuộc họp đang được ghi.
 */
export function markChunkFailed(session: RecordingSession, message?: string): RecordingSession {
  return {
    ...session,
    failedChunks: session.failedChunks + 1,
    lastChunkError: message ?? session.lastChunkError,
  };
}

/**
 * Người dùng bấm dừng: chuyển sang finalizing để popup hiện "đang tải lên chunk
 * cuối". Gọi lúc đang idle/done thì trả về nguyên trạng — bấm dừng nhầm không
 * được làm hỏng state machine.
 */
export function stopRecording(session: RecordingSession): RecordingSession {
  if (session.state !== "recording" && session.state !== "requesting") return session;
  return { ...session, state: "finalizing" };
}

/** Chunk cuối đã gửi xong, phiên khép lại — popup chuyển sang màn "xong". */
export function markDone(session: RecordingSession, title?: string): RecordingSession {
  return { ...session, state: "done", title: title ?? session.title };
}

/**
 * Không thu được chữ nào nên server đã xoá cuộc họp. Phải nói thẳng ra thay vì
 * hiện "Đã ghi xong": người dùng tưởng có bản ghi rồi mới phát hiện mất trắng.
 */
export function markEmptyDiscarded(session: RecordingSession): RecordingSession {
  return { ...session, state: "emptyDiscarded", noteId: null, title: null };
}

/** Lỗi chặn cả phiên (mất quyền mic, tabCapture từ chối...), khác hẳn lỗi từng chunk. */
export function markError(session: RecordingSession, message: string): RecordingSession {
  return { ...session, state: "error", errorMessage: message };
}

/**
 * Vị trí của một chunk trên trục thời gian cuộc họp, tính bằng ms kể từ mốc bắt
 * đầu ghi. Server ghép mic + tab lại theo đúng con số này nên không được lấy
 * thời điểm upload thay cho thời điểm ghi.
 */
export function computeOffsetMs(startedAt: number, now: number): number {
  return Math.max(0, now - startedAt);
}

/** Đồng hồ mm:ss đếm lên trong popup. */
export function formatElapsed(elapsedMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

/** Chỉ lúc đang ghi mới cần badge đỏ + nút dừng, gom điều kiện về một chỗ. */
export function isActive(session: RecordingSession): boolean {
  return session.state === "requesting" || session.state === "recording" || session.state === "finalizing";
}

/** Nhãn tiếng Việt cho từng trạng thái, dùng chung popup để không lệch chữ. */
export function describeState(session: RecordingSession): string {
  switch (session.state) {
    case "idle":
      return "Sẵn sàng ghi";
    case "requesting":
      return "Đang xin quyền và chuẩn bị...";
    case "recording":
      // Đang treo câu hỏi thì popup phải nói thẳng, nếu không người dùng mở
      // popup ra chỉ thấy "đang ghi" rồi bị dừng sau một phút mà không hiểu vì sao.
      return session.idleAskedAt !== null
        ? "Không nghe thấy gì 10 phút — cuộc họp còn diễn ra không?"
        : "Đang ghi cuộc họp";
    case "finalizing":
      return "Đang tải lên đoạn cuối...";
    case "done":
      return session.title ? `Đã lưu: ${session.title}` : "Đã ghi xong";
    case "error":
      return session.errorMessage ?? "Ghi âm gặp lỗi";
    case "quotaExhausted":
      return "Đã hết thời lượng ghi hôm nay — phần đã ghi vẫn được giữ";
    case "emptyDiscarded":
      return "Không nghe được nội dung nào — cuộc họp trống đã được bỏ";
  }
}

/** Nhãn người nói để hiện trong UI — "mine" là micro của mình, "theirs" là tiếng từ tab. */
export function describeSpeaker(speaker: RecordingSpeaker): string {
  return speaker === "mine" ? "Micro của bạn" : "Tiếng từ cuộc họp";
}
