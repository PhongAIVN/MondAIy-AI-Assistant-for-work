import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Sidebar, SIDEBAR_WIDTH } from './Sidebar';
import { TopBar } from './TopBar';
import { PageTransition } from './PageTransition';
import { ToastContainer } from '../ui/Toast';
import { TaskReviewModal } from '../briefing/TaskReviewModal';
import { SourceDetailModal } from '../briefing/SourceDetailModal';
import { ConflictCompareModal } from '../briefing/ConflictCompareModal';
import { CalendarReviewModal } from '../briefing/CalendarReviewModal';
import { SourceLibraryModal } from '../briefing/SourceLibraryModal';
import { CommandPalette } from '../ui/CommandPalette';
import { InstallPrompt } from '../pwa/InstallPrompt';
import { AppUpdateNotice } from '../pwa/AppUpdateNotice';
import { usePreferencesStore, applyThemeToDOM, applyPaletteToDOM, applyAccessibilityToDOM } from '../../stores/usePreferencesStore';
import { useAuthStore } from '../../stores/useAuthStore';
import { usePipelineRunStore } from '../../stores/usePipelineRunStore';
import { useAppTourStore } from '../../stores/useAppTourStore';
import { useProductRating } from '../../hooks/useProductRating';
import { ProductRatingModal } from '../ui/ProductRatingModal';
import { useOnboardingTour } from '../../hooks/useOnboardingTour';
import { APP_TOUR_GOOGLE_RESUME_KEY, APP_TOUR_ID, buildAppTourSteps } from '../../lib/tours/appTour';
import { useTranslation } from '../../i18n/useTranslation';
import { MobileBottomNav } from './MobileBottomNav';
import { MaintenanceBanner } from '../system/MaintenanceBanner';

const SIDEBAR_WIDTH_KEY = 'mondaiy.sidebarWidth';
const PEEK_LOCK_MS = 300;
const PEEK_OPEN_DELAY_MS = 180;

function clampSidebarWidth(width: number): number {
  return Math.min(SIDEBAR_WIDTH.max, Math.max(SIDEBAR_WIDTH.min, Math.round(width)));
}

function readStoredSidebarWidth(): number {
  try {
    const raw = localStorage.getItem(SIDEBAR_WIDTH_KEY);
    if (!raw) return SIDEBAR_WIDTH.default;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return SIDEBAR_WIDTH.default;
    return clampSidebarWidth(parsed);
  } catch {
    return SIDEBAR_WIDTH.default;
  }
}

export const AppShell: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarPeek, setSidebarPeek] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth);
  const peekLockedUntil = useRef(0);
  const peekOpenTimer = useRef<number | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  const theme = usePreferencesStore((s) => s.theme);
  const palette = usePreferencesStore((s) => s.palette);
  const accessibility = usePreferencesStore((s) => s.accessibility);
  const onboardingDismissed = usePreferencesStore((s) => s.onboardingDismissed);
  const user = useAuthStore((s) => s.user);
  const loadConnections = usePipelineRunStore((s) => s.loadConnections);
  const connections = usePipelineRunStore((s) => s.connections);
  const { prompt, submit, closePrompt } = useProductRating();
  const tourPending = useAppTourStore((s) => s.pending);
  const clearAppTourRequest = useAppTourStore((s) => s.clearAppTourRequest);
  const { startTour } = useOnboardingTour(APP_TOUR_ID);
  const { t } = useTranslation();

  // User mới chưa xong setup: chỉ hiện onboarding, không mở workspace.
  const setupOnly =
    Boolean(user) &&
    user?.role !== 'admin' &&
    !onboardingDismissed &&
    location.pathname === '/onboarding';

  const handleSidebarWidthChange = useCallback((width: number) => {
    const next = clampSidebarWidth(width);
    setSidebarWidth(next);
    try {
      localStorage.setItem(SIDEBAR_WIDTH_KEY, String(next));
    } catch {
      /* ignore quota / private mode */
    }
  }, []);

  const toggleSidebarCollapse = useCallback(() => {
    if (peekOpenTimer.current !== null) {
      window.clearTimeout(peekOpenTimer.current);
      peekOpenTimer.current = null;
    }
    setSidebarCollapsed((prev) => {
      if (prev) {
        setSidebarPeek(false);
        return false;
      }
      setSidebarPeek(false);
      peekLockedUntil.current = Date.now() + PEEK_LOCK_MS;
      return true;
    });
  }, []);

  const handleSidebarMouseEnter = useCallback(() => {
    if (!sidebarCollapsed) return;
    if (Date.now() < peekLockedUntil.current) return;
    if (peekOpenTimer.current !== null) window.clearTimeout(peekOpenTimer.current);
    peekOpenTimer.current = window.setTimeout(() => {
      setSidebarPeek(true);
      peekOpenTimer.current = null;
    }, PEEK_OPEN_DELAY_MS);
  }, [sidebarCollapsed]);

  const handleSidebarMouseLeave = useCallback(() => {
    if (peekOpenTimer.current !== null) {
      window.clearTimeout(peekOpenTimer.current);
      peekOpenTimer.current = null;
    }
    setSidebarPeek(false);
  }, []);

  useEffect(() => () => {
    if (peekOpenTimer.current !== null) window.clearTimeout(peekOpenTimer.current);
  }, []);

  useEffect(() => {
    applyThemeToDOM(theme);
    applyPaletteToDOM(palette);
    applyAccessibilityToDOM(accessibility);
  }, [theme, palette, accessibility]);

  // Sidebar và Source Library đều hiển thị số nguồn thật, nên nạp một lần ở
  // shell thay vì để mỗi trang tự gọi.
  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  // AppShell là nơi duy nhất vừa điều hướng trang vừa điều khiển Command
  // Palette, nên tour toàn app (nhiều trang) chỉ có thể khởi động từ đây.
  // Nội dung + nhãn nút lấy theo t.tour để theo đúng ngôn ngữ đang chọn.
  const startAppTour = useCallback(() => {
    const steps = buildAppTourSteps(
      {
        navigateTo: (path) => navigate(path),
        openCommandPalette: () => setCommandPaletteOpen(true),
        closeCommandPalette: () => setCommandPaletteOpen(false),
      },
      t.tour,
    );
    startTour(steps, {
      nextBtnText: t.tour.nextBtn,
      prevBtnText: t.tour.previousBtn,
      doneBtnText: t.tour.doneBtn,
      progressText: t.tour.progressText,
    });
  }, [navigate, startTour, t.tour]);

  // Tour bắt buộc Google sẽ rời app trong vòng OAuth. Khi redirect về và
  // store xác nhận Google đã kết nối, tự chạy lại tour để người dùng
  // tiếp tục use case Gmail → task → Calendar thay vì bị bỏ giữa chừng.
  useEffect(() => {
    const googleConnected = connections.some((connection) => connection.provider === 'google' && connection.connected);
    if (!googleConnected) return;

    try {
      if (window.sessionStorage.getItem(APP_TOUR_GOOGLE_RESUME_KEY) !== '1') return;
      window.sessionStorage.removeItem(APP_TOUR_GOOGLE_RESUME_KEY);
    } catch {
      return;
    }

    const timer = window.setTimeout(() => startAppTour(), 600);
    return () => window.clearTimeout(timer);
  }, [connections, startAppTour]);

  // Sidebar (menu tài khoản) chỉ phát yêu cầu — AppShell thật sự chạy tour.
  useEffect(() => {
    if (!tourPending) return;
    startAppTour();
    clearAppTourRequest();
  }, [tourPending, startAppTour, clearAppTourRequest]);

  // Chỉ tự chạy tour đúng khoảnh khắc onboardingDismissed chuyển false → true
  // trong phiên này — tức vừa hoàn tất wizard onboarding, người dùng mới thật
  // sự. Không dựa vào hasSeenTour: user cũ có sẵn từ trước khi tính năng này
  // ra mắt cũng có hasSeenTour=false, sẽ bị tự chạy oan nếu dùng cờ đó.
  // User cũ chỉ xem tour qua menu tài khoản (requestAppTour ở trên).
  const wasOnboardingDismissed = useRef(onboardingDismissed);
  useEffect(() => {
    const justFinishedOnboarding = !wasOnboardingDismissed.current && onboardingDismissed;
    wasOnboardingDismissed.current = onboardingDismissed;
    if (!justFinishedOnboarding) return;
    const timer = window.setTimeout(() => startAppTour(), 600);
    return () => window.clearTimeout(timer);
  }, [onboardingDismissed, startAppTour]);

  // Global Ctrl+K / Cmd+K, Ctrl+B / Cmd+B và Ctrl+Shift+Enter / Cmd+Shift+Enter.
  // Enter có Shift để tránh đụng Ctrl/Cmd+N của trình duyệt.
  useEffect(() => {
    if (setupOnly) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      const key = e.key.toLowerCase();
      const target = e.target as HTMLElement | null;
      if (commandPaletteOpen && key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(false);
        return;
      }
      if (target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName ?? '')) return;
      if (key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      } else if (key === 'b') {
        e.preventDefault();
        toggleSidebarCollapse();
      } else if (key === 'enter' && e.shiftKey) {
        e.preventDefault();
        navigate('/briefing', { state: { reset: true } });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, navigate, toggleSidebarCollapse, setupOnly]);

  // Thu ghim nhưng đang peek thì hiển thị như đang mở rộng.
  const sidebarVisuallyCollapsed = sidebarCollapsed && !sidebarPeek;

  if (setupOnly) {
    return (
      <div className="app-shell min-h-[100dvh] flex flex-col transition-colors bg-[var(--color-bg)]">
        <main className="flex-1 w-full p-3 sm:p-5 lg:p-6 pb-12">
          <PageTransition />
        </main>
        <AppUpdateNotice />
        <ToastContainer />
      </div>
    );
  }

  return (
    // h-[100dvh] + overflow-hidden ở đây là trần cứng của cả app: trước là
    // min-h nên trang có thể cao hơn viewport và cả trang cuộn theo, kéo
    // composer đáy hội thoại (DailyBriefingPage) trôi mất khỏi màn hình cùng
    // header/sidebar. Khoá trần ở đây, để main tự cuộn nội dung của nó.
    // Padding safe-area: index.html khai viewport-fit=cover để chạy standalone
    // phủ hết màn iPhone tai thỏ, đổi lại phải tự chừa chỗ cho home indicator
    // và notch, nếu không hàng cuối của trang bị gạch ngang che.
    <>
    <MaintenanceBanner />
    <div
      className="app-shell h-[100dvh] overflow-hidden flex flex-col lg:flex-row transition-colors"
      style={{
        paddingBottom: 'env(safe-area-inset-bottom)',
        paddingLeft: 'env(safe-area-inset-left)',
        paddingRight: 'env(safe-area-inset-right)',
      }}
    >
      <Sidebar
        isOpenOnMobile={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        isCollapsed={sidebarVisuallyCollapsed}
        width={sidebarWidth}
        onWidthChange={handleSidebarWidthChange}
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        onMouseEnterDesktop={handleSidebarMouseEnter}
        onMouseLeaveDesktop={handleSidebarMouseLeave}
        isPeeking={sidebarPeek}
        onToggleCollapse={toggleSidebarCollapse}
      />

      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <TopBar
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        />

        <main className="min-w-0 flex-1 min-h-0 w-full overflow-x-hidden overflow-y-auto p-3 pb-28 sm:p-5 sm:pb-28 lg:p-6 lg:pb-12">
          <PageTransition />
        </main>
      </div>

      <AppUpdateNotice />
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />

      <MobileBottomNav
        onOpenMenu={() => setMobileMenuOpen((open) => !open)}
        onOpenSearch={() => setCommandPaletteOpen(true)}
      />

      <ToastContainer />

      <InstallPrompt />

      <AppUpdateNotice />

      <TaskReviewModal />
      <SourceDetailModal />
      <ConflictCompareModal />
      <CalendarReviewModal />
      <SourceLibraryModal />
      <ProductRatingModal
        isOpen={Boolean(prompt)}
        actionCount={prompt?.actionCount ?? 0}
        isManual={prompt?.trigger === 'manual'}
        onSubmit={submit}
        onDismiss={closePrompt}
      />
    </div>
    </>
  );
};
