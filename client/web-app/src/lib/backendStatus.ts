/** Trạng thái backend nhìn từ phía trình duyệt.
 *
 * Module này CỐ Ý không import gì: `apiClient` báo trạng thái vào đây, nên nếu
 * chiều ngược lại tồn tại sẽ thành import vòng và `API_BASE_URL` có thể undefined
 * lúc khởi tạo module.
 *
 * - `ok`           gọi API bình thường.
 * - `maintenance`  backend còn sống nhưng phụ thuộc chết (DB ngủ) → readiness trả 503.
 * - `unreachable`  không tới được backend: mất mạng, timeout, DNS hỏng, server tắt.
 */
export type BackendStatus = 'ok' | 'maintenance' | 'unreachable';

let current: BackendStatus = 'ok';
const listeners = new Set<() => void>();

export function getBackendStatus(): BackendStatus {
  return current;
}

export function subscribeBackendStatus(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setStatus(next: BackendStatus): void {
  if (next === current) return;
  current = next;
  listeners.forEach((listener) => listener());
}

export function reportBackendOk(): void {
  setStatus('ok');
}

export function reportBackendMaintenance(): void {
  setStatus('maintenance');
}

export function reportBackendUnreachable(): void {
  setStatus('unreachable');
}

/** Chỉ dùng trong test để trả module về trạng thái sạch. */
export function resetBackendStatus(): void {
  current = 'ok';
  listeners.clear();
}
