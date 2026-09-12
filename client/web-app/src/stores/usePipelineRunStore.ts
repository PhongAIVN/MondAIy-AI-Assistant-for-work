import { create } from 'zustand';
import { useAuthStore } from './useAuthStore';
import { usePreferencesStore } from './usePreferencesStore';
import { getTranslations } from '../i18n/useTranslation';
import { loadedSourceListState } from '../lib/sourceListState';
import {
  confirmTask as confirmTaskApi,
  createCalendarHandoff,
  createConnectIntent,
  disconnectProvider,
  dismissTask as dismissTaskApi,
  fetchRunLimits,
  listConnections,
  listIntegrationSources,
  listIntegrations,
  markCalendarHandoffOpened,
  runPipeline,
  type PipelineTransport,
} from '../lib/pipelineApi';
import {
  DEFAULT_RUN_LIMITS,
  PIPELINE_NODES,
  type Brief,
  type CalendarHandoffResponse,
  type ConnectionProvider,
  type ConnectionStatus,
  type Integration,
  type PipelineNode,
  type PipelineNodeProgress,
  type RunLimits,
  type RunNodeEventPayload,
  type RunResponse,
  type SourceInfo,
  type SyncSourceRef,
  type Task,
} from '../types/pipeline';

export type RangePreset = '24h' | '3d' | '7d' | 'custom';

export type RunPhase = 'idle' | 'running' | 'succeeded' | 'failed' | 'cancelled';

/** Danh sách nguồn con của một integration, kèm lý do nếu backend chưa hỗ trợ. */
export type SourceListState = {
  loading: boolean;
  items: SourceInfo[];
  unsupported?: string;
  warnings?: string[];
  error?: string;
};

const emptyNodes = (): Record<PipelineNode, PipelineNodeProgress> =>
  PIPELINE_NODES.reduce(
    (acc, node) => {
      acc[node] = { node, status: 'pending' };
      return acc;
    },
    {} as Record<PipelineNode, PipelineNodeProgress>,
  );

const PRESET_HOURS: Record<Exclude<RangePreset, 'custom'>, number> = {
  '24h': 24,
  '3d': 72,
  '7d': 168,
};

/** ISO 8601 giữ offset địa phương — node resolve cần offset thật để tính giờ. */
const toLocalIso = (date: Date): string => {
  const pad = (v: number) => String(v).padStart(2, '0');
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const abs = Math.abs(offsetMinutes);
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  );
};

const sameSource = (a: SyncSourceRef, b: SyncSourceRef): boolean =>
  a.connectionId === b.connectionId && a.sourceId === b.sourceId;

const isValidTimezone = (value: string): boolean => {
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: value });
    return true;
  } catch {
    return false;
  }
};

/**
 * Múi giờ gửi lên backend: lấy theo khai báo của người dùng ở trang Hồ sơ
 * (Program Frame mục 2, FR-001), không lấy múi giờ của máy. Người dùng đi công
 * tác không làm hạn chót của chương trình chạy lệch.
 *
 * Bản cũ lưu chuỗi hiển thị như `UTC / EST` trong localStorage, không phải tên
 * IANA. Giá trị nào không hợp lệ thì bỏ qua, dùng múi giờ của máy.
 */
export const resolveTimezone = (): string => {
  const declared = usePreferencesStore.getState().briefingPreferences.timezone;
  if (declared && isValidTimezone(declared)) return declared;
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
};

type PipelineRunStore = {
  connections: ConnectionStatus[];
  connectionsLoaded: boolean;
  connectionsLoading: boolean;
  connectionsError: string | null;

  integrations: Integration[];
  integrationsLoading: boolean;
  integrationsError: string | null;
  sources: Record<number, SourceListState>;

  selectedSources: SyncSourceRef[];
  /** Hạn mức do server quyết; giữ default cho tới khi loadRunLimits() xong. */
  limits: RunLimits;
  rangePreset: RangePreset;
  customFrom: string;
  customTo: string;

  phase: RunPhase;
  run: RunResponse | null;
  lastRunAt: string | null;
  nodes: Record<PipelineNode, PipelineNodeProgress>;
  tasks: Task[];
  brief: Brief | null;
  error: string | null;

  transport: PipelineTransport | null;
  transportReason: string | null;

  actionPending: number | null;
  handoffs: Record<number, CalendarHandoffResponse>;
  handoffPending: number | null;

  loadConnections: () => Promise<void>;
  connect: (provider: ConnectionProvider) => Promise<void>;
  disconnect: (provider: ConnectionProvider) => Promise<void>;

  loadRunLimits: () => Promise<void>;
  loadIntegrations: () => Promise<void>;
  loadSources: (integrationId: number) => Promise<void>;
  toggleSource: (ref: SyncSourceRef) => void;

  setRangePreset: (preset: RangePreset) => void;
  setCustomRange: (from: string, to: string) => void;

  start: () => Promise<void>;
  cancel: () => void;

  confirmTask: (taskId: number) => Promise<void>;
  dismissTask: (taskId: number) => Promise<void>;
  openCalendar: (taskId: number) => Promise<CalendarHandoffResponse>;
  markCalendarOpened: (taskId: number) => Promise<void>;
};

let activeController: AbortController | null = null;

export const usePipelineRunStore = create<PipelineRunStore>((set, get) => {
  const token = () => useAuthStore.getState().accessToken;

  /**
   * Backend chỉ bắn event khi node đã chạy xong (`status` là `ok` hoặc
   * `error`), không có `running`. Nên node đang chạy được suy ra: node kế tiếp
   * ngay sau node vừa xong.
   */
  const applyEvent = (event: RunNodeEventPayload): void => {
    if (event.node === 'done') {
      set({ phase: 'succeeded' });
      return;
    }
    if (event.node === 'error') {
      set({ phase: 'failed', error: event.message ?? 'Pipeline lỗi giữa chừng.' });
      return;
    }

    const index = PIPELINE_NODES.indexOf(event.node);
    if (index === -1) return;

    set((state) => {
      const nodes = {
        ...state.nodes,
        [event.node]: {
          node: event.node as PipelineNode,
          status: event.status === 'error' ? ('error' as const) : ('done' as const),
          count: event.count,
          message: event.message,
        },
      };

      const next = PIPELINE_NODES[index + 1];
      if (next && nodes[next].status === 'pending') {
        nodes[next] = { ...nodes[next], status: 'running' };
      }

      return {
        nodes,
        error: event.status === 'error' ? (event.message ?? state.error) : state.error,
      };
    });
  };

  /**
   * Đổi trạng thái việc. Fixture không tồn tại trong database nên ở chế độ dữ
   * liệu giả phải đổi tại chỗ, gọi API sẽ nhận 404.
   */
  const transition = async (taskId: number, next: 'confirmed' | 'dismissed'): Promise<void> => {
    if (get().transport === 'mock') {
      set((state) => ({
        tasks: state.tasks.map((task) =>
          task.id === taskId ? { ...task, status: next, updatedAt: new Date().toISOString() } : task,
        ),
      }));
      return;
    }

    set({ actionPending: taskId });
    try {
      const updated =
        next === 'confirmed' ? await confirmTaskApi(taskId, token()) : await dismissTaskApi(taskId, token());
      set((state) => ({
        tasks: state.tasks.map((task) => (task.id === taskId ? updated : task)),
        actionPending: null,
      }));
    } catch (error) {
      set({ actionPending: null });
      throw error;
    }
  };

  return {
    connections: [],
    connectionsLoaded: false,
    connectionsLoading: false,
    connectionsError: null,

    integrations: [],
    integrationsLoading: false,
    integrationsError: null,
    sources: {},

    selectedSources: [],
    limits: DEFAULT_RUN_LIMITS,
    rangePreset: '3d',
    customFrom: '',
    customTo: '',

    phase: 'idle',
    run: null,
    lastRunAt: null,
    nodes: emptyNodes(),
    tasks: [],
    brief: null,
    error: null,

    transport: null,
    transportReason: null,

    actionPending: null,
    handoffs: {},
    handoffPending: null,

    loadConnections: async () => {
      set({ connectionsLoaded: false, connectionsLoading: true, connectionsError: null });
      try {
        const { connections } = await listConnections(token());
        set({ connections, connectionsLoaded: true, connectionsLoading: false });
      } catch (error) {
        set({
          connectionsLoaded: false,
          connectionsLoading: false,
          connectionsError: error instanceof Error ? error.message : getTranslations().pipeline.sourcesError,
        });
      }
    },

    connect: async (provider) => {
      // Backend ký ext_redirect_uri rồi trả người dùng về đúng URL này kèm
      // ?status=&provider= sau khi xong vòng OAuth.
      const { authorizeUrl } = await createConnectIntent(
        provider,
        `${window.location.origin}/sources`,
        token(),
      );
      window.location.assign(authorizeUrl);
    },

    disconnect: async (provider) => {
      await disconnectProvider(provider, token());
      await get().loadConnections();
      await get().loadIntegrations();
    },

    loadIntegrations: async () => {
      set({ integrationsLoading: true, integrationsError: null });
      try {
        const { integrations } = await listIntegrations(token());
        set((state) => ({
          integrations,
          integrationsLoading: false,
          // Nguồn vừa bị ngắt kết nối phải rơi khỏi danh sách đã chọn.
          selectedSources: state.selectedSources.filter((ref) =>
            integrations.some((integration) => integration.id === ref.connectionId),
          ),
        }));

        await Promise.all(integrations.map((integration) => get().loadSources(integration.id)));
      } catch (error) {
        set({
          integrationsLoading: false,
          integrationsError: error instanceof Error ? error.message : getTranslations().pipeline.sourcesError,
        });
      }
    },

    loadSources: async (integrationId) => {
      set((state) => ({
        sources: { ...state.sources, [integrationId]: { loading: true, items: [] } },
      }));

      try {
        const result = await listIntegrationSources(integrationId, token());
        set((state) => ({
          sources: {
            ...state.sources,
            // `unsupported` có giá trị nghĩa là `items` là nguồn giả do FE dựng,
            // không phải nguồn thật từ backend.
            [integrationId]: loadedSourceListState(result),
          },
        }));
      } catch (error) {
        set((state) => ({
          sources: {
            ...state.sources,
            [integrationId]: {
              loading: false,
              items: [],
              error: error instanceof Error ? error.message : getTranslations().pipeline.childSourcesError,
            },
          },
        }));
      }
    },

    loadRunLimits: async () => {
      // Hạn mức không phải dữ liệu người dùng: gọi hỏng thì im lặng giữ
      // DEFAULT_RUN_LIMITS chứ không dựng banner lỗi ở trang chọn nguồn.
      try {
        set({ limits: await fetchRunLimits(token()) });
      } catch {
        set({ limits: DEFAULT_RUN_LIMITS });
      }
    },

    toggleSource: (ref) =>
      set((state) => {
        const selected = state.selectedSources.some((item) => sameSource(item, ref));
        if (selected) {
          // Bỏ tick thì luôn cho, kể cả khi đang vượt hạn mức — nếu không,
          // hạn mức bị hạ xuống sẽ khoá cứng danh sách đang chọn.
          return { selectedSources: state.selectedSources.filter((item) => !sameSource(item, ref)), error: null };
        }
        if (state.selectedSources.length >= state.limits.maxSyncSources) {
          // Chặn tại chỗ tick. Trước đây FE cho tick thoải mái rồi backend mới
          // trả 422 lúc bấm Sync, người dùng không biết phải bỏ bớt cái nào.
          return {
            selectedSources: state.selectedSources,
            error: getTranslations().pipeline.sourceLimitReached.replace(
              '{max}',
              String(state.limits.maxSyncSources),
            ),
          };
        }
        return { selectedSources: [...state.selectedSources, ref], error: null };
      }),

    setRangePreset: (rangePreset) => set({ rangePreset }),

    setCustomRange: (customFrom, customTo) => set({ customFrom, customTo, rangePreset: 'custom' }),

    start: async () => {
      const { selectedSources, rangePreset, customFrom, customTo } = get();
      if (selectedSources.length === 0) {
        set({ error: getTranslations().pipeline.selectSourceFirst });
        return;
      }

      const range =
        rangePreset === 'custom' && customFrom && customTo
          ? { from: new Date(`${customFrom}T00:00:00`), to: new Date(`${customTo}T23:59:59`) }
          : (() => {
              const to = new Date();
              const hours = PRESET_HOURS[rangePreset === 'custom' ? '3d' : rangePreset];
              return { from: new Date(to.getTime() - hours * 3600_000), to };
            })();

      activeController?.abort();
      const controller = new AbortController();
      activeController = controller;

      set({
        phase: 'running',
        nodes: { ...emptyNodes(), fetch: { node: 'fetch', status: 'running' } },
        tasks: [],
        brief: null,
        error: null,
        run: null,
        handoffs: {},
        transport: null,
        transportReason: null,
      });

      try {
        const run = await runPipeline(
          {
            sources: selectedSources,
            timeFrom: toLocalIso(range.from),
            timeTo: toLocalIso(range.to),
            timezone: resolveTimezone(),
            language: usePreferencesStore.getState().language,
            idempotencyKey: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
          },
          {
            accessToken: token(),
            signal: controller.signal,
            onTransport: (transport, transportReason) =>
              set({ transport, transportReason: transportReason ?? null }),
            onEvent: applyEvent,
            onResult: (tasks, brief) => set({ tasks, brief }),
          },
        );

        set((state) => ({
          run,
          lastRunAt: new Date().toISOString(),
          phase: state.phase === 'running' ? 'succeeded' : state.phase,
          error: run.errorMessage ?? state.error,
        }));
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          set({ phase: 'cancelled', lastRunAt: new Date().toISOString() });
          return;
        }
        set({
          phase: 'failed',
          lastRunAt: new Date().toISOString(),
          error: error instanceof Error ? error.message : getTranslations().pipeline.runFailed,
        });
      } finally {
        if (activeController === controller) activeController = null;
      }
    },

    cancel: () => {
      // Chỉ đóng stream phía FE. Run vẫn chạy tiếp ở backend — mở lại trang là
      // xem tiếp được vì `/runs/{id}/events` replay toàn bộ event đã ghi.
      activeController?.abort();
      activeController = null;
      set({ phase: 'cancelled' });
    },

    confirmTask: (taskId) => transition(taskId, 'confirmed'),

    dismissTask: (taskId) => transition(taskId, 'dismissed'),

    openCalendar: async (taskId) => {
      const task = get().tasks.find((item) => item.id === taskId);
      if (!task) throw new Error(getTranslations().pipeline.taskNotFound);
      if (!task.dueAt) {
        throw new Error(getTranslations().pipeline.calendarNeedDue);
      }

      set({ handoffPending: taskId });
      try {
        const response = await createCalendarHandoff(
          {
            taskId,
            title: task.title,
            startsAt: task.dueAt,
            description: task.evidence.map((item) => `${item.provider}: "${item.evidenceQuote}"`).join('\n'),
            timezone: resolveTimezone(),
          },
          token(),
          (transport, transportReason) => set({ transport, transportReason: transportReason ?? null }),
        );

        const previousIcsUrl = get().handoffs[taskId]?.icsUrl;
        if (previousIcsUrl?.startsWith('blob:') && previousIcsUrl !== response.icsUrl) {
          URL.revokeObjectURL(previousIcsUrl);
        }
        set((state) => ({
          handoffs: { ...state.handoffs, [taskId]: response },
          handoffPending: null,
        }));
        return response;
      } catch (error) {
        set({ handoffPending: null });
        throw error;
      }
    },

    markCalendarOpened: async (taskId) => {
      if (get().transport === 'mock') return;
      const response = await markCalendarHandoffOpened(taskId, token());
      set((state) => {
        const current = state.handoffs[taskId];
        if (!current) return state;
        return {
          handoffs: {
            ...state.handoffs,
            [taskId]: {
              ...current,
              opened: response.opened,
              openedAt: response.openedAt,
            },
          },
        };
      });
    },
  };
});
