import { describe, expect, it, vi } from "vitest";
import {
  computeOffsetMs,
  createRecordingSession,
  decideIdleAction,
  describeState,
  IDLE_AUTO_STOP_AFTER_MS,
  IDLE_PROMPT_AFTER_MS,
  markIdleAsked,
  markSignal,
  markStillMeeting,
  formatElapsed,
  hydrateRecordingSession,
  isActive,
  markChunkFailed,
  markChunkUploaded,
  markDone,
  markEmptyDiscarded,
  markQuotaExhausted,
  markError,
  markRecording,
  RecorderRotationState,
  recordingSessionNeedsMigration,
  startRequesting,
  stopRecording,
} from "./recording";

describe("vòng đời phiên ghi âm", () => {
  it("đi đúng chuỗi idle -> requesting -> recording -> finalizing -> done", () => {
    let session = createRecordingSession();
    expect(session.state).toBe("idle");

    session = startRequesting(session);
    expect(session.state).toBe("requesting");

    session = markRecording(session, "note-1", 1_000);
    expect(session.state).toBe("recording");
    expect(session.noteId).toBe("note-1");
    expect(session.startedAt).toBe(1_000);

    session = stopRecording(session);
    expect(session.state).toBe("finalizing");

    session = markDone(session);
    expect(session.state).toBe("done");
  });

  it("bắt đầu phiên mới thì xoá bộ đếm chunk của phiên trước", () => {
    let session = markChunkUploaded(markRecording(startRequesting(createRecordingSession()), "note-1", 0));
    session = markDone(session);

    const fresh = startRequesting(session);
    expect(fresh.uploadedChunks).toBe(0);
    expect(fresh.failedChunks).toBe(0);
    expect(fresh.noteId).toBeNull();
  });
});

describe("đếm chunk", () => {
  it("upload lỗi chỉ tăng số chunk hỏng, không đá phiên khỏi trạng thái recording", () => {
    let session = markRecording(startRequesting(createRecordingSession()), "note-1", 0);

    session = markChunkFailed(session);
    session = markChunkFailed(session);

    expect(session.failedChunks).toBe(2);
    expect(session.uploadedChunks).toBe(0);
    expect(session.state).toBe("recording");
  });

  it("upload thành công tăng số chunk đã gửi và giữ nguyên trạng thái", () => {
    let session = markRecording(startRequesting(createRecordingSession()), "note-1", 0);

    session = markChunkUploaded(markChunkUploaded(session));

    expect(session.uploadedChunks).toBe(2);
    expect(session.state).toBe("recording");
  });
});

describe("computeOffsetMs", () => {
  it("tính đúng khoảng cách tới mốc bắt đầu", () => {
    expect(computeOffsetMs(1_000, 1_000)).toBe(0);
    expect(computeOffsetMs(1_000, 21_000)).toBe(20_000);
    expect(computeOffsetMs(1_000, 61_500)).toBe(60_500);
  });

  it("không trả số âm khi đồng hồ hệ thống bị lùi", () => {
    expect(computeOffsetMs(5_000, 1_000)).toBe(0);
  });
});

describe("dừng ghi", () => {
  it("bấm dừng lúc đang idle không crash và không đổi trạng thái", () => {
    const session = createRecordingSession();
    expect(() => stopRecording(session)).not.toThrow();
    expect(stopRecording(session).state).toBe("idle");
  });

  it("bấm dừng lúc đã done cũng không quay ngược về finalizing", () => {
    const session = markDone(markRecording(startRequesting(createRecordingSession()), "note-1", 0));
    expect(stopRecording(session).state).toBe("done");
  });
});

describe("cắt chunk MediaRecorder", () => {
  it("chỉ cho restart sau khi stop-event đã tới", () => {
    const rotation = new RecorderRotationState();

    expect(rotation.requestRotation()).toBe(true);
    // Timer chạy lại khi stop cũ còn pending không được gọi stop lần hai.
    expect(rotation.requestRotation()).toBe(false);
    // stop-event là thời điểm duy nhất caller được gọi recorder.start().
    expect(rotation.recorderStopped()).toBe(true);
    expect(rotation.requestRotation()).toBe(true);
  });

  it("dừng cuối phiên trong lúc rotate đang pending không stop hoặc restart lần hai", () => {
    const rotation = new RecorderRotationState();

    expect(rotation.requestRotation()).toBe(true);
    expect(rotation.requestFinalStop()).toBe(false);
    expect(rotation.recorderStopped()).toBe(false);
    expect(rotation.requestRotation()).toBe(false);
  });

  it("dừng cuối phiên bình thường phát đúng một lệnh stop", () => {
    const rotation = new RecorderRotationState();

    expect(rotation.requestFinalStop()).toBe(true);
    expect(rotation.requestFinalStop()).toBe(false);
    expect(rotation.recorderStopped()).toBe(false);
  });
});

describe("trạng thái phụ", () => {
  it("markError giữ lại thông điệp để popup hiện đúng lý do", () => {
    const session = markError(createRecordingSession(), "Không truy cập được micro.");
    expect(session.state).toBe("error");
    expect(session.errorMessage).toBe("Không truy cập được micro.");
  });

  it("isActive chỉ đúng với các trạng thái đang chiếm micro", () => {
    const base = createRecordingSession();
    expect(isActive(base)).toBe(false);
    expect(isActive(startRequesting(base))).toBe(true);
    expect(isActive(markRecording(base, "note-1", 0))).toBe(true);
    expect(isActive(stopRecording(markRecording(base, "note-1", 0)))).toBe(true);
    expect(isActive(markDone(base))).toBe(false);
    expect(isActive(markError(base, "lỗi"))).toBe(false);
  });

  it("formatElapsed hiện mm:ss", () => {
    expect(formatElapsed(0)).toBe("00:00");
    expect(formatElapsed(65_000)).toBe("01:05");
    expect(formatElapsed(-5_000)).toBe("00:00");
  });
});

describe("hạn mức ghi âm", () => {
  it("phiên mới chưa biết hạn mức", () => {
    expect(createRecordingSession().remainingMs).toBeNull();
  });

  it("chunk thành công cập nhật hạn mức server trả về", () => {
    const session = markChunkUploaded(createRecordingSession(), 880_000);
    expect(session.remainingMs).toBe(880_000);
    expect(session.uploadedChunks).toBe(1);
  });

  it("server không trả hạn mức thì giữ nguyên số cũ, không ghi đè thành null", () => {
    const first = markChunkUploaded(createRecordingSession(), 880_000);
    const second = markChunkUploaded(first, null);
    expect(second.remainingMs).toBe(880_000);
    expect(second.uploadedChunks).toBe(2);
  });

  it("hết hạn mức chuyển trạng thái riêng, không phải error", () => {
    const recording = markRecording(createRecordingSession(), "12", Date.now());
    const exhausted = markQuotaExhausted(markChunkUploaded(recording, 20_000));

    expect(exhausted.state).toBe("quotaExhausted");
    expect(exhausted.remainingMs).toBe(0);
    // Phần đã ghi vẫn hợp lệ nên bộ đếm phải còn nguyên.
    expect(exhausted.uploadedChunks).toBe(1);
    expect(exhausted.errorMessage).toBeNull();
  });

  it("trạng thái hết hạn mức có nhãn riêng nói rõ phần đã ghi vẫn được giữ", () => {
    const label = describeState(markQuotaExhausted(createRecordingSession()));
    expect(label).toContain("hết thời lượng ghi hôm nay");
    expect(label).toContain("vẫn được giữ");
  });
});

describe("khép sổ phiên ghi", () => {
  it("cuộc họp rỗng bị xoá thì nói thẳng, không hiện 'đã ghi xong'", () => {
    const session = markEmptyDiscarded(markRecording(createRecordingSession(), "42", Date.now()));

    expect(session.state).toBe("emptyDiscarded");
    // noteId phải bị xoá: mở trang của note đã bị server xoá sẽ ra 404.
    expect(session.noteId).toBeNull();
    expect(describeState(session)).toContain("Không nghe được nội dung nào");
  });

  it("có tiêu đề server đặt thì hiện luôn trong popup", () => {
    const done = markDone(markRecording(createRecordingSession(), "42", Date.now()), "Chốt tiến độ đăng nhập");

    expect(done.state).toBe("done");
    expect(done.title).toBe("Chốt tiến độ đăng nhập");
    expect(describeState(done)).toBe("Đã lưu: Chốt tiến độ đăng nhập");
  });

  it("không có tiêu đề thì vẫn hiện nhãn cũ", () => {
    const done = markDone(markRecording(createRecordingSession(), "42", Date.now()));

    expect(describeState(done)).toBe("Đã ghi xong");
  });
});

describe("chẩn đoán chunk lỗi", () => {
  it("giữ lại thông báo lỗi để hiện ra thay vì chỉ đếm số", () => {
    const failed = markChunkFailed(createRecordingSession(), "TypeError: Failed to fetch");

    expect(failed.failedChunks).toBe(1);
    expect(failed.lastChunkError).toBe("TypeError: Failed to fetch");
    // Chunk hỏng không được dừng phiên ghi.
    expect(failed.state).toBe("idle");
  });

  it("lỗi sau không có thông báo thì giữ nguyên thông báo cũ", () => {
    const first = markChunkFailed(createRecordingSession(), "TypeError: Failed to fetch");
    const second = markChunkFailed(first);

    expect(second.failedChunks).toBe(2);
    expect(second.lastChunkError).toBe("TypeError: Failed to fetch");
  });
});

describe("lỗi đọc storage không được nuốt mất lời gọi mạng", () => {
  it("getSession trả null thay vì ném khi vùng storage không truy cập được", async () => {
    // Tái hiện đúng lỗi đã gặp: driver storage của wxt ném Error khi ngữ cảnh
    // đang chạy không đọc được vùng session. Trước khi sửa, lỗi này xuyên qua
    // getValidAccessToken rồi thoát ra TRƯỚC lời gọi fetch, nên chunk hỏng mà
    // server không nhận được request nào để mà log.
    vi.resetModules();
    vi.doMock("@/lib/storage", () => ({
      authSessionItem: {
        getValue: () => {
          throw new Error('"browser.storage.session" is undefined');
        },
        setValue: async () => {},
      },
    }));

    const { getSession, getValidAccessToken } = await import("@/lib/auth");

    await expect(getSession()).resolves.toBeNull();
    await expect(getValidAccessToken()).resolves.toBeNull();
    vi.doUnmock("@/lib/storage");
  });
});

describe("phát hiện cuộc họp im lặng", () => {
  const startedAt = 1_000_000;

  /** Phiên đang ghi, mốc tín hiệu cuối đúng bằng lúc bắt đầu. */
  function recordingSession() {
    return markRecording(startRequesting(createRecordingSession()), "note-1", startedAt);
  }

  it("chưa đủ 10 phút im lặng thì không làm gì", () => {
    const session = recordingSession();
    expect(decideIdleAction(session, startedAt + IDLE_PROMPT_AFTER_MS - 1)).toBe("none");
  });

  it("im lặng đủ 10 phút thì hỏi người dùng", () => {
    const session = recordingSession();
    expect(decideIdleAction(session, startedAt + IDLE_PROMPT_AFTER_MS)).toBe("ask");
  });

  it("chunk nghe ra chữ dời mốc im lặng, chunk im lặng thì không", () => {
    // markChunkUploaded một mình KHÔNG được coi là tín hiệu: chunk toàn tiếng
    // ồn vẫn upload thành công, nhận nhầm là có người nói thì máy ghi chạy mãi.
    const noisy = markChunkUploaded(recordingSession(), 1_000);
    expect(decideIdleAction(noisy, startedAt + IDLE_PROMPT_AFTER_MS)).toBe("ask");

    const heard = markSignal(noisy, startedAt + 60_000);
    expect(decideIdleAction(heard, startedAt + IDLE_PROMPT_AFTER_MS)).toBe("none");
    expect(decideIdleAction(heard, startedAt + 60_000 + IDLE_PROMPT_AFTER_MS)).toBe("ask");
  });

  it("hỏi rồi không ai trả lời trong 1 phút thì dừng", () => {
    const asked = markIdleAsked(recordingSession(), startedAt + IDLE_PROMPT_AFTER_MS);
    const deadline = startedAt + IDLE_PROMPT_AFTER_MS + IDLE_AUTO_STOP_AFTER_MS;
    expect(decideIdleAction(asked, deadline - 1)).toBe("none");
    expect(decideIdleAction(asked, deadline)).toBe("stop");
  });

  it("trả lời còn họp thì huỷ đồng hồ tự dừng và đếm lại từ đầu", () => {
    const asked = markIdleAsked(recordingSession(), startedAt + IDLE_PROMPT_AFTER_MS);
    const answeredAt = startedAt + IDLE_PROMPT_AFTER_MS + 10_000;
    const answered = markStillMeeting(asked, answeredAt);

    expect(answered.idleAskedAt).toBeNull();
    expect(decideIdleAction(answered, answeredAt + IDLE_AUTO_STOP_AFTER_MS)).toBe("none");
    expect(decideIdleAction(answered, answeredAt + IDLE_PROMPT_AFTER_MS)).toBe("ask");
  });

  it("phiên không còn ghi thì không hỏi và không tự dừng nữa", () => {
    const asked = markIdleAsked(recordingSession(), startedAt);
    const stopped = stopRecording(asked);
    expect(decideIdleAction(stopped, startedAt + IDLE_PROMPT_AFTER_MS * 10)).toBe("none");
  });

  it("popup nói rõ đang chờ xác nhận thay vì chỉ 'đang ghi'", () => {
    const asked = markIdleAsked(recordingSession(), startedAt);
    expect(describeState(asked)).toContain("còn diễn ra không");
  });
});

describe("migrate phiên ghi từ extension cũ", () => {
  it("hydrate phiên recording thiếu mốc idle và vẫn hỏi sau đúng 10 phút", () => {
    const startedAt = 1_000_000;
    const current = markRecording(createRecordingSession(), "note-legacy", startedAt);
    const {
      lastSignalAt: _lastSignalAt,
      idleAskedAt: _idleAskedAt,
      ...legacySession
    } = current;

    expect(recordingSessionNeedsMigration(legacySession)).toBe(true);

    const hydrated = hydrateRecordingSession(legacySession);
    expect(hydrated.lastSignalAt).toBe(startedAt);
    expect(hydrated.idleAskedAt).toBeNull();
    expect(describeState(hydrated)).toBe("Đang ghi cuộc họp");
    expect(decideIdleAction(hydrated, startedAt + IDLE_PROMPT_AFTER_MS - 1)).toBe("none");
    expect(decideIdleAction(hydrated, startedAt + IDLE_PROMPT_AFTER_MS)).toBe("ask");
  });

  it("storage event của schema cũ không làm popup hiện nhầm câu hỏi idle", () => {
    const legacySession = {
      ...createRecordingSession(),
      state: "recording" as const,
      noteId: "note-legacy",
      startedAt: 5_000,
    };
    delete (legacySession as Partial<typeof legacySession>).lastSignalAt;
    delete (legacySession as Partial<typeof legacySession>).idleAskedAt;

    const popupSession = hydrateRecordingSession(legacySession);

    expect(describeState(popupSession)).toBe("Đang ghi cuộc họp");
    expect(popupSession.idleAskedAt).toBeNull();
  });

  it("phiên schema hiện tại không bị ghi migration lặp lại", () => {
    expect(recordingSessionNeedsMigration(createRecordingSession())).toBe(false);
    expect(recordingSessionNeedsMigration(undefined)).toBe(false);
  });
});
