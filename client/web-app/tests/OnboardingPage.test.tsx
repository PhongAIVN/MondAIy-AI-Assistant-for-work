import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { OnboardingPage } from '../src/pages/OnboardingPage';
import { translations } from '../src/i18n/translations';

const { mocks } = vi.hoisted(() => ({
  mocks: {
    navigate: vi.fn(),
    signOut: vi.fn(),
    updateBriefingPreferences: vi.fn(),
    updateNotificationPreferences: vi.fn(),
    dismissOnboarding: vi.fn(),
    addToast: vi.fn(),
    listConnections: vi.fn(),
    createConnectIntent: vi.fn(),
    updateReminderPreferences: vi.fn(),
  },
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useLocation: () => ({ pathname: '/onboarding', search: '' }),
  };
});

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ language: 'en', t: translations.en }),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      user: { id: 'u1', name: 'Test', email: 't@test.dev', role: 'participant' },
      accessToken: 'access-token',
      signOut: mocks.signOut,
    }),
}));

vi.mock('../src/stores/usePreferencesStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/stores/usePreferencesStore')>();
  return {
    ...actual,
    usePreferencesStore: () => ({
      briefingPreferences: { briefingTime: '07:00 AM', timezone: 'Asia/Ho_Chi_Minh' },
      updateBriefingPreferences: mocks.updateBriefingPreferences,
      updateNotificationPreferences: mocks.updateNotificationPreferences,
      dismissOnboarding: mocks.dismissOnboarding,
    }),
  };
});

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ addToast: mocks.addToast }),
}));

vi.mock('../src/lib/connectionsApi', () => ({
  listConnections: mocks.listConnections,
  createConnectIntent: mocks.createConnectIntent,
}));

vi.mock('../src/lib/reminderApi', () => ({
  updateReminderPreferences: mocks.updateReminderPreferences,
}));

describe('OnboardingPage', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.listConnections.mockResolvedValue({ connections: [] });
    mocks.updateReminderPreferences.mockResolvedValue({});
    mocks.createConnectIntent.mockResolvedValue({ authorizeUrl: 'https://accounts.google.test/authorize' });
  });

  it('shows the 4-step flow: Welcome, About mondaiy, Connect & Privacy, Done', () => {
    mocks.listConnections.mockResolvedValue({ connections: [] });
    render(<OnboardingPage />);
    expect(screen.getByText('Welcome')).toBeTruthy();
    expect(screen.getByText('About mondaiy')).toBeTruthy();
    expect(screen.getByText('Connect & Privacy')).toBeTruthy();
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.getByText('Hi there, welcome to mondaiy!')).toBeTruthy();
  });

  it('shows the 3 "what mondaiy does" cards on the About step', () => {
    mocks.listConnections.mockResolvedValue({ connections: [] });
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText('About mondaiy'));

    expect(screen.getByText('Smart task management')).toBeTruthy();
    expect(screen.getByText('Context-aware')).toBeTruthy();
    expect(screen.getByText("Don't let deadlines run you.")).toBeTruthy();
  });

  it('offers Discord and Jira as other sources with the same big-button style as Google, and drops VLearn', () => {
    mocks.listConnections.mockResolvedValue({ connections: [] });
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText('Connect & Privacy'));

    expect(screen.queryByText(/VLearn/)).toBeNull();
    expect(screen.getByText('Discord Server')).toBeTruthy();
    expect(screen.getByText('Jira')).toBeTruthy();

    const connectButtons = screen.getAllByRole('button', { name: 'Connect' });
    expect(connectButtons).toHaveLength(2);

    fireEvent.click(connectButtons[0]);
    expect(mocks.createConnectIntent).toHaveBeenCalledWith('discord', expect.any(String), 'access-token');

    fireEvent.click(connectButtons[1]);
    expect(mocks.createConnectIntent).toHaveBeenCalledWith('jira', expect.any(String), 'access-token');
  });

  it('offers a Google-first connect CTA on the Connect & Privacy step, alongside privacy consent', () => {
    mocks.listConnections.mockResolvedValue({ connections: [] });
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText('Connect & Privacy'));

    fireEvent.click(screen.getByRole('button', { name: 'Connect Google' }));
    expect(mocks.createConnectIntent).toHaveBeenCalledWith('google', expect.any(String), 'access-token');

    expect(screen.getByLabelText('I consent to read-only monitoring of my connected program sources.')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Read the full Privacy Policy/ })).toHaveProperty('href', expect.stringContaining('/policy'));
  });

  it('shows Google as already connected instead of offering the CTA again', async () => {
    mocks.listConnections.mockResolvedValue({ connections: [{ provider: 'google', connected: true }] });
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText('Connect & Privacy'));

    expect((await screen.findAllByText('Connected')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Connect Google' })).toBeNull();
  });

  it('removes the redundant Skip button from the Welcome and About steps', () => {
    mocks.listConnections.mockResolvedValue({ connections: [] });
    render(<OnboardingPage />);

    expect(screen.queryByRole('button', { name: 'Skip Step' })).toBeNull();
    fireEvent.click(screen.getByText('About mondaiy'));
    expect(screen.queryByRole('button', { name: 'Skip Step' })).toBeNull();
  });

  it('offers browse mode beside Google and completes onboarding without connecting a source', () => {
    mocks.listConnections.mockResolvedValue({ connections: [] });
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText('Connect & Privacy'));

    const googleChoice = screen.getByTestId('google-onboarding-choice');
    const browseChoice = screen.getByTestId('browse-onboarding-choice');
    expect(browseChoice.className).toBe(googleChoice.className);
    expect(screen.queryByText(/required before you can use mondaiy/i)).toBeNull();
    const continueButton = screen.getByRole('button', { name: 'Continue' });
    expect(continueButton).toHaveProperty('disabled', true);
    fireEvent.click(continueButton);
    expect(mocks.dismissOnboarding).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Explore mondaiy' }));

    expect(mocks.dismissOnboarding).toHaveBeenCalledTimes(1);
    expect(mocks.navigate).toHaveBeenCalledWith('/briefing');
    expect(mocks.createConnectIntent).not.toHaveBeenCalled();
    expect(mocks.updateReminderPreferences).not.toHaveBeenCalled();
    expect(mocks.addToast).toHaveBeenCalledWith(expect.objectContaining({
      type: 'success',
      message: expect.stringContaining('no connected sources'),
    }));
  });

  it('completes and persists real defaults only once Google is connected', async () => {
    mocks.listConnections.mockResolvedValue({ connections: [{ provider: 'google', connected: true }] });
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText('Connect & Privacy'));
    await screen.findAllByText('Connected');

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Launch Daily Briefing' }));

    expect(mocks.updateNotificationPreferences).toHaveBeenCalledWith({ reminderLeadTime: '24h' });
    expect(mocks.updateBriefingPreferences).toHaveBeenCalledWith({ briefingTime: '07:00 AM' });
    await vi.waitFor(() => expect(mocks.updateReminderPreferences).toHaveBeenCalledWith({ dailyBriefHour: 7 }, 'access-token'));
    await vi.waitFor(() => expect(mocks.dismissOnboarding).toHaveBeenCalled());
    expect(mocks.navigate).toHaveBeenCalledWith('/briefing');
  });

  it('keeps English and Vietnamese onboarding contracts aligned', () => {
    expect(Object.keys(translations.en.onboarding).sort()).toEqual(
      Object.keys(translations.vi.onboarding).sort(),
    );
  });
});
