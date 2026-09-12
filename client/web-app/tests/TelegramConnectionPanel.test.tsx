// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TelegramConnectionPanel } from '../src/pages/SourceLibraryPage';

const copy = {
  connected: 'Connected',
  notConnected: 'Not connected',
  connect: 'Connect',
  disconnect: 'Disconnect',
  title: 'Telegram assistant',
  connectedTitle: 'Your private delivery channel is ready',
  disconnectedTitle: 'Bring Mondaiy into Telegram',
  connectedBody: 'Mondaiy can now deliver your summaries.',
  disconnectedBody: 'Connect once to receive useful updates.',
  privateDelivery: 'Private to your account',
  summaryDelivery: 'Daily summaries',
  reminderDelivery: 'Deadline reminders',
};

describe('TelegramConnectionPanel', () => {
  afterEach(cleanup);

  it('shows the linked identity and delivery benefits after connection', async () => {
    const disconnect = vi.fn();
    const user = userEvent.setup();
    render(
      <TelegramConnectionPanel
        connection={{ provider: 'telegram', connected: true, accountLabel: 'an_test', expiresAt: null }}
        onConnect={vi.fn()}
        onDisconnect={disconnect}
        copy={copy}
      />,
    );

    expect(screen.getByText('@an_test')).toBeTruthy();
    expect(screen.getByText('Your private delivery channel is ready')).toBeTruthy();
    expect(screen.getByText('Private to your account')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Disconnect' }));
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it('offers a single clear connect action when disconnected', async () => {
    const connect = vi.fn();
    const user = userEvent.setup();
    render(
      <TelegramConnectionPanel
        connection={{ provider: 'telegram', connected: false, accountLabel: null, expiresAt: null }}
        onConnect={connect}
        onDisconnect={vi.fn()}
        copy={copy}
      />,
    );

    expect(screen.getByText('Bring Mondaiy into Telegram')).toBeTruthy();
    expect(screen.queryByText('@an_test')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Connect' }));
    expect(connect).toHaveBeenCalledOnce();
  });
});
