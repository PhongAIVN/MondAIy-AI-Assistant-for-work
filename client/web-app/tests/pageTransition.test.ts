/**
 * Kiểm tra gom khóa chuyển trang, stagger targets và wiring motion.
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { getPageTransitionKey } from '../src/lib/pageTransitionKey.ts';
import { collectStaggerTargets, PAGE_MOTION } from '../src/lib/pageMotion.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

describe('page transitions', () => {
  it('groups nested briefing and privacy routes', () => {
    assert.equal(getPageTransitionKey('/briefing'), '/briefing');
    assert.equal(getPageTransitionKey('/briefing/conversation/abc'), '/briefing');
    assert.equal(getPageTransitionKey('/data-privacy/memory'), '/data-privacy');
    assert.equal(getPageTransitionKey('/tasks'), '/tasks');
  });

  it('groups admin detail under section', () => {
    assert.equal(getPageTransitionKey('/admin'), '/admin');
    assert.equal(getPageTransitionKey('/admin/users'), '/admin/users');
    assert.equal(getPageTransitionKey('/admin/programs/42'), '/admin/programs');
  });

  it('uses slower timings so motion is noticeable', () => {
    assert.ok(PAGE_MOTION.enterMs >= 400);
    assert.ok(PAGE_MOTION.exitMs >= 280);
    assert.ok(PAGE_MOTION.staggerStepMs >= 80);
    assert.ok(PAGE_MOTION.staggerItemMs >= 480);
  });

  it('collects nested section targets through a single wrapper', () => {
    const a = { tagName: 'SECTION', children: [] as [] };
    const b = { tagName: 'SECTION', children: [] as [] };
    const c = { tagName: 'SECTION', children: [] as [] };
    const page = { tagName: 'DIV', children: [a, b, c] };
    const host = { tagName: 'DIV', children: [page] };

    const targets = collectStaggerTargets(host);
    assert.equal(targets.length, 3);
    assert.equal(targets[0], a);
    assert.equal(targets[2], c);
  });

  it('wires PageTransition into app shells', () => {
    const appShell = readFileSync(join(root, 'src/components/layout/AppShell.tsx'), 'utf8');
    const adminShell = readFileSync(join(root, 'src/components/layout/AdminShell.tsx'), 'utf8');
    const marketing = readFileSync(join(root, 'src/components/layout/MarketingLayout.tsx'), 'utf8');
    const sidebar = readFileSync(join(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
    const pageTransition = readFileSync(join(root, 'src/components/layout/PageTransition.tsx'), 'utf8');

    assert.match(appShell, /PageTransition/);
    assert.match(adminShell, /PageTransition/);
    assert.match(marketing, /PageTransition/);
    assert.match(sidebar, /layoutId="app-nav-active"/);
    assert.match(adminShell, /layoutId="admin-nav-active"/);
    assert.match(pageTransition, /playStaggerEnter/);
    assert.match(pageTransition, /initial=\{false\}/);
    assert.doesNotMatch(pageTransition, /initial=\{\{\s*opacity:\s*0/);
  });
});
