import React, { useEffect } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Bell } from 'lucide-react';
import { useTranslation } from '../i18n/useTranslation';
import { useAuthStore } from '../stores/useAuthStore';
import { useNotificationsStore, type NotificationItem } from '../stores/useNotificationsStore';
import { formatNotificationSubtitle, NotificationKindIcon } from '../lib/notificationDisplay';
import { getFeatureAnnouncementCopy } from '../lib/featureAnnouncement';
import { useNavigate } from 'react-router-dom';

export const NotificationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { language } = useTranslation();
  const { accessToken } = useAuthStore();
  const { items, isLoading, fetchDue, markAllRead, markRead } = useNotificationsStore();
  const unreadCount = items.filter((item) => !item.isRead).length;

  useEffect(() => {
    if (accessToken) void fetchDue(accessToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

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
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <Bell className="w-4 h-4" /> {language === 'vi' ? 'Trung tâm cập nhật' : 'Updates Center'}
          </div>
          <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] font-heading">
            {language === 'vi' ? 'Thông báo' : 'Notifications'}
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">
            {language === 'vi'
              ? 'Lời nhắc đến hạn cho công việc đã xác nhận, mở được bằng chứng nguồn gốc.'
              : 'Due reminders for confirmed tasks, each opens back to its source evidence.'}
          </p>
        </div>

        {unreadCount > 0 && (
          <Button variant="outline" size="sm" onClick={handleMarkAllRead} data-tour-id="notifications-mark-all">
            {language === 'vi' ? `Đánh dấu đã đọc hết (${unreadCount})` : `Mark All as Read (${unreadCount})`}
          </Button>
        )}
      </div>

      <div data-tour-id="notifications-list">
        {items.length === 0 ? (
          <Card className="p-8 text-center text-sm text-[var(--color-text-secondary)]">
            {isLoading
              ? language === 'vi'
                ? 'Đang tải…'
                : 'Loading…'
              : language === 'vi'
                ? 'Không có lời nhắc nào đến hạn ngay bây giờ.'
                : 'No reminders due right now.'}
          </Card>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <Card
                key={item.id}
                onClick={() => handleOpenItem(item)}
                className={`flex items-start justify-between gap-4 p-4 transition-all cursor-pointer border-l-4 ${
                  item.isRead
                    ? 'border-l-transparent opacity-70 hover:opacity-100'
                    : 'border-l-[var(--color-primary)] bg-[var(--color-accent-soft)]/40'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`p-2.5 rounded-xl shrink-0 mt-0.5 ${
                      item.isRead
                        ? 'bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)]'
                        : 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]'
                    }`}
                  >
                    <NotificationKindIcon kind={item.kind} milestone={item.milestone} className="w-4 h-4" />
                  </div>

                  <div className="space-y-0.5">
                    <h3
                      className={`text-sm font-heading ${
                        item.isRead ? 'font-medium text-[var(--color-text-secondary)]' : 'font-bold text-[var(--color-text-primary)]'
                      }`}
                    >
                      {item.kind === 'feature_announcement' ? getFeatureAnnouncementCopy(language).title : item.title}
                    </h3>
                    <span className="text-[10px] text-[var(--color-text-muted)] block pt-1">
                      {formatNotificationSubtitle(item.kind, item.milestone, item.dueAt, language)}
                    </span>
                    {item.kind === 'feature_announcement' && (
                      <p className="pt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                        {getFeatureAnnouncementCopy(language).subtitle}
                      </p>
                    )}
                  </div>
                </div>

                {!item.isRead && (
                  <span
                    className="w-2.5 h-2.5 rounded-full bg-[#2563A6] shrink-0 mt-2"
                    title={language === 'vi' ? 'Chưa đọc' : 'Unread'}
                    data-tour-id="notifications-unread-dot"
                  />
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
