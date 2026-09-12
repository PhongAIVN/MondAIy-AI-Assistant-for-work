// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

// App.tsx định nghĩa storage item ở module scope (import time) — mock để
// import module không đụng chrome.storage thật, giống ExtractDataView.test.tsx.
vi.mock("@/lib/storage", () => {
  const item = () => ({ getValue: vi.fn(), setValue: vi.fn(), watch: vi.fn() });
  return {
    pendingTaskCountItem: item(),
    notificationBundlesItem: item(),
    autoOpenReminderPopupItem: item(),
    activeReminderBundleItem: item(),
    authSessionItem: item(),
  };
});

// Cùng lý do — usePreferenceSync() (App.tsx) đọc 4 item này ở module scope.
vi.mock("@/lib/theme", () => ({ applyTheme: vi.fn(), initTheme: vi.fn(), themeItem: { watch: vi.fn(() => () => {}) } }));
vi.mock("@/lib/palette", () => ({
  applyPalette: vi.fn(),
  initPalette: vi.fn(),
  paletteItem: { watch: vi.fn(() => () => {}) },
}));
vi.mock("@/lib/textSize", () => ({
  applyTextSize: vi.fn(),
  initTextSize: vi.fn(),
  textSizeItem: { watch: vi.fn(() => () => {}) },
}));
vi.mock("@/lib/highContrast", () => ({
  applyHighContrast: vi.fn(),
  initHighContrast: vi.fn(),
  highContrastItem: { watch: vi.fn(() => () => {}) },
}));

import { extractPageContentInPage } from "./App";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("extractPageContentInPage", () => {
  it("tự chứa hoàn toàn — chạy được sau khi tái tạo từ toString(), không còn closure module gốc", () => {
    // chrome.scripting.executeScript({ func }) serialize hàm bằng
    // Function.prototype.toString() rồi re-eval RIÊNG LẺ trong trang đích —
    // mọi tham chiếu ra hằng số/hàm phụ ở scope module ngoài sẽ vỡ với
    // ReferenceError ở đó (không phát hiện được nếu chỉ gọi hàm trực tiếp
    // như các test khác — bug thật đã từng lọt qua kiểu đó). `new Function`
    // tái tạo đúng thứ scope đó: chỉ có global, không có closure cũ.
    document.body.innerHTML = "<div>Gửi báo cáo trước 20/8</div>";

    // eslint-disable-next-line no-new-func -- cố ý, mô phỏng cơ chế executeScript
    const reconstructed = new Function(
      `return (${extractPageContentInPage.toString()})`
    )() as typeof extractPageContentInPage;

    const result = reconstructed();

    expect(result.text).not.toMatch(/^\[Lỗi trích xuất/);
    expect(result.text).toContain("Gửi báo cáo trước 20/8");
  });


  it("ưu tiên nội dung trong landmark <main> khi trang có khai báo, bỏ qua sidebar cạnh nó", () => {
    document.body.innerHTML = `
      <aside class="sidebar">Trò chuyện A\nTrò chuyện B\nTrò chuyện C</aside>
      <main>Gửi báo cáo cho khách trước ngày 20/8, nhớ đính kèm file hợp đồng bản mới nhất.</main>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Gửi báo cáo cho khách trước ngày 20/8");
    expect(text).not.toContain("Trò chuyện A");
  });

  it("loại class BEM double-underscore (vd tds-global-search__footer-content) — case thật gặp ở Zalo web", () => {
    // "_" là word character trong regex, "\b" không tạo boundary quanh nó —
    // test thẳng \bfooter\b trên "search__footer-content" sẽ KHÔNG khớp nếu
    // không chuẩn hoá "_" -> "-" trước (bug thật, đã sửa trong isNodeNoisy).
    document.body.innerHTML = `
      <div class="tds-global-search__footer-content">Sử dụng ứng dụng Zalo PC để tìm tin nhắn trước ngày 08/08/2026</div>
      <div>Gửi báo cáo cho khách trước ngày 20/8, nhớ đính kèm file hợp đồng bản mới nhất.</div>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Gửi báo cáo cho khách trước ngày 20/8");
    expect(text).not.toContain("Sử dụng ứng dụng Zalo PC");
  });

  it("loại class noise NGAY CẢ khi lồng bên trong <main> đáng tin", () => {
    document.body.innerHTML = `
      <main>
        <div class="promo-banner">Tải ngay ứng dụng để trải nghiệm đầy đủ</div>
        <div>Gửi báo cáo cho khách trước ngày 20/8, nhớ đính kèm file hợp đồng bản mới nhất.</div>
      </main>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Gửi báo cáo cho khách trước ngày 20/8");
    expect(text).not.toContain("Tải ngay ứng dụng");
  });

  it("không có landmark ngữ nghĩa: loại text trong nav/header/footer, giữ nội dung chính", () => {
    document.body.innerHTML = `
      <nav>Trang chủ Giới thiệu Liên hệ</nav>
      <header>Tên trang web</header>
      <div>Nội dung chính của trang cần được giữ lại nguyên vẹn.</div>
      <footer>Bản quyền 2026</footer>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Nội dung chính của trang cần được giữ lại nguyên vẹn.");
    expect(text).not.toContain("Trang chủ");
    expect(text).not.toContain("Tên trang web");
    expect(text).not.toContain("Bản quyền");
  });

  it("SPA không dùng landmark ngữ nghĩa (kiểu Zalo web): loại theo class/id gợi ý sidebar/danh sách chat", () => {
    document.body.innerHTML = `
      <div class="sidebar-list">
        <div>Trò chuyện với Minh</div>
        <div>Nhóm Việc làm part time</div>
      </div>
      <div class="chat-pane">
        <div>Gửi báo cáo trước 20/8 nhé</div>
      </div>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Gửi báo cáo trước 20/8 nhé");
    expect(text).not.toContain("Trò chuyện với Minh");
    expect(text).not.toContain("Việc làm part time");
  });

  it("bỏ qua phần tử bị ẩn (display:none)", () => {
    document.body.innerHTML = `
      <div style="display:none">Nội dung ẩn không nên xuất hiện</div>
      <div>Nội dung hiển thị bình thường</div>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Nội dung hiển thị bình thường");
    expect(text).not.toContain("Nội dung ẩn không nên xuất hiện");
  });

  it("cắt ở 20.000 ký tự", () => {
    document.body.innerHTML = `<div>${"a".repeat(25_000)}</div>`;

    const { text } = extractPageContentInPage();

    expect(text.length).toBe(20_000);
  });

  it("loại <nav> lồng bên trong <main> — structural noise áp cả khi đang tin scanRoot", () => {
    document.body.innerHTML = `
      <main>
        <nav>Mục lục Giới thiệu Liên hệ</nav>
        <div>Gửi báo cáo cho khách trước ngày 20/8, nhớ đính kèm file hợp đồng bản mới nhất.</div>
      </main>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Gửi báo cáo cho khách trước ngày 20/8");
    expect(text).not.toContain("Mục lục");
  });

  it("fallback về innerText thô khi bộ lọc lỡ khớp nhầm gần hết nội dung thật", () => {
    document.body.innerHTML = `
      <div class="app-nav-wrapper">
        Toàn bộ nội dung thật của trang lại nằm trong một wrapper lỡ đặt tên
        chứa chữ nav, khiến bộ lọc noise-keyword loại nhầm gần hết.
      </div>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Toàn bộ nội dung thật của trang");
  });

  it("bắt được class noise ở tổ tiên sâu (>12 cấp, SPA nhiều wrapper div)", () => {
    const wrap = (n: number, inner: string): string =>
      n <= 0 ? inner : `<div class="layer-${n}">${wrap(n - 1, inner)}</div>`;

    document.body.innerHTML = `
      <div class="sidebar-list">${wrap(15, "<div>Trò chuyện với Minh</div>")}</div>
      <div>${wrap(15, "<div>Gửi báo cáo trước 20/8 nhé</div>")}</div>
    `;

    const { text } = extractPageContentInPage();

    expect(text).toContain("Gửi báo cáo trước 20/8 nhé");
    expect(text).not.toContain("Trò chuyện với Minh");
  });

  it("loại dòng emoticon/reaction thuần dưới 2 chữ cái thật (case thật gặp ở Zalo web)", () => {
    document.body.innerHTML = `
      <div>:o</div>
      <div>:-((</div>
      <div>:-h</div>
      <div>&gt;:&gt;</div>
      <div>Duy Hứa nhớ gửi file báo cáo trước 5h chiều mai nhé</div>
    `;

    const { text } = extractPageContentInPage();

    expect(text).not.toContain(":o");
    expect(text).not.toContain(":-((");
    expect(text).not.toContain(":-h");
    expect(text).not.toContain(">:>");
    expect(text).toContain("Duy Hứa nhớ gửi file báo cáo trước 5h chiều mai nhé");
  });

  describe("sourceContext — nhãn nguồn cụ thể hơn url cho SPA route tĩnh (vd Zalo web)", () => {
    it("lấy heading ngữ nghĩa gần nhất (h1/h2/role=heading) làm sourceContext", () => {
      document.title = "Zalo";
      document.body.innerHTML = `
        <div class="sidebar-list"><div>Trò chuyện với Minh</div></div>
        <header><h2>S25-64CNTT</h2></header>
        <div>Gửi báo cáo trước 20/8 nhé</div>
      `;

      const { sourceContext } = extractPageContentInPage();

      expect(sourceContext).toBe("S25-64CNTT");
    });

    it("không có heading nào thì trả rỗng, không đoán mù", () => {
      document.title = "Trang không có heading";
      document.body.innerHTML = `<div>Gửi báo cáo trước 20/8, đính kèm file hợp đồng bản mới nhất.</div>`;

      const { sourceContext } = extractPageContentInPage();

      expect(sourceContext).toBe("");
    });

    it("bỏ qua heading trùng hệt document.title (không thêm tín hiệu mới)", () => {
      document.title = "Trang chủ mondaiy";
      document.body.innerHTML = `<h1>Trang chủ mondaiy</h1><div>Gửi báo cáo trước 20/8 nhé bạn ơi.</div>`;

      const { sourceContext } = extractPageContentInPage();

      expect(sourceContext).toBe("");
    });

    it("bỏ qua heading bị ẩn (display:none), lấy heading hiển thị kế tiếp", () => {
      document.title = "Zalo";
      document.body.innerHTML = `
        <h2 style="display:none">Nhóm đã ẩn</h2>
        <h2>Khởi Nghiệp Real</h2>
        <div>Gửi báo cáo trước 20/8 nhé</div>
      `;

      const { sourceContext } = extractPageContentInPage();

      expect(sourceContext).toBe("Khởi Nghiệp Real");
    });
  });
});
