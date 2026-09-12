import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  STALLED_AFTER_MS,
  formatDuration,
  meetingDurationMs,
  meetingPhase,
  type MeetingTiming,
} from '../src/lib/meetingDisplay.ts';

const NOW = Date.parse('2026-08-14T10:00:00Z');

/** Một hàng danh sách tối thiểu; từng test chỉ ghi đè phần nó quan tâm. */
function meeting(overrides: Partial<MeetingTiming> = {}): MeetingTiming {
  return {
    status: 'open',
    startedAt: new Date(NOW - 45 * 60_000).toISOString(),
    endedAt: null,
    updatedAt: new Date(NOW - 60_000).toISOString(),
    ...overrides,
  };
}

const LABELS = { hour: 'giờ', minute: 'phút', lessThanMinute: 'dưới 1 phút' };

describe('pha hiển thị của cuộc họp', () => {
  it('còn tín hiệu gần đây thì là đang ghi', () => {
    assert.equal(meetingPhase(meeting(), NOW), 'recording');
  });

  it('im lặng quá ngưỡng mà chưa khép sổ thì coi là dừng giữa chừng', () => {
    // Extension bị đóng hoặc máy sập nguồn nên không kịp gọi finalize. Để nhãn
    // "đang ghi" cho cuộc họp từ hôm trước là nói dối người dùng.
    const stale = meeting({ updatedAt: new Date(NOW - STALLED_AFTER_MS - 1_000).toISOString() });
    assert.equal(meetingPhase(stale, NOW), 'stalled');
  });

  it('đã khép sổ nhưng chưa tổng hợp là một pha riêng', () => {
    const recorded = meeting({ endedAt: new Date(NOW - 5 * 60_000).toISOString() });
    assert.equal(meetingPhase(recorded, NOW), 'recorded');
  });

  it('đã tổng hợp thì luôn là summarized', () => {
    assert.equal(meetingPhase(meeting({ status: 'summarized' }), NOW), 'summarized');
  });
});

describe('thời lượng cuộc họp', () => {
  it('đang ghi thì đếm tới hiện tại', () => {
    assert.equal(meetingDurationMs(meeting(), 'recording', NOW), 45 * 60_000);
  });

  it('đã khép sổ thì lấy mốc kết thúc, không lấy hiện tại', () => {
    const ended = meeting({
      status: 'summarized',
      startedAt: new Date(NOW - 3 * 3_600_000).toISOString(),
      endedAt: new Date(NOW - 2 * 3_600_000).toISOString(),
    });
    assert.equal(meetingDurationMs(ended, 'summarized', NOW), 3_600_000);
  });

  it('dừng giữa chừng thì dừng đếm ở tín hiệu cuối', () => {
    // Khoảng lặng sau khi extension chết không phải là thời gian họp — tính tới
    // hiện tại sẽ ra "cuộc họp 3 ngày".
    const stale = meeting({
      startedAt: new Date(NOW - 5 * 3_600_000).toISOString(),
      updatedAt: new Date(NOW - 4 * 3_600_000).toISOString(),
    });
    assert.equal(meetingDurationMs(stale, 'stalled', NOW), 3_600_000);
  });

  it('mốc bắt đầu hỏng thì trả null thay vì NaN', () => {
    assert.equal(meetingDurationMs(meeting({ startedAt: 'không phải ngày' }), 'recording', NOW), null);
  });
});

describe('định dạng thời lượng', () => {
  it('dưới một phút nói thẳng thay vì hiện 0 phút', () => {
    assert.equal(formatDuration(45_000, LABELS), 'dưới 1 phút');
  });

  it('dưới một giờ chỉ hiện phút', () => {
    assert.equal(formatDuration(46 * 60_000, LABELS), '46 phút');
  });

  it('trên một giờ hiện cả giờ lẫn phút', () => {
    assert.equal(formatDuration(65 * 60_000, LABELS), '1 giờ 05 phút');
  });
});
