// Phần "suy nghĩ" của service worker khi có thông báo đẩy tới.
//
// Tách khỏi src/sw.ts vì service worker chạy trong một global scope không có
// DOM, không dựng lên được trong test thường. Mọi quyết định thật — hiện tiêu
// đề gì, mở trang nào, focus tab đang mở hay mở tab mới — nằm ở đây dưới dạng
// hàm thuần, còn sw.ts chỉ nối chúng vào sự kiện của trình duyệt.
//
// Ràng buộc bao trùm cả file: KHÔNG BAO GIỜ được im lặng. Web Push đăng ký với
// `userVisibleOnly: true`, nghĩa là mỗi lần nhận đẩy mà không hiện gì thì trình
// duyệt tự hiện một thông báo vô nghĩa kiểu "trang này đã được cập nhật ngầm",
// và sau vài lần như thế Chrome thu hồi luôn quyền đẩy của tên miền. Vì vậy
// payload hỏng vẫn phải ra được một thông báo thật thà.

/** Đúng những gì src/services/web_push.py::WebPushPayload gửi sang. */
export type PushPayload = {
  title: string;
  body: string;
  tag: string;
  url: string | null;
};

/** Tiêu đề dùng khi payload không nói được nó là thông báo gì. */
export const DEFAULT_PUSH_TITLE = 'mondaiy';

/** Trang mở khi thông báo không kèm liên kết bằng chứng nào. */
export const FALLBACK_PUSH_PATH = '/tasks';

/**
 * Đổi phần dữ liệu thô của sự kiện push thành payload dùng được.
 *
 * Cơ chế: thử đọc JSON, lấy ra bốn trường đã thoả thuận với backend, và mọi
 * trường thiếu/sai kiểu đều rơi về một giá trị an toàn thay vì ném lỗi. Ném lỗi
 * ở đây đồng nghĩa không hiện gì — đúng tình huống bị trình duyệt phạt nói ở
 * đầu file — nên hàm này luôn trả về một payload hợp lệ.
 */
export function parsePushPayload(raw: string | null | undefined): PushPayload {
  const fallback: PushPayload = { title: DEFAULT_PUSH_TITLE, body: '', tag: 'mondaiy', url: null };
  if (!raw) return fallback;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // Không phải JSON thì coi nguyên chuỗi là phần thân: vẫn còn hơn nuốt mất.
    return { ...fallback, body: raw };
  }
  if (typeof parsed !== 'object' || parsed === null) return fallback;

  const data = parsed as Record<string, unknown>;
  return {
    title: typeof data.title === 'string' && data.title.trim() ? data.title : DEFAULT_PUSH_TITLE,
    body: typeof data.body === 'string' ? data.body : '',
    tag: typeof data.tag === 'string' && data.tag.trim() ? data.tag : fallback.tag,
    url: typeof data.url === 'string' && data.url.trim() ? data.url : null,
  };
}

/**
 * Dựng tuỳ chọn cho `showNotification`.
 *
 * `tag` lấy thẳng bundle key của backend nên một bundle được giao lại (ví dụ
 * sau khi nhắc lại) thay thế thông báo cũ trên màn hình thay vì chồng thêm một
 * cái nữa. `url` được gói vào `data` vì lúc người dùng bấm thì chỉ còn đối
 * tượng notification, không còn payload gốc.
 */
export function buildNotificationOptions(payload: PushPayload): NotificationOptions {
  return {
    body: payload.body,
    tag: payload.tag,
    icon: '/favicon-192x192.png',
    badge: '/favicon-48x48.png',
    data: { url: payload.url },
  };
}

/**
 * Quy liên kết trong thông báo về một URL tuyệt đối mở được.
 *
 * Ba dạng đầu vào: liên kết ngoài đầy đủ (bằng chứng ở Gmail, Google
 * Calendar...), đường dẫn nội bộ bắt đầu bằng "/", và không có gì. Dạng thứ ba
 * rơi về trang việc cần làm — bấm vào một lời nhắc mà không mở ra gì là kiểu
 * hỏng khiến người dùng nghĩ app đứng.
 *
 * Giao thức khác http/https (javascript:, data:...) bị loại: nội dung
 * `deep_link` đến từ dữ liệu nguồn, và một URL đã đi qua tay người khác thì
 * không được phép tự chạy trong ngữ cảnh của app.
 */
export function resolveNotificationUrl(url: string | null | undefined, origin: string): string {
  const fallback = new URL(FALLBACK_PUSH_PATH, origin).toString();
  if (!url) return fallback;
  try {
    const resolved = new URL(url, origin);
    if (resolved.protocol !== 'http:' && resolved.protocol !== 'https:') return fallback;
    return resolved.toString();
  } catch {
    return fallback;
  }
}

/** Việc cần làm khi người dùng bấm vào thông báo. */
export type NotificationClickPlan =
  | { action: 'focus'; clientIndex: number; navigateTo: string | null }
  | { action: 'open'; url: string };

/**
 * Chọn giữa "kéo tab Mondaiy đang mở lên" và "mở tab mới".
 *
 * Cơ chế: chỉ tab CÙNG GỐC với app mới được tái sử dụng, và chỉ điều hướng nó
 * khi nó đang ở một địa chỉ khác — kéo lên đúng trang người dùng đang đứng rồi
 * tải lại là làm mất thao tác dở dang của họ.
 *
 * Liên kết ngoài (bằng chứng ở Gmail chẳng hạn) luôn mở tab mới: đẩy tab app
 * sang tên miền khác là lấy mất chỗ làm việc của người dùng để đổi lấy một thứ
 * họ chỉ định liếc qua.
 */
export function planNotificationClick(
  targetUrl: string,
  openClientUrls: string[],
  origin: string,
): NotificationClickPlan {
  const target = new URL(targetUrl, origin);
  if (target.origin !== new URL(origin).origin) {
    return { action: 'open', url: target.toString() };
  }

  const index = openClientUrls.findIndex((clientUrl) => {
    try {
      return new URL(clientUrl).origin === target.origin;
    } catch {
      return false;
    }
  });
  if (index === -1) return { action: 'open', url: target.toString() };

  const current = openClientUrls[index];
  const alreadyThere = current === target.toString();
  return { action: 'focus', clientIndex: index, navigateTo: alreadyThere ? null : target.toString() };
}
