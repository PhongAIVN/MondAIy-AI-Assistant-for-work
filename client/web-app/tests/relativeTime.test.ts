import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatRelativeTime } from '../src/lib/relativeTime.ts';

describe('formatRelativeTime', () => {
  it('formats a moment just now', () => {
    assert.equal(formatRelativeTime(new Date().toISOString(), 'vi'), 'vừa');
    assert.equal(formatRelativeTime(new Date().toISOString(), 'en'), 'now');
  });

  it('formats minutes and hours ago from a real elapsed diff, not a stored label', () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60_000).toISOString();
    assert.equal(formatRelativeTime(fiveMinAgo, 'vi'), '5p');
    assert.equal(formatRelativeTime(fiveMinAgo, 'en'), '5m');

    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000).toISOString();
    assert.equal(formatRelativeTime(threeHoursAgo, 'vi'), '3g');
    assert.equal(formatRelativeTime(threeHoursAgo, 'en'), '3h');
  });

  it('formats days ago', () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 86_400_000).toISOString();
    assert.equal(formatRelativeTime(twoDaysAgo, 'vi'), '2ng');
    assert.equal(formatRelativeTime(twoDaysAgo, 'en'), '2d');
  });

  it('falls back to the raw input for a non-date string instead of throwing', () => {
    assert.equal(formatRelativeTime('not-a-date', 'vi'), 'not-a-date');
  });
});
