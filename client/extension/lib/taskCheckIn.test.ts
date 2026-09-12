import { describe, expect, it, vi } from "vitest";

import {
  handleTaskCheckInButton,
  isWithinWorkHours,
  NEUTRAL_ESTIMATE_MINUTES,
  selectTaskCheckIn,
  taskCheckInNotificationId,
} from "@/lib/taskCheckIn";
import type { Task } from "@/types";

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    title: "Viết báo cáo",
    detail: "",
    dueAt: null,
    allDay: false,
    ambiguous: false,
    assignee: null,
    assigneeAmbiguous: false,
    status: "confirmed",
    startedAt: null,
    sourceCount: 1,
    signalStrength: 1,
    evidence: [],
    ...overrides,
  };
}

function localTime(hour: number, minute = 0): Date {
  return new Date(2026, 7, 27, hour, minute, 0, 0);
}

describe("giờ làm việc", () => {
  it.each([
    [8, 0, true],
    [10, 0, true],
    [21, 59, true],
    [7, 59, false],
    [22, 0, false],
    [2, 0, false],
  ])("xác định %02i:%02i là within=%s", (hour, minute, expected) => {
    expect(isWithinWorkHours(localTime(hour, minute))).toBe(expected);
  });
});

describe("chọn task check-in", () => {
  it("hỏi bắt đầu và nút Đang làm gọi startTask", async () => {
    const prompt = selectTaskCheckIn([makeTask()], {}, localTime(8));
    expect(prompt).toEqual(
      expect.objectContaining({
        question: "start",
        title: "Bắt đầu làm việc này chưa?",
        buttons: [{ title: "Đang làm" }, { title: "Chưa" }],
      })
    );

    const startTask = vi.fn().mockResolvedValue(undefined);
    const clearNotification = vi.fn();
    await handleTaskCheckInButton(prompt!.notificationId, 0, {
      startTask,
      completeTask: vi.fn(),
      clearNotification,
    });

    expect(startTask).toHaveBeenCalledOnce();
    expect(startTask).toHaveBeenCalledWith(1);
    expect(clearNotification).toHaveBeenCalledWith(prompt!.notificationId);
  });

  it("hỏi xong khi đã qua mốc estimate trung tính", () => {
    const now = localTime(10);
    const task = makeTask({
      startedAt: new Date(now.getTime() - NEUTRAL_ESTIMATE_MINUTES * 60_000).toISOString(),
    });

    expect(selectTaskCheckIn([task], {}, now)).toEqual(
      expect.objectContaining({
        question: "complete",
        title: "Xong chưa?",
        buttons: [{ title: "Xong" }, { title: "Chưa xong" }],
      })
    );
  });

  it("không hỏi lại cùng task và cùng câu hỏi", () => {
    const task = makeTask();
    const asked = { [taskCheckInNotificationId(task.id, "start")]: true } as Record<string, true>;

    expect(selectTaskCheckIn([task], asked, localTime(10))).toBeNull();
  });

  it.each([
    [8, 0],
    [10, 0],
    [21, 59],
  ])("hỏi trong giờ làm tại %02i:%02i", (hour, minute) => {
    expect(selectTaskCheckIn([makeTask()], {}, localTime(hour, minute))).toEqual(
      expect.objectContaining({ question: "start" })
    );
  });

  it.each([
    [7, 59],
    [22, 0],
    [2, 0],
  ])("không hỏi ngoài giờ làm tại %02i:%02i", (hour, minute) => {
    expect(selectTaskCheckIn([makeTask()], {}, localTime(hour, minute))).toBeNull();
  });

  it("mỗi lượt chỉ chọn tối đa một task", () => {
    const prompt = selectTaskCheckIn(
      [makeTask({ id: 1 }), makeTask({ id: 2 }), makeTask({ id: 3 })],
      {},
      localTime(10)
    );

    expect(prompt?.taskId).toBe(1);
  });

  it("đã hỏi bắt đầu vẫn được hỏi xong sau khi task có startedAt", () => {
    const now = localTime(10);
    const task = makeTask({
      startedAt: new Date(now.getTime() - NEUTRAL_ESTIMATE_MINUTES * 60_000).toISOString(),
    });
    const asked = { [taskCheckInNotificationId(task.id, "start")]: true } as Record<string, true>;

    expect(selectTaskCheckIn([task], asked, now)?.question).toBe("complete");
  });

  it("nút Chưa xong không gọi API và chỉ clear notification", async () => {
    const notificationId = taskCheckInNotificationId(7, "complete");
    const startTask = vi.fn();
    const completeTask = vi.fn();
    const clearNotification = vi.fn();

    await handleTaskCheckInButton(notificationId, 1, {
      startTask,
      completeTask,
      clearNotification,
    });

    expect(startTask).not.toHaveBeenCalled();
    expect(completeTask).not.toHaveBeenCalled();
    expect(clearNotification).toHaveBeenCalledWith(notificationId);
  });

  it("nút Xong gọi completeTask không tự khai actualMinutes", async () => {
    const notificationId = taskCheckInNotificationId(7, "complete");
    const completeTask = vi.fn().mockResolvedValue(undefined);
    const clearNotification = vi.fn();

    await handleTaskCheckInButton(notificationId, 0, {
      startTask: vi.fn(),
      completeTask,
      clearNotification,
    });

    expect(completeTask).toHaveBeenCalledOnce();
    expect(completeTask).toHaveBeenCalledWith(7);
    expect(clearNotification).toHaveBeenCalledWith(notificationId);
  });

  it("API hoàn thành lỗi thì không clear notification để còn retry", async () => {
    const notificationId = taskCheckInNotificationId(7, "complete");
    const clearNotification = vi.fn();

    await expect(
      handleTaskCheckInButton(notificationId, 0, {
        startTask: vi.fn(),
        completeTask: vi.fn().mockRejectedValue(new Error("offline")),
        clearNotification,
      })
    ).rejects.toThrow("offline");
    expect(clearNotification).not.toHaveBeenCalled();
  });
});
