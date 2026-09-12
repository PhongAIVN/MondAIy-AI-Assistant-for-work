import React from 'react';
import { Link } from 'react-router-dom';
import { Sun, Moon, Globe } from 'lucide-react';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useTranslation } from '../../i18n/useTranslation';
import { MondaiyLogo } from '../ui/MondaiyLogo';
import { PageTransition } from './PageTransition';
import { MaintenanceBanner } from '../system/MaintenanceBanner';

export const AuthLayout: React.FC = () => {
  const { theme, setTheme, language, setLanguage } = usePreferencesStore();
  const { t } = useTranslation();

  return (
    <div className="app-shell min-h-[100dvh] flex flex-col font-sans transition-colors duration-200">
      <MaintenanceBanner />
      {/* Header */}
      <header className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 group">
          <MondaiyLogo size="md" variant="auto" />
        </Link>

        <div className="flex items-center gap-3">
          {/* Language Selector */}
          <button
            onClick={() => setLanguage(language === 'en' ? 'vi' : 'en')}
            className="app-control flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg"
            title="Toggle Language"
          >
            <Globe className="w-3.5 h-3.5 text-[var(--color-primary)]" />
            <span className="font-semibold uppercase">{language}</span>
          </button>

          {/* Theme Selector */}
          <button
            onClick={() => setTheme(theme === 'dark' || theme === 'black' ? 'light' : 'dark')}
            className="app-icon-button p-1.5 rounded-lg"
            title="Toggle Theme"
          >
            {theme === 'dark' || theme === 'black' ? (
              <Sun className="w-4 h-4 text-[var(--color-warning)]" />
            ) : (
              <Moon className="w-4 h-4 text-[var(--color-primary)]" />
            )}
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="app-panel w-full max-w-md rounded-2xl p-6 sm:p-8 shadow-lg">
          <PageTransition />
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-[var(--color-text-muted)]">
        <p>{t.marketing.footerRights}</p>
      </footer>
    </div>
  );
};
