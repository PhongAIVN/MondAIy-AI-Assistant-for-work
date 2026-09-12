import { Clock, Sparkles, AlertTriangle, Newspaper } from 'lucide-react';
import type { AppNotificationKind } from '../stores/useNotificationsStore';

/** Dung chung giua NotificationPopover (header) va NotificationsPage (/notifications)
 * — 2 cho doc cung 1 nguon GET /reminders/due, khong duoc lech logic hien thi. */

function formatDateTime(dueAt: string, language: string): string {
  return new Date(dueAt).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatNotificationSubtitle(
  kind: AppNotificationKind,
  milestone: string,
  dueAt: string | null,
  language: string,
): string {
  if (kind === 'task_due' && dueAt) {
    const time = formatDateTime(dueAt, language);
    if (language === 'vi') return milestone === '30_min' ? `Còn 30 phút — hạn ${time}` : `Còn 1 ngày — hạn ${time}`;
    return milestone === '30_min' ? `Due in 30 minutes — ${time}` : `Due in 1 day — ${time}`;
  }
  if (kind === 'task_proposed') {
    return language === 'vi' ? 'Việc mới — cần bạn xác nhận' : 'New task — needs your review';
  }
  if (kind === 'conflict_schedule' && dueAt) {
    const time = formatDateTime(dueAt, language);
    return language === 'vi' ? `Trùng lịch — hạn ${time}` : `Schedule conflict — due ${time}`;
  }
  if (kind === 'conflict_evidence') {
    return language === 'vi' ? 'Nguồn tin không khớp về hạn chót' : 'Sources disagree on the deadline';
  }
  if (kind === 'daily_brief') {
    return language === 'vi' ? 'Tổng hợp cuối ngày' : 'Daily digest';
  }
  if (kind === 'feature_announcement') {
    return language === 'vi' ? 'Cập nhật sản phẩm' : 'Product update';
  }
  return dueAt ? formatDateTime(dueAt, language) : '';
}

export function NotificationKindIcon({ kind, milestone, className }: { kind: AppNotificationKind; milestone: string; className?: string }) {
  const cls = className ?? 'h-3.5 w-3.5';
  if (kind === 'task_due') {
    return milestone === '30_min' ? (
      <Clock className={`${cls} text-[var(--color-danger)]`} />
    ) : (
      <Sparkles className={`${cls} text-[var(--color-primary)]`} />
    );
  }
  if (kind === 'conflict_schedule' || kind === 'conflict_evidence') {
    return <AlertTriangle className={`${cls} text-[var(--color-warning)]`} />;
  }
  if (kind === 'daily_brief') {
    return <Newspaper className={`${cls} text-[var(--color-primary)]`} />;
  }
  return <Sparkles className={`${cls} text-[var(--color-primary)]`} />;
}
