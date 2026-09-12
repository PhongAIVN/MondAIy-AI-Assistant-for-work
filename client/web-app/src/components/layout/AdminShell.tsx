import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { PageTransition } from './PageTransition';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';
import {
  ShieldCheck,
  Users,
  FolderKanban,
  CalendarDays,
  Layers,
  FileCheck2,
  AlertTriangle,
  MessageSquare,
  Activity,
  Settings,
  Newspaper,
  Compass,
  ArrowUpRight,
  LogOut,
  Sun,
  Moon,
  Globe,
  Menu,
  X,
} from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useTranslation } from '../../i18n/useTranslation';
import { ToastContainer } from '../ui/Toast';

export const AdminShell: React.FC = () => {
  const { user, signOut } = useAuthStore();
  const { theme, setTheme, language, setLanguage } = usePreferencesStore();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const motionEnabled = useMotionEnabled();

  const navItems = [
    { path: '/admin', label: t.admin.overview, icon: ShieldCheck, exact: true },
    { path: '/admin/users', label: t.admin.users, icon: Users },
    { path: '/admin/programs', label: t.admin.programs, icon: FolderKanban },
    { path: '/admin/program-events', label: t.admin.programEvents, icon: CalendarDays },
    {
      path: '/admin/discord-announcements',
      label: t.admin.discordAnnouncements,
      icon: MessageSquare,
    },
    { path: '/admin/sources', label: t.admin.sources, icon: Layers },
    { path: '/admin/briefings', label: t.admin.briefings, icon: FileCheck2 },
    { path: '/admin/conflicts', label: t.admin.conflicts, icon: AlertTriangle, badge: '2' },
    { path: '/admin/feedback', label: t.admin.feedback, icon: MessageSquare },
    { path: '/admin/blog', label: t.admin.blog, icon: Newspaper },
    { path: '/admin/activity', label: t.admin.activity, icon: Activity },
    { path: '/admin/settings', label: t.admin.settings, icon: Settings },
  ];

  const handleSignOut = () => {
    signOut();
    navigate('/');
  };

  return (
    <div className="app-shell min-h-[100dvh] font-sans flex flex-col md:flex-row transition-colors duration-200">
      {/* Admin Sidebar */}
      <aside
        className={`fixed md:sticky top-0 z-40 h-[100dvh] w-64 bg-[#17343F] text-[#FFFFDD] border-r border-[#325964] flex flex-col justify-between transition-transform duration-300 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-4 space-y-6">
          {/* Admin Header */}
          <div className="flex items-center justify-between pb-4 border-b border-[#325964]">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#61A3BA] text-[#17343F] flex items-center justify-center font-bold">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-white">{t.admin.title}</h1>
                <span className="text-[10px] font-semibold text-[#A2C579]">
                  Global Portal
                </span>
              </div>
            </div>
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="md:hidden text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.exact}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `relative flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-[color,background-color,transform] duration-150 ease-[var(--ease-out-quint)] active:scale-[0.98] ${
                    isActive
                      ? 'text-[#FFFFDD]'
                      : 'text-[#C8D9D6] hover:bg-[#234F5D] hover:text-[#FFFFDD]'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive &&
                      (motionEnabled ? (
                        <motion.span
                          layoutId="admin-nav-active"
                          className="absolute inset-0 rounded-xl bg-[#356F83] shadow-sm ring-1 ring-[#61A3BA]/40"
                          transition={{ type: 'spring', stiffness: 260, damping: 28, mass: 0.85 }}
                        />
                      ) : (
                        <span className="absolute inset-0 rounded-xl bg-[#356F83] shadow-sm ring-1 ring-[#61A3BA]/40" />
                      ))}
                    <div className="relative z-10 flex items-center gap-2.5">
                      <item.icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="relative z-10 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-rose-500 text-white">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Footer Quick Action */}
        <div className="p-4 border-t border-[#325964] space-y-3">
          <button
            onClick={() => navigate('/briefing')}
            className="w-full px-3 py-2 rounded-xl bg-[#234F5D] hover:bg-[#2E5C69] text-xs font-semibold text-[#9BCBD2] border border-[#325964] flex items-center justify-between transition-colors"
          >
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4" />
              <span>{t.nav.userWorkspace}</span>
            </div>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          <div className="flex items-center justify-between text-xs text-[#C8D9D6]">
            <div className="truncate max-w-[120px]">
              <span className="font-bold text-white block truncate">{user?.name}</span>
              <span className="text-[10px] font-semibold text-[#A2C579]">{user?.role}</span>
            </div>
            <button
              onClick={handleSignOut}
              className="p-1.5 rounded-lg hover:bg-rose-950/50 hover:text-rose-400 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Admin Content Container */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="app-toolbar sticky top-0 z-30 h-16 border-b px-4 sm:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="app-icon-button md:hidden p-2 rounded-lg"
            >
              <Menu className="w-5 h-5" />
            </button>
            <span className="font-bold text-sm text-[var(--color-text-primary)] flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[var(--color-primary)]" />
              <span>Admin Workspace</span>
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Language Selector */}
            <button
              onClick={() => setLanguage(language === 'en' ? 'vi' : 'en')}
              className="app-control flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold rounded-lg"
            >
              <Globe className="w-3.5 h-3.5 text-[var(--color-primary)]" />
              <span className="uppercase">{language}</span>
            </button>

            {/* Theme Toggle */}
            <button
              onClick={() => setTheme(theme === 'dark' || theme === 'black' ? 'light' : 'dark')}
              className="app-icon-button p-2 rounded-lg"
            >
              {theme === 'dark' || theme === 'black' ? <Sun className="w-4 h-4 text-[var(--color-warning)]" /> : <Moon className="w-4 h-4 text-[var(--color-primary)]" />}
            </button>
          </div>
        </header>

        {/* Admin Content Area */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          <PageTransition />
        </main>
        <ToastContainer />
      </div>
    </div>
  );
};
