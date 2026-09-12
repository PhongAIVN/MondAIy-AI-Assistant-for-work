import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../i18n/useTranslation';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useAppStore } from '../../stores/useAppStore';
import { usePipelineRunStore } from '../../stores/usePipelineRunStore';
import { PROVIDER_LABEL, isEnabledProvider } from '../../types/pipeline';
import {
  Search,
  Compass,
  CheckSquare,
  Layers,
  ShieldCheck,
  Bell,
  Clock3,
  Settings,
  User,
  HelpCircle,
  Sparkles,
  Sun,
  Moon,
  Globe,
  X,
  ArrowRight,
} from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const connections = usePipelineRunStore((state) => state.connections);
  const { theme, setTheme, language, setLanguage, onboardingDismissed } = usePreferencesStore();
  const { addToast } = useAppStore();

  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Build searchable items list
  const navItems = [
    { id: 'nav-briefing', group: t.commandPalette.quickNav, title: t.nav.dailyBriefing, icon: <Compass className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/briefing') },
    { id: 'nav-tasks', group: t.commandPalette.quickNav, title: t.nav.myTasks, icon: <CheckSquare className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/tasks') },
    { id: 'nav-sources', group: t.commandPalette.quickNav, title: t.nav.sources, icon: <Layers className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/sources') },
    { id: 'nav-privacy', group: t.commandPalette.quickNav, title: t.nav.dataPrivacy, icon: <ShieldCheck className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/data-privacy') },
    { id: 'nav-notifications', group: t.commandPalette.quickNav, title: t.nav.notifications, icon: <Bell className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/notifications') },
    { id: 'nav-routines', group: t.commandPalette.quickNav, title: t.nav.routines, icon: <Clock3 className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/routines') },
    // Chỉ gợi ý wizard onboarding khi user chưa hoàn thành — xong rồi thì tìm
    // lại làm gì, cưỡng ép quay lại chỉ gây khó chịu.
    ...(onboardingDismissed
      ? []
      : [{ id: 'nav-onboarding', group: t.commandPalette.quickNav, title: 'Onboarding Setup Wizard', icon: <User className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/onboarding') }]),
    { id: 'nav-settings', group: t.commandPalette.quickNav, title: t.nav.settings, icon: <Settings className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/settings') },
    { id: 'nav-profile', group: t.commandPalette.quickNav, title: t.nav.profile, icon: <User className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/profile') },
    { id: 'nav-help', group: t.commandPalette.quickNav, title: t.nav.help, icon: <HelpCircle className="w-4 h-4 text-[#2563A6]" />, action: () => navigate('/help') },
  ];

  const actionItems = [
    {
      id: 'act-ask',
      group: t.commandPalette.actionsGroup,
      title: t.nav.askNavigator,
      icon: <Sparkles className="w-4 h-4 text-[#2563A6]" />,
      action: () => navigate('/briefing'),
    },
    {
      id: 'act-theme',
      group: t.commandPalette.actionsGroup,
      title: `${t.topbar.theme}: ${theme === 'dark' || theme === 'black' ? t.topbar.dark : t.topbar.light}`,
      icon: theme === 'dark' || theme === 'black' ? <Moon className="w-4 h-4 text-[#2563A6]" /> : <Sun className="w-4 h-4 text-[#2563A6]" />,
      action: () => {
        const next = theme === 'dark' || theme === 'black' ? 'light' : 'dark';
        setTheme(next);
        addToast({ type: 'info', title: 'Theme Updated', message: `Switched to ${next} mode.` });
      },
    },
    {
      id: 'act-lang',
      group: t.commandPalette.actionsGroup,
      title: `${t.topbar.language}: ${language === 'en' ? 'Tiếng Việt' : 'English'}`,
      icon: <Globe className="w-4 h-4 text-[#2563A6]" />,
      action: () => {
        const next = language === 'en' ? 'vi' : 'en';
        setLanguage(next);
        addToast({ type: 'info', title: 'Language Updated', message: `Switched to ${next === 'en' ? 'English' : 'Tiếng Việt'}.` });
      },
    },
  ];

  // Nguồn thật từ /api/v1/connections, lọc theo phạm vi ADR-002 và chỉ lấy
  // nguồn đã kết nối — không dùng danh sách cứng nữa, nếu không Ctrl+K sẽ gợi
  // ý nguồn không hề tồn tại.
  const sourceItems = connections
    .filter((connection) => connection.connected && isEnabledProvider(connection.provider))
    .map((connection) => ({
      id: `src-${connection.provider}`,
      group: t.commandPalette.sourcesGroup,
      title: connection.accountLabel
        ? `${PROVIDER_LABEL[connection.provider]} (${connection.accountLabel})`
        : PROVIDER_LABEL[connection.provider],
      icon: <Layers className="w-4 h-4 text-[#2563A6]" />,
      action: () => navigate('/sources'),
    }));

  const allItems = [...navItems, ...actionItems, ...sourceItems];

  const filtered = query.trim()
    ? allItems.filter(
        (item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          item.group.toLowerCase().includes(query.toLowerCase())
      )
    : allItems;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action();
        onClose();
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      className="app-overlay fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="app-panel w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Header */}
        <div className="flex items-center px-4 py-3.5 border-b border-[var(--color-border)] bg-[var(--color-surface)] gap-3">
          <Search className="w-5 h-5 text-[var(--color-primary)] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder={t.commandPalette.placeholder}
            data-tour-id="command-palette-input"
            className="w-full text-sm font-medium text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] bg-transparent outline-none focus:outline-none focus-visible:outline-none"
          />
          <button
            onClick={onClose}
            className="app-icon-button p-1 rounded-lg border-transparent shadow-none"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1" data-tour-id="command-palette-list">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-[var(--color-text-secondary)]">
              {t.commandPalette.noResults}
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    item.action();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-xs transition-all ${
                    isSelected
                      ? 'bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-sm font-bold'
                      : 'app-menu-item text-[var(--color-text-primary)]'
                  }`}
                >
                  <div className="flex items-center gap-3 truncate">
                    <span className={isSelected ? 'text-[var(--color-on-primary)]' : ''}>{item.icon}</span>
                    <div className="truncate">
                      <span className="block truncate">{item.title}</span>
                      <span
                        className={`text-[10px] block ${
                          isSelected ? 'opacity-75' : 'text-[var(--color-text-muted)]'
                        }`}
                      >
                        {item.group}
                      </span>
                    </div>
                  </div>

                  <ArrowRight
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isSelected ? 'text-[var(--color-on-primary)]' : 'text-[var(--color-text-muted)]'
                    }`}
                  />
                </button>
              );
            })
          )}
        </div>

        {/* Footer Hint */}
        <div className="app-panel-muted px-4 py-2.5 border-t flex items-center justify-between text-[11px] text-[var(--color-text-muted)]">
          <span>{t.commandPalette.shortcutHint}</span>
          <span className="px-2 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[10px] font-bold">
            ESC
          </span>
        </div>
      </div>
    </div>
  );
};
