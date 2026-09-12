/**
 * Phát hiện bản đang chạy đã cũ so với bản đã deploy.
 *
 * Vì sao cần: `registerType: 'autoUpdate'` thay service worker nền, nhưng KHÔNG
 * tải lại trang. Một tab để mở xuyên qua một lần deploy vẫn chạy JS cũ cho tới
 * khi người dùng tự refresh — và trong lúc đó nó gọi backend đã đổi hợp đồng.
 * Không có gì phát hiện, không có gì nhắc; người dùng chỉ thấy lỗi lạ.
 *
 * Cách đo: `__BUILD_ID__` được Vite chèn lúc build vào chính bundle đang chạy.
 * `version.json` nằm cạnh nó trên server và luôn được fetch `no-store`. Hai giá
 * trị lệch nhau nghĩa là server đã có bản mới hơn bản đang chạy.
 *
 * Cố ý KHÔNG tự reload khi phát hiện: người dùng có thể đang gõ dở. Ta chỉ báo
 * và để họ bấm.
 */

/** Vite chèn lúc build. Trong test/dev có thể không có nên phải phòng. */
declare const __BUILD_ID__: string | undefined;

export const VERSION_ENDPOINT = '/version.json';

export function currentBuildId(): string {
  try {
    return typeof __BUILD_ID__ === 'string' ? __BUILD_ID__ : '';
  } catch {
    // ReferenceError khi bundle chạy ngoài môi trường đã define.
    return '';
  }
}

export type VersionCheck =
  | { status: 'current' }
  | { status: 'stale'; deployed: string; running: string }
  | { status: 'unknown'; reason: string };

/**
 * So bản đang chạy với bản trên server.
 *
 * Trả `unknown` thay vì ném lỗi cho mọi trường hợp không kết luận được — mất
 * mạng, đang offline, server chưa có version.json. Một lần kiểm hỏng không được
 * phép làm phiền người dùng: báo nhầm "có bản mới" còn tệ hơn không báo.
 */
export async function checkAppVersion(
  fetchImpl: typeof fetch = fetch,
): Promise<VersionCheck> {
  const running = currentBuildId();
  if (!running) return { status: 'unknown', reason: 'no_build_id' };

  let response: Response;
  try {
    response = await fetchImpl(VERSION_ENDPOINT, {
      cache: 'no-store',
      headers: { accept: 'application/json' },
    });
  } catch (error) {
    return { status: 'unknown', reason: `fetch_failed: ${String(error)}` };
  }

  if (!response.ok) return { status: 'unknown', reason: `http_${response.status}` };

  let deployed: unknown;
  try {
    deployed = ((await response.json()) as { buildId?: unknown })?.buildId;
  } catch (error) {
    return { status: 'unknown', reason: `bad_json: ${String(error)}` };
  }

  if (typeof deployed !== 'string' || !deployed) {
    return { status: 'unknown', reason: 'no_build_id_on_server' };
  }

  return deployed === running
    ? { status: 'current' }
    : { status: 'stale', deployed, running };
}

/**
 * Dọn service worker + cache tĩnh rồi tải lại.
 *
 * Cùng đường mà `AppErrorBoundary.recover` đang dùng và đã chạy tốt: chỉ xoá
 * cache tĩnh và SW, KHÔNG đụng localStorage/sessionStorage — phiên đăng nhập
 * phải sống sót qua một lần làm mới.
 */
export async function reloadToLatest(
  reload: () => void = () => window.location.reload(),
): Promise<void> {
  try {
    const registrations = await navigator.serviceWorker?.getRegistrations?.();
    await Promise.all((registrations ?? []).map((r) => r.unregister()));
    const keys = await globalThis.caches?.keys?.();
    await Promise.all((keys ?? []).map((key) => globalThis.caches.delete(key)));
  } finally {
    reload();
  }
}
