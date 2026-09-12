// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as authApi from '../src/lib/authApi';
import { useAuthStore } from '../src/stores/useAuthStore';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';

vi.mock('../src/lib/authApi', () => ({
  login: vi.fn(),
  me: vi.fn(),
  refresh: vi.fn(),
  register: vi.fn(),
}));

const tokens = {
  accessToken: 'access-token',
  expiresIn: 3600,
  refreshToken: 'refresh-token',
  userId: '42',
  email: 'member@example.com',
  role: 'participant' as const,
  avatarUrl: 'https://lh3.googleusercontent.com/a/profile-photo',
};

const realRefreshSession = useAuthStore.getState().refreshSession;

const resetStore = () => {
  usePreferencesStore.getState().clearWorkspaceUser();
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    rememberMe: true,
    isAuthenticated: false,
    isBootstrapping: true,
    refreshSession: realRefreshSession,
  });
};

describe('useAuthStore session persistence', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    resetStore();
    vi.clearAllMocks();
    vi.mocked(authApi.login).mockResolvedValue(tokens);
  });

  it('keeps a remembered login in localStorage across browser sessions', async () => {
    window.sessionStorage.setItem('nav_session', 'stale-session');

    await useAuthStore.getState().signIn('MEMBER@example.com', 'password', true);

    expect(JSON.parse(window.localStorage.getItem('nav_session') ?? '')).toEqual({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    });
    expect(window.sessionStorage.getItem('nav_session')).toBeNull();
    expect(useAuthStore.getState().user?.avatarUrl).toBe(
      'https://lh3.googleusercontent.com/a/profile-photo',
    );
  });

  it('keeps a non-remembered login only in sessionStorage', async () => {
    window.localStorage.setItem('nav_session', 'stale-session');

    await useAuthStore.getState().signIn('MEMBER@example.com', 'password', false);

    expect(window.localStorage.getItem('nav_session')).toBeNull();
    expect(JSON.parse(window.sessionStorage.getItem('nav_session') ?? '')).toEqual({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    });
  });

  it('persists tokens received from Google OAuth in the selected storage', () => {
    useAuthStore.getState().signInWithTokens(tokens, true);

    expect(JSON.parse(window.localStorage.getItem('nav_session') ?? '')).toEqual({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    });
    expect(useAuthStore.getState().user?.email).toBe('member@example.com');
  });

  it('preserves session-only persistence while refreshing during bootstrap', async () => {
    window.sessionStorage.setItem(
      'nav_session',
      JSON.stringify({ accessToken: 'expired-token', refreshToken: 'refresh-token' }),
    );
    vi.mocked(authApi.me).mockRejectedValue(new Error('expired'));
    vi.mocked(authApi.refresh).mockResolvedValue(tokens);

    await useAuthStore.getState().bootstrap();

    expect(window.localStorage.getItem('nav_session')).toBeNull();
    expect(JSON.parse(window.sessionStorage.getItem('nav_session') ?? '')).toEqual({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    });
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().rememberMe).toBe(false);
  });

  it('hydrates the Google profile picture returned by the backend', async () => {
    window.localStorage.setItem(
      'nav_session',
      JSON.stringify({ accessToken: 'access-token', refreshToken: 'refresh-token' }),
    );
    vi.mocked(authApi.me).mockResolvedValue({
      id: '42',
      email: 'member@example.com',
      role: 'participant',
      displayName: 'Member',
      avatarUrl: 'https://lh3.googleusercontent.com/a/profile-photo',
    });

    await useAuthStore.getState().bootstrap();

    expect(useAuthStore.getState().user?.avatarUrl).toBe(
      'https://lh3.googleusercontent.com/a/profile-photo',
    );
  });

  it('always finishes bootstrap when session recovery throws unexpectedly', async () => {
    window.localStorage.setItem(
      'nav_session',
      JSON.stringify({ accessToken: 'expired-token', refreshToken: 'refresh-token' }),
    );
    vi.mocked(authApi.me).mockRejectedValue(new Error('network failed'));
    useAuthStore.setState({ refreshSession: vi.fn().mockRejectedValue(new Error('unexpected failure')) });

    await useAuthStore.getState().bootstrap();

    expect(useAuthStore.getState().isBootstrapping).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('removes both persistent and tab-scoped sessions on sign out', () => {
    window.localStorage.setItem('nav_session', 'local-session');
    window.sessionStorage.setItem('nav_session', 'tab-session');

    useAuthStore.getState().signOut();

    expect(window.localStorage.getItem('nav_session')).toBeNull();
    expect(window.sessionStorage.getItem('nav_session')).toBeNull();
  });
});
