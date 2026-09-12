// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatTaskSuggestionCard } from '../src/components/briefing/ChatTaskSuggestionCard';

const mocks = vi.hoisted(() => ({ createTaskFromSuggestion: vi.fn() }));
vi.mock('../src/lib/tasksApi', () => ({ createTaskFromSuggestion: mocks.createTaskFromSuggestion }));

const suggestion = {
  title: 'Nộp báo cáo',
  detail: 'Gửi PDF cho mentor',
  dueAt: '2026-08-14T09:00:00+07:00',
  allDay: false,
  source: 'Gmail',
};

describe('ChatTaskSuggestionCard', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('does not create anything until the user clicks Add task', async () => {
    mocks.createTaskFromSuggestion.mockResolvedValue({ id: 9, status: 'proposed' });
    const user = userEvent.setup();
    render(
      <ChatTaskSuggestionCard
        suggestion={suggestion}
        accessToken="access-token"
        language="vi"
        onOpenTasks={vi.fn()}
      />,
    );

    expect(mocks.createTaskFromSuggestion).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Thêm task' }));
    await waitFor(() => expect(mocks.createTaskFromSuggestion).toHaveBeenCalledWith(suggestion, 'access-token'));
    expect(screen.getByRole('button', { name: /Đã thêm/ })).toBeTruthy();
  });
});
