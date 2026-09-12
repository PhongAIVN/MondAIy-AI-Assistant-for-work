// Client đăng ký nhận thông báo đẩy của trình duyệt (Web Push).
//
// Đây là kênh giao thứ ba, sau extension và Telegram. Nó cắm vào đúng pipe
// thông báo có sẵn ở backend, nên mọi loại đã có — task tới hạn, task mới,
// mâu thuẫn lịch, tổng hợp cuối ngày, lịch bị đổi — tự chảy ra đây mà không
// cần thêm gì. Kèm theo là toàn bộ luật chống bão thông báo: giờ yên lặng,
// trần mỗi giờ, gộp theo cửa sổ.
//
// Ranh giới của file này: nó CHỈ lo đăng ký và huỷ đăng ký. Việc hiển thị
// thông báo là của service worker, việc quyết định gửi gì là của backend.

import { apiRequest } from './apiClient';

export type PushPublicKey = {
  /** Rỗng nghĩa là máy chủ chưa cấu hình VAPID — coi như tính năng chưa bật. */
  publicKey: string;
  /**
   * Máy chủ có đang thật sự gửi Web Push hay không.
   *
   * Tách khỏi `publicKey` vì hai thứ này tắt độc lập: khoá VAPID có thể đã cấu
   * hình xong trong khi cờ WEB_PUSH_ENABLED còn tắt. Bỏ qua cờ này thì trình
   * duyệt đăng ký thành công, toggle sáng lên, mà không thông báo nào tới —
   * kiểu hỏng tệ nhất vì người dùng tin là mình đã bật rồi.
   */
  enabled: boolean;
};

export type PushSubscribeRequest = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
  userAgent?: string;
};

export const fetchPushPublicKey = (accessToken: string): Promise<PushPublicKey> =>
  apiRequest<PushPublicKey>('/api/v1/push/public-key', { accessToken });

export const subscribeToPush = (accessToken: string, body: PushSubscribeRequest): Promise<void> =>
  apiRequest<void>('/api/v1/push/subscribe', { method: 'POST', body, accessToken });

export const unsubscribeFromPush = (accessToken: string, endpoint: string): Promise<void> =>
  apiRequest<void>('/api/v1/push/subscribe', { method: 'DELETE', body: { endpoint }, accessToken });

/**
 * Đổi khoá VAPID dạng base64url sang Uint8Array cho `pushManager.subscribe`.
 *
 * Cơ chế: base64url thay `+/` bằng `-_` và bỏ dấu `=` đệm, trong khi `atob`
 * chỉ hiểu base64 chuẩn — nên phải đắp lại phần đệm rồi dịch ngược hai ký tự
 * đó. Thiếu bước này thì trình duyệt ném InvalidCharacterError với một thông
 * báo không gợi ý gì về nguyên nhân thật.
 */
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  // Cấp phát ArrayBuffer tường minh thay vì `new Uint8Array(length)`: từ TS 5.7
  // Uint8Array là generic trên ArrayBufferLike, mà `applicationServerKey` đòi
  // BufferSource — dạng mặc định không gán được và build sẽ gãy.
  const output = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

/** Trình duyệt này có đủ điều kiện kỹ thuật để nhận push hay không. */
export function pushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

/**
 * Trạng thái push hiện tại của máy này, đủ để giao diện nói đúng sự thật.
 *
 * Tách `supported` khỏi `permission` khỏi `subscribed` vì ba thứ này hỏng theo
 * ba cách khác nhau và cần ba câu trả lời khác nhau cho người dùng: máy không
 * hỗ trợ, người dùng đã từ chối quyền, hay đơn giản là chưa bật.
 */
export type PushStatus = {
  supported: boolean;
  permission: NotificationPermission | 'unsupported';
  subscribed: boolean;
};

export async function readPushStatus(): Promise<PushStatus> {
  if (!pushSupported()) {
    return { supported: false, permission: 'unsupported', subscribed: false };
  }
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = registration ? await registration.pushManager.getSubscription() : null;
  return {
    supported: true,
    permission: Notification.permission,
    subscribed: subscription !== null,
  };
}

/**
 * Bật thông báo đẩy trên máy này: xin quyền, đăng ký với trình duyệt, rồi báo
 * endpoint về máy chủ.
 *
 * Trả về false khi người dùng từ chối quyền hoặc máy chủ chưa cấu hình VAPID.
 * Không ném lỗi ở hai nhánh đó vì chúng là lựa chọn hợp lệ của người dùng và
 * của môi trường, không phải sự cố.
 */
export async function enablePush(accessToken: string): Promise<boolean> {
  if (!pushSupported()) return false;

  const { publicKey, enabled } = await fetchPushPublicKey(accessToken);
  if (!publicKey || !enabled) return false;

  // Xin quyền TRƯỚC khi đăng ký: gọi ngược lại thì Chrome vẫn chạy nhưng
  // Safari coi là đăng ký khi chưa có quyền và từ chối thẳng.
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return false;

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    // Web Push không cho đăng ký im lặng: mọi thông báo phải hiện ra cho người
    // dùng thấy. Đặt false là trình duyệt từ chối đăng ký.
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });

  const raw = subscription.toJSON();
  await subscribeToPush(accessToken, {
    endpoint: subscription.endpoint,
    keys: {
      p256dh: raw.keys?.p256dh ?? '',
      auth: raw.keys?.auth ?? '',
    },
    userAgent: navigator.userAgent,
  });
  return true;
}

/**
 * Tắt thông báo đẩy trên máy này.
 *
 * Huỷ ở trình duyệt trước rồi mới báo máy chủ, và báo máy chủ kể cả khi bước
 * huỷ phía trình duyệt thất bại — bỏ sót bước đó thì máy chủ còn giữ một
 * endpoint chết và cứ gửi vào đó cho tới khi bị 410.
 */
export async function disablePush(accessToken: string): Promise<void> {
  if (!pushSupported()) return;
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = registration ? await registration.pushManager.getSubscription() : null;
  if (!subscription) return;

  const endpoint = subscription.endpoint;
  try {
    await subscription.unsubscribe();
  } finally {
    await unsubscribeFromPush(accessToken, endpoint);
  }
}
