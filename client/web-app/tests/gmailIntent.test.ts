/** Regression: câu hỏi công việc theo thời gian không được chuyển nhầm sang Gmail. */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { isGmailBriefingIntent } from '../src/lib/gmailIntent.ts';

describe('isGmailBriefingIntent', () => {
  it('requires an explicit mailbox reference', () => {
    assert.equal(isGmailBriefingIntent('hello, chiều nay tôi cần làm cái gì'), false);
    assert.equal(isGmailBriefingIntent('hôm nay tôi cần làm gì'), false);
    assert.equal(isGmailBriefingIntent('tóm tắt email có việc cần làm'), true);
    assert.equal(isGmailBriefingIntent('deadline nào có trong Gmail?'), true);
  });

  it('keeps productivity/calendar requests out of the Gmail fetch flow', () => {
    assert.equal(isGmailBriefingIntent('thêm việc trong email vào lịch'), false);
    assert.equal(isGmailBriefingIntent('tạo meeting từ mail này'), false);
    assert.equal(isGmailBriefingIntent('tóm tắt email có việc cần làm'), true);
  });
});
