import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { isPrimaryGmailSource, loadedSourceListState } from '../src/lib/sourceListState.ts';

describe('source list state', () => {
  it('keeps live sources and partial Calendar warnings together', () => {
    const state = loadedSourceListState({
      sources: [{ id: 'INBOX', name: 'Gmail · Hộp thư chính' }],
      warnings: ['Calendar: token cần cấp lại calendar.readonly'],
    });

    assert.equal(state.loading, false);
    assert.equal(state.items[0]?.id, 'INBOX');
    assert.deepEqual(state.warnings, ['Calendar: token cần cấp lại calendar.readonly']);
  });

  it('accepts namespaced and legacy primary Gmail source IDs', () => {
    assert.equal(isPrimaryGmailSource('gmail:INBOX'), true);
    assert.equal(isPrimaryGmailSource('INBOX'), true);
    assert.equal(isPrimaryGmailSource('calendar:primary'), false);
  });
});
