// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';

import { SignInPage } from '../src/pages/auth/SignInPage';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';

const { signIn } = vi.hoisted(() => ({ signIn: vi.fn() }));

const LocationProbe = () => {
  const location = useLocation();
  return (
    <>
      <output data-testid="location">{`${location.pathname}${location.search}`}</output>
      <output data-testid="location-state">{JSON.stringify(location.state)}</output>
    </>
  );
};

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({ signIn }),
}));

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: {
      auth: {
        welcomeBack: 'Welcome back',
        signInSubtitle: 'Sign in to continue',
        emailLabel: 'Email',
        passwordLabel: 'Password',
        forgotPasswordQuestion: 'Forgot password?',
        rememberMe: 'Remember me',
        noAccountQuestion: 'No account?',
        requiredFieldError: 'Required',
        invalidCredentials: 'Invalid credentials',
        signInFailed: 'Sign in failed',
        continueWithGoogle: 'Continue with Google',
      },
      actions: { signIn: 'Sign in', signUp: 'Sign up' },
    },
  }),
}));

describe('SignInPage', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    usePreferencesStore.setState({ onboardingDismissed: false });
  });

  it('passes the unchecked Remember me choice to the auth store', async () => {
    const user = userEvent.setup();
    signIn.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={['/sign-in']}>
        <SignInPage />
      </MemoryRouter>,
    );

    await user.type(screen.getByPlaceholderText('alex.nguyen@example.com'), 'member@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
    await user.click(screen.getByLabelText('Remember me'));
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(signIn).toHaveBeenCalledWith('member@example.com', 'password', false);
  });

  it('preserves the Telegram connection query after sign-in', async () => {
    const user = userEvent.setup();
    signIn.mockResolvedValue(undefined);
    usePreferencesStore.setState({ onboardingDismissed: true });
    render(
      <MemoryRouter
        initialEntries={[{
          pathname: '/sign-in',
          state: { from: { pathname: '/sources', search: '?connect=telegram' } },
        }]}
      >
        <SignInPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await user.type(screen.getByPlaceholderText('alex.nguyen@example.com'), 'member@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/sources?connect=telegram'));
  });

  it('carries the Telegram return path into onboarding for a new user', async () => {
    const user = userEvent.setup();
    signIn.mockResolvedValue(undefined);
    render(
      <MemoryRouter
        initialEntries={[{
          pathname: '/sign-in',
          state: { from: { pathname: '/sources', search: '?connect=telegram' } },
        }]}
      >
        <SignInPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await user.type(screen.getByPlaceholderText('alex.nguyen@example.com'), 'new@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/onboarding'));
    expect(screen.getByTestId('location-state').textContent).toContain('/sources?connect=telegram');
  });
});
