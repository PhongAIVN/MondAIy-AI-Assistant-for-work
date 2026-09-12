// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../src/components/layout/Sidebar';
import {
  PALETTES,
  usePreferencesStore,
  type ThemeMode,
} from '../src/stores/usePreferencesStore';

const mocks = vi.hoisted(() => ({
  listProjects: vi.fn().mockResolvedValue([]),
  fetchConversations: vi.fn().mockResolvedValue(undefined),
  addToast: vi.fn(),
  signOut: vi.fn(),
  requestAppTour: vi.fn(),
}));

vi.mock('../src/lib/projectsApi', () => ({
  listProjects: mocks.listProjects,
  addConversationToProject: vi.fn(),
  removeConversationFromProject: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({
    user: { id: 'user-1', name: 'Thái', email: 'thai@example.com', role: 'participant' },
    accessToken: 'access-token',
    signOut: mocks.signOut,
  }),
}));

vi.mock('../src/stores/useConversationStore', () => ({
  useConversationStore: () => ({
    conversations: [],
    fetchConversations: mocks.fetchConversations,
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
    setFavorite: vi.fn(),
    generatingIds: new Set<string>(),
  }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ addToast: mocks.addToast }),
}));

vi.mock('../src/stores/usePipelineRunStore', () => ({
  usePipelineRunStore: (selector: (state: { connections: never[] }) => unknown) =>
    selector({ connections: [] }),
}));

vi.mock('../src/stores/useAppTourStore', () => ({
  useAppTourStore: (selector: (state: { requestAppTour: typeof mocks.requestAppTour }) => unknown) =>
    selector({ requestAppTour: mocks.requestAppTour }),
}));

vi.mock('../src/hooks/useMotionEnabled', () => ({ useMotionEnabled: () => false }));

const viLabels = ['Sáng', 'Tối', 'Trắng tinh', 'Đen tuyệt đối', 'Hệ thống'];
const enLabels = ['Light', 'Dark', 'Pure white', 'Pure black', 'System'];

const renderOpenMenu = async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/briefing']}>
      <Sidebar />
    </MemoryRouter>,
  );
  await user.click(screen.getByRole('button', { name: 'User account menu' }));
  return user;
};

beforeEach(() => {
  usePreferencesStore.getState().resetAllPrototypeData();
  usePreferencesStore.setState({
    profile: {
      name: 'Thái',
      email: 'thai@example.com',
      program: 'AI Product Development Program',
      cohort: 'Cohort 2026',
      stage: 'AI Innovation Fellow',
      mentor: '',
    },
  });
  vi.clearAllMocks();
  mocks.listProjects.mockResolvedValue([]);
  mocks.fetchConversations.mockResolvedValue(undefined);
});

afterEach(cleanup);

describe('Sidebar — theme mode in user menu', () => {
  it('renders all five modes and marks only the current mode active', async () => {
    await renderOpenMenu();

    expect(screen.getByText('Chế độ giao diện')).toBeTruthy();
    for (const label of viLabels) {
      const button = screen.getByRole('button', { name: label });
      expect(button.getAttribute('aria-pressed')).toBe(label === 'Sáng' ? 'true' : 'false');
    }
  });

  it('updates the shared theme state, persistence and active marker for every mode', async () => {
    const user = await renderOpenMenu();
    const modes: Array<{ mode: ThemeMode; label: string }> = [
      { mode: 'light', label: 'Sáng' },
      { mode: 'dark', label: 'Tối' },
      { mode: 'white', label: 'Trắng tinh' },
      { mode: 'black', label: 'Đen tuyệt đối' },
      { mode: 'system', label: 'Hệ thống' },
    ];

    for (const { mode, label } of modes) {
      await user.click(screen.getByRole('button', { name: label }));
      expect(usePreferencesStore.getState().theme).toBe(mode);
      expect(localStorage.getItem('nav_theme')).toBe(mode);
      expect(screen.getByRole('button', { name: label }).getAttribute('aria-pressed')).toBe('true');
      for (const other of modes.filter((item) => item.mode !== mode)) {
        expect(screen.getByRole('button', { name: other.label }).getAttribute('aria-pressed')).toBe('false');
      }
    }
  });

  it('keeps palette controls independent from theme mode', async () => {
    const user = await renderOpenMenu();

    for (const palette of PALETTES) {
      expect(screen.getByRole('button', { name: palette.labelVi })).toBeTruthy();
    }
    await user.click(screen.getByRole('button', { name: 'Mận' }));

    expect(usePreferencesStore.getState().palette).toBe('plum');
    expect(localStorage.getItem('nav_palette')).toBe('plum');
    expect(usePreferencesStore.getState().theme).toBe('light');
    expect(screen.getByRole('button', { name: 'Mận' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Sáng' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('reuses the existing English labels', async () => {
    usePreferencesStore.setState({ language: 'en' });
    await renderOpenMenu();

    expect(screen.getByText('Theme Mode')).toBeTruthy();
    for (const label of enLabels) {
      expect(screen.getByRole('button', { name: label })).toBeTruthy();
    }
  });
});
