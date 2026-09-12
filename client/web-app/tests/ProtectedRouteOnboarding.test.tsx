import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from '../src/components/auth/ProtectedRoute';

const { mocks } = vi.hoisted(() => ({
  mocks: {
    role: 'participant' as 'participant' | 'admin',
    onboardingDismissed: true,
  },
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    isBootstrapping: false,
    user: { id: 'u1', name: 'Test', email: 't@test.dev', role: mocks.role },
    accessToken: 'access-token',
  }),
}));

vi.mock('../src/stores/usePreferencesStore', () => ({
  usePreferencesStore: (selector: (state: { onboardingDismissed: boolean }) => unknown) =>
    selector({ onboardingDismissed: mocks.onboardingDismissed }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ addToast: vi.fn() }),
}));

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: { auth: { noPermissionAdmin: 'No permission' } } }),
}));

function renderAtOnboarding() {
  return render(
    <MemoryRouter initialEntries={['/onboarding']}>
      <Routes>
        <Route path="/onboarding" element={<ProtectedRoute>onboarding-page</ProtectedRoute>} />
        <Route path="/briefing" element={<div>briefing-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute — khoá /onboarding sau khi đã hoàn thành', () => {
  afterEach(() => {
    cleanup();
    mocks.role = 'participant';
    mocks.onboardingDismissed = true;
  });

  it('người dùng thường đã xong onboarding gõ thẳng link /onboarding thì bị đá về /briefing', () => {
    renderAtOnboarding();
    expect(screen.queryByText('onboarding-page')).toBeNull();
    expect(screen.getByText('briefing-page')).toBeTruthy();
  });

  it('admin vẫn vào được /onboarding dù đã đánh dấu hoàn thành', () => {
    mocks.role = 'admin';
    renderAtOnboarding();
    expect(screen.getByText('onboarding-page')).toBeTruthy();
  });

  it('người dùng thường chưa hoàn thành onboarding vẫn vào /onboarding bình thường', () => {
    mocks.onboardingDismissed = false;
    renderAtOnboarding();
    expect(screen.getByText('onboarding-page')).toBeTruthy();
  });
});
