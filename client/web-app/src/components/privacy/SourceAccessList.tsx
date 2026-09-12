import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../i18n/useTranslation';
import {
  localizeScope,
  localizeSourceName,
  localizeTimeLabel,
} from '../../i18n/privacyCatalog';
import { type ConnectedSourceAccess } from '../../types/dataPrivacy';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { useAppStore } from '../../stores/useAppStore';
import { GranularAccessDrawer } from './GranularAccessDrawer';
import { SourcePauseModal } from './SourcePauseModal';
import { SourceDisconnectModal } from './SourceDisconnectModal';
import { resolveBrandIcon } from '../ui/BrandIcons';
import {
  Layers,
  PauseCircle,
  PlayCircle,
  AlertCircle,
  SlidersHorizontal,
  Activity,
  Unplug,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from 'lucide-react';

export const SourceAccessList: React.FC = () => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const { sources, toggleSourceCapture, refreshSource } = useDataPrivacyStore();
  const { addToast } = useAppStore();

  const [selectedDrawerSource, setSelectedDrawerSource] = useState<ConnectedSourceAccess | null>(null);
  const [selectedPauseSource, setSelectedPauseSource] = useState<ConnectedSourceAccess | null>(null);
  const [selectedDisconnectSource, setSelectedDisconnectSource] = useState<ConnectedSourceAccess | null>(null);

  const getSourceIcon = (iconName: string) =>
    resolveBrandIcon(iconName, 'w-5 h-5') ?? <Layers className="w-5 h-5" />;

  const renderBadge = (coverage: string, captureEnabled: boolean, connected: boolean) => {
    if (!connected) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-[#F9DEDE] text-[#A03D3D] border border-[#F0D8D3] dark:bg-[#0F1F38] dark:border-[#1E2E4A] dark:text-[#DC9A91]">
          <XCircle className="w-3 h-3" />
          {language === 'vi' ? 'Đã ngắt kết nối' : 'Disconnected'}
        </span>
      );
    }
    if (!captureEnabled) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-[#F6EEDA] text-[#8A5712] border border-[#D7B270] dark:bg-[#0F1F38] dark:border-[#1E2E4A] dark:text-[#D7B270]">
          <PauseCircle className="w-3 h-3" />
          {language === 'vi' ? 'Tạm dừng' : 'Paused'}
        </span>
      );
    }
    if (coverage === 'limited') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-[#F6EEDA] text-[#8A5712] border border-[#D7B270] dark:bg-[#0F1F38] dark:border-[#1E2E4A] dark:text-[#D7B270]">
          <AlertCircle className="w-3 h-3" />
          {language === 'vi' ? 'Phạm vi giới hạn' : 'Limited coverage'}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-[#DFF0E6] text-[#2A6B4F] border border-[#C4DDCB] dark:bg-[#0F1F38] dark:border-[#1E2E4A] dark:text-[#8CC3A2]">
        <CheckCircle2 className="w-3 h-3" />
        {language === 'vi' ? 'Đang hoạt động' : 'Active'}
      </span>
    );
  };

  const handleToggleCapture = (source: ConnectedSourceAccess) => {
    if (source.captureEnabled) {
      setSelectedPauseSource(source);
    } else {
      toggleSourceCapture(source.id, true);
      addToast({
        type: 'success',
        title: 'Source Resumed',
        message: t.dataPrivacy.sources.resumeSourceToast.replace(
          '{source}',
          localizeSourceName(source.id, source.name, language),
        ),
      });
    }
  };

  const handleConfirmPauseSource = () => {
    if (selectedPauseSource) {
      toggleSourceCapture(selectedPauseSource.id, false);
      addToast({
        type: 'info',
        title: 'Source Paused',
        message: `Data capture paused for ${selectedPauseSource.name}`,
      });
      setSelectedPauseSource(null);
    }
  };

  const handleRefresh = (source: ConnectedSourceAccess) => {
    if (!source.connected) return;
    refreshSource(source.id);
    addToast({
      type: 'success',
      title: language === 'vi' ? 'Đã làm mới nguồn' : 'Source refreshed',
      message: t.dataPrivacy.sources.refreshToast.replace(
        '{source}',
        localizeSourceName(source.id, source.name, language),
      ),
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-extrabold text-[var(--color-text-primary)] font-heading">
            {t.dataPrivacy.sources.sectionTitle}
          </h2>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1 max-w-xl">
            {t.dataPrivacy.sources.sectionHint}
          </p>
        </div>
        <span className="text-xs text-[var(--color-text-secondary)] shrink-0">
          {sources.filter((s) => s.connected && s.captureEnabled).length} / {sources.length}{' '}
          {language === 'vi' ? 'nguồn đang hoạt động' : 'active sources'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sources.map((src) => (
          <div
            key={src.id}
            className="bg-[var(--color-surface-muted)] p-5 rounded-2xl border border-[var(--color-border)] shadow-2xs hover:border-[var(--color-border-strong)] transition-all flex flex-col justify-between space-y-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--color-accent-soft)] flex items-center justify-center text-[var(--color-primary)] shrink-0">
                  {getSourceIcon(src.icon)}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-bold text-[var(--color-text-primary)]">
                      {localizeSourceName(src.id, src.name, language)}
                    </h3>
                    {renderBadge(src.coverage, src.captureEnabled, src.connected)}
                  </div>
                  <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
                    {src.accountEmailOrUser}
                  </p>
                </div>
              </div>

              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  disabled={!src.connected}
                  checked={src.captureEnabled && src.connected}
                  onChange={() => handleToggleCapture(src)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-200 dark:bg-[#1A2A42] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#0F1F38] dark:peer-checked:bg-[#2563A6] disabled:opacity-50"></div>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs p-3 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)]">
              <div>
                <span className="text-[var(--color-text-secondary)] block">
                  {t.dataPrivacy.sources.lastReviewed}:
                </span>
                <span className="font-bold text-[var(--color-text-primary)]">
                  {localizeTimeLabel(src.lastReviewedAt, language)}
                </span>
              </div>
              <div>
                <span className="text-[var(--color-text-secondary)] block">
                  {language === 'vi' ? 'Bản ghi thu thập:' : 'Captured:'}
                </span>
                <span className="font-bold text-[var(--color-text-primary)]">
                  {src.capturedRecordsCount} {t.dataPrivacy.sources.recordsCount}
                </span>
              </div>
            </div>

            <div className="text-xs space-y-1">
              <p className="text-[#2A6B4F] dark:text-[#8CC3A2] font-medium truncate">
                ✓ {localizeScope(src.permissions.canAccess[0], language)}
              </p>
              <p className="text-[#A03D3D] dark:text-[#DC9A91] font-medium truncate">
                ✕ {localizeScope(src.permissions.cannotAccess[0], language)}
              </p>
            </div>

            <div className="pt-2 border-t border-[var(--color-border)] flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={!src.connected}
                onClick={() => handleToggleCapture(src)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 disabled:opacity-50 ${
                  src.captureEnabled
                    ? 'bg-[#F6EEDA] text-[#8A5712] border border-[#D7B270] hover:bg-[#F0E4C8]'
                    : 'bg-[#DFF0E6] text-[#2A6B4F] border border-[#C4DDCB] hover:bg-[#CFE8DA]'
                }`}
              >
                {src.captureEnabled ? (
                  <PauseCircle className="w-3.5 h-3.5" />
                ) : (
                  <PlayCircle className="w-3.5 h-3.5" />
                )}
                {src.captureEnabled
                  ? t.dataPrivacy.sources.pauseCapture
                  : t.dataPrivacy.sources.resumeCapture}
              </button>

              <button
                type="button"
                disabled={!src.connected}
                onClick={() => handleRefresh(src)}
                className="px-3 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-primary)] rounded-xl text-xs font-bold hover:bg-[var(--color-surface-hover)] transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                {t.dataPrivacy.sources.refreshSource}
              </button>

              <button
                type="button"
                onClick={() => setSelectedDrawerSource(src)}
                className="px-3 py-1.5 bg-[var(--color-accent-soft)] text-[var(--color-primary)] rounded-xl text-xs font-bold hover:bg-[#D5DDEB] transition-colors flex items-center gap-1.5"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                {t.dataPrivacy.sources.managePermissions}
              </button>

              <div className="flex items-center gap-1.5 ml-auto">
                <button
                  type="button"
                  onClick={() => navigate('/data-privacy/activity')}
                  className="p-1.5 text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] rounded-lg transition-colors"
                  title={t.dataPrivacy.sources.viewActivity}
                >
                  <Activity className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDisconnectSource(src)}
                  className="p-1.5 text-[#A03D3D] dark:text-[#DC9A91] hover:bg-[#F9DEDE] dark:hover:bg-[#0F1F38] rounded-lg transition-colors"
                  title={language === 'vi' ? 'Ngắt kết nối nguồn' : 'Disconnect source'}
                >
                  <Unplug className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <GranularAccessDrawer
        source={selectedDrawerSource}
        isOpen={Boolean(selectedDrawerSource)}
        onClose={() => setSelectedDrawerSource(null)}
      />

      <SourcePauseModal
        source={selectedPauseSource}
        isOpen={Boolean(selectedPauseSource)}
        onClose={() => setSelectedPauseSource(null)}
        onConfirm={handleConfirmPauseSource}
      />

      <SourceDisconnectModal
        source={selectedDisconnectSource}
        isOpen={Boolean(selectedDisconnectSource)}
        onClose={() => setSelectedDisconnectSource(null)}
      />
    </div>
  );
};
