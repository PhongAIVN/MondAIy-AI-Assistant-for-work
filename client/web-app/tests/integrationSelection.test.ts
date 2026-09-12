import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { selectPreferredIntegration } from '../src/lib/integrationSelection.ts';

describe('selectPreferredIntegration', () => {
  it('chooses a non-expired newer connection over an expired first row', () => {
    const now = Date.parse('2026-08-10T09:00:00Z');
    const selected = selectPreferredIntegration(
      [
        { provider: 'google', expiresAt: '2026-08-10T08:00:00Z' },
        { provider: 'google', expiresAt: '2026-08-10T10:00:00Z' },
        { provider: 'discord', expiresAt: null },
      ],
      'google',
      now,
    );
    assert.equal(selected?.expiresAt, '2026-08-10T10:00:00Z');
  });
});
