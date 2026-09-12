import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { GuestRoute } from '../src/components/auth/GuestRoute';

const { mocks } = vi.hoisted(() => ({
  mocks: {
    isAuthenticated: false,
    isBootstrapping: false,
    accessToken: null as string | null,
  },
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => mocks,
}));

function renderAtRoot() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<GuestRoute><div>landing-page</div></GuestRoute>} />
        <Route path="/briefing" element={<div>briefing-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('GuestRoute — dùng để chặn landing page khi đã đăng nhập', () => {
  afterEach(() => {
    cleanup();
    mocks.isAuthenticated = false;
    mocks.isBootstrapping = false;
    mocks.accessToken = null;
  });

  it('chưa đăng nhập thì "/" vẫn hiện landing page', () => {
    renderAtRoot();
    expect(screen.getByText('landing-page')).toBeTruthy();
    expect(screen.queryByText('briefing-page')).toBeNull();
  });

  it('đã đăng nhập mà gõ "/" thì bị đưa thẳng vào /briefing, không thấy landing page', () => {
    mocks.isAuthenticated = true;
    mocks.accessToken = 'access-token';
    renderAtRoot();
    expect(screen.queryByText('landing-page')).toBeNull();
    expect(screen.getByText('briefing-page')).toBeTruthy();
  });

  it('đang bootstrap phiên đăng nhập thì chưa quyết định, không lộ landing page', () => {
    mocks.isBootstrapping = true;
    renderAtRoot();
    expect(screen.queryByText('landing-page')).toBeNull();
    expect(screen.queryByText('briefing-page')).toBeNull();
  });
});
