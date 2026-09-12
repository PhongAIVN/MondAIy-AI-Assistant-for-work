// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AutoSyncPreferenceControl } from '../src/pages/SourceLibraryPage';

describe('Source Library automatic sync preference', () => {
  afterEach(cleanup);

  it('shows the saved consent and sends the changed value when toggled', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <AutoSyncPreferenceControl
        language="en"
        preference={{ autoSyncEnabled: true, userAutoSyncEnabled: true, autoSyncIntervalMinutes: 180 }}
        loading={false}
        saving={false}
        error={null}
        onChange={onChange}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('true');
    expect(screen.getByText(/latest successful manual sync/)).toBeTruthy();
    expect(screen.getByText(/every 3h/)).toBeTruthy();

    await user.click(screen.getByRole('switch'));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('keeps consent visible when the environment scheduler is disabled', () => {
    render(
      <AutoSyncPreferenceControl
        language="en"
        preference={{ autoSyncEnabled: false, userAutoSyncEnabled: true, autoSyncIntervalMinutes: 180 }}
        loading={false}
        saving={false}
        error={null}
        onChange={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('true');
    expect(screen.getByText(/not enabled for this environment/)).toBeTruthy();
  });

  it('disables the control while the preference is loading or saving', () => {
    render(
      <AutoSyncPreferenceControl
        language="en"
        preference={null}
        loading
        saving={false}
        error={null}
        onChange={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('switch').hasAttribute('disabled')).toBe(true);
  });

  it('keeps the control disabled and offers retry when saving fails', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <AutoSyncPreferenceControl
        language="en"
        preference={{ autoSyncEnabled: true, userAutoSyncEnabled: true, autoSyncIntervalMinutes: 180 }}
        loading={false}
        saving={false}
        error="Could not save preference."
        onChange={vi.fn()}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByRole('switch').hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('alert').textContent).toContain('Could not save preference.');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('explains the saved-off state without suggesting background work continues', () => {
    render(
      <AutoSyncPreferenceControl
        language="en"
        preference={{ autoSyncEnabled: false, userAutoSyncEnabled: false, autoSyncIntervalMinutes: 180 }}
        loading={false}
        saving={false}
        error={null}
        onChange={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText(/^Off\. Turn it on/)).toBeTruthy();
  });
});
