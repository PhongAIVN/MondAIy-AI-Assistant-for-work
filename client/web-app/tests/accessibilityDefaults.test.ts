/**
 * Mặc định a11y: high contrast tắt.
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

describe('accessibility defaults', () => {
  it('disables high contrast by default', () => {
    const source = readFileSync(join(root, 'src/stores/usePreferencesStore.ts'), 'utf8');
    assert.match(source, /highContrast:\s*false/);
    assert.match(
      source,
      /'highContrast' in raw \? Boolean\(raw\.highContrast\) : DEFAULT_ACCESSIBILITY\.highContrast/,
    );
  });
});
