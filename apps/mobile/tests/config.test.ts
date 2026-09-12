import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { MOBILE_GOOGLE_CALLBACK_URI, MOBILE_WEB_APP_URL } from '../src/config.ts';

describe('mobile configuration', () => {
  it('uses the native deep link for Google OAuth handoff', () => {
    assert.equal(MOBILE_WEB_APP_URL, 'https://www.c3-app-004.io.vn');
    assert.equal(MOBILE_GOOGLE_CALLBACK_URI, 'mondaiy://auth/callback');
  });
});
