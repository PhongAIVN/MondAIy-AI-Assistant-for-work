/**
 * Cách một cuộc họp được diễn giải để hiển thị: pha nào, kéo dài bao lâu.
 *
 * Tách khỏi trang danh sách vì đây là suy luận từ dữ liệu chứ không phải cách
 * vẽ, và vì phần suy luận này cần test được mà không phải dựng cả React tree.
 */

/**
 * Một cuộc họp "open" mà không có tín hiệu nào trong ngần này coi như đã dừng
 * giữa chừng. Đây chỉ là suy đoán hiển thị: extension có thể bị đóng, máy sập
 * nguồn hay mất mạng nên không kịp gọi finalize, và để nguyên nhãn "đang ghi"
 * cho cuộc họp từ tuần trước thì cả danh sách mất hết ý nghĩa.
 */
export const STALLED_AFTER_MS = 15 * 60_000;

/** 4 pha hiển thị của một cuộc họp, suy từ status cùng hai mốc thời gian. */
export type MeetingPhase = 'recording' | 'stalled' | 'recorded' | 'summarized';

/**
 * Phần dữ liệu duy nhất mà hai hàm dưới cần. Khai báo hẹp như vậy để dùng được
 * cho cả hàng danh sách lẫn cuộc họp đầy đủ ở trang chi tiết.
 */
export type MeetingTiming = {
  status: 'open' | 'summarized';
  startedAt: string;
  endedAt: string | null;
  updatedAt: string;
};

/**
 * Xác định pha hiển thị.
 *
 * Cơ chế: đã tổng hợp thì xong chuyện. Chưa tổng hợp mà có `endedAt` nghĩa là
 * phiên ghi đã khép sổ tử tế, chỉ còn chờ người dùng bấm tổng hợp. Không có
 * `endedAt` thì dựa vào `updatedAt` — mốc server ghi nhận thay đổi cuối cùng —
 * để phân biệt đang ghi thật với phiên chết giữa chừng.
 */
export function meetingPhase(meeting: MeetingTiming, now: number): MeetingPhase {
  if (meeting.status === 'summarized') return 'summarized';
  if (meeting.endedAt) return 'recorded';
  const lastSignal = new Date(meeting.updatedAt).getTime();
  if (Number.isNaN(lastSignal) || now - lastSignal > STALLED_AFTER_MS) return 'stalled';
  return 'recording';
}

/**
 * Thời lượng cuộc họp tính bằng mili giây, null khi mốc bắt đầu không đọc được.
 *
 * Cuộc họp đã khép sổ lấy mốc `endedAt`. Đang ghi thì đếm tới hiện tại. Dừng
 * giữa chừng thì lấy `updatedAt` — tín hiệu cuối cùng server nhận được — thay
 * vì hiện tại, vì khoảng lặng sau đó không phải là thời gian họp.
 */
export function meetingDurationMs(
  meeting: MeetingTiming,
  phase: MeetingPhase,
  now: number,
): number | null {
  const start = new Date(meeting.startedAt).getTime();
  if (Number.isNaN(start)) return null;
  const end = phase === 'recording' ? now : new Date(meeting.endedAt ?? meeting.updatedAt).getTime();
  if (Number.isNaN(end)) return null;
  return Math.max(0, end - start);
}

/** Nhãn đơn vị thời lượng, truyền vào để hàm này không phụ thuộc i18n. */
export type DurationLabels = { hour: string; minute: string; lessThanMinute: string };

/** "1 giờ 05 phút" / "46 phút" / "dưới 1 phút" — bỏ giây vì không ai cần độ chính xác đó. */
export function formatDuration(ms: number, labels: DurationLabels): string {
  const totalMinutes = Math.floor(ms / 60_000);
  if (totalMinutes < 1) return labels.lessThanMinute;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} ${labels.minute}`;
  return `${hours} ${labels.hour} ${String(minutes).padStart(2, '0')} ${labels.minute}`;
}
