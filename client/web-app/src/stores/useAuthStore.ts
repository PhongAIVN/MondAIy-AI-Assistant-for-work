import { create } from 'zustand';
import * as authApi from '../lib/authApi';
import { usePreferencesStore } from './usePreferencesStore';

export type UserRole = 'participant' | 'mentor' | 'admin';

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatarUrl?: string;
  program?: string;
  cohort?: string;
};

type StoredSession = {
  accessToken: string;
  refreshToken: string;
};

type SessionPersistence = 'local' | 'session';

type PersistedSession = StoredSession & {
  persistence: SessionPersistence;
};

type ProfileOverride = {
  name: string;
  program?: string;
  cohort?: string;
};

const SESSION_KEY = 'nav_session';
const PROFILE_KEY = 'nav_profiles';

// ---------------------------------------------------------------------------
// Mock auth — chỉ bật khi VITE_AUTH_MOCK=1, dùng cho demo offline không có
// backend. Không ảnh hưởng production (biến Vite bị tree-shake ra ngoài build).
// ---------------------------------------------------------------------------
const AUTH_MOCK_ENABLED = import.meta.env.VITE_AUTH_MOCK === '1';

const MOCK_USER: AuthUser = {
  id: 'mock-user-1',
  name: 'Demo User',
  email: 'demo@mondaiy.local',
  role: 'participant',
  program: 'AI Product Development Program',
  cohort: 'Cohort 2026',
};

const MOCK_ACCESS_TOKEN = 'mock-access-token';

const readSession = (): PersistedSession | null => {
  if (typeof window === 'undefined') return null;

  const candidates: Array<{ storage: Storage; persistence: SessionPersistence }> = [
    { storage: window.sessionStorage, persistence: 'session' },
    { storage: window.localStorage, persistence: 'local' },
  ];

  for (const { storage, persistence } of candidates) {
    try {
      const raw = storage.getItem(SESSION_KEY);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      if (typeof parsed?.accessToken === 'string' && typeof parsed?.refreshToken === 'string') {
        return { ...parsed, persistence } as PersistedSession;
      }
    } catch {
      // corrupted session, try the other storage before treating as signed out
    }
  }
  return null;
};

const writeSession = (
  session: StoredSession | null,
  persistence: SessionPersistence = 'local',
): void => {
  if (typeof window === 'undefined') return;
  const target = persistence === 'local' ? window.localStorage : window.sessionStorage;
  const other = persistence === 'local' ? window.sessionStorage : window.localStorage;

  if (session) {
    target.setItem(SESSION_KEY, JSON.stringify(session));
    other.removeItem(SESSION_KEY);
  } else {
    window.localStorage.removeItem(SESSION_KEY);
    window.sessionStorage.removeItem(SESSION_KEY);
  }
};

// Tên/chương trình/cohort chỉ để hiển thị. Quyền luôn lấy từ backend, không
// đọc từ localStorage để người dùng không thể tự nâng mình thành admin.
const readProfiles = (): Record<string, ProfileOverride> => {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, ProfileOverride>) : {};
  } catch {
    return {};
  }
};

const writeProfile = (email: string, profile: ProfileOverride): void => {
  if (typeof window === 'undefined') return;
  const all = readProfiles();
  all[email] = profile;
  localStorage.setItem(PROFILE_KEY, JSON.stringify(all));
};

const buildUser = (
  id: string,
  email: string,
  role: UserRole,
  displayName = '',
  avatarUrl?: string | null,
): AuthUser => {
  const profile = readProfiles()[email];
  return {
    id,
    email,
    name: displayName || profile?.name || email.split('@')[0],
    role,
    ...(avatarUrl ? { avatarUrl } : {}),
    program: profile?.program,
    cohort: profile?.cohort,
  };
};

// Profile/avatar/onboarding lưu theo email — hydrate mỗi lần đổi session,
// không merge vào profile global (tránh avatar user cũ dính sang user mới).
const syncDisplayProfile = (user: AuthUser): void => {
  usePreferencesStore.getState().hydrateForUser(user.email, {
    name: user.name,
    email: user.email,
    ...(user.program ? { program: user.program } : {}),
    ...(user.cohort ? { cohort: user.cohort } : {}),
  });
};

type AuthStore = {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  rememberMe: boolean;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  bootstrap: () => Promise<void>;
  signIn: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  signUp: (name: string, email: string, password: string, role: UserRole) => Promise<void>;
  /** Áp token đã có sẵn (luồng Đăng nhập với Google — token đổi được từ
   * authApi.exchangeGoogleLoginCode, không qua email/password). */
  signInWithTokens: (tokens: authApi.TokenResponse, rememberMe?: boolean) => void;
  signOut: () => void;
  refreshSession: () => Promise<string | null>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (token: string, password: string) => Promise<void>;
};

export const useAuthStore = create<AuthStore>((set, get) => {
  const applySession = (
    id: string,
    email: string,
    role: UserRole,
    accessToken: string,
    refreshToken: string,
    displayName = '',
    rememberMe = true,
    avatarUrl?: string | null,
  ): void => {
    const user = buildUser(id, email, role, displayName, avatarUrl);
    writeSession({ accessToken, refreshToken }, rememberMe ? 'local' : 'session');
    syncDisplayProfile(user);
    set({
      user,
      accessToken,
      refreshToken,
      rememberMe,
      isAuthenticated: true,
      isBootstrapping: false,
    });
  };

  return {
    user: null,
    accessToken: null,
    refreshToken: null,
    rememberMe: true,
    isAuthenticated: false,
    isBootstrapping: true,

    bootstrap: async () => {
      // Mock mode: langqua backend hoàn toàn, fake session ngay lập tức.
      if (AUTH_MOCK_ENABLED) {
        syncDisplayProfile(MOCK_USER);
        set({
          user: MOCK_USER,
          accessToken: MOCK_ACCESS_TOKEN,
          refreshToken: MOCK_ACCESS_TOKEN,
          isAuthenticated: true,
          isBootstrapping: false,
        });
        return;
      }

      const session = readSession();
      if (!session) {
        set({ isBootstrapping: false });
        return;
      }
      // `finally` ở đây là chốt chặn cuối, không phải thừa: cả hai route guard
      // render RỖNG khi isBootstrapping còn true, nên bất kỳ lỗi nào thoát ra
      // khỏi khối này đều biến toàn bộ ứng dụng thành màn hình trắng không lối
      // thoát. Đăng nhập hỏng thì phải hiện màn đăng nhập, không phải hiện gì cả.
      try {
        const profile = await authApi.me(session.accessToken);
        applySession(
          profile.id,
          profile.email,
          profile.role,
          session.accessToken,
          session.refreshToken,
          profile.displayName,
          session.persistence === 'local',
          profile.avatarUrl,
        );
      } catch {
        set({
          refreshToken: session.refreshToken,
          rememberMe: session.persistence === 'local',
        });
        try {
          await get().refreshSession();
        } catch {
          get().signOut();
        }
      } finally {
        // Route guards must never remain in their loading branch forever.
        set({ isBootstrapping: false });
      }
    },

    signIn: async (email, password, rememberMe = true) => {
      // Mock mode: bất kỳ email/password nào cũng đăng nhập được.
      if (AUTH_MOCK_ENABLED) {
        const mockEmail = email.trim().toLowerCase() || MOCK_USER.email;
        const user: AuthUser = { ...MOCK_USER, email: mockEmail, name: mockEmail.split('@')[0] };
        syncDisplayProfile(user);
        set({
          user,
          accessToken: MOCK_ACCESS_TOKEN,
          refreshToken: MOCK_ACCESS_TOKEN,
          isAuthenticated: true,
          isBootstrapping: false,
        });
        return;
      }
      const normalizedEmail = email.trim().toLowerCase();
      const tokens = await authApi.login(normalizedEmail, password);
      applySession(
        tokens.userId,
        tokens.email,
        tokens.role,
        tokens.accessToken,
        tokens.refreshToken,
        '',
        rememberMe,
        tokens.avatarUrl,
      );
    },

    signUp: async (name, email, password, role) => {
      // Mock mode: đăng ký không cần backend.
      if (AUTH_MOCK_ENABLED) {
        const user: AuthUser = {
          ...MOCK_USER,
          name: name.trim() || MOCK_USER.name,
          email: email.trim().toLowerCase() || MOCK_USER.email,
          role,
        };
        syncDisplayProfile(user);
        set({
          user,
          accessToken: MOCK_ACCESS_TOKEN,
          refreshToken: MOCK_ACCESS_TOKEN,
          isAuthenticated: true,
          isBootstrapping: false,
        });
        return;
      }
      const normalizedEmail = email.trim().toLowerCase();
      const displayName = name.trim();
      const tokens = await authApi.register(normalizedEmail, password, displayName);
      writeProfile(normalizedEmail, {
        name: displayName,
        program: 'AI Product Development Program',
        cohort: 'Cohort 2026',
      });
      applySession(
        tokens.userId,
        tokens.email,
        tokens.role,
        tokens.accessToken,
        tokens.refreshToken,
        displayName,
        true,
        tokens.avatarUrl,
      );
    },

    signInWithTokens: (tokens, rememberMe = true) => {
      applySession(
        tokens.userId,
        tokens.email,
        tokens.role,
        tokens.accessToken,
        tokens.refreshToken,
        '',
        rememberMe,
        tokens.avatarUrl,
      );
    },

    signOut: () => {
      writeSession(null);
      usePreferencesStore.getState().clearWorkspaceUser();
      set({
        user: null,
        accessToken: null,
        refreshToken: null,
        rememberMe: true,
        isAuthenticated: false,
        isBootstrapping: false,
      });
    },

    refreshSession: async () => {
      // Mock mode: token giả không bao giờ hết hạn.
      if (AUTH_MOCK_ENABLED) return MOCK_ACCESS_TOKEN;

      const { refreshToken, rememberMe } = get();
      if (!refreshToken) {
        get().signOut();
        return null;
      }
      try {
        const tokens = await authApi.refresh(refreshToken);
        applySession(
          tokens.userId,
          tokens.email,
          tokens.role,
          tokens.accessToken,
          tokens.refreshToken,
          '',
          rememberMe,
          tokens.avatarUrl,
        );
        return tokens.accessToken;
      } catch {
        get().signOut();
        return null;
      }
    },

    forgotPassword: async (email) => {
      // Mock mode: không có backend để gửi mail, coi như đã gửi.
      if (AUTH_MOCK_ENABLED) return;
      await authApi.forgotPassword(email.trim().toLowerCase());
    },

    resetPassword: async (token, password) => {
      if (AUTH_MOCK_ENABLED) return;
      await authApi.resetPassword(token, password);
    },
  };
});
