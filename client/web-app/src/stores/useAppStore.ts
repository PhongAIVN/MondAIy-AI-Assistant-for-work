import { create } from 'zustand';

export type BriefingSimulatedState = 'normal' | 'urgent' | 'conflict' | 'no_updates' | 'limited_coverage' | 'loading' | 'error';

export type ToastMessage = {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
  message: string;
  /** Ảnh mascot thay cho icon loại toast — dùng cho các thông báo mang tính cảm xúc. */
  mascotGif?: string;
};

type AppStore = {
  briefingState: BriefingSimulatedState;
  setBriefingState: (state: BriefingSimulatedState) => void;
  
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;

  activeModal: 'none' | 'task_review' | 'source_detail' | 'conflict_compare' | 'calendar_event' | 'new_task' | 'source_library';
  modalData: any;
  openModal: (modal: AppStore['activeModal'], data?: any) => void;
  closeModal: () => void;

  searchQuery: string;
  setSearchQuery: (query: string) => void;
};

export const useAppStore = create<AppStore>((set, get) => ({
  briefingState: 'normal',
  setBriefingState: (briefingState) => set({ briefingState }),

  toasts: [],
  addToast: (toast) => {
    // Cùng type+title+message đang hiển thị thì bỏ qua, tránh xếp chồng khi
    // người dùng bấm nhanh nhiều lần (vd đổi ngôn ngữ/theme liên tiếp).
    const isDuplicate = get().toasts.some(
      (t) => t.type === toast.type && t.title === toast.title && t.message === toast.message,
    );
    if (isDuplicate) return;

    const id = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4);
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  activeModal: 'none',
  modalData: null,
  openModal: (activeModal, modalData = null) => set({ activeModal, modalData }),
  closeModal: () => set({ activeModal: 'none', modalData: null }),

  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),
}));
