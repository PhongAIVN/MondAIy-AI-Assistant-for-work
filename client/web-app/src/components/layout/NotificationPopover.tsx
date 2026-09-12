import React from 'react';
import { CheckCheck, ArrowRight } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { useAuthStore } from '../../stores/useAuthStore';
import { useNotificationsStore, type NotificationItem } from '../../stores/useNotificationsStore';
import { formatNotificationSubtitle, NotificationKindIcon } from '../../lib/notificationDisplay';
import { IconBell } from '../ui/ProductIcons';
import { getFeatureAnnouncementCopy } from '../../lib/featureAnnouncement';
import { useNavigate } from 'react-router-dom';

type NotificationPopoverProps = {
  /** Dieu huong sang trang /notifications day du, kem dong popover phia goi. */
  onViewAll: () => void;
};

/** Panel thông báo thu gọn gắn TopBar — đọc thật từ GET /reminders/due. */
export const NotificationPopover: React.FC<NotificationPopoverProps> = ({ onViewAll }) => {
  const navigate = useNavigate();
  const { language } = useTranslation();
  const { accessToken } = useAuthStore();
  const { items, isLoading, markAllRead, markRead } = useNotificationsStore();
  const unreadCount = items.filter((item) => !item.isRead).length;

  const handleMarkAllRead = () => {
    if (accessToken) void markAllRead(accessToken);
  };

  const handleOpenItem = (item: NotificationItem) => {
    if (accessToken) void markRead(accessToken, item);
    if (item.kind === 'feature_announcement') {
      navigate('/routines');
      return;
    }
    if (item.evidenceDeepLink) {
      window.open(item.evidenceDeepLink, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="app-panel absolute right-0 mt-2 w-[min(100vw-1.5rem,22rem)] overflow-hidden rounded-2xl shadow-xl z-50 animate-in fade-in zoom-in-95 duration-150">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] px-3.5 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--color-primary)]">
            <IconBell size={14} className="text-[var(--color-primary)]" />
            {language === 'vi' ? 'Trung tâm cập nhật' : 'Updates Center'}
          </div>
          <p className="truncate text-sm font-extrabold font-heading text-[var(--color-text-primary)]">
            {language === 'vi' ? 'Thông báo' : 'Notifications'}
            {unreadCount > 0 && (
              <span className="ml-1.5 text-xs font-semibold text-[var(--color-primary)]">
                ({unreadCount})
              </span>
            )}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={handleMarkAllRead}
            className="app-control inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold"
            title={language === 'vi' ? 'Đánh dấu đã đọc hết' : 'Mark all as read'}
          >
            <CheckCheck className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">
              {language === 'vi' ? 'Đã đọc hết' : 'Mark all read'}
            </span>
          </button>
        )}
      </div>

      <div className="max-h-80 overflow-y-auto p-1.5">
        {items.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-[var(--color-text-secondary)]">
            {isLoading
              ? language === 'vi'
                ? 'Đang tải…'
                : 'Loading…'
              : language === 'vi'
                ? 'Không có lời nhắc nào đến hạn.'
                : 'No reminders due right now.'}
          </p>
        ) : (
          <ul className="space-y-0.5">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => handleOpenItem(item)}
                  className={`flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2.5 text-left transition-colors ${
                    item.isRead
                      ? 'bg-transparent hover:bg-[var(--color-surface-muted)]'
                      : 'bg-[var(--color-accent-soft)] hover:bg-[var(--color-accent-soft)]/80'
                  }`}
                >
                  <div
                    className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                      item.isRead ? 'bg-[var(--color-surface-muted)]' : 'bg-[var(--color-primary)]/15'
                    }`}
                  >
                    <NotificationKindIcon kind={item.kind} milestone={item.milestone} />
                  </div>
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex items-start justify-between gap-2">
                      <p
                        className={`text-xs leading-snug ${
                          item.isRead
                            ? 'font-medium text-[var(--color-text-secondary)]'
                            : 'font-bold text-[var(--color-text-primary)]'
                        }`}
                      >
                        {item.kind === 'feature_announcement' ? getFeatureAnnouncementCopy(language).title : item.title}
                      </p>
                      {!item.isRead && (
                        <span
                          className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--color-primary)]"
                          title={language === 'vi' ? 'Chưa đọc' : 'Unread'}
                        />
                      )}
                    </div>
                    <span className="block pt-0.5 text-[10px] text-[var(--color-text-muted)]">
                      {formatNotificationSubtitle(item.kind, item.milestone, item.dueAt, language)}
                    </span>
                    {item.kind === 'feature_announcement' && (
                      <span className="block text-[10px] leading-snug text-[var(--color-text-secondary)]">
                        {getFeatureAnnouncementCopy(language).subtitle}
                      </span>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-[var(--color-border)] bg-[var(--color-surface-muted)] p-1.5">
        <button
          type="button"
          onClick={onViewAll}
          className="app-control flex w-full items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold text-[var(--color-primary)]"
        >
          <span>{language === 'vi' ? 'Xem tất cả thông báo' : 'View all notifications'}</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};
