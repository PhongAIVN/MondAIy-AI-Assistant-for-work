import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

test('mobile source and manifest contain no fabricated App Store rating claim', async () => {
  const files = await Promise.all([
    readFile('app.json', 'utf8'),
    readFile('src/components/MobileProduct.tsx', 'utf8'),
    readFile('src/components/RealWorkspace.tsx', 'utf8'),
    readFile('src/components/WorkspaceMobileViews.tsx', 'utf8'),
  ]);
  const source = files.join('\n');

  assert.doesNotMatch(source, /4[.,]9\s*[•·]?\s*12K\+?/i);
  assert.doesNotMatch(source, /12K\+?.{0,40}(?:App\s*Store|đánh giá)/i);
  assert.doesNotMatch(source, /AI Productivity Assistant\s+4[.,]9/i);
});
