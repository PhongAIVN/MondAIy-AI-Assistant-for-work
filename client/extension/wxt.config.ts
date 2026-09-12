import { defineConfig } from "wxt";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  manifest: () => {
    const apiBase = process.env.WXT_API_BASE_URL;
    const webAppUrl = process.env.WXT_WEB_APP_URL;
    if (!apiBase || !webAppUrl) {
      throw new Error(
        "WXT_API_BASE_URL/WXT_WEB_APP_URL chưa cấu hình. Tạo file .env từ .env.example trước khi build."
      );
    }

    return {
      name: "mondaiy",
      description: "Thông báo việc cần làm từ mondaiy ngay trên trình duyệt",
      // "scripting" + host_permissions: đọc trạng thái đăng nhập từ tab web app
      // (lib/webSession.ts) VÀ đọc nội dung trang ở tab "Lấy dữ liệu"
      // (entrypoints/sidepanel). Đã thử "activeTab" (không cần host_permissions
      // rộng) trước — nhưng activeTab chỉ chắc chắn còn hiệu lực cho tab active
      // tại đúng thời điểm invoke, và Side Panel cố tình sống xuyên suốt lúc đổi
      // tab (khác popup) nên activeTab hết hạn ngay khi đổi tab, kể cả bấm lại
      // icon toolbar (đã verify thực tế bị Chrome từ chối — khớp báo cáo lỗi đã
      // biết của Chromium về activeTab + Side Panel, xem README mục "Lấy dữ liệu").
      // "tabs": đọc tab.url/tab.title của tab đang active — activeTab cũ vẫn cấp
      // được cái này miễn phí, nhưng bỏ activeTab rồi thì cần permission riêng.
      // Logic "chỉ đọc tab đang ACTIVE, đọc lại ngay lúc bấm nút" nằm ở code
      // (entrypoints/sidepanel/App.tsx: readActiveTab), không phải ở permission
      // — <all_urls> chỉ cấp KHẢ NĂNG kỹ thuật, không tự ý đọc tab nào cả.
      // "tabCapture" + "offscreen": ghi âm cuộc họp. Service worker MV3 không
      // có DOM nên không chạy được MediaRecorder — phải mượn một offscreen
      // document, và tiếng của tab chỉ lấy được qua tabCapture.
      permissions: ["storage", "notifications", "alarms", "scripting", "tabs", "tabCapture", "offscreen"],
      host_permissions: ["<all_urls>"],
      action: {
        default_title: "mondaiy",
      },
    };
  },
  vite: () => ({
    plugins: [tailwindcss()],
    // MV3 options/offscreen pages run in an extension isolated world. Vite's
    // modulepreload tags point at chunks that Chrome resolves in a different
    // world, producing a noisy "cross-world extension resource mismatch" and
    // no measurable startup benefit for these small entrypoints. Let the
    // browser load the module graph from the entry script instead.
    build: {
      modulePreload: false,
    },
  }),
});
