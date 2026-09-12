import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../i18n/useTranslation';
import { localizeTimeLabel } from '../i18n/privacyCatalog';
import { useDataPrivacyStore } from '../stores/useDataPrivacyStore';
import { GlobalCaptureCard } from '../components/privacy/GlobalCaptureCard';
import { SourceAccessList } from '../components/privacy/SourceAccessList';
import { DataActivityTab } from '../components/privacy/DataActivityTab';
import { MemoryInspectorTab } from '../components/privacy/MemoryInspectorTab';
import { DataRetentionSection } from '../components/privacy/DataRetentionSection';
import { PrivacyAuditLogSection } from '../components/privacy/PrivacyAuditLogSection';
import {
  Activity,
  Brain,
  Sliders,
  Shield
} from 'lucide-react';

// Overview & Access (granular per-channel capture, global pause) và Data
// Activity (captured records, redact/xoá từng đoạn) chưa có backend nào hỗ
// trợ mức chi tiết này — chỉ có connect/disconnect toàn provider thật, không
// có bảng captured-record hay cờ pause toàn cục nào ở backend. Code 2 tab này
// giữ nguyên bên dưới, chỉ ẩn qua cờ này — đổi thành true là bật lại được
// ngay khi có backend, không cần viết lại.
const ADVANCED_TABS_ENABLED = false;

const summaryCardClass =
  'p-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] shadow-[var(--shadow-sm)]';

export const DataPrivacyPage: React.FC = () => {
  const { t, language } = useTranslation();
  const { tab: rawTab = 'overview' } = useParams<{ tab?: string }>();
  const navigate = useNavigate();
  const tab = ADVANCED_TABS_ENABLED ? rawTab : 'memory';

  const { sources, records, memories, lastDataReview } = useDataPrivacyStore();

  const connectedCount = sources.filter((s) => s.connected).length;
  const activeCount = sources.filter((s) => s.connected && s.captureEnabled).length;
  const pausedCount = sources.filter((s) => s.connected && !s.captureEnabled).length;
  const totalCapturedCount = records.length;
  const totalMemoriesCount = memories.length;

  // Tab ẩn (overview/activity) mà vẫn có người vào thẳng URL cũ thì đưa về
  // tab thật duy nhất đang bật, không để họ đứng trước trang trống.
  useEffect(() => {
    if (!ADVANCED_TABS_ENABLED && rawTab !== 'memory') {
      navigate('/data-privacy/memory', { replace: true });
    }
  }, [rawTab, navigate]);

  const tabActive =
    'bg-[var(--color-surface-muted)] text-[var(--color-text-primary)] shadow-[var(--shadow-sm)] border border-[var(--color-border)]';
  const tabIdle =
    'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] border border-transparent';

  return (
    <div className="text-[var(--color-text-primary)]">
      <div className="space-y-8">
        {/* Header — hòa nền, không hộp trắng */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--color-border-subtle)] pb-6">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
              <Shield className="w-4 h-4" />
              <span>{t.nav.dataPrivacy}</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-semibold text-[var(--color-text-primary)] font-heading">
              {t.dataPrivacy.title}
            </h1>
            <p className="text-xs sm:text-sm text-[var(--color-text-secondary)] mt-1 max-w-2xl">
              {t.dataPrivacy.subtitle}
            </p>
          </div>

          {ADVANCED_TABS_ENABLED && (
            <div className="flex items-center gap-1.5 p-1.5 bg-[var(--color-accent-soft)] border border-[var(--color-border-subtle)] rounded-2xl shrink-0">
              <button
                onClick={() => navigate('/data-privacy')}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                  tab === 'overview' ? tabActive : tabIdle
                }`}
              >
                <Sliders className="w-4 h-4" />
                {t.dataPrivacy.tabs.overview}
              </button>

              <button
                onClick={() => navigate('/data-privacy/activity')}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                  tab === 'activity' ? tabActive : tabIdle
                }`}
              >
                <Activity className="w-4 h-4" />
                {t.dataPrivacy.tabs.activity}
              </button>

              <button
                onClick={() => navigate('/data-privacy/memory')}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                  tab === 'memory' ? tabActive : tabIdle
                }`}
              >
                <Brain className="w-4 h-4" />
                {t.dataPrivacy.tabs.memory}
              </button>
            </div>
          )}
        </div>

        {ADVANCED_TABS_ENABLED && tab === 'overview' && (
          <div className="space-y-8 animate-in fade-in duration-200">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className={summaryCardClass}>
                <span className="text-[11px] text-[var(--color-text-secondary)] block font-medium">
                  {t.dataPrivacy.summary.connectedSources}
                </span>
                <span className="text-2xl font-semibold text-[var(--color-text-primary)] font-heading mt-1 block">
                  {connectedCount}
                </span>
              </div>

              <div className={summaryCardClass}>
                <span className="text-[11px] text-[var(--color-text-secondary)] block font-medium">
                  {t.dataPrivacy.summary.activeSources}
                </span>
                <span className="text-2xl font-semibold text-[var(--color-success)] font-heading mt-1 block">
                  {activeCount}
                </span>
              </div>

              <div className={summaryCardClass}>
                <span className="text-[11px] text-[var(--color-text-secondary)] block font-medium">
                  {t.dataPrivacy.summary.pausedSources}
                </span>
                <span className="text-2xl font-semibold text-[var(--color-warning)] font-heading mt-1 block">
                  {pausedCount}
                </span>
              </div>

              <div className={summaryCardClass}>
                <span className="text-[11px] text-[var(--color-text-secondary)] block font-medium">
                  {t.dataPrivacy.summary.capturedRecords}
                </span>
                <span className="text-2xl font-semibold text-[var(--color-text-primary)] font-heading mt-1 block">
                  {totalCapturedCount}
                </span>
              </div>

              <div className={summaryCardClass}>
                <span className="text-[11px] text-[var(--color-text-secondary)] block font-medium">
                  {t.dataPrivacy.summary.savedMemories}
                </span>
                <span className="text-2xl font-semibold text-[var(--color-primary)] font-heading mt-1 block">
                  {totalMemoriesCount}
                </span>
              </div>

              <div className={summaryCardClass}>
                <span className="text-[11px] text-[var(--color-text-secondary)] block font-medium">
                  {t.dataPrivacy.summary.lastReview}
                </span>
                <span className="text-xs font-extrabold text-[var(--color-text-primary)] mt-2 block">
                  {localizeTimeLabel(lastDataReview, language)}
                </span>
              </div>
            </div>

            <GlobalCaptureCard />
            <SourceAccessList />
            <DataRetentionSection />
            <PrivacyAuditLogSection />
          </div>
        )}

        {ADVANCED_TABS_ENABLED && tab === 'activity' && (
          <div className="animate-in fade-in duration-200">
            <DataActivityTab />
          </div>
        )}

        {tab === 'memory' && (
          <div className="animate-in fade-in duration-200">
            <MemoryInspectorTab />
          </div>
        )}
      </div>
    </div>
  );
};
