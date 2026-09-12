import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatConversationTimestamp } from '../src/lib/conversationTimestamp.ts';

describe('formatConversationTimestamp', () => {
  it('formats an API ISO timestamp instead of exposing the raw value', () => {
    const raw = '2026-08-16T07:50:54.680Z';
    const formatted = formatConversationTimestamp(raw, 'vi');

    assert.notEqual(formatted, raw);
    assert.match(formatted, /\d{1,2}:\d{2}/);
  });

  it('keeps human-readable labels already produced by the client', () => {
    assert.equal(formatConversationTimestamp('Vừa xong', 'vi'), 'Vừa xong');
    assert.equal(formatConversationTimestamp('Just now', 'en'), 'Just now');
  });
});
