import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import {
  getFeatureAnnouncementCopy,
  isFeatureAnnouncementRead,
  markFeatureAnnouncementRead,
} from '../src/lib/featureAnnouncement';
import { NotificationsPage } from '../src/pages/NotificationsPage';

const mocks = vi.hoisted(() => ({
  fetchDue: vi.fn(),
  markAllRead: vi.fn(),
  markRead: vi.fn(),
}));

const featureAnnouncement = {
  id: 'feature-announcement-2026-08-17',
  reminderId: null,
  kind: 'feature_announcement' as const,
  title: 'Feature announcement',
  milestone: 'release',
  taskId: null,
  dueAt: null,
  scheduledAt: '2026-08-17T00:00:00Z',
  evidenceDeepLink: null,
  payload: {},
  isRead: false,
};

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ language: 'vi' }),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({ accessToken: 'access-token' }),
}));

vi.mock('../src/stores/useNotificationsStore', () => ({
  useNotificationsStore: () => ({
    items: [featureAnnouncement],
    isLoading: false,
    fetchDue: mocks.fetchDue,
    markAllRead: mocks.markAllRead,
    markRead: mocks.markRead,
  }),
}));

const LocationProbe = () => <output data-testid="location">{useLocation().pathname}</output>;

describe('feature announcement notification', () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('provides the update content in Vietnamese and English', () => {
    expect(getFeatureAnnouncementCopy('vi')).toMatchObject({ title: 'Có gì mới trên mondaiy', link: 'Xem Routine mới' });
    expect(getFeatureAnnouncementCopy('en')).toMatchObject({ title: "What's new on mondaiy", link: 'View new routines' });
  });

  it('remembers when the notification has been read', () => {
    expect(isFeatureAnnouncementRead()).toBe(false);
    markFeatureAnnouncementRead();
    expect(isFeatureAnnouncementRead()).toBe(true);
  });

  it('shows the announcement in Notifications and opens Routines when read', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <NotificationsPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await user.click(screen.getByText('Có gì mới trên mondaiy'));
    expect(mocks.markRead).toHaveBeenCalledWith('access-token', featureAnnouncement);
    expect(screen.getByTestId('location').textContent).toBe('/routines');
  });
});
