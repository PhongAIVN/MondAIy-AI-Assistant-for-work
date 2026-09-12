// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../src/components/layout/Sidebar';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';

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

beforeEach(() => {
  usePreferencesStore.getState().resetAllPrototypeData();
  vi.clearAllMocks();
  mocks.listProjects.mockResolvedValue([]);
  mocks.fetchConversations.mockResolvedValue(undefined);
});

afterEach(cleanup);

describe('Sidebar — header logo shrinks at large system font size', () => {
  it('shows the mondaiy wordmark at the default (medium) logo size', () => {
    render(
      <MemoryRouter initialEntries={['/briefing']}>
        <Sidebar />
      </MemoryRouter>,
    );

    const logoLink = screen.getByRole('link', { name: 'mondaiy' });
    expect(logoLink.textContent).toContain('mond');
    const mark = screen.getByAltText('Mondaiy');
    expect(mark.getAttribute('width')).toBe('26');
    expect(logoLink.querySelector('span')?.className).toContain('text-lg');
  });

  it('keeps the wordmark but shrinks icon and text once font size is set to large, leaving the toggle/search buttons unobstructed', () => {
    usePreferencesStore.setState((state) => ({
      accessibility: { ...state.accessibility, fontSize: 'large' },
    }));

    render(
      <MemoryRouter initialEntries={['/briefing']}>
        <Sidebar />
      </MemoryRouter>,
    );

    const logoLink = screen.getByRole('link', { name: 'mondaiy' });
    // Chữ vẫn còn nguyên, chỉ nhỏ lại — không ẩn wordmark.
    expect(logoLink.textContent).toContain('mond');
    const mark = screen.getByAltText('Mondaiy');
    expect(mark.getAttribute('width')).toBe('18');
    expect(logoLink.querySelector('span')?.className).toContain('text-sm');
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toBeTruthy();
  });
});
