/// <reference lib="dom" />
import type { DriveStep, DriverHook } from 'driver.js';
import type { TranslationKeys } from '../../i18n/translations.js';

/** Khoá tour toàn app — một hành trình xuyên nhiều trang, không phải tour riêng từng trang. */
export const APP_TOUR_ID = 'app-guided-tour';
/** Đọc lại ở AppShell sau khi Google OAuth redirect về app — biết mà tự chạy lại tour. */
export const APP_TOUR_GOOGLE_RESUME_KEY = 'mondaiy.appTour.resumeAfterGoogle';

/** localStorage key của DailyBriefingPage cho trạng thái mở/đóng At a Glance — đọc lại ở đây để quyết định có đưa bước đó vào tour hay không. */
const AT_A_GLANCE_KEY = 'mondaiy.atAGlanceOpen';

export type TourCopy = TranslationKeys['tour'];

/** Các callback tour cần để tự điều hướng trang và mở/đóng thanh tìm kiếm thay cho người dùng bấm thật. */
export interface AppTourNav {
  navigateTo: (path: string) => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
}

const POLL_INTERVAL_MS = 60;
const POLL_TIMEOUT_MS = 4000;

/**
 * Chạy side effect (điều hướng trang, mở Command Palette...) rồi tự dò DOM
 * cho tới khi phần tử của bước kế tiếp thật sự xuất hiện mới gọi moveNext() —
 * không dựa vào waitForElement/skipMissingElement có sẵn của driver.js.
 * Combo đó từng gây tour đứng hình rồi bất ngờ nhảy cách nhiều bước cùng lúc
 * (skip dây chuyền qua từng bước thiếu phần tử cho tới khi gặp bước nào có).
 * Tự poll bằng document.querySelector cho chắc; hết POLL_TIMEOUT_MS mà vẫn
 * không thấy thì vẫn gọi moveNext() để không kẹt tour vĩnh viễn.
 */
function advanceWhenReady(sideEffect: () => void, nextAnchorSelector: string): DriverHook {
  return (_element, _step, opts) => {
    sideEffect();
    const startedAt = Date.now();
    const tryAdvance = () => {
      if (typeof document === 'undefined') return;
      const found = document.querySelector(nextAnchorSelector);
      if (found || Date.now() - startedAt > POLL_TIMEOUT_MS) {
        opts.driver.moveNext();
        return;
      }
      setTimeout(tryAdvance, POLL_INTERVAL_MS);
    };
    setTimeout(tryAdvance, POLL_INTERVAL_MS);
  };
}

function navigateThenAdvance(path: string, nextAnchorSelector: string, nav: AppTourNav): DriverHook {
  return advanceWhenReady(() => nav.navigateTo(path), nextAnchorSelector);
}

/**
 * Google là điều kiện tiên quyết của use case Gmail → task → Calendar.
 * Khi chưa kết nối, nút Tiếp theo thực hiện chính CTA OAuth và không cho
 * tour đi tiếp — bấm nút connect-google thật, đánh dấu sessionStorage để
 * AppShell tự chạy lại tour sau khi Google redirect về app.
 *
 * Khi đã kết nối, tour KHÔNG nhảy thẳng sang /briefing nữa — ở lại /sources
 * để đi tiếp qua các bước giới thiệu toàn bộ nguồn (Discord/Jira/Telegram) và
 * import Google Sheets, trước khi mới rời trang. Việc điều hướng sang
 * /briefing chuyển xuống bước cuối của nhóm "sources" (xem buildAppTourSteps).
 */
function requireGoogleConnection(_nav: AppTourNav): DriverHook {
  return (element, step, opts) => {
    const connected = element?.getAttribute('data-tour-source-connected') === 'true';
    if (connected) {
      advanceWhenReady(() => {}, '[data-tour-id="sources-connected-grid"]')(element, step, opts);
      return;
    }

    try {
      sessionStorage.setItem(APP_TOUR_GOOGLE_RESUME_KEY, '1');
    } catch {
      /* private mode: OAuth vẫn tiếp tục, chỉ không tự resume tour */
    }
    document.querySelector<HTMLButtonElement>('[data-tour-action="connect-google"]')?.click();
  };
}

/** Panel đóng thì không có gì để trỏ vào — bỏ hẳn bước này thay vì để driver.js tự đoán skip hay không. */
function isAtAGlanceOpen(): boolean {
  try {
    const raw = localStorage.getItem(AT_A_GLANCE_KEY);
    return raw === null || raw !== 'false';
  } catch {
    return true;
  }
}

/**
 * Dựng chuỗi bước cho tour hướng dẫn toàn app: bắt đầu bằng kết nối Google,
 * trình bày trọn use case Gmail → tóm tắt việc → xác nhận task → Google
 * Calendar, rồi mới đi qua tìm kiếm, Tasks, Meeting Notes, Routines, Thông
 * báo, Quyền riêng tư, Cài đặt. Mọi bước "điều hướng" (đổi trang hoặc mở
 * Command Palette) tự dò DOM qua advanceWhenReady() thay vì bắt người dùng đi
 * tìm đường và thay vì dựa vào cơ chế wait/skip có sẵn của driver.js
 * (waitForElement kết hợp điều hướng SPA từng không đáng tin, kẹt tour — đã
 * bỏ hẳn, không dùng lại kể cả làm lưới an toàn phụ). Nội dung lấy từ t.tour
 * để theo đúng ngôn ngữ người dùng đang chọn (en/vi).
 */
export function buildAppTourSteps(nav: AppTourNav, t: TourCopy): DriveStep[] {
  const steps: DriveStep[] = [
    {
      popover: {
        title: t.welcomeTitle,
        description: t.welcomeDesc,
        onNextClick: navigateThenAdvance('/sources', '[data-tour-id="sources-google-primary"]', nav),
      },
    },
    {
      element: '[data-tour-id="sources-google-primary"]',
      popover: {
        title: t.googleConnectTitle,
        description: t.googleConnectDesc,
        onNextClick: requireGoogleConnection(nav),
      },
    },
    {
      element: '[data-tour-id="sources-connected-grid"]',
      popover: {
        title: t.sourcesGridTitle,
        description: t.sourcesGridDesc,
        onNextClick: advanceWhenReady(() => {}, '[data-tour-id="sources-sync-all"]'),
      },
    },
    {
      element: '[data-tour-id="sources-sync-all"]',
      popover: {
        title: t.sourcesSyncTitle,
        description: t.sourcesSyncDesc,
        onNextClick: advanceWhenReady(() => {}, '[data-tour-id="sources-google-sheets-import"]'),
      },
    },
    {
      element: '[data-tour-id="sources-google-sheets-import"]',
      popover: {
        title: t.sheetsImportTitle,
        description: t.sheetsImportDesc,
        onNextClick: navigateThenAdvance('/briefing', '[data-tour-id="briefing-compose-input"]', nav),
      },
    },
    {
      element: '[data-tour-id="briefing-compose-input"]',
      popover: {
        title: t.composeTitle,
        description: t.composeDesc,
      },
    },
    {
      element: '[data-tour-id="briefing-toolbar"]',
      popover: {
        title: t.toolbarTitle,
        description: t.toolbarDesc,
      },
    },
    {
      element: '[data-tour-id="briefing-suggestions"]',
      popover: {
        title: t.suggestionsTitle,
        description: t.suggestionsDesc,
      },
    },
  ];

  if (isAtAGlanceOpen()) {
    steps.push({
      element: '[data-tour-id="briefing-glance-panel"]',
      popover: {
        title: t.glanceTitle,
        description: t.glanceDesc,
      },
    });
  }

  steps.push(
    {
      element: '[data-tour-id="sidebar-search"]',
      popover: {
        title: t.searchTitle,
        description: t.searchDesc,
        onNextClick: advanceWhenReady(
          () => nav.openCommandPalette(),
          '[data-tour-id="command-palette-input"]',
        ),
      },
    },
    {
      element: '[data-tour-id="command-palette-input"]',
      popover: {
        title: t.paletteInputTitle,
        description: t.paletteInputDesc,
      },
    },
    {
      element: '[data-tour-id="command-palette-list"]',
      popover: {
        title: t.paletteListTitle,
        description: t.paletteListDesc,
        onNextClick: advanceWhenReady(() => {
          nav.closeCommandPalette();
          nav.navigateTo('/tasks');
        }, '[data-tour-id="tasks-inbox-list"]'),
      },
    },
    {
      element: '[data-tour-id="tasks-inbox-list"]',
      popover: {
        title: t.tasksInboxTitle,
        description: t.tasksInboxDesc,
      },
    },
    {
      element: '[data-tour-id="tasks-calendar-grid"]',
      popover: {
        title: t.tasksCalendarTitle,
        description: t.tasksCalendarDesc,
        onNextClick: navigateThenAdvance('/meeting-notes', '[data-tour-id="meeting-notes-header"]', nav),
      },
    },
    {
      element: '[data-tour-id="meeting-notes-header"]',
      popover: {
        title: t.meetingNotesTitle,
        description: t.meetingNotesDesc,
        onNextClick: navigateThenAdvance('/routines', '[data-tour-id="routines-header"]', nav),
      },
    },
    {
      element: '[data-tour-id="routines-header"]',
      popover: {
        title: t.routinesTitle,
        description: t.routinesDesc,
        // Bấm thật nút "Routine mới" để mở modal tạo routine, rồi mới đi tiếp —
        // giống pattern search → Command Palette bên trên.
        onNextClick: advanceWhenReady(() => {
          document.querySelector<HTMLButtonElement>('[data-tour-id="routines-new-button"]')?.click();
        }, '[data-tour-id="routines-create-modal"]'),
      },
    },
    {
      element: '[data-tour-id="routines-create-modal"]',
      popover: {
        title: t.routinesCreateTitle,
        description: t.routinesCreateDesc,
        // Đóng modal thật (bấm nút X) trước khi rời trang, rồi mới điều hướng
        // sang /notifications — không để modal còn mở đè lên trang kế tiếp.
        onNextClick: advanceWhenReady(() => {
          document.querySelector<HTMLButtonElement>('[data-tour-id="routines-modal-close"]')?.click();
          nav.navigateTo('/notifications');
        }, '[data-tour-id="notifications-list"]'),
      },
    },
    {
      element: '[data-tour-id="notifications-list"]',
      popover: {
        title: t.notificationsTitle,
        description: t.notificationsDesc,
        // /data-privacy tự redirect sang /data-privacy/memory qua useEffect
        // (ADVANCED_TABS_ENABLED=false) — trỏ thẳng route đích, tránh 2 lần
        // điều hướng chồng nhau ngay lúc đang dò phần tử kế tiếp.
        onNextClick: navigateThenAdvance('/data-privacy/memory', '[data-tour-id="privacy-memory-summary"]', nav),
      },
    },
    {
      element: '[data-tour-id="privacy-memory-summary"]',
      popover: {
        title: t.privacyTitle,
        description: t.privacyDesc,
        onNextClick: advanceWhenReady(() => {}, '[data-tour-id="privacy-memory-pending"]'),
      },
    },
    {
      // Chỉ tồn tại khi có candidate đang chờ xác nhận/từ chối; nếu tài khoản
      // demo không có candidate nào, advanceWhenReady tự timeout rồi đi tiếp
      // — không kẹt tour.
      element: '[data-tour-id="privacy-memory-pending"]',
      popover: {
        title: t.privacyPendingTitle,
        description: t.privacyPendingDesc,
        onNextClick: advanceWhenReady(() => {}, '[data-tour-id="privacy-memory-canonical"]'),
      },
    },
    {
      element: '[data-tour-id="privacy-memory-canonical"]',
      popover: {
        title: t.privacyCanonicalTitle,
        description: t.privacyCanonicalDesc,
        onNextClick: navigateThenAdvance('/settings', '[data-tour-id="settings-tabs"]', nav),
      },
    },
    {
      element: '[data-tour-id="settings-tabs"]',
      popover: {
        title: t.settingsTitle,
        description: t.settingsDesc,
      },
    },
    {
      element: '[data-tour-id="sidebar-profile-button"]',
      popover: {
        title: t.finishTitle,
        description: t.finishDesc,
      },
    },
  );

  return steps;
}
