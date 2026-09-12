import { create } from 'zustand';
import {
  listRecentRoutineRuns,
  listRoutines,
  type Routine,
  type RoutineRun,
} from '../lib/routinesApi';

type RoutineStore = {
  userKey: string | null;
  routines: Routine[];
  recentRuns: RoutineRun[];
  loaded: boolean;
  loading: boolean;
  ensureLoaded: (accessToken: string, userKey: string, force?: boolean) => Promise<void>;
  setRoutines: (routines: Routine[]) => void;
  upsertRoutine: (routine: Routine) => void;
  removeRoutine: (routineId: number) => void;
  prependRecentRun: (run: RoutineRun) => void;
  reset: () => void;
};

const inFlight = new Map<string, Promise<void>>();

export const useRoutineStore = create<RoutineStore>((set, get) => ({
  userKey: null,
  routines: [],
  recentRuns: [],
  loaded: false,
  loading: false,

  ensureLoaded: async (accessToken, userKey, force = false) => {
    const current = get();
    if (!force && current.userKey === userKey && current.loaded) return;
    const existing = inFlight.get(userKey);
    if (!force && existing) return existing;

    if (current.userKey !== userKey) {
      set({ userKey, routines: [], recentRuns: [], loaded: false });
    }
    set({ loading: true });

    const request = (async () => {
      try {
        // Routine list là dữ liệu bắt buộc. Recent runs là dữ liệu bổ sung nên
        // lỗi riêng không được xoá routine đã cache.
        const routines = await listRoutines(accessToken);
        const recentRuns = await listRecentRoutineRuns(accessToken).catch(() => []);
        set({ userKey, routines, recentRuns, loaded: true });
      } finally {
        set({ loading: false });
        inFlight.delete(userKey);
      }
    })();
    inFlight.set(userKey, request);
    return request;
  },

  setRoutines: (routines) => set({ routines }),

  upsertRoutine: (routine) => {
    set((state) => {
      const exists = state.routines.some((row) => row.id === routine.id);
      return {
        routines: exists
          ? state.routines.map((row) => (row.id === routine.id ? routine : row))
          : [routine, ...state.routines],
      };
    });
  },

  removeRoutine: (routineId) => {
    set((state) => ({
      routines: state.routines.filter((routine) => routine.id !== routineId),
      recentRuns: state.recentRuns.filter((run) => run.routineId !== routineId),
    }));
  },

  prependRecentRun: (run) => {
    set((state) => ({
      recentRuns: [run, ...state.recentRuns.filter((item) => item.id !== run.id)].slice(0, 12),
    }));
  },

  reset: () => set({ userKey: null, routines: [], recentRuns: [], loaded: false, loading: false }),
}));

export const resetRoutineStore = (): void => {
  inFlight.clear();
  useRoutineStore.getState().reset();
};
