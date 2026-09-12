import { create } from 'zustand';
import { type BriefingItem, type BriefingFeedbackOverall, type FeedbackType } from '../types/briefing';
import { initialBriefingItems, conflictBriefingItem } from '../data/briefingData';

type BriefingStore = {
  items: BriefingItem[];
  lastUpdated: string;
  isRefreshing: boolean;
  overallFeedback: BriefingFeedbackOverall | null;

  setItems: (items: BriefingItem[]) => void;
  updateItemFeedback: (id: string, feedback: FeedbackType) => void;
  dismissItem: (id: string) => void;
  setOverallFeedback: (feedback: BriefingFeedbackOverall) => void;
  refreshBriefing: () => Promise<void>;
  
  getItemById: (id: string) => BriefingItem | undefined;
};

export const useBriefingStore = create<BriefingStore>((set, get) => ({
  items: initialBriefingItems,
  lastUpdated: 'Updated 7 minutes ago',
  isRefreshing: false,
  overallFeedback: null,

  setItems: (items) => set({ items }),

  updateItemFeedback: (id, feedback) => {
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? { ...item, userFeedback: feedback } : item
      ),
    }));
  },

  dismissItem: (id) => {
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? { ...item, dismissed: true } : item
      ),
    }));
  },

  setOverallFeedback: (overallFeedback) => set({ overallFeedback }),

  refreshBriefing: async () => {
    set({ isRefreshing: true });
    // Simulate network sync with connected sources
    await new Promise((resolve) => setTimeout(resolve, 1200));
    set({
      isRefreshing: false,
      lastUpdated: 'Updated just now',
    });
  },

  getItemById: (id) => get().items.find((item) => item.id === id) || (id === conflictBriefingItem.id ? conflictBriefingItem : undefined),
}));
