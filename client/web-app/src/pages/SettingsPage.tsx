import React, { useState } from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { usePreferencesStore } from '../stores/usePreferencesStore';
import { useAppStore } from '../stores/useAppStore';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Toggle } from '../components/ui/Toggle';
import { PushToggle } from '../components/pwa/PushToggle';
import { NotificationPreferencesPanel } from '../components/settings/NotificationPreferencesPanel';
import {
  Settings,
  Globe,
  Clock,
  Bell,
  Lock,
  Eye,
  Download,
  Trash2,
  AlertTriangle
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const { addToast } = useAppStore();
  const {
    theme,
    language,
    setLanguage,
    accessibility,
    updateAccessibility,
    briefingPreferences,
    updateBriefingPreferences,
    notificationPreferences,
  } = usePreferencesStore();

  const [activeTab, setActiveTab] = useState<
    'language' | 'briefing' | 'notifications' | 'privacy' | 'accessibility'
  >('language');

  const [showDisconnectModal, setShowDisconnectModal] = useState(false);

  // Tab "Giao diện" (theme mode) đã dời hẳn vào menu người dùng ở Sidebar,
  // cạnh bộ chọn nền màu — không giữ selector trùng lặp ở đây nữa.
  const tabs = [
    { id: 'language', label: t.settingsPage.language, icon: <Globe className="w-4 h-4" /> },
    { id: 'briefing', label: t.settingsPage.briefingPrefsTab, icon: <Clock className="w-4 h-4" /> },
    { id: 'notifications', label: t.settingsPage.notifPrefsTab, icon: <Bell className="w-4 h-4" /> },
    { id: 'privacy', label: t.settingsPage.privacyTab, icon: <Lock className="w-4 h-4" /> },
    { id: 'accessibility', label: t.settingsPage.accessibilityTab, icon: <Eye className="w-4 h-4" /> },
  ] as const;

  const handleExportData = () => {
    const data = {
      timestamp: new Date().toISOString(),
      theme,
      language,
      accessibility,
      briefingPreferences,
      notificationPreferences,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'navigator-prototype-data.json';
    a.click();
    addToast({
      type: 'success',
      title: 'Data Exported',
      message: 'Downloaded navigator-prototype-data.json file.',
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <Settings className="w-4 h-4" /> {t.settingsPage.eyebrow}
          </div>
          <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] font-heading">
            {t.settingsPage.title}
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">{t.settingsPage.subtitle}</p>
        </div>

        <Button
          variant="primary"
          size="md"
          data-tour-id="settings-save"
          onClick={() => {
            addToast({
              type: 'success',
              title: t.actions.savePreferences,
              message: 'Preferences stored in localStorage.',
            });
          }}
        >
          {t.actions.savePreferences}
        </Button>
      </div>

      {/* Desktop & Mobile Settings Layout */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Navigation Panel */}
        <div className="flex md:flex-col gap-1 overflow-x-auto pb-2 md:pb-0 scrollbar-none" data-tour-id="settings-tabs">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all text-left whitespace-nowrap ${
                  isActive
                    ? 'bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-xs'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Content Panel */}
        <div className="md:col-span-3 space-y-6" data-tour-id="settings-content">
          {/* TAB 2: Language */}
          {activeTab === 'language' && (
            <Card className="space-y-4">
              <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading border-b border-[var(--color-border)] pb-3">
                {t.settingsPage.language}
              </h3>

              <div>
                <label className="text-xs font-bold text-[var(--color-text-primary)] block mb-2">
                  {t.settingsPage.languageLabel}
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { code: 'en', label: 'English' },
                    { code: 'vi', label: 'Tiếng Việt' },
                  ].map((item) => (
                    <button
                      key={item.code}
                      onClick={() => setLanguage(item.code as any)}
                      className={`flex items-center justify-center gap-2 p-3.5 rounded-xl border text-xs font-bold transition-all ${
                        language === item.code
                          ? 'border-[#2563A6] bg-[#E1EBFA] text-[var(--color-text-primary)] ring-2 ring-[#2563A6]/20'
                          : 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-soft)]'
                      }`}
                    >
                      <Globe className="w-4 h-4 text-[var(--color-primary)]" />
                      <span>{item.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {/* TAB 3: Briefing Preferences */}
          {activeTab === 'briefing' && (
            <Card className="space-y-4">
              <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading border-b border-[var(--color-border)] pb-3">
                {t.profilePage.briefingPreferences}
              </h3>

              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
                  <div>
                    <span className="font-bold text-[var(--color-text-primary)] block">
                      {t.profilePage.dailyBriefingEnabled}
                    </span>
                    <span className="text-[var(--color-text-secondary)] text-[11px]">
                      Automated morning synthesis of connected sources
                    </span>
                  </div>
                  <Toggle
                    checked={briefingPreferences.dailyBriefingEnabled}
                    onChange={(checked) =>
                      updateBriefingPreferences({ dailyBriefingEnabled: checked })
                    }
                    aria-label={t.profilePage.dailyBriefingEnabled}
                  />
                </div>

                <div className="p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl space-y-2">
                  <span className="font-bold text-[var(--color-text-primary)] block">
                    {t.settingsPage.autodraftLabel}
                  </span>
                  <p className="text-[var(--color-text-secondary)] text-[11px]">{t.settingsPage.autodraftDesc}</p>
                </div>
              </div>
            </Card>
          )}

          {/* TAB 4: Notifications */}
          {activeTab === 'notifications' && (
            <Card className="space-y-4">
              <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading border-b border-[var(--color-border)] pb-3">
                {t.settingsPage.notifPrefsTab}
              </h3>

              <div className="space-y-4 text-xs">
                {/* Cấp quyền trên máy này trước, chọn nhận gì sau — thứ tự này
                    khớp thứ tự người dùng nghĩ, và mọi lựa chọn bên dưới vô
                    nghĩa nếu thiết bị chưa được phép hiện thông báo.

                    Hai khối này lưu ở hai nơi khác nhau và không gộp được:
                    PushToggle là đăng ký của riêng trình duyệt trên máy này,
                    còn bảng bên dưới là cấu hình của tài khoản, áp cho mọi
                    thiết bị và mọi kênh. */}
                <PushToggle />
                <NotificationPreferencesPanel />
              </div>
            </Card>
          )}

          {/* TAB 5: Privacy & Data */}
          {activeTab === 'privacy' && (
            <Card className="space-y-4">
              <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading border-b border-[var(--color-border)] pb-3">
                {t.privacy.title}
              </h3>

              <div className="p-3 bg-[#E1EBFA] border border-[#E1EBFA] rounded-xl text-xs text-[var(--color-text-primary)] space-y-1">
                <strong className="block font-bold">{t.privacy.connectedDataTitle}</strong>
                <p>{t.privacy.privacyNote}</p>
              </div>

              <div className="space-y-2 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={<Download className="w-3.5 h-3.5" />}
                  onClick={handleExportData}
                >
                  {t.privacy.exportData}
                </Button>

                <Button
                  variant="danger"
                  size="sm"
                  icon={<Trash2 className="w-3.5 h-3.5" />}
                  onClick={() => setShowDisconnectModal(true)}
                >
                  {t.privacy.disconnectSource}
                </Button>
              </div>
            </Card>
          )}

          {/* TAB 6: Accessibility */}
          {activeTab === 'accessibility' && (
            <div className="space-y-4">
              <Card className="space-y-4">
                <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading border-b border-[var(--color-border)] pb-3">
                  {t.accessibility.title}
                </h3>

                <div className="space-y-3 text-xs">
                  <div className="flex items-start justify-between gap-3 p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
                    <div>
                      <span className="font-bold text-[var(--color-text-primary)] block">
                        {t.accessibility.reduceMotion}
                      </span>
                      <span className="text-[var(--color-text-secondary)] text-[11px]">
                        {t.accessibility.reduceMotionDesc}
                      </span>
                    </div>
                    <Toggle
                      checked={accessibility.reduceMotion}
                      onChange={(checked) => updateAccessibility({ reduceMotion: checked })}
                      aria-label={t.accessibility.reduceMotion}
                      className="mt-0.5"
                    />
                  </div>

                  <div className="flex items-start justify-between gap-3 p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
                    <div>
                      <span className="font-bold text-[var(--color-text-primary)] block">
                        {t.accessibility.highContrast}
                      </span>
                      <span className="text-[var(--color-text-secondary)] text-[11px]">
                        {t.accessibility.highContrastDesc}
                      </span>
                    </div>
                    <Toggle
                      checked={accessibility.highContrast}
                      onChange={(checked) => updateAccessibility({ highContrast: checked })}
                      aria-label={t.accessibility.highContrast}
                      className="mt-0.5"
                    />
                  </div>

                  <div className="p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl space-y-3">
                    <div>
                      <span className="font-bold text-[var(--color-text-primary)] block">
                        {t.accessibility.largerText}
                      </span>
                      <span className="text-[var(--color-text-secondary)] text-[11px]">
                        {t.accessibility.largerTextDesc}
                      </span>
                    </div>
                    <div
                      className="grid grid-cols-3 gap-2"
                      role="radiogroup"
                      aria-label={t.accessibility.largerText}
                    >
                      {(
                        [
                          { id: 'small', label: t.accessibility.fontSizeSmall },
                          { id: 'medium', label: t.accessibility.fontSizeMedium },
                          { id: 'large', label: t.accessibility.fontSizeLarge },
                        ] as const
                      ).map((option) => {
                        const selected = accessibility.fontSize === option.id;
                        return (
                          <button
                            key={option.id}
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            onClick={() => updateAccessibility({ fontSize: option.id })}
                            className={`rounded-xl border px-3 py-2.5 text-center font-semibold transition-colors cursor-pointer ${
                              selected
                                ? 'border-[var(--color-primary)] bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-sm'
                                : 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text-primary)]'
                            }`}
                          >
                            {option.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </Card>

              <Card className="space-y-4">
                <div className="border-b border-[var(--color-border)] pb-3">
                  <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading">
                    {t.accessibility.keyboardHints}
                  </h3>
                  <p className="text-[11px] text-[var(--color-text-secondary)] mt-1">
                    {t.accessibility.keyboardHintsDesc}
                  </p>
                </div>

                <ul className="space-y-2 text-xs">
                  {(
                    [
                      { keys: ['Ctrl', 'K'], desc: t.accessibility.cmdKDesc },
                      { keys: ['Ctrl', 'B'], desc: t.accessibility.cmdBDesc },
                      { keys: ['Esc'], desc: t.accessibility.escDesc },
                      { keys: ['↑', '↓'], desc: t.accessibility.arrowDesc },
                      { keys: ['Enter'], desc: t.accessibility.enterDesc },
                    ] as const
                  ).map((row) => (
                    <li
                      key={row.desc}
                      className="flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-accent-soft)] px-3 py-2.5"
                    >
                      <span className="text-[var(--color-text-secondary)]">{row.desc}</span>
                      <span className="flex shrink-0 items-center gap-1">
                        {row.keys.map((key) => (
                          <kbd
                            key={key}
                            className="min-w-[1.75rem] rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-muted)] px-1.5 py-1 text-center text-[10px] font-bold text-[var(--color-text-primary)] shadow-sm"
                          >
                            {key}
                          </kbd>
                        ))}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          )}
        </div>
      </div>

      {/* Disconnect Confirmation Modal */}
      {showDisconnectModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <Card className="max-w-md w-full space-y-4">
            <div className="flex items-center gap-2 text-[#A03D3D] font-bold text-base font-heading">
              <AlertTriangle className="w-5 h-5" />
              <h3>{t.privacy.disconnectModalTitle}</h3>
            </div>
            <p className="text-xs text-[var(--color-text-secondary)]">{t.privacy.disconnectModalDesc}</p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowDisconnectModal(false)}
              >
                {t.actions.cancel}
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  setShowDisconnectModal(false);
                  addToast({
                    type: 'info',
                    title: 'Source Disconnected',
                    message: 'Discord integration disconnected.',
                  });
                }}
              >
                {t.privacy.disconnectSource}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
