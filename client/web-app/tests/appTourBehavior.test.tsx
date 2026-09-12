// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';
import { APP_TOUR_GOOGLE_RESUME_KEY, buildAppTourSteps } from '../src/lib/tours/appTour';
import { translations } from '../src/i18n/translations';

const tourCopy = translations.en.tour;

/** driver.js truyền (element, step, opts) vào onNextClick — chỉ opts.driver là quan trọng ở đây. */
function fakeOpts() {
  return { config: {}, state: {}, driver: { moveNext: vi.fn() }, index: 0 } as any;
}

/** Tạo sẵn phần tử đích trong DOM, mô phỏng trang đã render xong sau điều hướng. */
function mountAnchor(anchor: string): HTMLElement {
  const el = document.createElement('div');
  el.setAttribute('data-tour-id', anchor);
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.innerHTML = '';
  sessionStorage.clear();
  vi.useRealTimers();
});

describe('buildAppTourSteps', () => {
  it('navigates to Google sources before showing any briefing feature', async () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const intro = steps[0]!;
    const opts = fakeOpts();

    intro.popover!.onNextClick!(undefined as any, intro, opts);
    expect(nav.navigateTo).toHaveBeenCalledWith('/sources');
    expect(opts.driver.moveNext).not.toHaveBeenCalled();

    mountAnchor('sources-google-primary');
    await vi.waitFor(() => expect(opts.driver.moveNext).toHaveBeenCalledTimes(1));
  });

  it('blocks the tour and starts Google OAuth while the preferred source is disconnected', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const googleStep = steps.find((s) => String(s.element) === '[data-tour-id="sources-google-primary"]')!;
    const googleCard = mountAnchor('sources-google-primary');
    googleCard.setAttribute('data-tour-source-connected', 'false');
    const connect = document.createElement('button');
    connect.setAttribute('data-tour-action', 'connect-google');
    const click = vi.spyOn(connect, 'click');
    googleCard.appendChild(connect);
    const opts = fakeOpts();

    googleStep.popover!.onNextClick!(googleCard, googleStep, opts);

    expect(click).toHaveBeenCalledTimes(1);
    expect(opts.driver.moveNext).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(APP_TOUR_GOOGLE_RESUME_KEY)).toBe('1');
  });

  it('stays on /sources to show the full source grid once Google is already connected — does not jump to /briefing yet', async () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const googleStep = steps.find((s) => String(s.element) === '[data-tour-id="sources-google-primary"]')!;
    const googleCard = mountAnchor('sources-google-primary');
    googleCard.setAttribute('data-tour-source-connected', 'true');
    const opts = fakeOpts();

    googleStep.popover!.onNextClick!(googleCard, googleStep, opts);

    expect(nav.navigateTo).not.toHaveBeenCalled();
    expect(opts.driver.moveNext).not.toHaveBeenCalled();
    mountAnchor('sources-connected-grid');
    await vi.waitFor(() => expect(opts.driver.moveNext).toHaveBeenCalledTimes(1));
    expect(sessionStorage.getItem(APP_TOUR_GOOGLE_RESUME_KEY)).toBeNull();
  });

  it('walks Discord/Jira/Telegram grid -> sync-all -> Google Sheets import, then finally reaches /briefing', async () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const byAnchor = (anchor: string) => steps.find((s) => String(s.element) === `[data-tour-id="${anchor}"]`)!;
    const fire = async (step: (typeof steps)[number], nextAnchor: string) => {
      step.popover!.onNextClick!(undefined as any, step, fakeOpts());
      mountAnchor(nextAnchor);
      await vi.waitFor(() => expect(document.querySelector(`[data-tour-id="${nextAnchor}"]`)).toBeTruthy());
    };

    await fire(byAnchor('sources-connected-grid'), 'sources-sync-all');
    await fire(byAnchor('sources-sync-all'), 'sources-google-sheets-import');

    const sheetsStep = byAnchor('sources-google-sheets-import');
    const opts = fakeOpts();
    sheetsStep.popover!.onNextClick!(undefined as any, sheetsStep, opts);
    expect(nav.navigateTo).toHaveBeenCalledWith('/briefing');
    expect(opts.driver.moveNext).not.toHaveBeenCalled();
    mountAnchor('briefing-compose-input');
    await vi.waitFor(() => expect(opts.driver.moveNext).toHaveBeenCalledTimes(1));
  });

  it('opens the command palette and advances when leaving the search step', async () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const searchStep = steps.find((s) => String(s.element) === '[data-tour-id="sidebar-search"]')!;
    const opts = fakeOpts();

    searchStep.popover!.onNextClick!(undefined as any, searchStep, opts);

    expect(nav.openCommandPalette).toHaveBeenCalledTimes(1);
    expect(nav.navigateTo).not.toHaveBeenCalled();
    // Không gọi ngay — cũng tự dò DOM như mọi bước điều hướng khác.
    expect(opts.driver.moveNext).not.toHaveBeenCalled();

    mountAnchor('command-palette-input');
    await vi.waitFor(() => expect(opts.driver.moveNext).toHaveBeenCalledTimes(1));
  });

  it('closes the palette, navigates to /tasks, and advances once the next page renders its anchor', async () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const resultsStep = steps.find((s) => String(s.element) === '[data-tour-id="command-palette-list"]')!;
    const opts = fakeOpts();

    resultsStep.popover!.onNextClick!(undefined as any, resultsStep, opts);

    expect(nav.closeCommandPalette).toHaveBeenCalledTimes(1);
    expect(nav.navigateTo).toHaveBeenCalledWith('/tasks');
    // moveNext() không gọi ngay — nó tự poll DOM chờ trang mới render xong.
    expect(opts.driver.moveNext).not.toHaveBeenCalled();

    // Mô phỏng trang /tasks vừa render xong anchor của bước kế tiếp.
    mountAnchor('tasks-inbox-list');
    await vi.waitFor(() => expect(opts.driver.moveNext).toHaveBeenCalledTimes(1));
  });

  it('never calls moveNext() if the next anchor never appears — until the poll times out', async () => {
    vi.useFakeTimers();
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const resultsStep = steps.find((s) => String(s.element) === '[data-tour-id="command-palette-list"]')!;
    const opts = fakeOpts();

    resultsStep.popover!.onNextClick!(undefined as any, resultsStep, opts);
    await vi.advanceTimersByTimeAsync(3000);
    expect(opts.driver.moveNext).not.toHaveBeenCalled();

    // Không thấy anchor sau 4s — vẫn phải nhả moveNext(), không kẹt vĩnh viễn.
    await vi.advanceTimersByTimeAsync(1500);
    expect(opts.driver.moveNext).toHaveBeenCalledTimes(1);
  });

  it('walks through the remaining pages in order: tasks -> meeting notes -> routines -> create-routine modal -> notifications -> privacy (pending -> canonical) -> settings', async () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);

    const byAnchor = (anchor: string) =>
      steps.find((s) => String(s.element) === `[data-tour-id="${anchor}"]`)!;
    const fire = async (step: (typeof steps)[number], nextAnchor: string) => {
      step.popover!.onNextClick!(undefined as any, step, fakeOpts());
      mountAnchor(nextAnchor);
      await vi.waitFor(() => expect(document.querySelector(`[data-tour-id="${nextAnchor}"]`)).toBeTruthy());
    };

    await fire(byAnchor('command-palette-list'), 'tasks-inbox-list');
    await fire(byAnchor('tasks-calendar-grid'), 'meeting-notes-header');
    await fire(byAnchor('meeting-notes-header'), 'routines-header');
    await fire(byAnchor('routines-header'), 'routines-create-modal');
    await fire(byAnchor('routines-create-modal'), 'notifications-list');
    await fire(byAnchor('notifications-list'), 'privacy-memory-summary');
    await fire(byAnchor('privacy-memory-summary'), 'privacy-memory-pending');
    await fire(byAnchor('privacy-memory-pending'), 'privacy-memory-canonical');
    await fire(byAnchor('privacy-memory-canonical'), 'settings-tabs');

    expect(nav.navigateTo.mock.calls.map((call) => call[0])).toEqual([
      '/tasks',
      '/meeting-notes',
      '/routines',
      // routines-header -> routines-create-modal không điều hướng trang, chỉ
      // bấm thật nút "Routine mới" để mở modal ngay tại /routines.
      '/notifications',
      // Route thật /data-privacy/memory thẳng luôn — /data-privacy tự
      // redirect sang đây qua useEffect, trỏ thẳng tránh double-navigate.
      '/data-privacy/memory',
      // privacy-memory-summary -> pending -> canonical không điều hướng
      // trang, chỉ đi tiếp trong cùng /data-privacy/memory.
      '/settings',
    ]);
  });

  it('clicks the real "new routine" button to open the create-routine modal, then closes it before leaving the page', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const routinesStep = steps.find((s) => String(s.element) === '[data-tour-id="routines-header"]')!;

    const newRoutineButton = document.createElement('button');
    newRoutineButton.setAttribute('data-tour-id', 'routines-new-button');
    const clickNewRoutine = vi.spyOn(newRoutineButton, 'click');
    document.body.appendChild(newRoutineButton);

    const opts = fakeOpts();
    routinesStep.popover!.onNextClick!(undefined as any, routinesStep, opts);
    expect(clickNewRoutine).toHaveBeenCalledTimes(1);
    expect(nav.navigateTo).not.toHaveBeenCalled();

    const modal = mountAnchor('routines-create-modal');
    const closeButton = document.createElement('button');
    closeButton.setAttribute('data-tour-id', 'routines-modal-close');
    const clickClose = vi.spyOn(closeButton, 'click');
    modal.appendChild(closeButton);

    const modalStep = steps.find((s) => String(s.element) === '[data-tour-id="routines-create-modal"]')!;
    modalStep.popover!.onNextClick!(undefined as any, modalStep, fakeOpts());
    expect(clickClose).toHaveBeenCalledTimes(1);
    expect(nav.navigateTo).toHaveBeenCalledWith('/notifications');
  });

  it('does not attach onNextClick to steps meant to be read, not to trigger navigation', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const readOnlyAnchors = [
      'briefing-compose-input',
      'briefing-toolbar',
      'briefing-suggestions',
      'briefing-glance-panel',
      'tasks-inbox-list',
      'settings-tabs',
      'sidebar-profile-button',
    ];

    for (const anchor of readOnlyAnchors) {
      const step = steps.find((s) => String(s.element) === `[data-tour-id="${anchor}"]`);
      expect(step?.popover?.onNextClick).toBeUndefined();
    }
  });

  it('includes the At a Glance step when the panel is open (default), drops it when the user closed it', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };

    localStorage.removeItem('mondaiy.atAGlanceOpen');
    const openSteps = buildAppTourSteps(nav, tourCopy);
    expect(openSteps.some((s) => String(s.element) === '[data-tour-id="briefing-glance-panel"]')).toBe(true);

    localStorage.setItem('mondaiy.atAGlanceOpen', 'false');
    const closedSteps = buildAppTourSteps(nav, tourCopy);
    expect(closedSteps.some((s) => String(s.element) === '[data-tour-id="briefing-glance-panel"]')).toBe(false);

    localStorage.removeItem('mondaiy.atAGlanceOpen');
  });

  it('places Google connection before the Gmail summary composer and task review', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const anchors = steps.map((s) => (s.element ? String(s.element) : '(intro)'));

    const googleIdx = anchors.indexOf('[data-tour-id="sources-google-primary"]');
    const composeIdx = anchors.indexOf('[data-tour-id="briefing-compose-input"]');
    const inboxIdx = anchors.indexOf('[data-tour-id="tasks-inbox-list"]');

    expect(googleIdx).toBeGreaterThan(-1);
    expect(composeIdx).toBeGreaterThan(-1);
    expect(inboxIdx).toBeGreaterThan(-1);
    expect(googleIdx).toBeLessThan(composeIdx);
    expect(composeIdx).toBeLessThan(inboxIdx);
  });

  it('uses the given locale copy for title/description, e.g. Vietnamese', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, translations.vi.tour);
    const composeStep = steps.find((s) => String(s.element) === '[data-tour-id="briefing-compose-input"]')!;

    expect(composeStep.popover!.title).toBe(translations.vi.tour.composeTitle);
    expect(composeStep.popover!.description).toBe(translations.vi.tour.composeDesc);
  });

  it('covers Meeting Notes and Routines between Tasks and Notifications', () => {
    const nav = { navigateTo: vi.fn(), openCommandPalette: vi.fn(), closeCommandPalette: vi.fn() };
    const steps = buildAppTourSteps(nav, tourCopy);
    const anchors = steps.map((s) => (s.element ? String(s.element) : '(intro)'));

    const tasksIdx = anchors.indexOf('[data-tour-id="tasks-calendar-grid"]');
    const meetingIdx = anchors.indexOf('[data-tour-id="meeting-notes-header"]');
    const routinesIdx = anchors.indexOf('[data-tour-id="routines-header"]');
    const notificationsIdx = anchors.indexOf('[data-tour-id="notifications-list"]');

    expect(tasksIdx).toBeLessThan(meetingIdx);
    expect(meetingIdx).toBeLessThan(routinesIdx);
    expect(routinesIdx).toBeLessThan(notificationsIdx);

    const meetingStep = steps[meetingIdx]!;
    const routinesStep = steps[routinesIdx]!;
    expect(meetingStep.popover!.title).toBe(tourCopy.meetingNotesTitle);
    expect(meetingStep.popover!.description).toBe(tourCopy.meetingNotesDesc);
    expect(routinesStep.popover!.title).toBe(tourCopy.routinesTitle);
    expect(routinesStep.popover!.description).toBe(tourCopy.routinesDesc);
  });
});
