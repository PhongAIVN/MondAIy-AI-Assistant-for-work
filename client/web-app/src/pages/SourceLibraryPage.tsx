import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Toggle } from '../components/ui/Toggle';
import { Dialog } from '../components/ui/Dialog';
import { usePipelineRunStore } from '../stores/usePipelineRunStore';
import { resolveBrandIcon } from '../components/ui/BrandIcons';
import { useAppStore } from '../stores/useAppStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useTranslation } from '../i18n/useTranslation';
import type { TranslationKeys } from '../i18n/translations';
import { localizeGmailLabel } from '../i18n/privacyCatalog';
import {
  listConnections,
  listIntegrations,
  listIntegrationSources,
  createConnectIntent,
  disconnect as disconnectProvider,
  type ConnectionProvider,
  type ConnectionStatus,
  type IntegrationResponse,
  type SourceInfo,
} from '../lib/connectionsApi';
import { createRun, streamRunEvents, type RunNodeEvent, type SyncSourceRef } from '../lib/runsApi';
import { manualSyncUiEnabled } from '../lib/featureFlags';
import { ApiError } from '../lib/apiClient';
import { fetchAutoSyncPreference, fetchRunLimits, updateAutoSyncPreference } from '../lib/pipelineApi';
import { selectPreferredIntegration } from '../lib/integrationSelection';
import {
  DEFAULT_RUN_LIMITS,
  isConnectableProvider,
  isEnabledProvider,
  type AutoSyncPreference,
  type RunLimits,
} from '../types/pipeline';
import { ChevronDown, Layers, Plus, RefreshCw, Search, Send, ShieldCheck, Unplug, X } from 'lucide-react';
import { GoogleSheetsTaskImporter } from '../components/sources/GoogleSheetsTaskImporter';
import { GoogleDriveFilePicker } from '../components/sources/GoogleDriveFilePicker';
import { ExcelTaskImporter } from '../components/sources/ExcelTaskImporter';
import { readGoogleSheetPrefill } from '../lib/googleSheetsIntent';
import { readGoogleDocPrefill } from '../lib/googleDocsIntent';

const PROVIDER_LABEL: Record<ConnectionProvider, string> = {
  google: 'Google',
  discord: 'Discord',
  telegram: 'Telegram',
  jira: 'Jira',
  outlook: 'Outlook',
  slack: 'Slack',
};

/**
 * Map giá trị `message` mà backend `_finish(..., message=...)` gắn vào redirect
 * OAuth lỗi (xem `src/api/connections.py`) sang key text trong `sourcesPage`.
 * Giá trị lạ/chưa biết (bao gồm khi thiếu `message`) rơi về `connectFailMsg` chung.
 */
const CONNECT_FAIL_REASON_KEYS = {
  exchange_failed: 'connectFailReasonExchangeFailed',
  verify_failed: 'connectFailReasonVerifyFailed',
} as const satisfies Record<string, keyof TranslationKeys['sourcesPage']>;

/** Pure function — tách riêng để test không cần mount cả trang. */
export function resolveConnectFailMessage(
  message: string | null | undefined,
  provider: string,
  t: TranslationKeys,
): string {
  const providerLabel = PROVIDER_LABEL[provider as ConnectionProvider] || provider;
  const reasonKey = message
    ? CONNECT_FAIL_REASON_KEYS[message as keyof typeof CONNECT_FAIL_REASON_KEYS]
    : undefined;
  const template = reasonKey ? t.sourcesPage[reasonKey] : t.sourcesPage.connectFailMsg;
  return template.replace('{provider}', providerLabel);
}

const ACTIVE_SOURCES_KEY = 'mondaiy.activeSources.v1';
const PROVIDER_SYNC_KEY = 'mondaiy.providerSync.v1';
const MAX_LIVE_EVENTS = 15;
const ALL_PLATFORMS_KEY = 'all';

export function openTelegramConnectWindow(): Window | null {
  const popup = window.open('about:blank', 'mondaiy-telegram');
  if (popup) popup.opener = null;
  return popup;
}

export function navigateToTelegramLink(popup: Window | null, authorizeUrl: string): void {
  if (popup) {
    popup.location.href = authorizeUrl;
    return;
  }
  window.location.href = authorizeUrl;
}

type ProviderSources = {
  provider: ConnectionProvider;
  sources: SourceInfo[];
  error: string | null;
};

type SyncState = {
  syncing: boolean;
  events: RunNodeEvent[];
};

const EMPTY_SYNC_STATE: SyncState = { syncing: false, events: [] };

type DateRange = { from: string; to: string };

type IntegrationCatalogItem = {
  provider: ConnectionProvider;
  description: Record<'en' | 'vi', string>;
};

const INTEGRATION_CATALOG: IntegrationCatalogItem[] = [
  { provider: 'google', description: { en: 'Gmail and Google Calendar', vi: 'Gmail và Google Calendar' } },
  { provider: 'discord', description: { en: 'Read updates from selected Discord channels', vi: 'Đọc cập nhật từ các kênh Discord đã chọn' } },
  { provider: 'jira', description: { en: 'Read issues and project updates from Jira', vi: 'Đọc issue và cập nhật dự án từ Jira' } },
  // Slack bật theo ADR-016 — xem
  // docs/projects/engineering/adr/adr-016-slack-connector-pilot-scope.md.
  { provider: 'slack', description: { en: 'Read channels and DMs from selected Slack conversations', vi: 'Đọc kênh và tin nhắn trực tiếp từ các cuộc trò chuyện Slack đã chọn' } },
];

const shouldLockSourceSelection = (selected: boolean, selectedCount: number, maxSources: number): boolean =>
  !selected && selectedCount >= maxSources;

type CollapsibleSourceSectionProps = {
  title: string;
  summary: string;
  expandLabel: string;
  collapseLabel: string;
  children: React.ReactNode;
};

type TelegramConnectionPanelProps = {
  connection: ConnectionStatus;
  onConnect: () => void;
  onDisconnect: () => void;
  copy: {
    connected: string;
    notConnected: string;
    connect: string;
    disconnect: string;
    title: string;
    connectedTitle: string;
    disconnectedTitle: string;
    connectedBody: string;
    disconnectedBody: string;
    privateDelivery: string;
    summaryDelivery: string;
    reminderDelivery: string;
  };
};

export const TelegramConnectionPanel: React.FC<TelegramConnectionPanelProps> = ({
  connection,
  onConnect,
  onDisconnect,
  copy,
}) => (
  <Card className="relative overflow-hidden border-sky-200/70 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_38%),var(--color-surface)] !p-0">
    <div className="absolute inset-y-0 left-0 w-1 bg-sky-500" aria-hidden />
    <div className="space-y-5 px-5 py-5 sm:px-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3.5">
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-[14px] bg-sky-500 text-white shadow-[0_10px_28px_rgba(14,165,233,0.28)]">
            <Send className="h-5 w-5 -translate-x-px translate-y-px" aria-hidden />
          </div>
          <div className="min-w-0 pt-0.5">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-heading text-base font-bold tracking-[-0.01em] text-[var(--color-text-primary)]">
                {copy.title}
              </h3>
              <Badge variant={connection.connected ? 'success' : 'neutral'}>
                {connection.connected ? copy.connected : copy.notConnected}
              </Badge>
            </div>
            <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">
              {connection.connected ? copy.connectedTitle : copy.disconnectedTitle}
            </p>
            <p className="mt-1 max-w-xl text-xs leading-5 text-[var(--color-text-muted)]">
              {connection.connected ? copy.connectedBody : copy.disconnectedBody}
            </p>
          </div>
        </div>

        <Button
          variant={connection.connected ? 'outline' : 'primary'}
          size="sm"
          className="shrink-0 whitespace-nowrap"
          icon={connection.connected ? <Unplug className="h-3.5 w-3.5" /> : <Send className="h-3.5 w-3.5" />}
          onClick={connection.connected ? onDisconnect : onConnect}
        >
          {connection.connected ? copy.disconnect : copy.connect}
        </Button>
      </div>

      {connection.connected && connection.accountLabel && (
        <div className="flex items-center gap-2 rounded-xl bg-sky-500/10 px-3 py-2 text-xs text-[var(--color-text-primary)]">
          <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]" aria-hidden />
          <span className="font-medium">@{connection.accountLabel.replace(/^@/, '')}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-2.5">
        {[copy.privateDelivery, copy.summaryDelivery, copy.reminderDelivery].map((item) => (
          <div key={item} className="flex items-center gap-2.5 whitespace-nowrap rounded-xl bg-[var(--color-bg-secondary)]/80 px-3 py-2.5 text-xs font-medium text-[var(--color-text-secondary)]">
            <ShieldCheck className="h-4 w-4 shrink-0 text-sky-600" aria-hidden />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  </Card>
);

export const CollapsibleSourceSection: React.FC<CollapsibleSourceSectionProps> = ({
  title,
  summary,
  expandLabel,
  collapseLabel,
  children,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        aria-expanded={expanded}
        aria-label={`${title} — ${expanded ? collapseLabel : expandLabel}`}
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-center justify-between gap-3 rounded-lg px-1 py-1.5 text-left outline-none transition-colors hover:text-[var(--color-primary)] focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2"
      >
        <span className="text-xs font-bold text-[var(--color-text-primary)] font-heading">
          {title}
        </span>
        <span className="flex shrink-0 items-center gap-2 text-[11px] font-medium text-[var(--color-text-muted)]">
          {summary}
          <ChevronDown
            className={`h-4 w-4 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            aria-hidden
          />
        </span>
      </button>
      {expanded && <div className="mt-2">{children}</div>}
    </div>
  );
};

type AutoSyncPreferenceControlProps = {
  preference: AutoSyncPreference | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
  language: 'en' | 'vi';
  onChange: (enabled: boolean) => void;
  onRetry: () => void;
};

export const AutoSyncPreferenceControl: React.FC<AutoSyncPreferenceControlProps> = ({
  preference,
  loading,
  saving,
  error,
  language,
  onChange,
  onRetry,
}) => {
  const vi = language === 'vi';
  const hours = preference ? Math.max(1, Math.round(preference.autoSyncIntervalMinutes / 60)) : null;
  const description = preference?.autoSyncEnabled
    ? vi
      ? `Đang bật. Hệ thống làm mới lại đúng các nguồn của lần đồng bộ thủ công thành công gần nhất khoảng mỗi ${hours} giờ, kể cả khi đóng ứng dụng.`
      : `On. It refreshes exactly the sources from your latest successful manual sync roughly every ${hours}h, even when the app is closed.`
    : preference?.userAutoSyncEnabled
      ? vi
        ? 'Lựa chọn của bạn đã được lưu, nhưng đồng bộ nền chưa được bật cho môi trường này.'
        : 'Your preference is saved, but background sync is not enabled for this environment.'
      : vi
        ? 'Đang tắt. Bật để cho phép làm mới nền đúng các nguồn của lần đồng bộ thủ công thành công gần nhất.'
        : 'Off. Turn it on to allow background refresh of the exact sources in your latest successful manual sync.';

  return (
    <section aria-label={vi ? 'Tự động đồng bộ' : 'Automatic sync'} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <RefreshCw className={`mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)] ${saving ? 'animate-spin' : ''}`} aria-hidden />
          <div>
            <p className="font-heading text-sm font-bold text-[var(--color-text-primary)]">{vi ? 'Tự động đồng bộ' : 'Automatic sync'}</p>
            <p className="mt-0.5 text-xs leading-5 text-[var(--color-text-secondary)]">
              {loading ? (vi ? 'Đang tải lựa chọn của bạn…' : 'Loading your preference…') : description}
            </p>
          </div>
        </div>
        <Toggle
          checked={preference?.userAutoSyncEnabled ?? false}
          disabled={loading || saving || preference === null || error !== null}
          onChange={onChange}
          aria-label={vi ? 'Bật hoặc tắt tự động đồng bộ' : 'Turn automatic sync on or off'}
        />
      </div>
      <p className="mt-2 text-[11px] leading-4 text-[var(--color-text-muted)]">
        {vi
          ? 'Không tự chọn nguồn mới. Chưa có lần đồng bộ thủ công thành công thì không có gì được lên lịch.'
          : 'It never selects new sources. Without a successful manual sync, nothing is scheduled.'}
      </p>
      {error && (
        <div role="alert" className="mt-3 flex items-center justify-between gap-3 text-xs text-[var(--color-danger)]">
          <span>{error}</span>
          <Button variant="outline" size="xs" onClick={onRetry}>{vi ? 'Thử lại' : 'Retry'}</Button>
        </div>
      )}
    </section>
  );
};

const readJsonMap = (key: string): Record<string, boolean> => {
  try {
    return JSON.parse(localStorage.getItem(key) || '{}');
  } catch {
    return {};
  }
};

const writeJsonMap = (key: string, map: Record<string, boolean>): void => {
  localStorage.setItem(key, JSON.stringify(map));
};

const toDatetimeLocal = (date: Date): string => {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const defaultDateRange = (): DateRange => ({
  from: toDatetimeLocal(new Date(Date.now() - 7 * 24 * 3600 * 1000)),
  to: toDatetimeLocal(new Date()),
});

export const SourceLibraryPage: React.FC = () => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { addToast } = useAppStore();
  const accessToken = useAuthStore((s) => s.accessToken);

  const [connections, setConnections] = useState<ConnectionStatus[] | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [sourcesByIntegration, setSourcesByIntegration] = useState<Record<number, ProviderSources>>({});
  const [runLimits, setRunLimits] = useState<RunLimits>(DEFAULT_RUN_LIMITS);
  const [autoSyncPreference, setAutoSyncPreference] = useState<AutoSyncPreference | null>(null);
  const [autoSyncPreferenceLoading, setAutoSyncPreferenceLoading] = useState(true);
  const [autoSyncPreferenceSaving, setAutoSyncPreferenceSaving] = useState(false);
  const [autoSyncPreferenceError, setAutoSyncPreferenceError] = useState<string | null>(null);
  const [activeSourceMap, setActiveSourceMap] = useState<Record<string, boolean>>(
    () => readJsonMap(ACTIVE_SOURCES_KEY),
  );
  const [providerSyncMap, setProviderSyncMap] = useState<Record<string, boolean>>(
    () => readJsonMap(PROVIDER_SYNC_KEY),
  );
  const [addIntegrationOpen, setAddIntegrationOpen] = useState(false);
  const [integrationQuery, setIntegrationQuery] = useState('');
  const [integrationCategory, setIntegrationCategory] = useState<'featured' | 'connected' | 'all'>('featured');
  const [loadError, setLoadError] = useState<string | null>(null);

  const [dateRangeByKey, setDateRangeByKey] = useState<Record<string, DateRange>>({});
  const [syncStateByKey, setSyncStateByKey] = useState<Record<string, SyncState>>({});
  const abortRefs = useRef<Record<string, AbortController>>({});
  const telegramAutoConnectStarted = useRef(false);
  const googleAutoConnectStarted = useRef(false);
  const googleSheetPrefill = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const url = params.get('googleSheetUrl');
    const sheetName = params.get('googleSheetTab');
    if (url) return { spreadsheetUrl: url, sheetName: sheetName || 'Backlog' };
    return readGoogleSheetPrefill();
  }, [location.search]);
  const googleDocPrefill = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const url = params.get('googleDocsUrl');
    return url ? { documentUrl: url } : readGoogleDocPrefill();
  }, [location.search]);

  const reload = useCallback(async () => {
    if (!accessToken) return;
    setLoadError(null);
    setAutoSyncPreferenceLoading(true);
    setAutoSyncPreferenceError(null);
    try {
      const [{ connections: conns }, { integrations: ints }] = await Promise.all([
        listConnections(accessToken),
        listIntegrations(accessToken),
      ]);
      setConnections(conns.filter((c) => isConnectableProvider(c.provider)));
      setIntegrations(ints.filter((i) => isEnabledProvider(i.provider)));
      try {
        setRunLimits(await fetchRunLimits(accessToken));
      } catch {
        // Không chặn danh sách nguồn nếu server tạm thời không trả được hạn mức.
      }
      try {
        setAutoSyncPreference(await fetchAutoSyncPreference(accessToken));
      } catch (err) {
        setAutoSyncPreferenceError(err instanceof ApiError ? err.message : t.sourcesPage.unknownError);
      }

      const entries = await Promise.all(
        ints
          .filter((i) => isEnabledProvider(i.provider))
          .map(async (integration): Promise<[number, ProviderSources]> => {
            try {
              const { sources } = await listIntegrationSources(integration.id, accessToken);
              return [integration.id, { provider: integration.provider, sources, error: null }];
            } catch (err) {
              return [
                integration.id,
                {
                  provider: integration.provider,
                  sources: [],
                  error: err instanceof ApiError ? err.message : t.sourcesPage.unknownError,
                },
              ];
            }
          }),
      );
      setSourcesByIntegration(Object.fromEntries(entries));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : t.sourcesPage.loadError);
    } finally {
      setAutoSyncPreferenceLoading(false);
    }
  }, [accessToken, t.sourcesPage.loadError, t.sourcesPage.unknownError]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const status = params.get('status');
    const provider = params.get('provider') as ConnectionProvider | null;
    const message = params.get('message');
    if (status && provider) {
      addToast({
        type: status === 'connected' ? 'success' : 'error',
        title:
          status === 'connected'
            ? t.sourcesPage.connectSuccessTitle
            : t.sourcesPage.connectFailTitle,
        message:
          status === 'connected'
            ? t.sourcesPage.connectSuccessMsg.replace('{provider}', PROVIDER_LABEL[provider] || provider)
            : resolveConnectFailMessage(message, provider, t),
      });
      navigate(location.pathname, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => () => Object.values(abortRefs.current).forEach((c) => c.abort()), []);

  const isProviderSyncOn = (provider: ConnectionProvider): boolean => providerSyncMap[provider] ?? true;

  const setProviderSync = (provider: ConnectionProvider, on: boolean) => {
    const next = { ...providerSyncMap, [provider]: on };
    setProviderSyncMap(next);
    writeJsonMap(PROVIDER_SYNC_KEY, next);
  };

  const handleAutoSyncPreferenceChange = async (enabled: boolean) => {
    if (!accessToken || autoSyncPreferenceSaving) return;
    setAutoSyncPreferenceSaving(true);
    setAutoSyncPreferenceError(null);
    try {
      setAutoSyncPreference(await updateAutoSyncPreference(enabled, accessToken));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t.sourcesPage.unknownError;
      setAutoSyncPreferenceError(message);
      addToast({ type: 'error', title: t.sourcesPage.syncFailTitle, message });
    } finally {
      setAutoSyncPreferenceSaving(false);
    }
  };

  const isSourceActive = (integrationId: number, sourceId: string): boolean => {
    const key = `${integrationId}:${sourceId}`;
    return activeSourceMap[key] ?? true;
  };

  const activeSourceCount = (): number =>
    integrations.reduce(
      (count, integration) =>
        count + (sourcesByIntegration[integration.id]?.sources ?? []).filter((source) => isSourceActive(integration.id, source.id)).length,
      0,
    );

  const toggleSource = (integrationId: number, sourceId: string) => {
    const key = `${integrationId}:${sourceId}`;
    if (!isSourceActive(integrationId, sourceId) && activeSourceCount() >= runLimits.maxSyncSources) {
      addToast({
        type: 'warning',
        title: t.sourcesPage.sourceLimitTitle,
        message: t.sourcesPage.sourceLimitMessage.replace('{max}', String(runLimits.maxSyncSources)),
      });
      return;
    }
    const next = { ...activeSourceMap, [key]: !isSourceActive(integrationId, sourceId) };
    setActiveSourceMap(next);
    writeJsonMap(ACTIVE_SOURCES_KEY, next);
  };

  const handleConnect = useCallback(async (provider: ConnectionProvider) => {
    if (!accessToken) return;
    // Telegram must be opened synchronously from the click. Opening it after
    // awaiting the intent API is treated as an unsolicited popup by browsers.
    const telegramWindow = provider === 'telegram' ? openTelegramConnectWindow() : null;
    try {
      const cleanReturnUrl = `${window.location.origin}${window.location.pathname}`;
      const { authorizeUrl } = await createConnectIntent(provider, cleanReturnUrl, accessToken);
      if (provider === 'telegram') {
        navigateToTelegramLink(telegramWindow, authorizeUrl);
        window.setTimeout(() => void reload(), 1500);
      } else {
        window.location.href = authorizeUrl;
      }
    } catch (err) {
      telegramWindow?.close();
      addToast({
        type: 'error',
        title: t.sourcesPage.connectStartFail,
        message: err instanceof ApiError ? err.message : t.sourcesPage.unknownError,
      });
    }
  }, [accessToken, addToast, reload, t.sourcesPage.connectStartFail, t.sourcesPage.unknownError]);

  useEffect(() => {
    const telegram = connections?.find((connection) => connection.provider === 'telegram');
    if (telegram?.connected) return;
    const refreshOnFocus = () => void reload();
    window.addEventListener('focus', refreshOnFocus);
    return () => window.removeEventListener('focus', refreshOnFocus);
  }, [connections, reload]);

  useEffect(() => {
    const wantsTelegram = new URLSearchParams(location.search).get('connect') === 'telegram';
    const telegram = connections?.find((connection) => connection.provider === 'telegram');
    if (!wantsTelegram || !telegram || telegram.connected || telegramAutoConnectStarted.current) return;
    telegramAutoConnectStarted.current = true;
    void handleConnect('telegram');
  }, [connections, handleConnect, location.search]);

  useEffect(() => {
    const wantsGoogle = new URLSearchParams(location.search).get('connect') === 'google';
    const google = connections?.find((connection) => connection.provider === 'google');
    if (!wantsGoogle || !google || google.connected || googleAutoConnectStarted.current) return;
    googleAutoConnectStarted.current = true;
    void handleConnect('google');
  }, [connections, handleConnect, location.search]);

  const [disconnectTarget, setDisconnectTarget] = useState<ConnectionProvider | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const handleDisconnect = async (provider: ConnectionProvider) => {
    if (!accessToken) return;
    setDisconnecting(true);
    try {
      await disconnectProvider(provider, accessToken);
      addToast({
        type: 'info',
        title: t.sourcesPage.disconnectTitle,
        message: t.sourcesPage.disconnectMsg.replace('{provider}', PROVIDER_LABEL[provider]),
      });
      setDisconnectTarget(null);
      await reload();
      // usePipelineRunStore giữ bản riêng của danh sách connections cho
      // Sidebar/CommandPalette/SourcePicker — không nối vào thì các UI đó vẫn
      // hiện "đã kết nối" cho tới khi người dùng tự tải lại trang.
      void usePipelineRunStore.getState().loadConnections();
    } catch (err) {
      addToast({
        type: 'error',
        title: t.sourcesPage.disconnectFail,
        message: err instanceof ApiError ? err.message : t.sourcesPage.unknownError,
      });
    } finally {
      setDisconnecting(false);
    }
  };

  const getDateRange = (key: string): DateRange => dateRangeByKey[key] ?? defaultDateRange();

  const setDateRangeField = (key: string, field: 'from' | 'to', value: string) => {
    setDateRangeByKey((prev) => ({ ...prev, [key]: { ...getDateRange(key), [field]: value } }));
  };

  const parseDateRange = (range: DateRange): { fromDate: Date; toDate: Date } | null => {
    const fromDate = new Date(range.from);
    const toDate = new Date(range.to);
    if (Number.isNaN(fromDate.getTime()) || Number.isNaN(toDate.getTime()) || fromDate >= toDate) {
      addToast({
        type: 'warning',
        title: t.sourcesPage.invalidRangeTitle,
        message: t.sourcesPage.invalidRangeMsg,
      });
      return null;
    }
    return { fromDate, toDate };
  };

  // Extra Gmail prototype không đưa vào createRun — chỉ Gmail OAuth chính.
  const runSync = async (key: string, sources: SyncSourceRef[], label: string) => {
    if (!accessToken || sources.length === 0) {
      addToast({
        type: 'warning',
        title: t.sourcesPage.noSourcesSelectedTitle,
        message: t.sourcesPage.noSourcesSelectedMsg,
      });
      return;
    }
    if (sources.length > runLimits.maxSyncSources) {
      addToast({
        type: 'warning',
        title: t.sourcesPage.sourceLimitTitle,
        message: t.sourcesPage.sourceLimitMessage.replace('{max}', String(runLimits.maxSyncSources)),
      });
      return;
    }
    const range = parseDateRange(getDateRange(key));
    if (!range) return;

    setSyncStateByKey((prev) => ({ ...prev, [key]: { syncing: true, events: [] } }));
    try {
      const run = await createRun(
        {
          sources,
          timeFrom: range.fromDate.toISOString(),
          timeTo: range.toDate.toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          language,
          idempotencyKey: crypto.randomUUID(),
        },
        accessToken,
      );

      const controller = new AbortController();
      abortRefs.current[key] = controller;
      let tasksPersisted = 0;
      let sawError = false;

      await streamRunEvents(
        run.id,
        accessToken,
        (event) => {
          setSyncStateByKey((prev) => {
            const current = prev[key] ?? EMPTY_SYNC_STATE;
            const events = [...current.events, event].slice(-MAX_LIVE_EVENTS);
            return { ...prev, [key]: { syncing: true, events } };
          });
          if (event.node === 'done') tasksPersisted = event.count ?? 0;
          if (event.status === 'error') sawError = true;
        },
        controller.signal,
      );

      if (sawError) {
        addToast({
          type: 'error',
          title: t.sourcesPage.syncErrorTitle,
          message: `${label}: ${t.sourcesPage.syncErrorMsg}`,
        });
      } else {
        addToast({
          type: 'success',
          title: t.sourcesPage.syncDoneTitle,
          message:
            tasksPersisted > 0
              ? `${label}: ${t.sourcesPage.syncDoneTasks.replace('{count}', String(tasksPersisted))}`
              : `${label}: ${t.sourcesPage.syncDoneEmpty}`,
        });
      }
    } catch (err) {
      addToast({
        type: 'error',
        title: t.sourcesPage.syncFailTitle,
        message: err instanceof ApiError ? err.message : t.sourcesPage.unknownError,
      });
    } finally {
      setSyncStateByKey((prev) => ({ ...prev, [key]: { syncing: false, events: prev[key]?.events ?? [] } }));
    }
  };

  const handleForceSyncIntegration = (integration: IntegrationResponse) => {
    const entry = sourcesByIntegration[integration.id];
    const activeSources = (entry?.sources ?? []).filter((s) => isSourceActive(integration.id, s.id));
    void runSync(
      String(integration.id),
      activeSources.map((s) => ({ connectionId: integration.id, sourceId: s.id })),
      PROVIDER_LABEL[integration.provider],
    );
  };

  const handleForceSyncAll = () => {
    const sources: SyncSourceRef[] = [];
    for (const integration of integrations) {
      if (!isProviderSyncOn(integration.provider)) continue;
      const entry = sourcesByIntegration[integration.id];
      if (!entry || entry.error) continue;
      for (const s of entry.sources) {
        if (isSourceActive(integration.id, s.id)) {
          sources.push({ connectionId: integration.id, sourceId: s.id });
        }
      }
    }
    void runSync(ALL_PLATFORMS_KEY, sources, t.sourcesPage.syncAllTitle);
  };

  const getProviderIcon = (provider: ConnectionProvider) =>
    resolveBrandIcon(provider, 'w-5 h-5') ?? <Send className="w-5 h-5 text-[var(--color-primary)]" />;

  const renderLiveFeed = (events: RunNodeEvent[]) => {
    if (events.length === 0) return null;
    return (
      <div className="pt-2 border-t border-[var(--color-border-subtle)] space-y-1.5 max-h-40 overflow-y-auto">
        {events.map((ev, idx) => (
          <div key={idx} className="flex items-center justify-between text-xs gap-2">
            <span
              className={
                ev.status === 'error'
                  ? 'text-[var(--color-danger)] font-semibold shrink-0'
                  : 'text-[var(--color-text-primary)] shrink-0'
              }
            >
              {ev.node}
            </span>
            <span className="text-[var(--color-text-muted)] truncate">
              {ev.count !== null ? `${ev.count} · ` : ''}
              {ev.message || (ev.status === 'ok' ? 'OK' : '')}
            </span>
          </div>
        ))}
      </div>
    );
  };

  const renderDateRangeInputs = (key: string) => {
    const range = getDateRange(key);
    return (
      <div className="flex items-end gap-3">
        <label className="text-xs font-semibold text-[var(--color-text-primary)] space-y-1">
          <span className="block">{t.sourcesPage.from}</span>
          <input
            type="datetime-local"
            value={range.from}
            onChange={(e) => setDateRangeField(key, 'from', e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-[var(--color-text-primary)]"
          />
        </label>
        <label className="text-xs font-semibold text-[var(--color-text-primary)] space-y-1">
          <span className="block">{t.sourcesPage.to}</span>
          <input
            type="datetime-local"
            value={range.to}
            onChange={(e) => setDateRangeField(key, 'to', e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-[var(--color-text-primary)]"
          />
        </label>
      </div>
    );
  };

  const renderSourceToggleList = (integrationId: number, sources: SourceInfo[]) => (
    <div className="space-y-2">
      {sources.map((src) => (
        <div
          key={src.id}
          className="flex items-center justify-between gap-3 p-2.5 bg-[var(--color-accent-soft)] border border-[var(--color-border-subtle)] rounded-lg text-xs"
        >
          <div className="min-w-0">
            <span className="font-bold text-[var(--color-text-primary)] block truncate">
              {localizeGmailLabel(src.id, src.name, language)}
            </span>
            {src.itemCount !== null && (
              <span className="text-[10px] text-[var(--color-text-muted)]">
                {t.sourcesPage.itemCount.replace('{count}', String(src.itemCount))}
              </span>
            )}
          </div>
          <Toggle
            checked={isSourceActive(integrationId, src.id)}
            onChange={() => toggleSource(integrationId, src.id)}
            aria-label={src.name}
            disabled={shouldLockSourceSelection(isSourceActive(integrationId, src.id), activeSourceCount(), runLimits.maxSyncSources)}
          />
        </div>
      ))}
    </div>
  );

  const renderProviderCard = (conn: ConnectionStatus, options?: { primaryGmail?: boolean }) => {
    if (conn.provider === 'telegram') {
      return (
        <TelegramConnectionPanel
          key={conn.provider}
          connection={conn}
          onConnect={() => handleConnect('telegram')}
          onDisconnect={() => setDisconnectTarget('telegram')}
          copy={{
            connected: t.sourcesPage.connected,
            notConnected: t.sourcesPage.notConnected,
            connect: t.sourcesPage.connect,
            disconnect: t.sourcesPage.disconnect,
            title: t.sourcesPage.telegramPanelTitle,
            connectedTitle: t.sourcesPage.telegramConnectedTitle,
            disconnectedTitle: t.sourcesPage.telegramDisconnectedTitle,
            connectedBody: t.sourcesPage.telegramConnectedBody,
            disconnectedBody: t.sourcesPage.telegramDisconnectedBody,
            privateDelivery: t.sourcesPage.telegramPrivateDelivery,
            summaryDelivery: t.sourcesPage.telegramSummaryDelivery,
            reminderDelivery: t.sourcesPage.telegramReminderDelivery,
          }}
        />
      );
    }
    const integration = selectPreferredIntegration(integrations, conn.provider);
    const entry = integration ? sourcesByIntegration[integration.id] : undefined;
    const syncState = integration ? syncStateByKey[String(integration.id)] ?? EMPTY_SYNC_STATE : EMPTY_SYNC_STATE;
    const unsupported = Boolean(entry?.error);
    // Nút Sync tay ẩn sau cờ: đồng bộ nay do trang chat tự kéo. Phần tick
    // chọn nguồn vẫn giữ nguyên — người dùng vẫn phải nói rõ quét cái gì.
    const syncOn = isProviderSyncOn(conn.provider) && manualSyncUiEnabled();

    return (
      <Card key={conn.provider} className="space-y-5 rounded-2xl border-[var(--color-border)] bg-[var(--color-surface-muted)] p-6 shadow-none">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex shrink-0 items-center justify-center">
              {getProviderIcon(conn.provider)}
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading flex items-center gap-2 flex-wrap">
                {PROVIDER_LABEL[conn.provider]}
                {conn.connected && conn.needsReconnect ? (
                  <Badge variant="warning">{t.sourcesPage.needsReconnect}</Badge>
                ) : conn.connected ? (
                  <Badge variant="success">{t.sourcesPage.connected}</Badge>
                ) : (
                  <Badge variant="neutral">{t.sourcesPage.notConnected}</Badge>
                )}
                {options?.primaryGmail && conn.connected && (
                  <Badge variant="neutral">{t.sourcesPage.gmailPrimaryBadge}</Badge>
                )}
              </h3>
              {conn.accountLabel && (
                <p className="text-[11px] text-[var(--color-text-muted)] truncate">
                  {conn.accountLabel}
                </p>
              )}
              {conn.connected && conn.needsReconnect && (
                <p className="mt-0.5 text-[11px] text-[var(--color-warning)]">
                  {t.sourcesPage.needsReconnectHint}
                </p>
              )}
            </div>
          </div>

          {conn.connected && conn.needsReconnect ? (
            <Button
              variant="primary"
              size="sm"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => handleConnect(conn.provider)}
            >
              {t.sourcesPage.reconnect}
            </Button>
          ) : conn.connected ? (
            <Button
              variant="outline"
              size="sm"
              icon={<Unplug className="w-3.5 h-3.5" />}
              onClick={() => setDisconnectTarget(conn.provider)}
            >
              {t.sourcesPage.disconnect}
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => handleConnect(conn.provider)}
              data-tour-action={conn.provider === 'google' ? 'connect-google' : undefined}
            >
              {t.sourcesPage.connect}
            </Button>
          )}
        </div>

        {conn.connected && integration && (
          <div className="space-y-3 border-t border-[var(--color-border)] pt-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="text-xs font-bold text-[var(--color-text-primary)] block font-heading">
                  {t.sourcesPage.manualSyncInclude}
                </span>
                <span className="text-[11px] text-[var(--color-text-muted)]">
                  {syncOn ? t.sourcesPage.manualSyncActive : t.sourcesPage.manualSyncPaused}
                </span>
              </div>
              <Toggle
                checked={syncOn}
                onChange={(on) => setProviderSync(conn.provider, on)}
                aria-label={t.sourcesPage.manualSyncInclude}
              />
            </div>

            {syncOn && unsupported && (
              <p className="text-xs text-[var(--color-text-muted)]">
                {t.sourcesPage.unsupportedProvider.replace('{error}', entry?.error ?? '')}
              </p>
            )}

            {syncOn && !unsupported && (
              <CollapsibleSourceSection
                title={conn.provider === 'google' ? t.sourcesPage.gmailLabels : t.sourcesPage.monitoredChannels}
                summary={t.sourcesPage.sourceListSelected
                  .replace(
                    '{selected}',
                    String((entry?.sources ?? []).filter((source) => isSourceActive(integration.id, source.id)).length),
                  )
                  .replace('{total}', String(entry?.sources.length ?? 0))}
                expandLabel={t.sourcesPage.expandSourceList}
                collapseLabel={t.sourcesPage.collapseSourceList}
              >
                {(entry?.sources.length ?? 0) === 0 ? (
                  <p className="text-xs text-[var(--color-text-muted)]">{t.sourcesPage.labelsEmpty}</p>
                ) : (
                  renderSourceToggleList(integration.id, entry?.sources ?? [])
                )}
              </CollapsibleSourceSection>
            )}

            {syncOn && (
              <Button
                variant="primary"
                size="sm"
                icon={<RefreshCw className={`w-3.5 h-3.5 ${syncState.syncing ? 'animate-spin' : ''}`} />}
                onClick={() => handleForceSyncIntegration(integration)}
                disabled={syncState.syncing || unsupported}
              >
                {syncState.syncing ? t.sourcesPage.syncing : t.sourcesPage.forceSync}
              </Button>
            )}

            {/* Khoảng thời gian tuỳ chỉnh và log realtime dồn vào một khối
                thu gọn — đồng bộ nhanh dùng khoảng mặc định, không cần mở. */}
            {syncOn && !unsupported && (
              <CollapsibleSourceSection
                title={t.sourcesPage.advancedOptions}
                summary={t.sourcesPage.advancedHint}
                expandLabel={t.sourcesPage.expandAdvanced}
                collapseLabel={t.sourcesPage.collapseAdvanced}
              >
                <div className="space-y-3">
                  {renderDateRangeInputs(String(integration.id))}
                  {renderLiveFeed(syncState.events)}
                </div>
              </CollapsibleSourceSection>
            )}
          </div>
        )}
      </Card>
    );
  };

  const googleConn = connections?.find((c) => c.provider === 'google');
  const otherConns = (connections ?? []).filter((c) => c.provider !== 'google');
  const allSupportedCount = integrations.filter((i) => !sourcesByIntegration[i.id]?.error).length;

  return (
    <div className="mx-auto max-w-6xl space-y-8 pb-10 animate-in fade-in duration-200">
      <div className="flex flex-col gap-5 border-b border-[var(--color-border)] pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">
            <Layers className="w-4 h-4" /> {t.sourcesPage.connectedIntegrations}
          </div>
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            {t.sourcesPage.title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">{t.sourcesPage.subtitle}</p>
        </div>
        <Button variant="primary" size="md" icon={<Plus className="h-4 w-4" />} onClick={() => setAddIntegrationOpen(true)}>
          {t.sourcesPage.addIntegration}
        </Button>
      </div>

      <AutoSyncPreferenceControl
        preference={autoSyncPreference}
        loading={autoSyncPreferenceLoading}
        saving={autoSyncPreferenceSaving}
        error={autoSyncPreferenceError}
        language={language}
        onChange={(enabled) => void handleAutoSyncPreferenceChange(enabled)}
        onRetry={() => void reload()}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
          <Badge variant="neutral">{activeSourceCount()}/{runLimits.maxSyncSources}</Badge>
          <span>{t.sourcesPage.manualSourceLimit}</span>
        </div>
        <span className="text-xs text-[var(--color-text-muted)]">
          {language === 'vi' ? `${connections?.filter((connection) => connection.connected).length ?? 0} nền tảng đang hoạt động` : `${connections?.filter((connection) => connection.connected).length ?? 0} active platforms`}
        </span>
      </div>

      {loadError && (
        <Card className="border-[var(--color-danger)] text-xs text-[var(--color-danger)]">{loadError}</Card>
      )}

      <div data-tour-id="sources-connected-grid" className="space-y-6">
      <div className="space-y-3">
        <div>
          <h2 className="font-heading text-xl font-semibold text-[var(--color-text-primary)]">
            {language === 'vi' ? 'Đang kết nối' : 'Connected integrations'}
          </h2>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            {language === 'vi' ? 'Những nền tảng Mondaiy có thể đọc dữ liệu cho bạn.' : 'Platforms Mondaiy can read data from.'}
          </p>
        </div>
      {accessToken && <ExcelTaskImporter accessToken={accessToken} />}
      {googleConn && (
        <section data-tour-id="sources-google-primary" data-tour-source-connected={String(googleConn.connected)}>
          {renderProviderCard(googleConn, { primaryGmail: true })}
          {googleConn.connected && accessToken && (
            <div className="mt-4 space-y-4" data-tour-id="sources-google-sheets-import">
              <GoogleDriveFilePicker accessToken={accessToken} />
              {googleDocPrefill?.documentUrl && (
                <p className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3 text-xs text-[var(--color-text-secondary)]">
                  Đã nhận diện Google Docs: <span className="break-all">{googleDocPrefill.documentUrl}</span>. Chọn tài liệu trong Google Drive để quét task.
                </p>
              )}
              <GoogleSheetsTaskImporter
                accessToken={accessToken}
                initialSpreadsheetUrl={googleSheetPrefill?.spreadsheetUrl}
                initialSheetName={googleSheetPrefill?.sheetName}
              />
            </div>
          )}
        </section>
      )}

      {otherConns.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {otherConns.map((conn) => renderProviderCard(conn))}
        </div>
      )}
      </div>
      </div>

      {/* Wrapper luôn render dù chưa có integration nào — anchor tour cần tồn
          tại sẵn, không đợi API trả integrations mới có chỗ để trỏ vào. */}
      <div data-tour-id="sources-sync-all">
        {integrations.length > 0 && (
          <Card className="space-y-4">
            <div>
              <h2 className="text-sm font-bold text-[var(--color-text-primary)] font-heading">
                {t.sourcesPage.syncAllTitle}
              </h2>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {t.sourcesPage.syncAllSubtitle.replace('{count}', String(allSupportedCount))}
              </p>
            </div>

          {manualSyncUiEnabled() && (
            <Button
              variant="primary"
              size="sm"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${syncStateByKey[ALL_PLATFORMS_KEY]?.syncing ? 'animate-spin' : ''}`} />}
              onClick={handleForceSyncAll}
              disabled={syncStateByKey[ALL_PLATFORMS_KEY]?.syncing || allSupportedCount === 0}
              data-tour-id="sources-sync-all"
            >
              {syncStateByKey[ALL_PLATFORMS_KEY]?.syncing ? t.sourcesPage.syncing : t.sourcesPage.syncAllButton}
            </Button>
          )}

          <CollapsibleSourceSection
            title={t.sourcesPage.advancedOptions}
            summary={t.sourcesPage.advancedHint}
            expandLabel={t.sourcesPage.expandAdvanced}
            collapseLabel={t.sourcesPage.collapseAdvanced}
          >
            <div className="space-y-3">
              {renderDateRangeInputs(ALL_PLATFORMS_KEY)}
              {renderLiveFeed(syncStateByKey[ALL_PLATFORMS_KEY]?.events ?? [])}
            </div>
          </CollapsibleSourceSection>
        </Card>
      )}
      </div>

      <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-secondary)]">
        <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-success)]" />
        {t.sourcesPage.readOnlyFooter}
      </div>

      {addIntegrationOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--color-app-bg)]/80 p-4 backdrop-blur-md" role="dialog" aria-modal="true" aria-label={t.sourcesPage.addIntegration}>
          <div className="flex max-h-[92vh] w-full max-w-6xl overflow-hidden rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
            <aside className="hidden w-52 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 md:block">
              <div className="mb-5 px-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                {language === 'vi' ? 'Danh mục' : 'Categories'}
              </div>
              <div className="space-y-1">
                {([
                  ['featured', language === 'vi' ? 'Nổi bật' : 'Featured'],
                  ['connected', language === 'vi' ? 'Đã kết nối' : 'Connected'],
                  ['all', language === 'vi' ? 'Tất cả' : 'All integrations'],
                ] as const).map(([key, label]) => (
                  <button key={key} type="button" onClick={() => setIntegrationCategory(key)} className={`flex w-full items-center rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${integrationCategory === key ? 'bg-[var(--color-surface-hover)] text-[var(--color-text-primary)]' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'}`}>
                    {label}
                  </button>
                ))}
              </div>
            </aside>
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-6 py-5">
                <div>
                  <h2 className="font-heading text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">{t.sourcesPage.addIntegration}</h2>
                  <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{t.sourcesPage.addIntegrationHint}</p>
                </div>
                <button type="button" onClick={() => setAddIntegrationOpen(false)} aria-label={t.actions.close} className="rounded-full p-2 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]"><X className="h-5 w-5" /></button>
              </div>
              <div className="min-h-0 overflow-y-auto p-6">
                <div className="flex flex-col gap-3 sm:flex-row">
                  <label className="flex flex-1 items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3.5 py-3 text-[var(--color-text-muted)] focus-within:border-[var(--color-accent)]">
                    <Search className="h-4 w-4" aria-hidden />
                    <input autoFocus value={integrationQuery} onChange={(event) => setIntegrationQuery(event.target.value)} placeholder={t.sourcesPage.searchIntegrations} className="w-full bg-transparent text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]" />
                  </label>
                </div>
                <div className="mb-4 mt-8 flex items-center justify-between">
                  <h3 className="font-heading text-lg font-semibold text-[var(--color-text-primary)]">{language === 'vi' ? (integrationCategory === 'connected' ? 'Đã kết nối' : 'Tích hợp') : (integrationCategory === 'connected' ? 'Connected' : 'Integrations')}</h3>
                  <span className="text-xs text-[var(--color-text-muted)]">{INTEGRATION_CATALOG.length} {language === 'vi' ? 'nguồn' : 'sources'}</span>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  {INTEGRATION_CATALOG.filter((item) => {
                    const connection = connections?.find((candidate) => candidate.provider === item.provider);
                    const matchesCategory = integrationCategory !== 'connected' || connection?.connected;
                    return matchesCategory && `${PROVIDER_LABEL[item.provider]} ${item.description[language]}`.toLowerCase().includes(integrationQuery.toLowerCase());
                  }).map((item) => {
                    const connection = connections?.find((candidate) => candidate.provider === item.provider);
                    return <div key={item.provider} className="flex min-h-36 flex-col justify-between rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-5 transition-colors hover:border-[var(--color-accent)]">
                      <div className="flex items-start justify-between gap-3"><div className="flex min-w-0 items-center gap-3"><div className="flex shrink-0 items-center justify-center">{getProviderIcon(item.provider)}</div><div><p className="font-semibold text-[var(--color-text-primary)]">{PROVIDER_LABEL[item.provider]}</p><p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">{item.description[language]}</p></div></div>{connection?.connected && <Badge variant="success">{t.sourcesPage.connected}</Badge>}</div>
                      <div className="mt-5">{!connection?.connected && <Button size="sm" variant="outline" onClick={() => void handleConnect(item.provider)}>{t.sourcesPage.connect}</Button>}</div>
                    </div>;
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <Dialog
        isOpen={disconnectTarget !== null}
        onClose={() => setDisconnectTarget(null)}
        title={t.sourcesPage.disconnectConfirmTitle.replace('{provider}', disconnectTarget ? PROVIDER_LABEL[disconnectTarget] : '')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDisconnectTarget(null)}>{t.sourcesPage.disconnectConfirmCancel}</Button>
            <Button
              variant="danger"
              icon={<Unplug className="w-3.5 h-3.5" />}
              disabled={disconnecting}
              onClick={() => disconnectTarget && void handleDisconnect(disconnectTarget)}
            >
              {disconnecting ? t.sourcesPage.disconnecting : t.sourcesPage.disconnectConfirmAction}
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-secondary)]">{t.sourcesPage.disconnectConfirmBody}</p>
      </Dialog>
    </div>
  );
};
