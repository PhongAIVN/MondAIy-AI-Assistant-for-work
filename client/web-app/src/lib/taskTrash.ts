import type { Task } from './tasksApi';

/**
 * Trạng thái lưu giữ của một task trong thùng rác.
 *
 * Vì sao tách khỏi component: đây là chỗ duy nhất quyết định "task này có bị
 * xoá không, và còn bao lâu". Nhúng vào JSX thì mỗi chỗ hiển thị sẽ tự suy diễn
 * lại một kiểu, và chỉ cần một chỗ suy sai là người dùng đọc được một hạn xoá
 * không có thật.
 */

/** Khớp `task_trash_retention_days` ở backend (src/config.py). */
export const TRASH_RETENTION_DAYS = 7;

export type TrashState =
  /** Không nằm trong thùng rác. */
  | { kind: 'not_in_trash' }
  /**
   * Trong thùng rác nhưng KHÔNG có hạn xoá: task bị huỷ trước khi backend có
   * cột `cancelled_at`. Backend cố ý không backfill và không bao giờ tự xoá
   * chúng, nên hiển thị hạn ở đây là bịa.
   */
  | { kind: 'kept_indefinitely' }
  /** Trong thùng rác, còn `daysLeft` ngày trước khi bị xoá vĩnh viễn. */
  | { kind: 'expiring'; daysLeft: number }
  /** Đã quá hạn — vòng dọn kế tiếp sẽ xoá. */
  | { kind: 'due_for_purge' };

export function trashState(task: Task, now: Date = new Date()): TrashState {
  if (task.status !== 'cancelled') return { kind: 'not_in_trash' };
  if (!task.cancelledAt) return { kind: 'kept_indefinitely' };

  const cancelledAt = new Date(task.cancelledAt);
  if (Number.isNaN(cancelledAt.getTime())) {
    // Mốc không đọc được thì KHÔNG đoán một con số. Nói là giữ lại vô thời hạn
    // vẫn đúng về mặt hệ quả — backend cũng chỉ xoá khi so được mốc.
    return { kind: 'kept_indefinitely' };
  }

  const msLeft = cancelledAt.getTime() + TRASH_RETENTION_DAYS * 86_400_000 - now.getTime();
  if (msLeft <= 0) return { kind: 'due_for_purge' };

  // Làm tròn LÊN: còn 0,3 ngày thì với người dùng vẫn là "còn 1 ngày". Làm tròn
  // xuống sẽ hiện "còn 0 ngày" cho một task vẫn đang khôi phục được.
  return { kind: 'expiring', daysLeft: Math.ceil(msLeft / 86_400_000) };
}

export function trashLabel(state: TrashState, language: 'vi' | 'en'): string | null {
  switch (state.kind) {
    case 'not_in_trash':
      return null;
    case 'kept_indefinitely':
      return language === 'vi' ? 'Giữ lại, không tự xoá' : 'Kept, never auto-deleted';
    case 'due_for_purge':
      return language === 'vi' ? 'Sắp bị xoá vĩnh viễn' : 'About to be deleted permanently';
    case 'expiring':
      return language === 'vi'
        ? `Còn ${state.daysLeft} ngày trước khi xoá`
        : `${state.daysLeft} day${state.daysLeft === 1 ? '' : 's'} before deletion`;
  }
}
