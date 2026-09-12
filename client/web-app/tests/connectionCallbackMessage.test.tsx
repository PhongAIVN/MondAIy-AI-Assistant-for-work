import { describe, expect, it } from 'vitest';

import { resolveConnectionCallbackMessage } from '../src/lib/connectionCallback';

describe('resolveConnectionCallbackMessage', () => {
  it('shows the backend callback message instead of replacing it with generic copy', () => {
    expect(resolveConnectionCallbackMessage('exchange_failed', 'Could not connect Discord. Try again.')).toBe(
      'exchange_failed',
    );
  });

  it('keeps the localized fallback when the backend sends no message', () => {
    expect(resolveConnectionCallbackMessage(null, 'Không kết nối được Discord. Thử lại sau.')).toBe(
      'Không kết nối được Discord. Thử lại sau.',
    );
  });
});
