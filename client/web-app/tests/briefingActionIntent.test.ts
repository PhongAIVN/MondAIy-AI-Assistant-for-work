/**
 * Kiểm thử khi nào hiện nút task/calendar/mentor trên chat.
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  isPlanningOrSummaryIntent,
  shouldShowMessageQuickActions,
  buildPlanningOrSummaryMockReply,
} from '../src/lib/briefingActionIntent.ts';

describe('briefingActionIntent', () => {
  it('matches planning and day-summary prompts', () => {
    assert.equal(isPlanningOrSummaryIntent('lên kế hoạch giúp tôi'), true);
    assert.equal(isPlanningOrSummaryIntent('Help me plan my week'), true);
    assert.equal(isPlanningOrSummaryIntent('tóm tắt ngày hôm qua đã làm gì'), true);
    assert.equal(isPlanningOrSummaryIntent('hôm nay tôi đã làm gì'), true);
    assert.equal(isPlanningOrSummaryIntent('Summarize what I did today'), true);
  });

  it('rejects ordinary chat', () => {
    assert.equal(isPlanningOrSummaryIntent('xin chào'), false);
    assert.equal(isPlanningOrSummaryIntent('mondaiy là gì?'), false);
    assert.equal(isPlanningOrSummaryIntent('deadline milestone nào?'), false);
  });

  it('shows actions only when prior user turn matches intent', () => {
    const messages = [
      { sender: 'user', text: 'xin chào' },
      { sender: 'ai', text: 'Chào bạn' },
      { sender: 'user', text: 'lên kế hoạch giúp tôi' },
      { sender: 'ai', text: 'Đây là gợi ý...' },
    ];
    assert.equal(shouldShowMessageQuickActions(messages, 1), false);
    assert.equal(shouldShowMessageQuickActions(messages, 3), true);
  });

  it('builds non-empty mock reply for planning and day summary', () => {
    const plan = buildPlanningOrSummaryMockReply('lên kế hoạch giúp tôi', 'vi');
    assert.ok(plan.text.length > 40);
    assert.ok(plan.summary.length > 10);
    assert.match(plan.text, /kế hoạch|nháp/i);

    const day = buildPlanningOrSummaryMockReply('tóm tắt ngày hôm nay đã làm gì', 'en');
    assert.ok(day.text.length > 40);
    assert.match(day.text, /summary|today|mock/i);
  });
});
