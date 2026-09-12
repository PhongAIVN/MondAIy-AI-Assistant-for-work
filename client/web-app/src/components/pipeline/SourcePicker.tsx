import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Check, Layers, Loader2, RefreshCw, Send, ShieldCheck } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { resolveBrandIcon } from '../ui/BrandIcons';
import type { SourceListState } from '../../stores/usePipelineRunStore';
import {
  PROVIDER_LABEL,
  SOURCE_LEVEL,
  isEnabledProvider,
  isMockSourceId,
  type ConnectionProvider,
  type Integration,
  type SyncSourceRef,
} from '../../types/pipeline';

const ProviderIcon: React.FC<{ provider: ConnectionProvider }> = ({ provider }) =>
  resolveBrandIcon(provider, 'w-4 h-4') ?? (
    <Send className="w-4 h-4 text-[#229ED9]" aria-hidden="true" />
  );

export interface SourcePickerProps {
  integrations: Integration[];
  sources: Record<number, SourceListState>;
  selected: SyncSourceRef[];
  loading: boolean;
  error: string | null;
  disabled?: boolean;
  /** Trần nguồn mỗi lần Sync, lấy từ GET /runs/limits — không hardcode ở FE. */
  maxSources: number;
  autoSyncEnabled: boolean;
  autoSyncIntervalMinutes: number;
  onToggle: (ref: SyncSourceRef) => void;
  onReload: () => void;
}

export const SourcePicker: React.FC<SourcePickerProps> = ({
  integrations,
  sources,
  selected,
  loading,
  error,
  disabled = false,
  maxSources,
  autoSyncEnabled,
  autoSyncIntervalMinutes,
  onToggle,
  onReload,
}) => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();

  const formatExpiry = (value?: string | null): string | null => {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const isSelected = (integrationId: number, sourceId: string): boolean =>
    selected.some((ref) => ref.connectionId === integrationId && ref.sourceId === sourceId);

  // Đã chạm trần thì các ô CHƯA tick bị khoá, ô đã tick vẫn bấm được để bỏ ra.
  const atLimit = selected.length >= maxSources;

  const fill = (template: string, values: Record<string, string | number>): string =>
    Object.entries(values).reduce((text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), template);

  return (
    <section aria-labelledby="source-picker-heading" className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2
            id="source-picker-heading"
            className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading flex items-center gap-2"
          >
            <Layers className="w-4 h-4 text-[var(--color-primary)]" aria-hidden="true" />
            {t.pipeline.sourcesTitle}
          </h2>
          <p className="text-[11px] text-[var(--color-text-secondary)] mt-0.5">{t.pipeline.sourcesHint}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span title={fill(t.pipeline.sourceCountHint, { max: maxSources })}>
            <Badge variant={atLimit ? 'warning' : 'neutral'}>
              {fill(t.pipeline.sourceCount, { selected: selected.length, max: maxSources })}
            </Badge>
          </span>

          <Button
            variant="ghost"
            size="xs"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            onClick={onReload}
            disabled={loading}
          >
            {t.pipeline.retry}
          </Button>
        </div>
      </div>

      {/* Auto-sync đang bật thì nói rõ nhịp — người dùng phải biết hệ thống
          đang tự lấy dữ liệu hộ mình, chứ không để nó chạy ngầm im lặng. */}
      {autoSyncEnabled && (
        <p className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-secondary)] bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg p-2">
          <RefreshCw className="w-3.5 h-3.5 shrink-0 text-[var(--color-primary)]" aria-hidden="true" />
          {fill(t.pipeline.autoSyncOn, { hours: Math.round(autoSyncIntervalMinutes / 60) })}
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 p-3 rounded-xl border border-[var(--color-danger)]/35 bg-[var(--color-danger-soft)] text-xs text-[var(--color-danger)]"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span className="font-semibold">{t.pipeline.sourcesError}</span>
          <span className="text-[var(--color-text-secondary)]">{error}</span>
        </div>
      )}

      {!error && integrations.length === 0 && !loading && (
        <div className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-accent-soft)] text-xs space-y-2">
          <p className="font-semibold text-[var(--color-text-primary)]">{t.pipeline.sourcesEmpty}</p>
          <p className="text-[var(--color-text-secondary)]">{t.pipeline.sourcesEmptyHint}</p>
          <Button variant="outline" size="sm" onClick={() => navigate('/sources')}>
            {t.nav.sources}
          </Button>
        </div>
      )}

      <div className="space-y-3">
        {/* Chỉ hiện nguồn trong phạm vi ADR-002 — xem ENABLED_PROVIDERS. */}
        {integrations.filter((integration) => isEnabledProvider(integration.provider)).map((integration) => {
          const state = sources[integration.id];
          const level = SOURCE_LEVEL[integration.provider];
          const expiry = formatExpiry(integration.expiresAt);
          const expired = integration.expiresAt ? new Date(integration.expiresAt).getTime() < Date.now() : false;

          return (
            <div
              key={integration.id}
              className="p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] space-y-2"
            >
              <div className="flex items-start justify-between gap-2 flex-wrap">
                <span className="flex items-center gap-2 min-w-0">
                  <ProviderIcon provider={integration.provider} />
                  <span className="text-xs font-bold text-[var(--color-text-primary)]">
                    {PROVIDER_LABEL[integration.provider]}
                  </span>
                  {/* Mức đáng tin lấy từ Program Frame mục 5 — quyết định nguồn
                      nào thắng khi hai nguồn nói khác nhau. */}
                  {level === 'A' && (
                    <span title={t.pipeline.levelAHint}>
                      <Badge variant="success" icon={<ShieldCheck className="w-3 h-3" />}>
                        {t.pipeline.levelA}
                      </Badge>
                    </span>
                  )}
                  {level === 'B' && (
                    <span title={t.pipeline.levelBHint}>
                      <Badge variant="neutral">{t.pipeline.levelB}</Badge>
                    </span>
                  )}
                  {integration.accountLabel && (
                    <span className="text-[11px] text-[#5E6B7D] dark:text-[#AEB9CC] truncate">
                      {integration.accountLabel}
                    </span>
                  )}
                </span>

                {expiry && (
                  <span
                    className={`text-[10px] ${
                      expired ? 'text-[var(--color-danger)] dark:text-[#FEB2B2] font-semibold' : 'text-[#5E6B7D] dark:text-[#AEB9CC]'
                    }`}
                  >
                    {expired ? t.pipeline.tokenExpired : `${t.pipeline.tokenExpires}: ${expiry}`}
                  </span>
                )}
              </div>

              {state?.loading && (
                <p className="flex items-center gap-1.5 text-[11px] text-[#5E6B7D] dark:text-[#AEB9CC]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                  {t.pipeline.running}
                </p>
              )}

              {/* Google trả nguồn Gmail + Calendar thật. Provider chưa hỗ trợ
                  trả 400; FE dựng một nguồn mẫu và luôn hiện cảnh báo. */}
              {state?.unsupported && (
                <p className="text-[11px] text-[var(--color-warning)] bg-[var(--color-warning-soft)] border border-[var(--color-warning)]/35 rounded-lg p-2">
                  {t.pipeline.sourceListUnsupported}
                </p>
              )}

              {state?.warnings && state.warnings.length > 0 && (
                <p className="text-[11px] text-[var(--color-warning)] bg-[var(--color-warning-soft)] border border-[var(--color-warning)]/35 rounded-lg p-2">
                  {t.pipeline.sourceListPartial} {state.warnings.join(' · ')}
                </p>
              )}

              {state?.error && (
                <p role="alert" className="text-[11px] text-[var(--color-danger)] dark:text-[#FEB2B2]">
                  {t.pipeline.sourceListError} {state.error}
                </p>
              )}

              {state && !state.loading && !state.error && state.items.length === 0 && (
                <p className="text-[11px] text-[#5E6B7D] dark:text-[#AEB9CC]">{t.pipeline.sourceListEmpty}</p>
              )}

              {state && state.items.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {state.items.map((source) => {
                    const checked = isSelected(integration.id, source.id);
                    const blocked = !checked && atLimit;
                    return (
                      <button
                        key={source.id}
                        type="button"
                        role="checkbox"
                        aria-checked={checked}
                        disabled={disabled || blocked}
                        title={blocked ? fill(t.pipeline.sourceLimitReached, { max: maxSources }) : undefined}
                        onClick={() => onToggle({ connectionId: integration.id, sourceId: source.id })}
                        className={`flex items-center justify-between gap-2 text-left p-2 rounded-lg border text-[11px] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] focus-visible:ring-offset-1 disabled:opacity-60 disabled:cursor-not-allowed ${
                          checked
                            ? 'border-[var(--color-primary)] bg-[var(--color-accent-soft)]'
                            : 'border-[var(--color-border)] bg-[var(--color-accent-soft)]/40 hover:border-[var(--color-primary)]'
                        }`}
                      >
                        <span className="font-semibold text-[var(--color-text-primary)] truncate">
                          {source.name}
                          {source.itemCount != null && (
                            <span className="font-normal text-[#5E6B7D] dark:text-[#AEB9CC]"> · {source.itemCount}</span>
                          )}
                          {isMockSourceId(source.id) && (
                            <span className="ml-1 font-normal text-[var(--color-warning)]">
                              · {t.pipeline.mockSource}
                            </span>
                          )}
                        </span>

                        <span
                          aria-hidden="true"
                          className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                            checked
                              ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-[var(--color-on-primary)]'
                              : 'border-[#C8D2DE] dark:border-[#273653]'
                          }`}
                        >
                          {checked && <Check className="w-3 h-3" />}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
