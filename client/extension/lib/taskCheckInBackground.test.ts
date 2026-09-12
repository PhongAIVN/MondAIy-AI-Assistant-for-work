import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  completeTask: vi.fn(),
  createMeetingNote: vi.fn(),
  dismissReminder: vi.fn(),
  finalizeRecording: vi.fn(),
  getDueReminders: vi.fn(),
  listConfirmedTasks: vi.fn(),
  listProposedTasks: vi.fn(),
  recordReminderDeliveries: vi.fn(),
  snoozeReminder: vi.fn(),
  startTask: vi.fn(),
}));

const storageItems = vi.hoisted(() => ({
  activeReminderBundleItem: { getValue: vi.fn(), setValue: vi.fn() },
  askedTaskCheckInsItem: { getValue: vi.fn(), setValue: vi.fn() },
  autoOpenReminderPopupItem: { getValue: vi.fn() },
  notificationBundlesItem: { getValue: vi.fn(), setValue: vi.fn() },
  pendingTaskCountItem: { getValue: vi.fn(), setValue: vi.fn(), watch: vi.fn() },
}));

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/storage", () => storageItems);
vi.mock("@/lib/auth", () => ({
  applyWebSession: vi.fn(),
  getValidAccessToken: vi.fn(),
}));
vi.mock("@/lib/reminderPopup", () => ({
  maybeOpenReminderPopup: vi.fn(),
  shouldAutoOpenReminderPopup: vi.fn(() => false),
}));

function makeChromeMock() {
  return {
    action: {
      setBadgeBackgroundColor: vi.fn().mockResolvedValue(undefined),
      setBadgeText: vi.fn().mockResolvedValue(undefined),
    },
    alarms: {
      create: vi.fn(),
      onAlarm: { addListener: vi.fn() },
    },
    notifications: {
      clear: vi.fn().mockResolvedValue(true),
      create: vi.fn().mockResolvedValue("notification-id"),
      onButtonClicked: { addListener: vi.fn() },
      onClicked: { addListener: vi.fn() },
    },
    runtime: {
      onMessage: { addListener: vi.fn() },
      sendMessage: vi.fn().mockResolvedValue(undefined),
    },
    sidePanel: {
      open: vi.fn().mockResolvedValue(undefined),
      setPanelBehavior: vi.fn().mockResolvedValue(undefined),
    },
    storage: {
      local: {
        get: vi.fn().mockResolvedValue({}),
        set: vi.fn().mockResolvedValue(undefined),
      },
    },
    tabs: { create: vi.fn().mockResolvedValue(undefined) },
    windows: { getLastFocused: vi.fn() },
  };
}

function confirmedTask() {
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
  };
}

let startBackground: () => void;

beforeEach(async () => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  vi.stubGlobal("chrome", makeChromeMock());

  api.getDueReminders.mockResolvedValue([]);
  api.listConfirmedTasks.mockResolvedValue([confirmedTask()]);
  api.listProposedTasks.mockResolvedValue([]);
  storageItems.askedTaskCheckInsItem.getValue.mockResolvedValue({});
  storageItems.askedTaskCheckInsItem.setValue.mockResolvedValue(undefined);
  storageItems.pendingTaskCountItem.getValue.mockResolvedValue(0);
  storageItems.pendingTaskCountItem.setValue.mockResolvedValue(undefined);

  // Module giữ mutex trong memory; import mới mỗi case để negative test không
  // thể xanh giả vì poll của case trước vẫn đang chạy.
  vi.resetModules();
  vi.stubGlobal("defineBackground", (main: () => void) => ({ main }));
  const background = await import("../entrypoints/background");
  startBackground = (background.default as { main: () => void }).main;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("task check-in background guard", () => {
  it("08:00 gọi API task check-in và tạo câu hỏi", async () => {
    vi.setSystemTime(new Date(2026, 7, 27, 8, 0, 0, 0));

    startBackground();

    await vi.waitFor(() => {
      expect(api.listConfirmedTasks).toHaveBeenCalledOnce();
      expect(chrome.notifications.create).toHaveBeenCalledWith(
        "mondaiy-task-check-in-start-1",
        expect.objectContaining({ title: "Bắt đầu làm việc này chưa?" })
      );
    });
  });

  it.each([
    [7, 59],
    [22, 0],
    [2, 0],
  ])("%02i:%02i không gọi API task check-in và không tạo câu hỏi", async (hour, minute) => {
    vi.setSystemTime(new Date(2026, 7, 27, hour, minute, 0, 0));

    startBackground();
    await vi.waitFor(() => expect(api.listProposedTasks).toHaveBeenCalledOnce());

    expect(api.listConfirmedTasks).not.toHaveBeenCalled();
    expect(storageItems.askedTaskCheckInsItem.getValue).not.toHaveBeenCalled();
    expect(chrome.notifications.create).not.toHaveBeenCalledWith(
      expect.stringMatching(/^mondaiy-task-check-in-/),
      expect.anything()
    );
  });
});
