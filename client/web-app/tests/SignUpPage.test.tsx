// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

import { SignUpPage } from '../src/pages/auth/SignUpPage';

const { signUp } = vi.hoisted(() => ({ signUp: vi.fn() }));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({ signUp }),
}));

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: {
      auth: {
        signUpTitle: 'Create your account',
        signUpSubtitle: 'Start your journey',
        fullNameLabel: 'Full name',
        emailLabel: 'Email',
        passwordLabel: 'Password',
        confirmPasswordLabel: 'Confirm password',
        showPassword: 'Show password',
        hidePassword: 'Hide password',
        agreeToTerms: 'I agree to the Terms and Privacy Policy',
        orDivider: 'or',
        hasAccountQuestion: 'Already have an account?',
        requiredFieldError: 'Required',
        passwordTooShortError: 'Password must be at least 8 characters.',
        passwordMatchError: 'Passwords do not match.',
        agreeTermsError: 'You must agree to the Terms and Privacy Policy to continue.',
        emailTaken: 'Email already registered.',
        signUpFailed: 'Sign up failed.',
      },
      actions: { signIn: 'Sign in', signUp: 'Sign up' },
    },
  }),
}));

describe('SignUpPage', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('keeps the submit button disabled until the password is long enough and confirmed', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SignUpPage />
      </MemoryRouter>,
    );

    const submit = screen.getByRole('button', { name: 'Sign up' }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    const [passwordInput, confirmInput] = screen.getAllByPlaceholderText('••••••••');
    await user.type(passwordInput, 'short');
    expect(submit.disabled).toBe(true);

    await user.clear(passwordInput);
    await user.type(passwordInput, 'correct-horse-1');
    expect(submit.disabled).toBe(true);

    await user.type(confirmInput, 'not-the-same');
    expect(submit.disabled).toBe(true);

    await user.clear(confirmInput);
    await user.type(confirmInput, 'correct-horse-1');
    expect(submit.disabled).toBe(false);
  });

  it('toggles password visibility independently for password and confirm password', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SignUpPage />
      </MemoryRouter>,
    );

    const [passwordInput, confirmInput] = screen.getAllByPlaceholderText('••••••••') as HTMLInputElement[];
    expect(passwordInput.type).toBe('password');
    expect(confirmInput.type).toBe('password');

    await user.click(screen.getAllByLabelText('Show password')[0]);
    expect(passwordInput.type).toBe('text');
    expect(confirmInput.type).toBe('password');
  });

  it('does not rely on native browser validation bubbles', () => {
    render(
      <MemoryRouter>
        <SignUpPage />
      </MemoryRouter>,
    );

    const form = screen.getByRole('button', { name: 'Sign up' }).closest('form') as HTMLFormElement;
    expect(form.noValidate).toBe(true);
  });
});
