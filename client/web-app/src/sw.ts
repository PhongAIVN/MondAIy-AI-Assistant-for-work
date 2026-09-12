/// <reference lib="webworker" />

// Service worker của mondaiy.
//
// Trước file này, vỏ PWA dùng service worker do Workbox sinh sẵn — nó precache
// tốt nhưng không biết gì về sự kiện `push`. Backend đã gửi thông báo đi
// (src/services/web_push.py) mà trình duyệt lại không có ai lắng nghe, nên
// người dùng chỉ nhận được thông báo mặc định "trang này đã được cập nhật
// ngầm", bấm vào không mở gì. Nói cách khác cả một kênh giao coi như không có.
//
// Hai trách nhiệm, tách bạch:
//   1. Vỏ ứng dụng — chỉ precache tài nguyên tĩnh ổn định. Navigation, HTML,
//      bundle JS/CSS và /api/* luôn đi network. Cache API sai phạm vi là rò dữ
//      liệu; cache bundle cũ khiến iOS có thể khôi phục thành màn hình trắng.
//   2. Thông báo đẩy — hiện thông báo và mở đúng nguồn khi người dùng bấm.
//
// Mọi quyết định của phần 2 nằm ở src/lib/pushNotification.ts để test được;
// file này chỉ nối dây.

import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching';

import {
  buildNotificationOptions,
  parsePushPayload,
  planNotificationClick,
  resolveNotificationUrl,
} from './lib/pushNotification';

declare const self: ServiceWorkerGlobalScope & {
  // Danh sách file vỏ do vite-plugin-pwa chèn vào lúc build.
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Không dựng NavigationRoute hoặc runtime cache. Vercel chịu trách nhiệm SPA
// rewrite; mọi request ngoài precache đi thẳng ra mạng và không để lại phản hồi
// người dùng trong Cache Storage.

// Thay cho registerType 'autoUpdate' của bản sinh sẵn: bản mới chiếm quyền ngay
// thay vì đợi người dùng đóng hết tab. App này đọc dữ liệu tươi liên tục, để vỏ
// cũ chạy với hợp đồng API mới là nguồn lỗi rất khó truy.
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  const payload = parsePushPayload(event.data?.text() ?? null);
  // waitUntil là bắt buộc: không giữ sự kiện sống thì trình duyệt có thể tắt
  // service worker trước khi thông báo kịp hiện.
  event.waitUntil(self.registration.showNotification(payload.title, buildNotificationOptions(payload)));
});

self.addEventListener('notificationclick', (event) => {
  // Đóng trước khi làm việc khác: người dùng đã bấm rồi, để nó nằm lại trên màn
  // hình khiến họ tưởng cú bấm không ăn.
  event.notification.close();

  const data = event.notification.data as { url?: string | null } | null;
  const target = resolveNotificationUrl(data?.url ?? null, self.location.origin);

  event.waitUntil(
    (async () => {
      // includeUncontrolled: tab mở trước khi service worker này giành quyền
      // vẫn là tab Mondaiy của người dùng, bỏ qua nó là mở thừa một tab nữa.
      const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      const plan = planNotificationClick(
        target,
        clients.map((client) => client.url),
        self.location.origin,
      );

      if (plan.action === 'open') {
        await self.clients.openWindow(plan.url);
        return;
      }

      const client = clients[plan.clientIndex];
      await client.focus();
      if (plan.navigateTo) {
        // navigate() bị từ chối ở một số trình duyệt/ngữ cảnh; tab đã được kéo
        // lên rồi nên thất bại ở đây chỉ là không nhảy đúng trang, không đáng
        // để làm hỏng cả cú bấm.
        await client.navigate(plan.navigateTo).catch(() => undefined);
      }
    })(),
  );
});
