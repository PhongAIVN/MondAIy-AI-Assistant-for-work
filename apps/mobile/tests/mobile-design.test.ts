import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { describe, it } from 'node:test';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MOBILE_APP_SCREENS, MOBILE_CHAT_SUGGESTIONS, MOBILE_HOME_VIEWS, MOBILE_PRODUCT_STATES } from '../src/mobileDesign.ts';

describe('native mobile design contract', () => {
  it('covers the agreed primary mobile screens', () => {
    for (const screen of ['onboarding', 'authentication', 'home', 'discover', 'content-detail', 'search', 'notifications', 'profile', 'settings']) {
      assert.ok(MOBILE_APP_SCREENS.includes(screen as typeof MOBILE_APP_SCREENS[number]));
    }
  });

  it('declares every non-happy-path product state', () => {
    assert.deepEqual(MOBILE_PRODUCT_STATES, ['loading', 'empty', 'error', 'success']);
  });

  it('keeps task, calendar and guided chat entry points intentional', () => {
    assert.deepEqual(MOBILE_HOME_VIEWS, ['tasks', 'calendar']);
    assert.ok(MOBILE_CHAT_SUGGESTIONS.length >= 3);
  });

  it('keeps the selected mascot asset available to Metro', () => {
    assert.equal(existsSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'monbthvippro (1).png')), true);
  });
});
