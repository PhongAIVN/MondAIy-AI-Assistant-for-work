import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Menu, X, Sun, Moon, Globe, ArrowRight } from 'lucide-react';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useTranslation } from '../../i18n/useTranslation';
import { MondaiyLogo } from '../ui/MondaiyLogo';
import { Button } from '../ui/Button';
import { BrandLandscapeFooter } from '../marketing/NatureStages';
import { BackToTopButton } from '../marketing/BackToTopButton';
import { PageTransition } from './PageTransition';

type NavLink =
  | { label: string; kind: 'hash'; hash: string }
  | { label: string; kind: 'route'; to: string };

export const MarketingLayout: React.FC = () => {
  const { theme, setTheme, language, setLanguage } = usePreferencesStore();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Hash trên landing; Blog / Policy / Help là trang riêng.
  const navLinks: NavLink[] = [
    { label: t.marketing.product, kind: 'hash', hash: 'product' },
    { label: t.marketing.useCases, kind: 'hash', hash: 'use-cases' },
    { label: t.marketing.blog, kind: 'route', to: '/blog' },
    { label: t.marketing.policy, kind: 'route', to: '/policy' },
    { label: t.marketing.extension, kind: 'route', to: '/extension' },
    { label: t.marketing.help, kind: 'route', to: '/help' },
  ];

  const handleNavClick = (link: NavLink) => {
    setMobileMenuOpen(false);
    if (link.kind === 'route') {
      navigate(link.to);
      return;
    }
    // "/" chỉ hiện landing cho khách chưa đăng nhập — người dùng đã đăng
    // nhập trỏ vào "/" bị GuestRoute đá thẳng sang /briefing, mất luôn hash.
    // "/landing" xem được ở mọi trạng thái đăng nhập nên dùng làm đích chung
    // khi đang đứng ở trang marketing khác (blog, policy, extension, help...).
    if (location.pathname !== '/' && location.pathname !== '/landing') {
      navigate({ pathname: '/landing', hash: link.hash });
      return;
    }
    const elem = document.getElementById(link.hash);
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const isLinkActive = (link: NavLink): boolean => {
    if (link.kind === 'route') {
      return location.pathname === link.to || location.pathname.startsWith(`${link.to}/`);
    }
    return location.pathname === '/' && location.hash === `#${link.hash}`;
  };

  useEffect(() => {
    if ((location.pathname !== '/' && location.pathname !== '/landing') || !location.hash) return;
    const id = location.hash.replace(/^#/, '');
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    });
  }, [location.pathname, location.hash]);

  // React Router không tự cuộn về đầu trang khi đổi route (khác hành vi
  // điều hướng trình duyệt truyền thống). Không có bước này, người dùng cuộn
  // xuống landing rồi bấm sang /blog, /policy... sẽ giữ nguyên vị trí cuộn cũ.
  useEffect(() => {
    if (location.hash) return;
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [location.pathname, location.hash]);

  return (
    <div className="landing-root flex min-h-[100dvh] flex-col bg-paper font-sans text-ink-900 transition-colors duration-[var(--d-base)] dark:bg-[#17343F] dark:text-[#FFFFDD]">
      <header className="sticky top-0 z-40 w-full border-b border-hairline bg-paper/88 backdrop-blur-md dark:bg-[#17343F]/88">
        <div className="mx-auto flex h-[4.25rem] max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="group flex items-center gap-2.5">
            <MondaiyLogo size="lg" variant="auto" hoverSrc="/loadinggif1.gif" />
          </Link>

          <nav className="hidden items-center gap-7 lg:flex">
            {navLinks.map((link) => {
              const active = isLinkActive(link);
              return (
                <button
                  key={link.kind === 'route' ? link.to : link.hash}
                  type="button"
                  onClick={() => handleNavClick(link)}
                  aria-current={active ? 'page' : undefined}
                  className={`text-sm font-semibold transition-colors ${
                    active
                      ? 'text-ink-900 dark:text-white'
                      : 'text-ink-500 hover:text-ink-900 dark:text-slate-300 dark:hover:text-white'
                  }`}
                >
                  {link.label}
                </button>
              );
            })}
          </nav>

          <div className="hidden items-center gap-2 md:flex">
            <button
              type="button"
              onClick={() => setLanguage(language === 'en' ? 'vi' : 'en')}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold leading-none text-ink-500 transition-colors hover:bg-paper-sunken hover:text-ink-900"
              title="Toggle Language"
            >
              <Globe className="h-3.5 w-3.5 shrink-0 text-action-solid" strokeWidth={1.5} />
              <span className="uppercase leading-none">{language}</span>
            </button>

            <button
              type="button"
              onClick={() => setTheme(theme === 'dark' || theme === 'black' ? 'light' : 'dark')}
              className="rounded-full p-2 text-ink-500 transition-colors hover:bg-paper-sunken hover:text-ink-900"
              title="Toggle Theme"
            >
              {theme === 'dark' || theme === 'black' ? (
                <Sun className="h-4 w-4 text-amber-400" strokeWidth={1.5} />
              ) : (
                <Moon className="h-4 w-4 text-action-solid" strokeWidth={1.5} />
              )}
            </button>

            <Link
              to="/sign-in"
              className="px-3 py-2 text-sm font-semibold text-ink-700 transition-colors hover:text-action-solid dark:text-white"
            >
              {t.actions.signIn}
            </Link>

            <Link to="/sign-up">
              <Button className="!rounded-full bg-action-solid px-4 py-2 text-sm font-semibold text-[var(--color-on-primary)] hover:bg-action-hover">
                <span className="inline-flex items-center gap-1.5">
                  {t.actions.getStarted}
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
                </span>
              </Button>
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="rounded-full p-2 text-ink-900 hover:bg-paper-sunken md:hidden dark:text-white"
          >
            {mobileMenuOpen ? <X className="h-6 w-6" strokeWidth={1.5} /> : <Menu className="h-6 w-6" strokeWidth={1.5} />}
          </button>
        </div>
      </header>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-[#17343F]/45 backdrop-blur-xs md:hidden">
          {/* Token marketing (paper/ink/hairline/action-solid), không phải token
              app-palette — trước đây lẫn 2 bộ token, viền trái đục hẳn ra so với
              mọi đường hairline mờ còn lại trên trang. */}
          <div className="flex h-full w-4/5 max-w-xs flex-col justify-between border-l border-hairline bg-paper-raised p-6 shadow-e4">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-ink-900">{t.marketing.mobileMenuLabel}</span>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex h-11 w-11 items-center justify-center rounded-lg text-ink-500 hover:text-ink-900"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex flex-col gap-3">
                {navLinks.map((link) => {
                  const active = isLinkActive(link);
                  return (
                    <button
                      key={link.kind === 'route' ? link.to : link.hash}
                      type="button"
                      onClick={() => handleNavClick(link)}
                      aria-current={active ? 'page' : undefined}
                      className={`min-h-11 border-b border-hairline py-2 text-left text-sm font-semibold ${
                        active ? 'text-action-solid' : 'text-ink-900'
                      }`}
                    >
                      {link.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-3 border-t border-hairline pt-6">
              <div className="flex items-center justify-between pb-2">
                <button
                  type="button"
                  onClick={() => setLanguage(language === 'en' ? 'vi' : 'en')}
                  className="flex h-11 items-center gap-1.5 rounded-lg border border-hairline px-3 text-xs font-semibold leading-none text-ink-700"
                >
                  <Globe className="h-3.5 w-3.5 shrink-0 text-action-solid" />
                  <span className="uppercase leading-none">{language}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setTheme(theme === 'dark' || theme === 'black' ? 'light' : 'dark')}
                  className="flex h-11 w-11 items-center justify-center rounded-lg border border-hairline"
                >
                  {theme === 'dark' || theme === 'black' ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-action-solid" />}
                </button>
              </div>

              <Link
                to="/sign-in"
                onClick={() => setMobileMenuOpen(false)}
                className="flex min-h-11 w-full items-center justify-center rounded-xl border border-hairline text-center text-xs font-semibold text-ink-900"
              >
                {t.actions.signIn}
              </Link>
              <Link
                to="/sign-up"
                onClick={() => setMobileMenuOpen(false)}
                className="flex min-h-11 w-full items-center justify-center rounded-xl bg-action-solid text-center text-xs font-semibold text-[var(--color-on-primary)] shadow-e2"
              >
                {t.actions.getStarted}
              </Link>
            </div>
          </div>
        </div>
      )}

      <main className="flex-1">
        <PageTransition />
      </main>

      <BrandLandscapeFooter rightsText={t.marketing.footerRights} />

      <BackToTopButton />
    </div>
  );
};
