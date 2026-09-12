/**
 * Kiểm tra khóa i18n admin blog EN/VI khớp nhau.
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { translations } from '../src/i18n/translations.ts';

function keyPaths(value: unknown, prefix = ''): string[] {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    keyPaths(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe('admin blog i18n', () => {
  it('en and vi share the same admin.blogPage keys', () => {
    const en = keyPaths(translations.en.admin.blogPage).sort();
    const vi = keyPaths(translations.vi.admin.blogPage).sort();
    assert.deepEqual(vi, en);
  });

  it('english manage copy is English', () => {
    assert.match(translations.en.admin.blogPage.refreshList, /Refresh/i);
    assert.match(translations.en.admin.blogPage.newPost, /New post/i);
    assert.doesNotMatch(translations.en.admin.blogPage.subtitle, /Quản lý|Đăng bài/);
  });

  it('vietnamese manage copy is Vietnamese', () => {
    assert.match(translations.vi.admin.blogPage.refreshList, /Làm mới/);
    assert.match(translations.vi.admin.blogPage.newPost, /Bài mới/);
  });
});
