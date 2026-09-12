import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Chỉ chạy unit test cho phần logic thuần (lib/), không đụng entrypoint vì
// những file đó cần API của Chrome. Alias "@" phải khai lại vì vitest không đọc
// paths trong tsconfig của WXT.
export default defineConfig({
  // Vite mặc định chỉ expose biến môi trường tiền tố VITE_ ra import.meta.env
  // — WXT dùng tiền tố WXT_ (xem .env.example), không khai lại ở đây thì mọi
  // module đọc import.meta.env.WXT_* (vd App.tsx: WEB_APP_URL) nhận undefined
  // trong test dù .env đã set đúng, chỉ lộ ra khi có test thật sự chạm code
  // path dùng biến đó (không throw ngay lúc import).
  envPrefix: "WXT_",
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    // Mặc định cho test, để suite chạy được trên clean checkout và trong
    // worktree — hai nơi không có `.env` (file đó bị gitignore).
    //
    // Thiếu chúng thì 5 file test đỏ với TypeError khó đọc ("Cannot read
    // properties of undefined") thay vì một thông báo nói rõ thiếu cấu hình.
    // Giá trị thật từ `.env` vẫn thắng vì Vite nạp .env sau block này.
    env: {
      WXT_API_BASE_URL: "http://localhost:8000",
      WXT_WEB_APP_URL: "http://localhost:5173",
    },
    include: ["lib/**/*.test.ts", "components/**/*.test.tsx", "entrypoints/**/*.test.{ts,tsx}"],
  },
});
