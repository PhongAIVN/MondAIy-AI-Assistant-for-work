// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtractDataView } from "./App";

const api = vi.hoisted(() => ({
  summarizePageExtraction: vi.fn(),
  createTaskFromSuggestion: vi.fn(),
  confirmTask: vi.fn().mockResolvedValue({ id: 1 }),
  ApiError: class ApiError extends Error {},
}));

const auth = vi.hoisted(() => ({
  applyWebSession: vi.fn(),
  getValidAccessToken: vi.fn(),
}));

// usePreferenceSync() (App.tsx) đọc + watch 4 item này lúc App() mount — dù
// ExtractDataView không tự mount App(), module App.tsx vẫn import các module
// này ở top-level nên phải mock để test không đụng storage.defineItem thật.
const preferenceMock = vi.hoisted(() => ({
  applyTheme: vi.fn(),
  initTheme: vi.fn().mockResolvedValue("light"),
  themeItem: { watch: vi.fn(() => () => {}) },
  applyPalette: vi.fn(),
  initPalette: vi.fn().mockResolvedValue("paper"),
  paletteItem: { watch: vi.fn(() => () => {}) },
  applyTextSize: vi.fn(),
  initTextSize: vi.fn().mockResolvedValue("md"),
  textSizeItem: { watch: vi.fn(() => () => {}) },
  applyHighContrast: vi.fn(),
  initHighContrast: vi.fn().mockResolvedValue(false),
  highContrastItem: { watch: vi.fn(() => () => {}) },
}));

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/auth", () => auth);
vi.mock("@/lib/storage", () => ({
  activeReminderBundleItem: { getValue: vi.fn(), watch: vi.fn() },
  pendingTaskCountItem: { getValue: vi.fn(), watch: vi.fn() },
}));
vi.mock("@/lib/theme", () => preferenceMock);
vi.mock("@/lib/palette", () => preferenceMock);
vi.mock("@/lib/textSize", () => preferenceMock);
vi.mock("@/lib/highContrast", () => preferenceMock);

const ACTIVE_TAB = { id: 7, title: "Trang cần lấy dữ liệu", url: "https://example.com/page" };

/** Suggestion mock tối thiểu — field mở rộng (expectedOutput...deliverTo) mặc
 * định rỗng/[] giống response thật khi nguồn không nêu (xem
 * PageExtractionSuggestion ở client/extension/types/index.ts). */
function makeSuggestionResponse(overrides: {
  title: string;
  detail: string;
  dueAt: string | null;
}): {
  title: string;
  detail: string;
  dueAt: string | null;
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
} {
  return {
    ...overrides,
    sourceUrl: "https://example.com/page",
    sourceLabel: "",
    expectedOutput: "",
    constraint: "",
    executionSteps: [],
    executionTool: "",
    executionMethod: "",
    priority: "",
    assignee: "",
    stakeholders: "",
    deliverTo: "",
  };
}

/** Chrome API tối thiểu ExtractDataView chạm tới: readActiveTab() (query
 * active tab), listener đổi tab, và executeScript() để đọc nội dung trang.
 * probeWebAppSession() (reconcileWebSession/ensureLoggedIn) cũng gọi
 * tabs.query({url}) — trả mảng rỗng ở đây để mô phỏng "chưa mở tab web app",
 * ensureLoggedIn khi đó chỉ còn phụ thuộc auth.getValidAccessToken(). */
function stubChrome(overrides: { executeScript?: () => unknown } = {}) {
  const executeScript =
    overrides.executeScript ??
    (() => Promise.resolve([{ result: { title: "T", url: "https://x", text: "", sourceContext: "" } }]));

  (globalThis as unknown as { chrome: unknown }).chrome = {
    tabs: {
      query: vi.fn((info: { url?: string; active?: boolean }) =>
        info.url ? Promise.resolve([]) : Promise.resolve([ACTIVE_TAB])
      ),
      onActivated: { addListener: vi.fn(), removeListener: vi.fn() },
      onUpdated: { addListener: vi.fn(), removeListener: vi.fn() },
    },
    scripting: {
      executeScript: vi.fn(executeScript),
    },
  };
}

/** Flow 2 bước: "Lấy dữ liệu từ tab này" chỉ extract raw (không gọi backend),
 * "Extract công việc" mới gọi summarizePageExtraction — bấm hộ cả 2 bước để
 * các test chỉ quan tâm bước lưu/lỗi không phải lặp lại thao tác này. */
async function extractThenClassify() {
  fireEvent.click(await screen.findByRole("button", { name: /Lấy dữ liệu từ tab này/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Extract công việc" }));
}

describe("ExtractDataView", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    stubChrome();
    auth.getValidAccessToken.mockResolvedValue("token-123");
  });

  afterEach(cleanup);

  it("hiện tab đang active sau khi mount", async () => {
    render(<ExtractDataView />);
    expect(await screen.findByText("Trang cần lấy dữ liệu")).toBeTruthy();
  });

  it("lấy dữ liệu xong hiện list nội dung thô trước — chưa gọi backend phân loại", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          {
            result: {
              title: "Trang cần lấy dữ liệu",
              url: "https://example.com/page",
              text: "Gửi báo cáo trước 20/8\nChào buổi sáng",
              sourceContext: "",
            },
          },
        ]),
    });

    render(<ExtractDataView />);
    fireEvent.click(await screen.findByRole("button", { name: /Lấy dữ liệu từ tab này/ }));

    expect(await screen.findByText("Gửi báo cáo trước 20/8")).toBeTruthy();
    expect(screen.getByText("Chào buổi sáng")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Extract công việc" })).toBeTruthy();
    expect(api.summarizePageExtraction).not.toHaveBeenCalled();
  });

  it("bấm Extract công việc gọi backend rồi hiện list suggestion để confirm từng cái", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          {
            result: {
              title: "T",
              url: "https://example.com/page",
              text: "Gửi báo cáo trước 20/8\nĐặt lịch họp",
              sourceContext: "S25-64CNTT",
            },
          },
        ]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({
        title: "Gửi báo cáo trước 20/8",
        detail: "Gửi báo cáo trước 20/8 cho khách hàng.",
        dueAt: null,
      }),
      makeSuggestionResponse({
        title: "Đặt lịch họp",
        detail: "Đặt lịch họp với khách.",
        dueAt: null,
      }),
    ]);

    render(<ExtractDataView />);
    await extractThenClassify();

    await waitFor(() =>
      expect(api.summarizePageExtraction).toHaveBeenCalledWith(
        "https://example.com/page",
        "T",
        "Gửi báo cáo trước 20/8\nĐặt lịch họp",
        "S25-64CNTT"
      )
    );

    expect(await screen.findByText("2 việc được nhận diện")).toBeTruthy();
    expect(screen.getByDisplayValue("Gửi báo cáo trước 20/8")).toBeTruthy();
    expect(screen.getByDisplayValue("Đặt lịch họp")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Lưu" })).toHaveLength(2);
  });

  it("báo lỗi thân thiện khi trang bị Chrome khoá (chrome://, Web Store...)", async () => {
    stubChrome({ executeScript: () => Promise.reject(new Error("Cannot access a chrome:// URL")) });

    render(<ExtractDataView />);
    fireEvent.click(await screen.findByRole("button", { name: /Lấy dữ liệu từ tab này/ }));

    expect(await screen.findByText(/Chrome không cho phép đọc nội dung trang này/)).toBeTruthy();
    expect(api.summarizePageExtraction).not.toHaveBeenCalled();
  });

  it("báo chưa đăng nhập thay vì lỗi thô khi bấm Extract công việc lúc chưa có token", async () => {
    auth.getValidAccessToken.mockResolvedValue(null);
    stubChrome({
      executeScript: () => Promise.resolve([{ result: { title: "T", url: "https://example.com/page", text: "abc" } }]),
    });

    render(<ExtractDataView />);
    await extractThenClassify();

    expect(await screen.findByText(/Chưa đăng nhập mondaiy/)).toBeTruthy();
    expect(api.summarizePageExtraction).not.toHaveBeenCalled();
  });

  it("lưu một suggestion thành công — suggestion còn lại không bị đụng tới", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          { result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8\nĐặt lịch họp" } },
        ]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({
        title: "Gửi báo cáo trước 20/8",
        detail: "Gửi báo cáo trước 20/8 cho khách hàng.",
        dueAt: null,
      }),
      makeSuggestionResponse({
        title: "Đặt lịch họp",
        detail: "Đặt lịch họp với khách.",
        dueAt: null,
      }),
    ]);
    api.createTaskFromSuggestion.mockResolvedValue({ id: 1 });

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByText("2 việc được nhận diện");

    const [firstSaveButton] = screen.getAllByRole("button", { name: "Lưu" });
    fireEvent.click(firstSaveButton as HTMLElement);

    await waitFor(() =>
      expect(api.createTaskFromSuggestion).toHaveBeenCalledWith(
        "Gửi báo cáo trước 20/8",
        "Gửi báo cáo trước 20/8 cho khách hàng.",
        null,
        expect.objectContaining({
          source: "https://example.com/page",
        })
      )
    );
    expect(await screen.findByText("Đã lưu vào công việc")).toBeTruthy();
    expect(screen.getByDisplayValue("Đặt lịch họp")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Lưu" })).toHaveLength(1);
  });

  it("báo lỗi riêng trên đúng suggestion khi lưu thất bại, không mất input", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([{ result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8" } }]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({
        title: "Gửi báo cáo trước 20/8",
        detail: "Gửi báo cáo trước 20/8 cho khách hàng.",
        dueAt: null,
      }),
    ]);
    api.createTaskFromSuggestion.mockRejectedValue(new api.ApiError("Mất mạng"));

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByDisplayValue("Gửi báo cáo trước 20/8");

    fireEvent.click(screen.getByRole("button", { name: "Lưu" }));

    expect(await screen.findByText("Mất mạng")).toBeTruthy();
    expect(screen.getByDisplayValue("Gửi báo cáo trước 20/8")).toBeTruthy();
  });

  it("bỏ qua một suggestion thì biến mất khỏi list, không gọi API", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          { result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8\nĐặt lịch họp" } },
        ]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({ title: "Gửi báo cáo trước 20/8", detail: "...", dueAt: null }),
      makeSuggestionResponse({ title: "Đặt lịch họp", detail: "...", dueAt: null }),
    ]);

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByText("2 việc được nhận diện");

    const [firstDismissButton] = screen.getAllByRole("button", { name: /Bỏ qua/ });
    fireEvent.click(firstDismissButton as HTMLElement);

    expect(await screen.findByText("1 việc được nhận diện")).toBeTruthy();
    expect(screen.queryByDisplayValue("Gửi báo cáo trước 20/8")).toBeNull();
    expect(screen.getByDisplayValue("Đặt lịch họp")).toBeTruthy();
    expect(api.createTaskFromSuggestion).not.toHaveBeenCalled();
  });

  it("suggestion có field mở rộng hiện khối 'Chi tiết thêm', lưu thì gộp vào detail", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          { result: { title: "T", url: "https://example.com/page", text: "Phong làm slide báo cáo quý giúp anh" } },
        ]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      {
        ...makeSuggestionResponse({
          title: "Làm slide báo cáo quý",
          detail: "Làm slide báo cáo quý cho phòng kinh doanh.",
          dueAt: null,
        }),
        expectedOutput: "Slide tối đa 10 trang",
        constraint: "Không dùng logo cũ",
        executionSteps: ["Thu thập số liệu quý 3", "Vẽ biểu đồ"],
        executionTool: "Google Slides",
        executionMethod: "Theo template quý trước",
        priority: "gấp lắm",
        assignee: "Phong",
        stakeholders: "chị Lan",
        deliverTo: "nhóm Kinh doanh trên Zalo",
      },
    ]);
    api.createTaskFromSuggestion.mockResolvedValue({ id: 1 });

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByText("1 việc được nhận diện");

    expect(screen.getByText("Chi tiết thêm")).toBeTruthy();
    expect(screen.getByDisplayValue("Slide tối đa 10 trang")).toBeTruthy();
    expect(screen.getByDisplayValue("Không dùng logo cũ")).toBeTruthy();
    // getByDisplayValue collapse whitespace (kể cả \n) khi so khớp — dùng
    // getByLabelText + đọc .value trực tiếp để giữ đúng ranh giới dòng.
    const stepsField = screen.getByLabelText("Các bước thực hiện") as HTMLTextAreaElement;
    expect(stepsField.value).toBe("Thu thập số liệu quý 3\nVẽ biểu đồ");
    expect(screen.getByDisplayValue("Google Slides")).toBeTruthy();
    expect(screen.getByDisplayValue("gấp lắm")).toBeTruthy();
    expect(screen.getByDisplayValue("Phong")).toBeTruthy();
    expect(screen.getByDisplayValue("chị Lan")).toBeTruthy();
    expect(screen.getByDisplayValue("nhóm Kinh doanh trên Zalo")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Lưu" }));

    await waitFor(() => expect(api.createTaskFromSuggestion).toHaveBeenCalled());
    const [title, cleanDetail, dueAt, extras] = api.createTaskFromSuggestion.mock.calls[0] as [string, string, string | null, Record<string, any>];
    expect(cleanDetail).toBe("Làm slide báo cáo quý cho phòng kinh doanh.");
    expect(extras.expectedOutput).toBe("Slide tối đa 10 trang");
    expect(extras.constraints).toBe("Không dùng logo cũ");
    expect(extras.executionTool).toBe("Google Slides");
    expect(extras.deliverTo).toBe("nhóm Kinh doanh trên Zalo");
  });

  it("suggestion không có field mở rộng thì KHÔNG hiện khối 'Chi tiết thêm'", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([{ result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8" } }]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({ title: "Gửi báo cáo trước 20/8", detail: "...", dueAt: null }),
    ]);

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByDisplayValue("Gửi báo cáo trước 20/8");

    expect(screen.queryByText("Chi tiết thêm")).toBeNull();
  });

  it("chọn nhiều gợi ý hiện thanh nổi, Bỏ qua tất cả xoá đúng các mục đã chọn", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          { result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8\nĐặt lịch họp" } },
        ]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({ title: "Gửi báo cáo trước 20/8", detail: "...", dueAt: null }),
      makeSuggestionResponse({ title: "Đặt lịch họp", detail: "...", dueAt: null }),
    ]);

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByText("2 việc được nhận diện");

    expect(screen.queryByText(/Đã chọn/)).toBeNull();

    const [firstCheckbox] = screen.getAllByRole("checkbox", { name: "Chọn gợi ý này" });
    fireEvent.click(firstCheckbox as HTMLElement);

    expect(await screen.findByText("Đã chọn 1 mục")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Bỏ qua tất cả" }));

    expect(screen.queryByDisplayValue("Gửi báo cáo trước 20/8")).toBeNull();
    expect(screen.getByDisplayValue("Đặt lịch họp")).toBeTruthy();
    expect(screen.queryByText(/Đã chọn/)).toBeNull();
    expect(api.createTaskFromSuggestion).not.toHaveBeenCalled();
  });

  it("chọn nhiều rồi Lưu tất cả gọi createTaskFromSuggestion cho đúng từng mục đã chọn", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([
          { result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8\nĐặt lịch họp" } },
        ]),
    });
    api.summarizePageExtraction.mockResolvedValue([
      makeSuggestionResponse({ title: "Gửi báo cáo trước 20/8", detail: "Nội dung A", dueAt: null }),
      makeSuggestionResponse({ title: "Đặt lịch họp", detail: "Nội dung B", dueAt: null }),
    ]);
    api.createTaskFromSuggestion.mockResolvedValue({ id: 1 });

    render(<ExtractDataView />);
    await extractThenClassify();
    await screen.findByText("2 việc được nhận diện");

    for (const checkbox of screen.getAllByRole("checkbox", { name: "Chọn gợi ý này" })) {
      fireEvent.click(checkbox);
    }
    expect(await screen.findByText("Đã chọn 2 mục")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Lưu tất cả" }));

    await waitFor(() => expect(api.createTaskFromSuggestion).toHaveBeenCalledTimes(2));
    expect(api.createTaskFromSuggestion).toHaveBeenCalledWith(
      "Gửi báo cáo trước 20/8",
      "Nội dung A",
      null,
      expect.anything()
    );
    expect(api.createTaskFromSuggestion).toHaveBeenCalledWith(
      "Đặt lịch họp",
      "Nội dung B",
      null,
      expect.anything()
    );
  });

  it("Huỷ ở bước xem list thô quay lại trạng thái ban đầu", async () => {
    stubChrome({
      executeScript: () =>
        Promise.resolve([{ result: { title: "T", url: "https://example.com/page", text: "Gửi báo cáo trước 20/8" } }]),
    });

    render(<ExtractDataView />);
    fireEvent.click(await screen.findByRole("button", { name: /Lấy dữ liệu từ tab này/ }));
    await screen.findByText("Gửi báo cáo trước 20/8");

    fireEvent.click(screen.getByRole("button", { name: "Huỷ" }));

    expect(await screen.findByRole("button", { name: "Lấy dữ liệu từ tab này" })).toBeTruthy();
    expect(screen.queryByText("Gửi báo cáo trước 20/8")).toBeNull();
  });
});
