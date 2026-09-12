// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../src/components/layout/Sidebar';
import { ProjectsPage } from '../src/pages/ProjectsPage';
import type { Project } from '../src/lib/projectsApi';
import type { Conversation } from '../src/types/conversation';

const mocks = vi.hoisted(() => ({
  language: 'vi' as 'vi' | 'en',
  projects: [] as Project[],
  conversations: [] as Conversation[],
  listProjects: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  deleteProject: vi.fn(),
  fetchConversations: vi.fn(),
  deleteConversation: vi.fn(),
  renameConversation: vi.fn(),
  setFavorite: vi.fn(),
  addToast: vi.fn(),
  signOut: vi.fn(),
  setPalette: vi.fn(),
  requestAppTour: vi.fn(),
}));

vi.mock('../src/lib/projectsApi', () => ({
  listProjects: mocks.listProjects,
  createProject: mocks.createProject,
  updateProject: mocks.updateProject,
  deleteProject: mocks.deleteProject,
  addConversationToProject: vi.fn(),
  removeConversationFromProject: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector?: (state: {
    user: { id: string; name: string; email: string; role: string };
    accessToken: string;
    signOut: typeof mocks.signOut;
  }) => unknown) => {
    const state = {
      user: { id: 'user-1', name: 'Thái', email: 'thai@example.com', role: 'participant' },
      accessToken: 'access-token',
      signOut: mocks.signOut,
    };
    return selector ? selector(state) : state;
  },
}));

vi.mock('../src/stores/useConversationStore', () => ({
  useConversationStore: () => ({
    conversations: mocks.conversations,
    fetchConversations: mocks.fetchConversations,
    deleteConversation: mocks.deleteConversation,
    renameConversation: mocks.renameConversation,
    setFavorite: mocks.setFavorite,
    generatingIds: new Set<string>(),
  }),
}));

vi.mock('../src/stores/usePreferencesStore', () => {
  const state = {
    get language() {
      return mocks.language;
    },
    palette: 'default',
    setPalette: mocks.setPalette,
    profile: { name: 'Thái', avatarUrl: undefined },
    accessibility: { fontSize: 'medium' as const },
  };
  return {
    PALETTES: [],
    usePreferencesStore: (selector?: (value: typeof state) => unknown) =>
      selector ? selector(state) : state,
  };
});

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: (selector?: (state: { addToast: typeof mocks.addToast }) => unknown) => {
    const state = { addToast: mocks.addToast };
    return selector ? selector(state) : state;
  },
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

const PROJECT: Project = {
  id: 7,
  name: 'Luận văn',
  description: 'Tài liệu nghiên cứu',
  color: 'plum',
  conversationCount: 1,
  createdAt: '2026-08-26T00:00:00Z',
  updatedAt: '2026-08-26T00:00:00Z',
};

const conversation = (projectId: number | null): Conversation => ({
  id: '11',
  title: 'Trao đổi nghiên cứu',
  dateGroup: 'today',
  lastUpdated: '2026-08-26T10:00:00+07:00',
  messageCount: 1,
  messages: [],
  messagesLoaded: true,
  projectId,
  isFavorite: false,
});

const renderSidebar = () =>
  render(
    <MemoryRouter initialEntries={['/briefing']}>
      <Routes>
        <Route path="/briefing" element={<Sidebar />} />
        <Route path="/projects" element={<div>PROJECTS PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );

const renderProjectsPage = () =>
  render(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  mocks.language = 'vi';
  mocks.projects = [];
  mocks.conversations = [];
  mocks.listProjects.mockReset().mockImplementation(async () => mocks.projects);
  mocks.fetchConversations.mockReset().mockResolvedValue(undefined);
  mocks.createProject.mockReset();
  mocks.updateProject.mockReset();
  mocks.deleteProject.mockReset();
  vi.clearAllMocks();
});

afterEach(cleanup);

describe('Sidebar — Projects navigation', () => {
  it('keeps Projects navigation available when project inventory is empty', async () => {
    const user = userEvent.setup();
    renderSidebar();

    const projectsLink = await screen.findByRole('link', { name: 'Dự án' });
    expect(projectsLink.getAttribute('href')).toBe('/projects');
    expect(screen.queryByRole('link', { name: PROJECT.name })).toBeNull();

    await user.click(projectsLink);
    expect(await screen.findByText('PROJECTS PAGE')).toBeTruthy();
  });

  it('keeps Projects navigation and renders the project list when inventory is non-empty', async () => {
    mocks.projects = [PROJECT];
    renderSidebar();

    expect(await screen.findByRole('link', { name: 'Dự án' })).toBeTruthy();
    const projectLink = await screen.findByRole('link', { name: PROJECT.name });
    expect(projectLink.getAttribute('href')).toBe('/projects/7');
    expect(screen.getByRole('button', { name: 'Dự án' }).getAttribute('aria-expanded')).toBe('true');
  });

  it('does not show an unassigned reminder when no project exists', async () => {
    mocks.conversations = [conversation(null)];
    renderSidebar();

    await waitFor(() => expect(mocks.listProjects).toHaveBeenCalledOnce());
    expect(screen.queryByTitle('Chưa xếp vào dự án')).toBeNull();
  });

  it('shows an unassigned reminder when projects exist and the conversation is unassigned', async () => {
    mocks.projects = [PROJECT];
    mocks.conversations = [conversation(null)];
    renderSidebar();

    expect(await screen.findByTitle('Chưa xếp vào dự án')).toBeTruthy();
  });

  it('does not show an unassigned reminder for a conversation already in a project', async () => {
    mocks.projects = [PROJECT];
    mocks.conversations = [conversation(PROJECT.id)];
    renderSidebar();

    await screen.findByRole('link', { name: PROJECT.name });
    expect(screen.queryByTitle('Chưa xếp vào dự án')).toBeNull();
  });
});

describe('ProjectsPage — empty state', () => {
  it('shows an actionable Vietnamese empty state and focuses project creation', async () => {
    const user = userEvent.setup();
    renderProjectsPage();

    expect(await screen.findByText(/Chưa có dự án nào/)).toBeTruthy();
    const createFirstButton = screen.getByRole('button', { name: 'Tạo dự án đầu tiên' });
    expect(createFirstButton.className).not.toMatch(/opacity-0|invisible|hidden/);

    await user.click(createFirstButton);
    expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Tên dự án' }));
  });

  it('shows the actionable empty state in English', async () => {
    mocks.language = 'en';
    renderProjectsPage();

    expect(await screen.findByText(/No projects yet/)).toBeTruthy();
    const createFirstButton = screen.getByRole('button', { name: 'Create first project' });
    expect(createFirstButton.className).not.toMatch(/opacity-0|invisible|hidden/);
  });
});
