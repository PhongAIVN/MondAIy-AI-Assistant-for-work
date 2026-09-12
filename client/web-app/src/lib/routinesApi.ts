import { apiRequest } from './apiClient';

// Khớp ROUTINE_FREQUENCIES trong src/models/routine.py. "trigger" (theo sự
// kiện) chưa làm — xem TODO(OD) ở src/services/routines.py.
export type RoutineFrequency = 'daily' | 'weekly' | 'monthly';

export type Routine = {
  id: number;
  name: string;
  instructions: string;
  frequency: RoutineFrequency;
  hour: number;
  dayOfWeek: number | null;
  dayOfMonth: number | null;
  timezone: string;
  enabled: boolean;
  // Chỉ lưu lựa chọn — chưa có delivery push/email thật đứng sau (xem
  // src/services/routines.py). Không hiện là "đã bật thông báo thật".
  notifyPush: boolean;
  notifyEmail: boolean;
  lastRunDate: string | null;
};

export type RoutineRun = {
  id: number;
  routineId: number;
  status: 'running' | 'done' | 'error';
  outputText: string | null;
  outputJson: Record<string, unknown> | null;
  errorMessage: string | null;
  startedAt: string;
  finishedAt: string | null;
  routineName?: string;
};

export type CreateRoutineInput = {
  name: string;
  instructions: string;
  frequency: RoutineFrequency;
  hour: number;
  dayOfWeek?: number;
  dayOfMonth?: number;
  timezone?: string;
  notifyPush?: boolean;
  notifyEmail?: boolean;
};

export type UpdateRoutineInput = Partial<CreateRoutineInput> & { enabled?: boolean };

type RoutineListResponse = { routines: Routine[] };
type RoutineRunListResponse = { runs: RoutineRun[] };

export const listRoutines = (accessToken: string): Promise<Routine[]> =>
  apiRequest<RoutineListResponse>('/api/v1/routines', { accessToken }).then((body) => body.routines);

export const getRoutine = (accessToken: string, routineId: number): Promise<Routine> =>
  apiRequest<Routine>(`/api/v1/routines/${routineId}`, { accessToken });

export const createRoutine = (accessToken: string, input: CreateRoutineInput): Promise<Routine> =>
  apiRequest<Routine>('/api/v1/routines', { accessToken, method: 'POST', body: input });

export const updateRoutine = (
  accessToken: string,
  routineId: number,
  patch: UpdateRoutineInput,
): Promise<Routine> =>
  apiRequest<Routine>(`/api/v1/routines/${routineId}`, { accessToken, method: 'PATCH', body: patch });

export const deleteRoutine = (accessToken: string, routineId: number): Promise<void> =>
  apiRequest<void>(`/api/v1/routines/${routineId}`, { accessToken, method: 'DELETE' });

export const listRoutineRuns = (accessToken: string, routineId: number): Promise<RoutineRun[]> =>
  apiRequest<RoutineRunListResponse>(`/api/v1/routines/${routineId}/runs`, { accessToken }).then(
    (body) => body.runs,
  );

export const listRecentRoutineRuns = (accessToken: string): Promise<RoutineRun[]> =>
  apiRequest<RoutineRunListResponse>('/api/v1/routines/runs/recent', { accessToken }).then((body) => body.runs);

// Endpoint này chạy nguyên vòng agent thật (nhiều lượt gọi LLM + tool đọc
// nguồn) trong lúc xử lý request — chậm hơn hẳn CRUD thường, đặc biệt với tài
// khoản có nhiều nguồn đã kết nối. DEFAULT_TIMEOUT_MS (15s) của apiRequest
// hụt trước khi agent kịp xong, làm request bị huỷ và hiện lỗi "không lưu
// được" dù backend vẫn đang chạy tiếp — nới riêng timeout cho đúng route này.
const RUN_NOW_TIMEOUT_MS = 120_000;

/** Chạy thử ngay, không đợi vòng poll — cho UX "Tạo xong thấy kết quả liền". */
export const runRoutineNow = (accessToken: string, routineId: number): Promise<RoutineRun> =>
  apiRequest<RoutineRun>(`/api/v1/routines/${routineId}/run-now`, {
    accessToken,
    method: 'POST',
    timeoutMs: RUN_NOW_TIMEOUT_MS,
  });
