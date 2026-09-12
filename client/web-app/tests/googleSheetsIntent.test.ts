import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { extractGoogleSheetsUrl, isGoogleSheetsUrl } from '../src/lib/googleSheetsIntent.ts';
import { extractGoogleDocsUrl, isGoogleDocsUrl } from '../src/lib/googleDocsIntent.ts';

describe('google sheet chat handoff', () => {
  it('extracts a pasted sheet URL and strips sentence punctuation', () => {
    assert.equal(
      extractGoogleSheetsUrl('Đọc giúp tôi https://docs.google.com/spreadsheets/d/abc_123/edit.'),
      'https://docs.google.com/spreadsheets/d/abc_123/edit',
    );
  });

  it('rejects non-Sheets URLs before opening the connector flow', () => {
    assert.equal(isGoogleSheetsUrl('https://example.com/spreadsheets/d/abc'), false);
    assert.equal(isGoogleSheetsUrl('https://docs.google.com/spreadsheets/d/abc/edit'), true);
  });
});

describe('google docs chat handoff', () => {
  it('extracts a pasted Docs URL and strips sentence punctuation', () => {
    assert.equal(
      extractGoogleDocsUrl('Tóm tắt giúp tôi https://docs.google.com/document/d/abc_123/edit.'),
      'https://docs.google.com/document/d/abc_123/edit',
    );
  });

  it('does not confuse Sheets with Docs', () => {
    assert.equal(isGoogleDocsUrl('https://docs.google.com/spreadsheets/d/abc/edit'), false);
    assert.equal(isGoogleDocsUrl('https://docs.google.com/document/d/abc/edit'), true);
  });
});
