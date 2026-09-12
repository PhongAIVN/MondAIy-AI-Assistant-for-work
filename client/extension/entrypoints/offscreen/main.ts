import { ApiError, uploadAudioChunk } from "@/lib/api";
import {
  CHUNK_DURATION_MS,
  RecorderRotationState,
  UPLOAD_RETRY_DELAYS_MS,
  computeOffsetMs,
} from "@/lib/recording";
import { RECORDING_MESSAGES } from "@/types";
import type { OffscreenStartPayload, RecordingSpeaker } from "@/types";

// Opus trong webm là định dạng duy nhất Chrome ghi ổn định cho audio thuần.
const MIME_TYPE = "audio/webm;codecs=opus";

/** Một nguồn tiếng đang được ghi (micro hoặc tab) kèm bộ đếm cắt chunk của riêng nó. */
interface ChunkTrack {
  speaker: RecordingSpeaker;
  stream: MediaStream;
  recorder: MediaRecorder;
  rotateTimer: ReturnType<typeof setInterval> | null;
  // Offset (ms) của chunk đang ghi dở, tính từ mốc bắt đầu cuộc họp.
  currentOffsetMs: number;
  // Hàng đợi offset của các chunk đã stop nhưng blob chưa kịp về. Dùng hàng đợi
  // vì ondataavailable chạy bất đồng bộ, lúc đó currentOffsetMs đã nhảy sang
  // chunk kế tiếp rồi.
  pendingOffsets: number[];
  rotation: RecorderRotationState;
  // Được gắn lúc dừng toàn phiên và chỉ resolve từ `onstop`, sau khi browser đã
  // phát `dataavailable`. Đây là hàng rào bảo đảm chunk cuối đã vào upload queue.
  resolveFinalStop: (() => void) | null;
}

// Trạng thái phiên hiện tại của offscreen document. Chỉ có tối đa một phiên vì
// Chrome chỉ cho phép một offscreen document tồn tại tại một thời điểm.
let tracks: ChunkTrack[] = [];
let audioContext: AudioContext | null = null;
let currentNoteId: string | null = null;
let recordingStartedAt = 0;
// Các promise upload đang bay; lúc dừng phải chờ hết mới báo xong cho popup.
let inflightUploads: Promise<void>[] = [];

/** Báo ngược về background một sự kiện của phiên ghi; background giữ state để popup đọc. */
function notifyBackground(type: string, payload: Record<string, unknown> = {}): void {
  void chrome.runtime.sendMessage({ type, ...payload }).catch(() => {
    // Service worker đang ngủ hoặc popup đã đóng — không có gì để làm thêm,
    // nuốt lỗi để không kéo sập vòng ghi âm.
  });
}

/**
 * Xin access token từ background thay vì tự đọc storage.
 *
 * Phiên đăng nhập nằm ở storage.session, mà offscreen document không đọc được
 * vùng đó — driver storage ném Error, lỗi xuyên qua getValidAccessToken rồi
 * thoát ra trước cả lời gọi fetch, nên chunk hỏng mà server không thấy request
 * nào. Xin mỗi lần upload (không cache) để token hết hạn giữa cuộc họp dài vẫn
 * được background refresh giúp.
 */
async function requestAccessToken(): Promise<string | null> {
  try {
    const reply = (await chrome.runtime.sendMessage({
      type: RECORDING_MESSAGES.requestToken,
    })) as { token?: string | null } | undefined;
    return reply?.token ?? null;
  } catch {
    return null;
  }
}

/** Chờ một khoảng ms, dùng cho backoff giữa các lần retry upload. */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Upload một chunk, thử lại theo UPLOAD_RETRY_DELAYS_MS rồi bỏ cuộc.
 * Không bao giờ ném lỗi ra ngoài: mất một chunk chỉ làm ghi chú thiếu một đoạn,
 * còn dừng ghi giữa cuộc họp thì mất tất cả.
 */
async function uploadChunkWithRetry(
  noteId: string,
  blob: Blob,
  speaker: RecordingSpeaker,
  offsetMs: number
): Promise<void> {
  let lastUploadError = "khong ro";
  for (let attempt = 0; attempt <= UPLOAD_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const token = await requestAccessToken();
      const { remainingMs, heard } = await uploadAudioChunk(noteId, blob, speaker, offsetMs, token);
      notifyBackground(RECORDING_MESSAGES.chunkUploaded, { remainingMs, heard });
      return;
    } catch (error: unknown) {
      // Hết hạn mức ngày thì retry vô nghĩa: chunk sau cũng 429. Báo ngược để
      // background dừng hẳn phiên thay vì để người dùng tưởng vẫn đang ghi.
      if (error instanceof ApiError && error.status === 429) {
        notifyBackground(RECORDING_MESSAGES.quotaExhausted);
        return;
      }
      // Giữ lại lỗi cuối để báo ngược lên popup. Trước đây chỗ này nuốt lỗi
      // hoàn toàn nên chunk hỏng chỉ hiện ra dưới dạng một con số, không ai biết
      // hỏng vì cái gì — chẩn đoán bằng log server cũng vô ích khi request còn
      // chưa rời khỏi trình duyệt.
      lastUploadError = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
      console.error("[mondaiy] upload chunk lỗi", { speaker, offsetMs, attempt, error });
      const backoffMs = UPLOAD_RETRY_DELAYS_MS[attempt];
      if (backoffMs === undefined) break;
      await delay(backoffMs);
    }
  }
  notifyBackground(RECORDING_MESSAGES.chunkFailed, { message: lastUploadError });
}

/** Xếp một upload vào hàng chờ để lúc dừng còn biết mà đợi cho hết. */
function enqueueUpload(promise: Promise<void>): void {
  inflightUploads.push(promise);
  void promise.finally(() => {
    inflightUploads = inflightUploads.filter((item) => item !== promise);
  });
}

/**
 * Dựng một track ghi: mỗi lần MediaRecorder stop sẽ nhả ra một Blob webm hoàn
 * chỉnh (có header) nên upload thẳng được. Cố ý KHÔNG dùng timeslice của
 * MediaRecorder vì chunk sinh từ timeslice thiếu header, server không decode nổi.
 */
function createTrack(speaker: RecordingSpeaker, stream: MediaStream): ChunkTrack {
  const recorder = new MediaRecorder(stream, { mimeType: MIME_TYPE });
  const track: ChunkTrack = {
    speaker,
    stream,
    recorder,
    rotateTimer: null,
    currentOffsetMs: 0,
    pendingOffsets: [],
    rotation: new RecorderRotationState(),
    resolveFinalStop: null,
  };

  recorder.ondataavailable = (event: BlobEvent) => {
    const offsetMs = track.pendingOffsets.shift() ?? 0;
    if (event.data.size === 0 || !currentNoteId) return;
    enqueueUpload(uploadChunkWithRetry(currentNoteId, event.data, speaker, offsetMs));
  };

  // stop() phát dataavailable trước rồi mới phát stop. Chỉ tại stop-event này
  // recorder mới chắc chắn inactive và được phép start phiên chunk kế tiếp.
  recorder.onstop = () => {
    if (track.rotation.recorderStopped()) {
      recorder.start();
      return;
    }
    track.resolveFinalStop?.();
    track.resolveFinalStop = null;
  };

  recorder.start();
  track.rotateTimer = setInterval(() => rotateTrack(track), CHUNK_DURATION_MS);
  return track;
}

/**
 * Cắt chunk: stop để chốt file webm hiện tại, ghi lại mốc bắt đầu của chunk kế
 * tiếp TRƯỚC khi start lại, rồi start ngay để không hở tiếng giữa hai chunk.
 */
function rotateTrack(track: ChunkTrack): void {
  if (!track.rotation.requestRotation()) return;
  track.pendingOffsets.push(track.currentOffsetMs);
  track.recorder.stop();
  track.currentOffsetMs = computeOffsetMs(recordingStartedAt, Date.now());
}

/**
 * Xin hai stream riêng biệt và bắt đầu ghi.
 *
 * Bắt buộc phát lại tabStream qua AudioContext: tabCapture "chiếm" đường tiếng
 * của tab, không nối MediaStreamSource vào ctx.destination thì người dùng mất
 * hẳn tiếng cuộc họp trong lúc ghi.
 */
async function startRecording(payload: OffscreenStartPayload): Promise<void> {
  // In ra cấu hình thật lúc chạy: nếu WXT không inline được biến môi trường thì
  // URL thành "undefined/api/..." và fetch ném TypeError trước khi ra mạng —
  // đúng triệu chứng chunk hỏng mà server không thấy request nào.
  console.info("[mondaiy] offscreen bắt đầu", {
    apiBase: import.meta.env.WXT_API_BASE_URL,
    noteId: payload.noteId,
  });
  currentNoteId = payload.noteId;
  recordingStartedAt = payload.startedAt;

  const tabStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: payload.streamId,
      },
    },
  } as unknown as MediaStreamConstraints);

  const micStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true },
  });

  audioContext = new AudioContext();
  const passthrough = audioContext.createMediaStreamSource(tabStream);
  passthrough.connect(audioContext.destination);

  tracks = [createTrack("mine", micStream), createTrack("theirs", tabStream)];
}

/** Dừng hẳn: chốt chunk cuối của cả hai track, chờ upload xong rồi mới báo hoàn tất. */
async function stopRecording(): Promise<void> {
  // Gắn waiter trước khi gọi stop để không bỏ lỡ `onstop`. Nếu đúng lúc timer
  // đang rotate, requestFinalStop chỉ đánh dấu finalizing; chính stop-event đang
  // bay vẫn resolve waiter sau khi dataavailable của chunk đó được phát.
  const finalStops = tracks.map(
    (track) =>
      new Promise<void>((resolve) => {
        track.resolveFinalStop = resolve;
      })
  );

  for (const track of tracks) {
    if (track.rotateTimer !== null) clearInterval(track.rotateTimer);
    track.rotateTimer = null;
    if (track.rotation.requestFinalStop()) {
      track.pendingOffsets.push(track.currentOffsetMs);
      track.recorder.stop();
    }
  }

  // Theo MediaRecorder, dataavailable được phát trước stop. Chờ stop thật thay
  // vì đoán bằng setTimeout(0), vốn có thể chạy trước event của browser và làm
  // offscreen bị đóng khi chunk cuối chưa kịp upload.
  await Promise.all(finalStops);
  await Promise.allSettled(inflightUploads);

  for (const track of tracks) {
    track.stream.getTracks().forEach((mediaTrack) => mediaTrack.stop());
  }
  tracks = [];

  if (audioContext) {
    await audioContext.close();
    audioContext = null;
  }
  currentNoteId = null;
  notifyBackground(RECORDING_MESSAGES.finished);
}

chrome.runtime.onMessage.addListener((message: { type?: string } & Partial<OffscreenStartPayload>) => {
  if (message?.type === RECORDING_MESSAGES.offscreenStart) {
    void startRecording(message as OffscreenStartPayload).catch((error: unknown) => {
      notifyBackground(RECORDING_MESSAGES.failed, {
        message: error instanceof Error ? error.message : "Không truy cập được micro hoặc tiếng của tab.",
      });
    });
    return;
  }
  if (message?.type === RECORDING_MESSAGES.offscreenStop) {
    void stopRecording();
  }
});
