// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { ProfilePage } from '../src/pages/ProfilePage';
import { useAuthStore } from '../src/stores/useAuthStore';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';

describe('ProfilePage Google avatar', () => {
  beforeEach(() => {
    window.localStorage.clear();
    usePreferencesStore.getState().clearWorkspaceUser();
    usePreferencesStore.getState().hydrateForUser('member@example.com', { name: 'Member' });
    useAuthStore.setState({
      user: {
        id: '42',
        name: 'Member',
        email: 'member@example.com',
        role: 'participant',
        avatarUrl: 'https://lh3.googleusercontent.com/a/profile-photo',
      },
      isAuthenticated: true,
      isBootstrapping: false,
    });
  });

  afterEach(() => cleanup());

  it('shows the Gmail profile picture when no custom avatar exists', () => {
    render(<ProfilePage />);

    expect(screen.getByRole('img', { name: 'Member' }).getAttribute('src')).toBe(
      'https://lh3.googleusercontent.com/a/profile-photo',
    );
  });
});
