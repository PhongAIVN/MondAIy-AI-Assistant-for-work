import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  uploadAudioChunk: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    constructor(public readonly status: number, message: string) {
      super(message);
    }
  },
  uploadAudioChunk: api.uploadAudioChunk,
}));

type MessageListener = (message: Record<string, unknown>) => void;

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(_stream: MediaStream, _options: MediaRecorderOptions) {
    FakeMediaRecorder.instances.push(this);
  }

  start() {}

  stop() {
    // Browser không hứa event sẽ tới trong cùng tick. Độ trễ này tái hiện lỗi
    // cũ: finished được báo trước khi dataavailable của chunk cuối xuất hiện.
    setTimeout(() => {
      this.ondataavailable?.({ data: new Blob(["last audio chunk"]) });
      this.onstop?.();
    }, 20);
  }
}

describe("khép phiên ghi offscreen", () => {
  let listener: MessageListener;
  let sentMessages: Array<Record<string, unknown>>;
  let resolveUploads: Array<() => void>;

  beforeEach(async () => {
    vi.resetModules();
    vi.useRealTimers();
    FakeMediaRecorder.instances = [];
    sentMessages = [];
    resolveUploads = [];
    api.uploadAudioChunk.mockReset();
    // Trả đúng hình dạng thật của uploadAudioChunk: chỗ gọi destructure kết quả
    // nên resolve undefined sẽ ném TypeError và biến test thành nhánh lỗi.
    api.uploadAudioChunk.mockImplementation(
      () =>
        new Promise<{ remainingMs: number | null; heard: boolean }>((resolve) => {
          resolveUploads.push(() => resolve({ remainingMs: null, heard: true }));
        })
    );

    const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } },
    });
    Object.assign(globalThis, {
      MediaRecorder: FakeMediaRecorder,
      AudioContext: class {
        destination = {};
        createMediaStreamSource() { return { connect: vi.fn() }; }
        close() { return Promise.resolve(); }
      },
      chrome: {
        runtime: {
          onMessage: { addListener: (callback: MessageListener) => { listener = callback; } },
          sendMessage: vi.fn(async (message: Record<string, unknown>) => {
            sentMessages.push(message);
            if (message.type === "mondaiy-recording-request-token") return { token: "token" };
            return undefined;
          }),
        },
      },
    });

    await import("@/entrypoints/offscreen/main");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("chỉ báo finished sau khi dataavailable cuối và upload hoàn tất", async () => {
    listener({
      type: "mondaiy-offscreen-start",
      streamId: "stream-1",
      noteId: "42",
      startedAt: Date.now(),
    });
    await vi.waitFor(() => expect(FakeMediaRecorder.instances).toHaveLength(2));

    listener({ type: "mondaiy-offscreen-stop" });
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(sentMessages.some((message) => message.type === "mondaiy-recording-finished")).toBe(false);

    await vi.waitFor(() => expect(api.uploadAudioChunk).toHaveBeenCalledTimes(2));
    expect(sentMessages.some((message) => message.type === "mondaiy-recording-finished")).toBe(false);

    resolveUploads.forEach((resolve) => resolve());
    await vi.waitFor(() =>
      expect(sentMessages.some((message) => message.type === "mondaiy-recording-finished")).toBe(true)
    );
  });
});
