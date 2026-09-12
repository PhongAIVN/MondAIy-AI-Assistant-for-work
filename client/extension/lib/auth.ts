import { authSessionItem } from "@/lib/storage";
import type { AuthSession } from "@/types";
import type { WebSession } from "@/lib/webSession";

const API_BASE = import.meta.env.WXT_API_BASE_URL;

interface TokenResponseBody {
  accessToken?: string;
  access_token?: string;
  expiresIn?: number;
  expires_in?: number;
  refreshToken?: string;
  refresh_token?: string;
  avatarUrl?: string | null;
  avatar_url?: string | null;
  email?: string | null;
}

function toSession(body: TokenResponseBody): AuthSession {
  const accessToken = body.accessToken || body.access_token || "";
  const expiresIn = body.expiresIn || body.expires_in || 1800;
  const refreshToken = body.refreshToken || body.refresh_token || null;
  const avatarUrl = body.avatarUrl || body.avatar_url || null;
  const email = body.email || null;

  return {
    accessToken,
    expiresAt: Date.now() + expiresIn * 1000,
    refreshToken,
    avatarUrl,
    email,
  };
}

/**
 * Đăng nhập trực tiếp bằng email & mật khẩu ngay trong Extension.
 * Gọi thẳng POST /api/v1/auth/login và lưu phiên vào storage.
 */
export async function loginWithCredentials(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string }> {
  const cleanEmail = email.trim().toLowerCase();
  if (!cleanEmail || !password) {
    return { success: false, error: "Vui lòng nhập đầy đủ email và mật khẩu." };
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: cleanEmail, password }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        return { success: false, error: "Email hoặc mật khẩu không chính xác." };
      }
      if (response.status === 429) {
        return { success: false, error: "Quá nhiều lần thử đăng nhập. Vui lòng thử lại sau vài phút." };
      }
      try {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || "Đăng nhập thất bại." };
      } catch {
        return { success: false, error: `Đăng nhập thất bại (mã lỗi ${response.status}).` };
      }
    }

    const data = (await response.json()) as TokenResponseBody;
    const session = toSession(data);
    await authSessionItem.setValue(session);
    return { success: true };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, error: `Không thể kết nối đến máy chủ: ${msg}` };
  }
}

/**
 * Đồng bộ phiên đăng nhập lấy từ web app (content script / popup probe).
 *
 * `expiresAt: 0` vì không biết hạn thật của accessToken lấy từ localStorage —
 * ép getValidAccessToken() refresh ngay lần dùng đầu tiên để lấy hạn chính xác
 * từ backend, thay vì đoán bừa.
 */
export async function applyWebSession(session: WebSession | null): Promise<void> {
  if (!session) {
    await logout();
    return;
  }
  const current = await getSession();
  if (current?.refreshToken === session.refreshToken) return; // đã đồng bộ, khỏi ghi lại

  await authSessionItem.setValue({
    accessToken: session.accessToken,
    expiresAt: 0,
    refreshToken: session.refreshToken,
    avatarUrl: current?.avatarUrl ?? null,
    email: current?.email ?? null,
  });
}

export async function getSession(): Promise<AuthSession | null> {
  // Bọc lại vì driver storage của wxt ném Error khi vùng storage không truy cập
  // được từ ngữ cảnh đang chạy. Trước đây lỗi đó xuyên thẳng qua
  // getValidAccessToken rồi ra tận nơi gọi fetch, khiến request không bao giờ
  // được gửi mà chỗ gọi lại tưởng là lỗi mạng.
  try {
    return await authSessionItem.getValue();
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await authSessionItem.setValue(null);
}

export async function refreshSession(): Promise<AuthSession | null> {
  const current = await getSession();
  if (!current?.refreshToken) {
    await logout();
    return null;
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: current.refreshToken }),
    });
    if (!response.ok) throw new Error("Refresh token không hợp lệ hoặc đã hết hạn.");

    const session = toSession((await response.json()) as TokenResponseBody);
    await authSessionItem.setValue(session);
    return session;
  } catch {
    // Refresh thất bại ⇒ coi như phiên đăng xuất, buộc login lại (an toàn hơn suy đoán).
    await logout();
    return null;
  }
}

export async function getValidAccessToken(): Promise<string | null> {
  const session = await getSession();
  if (!session) return null;

  const isExpired = Date.now() >= session.expiresAt;
  if (!isExpired) return session.accessToken;

  const refreshed = await refreshSession();
  return refreshed?.accessToken ?? null;
}
