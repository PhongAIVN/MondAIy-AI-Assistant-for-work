import { storage } from "wxt/utils/storage";
import type { AuthSession, NotificationBundle } from "@/types";

export const pendingTaskCountItem = storage.defineItem<number>(
  "local:pendingTaskCount",
  { fallback: 0 }
);

// Notification đã hỏi được lưu theo cả task và loại câu hỏi. Hai trạng thái
// tách nhau để một task đã hỏi "bắt đầu chưa" vẫn được hỏi "xong chưa" sau đó.
export const askedTaskCheckInsItem = storage.defineItem<Record<string, true>>(
  "local:askedTaskCheckIns",
  { fallback: {} }
);

// Map chrome notification id -> bundle đã hiện, để xử lý click/button đúng
// task ngay cả khi service worker MV3 bị dừng giữa lúc hiện và lúc bấm — đọc
// lại từ local storage thay vì tin biến trong bộ nhớ (ADR-007 mục 9).
export const notificationBundlesItem = storage.defineItem<Record<string, NotificationBundle>>(
  "local:notificationBundles",
  { fallback: {} }
);

// Opt-in: Side Panel tự mở có thể làm gián đoạn công việc nên mặc định tắt.
// Lưu local để lựa chọn tồn tại qua các lần Chrome khởi động lại mà không cần
// backend. Tên biến/khoá storage giữ nguyên "Popup" vì đây chỉ là định danh,
// đổi khoá storage sẽ làm mất lựa chọn đã lưu của người dùng đang cài.
export const autoOpenReminderPopupItem = storage.defineItem<boolean>(
  "local:autoOpenReminderPopup",
  { fallback: false }
);

// Bundle gần nhất được background lưu trước khi gọi sidePanel.open(). Side
// Panel đọc giá trị này để hiện đúng việc đang nhắc thay vì chỉ mở danh sách chung.
export const activeReminderBundleItem = storage.defineItem<NotificationBundle | null>(
  "local:activeReminderBundle",
  { fallback: null }
);

// session: area = chrome.storage.session, memory-only, mất khi browser đóng.
// Bắt buộc dùng area này cho token, KHÔNG local — hard rule auth.
export const authSessionItem = storage.defineItem<AuthSession | null>(
  "session:authSession",
  { fallback: null }
);
