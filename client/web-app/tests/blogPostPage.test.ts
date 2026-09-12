/**
 * Trang đọc bài không hiện cover — cover chỉ trên card list.
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

describe('BlogPostPage', () => {
  it('does not render cover image on the reading page', () => {
    const source = readFileSync(
      join(root, 'src/pages/marketing/BlogPostPage.tsx'),
      'utf8',
    );
    assert.doesNotMatch(source, /coverImageUrl/);
    assert.doesNotMatch(source, /<img\b/);
  });
});
