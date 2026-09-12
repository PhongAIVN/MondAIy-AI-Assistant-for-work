export const FEATURE_ANNOUNCEMENT_ID = 'feature-announcement-2026-08-17';
const FEATURE_ANNOUNCEMENT_KEY = 'mondaiy.feature-announcement.2026-08-17';

export type FeatureAnnouncementCopy = {
  title: string;
  subtitle: string;
  link: string;
};

/** Thông báo phát hành là client-side, không phải reminder của người dùng. */
export function getFeatureAnnouncementCopy(language: string): FeatureAnnouncementCopy {
  return language === 'vi'
    ? {
        title: 'Có gì mới trên mondaiy',
        subtitle: 'Routine có tóm tắt nhanh, ảnh trong chat có thể đọc nội dung và task/lịch luôn chờ bạn xác nhận.',
        link: 'Xem Routine mới',
      }
    : {
        title: "What's new on mondaiy",
        subtitle: 'Routine summaries are faster to scan, chat can read images, and suggested tasks or events always wait for your confirmation.',
        link: 'View new routines',
      };
}

export function isFeatureAnnouncementRead(): boolean {
  try {
    return localStorage.getItem(FEATURE_ANNOUNCEMENT_KEY) === '1';
  } catch {
    return false;
  }
}

export function markFeatureAnnouncementRead(): void {
  try {
    localStorage.setItem(FEATURE_ANNOUNCEMENT_KEY, '1');
  } catch {
    // Private browsing/quota errors should not block opening the update.
  }
}
