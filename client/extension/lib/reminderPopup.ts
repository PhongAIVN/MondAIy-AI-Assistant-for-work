import type { NotificationBundle } from "@/types";

export type ReminderPopupResult = "disabled" | "opened" | "unavailable";

/**
 * Quyết định có nên tự mở popup cho bundle này không.
 *
 * pollReminders() chạy lại mỗi 5 phút (alarm định kỳ) VÀ mỗi khi web app báo
 * đổi phiên đăng nhập (mỗi lần load trang/đổi tab/đổi localStorage — có thể
 * xảy ra nhiều lần liên tục lúc user đăng nhập hoặc lướt web app). Bundle còn
 * hạn (chưa dismiss/snooze/confirm) thì server vẫn trả lại y hệt ở mọi lần
 * gọi /reminders/due tiếp theo — không có guard thì mỗi lần poll (kể cả do
 * đăng nhập kích hoạt) đều ép mở lại popup, dù user vừa tự đóng nó.
 *
 * Chỉ mở khi bundleKey khác bundle đang active (chưa từng mở cho bundle này,
 * hoặc bundle trước đã được xử lý/xoá) — không mở lại cho đúng 1 bundle nhiều lần.
 */
export function shouldAutoOpenReminderPopup(
  bundle: NotificationBundle,
  activeBundle: NotificationBundle | null
): boolean {
  return activeBundle?.bundleKey !== bundle.bundleKey;
}

/**
 * Thử mở action popup cho một reminder opt-in.
 *
 * Notification đã được tạo trước khi hàm này chạy, vì vậy mọi lỗi API (Chrome
 * cũ, cửa sổ không phù hợp, popup đang mở...) đều được nuốt để notification
 * hệ điều hành tiếp tục làm fallback đáng tin cậy.
 */
export async function maybeOpenReminderPopup(
  enabled: boolean,
  openPopup: (() => Promise<void>) | undefined
): Promise<ReminderPopupResult> {
  if (!enabled) return "disabled";
  if (!openPopup) return "unavailable";

  try {
    await openPopup();
    return "opened";
  } catch {
    return "unavailable";
  }
}
