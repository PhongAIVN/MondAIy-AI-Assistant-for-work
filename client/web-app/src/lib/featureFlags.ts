/** Công tắc tính năng đọc từ biến môi trường build (Vite). */

/**
 * Nút Đồng bộ thủ công ở trang Thư viện nguồn.
 *
 * Tắt từ 2026-08-21: việc đồng bộ nay do trang chat tự kéo (câu chat đầu tiên
 * mỗi ngày, hoặc câu hỏi về việc trên dữ liệu đã cũ — xem
 * src/services/chat_sync.py). Người dùng không phải nhớ bấm Sync nữa.
 *
 * Đây là CỜ chứ không phải xoá code: đặt VITE_MANUAL_SYNC_UI=1 là các nút hiện
 * lại nguyên vẹn, không cần khôi phục gì.
 */
export const manualSyncUiEnabled = (): boolean =>
  (import.meta.env.VITE_MANUAL_SYNC_UI as string | undefined) === '1';
