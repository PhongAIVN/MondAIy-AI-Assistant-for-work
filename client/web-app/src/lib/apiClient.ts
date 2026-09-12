import {
  getBackendStatus,
  reportBackendMaintenance,
  reportBackendOk,
  reportBackendUnreachable,
  type BackendStatus,
} from './backendStatus';

// Dev: mặc định gọi thẳng backend cổng 8000. Prod: mặc định rỗng (same-origin)
// vì Caddy đã reverse-proxy /api/* sang backend cùng domain — xem
// client/web-app/Caddyfile. VITE_API_URL override cả 2 khi cần.
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (import.meta.env.DEV ? 'http://localhost:8000' : '');

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  accessToken?: string | null;
  /** Huỷ lời gọi đã lỗi thời (đổi cửa sổ thời gian, rời trang) để phản hồi cũ
   * về muộn không ghi đè dữ liệu mới hơn. */
  signal?: AbortSignal;
  /** Trần riêng cho request; mặc định dùng DEFAULT_TIMEOUT_MS. */
  timeoutMs?: number;
};

/** Không để một fetch treo vô hạn giữ router ở trạng thái bootstrap. */
export const DEFAULT_TIMEOUT_MS = 15_000;

const withTimeout = (
  sourceSignal: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; finish: () => void } => {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => {
    controller.abort(new DOMException('Request timed out', 'TimeoutError'));
  }, timeoutMs);

  if (sourceSignal) {
    if (sourceSignal.aborted) controller.abort(sourceSignal.reason);
    else {
      sourceSignal.addEventListener('abort', () => controller.abort(sourceSignal.reason), {
        once: true,
      });
    }
  }

  return {
    signal: controller.signal,
    finish: () => globalThis.clearTimeout(timer),
  };
};

const extractErrorMessage = async (response: Response): Promise<string> => {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
    // slowapi's default 429 handler trả {"error": "..."} thay vì {"detail": "..."}
    // (xem src/api/rate_limit.py + main.py add_exception_handler(RateLimitExceeded, ...)).
    // Không đọc field này thì mọi 429 do rate-limit-per-phút rơi về statusText chung chung.
    if (typeof data?.error === 'string') return data.error;
  } catch {
    // response has no JSON body
  }
  return response.statusText || 'Request failed';
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (options.accessToken) {
    headers.Authorization = `Bearer ${options.accessToken}`;
  }

  const timed = withTimeout(options.signal, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: timed.signal,
    });
  } catch (error) {
    // Không nuốt lỗi: vẫn ném tiếp cho caller, chỉ ghi nhận thêm để UI báo bảo trì.
    // Huỷ chủ động (đổi cửa sổ thời gian, rời trang) KHÔNG phải backend chết.
    if (!options.signal?.aborted) {
      reportBackendUnreachable();
    }
    throw error;
  } finally {
    timed.finish();
  }

  if (!response.ok) {
    // 503 = backend tự khai là chưa sẵn sàng → tin ngay.
    if (response.status === 503) {
      reportBackendMaintenance();
    } else if (response.status >= 500) {
      // 5xx khác thì CHƯA kết luận. DB chết không làm endpoint thường trả 503 —
      // nó trả 500 — nên nếu chỉ nghe 503 thì banner không bao giờ hiện đúng lúc cần.
      // Hỏi thẳng readiness để phân biệt "hạ tầng chết" với "bug 500 bình thường".
      // Không await: caller không phải chờ, và probe dùng fetch trần nên không đệ quy.
      void probeBackendReadiness();
    }
    throw new ApiError(response.status, await extractErrorMessage(response));
  }

  reportBackendOk();

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Hỏi thẳng readiness của backend và cập nhật trạng thái.
 *
 * Dùng `/health/ready` chứ không phải `/health`: `/health` là liveness, luôn trả 200
 * kể cả khi DB ngủ (deploy.yml, Caddyfile, vercel.json, healthcheck compose và
 * deploy_vm_local.sh đều dựa vào nó), nên nó không bao giờ phát hiện được bảo trì.
 */
export async function probeBackendReadiness(): Promise<BackendStatus> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/health/ready`, { method: 'GET' });
  } catch {
    reportBackendUnreachable();
    return 'unreachable';
  }

  // KHÔNG tin mỗi `response.ok`. Nếu host quên rewrite `/health/ready` sang backend,
  // fallback SPA trả về index.html kèm 200 — probe sẽ tưởng hệ thống khoẻ trong khi
  // backend đã chết. Đây là lỗi có thật trên production, không phải giả định.
  // Chỉ kết luận khi đọc được JSON có field `status` do chính backend trả.
  let payload: { status?: string } | null = null;
  try {
    payload = (await response.clone().json()) as { status?: string };
  } catch {
    payload = null;
  }

  if (!payload || typeof payload.status !== 'string') {
    // Không phân biệt được — giữ nguyên trạng thái hiện tại, không đoán theo hướng nào.
    return getBackendStatus();
  }

  if (response.ok && payload.status === 'ok') {
    reportBackendOk();
    return 'ok';
  }

  reportBackendMaintenance();
  return 'maintenance';
}
