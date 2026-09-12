import { create } from 'zustand';

type AppTourStore = {
  /** true = có yêu cầu chạy tour toàn app đang chờ AppShell xử lý. */
  pending: boolean;
  /** Gọi từ menu tài khoản (Sidebar) để yêu cầu chạy lại tour hướng dẫn. */
  requestAppTour: () => void;
  /** AppShell gọi sau khi đã bắt đầu tour, để không lặp lại yêu cầu cũ. */
  clearAppTourRequest: () => void;
};

/**
 * Cầu nối yêu cầu chạy tour: Sidebar không có quyền điều hướng trang + mở
 * thanh tìm kiếm cùng lúc, nên chỉ phát yêu cầu — AppShell (nơi giữ cả
 * navigate lẫn trạng thái Command Palette) mới thực sự khởi động tour.
 */
export const useAppTourStore = create<AppTourStore>((set) => ({
  pending: false,
  requestAppTour: () => set({ pending: true }),
  clearAppTourRequest: () => set({ pending: false }),
}));
