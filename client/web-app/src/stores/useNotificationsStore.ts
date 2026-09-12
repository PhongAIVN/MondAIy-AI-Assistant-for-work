import { create } from 'zustand';
import { listNotifications, recordReminderDeliveries, type NotificationEntry, type NotificationKind } from '../lib/reminderApi';
import {
  FEATURE_ANNOUNCEMENT_ID,
  isFeatureAnnouncementRead,
  markFeatureAnnouncementRead,
} from '../lib/featureAnnouncement';

export type AppNotificationKind = NotificationKind | 'feature_announcement';

export type NotificationItem = {
  id: string;
  reminderId: number | null;
  kind: AppNotificationKind;
  title: string;
  milestone: string;
  taskId: number | null;
  dueAt: string | null;
  scheduledAt: string;
  evidenceDeepLink: string | null;
  payload: Record<string, unknown>;
  isRead: boolean;
};

const toItem = (entry: NotificationEntry): NotificationItem => ({
  id: String(entry.reminderId),
  reminderId: entry.reminderId,
  kind: entry.kind,
  title: entry.title,
  milestone: entry.milestone,
  taskId: entry.taskId,
  dueAt: entry.dueAt,
  scheduledAt: entry.scheduledAt,
  evidenceDeepLink: entry.evidenceDeepLink,
  payload: entry.payload,
  isRead: entry.isRead,
});

/** Release note là notification local: không được gửi vào pipeline reminder của user. */
const featureAnnouncementItem = (): NotificationItem => ({
  id: FEATURE_ANNOUNCEMENT_ID,
  reminderId: null,
  kind: 'feature_announcement',
  title: 'Feature announcement',
  milestone: 'release',
  taskId: null,
  dueAt: null,
  scheduledAt: '2026-08-17T00:00:00Z',
  evidenceDeepLink: null,
  payload: {},
  isRead: isFeatureAnnouncementRead(),
});

type NotificationsStore = {
  items: NotificationItem[];
  isLoading: boolean;
  /** Kieu Facebook: doc roi khong bien mat, chi mo di — nen fetch tra ve ca
   * da doc lan chua doc (GET /reminders/notifications), khac /due truoc day. */
  fetchDue: (accessToken: string) => Promise<void>;
  markAllRead: (accessToken: string) => Promise<void>;
  markRead: (accessToken: string, item: NotificationItem) => Promise<void>;
  unreadCount: () => number;
};

export const useNotificationsStore = create<NotificationsStore>((set, get) => ({
  items: [],
  isLoading: false,

  fetchDue: async (accessToken) => {
    set({ isLoading: true });
    try {
      const entries = await listNotifications(accessToken);
      set({ items: [featureAnnouncementItem(), ...entries.map(toItem)], isLoading: false });
    } catch {
      // Chua dang nhap hoac loi mang — giu list hien tai, khong bao sai so lieu.
      set((state) => ({
        items: state.items.some((item) => item.kind === 'feature_announcement')
          ? state.items
          : [featureAnnouncementItem(), ...state.items],
        isLoading: false,
      }));
    }
  },

  markAllRead: async (accessToken) => {
    const unreadItems = get().items.filter((item) => !item.isRead);
    const unreadIds = unreadItems.flatMap((item) => item.reminderId === null ? [] : [item.reminderId]);
    if (unreadItems.length === 0) return;
    set((state) => ({
      items: state.items.map((item) => (item.isRead ? item : { ...item, isRead: true })),
    }));
    try {
      if (unreadItems.some((item) => item.kind === 'feature_announcement')) {
        markFeatureAnnouncementRead();
      }
      await recordReminderDeliveries(accessToken, unreadIds);
    } catch {
      // Best-effort: lan fetchDue ke tiep se doc lai dung trang thai tu server.
    }
  },

  markRead: async (accessToken, item) => {
    if (item.isRead) return;
    set((state) => ({
      items: state.items.map((row) => (row.id === item.id ? { ...row, isRead: true } : row)),
    }));
    if (item.kind === 'feature_announcement') {
      markFeatureAnnouncementRead();
      return;
    }
    try {
      if (item.reminderId !== null) await recordReminderDeliveries(accessToken, [item.reminderId]);
    } catch {
      // Best-effort, cung ly do nhu tren.
    }
  },

  unreadCount: () => get().items.filter((item) => !item.isRead).length,
}));
