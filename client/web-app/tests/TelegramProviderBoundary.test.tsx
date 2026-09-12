import { describe, expect, it } from 'vitest';

import {
  CONNECTABLE_PROVIDERS,
  ENABLED_PROVIDERS,
  isConnectableProvider,
  isEnabledProvider,
} from '../src/types/pipeline';

describe('Telegram provider boundary', () => {
  it('allows account connection without treating Telegram as an ingestion source', () => {
    expect(CONNECTABLE_PROVIDERS).toContain('telegram');
    expect(ENABLED_PROVIDERS).not.toContain('telegram');
    expect(isConnectableProvider('telegram')).toBe(true);
    expect(isEnabledProvider('telegram')).toBe(false);
  });
});
