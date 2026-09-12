import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

import { buildIdPlugin, resolveBuildId } from './build-id.ts'
import { pwaOptions } from './pwa.config.ts'

// Gọi MỘT lần rồi dùng cho cả `define` lẫn `version.json`. Gọi hai lần sẽ cho
// hai giá trị khác nhau ở nhánh fallback theo thời gian, và app sẽ báo "có bản
// mới" ngay sau khi vừa tải bản mới.
const buildId = resolveBuildId()

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA(pwaOptions), buildIdPlugin(buildId)],
  define: {
    __BUILD_ID__: JSON.stringify(buildId),
  },
  // Vite 8 mặc định nhắm baseline mới (Safari 16.4+). PWA vẫn được dùng trên
  // một số iPhone cũ hơn; nếu giữ target mặc định WebKit dừng ngay khi parse
  // bundle, CSS đã tải nhưng React chưa mount nên người dùng chỉ thấy nền trống.
  build: {
    target: 'es2019',
  },
})
