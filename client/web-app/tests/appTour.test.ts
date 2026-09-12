/**
 * Kiểm tra tour toàn app: mọi data-tour-id mà buildAppTourSteps() tham chiếu
 * thật sự tồn tại trong file nguồn tương ứng, và lối vào (menu tài khoản +
 * AppShell) đã được gắn dây — tour không âm thầm rỗng khi ai đó đổi UI.
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import type { DriveStep } from 'driver.js';
import { buildAppTourSteps } from '../src/lib/tours/appTour.ts';
import { translations } from '../src/i18n/translations.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const ANCHOR_TO_FILE: Record<string, string> = {
  'briefing-compose-input': 'src/pages/DailyBriefingPage.tsx',
  'briefing-toolbar': 'src/pages/DailyBriefingPage.tsx',
  'briefing-suggestions': 'src/pages/DailyBriefingPage.tsx',
  'briefing-glance-panel': 'src/pages/DailyBriefingPage.tsx',
  'sidebar-search': 'src/components/layout/Sidebar.tsx',
  'sidebar-profile-button': 'src/components/layout/Sidebar.tsx',
  'command-palette-input': 'src/components/ui/CommandPalette.tsx',
  'command-palette-list': 'src/components/ui/CommandPalette.tsx',
  'tasks-calendar-grid': 'src/pages/TasksPage.tsx',
  'tasks-inbox-list': 'src/pages/TasksPage.tsx',
  'meeting-notes-header': 'src/pages/MeetingNotesPage.tsx',
  'routines-header': 'src/pages/RoutinesPage.tsx',
  'routines-create-modal': 'src/pages/RoutinesPage.tsx',
  'sources-google-primary': 'src/pages/SourceLibraryPage.tsx',
  'sources-connected-grid': 'src/pages/SourceLibraryPage.tsx',
  'sources-sync-all': 'src/pages/SourceLibraryPage.tsx',
  'sources-google-sheets-import': 'src/pages/SourceLibraryPage.tsx',
  'notifications-list': 'src/pages/NotificationsPage.tsx',
  'privacy-memory-summary': 'src/components/privacy/MemoryInspectorTab.tsx',
  'privacy-memory-pending': 'src/components/privacy/MemoryInspectorTab.tsx',
  'privacy-memory-canonical': 'src/components/privacy/MemoryInspectorTab.tsx',
  'settings-tabs': 'src/pages/SettingsPage.tsx',
};

function stepAnchor(step: DriveStep): string | null {
  const match = /data-tour-id="([^"]+)"/.exec(String(step.element ?? ''));
  return match ? match[1] : null;
}

describe('app tour', () => {
  const noopNav = { navigateTo: () => {}, openCommandPalette: () => {}, closeCommandPalette: () => {} };
  const steps = buildAppTourSteps(noopNav, translations.en.tour);

  it('has at least one intro step without a highlighted element', () => {
    assert.ok(steps.some((step) => !step.element));
  });

  it('every anchored step targets a known page/component', () => {
    for (const step of steps) {
      const anchor = stepAnchor(step);
      if (!anchor) continue;
      assert.ok(anchor in ANCHOR_TO_FILE, `anchor "${anchor}" không có trong ANCHOR_TO_FILE — cập nhật test`);
    }
  });

  for (const [anchor, file] of Object.entries(ANCHOR_TO_FILE)) {
    it(`"${anchor}" exists in ${file}`, () => {
      const source = readFileSync(join(root, file), 'utf8');
      assert.ok(source.includes(`data-tour-id="${anchor}"`), `thiếu data-tour-id="${anchor}" trong ${file}`);
    });
  }

  it('wires AppShell to start the app tour via useOnboardingTour + APP_TOUR_ID', () => {
    const appShell = readFileSync(join(root, 'src/components/layout/AppShell.tsx'), 'utf8');
    assert.match(appShell, /useOnboardingTour\(APP_TOUR_ID\)/);
    assert.match(appShell, /buildAppTourSteps/);
    assert.match(appShell, /APP_TOUR_GOOGLE_RESUME_KEY/);
  });

  it('auto-starts only right when onboardingDismissed flips to true this session — not from a stale hasSeenTour flag', () => {
    const appShell = readFileSync(join(root, 'src/components/layout/AppShell.tsx'), 'utf8');
    assert.match(appShell, /wasOnboardingDismissed/);
    assert.match(appShell, /justFinishedOnboarding/);
    assert.doesNotMatch(
      appShell,
      /hasSeenTour\(/,
      'auto-start không nên gọi hasSeenTour() để quyết định — user cũ có sẵn cũng có cờ này = false',
    );
  });

  it('wires the account menu (Sidebar) to request the tour, not a visible page button', () => {
    const sidebar = readFileSync(join(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
    assert.match(sidebar, /requestAppTour/);

    // Không còn nút "Xem hướng dẫn" lộ liễu trên từng trang.
    for (const page of [
      'src/pages/DailyBriefingPage.tsx',
      'src/pages/TasksPage.tsx',
      'src/pages/SourceLibraryPage.tsx',
      'src/pages/NotificationsPage.tsx',
      'src/pages/DataPrivacyPage.tsx',
      'src/pages/SettingsPage.tsx',
    ]) {
      const source = readFileSync(join(root, page), 'utf8');
      assert.doesNotMatch(source, /TourTriggerButton/, `${page} không nên còn nút tour lộ trên trang`);
    }
  });

  it('has matching en/vi tour copy — no step falls back to hardcoded Vietnamese in English mode', () => {
    const enKeys = Object.keys(translations.en.tour).sort();
    const viKeys = Object.keys(translations.vi.tour).sort();
    assert.deepEqual(viKeys, enKeys);

    for (const key of enKeys) {
      assert.ok(translations.en.tour[key as keyof typeof translations.en.tour].trim().length > 0, `en.tour.${key} rỗng`);
      assert.ok(translations.vi.tour[key as keyof typeof translations.vi.tour].trim().length > 0, `vi.tour.${key} rỗng`);
    }
  });

  it('renders every popover title/description straight from t.tour in both languages', () => {
    for (const lang of ['en', 'vi'] as const) {
      const langSteps = buildAppTourSteps(noopNav, translations[lang].tour);
      for (const step of langSteps) {
        assert.ok(step.popover?.title, `thiếu title (${lang})`);
        assert.ok(step.popover?.description, `thiếu description (${lang})`);
      }
    }
  });
});
