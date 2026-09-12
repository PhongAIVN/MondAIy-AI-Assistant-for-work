import { API_BASE_URL, apiRequest } from './apiClient';

export type UserRole = 'participant' | 'mentor' | 'admin';

export type TokenResponse = {
  accessToken: string;
  expiresIn: number;
  refreshToken: string;
  userId: string;
  email: string;
  role: UserRole;
  avatarUrl?: string | null;
  programAccessLevel: 'A' | 'B' | 'C';
};

export type UserResponse = {
  id: string;
  email: string;
  role: UserRole;
  displayName: string;
  avatarUrl?: string | null;
  programAccessLevel: 'A' | 'B' | 'C';
};

// Không gửi role lên: server luôn tạo tài khoản mới là participant. Nâng quyền
// chỉ qua /admin/users/{id} hoặc scripts/grant_role.py.
export const register = (
  email: string,
  password: string,
  displayName = '',
): Promise<TokenResponse> =>
  apiRequest<TokenResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: { email, password, displayName },
  });

export const login = (email: string, password: string): Promise<TokenResponse> =>
  apiRequest<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: { email, password },
  });

export const refresh = (refreshToken: string): Promise<TokenResponse> =>
  apiRequest<TokenResponse>('/api/v1/auth/refresh', {
    method: 'POST',
    body: { refreshToken },
  });

export const me = (accessToken: string): Promise<UserResponse> =>
  apiRequest<UserResponse>('/api/v1/auth/me', { accessToken });

/** Server luôn trả cùng message + 200 dù email có tồn tại hay không, để
 * tránh lộ danh sách email đã đăng ký (user enumeration). */
export const forgotPassword = (email: string): Promise<{ message: string }> =>
  apiRequest<{ message: string }>('/api/v1/auth/forgot-password', {
    method: 'POST',
    body: { email },
  });

export const resetPassword = (token: string, newPassword: string): Promise<{ message: string }> =>
  apiRequest<{ message: string }>('/api/v1/auth/reset-password', {
    method: 'POST',
    body: { token, newPassword },
  });

/** URL bắt đầu OAuth Google cho đăng nhập/đăng ký — điều hướng cả trang
 * (không phải fetch), backend redirect thẳng sang Google. Tự tạo tài khoản
 * nếu email Google chưa từng đăng ký. */
export const googleLoginUrl = (extRedirectUri: string): string =>
  `${API_BASE_URL}/api/v1/auth/google/login?extRedirectUri=${encodeURIComponent(extRedirectUri)}`;

/** Đổi login code ngắn hạn (đọc từ query khi callback redirect về) lấy token thật. */
export const exchangeGoogleLoginCode = (code: string): Promise<TokenResponse> =>
  apiRequest<TokenResponse>('/api/v1/auth/google/session', {
    method: 'POST',
    body: { code },
  });
