import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  getValidAccessToken: vi.fn(),
  refreshSession: vi.fn(),
}));

vi.mock("@/lib/auth", () => auth);

describe("upload chunk từ offscreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("tôn trọng token null tường minh và không đọc storage.session", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ remainingMs: 1234, appended: true }), { status: 200 })
      );
    const { uploadAudioChunk } = await import("@/lib/api");

    await expect(
      uploadAudioChunk("42", new Blob(["audio"]), "mine", 0, null)
    ).resolves.toEqual({ remainingMs: 1234, heard: true });

    expect(auth.getValidAccessToken).not.toHaveBeenCalled();
    expect(auth.refreshSession).not.toHaveBeenCalled();
    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("chunk không nối thêm chữ nào thì không tính là có tín hiệu", async () => {
    // appended=false nghĩa là STT chỉ nghe ra tiếng ồn. Đây chính là dữ liệu để
    // background đếm khoảng lặng, nhận nhầm thành có người nói thì cuộc họp đã
    // tan vẫn bị ghi tiếp cho tới khi hết hạn mức.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ appended: false, remainingMs: 900 }), { status: 200 })
    );
    const { uploadAudioChunk } = await import("@/lib/api");

    await expect(
      uploadAudioChunk("42", new Blob(["audio"]), "theirs", 20_000, "token")
    ).resolves.toEqual({ remainingMs: 900, heard: false });
  });

  it("để background cấp token mới ở vòng retry khi server trả 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Token hết hạn" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );
    const { uploadAudioChunk } = await import("@/lib/api");

    await expect(
      uploadAudioChunk("42", new Blob(["audio"]), "mine", 0, "expired-token")
    ).rejects.toEqual(expect.objectContaining({ status: 401 }));

    expect(auth.refreshSession).not.toHaveBeenCalled();
  });
});

describe("task check-in API", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("đánh dấu bắt đầu bằng POST đúng endpoint", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ id: 42 }), { status: 200 }));
    const { startTask } = await import("@/lib/api");

    await startTask(42);

    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/api\/v1\/tasks\/42\/start$/);
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
  });

  it("hoàn thành không tự khai thời lượng thì không gửi body", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ id: 42 }), { status: 200 }));
    const { completeTask } = await import("@/lib/api");

    await completeTask(42);

    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/api\/v1\/tasks\/42\/complete$/);
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBeUndefined();
  });

  it("hoàn thành có số phút thì gửi actualMinutes tường minh", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ id: 42 }), { status: 200 }));
    const { completeTask } = await import("@/lib/api");

    await completeTask(42, 25);

    expect(fetchMock.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ method: "POST", body: JSON.stringify({ actualMinutes: 25 }) })
    );
  });
});
