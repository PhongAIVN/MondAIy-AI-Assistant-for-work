// Cấu hình vỏ PWA, tách riêng khỏi vite.config.ts để test khẳng định được
// trực tiếp trên object thay vì phải chạy service worker thật.
//
// Ràng buộc cứng: service worker KHÔNG được chạm vào /api/*. Cache phản hồi
// API là rò dữ liệu giữa các tài khoản dùng chung một máy — người sau mở app
// sẽ đọc được briefing/task của người trước từ đệm. Vì vậy ở đây không khai
// báo runtimeCaching nào cả, và mọi điều hướng vào /api/* đều bị loại khỏi
// navigateFallback.

/** Tiền tố đường dẫn API — khai báo một chỗ để cả cấu hình lẫn test cùng dùng. */
export const API_PATH_PREFIX = '/api/';

/**
 * Chỉ precache tài sản ổn định, tuyệt đối không precache HTML/JS/CSS có hash.
 *
 * iOS có thể khôi phục một document cũ từ snapshot sau khi service worker mới
 * đã dọn bundle cũ. Nếu JS/CSS do Workbox quản lý, document đó sẽ trỏ vào file
 * không còn tồn tại và WebKit chỉ còn một nền trống. App này cần dữ liệu online
 * nên bundle luôn đi network an toàn hơn một "offline shell" không đồng bộ.
 */
export const SHELL_GLOB_PATTERNS = [
  '**/*.{ico,png,svg,webmanifest,woff,woff2,mp3}',
];

/**
 * Options truyền cho VitePWA.
 *
 * Cơ chế: plugin chèn manifest precache vào service worker viết tay ở src/sw.ts
 * để giữ được handler Web Push. Chỉ những file khớp SHELL_GLOB_PATTERNS được
 * chèn; navigation, HTML và bundle JS/CSS luôn đi network. `registerType:
 * 'autoUpdate'` kết hợp với skipWaiting + clients.claim trong service worker để
 * bản mới chiếm quyền ngay mà không cần dựng thêm UI cập nhật.
 *
 * `manifest: false` vì manifest được viết tay ở public/manifest.webmanifest và
 * khai báo tường minh trong index.html — giữ một nguồn chuẩn duy nhất, tránh
 * plugin chèn thêm thẻ link thứ hai trỏ vào manifest do nó tự sinh.
 */
export const pwaOptions = {
  strategies: 'injectManifest' as const,
  srcDir: 'src',
  filename: 'sw.ts',
  registerType: 'autoUpdate' as const,
  injectRegister: 'auto' as const,
  manifest: false as const,
  injectManifest: {
    globPatterns: SHELL_GLOB_PATTERNS,
  },
  devOptions: {
    // Không bật SW ở dev: service worker cache vỏ sẽ che mất HMR.
    enabled: false,
  },
};
