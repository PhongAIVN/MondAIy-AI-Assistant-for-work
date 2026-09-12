// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  App,
  compareTaskPriority,
  composeFinalDetail,
  computeTaskStats,
  daysUntil,
  groupTasksByDate,
  matchesTaskFilter,
  priorityLabel,
  suggestionUrgency,
  TaskCard,
} from "./App";
import type { Task } from "@/types";

const api = vi.hoisted(() => ({
  createTaskFromSuggestion: vi.fn(),
  getRecordingQuota: vi.fn(),
  listProposedTasks: vi.fn(),
  listConfirmedTasks: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

const auth = vi.hoisted(() => ({
  applyWebSession: vi.fn(),
  getSession: vi.fn(),
  getValidAccessToken: vi.fn(),
  loginWithCredentials: vi.fn().mockResolvedValue({ success: true }),
  logout: vi.fn(),
}));

const storageMock = vi.hoisted(() => ({
  activeReminderBundleItem: { getValue: vi.fn(), watch: vi.fn(() => () => {}) },
  authSessionItem: { watch: vi.fn(() => () => {}) },
  autoOpenReminderPopupItem: { getValue: vi.fn().mockResolvedValue(false), setValue: vi.fn(), watch: vi.fn(() => () => {}) },
}));

// usePreferenceSync() (App.tsx) đọc + watch 4 item này lúc mount — cùng
// storage.defineItem thật (wxt/utils/storage) đụng thẳng vào chrome.storage,
// chrome mock trong file này (stubChromeForApp) không đủ field cho driver đó
// chạy được, nên mock hẳn 4 module này thay vì cố mô phỏng sâu hơn.
const preferenceMock = vi.hoisted(() => ({
  applyTheme: vi.fn(),
  initTheme: vi.fn().mockResolvedValue("light"),
  toggleTheme: vi.fn().mockResolvedValue("dark"),
  themeItem: { watch: vi.fn(() => () => {}), getValue: vi.fn().mockResolvedValue("light"), setValue: vi.fn() },
  applyPalette: vi.fn(),
  initPalette: vi.fn().mockResolvedValue("paper"),
  // Hằng số thật (không phải hàm) — SettingsView dùng trực tiếp để render 4
  // chấm chọn tông, phải khớp đúng giá trị thật ở lib/palette.ts.
  PALETTE_NAMES: ["paper", "jade", "plum", "quartz"],
  PALETTE_LABEL: { paper: "Paper", jade: "Ngọc bích", plum: "Mận", quartz: "Thạch anh" },
  paletteItem: {
    watch: vi.fn(() => () => {}),
    getValue: vi.fn().mockResolvedValue("paper"),
    setValue: vi.fn(),
  },
  applyTextSize: vi.fn(),
  initTextSize: vi.fn().mockResolvedValue("md"),
  textSizeItem: { watch: vi.fn(() => () => {}), getValue: vi.fn().mockResolvedValue("md"), setValue: vi.fn() },
  applyHighContrast: vi.fn(),
  initHighContrast: vi.fn().mockResolvedValue(false),
  highContrastItem: {
    watch: vi.fn(() => () => {}),
    getValue: vi.fn().mockResolvedValue(false),
    setValue: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/auth", () => auth);
vi.mock("@/lib/storage", () => storageMock);
vi.mock("@/lib/theme", () => preferenceMock);
vi.mock("@/lib/palette", () => preferenceMock);
vi.mock("@/lib/textSize", () => preferenceMock);
vi.mock("@/lib/highContrast", () => preferenceMock);

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 42,
    title: "Nộp bài tập",
    detail: "Hoàn thiện bản nộp.",
    dueAt: null,
    allDay: false,
    ambiguous: false,
    assignee: null,
    assigneeAmbiguous: false,
    status: "confirmed",
    startedAt: null,
    sourceCount: 1,
    signalStrength: 0.9,
    evidence: [],
    ...overrides,
  };
}

describe("TaskCard — danh sách task đã duyệt kèm mức ưu tiên", () => {
  afterEach(cleanup);

  it("hiện nhãn ưu tiên theo hạn: quá hạn > hôm nay > ngày mai > còn X ngày", () => {
    const overdue = makeTask({ dueAt: new Date(Date.now() - 86_400_000).toISOString() });
    const today = makeTask({ dueAt: new Date().toISOString() });
    const tomorrow = makeTask({ dueAt: new Date(Date.now() + 86_400_000).toISOString() });
    const later = makeTask({ dueAt: new Date(Date.now() + 4 * 86_400_000).toISOString() });
    const noDue = makeTask({ dueAt: null });

    expect(priorityLabel(overdue)).toBe("QUÁ HẠN");
    expect(priorityLabel(today)).toBe("HÔM NAY");
    expect(priorityLabel(tomorrow)).toBe("NGÀY MAI");
    expect(priorityLabel(later)).toBe("CÒN 4 NGÀY");
    expect(priorityLabel(noDue)).toBe("KHÔNG HẠN");
    expect(priorityLabel(makeTask({ ambiguous: true }))).toBe("CHƯA RÕ");
  });

  it("sắp theo độ gấp: quá hạn trước, việc không hạn xuống cuối", () => {
    const overdue = makeTask({ id: 1, dueAt: new Date(Date.now() - 86_400_000).toISOString() });
    const today = makeTask({ id: 2, dueAt: new Date().toISOString() });
    const noDue = makeTask({ id: 3, dueAt: null });
    const sorted = [noDue, today, overdue].sort(compareTaskPriority);
    expect(sorted.map((task) => task.id)).toEqual([1, 2, 3]);
  });

  it("daysUntil so theo ngày lịch, không tính giờ", () => {
    const lateNight = makeTask({ dueAt: new Date(new Date().setHours(23, 59, 0, 0)).toISOString() });
    expect(daysUntil(lateNight)).toBe(0);
  });

  it("card đã duyệt không còn nút xác nhận/bỏ qua", () => {
    render(<TaskCard task={makeTask()} />);
    expect(screen.getByText("Nộp bài tập")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Xác nhận" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Bỏ qua" })).toBeNull();
  });
});

describe("suggestionUrgency — badge khẩn cấp cho gợi ý chưa xác nhận (tab Lấy dữ liệu)", () => {
  it("còn ≤1 ngày (kể cả quá hạn/hôm nay) → Cảnh báo", () => {
    const overdue = { dueAt: new Date(Date.now() - 86_400_000).toISOString() };
    const today = { dueAt: new Date().toISOString() };
    const oneDayLeft = { dueAt: new Date(Date.now() + 86_400_000).toISOString() };
    expect(suggestionUrgency(overdue)?.label).toBe("Cảnh báo");
    expect(suggestionUrgency(today)?.label).toBe("Cảnh báo");
    expect(suggestionUrgency(oneDayLeft)?.label).toBe("Cảnh báo");
  });

  it("trong vòng 3 ngày (2-3 ngày) → Cần chú ý", () => {
    const twoDays = { dueAt: new Date(Date.now() + 2 * 86_400_000).toISOString() };
    const threeDays = { dueAt: new Date(Date.now() + 3 * 86_400_000).toISOString() };
    expect(suggestionUrgency(twoDays)?.label).toBe("Cần chú ý");
    expect(suggestionUrgency(threeDays)?.label).toBe("Cần chú ý");
  });

  it("chưa rõ hạn (dueAt null) → Cần xem", () => {
    expect(suggestionUrgency({ dueAt: null })?.label).toBe("Cần xem");
  });

  it("hơn 3 ngày → không hiện badge", () => {
    const farAway = { dueAt: new Date(Date.now() + 10 * 86_400_000).toISOString() };
    expect(suggestionUrgency(farAway)).toBeNull();
  });
});

describe("composeFinalDetail — gộp field mở rộng vào detail lúc lưu thật (Task DB không có cột riêng)", () => {
  function makeItem(overrides: Partial<Parameters<typeof composeFinalDetail>[0]> = {}) {
    return {
      detail: "Gửi báo cáo cho khách.",
      sourceUrl: "",
      sourceLabel: "",
      expectedOutput: "",
      constraint: "",
      executionSteps: "",
      executionTool: "",
      executionMethod: "",
      priority: "",
      assignee: "",
      stakeholders: "",
      deliverTo: "",
      ...overrides,
    };
  }

  it("không có field mở rộng nào thì giữ nguyên detail gốc", () => {
    expect(composeFinalDetail(makeItem())).toBe("Gửi báo cáo cho khách.");
  });

  it("gộp từng field có nội dung thành đoạn riêng, có nhãn", () => {
    const result = composeFinalDetail(
      makeItem({
        expectedOutput: "Slide tối đa 10 trang",
        constraint: "Không dùng logo cũ",
        executionSteps: "Thu thập số liệu\nVẽ biểu đồ",
        executionTool: "Google Slides",
        executionMethod: "Theo template quý trước",
        priority: "gấp lắm",
        assignee: "Phong",
        stakeholders: "chị Lan",
        deliverTo: "nhóm Kinh doanh",
      })
    );

    expect(result).toContain("Kết quả mong đợi: Slide tối đa 10 trang");
    expect(result).toContain("Ràng buộc: Không dùng logo cũ");
    expect(result).toContain("Các bước thực hiện:\nThu thập số liệu\nVẽ biểu đồ");
    expect(result).toContain("Công cụ: Google Slides");
    expect(result).toContain("Cách làm đề xuất: Theo template quý trước");
    expect(result).toContain("Độ ưu tiên: gấp lắm");
    expect(result).toContain("Người phụ trách: Phong");
    expect(result).toContain("Người liên quan: chị Lan");
    expect(result).toContain("Hoàn thành gửi cho: nhóm Kinh doanh");
  });

  it("field chỉ có khoảng trắng thì coi như rỗng, không thêm đoạn thừa", () => {
    const result = composeFinalDetail(makeItem({ constraint: "   " }));
    expect(result).toBe("Gửi báo cáo cho khách.");
  });

  it("có sourceLabel thì Nguồn hiện cả nhãn lẫn url, luôn ở cuối cùng", () => {
    const result = composeFinalDetail(
      makeItem({ sourceUrl: "https://chat.zalo.me", sourceLabel: "S25-64CNTT", constraint: "Không dùng logo cũ" })
    );

    expect(result).toBe(
      "Gửi báo cáo cho khách.\n\nRàng buộc: Không dùng logo cũ\n\nNguồn: S25-64CNTT (https://chat.zalo.me)"
    );
  });

  it("không có sourceLabel thì Nguồn chỉ hiện url", () => {
    const result = composeFinalDetail(makeItem({ sourceUrl: "https://example.com" }));
    expect(result).toBe("Gửi báo cáo cho khách.\n\nNguồn: https://example.com");
  });
});

describe("computeTaskStats — dải thống kê đầu tab Công việc", () => {
  it("đếm đúng quá hạn / trong 7 ngày tới / tổng, bỏ qua task chưa rõ hạn", () => {
    const tasks = [
      makeTask({ id: 1, dueAt: new Date(Date.now() - 86_400_000).toISOString() }), // quá hạn
      makeTask({ id: 2, dueAt: new Date().toISOString() }), // hôm nay -> trong tuần
      makeTask({ id: 3, dueAt: new Date(Date.now() + 6 * 86_400_000).toISOString() }), // còn 6 ngày -> trong tuần
      makeTask({ id: 4, dueAt: new Date(Date.now() + 10 * 86_400_000).toISOString() }), // ngoài 7 ngày
      makeTask({ id: 5, dueAt: null }), // không hạn -> không tính overdue/thisWeek
      makeTask({ id: 6, dueAt: new Date(Date.now() - 86_400_000).toISOString(), ambiguous: true }), // chưa rõ -> bỏ qua
    ];

    expect(computeTaskStats(tasks)).toEqual({ overdue: 1, thisWeek: 2, total: 6 });
  });

  it("danh sách rỗng thì mọi số liệu bằng 0", () => {
    expect(computeTaskStats([])).toEqual({ overdue: 0, thisWeek: 0, total: 0 });
  });
});

describe("matchesTaskFilter — lọc theo đúng 2 mốc dải thống kê", () => {
  const overdue = makeTask({ dueAt: new Date(Date.now() - 86_400_000).toISOString() });
  const thisWeek = makeTask({ dueAt: new Date().toISOString() });
  const later = makeTask({ dueAt: new Date(Date.now() + 10 * 86_400_000).toISOString() });
  const noDate = makeTask({ dueAt: null });
  const ambiguousDate = makeTask({ dueAt: new Date().toISOString(), ambiguous: true });

  it("'all' luôn khớp mọi task", () => {
    for (const task of [overdue, thisWeek, later, noDate, ambiguousDate]) {
      expect(matchesTaskFilter(task, "all")).toBe(true);
    }
  });

  it("'overdue' chỉ khớp task quá hạn thật (không tính task chưa rõ hạn)", () => {
    expect(matchesTaskFilter(overdue, "overdue")).toBe(true);
    expect(matchesTaskFilter(thisWeek, "overdue")).toBe(false);
    expect(matchesTaskFilter(ambiguousDate, "overdue")).toBe(false);
  });

  it("'thisWeek' khớp task trong 0-6 ngày tới, không khớp quá hạn/xa hơn", () => {
    expect(matchesTaskFilter(thisWeek, "thisWeek")).toBe(true);
    expect(matchesTaskFilter(overdue, "thisWeek")).toBe(false);
    expect(matchesTaskFilter(later, "thisWeek")).toBe(false);
  });

  it("'noDate' khớp task không có hạn hoặc hạn chưa rõ (ambiguous)", () => {
    expect(matchesTaskFilter(noDate, "noDate")).toBe(true);
    expect(matchesTaskFilter(ambiguousDate, "noDate")).toBe(true);
    expect(matchesTaskFilter(thisWeek, "noDate")).toBe(false);
  });
});

describe("groupTasksByDate — nhóm cho chế độ xem Theo ngày", () => {
  it("gom đúng nhãn Quá hạn/Hôm nay/Ngày mai, task chưa rõ hạn vào nhóm riêng", () => {
    const tasks = [
      makeTask({ id: 1, dueAt: new Date(Date.now() - 86_400_000).toISOString() }),
      makeTask({ id: 2, dueAt: new Date().toISOString() }),
      makeTask({ id: 3, dueAt: new Date(Date.now() + 86_400_000).toISOString() }),
      makeTask({ id: 4, dueAt: null }),
    ];

    const groups = groupTasksByDate(tasks);

    expect(groups.map((g) => g.label)).toEqual(["Quá hạn", "Hôm nay", "Ngày mai", "Không hạn"]);
    expect(groups.every((g) => g.tasks.length === 1)).toBe(true);
  });

  it("gom 2 task CÙNG nhãn liên tiếp vào một nhóm duy nhất", () => {
    const tasks = [
      makeTask({ id: 1, dueAt: new Date().toISOString() }),
      makeTask({ id: 2, dueAt: new Date(new Date().setHours(23, 0, 0, 0)).toISOString() }),
    ];

    const groups = groupTasksByDate(tasks);
    const [group] = groups;

    expect(groups).toHaveLength(1);
    expect(group?.label).toBe("Hôm nay");
    expect(group?.tasks.map((t) => t.id)).toEqual([1, 2]);
  });

  it("danh sách rỗng trả về mảng rỗng", () => {
    expect(groupTasksByDate([])).toEqual([]);
  });
});

/** Chrome API tối thiểu để mount toàn bộ App() ở nhánh "authed": readActiveTab
 * không chạm tới (tab mặc định là "tasks", ExtractDataView chưa mount), nhưng
 * TasksView/RecordingPanel vẫn tự chạy effect riêng ngay khi mount. */
function stubChromeForApp() {
  (globalThis as unknown as { chrome: unknown }).chrome = {
    tabs: {
      query: vi.fn(() => Promise.resolve([])), // không có tab web app nào đang mở
      create: vi.fn(),
    },
    scripting: { executeScript: vi.fn() },
    storage: {
      local: { get: vi.fn(() => Promise.resolve({})) },
      onChanged: { addListener: vi.fn(), removeListener: vi.fn() },
    },
    runtime: { openOptionsPage: vi.fn() },
  };
}

describe("TasksView — chỉ hiện task đã duyệt, việc chờ duyệt là banner đếm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    stubChromeForApp();
    api.listConfirmedTasks.mockResolvedValue([]);
    api.listProposedTasks.mockResolvedValue([]);
    api.getRecordingQuota.mockResolvedValue({ unlimited: true, remainingMs: null });
    storageMock.activeReminderBundleItem.getValue.mockResolvedValue(null);
    storageMock.activeReminderBundleItem.watch.mockReturnValue(() => {});
    storageMock.authSessionItem.watch.mockReturnValue(() => {});
  });

  afterEach(cleanup);

  it("chưa đăng nhập -> hiện màn hình khoá, không gọi API task", async () => {
    auth.getSession.mockResolvedValue(null);
    render(<App />);

    expect(await screen.findByText(/Đăng nhập mond/)).toBeTruthy();
    expect(api.listConfirmedTasks).not.toHaveBeenCalled();
    expect(api.listProposedTasks).not.toHaveBeenCalled();
  });

  it("đã đăng nhập -> tải task đã duyệt và số việc chờ duyệt", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    api.listConfirmedTasks.mockResolvedValue([makeTask()]);
    api.listProposedTasks.mockResolvedValue([makeTask({ id: 7 }), makeTask({ id: 8 })]);
    render(<App />);

    // Mặc định mở tab "tasks" -> TasksView mount ngay.
    expect(await screen.findByText("Nộp bài tập")).toBeTruthy();
    expect(await screen.findByText("2 việc đang chờ bạn duyệt")).toBeTruthy();
    expect(api.listConfirmedTasks).toHaveBeenCalled();
    expect(api.listProposedTasks).toHaveBeenCalled();
  });

  it("không có việc chờ duyệt thì không hiện banner", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    api.listConfirmedTasks.mockResolvedValue([makeTask()]);
    render(<App />);

    expect(await screen.findByText("Nộp bài tập")).toBeTruthy();
    expect(screen.queryByText(/đang chờ bạn duyệt/)).toBeNull();
  });

  it("tìm kiếm lọc đúng theo tiêu đề, không gọi lại API", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    api.listConfirmedTasks.mockResolvedValue([
      makeTask({ id: 1, title: "Nộp bài tập" }),
      makeTask({ id: 2, title: "Gửi báo cáo tuần" }),
    ]);
    render(<App />);
    await screen.findByText("Nộp bài tập");

    fireEvent.change(screen.getByLabelText("Tìm kiếm công việc"), { target: { value: "báo cáo" } });

    expect(screen.queryByText("Nộp bài tập")).toBeNull();
    expect(screen.getByText("Gửi báo cáo tuần")).toBeTruthy();
    expect(api.listConfirmedTasks).toHaveBeenCalledTimes(1);
  });

  it("thêm việc thủ công gọi createTaskFromSuggestion rồi tải lại danh sách", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    api.listConfirmedTasks.mockResolvedValueOnce([makeTask({ id: 1, title: "Nộp bài tập" })]);
    api.listConfirmedTasks.mockResolvedValueOnce([
      makeTask({ id: 1, title: "Nộp bài tập" }),
      makeTask({ id: 2, title: "Việc mới thêm tay" }),
    ]);
    api.createTaskFromSuggestion.mockResolvedValue(makeTask({ id: 2, title: "Việc mới thêm tay" }));
    render(<App />);
    await screen.findByText("Nộp bài tập");

    fireEvent.click(screen.getByRole("button", { name: "Thêm việc thủ công" }));
    fireEvent.change(screen.getByLabelText("Tiêu đề công việc mới"), { target: { value: "Việc mới thêm tay" } });
    fireEvent.click(screen.getByRole("button", { name: "Thêm việc" }));

    await waitFor(() => expect(api.createTaskFromSuggestion).toHaveBeenCalledWith("Việc mới thêm tay", "", null));
    expect(await screen.findByText("Việc mới thêm tay")).toBeTruthy();
    expect(api.listConfirmedTasks).toHaveBeenCalledTimes(2);
  });

  it("quay lại panel (visibilitychange) tải lại danh sách ngầm, không chớp màn 'Đang tải'", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    api.listConfirmedTasks.mockResolvedValueOnce([makeTask({ id: 1, title: "Việc cũ" })]);
    render(<App />);
    await screen.findByText("Việc cũ");

    // Bên web app vừa duyệt thêm một việc -> lần tải sau có thêm nó.
    api.listConfirmedTasks.mockResolvedValueOnce([
      makeTask({ id: 1, title: "Việc cũ" }),
      makeTask({ id: 2, title: "Việc vừa duyệt bên web" }),
    ]);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    fireEvent(document, new Event("visibilitychange"));

    expect(await screen.findByText("Việc vừa duyệt bên web")).toBeTruthy();
    expect(screen.queryByText("Đang tải...")).toBeNull();
    expect(api.listConfirmedTasks).toHaveBeenCalledTimes(2);
  });

  it("làm mới ngầm lỗi mạng thì giữ nguyên danh sách đang hiện, không nhảy màn lỗi", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    api.listConfirmedTasks.mockResolvedValueOnce([makeTask({ id: 1, title: "Việc cũ" })]);
    render(<App />);
    await screen.findByText("Việc cũ");

    api.listConfirmedTasks.mockRejectedValueOnce(new Error("mạng lỗi"));
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    fireEvent(document, new Event("visibilitychange"));

    await waitFor(() => expect(api.listConfirmedTasks).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Việc cũ")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Thử lại" })).toBeNull();
  });
});

describe("App — chặn toàn bộ panel khi chưa đăng nhập web", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    stubChromeForApp();
    api.listConfirmedTasks.mockResolvedValue([]);
    api.listProposedTasks.mockResolvedValue([]);
    api.getRecordingQuota.mockResolvedValue({ unlimited: true, remainingMs: null });
    storageMock.activeReminderBundleItem.getValue.mockResolvedValue(null);
    storageMock.activeReminderBundleItem.watch.mockReturnValue(() => {});
    storageMock.authSessionItem.watch.mockReturnValue(() => {});
    storageMock.autoOpenReminderPopupItem.getValue.mockResolvedValue(false);
    storageMock.autoOpenReminderPopupItem.watch.mockReturnValue(() => {});
    // SettingsView (bấm icon Cài đặt) đọc trực tiếp các item này lúc mount.
    preferenceMock.initTheme.mockResolvedValue("light");
    preferenceMock.toggleTheme.mockResolvedValue("dark");
    preferenceMock.paletteItem.getValue.mockResolvedValue("paper");
    preferenceMock.textSizeItem.getValue.mockResolvedValue("md");
    preferenceMock.highContrastItem.getValue.mockResolvedValue(false);
  });

  afterEach(cleanup);

  it("hỗ trợ đăng nhập trực tiếp bằng email & mật khẩu ngay trong panel", async () => {
    auth.getSession.mockResolvedValue(null);
    render(<App />);

    const emailInput = await screen.findByPlaceholderText("name@example.com");
    const passwordInput = screen.getByPlaceholderText("••••••••");
    fireEvent.change(emailInput, { target: { value: "user@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập ngay" }));

    expect(auth.loginWithCredentials).toHaveBeenCalledWith("user@example.com", "password123");
  });

  it("bấm nút ở tab Web/Google mở tab mondaiy để đăng nhập", async () => {
    auth.getSession.mockResolvedValue(null);
    render(<App />);

    fireEvent.click(await screen.findByRole("tab", { name: "Web / Google" }));
    fireEvent.click(await screen.findByRole("button", { name: /Mở mondaiy để đăng nhập/ }));
    expect((globalThis as unknown as { chrome: { tabs: { create: ReturnType<typeof vi.fn> } } }).chrome.tabs.create).toHaveBeenCalledWith(
      expect.objectContaining({ url: expect.stringContaining("/tasks") })
    );
  });

  it("đã đăng nhập -> hiện tab nav bình thường, không hiện màn hình khoá", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    render(<App />);

    expect(await screen.findByRole("tablist")).toBeTruthy();
    expect(screen.queryByText(/Đăng nhập mond/)).toBeNull();
  });

  it("bấm icon Cài đặt hiện Cài đặt NGAY TRONG panel (không mở tab), Quay lại trở về tab cũ", async () => {
    auth.getSession.mockResolvedValue({ accessToken: "t", refreshToken: "r", expiresAt: Date.now() + 60_000 });
    render(<App />);
    await screen.findByRole("tablist");

    fireEvent.click(screen.getByRole("button", { name: "Cài đặt / đăng nhập" }));

    expect(await screen.findByRole("heading", { name: "Cài đặt" })).toBeTruthy();
    expect(screen.getByText("Hiển thị")).toBeTruthy();
    expect(screen.getByText("Chế độ tối")).toBeTruthy();
    // Không mở tab trình duyệt thật nào cho Cài đặt.
    expect((globalThis as unknown as { chrome: { tabs: { create: ReturnType<typeof vi.fn> } } }).chrome.tabs.create).not.toHaveBeenCalled();
    expect(screen.queryByRole("tablist")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Quay lại" }));

    expect(await screen.findByRole("tablist")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Cài đặt" })).toBeNull();
  });
});
