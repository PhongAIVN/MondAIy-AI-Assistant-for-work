/**
 * Khóa i18n của luồng đồng bộ lịch chương trình phải khớp EN/VI.
 * Thiếu một khóa ở một locale thì giao diện hiện `undefined` cho đúng người dùng
 * đang chọn ngôn ngữ đó — lỗi chỉ lộ ra khi đổi ngôn ngữ, nên bắt ở đây.
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

describe('program sync i18n', () => {
  it('en và vi có cùng bộ khóa programSync', () => {
    const en = keyPaths(translations.en.programSync).sort();
    const vi = keyPaths(translations.vi.programSync).sort();
    assert.deepEqual(vi, en);
  });

  it('bản tiếng Anh không lẫn tiếng Việt', () => {
    assert.doesNotMatch(translations.en.programSync.title, /Đồng bộ/);
    assert.doesNotMatch(translations.en.programSync.notice, /lịch của bạn/);
  });

  it('giữ nguyên placeholder để chỗ thay số không vỡ', () => {
    for (const locale of [translations.en, translations.vi]) {
      assert.match(locale.programSync.confirm, /\{count\}/);
      assert.match(locale.programSync.resultSummary, /\{created\}/);
      assert.match(locale.programSync.resultSummary, /\{updated\}/);
    }
  });

  it('nhãn trang quản trị lịch có ở cả hai locale', () => {
    assert.ok(translations.en.admin.programEvents);
    assert.ok(translations.vi.admin.programEvents);
  });
});
